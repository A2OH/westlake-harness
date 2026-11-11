/*
 * netprobe: what the board's network answers for a list of names, through the resolver apps use
 * (OpenHarmony's netsys DNS proxy, which musl's getaddrinfo asks). For each name: getaddrinfo
 * (AF_UNSPEC, SOCK_STREAM), a TCP connect to port 443 of the first IPv4 answer, then a TLS 1.2
 * ClientHello naming the host (SNI), recording whether any TLS record comes back. A filter that
 * resets or drops connections by address or by SNI shows as a failed connect or a reset/timeout
 * after the hello, where a working path answers with a handshake or an alert record.
 *
 * Usage: netprobe <name>...   One JSON object per name on stdout.
 */
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netdb.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#define TIMEOUT_MS 3000

static long now_ms(void)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec * 1000L + t.tv_nsec / 1000000L;
}

static size_t put16(unsigned char *p, size_t at, unsigned v)
{
    p[at] = (unsigned char) (v >> 8);
    p[at + 1] = (unsigned char) v;
    return at + 2;
}

/* A TLS 1.2 ClientHello with SNI, ECDHE suites and the extensions servers expect for them. */
static size_t client_hello(const char *name, unsigned char *out)
{
    static const unsigned suites[] = { 0xc02b, 0xc02f, 0xc02c, 0xc030, 0xcca9, 0xcca8 };
    static const unsigned signatures[] = { 0x0403, 0x0804, 0x0401, 0x0503, 0x0805, 0x0501 };
    size_t n = strlen(name), e = 0;
    unsigned char ext[512];
    e = put16(ext, e, 0x0000);              /* server_name */
    e = put16(ext, e, (unsigned) n + 5);
    e = put16(ext, e, (unsigned) n + 3);
    ext[e++] = 0;
    e = put16(ext, e, (unsigned) n);
    memcpy(ext + e, name, n);
    e += n;
    e = put16(ext, e, 0x000a);              /* supported_groups: x25519, secp256r1, secp384r1 */
    e = put16(ext, e, 8);
    e = put16(ext, e, 6);
    e = put16(ext, e, 0x001d);
    e = put16(ext, e, 0x0017);
    e = put16(ext, e, 0x0018);
    e = put16(ext, e, 0x000b);              /* ec_point_formats: uncompressed */
    e = put16(ext, e, 2);
    ext[e++] = 1;
    ext[e++] = 0;
    e = put16(ext, e, 0x000d);              /* signature_algorithms */
    e = put16(ext, e, 2 + 2 * (unsigned) (sizeof(signatures) / sizeof(signatures[0])));
    e = put16(ext, e, 2 * (unsigned) (sizeof(signatures) / sizeof(signatures[0])));
    for (size_t i = 0; i < sizeof(signatures) / sizeof(signatures[0]); ++i) e = put16(ext, e, signatures[i]);

    unsigned char body[768];
    size_t b = 0;
    body[b++] = 3;                          /* client_version TLS 1.2 */
    body[b++] = 3;
    for (int i = 0; i < 32; ++i) body[b++] = (unsigned char) rand();
    body[b++] = 0;                          /* no session id */
    b = put16(body, b, 2 * (unsigned) (sizeof(suites) / sizeof(suites[0])));
    for (size_t i = 0; i < sizeof(suites) / sizeof(suites[0]); ++i) b = put16(body, b, suites[i]);
    body[b++] = 1;                          /* compression: null */
    body[b++] = 0;
    b = put16(body, b, (unsigned) e);
    memcpy(body + b, ext, e);
    b += e;

    size_t o = 0;
    out[o++] = 0x16;                        /* handshake record, TLS 1.0 framing as clients send */
    out[o++] = 3;
    out[o++] = 1;
    o = put16(out, o, (unsigned) b + 4);
    out[o++] = 1;                           /* client_hello */
    out[o++] = 0;
    o = put16(out, o, (unsigned) b);
    memcpy(out + o, body, b);
    return o + b;
}

static const char *wait_for(int fd, short events)
{
    struct pollfd p = { fd, events, 0 };
    int r = poll(&p, 1, TIMEOUT_MS);
    if (r == 0) return "timeout";
    if (r < 0) return "error";
    return NULL;
}

