# Westlake API-gap benchmark

Generated: `2026-08-22T03:45:32+00:00`  
Runtime: `sha256:acd4b44a4ef5cae0cc9485c6a16658f3f2609f4daf9391140cd19dfe8281c335`  
APKs scanned: **3**  
Unique static gap candidates: **664**  
Directly absent classes/members: **231**  
Unresolved `CU` native/reflection records (not counted as gaps): **1947**

> This is a static compatibility overview, not a claim that every finding is reached at runtime. Computed reflection, downloaded code, dynamically registered JNI, and semantic differences require runtime probes.

## Corpus

Source: [Similarweb global Google Play top-free third-party benchmark](https://www.similarweb.com/top-apps/google/top-free/), observed `2026-08-20`.

Selection rule: First ten ranked third-party installable applications in chart order. Excluded: Google platform applications/services and OEM/system applications.

Exact downloaded versions, container hashes, split counts, and retrieval tooling are recorded in the supplied download lock.

## Per-APK overview

| Rank | App | Package | Version | DEX classes | Platform types | Methods | Fields | Candidates | Unresolved |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 4 | Amazon Shopping | `com.amazon.mShop.android.shopping` | 32.12.4.100 | 70221 | 2389 | 13343 | 1832 | 461 | 453 |
| 8 | Discord | `com.discord` | 341.13 - Stable | 17535 | 1467 | 8076 | 771 | 306 | 680 |
| 10 | Yahoo Mail | `com.yahoo.mobile.client.android.mail` | 26.32.1 | 71528 | 1985 | 10614 | 1245 | 380 | 814 |

## Native evidence funnel

DEX native declarations: **6516** records / **5402** unique contracts.

Retained native `CU`: **1920** records / **1083** unique contracts. Retained reflection `CU`: **27** records / **20** unique contracts.

| State | Records | Unique contracts |
|---|---:|---:|
| `apk-export-resolved` | 4596 | 4319 |
| `library-scoped-registration-unresolved` | 157 | 111 |
| `registration-source-unattributed` | 27 | 27 |
| `static-registration-table-candidate` | 1736 | 968 |

### Native ABI coverage

| App | Target ABI | Packaged ABIs | Status | Native declarations | Resolved | Unresolved | Candidates |
|---|---|---|---|---:|---:|---:|---:|
| Amazon Shopping | `armeabi-v7a` | `armeabi-v7a` | `target-abi-available` | 3755 | 3312 | 443 | 0 |
| Discord | `armeabi-v7a` | `armeabi-v7a` | `target-abi-available` | 1340 | 665 | 675 | 0 |
| Yahoo Mail | `armeabi-v7a` | `armeabi-v7a` | `target-abi-available` | 1421 | 619 | 802 | 0 |

### Per-app native evidence states

| App | APK export | Runtime export | Static table | Load-scoped | Unattributed | ABI unavailable |
|---|---:|---:|---:|---:|---:|---:|
| Amazon Shopping | 3312 | 0 | 403 | 13 | 27 | 0 |
| Discord | 665 | 0 | 602 | 73 | 0 | 0 |
| Yahoo Mail | 619 | 0 | 731 | 71 | 0 | 0 |

## Finding counts

- `existence_probe`: 189
- `hollow_method`: 592
- `missing_class`: 78
- `missing_field`: 36
- `missing_method`: 252

## Directly absent classes and members

| APKs | Kind | Classification | Contract | References |
|---:|---|---|---|---:|
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager;->getActiveNetworkInfo()Landroid/net/NetworkInfo;` | 91 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkCapabilities;->hasTransport(I)Z` | 90 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkInfo;->isConnected()Z` | 69 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkInfo;->getType()I` | 48 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkCapabilities;->hasCapability(I)Z` | 46 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager;->getNetworkCapabilities(Landroid/net/Network;)Landroid/net/NetworkCapabilities;` | 45 |
| 3 | `missing_field` | `C9-candidate` | `Landroid/provider/MediaStore$Images$Media;->EXTERNAL_CONTENT_URI:Landroid/net/Uri;` | 40 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager;->getActiveNetwork()Landroid/net/Network;` | 39 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/TrafficStats;->clearThreadStatsTag()V` | 38 |
| 3 | `missing_field` | `C9-candidate` | `Landroid/provider/MediaStore$Video$Media;->EXTERNAL_CONTENT_URI:Landroid/net/Uri;` | 22 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/graphics/ColorMatrix;-><init>([F)V` | 20 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager;->unregisterNetworkCallback(Landroid/net/ConnectivityManager$NetworkCallback;)V` | 20 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager;->registerDefaultNetworkCallback(Landroid/net/ConnectivityManager$NetworkCallback;)V` | 19 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkInfo;->getSubtype()I` | 18 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkRequest$Builder;->build()Landroid/net/NetworkRequest;` | 14 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkInfo;->isConnectedOrConnecting()Z` | 13 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkCapabilities;->getLinkDownstreamBandwidthKbps()I` | 12 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/provider/MediaStore$Files;->getContentUri(Ljava/lang/String;)Landroid/net/Uri;` | 12 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkRequest$Builder;->addCapability(I)Landroid/net/NetworkRequest$Builder;` | 11 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager;->registerNetworkCallback(Landroid/net/NetworkRequest;Landroid/net/ConnectivityManager$NetworkCallback;)V` | 10 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkRequest$Builder;->addTransportType(I)Landroid/net/NetworkRequest$Builder;` | 10 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager;->getAllNetworks()[Landroid/net/Network;` | 8 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager;->isActiveNetworkMetered()Z` | 8 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiManager;->getConnectionInfo()Landroid/net/wifi/WifiInfo;` | 8 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/graphics/ColorMatrix;->setSaturation(F)V` | 7 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager;->getNetworkInfo(Landroid/net/Network;)Landroid/net/NetworkInfo;` | 7 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/graphics/ColorMatrix;->setScale(FFFF)V` | 6 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getIpAddress()I` | 6 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getSSID()Ljava/lang/String;` | 6 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiManager;->isWifiEnabled()Z` | 6 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getBSSID()Ljava/lang/String;` | 5 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getLinkSpeed()I` | 5 |
| 3 | `missing_field` | `C9-candidate` | `Landroid/provider/MediaStore$Images$Media;->INTERNAL_CONTENT_URI:Landroid/net/Uri;` | 5 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/provider/MediaStore;->getPickImagesMaxLimit()I` | 5 |
| 3 | `missing_method` | `C1/C4` | `Landroid/view/View;->setFrameContentVelocity(F)V` | 5 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkCapabilities;->getLinkUpstreamBandwidthKbps()I` | 4 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getFrequency()I` | 4 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getRssi()I` | 4 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/graphics/ColorMatrix;->preConcat(Landroid/graphics/ColorMatrix;)V` | 3 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkInfo;->isRoaming()Z` | 3 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getRxLinkSpeedMbps()I` | 3 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getTxLinkSpeedMbps()I` | 3 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiManager;->calculateSignalLevel(II)I` | 3 |
| 3 | `missing_method` | `C9-candidate` | `Landroid/provider/MediaStore$Images$Thumbnails;->queryMiniThumbnail(Landroid/content/ContentResolver;JI[Ljava/lang/String;)Landroid/database/Cursor;` | 3 |
| 3 | `missing_class` | `C1/C4` | `Landroid/net/ssl/SSLSockets;` | 0 |
| 3 | `missing_class` | `C1/C4` | `Landroid/os/ext/SdkExtensions;` | 0 |
| 2 | `missing_method` | `C9-candidate` | `Landroid/graphics/ColorMatrix;->set([F)V` | 8 |
| 2 | `missing_field` | `C9-candidate` | `Landroid/provider/MediaStore$Audio$Media;->EXTERNAL_CONTENT_URI:Landroid/net/Uri;` | 8 |
| 2 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager$NetworkCallback;->onAvailable(Landroid/net/Network;)V` | 5 |
| 2 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiManager;->createWifiLock(ILjava/lang/String;)Landroid/net/wifi/WifiManager$WifiLock;` | 5 |
| 2 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager$NetworkCallback;->onLost(Landroid/net/Network;)V` | 4 |
| 2 | `missing_method` | `C9-candidate` | `Landroid/provider/MediaStore$Audio$Media;->getContentUri(Ljava/lang/String;)Landroid/net/Uri;` | 4 |
| 2 | `missing_method` | `C9-candidate` | `Landroid/provider/MediaStore$Images$Media;->getContentUri(Ljava/lang/String;)Landroid/net/Uri;` | 4 |
| 2 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager$NetworkCallback;->onUnavailable()V` | 3 |
| 2 | `missing_method` | `C9-candidate` | `Landroid/net/LinkProperties;->getLinkAddresses()Ljava/util/List;` | 3 |
| 2 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkInfo;->getDetailedState()Landroid/net/NetworkInfo$DetailedState;` | 3 |
| 2 | `missing_method` | `C9-candidate` | `Landroid/provider/MediaStore$Video$Media;->getContentUri(Ljava/lang/String;)Landroid/net/Uri;` | 3 |
| 2 | `missing_method` | `C1/C4` | `Landroid/text/StaticLayout$Builder;->setUseBoundsForWidth(Z)Landroid/text/StaticLayout$Builder;` | 3 |
| 2 | `missing_method` | `C1/C4` | `Landroid/app/Notification$Builder;->setShortCriticalText(Ljava/lang/String;)Landroid/app/Notification$Builder;` | 2 |
| 2 | `missing_method` | `C1/C4` | `Landroid/app/job/JobInfo$Builder;->setTraceTag(Ljava/lang/String;)Landroid/app/job/JobInfo$Builder;` | 2 |
| 2 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager$NetworkCallback;->onCapabilitiesChanged(Landroid/net/Network;Landroid/net/NetworkCapabilities;)V` | 2 |
| 2 | `missing_method` | `C9-candidate` | `Landroid/net/ConnectivityManager;->getLinkProperties(Landroid/net/Network;)Landroid/net/LinkProperties;` | 2 |
| 2 | `missing_method` | `C9-candidate` | `Landroid/net/LinkAddress;->getAddress()Ljava/net/InetAddress;` | 2 |
| 2 | `missing_field` | `C9-candidate` | `Landroid/net/NetworkInfo$DetailedState;->CONNECTED:Landroid/net/NetworkInfo$DetailedState;` | 2 |
| 2 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkRequest$Builder;->removeCapability(I)Landroid/net/NetworkRequest$Builder;` | 2 |
| 2 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkRequest;->getCapabilities()[I` | 2 |
| 2 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkRequest;->getTransportTypes()[I` | 2 |
| 2 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkRequest;->hasCapability(I)Z` | 2 |
| 2 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkRequest;->hasTransport(I)Z` | 2 |
| 2 | `missing_method` | `C9-candidate` | `Landroid/net/wifi/WifiInfo;->getNetworkId()I` | 2 |
| 2 | `missing_method` | `C9-candidate` | `Landroid/provider/MediaStore$Images$Media;->getBitmap(Landroid/content/ContentResolver;Landroid/net/Uri;)Landroid/graphics/Bitmap;` | 2 |
| 2 | `missing_field` | `C9-candidate` | `Landroid/provider/MediaStore$Images$Thumbnails;->EXTERNAL_CONTENT_URI:Landroid/net/Uri;` | 2 |
| 2 | `missing_method` | `C9-candidate` | `Landroid/provider/MediaStore$Images$Thumbnails;->getThumbnail(Landroid/content/ContentResolver;JILandroid/graphics/BitmapFactory$Options;)Landroid/graphics/Bitmap;` | 2 |
| 2 | `missing_method` | `C9-candidate` | `Landroid/provider/MediaStore;->openAssetFileDescriptor(Landroid/content/ContentResolver;Landroid/net/Uri;Ljava/lang/String;Landroid/os/CancellationSignal;)Landroid/content/res/AssetFileDescriptor;` | 2 |
| 2 | `missing_method` | `C9-candidate` | `Landroid/provider/MediaStore;->setRequireOriginal(Landroid/net/Uri;)Landroid/net/Uri;` | 2 |
| 2 | `missing_method` | `C1/C4` | `Landroid/view/accessibility/AccessibilityNodeInfo;->getChecked()I` | 2 |
| 2 | `missing_method` | `C1/C4` | `Landroid/view/accessibility/AccessibilityNodeInfo;->getExpandedState()I` | 2 |
| 2 | `missing_method` | `C1/C4` | `Landroid/view/accessibility/AccessibilityNodeInfo;->getSupplementalDescription()Ljava/lang/CharSequence;` | 2 |
| 2 | `missing_method` | `C1/C4` | `Landroid/view/accessibility/AccessibilityNodeInfo;->isFieldRequired()Z` | 2 |
| 2 | `missing_class` | `C1/C4` | `Landroid/adservices/measurement/MeasurementManager;` | 0 |
| 2 | `missing_class` | `C1/C4` | `Landroid/app/Notification$ProgressStyle$Point;` | 0 |
| 2 | `missing_class` | `C1/C4` | `Landroid/app/Notification$ProgressStyle$Segment;` | 0 |
| 2 | `missing_class` | `C1/C4` | `Landroid/app/Notification$ProgressStyle;` | 0 |
| 2 | `missing_class` | `C1/C4` | `Landroid/net/wifi/WifiManager$WifiLock;` | 0 |
| 2 | `missing_class` | `C1/C4` | `Landroid/provider/MediaStore$Downloads;` | 0 |
| 2 | `missing_class` | `C1/C4` | `Landroid/provider/MediaStore$Video$Thumbnails;` | 0 |
| 2 | `missing_class` | `C1/C4` | `Landroid/view/DisplayListCanvas;` | 0 |
| 2 | `missing_class` | `C1/C4` | `Landroid/view/RenderNode;` | 0 |
| 2 | `missing_class` | `C1/C4` | `Landroid/view/ScrollFeedbackProvider;` | 0 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/bluetooth/BluetoothDevice;->getAddress()Ljava/lang/String;` | 16 |
| 1 | `missing_field` | `C9-candidate` | `Landroid/net/wifi/WifiConfiguration;->allowedKeyManagement:Ljava/util/BitSet;` | 16 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkInfo;->getTypeName()Ljava/lang/String;` | 12 |
| 1 | `missing_field` | `C9-candidate` | `Landroid/net/wifi/ScanResult;->capabilities:Ljava/lang/String;` | 11 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/bluetooth/le/ScanFilter$Builder;->build()Landroid/bluetooth/le/ScanFilter;` | 9 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/bluetooth/BluetoothDevice;->getName()Ljava/lang/String;` | 5 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/bluetooth/le/ScanResult;->getDevice()Landroid/bluetooth/BluetoothDevice;` | 5 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/bluetooth/le/ScanResult;->getScanRecord()Landroid/bluetooth/le/ScanRecord;` | 5 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/net/NetworkInfo;->getSubtypeName()Ljava/lang/String;` | 5 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/bluetooth/le/ScanFilter$Builder;->setServiceData(Landroid/os/ParcelUuid;[B)Landroid/bluetooth/le/ScanFilter$Builder;` | 4 |
| 1 | `missing_method` | `C9-candidate` | `Landroid/bluetooth/le/ScanFilter$Builder;->setServiceUuid(Landroid/os/ParcelUuid;)Landroid/bluetooth/le/ScanFilter$Builder;` | 3 |

These contracts are absent from the exact runtime index. `C1/C4` still needs the implementation-exists decision; `C9-candidate` here means the containing deployed class or jar is demonstrably hollow/stub-like.

## Probe-only absence candidates

| APKs | Kind | Classification | Contract | References |
|---:|---|---|---|---:|
| 3 | `existence_probe` | `C8-candidate` | `Lsun/misc/JavaLangAccess;` | 6 |
| 3 | `existence_probe` | `C8-candidate` | `Lsun/misc/SharedSecrets;` | 4 |
| 3 | `existence_probe` | `C8-candidate` | `Landroidx/datastore/preferences/protobuf/DescriptorMessageInfoFactory;` | 3 |
| 3 | `existence_probe` | `C8-candidate` | `Landroidx/datastore/preferences/protobuf/ExtensionRegistry;` | 3 |
| 3 | `existence_probe` | `C8-candidate` | `Landroidx/datastore/preferences/protobuf/ExtensionSchemaFull;` | 3 |
| 3 | `existence_probe` | `C8-candidate` | `Landroidx/datastore/preferences/protobuf/MapFieldSchemaFull;` | 3 |
| 3 | `existence_probe` | `C8-candidate` | `Landroidx/datastore/preferences/protobuf/NewInstanceSchemaFull;` | 3 |
| 3 | `existence_probe` | `C8-candidate` | `Landroidx/datastore/preferences/protobuf/UnknownFieldSetSchema;` | 3 |
| 3 | `existence_probe` | `C8-candidate` | `Lcom/facebook/imagepipeline/nativecode/NativeCodeInitializer;` | 3 |
| 3 | `existence_probe` | `C8-candidate` | `Lcom/google/android/gms/chimera/container/DynamiteLoaderImpl;` | 3 |
| 3 | `existence_probe` | `C8-candidate` | `Lcom/google/android/gms/dynamiteloader/DynamiteLoaderV2;` | 3 |
| 3 | `existence_probe` | `C8-candidate` | `Ljava/lang/Module;` | 3 |
| 3 | `existence_probe` | `C8-candidate` | `Ljava/lang/module/ModuleDescriptor;` | 3 |
| 3 | `existence_probe` | `C8-candidate` | `Lorg/chromium/support_lib_glue/SupportLibReflectionUtil;` | 3 |
| 2 | `existence_probe` | `C8-candidate` | `Lorg/robolectric/Robolectric;` | 5 |
| 2 | `existence_probe` | `C8-candidate` | `Lcom/google/android/instantapps/supervisor/InstantAppsRuntime;` | 3 |
| 2 | `existence_probe` | `C8-candidate` | `Landroidx/datastore/preferences/protobuf/GeneratedMessage;` | 2 |
| 2 | `existence_probe` | `C8-candidate` | `Landroidx/datastore/preferences/protobuf/ListFieldSchemaFull;` | 2 |
| 2 | `existence_probe` | `C8-candidate` | `Landroidx/media3/datasource/rtmp/RtmpDataSource;` | 2 |
| 2 | `existence_probe` | `C8-candidate` | `Landroidx/media3/decoder/flac/FlacExtractor;` | 2 |
| 2 | `existence_probe` | `C8-candidate` | `Landroidx/media3/decoder/flac/FlacLibrary;` | 2 |
| 2 | `existence_probe` | `C8-candidate` | `Landroidx/media3/decoder/midi/MidiExtractor;` | 2 |
| 2 | `existence_probe` | `C8-candidate` | `Landroidx/media3/effect/PreviewingSingleInputVideoGraph$Factory;` | 2 |
| 2 | `existence_probe` | `C8-candidate` | `Lcom/android/billingclient/ktx/BuildConfig;` | 2 |
| 2 | `existence_probe` | `C8-candidate` | `Lcom/google/ccc/abuse/droidguard/DroidGuard;` | 2 |
| 2 | `existence_probe` | `C8-candidate` | `Lcom/google/protobuf/DescriptorMessageInfoFactory;` | 2 |
| 2 | `existence_probe` | `C8-candidate` | `Lcom/google/protobuf/ExtensionSchemaFull;` | 2 |
| 2 | `existence_probe` | `C8-candidate` | `Lcom/google/protobuf/MapFieldSchemaFull;` | 2 |
| 2 | `existence_probe` | `C8-candidate` | `Lcom/google/protobuf/NewInstanceSchemaFull;` | 2 |
| 2 | `existence_probe` | `C8-candidate` | `Lcom/google/protobuf/UnknownFieldSetSchema;` | 2 |
| 2 | `existence_probe` | `C8-candidate` | `Lcom/horcrux/svg/SvgPackage$$ReactModuleInfoProvider;` | 2 |
| 2 | `existence_probe` | `C8-candidate` | `Lcom/reactnativecommunity/clipboard/ClipboardPackage$$ReactModuleInfoProvider;` | 2 |
| 2 | `existence_probe` | `C8-candidate` | `Lcom/swmansion/gesturehandler/RNGestureHandlerPackage$$ReactModuleInfoProvider;` | 2 |
| 2 | `existence_probe` | `C8-candidate` | `Lorg/eclipse/jetty/alpn/ALPN;` | 2 |
| 2 | `existence_probe` | `C8-candidate` | `Lorg/osgi/framework/BundleEvent;` | 2 |
| 1 | `existence_probe` | `C8-candidate` | `Landroidx/window/extensions/layout/DisplayFoldFeature;` | 2 |
| 1 | `existence_probe` | `C8-candidate` | `Landroidx/window/extensions/layout/SupportedWindowFeatures;` | 2 |
| 1 | `existence_probe` | `C8-candidate` | `Lcom/google/android/gms/ads/doubleclick/PublisherAdRequest;` | 2 |
| 1 | `existence_probe` | `C8-candidate` | `Lcom/google/android/gms/tagmanager/TagManagerService;` | 2 |
| 1 | `existence_probe` | `C8-candidate` | `Lcom/google/protobuf/BlazeGeneratedExtensionRegistryLiteLoader;` | 2 |

These require the strict C8 gate: all supplied/plugin DEX must remain call-free for the type, and runtime evidence must show which presence branch is faithful.

## Hollow-body heuristic candidates

| APKs | Kind | Classification | Contract | References |
|---:|---|---|---|---:|
| 3 | `hollow_method` | `C9-candidate` | `Ljava/io/InputStream;->close()V` | 958 |
| 3 | `hollow_method` | `C9-candidate` | `Ljava/io/OutputStream;->close()V` | 422 |
| 3 | `hollow_method` | `C9-candidate` | `Landroid/graphics/drawable/Drawable;->getIntrinsicWidth()I` | 181 |
| 3 | `hollow_method` | `C9-candidate` | `Landroid/graphics/drawable/Drawable;->getIntrinsicHeight()I` | 175 |
| 3 | `hollow_method` | `C9-candidate` | `Landroid/view/View;->onDetachedFromWindow()V` | 144 |
| 3 | `hollow_method` | `C9-candidate` | `Ljava/io/ByteArrayOutputStream;->close()V` | 140 |
| 3 | `hollow_method` | `C9-candidate` | `Ljava/io/OutputStream;->flush()V` | 134 |
| 3 | `hollow_method` | `C9-candidate` | `Ljava/io/InputStream;->available()I` | 128 |
| 3 | `hollow_method` | `C9-candidate` | `Ljava/lang/Object;->finalize()V` | 108 |
| 3 | `hollow_method` | `C9-candidate` | `Landroid/graphics/drawable/Drawable;->isStateful()Z` | 105 |
| 3 | `hollow_method` | `C9-candidate` | `Landroid/view/View;->isInEditMode()Z` | 101 |
| 3 | `hollow_method` | `C9-candidate` | `Landroid/view/View;->onDraw(Landroid/graphics/Canvas;)V` | 93 |
| 3 | `hollow_method` | `C9-candidate` | `Landroid/graphics/drawable/Drawable;->setTintList(Landroid/content/res/ColorStateList;)V` | 76 |
| 3 | `hollow_method` | `C9-candidate` | `Ljava/io/InputStream;->markSupported()Z` | 70 |
| 3 | `hollow_method` | `C9-candidate` | `Ljava/net/HttpURLConnection;->getErrorStream()Ljava/io/InputStream;` | 63 |
| 3 | `hollow_method` | `C9-candidate` | `Ljava/net/URLConnection;->getHeaderField(Ljava/lang/String;)Ljava/lang/String;` | 63 |
| 3 | `hollow_method` | `C9-candidate` | `Landroid/graphics/drawable/Drawable;->getConstantState()Landroid/graphics/drawable/Drawable$ConstantState;` | 58 |
| 3 | `hollow_method` | `C9-candidate` | `Landroid/view/View;->getBaseline()I` | 56 |
| 3 | `hollow_method` | `C9-candidate` | `Landroid/animation/Animator;->cancel()V` | 40 |
| 3 | `hollow_method` | `C9-candidate` | `Landroid/view/View;->onConfigurationChanged(Landroid/content/res/Configuration;)V` | 38 |
| 3 | `hollow_method` | `C9-candidate` | `Landroid/graphics/drawable/Drawable;->jumpToCurrentState()V` | 36 |
| 3 | `hollow_method` | `C9-candidate` | `Landroid/view/View;->onSizeChanged(IIII)V` | 36 |
| 3 | `hollow_method` | `C9-candidate` | `Landroid/view/View;->onFinishInflate()V` | 33 |
| 3 | `hollow_method` | `C9-candidate` | `Landroid/animation/Animator;->start()V` | 30 |
| 3 | `hollow_method` | `C9-candidate` | `Landroid/graphics/drawable/Drawable;->onBoundsChange(Landroid/graphics/Rect;)V` | 30 |
| 3 | `hollow_method` | `C9-candidate` | `Landroid/app/Service;->onCreate()V` | 29 |
| 3 | `hollow_method` | `C9-candidate` | `Landroid/animation/AnimatorListenerAdapter;->onAnimationEnd(Landroid/animation/Animator;)V` | 27 |
| 3 | `hollow_method` | `C9-candidate` | `Landroid/graphics/drawable/Drawable;->setHotspot(FF)V` | 27 |
| 3 | `hollow_method` | `C9-candidate` | `Landroid/net/TrafficStats;->setThreadStatsTag(I)V` | 27 |
| 3 | `hollow_method` | `C9-candidate` | `Landroid/webkit/WebViewClient;->onPageFinished(Landroid/webkit/WebView;Ljava/lang/String;)V` | 27 |
| 3 | `hollow_method` | `C9-candidate` | `Ljava/net/InetAddress;->getHostAddress()Ljava/lang/String;` | 26 |
| 3 | `hollow_method` | `C9-candidate` | `Landroid/app/Activity;->onActivityResult(IILandroid/content/Intent;)V` | 25 |
| 3 | `hollow_method` | `C9-candidate` | `Landroid/app/Service;->onDestroy()V` | 23 |
| 3 | `hollow_method` | `C9-candidate` | `Landroid/content/Context;->isRestricted()Z` | 22 |
| 3 | `hollow_method` | `C9-candidate` | `Landroid/view/View;->onLayout(ZIIII)V` | 22 |
| 3 | `hollow_method` | `C9-candidate` | `Landroid/view/View;->onVisibilityChanged(Landroid/view/View;I)V` | 21 |
| 3 | `hollow_method` | `C9-candidate` | `Landroid/webkit/WebViewClient;->onPageStarted(Landroid/webkit/WebView;Ljava/lang/String;Landroid/graphics/Bitmap;)V` | 19 |
| 3 | `hollow_method` | `C9-candidate` | `Landroid/graphics/Canvas;->isHardwareAccelerated()Z` | 18 |
| 3 | `hollow_method` | `C9-candidate` | `Ljava/io/ByteArrayInputStream;->close()V` | 18 |
| 3 | `hollow_method` | `C9-candidate` | `Landroid/graphics/drawable/Drawable;->setFilterBitmap(Z)V` | 16 |

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
