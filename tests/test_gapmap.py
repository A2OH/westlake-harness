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
from westlake_gap import contracts, gapmap, services
from westlake_gap.contracts import (direct_launch_am_model, feature_claims_model, keystore_model,
                                    libc_constant_model, pm_adapter_model, window_adapter_model)
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

    def test_a_null_checked_service_result_is_marked(self) -> None:
        """clauncher: R8 compiles Kotlin's non-null check to getClass() on the manager, so a null
        getSystemService("device_policy") threw in HomeFragment; no cast message marks it."""
        javac, d8 = shutil.which("javac"), _find_android_d8()
        if not javac or not d8:
            self.skipTest("javac and d8 are required for the executable fixture")
        with tempfile.TemporaryDirectory(prefix="westlake-nullcheck-") as temp:
            root = Path(temp)
            _write(root / "api/android/content/Context.java", """package android.content;
                public abstract class Context { public abstract Object getSystemService(String name); }""")
            _write(root / "app/fixture/ChecksServices.java", """package fixture;
                import android.content.Context;
                public class ChecksServices {
                    static Object compiledCheck(Context c) { Object m = c.getSystemService("device_policy"); m.getClass(); return m; }
                    static Object required(Context c) { return java.util.Objects.requireNonNull(c.getSystemService("uimode")); }
                    static Object unchecked(Context c) { Object m = c.getSystemService("alarm"); return m; }
                    static void discarded(Context c, Object other) { c.getSystemService("power"); other.getClass(); }
                }""")
            api, app, dex = root / "api-classes", root / "app-classes", root / "dex"
            for directory in (api, app, dex):
                directory.mkdir()
            _run(javac, "--release", "8", "-d", str(api), *map(str, (root / "api").rglob("*.java")))
            _run(javac, "--release", "8", "-cp", str(api), "-d", str(app), str(root / "app/fixture/ChecksServices.java"))
            _run(d8, "--min-api", "21", "--output", str(dex), str(app / "fixture/ChecksServices.class"))

            by_method = {r["method"]: r for r in inventory_dex(dex / "classes.dex").service_requests}
            self.assertTrue(by_method["compiledCheck"].get("null_checked"))
            self.assertTrue(by_method["required"].get("null_checked"))
            self.assertFalse(by_method["unchecked"].get("null_checked"))
            self.assertFalse(by_method["discarded"].get("null_checked"), "a discarded result is not the value checked")

    def test_feature_queries_name_the_feature(self) -> None:
        javac, d8 = shutil.which("javac"), _find_android_d8()
        if not javac or not d8:
            self.skipTest("javac and d8 are required for the executable fixture")
        with tempfile.TemporaryDirectory(prefix="westlake-features-") as temp:
            root = Path(temp)
            _write(root / "api/android/content/pm/PackageManager.java", """package android.content.pm;
                public abstract class PackageManager {
                    public static final String FEATURE_CAMERA = "android.hardware.camera";
                    public abstract boolean hasSystemFeature(String name);
                    public abstract boolean hasSystemFeature(String name, int version);
                }""")
            _write(root / "app/fixture/AsksFeatures.java", """package fixture;
                import android.content.pm.PackageManager;
                public class AsksFeatures {
                    static boolean camera(PackageManager pm) { return pm.hasSystemFeature(PackageManager.FEATURE_CAMERA); }
                    static boolean versioned(PackageManager pm) { return pm.hasSystemFeature("android.hardware.vulkan.level", 1); }
                    static boolean computed(PackageManager pm, String name) { return pm.hasSystemFeature(name); }
                }""")
            api, app, dex = root / "api-classes", root / "app-classes", root / "dex"
            for directory in (api, app, dex):
                directory.mkdir()
            _run(javac, "--release", "8", "-d", str(api), *map(str, (root / "api").rglob("*.java")))
            _run(javac, "--release", "8", "-cp", str(api), "-d", str(app), str(root / "app/fixture/AsksFeatures.java"))
            _run(d8, "--min-api", "21", "--output", str(dex), str(app / "fixture/AsksFeatures.class"))

            by_method = {q["method"]: q for q in inventory_dex(dex / "classes.dex").feature_queries}
            self.assertEqual(by_method["camera"]["feature"], "android.hardware.camera", "the constant is inlined at the call")
            self.assertEqual(by_method["versioned"]["feature"], "android.hardware.vulkan.level")
            self.assertIsNone(by_method["computed"]["feature"], "a computed name must be reported, not guessed")


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

    def test_a_claimed_feature_needs_its_service(self) -> None:
        """FairScan: hasSystemFeature claimed a back camera that no Android camera service listed;
        CameraX expected it, found no camera, and retried its init until it failed."""
        _write(self.root / "westlake/framework/package-manager/java/PackageManagerAdapter.java", """class PackageManagerAdapter {
            @Override
            public boolean hasSystemFeature(String name, int version) {
                switch (name) {
                    case "android.software.webview":
                        return getSideloadedWebViewPackageInfo() != null;
                    // a comment between the labels
                    case "android.hardware.touchscreen":
                    case "android.hardware.camera":
                    case "android.hardware.location.gps":
                        return true;
                    case "android.hardware.nfc":
                        return false;
                    default:
                        return false;
                }
            }
        }""")
        claims = feature_claims_model(self.root / "westlake")
        self.assertEqual(claims["claimed"], ["android.hardware.camera", "android.hardware.location.gps",
                                             "android.hardware.touchscreen"])
        self.assertEqual(claims["conditional"], {"android.software.webview": "getSideloadedWebViewPackageInfo() != null"})
        aosp_root = self.root / "aosp"
        table = services.aosp_service_table(
            aosp_root / "frameworks-base/core/java/android/app/SystemServiceRegistry.java",
            aosp_root / "frameworks-base/core/java/android/content/Context.java",
            [aosp_root / "frameworks-base", aosp_root / "modules-scheduling"],
        )
        site = {"owner": "Lx/A;", "method": "m", "offset": 4}
        scan = {"inventory": {"feature_queries": [
            {**site, "feature": "android.hardware.camera"}, {**site, "feature": "android.hardware.location.gps"},
            {**site, "feature": "android.hardware.touchscreen"}, {**site, "feature": "android.hardware.nfc"},
            {**site, "feature": None}]}}
        rows = {r["id"]: r for r in gapmap.feature_rows(scan, claims, table, services.westlake_service_model(self.root / "westlake"))}
        self.assertEqual(rows["feature:android.hardware.camera"]["verdict"], "contradicted")
        self.assertEqual(rows["feature:android.hardware.location.gps"]["verdict"], "supplied")
        self.assertNotIn("feature:android.hardware.touchscreen", rows, "no service backs a form factor")
        self.assertNotIn("feature:android.hardware.nfc", rows, "a feature reported absent promises nothing")

    def test_feature_table_claims_with_versions(self) -> None:
        """The claims can live in a CLAIMED_FEATURES table with versions; the WebView answer stays
        conditional."""
        _write(self.root / "westlake/framework/package-manager/java/PackageManagerAdapter.java", """class PackageManagerAdapter {
            @Override
            public boolean hasSystemFeature(String name, int version) {
                if ("android.software.webview".equals(name)) {
                    return getSideloadedWebViewPackageInfo() != null;
                }
                Integer claimed = name != null ? CLAIMED_FEATURES.get(name) : null;
                return claimed != null && claimed >= version;
            }
            private static final int VULKAN_API_VERSION = (1 << 22) | (2 << 12);  // 1.2.0
            private static final java.util.Map<String, Integer> CLAIMED_FEATURES = new java.util.LinkedHashMap<>();
            static {
                CLAIMED_FEATURES.put("android.hardware.touchscreen", 0);
                CLAIMED_FEATURES.put("android.hardware.vulkan.version", VULKAN_API_VERSION);
            }
        }""")
        claims = feature_claims_model(self.root / "westlake")
        self.assertEqual(claims["claimed"], ["android.hardware.touchscreen", "android.hardware.vulkan.version"])
        self.assertEqual(claims["versions"]["android.hardware.vulkan.version"], 0x402000)
        self.assertEqual(claims["conditional"], {"android.software.webview": "getSideloadedWebViewPackageInfo() != null"})

    def test_vulkan_feature_must_match_the_runtime_loader(self) -> None:
        """Godot (duckrun): unclaimed Vulkan sent its Java side to an OpenGL view while its engine,
        finding the runtime's libvulkan, chose Vulkan and had no window."""
        site = {"owner": "Lorg/godotengine/godot/Godot;", "method": "meetsVulkanRequirements", "offset": 50}
        scan = {"inventory": {"feature_queries": [{**site, "feature": "android.hardware.vulkan.version"}]}}
        unclaimed = {"claimed": ["android.hardware.touchscreen"], "versions": {}, "source": "PM.java:1"}
        claimed = {"claimed": ["android.hardware.vulkan.version"],
                   "versions": {"android.hardware.vulkan.version": 0x402000}, "source": "PM.java:1"}
        row = gapmap.vulkan_feature_rows(scan, unclaimed, ["libvulkan.so"])[0]
        self.assertEqual((row["id"], row["verdict"]), ("feature:android.hardware.vulkan.version", "contradicted"))
        row = gapmap.vulkan_feature_rows(scan, claimed, ["libvulkan.so"])[0]
        self.assertEqual(row["verdict"], "supplied")
        self.assertIn("Vulkan 1.2.0", row["provider"])
        self.assertEqual(gapmap.vulkan_feature_rows(scan, claimed, [])[0]["verdict"], "contradicted",
                         "a claim with no loader sends the app to a Vulkan that is not there")
        self.assertEqual(gapmap.vulkan_feature_rows(scan, unclaimed, []), [], "absent and unclaimed agree")
        self.assertEqual(gapmap.vulkan_feature_rows({"inventory": {}}, unclaimed, ["libvulkan.so"]), [])

    def test_versioned_import_clash_is_supplied_name_by_name(self) -> None:
        """Fennec: free@libmozglue.so bound to musl's free; the shim's non-default libmozglue.so
        forwarders restore libmozglue's own, for the names they forward."""
        clashes = [{"symbol": "free", "version": "libmozglue", "importing_libraries": ["libxul.so"],
                    "versioned_clash": True},
                   {"symbol": "malloc", "version": "libmozglue", "importing_libraries": ["libxul.so", "libnss3.so"],
                    "versioned_clash": True}]
        row = gapmap.versioned_clash_rows(clashes, {"LIBC": {"open"}})[0]
        self.assertEqual((row["id"], row["verdict"]), ("abi:versioned-import-clash", "missing"))
        self.assertEqual(row["open_symbols"], ["free@libmozglue", "malloc@libmozglue"])
        forwarders = {"libmozglue.so": {"free", "malloc"}}
        self.assertEqual(gapmap.versioned_clash_rows(clashes, forwarders)[0]["verdict"], "supplied")
        mixed = clashes + [{"symbol": "sqlite3_open", "version": "libnss3", "importing_libraries": ["libxul.so"],
                            "versioned_clash": True},
                           {"symbol": "_ZdlPvm", "version": "libmozglue", "importing_libraries": ["libxul.so"],
                            "versioned_clash": True}]
        row = gapmap.versioned_clash_rows(mixed, forwarders)[0]
        self.assertEqual((row["verdict"], row["open_symbols"]), ("missing", ["sqlite3_open@libnss3", "_ZdlPvm@libmozglue"]),
                         "a name the shim does not forward is open, whatever else its version covers")
        self.assertEqual(gapmap.versioned_clash_rows([], {}), [])
        _write(self.root / "westlake/framework/webview-shim/webview_bionic_shim.c", """
#define WL_MOZGLUE_FORWARD(index, ret, name, params, args)                                      \\
    ret westlake_mozglue_##name params { return ((ret (*) params) entry(index)) args; }         \\
    __asm__(".symver westlake_mozglue_" #name ", " #name "@libmozglue.so");
WL_MOZGLUE_FORWARD(WL_MOZ_MALLOC, void *, malloc, (size_t size), (size))
WL_MOZGLUE_FORWARD(WL_MOZ_POSIX_MEMALIGN, int, posix_memalign, (void **out, size_t alignment, size_t size),
                   (out, alignment, size))
void westlake_mozglue__ZdlPvm(void *pointer, size_t size) { }
__asm__(".symver westlake_mozglue__ZdlPvm, _ZdlPvm@libmozglue.so");
/* __asm__(".symver westlake_old, old@libmozglue.so"); */
""")
        self.assertEqual(contracts.shim_versioned_definitions(self.root / "westlake"),
                         {"libmozglue.so": {"malloc", "posix_memalign", "_ZdlPvm"}})
        _write(self.root / "westlake/framework/webview-shim/webview_bionic_shim.map",
               "/* comment {not a node} */\nLIBC_N {\n global: x;\n};\nlibmozglue.so {\n};\nLIBC {\n global: *;\n} LIBC_N;\n")
        self.assertEqual(contracts.shim_version_nodes(self.root / "westlake"), {"LIBC_N", "libmozglue.so", "LIBC"})

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


class FrameworkNatives(unittest.TestCase):
    RUNTIME = {"bridge_libraries": [{"jni_registration_entries": [{"name": "_nativeClassInit", "signature": "()V"}]}],
               "classes": {
                   "Landroid/opengl/EGL14;": {"native_methods": ["_nativeClassInit()V", "eglGetDisplay(I)Landroid/opengl/EGLDisplay;"]},
                   "Landroid/opengl/GLES20;": {"native_methods": ["glClear(I)V"]},
                   "Landroid/os/ParcelFileDescriptor;": {"native_methods": ["native_close$ravenwood(Ljava/io/FileDescriptor;)V"]}}}
    SCAN = {"inventory": {"platform_method_names": {"Landroid/opengl/EGL14;": ["eglGetDisplay"],
                                                    "Landroid/opengl/GLES20;": ["glClear"],
                                                    "Landroid/os/ParcelFileDescriptor;": ["close"]}}}

    def test_a_class_no_runtime_library_names_is_unbound(self) -> None:
        rows = {r["id"]: r for r in gapmap.framework_native_rows(self.SCAN, self.RUNTIME,
                                                                 {"android/opengl/GLES20", "#glClear"})}
        self.assertEqual(set(rows), {"jni:android.opengl.EGL14"},
                         "GLES20 is named by a runtime library; ravenwood natives never run on a device")
        egl = rows["jni:android.opengl.EGL14"]
        self.assertEqual(egl["open_symbols"], ["_nativeClassInit()V"],
                         "another class's _nativeClassInit()V registration does not bind EGL14's")
        self.assertIn("class initializer", egl["app_evidence"])

    def test_a_named_class_is_bound_only_for_the_method_names_its_library_holds(self) -> None:
        runtime = {"classes": {"Landroid/media/AudioTrack;": {
            "native_methods": ["native_start()V", "native_getParameters()I", "native_get_buffer_size_frames()I"]}}}
        scan = {"inventory": {"platform_method_names": {"Landroid/media/AudioTrack;": [
            "native_start", "native_getParameters", "native_get_buffer_size_frames"]}}}
        strings = {"android/media/AudioTrack", "#native_start", "#native_getParameters_merged_tail",
                   "#xnative_getParameters"}
        row = gapmap.framework_native_rows(scan, runtime, strings)[0]
        self.assertEqual(row["open_symbols"], ["native_get_buffer_size_frames()I"],
                         "a name stored as the tail of a longer string still counts")

    def test_a_wrapper_reaching_an_unbound_native_flags_the_natives_class(self) -> None:
        runtime = {"bridge_libraries": [{"jni_registration_entries": [
                       {"name": "native_start", "signature": "()V"},
                       {"name": "getDevices", "signature": "()I"}]}],
                   "classes": {
                       "Landroid/media/AudioTrack;": {
                           "native_methods": ["native_start()V", "native_get_buffer_size_frames()I"],
                           "native_calls": {"play()V": ["Landroid/media/AudioTrack;->native_start()V"],
                                            "getBufferSizeInFrames()I":
                                                ["Landroid/media/AudioTrack;->native_get_buffer_size_frames()I"]}},
                       "Landroid/media/AudioManager;": {
                           "native_methods": [],
                           "native_calls": {"getParameters(Ljava/lang/String;)Ljava/lang/String;":
                                                ["Landroid/media/AudioSystem;->getParameters(Ljava/lang/String;)Ljava/lang/String;"]}},
                       "Landroid/media/AudioSystem;": {
                           "native_methods": ["getDevices()I", "getParameters(Ljava/lang/String;)Ljava/lang/String;"]}}}
        played = {"inventory": {"platform_method_names": {"Landroid/media/AudioTrack;": ["play"]}}}
        self.assertEqual(gapmap.framework_native_rows(played, runtime), [],
                         "play reaches only a registered native")
        sized = {"inventory": {"platform_method_names": {"Landroid/media/AudioTrack;": ["play", "getBufferSizeInFrames"],
                                                         "Landroid/media/AudioManager;": ["getParameters"]}}}
        rows = {r["id"]: r for r in gapmap.framework_native_rows(sized, runtime)}
        self.assertEqual(set(rows), {"jni:android.media.AudioTrack", "jni:android.media.AudioSystem"},
                         "AudioSystem is flagged though the app never names it")
        self.assertEqual(rows["jni:android.media.AudioTrack"]["open_symbols"], ["native_get_buffer_size_frames()I"])
        self.assertIn("AudioManager.getParameters", rows["jni:android.media.AudioSystem"]["app_evidence"])


