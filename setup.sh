#!/bin/sh

# 编译
mkdir ./bin/
gcc ./source/loader/core_dump.c -o ./bin/core_dump.so -fPIC -shared -ldl
gcc ./source/loader/mmap_dump.c -o ./bin/mmap_dump.so -fPIC -shared -ldl
gcc ./source/loader/tee.c  -o ./bin/tee
gcc ./test/replay_test/replay_test.c -o ./bin/replay_test
gcc ./test/replay_test/get_bp.c -o ./bin/get_bp_test
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


