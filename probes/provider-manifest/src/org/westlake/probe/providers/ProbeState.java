package org.westlake.probe.providers;

final class ProbeState {
    static volatile int mainProviderCreates;
    static volatile int remoteProviderCreates;

    private ProbeState() {}
}
