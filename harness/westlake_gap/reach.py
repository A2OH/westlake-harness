"""Static startup reachability: which platform contracts an APK touches on its way to the first screens.

A gap list says what is missing. It does not say which of it stands between process start and a
usable screen, so bring-up falls back to launching and seeing what breaks next. This pass answers
that from the bytecode, before any launch.

It builds a call graph over every dex in the APK and runs a rapid-type-analysis (RTA) reachability
from the things Android itself starts, in the order it starts them:

- **stage 0, process start**: the `Application` class, the `AppComponentFactory`, every
  main-process content provider, and every app class named in manifest `<meta-data>` (initializers
  and registrars exist to be loaded reflectively by whoever reads the manifest);
- **stage 1, first activity**: the launcher activity;
- **stage 2, next screens**: manifest components referenced (`const-class`, or their name as a
  string) from code reached so far;
- **stage 3, later**: the transitive closure over further components.

RTA rules: a virtual or interface call dispatches to the implementations in classes instantiated
so far (plus the statically declared target); instantiating a class makes every method that
overrides a *platform* supertype's method reachable, because the framework may call it (lifecycle
methods, `Runnable.run`, listeners); touching a class reaches its `<clinit>`.

The result over-approximates what one run executes and under-approximates reflection it cannot
see (classes named only in layouts or navigation graphs, computed `Class.forName`). Both are
measurable: `trace-compare` checks it against a method trace recorded on a real device.
"""

from __future__ import annotations

import gc
from array import array
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Iterable

from .scanner import DEX, compact_descriptor, dex_blobs, is_platform_type, quiet_androguard

import re

# Callbacks the framework only delivers in response to the user. Instantiating a listener does not
# put its handler on the startup path; without this, every screen a button leads to counts as
# "process start".
USER_INPUT_CALLBACK = re.compile(
    r"^on(Click|LongClick|Touch|TouchEvent|InterceptTouchEvent|Key|KeyDown|KeyUp|KeyLongPress|GenericMotion|Hover|Drag|"
    r"ContextClick|MenuItemClick|OptionsItemSelected|ContextItemSelected|NavigationItemSelected|ItemClick|ItemLongClick|"
    r"ItemSelected|NothingSelected|CheckedChanged|EditorAction|BackPressed|ActivityResult|RequestPermissionsResult|"
    r"NewIntent|QueryTextSubmit|QueryTextChange|ProgressChanged|StartTrackingTouch|StopTrackingTouch|Fling|Scroll|"
    r"LongPress|SingleTapUp|SingleTapConfirmed|DoubleTap|Down|ShowPress|Swipe|Refresh|TabSelected|TabReselected|"
    r"PageSelected|DateSet|TimeSet|RatingChanged|FocusChange|TextChanged|CreateContextMenu|PrepareOptionsMenu)\("
    r"|^(afterTextChanged|beforeTextChanged|dispatchTouchEvent|dispatchKeyEvent|performClick)\("
)

UNREACHED = 255
STAGE_NAMES = {0: "process start", 1: "first activity", 2: "next screens", 3: "later", UNREACHED: "not reached statically"}

_INVOKE_VIRTUAL = {0x6E, 0x72, 0x74, 0x78}          # virtual, interface and their /range forms
_INVOKE_EXACT = {0x6F, 0x70, 0x71, 0x75, 0x76, 0x77}  # super, direct, static and their /range forms
_NEW_INSTANCE, _CONST_CLASS, _CHECK_CAST, _INSTANCE_OF = 0x22, 0x1C, 0x1F, 0x20
_CONST_STRING = {0x1A, 0x1B}
_STATIC_FIELD = set(range(0x60, 0x6E))
_INSTANCE_FIELD = set(range(0x52, 0x60))
_FLAG_STATIC, _FLAG_NATIVE, _FLAG_CODE = 1, 2, 4


