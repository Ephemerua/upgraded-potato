from pygdbmi import gdbmiparser
from pygdbmi.gdbcontroller import GdbController
"""
get struct definition using gdb...
Dirty Deeds Done Dirty Cheap
Mostly not tested....
"""


class gdb_wrapper(GdbController):
    def __init__(self):
        super().__init__()
        self.type_cache = {}
        self.struct_cache = {}

    def load_file(self, file):
        self.write("file %s" % file)
        self.write("b __libc_start_main")
        self.write("run")

    def resolve_symbol(self, addr):
        resp = self.write("info symbol %s" % hex(addr))
        resp = [line for line in resp if line['type']=='console']
        if resp:
            resp = resp[0]['payload']
            if 'No symbol' in resp:
                return None
            else:
                return resp.split(" in section")[0]

    def resolve_address(self, symbol):
        resp = self.write("info address %s" % symbol)
        resp = [line for line in resp if line['type']=='console']
        if resp:
            resp = resp[0]['payload']
            if 'No symbol' in resp:
                return None
            else:
                result = resp.split(" ")[-1][:-3]
                result = int(result, 16)
                return result

    def query_size(self, name):
        if name in self.type_cache:
            return self.type_cache[name]
        resp = self.write("p sizeof( " + name + ")")
        resp = [line for line in resp if line['type']=='console'][0]['payload']
        result = int(resp.split(" ")[-1])
        self.type_cache[name] = result
        return result


    def query_struct(self, struct):
        if struct in self.struct_cache:
            return self.struct_cache[struct]

        parsed_struct = {}
        resp = self.write("ptype " + struct)
        # remove first line and last line(that should be useless?)
        resp = [line['payload'][:-2] for line in resp if line['type']=='console'][1:-1]
        # remove blanks, get type and member name
        for line in resp:
            # remove leading blanks and ';' at ending
            line = line.strip(" ")[:-1]
            # take last string as member name, all other are type info.
            line = line.split(" ")
            name = line[-1]
            type = " ".join(line[:-1])
            # care about ptr
            if name[0]=="*":
                name = name[1:]
                type += "*"

            # arraylike?
            arraylike = False
            num = 0
            if name[-1]==']':
                arraylike = True
                idx = name.find('[')
                num = int(name[ idx+1: -1])
                name = name[:idx]

            # try to get type size
            member_size = self.query_size(type)
            parsed_struct[name] = {"type":type, "array": arraylike, "size":member_size,\
                 "array_len": num}
        self.struct_cache[struct] = parsed_struct
        return parsed_struct

        