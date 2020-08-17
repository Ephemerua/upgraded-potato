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
#include <string.h>
#include <stdio.h>
#include <stdint.h>
#include <assert.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

#define DEBUG 1
#if DEBUG == 0
    #define B64_ENCODE 1
#endif

#define likely(x)       __builtin_expect(!!(x), 1)
#define unlikely(x)     __builtin_expect(!!(x), 0)

// returns a buffer, containing the str wanted
#define alloc_printf(_str...) ({ \
    char* _tmp; \
    size_t _len = snprintf(NULL, 0, _str); \
    if (_len < 0) {perror("Whoa, snprintf() fails?!"); abort();}\
    _tmp = malloc(_len + 1); \
    snprintf((char*)_tmp, _len + 1, _str); \
    _tmp; \
  })

//print debug info
#define debug_info(_str...) \
do {\
    if(DEBUG){\
        fprintf(stderr, "%s, %d: ", __FILE__, __LINE__); \
        fprintf(stderr, _str); \
    }\
}while(0)

#define ull unsigned long long

// base64 encoding goes here
static char encoding_table[] = {'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H',
                                'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P',
                                'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X',
                                'Y', 'Z', 'a', 'b', 'c', 'd', 'e', 'f',
                                'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n',
                                'o', 'p', 'q', 'r', 's', 't', 'u', 'v',
                                'w', 'x', 'y', 'z', '0', '1', '2', '3',
                                '4', '5', '6', '7', '8', '9', '+', '/'};
static char *decoding_table = NULL;
static int mod_table[] = {0, 2, 1};

void build_decoding_table() {

    decoding_table = malloc(256);

    for (int i = 0; i < 64; i++)
        decoding_table[(unsigned char) encoding_table[i]] = i;
}

char *base64_encode(const unsigned char *data,
                    size_t input_length,
                    size_t *output_length) {

    *output_length = 4 * ((input_length + 2) / 3);

    char *encoded_data = malloc(*output_length);
    if (encoded_data == NULL) return NULL;

    for (int i = 0, j = 0; i < input_length;) {

        uint32_t octet_a = i < input_length ? (unsigned char)data[i++] : 0;
        uint32_t octet_b = i < input_length ? (unsigned char)data[i++] : 0;
        uint32_t octet_c = i < input_length ? (unsigned char)data[i++] : 0;

        uint32_t triple = (octet_a << 0x10) + (octet_b << 0x08) + octet_c;

        encoded_data[j++] = encoding_table[(triple >> 3 * 6) & 0x3F];
        encoded_data[j++] = encoding_table[(triple >> 2 * 6) & 0x3F];
        encoded_data[j++] = encoding_table[(triple >> 1 * 6) & 0x3F];
        encoded_data[j++] = encoding_table[(triple >> 0 * 6) & 0x3F];
    }

    for (int i = 0; i < mod_table[input_length % 3]; i++)
        encoded_data[*output_length - 1 - i] = '=';

    return encoded_data;
}


unsigned char *base64_decode(const char *data,
                             size_t input_length,
                             size_t *output_length) {

    if (decoding_table == NULL) build_decoding_table();

    if (input_length % 4 != 0) return NULL;

    *output_length = input_length / 4 * 3;
    if (data[input_length - 1] == '=') (*output_length)--;
    if (data[input_length - 2] == '=') (*output_length)--;

    unsigned char *decoded_data = malloc(*output_length);
    if (decoded_data == NULL) return NULL;

    for (int i = 0, j = 0; i < input_length;) {

        uint32_t sextet_a = data[i] == '=' ? 0 & i++ : decoding_table[data[i++]];
        uint32_t sextet_b = data[i] == '=' ? 0 & i++ : decoding_table[data[i++]];
        uint32_t sextet_c = data[i] == '=' ? 0 & i++ : decoding_table[data[i++]];
        uint32_t sextet_d = data[i] == '=' ? 0 & i++ : decoding_table[data[i++]];

        uint32_t triple = (sextet_a << 3 * 6)
        + (sextet_b << 2 * 6)
        + (sextet_c << 1 * 6)
        + (sextet_d << 0 * 6);

        if (j < *output_length) decoded_data[j++] = (triple >> 2 * 8) & 0xFF;
        if (j < *output_length) decoded_data[j++] = (triple >> 1 * 8) & 0xFF;
        if (j < *output_length) decoded_data[j++] = (triple >> 0 * 8) & 0xFF;
    }

    return decoded_data;
}