class Graph:
    """Interned call graph of one APK. Classes, signatures and methods are small integers."""

    def __init__(self) -> None:
        self.cls_ids: dict[str, int] = {}
        self.cls_names: list[str] = []
        self.sig_ids: dict[str, int] = {}
        self.sig_names: list[str] = []
        self.meth_ids: dict[tuple[int, int], int] = {}
        self.m_cls = array("I")
        self.m_sig = array("I")
        self.m_flags = bytearray()
        self.calls: dict[int, array] = {}     # mid -> [target mid * 2 + is_virtual]
        self.news: dict[int, array] = {}      # mid -> instantiated class ids
        self.comps: dict[int, array] = {}     # mid -> manifest component class ids referenced
        self.defined: set[int] = set()        # app-defined class ids
        self.supers: dict[int, int] = {}
        self.ifaces: dict[int, list[int]] = {}
        self.cls_methods: dict[int, dict[int, int]] = defaultdict(dict)

    def cls(self, name: str) -> int:
        cid = self.cls_ids.get(name)
        if cid is None:
            cid = self.cls_ids[name] = len(self.cls_names)
            self.cls_names.append(name)
        return cid

    def sig(self, name: str) -> int:
        sid = self.sig_ids.get(name)
        if sid is None:
            sid = self.sig_ids[name] = len(self.sig_names)
            self.sig_names.append(name)
        return sid

    def meth(self, cid: int, sid: int) -> int:
        mid = self.meth_ids.get((cid, sid))
        if mid is None:
            mid = self.meth_ids[(cid, sid)] = len(self.m_cls)
            self.m_cls.append(cid)
            self.m_sig.append(sid)
            self.m_flags.append(0)
        return mid

    def name(self, mid: int) -> str:
        return f"{self.cls_names[self.m_cls[mid]]}->{self.sig_names[self.m_sig[mid]]}"


def build_graph(path: Path, component_names: Iterable[str] = ()) -> Graph:
    """One pass over every dex: hierarchy, call edges, instantiations and component references."""
    quiet_androguard()
    g = Graph()
    dotted = {name: "L" + name.replace(".", "/") + ";" for name in component_names}
    component_desc = set(dotted.values())
    clinit = g.sig("<clinit>()V")

    for _dex_name, blob in dex_blobs(path):
        dex = DEX(blob)
        method_cache: dict[int, int] = {}
        type_cache: dict[int, str] = {}

        def type_at(idx: int) -> str:
            value = type_cache.get(idx)
            if value is None:
                value = type_cache[idx] = str(dex.get_cm_type(idx)).lstrip("[")
            return value

        def method_at(idx: int) -> int:
            mid = method_cache.get(idx)
            if mid is None:
                owner, name, proto = dex.get_cm_method(idx)
                mid = method_cache[idx] = g.meth(g.cls(str(owner).lstrip("[")), g.sig(f"{name}{compact_descriptor(proto)}"))
            return mid

        for class_def in dex.get_classes():
            cid = g.cls(str(class_def.get_name()))
            if cid in g.defined:
                continue  # first definition wins, as in the class loader
            g.defined.add(cid)
            parent = str(class_def.get_superclassname() or "")
            if parent:
                g.supers[cid] = g.cls(parent)
            g.ifaces[cid] = [g.cls(str(item)) for item in class_def.get_interfaces()]
            for method in class_def.get_methods():
                sid = g.sig(f"{method.get_name()}{compact_descriptor(method.get_descriptor())}")
                mid = g.meth(cid, sid)
                g.cls_methods[cid][sid] = mid
                access = str(method.get_access_flags_string())
                flags = (_FLAG_STATIC if "static" in access else 0) | (_FLAG_NATIVE if "native" in access else 0)
                code = method.get_code()
                if code is None:
                    g.m_flags[mid] = flags
                    continue
                g.m_flags[mid] = flags | _FLAG_CODE
                calls, news, comps = array("I"), array("I"), array("I")
                for _offset, ins in method.get_instructions_idx():
                    op = ins.get_op_value()
                    if op in _INVOKE_VIRTUAL:
                        calls.append(method_at(ins.get_ref_kind()) * 2 + 1)
                    elif op in _INVOKE_EXACT:
                        target = method_at(ins.get_ref_kind())
                        calls.append(target * 2)
                        if op in (0x71, 0x77):  # invoke-static initializes the class
                            calls.append(g.meth(g.m_cls[target], clinit) * 2)
                    elif op == _NEW_INSTANCE:
                        owner = type_at(ins.get_ref_kind())
                        target_cid = g.cls(owner)
                        news.append(target_cid)
                        calls.append(g.meth(target_cid, clinit) * 2)
                        if is_platform_type(owner):
                            calls.append(g.meth(target_cid, g.sig("C:")) * 2)
                    elif op in (_CONST_CLASS, _CHECK_CAST, _INSTANCE_OF):
                        owner = type_at(ins.get_ref_kind())
                        if owner in component_desc and op == _CONST_CLASS:
                            comps.append(g.cls(owner))
                        elif is_platform_type(owner):
                            calls.append(g.meth(g.cls(owner), g.sig("C:")) * 2)
                    elif op in _STATIC_FIELD or op in _INSTANCE_FIELD:
                        owner, ftype, fname = dex.get_cm_field(ins.get_ref_kind())
                        owner = str(owner)
                        owner_cid = g.cls(owner)
                        if op in _STATIC_FIELD:
                            calls.append(g.meth(owner_cid, clinit) * 2)
                        if is_platform_type(owner):
                            calls.append(g.meth(owner_cid, g.sig(f"F:{fname}:{compact_descriptor(ftype)}")) * 2)
                    elif op in _CONST_STRING and dotted:
                        target = dotted.get(str(ins.get_string()))
                        if target:
                            comps.append(g.cls(target))
                if calls:
                    g.calls[mid] = calls
                if news:
                    g.news[mid] = news
                if comps:
                    g.comps[mid] = comps
        del dex
        gc.collect()
    return g


