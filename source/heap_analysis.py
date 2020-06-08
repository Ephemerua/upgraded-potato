import claripy
import angr
import os
from structures import malloc_state
from arena import Arena
from util.info_print import  stack_backtrace, printable_backtrace, printable_memory
import logging
from analysis import register_ana
from common import state_timestamp
import logger

"""
TODO: move this part to doc
Heap analysis, focus on alloc, free and read/write on heap.

To detect overflow:
Backward overflow:
    A write with size exceeding the size of chunk.
    We need write bp definitly, so set a bp on malloc's return address, we can track all operaion
    on that chunk.
    Remove the bp after the chunk is freed.
Forward overflow:
    A write's start address is before the begin of the chunk.(Just care about metadata of 
    chunk structure. Even with source code, we cannot define if a write writes to unexpected place)
    Set write bp on chunk's metadata.
    2 conditions to consider:
        1. allocated chunk: set write bp on its matadata, delete the bp on free
        2. free chunk: how to know where the chunk is ???
            2.1 after free, set bp on all chunks tracked by arena.
            2.2 when alloced, remove the bp
        3. heap operation itself write to free chunks, identify them by call stack?

Fake chunk:
Chunks to be free must be malloc before, so track malloc to identify fake chunks.

UAF:
For simple double free it is easy. TODO: any other case?
"""



            

def bp_overflow(report_logger, start_addr, size, callback = None):
    def write_bp(state):
        target_addr = state.inspect.mem_write_address
        target_size = state.inspect.mem_write_length
        if type(target_addr) != int:
            target_addr = target_addr.args[0]
        if type(target_size) != int:
            target_size = target_size.args[0]

        
        if (target_addr >= start_addr + size) \
            or (start_addr >= target_addr + target_size):
            return

        if (target_addr + target_size > start_addr + size):
            overflow_len = target_addr + target_size - (start_addr + size)
            overflow_content = state.inspect.mem_write_expr[overflow_len*8 - 1:0]
            memory = printable_memory(state, min(start_addr, target_addr), max(size,target_size)\
                ,warn_pos = start_addr+size, warn_size  = overflow_len, info_pos = target_addr\
                    ,info_size = target_size)
            message = "Found chunk overflow at %s." % hex(start_addr)
            report_logger.warn(message, type='heap_overflow', start_addr = start_addr, size = size, target_addr = target_addr, \
                               target_size = target_size, overflow_len = overflow_len, overflow_content = overflow_content, memory = memory, state_timestamp = state_timestamp(state))
        return
    return write_bp



