import angr
from pwnlib.elf.elf import ELF

# TODO: test this function
class got_analysis(object):
    def __inif__(self, project):
        self.project = project

    def do_analysis(self):
        # first we resolve all imported symbols' addr
        main = self.project.elfs["main"]
        orirgin_got = {}
        exploited_got = {}
        for sym in main.got:
            # how to judge which file a symbol belongs to ??? 
            # XXX: now just iter over all objects
            for libname, obj in self.project.elfs.items():
                if libname == "main":
                    continue
                if sym in obj.symbols:
                    origin_got[sym] = obj.symbols[sym]
                    break

            # then save exploited got to dict
            addr = main.got[sym]
            sym_addr = self.project.exploied_state.memory.load(addr, 8, endness = 'Iend_LE')
            assert(sym_addr.concrete)
            sym_addr = sym_addr.args[0]
            exploited_got[sym] = sym_addr
        
        self.origin_got = origin_got
        self.exploited_got = exploited_got
        
        # then compare addr with exploited state
        assert(len(origin_got) == len(exploited_got))
        for sym, addr in exploited_got.items():
            # check if addr matched, or the symbol haven't been resolved 
            if origin_got[sym] == addr:
                continue
            elif main.plt[sym] == addr:
                continue
            else:
                #TODO: do report
                print("Found got mismatch: symbol %s with addr %s" % (sym, hex(addr)) )
                pass

            
        