class Reachability:
    def __init__(self, graph: Graph, runtime: dict[str, Any] | None = None, user_input_callbacks: bool = False):
        self.g = graph
        self.user_input_callbacks = user_input_callbacks
        self.deferred_user_input = 0
        self.runtime_classes = (runtime or {}).get("classes", {})
        self.stage = bytearray([UNREACHED]) * len(graph.m_cls)
        self.parent = array("i", [-1]) * len(graph.m_cls)   # who first reached each method: the explanation
        self._cause = -1
        self.instantiated: dict[int, int] = {}
        self.current = 0
        self.work: deque[int] = deque()
        self.vcalls: dict[int, set[int]] = defaultdict(set)      # declared class -> virtual sigs called on it
        self.subs: dict[int, set[int]] = defaultdict(set)        # class -> instantiated subtypes
        self.pending_components: set[int] = set()
        self.named_by: dict[int, list[int]] = {}   # holder component -> classes its <meta-data> names
        self._supertypes: dict[int, frozenset[int]] = {}
        self._platform_sigs: dict[frozenset[int], frozenset[int]] = {}
        self._resolved: dict[tuple[int, int], int | None] = {}

    # ---- hierarchy -------------------------------------------------------------------------
    def supertypes(self, cid: int) -> frozenset[int]:
        cached = self._supertypes.get(cid)
        if cached is not None:
            return cached
        g, out, queue = self.g, set(), [cid]
        while queue:
            current = queue.pop()
            if current in out:
                continue
            out.add(current)
            if current in g.defined:
                if current in g.supers:
                    queue.append(g.supers[current])
                queue.extend(g.ifaces.get(current, []))
            else:
                record = self.runtime_classes.get(g.cls_names[current])
                if record:
                    queue.extend(g.cls(p) for p in [record.get("super", ""), *record.get("interfaces", [])] if p)
        result = self._supertypes[cid] = frozenset(out)
        return result

    def platform_sigs(self, cid: int) -> frozenset[int] | None:
        """Method signatures of a class's platform supertypes; `None` when no runtime index says."""
        g = self.g
        platform = frozenset(c for c in self.supertypes(cid)
                             if c not in g.defined and g.cls_names[c] != "Ljava/lang/Object;")
        if not platform:
            return frozenset()
        cached = self._platform_sigs.get(platform)
        if cached is None:
            sigs, known = set(), False
            for c in platform:
                record = self.runtime_classes.get(g.cls_names[c])
                if record:
                    known = True
                    sigs.update(g.sig(m) for m in record.get("methods", []))
            cached = self._platform_sigs[platform] = frozenset(sigs) if known else None  # type: ignore[assignment]
        return cached

    def resolve(self, cid: int, sid: int) -> int | None:
        """The method a call on `cid` with signature `sid` lands in: class chain, then interfaces."""
        key = (cid, sid)
        if key in self._resolved:
            return self._resolved[key]
        g, current, result = self.g, cid, None
        while current is not None and current in g.defined:
            hit = g.cls_methods[current].get(sid)
            if hit is not None:
                result = hit
                break
            current = g.supers.get(current)
        if result is None:
            for parent in self.supertypes(cid):
                if parent in g.defined:
                    hit = g.cls_methods[parent].get(sid)
                    if hit is not None and g.m_flags[hit] & _FLAG_CODE:
                        result = hit
                        break
        self._resolved[key] = result
        return result

    # ---- worklist --------------------------------------------------------------------------
    def reach(self, mid: int | None) -> None:
        if mid is not None and self.stage[mid] == UNREACHED:
            self.stage[mid] = self.current
            self.parent[mid] = self._cause
            self.work.append(mid)

    def explain(self, mid: int, limit: int = 40) -> list[str]:
        """The chain of methods from an entry point to `mid`, entry first."""
        chain = []
        while mid >= 0 and len(chain) < limit:
            chain.append(self.g.name(mid))
            mid = self.parent[mid]
        return chain[::-1]

    def instantiate(self, cid: int) -> None:
        g = self.g
        if cid in self.instantiated or cid not in g.defined:
            return
        self.instantiated[cid] = self.current
        supers = self.supertypes(cid)
        for parent in supers:
            self.subs[parent].add(cid)
        callbacks = self.platform_sigs(cid)
        seen: set[int] = set()
        for owner in supers:
            if owner not in g.defined:
                continue
            for sid, mid in g.cls_methods[owner].items():
                if sid in seen or g.m_flags[mid] & _FLAG_STATIC:
                    continue
                target = self.resolve(cid, sid)
                if target is None:
                    continue
                overrides_platform = callbacks is None or sid in callbacks
                if overrides_platform and not self.user_input_callbacks and USER_INPUT_CALLBACK.match(g.sig_names[sid]):
                    overrides_platform = False
                    self.deferred_user_input += 1
                called = any(sid in self.vcalls.get(parent, ()) for parent in supers)
                if overrides_platform or called:
                    seen.add(sid)
                    self.reach(target)

    def run(self) -> None:
        g = self.g
        while self.work:
            mid = self.work.popleft()
            self._cause = mid
            for enc in g.calls.get(mid, ()):
                target, virtual = enc >> 1, enc & 1
                cid, sid = g.m_cls[target], g.m_sig[target]
                if cid not in g.defined:
                    self.reach(target)  # platform node: record the stage it is first needed at
                else:
                    self.reach(self.resolve(cid, sid))
                if virtual:
                    if sid not in self.vcalls[cid]:
                        self.vcalls[cid].add(sid)
                    for sub in tuple(self.subs.get(cid, ())):
                        self.reach(self.resolve(sub, sid))
            for cid in g.news.get(mid, ()):
                self.instantiate(cid)
            for cid in g.comps.get(mid, ()):
                # Code that names a component class can read its <meta-data>, which is how the
                # classes listed there get loaded (Firebase registrars, CameraX config, startup
                # initializers): they become live here, not at process start.
                for named in self.named_by.pop(cid, ()):
                    self.start_component(g.cls_names[named])
                if cid not in self.instantiated:
                    self.pending_components.add(cid)

    def start_component(self, descriptor: str) -> bool:
        g = self.g
        cid = g.cls_ids.get(descriptor)
        if cid is None or cid not in g.defined:
            return False
        for named in self.named_by.pop(cid, ()):
            self.start_component(g.cls_names[named])
        self.instantiate(cid)
        for sid, mid in g.cls_methods[cid].items():
            if g.sig_names[sid].startswith(("<init>", "<clinit>")):
                self.reach(mid)
        return True


