'use strict';
// Frida 17: no Java/ObjC bridge globals, and Module.findExportByName(null, ..) is gone.
// Everything below goes through the raw JNI function tables instead.
const PS = Process.pointerSize;
const uniqDlsym = new Set(), uniqDlopen = new Set();
let dlsymCalls = 0, dlopenCalls = 0, registered = 0, tables = 0;

function emit(type, payload) { payload.type = type; send(payload); }

function findExport(name) {
  if (typeof Module.findGlobalExportByName === 'function') return Module.findGlobalExportByName(name);
  if (typeof Module.findExportByName === 'function') return Module.findExportByName(null, name);
  return null;
}
function moduleAt(addr) {
  try { if (typeof Process.findModuleByAddress === 'function') return Process.findModuleByAddress(addr); } catch (e) {}
  return null;
}
const moduleCache = [];
function describe(addr) {
  for (let i = 0; i < moduleCache.length; i++) {
    const c = moduleCache[i];
    if (addr.compare(c.base) >= 0 && addr.compare(c.end) < 0) return { lib: c.name, offset: addr.sub(c.base).toString() };
  }
  const m = moduleAt(addr);
  if (!m) return { lib: null, offset: null };
  moduleCache.push({ name: m.name, base: m.base, end: m.base.add(m.size) });
  return { lib: m.name, offset: addr.sub(m.base).toString() };
}

['dlopen', 'android_dlopen_ext'].forEach(function (name) {
  const p = findExport(name);
  if (!p) return;
  Interceptor.attach(p, {
    onEnter: function (args) { this.path = args[0].isNull() ? null : args[0].readCString(); },
    onLeave: function (ret) {
      dlopenCalls++;
      const key = this.path + '|' + (!ret.isNull());
      if (uniqDlopen.has(key)) return;
      uniqDlopen.add(key);
      emit('dlopen', { path: this.path, ok: !ret.isNull(), via: name });
    }
  });
});

let dlsymListener = null;
function enableDlsym() {
  const dlsymPtr = findExport('dlsym');
  if (!dlsymPtr || dlsymListener) return false;
  dlsymListener = Interceptor.attach(dlsymPtr, {
    onEnter: function (args) { this.sym = args[1].isNull() ? null : args[1].readCString(); },
    onLeave: function (ret) {
      dlsymCalls++;
      const key = this.sym + '|' + (!ret.isNull());
      if (uniqDlsym.has(key)) return;
      uniqDlsym.add(key);
      emit('dlsym', { symbol: this.sym, resolved: !ret.isNull(), caller_lib: describe(this.returnAddress).lib });
    }
  });
  emit('status', { message: 'dlsym hook installed' });
  return true;
}

// --- JNI vtable indices (JNINativeInterface / JNIInvokeInterface) ---
const VM_ATTACH = 4, VM_DETACH = 5, VM_GET_ENV = 6;
const FIND_CLASS = 6, GET_METHOD_ID = 33, CALL_OBJECT_METHOD = 34;
const GET_STRING_UTF = 169, RELEASE_STRING_UTF = 170, REGISTER_NATIVES = 215;

function javaVm() {
  // Frida 17 moved the module lookups around; go straight for the global export.
  let sym = findExport('JNI_GetCreatedJavaVMs');
  if (!sym) {
    let libart = null;
    try { libart = Process.enumerateModules().filter(function (m) { return m.name === 'libart.so'; })[0] || null; } catch (e) {}
    if (libart) {
      try { sym = libart.findExportByName('JNI_GetCreatedJavaVMs'); } catch (e) {}
      if (!sym) { try { sym = libart.getExportByName('JNI_GetCreatedJavaVMs'); } catch (e) {} }
    }
  }
  if (!sym) return null;
  const call = new NativeFunction(sym, 'int', ['pointer', 'int', 'pointer']);
  const vms = Memory.alloc(PS), count = Memory.alloc(4);
  if (call(vms, 1, count) !== 0 || count.readInt() < 1) return null;
  return vms.readPointer();
}

