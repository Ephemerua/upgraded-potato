#!/bin/sh

# 编译
mkdir ./bin/
gcc ./source/loader/mmap_dump.c -o ./bin/mmap_dump.so -fPIC -shared -ldl
gcc ./source/loader/tee.c  -o ./bin/tee

# 暂时需要angr和pwnlib
python3 -m pip install angr
python3 -m pip install pwn

