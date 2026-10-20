package org.westlake.probe.contracts;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

import java.util.concurrent.CountDownLatch;

/** Found by queryBroadcastReceivers; the svc:alarm check's PendingIntent alarm is sent to it. */
public class ProbeReceiver extends BroadcastReceiver {
    static final String ALARM = "org.westlake.probe.contracts.ALARM";
    static final CountDownLatch ALARMED = new CountDownLatch(1);

    @Override
    public void onReceive(Context context, Intent intent) {
        if (ALARM.equals(intent.getAction())) ALARMED.countDown();
    }
}
