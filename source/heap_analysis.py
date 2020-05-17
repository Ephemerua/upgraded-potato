import claripy
import angr
import os
from structures import malloc_state
from arena import Arena
import logging

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



def _print_callstack(state):
    cs = state.callstack
    result = ""
    result += "\nStack:"
    for frame in cs:
        if not frame.func_addr:
            return result + '\n'
        symbol  = state.project.symbol_resolve.reverse_resolve(frame.func_addr)
        if symbol:
            if '__gmon_start__' in symbol[0]:
                symbol = list(symbol)
                symbol[0] = 'sub_%x'% frame.func_addr
                symbol[1] = 0
            result += '\t'+ symbol[0]+ "+ %d" % symbol[1]
        else:
            result += '\t'+ hex(frame.func_addr)
    return result + '\n'


# TODO: move this to other place
from termcolor import colored
def printable_memory(state, start, size, warn_pos = 0, warn_size = 0, info_pos = 0, info_size = 0):
    result = ""
    # align
    size = ((size >>3) <<3) + 0x10
    endl = -1
    warn = 0
    for addr in range(start, start+size, 8):
        mem = state.memory.load(addr, 8, endness = "Iend_LE")
        assert(mem.concrete)
        mem = mem.args[0]
        if endl:
            result += "%s| " %(hex(addr))
            endl = ~endl
        else:
            result += '  ' 
            endl = ~endl
        mem = "%016x" % mem
        colored_mem = ["" for i in range(8)]
        j = 0
        for i in range(14, -2, -2):
            bt = mem[i:i+2]
            if addr + j in range(warn_pos, warn_pos+warn_size):
                bt = colored(bt, 'red')
            if addr + j in range(info_pos, info_pos+info_size):
                bt = colored(bt, 'yellow')
            colored_mem[7-j] = bt
            j += 1

        result += "".join(colored_mem) 
        if endl:
            result += '\n'
    return result
            

def bp_overflow(report_logger, start_addr, size, callback = None, debug = False):
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

        
        if debug:
            # print("mem write to %s with length %s" % (hex(target_addr), hex(target_size)))
            report_logger.info("mem write to %s with length %s" % (hex(target_addr), hex(target_size)))

        if (target_addr + target_size > start_addr + size):
            # print("Found overflow in chunk at %s, size %s with write starts at %s, size %s!"
            #  % (hex(start_addr), hex(size), hex(target_addr), hex(target_size)))
            report_logger.info("Found overflow in chunk at %s, size %s with write starts at %s, size %s!"
                            % (hex(start_addr), hex(size), hex(target_addr), hex(target_size)))
            # report_logger.debug("Found overflow in chunk at %s, size %s with write starts at %s, size %s!"
            #                    % (hex(start_addr), hex(size), hex(target_addr), hex(target_size)))

            overflow_len = target_addr + target_size - (start_addr + size)
            #print("Overflow length: %s" % hex(overflow_len))
            overflow_content = state.inspect.mem_write_expr[overflow_len*8 - 1:0]
            # print("Overflow length: %s, content: %s" % (hex(overflow_len), overflow_content))
            report_logger.info("Overflow length: %s, content: %s" % (hex(overflow_len), overflow_content))
            # report_logger.debug("Overflow length: %s, content: %s" % (hex(overflow_len), overflow_content))
            str = printable_memory(state, min(start_addr, target_addr), max(size,target_size)\
                ,warn_pos = start_addr+size, warn_size  = overflow_len, info_pos = target_addr\
                    ,info_size = target_size)
            # print(str)
            report_logger.info("\n"+str)
            # print(printable_memory(state, min(start_addr, target_addr), max(size,target_size)\
            #     ,warn_pos = start_addr+size, warn_size  = overflow_len, info_pos = target_addr\
            #         ,info_size = target_size))
        return
    return write_bp



