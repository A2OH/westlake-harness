package org.westlake.probe.defaultinterface;

import android.util.Log;

import java.util.Collections;
import java.util.Set;

/** A minimal model of Firebase ComponentContainer's four default methods. */
public final class DispatchProbe {
    private static final String TAG = "WL-DEFAULT-IFACE";
    private static final Key<String> STRING_KEY = new Key<>(String.class);
    private static final String EXPECTED = "crashlytics-present";

    public interface Provider<T> {
        T get();
    }

    public interface Deferred<T> {
        Provider<T> provider();
    }

    public static final class Key<T> {
        final Class<T> type;

        Key(Class<T> type) {
            this.type = type;
        }
    }

    public interface ComponentContainer {
        default <T> T a(Class<T> type) {
            return g(new Key<>(type));
        }

        default <T> Provider<T> b(Class<T> type) {
            return d(new Key<>(type));
        }

        <T> Deferred<T> c(Key<T> key);

        <T> Provider<T> d(Key<T> key);

        default <T> Set<T> e(Key<T> key) {
            return f(key).get();
        }

        <T> Provider<Set<T>> f(Key<T> key);

        default <T> T g(Key<T> key) {
            Provider<T> provider = d(key);
            return provider == null ? null : provider.get();
        }
    }

    public static final class RuntimeContainer implements ComponentContainer {
        @Override
        public <T> Deferred<T> c(Key<T> key) {
            final Provider<T> provider = d(key);
            return () -> provider;
        }

        @Override
        @SuppressWarnings("unchecked")
        public <T> Provider<T> d(Key<T> key) {
            if (key.type != String.class) {
                return null;
            }
            return () -> (T) EXPECTED;
        }

        @Override
        @SuppressWarnings("unchecked")
        public <T> Provider<Set<T>> f(Key<T> key) {
            if (key.type != String.class) {
                return Collections::emptySet;
            }
            return () -> (Set<T>) Collections.singleton(EXPECTED);
        }
    }

    public static String run(String phase) {
        ComponentContainer container = new RuntimeContainer();
        Provider<String> provider = container.b(String.class);
        String fromProvider = provider == null ? null : provider.get();
        String direct = container.a(String.class);
        Set<String> set = container.e(STRING_KEY);
        boolean pass = EXPECTED.equals(fromProvider)
                && EXPECTED.equals(direct)
                && set != null
                && set.contains(EXPECTED);
        String verdict = pass ? "PASS_DEFAULT_AND_ABSTRACT_DISPATCH" : "FAIL_DISPATCH";
        String detail = "[WL-DEFAULT-IFACE] phase=" + phase
                + " verdict=" + verdict
                + " provider=" + fromProvider
                + " direct=" + direct
                + " set=" + set;
        Log.e(TAG, detail);
        System.err.println(detail);
        return detail;
    }

    private DispatchProbe() {}
}
