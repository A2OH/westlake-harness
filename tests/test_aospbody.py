"""The AOSP body comparison: a constant runtime body is a gap only where AOSP's body does more."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from westlake_gap.aospbody import BodyShapes, body_shape, patched_files

THING = """
package android.foo;

import android.util.Log;

/** A class whose {braces} in comments, "strings {" and '{' chars must not confuse the reader. */
public class Thing<Params, Result> {
    private static final boolean DEBUG = false;
    private static final String TAG = "Thing{";
    private final int mRoutes = Other.ROUTE_ALL;
    static final long sMinor = 1;
    private int mCount;

    @ViewDebug.ExportedProperty(mapping = {
            @ViewDebug.IntToString(from = 0, to = "NONE"),
            @ViewDebug.IntToString(from = 1, to = "ONE")
    }, category = "focus")
    public int getFocusable() {
        return mCount > 0 ? 1 : 0;
    }

    public void close() throws java.io.IOException {}

    public int getIntrinsicWidth() {
        return -1;
    }

    public static int ime() {
        return 1 << 3;
    }

    private int getLayoutResource() {
        return R.layout.thing_layout;
    }

    public int routes() {
        return mRoutes;
    }

    public static long minor() {
        return sMinor;
    }

    void log(String heading) {
        if (DEBUG) {
            Log.i(TAG, heading);
            for (int i = 0; i < 3; i++) {
                Log.i(TAG, "again");
            }
        }
    }

    void drawMargin(android.graphics.Canvas c, int x) {
        ;
    }

    void checkLooper() {
        assert mCount >= 0 : "negative";
    }

    void onKeyAccess(String key) {
        if (!DEBUG) return;
        mCount++;
    }

    protected void onPostExecute(Result result) {
    }

    public int count() {
        return mCount;
    }

    public void start() {
        mCount = 1;
        notifyAll();
    }

    public boolean isEnabled() {
        return true;
    }

    public static <T extends android.view.View> T find(T[] views, int id) {
        return null;
    }

    public static class Inner {
        public void onDone() {
        }
    }
}
"""

OVERLAY = """
package android.foo;

public class Thing {
    public boolean isEnabled() {
        return false;
    }

