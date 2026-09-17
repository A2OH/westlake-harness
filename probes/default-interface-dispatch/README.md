# Default-interface-dispatch white-box probe

This probe models the exact dispatch shape exposed by X's Firebase startup:
an interface has seven methods, four are Java 8 default methods, and the concrete
receiver implements the other three. The default methods call the receiver's
abstract implementations and must return non-null values.

The Westlake failure signature is an out-of-bounds interface-method-array lookup
where a copied default method carries its receiver vtable index instead of the
declaring interface's local method index. A conforming runtime prints
`PASS_DEFAULT_AND_ABSTRACT_DISPATCH` in both `Application` and `Activity` phases.

Build with `./build.sh`. Run this same signed APK unchanged on stock Android and
Westlake, and retain the `[WL-DEFAULT-IFACE]`, `[WESTLAKE-IFOOB]`, and
`[WESTLAKE-BADIFACE]` lines as the oracle.

## 2026-08-23 result

The current Westlake runtime logs the suspected out-of-bounds diagnostic, but
the same unchanged probe passes both phases and renders:

```text
PASS_DEFAULT_AND_ABSTRACT_DISPATCH provider=crashlytics-present direct=crashlytics-present set=[crashlytics-present]
```

That refutes interface-default dispatch as the cause of X's missing
Crashlytics component. The warning is retained as diagnostic debt, but it must
not be used to justify an ART change without a separate failing reproducer.
Evidence is in
`benchmark/2026-08-22-x-weibo/probes/default-interface-baseline/`.