def bp_redzone(report_logger, start_addr, size, callback = None, debug = False, allow_heap_ops = False, mtype = 'redzone'):
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

        # print("Mem write to %s %s start at %s with size %s: %s" %(mtype, hex(start_addr), hex(target_addr),\
        #      hex(write_size), write_expr))
        report_logger.info("Mem write to %s %s start at %s with size %s: %s" % (mtype, hex(start_addr), hex(target_addr), \
                                                                             hex(write_size), write_expr))
        # report_logger.debug(
        #     "Mem write to %s %s start at %s with size %s: %s" % (mtype, hex(start_addr), hex(target_addr), \
        #                                                          hex(write_size), write_expr))
        if size > 0x40:
            start_addr = (target_addr>>4)<<4 - 0x10
            size = (write_size>>4)<<4 + 0x10
        str = printable_memory(state, min(start_addr, info_pos)\
            , max(size, info_size), warn_pos = target_addr,\
                 warn_size  = write_size, info_pos = info_pos, info_size = info_size)
        report_logger.info("\n"+str)

        stackstr = _print_callstack(state)
        report_logger.info(stackstr)
        # report_logger.debug(stackstr)
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
        # TODO: do log
        # print("Malloc called with size %s, returns addr %s" % (hex(size), hex(rax)))
        state.project.report_logger.info("Malloc called with size %s, returns addr %s" % (hex(size), hex(rax)))
        # report_logger.debug("Malloc called with size %s, returns addr %s" % (hex(size), hex(rax)))
        # TODO: check if return addr is sane. 
        symbol = state.project.symbol_resolve.reverse_resolve(rax) # dirty but easy
        if symbol:
            # print("Chunk address not in heap: %s + %d" % (hex(symbol[0], symbol[1])))
            state.project.report_logger.info("Chunk address not in heap: %s + %d" % (hex(symbol[0], symbol[1])))

        state.project.heap_analysis.add_chunk(rax, size)
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
        # TODO: do log
        # print("Calloc called with size %d, returns addr %s" % (size*count, hex(rax)))
        state.project.report_logger.info("Calloc called with size %d, returns addr %s" % (size*count, hex(rax)))
        # report_logger.debug("Calloc called with size %d, returns addr %s" % (size * count, hex(rax)))
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
    state.project.report_logger.info("Free called to free %s with size %s" % (hex(addr), hex(size)))
    # report_logger.debug("Free called to free %s with size %s" % (hex(addr), hex(size)))

    # get info for ret callback
    # stack frame haven't been created, so return address is in rsp
    ret_addr = state.memory.load(state.regs.rsp, endness = 'Iend_LE')
    ret_addr = ret_addr.args[0]
    state.project.heap_analysis.del_chunk(addr, size)

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
        # global report_logger
        self.project.report_logger = logging.getLogger('heap_analysis')
        self.project.report_logger.setLevel(logging.INFO)

    
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
            # print("Chunk at %s size %s : Already allocated!" % (hex(addr), hex(size)))
            self.project.report_logger.info("Chunk at %s size %s : Already allocated!" % (hex(addr), hex(size)))

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
                    # print("Chunk at %s size %s : Freed with mofied size!" % (hex(addr), hex(size)))
                    self.project.report_logger.info("Chunk at %s size %s : Freed with mofied size!" % \
                                                    (hex(addr), hex(size)))
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
            # print("Chunk at %s size %s : Chunk haven't been allocated is freed!" % (hex(addr), hex(size)))
            self.project.report_logger.info("Chunk at %s size %s : Chunk haven't been allocated is freed!" % \
                                            (hex(addr), hex(size)))

    
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
        file_handle = logging.FileHandler(os.path.join(self.project.target_path, "heap_analy.log"), mode="w+")
        self.project.report_logger.addHandler(file_handle)

        self.enable_hook()
        state = self.project.get_entry_state()
        #state.options.discard("UNICORN")
        simgr = self.project.get_simgr(state)
        simgr.run()
        self.disable_hook()
        


