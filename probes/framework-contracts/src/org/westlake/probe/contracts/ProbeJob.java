package org.westlake.probe.contracts;

import android.app.job.JobParameters;
import android.app.job.JobService;

import java.util.concurrent.CountDownLatch;

/** Scheduled by the JobScheduler check, which waits for it to run. */
public class ProbeJob extends JobService {
    static final CountDownLatch RAN = new CountDownLatch(1);

    @Override
    public boolean onStartJob(JobParameters params) {
        RAN.countDown();
        return false;
    }

    @Override
    public boolean onStopJob(JobParameters params) {
        return false;
    }
}
