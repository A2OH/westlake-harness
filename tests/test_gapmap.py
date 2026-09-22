"""Known answers for the contract surfaces the class/member subtraction cannot see.

Each case is a failure McDonald's actually hit on the OH board, reduced to the smallest input
that must reproduce the verdict: a null service, a hollow service, a PM path that drops every
component, and a kernel policy that denies the object a native library creates.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from test_known_answers import _find_android_d8, _run, _write
from westlake_gap import gapmap, services
from westlake_gap.contracts import direct_launch_am_model, pm_adapter_model, window_adapter_model
from westlake_gap.scanner import inventory_dex


class ServiceRequestCapture(unittest.TestCase):
    def test_names_classes_and_servicemanager(self) -> None:
        javac, d8 = shutil.which("javac"), _find_android_d8()
        if not javac or not d8:
            self.skipTest("javac and d8 are required for the executable fixture")
        with tempfile.TemporaryDirectory(prefix="westlake-services-") as temp:
            root = Path(temp)
            _write(root / "api/android/content/Context.java", """package android.content;
                public abstract class Context {
                    public abstract Object getSystemService(String name);
                    public final <T> T getSystemService(Class<T> cls) { return null; }
                }""")
            _write(root / "api/android/app/job/JobScheduler.java", "package android.app.job; public class JobScheduler {}")
            _write(root / "api/android/os/ServiceManager.java", """package android.os;
                public class ServiceManager { public static Object getService(String n) { return null; } }""")
            _write(root / "app/fixture/UsesServices.java", """package fixture;
                import android.content.Context;
                public class UsesServices {
                    static Object byName(Context c) { return c.getSystemService("jobscheduler"); }
                    static Object byClass(Context c) { return c.getSystemService(android.app.job.JobScheduler.class); }
                    static Object direct() { return android.os.ServiceManager.getService("location"); }
                    static Object computed(Context c, String n) { return c.getSystemService(n); }
                }""")
            api, app, dex = root / "api-classes", root / "app-classes", root / "dex"
            for directory in (api, app, dex):
                directory.mkdir()
            _run(javac, "--release", "8", "-d", str(api), *map(str, (root / "api").rglob("*.java")))
            _run(javac, "--release", "8", "-cp", str(api), "-d", str(app), str(root / "app/fixture/UsesServices.java"))
            _run(d8, "--min-api", "21", "--output", str(dex), str(app / "fixture/UsesServices.class"))

            requests = inventory_dex(dex / "classes.dex").service_requests
            by_method = {r["method"]: r for r in requests}
            self.assertEqual(by_method["byName"]["service"], "jobscheduler")
            self.assertEqual(by_method["byClass"]["manager_class"], "Landroid/app/job/JobScheduler;")
            self.assertEqual(by_method["direct"]["service"], "location")
            self.assertTrue(by_method["direct"]["binder_direct"])
            self.assertTrue(by_method["computed"]["dynamic"], "a computed name must be reported, not guessed")


class ServiceVerdicts(unittest.TestCase):
    """Every verdict class, from a miniature AOSP and Westlake tree."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="westlake-service-model-")
        root = Path(self.temp.name)
        aosp = root / "aosp/frameworks-base/core/java/android"
        _write(aosp / "content/Context.java", """package android.content;
            public abstract class Context {
                public static final String JOB_SCHEDULER_SERVICE = "jobscheduler";
                public static final String LOCATION_SERVICE = "location";
                public static final String NOTIFICATION_SERVICE = "notification";
                public static final String ALARM_SERVICE = "alarm";
                public static final String ACCESSIBILITY_SERVICE = "accessibility";
                public static final String LAYOUT_INFLATER_SERVICE = "layout_inflater";
                public static final String CAMERA_SERVICE = "camera";
            }""")
        _write(aosp / "app/SystemServiceRegistry.java", """package android.app;
            import android.location.LocationManager;
            import android.view.LayoutInflater;
            import android.view.accessibility.AccessibilityManager;
            final class SystemServiceRegistry { static {
                registerService(Context.LOCATION_SERVICE, LocationManager.class,
                        new CachedServiceFetcher<LocationManager>() {
                    public LocationManager createService(ContextImpl ctx) throws ServiceNotFoundException {
                        IBinder b = ServiceManager.getServiceOrThrow(Context.LOCATION_SERVICE);
                        return new LocationManager(ctx, ILocationManager.Stub.asInterface(b));
                    }});
                registerService(Context.ALARM_SERVICE, AlarmManager.class,
                        new CachedServiceFetcher<AlarmManager>() {
                    public AlarmManager createService(ContextImpl ctx) throws ServiceNotFoundException {
                        IBinder b = ServiceManager.getServiceOrThrow(Context.ALARM_SERVICE);
                        return new AlarmManager(IAlarmManager.Stub.asInterface(b), ctx);
                    }});
                registerService(Context.NOTIFICATION_SERVICE, NotificationManager.class,
                        new CachedServiceFetcher<NotificationManager>() {
                    public NotificationManager createService(ContextImpl ctx) { return new NotificationManager(ctx); }});
                registerService(Context.ACCESSIBILITY_SERVICE, AccessibilityManager.class,
                        new CachedServiceFetcher<AccessibilityManager>() {
                    public AccessibilityManager createService(ContextImpl ctx) { return AccessibilityManager.getInstance(ctx); }});
                registerService(Context.LAYOUT_INFLATER_SERVICE, LayoutInflater.class,
                        new CachedServiceFetcher<LayoutInflater>() {
                    public LayoutInflater createService(ContextImpl ctx) { return new PhoneLayoutInflater(ctx); }});
                registerService(Context.CAMERA_SERVICE, CameraManager.class,
                        new CachedServiceFetcher<CameraManager>() {
                    public CameraManager createService(ContextImpl ctx) { return new CameraManager(ctx); }});
            }}""")
        _write(aosp / "app/NotificationManager.java", """package android.app;
            public class NotificationManager { static INotificationManager getService() {
                return INotificationManager.Stub.asInterface(ServiceManager.getService("notification")); } }""")
        _write(aosp / "view/accessibility/AccessibilityManager.java", """package android.view.accessibility;
            public final class AccessibilityManager { void connect() {
                IBinder iBinder = ServiceManager.getService(Context.ACCESSIBILITY_SERVICE); } }""")
        _write(aosp / "app/CameraManager.java", "package android.app; public final class CameraManager {}")
        _write(root / "aosp/modules-scheduling/framework/java/android/app/job/JobSchedulerFrameworkInitializer.java", """
            package android.app.job;
            public class JobSchedulerFrameworkInitializer { public static void registerServiceWrappers() {
                SystemServiceRegistry.registerContextAwareService(
                        Context.JOB_SCHEDULER_SERVICE, JobScheduler.class,
                        (context, b) -> new JobSchedulerImpl(context, IJobScheduler.Stub.asInterface(b)));
            }}""")
        westlake = root / "westlake/framework"
        _write(westlake / "core/java/OHServiceManager.java", """public final class OHServiceManager {
            private static IBinder lookupAdapter(String name) {
                switch (name) {
                    case "location":
                        return LocationManagerAdapter.getBinder();
                    case "game":
                        return null;
                    default:
                        return null;
                }
            }
            private static IBinder getAdapterBinder(String fqcn) { return null; }
            }""")
        _write(westlake / "android-runtime/src/AndroidRuntime.cpp",
               'static const char* kServices[] = { "notification" };\n')
        _write(westlake / "appspawn-x/java/com/android/internal/os/AppSpawnXInit.java", """class AppSpawnXInit {
            static void installJobSchedulerStub() { fetcherMap.put("jobscheduler", fetcher); }
            static Object newNoopJobSchedulerBinder() { return 1; /* JobScheduler.RESULT_SUCCESS */ }
            }""")
        self.root = root

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_each_verdict(self) -> None:
        aosp_root = self.root / "aosp"
        table = services.aosp_service_table(
            aosp_root / "frameworks-base/core/java/android/app/SystemServiceRegistry.java",
            aosp_root / "frameworks-base/core/java/android/content/Context.java",
            [aosp_root / "frameworks-base", aosp_root / "modules-scheduling"],
        )
        self.assertEqual(table["jobscheduler"]["manager"], "Landroid/app/job/JobScheduler;")
        self.assertEqual([b["name"] for b in table["notification"]["binders"]], ["notification"],
                         "a manager that fetches lazily must still name its binder")
        model = services.westlake_service_model(self.root / "westlake")
        rows = services.service_map([{"service": n} for n in table], table, model)
        verdict = {row["service"]: row["verdict"] for row in rows}
        self.assertEqual(verdict["location"], services.SUPPLIED)
        self.assertEqual(verdict["alarm"], services.NULL, "required binder with no provision → null manager")
        self.assertEqual(verdict["notification"], services.HOLLOW, "a bare Binder answers nothing")
        self.assertEqual(verdict["jobscheduler"], services.HOLLOW, "a no-op scheduler accepts jobs it never runs")
        self.assertEqual(verdict["accessibility"], services.INERT)
        self.assertEqual(verdict["layout_inflater"], services.SUPPLIED)
        self.assertEqual(verdict["camera"], services.UNRESOLVED, "no binder found must not read as supplied")