class LifecycleNatives(unittest.TestCase):
    RUNTIME = {"classes": {
        "Landroid/app/ActivityThread;": {"native_methods": ["nPurgePendingResources()V"], "native_calls": {
            "handleTrimMemory(I)V": ["Landroid/app/ActivityThread;->nPurgePendingResources()V"],
            "handleLowMemory()V": ["Landroid/database/sqlite/SQLiteGlobal;->nativeReleaseMemory()I"],
            "getApplication()Landroid/app/Application;": ["Landroid/os/Binder;->getCallingUid()I"]}},
        "Landroid/database/sqlite/SQLiteGlobal;": {"native_methods": ["nativeReleaseMemory()I"]}}}

    def test_buffer_classes_reach_libcore_memory(self) -> None:
        """Instagram: CharBuffer.get(char[]) on a view over a byte[] reaches HeapByteBuffer and then
        Memory.unsafeBulkGet, behind virtual dispatch the native-call index does not follow."""
        runtime = {"bridge_libraries": [{"name": "libart.so", "jni_registration_entries": [
                       {"name": "peekIntArray", "signature": "(J[IIIZ)V"}]}],
                   "classes": {"Llibcore/io/Memory;": {"native_methods": [
                       "peekIntArray(J[IIIZ)V", "unsafeBulkGet(Ljava/lang/Object;II[BIIZ)V"]}}}
        scan = {"inventory": {"platform_method_names": {"Ljava/nio/CharBuffer;": ["get"]}}}
        rows = {r["id"]: r for r in gapmap.framework_native_rows(scan, runtime)}
        row = rows["jni:libcore.io.Memory"]
        self.assertEqual(row["open_symbols"], ["unsafeBulkGet(Ljava/lang/Object;II[BIIZ)V"])
        self.assertIn("CharBuffer (its heap or direct buffer implementation)", row["app_evidence"])

    def test_natives_the_framework_reaches_are_flagged_for_every_app(self) -> None:
        strings = {"android/database/sqlite/SQLiteGlobal", "#nativeReleaseMemory", "android/app/ActivityThread"}
        rows = {r["id"]: r for r in gapmap.lifecycle_native_rows(self.RUNTIME, strings)}
        self.assertEqual(set(rows), {"jni-lifecycle:android.app.ActivityThread.nPurgePendingResources"},
                         "a bound native is not flagged; a non-entry method is not followed")
        self.assertIn("ActivityThread.handleTrimMemory", rows[
            "jni-lifecycle:android.app.ActivityThread.nPurgePendingResources"]["app_evidence"])

    def test_nothing_without_the_runtime_libraries(self) -> None:
        self.assertEqual(gapmap.lifecycle_native_rows(self.RUNTIME, None), [])


class BlockersLedger(unittest.TestCase):
    def test_rows_that_blocked_an_app_are_marked(self) -> None:
        rows = [{"id": "svc:notification", "verdict": "hollow"}, {"id": "svc:alarm", "verdict": "supplied"}]
        ledger = {"blockers": [{"app": "tusky", "corpus": "corpus-2", "row": "svc:notification", "fixed_in": "886b89b"},
                               {"app": "davx5", "corpus": "corpus-3", "row": None, "fixed_in": None}]}
        gapmap.apply_ledger(rows, ledger)
        self.assertEqual(rows[0]["seen_blocking"], ["tusky (corpus-2), fixed in 886b89b"])
        self.assertNotIn("seen_blocking", rows[1])


class EngineSurface(unittest.TestCase):
    def test_engine_library_or_native_activity(self) -> None:
        gdx = {"apk": {"target_abi": "arm64-v8a"}, "inventory": {"elfs": [
            {"soname": "libgdx.so", "abi": "arm64-v8a"}], "launch_activity_chains": {"a.L": ["Lp;", "Landroid/app/Activity;"]}}}
        rows = gapmap.engine_surface_rows(gdx)
        self.assertEqual([r["id"] for r in rows], ["window:engine-surface"])
        self.assertIn("libGDX", rows[0]["app_evidence"])
        native = {"inventory": {"elfs": [], "launch_activity_chains": {
            "o.P": ["Lorg/ppsspp/ppsspp/NativeActivity;", "Landroid/app/Activity;"]}}}
        self.assertEqual(len(gapmap.engine_surface_rows(native)), 1)
        plain = {"inventory": {"elfs": [{"soname": "libsqlite.so"}],
                               "launch_activity_chains": {"a.M": ["Landroidx/appcompat/app/AppCompatActivity;"]}}}
        self.assertEqual(gapmap.engine_surface_rows(plain), [])
        # usp: a GL renderer of its own in a GLSurfaceView, no engine library.
        renderer = {"inventory": {"elfs": [{"soname": "libusp.so"}], "launch_activity_chains": {},
                                  "platform_method_names": {"Landroid/opengl/GLSurfaceView;": ["setRenderer", "onPause"]}}}
        rows = gapmap.engine_surface_rows(renderer)
        self.assertEqual(([r["id"] for r in rows], rows[0]["app_evidence"]),
                         (["window:engine-surface"], "sets a GLSurfaceView renderer"))


class ShowWallpaper(unittest.TestCase):
    def test_a_theme_that_shows_the_wallpaper(self) -> None:
        """clauncher, cclauncher: their launch activities' themes inherit windowShowWallpaper."""
        from westlake_gap import scanner

        class Value:
            def __init__(self, data, data_type=0x12):
                self.data, self.data_type = data, data_type

        class Entry:
            def __init__(self, parent, items):
                self.item = type("Complex", (), {"id_parent": parent, "items": items})()

            def is_complex(self):
                return True

        styles = {0x7F110001: Entry(0x7F110002, []),                                   # AppTheme -> Base
                  0x7F110002: Entry(0x0103005F, [(0x01010054, Value(0x7F080001, 0x01))]),  # Base -> Theme.Wallpaper.NoTitleBar
                  0x7F110003: Entry(0x01030237, [(scanner._SHOW_WALLPAPER, Value(0xFFFFFFFF))]),
                  0x7F110004: Entry(0x0103005E, [(scanner._SHOW_WALLPAPER, Value(0))])}  # says no, over a wallpaper theme
        resources = type("Resources", (), {"get_res_configs": lambda self, rid: [(None, styles[rid])] if rid in styles else []})()
        self.assertTrue(scanner._shows_wallpaper(resources, 0x7F110001, set()))
        self.assertTrue(scanner._shows_wallpaper(resources, 0x7F110003, set()))
        self.assertFalse(scanner._shows_wallpaper(resources, 0x7F110004, set()))
        self.assertFalse(scanner._shows_wallpaper(resources, 0x01030237, set()), "Theme.Material.NoActionBar does not")
        scan = {"apk": {"main_activities": ["app.clauncher.MainActivity"],
                        "wallpaper_activities": ["app.clauncher.MainActivity", "app.clauncher.helper.FakeHomeActivity"]}}
        rows = gapmap.wallpaper_rows(scan)
        self.assertEqual([(r["id"], r["verdict"], r["app_evidence"]) for r in rows],
                         [("wm:show-wallpaper", "missing", "its launch activity MainActivity shows the wallpaper")])
        self.assertEqual(rows[0]["launch_activities"], ["app.clauncher.MainActivity"])
        self.assertEqual(gapmap.wallpaper_rows({"apk": {"wallpaper_activities": []}}), [])


class SurfaceViewOpacity(unittest.TestCase):
    def test_an_engines_own_window_needs_marking_opaque(self) -> None:
        """PPSSPP, routed: its SurfaceView's OH window blended alpha-0 frames with the host screen."""
        gdx = {"apk": {"target_abi": "arm64-v8a"}, "inventory": {"elfs": [
            {"soname": "libgdx.so", "abi": "arm64-v8a"}], "launch_activity_chains": {}}}
        own = {"own_surface": True, "evidence": "WindowSessionAdapter.java:557"}
        rows = gapmap.engine_surface_rows(gdx, own)
        self.assertEqual([(r["id"], r["verdict"]) for r in rows],
                         [("window:engine-surface", "supplied"), ("window:surfaceview-opacity", "missing")])
        rows = gapmap.engine_surface_rows(gdx, dict(own, opaque="WindowSessionAdapter.java:592"))
        self.assertEqual(rows[1]["verdict"], "supplied")
        self.assertEqual([r["id"] for r in gapmap.engine_surface_rows(gdx, {"own_surface": False})],
                         ["window:engine-surface"], "a SurfaceView sharing its window has no window to mark")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            # The window's own node marked opaque: no effect on the board, not counted.
            _write(root / "framework/window/java/WindowSessionAdapter.java",
                   "class W {\n    public static int attachSurfaceView(Object v, SurfaceControl blast) {\n"
                   "        new SurfaceControl.Transaction().setOpaque(blast, true).apply();\n        return 0;\n    }\n}\n")
            self.assertIsNone(gapmap.surfaceview_model(root, None, [])["opaque"])
            _write(root / "framework/window/jni/oh_window_manager_client.cpp",
                   "void f() {\n    wl_contentNode->SetSurfaceBufferOpaque(true);\n}\n")
            self.assertEqual(gapmap.surfaceview_model(root, None, [])["opaque"], "oh_window_manager_client.cpp:2")


class ObservedPath(unittest.TestCase):
    def test_engine_framework_natives_and_lookups(self) -> None:
        rows = [
            gapmap._row("window", "window:engine-surface", "e", engine_libraries=["libflutter.so"]),
            gapmap._row("framework-natives", "jni:android.media.MediaPlayer", "m"),
            gapmap._row("framework-natives", "jni:android.hardware.Camera", "c"),
            gapmap._row("native-symbols", "sym:runtime-resolved:libandroid.so", "l", importing_libraries=["libflutter.so"]),
            gapmap._row("native-symbols", "sym:runtime-resolved:libnativewindow.so", "n", importing_libraries=["libvlc.so"]),
        ]
        observed = {"platform_touch": {}, "executed_app_methods": [], "executed_methods": 1,
                    "executed_platform_classes": ["Landroid/media/MediaPlayer;"],
                    "loaded_app_libraries": ["libflutter.so"]}
        gap_map = {"rows": rows}
        gapmap.apply_observed(gap_map, {"inventory": {}}, observed, {})
        on = {r["id"]: r["observed"]["on_path"] for r in gap_map["rows"]}
        self.assertEqual(on, {"window:engine-surface": True, "jni:android.media.MediaPlayer": True,
                              "jni:android.hardware.Camera": False,
                              "sym:runtime-resolved:libandroid.so": True,
                              "sym:runtime-resolved:libnativewindow.so": False})


class RuntimeData(unittest.TestCase):
    def test_rows_from_calls_and_path_from_trace(self) -> None:
        scan = {"inventory": {"platform_method_names": {
            "Ljava/util/Locale;": ["getDefault", "getDisplayName"],
            "Ljava/time/LocalDate;": ["of"],
            "Ljava/time/ZoneId;": ["of"]}}}
        rows = gapmap.runtime_data_rows(scan)
        self.assertEqual({r["id"]: r["data_members"] for r in rows}, {
            "data:tzdata": ["Ljava/time/ZoneId;->of"],
            "data:icu-locale-display": ["Ljava/util/Locale;->getDisplayName"]},
            "LocalDate.of needs no zone rules; getDefault needs no display data")
        observed = {"platform_touch": {"Ljava/util/Locale;->getDisplayName()Ljava/lang/String;": "executed",
                                       "Ljava/time/ZoneId;->of(Ljava/lang/String;)Ljava/time/ZoneId;": "referenced"},
                    "executed_app_methods": [], "executed_methods": 1}
        gap_map = {"rows": rows}
        gapmap.apply_observed(gap_map, {"inventory": {}}, observed, {})
        self.assertEqual({r["id"]: r["observed"]["on_path"] for r in rows},
                         {"data:tzdata": False, "data:icu-locale-display": True})


