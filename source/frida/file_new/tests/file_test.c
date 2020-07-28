#include <unistd.h>
#include <fcntl.h>

int main(void) {
    int fd;
    char buffer[128];

    fd = open("rdwr.txt", O_RDWR);
    read(fd, buffer, 128uL);
    close(fd);

    fd = open("rdonly.txt", O_RDONLY);
    read(fd, buffer, 128uL);
    close(fd);

    fd = open("rdwr.txt", O_RDWR | O_APPEND);
    read(fd, buffer, 128uL);
    write(fd, "test!", 5uL);
    close(fd);

    // Does NOT call close
    fd = open("rdwr.txt", O_RDWR);
    read(fd, buffer, 128uL);

    return 0;
}
