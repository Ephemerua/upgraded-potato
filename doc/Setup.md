## 不使用docker
环境使用ubuntu 16.04
其他直接使用setup.sh即可。

## 使用docker
```
docker pull skysider/pwndocker
docker run --privileged  -it -v <path-to-your-work-dir>:/ctf/work  -p  23946:23946 --cap-add=SYS_PTRACE  skysider/pwndocker

```
之后在docker里面跑setup.sh