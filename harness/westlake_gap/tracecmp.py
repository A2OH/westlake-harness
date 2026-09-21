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
