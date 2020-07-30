#include <sys/wait.h>
#include <unistd.h>     /* For fork() */
#include <sys/ptrace.h>
#include <sys/wait.h>
#include <sys/reg.h>   /* For constants ORIG_RAX etc */
#include <sys/user.h>
#include <sys/syscall.h> /* SYS_write */
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <stdlib.h>

int main(int argc, char *argv[]) {
    pid_t child;
    long orig_rax;
    int status;
    int iscalling = 0;
    struct user_regs_struct regs;
 
    child = fork();
    if(child == 0)
    {
        ptrace(PTRACE_TRACEME, 0, NULL, NULL);
//        execl("/bin/ping", "ping", "baidu.com", NULL);
        execv(argv[1], argv+2);
    }
    else
    {
		int out_fd = open("stdin.txt", O_RDWR | O_CREAT, 0666);
		int fd = -1;
        while(1)
        {
            wait(&status);
            if(WIFEXITED(status))
            {
                break;
            }
            orig_rax = ptrace(PTRACE_PEEKUSER,
                              child, 8 * ORIG_RAX,
                              NULL);
            if(orig_rax == SYS_read)
            {
                ptrace(PTRACE_GETREGS, child, NULL, &regs);         //获取寄存器参数
                if(!iscalling)          //进入系统调用
                {
                    iscalling = 1;         
//                    printf("[SYS_read] with regs.rdi [%x], regs.rsi[%x], regs.rdx[%x], regs.rax[%x], regs.orig_rax[%x]\n",
//                            regs.rdi, regs.rsi, regs.rdx, regs.rax, regs.orig_rax);
                    fd = regs.rdi;
                }
                else            //离开此次系统调用
                {
//                    printf("[SYS_read] return regs.rsi [%x], regs.rax [%x], regs.orig_rax [%x]\n", regs.rsi, regs.rax, regs.orig_rax);
                    if(fd == 0) {
                        char* buff = (char *)malloc(sizeof(char) * regs.rax);
                        for(int i=0;i<regs.rax;i++) {
                            buff[i] = ptrace(PTRACE_PEEKTEXT, child, regs.rsi+i, NULL);
//                            printf("%c", buff[i]);
                        }
                        write(out_fd, buff, (size_t)regs.rax);
                    }
                    iscalling = 0;
                }

            }
            ptrace(PTRACE_SYSCALL, child, NULL, NULL);

        }
        close(out_fd);
    }
    return 0;
}
