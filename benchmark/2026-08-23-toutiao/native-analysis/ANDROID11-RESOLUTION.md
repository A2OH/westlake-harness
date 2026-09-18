# Resolving Toutiao's native imports against stock Android 11

**Reference platform.** OnePlus 6T (ONEPLUS A6013), Android 11, SDK 30, arm64-v8a. 17 system
libraries, 12,152 exported symbols. Stock Android *is* the contract a compatibility layer has to
satisfy, so resolving against it turns "we don't know" into "Android provides this, so we must".

The binaries themselves are Google and vendor property and are **not committed**. Their SHA-256,
Build-ID, size and export count are recorded in `android11-import-resolution.json` so a later run
can prove it used the same reference.

## Result

**3,405 of 3,415 undefined symbols decided — 99.7%.**

| Verdict | Symbols | Share |
|---|---|---|
| `C0` resolved | 3,133 | 91.7% |
| `N-C1-candidate` no provider | 259 | 7.6% |
| `N-C5-candidate` weak, optional by design | 13 | 0.4% |
| `CU` C++ runtime internals (an `N-C3` ordering question) | 10 | 0.3% |

Of the 3,133 resolved, **913 come from Android system libraries** and **2,220 from the app's own
packaged libraries resolving each other**. Only 17 system libraries were needed.

## The 259 with no provider are not platform gaps

239 of them are C++ mangled names, and they trace to four sonames that neither the APK nor stock
Android supplies:

| Soname | Named by |
|---|---|
| `libprofiler.so` | 2 app libraries |
| `libaudioeffect.so` | 1 |
| `libnapi_v8.so` | 1 |
| `libv8_libfull.cr.so` | 1 |

167 of the 259 are imported by a library that names one of those four. They are satisfied by code
**delivered after install** — the same phenomenon the runtime capture caught from the other side,
where `libwcdb.so`, `libavmdlv2.so`, `libpreload.so` and `libcachemodule.so` registered 240 JNI
methods without appearing in the APK (`../runtime-evidence/android-baseline/REPORT.md`). Static
analysis sees the dangling imports; the runtime capture sees the code that arrives to satisfy them.

## A parser defect this exposed

The first run reported 265 missing symbols led by `strlen` (imported by 103 libraries), `strcmp`
and `memchr` — all of which libc plainly exports. They are **IFUNCs**, and `readelf` prints an
IFUNC's type as `<OS specific>: 10`, three whitespace-separated tokens where every other symbol has
one. The column parser in `read_elf` shifted by two fields and dropped every IFUNC export; on
Android arm64 that is the whole optimized string and memory family.

Nothing had ever indexed a system library before, so the defect had no way to show itself. Symbol
reading now goes through pyelftools against `.dynsym`, with the column parse kept as a fallback and
taught to fold the `<OS specific>` form. `tests/test_native_provenance.py` pins both paths.

## Reproducing

```
for s in libc libm libdl liblog libandroid libjnigraphics libEGL libGLESv2 libGLESv3 \
         libOpenSLES libz libcutils libbase libc++ libstdc++ libart libdexfile; do
  adb pull $(adb shell "for d in /system/lib64 /apex/com.android.runtime/lib64/bionic \
     /apex/com.android.art/lib64; do [ -f \$d/$s.so ] && echo \$d/$s.so && break; done") ./syslibs/
done
westlake-apk-gap snapshot-runtime --classpath-file classpath.txt --bridge <bridge.so> \
  --system-lib ./syslibs/*.so --out runtime-lock.json
```

`adb pull` reads stdin, so inside a `while read` loop it eats the rest of the list — redirect it
from `/dev/null`.