def bp_redzone(report_logger, start_addr, size, callback = None,  allow_heap_ops = False, mtype = 'redzone'):
    def write_bp(state):
        nonlocal start_addr, size
        target_addr = state.inspect.mem_write_address
        target_size = state.inspect.mem_write_length
        if type(target_addr) != int:
            target_addr = target_addr.args[0]
        if type(target_size) != int:
            target_size = target_size.args[0]

        
        if (target_addr >= start_addr + size) \
            or (start_addr >= target_addr + target_size):
            return
        info_pos = target_addr
        info_size = target_size
        # true analysis starts from here
        # XXX: at present we extract the write content within the redzone, should we display whole
        # write content?
        if target_addr < start_addr:
            offset = start_addr - target_addr
            write_size = min(target_size - offset, size)
            target_addr = start_addr
        else:
            offset = 0
            write_size = min(target_size, size)
        assert(write_size)
        # figure out if this write comes from heap operations
        if write_size < 0x20 and allow_heap_ops:
            cs = state.callstack
            for frame in cs:
                symbol = state.project.symbol_resolve.reverse_resolve(frame.func_addr)
                if symbol:
                    name = symbol[0].split('.')[-1]
                    if name == 'malloc' or name == 'free' or name == 'calloc' or name == 'realloc':
                        #print(frame)
                        return
            
        write_expr = state.inspect.mem_write_expr
        write_expr = write_expr[(target_size-offset)*8 - 1: (target_size-offset-write_size)*8]

        if size > 0x40:
            start_addr = (target_addr>>4)<<4 - 0x10
            size = (write_size>>4)<<4 + 0x10

        memory = printable_memory(state, min(start_addr, info_pos)\
            , max(size, info_size), warn_pos = target_addr,\
                 warn_size  = write_size, info_pos = info_pos, info_size = info_size)

        backtrace = printable_backtrace(stack_backtrace(state))
        message = "Redzone(%s) at %s overwritten." %(mtype, hex(start_addr))
        report_logger.warn(message, type="redzone_write",mtype = mtype, start_addr = start_addr, target_addr = target_addr, \
                           write_size = write_size, write_expr = write_expr, backtrace = backtrace, memory = memory, state_timestamp = state_timestamp(state))
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
    origin_size = size
    size = ((size>>4)<<4) + 0x10
    if size < 0x20:
        size = 0x20

    rsp = state.regs.rsp
    assert(rsp.concrete)
    # stack frame haven't been created, so return address is in rsp
    ret_addr = state.memory.load(rsp, 8, endness = 'Iend_LE')
    assert(ret_addr.concrete)
    ret_addr = ret_addr.args[0]
    #print(hex(ret_addr))

    def _malloc_callback(state):
        # rax contains return address of malloc
        state.project.unhook(ret_addr)
        rax = state.regs.rax
        assert(rax.concrete)
        rax = rax.args[0]
        message = "Malloc(%s) => %s" % (hex(size), hex(rax))
        state.project.report_logger.info(message, size = size, addr = rax, type = "malloc", state_timestamp = state_timestamp(state))
        # TODO: check if return addr is sane. 
        symbol = state.project.symbol_resolve.reverse_resolve(rax) # dirty but easy
        if symbol:
            message = "Chunk returned (%s <- %s%+d)not in heap."% (hex(rax), hex(symbol[0]), hex(symbol[1]))
            state.project.report_logger.warn(message, symbol = symbol[0], offset = symbol[1], type = 'alloc_warn', state_timestamp = state_timestamp(state))

        state.project.heap_analysis.add_chunk(rax, size, state)
        # # TEST
        # ms, arena_addr = get_malloc_state(state, rax)
        # assert(ms)
        # fastbin_check(state, ms, arena_addr)
        # bin_check(state, ms, arena_addr)

        # set bp
        #if rax - 0x10 in state.project.heap_analysis.bps:
        # bps = state.project.heap_analysis.bps
        # for addr, bp in bps.items():
        #     if addr >= rax-0x10 and addr < rax-0x10 + size:
        #         state.inspect.remove_breakpoint(event_type = 'mem_write', bp = bp)
        bps = state.project.heap_analysis.free_bps
        if rax - 0x10 in bps:
            state.inspect.remove_breakpoint(event_type = 'mem_write', bp = bps[rax-0x10])
            state.project.heap_analysis.free_bps.pop(rax-0x10)
        if rax in bps:
            state.inspect.remove_breakpoint(event_type = 'mem_write', bp = bps[rax])
            state.project.heap_analysis.free_bps.pop(rax)
    
        bp_content = state.inspect.b("mem_write", action = bp_overflow(state.project.report_logger, rax, origin_size))
        bp_metadata = state.inspect.b("mem_write", action = \
            bp_redzone(state.project.report_logger, rax-0x10, 0x10, allow_heap_ops = False, mtype = 'chunk header'))
        state.project.heap_analysis.inuse_bps[rax] = bp_content
        state.project.heap_analysis.inuse_bps[rax - 0x10] = bp_metadata

    assert(not state.project.is_hooked(ret_addr))
    state.project.hook(ret_addr, _malloc_callback)

