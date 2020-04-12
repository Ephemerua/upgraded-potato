import claripy
import angr
from structures import malloc_state


def bp_constructor(start_addr, size, debug = False):
    """
    construct an state.inspect.bp, record mem write to detect overflow
    """
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
        if debug:
            print("mem write to %s with length %s" % ((target_addr), (target_size)))
        if (target_addr + target_size > start_addr + size).is_true():
            print("Found overflow in chunk at %s, size %s with write starts at %s, size %s!"
             % (hex(start_addr), hex(size), target_addr, target_size))
            overflow_len = target_addr + target_size - (start_addr + size)
            overflow_len = overflow_len.args[0]
            #print("Overflow length: %s" % hex(overflow_len))
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
    # stack frame haven't been created, so return address is in rsp
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
        # TEST
        ms, arena_addr = get_malloc_state(state, rax)
        assert(ms)
        fastbin_check(state, ms, arena_addr)
        bin_check(state, ms, arena_addr)
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
    # stack frame haven't been created, so return address is in rsp
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
    # stack frame haven't been created, so return address is in rsp
    ret_addr = state.memory.load(state.regs.rsp, endness = 'Iend_LE')
    ret_addr = ret_addr.args[0]
    state.project.heap_analysis.del_chunk(addr, size)
    def _free_callback(state):
        state.project.heap_analysis.parse_arena(state)
        state.project.unhook(ret_addr)
        # TEST: to be tested
        ms, arena_addr = get_malloc_state(state, addr)
        assert(ms)
        fastbin_check(state, ms, arena_addr)
        bin_check(state, ms, arena_addr)

    assert(not state.project.is_hooked(ret_addr))
    state.project.hook(ret_addr, _free_callback)


def ptr_check(ptr, reverse_maps, state = None):
    page = ptr >> 12
    prot = -1
    if state:
        try:
            prot = state.memory.permissions(ptr)
            return prot.args[0]
        except angr.errors.SimMemoryMissingError:
            return -1
    else:
        if page in reverse_maps:
            return reverse_maps[page]
        else:
            return -1
    
def ptr_lookup(ptr, reverse_maps, state = None):
    prot = ptr_check(ptr, reverse_maps, state)
    if prot == -1:
        return -1
    else:
        if ptr in reverse_maps:
            return reverse_maps[ptr]
        else:
            return None

def get_malloc_state(state, addr = 0):
    """
    TODO: test this func
    get struct malloc_state from memory
    still we need the address of the struct
    """
    # __malloc_hook is a private symbol
    main_arena_addr = state.project.symbol_resolve.resolve("__malloc_hook")[0] + 0x10
    result = malloc_state()
    mem = state.memory.load(main_arena_addr, result.size)
    mem = mem.args[0].to_bytes(result.size, 'big')
    result.unpack(mem)
    main_arena = malloc_state()
    main_arena.unpack(mem)
    # if addr is in main thread's heap, addr shouldn't be on the same segment 
    # of malloc_state's address. But if it's on thread heap, addr should be on
    # the same seg with thread arena.
    if main_arena_addr == result.next:
        # we have only one arena! just return it
        return result, main_arena_addr
    else:
        # consider thread arena
        # TEST: multi-thread support haven't been tested!
        addr >>= 20
        while result.next != main_arena_addr and result.next != 0:
            # go to next arena
            temp_addr = result.next
            mem = state.memory.load(result.next, result.size)
            mem = mem.args[0].to_bytes(result.size, 'big')
            result.unpack(mem)
            if temp_addr >> 20 == addr:
                # we found it!
                return result, temp_addr
            else:
                continue
        # there's no match arena, so maybe given addr is on main thread's heap，
        # or it is an abused addr
        # we cannot determine...
        #print("Unable to find thread arena with addr %s!" % hex(addr))
        return main_arena, main_arena_addr
            


def single_list_iterate(state, link_head, ptr_offset): 
    """
    iterate a single list, until it meets 0 or a circle.
    Returns a list of all nodes the list have, including the head node,
    and if it is a circler list.

    :param state:       the state to get memory from
    :param link_head:   head of the list
    :ptr_offset:        offset of fd(next) ptr in the list's struct
    """
    circlar_node = 0
    bin_list = [link_head]
    link_head = state.memory.load(link_head+ptr_offset, 8, endness = 'Iend_LE').args[0]
    while link_head!=0:
        # a circle?
        if link_head in bin_list:
            circlar_node = link_head
            break
        bin_list.append(link_head)
        link_head = state.memory.load(link_head+ptr_offset, 8, endness = 'Iend_LE').args[0]
    return bin_list, circlar_node

