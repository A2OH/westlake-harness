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
from westlake_gap.contracts import (direct_launch_am_model, keystore_model, libc_constant_model,
                                    pm_adapter_model, window_adapter_model)
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

    def test_a_proxy_that_throws_is_strict_not_hollow(self) -> None:
        """Burger King: WebView's policy provider called UserManager.getApplicationRestrictions; the
        runtime-published user proxy threw, Chromium aborted. The static model had read the native
        runtime's seeded bare binder and called it hollow."""
        _write(self.root / "westlake/framework/android-runtime/src/AndroidRuntime.cpp",
               'static const char* kServices[] = { "notification", "user" };\n')
        _write(self.root / "westlake/framework/package-manager/java/OHUserManager.java", """class OHUserManager {
            static void install() {
                Object service = Proxy.newProxyInstance(loader, types, (proxy, method, arguments) -> {
                    String name = method.getName();
                    if (name.equals("asBinder")) return binder;
                    if (name.equals("isUserUnlocked")) return true;
                    throw new UnsupportedOperationException("OH user service does not implement " + name);
                });
                Field cache = ServiceManager.class.getDeclaredField("sCache");
                services.put("user", binder);
            }
        }""")
        model = services.westlake_service_model(self.root / "westlake")
        verdict, basis = services.provision_verdict(model["user"])
        self.assertEqual(verdict, services.STRICT, "published at run time over the seeded binder")
        self.assertEqual(basis["answered"], ["isUserUnlocked"])
        self.assertEqual(services.provision_verdict(model["notification"])[0], services.HOLLOW)

    def test_null_service_behind_a_kotlin_cast_throws(self) -> None:
        """Burger King: `getSystemService(UI_MODE_SERVICE) as UiModeManager` threw inside a JS host
        function, where McDonald's had survived the same null service by checking it."""
        aosp_root = self.root / "aosp"
        table = services.aosp_service_table(
            aosp_root / "frameworks-base/core/java/android/app/SystemServiceRegistry.java",
            aosp_root / "frameworks-base/core/java/android/content/Context.java",
            [aosp_root / "frameworks-base", aosp_root / "modules-scheduling"],
        )
        scan = {"inventory": {
            "service_requests": [{"service": "alarm", "owner": "Lx/A;", "method": "m"},
                                 {"service": "location", "owner": "Lx/B;", "method": "m"}],
            "nonnull_casts": [{"owner": "Lexpo/Alarms;", "method": "schedule", "type": "android.app.AlarmManager"},
                              {"owner": "Lx/B;", "method": "m", "type": "android.location.LocationManager"}]}}
        rows, _ = gapmap.service_rows(scan, table, services.westlake_service_model(self.root / "westlake"))
        rows = {r["id"]: r for r in rows}
        self.assertEqual(rows["svc:alarm"]["throws_if_null"], 1)
        self.assertIn("expo.Alarms.schedule", rows["svc:alarm"]["app_evidence"])
        self.assertEqual(rows["svc:location"]["throws_if_null"], 0, "supplied: the cast never sees null")


