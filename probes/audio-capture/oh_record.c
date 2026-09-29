/*
 * oh_record <out.wav> <seconds> [source]
 *
 * Records what the board plays, so an audio port can be checked by its output rather than by its
 * state logs: a player that reports "playing" and a renderer that accepts writes can still be
 * silent. source 0 (default) is the microphone, which hears the speaker; 2 is OH's playback
 * capture, which records the mixed output digitally but is granted to system apps only.
 * Writes 48 kHz mono 16-bit WAV. Run from hdc shell.
 */
#include <ohaudio/native_audiocapturer.h>
#include <ohaudio/native_audiostreambuilder.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define RATE 48000

static FILE* g_out;
static long g_bytes;

static void on_data(OH_AudioCapturer* capturer, void* user, void* data, int32_t size)
{
    (void) capturer; (void) user;
    if (size > 0 && fwrite(data, 1, (size_t) size, g_out) == (size_t) size) g_bytes += size;
}

static void le32(unsigned char* p, uint32_t v) { p[0] = v; p[1] = v >> 8; p[2] = v >> 16; p[3] = v >> 24; }
static void le16(unsigned char* p, uint16_t v) { p[0] = v; p[1] = v >> 8; }

static void wav_header(FILE* f, uint32_t data_bytes, uint32_t rate)
{
    unsigned char h[44];
    memcpy(h, "RIFF", 4); le32(h + 4, 36 + data_bytes); memcpy(h + 8, "WAVEfmt ", 8);
    le32(h + 16, 16); le16(h + 20, 1); le16(h + 22, 1); le32(h + 24, rate); le32(h + 28, rate * 2);
    le16(h + 32, 2); le16(h + 34, 16); memcpy(h + 36, "data", 4); le32(h + 40, data_bytes);
    fseek(f, 0, SEEK_SET);
    fwrite(h, 1, sizeof(h), f);
}

int main(int argc, char** argv)
{
    OH_AudioStreamBuilder* builder = NULL;
    OH_AudioCapturer* capturer = NULL;
    int seconds, source, rc;
    if (argc < 3) {
        fprintf(stderr, "usage: oh_record <out.wav> <seconds> [source: 0 mic, 2 playback]\n");
        return 2;
    }
    seconds = atoi(argv[2]);
    source = argc > 3 ? atoi(argv[3]) : 0;
    g_out = fopen(argv[1], "wb");
    if (g_out == NULL) { perror("open"); return 1; }
    wav_header(g_out, 0, RATE);
    if ((rc = OH_AudioStreamBuilder_Create(&builder, AUDIOSTREAM_TYPE_CAPTURER)) != AUDIOSTREAM_SUCCESS) {
        fprintf(stderr, "builder create failed %d\n", rc);
        return 1;
    }
    OH_AudioStreamBuilder_SetSamplingRate(builder, RATE);
    OH_AudioStreamBuilder_SetChannelCount(builder, 1);
    OH_AudioStreamBuilder_SetSampleFormat(builder, AUDIOSTREAM_SAMPLE_S16LE);
    OH_AudioStreamBuilder_SetCapturerInfo(builder, (OH_AudioStream_SourceType) source);
    OH_AudioStreamBuilder_SetCapturerReadDataCallback(builder, on_data, NULL);
    if ((rc = OH_AudioStreamBuilder_GenerateCapturer(builder, &capturer)) != AUDIOSTREAM_SUCCESS) {
        fprintf(stderr, "generate capturer failed %d (source %d)\n", rc, source);
        return 1;
    }
    {
        int32_t rate = 0, channels = 0;
        OH_AudioStream_SampleFormat format = AUDIOSTREAM_SAMPLE_S16LE;
        OH_AudioCapturer_GetSamplingRate(capturer, &rate);
        OH_AudioCapturer_GetChannelCount(capturer, &channels);
        OH_AudioCapturer_GetSampleFormat(capturer, &format);
        printf("stream: %d Hz, %d channel(s), format %d\n", (int) rate, (int) channels, (int) format);
    }
    if ((rc = OH_AudioCapturer_Start(capturer)) != AUDIOSTREAM_SUCCESS) {
        fprintf(stderr, "start failed %d\n", rc);
        return 1;
    }
    sleep((unsigned) seconds);
    OH_AudioCapturer_Stop(capturer);
    OH_AudioCapturer_Release(capturer);
    OH_AudioStreamBuilder_Destroy(builder);
    /* Playback capture on this board delivers about five times the rate the stream reports
     * (240800 frames a second at a nominal 48000). The recording matched the source music only at
     * the wall-clock rate, so when the two disagree the header carries the measured rate. */
    {
        uint32_t measured = (uint32_t) (g_bytes / 2 / (seconds > 0 ? seconds : 1));
        uint32_t rate = (measured > RATE * 11 / 10 || measured < RATE * 9 / 10) ? measured : RATE;
        wav_header(g_out, (uint32_t) g_bytes, rate);
        fclose(g_out);
        printf("recorded %ld bytes (%d s) from source %d at %u Hz%s\n", g_bytes, seconds, source,
               (unsigned) rate, rate != RATE ? " (measured; the stream reports 48000)" : "");
    }
    return g_bytes > 0 ? 0 : 1;
}
