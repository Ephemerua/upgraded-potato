from replayer import Replayer


class memwrite_analysis(object):
    # TODO: addr can also be claripy.BVVs besides integers
    def __init__(self, project: Replayer, *addr):
        self.__project = project
        self.__addr = list(addr)
        self.__state = self.__project.factory.entry_state()

    def __set_bp(self):
        def memwrite_bp_callback(state):
            write_addr = state.inspect.mem_write_address

            # FIXME: result is incorrect, is it a bug of angr or due to alignment???
            # FIXME: eg: it yields 0x8 rather than 0x10, 0x10 rather than 0x20
            write_length = state.inspect.mem_write_length
            print('Memory wrote to', write_addr, 'length', write_length)

        for addr in self.__addr:
            # TODO: deal with excessive breakpoints so that the same breakpoint can't be added more than once
            # Do we need to do the above???
            self.__state.inspect.b('mem_write', mem_write_address=addr, action=memwrite_bp_callback)

    def add_addr(self, addr):
        self.__addr.append(addr)

    def do_analysis(self):
        """
        Do the job.
        """
        self.__set_bp()
        simgr = self.__project.get_simgr(self.__state)
        simgr.run()
