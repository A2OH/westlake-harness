/*
 * tone <mode> <rate> <seconds> [freq]
 *
 * Plays a sine tone so the board's audio path can be checked for pitch: record it with oh_record
 * and measure the frequency that comes out. mode "sl" drives Westlake's Android OpenSL ES adapter
 * with Android's 4-byte ABI, exactly as an app's audio engine does (engine, output mix, player
 * on an Android simple buffer queue, stereo 16-bit PCM); mode "oh" plays the same tone through
 * OH's own OHAudio renderer as the control.
 *
 * The AAudio modes open libaaudio.so and look its entry points up by handle, as Oboe does, so with
 * the shim preloaded they reach Westlake's AAudio over OHAudio:
 * - "aa": a data callback of OH's size, stereo float;
 * - "aa16": a data callback of exactly 192 frames, stereo 16-bit, the size cut and joined to OH's;
 * - "aaw": blocking writes of 256 frames, stereo 16-bit;
 * - "aain": blocking reads from the microphone, mono float, for <seconds>; prints the level.
 */
#include <dlfcn.h>
#include <math.h>
#include <ohaudio/native_audiorenderer.h>
#include <ohaudio/native_audiostreambuilder.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int g_rate;
static double g_freq = 1000.0, g_phase;

static void fill(int16_t *out, int frames)
{
    for (int i = 0; i < frames; i++) {
        int16_t v = (int16_t) (8000.0 * sin(g_phase));
        out[2 * i] = v;
        out[2 * i + 1] = v;
        g_phase += 2.0 * M_PI * g_freq / g_rate;
        if (g_phase > 2.0 * M_PI) g_phase -= 2.0 * M_PI;
    }
}

/* ---- Android OpenSL ES ABI (4-byte SLuint32), as an Android app compiles it ---- */
typedef uint32_t u32;
typedef const struct IID_ { u32 a; uint16_t b, c, d; uint8_t e[6]; } *IID;
typedef const struct ObjV *const *Obj;
typedef const struct EngV *const *Eng;
typedef const struct PlayV *const *Play;
typedef const struct SbqV *const *Sbq;
struct ObjV {
    u32 (*Realize)(Obj, u32);
    u32 (*Resume)(Obj, u32);
    u32 (*GetState)(Obj, u32 *);
    u32 (*GetInterface)(Obj, IID, void *);
    void *rest[6];
};
struct EngV {
    void *led, *vibra;
    u32 (*CreateAudioPlayer)(Eng, Obj *, void *, void *, u32, const IID *, const u32 *);
    void *recorder, *midi, *listener, *group3d;
    u32 (*CreateOutputMix)(Eng, Obj *, u32, const IID *, const u32 *);
};
struct PlayV { u32 (*SetPlayState)(Play, u32); };
struct SbqV {
    u32 (*Enqueue)(Sbq, const void *, u32);
    u32 (*Clear)(Sbq);
    u32 (*GetState)(Sbq, void *);
    u32 (*RegisterCallback)(Sbq, void (*)(Sbq, void *), void *);
};
typedef struct { u32 type; u32 buffers; } LocSbq;
typedef struct { u32 type; Obj mix; } LocMix;
typedef struct { u32 type, channels, rate_mhz, bits, container, mask, endian; } Pcm;
typedef struct { void *loc; void *fmt; } Data;

#define FRAMES 1024
static int16_t g_buf[2][FRAMES * 2];
static int g_next;

static void on_buffer(Sbq q, void *ctx)
{
    (void) ctx;
    fill(g_buf[g_next], FRAMES);
    (*q)->Enqueue(q, g_buf[g_next], sizeof(g_buf[0]));
    g_next ^= 1;
}

