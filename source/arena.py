import claripy
import angr
from structures import malloc_state

def get_malloc_state(state, addr = 0):
    """
    TODO: test this func
    get struct malloc_state from memory
    still we need the address of the struct
    """
    main_arena_addr = state.project.symbol_resolve.resolve("__malloc_hook") + 0x10
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
    link_head = state.memory.load(link_head + ptr_offset, 8, endness = 'Iend_LE').args[0]
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

def align16(value):
    return (value>>4)<<4


        
def _get_one_bin(state, link_head, head_addr = 0, is_bk = 0):
    circlar = 0
    chks = []
    if link_head:
        # get all chunk's addr
        if is_bk:
            nodes, circlar = bin_bk_iterate(state, link_head)
            #print(nodes)
        else:
            nodes, circlar = bin_fd_iterate(state, link_head)
        # also get size info now
        for node in nodes:
            if node == head_addr - 0x10 - 8*is_bk:
                chk_size = 0
            else:
                chk_size = state.memory.load(node+8, 8, endness = "Iend_LE").args[0]
            chk = (node, chk_size)
            chks.append(chk)
    return chks, circlar          

class Arena(object):
    def __init__(self, state, addr = 0):
        self.fastbin = [ 0 for i in range(10)]
        self.fastbin_c = [ 0 for i in range(10)]
        self.bins = [ 0 for i in range(254)]
        self.bins_c = [ 0 for i in range(254)]
        self.bins_addr = [0 for i in range(254)]
        self.unsorted_bin = 0
        self.unsorted_bin_c = 0
        self.arena = 0
        self.addr = 0
        self.state = state
        self.get_arena(addr)
        self.get_bins()
        self.get_fastbin()

    def get_arena(self, addr = 0):
        state = self.state
        self.arena, self.addr = get_malloc_state(state, addr)
        self.bins_addr = range(self.addr+0x68, self.addr+0x68+8*254, 8)

    def get_fastbin(self):
        state = self.state
        arena = self.arena
        assert(arena)
        for i in range(0, len(arena.fastbinsY)):
            link_head = arena.fastbinsY[i]
            chks, circlar = _get_one_bin(state, link_head)
            self.fastbin[i] = chks
            self.fastbin_c[i] = circlar
        
    def get_bins(self):
        state = self.state
        arena = self.arena
        assert(arena)
        for i in range(0, len(arena.bins), 2):
            fd = arena.bins[i]
            fd_addr = self.bins_addr[i]
            bk = arena.bins[i+1]
            bk_addr = self.bins_addr[i+1]
            chks, circlar = _get_one_bin(state, fd, head_addr=fd_addr)
            self.bins[i] = chks
            self.bins_c[i] = circlar
            chks, circlar = _get_one_bin(state, bk, head_addr=bk_addr, is_bk=1)
            self.bins[i+1] = chks
            self.bins_c[i+1] = circlar
        self.unsorted_bin = self.bins[:2]
        self.unsorted_bin_c = self.bins_c[:2]

    def get_all_chunks(self):
        chks = []
        for entry in self.fastbin:
            if entry:
                for i in entry:
                    chks.append(i)
        for entry in self.bins:
            if entry:
                for i in entry:
                    if i[1] != 0:
                        chks.append(i)
        chks = set(chks)
        return list(chks)
    
    def fastbin_check(self, idx):
        chks = self.fastbin[idx]
        circlar = self.fastbin_c[idx]

        if circlar:
            print("fastbin[%d] corrupted!" % idx)
            # TODO: show this bin
    
    def bin_check(self, idx):
        assert(idx >= 0 and idx <254)
        idx &= 0xfe
        fd_list = self.bins[idx]
        bk_list = self.bins[idx+1]
        bk_list = bk_list[::-1]
        fd_len = len(fd_list)
        bk_len = len(bk_list)
        show_bin = 0
        if fd_len != bk_len:
            print("Bin[%d] corrupted!" % idx)
            show_bin = 1
        for i in range(min(fd_len, bk_len)):
            if fd_list[i][0] != bk_list[i][0]:
                show_bin = 1
        



    def do_check(self):
        pass
    




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





def printable_fastbin_entry(nodes, circlar = 0):
    result = "fastbin: "
    for node in nodes:
        result += "0x%x[0x%x]"%nodes + " -> "
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

def unsortedbin_check(state, malloc_state, arena_addr):
    pass