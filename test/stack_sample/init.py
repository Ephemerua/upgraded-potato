#usr/local/env python3

import sys

sys.path.append("../../source/")

import source.parse_helpers
import source.replayer
import angr
import claripy
from source.call_analysis import *
from imp import reload



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
    p = source.replayer.Replayer("test", "./testinput.txt", "maps.test.55146")

    # state = p.get_entry_state()
    # simgr = p.get_simgr()
    c = call_analysis(p)
    c.do_analysis()

def full_reload():
    reload(parse_helpers)
    reload(replayer)
    reload(analyser)
    full_init()


full_init()