static int play_sl(int seconds)
{
    void *shim = dlopen("libwebview_bionic_shim.so", RTLD_NOW | RTLD_GLOBAL);
    if (shim == NULL) { fprintf(stderr, "shim: %s\n", dlerror()); return 1; }
    u32 (*create)(Obj *, u32, const void *, u32, const IID *, const u32 *) = dlsym(shim, "slCreateEngine");
    IID *iid_engine = dlsym(shim, "SL_IID_ENGINE"), *iid_play = dlsym(shim, "SL_IID_PLAY"),
        *iid_sbq = dlsym(shim, "SL_IID_ANDROIDSIMPLEBUFFERQUEUE");
    if (!create || !iid_engine || !iid_play || !iid_sbq) { fprintf(stderr, "symbols missing\n"); return 1; }
    Obj engine, mix, player;
    Eng eng;
    Play play;
    Sbq sbq;
    u32 r = create(&engine, 0, NULL, 0, NULL, NULL);
    r |= (*engine)->Realize(engine, 0);
    r |= (*engine)->GetInterface(engine, *iid_engine, &eng);
    r |= (*eng)->CreateOutputMix(eng, &mix, 0, NULL, NULL);
    r |= (*mix)->Realize(mix, 0);
    if (r) { fprintf(stderr, "engine/mix failed %u\n", r); return 1; }
    LocSbq loc = { 0x800007BD, 2 };
    Pcm pcm = { 2, 2, (u32) g_rate * 1000u, 16, 16, 3, 2 };
    LocMix out = { 4, mix };
    Data src = { &loc, &pcm }, sink = { &out, NULL };
    IID ids[1] = { *iid_sbq };
    u32 req[1] = { 1 };
    r = (*eng)->CreateAudioPlayer(eng, &player, &src, &sink, 1, ids, req);
    if (r) { fprintf(stderr, "CreateAudioPlayer %u\n", r); return 1; }
    r |= (*player)->Realize(player, 0);
    r |= (*player)->GetInterface(player, *iid_play, &play);
    r |= (*player)->GetInterface(player, *iid_sbq, &sbq);
    r |= (*sbq)->RegisterCallback(sbq, on_buffer, NULL);
    if (r) { fprintf(stderr, "player setup failed %u\n", r); return 1; }
    on_buffer(sbq, NULL);
    on_buffer(sbq, NULL);
    (*play)->SetPlayState(play, 3 /* SL_PLAYSTATE_PLAYING */);
    sleep((unsigned) seconds);
    (*play)->SetPlayState(play, 1);
    printf("played %d s of %.0f Hz at %d Hz through the Android OpenSL ES adapter\n", seconds, g_freq, g_rate);
    return 0;
}

/* ---- AAudio, looked up by handle ---- */
typedef struct AAudioStreamStruct AAudioStream;
typedef struct AAudioStreamBuilderStruct AAudioStreamBuilder;
typedef int32_t (*AADataCallback)(AAudioStream *, void *, void *, int32_t);
static struct {
    int32_t (*create_builder)(AAudioStreamBuilder **);
    void (*set_direction)(AAudioStreamBuilder *, int32_t);
    void (*set_rate)(AAudioStreamBuilder *, int32_t);
    void (*set_channels)(AAudioStreamBuilder *, int32_t);
    void (*set_format)(AAudioStreamBuilder *, int32_t);
    void (*set_performance)(AAudioStreamBuilder *, int32_t);
    void (*set_data_callback)(AAudioStreamBuilder *, AADataCallback, void *);
    void (*set_frames_per_callback)(AAudioStreamBuilder *, int32_t);
    int32_t (*open)(AAudioStreamBuilder *, AAudioStream **);
    int32_t (*delete_builder)(AAudioStreamBuilder *);
    int32_t (*start)(AAudioStream *);
    int32_t (*stop)(AAudioStream *);
    int32_t (*close)(AAudioStream *);
    int32_t (*write)(AAudioStream *, const void *, int32_t, int64_t);
    int32_t (*read)(AAudioStream *, void *, int32_t, int64_t);
    int32_t (*rate)(AAudioStream *);
    int32_t (*channels)(AAudioStream *);
    int32_t (*format)(AAudioStream *);
    int32_t (*burst)(AAudioStream *);
    int32_t (*capacity)(AAudioStream *);
    int32_t (*xruns)(AAudioStream *);
    int32_t (*state)(AAudioStream *);
    int64_t (*written)(AAudioStream *);
    int64_t (*read_count)(AAudioStream *);
    int32_t (*timestamp)(AAudioStream *, clockid_t, int64_t *, int64_t *);
    const char *(*text)(int32_t);
} aa;

