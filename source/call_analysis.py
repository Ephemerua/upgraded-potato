def call_cb_constructor(ana):
    def call_callback(state):
        ret_addr = state.memory.load(state.regs.rsp, 8, endness = 'Iend_LE')
        print(ret_addr)
        print("now at", state.regs.rip)
        assert(ret_addr.concrete)
        ret_addr = ret_addr.args[0]
        ana.call_stack.append(ret_addr)
        ana.call_track.append((state.regs.rip.args[0],'call'))
    return call_callback

def ret_cb_constructor(ana):
    def ret_callback(state):
        ret_origin = 0
        ret_addr = state.regs.rip
        assert(ret_addr.concrete)
        ret_addr = ret_addr.args[0]
        ana.call_track.append((ret_addr, 'ret'))
        print("return to 0x%x" % ret_addr)
        if ana.call_stack:
            ret_origin = ana.call_stack[-1]
        else:
            print("Found unrecorded return 0x%x" % ret_addr)
            ana.abnormal_calls.append({"at":state.history.bbl_addrs[-2], "to":ret_addr, "type":"unrecorded"})
        if ret_origin == ret_addr:
            ana.call_stack.pop()
        else:
            print("Found strange return to 0x%x" % ret_addr)
            ana.abnormal_calls.append({"at":state.history.bbl_addrs[-2], "to":ret_addr, "type":"mismatch"})

    return ret_callback


class call_analysis(object):
    """
    FIXME: sometimes bp won't be fired, why?????
    Set bp on call and return, compare the address called and returned to, 
    so we can find stack's return address overflow.

    :ivar project:          project
    :ivar call_stack:       used to compare return address
    :ivar abnormal_calls:   record mismatch or abnormal return
    :ivar call_track:       tracks call info
    """
    def __init__(self, project):
        self.project = project
        self.call_stack = []
        self.abnormal_calls = []
        self.call_track = []
        self.call_cb = call_cb_constructor(self)
        self.ret_cb = ret_cb_constructor(self)

    def do_analysis(self):
        """
        do the job
        XXX: could we merge this to avoid simgr.run() again?
        """
        state = self.project.get_entry_state()
        print(state.inspect.b("call", when = angr.BP_AFTER, action = self.call_cb))
        print(state.inspect.b("return", when = angr.BP_AFTER, action = self.ret_cb))
        simgr = self.project.factory.simgr(state)
        simgr.run()
