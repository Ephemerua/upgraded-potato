import angr
from pwnlib.elf.elf import ELF
import copy
import gc
from symbol_resolve import symbol_resolve
import logging
from pythonjsonlogger import jsonlogger
import os
from analysis import register_ana


# TODO: test this function
class got_analysis(object):
    """
    Compare exploited_state's got with original func address.
    If got is not modified, it should point to the function, or plt stub in elf.
    """

    def __init__(self, project):
        self.project = project
        self.symbol_resolve = symbol_resolve(project)
        self.mismatch = {}

        self.log_path = os.path.join(project.target_path, "got_analy.log")
        self.report_logger = logging.getLogger('got_analysis')
        self.report_logger.setLevel(logging.DEBUG)
        self.report_logger_handle = logging.FileHandler(self.log_path, mode="w")
        self.report_logger_handle.setFormatter(jsonlogger.JsonFormatter('%(message)%(levelname)%(asctime)'))
        # self.report_logger_handle.setFormatter(jsonlogger.JsonFormatter('%()'))
        self.report_logger.addHandler(self.report_logger_handle)

    def _resolve_mismatch(self, addr):
        """
        Deprecated function to do the resolve.
        """
        # first find which object the addr belongs to
        maps = self.project.maps
        found_obj = 0
        for obj in maps:
            for seg in maps[obj]:
                if addr >= seg["start"] and addr <= seg["end"]:
                    found_obj = obj
                else:
                    continue

        if found_obj == 0:
            # print("Cannot find symbol of addr %s." % hex(addr))
            self.report_logger.warning("Cannot find symbol of addr %s." % hex(addr))
            return None

        # now try to find the symbol name
        found_obj = found_obj.split('/')[-1]  # TEST: use filename, not path
        obj = self.project.elfs[found_obj]
        symbols = {v: k for k, v in obj.symbols.items()}
        addrs = [i for i in symbols]
        addrs_diff = [abs(i - addr) for i in addrs]
        idx = addrs_diff.index(min(addrs_diff))
        return symbols[addrs[idx]], found_obj

    def result_str(self):
        log_str = ""
        for k, v in self.mismatch.items():
            log_str += "%s: %s" % (k, hex(v["addr"]))
            if "sym" in v:
                log_str += " -> %s\n" % v["sym"]
            else:
                log_str += "\n"
        return log_str

    def do_analysis(self):
        """
        Do the job.
        """
        # first we resolve all imported symbols' addr
        self.report_logger.info("Got analysis started.")
        if not self.project.exploited_state:
            self.report_logger.warning("Exploited state haven't been set! Do replay now...?")
            simgr = self.project.get_simgr()
            simgr.run()
        assert (self.project.exploited_state)
        main = self.project.elfs[self.project.target]
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
            sym_addr = self.project.exploited_state.memory.load(addr, 8, endness='Iend_LE')
            assert (sym_addr.concrete)
            sym_addr = sym_addr.args[0]
            exploited_got[sym] = sym_addr

        self.origin_got = origin_got
        self.exploited_got = exploited_got

        # then compare addr with exploited state
        assert (len(origin_got) == len(exploited_got))
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
                    # TODO: do report
                    # print("Found got mismatch: symbol %s with addr %s" % (sym, hex(addr)) )
                    got_dict = {'mismatch': sym, 'addr': hex(addr), \
                                'function': "", 'file': ""}
                    self.report_logger.warning("Found got mismatch: symbol %s with addr %s" % (sym, hex(addr)))
                    resolve_result = self.symbol_resolve.reverse_resolve(addr)
                    self.mismatch[sym] = {"addr": addr}
                    if resolve_result:
                        self.mismatch[sym]["sym"] = resolve_result[0]
                        # print("which is func %s in file %s" % (resolve_result[0], resolve_result[2]))
                        self.report_logger.warning(
                            "which is func %s in file %s" % (resolve_result[0], resolve_result[2]))
                        got_dict['function'] = resolve_result[0]
                        got_dict['file'] = resolve_result[2]
                    got_dict["record"] = "true"
                    self.report_logger.info("[*]recording...", extra=got_dict)

        self.report_logger.info("Got analysis ended.")
        if self.mismatch:
            log_str = "\nFound %d mismatch entry: \n" % len(self.mismatch)
            log_str += self.result_str()
            self.report_logger.info(log_str)


register_ana('got_analysis', got_analysis)

