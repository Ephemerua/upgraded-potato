### using frida-gadget
使用`LD_PRELOAD=frida-gadget.so target_prog`运行程序。  
frida-gadget.so将会载入同名的config文件（如 `frida-gadget.config`），根据配置执行js。

sample:  
```
{
  "interaction": {
    "type": "script",
    "path": "./mem_dump_gadget.js"
  },
  "runtime":"jit"
}
```

### using frida-compile
javascript compiled by frida-compile

Before compiled, 
the Object "Buffer.alloc(size);" , "Buffer.toString('base64');" can not be used

install and compile:
```buildoutcfg
npm install frida-compile
./node_modules/.bin/frida-compile record_dump.js -o record_dump_compiled.js
frida-trace -f test -S record_dump_compiled.js
```