class AppStorageExec(unittest.TestCase):
    def rows(self, inventory: dict) -> dict:
        scan = {"apk": {"target_abi": "arm64-v8a"}, "inventory": dict({"elfs": []}, **inventory)}
        return {r["id"]: r for r in gapmap.native_loading_rows({"extract_native_libs": True}, scan, {"present": True}, [])}

    def test_soloader_and_path_loads_are_flagged(self) -> None:
        rows = self.rows({"declared_native_methods": [{"owner": "Lcom/facebook/soloader/MergedSoMapping$Invoke_JNI_OnLoad;"}]})
        self.assertEqual(rows["load:app-storage-exec"]["verdict"], "missing")
        self.assertIn("SoLoader", rows["load:app-storage-exec"]["app_evidence"])
        rows = self.rows({"load_library_calls": [{"api": "load", "owner": "Lx/Y;"}]})
        self.assertIn("load:app-storage-exec", rows)

    def test_load_library_by_name_is_not(self) -> None:
        rows = self.rows({"load_library_calls": [{"api": "loadLibrary", "owner": "Lx/Y;", "value": "foo"}]})
        self.assertNotIn("load:app-storage-exec", rows)

    def test_code_cache_copy_supplies_it(self) -> None:
        scan = {"apk": {"target_abi": "arm64-v8a"},
                "inventory": {"elfs": [], "load_library_calls": [{"api": "load", "owner": "Lx/Y;"}]}}
        rows = {r["id"]: r for r in gapmap.native_loading_rows(
            {"extract_native_libs": True}, scan, {"present": True}, [],
            loader={"code_cache_copy": "framework/webview-shim/webview_bionic_shim.c:1"})}
        self.assertEqual(rows["load:app-storage-exec"]["verdict"], "supplied")
        self.assertEqual(rows["load:app-storage-exec"]["launch_args"], ["--android-native-net-app-libraries"])

    def test_a_java_loaded_library_needing_a_sibling(self) -> None:
        """econverter: Chaquopy loads libpython3.11.so by path, then libchaquopy_java.so, whose
        DT_NEEDED found no short name to match and loaded Python a second time."""
        elf = {"abi": "arm64-v8a", "abi_matches_machine": True}
        scan = {"apk": {"target_abi": "arm64-v8a"}, "inventory": {
            "elfs": [{**elf, "name": "lib/arm64-v8a/libpython3.11.so", "soname": "libpython3.11.so", "needed": ["libc.so"]},
                     {**elf, "name": "lib/arm64-v8a/libchaquopy_java.so", "soname": "libchaquopy_java.so",
                      "needed": ["libpython3.11.so", "libc.so"]},
                     {**elf, "name": "lib/arm64-v8a/libother.so", "soname": "libother.so", "needed": ["libpython3.11.so"]}],
            "load_library_calls": [{"api": "loadLibrary", "owner": "Lcom/chaquo/python/GenericPlatform;", "value": "chaquopy_java"}]}}
        rows = {r["id"]: r for r in gapmap.native_loading_rows({"extract_native_libs": True}, scan, {"present": True}, [])}
        row = rows["load:needed-sibling"]
        self.assertEqual((row["verdict"], row["item"]), ("missing", "Java-loaded libraries that need a packaged sibling (libchaquopy_java.so)"))
        rows = {r["id"]: r for r in gapmap.native_loading_rows(
            {"extract_native_libs": True}, scan, {"present": True}, [],
            loader={"open_by_name": "framework/webview-shim/webview_bionic_shim.c:1"})}
        self.assertEqual(rows["load:needed-sibling"]["verdict"], "supplied")
        scan["inventory"]["load_library_calls"] = []
        self.assertNotIn("load:needed-sibling", {r["id"] for r in gapmap.native_loading_rows(
            {"extract_native_libs": True}, scan, {"present": True}, [])})

    def test_packed_relocation_constructors_need_a_sanitizer_that_knows_the_format(self) -> None:
        """Waze: libwaze.so's packed relocations fill its 2189 init array slots; the runtime's sanitizer
        did not recognize DT_ANDROID_RELA and dropped them all."""
        import struct
        from westlake_gap import scanner

        def elf(tags: dict[int, int]) -> bytes:
            dynamic = b"".join(struct.pack("<QQ", t, v) for t, v in tags.items()) + struct.pack("<QQ", 0, 0)
            header = bytearray(64)
            header[:6] = b"\x7fELF\x02\x01"
            struct.pack_into("<Q", header, 0x20, 64)       # e_phoff
            struct.pack_into("<H", header, 0x38, 1)        # e_phnum
            phdr = struct.pack("<IIQQQQQQ", 2, 6, 120, 0, 0, len(dynamic), len(dynamic), 8)
            return bytes(header) + phdr + dynamic

        self.assertEqual(scanner.packed_init_entries(elf({0x60000011: 0x1000, 0x60000012: 64, 25: 0x2000, 27: 2189 * 8})),
                         {"packed_init_entries": 2189})
        self.assertEqual(scanner.packed_init_entries(elf({0x60000011: 0x1000, 35: 0x3000, 25: 0x2000, 27: 16})), {},
                         "a library with RELR as well is left alone by the sanitizer")
        self.assertEqual(scanner.packed_init_entries(elf({7: 0x1000, 25: 0x2000, 27: 16})), {})
        base = {"abi": "arm64-v8a", "abi_matches_machine": True}
        scan = {"apk": {"target_abi": "arm64-v8a"}, "inventory": {
            "elfs": [{**base, "name": "lib/arm64-v8a/libwaze.so", "soname": "libwaze.so", "packed_init_entries": 2189,
                      "needed": ["libdep.so"]},
                     {**base, "name": "lib/arm64-v8a/libdep.so", "soname": "libdep.so", "packed_init_entries": 3}],
            "load_library_calls": [{"api": "loadLibrary", "owner": "Lcom/waze/NativeManager;", "value": "waze"}]}}
        rows = {r["id"]: r for r in gapmap.native_loading_rows({"extract_native_libs": True}, scan, {"present": True}, [])}
        row = rows["load:packed-init-array"]
        self.assertEqual((row["verdict"], row["item"]),
                         ("missing", "Java-loaded libraries whose constructors packed relocations fill (libwaze.so: 2189)"),
                         "a dependency the loader brings in never passes through the sanitizer")
        rows = {r["id"]: r for r in gapmap.native_loading_rows(
            {"extract_native_libs": True}, scan, {"present": True}, [],
            loader={"sanitizer_knows_packed_rela": "stubs/link_stubs_arm64.cc:1"})}
        self.assertEqual(rows["load:packed-init-array"]["verdict"], "supplied")
        scan["inventory"]["load_library_calls"] = []
        rows = {r["id"]: r for r in gapmap.native_loading_rows({"extract_native_libs": True}, scan, {"present": True}, [])}
        self.assertIn("libwaze.so: 2189", rows["load:packed-init-array"]["item"],
                      "a library nothing else needs is loaded from Java, by a name the scan may not see")

    def test_written_libraries_that_need_packaged_ones(self) -> None:
        """econverter: Chaquopy's extension modules, written at run time, need libpython3.11.so; the
        written-library namespace loaded a second copy instead of the one ART had loaded."""
        elf = {"abi": "arm64-v8a", "abi_matches_machine": True}
        packaged = [{**elf, "name": "lib/arm64-v8a/libpython3.11.so"},
                    {**elf, "name": "lib/arm64-v8a/libchaquopy_java.so", "soname": "libchaquopy_java-3.11.so",
                     "needed": ["libpython3.11.so"]}]
        scan = {"apk": {"target_abi": "arm64-v8a"}, "inventory": {"elfs": packaged}}
        rows = {r["id"]: r for r in gapmap.native_loading_rows({"extract_native_libs": True}, scan, {"present": True}, [])}
        self.assertEqual(rows["load:written-needs-packaged"]["verdict"], "missing", "Chaquopy, before any harvest")
        harvested = {**elf, "name": "files/zlib.so", "soname": "zlib.so", "origin": "unpacked",
                     "needed": ["libpython3.11.so", "libc.so"]}
        scan = {"apk": {"target_abi": "arm64-v8a"}, "inventory": {"elfs": [packaged[0], harvested]}}
        rows = {r["id"]: r for r in gapmap.native_loading_rows(
            {"extract_native_libs": True}, scan, {"present": True}, [],
            loader={"written_shares_packaged": "framework/webview-shim/webview_bionic_shim.c:1"})}
        row = rows["load:written-needs-packaged"]
        self.assertEqual((row["verdict"], row["item"]),
                         ("supplied", "Libraries written at run time that need packaged ones (libpython3.11.so)"))
        scan = {"apk": {"target_abi": "arm64-v8a"}, "inventory": {"elfs": [packaged[0]]}}
        self.assertNotIn("load:written-needs-packaged", {r["id"] for r in gapmap.native_loading_rows(
            {"extract_native_libs": True}, scan, {"present": True}, [])})


class AndroidRelocations(unittest.TestCase):
    ELFS = [{"soname": "libc++_shared.so", "name": "lib/arm64-v8a/libc++_shared.so", "abi": "arm64-v8a",
             "android_relocation_tags": ["ANDROID_RELR"]},
            {"soname": "libplain.so", "name": "lib/arm64-v8a/libplain.so", "abi": "arm64-v8a",
             "android_relocation_tags": []}]

    def rows(self, loader=None) -> dict:
        scan = {"apk": {"target_abi": "arm64-v8a"}, "inventory": {"elfs": self.ELFS}}
        return {r["id"]: r for r in gapmap.native_loading_rows(
            {"extract_native_libs": True}, scan, {"present": True}, [], loader=loader)}

    def test_flagged_and_missing_without_the_shim(self) -> None:
        row = self.rows()["load:android-relocations"]
        self.assertEqual(row["verdict"], "missing")
        self.assertIn("libc++_shared.so", row["item"])
        self.assertNotIn("libplain.so", row["item"])

    def test_supplied_by_the_shim(self) -> None:
        row = self.rows({"android_relr_launcher": "tools/probe_source_app.py:1"})["load:android-relocations"]
        self.assertEqual(row["verdict"], "supplied")

    def test_funopen_row(self) -> None:
        elfs = [{"soname": "libsuperpack-jni.so", "name": "lib/arm64-v8a/libsuperpack-jni.so", "abi": "arm64-v8a",
                 "undefined_symbols": ["funopen@LIBC", "fread@LIBC"]}]
        scan = {"apk": {"target_abi": "arm64-v8a"}, "inventory": {"elfs": elfs}}
        rows = lambda loader: {r["id"]: r for r in gapmap.native_loading_rows(
            {"extract_native_libs": True}, scan, {"present": True}, [], loader=loader)}
        self.assertEqual(rows(None)["abi:funopen"]["verdict"], "missing")
        self.assertEqual(rows({"funopen_unbuffered": "framework/webview-shim/webview_bionic_shim.c:1"})
                         ["abi:funopen"]["verdict"], "supplied")

    def test_scanner_reads_the_tags(self) -> None:
        from harness.westlake_gap import scanner
        text = (" 0x0000000000000001 (NEEDED) Shared library: [libc.so]\n"
                " 0x0000000060000011 (LOOS+0x11) 0x12f8\n 0x000000006fffe000 (<unknown>) 0x1310\n"
                " 0x0000000000000024 (RELR) 0x2000\n")
        self.assertEqual(scanner._android_relocation_tags(text), ["ANDROID_RELR"], "RELA and RELR are OH's own")


class LaunchRemedies(unittest.TestCase):
    def test_network_abi_row_and_launch_args(self) -> None:
        scan = {"apk": {"target_abi": "arm64-v8a"}, "inventory": {"elfs": [
            {"soname": "libflutter.so", "name": "lib/arm64-v8a/libflutter.so", "abi": "arm64-v8a",
             "undefined_symbols": ["getaddrinfo@LIBC", "malloc"]},
            {"soname": "libapp.so", "name": "lib/arm64-v8a/libapp.so", "abi": "arm64-v8a", "undefined_symbols": []}]}}
        facts = {"extract_native_libs": True}
        option = {"present": True, "source": "x:1", "net": {"present": True, "source": "x:2"}}
        rows = gapmap.native_loading_rows(facts, scan, {"present": True}, [], option)
        row = next(r for r in rows if r["id"] == "abi:addrinfo")
        self.assertEqual(row["verdict"], "supplied")
        self.assertEqual(row["launch_args"], ["--android-native-net-target", "libflutter.so"])
        both = [row, {"launch_args": ["--android-native-target", "libc++_shared.so",
                                      "--android-native-net-target", "libflutter.so"]}]
        self.assertEqual(gapmap.launch_args(both), ["--android-native-net-target", "libflutter.so",
                                                    "--android-native-target", "libc++_shared.so"])

    def test_engine_surface_follows_the_provider(self) -> None:
        scan = {"apk": {"target_abi": "arm64-v8a"}, "inventory": {"elfs": [{"soname": "libflutter.so", "abi": "arm64-v8a"}]}}
        self.assertEqual(gapmap.engine_surface_rows(scan)[0]["verdict"], "missing")
        supplied = gapmap.engine_surface_rows(scan, {"own_surface": True, "vulkan_android_surface": True, "evidence": "e"})
        self.assertEqual(supplied[0]["verdict"], "supplied")

    def test_an_engine_that_needs_focus_in_its_own_surface(self) -> None:
        """anarchre (SDL): OH moved focus to its SurfaceView's window and SDL paused."""
        sdl = {"apk": {"target_abi": "arm64-v8a"},
               "inventory": {"elfs": [{"soname": "libSDL2.so", "abi": "arm64-v8a"}],
                             "launch_activity_chains": {"dev.serwin.AnarchRE.AnarchreActivity":
                                                        ["Lorg/libsdl/app/SDLActivity;", "Landroid/app/Activity;"]}}}
        rows = {r["id"]: r for r in gapmap.engine_surface_rows(sdl, {"own_surface": True, "evidence": "e"})}
        self.assertEqual(rows["window:surfaceview-focus"]["verdict"], "missing")
        rows = {r["id"]: r for r in gapmap.engine_surface_rows(sdl, {"own_surface": True, "focus_group": "W.java:9"})}
        self.assertEqual(rows["window:surfaceview-focus"]["verdict"], "supplied")
        self.assertNotIn("window:surfaceview-focus", {r["id"] for r in gapmap.engine_surface_rows(sdl, {})},
                         "a SurfaceView that shares its window takes no focus from it")
        flutter = {"apk": {"target_abi": "arm64-v8a"}, "inventory": {"elfs": [{"soname": "libflutter.so", "abi": "arm64-v8a"}]}}
        self.assertNotIn("window:surfaceview-focus",
                         {r["id"] for r in gapmap.engine_surface_rows(flutter, {"own_surface": True})},
                         "Flutter draws on without focus")


class KeystoreProviderNames(unittest.TestCase):
    def test_each_requested_provider_name_is_its_own_row(self) -> None:
        scan = {"inventory": {"jca_requests": [
            {"api": "KeyStore.getInstance", "type": "AndroidKeyStore", "owner": "La;"},
            {"api": "provider name", "provider": "AndroidKeyStoreBCWorkaround", "owner": "Lb;"}]}}
        keystore = {"installed": {"present": False, "source": None}, "backend": {"present": False, "source": None},
                    "replacement": {"present": True, "source": "s:1"}, "registered": {"AndroidKeyStore": "s:1"}}
        rows = {r["id"]: r["verdict"] for r in gapmap.security_rows(scan, keystore)}
        self.assertEqual(rows, {"jca:AndroidKeyStore": "supplied", "jca:AndroidKeyStoreBCWorkaround": "missing"})
        keystore["registered"]["AndroidKeyStoreBCWorkaround"] = "s:2"
        rows = {r["id"]: r["verdict"] for r in gapmap.security_rows(scan, keystore)}
        self.assertEqual(rows["jca:AndroidKeyStoreBCWorkaround"], "supplied")


class PackageManagerNullConsequences(unittest.TestCase):
    def test_aosp_wrapper_that_throws_on_null(self) -> None:
        root = Path(tempfile.mkdtemp())
        try:
            source = root / "frameworks-base/core/java/android/app/ApplicationPackageManager.java"
            source.parent.mkdir(parents=True)
            source.write_text("""
    public InstallSourceInfo getInstallSourceInfo(String packageName) throws NameNotFoundException {
        final InstallSourceInfo installSourceInfo;
        try {
            installSourceInfo = mPM.getInstallSourceInfo(packageName, getUserId());
        } catch (RemoteException e) { throw e.rethrowFromSystemServer(); }
        if (installSourceInfo == null) {
            throw new NameNotFoundException(packageName);
        }
        return installSourceInfo;
    }
    public ServiceInfo getServiceInfo(ComponentName className, int flags) throws NameNotFoundException {
        ServiceInfo si = mPM.getServiceInfo(className, flags, getUserId());
        if (si != null) {
            return si;
        }
        throw new NameNotFoundException(className.toString());
    }
    public String getInstallerPackageName(String packageName) {
        String name = mPM.getInstallerPackageName(packageName);
        return name;
    }
""")
            found = gapmap.pm_null_consequences(root)
            self.assertEqual(set(found), {"getInstallSourceInfo", "getServiceInfo"},
                             "a wrapper that passes null on is not a consequence")
        finally:
            shutil.rmtree(root)


class AndroidPaths(unittest.TestCase):
    def test_path_in_code_against_runtime_data_and_namespace(self) -> None:
        import zipfile
        root = Path(tempfile.mkdtemp())
        try:
            apk = root / "app.apk"
            with zipfile.ZipFile(apk, "w") as archive:
                archive.writestr("lib/arm64-v8a/libflutter.so", b"..\x00/system/etc/security/cacerts\x00..")
            westlake = root / "westlake"
            (westlake / "native").mkdir(parents=True)
            helper = westlake / "native/source_app_namespace.c"
            scan = {"apk": {"target_abi": "arm64-v8a"}}
            data = {"artifacts": {"etc/security/cacerts/01419da9.0": {}}}
            helper.write_text("int etc = overlay(root, \"etc\", \"/system/etc\", \"x\");")
            rows = gapmap.android_path_rows(apk, scan, data, westlake)
            self.assertEqual([(r["id"], r["verdict"]) for r in rows], [("path:/system/etc/security/cacerts", "supplied")])
            helper.write_text("int main(void) { return 0; }")
            self.assertEqual(gapmap.android_path_rows(apk, scan, data, westlake)[0]["verdict"], "missing",
                             "shipped but not shown at the path")
            self.assertEqual(gapmap.android_path_rows(apk, scan, {"artifacts": {}}, westlake)[0]["verdict"], "missing")
        finally:
            shutil.rmtree(root)


class NioChannels(unittest.TestCase):
    def test_selector_use_against_registered_natives(self) -> None:
        scan = {"inventory": {"platform_method_names": {"Ljava/nio/channels/Selector;": ["open"]}}}
        self.assertEqual(gapmap.nio_rows(scan, {"android/os/Foo"})[0]["verdict"], "missing")
        self.assertEqual(gapmap.nio_rows(scan, {"sun/nio/ch/Net"})[0]["verdict"], "supplied")
        self.assertEqual(gapmap.nio_rows({"inventory": {"platform_method_names": {}}}, set()), [])


class NeededLibraries(unittest.TestCase):
    def test_a_library_nothing_provides(self) -> None:
        scan = {"inventory": {"elfs": [
            {"soname": "libxul.so", "name": "libxul.so", "needed": ["libc.so", "libmediandk.so", "libmozglue.so", "liblog.so"]},
            {"soname": "libmozglue.so", "name": "libmozglue.so", "needed": ["libc.so"]}]}}
        rows = gapmap.needed_library_rows(scan, ["/system/lib64/ndk/liblog.so"], ["libandroid.so"])
        self.assertEqual([r["open_symbols"] for r in rows], [["libmediandk.so"]])
        self.assertEqual(gapmap.needed_library_rows(scan, None, None), [], "no board listing, no claim")


