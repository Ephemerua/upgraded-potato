from elftools.elf.elffile import ELFFile
from elftools.dwarf.locationlists import (
    LocationEntry, LocationExpr, LocationParser)

def has_debug_info(elffile):
    if elffile.has_dwarf_info == False:
        return False
    if elffile.get_dwarf_info().has_debug_info == False:
        return False
    else:
        return True

class struct_parser(object):
    def __init__(self, path):
        with open(path, 'rb') as f:
            self.elffile = ELFFile(f)

            # check if we have debug info
            if not has_debug_info(self.elffile):
                print("File %s not have debug information!" % path)
                self.dw = 0
            else:
                self.dw = self.elffile.get_dwarf_info()

    def find_struct_die(self, sname):
        sname = bytes(sname, encoding="UTF-8")
        for cu in self.dw.iter_CUs():
            top_die = cu.get_top_DIE()
            for die in top_die.iter_children():
                if die.tag == "DW_TAG_structure_type":
                    if "DW_AT_name" in die.attributes:
                        if(die.attributes["DW_AT_name"].value== sname):
                            return die, cu
        return None

        
    def find_struct_die_with_filename(self, fname, sname):
        fname = bytes(fname, encoding="UTF-8")
        sname = bytes(sname, encoding="UTF-8")
        for cu in self.dw.iter_CUs():
            top_die = cu.get_top_DIE()
            if fname == top_die.attributes["DW_AT_name"].value:
                for die in top_die.iter_children():
                    if die.tag == "DW_TAG_structure_type":
                        if "DW_AT_name" in die.attributes:
                            if(die.attributes["DW_AT_name"].value == sname):
                                return die, cu
        return None
