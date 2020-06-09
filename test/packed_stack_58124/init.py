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

p = replayer.Replayer("stack", "./sample.txt", "maps.stack.58124")
simgr = p.get_simgr()
state = p.get_entry_state()

def run():
    p.enable_analysis(["heap_analysis", "got_analysis", "leak_analysis", "call_analysis"])
    p.do_analysis()
    p.generate_report()

