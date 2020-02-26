# README

## 配置环境
运行setup.sh即可。目前只需要pwnlib和angr两个python库。

## 使用说明
目前只做了记录和重放，功能还不完全。  
运行方法：  

```bash
./set-aslr.sh off # 关闭aslr以防问题，建议在docker/vm里面跑
./bin/tee output.txt | LD_PRELOAD=./bin/mmap_dump.so <path-to-target>
```