    public int getIntrinsicWidth() {
        return -1;
    }
}
"""


class BodyShapesAgainstAosp(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.aosp = root / "imports"
        source = self.aosp / "frameworks-base/core/java/android/foo/Thing.java"
        source.parent.mkdir(parents=True)
        source.write_text(THING)
        self.westlake = root / "westlake"
        (self.westlake / "framework").mkdir(parents=True)
        self.shapes = BodyShapes(self.aosp, self.westlake)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def shape(self, name: str, signature: str, owner: str = "Landroid/foo/Thing;") -> str:
        return self.shapes.shape(owner, name, signature)

    def test_aosps_own_trivial_bodies(self) -> None:
        for name, signature in [("close", "()V"), ("getIntrinsicWidth", "()I"), ("ime", "()I"),
                                ("getLayoutResource", "()I"), ("routes", "()I"), ("minor", "()J"),
                                ("drawMargin", "(Landroid/graphics/Canvas;I)V"), ("checkLooper", "()V"),
                                ("log", "(Ljava/lang/String;)V"), ("onPostExecute", "(Ljava/lang/Object;)V"),
                                ("find", "([Landroid/view/View;I)Landroid/view/View;")]:
            with self.subTest(name=name):
                self.assertEqual(self.shape(name, signature), "aosp-trivial")

    def test_a_member_after_an_annotation_with_an_array_is_found(self) -> None:
        self.assertEqual(self.shape("getFocusable", "()I"), "hollowed")
        self.assertEqual(self.shape("onDone", "()V", "Landroid/foo/Thing$Inner;"), "aosp-trivial")

    def test_a_body_aosp_gives_work_is_hollowed(self) -> None:
        self.assertEqual(self.shape("count", "()I"), "hollowed")  # a field read, not a constant
        self.assertEqual(self.shape("start", "()V"), "hollowed")

    def test_work_behind_a_constant_guard_is_undecided(self) -> None:
        self.assertEqual(self.shape("onKeyAccess", "(Ljava/lang/String;)V"), "unknown")

    def test_what_cannot_be_found_is_undecided(self) -> None:
        self.assertEqual(self.shape("close", "(I)V"), "unknown")
        self.assertEqual(self.shape("close", "()V", "Landroid/foo/Missing;"), "unknown")
        self.assertEqual(self.shape("run", "()V", "Landroid/foo/Thing$1;"), "unknown")

    def test_westlakes_own_copy_decides(self) -> None:
        overlay = self.westlake / "framework/core/java/android/foo/Thing.java"
        overlay.parent.mkdir(parents=True)
        overlay.write_text(OVERLAY)
        shapes = BodyShapes(self.aosp, self.westlake)
        self.assertEqual(shapes.shape("Landroid/foo/Thing;", "isEnabled", "()Z"), "hollowed")
        self.assertEqual(shapes.shape("Landroid/foo/Thing;", "getIntrinsicWidth", "()I"), "aosp-trivial")
        self.assertEqual(shapes.shape("Landroid/foo/Thing;", "close", "()V"), "unknown")

    def test_a_patched_file_is_undecided(self) -> None:
        manifest = Path(self.tmp.name) / "manifest"
        patch = manifest / "patches/android15/frameworks-base-compat.patch"
        patch.parent.mkdir(parents=True)
        patch.write_text("--- a/core/java/android/foo/Thing.java\n+++ b/core/java/android/foo/Thing.java\n")
        shapes = BodyShapes(self.aosp, self.westlake, patched_files(manifest))
        self.assertEqual(shapes.shape("Landroid/foo/Thing;", "close", "()V"), "unknown")

    def test_the_jar_decides_first(self) -> None:
        self.assertEqual(self.shapes.by_artifact("core-oj.jar", "Ljava/io/InputStream;", "close", "()V"),
                         "aosp-trivial")
        self.assertEqual(self.shapes.by_artifact("adapter-runtime-bcp.jar", "Landroid/foo/Thing;", "close", "()V"),
                         "hollowed")
        self.assertEqual(self.shapes.by_artifact("framework.jar", "Landroid/foo/Thing;", "close", "()V"),
                         "aosp-trivial")


class DeclaredOnAndroid(unittest.TestCase):
    """A member the runtime lacks is a gap only where Android's sources declare it."""

    def test_members_along_the_class_and_what_it_inherits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "imports/frameworks-base/core/java/android/foo"
            root.mkdir(parents=True)
            (root / "Base.java").write_text(
                "package android.foo; public class Base { public static final int ACTION_CLICK = 1;"
                " protected int mCount; public void setChecked(boolean checked) { mCount = 1; } }")
            (root / "Named.java").write_text("package android.foo; public interface Named { default String name() { return null; } }")
            (root / "Thing.java").write_text(
                "package android.foo; public class Thing extends Base implements Named { public Thing(int x) {} }")
            parents = {"Landroid/foo/Thing;": ["Landroid/foo/Base;", "Landroid/foo/Named;"],
                       "Landroid/foo/Base;": ["Ljava/lang/Object;"], "Landroid/foo/Named;": []}
            shapes = BodyShapes(Path(tmp) / "imports", parents=lambda c: parents.get(c, []))
            self.assertTrue(shapes.declares("Landroid/foo/Thing;", "setChecked", "(Z)V"))
            self.assertFalse(shapes.declares("Landroid/foo/Thing;", "setChecked", "(I)V"), "an overload Android lacks")
            self.assertTrue(shapes.declares("Landroid/foo/Thing;", "name", "()Ljava/lang/String;"), "an interface's")
            self.assertTrue(shapes.declares("Landroid/foo/Thing;", "ACTION_CLICK", None, field=True))
            self.assertTrue(shapes.declares("Landroid/foo/Thing;", "mCount", None, field=True))
            self.assertFalse(shapes.declares("Landroid/foo/Thing;", "ACTION_NEW", None, field=True))
            self.assertTrue(shapes.declares("Landroid/foo/Thing;", "<init>", "(I)V"))
            self.assertFalse(shapes.declares("Landroid/foo/Thing;", "<init>", "(IJ)V"))
            self.assertIsNone(shapes.declares("Landroid/bar/Other;", "run", "()V"), "no source: undecided")


class BodyShape(unittest.TestCase):
    def test_shapes(self) -> None:
        self.assertEqual(body_shape(" ", []), ("trivial", ""))
        self.assertEqual(body_shape(" return; ", []), ("trivial", ""))
        self.assertEqual(body_shape(" return (int) 0L ; ", []), ("trivial", "(int)0L"))
        self.assertEqual(body_shape(" return Integer.MAX_VALUE; ", []), ("trivial", "Integer.MAX_VALUE"))
        self.assertEqual(body_shape(" return \x010\x01; ", ['"x"']), ("trivial", '"x"'))
        self.assertEqual(body_shape(" return Foo.class; ", []), ("trivial", "Foo.class"))
        self.assertEqual(body_shape(" return compute(); ", []), ("work", ""))
        self.assertEqual(body_shape(" throw new UnsupportedOperationException(); ", []), ("work", ""))
        self.assertEqual(body_shape(" if (Build.VERSION.SDK_INT >= 21) { return; } mX = 1; ", []), ("folds", ""))
        self.assertEqual(body_shape(" if (DEBUG) Log.d(TAG, x); ", []), ("trivial", ""))
        self.assertEqual(body_shape(" if (DEBUG) a(); else b(); ", []), ("folds", ""))


if __name__ == "__main__":
    unittest.main()