def analyse(path: Path, facts: dict[str, Any], runtime: dict[str, Any] | None = None) -> tuple[Graph, Reachability, dict[str, Any]]:
    """Run staged reachability for one APK from its manifest entry points."""
    desc = lambda name: "L" + name.replace(".", "/") + ";"
    components = [c["name"] for c in facts["components"] if c.get("name")]
    graph = build_graph(path, components)
    r = Reachability(graph, runtime)

    def names_in(meta: dict[str, str]) -> list[str]:
        return sorted({token for key, value in meta.items() for token in [*str(key).split(":"), *str(value).split(":")]
                       if graph.cls_ids.get(desc(token)) in graph.defined})

    named = names_in(facts.get("application_meta_data", {}))  # read off ApplicationInfo: live from process start
    for component in facts["components"]:
        holder = graph.cls_ids.get(desc(component["name"] or ""))
        listed = names_in(component["meta_data"])
        if holder is not None and listed:
            r.named_by[holder] = [graph.cls_ids[desc(n)] for n in listed]

    entries: dict[str, list[str]] = {"0": [], "1": [], "2": [], "3": []}
    r.current = 0
    stage0 = [facts.get("application_class"), facts.get("app_component_factory"),
              *[c["name"] for c in facts["components"] if c["kind"] == "provider" and not c.get("process")],
              *sorted(named)]
    for name in filter(None, stage0):
        if r.start_component(desc(name)):
            entries["0"].append(name)
    r.run()

    r.current = 1
    for name in facts.get("main_activities", []):
        if r.start_component(desc(name)):
            entries["1"].append(name)
    r.run()

    for stage in (2, 3):
        r.current = stage
        while r.pending_components:
            batch, r.pending_components = r.pending_components, set()
            for cid in batch:
                if r.start_component(graph.cls_names[cid]):
                    entries[str(stage)].append(graph.cls_names[cid][1:-1].replace("/", "."))
            r.run()
            if stage == 2:
                break

    code_methods = sum(1 for flags in graph.m_flags if flags & _FLAG_CODE)
    by_stage = {name: 0 for name in STAGE_NAMES.values()}
    for mid, flags in enumerate(graph.m_flags):
        if flags & _FLAG_CODE:
            by_stage[STAGE_NAMES[r.stage[mid]]] += 1
    summary = {"classes_defined": len(graph.defined), "methods_with_code": code_methods,
               "methods_by_stage": by_stage, "classes_instantiated": len(r.instantiated),
               "entry_points": entries, "runtime_index_used": bool(runtime)}
    return graph, r, summary