# TODO： rewrite this!!!!
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
    if size < 0x20:
        size = 0x20

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
        state.project.report_logger.info("Calloc", type = 'calloc', size = size*count, ret_addr = rax, state_timestamp = state_timestamp(state))
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
    # print("Free called to free %s with size %s" % (hex(addr), hex(size)))
    message = "Free(%s) (size: %s)" % (hex(addr), hex(size))
    state.project.report_logger.info(message, addr = addr, size = size, type="free", state_timestamp = state_timestamp(state))

    # get info for ret callback
    # stack frame haven't been created, so return address is in rsp
    ret_addr = state.memory.load(state.regs.rsp, endness = 'Iend_LE')
    ret_addr = ret_addr.args[0]
    state.project.heap_analysis.del_chunk(addr, size, state)

    # since the chunk is freed, remove write bps
    bps = state.project.heap_analysis.inuse_bps
    if addr in bps:
        state.inspect.remove_breakpoint(event_type = 'mem_write', bp = bps[addr])
        bps.pop(addr)
    if addr-0x10 in bps:
        state.inspect.remove_breakpoint(event_type = 'mem_write', bp = bps[addr-0x10])
        bps.pop(addr-0x10)

    for addr, bp in state.project.heap_analysis.free_bps.items():
            #print(state.inspect._breakpoints)
        state.inspect.remove_breakpoint(event_type = 'mem_write', bp = bp)
    state.project.heap_analysis.free_bps = {}

        
    def _free_callback(state):
        state.project.heap_analysis.parse_arena(state)
        state.project.unhook(ret_addr)

        # # TEST: to be tested
        # ms, arena_addr = get_malloc_state(state, addr)
        # assert(ms)
        # fastbin_check(state, ms, arena_addr)
        # bin_check(state, ms, arena_addr)
        arena = Arena(state, addr = addr)
        chks = arena.get_all_chunks()
        for chk in chks:
            chk_size = (chk[1]>>4)<<4
            bp = state.inspect.b('mem_write', when = angr.BP_AFTER,action=bp_redzone(state.project.report_logger, chk[0], chk_size, allow_heap_ops = True, mtype = "freed chunk"))
            state.project.heap_analysis.free_bps[chk[0]] = bp


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
        self.inuse_bps ={}
        self.free_bps = {}
    
    # FIXME: bull shit
    def _ptr_in_chunk(self, ptr):
        for addr, size in self.chunks_av.items():
            if ptr in range(addr+0x10, addr+size-0x10):
                return addr, size
        return None

    def add_chunk(self, addr, size, state):
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
            self.project.report_logger.warn("Double allocated chunk", addr = addr, size = size, type = 'alloc_warn', state_timestamp = state_timestamp(state))

        else:
            self.chunks_av[addr] = size
            
        # do log in chunks_sv
        if size in self.chunks_sv:
            self.chunks_sv[size].append(addr)
        else:
            self.chunks_sv[size] = [addr]

    def del_chunk(self, addr, size, state):
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
                    self.project.report_logger.warn("Chunk freed with modified size", addr = addr, size = size, type='free_warn', state_timestamp = state_timestamp(state))
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
            self.project.report_logger.warn("Unallocated chunk is freed", addr = addr, size = size, type = 'free_warn', state_timestamp = state_timestamp(state))

    
    def enable_hook(self):
        # hook heap api, save address to hooked_addr
        self.hooked_addr.append(self.project.hook_symbol("malloc", self.malloc_hook))
        self.hooked_addr.append(self.project.hook_symbol("free", self.free_hook))
        # calloc still in work
        #self.hooked_addr.append(self.project.hook_symbol("calloc", self.calloc_hook))

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
        self.clear()
        self.project.report_logger = logger.get_logger(__name__)
        self.enable_hook()
        state = self.project.get_entry_state()
        #state.options.discard("UNICORN")
        simgr = self.project.get_simgr(state)
        simgr.run()
        self.disable_hook()
        
register_ana('heap_analysis', heap_analysis)

