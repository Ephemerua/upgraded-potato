import angr
from replayer import fetch_str
from  util.info_print import stack_backtrace, printable_backtrace
import logging
import os
"""
Set write bp on return address in stack.
TODO: get rop chain info

ROP usually calls other funcs to leak address and do other works, but the funcs called
in ROP will call other funcs recursivly, so how to judge if we should look into the calls
during ROP?

Return address changed => ret to somewhere => do a strange call X()=> 
1. call , call and call(libc func always have a deep call stack) => return to the X()'s 
caller => continue ROP attack

2. call other func, and overflow happens in the callee => other ROP operations

So there seems to be 2 situation: ROP callee just do some work, return and then continue ROP caller, 
or ROP callee(or its callee) will result in an overflow, continue attack but not return to ROP caller

Idea:
1. If overflow happens, save overflow position, so we can identify the return by the depth
2. set a track depth, track every call after step 1's return
For calls after step1's return:
3.1 If it calls other funcs, record the call if its depth haven't meet the limit we set. 
3.2 If there's a new overflow(or mismatch(unlikely)), reset track depth, get information.

There's a bug in angr's return breakpoint.
To make it work, I edited angr/engines/successors.py, lineno 211 to this:

+ if state.history.jumpkind == 'Ijk_Ret':
+                state._inspect('return', BP_AFTER)
+                return
             while True:
                 cur_sp = state.solver.max(state.regs._sp) if state.has_plugin('symbolizer') else state.regs._sp
                 if not state.solver.is_true(cur_sp > state.callstack.top.stack_ptr):
                     break
                 #state._inspect('return', BP_BEFORE, function_address=state.callstack.top.func_addr)
                 state.callstack.pop()
                 #state._inspect('return', BP_AFTER)
"""

def bp_constructor(ana, addr, size = 8, callback = None):
    """
    construct a bp before given addr is written, get its origin value and modified value.
    record the addr to call_analysis.overflow_pos
    """
    def write_bp(state):
        target_addr = state.inspect.mem_write_address
        target_size = state.inspect.mem_write_length
        write_expr = state.inspect.mem_write_expr

        if type(target_addr) != int:
            target_addr = target_addr.args[0]
        if type(target_size) != int:
            target_size = target_size.args[0]
        
        # make sure the write covers our addr
        if (target_addr >= addr+size):
            return
        if (target_addr + target_size <=addr):
            return

        # break on BP_AFTER, so we only need to get the value we care about
        origin = state.memory.load(addr, 8, endness = 'Iend_LE').args[0]
        #print(write_expr)
        bt = stack_backtrace(state)
        backup = state.memory.load(target_addr, size)
        state.memory.store(target_addr, write_expr, disable_actions=True, inspect = False)
        modified = state.memory.load(addr, 8, endness = 'Iend_LE').args[0]
        ana.overflow_pos.add(addr)
        state.memory.store(target_addr, backup, disable_actions=True, inspect = False)
        if origin == modified:
            return
        # print("address %s changed from %s to %s" % (hex(addr), hex(origin), hex(modified) ))
        state.project.report_logger.info("address %s changed from %s to %s" % (hex(addr), hex(origin), hex(modified)))
        # print(printable_backtrace(bt))
        state.project.report_logger.info(printable_backtrace(bt))
        #print(state.callstack)
        return
    return write_bp


def call_args_x64(state):
    regs = state.regs
    a1 = regs.rdi
    a2 = regs.rsi
    a3 = regs.rdx
    # a4 = regs.r10
    # a5 = regs.r8
    # a6 = regs.r9
    return {'rdi':a1, 'rsi':a2, 'rdx':a3}#, a4, a5, a6

def __test_filter(s, value):
    if s:
        if '__gmon_start__' in s[0]:
            s = list(s)
            s[0] = 'sub_%x'% value
            s[1] = 0
    return s

def ret_info(state):
    result = ""
    ret_src = state.history.bbl_addrs[-1]
    ret_dst = state.regs.rip.args[0]
    args = call_args_x64(state)
    dst_symbol = state.project.symbol_resolve.reverse_resolve(ret_dst)
    dst_symbol = __test_filter(dst_symbol, ret_dst)
    src_symbol = state.project.symbol_resolve.reverse_resolve(ret_src)
    src_symbol = __test_filter(src_symbol, ret_src)

    result += "From"
    if src_symbol:
        result += " %s: %s + %d (%s)" %(src_symbol[2], src_symbol[0], src_symbol[1], hex(ret_src))
    else:
        result += " %s" % hex(ret_src)
    result += " to"
    if dst_symbol:
        result += " %s: %s + %d (%s)\n" %(dst_symbol[2], dst_symbol[0], dst_symbol[1], hex(ret_dst))
    else:
        result += " %s\n" % hex(ret_dst)

    block = state.block().capstone.insns
    result += "Insns:\n"
    for insn in block:
        result += '\t' + str(insn)+'\n'
    result += 'Args:\n'
    for reg, value in args.items():
        result += "\t%s: %s" % (reg, hex(value.args[0]))
        s = fetch_str(state, value)
        result += s
        s = state.project.symbol_resolve.reverse_resolve(value)
        if s:
            if '__gmon_start__' in s[0]:
                s = list(s)
                s[0] = 'sub_%x'% value.args[0]
                s[1] = 0
            result += " (%s + %d)" % (s[0], s[1])
        result += '\n'

    return result


