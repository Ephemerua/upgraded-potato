## using frida-gadget.so
使用`LD_PRELOAD=frida-gadget.so target_prog`运行程序。  
frida-gadget.so将会载入同名的`.config`文件（如 `frida-gadget.config`），根据配置执行js。

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
