/*
 * The NDK asset path Meta's superpack takes: AAssetManager_open an asset stored uncompressed, then
 * AAsset_openFileDescriptor for the APK's descriptor and the asset's offset, and read it there.
 * Returns "fd ok, <n> bytes match" or where it failed.
 */
#define _BSD_SOURCE 1  /* funopen, as bionic declares it under __USE_BSD */
#include <android/asset_manager.h>
#include <android/asset_manager_jni.h>
#include <jni.h>
#include <stdio.h>
#include <stdlib.h>
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

/*
 * superpack's decompress_legacy: a Java InputStream wrapped in funopen with only a read function,
 * then fread of a 28-byte header. Returns the first 8 bytes read, in hex, or where it failed.
 * (Framework 73: "131415161718191a", the first 19 bytes lost.)
 */
struct stream_cookie { JNIEnv *env; jobject stream; jmethodID read; jbyteArray buffer; };

static int stream_read(void *cookie, char *out, int size)
{
    struct stream_cookie *c = cookie;
    JNIEnv *env = c->env;
    int n = (*env)->CallIntMethod(env, c->stream, c->read, c->buffer, 0, size > 4096 ? 4096 : size);
    if ((*env)->ExceptionCheck(env) || n < 0) { (*env)->ExceptionClear(env); return n < 0 ? 0 : -1; }
    (*env)->GetByteArrayRegion(env, c->buffer, 0, n, (jbyte *) out);
    return n;
}

static FILE *open_stream(struct stream_cookie *c, JNIEnv *env, jobject stream)
{
    jclass input = (*env)->FindClass(env, "java/io/InputStream");
    c->env = env;
    c->stream = stream;
    c->read = (*env)->GetMethodID(env, input, "read", "([BII)I");
    c->buffer = (*env)->NewByteArray(env, 4096);
    return funopen(c, stream_read, NULL, NULL, NULL);
}

/*
 * mode 0: fread(header, 28, 1) as superpack does; 1: the same on an unbuffered FILE; 2: fgetc x8;
 * 3: fread of 1 byte x8.
 */
JNIEXPORT jstring JNICALL
Java_org_westlake_probe_runtimeanswers_MainActivity_nativeFunopenRead(JNIEnv *env, jclass cls, jobject stream,
                                                                      jint mode)
{
    (void) cls;
    char result[96];
    struct stream_cookie c;
    FILE *file = open_stream(&c, env, stream);
    if (file == NULL) return (*env)->NewStringUTF(env, "funopen returned null");
    unsigned char header[28] = {0};
    size_t got = 0;
    if (mode == 1) setvbuf(file, NULL, _IONBF, 0);
    if (mode <= 1) got = fread(header, 28, 1, file) * 28;
    for (int i = 0; mode == 2 && i < 8; i++) {
        int ch = fgetc(file);
        if (ch == EOF) break;
        header[got++] = (unsigned char) ch;
    }
    for (int i = 0; mode == 3 && i < 8; i++) got += fread(header + got, 1, 1, file);
    fclose(file);
    if (got < 8) snprintf(result, sizeof(result), "read %zu bytes", got);
    else snprintf(result, sizeof(result), "%02x%02x%02x%02x%02x%02x%02x%02x", header[0], header[1], header[2],
                  header[3], header[4], header[5], header[6], header[7]);
    return (*env)->NewStringUTF(env, result);
}
