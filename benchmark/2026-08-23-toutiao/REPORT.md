# Westlake API-gap benchmark

Generated: `2026-08-24T05:34:23+00:00`  
Runtime: `sha256:96366a206a3fe68c5b78a68fafc9addc63932d8ecee1ee166ab802ea62322b2b`  
APKs scanned: **1**  
Unique static gap candidates: **626**  
Directly absent classes/members: **148**  
Unresolved `CU` native/reflection records (not counted as gaps): **1945**

> This is a static compatibility overview, not a claim that every finding is reached at runtime. Computed reflection, downloaded code, dynamically registered JNI, and semantic differences require runtime probes.

## Corpus

## Per-APK overview

| Rank | App | Package | Version | DEX classes | Platform types | Methods | Fields | Candidates | Unresolved |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| ? | Toutiao | `com.ss.android.article.news` | 13.9.0 | 213034 | 5556 | 45753 | 16882 | 626 | 1945 |

## Native evidence funnel

DEX native declarations: **3257** records / **3257** unique contracts.

Retained native `CU`: **1945** records / **1945** unique contracts. Retained reflection `CU`: **0** records / **0** unique contracts.

| State | Records | Unique contracts |
|---|---:|---:|
| `apk-export-resolved` | 1309 | 1309 |
| `library-scoped-registration-unresolved` | 552 | 552 |
| `load-attributed-no-binding-evidence` | 17 | 17 |
| `registration-source-unattributed` | 25 | 25 |
| `runtime-export-resolved` | 3 | 3 |
| `static-registration-table-candidate` | 1351 | 1351 |

### Native ABI coverage

| App | Target ABI | Packaged ABIs | Status | Native declarations | Resolved | Unresolved | Candidates |
|---|---|---|---|---:|---:|---:|---:|
| Toutiao | `arm64-v8a` | `arm64-v8a` | `target-abi-available` | 3257 | 1312 | 1945 | 0 |

### Per-app native evidence states

| App | APK export | Runtime export | Static table | Load-scoped | Unattributed | ABI unavailable |
|---|---:|---:|---:|---:|---:|---:|
| Toutiao | 1309 | 3 | 1351 | 569 | 25 | 0 |

## Finding counts

- `existence_probe`: 32
- `hollow_method`: 446
- `missing_class`: 32
- `missing_field`: 13
- `missing_method`: 103

## Directly absent classes and members