class OhEvents(unittest.TestCase):
    LOG = """[OHServiceManager] getService("deviceidle") \u2192 null (stub)
[OHServiceManager] getService("deviceidle") \u2192 null (stub)
[WESTLAKE-LOCAL-SERVICE] power bound in process
[B47-SLA] ENTRY bundle=a.b ability=a.b.Main recordId=1
[B43-BIND] ensureBindApplication FAILED phase=handleBindApplication cause[0]=java.lang.reflect.InvocationTargetException: null
[B43-BIND] ensureBindApplication FAILED phase=handleBindApplication cause[1]=java.lang.UnsatisfiedLinkError: No implementation found for byte[][] java.lang.ProcessEnvironment.environ() (tried x)
"""

    def test_events_and_root_cause(self) -> None:
        from westlake_gap import ohevents
        events = ohevents.parse(self.LOG)
        summary = ohevents.summarize("a", events)
        self.assertEqual(summary["services_null"], ["deviceidle"], "a repeated lookup is one event")
        self.assertEqual(summary["services_local"], ["power"])
        self.assertEqual(summary["natives_missing"], ["java.lang.ProcessEnvironment.environ"])
        self.assertEqual(summary["root_cause"]["error"], "java.lang.UnsatisfiedLinkError",
                         "the wrapper InvocationTargetException is not the cause")


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


class ProviderInitOrder(unittest.TestCase):
    FACTS = {"components": [
        {"kind": "provider", "name": "androidx.startup.InitializationProvider", "process": None,
         "direct_boot_aware": False, "meta_data": {}, "init_order": None},
        {"kind": "provider", "name": "com.google.firebase.provider.FirebaseInitProvider", "process": None,
         "direct_boot_aware": False, "meta_data": {}, "init_order": "100"}],
        "splits": [], "processes": []}
    SCAN = {"inventory": {"platform_method_names": {}}}

    def model(self, sorted_: bool) -> dict:
        return {"methods": {}, "semantics": {
            "direct_boot_match_defaults": {"present": True, "source": "s"},
            "split_paths_populated": {"present": True, "source": "s"},
            "providers_sorted_by_init_order": {"present": sorted_, "source": "b:1" if sorted_ else None}}}

    def test_an_ordered_provider_needs_the_bind_to_sort(self) -> None:
        rows = {r["id"]: r for r in gapmap.package_manager_rows(self.SCAN, self.FACTS, self.model(False))}
        self.assertEqual(rows["pm:provider-init-order"]["verdict"], "missing")
        self.assertIn("FirebaseInitProvider@100", rows["pm:provider-init-order"]["app_evidence"])
        rows = {r["id"]: r for r in gapmap.package_manager_rows(self.SCAN, self.FACTS, self.model(True))}
        self.assertEqual(rows["pm:provider-init-order"]["verdict"], "supplied")

    def test_no_row_when_no_provider_declares_an_order(self) -> None:
        facts = dict(self.FACTS, components=self.FACTS["components"][:1])
        rows = {r["id"] for r in gapmap.package_manager_rows(self.SCAN, facts, self.model(False))}
        self.assertNotIn("pm:provider-init-order", rows)


class ProviderAuthority(unittest.TestCase):
    """Quitter: a disabled provider holds the authority, and a later one for the same authority is
    never installed on Android; its class was gone, and installing it failed the bind."""
    FACTS = {"components": [
        {"kind": "provider", "name": "androidx.work.impl.WorkManagerInitializer", "process": None, "enabled": "false",
         "authorities": "a.workmanager-init", "meta_data": {}, "init_order": None, "direct_boot_aware": False},
        {"kind": "provider", "name": "dev.fluttercommunity.workmanager.WorkmanagerInitializer", "process": None,
         "enabled": None, "authorities": "a.workmanager-init", "meta_data": {}, "init_order": None,
         "direct_boot_aware": False},
        {"kind": "provider", "name": "androidx.startup.InitializationProvider", "process": None, "enabled": None,
         "authorities": "a.androidx-startup;a.workmanager-init", "meta_data": {}, "init_order": None,
         "direct_boot_aware": False}],
        "splits": [], "processes": []}
    SCAN = {"inventory": {"platform_method_names": {}}}

    def model(self, claims: bool) -> dict:
        return {"methods": {}, "semantics": {
            "direct_boot_match_defaults": {"present": True, "source": "s"},
            "split_paths_populated": {"present": True, "source": "s"},
            "provider_authority_claims": {"present": claims, "source": "p:1" if claims else None}}}

    def test_a_provider_whose_authority_is_held(self) -> None:
        rows = {r["id"]: r for r in gapmap.package_manager_rows(self.SCAN, self.FACTS, self.model(False))}
        row = rows["pm:provider-authority"]
        self.assertEqual(row["verdict"], "missing")
        self.assertEqual(row["item"], "Providers whose authority an earlier declaration holds (WorkmanagerInitializer)",
                         "a provider keeping one of its authorities is installed under it")
        rows = {r["id"]: r for r in gapmap.package_manager_rows(self.SCAN, self.FACTS, self.model(True))}
        self.assertEqual(rows["pm:provider-authority"]["verdict"], "supplied")
        facts = dict(self.FACTS, components=self.FACTS["components"][1:])
        self.assertNotIn("pm:provider-authority", {r["id"] for r in gapmap.package_manager_rows(
            self.SCAN, facts, self.model(False))})

class ActivityManagerDefaults(unittest.TestCase):
    """The census of ActivityManager calls the direct-launch proxy answers with a type default."""

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="westlake-am-census-"))
        app = self.root / "aosp/frameworks-base/core/java/android/app"
        _write(app / "IActivityManager.aidl", """interface IActivityManager {
            @UnsupportedAppUsage
            List<ActivityManager.RunningServiceInfo> getServices(int maxNum, int flags);
            List<ActivityManager.ProcessErrorStateInfo> getProcessesInErrorState();
            void getMyMemoryState(out ActivityManager.RunningAppProcessInfo outInfo);
            void getWidgetState(out Bundle state);
            ParceledListSlice<ApplicationExitInfo> getHistoricalProcessExitReasons(String packageName, int pid);
            boolean isUserAMonkey();
            IBinder getOddToken();
        }""")
        _write(app / "ActivityManager.java", """public class ActivityManager {
            /** @return the processes in error, or null if there are none. */
            public List<ProcessErrorStateInfo> getProcessesInErrorState() {
                return getService().getProcessesInErrorState();
            }
            public static void getMyMemoryState(RunningAppProcessInfo outState) { getService().getMyMemoryState(outState); }
            public void getWidgetState(Bundle out) { getService().getWidgetState(out); }
            public List<ApplicationExitInfo> getHistoricalProcessExitReasons(String p, int pid) {
                ParceledListSlice<ApplicationExitInfo> r = getService().getHistoricalProcessExitReasons(p, pid);
                return r == null ? Collections.emptyList() : r.getList();
            }
            @SuppressWarnings("x")
            public static boolean isUserAMonkey() { return getService().isUserAMonkey(); }
            public IBinder getOddToken() { return getService().getOddToken(); }
        }""")

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    def test_open_defaults_are_nulls_handed_on_and_untouched_out_parameters(self) -> None:
        census = gapmap.am_default_census(self.root / "aosp")
        self.assertTrue(census["getProcessesInErrorState"][0]["null_documented"])
        self.assertTrue(census["getHistoricalProcessExitReasons"][0]["null_checked"])
        scan = {"inventory": {"platform_method_names": {"Landroid/app/ActivityManager;": [
            "getProcessesInErrorState", "getMyMemoryState", "getWidgetState", "getHistoricalProcessExitReasons",
            "isUserAMonkey", "getOddToken", "getRunningServices"]}}}
        am = {"proxy_stub": True, "answered": [], "source": "AppSpawnXInit.java:1"}
        row = gapmap.am_default_rows(scan, am, census)[0]
        self.assertEqual(row["id"], "am:type-defaults")
        self.assertEqual(sorted(o.split(" ")[0] for o in row["open_symbols"]), ["getOddToken", "getWidgetState"],
                         "a documented null, a checked one, a primitive and an out parameter already right are answers; "
                         "the process table belongs to its own row")
        self.assertEqual(gapmap.am_default_rows(scan, dict(am, answered=["getOddToken", "getWidgetState"]), census), [])
        self.assertEqual(gapmap.am_default_rows(scan, dict(am, proxy_stub=False), census), [])


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

    def test_the_apps_own_services_need_start_and_bind_answers(self) -> None:
        scan = {"apk": {"services": 2}, "inventory": {"platform_method_names": {
            "Landroid/content/Context;": ["startForegroundService", "bindService", "getString"]}}}
        bound_only = self._model("""if ("AdapterIAM-stub".equals(label)) {
                        if ("bindService".equals(name)) return 1;
                    }""")
        row = {r["id"]: r for r in gapmap.app_framework_rows(scan, bound_only)}["am:in-app-services"]
        self.assertEqual((row["verdict"], row["open_symbols"]), ("missing", ["startService"]))
        both = self._model("""if ("AdapterIAM-stub".equals(label)) {
                        if ("bindService".equals(name)) return 1;
                        if ("startService".equals(name)) return start(args[1]);
                    }""")
        row = {r["id"]: r for r in gapmap.app_framework_rows(scan, both)}["am:in-app-services"]
        self.assertEqual(row["verdict"], "supplied")
        scan["apk"]["services"] = 0
        self.assertNotIn("am:in-app-services", {r["id"] for r in gapmap.app_framework_rows(scan, both)},
                         "an app with no services of its own starts other apps' services")
        scan["inventory"]["platform_method_names"]["Landroid/content/Context;"] = ["registerReceiver", "sendBroadcast"]
        row = {r["id"]: r for r in gapmap.app_framework_rows(scan, both)}["am:broadcasts"]
        self.assertEqual((row["verdict"], row["open_symbols"]),
                         ("missing", ["registerReceiverWithFeature", "broadcastIntentWithFeature"]))

    def test_memory_info_and_the_apps_own_task(self) -> None:
        scan = {"inventory": {"platform_method_names": {
            "Landroid/app/ActivityManager;": ["getMemoryInfo", "getRunningTasks", "getAppTasks"]}}}
        bare = self._model("")
        with tempfile.TemporaryDirectory(prefix="westlake-atm-") as temp:
            root = Path(temp)
            adapter = root / "framework/activity/java/ActivityTaskManagerAdapter.java"
            _write(adapter, """class ActivityTaskManagerAdapter {
                public List<RunningTaskInfo> getTasks(int maxNum, boolean a, boolean b, int d) {
                    logBridged("getTasks", "x");
                    return Collections.emptyList();
                }
                public List<IBinder> getAppTasks(String pkg) { return OwnTask.appTasks(); }
            }""")
            tasks = contracts.task_queries_model(root)
        self.assertEqual((tasks["answered"], tasks["empty"]), (["getAppTasks"], ["getTasks"]))
        rows = {r["id"]: r for r in gapmap.app_framework_rows(scan, bare, None, tasks)}
        self.assertEqual(rows["am:memory-info"]["verdict"], "hollow")
        self.assertEqual((rows["am:own-task"]["verdict"], rows["am:own-task"]["open_symbols"]),
                         ("hollow", ["getRunningTasks"]))
        answered = self._model("""if ("AdapterIAM-stub".equals(label)) {
                        if ("getMemoryInfo".equals(name)) { CallerProcess.memoryInfo(args[0]); return null; }
                    }""")
        rows = {r["id"]: r for r in gapmap.app_framework_rows(scan, answered, None, tasks)}
        self.assertEqual(rows["am:memory-info"]["verdict"], "supplied")

    def test_launch_extras_and_thread_priority(self) -> None:
        scan = {"inventory": {"platform_method_names": {
            "Landroid/content/Intent;": ["getStringExtra", "getParcelableExtra"],
            "Ljava/lang/Thread;": ["setPriority"]}}}
        bare = self._model("")
        rows = {r["id"]: r for r in gapmap.app_framework_rows(
            scan, bare, None, None, {"original_intent": False, "source": None}, {"answer": 0, "source": "s.cc:1"})}
        self.assertEqual((rows["am:launch-extras"]["verdict"], rows["am:launch-extras"]["open_symbols"]),
                         ("missing", ["getParcelableExtra"]))
        self.assertEqual(rows["rt:thread-priority"]["verdict"], "missing")
        rows = {r["id"]: r for r in gapmap.app_framework_rows(
            scan, bare, None, None, {"original_intent": True, "source": "a.java:1"}, {"answer": 5, "source": "s.cc:1"})}
        self.assertEqual((rows["am:launch-extras"]["verdict"], rows["rt:thread-priority"]["verdict"]),
                         ("supplied", "supplied"))
        with tempfile.TemporaryDirectory(prefix="westlake-art-") as temp:
            stub = Path(temp) / "stubs/link_stubs_arm64.cc"
            _write(stub, "int PaletteSchedGetPriority(int, int* p) { if (p) *p = 0; return 0; }\n")
            self.assertEqual(contracts.thread_priority_model(Path(temp))["answer"], 0)

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

    def test_launch_targets_are_file_names(self) -> None:
        # TikTok ships libeffect_plugin.so with the SONAME libeffect.so; the launcher routes files.
        scan = {"inventory": {"elfs": [
            {"name": "lib/arm64-v8a/libc++_shared.so", "soname": "libc++_shared.so", "needed": ["libc.so"]},
            {"name": "lib/arm64-v8a/libeffect_plugin.so", "soname": "libeffect.so", "needed": ["libc++_shared.so"]}]}}
        board = ["/system/lib64/libc++_shared.so"]
        with tempfile.TemporaryDirectory(prefix="westlake-ns-") as temp:
            launcher = Path(temp)
            _write(launcher / "tools/probe_source_app.py", "parser.add_argument('--android-native-target', action='append')")
            rows = gapmap.native_loading_rows({"extract_native_libs": True}, scan, {"present": True}, board,
                                              gapmap.launcher_namespace_option(launcher))
        targets = rows[0]["launch_args"][1::2]
        self.assertEqual(targets, ["libc++_shared.so", "libeffect_plugin.so"])


class LaunchArgsCheck(unittest.TestCase):
    def test_a_target_naming_no_packaged_file_is_reported(self) -> None:
        scan = {"inventory": {"elfs": [{"name": "lib/arm64-v8a/libeffect_plugin.so", "soname": "libeffect.so"}]}}
        args = ["--android-native-target", "libeffect_plugin.so", "--android-native-target", "libeffect.so",
                "--android-native-net-target", "libgone.so", "--app-oat-dir", "/x"]
        self.assertEqual(gapmap.unpackaged_launch_targets(args, scan), ["libeffect.so", "libgone.so"])