def export(graph: Graph, r: Reachability, summary: dict[str, Any], scan: dict[str, Any] | None = None) -> dict[str, Any]:
    """Stages for every platform node, for the app methods a scan names, and for each native library."""
    platform, natives = {}, {}
    for mid, stage in enumerate(r.stage):
        if stage == UNREACHED:
            continue
        cid = graph.m_cls[mid]
        if cid not in graph.defined and is_platform_type(graph.cls_names[cid]):
            platform[graph.name(mid)] = stage
        elif graph.m_flags[mid] & _FLAG_NATIVE:
            natives[graph.name(mid)] = stage

    callers, libraries = {}, {}
    if scan:
        inv = scan.get("inventory", {})
        wanted = [*inv.get("service_requests", []), *inv.get("existence_probes", []), *inv.get("load_library_calls", [])]
        for finding in scan.get("findings", []):
            wanted.extend(finding.get("evidence") or [])
        for site in wanted:
            if not isinstance(site, dict) or "owner" not in site or "method" not in site:
                continue
            key = f"{site['owner']}->{site['method']}{site.get('descriptor', '')}"
            cid, sid = graph.cls_ids.get(site["owner"]), graph.sig_ids.get(f"{site['method']}{site.get('descriptor', '')}")
            mid = graph.meth_ids.get((cid, sid)) if cid is not None and sid is not None else None
            if mid is not None and r.stage[mid] != UNREACHED:
                callers[key] = r.stage[mid]
        for native in inv.get("declared_native_methods", []):
            stage = natives.get(f"{native['owner']}->{native['name']}{native['descriptor']}")
            if stage is None:
                continue
            for lib in native.get("candidate_libraries", []):
                soname = lib["elf"].rsplit("/", 1)[-1]
                libraries[soname] = min(stage, libraries.get(soname, UNREACHED))
        for call in inv.get("load_library_calls", []):
            stage = callers.get(f"{call['owner']}->{call['method']}{call.get('descriptor', '')}")
            if stage is not None:
                soname = f"lib{call['value']}.so" if not str(call["value"]).endswith(".so") else str(call["value"]).rsplit("/", 1)[-1]
                libraries[soname] = min(stage, libraries.get(soname, UNREACHED))
    return {"stages": {str(k): v for k, v in STAGE_NAMES.items()}, "summary": summary,
            "platform_stage": platform, "caller_stage": callers, "native_method_stage": natives,
            "library_stage": libraries}
