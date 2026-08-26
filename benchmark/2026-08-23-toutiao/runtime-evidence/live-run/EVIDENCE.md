# Westlake runtime gap evidence

Run: `toutiao-live-25055`  
Scenario: `launch-feed-view-tree-native-load`  
Runtime locks: `sha256:96366a206a3fe68c5b78a68fafc9addc63932d8ecee1ee166ab802ea62322b2b`  
APK hashes: `a1112a0c941f865847c2fab9138cf815735268fbfcd41d697412fb80992c7395`

## Evidence coverage

- Parsed events: **199**
- Native contracts watched: **1945**
- Native records excluded from this ABI's watchlist: **0**
- Reflection sites watched: **0**
- Library load events: **0**
- Events deliberately left unmatched: **103**

### Native states

| Runtime state | Contracts |
|---|---:|
| `not-observed` | 1938 |
| `runtime-primary-lookup-miss-only` | 7 |

### Reflection states

| Runtime state | Probe sites |
|---|---:|

## Observed native contracts

| State | Package | Contract | Events |
|---|---|---|---:|
| `runtime-primary-lookup-miss-only` | `com.ss.android.article.news` | `LJ/N;->MVlvYo_c()Ljava/lang/String;` | 6 |
| `runtime-primary-lookup-miss-only` | `com.ss.android.article.news` | `Lcom/bytedance/crash/jni/NativeBridge;->nAnrNativeProfilerJvmStart(J)I` | 1 |
| `runtime-primary-lookup-miss-only` | `com.ss.android.article.news` | `Lcom/bytedance/frameworks/encryptor/EncryptorUtil;->ttEncrypt([BI)[B` | 8 |
| `runtime-primary-lookup-miss-only` | `com.ss.android.article.news` | `Lcom/bytedance/fresco/nativeheif/Heif;->parseSimpleMetaByNativePtr(JI)[I` | 75 |
| `runtime-primary-lookup-miss-only` | `com.ss.android.article.news` | `Lcom/bytedance/fresco/nativeheif/Heif;->toRgba([BZIZIZIIIIIIZ)Lcom/bytedance/fresco/nativeheif/HeifData;` | 3 |
| `runtime-primary-lookup-miss-only` | `com.ss.android.article.news` | `Lcom/bytedance/fresco/nativeheif/Heif;->toRgbaBitmapByNativePtr(JZIZIIZIZIIIIII[I)Landroid/graphics/Bitmap;` | 2 |
| `runtime-primary-lookup-miss-only` | `com.ss.android.article.news` | `Lcom/bytedance/vmsdk/log/VLog;->nativeSetNativeMinLogLevel(I)V` | 1 |

## Observed reflection sites

| State | Package | Requested class | Caller | Events |
|---|---|---|---|---:|

A primary JNI lookup miss is non-terminal: it remains a miss-only observation unless a later registry/dlsym hit or terminal lookup failure is captured. Legacy events without package/hash provenance are joined only when the ledger contains exactly one APK.
