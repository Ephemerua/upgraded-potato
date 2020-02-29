
/* from github apsun/hax.c */
/*
 * Hook main() using LD_PRELOAD, because why not?
 * Obviously, this code is not portable. Use at your own risk.
 *
 * Compile using 'gcc mmap_dump.c -o mmap_dump.so -fPIC -shared -ldl'
 * Then run your program as 'LD_PRELOAD=$PWD/hax.so ./a.out'
 */

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <dlfcn.h>
#include <stdarg.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/types.h>
#include "common.h"


#define md_debug(_str...) \
do { \
    if(DEBUG_MODE)\
        debug_info(_str); \
}while(0)

int static inline chk_pr(long long value, char * message)
{
    if(value < 0)
    {
        perror(message);
        return -1;
    }
    return 0;
}

/* Trampoline for the real main() */
static int (*main_orig)(int, char **, char **);
int DEBUG_MODE;



int copy_maps(pid_t pid, unsigned long long bp)
{
    char buf[0x200];
    char path[0x100];
    sprintf(path, "/proc/%d/maps", pid);
    md_debug("trying to get pid:%d's mmap\n", pid);
    int fd_r = open(path, O_RDONLY);
    chk_pr(fd_r, "Open read fd failed: ");
    int fd_w = open("./maps", O_RDWR|O_CREAT|O_TRUNC);
    chk_pr(fd_w, "Open write fd failed: ");
    char *bp_str = (char*)alloc_printf("got bp: %p\n", (void*)bp);
    if (fd_r > 0 && fd_w > 0)
    {
        int rlen, wlen;
        wlen = write(fd_w, bp_str, strlen(bp_str));
        if(chk_pr((long long)wlen, "write faied:"))
                return -1;
        while(rlen = read(fd_r, buf, 0x200), rlen>0)
        {

            wlen = write(fd_w, buf, rlen);
            if(chk_pr((long long)wlen, "write faied:"))
                return -1;
        }
        if(rlen < 0)
        {
            puts("Read Error: ");
            return -1;
        }
        close(fd_r);
        close(fd_w);
    }
    else
    {
        return -1;
    }
    return 0;
}

static unsigned long long inline get_bp()
{
    unsigned long long bp = 0;
    __asm__("movq %%rbp, %0\n\t"
            :"=r"(bp)
            :
            :
           );
    return bp;
}

/* Our fake main() that gets called by __libc_start_main() */
int main_hook(int argc, char **argv, char **envp)
{
    unsigned long long bp = get_bp();
    DEBUG_MODE = 0;
    char* temp_ptr = getenv("BISHE_DEBUG");
    if (temp_ptr)
    {
        DEBUG_MODE = atoi(temp_ptr);
    }
    
    
    pid_t self_pid = getpid();
    pid_t child_pid = fork();
    if(chk_pr(child_pid, "fork failed: "))
        exit(-1);
    if(child_pid == 0)
    {
        if(copy_maps(self_pid, bp))
        {
            puts("mmap dump: copy maps failed");
            exit(0);
        }
        // sleep(2);
        // if(copy_maps(self_pid))
        // {
        //     puts("mmap dump: copy maps failed");
        //     exit(0);
        // }
        return 0;   
    }
    else
    {
        waitpid(child_pid, 0, 0);
    }

    md_debug("got maps. run origin main\n");
    int ret = main_orig(argc, argv, envp);
    md_debug("after main with ret:%d\n", ret);

    return ret;
}

/*
 * Wrapper for __libc_start_main() that replaces the real main
 * function with our hooked version.
 */
int __libc_start_main(
    int (*main)(int, char **, char **),
    int argc,
    char **argv,
    int (*init)(int, char **, char **),
    void (*fini)(void),
    void (*rtld_fini)(void),
    void *stack_end)
{
    /* Save the real main function address */
    main_orig = main;
    /* Find the real __libc_start_main()... */
    typeof(&__libc_start_main) orig = dlsym(RTLD_NEXT, "__libc_start_main");
    /* ... and call it with our custom main function */
    return orig(main_hook, argc, argv, init, fini, rtld_fini, stack_end);
}
