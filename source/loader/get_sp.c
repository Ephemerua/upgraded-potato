#include <stdlib.h>
#include <stdio.h>


int main()
{
    unsigned long long bp = 0;
    __asm__("movq %%rbp, %0\n\t"
            :"=r"(bp)
            :
            :
           );
    printf("%p\n", bp);
    scanf("%p", &bp);
    return 0;
}
