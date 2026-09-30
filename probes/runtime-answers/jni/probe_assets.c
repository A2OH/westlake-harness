/*
 * The NDK asset path Meta's superpack takes: AAssetManager_open an asset stored uncompressed, then
 * AAsset_openFileDescriptor for the APK's descriptor and the asset's offset, and read it there.
 * Returns "fd ok, <n> bytes match" or where it failed.
 */
#include <android/asset_manager.h>
#include <android/asset_manager_jni.h>
#include <jni.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

JNIEXPORT jstring JNICALL
Java_org_westlake_probe_runtimeanswers_MainActivity_nativeAssetFd(JNIEnv *env, jclass cls, jobject manager,
                                                                   jstring name)
{
    (void) cls;
    char result[160];
    const char *path = (*env)->GetStringUTFChars(env, name, NULL);
    AAssetManager *am = AAssetManager_fromJava(env, manager);
    AAsset *asset = am != NULL ? AAssetManager_open(am, path, AASSET_MODE_UNKNOWN) : NULL;
    if (am == NULL) snprintf(result, sizeof(result), "AAssetManager_fromJava returned null");
    else if (asset == NULL) snprintf(result, sizeof(result), "AAssetManager_open returned null");
    else {
        char via_read[64] = {0}, via_fd[64] = {0};
        int n = AAsset_read(asset, via_read, sizeof(via_read));
        off_t start = 0, length = 0;
        int fd = AAsset_openFileDescriptor(asset, &start, &length);
        if (fd < 0) snprintf(result, sizeof(result), "AAsset_read %d bytes; AAsset_openFileDescriptor = %d", n, fd);
        else {
            ssize_t m = pread(fd, via_fd, n > 0 ? (size_t) n : 0, start);
            snprintf(result, sizeof(result), "fd ok (start %lld, length %lld), %zd bytes %s", (long long) start,
                     (long long) length, m, m == n && memcmp(via_read, via_fd, (size_t) n) == 0 ? "match" : "DIFFER");
            close(fd);
        }
        AAsset_close(asset);
    }
    (*env)->ReleaseStringUTFChars(env, name, path);
    return (*env)->NewStringUTF(env, result);
}
