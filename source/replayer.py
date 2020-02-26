# 

import angr
import sys
import copy

LOGGER_PROMPT = b"$LOGGER$"
from helpers import *


#p = angr.Project("./aa", main_opts = main_opts, lib_opts = lib_opts,auto_load_libs=True, use_sim_procedures=False )
#state = p.factory.entry_state(mode="tracing", stdin=sim_file)


class Replayer(object):
    '''
    wrapper for angr project
    '''
    __entry_state = 0
    __proj = 0
    __sim_file = 0
    def __init__(self):
        pass

    def __init__(self, path_to_target, path_to_log, path_to_map, check_sat = False):
        # construct the angr.Project, loader's options must be set at first
        target_name = path_to_log.split(r"/")[-1]
        main_opts, lib_opts = parse_maps_from_file(path_to_map, target_name)
        self.__proj = angr.Project(path_to_target, main_opts = main_opts, lib_opts = lib_opts, \
            auto_load_libs=True, use_sim_procedures=False )

        # contruct sim_file, and save an entry_state as backup
        self.__sim_file = parse_log_from_file(path_to_log)
        self.__entry_state = self.__proj.factory.entry_state(mode="tracing", stdin=self.__sim_file)

        if check_sat:
            self.check_sat()
    
    def get_entry_state(self):
        # state can't be modified
        return self.__entry_state

    def get_project(self):
        return self.__proj
    
    def get_sim_file(self):
        return self.__sim_file

    def check_sat(self):
        '''
        simpackets sometimes fails, so do check 
        '''
        simgr = self.__proj.factory.simgr(self.__entry_state)
        simgr.run()
        if len(simgr.deadended) > 1:
            print("More than one path is replayed...")
        return True

        








if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: replay.py path-to-binary path-to-log")

    binary = sys.argv[1]
    log = sys.argv[2]

    log_input = []
    with open(log, "rb") as f:
        log_input = f.read().split(LOGGER_PROMPT)
    
    if not log_input:
        print("No log file provided.")
        exit(0)

    sim_stdin = angr.SimPackets("sim-stdin")
    sim_stdin.content = log_input



