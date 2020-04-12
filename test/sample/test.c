#include <stdio.h>

struct base
{
	int a;
	int b;
	int c;
};

union testu
{
	int i;
	char b[24];
	struct base c;
};


int main()
{
	union testu aa;
	return 0;

}
