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
    cfg_seqence = []

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
    
    def do_track(self):
        simgr = self.replayer.get_simgr()
        simgr.run()
        state = simgr.deadended[0]
        self.cfg_seqence = list(final_state.history.bbl_addrs)

        # no history?
        assert(len(self.cfg_seqence) > 1)

        last_addr = self.cfg_seqence[0]
        for addr in self.cfg_seqence[1:]:
            self.cfg.add_edge(last_addr, addr)
            last_addr = addr


    # def do_track(self):
    #     simgr = self.replayer.get_simgr()
    #     while (simgr.active):
    #         # do step
    #         simgr.step()

    #         # if we run into a syscall that angr cannot handle, there will be 2 active state
    #         # use state.solver to check which state succeeds and stash another one
    #         if len(simgr.active)>1:
    #             temp = simgr.active[0].regs.rax.args[0]
    #             if "syscall_stub" in temp:
    #                 print("Run into a syscall stub. Stash failed state.")
    #                 simgr.move(from_stash="active", to_stash="deprecated", filter_func = _deprecate_state)
    #             else:
    #                 # only use the first active... leave check to user
    #                 print("Found more than one path! ")
    #                 simgr = p.factory.simgr(simgr.active[0])
            
    #         # check the state goes to deadended
    #         if  not simgr.active and simgr.deadended:
    #             final_state = simgr.deadended[0]
    #             # this part is not well documented.
    #             # in unicorn mode simgr.step() runs many blocks, 
    #             # all block addrs are logged in history.bbl_addrs
    #             self.cfg_seqence = list(final_state.history.bbl_addrs)
    #             last_addr = self.cfg_seqence[0]
    #             assert(len(self.cfg_seqence) > 1)

    #             # generate cfg
    #             for addr in self.cfg_seqence[1:]:
    #                 self.cfg.add_edge(last_addr, addr)
    #                 last_addr = addr

                

                
        

    









    

        
            
    
