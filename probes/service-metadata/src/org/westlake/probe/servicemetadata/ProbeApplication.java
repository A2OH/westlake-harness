package org.westlake.probe.defaultinterface;

import android.app.Application;
import android.content.ComponentName;
import android.content.pm.PackageManager;
import android.content.pm.ServiceInfo;
import android.os.Bundle;
import android.util.Log;

public final class ProbeApplication extends Application {
    static volatile String result = "application=not-run";

    @Override
    public void onCreate() {
        super.onCreate();
        try {
            ComponentName component = new ComponentName(this, MetadataService.class);
            ServiceInfo info = getPackageManager().getServiceInfo(
                    component, PackageManager.GET_META_DATA);
            Bundle meta = info != null ? info.metaData : null;
            String registrar = meta != null
                    ? meta.getString("org.westlake.probe.REGISTRAR") : null;
            String second = meta != null
                    ? meta.getString("org.westlake.probe.SECOND") : null;
            boolean pass = info != null
                    && MetadataService.class.getName().equals(info.name)
                    && getPackageName().equals(info.packageName)
                    && "org.westlake.probe.ComponentRegistrar".equals(registrar)
                    && "second-value".equals(second)
                    && meta.size() == 2;
            result = "verdict=" + (pass ? "PASS_SERVICE_INFO_METADATA" : "FAIL")
                    + " info=" + (info != null)
                    + " metadata=" + (meta != null ? meta.size() : -1)
                    + " registrar=" + registrar
                    + " second=" + second;
        } catch (Throwable t) {
            result = "verdict=FAIL exception=" + t;
        }
        Log.i("WL-SERVICE-META", result);
        System.err.println("[WL-SERVICE-META] " + result);
    }
}
