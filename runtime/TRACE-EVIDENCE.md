# Runtime evidence for native and reflective unknowns

The static scanner deliberately stops at `CU` when an APK can bind a native through
`RegisterNatives`, or when a computed/reflected class name has no proven runtime outcome. The
runtime ledger turns those records into observed states without promoting a lookup attempt into a
failure.

## Generate the watchlist

Use the per-APK scans from one runtime lock:

```bash
scan_args=()
for scan in benchmark/2026-08-21/apks/*.json; do
  scan_args+=(--scan "$scan")
done
westlake-apk-gap trace-watchlist "${scan_args[@]}" \
  --out benchmark/2026-08-21/runtime-watchlist.json
```

For a legacy Westlake stderr log, ingest **one APK at a time**. Legacy lines have no package or APK
hash envelope, so the ledger refuses to cross-attribute one event across a portfolio:

```bash
westlake-apk-gap ingest-trace \
  --scan benchmark/2026-08-21/apks/com.example.json \
  --trace runs/com.example/cold-launch.stderr \
  --run-id com.example-cold-001 \
  --scenario cold-launch \
  --out runs/com.example/cold-launch.evidence.json \
  --report-out runs/com.example/cold-launch.evidence.md
```

The parser understands the existing `[WESTLAKE-JNIMISS]`, `[WESTLAKE-JNIREG-HIT]`, and
`[WESTLAKE-JNIDLSYM]` lines. A primary miss followed by a registry or `dlsym` hit is resolved, not a
terminal failure.

## Structured event envelope

New probes should emit one JSON object after `[WESTLAKE-TRACE]`. Every event should carry the
artifact and run identity, including the actually loaded `libart`, so results from different apps
or runtime epochs cannot be merged:

```text
[WESTLAKE-TRACE] {"event_type":"REGISTER_NATIVE","run_id":"facebook-cold-001","scenario":"cold-launch","package":"com.facebook.katana","apk_sha256":"sha256...","runtime_lock_id":"sha256:...","libart_sha256":"sha256...","pid":123,"tid":456,"monotonic_ns":123456789,"class_descriptor":"Lcom/example/Foo;","method_name":"nativeOpen","method_signature":"(I)J","registration_path":"RegisterNatives","library_path":"/data/app/.../libfoo.so","library_build_id":"abcd...","function_address":"0x7f...","function_module_offset":"0x1234"}
```

Supported outcome events are:

- `NATIVE_LIBRARY_LOAD` / `NATIVE_LIBRARY_LOAD_FAILURE`
- `REGISTER_NATIVE`
- `JNI_DLSYM_HIT`
- `JNI_PRIMARY_LOOKUP_MISS` (non-terminal)
- `JNI_LOOKUP_MISS` (only after every fallback failed)
- `JNI_INVOKE_SUCCESS` / `JNI_INVOKE_FAILURE` (optional higher-cost probe)
- `CLASS_LOAD_ATTEMPT` / `CLASS_LOAD_SUCCESS` / `CLASS_LOAD_FAILURE`

Class-load events must include `requested_class`, `caller_class`, `caller_method`, and
`caller_signature`. Target-only class-load logging is ambiguous when several call sites probe the
same name.

## Runtime hook points

Keep the hooks at the Android runtime boundary:

1. Emit `REGISTER_NATIVE` in `ClassLinker::RegisterNative` after runtime callbacks have produced the
   effective function pointer. Record both original and effective pointers if they differ.
2. Emit the final lookup path from `JavaVMExt::FindCodeForNativeMethod`: normal library, agent,
   Westlake shadow registry, global `dlsym`, or terminal miss. The existing `JNIMISS` marker is
   before Westlake fallbacks and therefore must remain non-terminal.
3. Instrument the loader that actually serves `Runtime.nativeLoad`. This port currently bypasses
   `JavaVMExt::LoadNativeLibrary`, so probing only the upstream ART loader misses real app loads.
4. Emit caller-keyed class-load outcomes only for names in the generated watchlist. Do not log every
   `FindClass` call.

Resolve a function address to its module and build ID outside ART locks. On the hot path, write a
bounded event containing the pointer and take a matching `/proc/<pid>/maps` snapshot; use the ELF
build IDs from the static scan to perform the join offline. Calling `dladdr`, allocating an
unbounded string, or taking loader locks inside `RegisterNative` can change the behavior being
measured.

## Promotion rules

- `runtime-registered` and `runtime-dlsym-resolved` remove a native from the shim-port queue for that
  exact APK/runtime/run; they do not prove the implementation's semantics.
- `runtime-confirmed-miss` is actionable only when the feature stage regresses and a control run
  does not show the same observation defect.
- `not-observed` means coverage is absent. It is never evidence that the contract is optional.
- Reflection failure supports a missing-contract priority only at the exact caller site and after
  the presence/absence branch is understood.
