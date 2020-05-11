#usr/local/env python3

import sys

sys.path.append("../../source/")

import helpers
from replayer import *
from heap_analysis import *
from imp import reload
from call_analysis import *
from leak_analysis import *
from got_analysis import *

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
    p = Replayer("easyheap", "./sample.txt", "maps.8998")
    # p.do_track()
    # h = heap_analysis(p)
    # h.do_analysis()

    # leak_analy = leak_analysis(p)
    # leak_analy.do_analysis()
    c = call_analysis(p)
    c.do_analysis()
    # p.do_track()
    # got_analy = got_analysis(p)
    # got_analy.do_analysis()

def full_reload():
    reload(helpers)
    reload(replayer)
    reload(analyser)
    full_init()


full_init()

