# HAVEN'T BEEN TESTED
def malloc_hook(state):
    # get return address and arg
    size = state.regs.rdi
    assert(size.concrete)
    size = size.args[0]
    rbp = state.regs.rbp
    assert(rbp.concrete)
    ret_addr = state.memory.load(rbp+8, 8, endness = 'Iend_LE')
    assert(ret_addr.concrete)
    ret_addr = ret_addr.args[0]
    print(hex(ret_addr))

    def malloc_callback(state):
        # rax contains return address of malloc
        rax = state.regs.rax
        assert(rax.concrete)
        rax = rax.args[0]
        # TODO: do log
        print("Malloc called with size %d, returns addr %s" % (size, hex(rax)))
        state.project.unhook(ret_addr)

    state.project.hook(ret_addr, malloc_callback)

    






    
