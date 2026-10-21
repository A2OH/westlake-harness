package org.westlake.probe.contracts;

import android.app.job.JobParameters;
import android.app.job.JobService;
import android.app.job.JobWorkItem;
import android.net.Network;
import android.os.SystemClock;

import java.util.concurrent.CountDownLatch;

/**
 * Scheduled by the JobScheduler check, which waits for each of its jobs to run: one at once, one
 * 1.5 s ahead that needs a network, and one given work through enqueue.
 */
public class ProbeJob extends JobService {
    static final int NOW = 4242;
    static final int LATER = 4243;
    static final int WORK = 4244;
    static final CountDownLatch RAN = new CountDownLatch(1);
    static final CountDownLatch LATER_RAN = new CountDownLatch(1);
    static final CountDownLatch WORKED = new CountDownLatch(1);
    static volatile long laterAt;
    static volatile Network laterNetwork;
    static volatile String work;

    @Override
    public boolean onStartJob(JobParameters params) {
        switch (params.getJobId()) {
            case LATER:
                laterAt = SystemClock.elapsedRealtime();
                laterNetwork = params.getNetwork();
                LATER_RAN.countDown();
                return false;
            case WORK:
                // Once no work is left, dequeueWork answers null and the job is done.
                for (JobWorkItem item = params.dequeueWork(); item != null; item = params.dequeueWork()) {
                    work = item.getIntent().getStringExtra("probe");
                    params.completeWork(item);
                }
                WORKED.countDown();
                return false;
            default:
                RAN.countDown();
                return false;
        }
    }

    @Override
    public boolean onStopJob(JobParameters params) {
        return false;
    }
}
