# -*- coding:utf-8 -*-

import angr
import sys
import copy
from time import time
import claripy
import networkx
LOGGER_PROMPT = b"$LOGGER$"
from helpers import *
from exploited_state_hook import exploited_execve

#p = angr.Project("./aa", main_opts = main_opts, lib_opts = lib_opts,auto_load_libs=True, use_sim_procedures=False )
#state = p.factory.entry_state(mode="tracing", stdin=sim_file)


class Replayer(angr.project.Project):
    """
    Do the replay job.
    XXX: all unsupported syscall will always return 0

    :param binary:      path to the target binary
    :param log_path:    path to logged input
    :param map_path:    path to the memory map recorded at entry point

    :ivar exploited_state:  the final state when target it pwned
    :ivar input:        angr.SimPackets，contains the recorded input

    :ivar cfg:          target's cfg, with library func explored
    :ivar cfg_recorded: target's cfg, recorded during the exploit
    :ivar cfg_sequence: target's control flow sequence during the exploit

    :ivar hooked_addr:  list of addr been hooked
    """
    def __init__(self, binary, log_path, map_path):
        target_name = binary.split(r"/")[-1]
        main_opts, lib_opts, bp = parse_maps_from_file(map_path, target_name)

        self.cfg = 0
        self.cfg_recorded = 0
        self.cfg_seqence = 0

        self.hooked_addr = []

        self._main_opts = main_opts
        self._lib_opts = lib_opts
        self._bp = bp
        self.exploited_state = 0
        # input is the recorded stdin
        self.input = parse_log_from_file(log_path)

        # construct the project, load objects with recorded base addr
        super().__init__(binary, main_opts = main_opts, lib_opts = lib_opts, \
            auto_load_libs=True, use_sim_procedures=False)
        
        # replace unsupported syscall
        replace_stub(self)

        # FIXME: set the hook to detect pwned state??
        self.set_exploited_syscall("execve", exploited_execve())
    
    def get_entry_state(self):
        """
        Returns the state at entry point, with stdin set to recorded input
        """
        return self.factory.entry_state(mode="tracing", stdin=self.input)

    def get_simgr(self, from_state = None):
        """
        Returns the simgr at specific/entry state

        :param from_state:  start state of simgr
        """
        if from_state:
            return self.factory.simgr(from_state)
        else:
            return self.factory.simgr(self.get_entry_state())

    def navigate_to(self, addr, from_state = None):
        """
        Returns a state, which runs to specific addr

        :param addr:        target addr
        :param from_state:  start of simgr, default the entry_state
        """
        if from_state:
            state = from_state
        else:
            state = self.get_entry_state()

        simgr = self.factory.simgr(state)

        simgr.explore(find = addr)
        if simgr.stashes['found']:
            return simgr.found[0]
        return None

    def do_track(self):
        """
        Tracks control flow changes during the exploit.
        """
        simgr = self.get_simgr()
        simgr.run()
        state = simgr.deadended[0]
        self.cfg_seqence = list(state.history.bbl_addrs)
        self.cfg_recorded = networkx.Graph()

        # no history?
        assert(len(self.cfg_seqence) > 1)

        last_addr = self.cfg_seqence[0]
        for addr in self.cfg_seqence[1:]:
            self.cfg_recorded.add_edge(last_addr, addr)
            last_addr = addr

    def generate_cfg(self):
        """
        Generates the original cfg.
        XXX: Lib funcs are included.
        """
        self.cfg = self.analyses.CFGFast(force_complete_scan=False)
        return self.cfg

    def set_exploited_syscall(self, name, procedure):
        """
        Set a syscall sim_procedure. During replay, it will check the params passed to it,
        to decide if target is pwned.
        exploited_state will be set.

        :param name:        syscall name
        :param procedure:   sim procedure to do the work
        """
        procedure.project = self
        self.simos.syscall_library.procedures[name] = procedure

    def set_exploited_func(self, addr, hook_func):
        """
        Set a syscall sim_procedure. During replay, it will check the params passed to it,
        to decide if target is pwned.
        exploited_state will be set.

        :param addr:        addr to hook
        :param hook_func:   func to use
        """
        self.hook(addr, hook_func(self))
        self.hooked_addr.append(addr)



def stack_backtrace(state, depth = 'Max'):
    """
    Helper func to get stack backtrace.
    Do the same work as gdb's bt.

    :param state:   state to do bt
    :param depth:   bt depth
    """
    # gdb's backtrace records present rip in frame0, do the same with gdb
    result = [state.regs.rip]
    bp = state.regs.rbp
    frame_num = -1 if depth=='Max' else depths

    while bp.concrete and frame_num:
        frame_num -= 1
        # bp==0 means trace ends
        if (bp == 0).is_true():
            return result

        ret_addr = state.memory.load(bp+8, 8, endness = 'Iend_LE')
        bp = state.memory.load(bp, 8, endness = 'Iend_LE')
        # We have set uninited memory to zero, and ret_addr shouldn't be zero.
        if (ret_addr == 0).is_true():
            return result
        if (ret_addr > 0x7fffffffffff):
            return result
        result.append(ret_addr)







