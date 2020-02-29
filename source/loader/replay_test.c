#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <google/coredumper.h>
void init_test()
{
    setvbuf(stdin, 0, 2, 0);
    setvbuf(stdout, 0, 2, 0);
    alarm(0x10);
}

int scanf_test()
{
    printf("start %s:\n", __FUNCTION__);

    char str[10];
    int x;
    puts("test1");
    int num = scanf("%d%s", &x, str);
    if(num != 2)
        puts("scanf error");
    printf("got int: %d\ngot str: %s\n", x, str);
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
    WriteCoreDump("test.core");
    init_test();
    read_test();
    scanf_test();
    malloc_test();

    return 0;
}