def bin_fd_iterate(state, link_head):
    ptr_offset = 0x10
    return single_list_iterate(state, link_head, ptr_offset)

def bin_bk_iterate(state, link_head):
    ptr_offset = 0x18
    return single_list_iterate(state, link_head, ptr_offset)

def printable_fastbin_entry(nodes, circlar = 0, size = 0):
    result = "fastbin"
    if size:
        result += "[%s]"  % hex(size)
    result += ": "
    for node in nodes:
        result += hex(node) + " -> "
    if circlar:
        result += hex(circlar) + "(corrupted)"
    else:
        result += '0\n'
    return result

 # TODO: rewrite   
def fastbin_check(state, malloc_state, arena_addr):
    """
    fastbin is a single list, which shouldn't contain circle.

    """
    #output = ""
    for link_head in malloc_state.fastbinsY:
        if link_head == 0:
            continue
        nodes, circlar = bin_fd_iterate(state, link_head)
        for node in nodes:
            owner = ptr_lookup(node, state.project.reverse_maps, state)
            if owner == -1:
                print("Found unmapped address in fastbin.")
            elif owner:
                if owner[0]:
                    print("Found fastbin points to %s !" % owner[0])
        if circlar:
            print("Found corrupted fastbin!")
        print(printable_fastbin_entry(nodes, circlar))

def printable_bin_entry(fd_nodes, bk_nodes, size = 0):
    result = "bin"
    if size:
        result += "[%s]"  % hex(size)
    result += ": \n"
    for node in fd_nodes:
        result += hex(node) + " -> "
    result += '\n'
    for node in bk_nodes:
        result += hex(node) + " -> "
    return result

#TODO: rewrite
def bin_check(state, malloc_state, arena_addr):
    # seems we have to get arena address...
    arena_size = malloc_state.size
    for i in range(2, len(malloc_state.bins), 2):
        fd, bk = malloc_state.bins[i:i+2]
        fd_nodes, fd_circlar = bin_fd_iterate(state, fd)
        bk_nodes, bk_circlar = bin_bk_iterate(state, bk)
        if len(fd_nodes) == 1 and fd_nodes[0] == fd_circlar:
           if len(bk_nodes) == 1 and bk_nodes[0] == bk_circlar:
               continue
        print(printable_bin_entry(fd_nodes + [fd_circlar], bk_nodes + [bk_circlar]))
    pass



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
    
    # FIXME: bull shit
    def _ptr_in_chunk(self, ptr):
        for addr, size in self.chunks_av.items():
            if ptr in range(addr+0x10, addr+size-0x10):
                return addr, size
        return None

    def add_chunk(self, addr, size):
        """
        when a chunk is alloced, this func is called to do record and check.
        """
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
        """
        when a chunk is freed, this func is called to do record and check.
        """
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
            # target chunk doesn't been allocated more than one time,
            # so sizes is an int
            elif size == sizes:
                self.chunks_av.pop(addr)
            # do log in chunks_sv
            if size in self.chunks_sv:
                if addr in self.chunks_sv[size]:
                    self.chunks_sv[size].remove(addr)
        else:
            # this chunk is not allocated by c/m/relloc
            self.abused_chunks.append({"addr":addr, "size": size, "type":"chunk not allocated is freed"})
    
    def enable_hook(self):
        # hook heap api, save address to hooked_addr
        self.hooked_addr.append(self.project.hook_symbol("malloc", self.malloc_hook))
        self.hooked_addr.append(self.project.hook_symbol("free", self.free_hook))
        self.hooked_addr.append(self.project.hook_symbol("calloc", self.calloc_hook))

    def disable_hook(self):
        # clean hooks by saved addr
        for i in self.hooked_addr:
            self.project.unhook(i)

    def parse_arena(self, state):
        pass

    def clear(self):
        self.disable_hook()
        self.hooked_addr = []
        self.chunks_av = {}
        self.chunks_sv = {}
        self.abused_chunks = []
        self.arenas = []

    def do_analysis(self):
        """
        Do the job.
        """
        self.enable_hook()
        simgr = self.project.get_simgr()
        simgr.run()
        self.disable_hook()
        