function envFor(vm) {
  const table = vm.readPointer();
  const out = Memory.alloc(PS);
  const getEnv = new NativeFunction(table.add(VM_GET_ENV * PS).readPointer(), 'int', ['pointer', 'pointer', 'int']);
  if (getEnv(vm, out, 0x00010006) === 0 && !out.readPointer().isNull()) return { env: out.readPointer(), attached: false };
  // Frida's own thread is not attached to the VM, so GetEnv gives JNI_EDETACHED (-2).
  const attach = new NativeFunction(table.add(VM_ATTACH * PS).readPointer(), 'int', ['pointer', 'pointer', 'pointer']);
  if (attach(vm, out, NULL) === 0 && !out.readPointer().isNull()) return { env: out.readPointer(), attached: true };
  return null;
}

function detach(vm) {
  try {
    const d = new NativeFunction(vm.readPointer().add(VM_DETACH * PS).readPointer(), 'int', ['pointer']);
    d(vm);
  } catch (e) {}
}

let namer = null, namerTries = 0;
function buildNamer(env) {
  const t = env.readPointer();
  const fn = function (index, ret, args) { return new NativeFunction(t.add(index * PS).readPointer(), ret, args); };
  const findClass = fn(FIND_CLASS, 'pointer', ['pointer', 'pointer']);
  const getMethodId = fn(GET_METHOD_ID, 'pointer', ['pointer', 'pointer', 'pointer']);
  // CallObjectMethod is variadic; with zero varargs the three named args still land in x0-x2.
  const callObject = fn(CALL_OBJECT_METHOD, 'pointer', ['pointer', 'pointer', 'pointer']);
  const getChars = fn(GET_STRING_UTF, 'pointer', ['pointer', 'pointer', 'pointer']);
  const release = fn(RELEASE_STRING_UTF, 'void', ['pointer', 'pointer', 'pointer']);
  const klass = findClass(env, Memory.allocUtf8String('java/lang/Class'));
  if (klass.isNull()) return null;
  // jmethodID is a stable ArtMethod pointer, safe to cache; the jclass local ref is not.
  const getName = getMethodId(env, klass, Memory.allocUtf8String('getName'), Memory.allocUtf8String('()Ljava/lang/String;'));
  if (getName.isNull()) return null;
  return function (envNow, jclazz) {
    try {
      const jstr = callObject(envNow, jclazz, getName);
      if (jstr.isNull()) return '?';
      const chars = getChars(envNow, jstr, NULL);
      const text = chars.isNull() ? '?' : chars.readCString();
      if (!chars.isNull()) release(envNow, jstr, chars);
      return text;
    } catch (e) { return '?'; }
  };
}

function install() {
  const vm = javaVm();
  if (!vm) return false;
  const got = envFor(vm);
  if (!got) return false;
  const target = got.env.readPointer().add(REGISTER_NATIVES * PS).readPointer();
  if (got.attached) detach(vm);
  Interceptor.attach(target, {
    onEnter: function (args) {
      const envNow = args[0], methods = args[2], count = args[3].toInt32();
      const out = [];
      for (let i = 0; i < count && i < 4096; i++) {
        const base = methods.add(i * PS * 3);
        try {
          const fn = base.add(PS * 2).readPointer();
          const where = describe(fn);
          out.push({
            name: base.readPointer().readCString(),
            signature: base.add(PS).readPointer().readCString(),
            lib: where.lib, offset: where.offset
          });
        } catch (e) { break; }
      }
      tables++; registered += out.length;
      // The earliest registrations run in contexts where FindClass fails; keep retrying.
      if (!namer && namerTries < 12) {
        namerTries++;
        try { namer = buildNamer(envNow) || null; } catch (e) { namer = null; }
      }
      let clazz = '?';
      if (namer) { try { clazz = namer(envNow, args[1]); } catch (e) { clazz = '?'; } }
      emit('registerNatives', { clazz: clazz, count: count, methods: out });
    }
  });
  emit('status', { message: 'RegisterNatives hook installed at ' + target });
  return true;
}

(function retry(n) {
  let ok = false;
  try { ok = install(); } catch (e) { emit('error', { where: 'install', message: '' + e }); return; }
  if (ok) return;
  if (n > 400) { emit('error', { where: 'retry', message: 'ART never became available' }); return; }
  setTimeout(function () { retry(n + 1); }, 25);
})(0);

rpc.exports = {
  enabledlsym: function () { return enableDlsym(); },
  stats: function () {
    return { dlopenCalls: dlopenCalls, dlsymCalls: dlsymCalls, uniqueDlopen: uniqDlopen.size,
             uniqueDlsym: uniqDlsym.size, registrationTables: tables, registeredMethods: registered };
  }
};
emit('status', { message: 'native hooks installed' });
