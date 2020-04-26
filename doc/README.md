# README

## 目标
（半）自动化地分析漏洞利用的方法、过程，最终形成一份报告。

## 配置环境
[setup](./Setup.md)
运行setup.sh即可。目前只需要pwnlib和angr两个python库。

## 使用说明
目前只做了记录和重放，功能还不完全。  

### 记录

```bash
./set-aslr.sh off # 关闭aslr去掉内存随机化，建议在docker/vm里面跑
./bin/tee output.txt | LD_PRELOAD=./bin/mmap_dump.so <path-to-target> # 记录初始状态和输入
```

+ tee无法确定管道是否被关闭，需要在下一次read时读到eof才能结束进程，在运行记录的命令时，如果发生目标程序已经退出但tee还在运行的情况，用Ctrl-D或者敲回车解决，如果输入了其他字符，可能在重放时导致问题。
+ google coredumper产生的coredump不完整，修改了一下发现会破坏栈，暂时弃用。gcore的方案还没测试，但angr的elfcore的后端也存在问题。(原本想要应用的[coredumper](https://github.com/madscientist/google-coredumper.git))
+ **注意⚠️：现在只能在录制的环境下进行重放，正在准备添加打包动态链接库的功能😢**

### 重放
**迁移相关：maps文件的内容涉及到运行记录模块的设备的绝对路径，请手动修改至自己机器的路径，并保证依赖库版本一致**

```python
r = Replayer(...)
state = r.get_entry_state() # 这个state是设置好了内存布局、寄存器和输入流的entry_state，ip在目标程序的入口点。 主要用来分析的对象。
simgr = r.get_simgr() # 使用entry_state的simgr。

# 接下来就可以玩耍了，程序的行为应当和记录时一致，因此我们能够到达一次执行的任意状态。
simgr.step()
simgr.run()
```


### 分析
#### 已经实现
1. got表分析
2. 堆分析（部分）
3. 信息泄露分析
4. 函数调用分析（部分）
5. 控制流分析

#### 使用方法
还没有在replayer.py里面添加binding, 直接导入然后实例化，调用`do_analysis`即可。  
部分结果记录在类的变量中，暂时还没有确定最终可视化的表现形式。


### TODO
1. dwarf解析  （用pyelftools或别的工具，通过地址解析符号，通过调试\符号信息获取可读的信息）
    + 追踪一次内存修改
2. 一个stage，把目标程序绑定到某个端口（这样我们就可以分析ftp，webserver等等不使用stdio作为输入输出的程序）
3. desocket + stage测试
    目标：用这个模式正常运行tftp server，然后可以取得他的输入
4. logging （目前只是用print输出报告）  
暂定记录内容：
    + 日志级别（debug, info, critical等那一套）
    + 时序（使用state.history.bbl_addr可以表示）
    + 内容（主要的记录内容）
5. 可视化的表现形式（xml? html? 图表？）  
logging to html/xml
可以先转换为一些中间表示（json/yaml等）再转换为可读性高的文件


## 设计思路
1. 去随机化，使程序的运行结果固定不变。但是即使每次运行中的同一时刻其状态（寄存器、内存）都是固定不变的，我们也很难对他做分析，唯一方法是用调试器获得上下文，分析中的数据不好保存，实现起来也未必比记录+重放简单，再加上分析时几乎必须中止程序运行，可能导致问题。
2. 记录程序的外部输入和初始状态，用于重放。使用angr+unicorn进行重放。
3. 此时我们能够到达记录的那一次执行中的任意状态。到达目标状态然后获取数据，即可分析。