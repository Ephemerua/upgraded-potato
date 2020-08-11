import angr
import claripy
import base64


class syscall_dispatcher(angr.SimProcedure):
    def __init__(self, sysno, name = ""):
        super().__init__()
        print("%d sd inited!!!!!" % sysno)
        self.sysno = sysno
        self.posix_cb = []
        self.name = name
        self.is_stub = False
        

    def set_callinfo(self, syscall_info):
        self.syscall_info = syscall_info
        assert(len(syscall_info)&1 == 0)

    def __repr__(self):
        if 'resolves' in self.kwargs:
            return '<Success Syscall stub (%s)>' % self.kwargs['resolves']
        elif self.name:
            return '<Syscall Dispatcher for %s>' % self.name
        else:
            return '<Syscall Dispatcher for %d>' % self.sysno


    def next_info(self):
        idx = dispatch_index[self.sysno]
        result = self.syscall_info[idx:idx+2]
        dispatch_index[self.sysno] += 2
        assert(result[1]["is_result"])
        return result
    
    def recover_memory(self, mem_change):
        content = base64.b64decode(mem_change["content"])
        size = mem_change["size"]
        addr = mem_change["addr"]
        print("recovering to %#x with size %#x" %(addr, size))
        assert(len(content) == size)
        self.state.memory.store(addr, claripy.BVV(content))

    def log(self):
        print("call to %d\n" %self.sysno)

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

        if rbp == state_rbp and rip == state_rip and \
            rdi == state_rdi and rsi == state_rsi and \
            rdx == state_rdx:
            return 1
        else:
            return 0

    # default run for syscall dispatcher    
    def run(self, resolves=None):
        # angr's template
        self.resolves = resolves  # pylint:disable=attribute-defined-outside-init
        self.successors.artifacts['resolves'] = resolves

        # true run func
        self.log()
        call_info, ret_info = self.next_info()
        for mem_change in ret_info["mem_changes"]:
            self.recover_memory(mem_change)

        return claripy.BVV(ret_info["rax"], 64)


class open_dispatcher(syscall_dispatcher):
    def run(self, p_addr):
        self.log()
        strlen = angr.SIM_PROCEDURES['libc']['strlen']
        p_strlen = self.inline_call(strlen, p_addr)
        p_expr = self.state.memory.load(p_addr, p_strlen.max_null_index, endness='Iend_BE')
        path_state = self.state.solver.eval(p_expr, cast_to=bytes)

        call_info, ret_info = self.next_info()
        rdi = call_info["rdi"]
        p_strlen = self.inline_call(strlen, rdi)
        p_expr = self.state.memory.load(rdi, p_strlen.max_null_index, endness='Iend_BE')
        path_log = self.state.solver.eval(p_expr, cast_to=bytes)

        if path_log == path_state:
            fs_struct = {"path": path_log, "type":"file", "content":[], "last_fd":ret_info["rax"]}
            self.state.project.fake_fs.append(fs_struct)
            self.state.project.fdset[ret_info["rax"]] = len(self.state.project.fake_fs) - 1
        else:
            print(path_log, path_state)

        return claripy.BVV(ret_info["rax"], 64)

class socket_dispatcher(syscall_dispatcher):
    def run(self):
        self.log()
        call_info, ret_info = self.next_info()
        fs_struct = {"path": "", "type": "socket", "content":[], "last_fd":ret_info["rax"]}
        self.state.project.fake_fs.append(fs_struct)
        self.state.project.fdset[ret_info["rax"]] = len(self.state.project.fake_fs) - 1
        return claripy.BVV(ret_info["rax"], 64)


class read_dispatcher(syscall_dispatcher):
    def run(self, fd, buf, size):
        self.log()
        call_info, ret_info = self.next_info()
        assert(fd.args[0] == call_info["rdi"])
        assert(size.args[0] == call_info["rdx"])

        fs_struct = self.state.project.fake_fs[self.state.project.fdset[fd.args[0]]]
        mem_change = ret_info["mem_changes"][0]
        mem_change["addr"] = buf.args[0]
        self.recover_memory(mem_change)
        if fs_struct:
            fs_struct["content"].append(b"-" + base64.b64decode(mem_change["content"]))

        return claripy.BVV(ret_info["rax"], 64)

class recvfrom_dispatcher(read_dispatcher):
    pass

class recvmsg_dispatcher(read_dispatcher):
    def run(self, fd, buf, size):
        self.log()
        call_info, ret_info = self.next_info()
        assert(fd.args[0] == call_info["rdi"])
        assert(size.args[0] == call_info["rdx"])

        fs_struct = self.state.project.fake_fs[self.state.project.fdset[fd.args[0]]]
        mem_change = ret_info["mem_changes"][0]
        if fs_struct:
            fs_struct["content"].append(b"-" + base64.b64decode(mem_change["content"]))

        for mem_change in ret_info["mem_changes"]:
            self.recover_memory(mem_change)

class write_dispatcher(syscall_dispatcher):
    def run(self, fd, buf, size):
        self.log()
        call_info, ret_info = self.next_info()
        assert(fd.args[0] == call_info["rdi"])
        if (size.args[0]!= call_info["rdx"]):
            print("callsite rdx: %#x, logged rdx: %#x" % (size.args[0], call_info["rdx"]))

        mem_change = ret_info["mem_changes"][0]
        print(ret_info)
        fs_struct = self.state.project.fake_fs[self.state.project.fdset[fd.args[0]]]
        if fs_struct:
            fs_struct["content"].append(b"+" + base64.b64decode(mem_change["content"]))

        return claripy.BVV(ret_info["rax"], 64)

class sendto_dispatcher(write_dispatcher):
    pass

class sendmsg_dispatcher(write_dispatcher):
    pass

class getrandom_dispatcher(syscall_dispatcher):
    def run(self, buf, size):
        self.log()
        call_info, ret_info = self.next_info()

        mem_change = ret_info["mem_changes"][0]
        mem_change["addr"] = buf.args[0]
        self.recover_memory(mem_change)

        return claripy.BVV(ret_info["rax"], 64)



dispatchers = {0 : read_dispatcher(0),
              1 : write_dispatcher(1),
              2 : open_dispatcher(2),
              41 : socket_dispatcher(41),
              43 : socket_dispatcher(43),
              44 : sendto_dispatcher(44),
              46 : sendmsg_dispatcher(46),
              45 : recvfrom_dispatcher(45),
              47 : recvmsg_dispatcher(47),
              318 : getrandom_dispatcher(318),
                }

dispatch_index = {}

for i in dispatchers:
    dispatch_index[i] = 0