class PackageManagerSemantics(unittest.TestCase):
    def test_stub_bridged_and_direct_boot_defaults(self) -> None:
        with tempfile.TemporaryDirectory(prefix="westlake-pm-") as temp:
            root = Path(temp)
            pm = root / "framework/package-manager/java"
            _write(pm / "PackageManagerAdapter.java", """class PackageManagerAdapter {
                @Override
                public ServiceInfo getServiceInfo(ComponentName c, long f, int u) throws RemoteException {
                    logBridged("getServiceInfo", ""); return SourcePackageRegistry.find(c, f); }
                @Override
                public ParceledListSlice queryIntentServices(Intent i, String t, long f, int u) throws RemoteException {
                    logStub("queryIntentServices", ""); return null; }
                }""")
            _write(pm / "SourcePackageRegistry.java", "class SourcePackageRegistry { /* raw flags */ }")
            model = pm_adapter_model(root)
            self.assertEqual(model["methods"]["getServiceInfo"]["status"], "bridged")
            self.assertEqual(model["methods"]["queryIntentServices"]["status"], "stub")
            self.assertFalse(model["semantics"]["direct_boot_match_defaults"]["present"],
                             "raw caller flags reach PackageParser.isMatch and filter every component")

            facts = {"components": [{"kind": "service", "name": "x.ComponentDiscoveryService", "process": None,
                                     "direct_boot_aware": True, "meta_data": {"com.google.firebase.components:x.R": "v"},
                                     "init_order": None}],
                     "splits": [], "processes": []}
            scan = {"inventory": {"platform_method_names": {"Landroid/content/pm/PackageManager;": ["getServiceInfo"]}}}
            rows = {r["id"]: r for r in gapmap.package_manager_rows(scan, facts, model)}
            self.assertEqual(rows["pm:component-metadata"]["verdict"], "missing")
            self.assertEqual(rows["pm:component-metadata"]["probe"], "probes/service-metadata")


