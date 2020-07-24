javascript compiled by frida-compile

Before compiled, 
the Object "Buffer.alloc(size);" , "Buffer.toString('base64');" can not be used

install and compile:
```buildoutcfg
npm install frida-compile
./node_modules/.bin/frida-compile record_dump.js -o record_dump_compiled.js
frida-trace -f test -S record_dump_compiled.js
```


