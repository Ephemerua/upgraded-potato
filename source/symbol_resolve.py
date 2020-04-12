# 'resolve' symbol name from symbol addr
class symbol_resolve(object):
    """
    DO resolve job.
    TODO: rewrite
    """
    def __init__(self, project):
        self.project = project

    def resolve(self, name, obj_name = ""):
        """
        Resolve symbol address by name.
        Returns (symbol address, object name of the address)
        There maybe symbols with same names in different libs, specify the obj_name to
        get the specific address.
        """
        if obj_name:
            obj = self.project.elfs[obj_name]
            if name in obj.symbols:
                return obj[name], obj_name
            else:
                return None
        for obj_name, obj in self.project.elfs.items():
            if name in obj.symbols:
                return obj.symbols[name], obj_name
        return None

    def reverse_resolve(self, addr):
        """
        Resolve symbol name by symbol address. TODO: should be replace by using dwarf
        Returns (symbol name, offset of the found symbol, object name which includes
        the symbol).
        If not found, return None.
        """
        # first find which object the addr belongs to
        print(addr)
        maps = self.project.maps
        found_obj = 0
        for obj, segs in maps.items():
            for seg in segs:
                if addr >= seg["start"] and addr <=seg["end"]:
                    found_obj = obj
                else:
                    continue
        
        if found_obj == 0:
            print("Cannot find symbol of addr %s." % hex(addr))
            return None
        
        # now try to find the symbol name
        obj = self.project.elfs[found_obj]
        # index the dict with addr
        symbols = {v:k for k, v in obj.symbols.items()}
        addrs = [ i for i in symbols]

        min_offset = 0xffffffff
        nearest_addr = -1
        for i in symbols:
            offset = abs(i - addr)
            if offset < min_offset:
                min_offset = offset
                nearest_addr = i

        min_offset = addr - nearest_addr
        name = symbols[nearest_addr]
        return name, min_offset, found_obj