class FrameworkSideThrows(unittest.TestCase):
    MANAGER = """public class NotificationManager {
    public List<NotificationChannel> getNotificationChannels() {
        INotificationManager service = getService();
        try {
            return service.getNotificationChannels(mContext.getOpPackageName(), mContext.getPackageName(),
                    mContext.getUserId()).getList();
        } catch (RemoteException e) { throw e.rethrowFromSystemServer(); }
    }
    public NotificationChannel getNotificationChannel(String id) {
        return getService().getNotificationChannel(mContext.getOpPackageName(), mContext.getUserId(), id);
    }
}
"""

    def test_unwrapping_methods(self) -> None:
        self.assertEqual(services.unwrapping_methods(self.MANAGER), ["getNotificationChannels"],
                         "only a method that calls getList() on the binder's answer throws on null")

    def test_hollow_service_called_through_an_unwrapping_method(self) -> None:
        aosp = {"notification": {"manager": "Landroid/app/NotificationManager;", "binders": [],
                                 "source": "SystemServiceRegistry.java:1", "unwrapping_methods": ["getNotificationChannels"]}}
        westlake = {"notification": [{"kind": "hollow-proxy", "detail": "d", "source": "s"}]}
        scan = {"inventory": {"service_requests": [{"service": "notification", "owner": "Lapp/A;", "method": "m"}],
                              "platform_method_names": {"Landroid/app/NotificationManager;": ["getNotificationChannels"]}}}
        rows, _ = gapmap.service_rows(scan, aosp, westlake)
        row = rows[0]
        self.assertEqual(row["throws_in_framework"], ["getNotificationChannels"])
        self.assertIn("throws inside NotificationManager", row["app_evidence"])

    def test_empty_list_answers_do_not_throw(self) -> None:
        aosp = {"jobscheduler": {"manager": "Landroid/app/job/JobScheduler;", "binders": [],
                                 "source": "s:1", "unwrapping_methods": ["getAllPendingJobs"]}}
        westlake = {"jobscheduler": [{"kind": "hollow-proxy", "detail": "d", "source": "s", "empty_lists": True}]}
        scan = {"inventory": {"service_requests": [{"service": "jobscheduler", "owner": "Lapp/A;", "method": "m"}],
                              "platform_method_names": {"Landroid/app/job/JobScheduler;": ["getAllPendingJobs"]}}}
        rows, _ = gapmap.service_rows(scan, aosp, westlake)
        self.assertEqual(rows[0]["verdict"], "hollow", "jobs still never run")
        self.assertEqual(rows[0]["throws_in_framework"], [], "an empty slice is unwrapped without throwing")


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
                @Override
                public ProviderInfo resolveContentProvider(String a, long f, int u) throws RemoteException {
                    if (a == null) { logStub("resolveContentProvider", ""); return null; }
                    ProviderInfo info = find(a); return info; }
                }""")
            _write(pm / "SourcePackageRegistry.java", "class SourcePackageRegistry { /* raw flags */ }")
            model = pm_adapter_model(root)
            self.assertEqual(model["methods"]["getServiceInfo"]["status"], "bridged")
            self.assertEqual(model["methods"]["queryIntentServices"]["status"], "stub")
            self.assertEqual(model["methods"]["resolveContentProvider"]["status"], "bridged",
                             "logStub on a guard is not a stub when the method answers otherwise")
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

            _write(adapter, """class WindowSessionAdapter {
                Rect place() { new android.view.WindowLayout().computeFrames(attrs, state, safe, bounds,
                        mode, w, h, types, 1f, frames); return frames.frame; }
                float dim(LayoutParams attrs) { return (attrs.flags & FLAG_DIM_BEHIND) != 0 ? attrs.dimAmount : 0f; }
            }""")
            wm = window_adapter_model(root)
            self.assertTrue(wm["placement_from_gravity"]["present"], "a call to Android's WindowLayout places windows")
            self.assertTrue(wm["dim_behind"]["present"])

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


class StaticServiceAccessors(unittest.TestCase):
    """Wikipedia died in onCreate on a null AccountManager and its map had no row for the account
    service: the app never names it, AccountManager.get(context) asks the platform inside."""

    def test_accessor_counts_as_a_service_request(self) -> None:
        javac, d8 = shutil.which("javac"), _find_android_d8()
        if not javac or not d8:
            self.skipTest("javac and d8 are required for the executable fixture")
        with tempfile.TemporaryDirectory(prefix="westlake-accessor-") as temp:
            root = Path(temp)
            _write(root / "api/android/content/Context.java", "package android.content; public abstract class Context {}")
            _write(root / "api/android/accounts/AccountManager.java", """package android.accounts;
                import android.content.Context;
                public class AccountManager {
                    public static AccountManager get(Context c) { return null; }
                }""")
            _write(root / "app/fixture/Login.java", """package fixture;
                import android.accounts.AccountManager;
                import android.content.Context;
                public class Login {
                    static boolean isLoggedIn(Context c) { return AccountManager.get(c).getClass() != null; }
                }""")
            api, app, dex = root / "api-classes", root / "app-classes", root / "dex"
            for directory in (api, app, dex):
                directory.mkdir()
            _run(javac, "--release", "8", "-d", str(api), *map(str, (root / "api").rglob("*.java")))
            _run(javac, "--release", "8", "-cp", str(api), "-d", str(app), str(root / "app/fixture/Login.java"))
            _run(d8, "--min-api", "21", "--output", str(dex), str(app / "fixture/Login.class"))

            requests = inventory_dex(dex / "classes.dex").service_requests
            account = [r for r in requests if r.get("service") == "account"]
            self.assertEqual(len(account), 1, "AccountManager.get is a service request with no getSystemService call site")
            self.assertTrue(account[0]["via_static_accessor"])
            self.assertFalse(account[0]["dynamic"], "the name is known, it is just never written down by the app")


class KeystoreAndLoaderOrder(unittest.TestCase):
    """Burger King's two startup blockers: neither is an absent name.

    KeyStore exists in the boot jars; the provider the app names at run time was never installed.
    libc++_shared.so exists in the APK; the board's library of the same name was found first.
    """

    def test_provider_names_are_captured(self) -> None:
        javac, d8 = shutil.which("javac"), _find_android_d8()
        if not javac or not d8:
            self.skipTest("javac and d8 are required for the executable fixture")
        with tempfile.TemporaryDirectory(prefix="westlake-jca-") as temp:
            root = Path(temp)
            _write(root / "app/fixture/Keys.java", """package fixture;
                import java.security.KeyStore;
                import javax.crypto.KeyGenerator;
                public class Keys {
                    static final String STORE = "AndroidKeyStore";
                    static KeyStore store() throws Exception { return KeyStore.getInstance(STORE); }
                    static KeyGenerator aes() throws Exception { return KeyGenerator.getInstance("AES", "AndroidKeyStore"); }
                    static KeyStore file() throws Exception { return KeyStore.getInstance("PKCS12"); }
                }""")
            app, dex = root / "app-classes", root / "dex"
            for directory in (app, dex):
                directory.mkdir()
            _run(javac, "--release", "8", "-d", str(app), str(root / "app/fixture/Keys.java"))
            _run(d8, "--min-api", "21", "--output", str(dex), str(app / "fixture/Keys.class"))
            requests = inventory_dex(dex / "classes.dex").jca_requests
            calls = {(r["method"], r["api"], r.get("type"), r.get("provider")) for r in requests if r["api"] != "provider name"}
            self.assertIn(("aes", "KeyGenerator.getInstance", "AES", "AndroidKeyStore"), calls)
            self.assertIn(("store", "KeyStore.getInstance", "AndroidKeyStore", None), calls)
            self.assertIn(("file", "KeyStore.getInstance", "PKCS12", None), calls)
            self.assertIn("store", {r["method"] for r in requests if r["api"] == "provider name"},
                          "the constant is evidence even where it reaches getInstance as the type")

    def test_kotlin_nonnull_casts_are_captured(self) -> None:
        javac, d8 = shutil.which("javac"), _find_android_d8()
        if not javac or not d8:
            self.skipTest("javac and d8 are required for the executable fixture")
        with tempfile.TemporaryDirectory(prefix="westlake-cast-") as temp:
            root = Path(temp)
            # What kotlinc emits for `context.getSystemService(UI_MODE_SERVICE) as UiModeManager`.
            _write(root / "app/fixture/Casts.java", """package fixture;
                public class Casts {
                    static Object mode(Object service) {
                        if (service == null) throw new NullPointerException("null cannot be cast to non-null type android.app.UiModeManager");
                        return service;
                    }
                    static Object own(Object value) {
                        if (value == null) throw new NullPointerException("null cannot be cast to non-null type kotlin.String");
                        return value;
                    }
                }""")
            app, dex = root / "app-classes", root / "dex"
            for directory in (app, dex):
                directory.mkdir()
            _run(javac, "--release", "8", "-d", str(app), str(root / "app/fixture/Casts.java"))
            _run(d8, "--min-api", "21", "--output", str(dex), str(app / "fixture/Casts.class"))
            casts = inventory_dex(dex / "classes.dex").nonnull_casts
            self.assertEqual([(c["method"], c["type"]) for c in casts], [("mode", "android.app.UiModeManager")],
                             "platform types only")

    def test_keystore_verdict_from_source(self) -> None:
        scan = {"inventory": {"jca_requests": [
            {"owner": "Lnj/i$v;", "method": "a", "api": "provider name", "provider": "AndroidKeyStore"},
            {"owner": "Lgc/P;", "method": "a", "api": "KeyPairGenerator.getInstance", "type": "EC", "provider": "AndroidKeyStore"}]}}
        with tempfile.TemporaryDirectory(prefix="westlake-ks-") as temp:
            root = Path(temp)
            init = root / "framework/appspawn-x/java/Init.java"
            _write(init, """class Init {
                // Android calls AndroidKeyStoreProvider.install() here; we skip it.
                void preload() { Security.getProviders(); }
            }""")
            rows = gapmap.security_rows(scan, keystore_model(root))
            self.assertEqual(len(rows), 1)
            self.assertEqual((rows[0]["verdict"], rows[0]["shim_class"]), ("missing", "C4"), "a comment is not an install")
            self.assertIn('KeyPairGenerator.getInstance("EC")', rows[0]["app_evidence"])

            _write(init, "class Init { void preload() { AndroidKeyStoreProvider.install(); } }")
            self.assertEqual(gapmap.security_rows(scan, keystore_model(root))[0]["verdict"], "hollow",
                             "installed with nothing behind it")
            _write(root / "framework/security/java/Keystore2Adapter.java",
                   'class Keystore2Adapter { static final String NAME = "android.system.keystore2.IKeystoreService/default"; }')
            self.assertEqual(gapmap.security_rows(scan, keystore_model(root))[0]["verdict"], "supplied")

        with tempfile.TemporaryDirectory(prefix="westlake-ks-") as temp:
            root = Path(temp)
            _write(root / "framework/core/java/SoftKeys.java", """package adapter.core;
                public final class SoftKeys extends Provider {
                    public static void install(File dir) { Security.addProvider(new SoftKeys()); }
                    private SoftKeys() { super("AndroidKeyStore", 1.0, "software"); }
                }""")
            self.assertEqual(gapmap.security_rows(scan, keystore_model(root))[0]["verdict"], "missing",
                             "declared but never installed")
            _write(root / "framework/activity/java/Bind.java", "class Bind { void bind() { SoftKeys.install(dir); } }")
            row = gapmap.security_rows(scan, keystore_model(root))[0]
            self.assertEqual((row["verdict"], row["effort"]), ("supplied", "verify"))
            self.assertIn("not hardware-backed", row["provider"])
        self.assertEqual(gapmap.security_rows({"inventory": {"jca_requests": [
            {"owner": "La;", "method": "b", "api": "KeyStore.getInstance", "type": "PKCS12"}]}}, keystore_model(Path("/nonexistent"))), [])

    def test_libc_constant_namespace(self) -> None:
        """McDonald's Realm asked musl for the page size with bionic's selector number and was told
        1000, so its mmap offset was unaligned and the home dashboard died opening its database."""
        scan = {"inventory": {"elfs": [
            {"name": "lib/arm64-v8a/librealm-jni.so", "soname": "librealm-jni.so",
             "undefined_symbols": ["sysconf", "mmap", "open"]},
            {"name": "lib/arm64-v8a/libquiet.so", "soname": "libquiet.so", "undefined_symbols": ["open"]}]}}
        with tempfile.TemporaryDirectory(prefix="westlake-libc-") as temp:
            root = Path(temp)
            shim = root / "framework/webview-shim/webview_bionic_shim.c"
            _write(shim, """long sysconf(int name) {
                if (caller_is_webview(__builtin_return_address(0), &caller_path)) { return getpagesize(); }
                return real_sysconf(name);
            }""")
            model = libc_constant_model(root)
            self.assertEqual((model["translated"], model["scope"]), (["sysconf"], "webview-only"))
            row = gapmap.libc_constant_rows(scan, model)[0]
            self.assertEqual((row["verdict"], row["shim_class"], row["effort"]), ("missing", "C2", "S"))
            self.assertIn("librealm-jni.so", row["app_evidence"])

            _write(shim, """long sysconf(int name) {
                if (!caller_is_android_dso(__builtin_return_address(0), &caller_path)) { return real_sysconf(name); }
                return real_sysconf(westlake_bionic_sysconf[name]);
            }""")
            model = libc_constant_model(root)
            self.assertEqual(model["scope"], "packaged-libraries")
            self.assertEqual(gapmap.libc_constant_rows(scan, model)[0]["verdict"], "supplied")
            self.assertEqual(gapmap.libc_constant_rows({"inventory": {"elfs": [
                {"name": "x.so", "soname": "x.so", "undefined_symbols": ["open"]}]}}, model), [],
                "no row when nothing asks libc for a numbered limit")

    def test_webview_renderer_process(self) -> None:
        """Burger King: WebView bound its sandboxed renderer, direct launch had none, Chromium aborted."""
        scan = {"inventory": {"platform_method_names": {"Landroid/webkit/WebView;": ["<init>", "loadUrl"]}}}
        with tempfile.TemporaryDirectory(prefix="westlake-wv-") as temp:
            root = Path(temp)
            _write(root / "aosp/frameworks-base/core/java/android/webkit/WebViewDelegate.java", """class WebViewDelegate {
    public boolean isMultiProcessEnabled() {
        if (Flags.updateServiceV2()) {
            return true;
        }
        return WebViewFactory.getUpdateService().isMultiProcessEnabled();
    }
}""")
            model = gapmap.webview_process_model(root / "aosp", root / "westlake")
            row = gapmap.webview_rows(scan, model)[0]
            self.assertEqual((row["verdict"], row["effort"]), ("missing", "L"))
            self.assertIn("Flags.updateServiceV2()", row["provider"])
            self.assertEqual(gapmap.webview_rows({"inventory": {"platform_method_names": {}}}, model), [])

    def test_a_load_that_reports_success_without_opening_the_library(self) -> None:
        with tempfile.TemporaryDirectory(prefix="westlake-load-") as temp:
            art = Path(temp) / "art-build"
            _write(art / "stubs/openjdk_stub.c", """