static int load_aaudio(void)
{
    void *lib = dlopen("libaaudio.so", RTLD_NOW);
    if (lib == NULL) { fprintf(stderr, "libaaudio.so: %s\n", dlerror()); return 1; }
#define AA(field, name) if ((aa.field = (__typeof__(aa.field)) dlsym(lib, name)) == NULL) { \
        fprintf(stderr, "libaaudio.so lacks %s\n", name); return 1; }
    AA(create_builder, "AAudio_createStreamBuilder");
    AA(set_direction, "AAudioStreamBuilder_setDirection");
    AA(set_rate, "AAudioStreamBuilder_setSampleRate");
    AA(set_channels, "AAudioStreamBuilder_setChannelCount");
    AA(set_format, "AAudioStreamBuilder_setFormat");
    AA(set_performance, "AAudioStreamBuilder_setPerformanceMode");
    AA(set_data_callback, "AAudioStreamBuilder_setDataCallback");
    AA(set_frames_per_callback, "AAudioStreamBuilder_setFramesPerDataCallback");
    AA(open, "AAudioStreamBuilder_openStream");
    AA(delete_builder, "AAudioStreamBuilder_delete");
    AA(start, "AAudioStream_requestStart");
    AA(stop, "AAudioStream_requestStop");
    AA(close, "AAudioStream_close");
    AA(write, "AAudioStream_write");
    AA(read, "AAudioStream_read");
    AA(rate, "AAudioStream_getSampleRate");
    AA(channels, "AAudioStream_getChannelCount");
    AA(format, "AAudioStream_getFormat");
    AA(burst, "AAudioStream_getFramesPerBurst");
    AA(capacity, "AAudioStream_getBufferCapacityInFrames");
    AA(xruns, "AAudioStream_getXRunCount");
    AA(state, "AAudioStream_getState");
    AA(written, "AAudioStream_getFramesWritten");
    AA(read_count, "AAudioStream_getFramesRead");
    AA(timestamp, "AAudioStream_getTimestamp");
    AA(text, "AAudio_convertResultToText");
#undef AA
    return 0;
}

static int g_float, g_per, g_wrong_sizes, g_callbacks;

static int32_t on_aaudio(AAudioStream *s, void *u, void *data, int32_t frames)
{
    (void) s; (void) u;
    g_callbacks++;
    if (g_per > 0 && frames != g_per) g_wrong_sizes++;
    if (g_float) {
        float *out = data;
        for (int i = 0; i < frames; i++) {
            float v = (float) (8000.0 / 32768.0 * sin(g_phase));
            out[2 * i] = v;
            out[2 * i + 1] = v;
            g_phase += 2.0 * M_PI * g_freq / g_rate;
            if (g_phase > 2.0 * M_PI) g_phase -= 2.0 * M_PI;
        }
    } else {
        fill(data, frames);
    }
    return 0;
}

static void describe(AAudioStream *s, const char *what)
{
    int64_t position = 0, time = 0;
    int32_t ts = aa.timestamp(s, CLOCK_MONOTONIC, &position, &time);
    printf("%s: %d Hz, %d channels, format %d, burst %d, capacity %d, state %d, xruns %d, written %lld, "
           "read %lld, timestamp %s (position %lld)\n", what, aa.rate(s), aa.channels(s), aa.format(s),
           aa.burst(s), aa.capacity(s), aa.state(s), aa.xruns(s), (long long) aa.written(s),
           (long long) aa.read_count(s), aa.text(ts), (long long) position);
}