class UnpackedLibraries(unittest.TestCase):
    """Libraries the app wrote at run time (scan --unpacked-libs) count as code the process loads,
    never as files the launcher can name."""
    SCAN = {"inventory": {"elfs": [
        {"name": "lib/arm64-v8a/libc++_shared.so", "soname": "libc++_shared.so", "needed": []},
        {"name": "lib/arm64-v8a/libsuperpack-jni.so", "soname": "libsuperpack-jni.so", "needed": ["libc++_shared.so"],
         "undefined_symbols": ["funopen"]},
        {"name": "/data/data/com.whatsapp/files/decompressed/libs.spo/libessential.so", "soname": "libessential.so",
         "needed": ["libc++_shared.so"], "undefined_symbols": ["getaddrinfo"], "origin": "unpacked",
         "android_relocation_tags": ["DT_ANDROID_RELR"]},
    ], "declared_native_methods": [], "load_library_calls": []}}

    def test_a_target_naming_a_written_library_is_reported(self) -> None:
        args = ["--android-native-target", "libsuperpack-jni.so", "--android-native-target", "libessential.so"]
        self.assertEqual(gapmap.unpackaged_launch_targets(args, self.SCAN), ["libessential.so"])

    def test_written_libraries_are_never_launch_targets(self) -> None:
        shadowed, targets = gapmap.shadowed_libraries(self.SCAN, ["/system/lib64/libc++_shared.so"])
        self.assertEqual(targets, ["libc++_shared.so", "libsuperpack-jni.so"])
        rows = gapmap.native_loading_rows({"extract_native_libs": True}, self.SCAN, {"present": True},
                                          ["/system/lib64/libc++_shared.so"],
                                          {"present": True, "source": "x", "net": {"present": True, "source": "y"}},
                                          loader={"android_relr_launcher": "launcher", "code_cache_copy": "shim"})
        by_id = {row["id"]: row for row in rows}
        self.assertNotIn("libessential.so", by_id["load:shadowed-by-board"]["launch_args"])
        # Its getaddrinfo is translated by the app-libraries switch, not by name.
        self.assertNotIn("abi:addrinfo", by_id)
        self.assertEqual(by_id["load:app-storage-exec"]["launch_args"], ["--android-native-net-app-libraries"])
        self.assertIn("1 libraries harvested", by_id["load:app-storage-exec"]["app_evidence"])
        # The launcher renumbers what it stages; a written library needs the shim to.
        self.assertEqual(by_id["load:android-relocations"]["verdict"], "missing")
        rows = gapmap.native_loading_rows({"extract_native_libs": True}, self.SCAN, {"present": True}, [], None,
                                          loader={"android_relr_launcher": "launcher", "android_relr_shim": "shim"})
        self.assertEqual({row["id"]: row for row in rows}["load:android-relocations"]["verdict"], "supplied")

    def test_harvest_inventory_skips_copies_and_non_elf_files(self) -> None:
        import hashlib
        import json
        import sys
        from westlake_gap.scanner import unpacked_elf_inventory
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            elf = Path(sys.executable).resolve().read_bytes()
            (root / "pkg/lib").mkdir(parents=True)
            (root / "pkg/lib/libwritten.so").write_bytes(elf)
            (root / "pkg/lib/libcopy.so").write_bytes(b"copy")
            (root / "pkg/lib/libpartial.so").write_bytes(b"\x00partial")
            entries = [{"file": "pkg/lib/" + name, "device_path": "/data/data/pkg/lib/" + name,
                        "sha256": hashlib.sha256((root / "pkg/lib" / name).read_bytes()).hexdigest(), "elf": is_elf}
                       for name, is_elf in (("libwritten.so", True), ("libcopy.so", True), ("libpartial.so", False))]
            (root / "harvest.json").write_text(json.dumps({"libraries": entries}))
            packaged = [{"name": "lib/arm64-v8a/libcopy.so", "sha256": entries[1]["sha256"]}]
            records = unpacked_elf_inventory(root, packaged)
        self.assertEqual([r["name"] for r in records], ["/data/data/pkg/lib/libwritten.so"])
        self.assertEqual(records[0]["origin"], "unpacked")


def _elf_with_init_array(values: list[int], relocated: list[int]) -> bytes:
    """A minimal ELF64 shared object: one PT_LOAD over the file, a PT_DYNAMIC naming a RELA table and
    an init array of ``values``, with an R_AARCH64_RELATIVE relocation for each slot in ``relocated``."""
    import struct
    dyn, rela, array = 0x100, 0x200, 0x300
    size = array + 8 * len(values)
    data = bytearray(size)
    data[:16] = b"\x7fELF\x02\x01\x01" + bytes(9)
    struct.pack_into("<HHIQQQIHHHHHH", data, 16, 3, 183, 1, 0, 64, 0, 0, 64, 56, 2, 64, 0, 0)
    struct.pack_into("<IIQQQQQQ", data, 64, 1, 5, 0, 0, 0, size, size, 0x1000)
    struct.pack_into("<IIQQQQQQ", data, 120, 2, 6, dyn, dyn, dyn, 96, 96, 8)
    for i, (tag, value) in enumerate([(7, rela), (8, 24 * len(relocated)), (9, 24), (25, array),
                                      (27, 8 * len(values)), (0, 0)]):
        struct.pack_into("<QQ", data, dyn + 16 * i, tag, value)
    for i, slot in enumerate(relocated):
        struct.pack_into("<QQq", data, rela + 24 * i, array + 8 * slot, 1027, 0x1234)
    for i, value in enumerate(values):
        struct.pack_into("<Q", data, array + 8 * i, value)
    return bytes(data)


class NullConstructors(unittest.TestCase):
    def test_unrelocated_null_and_minus_one_entries_are_counted(self) -> None:
        from westlake_gap.scanner import null_array_entries
        # A RELA-relocated slot reads 0 in the file; only unrelocated 0 and -1 are null.
        self.assertEqual(null_array_entries(_elf_with_init_array([0, 0, 2 ** 64 - 1, 0], [0, 3])), {"init": 2})
        self.assertEqual(null_array_entries(_elf_with_init_array([0], [0])), {})

    def test_the_launcher_fix_supplies_packaged_libraries_only(self) -> None:
        scan = {"inventory": {"elfs": [
            {"name": "lib/arm64-v8a/libttffmpeg.so", "null_array_entries": {"init": 1}},
            {"name": "lib/arm64-v8a/libplain.so", "null_array_entries": {}},
        ], "declared_native_methods": [], "load_library_calls": []}}
        loader = {"null_entries_launcher": "tools/probe_source_app.py:30"}
        rows = {r["id"]: r for r in gapmap.native_loading_rows({"extract_native_libs": True}, scan, {"present": True},
                                                                [], None, loader=loader)}
        self.assertEqual(rows["load:null-constructors"]["verdict"], "supplied")
        self.assertIn("libttffmpeg.so", rows["load:null-constructors"]["item"])
        scan["inventory"]["elfs"].append({"name": "/data/data/pkg/lib/libwritten.so", "origin": "unpacked",
                                          "null_array_entries": {"init": 1}})
        rows = {r["id"]: r for r in gapmap.native_loading_rows({"extract_native_libs": True}, scan, {"present": True},
                                                                [], None, loader=loader)}
        self.assertEqual((rows["load:null-constructors"]["verdict"], rows["load:null-constructors"]["open_symbols"]),
                         ("missing", ["libwritten.so"]))
        rows = {r["id"]: r for r in gapmap.native_loading_rows({"extract_native_libs": True}, scan, {"present": True},
                                                                [], None, loader={})}
        self.assertIn("not its dependencies", rows["load:null-constructors"]["provider"])


class ArtInternals(unittest.TestCase):
    def test_libraries_naming_art_internals_are_a_row(self) -> None:
        from westlake_gap.scanner import art_internal_names
        raw = b"\x00_ZN3art2gc4Heap18GrowForUtilizationEPNS0_9collector16GarbageCollectorEm\x00_ZN3art7Runtime5StartEv\x00"
        found = art_internal_names(raw)
        self.assertEqual(found["art_internal_symbols"], 2)
        self.assertEqual(art_internal_names(b"\x00plain\x00"), {})
        scan = {"inventory": {"elfs": [
            {"name": "lib/arm64-v8a/libjato.so", "art_internal_symbols": 174, "art_internal_sample": ["_ZN3art10ArtRuntime"]},
            {"name": "lib/arm64-v8a/libone.so", "art_internal_symbols": 1},
        ]}}
        rows = gapmap.art_internal_rows(scan)
        self.assertEqual([r["id"] for r in rows], ["art:internals"])
        self.assertIn("libjato.so names 174", rows[0]["app_evidence"])
        self.assertNotIn("libone.so", rows[0]["item"])


class SignalAbi(unittest.TestCase):
    MODEL = {"translated": ["sigaction", "sigemptyset"], "scope": {"packaged": True, "written": False},
             "dlsym": None, "source": "webview_bionic_shim.c:426"}

    def test_lookups_by_name_are_found(self) -> None:
        from westlake_gap.scanner import signal_lookups
        raw = b"\x00libc.so\x00sigaction64\x00sigaction\x00"
        self.assertEqual(signal_lookups(raw, set()), {"signal_lookups": ["sigaction", "sigaction64"]})
        self.assertEqual(signal_lookups(raw, {"sigaction", "sigaction64"}), {})

    def test_coverage_follows_the_callers_the_shim_counts(self) -> None:
        packaged = {"name": "lib/arm64-v8a/libcrash.so", "undefined_symbols": ["sigaction", "sigemptyset"]}
        rows = gapmap.signal_abi_rows({"inventory": {"elfs": [packaged]}}, self.MODEL)
        self.assertEqual(rows[0]["verdict"], "supplied")
        written = {"name": "/data/data/com.whatsapp/files/decompressed/libs.spo/libessential.so",
                   "undefined_symbols": ["sigaction"], "origin": "unpacked"}
        rows = gapmap.signal_abi_rows({"inventory": {"elfs": [packaged, written]}}, self.MODEL)
        self.assertEqual((rows[0]["verdict"], rows[0]["open_symbols"]), ("missing", ["libraries written at run time"]))
        hook = {"name": "lib/arm64-v8a/libshadowhook.so", "signal_lookups": ["sigaction", "sigaction64"]}
        model = dict(self.MODEL, scope={"packaged": True, "written": True})
        rows = gapmap.signal_abi_rows({"inventory": {"elfs": [packaged, hook]}}, model)
        self.assertEqual(rows[0]["open_symbols"], ["lookups by name"])
        self.assertIn("looked up by name in libshadowhook.so", rows[0]["app_evidence"])


def _adrp(rd: int, pc: int, target: int) -> int:
    pages = ((target & ~0xFFF) - (pc & ~0xFFF)) >> 12
    return 0x90000000 | ((pages & 3) << 29) | (((pages >> 2) & 0x7FFFF) << 5) | rd


def _add(rd: int, rn: int, imm: int) -> int:
    return 0x91000000 | (imm << 10) | (rn << 5) | rd