void base64_cleanup() {
    free(decoding_table);
}


/* global variables for each implemented syscall */
int out_fd;

int open_calling = 0;

int read_calling = 0;
ull read_fd;
ull read_addr;
ull read_size;
ull read_realsize;

int write_calling = 0;
ull write_fd;
ull write_addr;
ull write_size;
ull write_realsize;


/********************************************************************/
/**********************syscall record list***************************/

/*store information by list*/
typedef struct CONTENT_LIST{
    size_t size;
    char* content;
    struct CONTENT_LIST* next;
}content_list;

/*store syscall's information from one thread/process*/
typedef struct SYSCALL_LIST{
    pid_t pid;
    content_list* head;
    content_list* tail;
    struct SYSCALL_LIST* pre;
    struct SYSCALL_LIST* next;
}syscall_list;

/*mapping according to syscalls's number*/
syscall_list* call_table[512];

/*initialize call_table*/
void call_table_init() {
    for(int i=0;i<512;i++) {
        call_table[i] = NULL;
    }
}

content_list* create_content_node() {
    content_list* node = (content_list*)malloc(sizeof(content_list));
    node->size = 0;
    node->content = NULL;
    node->next = NULL;
    return node;
}

syscall_list* create_syscall_node() {
    syscall_list* node = (syscall_list*)malloc(sizeof(syscall_list));
    node->pid = 0;
    node->head = create_content_node();
    node->tail = node->head;
    node->pre = NULL;
    node->next = NULL;
    return node;
}

/* add new str into content list*/
content_list* add_content_list(content_list* p, char* str, size_t size) {
    p->next = create_content_node();
    p = p->next;
    p->content = (char*)malloc(size);
    p->size = size;
    memcpy(p->content, str, size);
    return p;
}

/* add new content into the syscalls' table*/
void add_syscall_table(long sysno, pid_t pid, char *str, size_t size) {
//    printf("pid: %d sysno: %d size: %d\n", pid, sysno, size);
    if(call_table[sysno] == NULL) {
        call_table[sysno] = create_syscall_node();
        call_table[sysno]->pid = pid;
        call_table[sysno]->tail = add_content_list(call_table[sysno]->tail, str, size);
    }
    else{
        syscall_list* p = call_table[sysno];
        while(p != NULL) {
            if(p->pid == pid) {
                p->tail = add_content_list(p->tail, str, size);
                return;
            }
            if(p->next == NULL)
                break;
            p = p->next;
        }
        p->next = create_syscall_node();
        p->next->pre = p;
        p = p->next;
        p->pid = pid;
        p->tail = add_content_list(p->tail, str, size);
    }
}

/* clean list */
void remove_content_list(content_list* p) {
    content_list* tail = p->next;
    while(p != NULL) {
//        printf("size: %d\n", p->size);
        free(p);
        p = tail;
        if(p == NULL)
            break;
        tail = p->next;
    }
}

/* clean list */
void remove_syscall_table(long sysno, pid_t pid) {
//    printf("delete pid: %d sysno: %d\n", pid, sysno);
    if(call_table[sysno] == NULL)
        return;
    if(call_table[sysno]->pid == pid) {
        syscall_list* p = call_table[sysno]->next;
        remove_content_list(call_table[sysno]->head);
        free(call_table[sysno]);
        call_table[sysno] = p;
        if(p != NULL) {
            p->pre = NULL;
        }
        return;
    }
    syscall_list* p = call_table[sysno];
    while(p != NULL) {
        if(p->pid == pid) {
            remove_content_list(p->head);
            syscall_list* pre = p->pre;
            syscall_list* next = p->next;
            free(p);
            pre->next = next;
            if(next != NULL) {
                next->pre = pre;
            }
            return;
        }
        p = p->next;
    }
}

/* write strs in content list into file */
void output_from_talbe_node(long sysno, pid_t pid, int fd) {
    if(call_table[sysno] == NULL)
        return;
    syscall_list* p = call_table[sysno];
    while(p != NULL) {
        if(p->pid == pid) {
            content_list* content_p = p->head;
            while(content_p != NULL) {
                if(content_p->size == 0) {
                    content_p = content_p->next;
                    continue;
                }
                write(fd ,content_p->content, content_p->size);
//                write(1, content_p->content, content_p->size);
                content_p = content_p->next;
            }
            break;
        }
    }
}
/**********************syscall record list***************************/
/********************************************************************/

int socket_calling = 0;

int accept_calling = 0;

int recvmsg_calling = 0;
ull msghdr_ptr;

