from replayer import Replayer


class memwrite_analysis(object):
    # TODO: maybe addr can also be claripy.BVVs besides integers
    def __init__(self, project: Replayer, *addr):
        self.__project = project
        self.__addr = set(addr)
        self.__state = self.__project.factory.entry_state()

    def __set_bp(self):
        def memwrite_bp_callback(state):
            nonlocal addr
            write_addr = state.inspect.mem_write_address
            write_length = state.inspect.mem_write_length
            print('Memory wrote to', write_addr, 'length', write_length)
            print('Contents', state.inspect.mem_write_expr)
            # TODO: doing the job recursively is too ugly and slow, can we do it more elegantly?
            # FIXME: we run into trouble here, generating too many incomprehensible and annoying error messages
            #  despite the fact that the results are correct
            m = memwrite_analysis(self.__project, addr + write_length.args[0])
            m.do_analysis()

        for addr in self.__addr:
            self.__state.inspect.b('mem_write', mem_write_address=addr, action=memwrite_bp_callback)

    def add_addr(self, addr):
        if not isinstance(addr, int):
            raise TypeError('Argument passed to add_addr must be an int')
        self.__addr.add(addr)

    def do_analysis(self):
        """
        Do the job.
        """
        self.__set_bp()
        simgr = self.__project.get_simgr(self.__state)
        simgr.run()
