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

#define DEBUG 1

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


/* global variables goes here */
int out_fd;
pid_t child = 0;

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

ull elf_entry = 0;
ull elf_loadaddr = 0;

ull elf_pokebak = 0;


static inline void dump_segment(char* line, int fd, size_t size){
    unsigned long long start, end;
    char prot[0x20] = {0};
    sscanf(line, "%llx-%llx %s", &start, &end, prot);
    if (elf_loadaddr == 0){ elf_loadaddr = start;  debug_info("loadaddr: %llx\n", start);}
    //debug_info("start: %llx-%llx\n", start, end);
    //debug_info("size: %llx\n", end-start);
    if (prot[2] != 'x'){
        // describe this segment
        write(fd, line, size);
        write(fd, "\n", 1);

        char* buffer = malloc(end - start);
        if (!buffer){
            puts("OOM!");
            exit(0);
        }
        for(unsigned long long i = 0; i < end-start; i+=1){
            buffer[i] = ptrace(PTRACE_PEEKTEXT, child, start + i, NULL);
        }
        size_t encoded_size;
        char* encoded_buffer = base64_encode(buffer, end-start, &encoded_size);
        write(fd, encoded_buffer, encoded_size);
        write(fd, "\n", 1);
        free(buffer);
        free(encoded_buffer);
    }
    
}

int do_memory_dump(char* map_file){
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
        ull rsp = ptrace(PTRACE_PEEKUSER, child, 8*RSP, NULL);
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
            dump_segment(line_buffer, dump_fd, offset);
            offset = 0;
        }else{
            line_buffer[offset++] = buf;
        }
    }

}

int map_parser(){
    pid_t c = fork();
    if (c == 0){
        char* file = alloc_printf("cp -f /proc/%d/maps ./maps.%d && chmod 0666 ./maps.%d", child, child, child);
        system(file);
        exit(0);
    }else{
        char* map_file = alloc_printf("maps.%d", child);
        waitpid(c, 0, 0);
        if (!access(map_file, F_OK)){
            do_memory_dump(map_file);
            free(map_file);
        }else{
            puts("map file copy failed!");
            exit(0);
        }
    }
    return 0;
}

int save_call_context(int sysno){
    struct user_regs_struct regs;
    ptrace(PTRACE_GETREGS, child, NULL, &regs);
    char* tmp = alloc_printf("{\"sysno\": %d, \"rdi\": %#llx, \"rsi\": %#llx, \"rdx\": %#llx, \"rbp\": %#llx, \"rip\": %#llx}\n",\
        sysno, regs.rdi, regs.rsi, regs.rdx, regs.rbp, regs.rip);
    write(out_fd, tmp, strlen(tmp));
    free(tmp);
    return 0;
}

int save_call_result(int sysno){
    unsigned long long rax = ptrace(PTRACE_PEEKUSER, child, 8 * RAX, NULL);
    char *tmp = alloc_printf("{\"is_result\": True, \"sysno\": %d, \"rax\": %#llx, \"mem_changes\": [", sysno, rax);
    write(out_fd, tmp, strlen(tmp));
    free(tmp);
    return rax;
}

void save_memory_change(ull addr, ull size){
    char* buf = malloc(size);
    for(ull i = 0; i < size; i++){
        buf[i] = ptrace(PTRACE_PEEKDATA, child, addr+i, NULL);
    }
    size_t encoded_size;
    char* encoded_buf = base64_encode(buf, size, &encoded_size);
    char* tmp = alloc_printf("{\"addr\": %#llx, \"size\": %lld, \"content\": \"", addr, size);
    write(out_fd, tmp, strlen(tmp));
    write(out_fd, encoded_buf, encoded_size);
    write(out_fd, "\"}, ", 4);
}

void save_end(){
    write(out_fd, "]}\n", 3);
}

int main(int argc, char *argv[]) {
    long orig_rax;
    int status;
    int iscalling = 0;
    int is_init = 1;
    struct user_regs_struct regs;
    ull elf_hdr[4];
    struct user_regs_struct regs_bak;


    // get entry point, we need break at there
    int elf_fd = open(argv[1], O_RDONLY);
    assert(read(elf_fd, elf_hdr, 0x20) == 0x20);
    close(elf_fd);
    elf_entry = elf_hdr[3];


    child = fork();
    if(child == 0)
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
            wait(&status);
            if(WIFEXITED(status))   break;

            if (is_init == 2){
                tmp_rip = ptrace(PTRACE_PEEKUSER, child, 8*RIP, NULL);
                // fucking rip points to next insn
                if (tmp_rip == elf_entry+1){
                    is_init = 0;
                    map_parser();
                    ptrace(PTRACE_GETREGS, child, NULL, &regs_bak);
                    regs_bak.rip -= 1;
                    ptrace(PTRACE_POKETEXT, child, elf_entry, elf_pokebak);
                    ptrace(PTRACE_SETREGS, child, NULL, &regs_bak);
                    ptrace(PTRACE_SYSCALL, child, NULL, NULL);
                    continue;
                }

            }

            orig_rax = ptrace(PTRACE_PEEKUSER, child, 8 * ORIG_RAX, NULL);
            if(orig_rax != -1) 
                debug_info("now syscall: %ld\n", orig_rax);
            
            switch(orig_rax){
                case SYS_execve:
                    if (unlikely(is_init == 1)){
                        map_parser();
                        is_init = 2;
                        if (elf_loadaddr){
                            if (elf_loadaddr>>12 != elf_entry>>12){
                                elf_entry = elf_entry + elf_loadaddr;
                            }
                            elf_pokebak = ptrace(PTRACE_PEEKTEXT, child, elf_entry, NULL);
                            ptrace(PTRACE_POKETEXT, child, elf_entry, 0xcc);
                            ptrace(PTRACE_SYSCALL, child, NULL, NULL);
                        }
                    }
                    break;
                
                case SYS_read:
                    if (!read_calling){
                        // 进入调用，获取参数
                        read_calling = 1;
                        read_fd = ptrace(PTRACE_PEEKUSER, child, 8 * RDI, NULL);
                        read_addr = ptrace(PTRACE_PEEKUSER, child, 8 * RSI, NULL);
                        read_size = ptrace(PTRACE_PEEKUSER, child, 8 * RDX, NULL);
                        // 记录调用信息
                        save_call_context(SYS_read);
                    }else{
                        // 从syscall返回
                        read_calling = 0;
                        // 记录返回信息
                        read_realsize = save_call_result(SYS_read);
                        // 记录内存变化
                        save_memory_change(read_addr, read_realsize);
                        // 加上结尾（手动构建的dict字符串）
                        save_end();
                    }
                    break;
                case SYS_write:
                    if (!write_calling){
                        write_calling = 1;
                        write_fd = ptrace(PTRACE_PEEKUSER, child, 8 * RDI, NULL);
                        write_addr = ptrace(PTRACE_PEEKUSER, child, 8 * RSI, NULL);
                        write_size = ptrace(PTRACE_PEEKUSER, child, 8 * RDX, NULL);
                        save_call_context(SYS_write);
                    }else{
                        write_calling = 0;
                        write_realsize = save_call_result(SYS_write);
                        save_memory_change(write_addr, write_realsize);
                        save_end();
                    }
                    break;
                
            }
            ptrace(PTRACE_SYSCALL, child, NULL, NULL);
        }
        close(out_fd);
    }
    return 0;
}