static jstring Runtime_nativeLoad(JNIEnv* env, jclass clazz, jstring filename,
                                   jobject classLoader, jclass caller) {
    const char* path = (*env)->GetStringUTFChars(env, filename, NULL);
    if (strstr(path, "javacore") || strstr(path, "openjdk") ||
        strstr(path, "icu_jni") || strstr(path, "icu-jni")) {
        (*env)->ReleaseStringUTFChars(env, filename, path);
        return NULL; /* null = success, already registered */
    }
    return JVM_NativeLoad(env, filename, classLoader, caller);
}""")
            model = gapmap.native_load_short_circuit(art)
        self.assertEqual(model["names"], ["icu-jni", "icu_jni", "javacore", "openjdk"])
        self.assertTrue(model["source"].startswith("art-build/stubs/openjdk_stub.c:"))
        scan = {"inventory": {"elfs": [
            {"name": "lib/arm64-v8a/libjavacore.so", "soname": "libjavacore.so"},
            {"name": "lib/arm64-v8a/libplain.so", "soname": "libplain.so"}]}}
        row = gapmap.silent_load_rows(scan, model)[0]
        self.assertEqual((row["id"], row["verdict"], row["shim_class"]), ("load:silent-success", "hollow", "C3"))
        self.assertIn("libjavacore.so", row["item"])
        self.assertNotIn("libplain.so", row["item"])
        self.assertIn("matched on javacore", row["provider"])
        self.assertEqual(gapmap.silent_load_rows(
            {"inventory": {"elfs": [{"name": "a/libplain.so", "soname": "libplain.so"}]}}, model), [],
            "nothing matches the filter, nothing to claim")
        self.assertEqual(gapmap.native_load_short_circuit(None)["names"], [], "no runtime, no claim")
        self.assertEqual(gapmap.silent_load_rows(scan, {"names": [], "source": None}), [])

        # The runtime shipping such a library is the case that actually bit, and it is a different
        # claim: the filter is there because the runtime registers those natives itself, so the row
        # says "verify the per-method coverage", not "these are unbound".
        runtime = gapmap.silent_load_rows({"inventory": {"elfs": []}}, model,
                                          ["libicu_jni.so", "libhwui.so", "libjavacore.so"])
        self.assertEqual([r["id"] for r in runtime], ["load:runtime-silent-success"])
        self.assertEqual((runtime[0]["verdict"], runtime[0]["effort"]), ("unresolved", "verify"))
        self.assertIn("libicu_jni.so", runtime[0]["item"])
        self.assertIn("libjavacore.so", runtime[0]["item"])
        self.assertNotIn("libhwui.so", runtime[0]["item"])
        self.assertEqual(gapmap.silent_load_rows({"inventory": {"elfs": []}}, model, ["libhwui.so"]), [])
        self.assertEqual(gapmap.silent_load_rows({"inventory": {"elfs": []}}, model, None), [])

    def test_symbols_looked_up_at_runtime_are_reported_as_candidates(self) -> None:
        # Only names in the public NDK surface are reported: a string of the right shape is not
        # evidence of a lookup, and an engine carries thousands of them.
        coverage = {"symbols": [
            {"symbol": "ASurfaceControl_createFromWindow", "library": "libandroid.so", "status": "missing"},
            {"symbol": "AMediaCodec_createDecoderByType", "library": "libmediandk.so", "status": "missing"},
            {"symbol": "ANativeWindow_lock", "library": "libnativewindow.so", "status": "oh"},
        ]}
        scan = {"inventory": {"elfs": [{
            "name": "lib/arm64-v8a/libengine.so", "soname": "libengine.so",
            "runtime_symbol_candidates": [
                "ASurfaceControl_createFromWindow",   # NDK, not supplied -> reported
                "AMediaCodec_createDecoderByType",    # NDK, not supplied -> reported
                "ANativeWindow_lock",                 # NDK but supplied  -> not a gap
                "SomeVendor_privateThing",            # not in the NDK    -> not a claim
            ]}]}}
        rows = {r["id"]: r for r in gapmap.runtime_resolved_rows(scan, coverage)}
        self.assertEqual(sorted(rows), ["sym:runtime-resolved:libandroid.so",
                                        "sym:runtime-resolved:libmediandk.so"])
        row = rows["sym:runtime-resolved:libandroid.so"]
        self.assertEqual((row["verdict"], row["decidable_by"]), ("unresolved", "probe"),
                         "a string is not a lookup: the board settles it, not the scan")
        self.assertEqual(row["symbols"], ["ASurfaceControl_createFromWindow"])
        self.assertIn("libengine.so", row["provider"])
        self.assertEqual(gapmap.runtime_resolved_rows(scan, None), [], "no NDK surface, no claim")
        self.assertEqual(gapmap.runtime_resolved_rows(scan, {"symbols": []}), [])

    def test_shadowed_libraries_and_their_importers(self) -> None:
        scan = {"inventory": {"elfs": [
            {"name": "config.arm64_v8a.apk!lib/arm64-v8a/libc++_shared.so", "soname": "libc++_shared.so", "needed": ["libc.so"]},
            {"name": "lib/arm64-v8a/libjsi.so", "soname": "libjsi.so", "needed": ["libc++_shared.so", "libc.so"]},
            {"name": "lib/arm64-v8a/libreactnative.so", "soname": "libreactnative.so", "needed": ["libjsi.so", "libc.so"]},
            {"name": "lib/arm64-v8a/libplain.so", "soname": "libplain.so", "needed": ["libc.so", "liblog.so"]}]}}
        board = ["/system/lib64/libc++_shared.so", "/system/lib64/libc.so", "/data/app/libjsi.so"]
        shadowed, targets = gapmap.shadowed_libraries(scan, board)
        self.assertEqual(shadowed, {"libc++_shared.so": "/system/lib64/libc++_shared.so"})
        self.assertEqual(targets, ["libc++_shared.so", "libjsi.so", "libreactnative.so"], "reached through libjsi.so")
        facts = {"extract_native_libs": True}
        with tempfile.TemporaryDirectory(prefix="westlake-ns-") as temp:
            launcher = Path(temp)
            _write(launcher / "tools/probe_source_app.py", "parser.add_argument('--android-native-target', action='append')")
            rows = gapmap.native_loading_rows(facts, scan, {"present": True}, board, gapmap.launcher_namespace_option(launcher))
        row = rows[0]
        self.assertEqual((row["id"], row["shim_class"], row["effort"]), ("load:shadowed-by-board", "C3", "XS"))
        self.assertEqual(row["launch_args"][:2], ["--android-native-target", "libc++_shared.so"])
        self.assertEqual(gapmap.native_loading_rows(facts, scan, {"present": True}, []), [], "no board listing, no claim")


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
