/*
 * Capture what an app actually puts on the wire, from the OS rather than from the app.
 *
 * An app's own network stack logs nothing we control: Chromium's does because the WebView shim
 * sits under it, but Toutiao's cronet, an SDK's OkHttp and every static library do not. That left
 * "is the request even sent" unanswerable from the app side, and on 2026-09-22 it was briefly
 * written down as needing an instrument the harness does not have. It does not. We own the board.
 *
 * AF_PACKET gives the frames; this writes them as a pcap so the answer is readable with ordinary
 * tools. Two things are legible even though the payload is TLS, and they are usually the two that
 * matter:
 *
 *   - DNS, in plaintext, which names the hosts the app is looking for and whether they resolve;
 *   - the TLS ClientHello SNI, which names the host of an encrypted connection.
 *
 * What it cannot give is the response body. An app that connects, completes a handshake and
 * receives a rejection looks the same here as one that succeeds, so this decides "was it asked"
 * and not "what was the answer".
 */
#include <arpa/inet.h>
#include <errno.h>
#include <linux/if_ether.h>
#include <linux/if_packet.h>
#include <net/if.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

#define SNAPLEN 262144

struct pcap_header {
    uint32_t magic, sigfigs_pad;
    uint16_t version_major, version_minor;
    int32_t thiszone;
    uint32_t sigfigs, snaplen, network;
};

static int write_global_header(FILE *out)
{
    /* Classic pcap, microsecond resolution, Ethernet link type. Written field by field rather
     * than as a struct so padding cannot change the file format. */
    const uint32_t magic = 0xa1b2c3d4, zero = 0, snaplen = SNAPLEN, ethernet = 1;
    const uint16_t major = 2, minor = 4;
    return fwrite(&magic, 4, 1, out) == 1 &&
           fwrite(&major, 2, 1, out) == 1 &&
           fwrite(&minor, 2, 1, out) == 1 &&
           fwrite(&zero, 4, 1, out) == 1 &&   /* thiszone */
           fwrite(&zero, 4, 1, out) == 1 &&   /* sigfigs */
           fwrite(&snaplen, 4, 1, out) == 1 &&
           fwrite(&ethernet, 4, 1, out) == 1;
}

int main(int argc, char **argv)
{
    if (argc < 4) {
        fprintf(stderr, "usage: %s <interface> <seconds> <out.pcap>\n", argv[0]);
        return 2;
    }
    const char *interface = argv[1];
    const long seconds = strtol(argv[2], NULL, 10);
    const char *path = argv[3];

    int fd = socket(AF_PACKET, SOCK_RAW, htons(ETH_P_ALL));
    if (fd < 0) {
        fprintf(stderr, "AF_PACKET socket failed: %s\n", strerror(errno));
        return 1;
    }
    /* Bind to one interface so the link type is known: an unbound capture mixes interfaces whose
     * link layers differ, and the pcap can then only be honestly labelled as cooked. */
    struct sockaddr_ll address;
    memset(&address, 0, sizeof(address));
    address.sll_family = AF_PACKET;
    address.sll_protocol = htons(ETH_P_ALL);
    address.sll_ifindex = (int) if_nametoindex(interface);
    if (address.sll_ifindex == 0) {
        fprintf(stderr, "no interface %s: %s\n", interface, strerror(errno));
        return 1;
    }
    if (bind(fd, (struct sockaddr *) &address, sizeof(address)) < 0) {
        fprintf(stderr, "bind %s failed: %s\n", interface, strerror(errno));
        return 1;
    }
    struct timeval timeout = {1, 0};
    setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));

    FILE *out = fopen(path, "wb");
    if (out == NULL || !write_global_header(out)) {
        fprintf(stderr, "cannot write %s\n", path);
        return 1;
    }

    static unsigned char frame[SNAPLEN];
    const time_t deadline = time(NULL) + (seconds > 0 ? seconds : 30);
    unsigned long captured = 0, bytes = 0;
    while (time(NULL) < deadline) {
        ssize_t n = recv(fd, frame, sizeof(frame), 0);
        if (n <= 0) {
            continue;   /* the receive timeout is what lets the deadline be checked */
        }
        struct timeval now;
        gettimeofday(&now, NULL);
        const uint32_t ts_sec = (uint32_t) now.tv_sec, ts_usec = (uint32_t) now.tv_usec;
        const uint32_t length = (uint32_t) n;
        if (fwrite(&ts_sec, 4, 1, out) != 1 || fwrite(&ts_usec, 4, 1, out) != 1 ||
            fwrite(&length, 4, 1, out) != 1 || fwrite(&length, 4, 1, out) != 1 ||
            fwrite(frame, 1, (size_t) n, out) != (size_t) n) {
            fprintf(stderr, "short write after %lu packets\n", captured);
            break;
        }
        captured++;
        bytes += (unsigned long) n;
    }
    fclose(out);
    close(fd);
    /* Printed rather than left to the file size, so a capture that saw nothing is obvious. */
    printf("NETCAP interface=%s packets=%lu bytes=%lu file=%s\n", interface, captured, bytes, path);
    return 0;
}