| APKs | Kind | Classification | Contract | References |
|---:|---|---|---|---:|
| 1 | `missing_field` | `C9-candidate` | `Landroid/provider/MediaStore$Images$Media;->EXTERNAL_CONTENT_URI:Landroid/net/Uri;` | 107 |
| 1 | `missing_field` | `C9-candidate` | `Landroid/provider/MediaStore$Video$Media;->EXTERNAL_CONTENT_URI:Landroid/net/Uri;` | 45 |
| 1 | `missing_field` | `C9-candidate` | `Landroid/provider/MediaStore$Audio$Media;->EXTERNAL_CONTENT_URI:Landroid/net/Uri;` | 20 |
| 1 | `missing_field` | `C9-candidate` | `Landroid/provider/MediaStore$Images$Media;->INTERNAL_CONTENT_URI:Landroid/net/Uri;` | 19 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/provider/MediaStore$Video$Media;->getContentUri(Ljava/lang/String;)Landroid/net/Uri;` | 16 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/provider/MediaStore$Images$Media;->getContentUri(Ljava/lang/String;)Landroid/net/Uri;` | 15 |
| 1 | `missing_field` | `C9-candidate` | `Landroid/net/wifi/ScanResult;->level:I` | 10 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/provider/MediaStore$Audio$Media;->getContentUri(Ljava/lang/String;)Landroid/net/Uri;` | 10 |
| 1 | `missing_field` | `C9-candidate` | `Landroid/net/wifi/ScanResult;->BSSID:Ljava/lang/String;` | 9 |
| 1 | `missing_field` | `C9-candidate` | `Landroid/net/wifi/ScanResult;->timestamp:J` | 9 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getRssi()I` | 9 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/TrafficStats;->getTotalRxBytes()J` | 8 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager;->getAllNetworkInfo()[Landroid/net/NetworkInfo;` | 6 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkInfo$State;->compareTo(Ljava/lang/Enum;)I` | 6 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/TrafficStats;->getUidRxBytes(I)J` | 6 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/TrafficStats;->getUidTxBytes(I)J` | 6 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/LinkAddress;->getAddress()Ljava/net/InetAddress;` | 5 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/TrafficStats;->getMobileRxBytes()J` | 5 |
| 1 | `missing_field` | `C9-candidate` | `Landroid/net/wifi/ScanResult;->SSID:Ljava/lang/String;` | 5 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getBSSID()Ljava/lang/String;` | 5 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getFrequency()I` | 5 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getHiddenSSID()Z` | 5 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getMacAddress()Ljava/lang/String;` | 5 |
| 1 | `missing_field` | `C9-candidate` | `Landroid/provider/MediaStore$Video$Media;->INTERNAL_CONTENT_URI:Landroid/net/Uri;` | 5 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/TrafficStats;->getThreadStatsTag()I` | 4 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/TrafficStats;->getTotalTxBytes()J` | 4 |
| 1 | `missing_field` | `C9-candidate` | `Landroid/net/wifi/ScanResult;->frequency:I` | 4 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getNetworkId()I` | 4 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiManager;->calculateSignalLevel(II)I` | 4 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiManager;->getDhcpInfo()Landroid/net/DhcpInfo;` | 4 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiManager;->getScanResults()Ljava/util/List;` | 4 |
| 1 | `missing_field` | `C9-candidate` | `Landroid/provider/MediaStore$Audio$Media;->INTERNAL_CONTENT_URI:Landroid/net/Uri;` | 4 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/provider/MediaStore;->setIncludePending(Landroid/net/Uri;)Landroid/net/Uri;` | 4 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/app/usage/NetworkStats$Bucket;->getRxBytes()J` | 3 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/app/usage/NetworkStats$Bucket;->getTxBytes()J` | 3 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/bluetooth/BluetoothDevice;->getAddress()Ljava/lang/String;` | 3 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/bluetooth/BluetoothDevice;->getName()Ljava/lang/String;` | 3 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/bluetooth/le/ScanResult;->getScanRecord()Landroid/bluetooth/le/ScanRecord;` | 3 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/RouteInfo;->getDestination()Landroid/net/IpPrefix;` | 3 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/RouteInfo;->getGateway()Ljava/net/InetAddress;` | 3 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/TrafficStats;->getMobileTxBytes()J` | 3 |
| 1 | `missing_field` | `C9-candidate` | `Landroid/net/wifi/ScanResult;->capabilities:Ljava/lang/String;` | 3 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getSSID()Ljava/lang/String;` | 3 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiManager;->createWifiLock(Ljava/lang/String;)Landroid/net/wifi/WifiManager$WifiLock;` | 3 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiManager;->getConnectionInfo()Landroid/net/wifi/WifiInfo;` | 3 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/provider/MediaStore$Files;->getContentUri(Ljava/lang/String;)Landroid/net/Uri;` | 3 |
| 1 | `missing_method` | `C1/C4` | `Landroid/app/servertransaction/ClientTransaction;->getTransactionItems()Ljava/util/List;` | 2 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/app/usage/NetworkStats$Bucket;->getUid()I` | 2 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/app/usage/NetworkStats;->close()V` | 2 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/app/usage/NetworkStats;->getNextBucket(Landroid/app/usage/NetworkStats$Bucket;)Z` | 2 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/app/usage/NetworkStats;->hasNextBucket()Z` | 2 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/bluetooth/BluetoothAdapter;->cancelDiscovery()Z` | 2 |
| 1 | `missing_method` | `C1/C4` | `Landroid/content/pm/PackageParser$Activity;-><init>()V` | 2 |
| 1 | `missing_method` | `C1/C4` | `Landroid/content/pm/PackageParser$Permission;-><init>()V` | 2 |
| 1 | `missing_method` | `C1/C4` | `Landroid/content/pm/PackageParser$Provider;-><init>()V` | 2 |
| 1 | `missing_method` | `C1/C4` | `Landroid/content/pm/PackageParser$Service;-><init>()V` | 2 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getIpAddress()I` | 2 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getLinkSpeed()I` | 2 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiManager;->getWifiState()I` | 2 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/provider/MediaStore$Images$Media;->getBitmap(Landroid/content/ContentResolver;Landroid/net/Uri;)Landroid/graphics/Bitmap;` | 2 |
| 1 | `missing_method` | `C1/C4` | `Landroid/app/Instrumentation;->execStartActivity(Landroid/content/Context;Landroid/os/IBinder;Landroid/os/IBinder;Landroid/app/Activity;Landroid/content/Intent;I)Landroid/app/Instrumentation$ActivityResult;` | 1 |
| 1 | `missing_method` | `C1/C4` | `Landroid/app/Instrumentation;->execStartActivity(Landroid/content/Context;Landroid/os/IBinder;Landroid/os/IBinder;Landroid/app/Fragment;Landroid/content/Intent;I)Landroid/app/Instrumentation$ActivityResult;` | 1 |
| 1 | `missing_method` | `C1/C4` | `Landroid/app/Instrumentation;->execStartActivity(Landroid/content/Context;Landroid/os/IBinder;Landroid/os/IBinder;Landroid/app/Fragment;Landroid/content/Intent;ILandroid/os/Bundle;)Landroid/app/Instrumentation$ActivityResult;` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/app/usage/NetworkStats$Bucket;->getRxPackets()J` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/app/usage/NetworkStats$Bucket;->getTxPackets()J` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/bluetooth/BluetoothAdapter;->getBluetoothLeScanner()Landroid/bluetooth/le/BluetoothLeScanner;` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/bluetooth/BluetoothAdapter;->getBondedDevices()Ljava/util/Set;` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/bluetooth/BluetoothAdapter;->startDiscovery()Z` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/bluetooth/BluetoothAdapter;->startLeScan(Landroid/bluetooth/BluetoothAdapter$LeScanCallback;)Z` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/bluetooth/BluetoothAdapter;->stopLeScan(Landroid/bluetooth/BluetoothAdapter$LeScanCallback;)V` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/bluetooth/le/ScanRecord;->getBytes()[B` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/bluetooth/le/ScanRecord;->getManufacturerSpecificData(I)[B` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/bluetooth/le/ScanResult;->getDevice()Landroid/bluetooth/BluetoothDevice;` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/bluetooth/le/ScanResult;->getRssi()I` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager;->getDefaultProxy()Landroid/net/ProxyInfo;` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager;->reportNetworkConnectivity(Landroid/net/Network;Z)V` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager;->requestNetwork(Landroid/net/NetworkRequest;Landroid/net/ConnectivityManager$NetworkCallback;I)V` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/InetAddresses;->parseNumericAddress(Ljava/lang/String;)Ljava/net/InetAddress;` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/IpPrefix;->getAddress()Ljava/net/InetAddress;` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/IpPrefix;->getPrefixLength()I` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/Network;->fromNetworkHandle(J)Landroid/net/Network;` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkInfo;->isFailover()Z` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/RouteInfo;->getInterface()Ljava/lang/String;` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/TrafficStats;->getThreadStatsUid()I` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/TrafficStats;->tagSocket(Ljava/net/Socket;)V` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/ScanResult;-><init>(Landroid/net/wifi/ScanResult;)V` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->describeContents()I` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getAffiliatedMloLinks()Ljava/util/List;` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getApMldMacAddress()Landroid/net/MacAddress;` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getApMloLinkId()I` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getApplicableRedactions()J` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getAssociatedMloLinks()Ljava/util/List;` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getCurrentSecurityType()I` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getInformationElements()Ljava/util/List;` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getMaxSupportedRxLinkSpeedMbps()I` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getMaxSupportedTxLinkSpeedMbps()I` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getPasspointFqdn()Ljava/lang/String;` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getPasspointProviderFriendlyName()Ljava/lang/String;` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getRxLinkSpeedMbps()I` | 1 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getSubscriptionId()I` | 1 |

These contracts are absent from the exact runtime index. `C1/C4` still needs the implementation-exists decision; `C9-candidate` here means the containing deployed class or jar is demonstrably hollow/stub-like.

## Probe-only absence candidates

| APKs | Kind | Classification | Contract | References |
|---:|---|---|---|---:|
| 1 | `existence_probe` | `C8-candidate` | `Lcom/huawei/android/util/HwNotchSizeUtil;` | 40 |
| 1 | `existence_probe` | `C8-candidate` | `Landroid/util/FtFeature;` | 5 |
| 1 | `existence_probe` | `C8-candidate` | `Lflyme/config/FlymeFeature;` | 2 |
| 1 | `existence_probe` | `C8-candidate` | `Landroid/os/PerformanceManager;` | 1 |
| 1 | `existence_probe` | `C8-candidate` | `Landroid/util/SeempLog;` | 1 |
| 1 | `existence_probe` | `C8-candidate` | `Landroid/view/MiuiWindowManager$LayoutParams;` | 1 |
| 1 | `existence_probe` | `C8-candidate` | `Landroidx/sharetarget/ShortcutInfoCompatSaverImpl;` | 1 |
| 1 | `existence_probe` | `C8-candidate` | `Lcom/bytedance/deviceinfo/AiEntryImpl;` | 1 |
| 1 | `existence_probe` | `C8-candidate` | `Lcom/bytedance/ies/android/loki_lynx/anniex/AnnieXLynxService;` | 1 |
| 1 | `existence_probe` | `C8-candidate` | `Lcom/bytedance/novel/service/loader/__service_loader;` | 1 |
| 1 | `existence_probe` | `C8-candidate` | `Lcom/bytedance/ugc/medialib/tt/VideoPublisherDependImpl;` | 1 |
| 1 | `existence_probe` | `C8-candidate` | `Lcom/bytedance/ugc/medialib/vesdk/VEEditorServiceImpl;` | 1 |
| 1 | `existence_probe` | `C8-candidate` | `Lcom/bytedance/ugc/medialib/vesdk/VideoNiuServiceImpl;` | 1 |
| 1 | `existence_probe` | `C8-candidate` | `Lcom/bytedance/ugc/publish/report/ActionAnalysisServiceImpl;` | 1 |
| 1 | `existence_probe` | `C8-candidate` | `Lcom/bytedance/ugc/ugcpublish/vesdklib/VEVideoServiceImpl;` | 1 |
| 1 | `existence_probe` | `C8-candidate` | `Lcom/google/android/gms/org/conscrypt/SSLParametersImpl;` | 1 |
| 1 | `existence_probe` | `C8-candidate` | `Lcom/google/net/cronet/telemetry/CronetLoggerImpl;` | 1 |
| 1 | `existence_probe` | `C8-candidate` | `Lcom/huawei/ark/app/ArkApplicationInfo;` | 1 |
| 1 | `existence_probe` | `C8-candidate` | `Lcom/mediatek/boostframework/Performance;` | 1 |
| 1 | `existence_probe` | `C8-candidate` | `Lcom/mediatek/powerhalmgr/PowerHalMgrImpl;` | 1 |
| 1 | `existence_probe` | `C8-candidate` | `Lcom/qualcomm/qti/Performance;` | 1 |
| 1 | `existence_probe` | `C8-candidate` | `Lcom/ss/android/ugc/aweme/im/saas/host_interface/IDouyinIMProvider;` | 1 |
| 1 | `existence_probe` | `C8-candidate` | `Lcom/ss/android/videoaddetail/VideoAdDetailManagerDepend;` | 1 |
| 1 | `existence_probe` | `C8-candidate` | `Lcom/tencent/tinker/loader/hotplug/mira/pm;` | 1 |
| 1 | `existence_probe` | `C8-candidate` | `Ljava/lang/Module;` | 1 |
| 1 | `existence_probe` | `C8-candidate` | `Ljava/lang/module/ModuleDescriptor;` | 1 |
| 1 | `existence_probe` | `C8-candidate` | `Lkotlinx/coroutines/test/internal/TestMainDispatcherFactory;` | 1 |
| 1 | `existence_probe` | `C8-candidate` | `Lmiui/util/FeatureParser;` | 1 |
| 1 | `existence_probe` | `C8-candidate` | `Lsun/misc/JavaLangAccess;` | 1 |
| 1 | `existence_probe` | `C8-candidate` | `Lsun/misc/SharedSecrets;` | 1 |
| 1 | `existence_probe` | `C8-candidate` | `Lvivo/app/VivoFrameworkFactory;` | 1 |
| 1 | `existence_probe` | `C8-candidate` | `Lvivo/app/vperf/AbsVivoPerfManager;` | 1 |

These require the strict C8 gate: all supplied/plugin DEX must remain call-free for the type, and runtime evidence must show which presence branch is faithful.

## Hollow-body heuristic candidates

| APKs | Kind | Classification | Contract | References |
|---:|---|---|---|---:|
| 1 | `hollow_method` | `C9-candidate` | `Ljava/io/InputStream;->close()V` | 1263 |
| 1 | `hollow_method` | `C9-candidate` | `Landroid/app/Activity;->onWindowFocusChanged(Z)V` | 597 |
| 1 | `hollow_method` | `C9-candidate` | `Landroid/graphics/drawable/Drawable;->getIntrinsicWidth()I` | 396 |
| 1 | `hollow_method` | `C9-candidate` | `Landroid/graphics/drawable/Drawable;->getIntrinsicHeight()I` | 379 |
| 1 | `hollow_method` | `C9-candidate` | `Ljava/io/ByteArrayOutputStream;->close()V` | 292 |
| 1 | `hollow_method` | `C9-candidate` | `Landroid/app/Dialog;->onCreate(Landroid/os/Bundle;)V` | 271 |
| 1 | `hollow_method` | `C9-candidate` | `Landroid/animation/AnimatorListenerAdapter;->onAnimationEnd(Landroid/animation/Animator;)V` | 189 |
| 1 | `hollow_method` | `C9-candidate` | `Ljava/io/OutputStream;->close()V` | 169 |
| 1 | `hollow_method` | `C9-candidate` | `Landroid/view/View;->onDraw(Landroid/graphics/Canvas;)V` | 168 |
| 1 | `hollow_method` | `C9-candidate` | `Ljava/net/InetAddress;->getHostAddress()Ljava/lang/String;` | 129 |
| 1 | `hollow_method` | `C9-candidate` | `Landroid/animation/Animator;->start()V` | 116 |
| 1 | `hollow_method` | `C9-candidate` | `Landroid/animation/Animator;->cancel()V` | 113 |
| 1 | `hollow_method` | `C9-candidate` | `Landroid/os/Handler;->handleMessage(Landroid/os/Message;)V` | 110 |
| 1 | `hollow_method` | `C9-candidate` | `Ljava/io/OutputStream;->flush()V` | 109 |
| 1 | `hollow_method` | `C9-candidate` | `Landroid/graphics/drawable/Drawable;->isStateful()Z` | 99 |
| 1 | `hollow_method` | `C9-candidate` | `Landroid/net/NetworkInfo;->isAvailable()Z` | 98 |
| 1 | `hollow_method` | `C9-candidate` | `Ljava/io/InputStream;->markSupported()Z` | 98 |
| 1 | `hollow_method` | `C9-candidate` | `Ljava/io/InputStream;->available()I` | 88 |
| 1 | `hollow_method` | `C9-candidate` | `Ljava/io/FileOutputStream;->flush()V` | 87 |
| 1 | `hollow_method` | `C9-candidate` | `Landroid/animation/AnimatorListenerAdapter;->onAnimationCancel(Landroid/animation/Animator;)V` | 85 |
| 1 | `hollow_method` | `C9-candidate` | `Ljava/lang/Object;->finalize()V` | 75 |
| 1 | `hollow_method` | `C9-candidate` | `Landroid/graphics/drawable/Drawable;->getConstantState()Landroid/graphics/drawable/Drawable$ConstantState;` | 68 |
| 1 | `hollow_method` | `C9-candidate` | `Landroid/animation/AnimatorListenerAdapter;->onAnimationStart(Landroid/animation/Animator;)V` | 67 |
| 1 | `hollow_method` | `C9-candidate` | `Landroid/widget/FrameLayout;->onSizeChanged(IIII)V` | 60 |
| 1 | `hollow_method` | `C9-candidate` | `Ljava/io/ByteArrayInputStream;->close()V` | 59 |
| 1 | `hollow_method` | `C9-candidate` | `Landroid/webkit/WebViewClient;->onPageFinished(Landroid/webkit/WebView;Ljava/lang/String;)V` | 54 |
| 1 | `hollow_method` | `C9-candidate` | `Landroid/view/View;->isInEditMode()Z` | 50 |
| 1 | `hollow_method` | `C9-candidate` | `Landroid/view/View;->onSizeChanged(IIII)V` | 50 |
| 1 | `hollow_method` | `C9-candidate` | `Landroid/app/Service;->onCreate()V` | 43 |
| 1 | `hollow_method` | `C9-candidate` | `Ljava/net/HttpURLConnection;->getHeaderField(Ljava/lang/String;)Ljava/lang/String;` | 43 |
| 1 | `hollow_method` | `C9-candidate` | `Landroid/view/View;->onDetachedFromWindow()V` | 40 |
| 1 | `hollow_method` | `C9-candidate` | `Ljava/io/ByteArrayOutputStream;->flush()V` | 40 |
| 1 | `hollow_method` | `C9-candidate` | `Landroid/app/Service;->onDestroy()V` | 38 |
| 1 | `hollow_method` | `C9-candidate` | `Landroid/webkit/WebViewClient;->onPageStarted(Landroid/webkit/WebView;Ljava/lang/String;Landroid/graphics/Bitmap;)V` | 38 |
| 1 | `hollow_method` | `C9-candidate` | `Landroid/webkit/WebViewClient;->onReceivedError(Landroid/webkit/WebView;ILjava/lang/String;Ljava/lang/String;)V` | 37 |
| 1 | `hollow_method` | `C9-candidate` | `Landroid/view/ViewGroup;->onSizeChanged(IIII)V` | 36 |
| 1 | `hollow_method` | `C9-candidate` | `Landroid/webkit/WebViewClient;->shouldInterceptRequest(Landroid/webkit/WebView;Ljava/lang/String;)Landroid/webkit/WebResourceResponse;` | 35 |
| 1 | `hollow_method` | `C9-candidate` | `Landroid/webkit/WebViewClient;->onReceivedHttpError(Landroid/webkit/WebView;Landroid/webkit/WebResourceRequest;Landroid/webkit/WebResourceResponse;)V` | 34 |
| 1 | `hollow_method` | `C9-candidate` | `Landroid/webkit/WebViewClient;->shouldOverrideUrlLoading(Landroid/webkit/WebView;Ljava/lang/String;)Z` | 34 |
| 1 | `hollow_method` | `C9-candidate` | `Ljava/lang/System;->getSecurityManager()Ljava/lang/SecurityManager;` | 34 |

Small constant/no-op bodies include legitimate base hooks and defaults. This list is a review queue, not proof that every listed body is a semantic defect.

## Prioritization

The process forbids composite portfolio scoring below 25 APKs.

## Interpretation limits

- Missing classes/members are direct static mismatches against the hashed runtime snapshot.
- `C8-candidate` means a missing class name flows into a class-existence API and has no callable use in the scanned input; runtime/plugin proof is still required before adding a presence-only class.
- `C9-candidate` is a generated-small-body or hollow/stub-container heuristic and requires comparison with the matching AOSP contract.
- `CU` native findings may be satisfied by `RegisterNatives`; they are not counted as proven unbound symbols.
- Native results are target-ABI-specific; an unavailable packaged ABI is reported separately instead of borrowing symbols from another ABI.
- Recovered `JNINativeMethod` entries and load-library attribution narrow the registration source but remain unresolved until runtime registration is observed.
- Split APKs and code downloaded after installation must be supplied as additional scan inputs for complete coverage.