int recvfrom_calling = 0;
ull recvfrom_ubuf;

int sendto_calling = 0;
ull sendto_buf;

int sendmsg_calling = 0;
ull sendmsg_msghdr;

int getrandom_calling = 0;
ull getrandom_buf;
ull getrandom_size;

int clone_calling = 0;

int fork_calling = 0;

int vfork_calling = 0;

ull elf_entry = 0;
ull elf_loadaddr = 0;

ull elf_pokebak = 0;


static inline void dump_segment(char* line, int fd, size_t size, pid_t pid){
    unsigned long long start, end;
    char prot[0x20] = {0};
    sscanf(line, "%llx-%llx %s", &start, &end, prot);
    if (elf_loadaddr == 0){ elf_loadaddr = start;  debug_info("loadaddr: %llx\n", start);}
    //debug_info("start: %llx-%llx\n", start, end);
    //debug_info("size: %llx\n", end-start);
    if (prot[1] == 'w'){
        // describe this segment
        write(fd, line, size);
        write(fd, "\n", 1);

        char* buffer = malloc(end - start);
        if (!buffer){
            puts("OOM!");
            exit(0);
        }
        for(unsigned long long i = 0; i < end-start; i+=1){
            buffer[i] = ptrace(PTRACE_PEEKTEXT, pid, start + i, NULL);
        }
        size_t encoded_size;
        char* encoded_buffer = base64_encode(buffer, end-start, &encoded_size);
        write(fd, encoded_buffer, encoded_size);
        write(fd, "\n", 1);
        free(buffer);
        free(encoded_buffer);
    }
    
}

int do_memory_dump(char* map_file, pid_t pid){
    int map_fd = open(map_file, O_RDONLY);
    char* dump_file = alloc_printf("%s.dump", map_file);
    int dump_fd = open(dump_file, O_CREAT | O_RDWR, 0666);
    free(dump_file);
    char line_buffer[0x1000] = {0};
    size_t offset = 0;
    char buf;
    struct stat st;

    // dirty way to add one line(sp value) at the beginning of map
    if (stat(map_file, &st) == 0){
        size_t fsize = st.st_size;
        ull rsp = ptrace(PTRACE_PEEKUSER, pid, 8*RSP, NULL);
        char *sp_str = alloc_printf("got bp: %#llx\n", rsp);
        debug_info("%s", sp_str);
        char* tmp_map = malloc(fsize);
        assert(read(map_fd, tmp_map, fsize) == fsize);
        close(map_fd);
        int new_fd = open(map_file, O_RDWR | O_TRUNC | O_CREAT, 0666);
        assert(new_fd>=0);
        assert(write(new_fd, sp_str, strlen(sp_str)) == strlen(sp_str));
        assert(write(new_fd, tmp_map, fsize) == fsize);
        close(new_fd);
        free(tmp_map);
        free(sp_str);
        map_fd = open(map_file, O_RDONLY);
    }else{ perror("dump sp's stat: "); exit(0); }

    int first_line = 1;
    while (read(map_fd, &buf, 1)){
        if (buf == '\n'){
            if(first_line){ first_line = 0; offset = 0;continue;}
            dump_segment(line_buffer, dump_fd, offset, pid);
            offset = 0;
        }else{
            line_buffer[offset++] = buf;
        }
    }

}

int map_parser(pid_t pid){
    pid_t c = fork();
    if (c == 0){
        char* file = alloc_printf("cp -f /proc/%d/maps ./maps.%d && chmod 0666 ./maps.%d", pid, pid, pid);
        system(file);
        exit(0);
    }else{
        char* map_file = alloc_printf("maps.%d", pid);
        waitpid(c, 0, 0);
        if (!access(map_file, F_OK)){
            do_memory_dump(map_file, pid);
            free(map_file);
        }else{
            puts("map file copy failed!");
            exit(0);
        }
    }
    return 0;
}

int save_call_context(int sysno, pid_t pid){
    struct user_regs_struct regs;
    ptrace(PTRACE_GETREGS, pid, NULL, &regs);
    char* tmp = alloc_printf("{\"sysno\": %d, \"rdi\": %#llx, \"rsi\": %#llx, \"rdx\": %#llx, \"rbp\": %#llx, \"rip\": %#llx}\n",\
        sysno, regs.rdi, regs.rsi, regs.rdx, regs.rbp, regs.rip);
    add_syscall_table(sysno, pid, tmp, strlen(tmp));
//    write(out_fd, tmp, strlen(tmp));
    free(tmp);
    return 0;
}

