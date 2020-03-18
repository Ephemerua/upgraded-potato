import claripy
def bp_constructor(start_addr, size):
    def write_bp(state):
        target_addr = state.inspect.mem_write_address
        target_size = state.inspect.mem_write_length
        if isinstance(target_addr, int):
            target_addr = claripy.BVV(target_addr, 64)

        # print("addr: %s" % (target_addr))
        # print("size: ", target_size)
        if (target_addr >= start_addr + size).is_true() \
            or (start_addr >= target_addr + target_size).is_true():
            return
        #print("mem write to %s with length %s" % ((target_addr), (target_size)))
        if (target_addr + target_size > start_addr + size).is_true():
            print("Found overflow in chunk at %s, size %s with write starts at %s, size %s!"
             % (hex(start_addr), hex(size), target_addr, target_size))
            overflow_len = target_addr + target_size - (start_addr + size)
            overflow_len = overflow_len.args[0]
            print("Overflow length: %s", hex(overflow_len))
            overflow_content = state.inspect.mem_write_expr[overflow_len*8 - 1:0]
            print("Overflow length: %s, content: %s" % (hex(overflow_len), overflow_content))
        return
    return write_bp




def _malloc_hook(state):
    """
    malloc hook.
    Get size passed to malloc, and set a hook on caller's return address to get malloc's 
    return value.
    After getting the return value, unhook the return address.
    """
    # get return address and arg
    size = state.regs.rdi
    assert(size.concrete)
    size = size.args[0]
    size = ((size>>4)<<4) + 0x10

    rsp = state.regs.rsp
    assert(rsp.concrete)
    # malloc use rsp to save return address...
    ret_addr = state.memory.load(rsp, 8, endness = 'Iend_LE')
    assert(ret_addr.concrete)
    ret_addr = ret_addr.args[0]
    #print(hex(ret_addr))

    def _malloc_callback(state):
        # rax contains return address of malloc
        rax = state.regs.rax
        assert(rax.concrete)
        rax = rax.args[0]
        # TODO: do log
        print("Malloc called with size %s, returns addr %s" % (hex(size), hex(rax)))
        state.project.unhook(ret_addr)
        state.project.heap_analysis.add_chunk(rax, size)
        # set bp
        if rax - 0x10 in state.project.heap_analysis.bps:
            return 
        else:
            bp = state.inspect.b("mem_write", action = bp_constructor(rax - 0x10, size + 0x18))
            state.project.heap_analysis.bps[rax - 0x10] = bp

    assert(not state.project.is_hooked(ret_addr))
    state.project.hook(ret_addr, _malloc_callback)

def _calloc_hook(state):
    """
    Same with _malloc_hook
    """
    # get return address and arg
    count = state.regs.rdi
    assert(count.concrete)
    count = count.args[0]

    size = state.regs.rsi
    assert(size.concrete)
    size = size.args[0]
    size = ((size>>4)<<4) + 0x10


    rsp = state.regs.rsp
    assert(rsp.concrete)
    # malloc use rsp to save return address...
    ret_addr = state.memory.load(rsp, 8, endness = 'Iend_LE')
    assert(ret_addr.concrete)
    ret_addr = ret_addr.args[0]

    def _calloc_callback(state):
        # rax contains return address of malloc
        rax = state.regs.rax
        assert(rax.concrete)
        #rax = rax.args[0]
        # TODO: do log
        print("Calloc called with size %d, returns addr %s" % (size*count, hex(rax)))
        state.project.unhook(ret_addr)

    assert(not state.project.is_hooked(ret_addr))
    state.project.hook(ret_addr, _calloc_callback)

def _free_hook(state):
    """
    free hook.
    Use chunk's metadata to decide chunk size.
    """
    # get addr and chunk_size
    addr = state.regs.rdi
    assert(addr.concrete)
    addr = addr.args[0]

    size = state.memory.load(addr-8, 8, endness = 'Iend_LE')
    assert(size.concrete)
    size = size.args[0]
    size = (size >> 4)<<4
    print("Free called to free %s with size %s" % (hex(addr), hex(size)))
    # free also use rsp to save return value
    ret_addr = state.memory.load(state.regs.rsp, endness = 'Iend_LE')
    ret_addr = ret_addr.args[0]
    state.project.heap_analysis.del_chunk(addr, size)
    def _free_callback(state):
        state.project.heap_analysis.parse_arena(state)
        state.project.unhook(ret_addr)

    assert(not state.project.is_hooked(ret_addr))
    state.project.hook(ret_addr, _free_callback)





class heap_analysis(object):
    """
    Analyses heap operations.
    Hooks the top level api(malloc, free, etc.), get information and then use read/write
    breakpoints to do analysis.

    :ivar chunks_av:        dict of allocated chunks, indexed by address
    :ivar chunks_sv:        dict of allocated chunks, indexed by size
    :ivar abused_chunks:    list of chunks been abused, chunk sample: 
                            {"addr": 0x603000, "size":0x68, "type": abused_type}

    :ivar arenas:           list of thread_arena structs # TODO: haven't do the parse job

    :ivar bps:              read/write breakpoints. A dict indexed by bp addr.
    """
    def __init__(self, project, segments=[], ):
        self.project = project
        self.heap_segments = segments
        self.malloc_hook = _malloc_hook
        self.calloc_hook = _calloc_hook
        self.free_hook = _free_hook
        self.hooked_addr = []
        self.chunks_av = {}
        self.chunks_sv = {}
        self.abused_chunks = []
        self.arenas = []
        self.bps = {}
    
    def add_chunk(self, addr, size):
        # do log in chunks_av
        if addr in self.chunks_av:
            # why allocated again?
            sizes = self.chunks_av[addr]
            if isinstance(sizes, list):
                sizes.append(size)
            else:
                self.chunks_av[addr] = [sizes, size]
            self.abused_chunks.append({"addr":addr, "size":size, "type":"allocated mutiple times"})
        else:
            self.chunks_av[addr] = size
            
        # do log in chunks_sv
        if size in self.chunks_sv:
            self.chunks_sv[size].append(addr)
        else:
            self.chunks_sv[size] = [addr]

    def del_chunk(self, addr, size):
        # check if the chunk is allocated
        if addr in self.chunks_av:
            sizes = self.chunks_av[addr]
            # check if size matchess
            if isinstance(sizes, list):
                if size in sizes:
                    sizes.remove(size)
                    if sizes==[]:
                        self.chunks_av.pop(addr)
                else:
                    self.abused_chunks.append({"addr": addr, "size":size, "type":"freed with modified size"})
            # target chunk doesn't been alloced more than one time,
            # so sizes is an int
            elif size == sizes:
                self.chunks_av.pop(addr)
            # do log in chunks_sv
            if size in self.chunks_sv:
                if addr in self.chunks_sv[size]:
                    self.chunks_sv[size].remove(addr)
        else:
            # this chunk is not alloced by c/m/relloc
            self.abused_chunks.append({"addr":addr, "size": size, "type":"chunk not allocated is freed"})
    
    def enable(self):
        # hook heap api, save address to hooked_addr
        self.hooked_addr.append(self.project.hook_symbol("malloc", self.malloc_hook))
        self.hooked_addr.append(self.project.hook_symbol("free", self.free_hook))
        self.hooked_addr.append(self.project.hook_symbol("calloc", self.calloc_hook))

    def disable(self):
        # clean hooks by saved addr
        for i in self.hooked_addr:
            self.project.unhook(i)

    def parse_arena(self, state):
        pass
        




                









    
