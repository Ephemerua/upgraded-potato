"""
Analysis to find information leakage in exploited state.
Use heuristic way to find leaked address from exploited_state's stdout. It doesn't work well
in most situation :(
"""

import struct
from symbol_resolve import symbol_resolve
import logging
import os
from analysis import register_ana

class leak_analysis(object):
    """
    Use heuristic way to find leaked address from exploited_state's stdout.
    Assume each loaded object is samller than 16MB, so the higher 3 bytes in
    address is always the same with object's base addr.
    Also, low bytes of address is usually useless in exploit, so we check leaked higher 
    three bytes to find leak.

    XXX: if we have 140737349736160 in output, which is actually an address, how can we
    find out that?

    :ivar project:          project of the analysis
    :ivar leaked_addrs:     all address that could be leak in stdout(and others).
    :ivar symbol_resolve:   helper to get symbol name from address
    """
    def __init__(self, project):
        self.project = project
        self.symbol_resolve = symbol_resolve(project)
        self._prefixs = []
        self.leaked_addrs = []
        self._find_prefix()
        self.report_logger = logging.getLogger('leak_analysis')
        self.report_logger.setLevel(logging.INFO)
        self.log_path = os.path.join(project.target_path, "leak_analy.log")
        self.report_logger_handle = logging.FileHandler(self.log_path, mode="w+")
        self.report_logger.addHandler(self.report_logger_handle)
        


    def _find_prefix(self):
        maps = self.project.maps
        for obj, segs in maps.items():
            for seg in segs:
                # use high 3 bytes as prefix
                # XXX: this assumes every segment is smaller than 16MB
                prefix = (seg['start'] >> (4*6)) & 0xffffff
                if prefix == 0 or prefix == 0xffffff:
                    continue
                prefix = struct.pack("<I", prefix)[:3]
                self._prefixs.append(prefix)


        self._prefixs = list(set(self._prefixs))

    def _match_output(self, prefix, output):
        """
        find address with specific prefix in output
        """
        pos_list = []
        pos = output.find(prefix)
        end = len(output)
        while pos!=-1:
            pos_list.append(pos)
            pos = output.find(prefix, pos + 1, end) 

        
        #try to get full addr, and unpack
        for pos in pos_list:
            if pos + 3 > end:
                continue
            addr = output[pos-3:pos+3] + b'\x00\x00'
            addr = struct.unpack("<Q", addr)[0]
            self.leaked_addrs.append(addr)

        # TODO: do report
        for i in self.leaked_addrs:
            result = self.symbol_resolve.reverse_resolve(i)
            if result:
                # print("Found leaked addr: %s %x in lib %s" %(result[0], result[1], result[2]))
                self.report_logger.info("Found leaked addr: %s %x in lib %s" %(result[0], result[1], result[2]))
    
    def do_analysis(self):
        """
        do the job
        """
        if not self.project.exploited_state:
            # print("No exploited state to analyse!")
            self.report_logger.warning("No exploited state to analyse!")
            return
        output = self.project.exploited_state.posix.dumps(1)
        for prefix in self._prefixs:
            self._match_output(prefix, output)
    
register_ana('leak_analysis', leak_analysis)