class StaticMutexes(unittest.TestCase):
    MODEL = {"adopted": ["pthread_mutex_lock", "pthread_mutex_trylock"], "source": "webview_bionic_shim.c:613"}

    def test_the_address_handed_to_a_lock_is_followed_back(self) -> None:
        from westlake_gap.scanner import x0_address_before
        base, mutex = 0x10000, 0x2B80CC
        words = [_adrp(8, base, mutex), 0xD503201F, _add(0, 8, mutex & 0xFFF), 0x94000000]   # adrp x8; nop; add x0, x8
        self.assertEqual(x0_address_before(words, 3, base), mutex)
        words = [_adrp(19, base, mutex), _add(19, 19, mutex & 0xFFF), 0xAA1303E0, 0x94000000]  # mov x0, x19
        self.assertEqual(x0_address_before(words, 3, base), mutex)
        # Through the GOT: adrp x0, slot page; ldr x0, [x0, #slot]; the slot holds the mutex's address.
        slot = 0x2A0010
        words = [_adrp(0, base, slot), 0xF9400000 | (((slot & 0xFFF) // 8) << 10), 0x94000000]
        self.assertEqual(x0_address_before(words, 2, base, {slot: mutex}), mutex)
        self.assertIsNone(x0_address_before(words, 2, base, {}))
        # A call in between leaves x0 to its return value.
        words = [_adrp(0, base, mutex), _add(0, 0, mutex & 0xFFF), 0x94000010, 0x94000000]
        self.assertIsNone(x0_address_before(words, 3, base))

    def test_only_locked_initializers_are_a_row_and_the_shim_converts_them(self) -> None:
        sentry = {"name": "lib/arm64-v8a/libsentry.so", "bionic_static_mutexes": {"recursive": 1}}
        plain = {"name": "lib/arm64-v8a/libplain.so"}
        rows = gapmap.static_mutex_rows({"inventory": {"elfs": [sentry, plain]}}, self.MODEL)
        self.assertEqual((rows[0]["id"], rows[0]["verdict"]), ("abi:static-mutex-init", "supplied"))
        self.assertIn("libsentry.so: 1 recursive locked as initialized", rows[0]["app_evidence"])
        rows = gapmap.static_mutex_rows({"inventory": {"elfs": [sentry]}}, {"adopted": [], "source": None})
        self.assertEqual((rows[0]["verdict"], rows[0]["open_symbols"]),
                         ("missing", ["pthread_mutex_lock", "pthread_mutex_trylock"]))
        self.assertEqual(gapmap.static_mutex_rows({"inventory": {"elfs": [plain]}}, self.MODEL), [])

    def test_the_model_reads_the_shims_lock_calls(self) -> None:
        import tempfile
        from westlake_gap import contracts
        with tempfile.TemporaryDirectory() as tmp:
            shim = Path(tmp) / "framework/webview-shim/webview_bionic_shim.c"
            shim.parent.mkdir(parents=True)
            shim.write_text("static void adopt(pthread_mutex_t *mutex)\n{\n    if (*(int *) mutex == 0x4000) {}\n}\n"
                            "int pthread_mutex_lock(pthread_mutex_t *mutex)\n{\n    adopt(mutex);\n"
                            "    return pthread_mutex_timedlock(mutex, NULL);\n}\n")
            model = contracts.static_mutex_model(Path(tmp))
        self.assertEqual(model["adopted"], ["pthread_mutex_lock"])
        self.assertTrue(model["source"].endswith(":5"))


class ThreadHandles(unittest.TestCase):
    MODEL = {"ordered": True, "source": "webview_bionic_shim.c:4038"}
    # vcbasekit's call (TikTok): ldr x8, [x19]; ldur x8, [x8, #-24]; add x0, x19, x8; bl; adrp x2;
    # add x0, x19, #256; add x2, x2, #1728; mov x1, sp; mov x3, x19; bl pthread_create
    VCBASEKIT = [0xF9400268, 0xF85E8108, 0x8B080260, 0x97FFB291, 0x90000002, 0x91040260, 0x911B0042,
                 0x910003E1, 0xAA1303E3, 0x97FFB3EF]

    def test_the_handle_inside_the_argument_is_seen(self) -> None:
        from westlake_gap.scanner import register_base_before
        words = self.VCBASEKIT
        self.assertEqual(register_base_before(words, 9, 0), (19, 256, 5))
        self.assertEqual(register_base_before(words, 9, 3), (19, 0, 8))
        self.assertEqual(register_base_before(words, 9, 1), (31, 0, 7), "mov x1, sp is add x1, sp, #0")
        self.assertIsNone(register_base_before(words, 3, 0), "x0 = x19 + x8 is no constant offset")
        # A store names the register it reads: str x0, [x19] between the add and the call is no write.
        words = [_add(0, 19, 256), 0xF9000260, 0xAA1303E3, 0x94000000]
        self.assertEqual(register_base_before(words, 3, 0), (19, 256, 0))
        # A call in between leaves x0 to its return value.
        words = [_add(0, 19, 256), 0x94000010, 0xAA1303E3, 0x94000000]
        self.assertIsNone(register_base_before(words, 3, 0))

    def test_writes_to_the_stack_pointer_are_add_and_sub_only(self) -> None:
        from westlake_gap.scanner import _writes
        self.assertTrue(_writes(0xD10083FF, 31), "sub sp, sp, #32")
        self.assertFalse(_writes(0xEB01001F, 31), "cmp x0, x1 writes xzr")
        self.assertFalse(_writes(0xF9000260, 0), "str x0, [x19]")
        self.assertTrue(_writes(0xF9400260, 0), "ldr x0, [x19]")

    def test_a_row_names_the_libraries_and_the_shim_orders_the_start(self) -> None:
        kit = {"name": "lib/arm64-v8a/libvcbasekit.so", "thread_handle_in_argument": 1}
        plain = {"name": "lib/arm64-v8a/libplain.so"}
        rows = gapmap.thread_handle_rows({"inventory": {"elfs": [kit, plain]}}, self.MODEL)
        self.assertEqual((rows[0]["id"], rows[0]["verdict"]), ("abi:thread-handle-order", "supplied"))
        self.assertIn("libvcbasekit.so: 1 call pthread_create(&obj->thread, ..., obj)", rows[0]["app_evidence"])
        rows = gapmap.thread_handle_rows({"inventory": {"elfs": [kit]}}, {"ordered": False, "source": None})
        self.assertEqual((rows[0]["verdict"], rows[0]["effort"]), ("missing", "S"))
        self.assertEqual(gapmap.thread_handle_rows({"inventory": {"elfs": [plain]}}, self.MODEL), [])

    def test_the_model_needs_a_start_routine_that_waits(self) -> None:
        import tempfile
        from westlake_gap import contracts
        start = ("static void *wait_then_run(void *data)\n{\n    syscall(SYS_futex, data, FUTEX_WAIT_PRIVATE, 0);\n"
                 "    return data;\n}\n")
        create = ("\nint pthread_create(pthread_t *t, const pthread_attr_t *a, void *(*r)(void *), void *v)\n{\n"
                  "    int rc = real(t, a, wait_then_run, v);\n    syscall(SYS_futex, v, FUTEX_WAKE_PRIVATE, 1);\n"
                  "    return rc;\n}\n")
        with tempfile.TemporaryDirectory() as tmp:
            shim = Path(tmp) / "framework/webview-shim/webview_bionic_shim.c"
            shim.parent.mkdir(parents=True)
            shim.write_text(start + create)
            model = contracts.thread_start_model(Path(tmp))
            self.assertEqual(model, {"ordered": True, "source": "framework/webview-shim/webview_bionic_shim.c:7"})
            shim.write_text(start.replace("FUTEX_WAIT", "FUTEX_NOP") + create)
            self.assertFalse(contracts.thread_start_model(Path(tmp))["ordered"], "a start routine that never waits")


class BionicTlsSlots(unittest.TestCase):
    def test_a_slot_read_is_a_row(self) -> None:
        sec = {"name": "lib/arm64-v8a/libmetasec_ov.so", "bionic_tls_slots": {"thread id": 1}}
        rows = gapmap.bionic_tls_rows({"inventory": {"elfs": [sec, {"name": "lib/arm64-v8a/libplain.so"}]}})
        self.assertEqual((rows[0]["id"], rows[0]["verdict"], rows[0]["libraries"]),
                         ("abi:bionic-tls-slots", "missing", ["libmetasec_ov.so"]))
        self.assertIn("libmetasec_ov.so: 1 thread id", rows[0]["app_evidence"])
        self.assertEqual(gapmap.bionic_tls_rows({"inventory": {"elfs": [{"name": "libplain.so"}]}}), [])


class WeakApi(unittest.TestCase):
    def test_weak_ndk_imports_are_a_row_until_the_shim_defines_them(self) -> None:
        weak = [{"symbol": "ASystemFontIterator_open", "importing_libraries": ["libxul.so"], "surface": "libandroid",
                 "weak": True}]
        rows = gapmap.weak_api_rows(weak, set())
        self.assertEqual((rows[0]["id"], rows[0]["verdict"], rows[0]["libraries"], rows[0]["crash_kinds"]),
                         ("ndk:weak-api", "missing", ["libxul.so"], ["null-call"]))
        self.assertEqual(gapmap.weak_api_rows(weak, {"ASystemFontIterator_open"})[0]["verdict"], "supplied")
        self.assertEqual(gapmap.weak_api_rows([], set()), [])


class OwnImplicitIntents(unittest.TestCase):
    def test_a_row_when_the_code_names_its_own_filters(self) -> None:
        scan = {"inventory": {"own_intent_names": ["shazam_activity", "shazam"]}}
        model = {"resolved": True, "started": True, "source": "SourcePackageRegistry.java:198"}
        rows = gapmap.own_intent_rows(scan, model)
        self.assertEqual((rows[0]["id"], rows[0]["verdict"]), ("am:own-implicit-intents", "supplied"))
        rows = gapmap.own_intent_rows(scan, dict(model, started=False))
        self.assertEqual((rows[0]["verdict"], rows[0]["open_symbols"]), ("missing", ["startActivity"]))
        self.assertEqual(gapmap.own_intent_rows({"inventory": {}}, model), [])

    def test_the_model_needs_the_registry_the_query_and_the_start(self) -> None:
        import tempfile
        from westlake_gap import contracts
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            files = {
                "framework/package-manager/java/SourcePackageRegistry.java":
                    "class R {\n    public static synchronized List<ResolveInfo> queryActivities(Intent i, String t, long f) {\n"
                    "        return null;\n    }\n}\n",
                "framework/package-manager/java/PackageManagerAdapter.java":
                    "class P {\n    public ParceledListSlice<ResolveInfo> queryIntentActivities(Intent i, String t, long f, int u) {\n"
                    "        return wrap(SourcePackageRegistry.queryActivities(i, t, f));\n    }\n}\n",
                "framework/activity/java/ActivityTaskManagerAdapter.java":
                    "class A {\n    public int startActivity(Intent intent, String type) {\n        intent = own(intent, type);\n"
                    "        return 0;\n    }\n    private static Intent own(Intent intent, String type) {\n"
                    "        return SourcePackageRegistry.queryActivities(intent, type, 0).isEmpty() ? intent : intent;\n"
                    "    }\n}\n"}
            for name, text in files.items():
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_text(text)
            self.assertEqual(contracts.own_intent_model(root),
                             {"resolved": True, "started": True,
                              "source": "framework/package-manager/java/SourcePackageRegistry.java:2"})
            (root / "framework/activity/java/ActivityTaskManagerAdapter.java").write_text(
                "class A {\n    public int startActivity(Intent intent, String type) {\n        return 0;\n    }\n}\n")
            self.assertFalse(contracts.own_intent_model(root)["started"])


class JavaVmLookups(unittest.TestCase):
    def test_an_import_or_a_name_for_dlsym(self) -> None:
        from westlake_gap.scanner import vm_lookups
        rust = b"\x7fELF api/\x00JNI_GetCreatedJavaVMs\x00\x02(?"
        self.assertEqual(vm_lookups(rust, set(), set()), {"vm_lookup": "by-name"})
        self.assertEqual(vm_lookups(b"\x00JNI_GetCreatedJavaVMs\x00", {"JNI_GetCreatedJavaVMs"}, set()),
                         {"vm_lookup": "import"})
        self.assertEqual(vm_lookups(b"\x00JNI_GetCreatedJavaVMs\x00", set(), {"JNI_GetCreatedJavaVMs"}), {},
                         "a library that defines it (a packaged runtime) is not a caller")
        self.assertEqual(vm_lookups(b"Failed to find JNI_GetCreatedJavaVMs", set(), set()), {},
                         "a message naming it is not a lookup")

    def test_a_row_supplied_when_the_shim_answers_it(self) -> None:
        scan = {"inventory": {"elfs": [{"name": "lib/arm64-v8a/libmatrix_sdk_ffi.so", "soname": "libmatrix_sdk_ffi.so",
                                        "vm_lookup": "by-name"}, {"name": "lib/arm64-v8a/libz.so"}]}}
        rows = gapmap.vm_lookup_rows(scan, {"dlsym"})
        self.assertEqual((rows[0]["id"], rows[0]["verdict"], rows[0]["libraries"]),
                         ("jni:created-vms", "missing", ["libmatrix_sdk_ffi.so"]))
        self.assertEqual(gapmap.vm_lookup_rows(scan, {"JNI_GetCreatedJavaVMs"})[0]["verdict"], "supplied")
        self.assertEqual(gapmap.vm_lookup_rows({"inventory": {"elfs": []}}, set()), [])


class CeStorageUnlocked(unittest.TestCase):
    def test_strictmode_apps_need_the_android_15_name(self) -> None:
        import tempfile
        from westlake_gap import contracts
        scan = {"inventory": {"platform_method_names": {"Landroid/os/StrictMode$VmPolicy$Builder;": ["detectAll", "build"]}}}
        self.assertEqual(gapmap.ce_storage_rows(scan, {"unlocked": False})[0]["verdict"], "missing")
        self.assertEqual(gapmap.ce_storage_rows(scan, {"unlocked": True})[0]["verdict"], "supplied")
        self.assertEqual(gapmap.ce_storage_rows({"inventory": {}}, {"unlocked": False}), [])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java"
            path.parent.mkdir(parents=True)
            old = '                    if ("isUserKeyUnlocked".equals(name)) {\n                        return Boolean.TRUE;\n'
            path.write_text("class I {\n" + old + "                    }\n}\n")
            self.assertFalse(contracts.ce_storage_model(root)["unlocked"])
            path.write_text("class I {\n" + old.replace('("isUserKeyUnlocked".equals(name))',
                            '("isUserKeyUnlocked".equals(name) || "isCeStorageUnlocked".equals(name))') + "                    }\n}\n")
            self.assertTrue(contracts.ce_storage_model(root)["unlocked"])


class PermissionRequests(unittest.TestCase):
    def test_a_row_when_the_app_requests_permissions(self) -> None:
        scan = {"inventory": {"platform_method_names": {"Landroid/app/Activity;": ["requestPermissions", "finish"]}}}
        rows = gapmap.permission_request_rows(scan, {"answered": False, "source": "A.java:142"})
        self.assertEqual((rows[0]["id"], rows[0]["verdict"]), ("am:permission-request", "missing"))
        self.assertEqual(gapmap.permission_request_rows(scan, {"answered": True})[0]["verdict"], "supplied")
        self.assertEqual(gapmap.permission_request_rows({"inventory": {}}, {"answered": False}), [])

    def test_the_model_needs_the_start_to_answer_with_a_result(self) -> None:
        import tempfile
        from westlake_gap import contracts
        tasks = ("class A {\n    public int startActivity(Intent intent, IBinder resultTo) {\n%s        return 0;\n    }\n"
                 "    private static int answer(Intent i, IBinder to) {\n"
                 "        t.addTransactionItem(ActivityResultItem.obtain(to, results));\n        return 0;\n    }\n}\n")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "framework/activity/java/ActivityTaskManagerAdapter.java"
            path.parent.mkdir(parents=True)
            path.write_text(tasks % "        if (PackageManager.ACTION_REQUEST_PERMISSIONS.equals(intent.getAction())) return answer(intent, resultTo);\n")
            self.assertEqual(contracts.permission_request_model(root),
                             {"answered": True, "source": "framework/activity/java/ActivityTaskManagerAdapter.java:2"})
            path.write_text(tasks % "        // ACTION_REQUEST_PERMISSIONS: not handled\n")
            self.assertFalse(contracts.permission_request_model(root)["answered"])


class HostPermissions(unittest.TestCase):
    def test_a_guarded_capability_needs_the_host_to_request_its_permission(self) -> None:
        """musekit: AudioRecord stayed uninitialized while the host did not request the microphone."""
        host = ('{"module": {"name": "entry",\n "requestPermissions": [\n  {"name": "ohos.permission.INTERNET"}%s\n]}}\n')
        mapper = ('    addMapping("android.permission.RECORD_AUDIO",             "ohos.permission.MICROPHONE");\n'
                  '    addMapping("android.permission.CAMERA", "ohos.permission.CAMERA");\n')
        facts = {"permissions": ["android.permission.CAMERA", "android.permission.INTERNET",
                                 "android.permission.RECORD_AUDIO"]}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(gapmap.host_permission_rows(facts, contracts.host_permission_model(root), root), [])
            _write(root / "apps/imehost/module.json", host % "")
            _write(root / "framework/package-manager/java/PermissionMapper.java", mapper)
            model = contracts.host_permission_model(root)
            self.assertEqual((model["requested"], model["source"]), (["ohos.permission.INTERNET"], "apps/imehost/module.json:2"))
            self.assertEqual(gapmap.host_permission_rows(facts, model, root), [],
                             "no row while the provider makes no capture call: that gap is another row's")
            _write(root / "framework/javacore-shim/audiorecord_natives.c",
                   'static void f(void) {\n    S(generate, "OH_AudioStreamBuilder_GenerateCapturer");\n}\n')
            rows = gapmap.host_permission_rows(facts, model, root)
            self.assertEqual([(r["id"], r["verdict"]) for r in rows], [("perm:host:ohos.permission.MICROPHONE", "missing")],
                             "the camera is not bridged, so its permission has no row")
            self.assertEqual(rows[0]["provider_source"],
                             "apps/imehost/module.json:2; framework/javacore-shim/audiorecord_natives.c:2")
            self.assertIn("uninitialized AudioRecord", rows[0]["symptoms"])
            _write(root / "apps/imehost/module.json", host % ',\n  {"name": "ohos.permission.MICROPHONE"}')
            rows = gapmap.host_permission_rows(facts, contracts.host_permission_model(root), root)
            self.assertEqual(rows[0]["verdict"], "supplied")
            self.assertEqual(gapmap.host_permission_rows({"permissions": ["android.permission.INTERNET"]},
                                                         contracts.host_permission_model(root), root), [])


class UserServiceAnswers(unittest.TestCase):
    def test_user_manager_calls_reaching_a_method_the_user_service_throws_for(self) -> None:
        """clauncher: UserManager.getUserProfiles asks getProfileIds, which the user service did not name."""
        manager = """public class UserManager {
    private final IUserManager mService;
    public List<UserHandle> getUserProfiles() {
        int[] userIds = getProfileIds(getContextUserIfAppropriate(), true /* enabledOnly */);
        return convertUserIdsToUserHandles(userIds);
    }
    public @NonNull int[] getProfileIds(@UserIdInt int userId, boolean enabledOnly) {
        try {
            return mService.getProfileIds(userId, enabledOnly);
        } catch (RemoteException re) {
            throw re.rethrowFromSystemServer();
        }
    }
    public boolean isManagedProfile() {
        return isManagedProfile(0);
    }
    public boolean isManagedProfile(int userId) {
        return "managed".equals(mService.getProfileType(userId));
    }
}
"""
        service = ("final class OHUserManager {\n    static Object answer(String name, Object[] arguments) {\n"
                   "        if (name.equals(\"isUserRunning\")) return true;\n        switch (name) {\n"
                   "            case \"getProfileType\":\n                return \"\";\n%s"
                   "            default:\n                break;\n        }\n"
                   "        throw new UnsupportedOperationException(\"OH user service does not implement \" + name);\n"
                   "    }\n}\n")
        scan = {"inventory": {"platform_method_names": {"Landroid/os/UserManager;": ["getUserProfiles", "isManagedProfile"]}}}
        with tempfile.TemporaryDirectory() as temp:
            aosp, westlake = Path(temp) / "aosp", Path(temp) / "westlake"
            _write(aosp / "frameworks-base/core/java/android/os/UserManager.java", manager)
            census = gapmap.user_manager_census(aosp)
            self.assertEqual((census["getUserProfiles"], census["isManagedProfile"]), (["getProfileIds"], ["getProfileType"]))
            _write(westlake / "framework/package-manager/java/OHUserManager.java", service % "")
            model = contracts.user_service_model(westlake)
            self.assertEqual((model["answered"], model["source"]),
                             (["getProfileType", "isUserRunning"], "framework/package-manager/java/OHUserManager.java:10"))
            rows = gapmap.user_service_rows(scan, model, census)
            self.assertEqual([(r["id"], r["verdict"], r["open_symbols"]) for r in rows],
                             [("svc:user-unanswered", "missing", ["getUserProfiles (getProfileIds)"])])
            _write(westlake / "framework/package-manager/java/OHUserManager.java",
                   service % "            case \"getProfileIds\":\n                return new int[] {0};\n")
            self.assertEqual(gapmap.user_service_rows(scan, contracts.user_service_model(westlake), census), [])
        self.assertEqual(gapmap.user_service_rows(scan, {"throws": True, "answered": []}, {}), [])


class PostCreateCallbacks(unittest.TestCase):
    def test_the_activity_or_a_named_base_class_overrides(self) -> None:
        from westlake_gap.scanner import after_start_overrides
        superclasses = {"Lorg/linphone/ui/main/MainActivity;": "Lk/h;", "Lk/h;": "Landroid/app/Activity;",
                        "Lnet/openid/appauth/RedirectActivity;": "Lk/h;",
                        "Lcom/app/Settings;": "Lcom/app/BaseActivity;", "Lcom/app/BaseActivity;": "Lk/h;",
                        "Lcom/app/Plain;": "Landroidx/appcompat/app/AppCompatActivity;",
                        "Landroidx/appcompat/app/AppCompatActivity;": "Landroid/app/Activity;"}
        callbacks = {"Lorg/linphone/ui/main/MainActivity;": {"onPostCreate"}, "Lk/h;": {"onPostCreate"},
                     "Lcom/app/BaseActivity;": {"onRestoreInstanceState"},
                     "Landroidx/appcompat/app/AppCompatActivity;": {"onPostCreate"}}
        found = after_start_overrides(["org.linphone.ui.main.MainActivity", "net.openid.appauth.RedirectActivity",
                                       "com.app.Settings", "com.app.Plain"], superclasses, callbacks)
        # R8's renamed AppCompatActivity (Lk/h;) and AndroidX's own are not the app's code.
        self.assertEqual([(f["activity"], f["class"], f["callbacks"]) for f in found],
                         [("org.linphone.ui.main.MainActivity", "Lorg/linphone/ui/main/MainActivity;", ["onPostCreate"]),
                          ("com.app.Settings", "Lcom/app/BaseActivity;", ["onRestoreInstanceState"])])

    def test_a_row_supplied_when_the_launch_carries_the_start(self) -> None:
        scan = {"apk": {"main_activities": ["org.linphone.ui.main.MainActivity"]},
                "inventory": {"after_start_overrides": [
                    {"activity": "org.linphone.ui.assistant.AssistantActivity", "class": "x", "callbacks": ["onPostCreate"]},
                    {"activity": "org.linphone.ui.main.MainActivity", "class": "y", "callbacks": ["onPostCreate"]}]}}
        rows = gapmap.post_create_rows(scan, {"carries_start": False, "source": "AppSchedulerBridge.java:1844"})
        self.assertEqual((rows[0]["id"], rows[0]["verdict"], rows[0]["effort"]), ("am:post-create", "missing", "XS"))
        self.assertTrue(rows[0]["app_evidence"].startswith("org.linphone.ui.main.MainActivity"), "the launch activity first")
        rows = gapmap.post_create_rows(scan, {"carries_start": True, "source": "AppSchedulerBridge.java:1844"})
        self.assertEqual(rows[0]["verdict"], "supplied")
        self.assertEqual(gapmap.post_create_rows({"inventory": {}}, {"carries_start": False}), [])

    def test_the_model_reads_the_launch_transaction(self) -> None:
        import tempfile
        from westlake_gap import contracts
        launch = ("class B {\n    public static void nativeOnScheduleLaunchAbility(Object t, String b) {\n"
                  "        LaunchActivityItem item = LaunchActivityItem.obtain(token, intent);\n"
                  "        transaction.addTransactionItem(item);\n%s    }\n}\n")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "framework/activity/java/AppSchedulerBridge.java"
            path.parent.mkdir(parents=True)
            path.write_text(launch % "        transaction.addTransactionItem(StartActivityItem.obtain(token, null));\n")
            self.assertEqual(contracts.launch_start_model(root),
                             {"carries_start": True, "source": "framework/activity/java/AppSchedulerBridge.java:2"})
            # A lifecycle request only in a comment is not one.
            path.write_text(launch % "        // NO setLifecycleStateRequest(ResumeActivityItem.obtain(token)) here\n")
            self.assertFalse(contracts.launch_start_model(root)["carries_start"])
            path.write_text("class B {}\n")
            self.assertIsNone(contracts.launch_start_model(root)["carries_start"])


class DeviceAnswers(unittest.TestCase):
    SOURCE = """
            switch (name) {
                case "role":
                    binder = proxy(name, "android.app.role.IRoleManager", LocalServiceBinders::role);
                    break;
                case "audio":
                    binder = proxy(name, "android.media.IAudioService", LocalServiceBinders::audio);
                    break;
                case "alarm":
                    binder = proxy(name, "android.app.IAlarmManager", LocalServiceBinders::alarm);
                    break;
                // No USB device or accessory attached: the device list is empty.
                case "usb":
                    binder = proxy(name, "android.hardware.usb.IUsbManager", (method, args) -> DEFAULT);
                    break;
            }

    /**
     * Roles on a board with no telephony: no role is available (so none is offered to the user)
     * and none is held. An SMS app sees that it is not the default.
     */
    private static Object role(String method, Object[] args) {
        return DEFAULT;   // isRoleAvailable/isRoleHeld false
    }

    /** Every player registers itself with the audio service's player registry. */
    private static Object audio(String method, Object[] args) {
        return DEFAULT;
    }

    /** No alarms are kept. */
    private static Object alarm(String method, Object[] args) {
        if ("set".equals(method)) return null;
        return DEFAULT;
    }
"""

    def test_handlers_that_answer_an_absence_with_defaults(self) -> None:
        from westlake_gap import services
        found = {name: detail for name, (detail, _) in services.device_answers(self.SOURCE).items()}
        self.assertEqual(found, {
            "role": "Roles on a board with no telephony: no role is available (so none is offered to the user) "
                    "and none is held.",
            "usb": "No USB device or accessory attached: the device list is empty."})


class StubNatives(unittest.TestCase):
    STUB = """
static jlong UnixFileSystem_getSpace0(JNIEnv* env, jobject thiz, jobject file, jint t) {
    return 0; /* stub */
}
static jboolean UnixFileSystem_delete0(JNIEnv* env, jobject thiz, jobject file) {
    return unlink("x") == 0;
}
void register(JNIEnv* env) {
    jclass cls = FindOptionalClass(env, "java/io/UnixFileSystem");
    JNINativeMethod methods[] = {
        {"getSpace0", "(Ljava/io/File;I)J", (void*)UnixFileSystem_getSpace0},
        {"delete0", "(Ljava/io/File;)Z", (void*)UnixFileSystem_delete0},
    };
}
"""

    def model(self, rebind: bool) -> dict:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "art-build/stubs").mkdir(parents=True)
            (root / "art-build/stubs/openjdk_stub.c").write_text(self.STUB)
            natives = root / "westlake/framework/javacore-shim/missing_natives.c"
            natives.parent.mkdir(parents=True)
            table = '    { "getSpace0", "(Ljava/io/File;I)J", (void*) wl_getSpace0 },\n' if rebind else ""
            natives.write_text("static const JNINativeMethod kUnixFileSystem[] = {\n" + table + "};\n"
                               'int fs = bind(env, "java/io/UnixFileSystem", kUnixFileSystem, 1);\n')
            return gapmap.stub_native_model(root / "art-build", root / "westlake")

    def test_a_constant_native_the_app_reaches_is_hollow_until_rebound(self) -> None:
        model = self.model(rebind=False)
        self.assertEqual(list(model["stubs"]), ["java/io/UnixFileSystem.getSpace0"])
        scan = {"inventory": {"platform_method_names": {"Ljava/io/File;": ["exists", "getUsableSpace"]}}}
        row = gapmap.stub_native_rows(scan, model)[0]
        self.assertEqual((row["id"], row["verdict"], row["open_symbols"]),
                         ("runtime:stub-natives", "hollow", ["java/io/UnixFileSystem.getSpace0"]))
        self.assertIn("File.getUsableSpace (UnixFileSystem.getSpace0, constant)", row["app_evidence"])
        self.assertEqual(gapmap.stub_native_rows(scan, self.model(rebind=True))[0]["verdict"], "supplied")
        self.assertEqual(gapmap.stub_native_rows({"inventory": {"platform_method_names": {
            "Ljava/io/File;": ["exists"]}}}, model), [])


class ApkMemberLoads(unittest.TestCase):
    def test_soloader_with_unfixed_split_libraries_is_a_row(self) -> None:
        scan = {"inventory": {"elfs": [
            {"name": "split_config.arm64_v8a.apk!lib/arm64-v8a/libc++_shared.so", "split_apk": "split_config.arm64_v8a.apk",
             "android_relocation_tags": ["ANDROID_RELR"]},
        ], "declared_native_methods": [{"owner": "Lcom/facebook/soloader/SoLoader;", "name": "x"}],
            "load_library_calls": []}}
        rows = {r["id"]: r for r in gapmap.native_loading_rows({"extract_native_libs": True}, scan, {"present": True},
                                                                [], None, loader={})}
        self.assertEqual(rows["load:apk-member"]["verdict"], "missing")
        rows = {r["id"]: r for r in gapmap.native_loading_rows({"extract_native_libs": True}, scan, {"present": True},
                                                                [], None, loader={"apk_member_redirect": "shim.c:1"})}
        self.assertEqual(rows["load:apk-member"]["verdict"], "supplied")


class SymbolVersions(unittest.TestCase):
    def test_version_mismatches_are_their_own_row(self) -> None:
        missing = [{"symbol": "__system_property_read_callback", "importers": 1, "importing_libraries": ["libcore.so"],
                    "surface": "libc", "version_mismatch": {"wanted": ["LIBC_O"], "defined": ["LIBC"]}}]
        rows = gapmap.symbol_version_rows(missing)
        self.assertEqual(rows[0]["open_symbols"], ["__system_property_read_callback@LIBC_O (defined @LIBC)"])
        self.assertEqual(gapmap.symbol_version_rows([{"symbol": "x", "importing_libraries": []}]), [])


class Interposition(unittest.TestCase):
    RUNTIME = {"bridge_libraries": [{"name": "libhwui.so", "exported_symbols": [
        "vmaCreateAllocator", "vmaCreateBuffer", "vmaDestroyBuffer", "JNI_OnLoad", "SkCanvas_draw"]}]}

    def test_an_app_library_sharing_the_runtimes_symbols_is_flagged_unless_routed(self) -> None:
        scan = {"inventory": {"elfs": [
            {"name": "lib/arm64-v8a/libppsspp_jni.so",
             "exported_symbols": ["vmaCreateAllocator", "vmaCreateBuffer", "vmaDestroyBuffer", "JNI_OnLoad"]},
            {"name": "lib/arm64-v8a/libplain.so", "exported_symbols": ["JNI_OnLoad", "Java_a_b_c"]}]}}
        row = gapmap.interposition_rows(scan, self.RUNTIME, [])[0]
        self.assertEqual((row["verdict"], row["open_symbols"]), ("missing", ["libppsspp_jni.so"]))
        self.assertIn("libppsspp_jni.so: 3 with libhwui.so", row["app_evidence"])
        routed = [{"launch_args": ["--android-native-target", "libppsspp_jni.so"]}]
        self.assertEqual(gapmap.interposition_rows(scan, self.RUNTIME, routed)[0]["verdict"], "supplied")
        self.assertEqual(gapmap.interposition_rows({"inventory": {"elfs": [scan["inventory"]["elfs"][1]]}},
                                                   self.RUNTIME, []), [])


class TaskRoot(unittest.TestCase):
    def test_a_constant_task_answer_is_a_gap_for_apps_that_ask(self) -> None:
        from westlake_gap.contracts import activity_client_model
        scan = {"inventory": {"platform_method_names": {"Landroid/app/Activity;": ["isTaskRoot", "finish"]}}}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "framework/activity/java/ActivityClientControllerAdapter.java"
            _write(source, "class A { @Override\n    public int getTaskForActivity(IBinder token, boolean onlyRoot) { return -1; } }")
            model = activity_client_model(root)
            self.assertEqual(model["task_for_activity"], "constant")
            self.assertEqual(gapmap.task_root_rows(scan, model)[0]["verdict"], "missing")
            _write(source, "class A { public int getTaskForActivity(IBinder token, boolean onlyRoot) {\n"
                           "        int position = taskPosition(token);\n        return position == 0 ? 1 : -1;\n    } }")
            self.assertEqual(gapmap.task_root_rows(scan, activity_client_model(root))[0]["verdict"], "supplied")
        self.assertEqual(gapmap.task_root_rows({"inventory": {"platform_method_names": {}}}, {"task_for_activity": "constant"}), [])



class WindowMetrics(unittest.TestCase):
    def test_metrics_in_oncreate_need_the_bounds_at_bind(self) -> None:
        """aat: getCurrentWindowMetrics() in onCreate answered 0x0, and it divided by zero."""
        from westlake_gap.contracts import window_metrics_model
        scan = {"inventory": {"platform_method_names": {"Landroid/view/WindowManager;": ["getCurrentWindowMetrics"]}}}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "framework/activity/java/AppSchedulerBridge.java"
            _write(source, "class B {\n    private static android.content.res.Configuration buildConfiguration(\n"
                           "            String[] kv, DisplaySnapshot disp) {\n        cfg.densityDpi = disp.densityDpi;\n    }\n"
                           "    void relayout() { config.windowConfiguration.setBounds(winBounds); }\n}")
            model = window_metrics_model(root)
            self.assertFalse(model["bounds_at_bind"], "bounds set at relayout do not count")
            self.assertEqual(gapmap.window_metrics_rows(scan, model)[0]["verdict"], "missing")
            _write(source, "class B {\n    private static android.content.res.Configuration buildConfiguration(\n"
                           "            String[] kv, DisplaySnapshot disp) {\n        cfg.windowConfiguration.setBounds(bounds);\n    }\n}")
            self.assertEqual(gapmap.window_metrics_rows(scan, window_metrics_model(root))[0]["verdict"], "supplied")
        self.assertEqual(gapmap.window_metrics_rows({"inventory": {"platform_method_names": {}}}, {}), [])


class NativeEglWindow(unittest.TestCase):
    def test_a_native_window_surface_needs_the_oh_window(self) -> None:
        """Cards with Cats: Flutter's Skia renderer passed ANativeWindow_fromSurface's wrapper to OH's EGL."""
        from westlake_gap.contracts import native_egl_window_model
        scan = {"inventory": {"elfs": [
            {"name": "lib/arm64-v8a/libflutter.so", "soname": "libflutter.so", "abi_matches_machine": True,
             "undefined_symbols": ["eglCreateWindowSurface", "eglQuerySurface"]},
            {"name": "lib/x86_64/libflutter.so", "soname": "libflutter.so", "abi_matches_machine": False,
             "undefined_symbols": ["eglCreateWindowSurface"]}]}}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "framework/webview-shim/webview_bionic_shim.c"
            _write(source, "unsigned eglTerminate(void *display)\n{\n    return 1;\n}\n")
            model = native_egl_window_model(root)
            self.assertEqual(gapmap.native_egl_window_rows(scan, model)[0]["verdict"], "missing")
            _write(source, "void *eglCreateWindowSurface(void *display, void *config, void *window, const int *attribs)\n{\n"
                           "    void *oh = wl_anw_get_oh != NULL ? wl_anw_get_oh(window) : NULL;\n    return oh;\n}\n")
            row = gapmap.native_egl_window_rows(scan, native_egl_window_model(root))[0]
            self.assertEqual(row["verdict"], "supplied")
            self.assertEqual(row["app_evidence"], "libflutter.so imports eglCreateWindowSurface")
        self.assertEqual(gapmap.native_egl_window_rows({"inventory": {"elfs": []}}, {"unwraps": True}), [])

    def test_egl_looked_up_by_handle_needs_the_shims_dlsym(self) -> None:
        """anarchre: SDL dlopens libEGL.so and takes eglCreateWindowSurface by handle, past the shim."""
        from westlake_gap import scanner
        from westlake_gap.contracts import native_egl_window_model
        raw = b"\x7fELF..\x00libEGL.so\x00eglCreateWindowSurface\x00eglTerminate\x00"
        self.assertEqual(scanner.egl_lookups(raw, set()), {"egl_lookups": ["eglCreateWindowSurface", "eglTerminate"]})
        self.assertEqual(scanner.egl_lookups(raw, {"eglCreateWindowSurface", "eglTerminate"}), {})
        scan = {"inventory": {"elfs": [{"name": "lib/arm64-v8a/libSDL3.so", "soname": "libSDL3.so",
                                        "abi_matches_machine": True, "egl_lookups": ["eglCreateWindowSurface"]}]}}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "framework/webview-shim/webview_bionic_shim.c"
            _write(source, "unsigned eglTerminate(void *display)\n{\n    return 1;\n}\n")
            rows = gapmap.native_egl_window_rows(scan, native_egl_window_model(root))
            self.assertEqual([(r["id"], r["verdict"]) for r in rows], [("egl:by-handle", "missing")])
            _write(source, "static void *westlake_egl_by_handle(const char *name)\n{\n    return 0;\n}\n")
            rows = gapmap.native_egl_window_rows(scan, native_egl_window_model(root))
            self.assertEqual([(r["id"], r["verdict"]) for r in rows], [("egl:by-handle", "supplied")])

    def test_gles3_looked_up_by_name_needs_libglesv2_to_carry_it(self) -> None:
        """aaaaxy: Ebiten looked glGenVertexArrays up in libGLESv2.so's handle, which on OH has GLES 2 only."""
        from westlake_gap import scanner
        from westlake_gap.contracts import native_egl_window_model
        # Go packs its strings with no terminators; an extension's name is not the core one's.
        raw = b"\x7fELF..\x00libGLESv2.so\x00glBindVertexArrayglGenVertexArraysglClear\x00glDrawBuffersEXT\x00"
        self.assertEqual(scanner.gles3_lookups(raw, set()), {"gles3_lookups": ["glBindVertexArray", "glGenVertexArrays"]})
        self.assertEqual(scanner.gles3_lookups(raw, {"glBindVertexArray", "glGenVertexArrays"}), {})
        scan = {"inventory": {"elfs": [{"name": "lib/arm64-v8a/libgojni.so", "abi_matches_machine": True,
                                        "gles3_lookups": ["glBindVertexArray", "glGenVertexArrays"]}]}}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "framework/webview-shim/webview_bionic_shim.c"
            webview_only = ('    if (basename != NULL && strcmp(basename, "libGLESv2.so") == 0 &&\n'
                            '        caller_is_webview(caller, NULL)) {\n'
                            '        actual_filename = "/system/lib64/platformsdk/libGLESv3.so";\n    }\n')
            _write(source, "void *dlopen(const char *filename, int flags)\n{\n" + webview_only + "}\n")
            rows = gapmap.native_egl_window_rows(scan, native_egl_window_model(root))
            self.assertEqual([(r["id"], r["verdict"]) for r in rows], [("gl:gles3-by-handle", "missing")])
            self.assertEqual(rows[0]["app_evidence"],
                             "lib/arm64-v8a/libgojni.so names 2 without importing them (glBindVertexArray, glGenVertexArrays)")
            _write(source, "void *dlopen(const char *filename, int flags)\n{\n"
                   + webview_only.replace("caller_is_webview(caller, NULL)", "caller_is_android_dso(caller, &gles_caller)")
                   + "}\n")
            model = native_egl_window_model(root)
            self.assertEqual(model["gles3_by_handle"], "framework/webview-shim/webview_bionic_shim.c:3")
            self.assertEqual([(r["id"], r["verdict"]) for r in gapmap.native_egl_window_rows(scan, model)],
                             [("gl:gles3-by-handle", "supplied")])
            # After the .z.so probe, which returns the bare name's own library first: never reached.
            probe = ("    if (basename != NULL && basename == filename) {\n"
                     "        void *plain = real_dlopen(actual_filename, flags);\n        if (plain != NULL) return plain;\n    }\n")
            translated = webview_only.replace("caller_is_webview(caller, NULL)", "caller_is_android_dso(caller, &gles_caller)")
            _write(source, "void *dlopen(const char *filename, int flags)\n{\n" + probe + translated + "}\n")
            self.assertIsNone(native_egl_window_model(root)["gles3_by_handle"])
            _write(source, "void *dlopen(const char *filename, int flags)\n{\n" + translated + probe + "}\n")
            self.assertEqual(native_egl_window_model(root)["gles3_by_handle"], "framework/webview-shim/webview_bionic_shim.c:3")

    def test_buffers_geometry_needs_androids_terms(self) -> None:
        """anarchre, diesimu: SDL's (0, 0, visual) reached OH as a 0x0 buffer size and CLUT1."""
        from westlake_gap.contracts import native_egl_window_model
        scan = {"inventory": {"elfs": [{"name": "lib/arm64-v8a/libSDL2.so", "soname": "libSDL2.so",
                                        "abi_matches_machine": True,
                                        "undefined_symbols": ["ANativeWindow_setBuffersGeometry"]}]}}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "framework/webview-shim/webview_bionic_shim.c"
            # Passing the arguments through is no answer.
            _write(source, "int32_t ANativeWindow_setBuffersGeometry(void *w, int32_t width, int32_t height, int32_t f)\n{\n"
                           "    return next(w, width, height, f);\n}\n")
            rows = gapmap.native_egl_window_rows(scan, native_egl_window_model(root))
            self.assertEqual([(r["id"], r["verdict"], r["shim_class"]) for r in rows],
                             [("window:buffers-geometry", "missing", "C2")])
            _write(source, "int32_t ANativeWindow_setBuffersGeometry(void *w, int32_t width, int32_t height, int32_t f)\n{\n"
                           "    int32_t host = wl_host_window_format(f);\n    if (width != 0) set(w, width, height);\n"
                           "    return host;\n}\n")
            row = gapmap.native_egl_window_rows(scan, native_egl_window_model(root))[0]
            self.assertEqual((row["verdict"], row["provider_source"]),
                             ("supplied", "framework/webview-shim/webview_bionic_shim.c:1"))
            self.assertEqual(row["app_evidence"], "libSDL2.so imports ANativeWindow_setBuffersGeometry")

class SoftwareCanvas(unittest.TestCase):
    def test_a_window_drawn_in_software_needs_a_buffer(self) -> None:
        """nounours: its SurfaceView, drawn with lockCanvas, was a transparent hole."""
        from westlake_gap.contracts import software_canvas_model
        scan = {"inventory": {"platform_method_names": {"Landroid/view/SurfaceHolder;": ["lockCanvas", "addCallback"]},
                              "elfs": [{"name": "lib/arm64-v8a/libvlc.so", "soname": "libvlc.so",
                                        "abi_matches_machine": True, "undefined_symbols": ["ANativeWindow_lock"]}]}}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shim = root / "framework/webview-shim/webview_bionic_shim.c"
            _write(shim, "int ANativeWindow_lock(void *window, void *out, void *dirty)\n{\n    errno = ENODEV;\n"
                         "    return -ENODEV;\n}\n")
            row = gapmap.software_canvas_rows(scan, software_canvas_model(root))[0]
            self.assertEqual((row["id"], row["verdict"], row["shim_class"]), ("window:software-canvas", "missing", "C9"))
            self.assertEqual(row["app_evidence"], "the app calls SurfaceHolder.lockCanvas; libvlc.so imports ANativeWindow_lock")
            _write(shim, "int ANativeWindow_lock(void *window, void *out, void *dirty)\n{\n"
                         "    RequestFn request = wl_native_window_symbol(\"OH_NativeWindow_NativeWindowRequestBuffer\");\n"
                         "    return request(oh, &buffer, &fence);\n}\n")
            model = software_canvas_model(root)
            self.assertEqual(model["native"], "framework/webview-shim/webview_bionic_shim.c:1")
            self.assertEqual(gapmap.software_canvas_rows(scan, model)[0]["verdict"], "missing", "lockCanvas is not wrapped")
            _write(root / "framework/javacore-shim/canvas_natives.c", "int wl_register_surface_canvas(JNIEnv* env)\n{\n}\n")
            _write(root / "framework/javacore-shim/missing_natives.c", "    int cv = wl_register_surface_canvas(env);\n")
            _write(root / "tools/build_missing_natives.sh", "for f in missing_natives canvas_natives; do\n")
            self.assertEqual(gapmap.software_canvas_rows(scan, software_canvas_model(root))[0]["verdict"], "supplied")
        self.assertEqual(gapmap.software_canvas_rows({"inventory": {}}, {}), [])


class SqliteCollations(unittest.TestCase):
    def test_sql_naming_androids_collations_needs_them_registered(self) -> None:
        """fnotes: "ORDER BY title COLLATE UNICODE" failed, no such collation sequence."""
        from westlake_gap import scanner
        from westlake_gap.contracts import sqlite_collations_model
        self.assertEqual(scanner.sql_collations(["SELECT * FROM notes ORDER BY title COLLATE UNICODE",
                                                 "name collate localized", "COLLATE NOCASE", "collateral"]),
                         {"UNICODE", "LOCALIZED"})
        scan = {"inventory": {"sql_collations": ["UNICODE"]}}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            row = gapmap.sqlite_collation_rows(scan, sqlite_collations_model(root))[0]
            self.assertEqual((row["id"], row["verdict"], row["app_evidence"]),
                             ("db:sqlite-collations", "missing", "the app's SQL names COLLATE UNICODE"))
            _write(root / "framework/javacore-shim/sqlite_natives.c",
                   'int wl_register_sqlite_collations(JNIEnv* env)\n{\n}\n'
                   'static void f(void) { wl_register_collation(db, "UNICODE", NULL, 0); }\n')
            _write(root / "framework/javacore-shim/missing_natives.c", "    int sc = wl_register_sqlite_collations(env);\n")
            self.assertEqual(gapmap.sqlite_collation_rows(scan, sqlite_collations_model(root))[0]["verdict"], "missing",
                             "registered nowhere until the build compiles it")
            _write(root / "tools/build_missing_natives.sh", "for f in missing_natives sqlite_natives; do\n")
            self.assertEqual(gapmap.sqlite_collation_rows(scan, sqlite_collations_model(root))[0]["verdict"], "supplied")
            self.assertEqual(gapmap.sqlite_collation_rows({"inventory": {"sql_collations": ["UNICODE", "PHONEBOOK"]}},
                                                          sqlite_collations_model(root))[0]["verdict"], "missing")
        self.assertEqual(gapmap.sqlite_collation_rows({"inventory": {}}, {}), [])


class DeviceIdentifiers(unittest.TestCase):
    def test_build_get_serial_needs_its_service(self) -> None:
        """wormhole2: Build.getSerial threw NullPointerException where Android throws SecurityException."""
        scan = {"inventory": {"platform_method_names": {"Landroid/os/Build;": ["getSerial", "getRadioVersion"]}}}
        row = gapmap.device_identifier_rows(scan, {})[0]
        self.assertEqual((row["id"], row["verdict"]), ("svc:device_identifiers", "null"))
        model = {"device_identifiers": [{"kind": "adapter", "source": "framework/core/java/OHServiceManager.java:188"}]}
        self.assertEqual(gapmap.device_identifier_rows(scan, model)[0]["verdict"], "supplied")
        self.assertEqual(gapmap.device_identifier_rows(scan, {"device_identifiers": [{"kind": "explicit-null"}]})[0]["verdict"],
                         "null")
        self.assertEqual(gapmap.device_identifier_rows({"inventory": {}}, model), [])


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


class UsesLibrary(unittest.TestCase):
    FACTS = {"uses_libraries": [{"name": "org.apache.http.legacy", "required": True},
                                {"name": "com.google.android.maps", "required": False},
                                {"name": "org.apache.http.legacy", "required": True}]}

    def test_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bridge = Path(tmp) / "framework/activity/java/AppSchedulerBridge.java"
            bridge.parent.mkdir(parents=True)
            bridge.write_text("static List sharedLibraryInfos(String[] jars)")
            data = {"artifacts": {"framework/org.apache.http.legacy.jar": {}}}
            rows = {r["id"]: r for r in gapmap.uses_library_rows(self.FACTS, data, Path(tmp))}
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows["pm:uses-library:org.apache.http.legacy"]["verdict"], "supplied")
            self.assertEqual(rows["pm:uses-library:com.google.android.maps"]["verdict"], "absent")
            rows = {r["id"]: r for r in gapmap.uses_library_rows(self.FACTS, {"artifacts": {}}, Path(tmp))}
            self.assertEqual(rows["pm:uses-library:org.apache.http.legacy"]["verdict"], "missing")


class LibcoreNatives(unittest.TestCase):
    RUNTIME = {"bridge_libraries": [{"name": "libart.so", "jni_registration_entries": [
                    {"name": "hashCode", "signature": "()I"}]}],
               "system_libraries": [],
               "classes": {"Ljava/nio/MappedByteBuffer;": {"native_methods": ["load0(JJ)V", "force0(Ljava/io/FileDescriptor;JJ)V"]},
                           "Ljava/lang/Object;": {"native_methods": ["hashCode()I"]},
                           "Ljava/util/TimeZone;": {"native_methods": ["getSystemTimeZoneID(Ljava/lang/String;)Ljava/lang/String;"]},
                           "Ljava/lang/invoke/VarHandle;": {"native_methods": ["get([Ljava/lang/Object;)Ljava/lang/Object;"]}}}

    def rows(self, runtime):
        scan = {"inventory": {"platform_method_names": {
            "Ljava/nio/MappedByteBuffer;": ["load"], "Ljava/lang/Object;": ["hashCode"],
            "Ljava/util/TimeZone;": ["getDefault"], "Ljava/lang/invoke/VarHandle;": ["get"]}}}
        return {r["id"]: r for r in gapmap.framework_native_rows(scan, runtime)}

    def test_libcore_judged_when_libart_indexed(self) -> None:
        rows = self.rows(self.RUNTIME)
        self.assertEqual(set(rows), {"jni:java.nio.MappedByteBuffer"}, "Object is libart's; TimeZone unreached; VarHandle intrinsic")
        self.assertIn("MappedByteBuffer.load", rows["jni:java.nio.MappedByteBuffer"]["app_evidence"])

    def test_libcore_ignored_without_libart(self) -> None:
        runtime = dict(self.RUNTIME, bridge_libraries=[])
        self.assertEqual(self.rows(runtime), {})

class AndroidNamespaceNdk(unittest.TestCase):
    RUNTIME = {"bridge_libraries": [
        {"name": "libandroid.so", "needed": ["libhwui.so"], "exported_symbols": ["ALooper_prepare"]},
        {"name": "libhwui.so", "needed": [], "exported_symbols": ["AHardwareBuffer_unlock", "glGetError"]}]}
    NAMESPACE = [{"name": "libandroid.so", "exported_symbols": []}]
    NDK = {"symbols": [{"library": "libandroid.so", "symbol": s}
                       for s in ("ALooper_prepare", "AHardwareBuffer_unlock")]}
    SCAN = {"apk": {}, "inventory": {"elfs": [
        {"name": "libscroll.so", "needed": ["libandroid.so", "libGLESv2.so"],
         "undefined_symbols": ["AHardwareBuffer_unlock", "ALooper_prepare", "glGetError"]}]}}

    def rows(self, rows, shim=frozenset()):
        return gapmap.android_namespace_rows(self.SCAN, rows, self.NAMESPACE, self.RUNTIME, set(shim), self.NDK)

    def test_routed_library_needs_what_only_the_runtime_copy_reaches(self) -> None:
        routed = [{"id": "load:x", "launch_args": ["--android-native-target", "libscroll.so"]}]
        (row,) = self.rows(routed)
        self.assertEqual(row["id"], "load:android-namespace-ndk:libandroid.so")
        self.assertEqual(row["open_symbols"], ["AHardwareBuffer_unlock", "ALooper_prepare"], "glGetError is not libandroid's")
        self.assertEqual(row["verdict"], "missing")
        (row,) = self.rows(routed, {"AHardwareBuffer_unlock", "ALooper_prepare"})
        self.assertEqual(row["verdict"], "supplied")

    def test_default_namespace_loads_are_not_affected(self) -> None:
        self.assertEqual(self.rows([]), [])
        self.assertEqual(len(self.rows([{"id": "load:app-storage-exec"}])), 1)

    def test_macro_forwarders_count_as_shim_exports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            shim = Path(tmp) / "framework/webview-shim/webview_bionic_shim.c"
            shim.parent.mkdir(parents=True)
            shim.write_text("WESTLAKE_ALOOPER_FORWARD(int, AHardwareBuffer_unlock, (void *b, int *f), (b, f))\n")
            self.assertIn("AHardwareBuffer_unlock", gapmap.bionic_shim_exports(Path(tmp)))

    def test_every_compiled_shim_source_counts(self) -> None:
        """SDL2's AConfiguration and sensor imports are defined in a second shim source."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shim = root / "framework/webview-shim"
            shim.mkdir(parents=True)
            (shim / "webview_bionic_shim.c").write_text("int sigaction64(int s, const void *a, void *o) {\n    return 0;\n}\n")
            (shim / "android_ndk_config.c").write_text(
                "WL_CONFIG_FIELD(Density, density)\nint ASensorManager_getSensorList(void *m, void *l)\n{\n    return 0;\n}\n"
                "static int wl_helper(void) { return 0; }\n")
            (shim / "unbuilt.c").write_text("int ASensor_getType(void *s) {\n    return -1;\n}\n")
            (root / "tools").mkdir()
            (root / "tools/build_bionic_shim.sh").write_text("$CC -c $W/webview_bionic_shim.c -o s.o\n$CC -c $W/android_ndk_config.c -o nc.o\n")
            exports = gapmap.bionic_shim_exports(root)
            self.assertTrue({"sigaction64", "AConfiguration_getDensity", "AConfiguration_setDensity",
                             "ASensorManager_getSensorList"} <= exports)
            self.assertNotIn("ASensor_getType", exports, "a source the build does not compile defines nothing")
            self.assertNotIn("wl_helper", exports)
