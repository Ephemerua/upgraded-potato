
/* from github apsun/hax.c */
/*
 * Hook main() using LD_PRELOAD, because why not?
 * Obviously, this code is not portable. Use at your own risk.
 *
 * Compile using 'gcc mmap_dump.c -o hax.so -fPIC -shared -ldl'
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

/* Trampoline for the real main() */
static int (*main_orig)(int, char **, char **);
int DEBUG_MODE;

void debug_info(char* format, ...)
{
    if(DEBUG_MODE)
    {
        va_list args;
        va_start(args, format);
        printf("Mmap dump debug: ");
        vprintf(format, args);
        puts("");
        va_end(args);
    }
}


int copy_maps(pid_t pid)
{
    char buf[0x200];
    char path[0x100];
    sprintf(path, "/proc/%d/maps", pid);
    int fd_r = open(path, O_RDONLY);
    int fd_w = open("./maps", O_RDWR|O_CREAT|O_TRUNC);
    if (fd_r > 0 && fd_w > 0)
    {
        int rlen, wlen;
        while(rlen = read(fd_r, buf, 0x200), rlen>0)
        {

            wlen = write(fd_w, buf, rlen);
            if(wlen < 0)
            {
                puts("write failed.");
                return -1;
            }   
        }
        if(rlen < 0)
        {
            puts("read failed.");
            return -1;
        }
        close(fd_r);
        close(fd_w);
    }
    else
    {
        puts("open failed.");
        return -1;
    }
    return 0;
}

/* Our fake main() that gets called by __libc_start_main() */
int main_hook(int argc, char **argv, char **envp)
{
    DEBUG_MODE = 0;
    char* temp_ptr = getenv("BISHE_DEBUG");
    if (temp_ptr)
    {
        DEBUG_MODE = atoi(temp_ptr);
    }
    

    
    pid_t self_pid = getpid();
    pid_t child_pid = fork();
    if(child_pid < 0)
    {
        puts("mmap dump: fork failed");
        exit(0);
    }
    if(child_pid == 0)
    {
        if(copy_maps(self_pid))
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



    debug_info("got maps. run origin main");
    int ret = main_orig(argc, argv, envp);
    debug_info("after main with ret:%d", ret);

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
