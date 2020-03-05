# README

## 配置环境
运行setup.sh即可。目前只需要pwnlib和angr两个python库。

## 使用说明
目前只做了记录和重放，功能还不完全。  

### 记录

```bash
./set-aslr.sh off # 关闭aslr去掉内存随机化，建议在docker/vm里面跑
./bin/tee output.txt | LD_PRELOAD=./bin/mmap_dump.so <path-to-target> # 记录初始状态和输入
```

+ tee无法确定管道是否被关闭，需要在下一次read时读到eof才能结束进程，在运行记录的命令时，如果发生目标程序已经退出但tee还在运行的情况，用Ctrl-D或者敲回车解决，如果输入了其他字符，可能在重放时导致问题。
+ google coredumper产生的coredump不完整，修改了一下发现会破坏栈，暂时弃用。gcore的方案还没测试，但angr的elfcore的后端也存在问题。

### 重放
```python
r = Replayer(...)
state = r.get_entry_state() # 这个state是设置好了内存布局、寄存器和输入流的entry_state，ip在目标程序的入口点。
```

Replayer几乎只是angr.project的一个封装，代码需要重构。  

+ ~~问题：angr只能处理只有一个参数的scanf，在使用sim_packets读入多个参数时，会发生错误。~~ok这个是angr的bug。暴力注释掉size check之后scanf能够完美运行。

### 分析
暂未实现。