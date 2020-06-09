import angr

PROT_READ = 1
PROT_WRITE = 2
PROT_EXEC = 4

def print_callstack(state):
    cs = state.callstack
    print("\nStack:")
    for frame in cs:
        if not frame.func_addr:
            return 
        symbol  = state.project.symbol_resolve.reverse_resolve(frame.func_addr)
        if symbol:
            if '__gmon_start__' in symbol[0]:
                symbol = list(symbol)
                symbol[0] = 'sub_%x'% frame.func_addr
                symbol[1] = 0
            print('\t'+ symbol[0]+ "+ %d" % symbol[1])
        else:
            print('\t'+ hex(frame.func_addr))

class stack_frame(object):
    def __init__(self, addr, bp, symbol = None, frame_no = -1):
        self.addr = addr
        self.bp = bp
        self.symbol = symbol
        self.next = None
        self.no = frame_no
    
    def __str__(self):
        result = "Frame "
        if self.no != -1:
            result += "%d: " % self.no
        else:
            result += ": "
        
        result += "%#018x" % self.addr
        if self.symbol:
            name = self.symbol[0]
            offset = self.symbol[1]
            if "__gmon_start__" in name:
                name = "sub_%x" % (self.addr+offset)
                offset = 0

            result += "\tin  %s" % name
            if offset != 0:
                result += "%+d\t" % offset
            else:
                result +='\t'
        else:
            result += '\t\t\t'
        result += "bp: 0x%x\n" % self.bp
                
            
        return result
    


def stack_backtrace(state, depth = 'Max'):
    """
    Helper func to get stack backtrace.
    Do the same work as gdb's bt.

    :param state:   state to do bt
    :param depth:   bt depth
    """
    # gdb's backtrace records present rip in frame0, do the same with gdb
    symbol = state.project.symbol_resolve.reverse_resolve(state.regs.rip.args[0])
    result = [stack_frame(state.regs.rip.args[0], state.regs.rbp.args[0], symbol, 0)]
    bp = state.regs.rbp.args[0]
    frame_num = -1 if depth=='Max' else depth
    no = 0

    while frame_num:
        no += 1
        frame_num -= 1
        # bp==0 means trace ends
        if (bp == 0):
            return result

        ret_addr = state.memory.load(bp+8, 8, endness = 'Iend_LE').args[0]
        bp = state.memory.load(bp, 8, endness = 'Iend_LE').args[0]
        symbol = state.project.symbol_resolve.reverse_resolve(ret_addr)
        frame = stack_frame(ret_addr, bp, symbol, no)
        result.append(frame)

        # We have set uninited memory to zero, and ret_addr shouldn't be zero.
        if ret_addr == 0:
            return result
        if ret_addr > 0x7fffffffffff:
            return result

def printable_backtrace(bt):
    """
    format stack_backtrace's result to a str

    :param bt: result of stack_backtrace
    """
    result = "\n"
    for i in bt:
        result += str(i)
    return result


def fetch_str(state, addr):
    try:
        prots = state.memory.permissions(addr)
    except angr.errors.SimMemoryMissingError:
        return ""
    prots = prots.args[0]
    result = ""
    is_str = 1
    # TODO: move prots definition to other place
    if not (prots & PROT_READ):
        return ""
    while is_str:
        m = state.memory.load(addr, 8)
        assert(m.concrete)
        m = m.args[0]
        addr += 8

        for i in range(8):
            c = (m >> (7-i)*8) & 0xff
            if c > 126 or c < 32:
                is_str = False
                break
            else:
                result += chr(c)

    return result

from termcolor import colored
def printable_memory(state, start, size, warn_pos = 0, warn_size = 0, info_pos = 0, info_size = 0):
    result = "\n"
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