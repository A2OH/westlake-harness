"""Known answers for static startup reachability and for the device-trace observation.

The fixture app has one platform call per situation that matters: reached at process start through
a Runnable, reached only from the launcher activity, sitting behind a click handler, and in a class
nothing instantiates. The trace fixture is a byte string in the shape ART writes method records.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from test_known_answers import _find_android_d8, _run, _write
from westlake_gap import reach, tracecmp

API = {
    "android/app/Application.java": "package android.app; public class Application { public void onCreate() {} }",
    "android/app/Activity.java": "package android.app; public class Activity { protected void onCreate(android.os.Bundle b) {} }",
    "android/os/Bundle.java": "package android.os; public class Bundle {}",
    "android/os/SystemClock.java": "package android.os; public class SystemClock { public static long uptimeMillis() { return 0; } }",
    "android/util/Log.java": "package android.util; public class Log { public static int d(String a, String b) { return 0; } }",
    "android/net/TrafficStats.java": "package android.net; public class TrafficStats { public static long getTotalRxBytes() { return 0; } }",
    "android/hardware/Camera.java": "package android.hardware; public class Camera { public static Camera open() { return null; } }",
    "android/view/View.java": """package android.view; public class View {
        public interface OnClickListener { void onClick(View v); }
        public void setOnClickListener(OnClickListener l) {} }""",
}
APP = {
    "fixture/App.java": """package fixture; public class App extends android.app.Application {
        public void onCreate() { Runnable r = new Worker(); r.run(); } }""",
    "fixture/Worker.java": """package fixture; class Worker implements Runnable {
        public void run() { android.util.Log.d("a", "b"); } }""",
    "fixture/Main.java": """package fixture; public class Main extends android.app.Activity {
        protected void onCreate(android.os.Bundle b) { android.os.SystemClock.uptimeMillis();
            new android.view.View().setOnClickListener(new Click()); } }""",
    "fixture/Click.java": """package fixture; class Click implements android.view.View.OnClickListener {
        public void onClick(android.view.View v) { android.net.TrafficStats.getTotalRxBytes(); } }""",
    "fixture/Never.java": "package fixture; class Never { void x() { android.hardware.Camera.open(); } }",
}
RUNTIME = {"classes": {
    "Ljava/lang/Runnable;": {"super": "", "interfaces": [], "methods": ["run()V"]},
    "Landroid/app/Application;": {"super": "Ljava/lang/Object;", "interfaces": [], "methods": ["onCreate()V"]},
    "Landroid/app/Activity;": {"super": "Ljava/lang/Object;", "interfaces": [], "methods": ["onCreate(Landroid/os/Bundle;)V"]},
    "Landroid/view/View$OnClickListener;": {"super": "", "interfaces": [], "methods": ["onClick(Landroid/view/View;)V"]},
}}
FACTS = {"application_class": "fixture.App", "app_component_factory": None, "application_meta_data": {},
         "main_activities": ["fixture.Main"],
         "components": [{"kind": "activity", "name": "fixture.Main", "process": None, "meta_data": {}}]}
LOG = "Landroid/util/Log;->d(Ljava/lang/String;Ljava/lang/String;)I"
CLOCK = "Landroid/os/SystemClock;->uptimeMillis()J"
TRAFFIC = "Landroid/net/TrafficStats;->getTotalRxBytes()J"
CAMERA = "Landroid/hardware/Camera;->open()Landroid/hardware/Camera;"


class StartupReach(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        javac, d8 = shutil.which("javac"), _find_android_d8()
        if not javac or not d8:
            raise unittest.SkipTest("javac and d8 are required for the executable fixture")
        cls.temp = tempfile.TemporaryDirectory(prefix="westlake-reach-")
        root = Path(cls.temp.name)
        for name, text in API.items():
            _write(root / "api" / name, text)
        for name, text in APP.items():
            _write(root / "app" / name, text)
        for directory in ("api-classes", "app-classes", "dex"):
            (root / directory).mkdir()
        _run(javac, "--release", "8", "-d", str(root / "api-classes"), *map(str, (root / "api").rglob("*.java")))
        _run(javac, "--release", "8", "-cp", str(root / "api-classes"), "-d", str(root / "app-classes"),
             *map(str, (root / "app").rglob("*.java")))
        _run(d8, "--min-api", "21", "--output", str(root / "dex"), *map(str, (root / "app-classes").rglob("*.class")))
        cls.graph, cls.result, cls.summary = reach.analyse(root / "dex/classes.dex", FACTS, RUNTIME)
        cls.stages = reach.export(cls.graph, cls.result, cls.summary)["platform_stage"]

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def test_stages(self) -> None:
        self.assertEqual(self.stages[LOG], 0, "reached at process start through Runnable.run")
        self.assertEqual(self.stages[CLOCK], 1, "reached only from the launcher activity")
        self.assertNotIn(TRAFFIC, self.stages, "a click handler is not on the startup path")
        self.assertNotIn(CAMERA, self.stages, "nothing instantiates Never")

    def test_explanation_chain(self) -> None:
        g = self.graph
        mid = g.meth_ids[(g.cls_ids["Landroid/util/Log;"], g.sig_ids["d(Ljava/lang/String;Ljava/lang/String;)I"])]
        chain = self.result.explain(mid)
        self.assertEqual(chain[-1], LOG)
        self.assertIn("Lfixture/Worker;->run()V", chain)
        self.assertTrue(chain[0].startswith("Lfixture/App;->"), chain)

    def test_trace_observation_and_comparison(self) -> None:
        trace = Path(self.temp.name) / "fixture.trace"
        trace.write_bytes(b"SLOW\x00\x01junk" + b"".join(
            f"\x00\x01{cls}\t{name}\t{sig}\tX.java\n".encode() for cls, name, sig in [
                ("fixture.App", "onCreate", "()V"), ("fixture.Worker", "run", "()V"),
                ("android.util.Log", "d", "(Ljava/lang/String;Ljava/lang/String;)I"),
                ("fixture.Main", "onCreate", "(Landroid/os/Bundle;)V")]))
        executed = tracecmp.executed_methods(trace)
        self.assertIn(LOG, executed)
        observed = tracecmp.observe(self.graph, executed, RUNTIME, ["libx.so"], "fixture run")
        self.assertEqual(observed["platform_touch"][LOG], "executed")
        self.assertEqual(observed["platform_touch"][CLOCK], "referenced", "its caller ran; the call itself was not recorded")
        self.assertNotIn(TRAFFIC, observed["platform_touch"])
        comparison = tracecmp.compare(self.graph, self.result, executed)
        self.assertEqual(comparison["executed_app_methods"], 3)
        self.assertEqual(comparison["static_vs_trace"][1]["recall"], 1.0)
        self.assertEqual(comparison["executed_but_not_reached"], 0)


class FrameworkCheck(unittest.TestCase):
    """Every platform method a run executed, looked up in the runtime under test."""

    RUNTIME = {"runtime_lock_id": "fixture", "classes": {
        "Landroid/view/Fine;": {"artifact": "framework.jar", "super": "Ljava/lang/Object;", "interfaces": [],
                                "methods": ["draw()V", "nBound()J", "nUnbound()J", "template()V"], "fields": [],
                                "hollow_methods": ["template()V"], "native_methods": ["nBound()J", "nUnbound()J"]},
        "Landroid/net/Stubbed;": {"artifact": "adapter-mainline-stubs.jar", "super": "Ljava/lang/Object;", "interfaces": [],
                                  "methods": ["tag(I)V"], "fields": [], "hollow_methods": ["tag(I)V"], "native_methods": []},
    }}

    def test_states_order_and_limits(self) -> None:
        from westlake_gap.scanner import RuntimeResolver

        with tempfile.TemporaryDirectory(prefix="westlake-fwcheck-") as temp:
            trace = Path(temp) / "run.trace"
            records = [("fixture.App", "onCreate", "()V"), ("android.view.Fine", "draw", "()V"),
                       ("android.view.Fine", "nBound", "()J"), ("android.view.Fine", "nUnbound", "()J"),
                       ("android.view.Fine", "template", "()V"), ("android.net.Stubbed", "tag", "(I)V"),
                       ("android.view.Fine", "gone", "()V"), ("android.view.Absent", "x", "()V"),
                       ("android.view.Fine", "-$$Nest$fgetmX", "()I")]
            trace.write_bytes(b"".join(f"\x00\x01{c}\t{n}\t{sig}\tX.java\n".encode() for c, n, sig in records))
            order = tracecmp.execution_order(trace)
        self.assertEqual(order["Lfixture/App;->onCreate()V"], 0)
        self.assertLess(order["Landroid/view/Fine;->draw()V"], order["Landroid/net/Stubbed;->tag(I)V"], "record order is first-execution order")

        tables = [{"library": "libruntime.so", "methods": {"nBound()J", "nOther()V"}}]
        result = tracecmp.framework_check(set(order), {"Lfixture/App;"}, self.RUNTIME, RuntimeResolver(self.RUNTIME), tables, set(), order)
        state = {f["method"]: f["state"] for f in result["findings"]}
        self.assertEqual(state["Landroid/view/Fine;->nUnbound()J"], "native-unbound", "its class table exists and lacks it")
        self.assertNotIn("Landroid/view/Fine;->nBound()J", state)
        self.assertEqual(state["Landroid/net/Stubbed;->tag(I)V"], "hollow", "placeholder in a Westlake stub jar")
        self.assertEqual(state["Landroid/view/Fine;->template()V"], "hollow-candidate", "framework.jar may carry AOSP's own empty body")
        self.assertEqual(state["Landroid/view/Fine;->gone()V"], "member-missing")
        self.assertEqual(state["Landroid/view/Absent;->x()V"], "class-missing")
        self.assertNotIn("Lfixture/App;->onCreate()V", state, "app methods are not platform methods")
        self.assertEqual(result["counts"]["compiler-generated"], 1, "nest accessors differ between builds and prove nothing")
        self.assertEqual([f["first_seen"] for f in result["findings"]], sorted(f["first_seen"] for f in result["findings"]))


if __name__ == "__main__":
    unittest.main()
