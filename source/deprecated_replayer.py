class Replayer(object):
    '''
    wrapper for angr project
    '''
    __entry_state = 0
    __proj = 0
    __sim_file = 0
    def __init__(self):
        pass

    def __init__(self, path_to_target, path_to_log, path_to_map):
        # construct the angr.Project, loader's options must be set at first
        target_name = path_to_log.split(r"/")[-1]
        main_opts, lib_opts, bp = parse_maps_from_file(path_to_map, target_name)
        self.__proj = angr.Project(path_to_target, main_opts = main_opts, lib_opts = lib_opts, \
            auto_load_libs=True, use_sim_procedures=False)

        # contruct sim_file, and save an entry_state as backup
        self.__sim_file = parse_log_from_file(path_to_log)
        self.__entry_state = self.__proj.factory.entry_state(mode="tracing", stdin=self.__sim_file)
        self.__entry_state.regs.rsp = bp

        # replace unsupported syscall
        replace_stub(self.__proj)


    
    def get_entry_state(self):
        # state can't be modified
        return self.__entry_state

    def get_project(self):
        return self.__proj
    
    def get_sim_file(self):
        return self.__sim_file

    def get_simgr(self):
        return self.__proj.factory.simgr(self.__entry_state)

    def set_sim_file(self, sf):
        self.__sim_file = sf
        self.__entry_state = self.__proj.factory.entry_state(mode="tracing", stdin=self.__sim_file)



    def navigate_to(self, addr, from_state = None):
        if from_state:
            state = from_state
        else:
            state = self.get_entry_state()

        simgr = self.__proj.factory.simgr(state)

        simgr.explore(find = addr)
        if simgr.stashes['found']:
            return simgr.found[0]
        return simgr

    # TODO: clean or reuse these trash
    # # FIXME: Extremely slow, can't work at all. We have to set hook to unicorn and use debugger's way to set breakpoint.
    # def navigate_to(self, addr, from_state = None):
    #     """
    #     replay to the given addr, default from the entry state.
    #     FIXME: At now it can only goto the start of a block.
    #     """
    #     if from_state:
    #         state = from_state
    #     else:
    #         state = self.get_entry_state()
        
    #     # XXX: we can set an interrupt hook to unicorn, and use debugger's way to set breakpoint,
    #     # but in angr it seems hard... haven't look into unicorn plugin
    #     # XXX: disable unicorn's step
    #     state.unicorn.max_steps = 1
    #     simgr = self.__proj.factory.simgr(state)
    #     while simgr.active:
    #         simgr.step()
    #         active = simgr.active
    #         if len(active) > 1:
    #             if 'syscall' in str(active[0].regs.rax.args[0]):
    #                 print("Found syscall stub, discard failed one.")
    #                 simgr.stash(filter_func = failed_stub_filter)
    #             else:
    #                 simgr.active = active[:1]
    #         if len(simgr.active) > 1:
    #             print("Found mutiple paths.")
        
        

    #     if simgr.found:
    #         # restore max_step to default value
    #         for i in simgr.found:
    #             i.unicorn.max_step = 10000
    #         return simgr.found
        
    #     # step interrupted by int3 won't be moved to deadended
    #     # seems we can't find the state
    #     print("Cannot navigate to the address.")
    #     return simgr

    # XXX: test func
    # def test_navigate_to(self, addr, from_state = None):
    #     """
    #     replay to the given addr, default from the entry state.
    #     FIXME: At now it can only goto the start of a block.
    #     """
    #     if from_state:
    #         state = from_state
    #     else:
    #         state = self.get_entry_state()
        
    #     state.options.discard("UNICORN")
    #     simgr = self.__proj.factory.simgr(state)
    #     while simgr.active:
    #         simgr.step()
    #         active = simgr.active
    #         if active:
    #             if (active[0].regs.rip == addr).is_true():
    #                 return active[0]
    #         if len(active) > 1:
    #             if 'syscall' in str(active[0].regs.rax.args[0]):
    #                 print("Found syscall stub, discard failed one.")
    #                 simgr.stash(filter_func = failed_stub_filter)
    #             else:
    #                 simgr.active = active[:1]
    #         if len(simgr.active) > 1:
    #             print("Found mutiple paths.")
        
    #     # step interrupted by int3 won't be moved to deadended
    #     # seems we can't find the state
    #     print("Cannot navigate to the address.")
    #     return simgr

def check_sat(simgr):
    '''
    Deprecated.
    Check if the entry_state could be replayed with the SimPackets.
    There should only be one path, but Simpackets sometimes fails, so do check.

    Args:
        Replayer's simgr

    Returns:
        Bool
        errored path could be found in simgr.errored
    '''
    start_time = time()
    while (simgr.active):
            # do step
            simgr.step()

            # if we run into a syscall that angr cannot handle, there will be 2 active state
            # use state.solver to check which state succeeds and stash another one
            if len(simgr.active)>1:
                temp = simgr.active[0].regs.rax.args[0]
                if "syscall_stub" in str(temp):
                    #print("Run into a syscall stub. Stash failed state.")
                    print(temp)
                    if "execve" in str(temp):
                        return
                    simgr.move(from_stash="active", to_stash="deprecated", filter_func = failed_stub_filter)
                else:
                    # only use the first active... leave check to user
                    print("Found more than one path! ")
                    simgr.active = simgr.active[:1]
                    ret = False
            
            # check the state goes to deadended
            if  not simgr.active and simgr.deadended:
                ret = True
                end_time = time()
                print("Replay finished in %f second." % (end_time - start_time))
    return ret