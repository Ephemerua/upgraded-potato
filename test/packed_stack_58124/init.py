#usr/local/env python3

import sys

sys.path.append("../../source/")

import parse_helpers
import replayer
import angr
import claripy
from call_analysis import *
from heap_analysis import *
from got_analysis import *
from imp import reload
from report.gen_html import *


def memory_sum(file):
    f = open(file, "r")
    maps = f.read()
    m_sum = 0
    for line in maps:
        if line=="":
            continue
        line = line.split(" ")[0]
        mem = [int(i,16) for i in line.split("-")]
        m_sum += mem[1]-mem[0]
        
state = 0
simgr = 0
p = 0
before_malloc = 0


def full_init():
    global state, simgr, p, before_malloc
    p = replayer.Replayer("stack1", "./sample.txt", "maps.stack.58124")
    p.enable_analysis(["heap_analysis", "call_analysis", "leak_analysis", "got_analysis"])
    p.do_analysis()
    generate_report('./stack1', got_log_path='./got_analy.log', leak_log_path='./leak_analy.log', \
                    heap_log_path='./heap_analy.log', call_log_path='./call_analy.log')


def full_reload():
    reload(parse_helpers)
    reload(replayer)
    reload(analyser)
    full_init()


full_init()

