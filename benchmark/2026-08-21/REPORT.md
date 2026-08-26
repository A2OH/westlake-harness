# Westlake API-gap benchmark

Generated: `2026-08-22T03:45:25+00:00`  
Runtime: `sha256:ea40fb1c62fd3a5bc9d45cf6db86de1ffafd783b9f6f9ade26abcdbfd7d5ab80`  
APKs scanned: **10**  
Unique static gap candidates: **1586**  
Directly absent classes/members: **594**  
Unresolved `CU` native/reflection records (not counted as gaps): **37330**

> This is a static compatibility overview, not a claim that every finding is reached at runtime. Computed reflection, downloaded code, dynamically registered JNI, and semantic differences require runtime probes.

## Corpus

Source: [Similarweb global Google Play top-free third-party benchmark](https://www.similarweb.com/top-apps/google/top-free/), observed `2026-08-20`.

Selection rule: First ten ranked third-party installable applications in chart order. Excluded: Google platform applications/services and OEM/system applications.

Exact downloaded versions, container hashes, split counts, and retrieval tooling are recorded in the supplied download lock.

## Per-APK overview

| Rank | App | Package | Version | DEX classes | Platform types | Methods | Fields | Candidates | Unresolved |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Facebook | `com.facebook.katana` | 575.0.0.45.73 | 4500 | 810 | 3563 | 270 | 179 | 1577 |
| 2 | Messenger | `com.facebook.orca` | 575.0.0.48.90 | 130078 | 2055 | 11312 | 990 | 530 | 11532 |
| 3 | Instagram | `com.instagram.android` | 443.0.0.48.82 | 188429 | 2230 | 12208 | 1155 | 565 | 8575 |
| 4 | Amazon Shopping | `com.amazon.mShop.android.shopping` | 32.12.4.100 | 70221 | 2389 | 13343 | 1832 | 461 | 3765 |
| 5 | TikTok | `com.zhiliaoapp.musically` | 46.6.1 | 456275 | 2008 | 12880 | 1072 | 723 | 3424 |
| 6 | WhatsApp | `com.whatsapp` | 2.26.31.77 | 94809 | 2094 | 11135 | 897 | 541 | 2989 |
| 7 | Cash App | `com.squareup.cash` | 5.65.0 | 103926 | 1947 | 10669 | 977 | 486 | 1087 |
| 8 | Discord | `com.discord` | 341.13 - Stable | 17535 | 1467 | 8076 | 771 | 306 | 1345 |
| 9 | Snapchat | `com.snapchat.android` | 14.20.0.50 | 88759 | 1745 | 9809 | 795 | 466 | 1603 |
| 10 | Yahoo Mail | `com.yahoo.mobile.client.android.mail` | 26.32.1 | 71528 | 1985 | 10614 | 1245 | 380 | 1433 |

## Native evidence funnel

DEX native declarations: **49941** records / **36002** unique contracts.

Retained native `CU`: **37247** records / **23949** unique contracts. Retained reflection `CU`: **83** records / **47** unique contracts.

| State | Records | Unique contracts |
|---|---:|---:|
| `apk-export-resolved` | 12692 | 12374 |
| `library-scoped-registration-unresolved` | 8891 | 7012 |
| `load-attributed-no-binding-evidence` | 1098 | 1098 |
| `registration-source-unattributed` | 18093 | 12682 |
| `runtime-export-resolved` | 2 | 2 |
| `static-registration-table-candidate` | 2649 | 2416 |
| `target-abi-unavailable` | 6516 | 5402 |

### Native ABI coverage

| App | Target ABI | Packaged ABIs | Status | Native declarations | Resolved | Unresolved | Candidates |
|---|---|---|---|---:|---:|---:|---:|
| Facebook | `arm64-v8a` | `arm64-v8a` | `target-abi-available` | 1578 | 1 | 1577 | 0 |
| Messenger | `arm64-v8a` | `arm64-v8a` | `target-abi-available` | 11537 | 8 | 11529 | 0 |
| Instagram | `arm64-v8a` | `arm64-v8a` | `target-abi-available` | 8887 | 321 | 8566 | 0 |
| Amazon Shopping | `arm64-v8a` | `armeabi-v7a` | `target-abi-unavailable` | 3755 | 0 | 3755 | 0 |
| TikTok | `arm64-v8a` | `arm64-v8a` | `target-abi-available` | 13166 | 9773 | 3393 | 0 |
| WhatsApp | `arm64-v8a` | `arm64-v8a` | `target-abi-available` | 2989 | 1 | 2988 | 0 |
| Cash App | `arm64-v8a` | `arm64-v8a` | `target-abi-available` | 1129 | 49 | 1080 | 0 |
| Discord | `arm64-v8a` | `armeabi-v7a` | `target-abi-unavailable` | 1340 | 0 | 1340 | 0 |
| Snapchat | `arm64-v8a` | `arm64-v8a` | `target-abi-available` | 4139 | 2541 | 1598 | 0 |
| Yahoo Mail | `arm64-v8a` | `armeabi-v7a` | `target-abi-unavailable` | 1421 | 0 | 1421 | 0 |

### Per-app native evidence states

| App | APK export | Runtime export | Static table | Load-scoped | Unattributed | ABI unavailable |
|---|---:|---:|---:|---:|---:|---:|
| Facebook | 1 | 0 | 71 | 1506 | 0 | 0 |
| Messenger | 8 | 0 | 127 | 4380 | 7022 | 0 |
| Instagram | 321 | 0 | 125 | 1789 | 6652 | 0 |
| Amazon Shopping | 0 | 0 | 0 | 0 | 0 | 3755 |
| TikTok | 9771 | 2 | 1688 | 283 | 1422 | 0 |
| WhatsApp | 1 | 0 | 26 | 0 | 2962 | 0 |
| Cash App | 49 | 0 | 64 | 1016 | 0 | 0 |
| Discord | 0 | 0 | 0 | 0 | 0 | 1340 |
| Snapchat | 2541 | 0 | 548 | 1015 | 35 | 0 |
| Yahoo Mail | 0 | 0 | 0 | 0 | 0 | 1421 |

## Finding counts

- `existence_probe`: 716
- `hollow_method`: 2289
- `missing_class`: 406
- `missing_field`: 131
- `missing_method`: 1095

## Directly absent classes and members

| APKs | Kind | Classification | Contract | References |
|---:|---|---|---|---:|
| 10 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkCapabilities;->hasTransport(I)Z` | 323 |
| 10 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkInfo;->isConnected()Z` | 273 |
| 10 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager;->getActiveNetworkInfo()Landroid/net/NetworkInfo;` | 229 |
| 10 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkInfo;->getType()I` | 188 |
| 10 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager;->getNetworkCapabilities(Landroid/net/Network;)Landroid/net/NetworkCapabilities;` | 175 |
| 10 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager;->getActiveNetwork()Landroid/net/Network;` | 155 |
| 10 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkInfo;->getSubtype()I` | 79 |
| 10 | `missing_class` | `C1/C4` | `Landroid/os/ext/SdkExtensions;` | 0 |
| 9 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkCapabilities;->hasCapability(I)Z` | 207 |
| 9 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager;->unregisterNetworkCallback(Landroid/net/ConnectivityManager$NetworkCallback;)V` | 101 |
| 9 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkRequest$Builder;->addCapability(I)Landroid/net/NetworkRequest$Builder;` | 96 |
| 9 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkRequest$Builder;->build()Landroid/net/NetworkRequest;` | 96 |
| 9 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkRequest$Builder;->addTransportType(I)Landroid/net/NetworkRequest$Builder;` | 74 |
| 9 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager;->registerDefaultNetworkCallback(Landroid/net/ConnectivityManager$NetworkCallback;)V` | 64 |
| 9 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager;->registerNetworkCallback(Landroid/net/NetworkRequest;Landroid/net/ConnectivityManager$NetworkCallback;)V` | 51 |
| 9 | `missing_method` | `C9-candidate` | `Landroid/graphics/ColorMatrix;->setSaturation(F)V` | 41 |
| 9 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager;->getAllNetworks()[Landroid/net/Network;` | 39 |
| 9 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiManager;->getConnectionInfo()Landroid/net/wifi/WifiInfo;` | 37 |
| 9 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkInfo;->isConnectedOrConnecting()Z` | 33 |
| 9 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getSSID()Ljava/lang/String;` | 33 |
| 9 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiManager;->isWifiEnabled()Z` | 33 |
| 9 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getBSSID()Ljava/lang/String;` | 31 |
| 9 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager;->getNetworkInfo(Landroid/net/Network;)Landroid/net/NetworkInfo;` | 30 |
| 9 | `missing_method` | `C9-candidate` | `Landroid/provider/MediaStore;->getPickImagesMaxLimit()I` | 21 |
| 9 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getRssi()I` | 19 |
| 9 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getFrequency()I` | 16 |
| 8 | `missing_field` | `C9-candidate` | `Landroid/provider/MediaStore$Images$Media;->EXTERNAL_CONTENT_URI:Landroid/net/Uri;` | 198 |
| 8 | `missing_field` | `C9-candidate` | `Landroid/provider/MediaStore$Video$Media;->EXTERNAL_CONTENT_URI:Landroid/net/Uri;` | 113 |
| 8 | `missing_method` | `C9-candidate` | `Landroid/provider/MediaStore$Files;->getContentUri(Ljava/lang/String;)Landroid/net/Uri;` | 47 |
| 8 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager;->isActiveNetworkMetered()Z` | 38 |
| 8 | `missing_method` | `C9-candidate` | `Landroid/graphics/ColorMatrix;-><init>([F)V` | 31 |
| 8 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkRequest$Builder;->removeCapability(I)Landroid/net/NetworkRequest$Builder;` | 21 |
| 8 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkInfo;->isRoaming()Z` | 17 |
| 8 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager;->getLinkProperties(Landroid/net/Network;)Landroid/net/LinkProperties;` | 16 |
| 8 | `missing_class` | `C1/C4` | `Landroid/net/ssl/SSLSockets;` | 0 |
| 7 | `missing_method` | `C9-candidate` | `Landroid/net/TrafficStats;->clearThreadStatsTag()V` | 216 |
| 7 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkInfo;->getTypeName()Ljava/lang/String;` | 75 |
| 7 | `missing_method` | `C9-candidate` | `Landroid/bluetooth/BluetoothDevice;->getAddress()Ljava/lang/String;` | 73 |
| 7 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkInfo;->getState()Landroid/net/NetworkInfo$State;` | 35 |
| 7 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager$NetworkCallback;->onAvailable(Landroid/net/Network;)V` | 33 |
| 7 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager$NetworkCallback;->onLost(Landroid/net/Network;)V` | 33 |
| 7 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkCapabilities;->getLinkDownstreamBandwidthKbps()I` | 33 |
| 7 | `missing_field` | `C9-candidate` | `Landroid/provider/MediaStore$Images$Media;->INTERNAL_CONTENT_URI:Landroid/net/Uri;` | 30 |
| 7 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkInfo;->getDetailedState()Landroid/net/NetworkInfo$DetailedState;` | 23 |
| 7 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager$NetworkCallback;->onCapabilitiesChanged(Landroid/net/Network;Landroid/net/NetworkCapabilities;)V` | 22 |
| 7 | `missing_method` | `C9-candidate` | `Landroid/graphics/ColorMatrix;->setScale(FFFF)V` | 20 |
| 7 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager;->requestNetwork(Landroid/net/NetworkRequest;Landroid/net/ConnectivityManager$NetworkCallback;)V` | 18 |
| 7 | `missing_method` | `C1/C4` | `Landroid/view/View;->setFrameContentVelocity(F)V` | 13 |
| 7 | `missing_method` | `C9-candidate` | `Landroid/provider/MediaStore$Images$Thumbnails;->queryMiniThumbnail(Landroid/content/ContentResolver;JI[Ljava/lang/String;)Landroid/database/Cursor;` | 8 |
| 7 | `missing_method` | `C1/C4` | `Landroid/text/StaticLayout$Builder;->setUseBoundsForWidth(Z)Landroid/text/StaticLayout$Builder;` | 8 |
| 7 | `missing_class` | `C1/C4` | `Landroid/bluetooth/BluetoothAdapter;` | 0 |
| 7 | `missing_class` | `C1/C4` | `Landroid/bluetooth/BluetoothManager;` | 0 |
| 7 | `missing_class` | `C1/C4` | `Landroid/bluetooth/le/BluetoothLeScanner;` | 0 |
| 7 | `missing_class` | `C1/C4` | `Landroid/bluetooth/le/ScanCallback;` | 0 |
| 7 | `missing_class` | `C1/C4` | `Landroid/bluetooth/le/ScanSettings;` | 0 |
| 7 | `missing_class` | `C1/C4` | `Landroid/net/NetworkInfo$State;` | 0 |
| 7 | `missing_class` | `C1/C4` | `Landroid/provider/MediaStore$Downloads;` | 0 |
| 7 | `missing_class` | `C1/C4` | `Landroid/provider/MediaStore$Video$Thumbnails;` | 0 |
| 6 | `missing_method` | `C9-candidate` | `Landroid/net/Network;->getNetworkHandle()J` | 73 |
| 6 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkInfo;->isAvailable()Z` | 58 |
| 6 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkInfo;->getSubtypeName()Ljava/lang/String;` | 54 |
| 6 | `missing_method` | `C9-candidate` | `Landroid/bluetooth/BluetoothDevice;->getName()Ljava/lang/String;` | 49 |
| 6 | `missing_field` | `C9-candidate` | `Landroid/provider/MediaStore$Audio$Media;->EXTERNAL_CONTENT_URI:Landroid/net/Uri;` | 36 |
| 6 | `missing_method` | `C9-candidate` | `Landroid/provider/MediaStore$Images$Media;->getContentUri(Ljava/lang/String;)Landroid/net/Uri;` | 24 |
| 6 | `missing_method` | `C9-candidate` | `Landroid/bluetooth/le/ScanResult;->getScanRecord()Landroid/bluetooth/le/ScanRecord;` | 18 |
| 6 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkCapabilities;->getLinkUpstreamBandwidthKbps()I` | 18 |
| 6 | `missing_method` | `C9-candidate` | `Landroid/provider/MediaStore$Images$Thumbnails;->getThumbnail(Landroid/content/ContentResolver;JILandroid/graphics/BitmapFactory$Options;)Landroid/graphics/Bitmap;` | 16 |
| 6 | `missing_method` | `C9-candidate` | `Landroid/net/LinkProperties;->getInterfaceName()Ljava/lang/String;` | 14 |
| 6 | `missing_field` | `C9-candidate` | `Landroid/net/wifi/ScanResult;->BSSID:Ljava/lang/String;` | 13 |
| 6 | `missing_field` | `C9-candidate` | `Landroid/provider/MediaStore$Images$Thumbnails;->EXTERNAL_CONTENT_URI:Landroid/net/Uri;` | 13 |
| 6 | `missing_method` | `C9-candidate` | `Landroid/net/LinkProperties;->getLinkAddresses()Ljava/util/List;` | 11 |
| 6 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkCapabilities;->getTransportInfo()Landroid/net/TransportInfo;` | 11 |
| 6 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkInfo;->getExtraInfo()Ljava/lang/String;` | 11 |
| 6 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getLinkSpeed()I` | 11 |
| 6 | `missing_method` | `C9-candidate` | `Landroid/bluetooth/le/ScanResult;->getRssi()I` | 9 |
| 6 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getRxLinkSpeedMbps()I` | 8 |
| 6 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getTxLinkSpeedMbps()I` | 8 |
| 6 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiManager;->calculateSignalLevel(II)I` | 8 |
| 6 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiManager;->getScanResults()Ljava/util/List;` | 8 |
| 6 | `missing_method` | `C1/C4` | `Landroid/view/inputmethod/EditorInfo;->setStylusHandwritingEnabled(Z)V` | 7 |
| 6 | `missing_method` | `C1/C4` | `Landroid/app/job/JobInfo$Builder;->setTraceTag(Ljava/lang/String;)Landroid/app/job/JobInfo$Builder;` | 6 |
| 6 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkRequest;->getCapabilities()[I` | 6 |
| 6 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkRequest;->getTransportTypes()[I` | 6 |
| 6 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkRequest;->hasCapability(I)Z` | 6 |
| 6 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkRequest;->hasTransport(I)Z` | 6 |
| 6 | `missing_class` | `C1/C4` | `Landroid/adservices/measurement/MeasurementManager;` | 0 |
| 6 | `missing_class` | `C1/C4` | `Landroid/bluetooth/BluetoothGatt;` | 0 |
| 6 | `missing_class` | `C1/C4` | `Landroid/bluetooth/BluetoothGattCallback;` | 0 |
| 6 | `missing_class` | `C1/C4` | `Landroid/bluetooth/BluetoothGattCharacteristic;` | 0 |
| 6 | `missing_class` | `C1/C4` | `Landroid/bluetooth/BluetoothGattService;` | 0 |
| 6 | `missing_class` | `C1/C4` | `Landroid/bluetooth/le/ScanSettings$Builder;` | 0 |
| 6 | `missing_class` | `C1/C4` | `Landroid/view/DisplayListCanvas;` | 0 |
| 6 | `missing_class` | `C1/C4` | `Landroid/view/RenderNode;` | 0 |
| 6 | `missing_class` | `C1/C4` | `Landroid/view/ScrollFeedbackProvider;` | 0 |
| 5 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager;->getRestrictBackgroundStatus()I` | 18 |
| 5 | `missing_method` | `C9-candidate` | `Landroid/bluetooth/BluetoothDevice;->getBondState()I` | 17 |
| 5 | `missing_method` | `C9-candidate` | `Landroid/provider/MediaStore$Video$Media;->getContentUri(Ljava/lang/String;)Landroid/net/Uri;` | 16 |
| 5 | `missing_method` | `C9-candidate` | `Landroid/net/TrafficStats;->getTotalTxBytes()J` | 15 |
| 5 | `missing_method` | `C9-candidate` | `Landroid/bluetooth/le/ScanResult;->getDevice()Landroid/bluetooth/BluetoothDevice;` | 13 |
| 5 | `missing_method` | `C9-candidate` | `Landroid/net/TrafficStats;->getTotalRxBytes()J` | 13 |

These contracts are absent from the exact runtime index. `C1/C4` still needs the implementation-exists decision; `C9-candidate` here means the containing deployed class or jar is demonstrably hollow/stub-like.

## Probe-only absence candidates

| APKs | Kind | Classification | Contract | References |
|---:|---|---|---|---:|
| 10 | `existence_probe` | `C8-candidate` | `Ljava/lang/Module;` | 10 |
| 10 | `existence_probe` | `C8-candidate` | `Ljava/lang/module/ModuleDescriptor;` | 10 |
| 9 | `existence_probe` | `C8-candidate` | `Lsun/misc/JavaLangAccess;` | 17 |
| 9 | `existence_probe` | `C8-candidate` | `Lsun/misc/SharedSecrets;` | 10 |
| 9 | `existence_probe` | `C8-candidate` | `Lcom/google/android/gms/chimera/container/DynamiteLoaderImpl;` | 9 |
| 9 | `existence_probe` | `C8-candidate` | `Lcom/google/android/gms/dynamiteloader/DynamiteLoaderV2;` | 9 |
| 9 | `existence_probe` | `C8-candidate` | `Lorg/chromium/support_lib_glue/SupportLibReflectionUtil;` | 9 |
| 8 | `existence_probe` | `C8-candidate` | `Lkotlin/reflect/jvm/internal/ReflectionFactoryImpl;` | 8 |
| 7 | `existence_probe` | `C8-candidate` | `Lorg/robolectric/Robolectric;` | 23 |
| 7 | `existence_probe` | `C8-candidate` | `Lorg/eclipse/jetty/alpn/ALPN;` | 7 |
| 6 | `existence_probe` | `C8-candidate` | `Lcom/google/protobuf/UnknownFieldSetSchema;` | 15 |
| 6 | `existence_probe` | `C8-candidate` | `Lcom/google/android/instantapps/supervisor/InstantAppsRuntime;` | 8 |
| 6 | `existence_probe` | `C8-candidate` | `Lcom/google/protobuf/DescriptorMessageInfoFactory;` | 8 |
| 6 | `existence_probe` | `C8-candidate` | `Landroidx/media3/datasource/rtmp/RtmpDataSource;` | 6 |
| 6 | `existence_probe` | `C8-candidate` | `Lcom/android/billingclient/ktx/BuildConfig;` | 6 |
| 5 | `existence_probe` | `C8-candidate` | `Lcom/google/protobuf/ExtensionRegistry;` | 7 |
| 5 | `existence_probe` | `C8-candidate` | `Landroidx/datastore/preferences/protobuf/UnknownFieldSetSchema;` | 6 |
| 5 | `existence_probe` | `C8-candidate` | `Landroidx/datastore/preferences/protobuf/DescriptorMessageInfoFactory;` | 5 |
| 5 | `existence_probe` | `C8-candidate` | `Landroidx/datastore/preferences/protobuf/ExtensionRegistry;` | 5 |
| 5 | `existence_probe` | `C8-candidate` | `Landroidx/datastore/preferences/protobuf/ExtensionSchemaFull;` | 5 |
| 5 | `existence_probe` | `C8-candidate` | `Landroidx/datastore/preferences/protobuf/MapFieldSchemaFull;` | 5 |
| 5 | `existence_probe` | `C8-candidate` | `Landroidx/datastore/preferences/protobuf/NewInstanceSchemaFull;` | 5 |
| 5 | `existence_probe` | `C8-candidate` | `Landroidx/media3/decoder/flac/FlacExtractor;` | 5 |
| 5 | `existence_probe` | `C8-candidate` | `Landroidx/media3/decoder/flac/FlacLibrary;` | 5 |
| 5 | `existence_probe` | `C8-candidate` | `Landroidx/media3/decoder/midi/MidiExtractor;` | 5 |
| 5 | `existence_probe` | `C8-candidate` | `Lcom/google/crypto/tink/shaded/protobuf/ExtensionRegistry;` | 5 |
| 5 | `existence_probe` | `C8-candidate` | `Lcom/google/crypto/tink/shaded/protobuf/UnknownFieldSetSchema;` | 5 |
| 5 | `existence_probe` | `C8-candidate` | `Lcom/google/protobuf/GeneratedMessageV3;` | 5 |
| 5 | `existence_probe` | `C8-candidate` | `Lcom/google/protobuf/MapFieldSchemaFull;` | 5 |
| 5 | `existence_probe` | `C8-candidate` | `Lcom/google/protobuf/NewInstanceSchemaFull;` | 5 |
| 5 | `existence_probe` | `C8-candidate` | `Lkotlinx/coroutines/test/internal/TestMainDispatcherFactory;` | 5 |
| 4 | `existence_probe` | `C8-candidate` | `Landroid/app/MiuiNotification;` | 4 |
| 4 | `existence_probe` | `C8-candidate` | `Landroidx/sharetarget/ShortcutInfoCompatSaverImpl;` | 4 |
| 4 | `existence_probe` | `C8-candidate` | `Lcom/facebook/common/zopt/ZOpt;` | 4 |
| 4 | `existence_probe` | `C8-candidate` | `Lcom/facebook/imagepipeline/nativecode/NativeCodeInitializer;` | 4 |
| 4 | `existence_probe` | `C8-candidate` | `Lcom/google/crypto/tink/shaded/protobuf/DescriptorMessageInfoFactory;` | 4 |
| 4 | `existence_probe` | `C8-candidate` | `Lcom/google/crypto/tink/shaded/protobuf/GeneratedMessage;` | 4 |
| 4 | `existence_probe` | `C8-candidate` | `Lcom/google/protobuf/ExtensionSchemaFull;` | 4 |
| 4 | `existence_probe` | `C8-candidate` | `Lorg/apache/harmony/xnet/provider/jsse/OpenSSLSocketImpl;` | 4 |
| 4 | `existence_probe` | `C8-candidate` | `Lorg/junit/Test;` | 4 |

These require the strict C8 gate: all supplied/plugin DEX must remain call-free for the type, and runtime evidence must show which presence branch is faithful.

## Hollow-body heuristic candidates

| APKs | Kind | Classification | Contract | References |
|---:|---|---|---|---:|
| 10 | `hollow_method` | `C9-candidate` | `Ljava/io/InputStream;->close()V` | 4189 |
| 10 | `hollow_method` | `C9-candidate` | `Ljava/io/OutputStream;->close()V` | 2606 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/graphics/drawable/Drawable;->getIntrinsicHeight()I` | 1831 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/graphics/drawable/Drawable;->getIntrinsicWidth()I` | 1828 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/animation/Animator;->cancel()V` | 1804 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/animation/Animator;->start()V` | 1446 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/view/View;->onDraw(Landroid/graphics/Canvas;)V` | 669 |
| 10 | `hollow_method` | `C9-candidate` | `Ljava/io/OutputStream;->flush()V` | 658 |
| 10 | `hollow_method` | `C9-candidate` | `Ljava/io/InputStream;->available()I` | 514 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/animation/AnimatorListenerAdapter;->onAnimationStart(Landroid/animation/Animator;)V` | 447 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/view/View;->onDetachedFromWindow()V` | 405 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/view/View;->onSizeChanged(IIII)V` | 361 |
| 10 | `hollow_method` | `C9-candidate` | `Ljava/io/InputStream;->markSupported()Z` | 180 |
| 10 | `hollow_method` | `C9-candidate` | `Ljava/net/HttpURLConnection;->getErrorStream()Ljava/io/InputStream;` | 148 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/app/Service;->onCreate()V` | 138 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/app/Service;->onDestroy()V` | 132 |
| 10 | `hollow_method` | `C9-candidate` | `Ljava/net/InetAddress;->getHostAddress()Ljava/lang/String;` | 117 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/app/Dialog;->onCreate(Landroid/os/Bundle;)V` | 74 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/app/Activity;->onActivityResult(IILandroid/content/Intent;)V` | 73 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/view/WindowInsets$Type;->ime()I` | 50 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/view/Window;->setDecorFitsSystemWindows(Z)V` | 41 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/view/WindowInsets$Type;->navigationBars()I` | 39 |
| 10 | `hollow_method` | `C9-candidate` | `Ljava/net/InetAddress;->getAddress()[B` | 38 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/view/WindowInsets$Type;->displayCutout()I` | 34 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/view/View;->onCheckIsTextEditor()Z` | 32 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/view/Window;->getInsetsController()Landroid/view/WindowInsetsController;` | 29 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/app/Activity;->onNewIntent(Landroid/content/Intent;)V` | 27 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/view/WindowInsets$Type;->systemGestures()I` | 26 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/view/WindowInsets$Type;->statusBars()I` | 24 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/view/WindowInsets$Type;->captionBar()I` | 18 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/view/WindowInsets$Type;->mandatorySystemGestures()I` | 17 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/view/WindowInsets$Type;->tappableElement()I` | 17 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/app/Activity;->onUserLeaveHint()V` | 16 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/app/Application;->onCreate()V` | 16 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/app/Service;->onStart(Landroid/content/Intent;I)V` | 16 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/os/Binder;->isBinderAlive()Z` | 15 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/app/Activity;->onRequestPermissionsResult(I[Ljava/lang/String;[I)V` | 13 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/app/Activity;->onCreateContextMenu(Landroid/view/ContextMenu;Landroid/view/View;Landroid/view/ContextMenu$ContextMenuInfo;)V` | 12 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/app/Activity;->onCreateView(Ljava/lang/String;Landroid/content/Context;Landroid/util/AttributeSet;)Landroid/view/View;` | 10 |
| 10 | `hollow_method` | `C9-candidate` | `Landroid/view/View$AccessibilityDelegate;->getAccessibilityNodeProvider(Landroid/view/View;)Landroid/view/accessibility/AccessibilityNodeProvider;` | 10 |

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
