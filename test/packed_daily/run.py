#encoding=utf-8
#usr/local/env python3
# import需要的依赖
import sys
import os
sys.path.append("../../source/")
import parse_helpers
import replayer
import angr
import claripy
from imp import reload
from report.gen_html import generate_report

# 创建项目
p = replayer.Replayer("daily", "output.txt", "maps.62587", new_syscall = True)


def run():
    # 选择开启堆内存分析与信息泄漏分析
    p.enable_analysis([ "heap_analysis", "leak_analysis"])
    # 开始分析
    p.do_analysis()
    # 生成报告
    p.generate_report()

if __name__ == "__main__":
    run()


