#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

void init_test()
{
    setvbuf(stdin, 0, 2, 0);
    setvbuf(stdout, 0, 2, 0);
    alarm(0x10);
}

int format_str_test()
{
    printf("start %s:\n", __FUNCTION__);

    char str[]="we have 321 and 123";
    char* dst = malloc(0x100);
    int x;
    puts("scanf test");
    int num = scanf("%d%s", &x, dst);
    if(num != 1)
        puts("scanf error");
    puts("printf test");
    num = printf("got int: %d, test printf with str:%s\n", x, dst);
    sscanf(str, "%s %d", dst, &x);
    num = printf("got int: %d\n, test printf with str:%s\n", x, dst);
    sprintf(dst, "%s %d", "123", 123);
    printf("%s\n", dst);
    return 0;
}

int read_test()
{
    printf("start %s:\n", __FUNCTION__);

    char str1[10];
    char str2[10];
    int len = read(0, str1, 10);
    if(len < 0)
        puts("read error.");
    len = read(0, str2, 10);
    if(len < 0)
        puts("read error.");
    printf("got str1:%s\ngot str2:%s\n", str1, str2);

    return 0;
}

int malloc_test()
{
    printf("start %s:\n", __FUNCTION__);

    void *chunk = malloc(0x38);
    if(!chunk)
        puts("malloc error.");
    return 0;
}


int main()
{
    init_test();
    read_test();
    format_str_test();
    malloc_test();

    return 0;
}