ull save_call_result(int sysno, pid_t pid){
    unsigned long long rax = ptrace(PTRACE_PEEKUSER, pid, 8 * RAX, NULL);
    char *tmp = alloc_printf("{\"is_result\": True, \"sysno\": %d, \"rax\": %#llx, \"mem_changes\": [", sysno, rax);
    add_syscall_table(sysno, pid, tmp, strlen(tmp));
    free(tmp);
    return rax;
}

void save_memory_change(ull addr, ull size, pid_t pid, int sysno){
    char* buf = malloc(size);
    for(ull i = 0; i < size; i++){
        buf[i] = ptrace(PTRACE_PEEKDATA, pid, addr+i, NULL);
    }
    #ifdef B64_ENCODE
        size_t encoded_size;
        char* encoded_buf = base64_encode(buf, size, &encoded_size);
    #endif

    char* tmp = alloc_printf("{\"addr\": %#llx, \"size\": %lld, \"content\": \"", addr, size);
//    write(out_fd, tmp, strlen(tmp));
    add_syscall_table(sysno, pid, tmp, strlen(tmp));
    #ifdef B64_ENCODE
//        write(out_fd, encoded_buf, encoded_size);
        add_syscall_table(sysno, pid, encoded_buf, encoded_size);
    #else
//        write(out_fd, buf, size);
        add_syscall_table(sysno, pid, buf, size);
    #endif
//    write(out_fd, "\"}, ", 4);
    add_syscall_table(sysno, pid, "\"}, ", 4);
}

void save_end(int sysno, pid_t pid){
//    write(out_fd, "]}\n", 3);
    add_syscall_table(sysno, pid, "]}\n", 3);
    output_from_talbe_node(sysno, pid, out_fd);
    remove_syscall_table(sysno, pid);
}

