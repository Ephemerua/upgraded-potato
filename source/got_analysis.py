import angr
from pwnlib.elf.elf import ELF
import copy
import gc


# TODO: test this function
class got_analysis(object):
    def __init__(self, project):
        self.project = project
    
    def _resolve_mismatch(self, addr):
        # first find which object the addr belongs to
        maps = self.project.maps
        found_obj = 0
        for obj in maps:
            for seg in maps[obj]:
                if addr >= seg["start"] and addr <=seg["end"]:
                    found_obj = obj
                else:
                    continue
        
        if found_obj == 0:
            print("Cannot find symbol of addr %s." % hex(addr))
            return None
        
        # now try to find the symbol name
        obj = self.project.elfs[found_obj]
        symbols = {v:k for k, v in obj.symbols.items()}
        addrs = [ i for i in symbols]
        addrs_diff = [ abs(i-addr) for i in addrs]
        idx = addrs_diff.index(min(addrs_diff))
        return symbols[addrs[idx]], found_obj




    def do_analysis(self):
        # first we resolve all imported symbols' addr
        assert(self.project.exploited_state)
        main = self.project.elfs["main"]
        origin_got = {}
        exploited_got = {}
        for sym in main.got:
            # how to judge which file a symbol belongs to ??? 
            # XXX: now just iter over all objects
            for libname, obj in self.project.elfs.items():
                if libname == "main":
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
                    #TODO: do report
                    print("Found got mismatch: symbol %s with addr %s" % (sym, hex(addr)) )
                    resolve_result = self._resolve_mismatch(addr)
                    if resolve_result:
                        print("which is func %s in file %s" % (resolve_result[0], resolve_result[1]))

            
        
