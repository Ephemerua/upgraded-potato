import angr
from pwnlib.elf.elf import ELF
import copy
import gc
from symbol_resolve import symbol_resolve
import os
from analysis import register_ana
import logger
from util.info_print import stack_backtrace, printable_backtrace
from common import *

# TODO: test this function
class got_analysis(object):
    """
    Compare exploited_state's got with original func address.
    If got is not modified, it should point to the function, or plt stub in elf. 
    """
    def __init__(self, project):
        self.project = project
        self.symbol_resolve = symbol_resolve(project)
        self.report_logger = logger.get_logger(__name__)
        self.mismatch = {}
    
    def result_str(self):
        log_str = ""
        for k,v in self.mismatch.items():
            log_str += "%s: %s" %(k, hex(v["addr"]))
            if "sym" in v:
                log_str += " -> %s\n" % v["sym"]
            else:
                log_str += "\n"
        return log_str
    
    def track_got(self):
        if self.mismatch == []:
            return
        main = self.project.elfs[self.project.target]
        ana = self
        state = self.project.get_entry_state()
        #state.options.discard("UNICORN")
        for sym in self.mismatch:
            addr = main.got[sym]
            def got_track_bp(state):
                nonlocal ana, sym, addr
                bt = printable_backtrace(stack_backtrace(state))
                changed = state.memory.load(addr, 8 , endness = "Iend_LE")
                changed = BV2Int(changed)
                message = "Found write to got table: %s" % sym
                ana.report_logger.warn(message, backtrace = bt)
            
            state.inspect.b("mem_write", action = got_track_bp, when = angr.BP_AFTER,\
                mem_write_address=addr )

        simgr = self.project.factory.simgr(state)
        simgr.run()


    def do_analysis(self):
        """
        Do the job.
        """
        self.report_logger.info("Got analysis started.")
        if not self.project.exploited_state:
            self.report_logger.warning("Exploited state haven't been set! Do replay now...?")
            simgr = self.project.get_simgr()
            simgr.run()
        assert(self.project.exploited_state)
        main = self.project.elfs[self.project.target]
        # save 'correct' got in origin_got
        # save exploited_state's got to exploited_got
        # e.g. xxx_got['puts'] = 0xdeadbeef
        origin_got = {}
        exploited_got = {}
        for sym in main.got:
            # how to judge which file a symbol belongs to ??? 
            # XXX: now just iter over all objects
            for libname, obj in self.project.elfs.items():
                if libname == self.project.target:
                    continue
                if sym in obj.symbols:
                    if sym in origin_got:
                        origin_got[sym].append(obj.symbols[sym])
                    else:
                        origin_got[sym] = [obj.symbols[sym]]
                    

            # then save exploited got to dict
            addr = main.got[sym]
            sym_addr = self.project.exploited_state.memory.load(addr, 8, endness = 'Iend_LE')
            assert(sym_addr.concrete)
            sym_addr = sym_addr.args[0]
            exploited_got[sym] = sym_addr
        
        self.origin_got = origin_got
        self.exploited_got = exploited_got
        
        # then compare addr with exploited state
        assert(len(origin_got) == len(exploited_got))
        for sym, addr in exploited_got.items():
            # check if addr matched, or the symbol haven't been resolved 
            # don't track 0 addr
            if addr == 0:
                continue
            if addr in origin_got[sym]:
                continue
            elif sym in main.plt:
                if main.plt[sym] == addr:
                    continue
                else:
                    resolve_result = self.symbol_resolve.reverse_resolve(addr)
                    self.mismatch[sym] = {"addr":addr}
                    if resolve_result:
                        self.report_logger.info("GOT mismatch", symbol = sym, addr = addr, func = resolve_result[0], file = resolve_result[2])
                    else:
                        self.report_logger.info("GOT mismatch", symbol = sym, addr = addr)
        self.track_got()
        self.report_logger.info("Got analysis done.")
            

register_ana('got_analysis', got_analysis)            
        
