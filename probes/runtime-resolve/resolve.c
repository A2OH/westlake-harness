/*
 * Resolve the platform entry points an app would look up by name, and report which file answers.
 *
 * The static side of this pair (sym:runtime-resolved) can only say that a name in the public NDK
 * surface appears as a string in a library. It cannot say whether the lookup succeeds, because a
 * dlopen/dlsym pair declares nothing: the name never reaches the symbol table, the loader never
 * records the dependency, and a missing entry point returns null instead of failing the load.
 *
 * So perform the lookup the app would perform. For each library, dlopen it by the bare soname the
 * caller passes -- deliberately not by path, because the search order is half of what is being
 * measured -- then dlsym each candidate and ask dladdr which file actually answered.
 *
 * That last column is the one nothing else produces. On 2026-09-22 two libandroid.so shipped, the
 * runtime's exported none of the NDK SurfaceControl surface and the WebView one exported all 27,
 * and the search path reached the wrong one first. Both files have the same name, so no symbol
 * table and no import list can express that; only asking the loader can.
 *
 * Run with the launch's own LD_LIBRARY_PATH. This measures the loader's answer for that search
 * path, in this process -- not inside the app's mount namespace and not as the app's uid, so a
 * path the app cannot read may still resolve here. It answers "would this name resolve", not
 * "does the app ask for it".
 */
#include <dlfcn.h>
#include <stdio.h>
#include <string.h>

#define MAX_LINE 512

static void emit(const char *library, const char *symbol, void *handle)
{
    if (handle == NULL) {
        printf("%s\t%s\tlibrary-unavailable\t-\n", library, symbol);
        return;
    }
    dlerror();
    void *address = dlsym(handle, symbol);
    if (address == NULL) {
        printf("%s\t%s\tnull\t-\n", library, symbol);
        return;
    }
    /* Which file answered.  A symbol resolving out of a different library than the one asked for
     * is not an error, but it is the thing worth seeing. */
    Dl_info info;
    if (dladdr(address, &info) != 0 && info.dli_fname != NULL) {
        printf("%s\t%s\tresolved\t%s\n", library, symbol, info.dli_fname);
    } else {
        printf("%s\t%s\tresolved\tunknown\n", library, symbol);
    }
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "usage: %s <candidates-file>\n"
                        "  each line: <library.so><TAB><symbol>\n", argv[0]);
        return 2;
    }
    FILE *file = fopen(argv[1], "r");
    if (file == NULL) {
        fprintf(stderr, "cannot read %s\n", argv[1]);
        return 2;
    }

    char line[MAX_LINE];
    char current[MAX_LINE] = "";
    void *handle = NULL;
    printf("library\tsymbol\tstatus\tprovider\n");
    while (fgets(line, sizeof(line), file) != NULL) {
        char *newline = strchr(line, '\n');
        if (newline != NULL) *newline = '\0';
        char *tab = strchr(line, '\t');
        if (tab == NULL || line[0] == '\0') continue;
        *tab = '\0';
        const char *library = line;
        const char *symbol = tab + 1;

        if (strcmp(library, current) != 0) {
            /* Not dlclose'd: closing and reopening between groups would let a later group see a
             * different resolution order than the app would. */
            snprintf(current, sizeof(current), "%s", library);
            dlerror();
            handle = dlopen(library, RTLD_NOW);
            const char *error = dlerror();
            fprintf(stderr, "[open] %s -> %s%s%s\n", library,
                    handle != NULL ? "ok" : "FAILED",
                    handle != NULL || error == NULL ? "" : ": ",
                    handle != NULL || error == NULL ? "" : error);
        }
        emit(library, symbol, handle);
    }
    fclose(file);
    return 0;
}