/* mode: "aa", "aa16", "aaw" or "aain". */
static int run_aaudio(const char *mode, int seconds)
{
    if (load_aaudio() != 0) return 1;
    int input = strcmp(mode, "aain") == 0, blocking = input || strcmp(mode, "aaw") == 0;
    g_float = input || strcmp(mode, "aa") == 0;
    g_per = strcmp(mode, "aa16") == 0 ? 192 : 0;
    AAudioStreamBuilder *b;
    AAudioStream *s;
    int32_t r = aa.create_builder(&b);
    aa.set_direction(b, input ? 1 : 0);
    aa.set_rate(b, g_rate);
    aa.set_channels(b, input ? 1 : 2);
    aa.set_format(b, g_float ? 2 /* PCM_FLOAT */ : 1 /* PCM_I16 */);
    aa.set_performance(b, 12 /* LOW_LATENCY */);
    if (!blocking) aa.set_data_callback(b, on_aaudio, NULL);
    if (g_per > 0) aa.set_frames_per_callback(b, g_per);
    if (r == 0) r = aa.open(b, &s);
    aa.delete_builder(b);
    if (r != 0) { fprintf(stderr, "openStream: %s\n", aa.text(r)); return 1; }
    describe(s, "opened");
    if ((r = aa.start(s)) != 0) { fprintf(stderr, "requestStart: %s\n", aa.text(r)); return 1; }
    double sum = 0;
    long long samples = 0;
    if (input) {
        float in[480];
        for (int i = 0; i < seconds * 100; i++) {
            int32_t n = aa.read(s, in, 480, 100000000);
            if (n < 0) { fprintf(stderr, "read: %s\n", aa.text(n)); break; }
            for (int k = 0; k < n; k++) sum += (double) in[k] * in[k];
            samples += n;
        }
    } else if (blocking) {
        int16_t out[256 * 2];
        for (long long frames = 0; frames < (long long) seconds * g_rate;) {
            fill(out, 256);
            int32_t n = aa.write(s, out, 256, 100000000);
            if (n < 0) { fprintf(stderr, "write: %s\n", aa.text(n)); break; }
            frames += n;
        }
    } else {
        sleep((unsigned) seconds);
    }
    describe(s, "playing");
    aa.stop(s);
    aa.close(s);
    if (input) {
        printf("read %lld frames in %d s through AAudio, RMS %.1f (16-bit scale)\n", samples, seconds,
               samples > 0 ? sqrt(sum / samples) * 32768.0 : 0.0);
    } else {
        printf("played %d s of %.0f Hz at %d Hz through AAudio (%s): %d callbacks, %d of the wrong size\n",
               seconds, g_freq, g_rate, mode, g_callbacks, g_wrong_sizes);
    }
    return 0;
}

static int32_t on_write(OH_AudioRenderer *r, void *u, void *buf, int32_t len)
{
    (void) r; (void) u;
    fill((int16_t *) buf, len / 4);
    return 0;
}

static int play_oh(int seconds)
{
    OH_AudioStreamBuilder *b;
    OH_AudioRenderer *r;
    OH_AudioRenderer_Callbacks cb = { on_write, NULL, NULL, NULL };
    OH_AudioStreamBuilder_Create(&b, AUDIOSTREAM_TYPE_RENDERER);
    OH_AudioStreamBuilder_SetSamplingRate(b, g_rate);
    OH_AudioStreamBuilder_SetChannelCount(b, 2);
    OH_AudioStreamBuilder_SetSampleFormat(b, AUDIOSTREAM_SAMPLE_S16LE);
    OH_AudioStreamBuilder_SetRendererCallback(b, cb, NULL);
    if (OH_AudioStreamBuilder_GenerateRenderer(b, &r) != AUDIOSTREAM_SUCCESS) { fprintf(stderr, "renderer failed\n"); return 1; }
    OH_AudioRenderer_Start(r);
    sleep((unsigned) seconds);
    OH_AudioRenderer_Stop(r);
    OH_AudioRenderer_Release(r);
    printf("played %d s of %.0f Hz at %d Hz through OHAudio\n", seconds, g_freq, g_rate);
    return 0;
}

int main(int argc, char **argv)
{
    if (argc < 4) { fprintf(stderr, "usage: tone <sl|oh|aa|aa16|aaw|aain> <rate> <seconds> [freq]\n"); return 2; }
    g_rate = atoi(argv[2]);
    if (argc > 4) g_freq = atof(argv[4]);
    if (strncmp(argv[1], "aa", 2) == 0) return run_aaudio(argv[1], atoi(argv[3]));
    return strcmp(argv[1], "sl") == 0 ? play_sl(atoi(argv[3])) : play_oh(atoi(argv[3]));
}
