#usr/local/env python3

import sys
import os

sys.path.append("../../source/")

import parse_helpers
import replayer
import angr
import claripy
from imp import reload
from report.gen_html import generate_report

# os.system("../../set-aslr.sh off")


# p = replayer.Replayer("easyheap", "./sample.txt", "maps.8998")
#
# state = p.get_entry_state()
# simgr = p.get_simgr()


if __name__=="__main__":
    # p.enable_analysis(["heap_analysis", "got_analysis", "leak_analysis", "call_analysis"])
    # p.do_analysis()
    generate_report('./easyheap', analysis_path='./analysis.log')
    

