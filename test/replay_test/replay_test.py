#!/usr/bin/env python3

import sys
import os
import time

sys.path.append("../../source/")

from replayer import Replayer

# do compile
os.system("gcc ./replay_test.c -o test")
if not os.access("./test", os.X_OK):
    print("Test elf can't execute. Check compiler.")
    exit(1)


# start test
from pwn import *
p = process("../../bin/tee output.txt | LD_PRELOAD=../../bin/mmap_dump.so ./test", shell=True)
context.timeout = 1
context.log_level = "debug"

p.sendafter("start read_test:\n", "123")
time.sleep(1)
p.sendline("456")
r = p.sendlineafter("start scanf_test:\n", "123asd")
log.info("got response:"+r)
r = p.recvuntil("got str")
if "scanf error" in r:
    print("found error in scanf test!")
p.close()

log.success("Record done.\nStart check replayer.")

Replayer()