class AppFrameworkContracts(unittest.TestCase):
    _STUB = """class AppSpawnXInit {
        private static InvocationHandler makeStubHandler(final String label, final Set<String> hot) {
            return new InvocationHandler() {
                public Object invoke(Object proxy, Method method, Object[] args) {
                    String name = method.getName();
                    if ("asBinder".equals(name)) return proxy;
                    %s
                    return null;
                }
            };
        }
        static void install() { iamImpl = makeProxyStub("AdapterIAM-stub", "android.app.IActivityManager", hot); }
    }"""

    def _model(self, answers: str) -> dict:
        with tempfile.TemporaryDirectory(prefix="westlake-am-") as temp:
            root = Path(temp)
            _write(root / "framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java", self._STUB % answers)
            return direct_launch_am_model(root)

    def test_null_answers_are_read_from_the_stub(self) -> None:
        scan = {"inventory": {"platform_method_names": {
            "Landroid/app/ActivityManager;": ["getRunningAppProcesses", "getRunningServices", "getMemoryClass"],
            "Landroid/app/Dialog;": ["show", "dismiss"]}}}
        bare = self._model("")
        self.assertTrue(bare["proxy_stub"])
        self.assertEqual(bare["answered"], [], "asBinder outside the label block is not an answer")
        rows = {r["id"]: r for r in gapmap.app_framework_rows(scan, bare)}
        self.assertEqual(rows["am:process-table"]["verdict"], "null")
        self.assertIn("getServices", rows["am:process-table"]["provider"], "getRunningServices is answered by getServices")
        self.assertEqual(rows["wm:dialog-stacking"]["verdict"], "unverified")

        answered = self._model("""if ("AdapterIAM-stub".equals(label)) {
                        if ("getRunningAppProcesses".equals(name)) return CallerProcess.runningAppProcesses();
                        if ("getServices".equals(name)) { return CallerProcess.runningServices(); }
                    }""")
        self.assertEqual(answered["answered"], ["getRunningAppProcesses", "getServices"])
        rows = {r["id"]: r for r in gapmap.app_framework_rows(scan, answered)}
        self.assertEqual(rows["am:process-table"]["verdict"], "supplied")

    def test_window_semantics_from_source(self) -> None:
        with tempfile.TemporaryDirectory(prefix="westlake-wm-") as temp:
            root = Path(temp)
            adapter = root / "framework/window/java/WindowSessionAdapter.java"
            # A comment naming ViewRootImpl's computeFrames is not placement support.
            _write(adapter, """class WindowSessionAdapter {
                // ViewRootImpl calls mWindowLayout.computeFrames(...) in LOCAL_LAYOUT mode
                int addToDisplay() { if (shouldHoldBack(type, token)) return holdBack(); return 0; }
            }""")
            wm = window_adapter_model(root)
            self.assertTrue(wm["dialogs_above_base"]["present"])
            self.assertFalse(wm["placement_from_gravity"]["present"])
            self.assertFalse(wm["dim_behind"]["present"])
            scan = {"inventory": {"platform_method_names": {"Landroid/app/Dialog;": ["show"]}}}
            rows = {r["id"]: r for r in gapmap.app_framework_rows(scan, {"proxy_stub": False, "answered": [], "source": None}, wm)}
            self.assertEqual(rows["wm:dialog-stacking"]["verdict"], "supplied")
            self.assertEqual((rows["wm:window-placement"]["verdict"], rows["wm:window-placement"]["effort"]), ("missing", "S"))
            self.assertEqual(rows["wm:dim-behind"]["verdict"], "missing")

    def test_probe_results_apply_only_to_their_commit(self) -> None:
        def fresh():
            return {"provider": {"westlake": {"commit": "f4e0366953002a33"}},
                    "rows": [{"id": "wm:dialog-stacking", "probe": "probes/dialog-before-window", "verdict": "unverified",
                              "shim_class": "CU", "effort": "verify", "confidence": "static"},
                             {"id": "pm:providers", "probe": "probes/provider-manifest", "verdict": "unverified",
                              "shim_class": "CU", "effort": "verify", "confidence": "static"}]}
        results = {"results": [
            {"probe": "dialog-before-window", "westlake_commit": "f4e0366953002a33db50", "passed": False, "verdict": "FAIL",
             "effort": "M", "shim_class": "C6", "finding": "stacked by creation order"},
            {"probe": "provider-manifest", "westlake_commit": "0231db6053cd1b43", "passed": False, "verdict": "FAIL"},
            {"probe": "provider-manifest", "westlake_commit": "f4e0366953002a33db50", "passed": True, "verdict": "PASS"}]}
        gap = fresh()
        gapmap.apply_probe_results(gap, results)
        rows = {r["id"]: r for r in gap["rows"]}
        self.assertEqual((rows["wm:dialog-stacking"]["verdict"], rows["wm:dialog-stacking"]["effort"]), ("missing", "M"))
        self.assertEqual(rows["wm:dialog-stacking"]["confidence"], gapmap.PROBED)
        self.assertEqual(rows["pm:providers"]["verdict"], "supplied", "the pass on this commit, not the older failure")

        older = fresh()
        older["provider"]["westlake"]["commit"] = "75d82d5"
        gapmap.apply_probe_results(older, results)
        rows = {r["id"]: r for r in older["rows"]}
        self.assertEqual(rows["pm:providers"]["verdict"], "unverified", "a later build's result says nothing about this one")
        self.assertEqual(rows["pm:providers"]["probe_result"]["note"], "measured on other builds only")


