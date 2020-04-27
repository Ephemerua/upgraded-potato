"""
TODO: logging
Visualisation isn't needed for this file because memwrite_analysis is used in other classes
"""

from replayer import Replayer


class _memwrite_result(object):
    """
    helper class to store result for memory writing to one address
    """
    def __init__(self, address, length, contents):
        self.address = address
        self.length = length
        self.contents = contents

    def __repr__(self):
        return "Memory wrote to address %s, length %s, contents %s" %\
               (hex(self.address), hex(self.length), self.contents)


class memwrite_analysis(object):
    """Analyse memory writing to given address(es)

    :param project:     Replayer to be analysed
    :param addr_list:   addresses to be analysed

    Note:
    If the address to be analysed is written more than once during the replay,
    the result will only show the last modification.
    In this case, if tracking all modifications is needed,
    look into self.complicated_result to see all info.
    Otherwise self.complicated_result isn't needed

    see __main__ below for usage
    """
    # TODO: maybe addr can also be claripy.BVVs besides integers?
    def __init__(self, project: Replayer, *addr_list):
        self.__project = project
        self.__addr = list(addr_list)
        self.__state = self.__project.factory.entry_state()
        self.__all_mem_write_info = {}  # saves all memory write info
        self.__result = []              # element type: class _memwrite_result
        self.__complicated_result = []  # element type: class _memwrite_result

    def __set_bp(self):
        def memwrite_bp_callback(state):
            write_addr = state.inspect.mem_write_address
            write_length = state.inspect.mem_write_length
            write_contents = state.inspect.mem_write_expr
            if not isinstance(write_addr, int):
                write_addr = write_addr.args[0]
            if not isinstance(write_length, int):
                write_length = write_length.args[0]
            self.__all_mem_write_info[write_addr] = (write_length, write_contents)

        self.__state.inspect.b('mem_write', action=memwrite_bp_callback)

    def __process_mem_write_info(self):
        """
        Process the result in self.__all_mem_write_info and save the results in self.__result
        """
        for addr in self.__addr:
            addr1 = addr
            write_length = 0    # Continuous write length to an address, a sum-up of state.inspect.mem_write_length
            while addr1 in self.__all_mem_write_info:
                # TODO: do the log for the print functions
                # these are debugging messages, visualization isn't needed
                print('Memory writing to address', hex(addr1), end=' ')
                print('length', self.__all_mem_write_info[addr1][0], end=' ')
                print('Contents', self.__all_mem_write_info[addr1][1])

                self.__complicated_result.append(
                    _memwrite_result(addr1, self.__all_mem_write_info[addr1][0], self.__all_mem_write_info[addr1][1])
                )

                write_length += self.__all_mem_write_info[addr1][0]
                if 'contents' in locals():
                    contents = contents.concat(self.__all_mem_write_info[addr1][1])
                else:
                    contents = self.__all_mem_write_info[addr1][1]
                addr1 += self.__all_mem_write_info[addr1][0]
            else:
                print('No memory writing to address', hex(addr1))
            self.__result.append(_memwrite_result(addr, write_length, contents))

    def add_addr(self, *addr_list):
        """
        Add addresses to analyse
        """
        for addr in addr_list:
            if not isinstance(addr, int):
                raise TypeError('Arguments passed to add_addr must be integers')
            self.__addr.append(addr)

    def do_analysis(self):
        """
        Do the job.
        """
        self.__set_bp()
        simgr = self.__project.get_simgr(self.__state)
        simgr.run()
        print(self.__all_mem_write_info)
        self.__process_mem_write_info()
        return self.__result

    @property
    def result(self):
        return self.__result

    @property
    def complicated_result(self):
        return self.__complicated_result


if __name__ == '__main__':
    from replayer import Replayer
    r = Replayer('../test/sample/easyheap', '../test/sample/sample.txt', '../test/sample/maps.easyheap.26197')
    m = memwrite_analysis(r, 0x123123, 0x456456)
    print(m.do_analysis())
    print(m.result)
