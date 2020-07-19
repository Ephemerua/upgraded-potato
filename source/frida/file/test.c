#include <unistd.h>
#include <fcntl.h>

int main(void) {
    int fd;

    fd = open("rdwr.txt", O_RDWR);
    close(fd);

    fd = open("rdonly.txt", O_RDONLY);
    close(fd);

    fd = open("/home/parallels/competition/frida-file/rdwr.txt", O_RDWR);
    close(fd);

    fd = open("rdwr.txt", O_RDWR);
    write(fd, "test!", 5uL);
    close(fd);

    // what if the program does NOT call close?
    fd = open("rdwr.txt", O_RDWR);
    close(fd);

    return 0;
}
