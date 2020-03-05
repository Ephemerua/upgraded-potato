# -*- coding:utf-8 -*-
import angr
import claripy
import replayer
import copy
import networkx as nx

proj = 0
_proj_bak = 0

def _deprecate_state(state):
    rax = state.solver.eval(state.regs.rax)
    # just consider rax != 0 means it failed
    if rax:
        return True
    return False

class Analyser(object):
    entry_state = 0
    hooks = []
    cfg = 0
    cf_seqence = []

    # FIXME: 最好生成一个新的project和state
    def __init__(self, re):
        if not isinstance(re, replayer.Replayer):
            raise TypeError("Not an instance of Replayer.")
        self.entry_state = re.get_entry_state()
        proj = re.get_project()
        _proj_bak = copy.deepcopy(proj)
        if not self.entry_state or not proj:
            raise ValueError("Replayer not initialized.")
        self.replayer = re
        self.cfg = nx.Graph()
    
    def track_cfg(self, use_hex = False):
        simgr = self.replayer.get_simgr()

        # initial rip
        last_ip = simgr.active[0].regs.rip.args[0]
        if use_hex:
            last_ip = hex(last_ip)
        self.cf_seqence.append(last_ip)


        while (simgr.active):
            # do step
            simgr.step()

            # if we run into a syscall that angr cannot handle, there will be 2 active state
            # use state.solver to check which state succeeds and stash another one
            if len(simgr.active)>1:
                temp = simgr.active[0].regs.rax.args[0]
                if "syscall_stub" in temp:
                    print("Run into a syscall stub. Stash failed state.")
                    simgr.move(from_stash="active", to_stash="deprecated", filter_func = _deprecate_state)
                else:
                    print("We need check why there are different paths!")
                    return simgr
            
            # check the state goes to deadended
            if  not simgr.active and simgr.deadended:
                new_ip = simgr.deadended[0].regs.rip.args[0]
            else:
                new_ip = simgr.active[0].regs.rip.args[0]

            # do record
            if use_hex:
                new_ip = hex(new_ip)
            self.cfg.add_edge(last_ip, new_ip)
            self.cf_seqence.append(new_ip)
            last_ip = new_ip
        
        return simgr









    

        
            
    
