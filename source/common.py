import claripy

def BV2Int(bv):
    if isinstance(bv, int):
        return bv
    assert(bv.concrete)
    return bv.args[0]