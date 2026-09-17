package org.westlake.probe.defaultinterface;

import android.app.Service;
import android.content.Intent;
import android.os.IBinder;

public final class MetadataService extends Service {
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
