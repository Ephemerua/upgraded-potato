gcc -o file_test file_test.c
frida-trace -f file_test -S ../file_new.js