def call_cb_constructor(ana, **kwargs):
    def call_callback(state):
        # get info, and do some record
        ret_addr = state.memory.load(state.regs.rsp, 8, endness = 'Iend_LE')
        rsp = state.regs.rsp.args[0]
        #print(ret_addr)
        #print("now at", state.regs.rip)
        assert(ret_addr.concrete)
        ret_addr = ret_addr.args[0]
        ana.call_stack.append(ret_addr)
        ana.call_history.append((state.regs.rip.args[0],'call'))

        # make a write bp on return address in case of overflow
        ana.ret_bps[rsp] = (state.inspect.b("mem_write", when = angr.BP_BEFORE, action = bp_constructor(ana, rsp, 8)))
        
        # should we track this call?
        if ana._last_depth < ana.track_depth:
            # control flow has changed, log the call
            call_info = {'at':state.history.bbl_addrs[-1], \
                'to':state.inspect.function_address.args[0], \
                'type': 'call after overflow'}
            ana.abnormal_calls.append(call_info)
            ana._last_depth += 1
        return 
    return call_callback

def ret_cb_constructor(ana, **kwargs):
    """
    make a ret bp.

    1. compare the return address with address saved in call stack
    2. if not match, means we are in ROP/overflow condition
        reset the _last_depth now, cause we are in a new overflow
    """
    def ret_callback(state):
        # filter simprocedures
        at = state.history.bbl_addrs[-1]
        if at >> 12 == 0x3000:
            return
        ret_origin = 0
        ret_addr = state.regs.rip
        origin_rsp = state.regs.rsp.args[0] - 8
        assert(ret_addr.concrete)
        ret_addr = ret_addr.args[0]
        ana.call_history.append((ret_addr, 'ret'))
        #print("return to 0x%x" % ret_addr)
        # get the top of call_stack
        if ana.call_stack:
            ret_origin = ana.call_stack[-1]
            # compare the top wit ret_addr
            if ret_origin == ret_addr:
                ana.call_stack.pop()
                if ana._last_depth and ana.call_track:
                    ana._last_depth -= 1
                 
            else:
                # FIXME: only reset _last_depth on mismatching????
                # print("\nStrange return to 0x%x:" % ret_addr)
                state.project.report_logger.info("\nStrange return to 0x%x:" % ret_addr)
                ana._last_depth = 0
                ana.call_track = 1
                ana.abnormal_calls.append({"at":state.history.bbl_addrs[-1], "to":ret_addr, "type":"mismatch"})
                #TODO: get rop info here
                # print(ret_info(state))
                state.project.report_logger.info(ret_info(state))

        else:
            # no frame? must be rop
            # print("\nUnrecorded return to 0x%x" % ret_addr)
            state.project.report_logger.info("\nUnrecorded return to 0x%x" % ret_addr)
            ana.call_track = 1
            ana.abnormal_calls.append({"at":state.history.bbl_addrs[-1], "to":ret_addr, "type":"unrecorded"})
            #TODO: get rop info here
            # print(ret_info(state))
            state.project.report_logger.info(ret_info(state))


        # remove the breakpoint
        bp = ana.ret_bps.pop(origin_rsp, None)
        if bp:
            state.inspect.remove_breakpoint(event_type = 'mem_write', bp = bp)
        return

    return ret_callback




class call_analysis(object):
    """
    FIXME: sometimes bp won't be fired, why?????
    XXX: state.callstack plugin doesn't work under unciron
    Set bp on call and return, compare the address called and returned to, 
    so we can find stack's return address overflow.

    :ivar project:          project
    :ivar call_stack:       used to compare return address
    :ivar abnormal_calls:   record mismatch or abnormal return
    :ivar call_track:       tracks call info
    """
    def __init__(self, project, track_depth = 1):
        self.project = project
        self.call_stack = []
        self.abnormal_calls = []
        self.call_history = []
        self.call_cb = call_cb_constructor(self)
        self.ret_cb = ret_cb_constructor(self)
        self.bps = []
        self.ret_bps = {}
        self.call_track = 0
        self._last_depth = track_depth
        self.track_depth = track_depth
        self.overflow_pos = set()
        self.project.report_logger = logging.getLogger('call_analysis')
        self.project.report_logger.setLevel(logging.INFO)



    def do_analysis(self):
        """
        do the job
        XXX: could we merge this to avoid simgr.run() again?
        """
        file_handle = logging.FileHandler(os.path.join(self.project.target_path, "call_analy.log"), mode="w+")
        self.project.report_logger.addHandler(file_handle)

        state = self.project.get_entry_state()
        # XXX: unicorn engine at present cannot handle call/return breakpoint...
        state.options.discard("UNICORN")
        self.bps.append(state.inspect.b("call", when = angr.BP_AFTER, action = self.call_cb))
        self.bps.append(state.inspect.b("return", when = angr.BP_AFTER, action = self.ret_cb))
        simgr = self.project.get_simgr(state)
        simgr.run()



