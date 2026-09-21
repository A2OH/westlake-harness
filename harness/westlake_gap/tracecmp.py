"""Ground truth for startup reachability: an ART method trace recorded on a real Android device.

On a userdebug or rooted device, `am start-activity --start-profiler <file> --streaming` records
every method the app executes, framework methods included, from process start onward. That is the
exact answer to "what does this app touch on the way to its first screens", for one run.

This module reads the executed-method set out of a trace and uses it two ways:

- **to stage gaps by observation**: a platform method is *executed* when it appears in the trace; a
  platform field, class or service request is *touched* when an executed app method contains the
  reference. Either puts the gap on the real startup path;
- **to measure the static pass** (`reach.py`): recall (executed app methods it also reached) and
  precision (reached methods that actually executed), per stage.

Method records are embedded as text in every ART trace format (`class\\tname\\tsignature\\tsource`),
so they are read with a pattern rather than by decoding the binary event stream; that keeps the
reader independent of the trace version.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .reach import UNREACHED, Graph, Reachability, _FLAG_CODE

_METHOD = re.compile(rb"([A-Za-z_$][\w$.]*(?:\[\])*)\t([\w$<>-]+)\t(\([^\t\n)]*\)[^\t\n]+)\t")


def executed_methods(trace: Path) -> set[str]:
    """`Lpkg/Class;->name(desc)ret` for every method recorded in an ART method trace."""
    out = set()
    for cls, name, sig in _METHOD.findall(trace.read_bytes()):
        descriptor = "L" + cls.decode().replace(".", "/") + ";"
        out.add(f"{descriptor}->{name.decode()}{sig.decode()}")
    return out


def execution_order(trace: Path) -> dict[str, int]:
    """Method -> rank of its first execution. A streaming trace emits each method record the first
    time the method runs, so record order is first-execution order: a ruler along the run. Known
    failure points on the target platform mark how far along it the port has got."""
    order: dict[str, int] = {}
    for cls, name, sig in _METHOD.findall(trace.read_bytes()):
        key = "L" + cls.decode().replace(".", "/") + ";->" + name.decode() + sig.decode()
        order.setdefault(key, len(order))
    return order


def compare(graph: Graph, reach: Reachability, executed: set[str]) -> dict[str, Any]:
    """Recall and precision of the static stages against one recorded run."""
    app_executed = set()
    for key in executed:
        owner, _, sig = key.partition("->")
        cid, sid = graph.cls_ids.get(owner), graph.sig_ids.get(sig)
        mid = graph.meth_ids.get((cid, sid)) if cid is not None and sid is not None else None
        if mid is not None and graph.m_flags[mid] & _FLAG_CODE:
            app_executed.add(mid)
    rows = []
    for limit, label in ((0, "process start"), (1, "+ first activity"), (2, "+ next screens"), (3, "+ later")):
        reached = {mid for mid, stage in enumerate(reach.stage) if stage <= limit and graph.m_flags[mid] & _FLAG_CODE}
        hit = len(reached & app_executed)
        rows.append({"through": label, "static_methods": len(reached), "executed_and_reached": hit,
                     "recall": round(hit / len(app_executed), 4) if app_executed else None,
                     "precision": round(hit / len(reached), 4) if reached else None})
    missed = sorted(graph.name(mid) for mid in app_executed if reach.stage[mid] == UNREACHED)
    return {"executed_methods_in_trace": len(executed), "executed_app_methods": len(app_executed),
            "static_vs_trace": rows, "executed_but_not_reached": len(missed), "executed_but_not_reached_sample": missed[:40]}


def observe(graph: Graph, executed: set[str], runtime: dict[str, Any] | None = None,
            loaded_libraries: list[str] | None = None, scenario: str = "") -> dict[str, Any]:
    """Everything one recorded run says about the platform boundary, keyed like `reach.export`.

    A platform method reference is **executed** when the trace holds that method on the referenced
    class or on a subclass of it (`PackageManager.getServiceInfo` runs as
    `ApplicationPackageManager.getServiceInfo`); otherwise it is **referenced** when an executed app
    method contains it: the method ran, that exact call may not have. Fields and class references
    can only ever be *referenced*.
    """
    classes = (runtime or {}).get("classes", {})
    supers_cache: dict[str, set[str]] = {}

    def supers(name: str) -> set[str]:
        if name not in supers_cache:
            out, queue = set(), [name]
            while queue:
                current = queue.pop()
                if current in out:
                    continue
                out.add(current)
                record = classes.get(current)
                if record:
                    queue.extend(p for p in [record.get("super", ""), *record.get("interfaces", [])] if p)
            supers_cache[name] = out
        return supers_cache[name]

    executed_mids, by_sig = set(), {}
    for key in executed:
        owner, _, sig = key.partition("->")
        cid, sid = graph.cls_ids.get(owner), graph.sig_ids.get(sig)
        mid = graph.meth_ids.get((cid, sid)) if cid is not None and sid is not None else None
        if mid is not None and cid in graph.defined:
            executed_mids.add(mid)
        elif cid is None or cid not in graph.defined:
            by_sig.setdefault(sig, set()).add(owner)

    platform: dict[str, str] = {}
    for mid in executed_mids:
        for enc in graph.calls.get(mid, ()):
            target = enc >> 1
            cid = graph.m_cls[target]
            if cid in graph.defined:
                continue
            owner, sig = graph.cls_names[cid], graph.sig_names[graph.m_sig[target]]
            key = f"{owner}->{sig}"
            if platform.get(key) == "executed":
                continue
            ran = any(k == owner or owner in supers(k) for k in by_sig.get(sig, ()))
            platform[key] = "executed" if ran else platform.get(key, "referenced")
    return {
        "scenario": scenario,
        "executed_methods": len(executed),
        "executed_app_methods": sorted(graph.name(m) for m in executed_mids),
        "executed_platform_classes": sorted({k.partition("->")[0] for k in executed
                                             if graph.cls_ids.get(k.partition("->")[0]) not in graph.defined}),
        "platform_touch": platform,
        "loaded_app_libraries": sorted(loaded_libraries or []),
    }


# Compiler-generated members whose names differ between two builds of the same source: nest-access
# bridges, desugared lambdas and their holder classes. Absence of one proves nothing.
_GENERATED = re.compile(r"-\$\$Nest\$|\$\$ExternalSyntheticLambda|\$\$Lambda\$|->lambda\$|\$\$ExternalSynthetic")


def jni_tables(library_dir: Path) -> tuple[list[dict[str, Any]], set[str]]:
    """JNI bindings a set of deployed libraries can supply: registration tables and `Java_*` exports.

    A `JNINativeMethod` table does not name its class, so entries are grouped by table (contiguous
    24-byte slots) and a class is matched to the table that shares the most of its native methods.
    """
    from .native import recover_jni_registration_entries
    from .ndk import elf_exports, is_variant

    tables, exports = [], set()
    for path in sorted(library_dir.glob("*.so")):
        if is_variant(path.name):
            continue
        data = path.read_bytes()
        exports |= {name for name in elf_exports(data) if name.startswith("Java_")}
        entries, _error = recover_jni_registration_entries(data)
        entries.sort(key=lambda e: e["table_vaddr"])
        current: list[dict[str, Any]] = []
        for entry in entries:
            if current and entry["table_vaddr"] - current[-1]["table_vaddr"] != 24:
                tables.append({"library": path.name, "methods": {f"{e['name']}{e['signature']}" for e in current}})
                current = []
            current.append(entry)
        if current:
            tables.append({"library": path.name, "methods": {f"{e['name']}{e['signature']}" for e in current}})
    return tables, exports


def framework_check(executed: set[str], app_classes: set[str], runtime: dict[str, Any], resolver: Any,
                    tables: list[dict[str, Any]], jni_exports: set[str], order: dict[str, int] | None = None) -> dict[str, Any]:
    """Every platform method a real run executed, looked up in the runtime under test.

    The gap map starts from what the *app* references. This starts from what actually *ran*, so it
    also covers the framework calling itself and its own native code, which is where surprises that
    no app-side scan can see come from. States: `class-missing`, `member-missing`, `hollow`
    (placeholder in a Westlake adapter/stub jar), `native-unbound` (declared native in the runtime,
    no registration table or export supplies it), and the fine ones.
    """
    from .nativeupcall import UPSTREAM_JARS, _westlake_owned
    from .scanner import jni_symbols

    classes = runtime["classes"]
    by_class_natives: dict[str, set[str]] = {}
    best_table: dict[str, dict[str, Any] | None] = {}

    def table_for(owner: str, natives: set[str]) -> dict[str, Any] | None:
        if owner not in best_table:
            scored = [(len(natives & t["methods"]) / len(t["methods"]), len(natives & t["methods"]), t) for t in tables
                      if natives & t["methods"]]
            scored = [item for item in scored if item[0] >= 0.5 or item[1] >= 3]
            best_table[owner] = max(scored, key=lambda item: (item[1], item[0]))[2] if scored else None
        return best_table[owner]

    rows, counts = [], {}
    for key in sorted(executed):
        owner, _, sig = key.partition("->")
        if owner in app_classes:
            continue
        state, detail = "present", ""
        if _GENERATED.search(key):
            state = "compiler-generated"
        elif owner not in classes:
            state = "class-missing"
        else:
            name, _, rest = sig.partition("(")
            hit = resolver.resolve_method(owner, name, "(" + rest)
            if hit is None:
                state = "member-missing"
            else:
                declaring, record = hit
                artifact = record.get("artifact")
                if sig in record.get("native_methods", []):
                    natives = by_class_natives.setdefault(declaring, set(record.get("native_methods", [])))
                    short, long = jni_symbols(declaring, name, "(" + rest)
                    table = table_for(declaring, natives)
                    if short in jni_exports or long in jni_exports:
                        state, detail = "native-bound", "exported"
                    elif table is not None and sig in table["methods"]:
                        state, detail = "native-bound", table["library"]
                    else:
                        state = "native-unbound"
                        detail = f"class table in {table['library']} lacks it" if table else "no registration table or export for this class"
                elif sig in record.get("hollow_methods", []) and artifact not in UPSTREAM_JARS:
                    state = "hollow" if _westlake_owned(artifact) else "hollow-candidate"
                    detail = artifact or ""
        counts[state] = counts.get(state, 0) + 1
        if state not in {"present", "native-bound", "compiler-generated"}:
            rows.append({"method": key, "state": state, "detail": detail, "first_seen": (order or {}).get(key)})
    rows.sort(key=lambda r: (r["first_seen"] is None, r["first_seen"] or 0))
    return {"counts": counts, "findings": rows}

