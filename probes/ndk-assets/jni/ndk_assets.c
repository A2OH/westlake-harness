/*
 * The NDK asset path React Native uses to load its bundle (JSLoader.cpp loadScriptFromAssets):
 * AAssetManager_fromJava, AAssetManager_open(..., AASSET_MODE_STREAMING), AAsset_getLength,
 * AAsset_read. Each step prints one [WL-NDKASSET] line to stderr, so a failure names its step.
 */
#include <android/asset_manager.h>
#include <android/asset_manager_jni.h>
#include <jni.h>
#include <stdio.h>
#include <stdlib.h>

static void check(AAssetManager* manager, const char* name, int mode) {
    AAsset* asset = AAssetManager_open(manager, name, mode);
    fprintf(stderr, "[WL-NDKASSET] open(%s, mode=%d) -> %p\n", name, mode, (void*) asset);
    if (!asset) return;
    off_t length = AAsset_getLength(asset);
    char* buffer = malloc(length > 0 ? (size_t) length : 1);
    off_t total = 0;
    int got;
    while (buffer && total < length && (got = AAsset_read(asset, buffer + total, (size_t) (length - total))) > 0) {
        total += got;
    }
    const void* direct = AAsset_getBuffer(asset);
    fprintf(stderr, "[WL-NDKASSET]   length=%ld read=%ld getBuffer=%p first=%.24s\n",
            (long) length, (long) total, direct, buffer && total ? buffer : "");
    free(buffer);
    AAsset_close(asset);
}

JNIEXPORT void JNICALL Java_org_westlake_probe_ndkassets_MainActivity_probe(
        JNIEnv* env, jclass cls, jobject assets) {
    (void) cls;
    AAssetManager* manager = AAssetManager_fromJava(env, assets);
    fprintf(stderr, "[WL-NDKASSET] fromJava(%p) -> %p\n", (void*) assets, (void*) manager);
    if (!manager) return;
    check(manager, "probe.bundle", AASSET_MODE_STREAMING);
    check(manager, "stored.bundle", AASSET_MODE_STREAMING);
    check(manager, "missing.bundle", AASSET_MODE_STREAMING);
    AAssetDir* dir = AAssetManager_openDir(manager, "");
    const char* entry;
    int n = 0;
    while (dir && (entry = AAssetDir_getNextFileName(dir)) != NULL && n < 8) {
        fprintf(stderr, "[WL-NDKASSET] dir entry %s\n", entry);
        n++;
    }
    if (dir) AAssetDir_close(dir);
    fflush(stderr);
}
