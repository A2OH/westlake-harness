/*
 * tone <mode> <rate> <seconds> [freq]
 *
 * Plays a sine tone so the board's audio path can be checked for pitch: record it with oh_record
 * and measure the frequency that comes out. mode "sl" drives Westlake's Android OpenSL ES adapter
 * with Android's 4-byte ABI, exactly as an app's audio engine does (engine, output mix, player
 * on an Android simple buffer queue, stereo 16-bit PCM); mode "oh" plays the same tone through
 * OH's own OHAudio renderer as the control.
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
    if (argc < 4) { fprintf(stderr, "usage: tone <sl|oh> <rate> <seconds> [freq]\n"); return 2; }
    g_rate = atoi(argv[2]);
    if (argc > 4) g_freq = atof(argv[4]);
    return strcmp(argv[1], "sl") == 0 ? play_sl(atoi(argv[3])) : play_oh(atoi(argv[3]));
}