int main(int argc, char *argv[]) {
    int status;
    int iscalling = 0;
    int is_init = 1;
    struct user_regs_struct regs;
    ull elf_hdr[4];
    struct user_regs_struct regs_bak;

    //init the call_table
    call_table_init();

    // get entry point, we need break at there
    int elf_fd = open(argv[1], O_RDONLY);
    assert(read(elf_fd, elf_hdr, 0x20) == 0x20);
    close(elf_fd);
    elf_entry = elf_hdr[3];


    pid_t child_pid = fork();
    if(child_pid == 0)
    {
        ptrace(PTRACE_TRACEME, 0, NULL, NULL);
//        execl("/bin/ping", "ping", "baidu.com", NULL);
        execv(argv[1], argv+1);
    }
    else
    {
		out_fd = open("stdin.txt", O_RDWR | O_CREAT | O_TRUNC, 0666);
		int fd = -1;
        ull tmp_rip;

        while(1)
        {
//            pid_t child_waited = wait(&status);
            pid_t child_waited = waitpid(-1, &status, __WALL);//等待接收信号

            if (child_waited == -1)
                break;
            if (WIFEXITED(status)) {
            //线程结束时，收到的信号
                WEXITSTATUS(status);
            }

            if (is_init == 2 && child_waited == child_pid){
//                printf("in_init2\n");
                tmp_rip = ptrace(PTRACE_PEEKUSER, child_waited, 8*RIP, NULL);
                // fucking rip points to next insn
                if (tmp_rip == elf_entry+1){
                    is_init = 0;
                    map_parser(child_waited);
                    ptrace(PTRACE_GETREGS, child_waited, NULL, &regs_bak);
                    regs_bak.rip -= 1;
                    ptrace(PTRACE_POKETEXT, child_waited, elf_entry, elf_pokebak);
                    ptrace(PTRACE_SETREGS, child_waited, NULL, &regs_bak);
//                    ptrace(PTRACE_SYSCALL, child_waited, NULL, NULL);
//                    continue;
                }
//                else{
//                    ptrace(PTRACE_SYSCALL, child_waited, NULL, NULL);
//                }

            }

            long orig_rax = ptrace(PTRACE_PEEKUSER, child_waited, 8 * ORIG_RAX, NULL);
            if(orig_rax != -1) 
                debug_info("now syscall: %ld\n", orig_rax);
            
            switch(orig_rax){
                case SYS_execve:
                    if (unlikely(is_init == 1) && child_waited == child_pid){

                        /***************trace multi-thread****************/
                        long ptraceOption = PTRACE_O_TRACECLONE;
                        ptrace(PTRACE_SETOPTIONS, child_waited, NULL, ptraceOption); //设置ptrace属性

                        map_parser(child_waited);
                        is_init = 2;
                        if (elf_loadaddr){
                            if (elf_loadaddr>>12 != elf_entry>>12){
                                elf_entry = elf_entry + elf_loadaddr;
                            }
                            elf_pokebak = ptrace(PTRACE_PEEKTEXT, child_waited, elf_entry, NULL);
                            ptrace(PTRACE_POKETEXT, child_waited, elf_entry, 0xcc);
//                            ptrace(PTRACE_SYSCALL, child_waited, NULL, NULL);
                        }
                    }
                    break;
                case SYS_open:
                    if(!open_calling){
                        open_calling = 1;
                        save_call_context(SYS_open, child_waited);
                    }else{
                        open_calling = 0;
                        save_call_result(SYS_open, child_waited);
                        save_end(SYS_open, child_waited);
                    }
                    break;
                
                case SYS_read:
                    if (!read_calling){
                        // 进入调用，获取参数
                        read_calling = 1;
                        read_fd = ptrace(PTRACE_PEEKUSER, child_waited, 8 * RDI, NULL);
                        read_addr = ptrace(PTRACE_PEEKUSER, child_waited, 8 * RSI, NULL);
                        read_size = ptrace(PTRACE_PEEKUSER, child_waited, 8 * RDX, NULL);
                        // 记录调用信息
                        save_call_context(SYS_read, child_waited);
                    }else{
                        // 从syscall返回
                        read_calling = 0;
                        // 记录返回信息
                        read_realsize = save_call_result(SYS_read, child_waited);
                        // 记录内存变化
                        save_memory_change(read_addr, read_realsize, child_waited, SYS_read);
                        // 加上结尾（手动构建的dict字符串）
                        save_end(SYS_read, child_waited);
                    }
                    break;
                case SYS_write:
                    if (!write_calling){
                        write_calling = 1;
                        write_fd = ptrace(PTRACE_PEEKUSER, child_waited, 8 * RDI, NULL);
                        write_addr = ptrace(PTRACE_PEEKUSER, child_waited, 8 * RSI, NULL);
                        write_size = ptrace(PTRACE_PEEKUSER, child_waited, 8 * RDX, NULL);
                        save_call_context(SYS_write, child_waited);
                    }else{
                        write_calling = 0;
                        write_realsize = save_call_result(SYS_write, child_waited);
                        save_memory_change(write_addr, write_realsize, child_waited, SYS_write);
                        save_end(SYS_write, child_waited);

                    }
                    break;

                case SYS_socket:
                    if(!socket_calling){
                        socket_calling = 1;
                        save_call_context(SYS_socket, child_waited);
                    }else{
                        socket_calling = 0;
                        save_call_result(SYS_socket, child_waited);
                        save_end(SYS_socket, child_waited);
                    }
                    break;
                
                case SYS_accept:
                    if(!accept_calling){
                        accept_calling = 1;
                        save_call_context(SYS_accept, child_waited);
                    }else{
                        accept_calling = 0;
                        save_call_result(SYS_accept, child_waited);
                        save_end(SYS_accept, child_waited);
                    }
                    break;
            
                case SYS_recvmsg:
                    if(!recvmsg_calling){
                        recvmsg_calling = 1;
                        msghdr_ptr = ptrace(PTRACE_PEEKUSER, child_waited, 8 * RSI, NULL);
                        save_call_context(SYS_recvmsg, child_waited);
                    }else{
                        recvmsg_calling = 0;
                        struct msghdr* msghdr_buf = malloc(sizeof(struct msghdr));
                        for(int i = 0; i < sizeof(struct msghdr); i++){
                            *((char*)msghdr_buf+i) = ptrace(PTRACE_PEEKDATA, child_waited, msghdr_ptr+i, NULL);
                        }
                        struct iovec* iov_buf = malloc(sizeof(struct iovec));
                        for(int i=0;i<sizeof(struct iovec);i++) {
                            *((char*)iov_buf+i) = ptrace(PTRACE_PEEKDATA, child_waited, (ull)msghdr_buf->msg_iov+i, NULL);
                        }   
                        ull msg_len = save_call_result(SYS_recvmsg, child_waited);
                        save_memory_change((ull)iov_buf->iov_base, msg_len, child_waited, SYS_recvmsg);
                        save_memory_change((ull)msghdr_ptr, sizeof(struct msghdr), child_waited, SYS_recvmsg);
                        save_memory_change((ull)msghdr_buf->msg_iov, sizeof(struct iovec), child_waited, SYS_recvmsg);
                        save_end(SYS_recvmsg, child_waited);
                        free(msghdr_buf);
                        free(iov_buf);
                    }
                    break;
                case  SYS_recvfrom:
                    if(!recvfrom_calling){
                        recvfrom_calling = 1;
                        recvfrom_ubuf = ptrace(PTRACE_PEEKUSER, child_waited, 8 * RSI, NULL);
                        save_call_context(SYS_recvfrom, child_waited);
                    }else{
                        recvfrom_calling = 0;
                        ull msg_len = save_call_result(SYS_recvfrom, child_waited);
                        save_memory_change(recvfrom_ubuf, msg_len, child_waited, SYS_recvfrom);
                        save_end(SYS_recvfrom, child_waited);
                    }
                    break;
                
                case SYS_sendto:
                    if(!sendto_calling){
                        sendto_calling = 1;
                        sendto_buf = ptrace(PTRACE_PEEKUSER, child_waited, 8 * RSI, NULL);
                        save_call_context(SYS_sendto, child_waited);
                    }else{
                        sendto_calling = 0;
                        ull msg_len = save_call_result(SYS_sendto, child_waited);
                        save_memory_change(sendto_buf, msg_len, child_waited, SYS_sendto);
                        save_end(SYS_sendto, child_waited);
                    }
                    break;
                case SYS_sendmsg:
                    if(!sendmsg_calling){
                        sendmsg_calling = 1;
                        sendmsg_msghdr = ptrace(PTRACE_PEEKUSER, child_waited, 8 * RSI, NULL);
                        save_call_context(SYS_sendmsg, child_waited);
                    }else{
                        sendmsg_calling = 0;
                        struct msghdr* msghdr_buf = malloc(sizeof(struct msghdr));
                        for(int i = 0; i < sizeof(struct msghdr); i++){
                            *((char*)msghdr_buf+i) = ptrace(PTRACE_PEEKDATA, child_waited, sendmsg_msghdr+i, NULL);
                        }
                        struct iovec* iov_buf = malloc(sizeof(struct iovec));
                        for(int i=0;i<sizeof(struct iovec);i++) {
                            *((char*)iov_buf+i) = ptrace(PTRACE_PEEKDATA, child_waited, (ull)msghdr_buf->msg_iov+i, NULL);
                        }   
                        ull msg_len = save_call_result(SYS_recvmsg, child_waited);
                        save_memory_change((ull)iov_buf->iov_base, msg_len, child_waited, SYS_sendmsg);
                        save_end(SYS_sendmsg, child_waited);
                        free(msghdr_buf);
                        free(iov_buf);
                    }
                    break;
                case SYS_getrandom:
                    if(!getrandom_calling){
                        getrandom_calling = 1;
                        getrandom_buf = ptrace(PTRACE_PEEKUSER, child_waited, 8 * RDI, NULL);
                        save_call_context(SYS_getrandom, child_waited);
                    }else{
                        getrandom_calling = 0;
                        ull real_getrandom_size = save_call_result(SYS_getrandom, child_waited);
                        save_memory_change(getrandom_buf, real_getrandom_size, child_waited, SYS_getrandom);
                        save_end(SYS_getrandom, child_waited);
                    }
                    break;

                case SYS_clone:
                    if(!clone_calling) {
                        clone_calling = 1;
                    }else{
                        clone_calling = 0;
                        pid_t new_pid = ptrace(PTRACE_PEEKUSER, child_waited, 8 * RAX, NULL);
                        ptrace(PTRACE_ATTACH, new_pid, NULL, NULL);
                    }
                    break;

                case SYS_fork:
                    if(!fork_calling) {
                        fork_calling = 1;
                    }else{
                        pid_t new_pid = ptrace(PTRACE_PEEKUSER, child_waited, 8 * RAX, NULL);
                        ptrace(PTRACE_ATTACH, new_pid, NULL, NULL);
                    }
                    break;

                case SYS_vfork:
                    if(!vfork_calling) {
                        vfork_calling = 1;
                    }else{
                        pid_t new_pid = ptrace(PTRACE_PEEKUSER, child_waited, 8 * RAX, NULL);
                        ptrace(PTRACE_ATTACH, new_pid, NULL, NULL);
                    }
                    break;

                default:
                    break;
            }
            ptrace(PTRACE_SYSCALL, child_waited, NULL, NULL);
        }
        close(out_fd);
    }
    return 0;
}
