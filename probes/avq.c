/* avq: ask the live kernel policy for an access decision via selinuxfs.
 * usage: avq <scontext> <tcontext> <class> <perm>...                     */
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

static int read_int(const char *path) {
    FILE *f = fopen(path, "r");
    int v = -1;
    if (f) { if (fscanf(f, "%d", &v) != 1) v = -1; fclose(f); }
    return v;
}

int main(int argc, char **argv) {
    if (argc < 5) { fprintf(stderr, "usage: avq scon tcon class perm...\n"); return 2; }
    char path[256], buf[512];
    snprintf(path, sizeof path, "/sys/fs/selinux/class/%s/index", argv[3]);
    int cls = read_int(path);
    if (cls < 0) { fprintf(stderr, "unknown class %s\n", argv[3]); return 2; }
    int fd = open("/sys/fs/selinux/access", O_RDWR);
    if (fd < 0) { perror("open access"); return 1; }
    int n = snprintf(buf, sizeof buf, "%s %s %d", argv[1], argv[2], cls);
    if (write(fd, buf, n) < 0) { perror("write access"); return 1; }
    n = read(fd, buf, sizeof buf - 1);
    if (n < 0) { perror("read access"); return 1; }
    buf[n] = 0;
    unsigned long long allowed = 0, decided = 0, auditallow = 0, auditdeny = 0;
    unsigned seq = 0, flags = 0;
    sscanf(buf, "%llx %llx %llx %llx %u %x", &allowed, &decided, &auditallow, &auditdeny, &seq, &flags);
    for (int i = 4; i < argc; i++) {
        snprintf(path, sizeof path, "/sys/fs/selinux/class/%s/perms/%s", argv[3], argv[i]);
        int bit = read_int(path);
        if (bit <= 0) { printf("  %-10s %-12s ?unknown-perm\n", argv[3], argv[i]); continue; }
        unsigned long long m = 1ULL << (bit - 1);
        printf("  %-10s %-12s %-8s %s\n", argv[3], argv[i],
               (allowed & m) ? "ALLOW" : "deny",
               (allowed & m) ? "" : ((auditdeny & m) ? "(audited)" : "(DONTAUDIT)"));
    }
    printf("  flags=0x%x%s\n", flags, (flags & 1) ? " PERMISSIVE-DOMAIN" : "");
    return 0;
}
