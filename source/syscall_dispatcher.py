import angr
import claripy
import base64


class syscall_dispatcher(angr.SimProcedure):

    def run(self, resolves=None):
        print("call to sysno %d" % self.sysno)

        self.resolves = resolves  # pylint:disable=attribute-defined-outside-init

        self.successors.artifacts['resolves'] = resolves

        call_info = self.syscall_info[self.syscall_idx]
        ret_info = self.syscall_info[self.syscall_idx+1]
        modify = self.check_call_info(call_info)
        assert(ret_info["is_result"])
        self.syscall_idx += 2

        ret = ret_info["rax"]
        print("ret: %#x"% ret)
        if ret_info["mem_changes"]:
            for mem_change in ret_info["mem_changes"]:
                if modify:
                    mem_change["addr"] = modify
                self.recover_memory(mem_change)
        return claripy.BVV(ret, 64)

    def __repr__(self):
        if 'resolves' in self.kwargs:
            return '<Success Syscall stub (%s)>' % self.kwargs['resolves']
        else:
            return '<Syscall Dispatcher for %d>' % self.sysno

    def recover_memory(self, mem_change):
        content = base64.b64decode(mem_change["content"])
        size = mem_change["size"]
        addr = mem_change["addr"]
        print("recovering to %#x with size %#x" %(addr, size))
        assert(len(content) == size)
        self.state.memory.store(addr, claripy.BVV(content))

    def check_call_info(self, call_info):
        rbp = call_info["rbp"]
        rip = call_info["rip"]
        rdi = call_info["rdi"]
        rsi = call_info["rsi"]
        rdx = call_info["rdx"]

        state_rbp = self.state.regs.rbp.args[0]
        state_rip = self.state.regs.rip.args[0]
        state_rdi = self.state.regs.rdi.args[0]
        state_rsi = self.state.regs.rsi.args[0]
        state_rdx = self.state.regs.rdx.args[0]


        #assert(rbp == state_rbp)
        #assert(rdi == state_rdi and rsi == state_rsi)

        if self.modify:
            return eval(self.modify)

        return 0

    def __init__(self, sysno, syscall_info, modify = ""):
        super().__init__()
        self.sysno = sysno
        self.syscall_info = syscall_info
        self.syscall_idx = 0
        if modify:
            self.modify = "state_" + modify
        else:
            self.modify = ""
        assert(len(syscall_info)&1 == 0)