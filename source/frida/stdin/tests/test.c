#include <stdio.h>

int main() {
    char buffer[20];

    scanf("%20s", buffer);
    puts(buffer);
    getchar();
    fgets(buffer, 20uL, stdin);
    puts(buffer);

    return 0;
}