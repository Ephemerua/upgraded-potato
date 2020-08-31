import angr
from pwnlib.elf.elf import ELF
import copy
import gc
from symbol_resolve import symbol_resolve
import os
from analysis import register_ana
import logger
from util.info_print import stack_backtrace, printable_callstack
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
        self.report_logger = 0
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
    
    def trace_got(self):
        if self.mismatch == []:
            return
        main = self.project.elfs[self.project.target]
        ana = self
        state = self.project.get_entry_state()
        state.options.discard("UNICORN")
        for sym in self.mismatch:
            addr = main.got[sym]
            def got_trace_bp(state):
                nonlocal ana, sym, addr
                bt = printable_callstack(state)
                changed = state.memory.load(addr, 8 , endness = "Iend_LE")
                changed = BV2Int(changed)
                message = "Found write to got table: %s" % sym
                ana.report_logger.warn(message, backtrace = bt, type='got_change', state_timestamp = state_timestamp(state))
            
            state.inspect.b("mem_write", action = got_trace_bp, when = angr.BP_AFTER,\
                mem_write_address=addr )

        simgr = self.project.factory.simgr(state)
        simgr.run()


    def do_analysis(self):
        """
        Do the job.
        """
        self.report_logger = logger.get_logger(__name__)

        self.report_logger.info("Got analysis started.", type='tips')
        if not self.project.exploited_state:
            self.report_logger.warning("Exploited state haven't been set! Do replay now...?", type='tips')
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
            if sym == "__gmon_start__":
                continue
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
            # don't trace 0 addr
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
                        message = "GOT mismatch: %s changed to %s%+d(%s)." % (sym, resolve_result[0], resolve_result[1], hex(addr))
                        self.report_logger.warn(message, got_entry_symbol = sym, modified_addr = addr, modified_to_func = resolve_result[0], modified_func_belongs_to = resolve_result[2], type='got_mismatch')
                    else:
                        message = "GOT mismatch: %s changed to %s." % (sym, hex(addr))
                        self.report_logger.warn(message, got_entry_symbol = sym, modified_addr = addr, type='got_mismatch')
        self.trace_got()
        self.report_logger.info("Got analysis done.", type='tips')
            

register_ana('got_analysis', got_analysis)            
        