class SandboxAndBacktest(unittest.TestCase):
    def test_realm_fifo_is_predicted(self) -> None:
        policy = {"oh": {"domain": "u:r:normal_hap:s0", "app_data_type": "u:object_r:appdat:s0",
                         "workaround_without_policy_change": "relabel",
                         "source_rules": {"fifo_granted_only_on_parent": "installs.te:199"},
                         "classes": {"fifo_file": {"allowed": False, "fixable_by_policy": True, "fix": "allow ..."},
                                     "file": {"allowed": True}}},
                  "android": {"classes": {"fifo_file": {"allowed": True}}}}
        scan = {"inventory": {"elfs": [{"soname": "librealmc.so", "name": "x", "undefined_symbols": ["mkfifo", "open"]},
                                       {"soname": "libplain.so", "name": "y", "undefined_symbols": ["open"]}],
                              "platform_method_names": {}}}
        rows = gapmap.sandbox_rows(scan, policy)
        self.assertEqual([r["id"] for r in rows], ["policy:fifo_file"])
        self.assertEqual(rows[0]["effort"], "OH")
        self.assertIn("librealmc.so:mkfifo", rows[0]["app_evidence"])

        results = gapmap.backtest({"rows": rows + [{"id": "pm:splits", "verdict": "supplied"}]}, [
            {"id": "B7", "symptom": "fifo EACCES", "predicted_by": ["policy:fifo_file"]},
            {"id": "B5", "symptom": "split", "predicted_by": ["pm:splits"]},
            {"id": "B9", "symptom": "unknown", "predicted_by": ["svc:none"]},
        ])
        self.assertEqual([r["outcome"] for r in results],
                         ["predicted", "missed: row claimed supplied", "missed: no row"])


if __name__ == "__main__":
    unittest.main()
