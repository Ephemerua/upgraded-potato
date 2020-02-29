#!/bin/sh

# 编译
mkdir ./bin/
gcc ./source/loader/mmap_dump.c -o ./bin/mmap_dump.so -fPIC -shared -ldl
gcc ./source/loader/tee.c  -o ./bin/tee

# 暂时需要angr和pwnlib
python3 -m pip show angr 1>/dev/null
if [ $? -ne 0  ]
then
    python3 -m pip install angr
fi
python3 -m pip show pwn 1>/dev/null
if [ $? -ne 0  ]
then
    python3 -m pip install pwn
fi