/* connect and TLS hello to one IPv4 address; fills connect and tls results. */
static void probe(const struct sockaddr_in *address, const char *name, const char **connect_result,
                  long *connect_ms, const char **tls_result, long *tls_ms)
{
    *tls_result = "none";
    *tls_ms = -1;
    long start = now_ms();
    int fd = socket(AF_INET, SOCK_STREAM | SOCK_CLOEXEC | SOCK_NONBLOCK, 0);
    if (fd < 0) {
        *connect_result = "socket";
        *connect_ms = -1;
        return;
    }
    int rc = connect(fd, (const struct sockaddr *) address, sizeof(*address));
    if (rc != 0 && errno != EINPROGRESS) {
        *connect_result = errno == ECONNREFUSED ? "refused" : errno == ENETUNREACH ? "unreachable" : "error";
        *connect_ms = now_ms() - start;
        close(fd);
        return;
    }
    const char *waited = rc == 0 ? NULL : wait_for(fd, POLLOUT);
    int error = 0;
    socklen_t length = sizeof(error);
    if (waited == NULL && getsockopt(fd, SOL_SOCKET, SO_ERROR, &error, &length) == 0 && error != 0) {
        waited = error == ECONNREFUSED ? "refused" : error == ECONNRESET ? "reset"
                 : error == ETIMEDOUT ? "timeout" : error == ENETUNREACH || error == EHOSTUNREACH ? "unreachable"
                 : "error";
    }
    *connect_ms = now_ms() - start;
    *connect_result = waited != NULL ? waited : "ok";
    if (waited != NULL) {
        close(fd);
        return;
    }
    unsigned char hello[1024];
    size_t size = client_hello(name, hello);
    start = now_ms();
    if (send(fd, hello, size, MSG_NOSIGNAL) != (ssize_t) size) {
        *tls_result = errno == ECONNRESET ? "reset" : "send-error";
    } else {
        unsigned char reply[5];
        waited = wait_for(fd, POLLIN);
        ssize_t got = waited == NULL ? recv(fd, reply, sizeof(reply), 0) : -1;
        if (waited != NULL) *tls_result = waited;
        else if (got > 0 && reply[0] == 0x16) *tls_result = "handshake";
        else if (got > 0 && reply[0] == 0x15) *tls_result = "alert";
        else if (got > 0) *tls_result = "other";
        else if (got == 0) *tls_result = "closed";
        else *tls_result = errno == ECONNRESET ? "reset" : "error";
    }
    *tls_ms = now_ms() - start;
    close(fd);
}

int main(int argc, char **argv)
{
    srand((unsigned) time(NULL));
    for (int i = 1; i < argc; ++i) {
        const char *name = argv[i];
        if (strlen(name) > 200 || strpbrk(name, "\"\\") != NULL) continue;
        struct addrinfo hints, *answers = NULL;
        memset(&hints, 0, sizeof(hints));
        hints.ai_family = AF_UNSPEC;
        hints.ai_socktype = SOCK_STREAM;
        long start = now_ms();
        int rc = getaddrinfo(name, "443", &hints, &answers);
        long gai_ms = now_ms() - start;
        char v4[4][INET_ADDRSTRLEN];
        int count4 = 0, count6 = 0;
        struct sockaddr_in first;
        for (struct addrinfo *a = rc == 0 ? answers : NULL; a != NULL; a = a->ai_next) {
            if (a->ai_family == AF_INET6) count6++;
            if (a->ai_family != AF_INET) continue;
            const struct sockaddr_in *in = (const struct sockaddr_in *) a->ai_addr;
            if (count4 == 0) first = *in;
            if (count4 < 4) inet_ntop(AF_INET, &in->sin_addr, v4[count4], sizeof(v4[count4]));
            count4++;
        }
        if (answers != NULL) freeaddrinfo(answers);
        printf("{\"name\":\"%s\",\"gai\":%d,\"gai_error\":\"%s\",\"gai_ms\":%ld,\"v4\":[", name, rc,
               rc != 0 ? gai_strerror(rc) : "", gai_ms);
        for (int k = 0; k < count4 && k < 4; ++k) printf("%s\"%s\"", k > 0 ? "," : "", v4[k]);
        printf("],\"v6\":%d", count6);
        if (count4 > 0) {
            const char *connect_result, *tls_result;
            long connect_ms, tls_ms;
            probe(&first, name, &connect_result, &connect_ms, &tls_result, &tls_ms);
            printf(",\"connect\":\"%s\",\"connect_ms\":%ld,\"tls\":\"%s\",\"tls_ms\":%ld", connect_result, connect_ms,
                   tls_result, tls_ms);
        }
        printf("}\n");
        fflush(stdout);
    }
    return 0;
}
