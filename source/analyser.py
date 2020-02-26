import angr
import claripy
import replayer


class Analyser(object):
    entry_state = 0
    proj = 0

    # FIXME: 最好生成一个新的project和state
    def __init__(re):
        if not isinstance(re, replayer.Replayer):
            raise TypeError("Not an instance of Replayer.")
        self.entry_state = re.get_entry_state()
        self.proj = re.get_project()
        if not self.entry_state or not self.proj:
            raise ValueError("Replayer not initialized.")
    
    def set_hooks(self, hooks_dict):
        '''
        set hooks

        Args:
            hooks_dict: a dict like {addr: hook_func}
    
        Returns:
            Null
        '''
        for addr, func in hooks_dict.items():
            self.proj.hook(aadr, func)



class heap_analyser(Analyser):
    pass

    

        
            
    
