import claripy

def BV2Int(bv):
    if isinstance(bv, int):
        return bv
    assert(bv.concrete)
    return bv.args[0]

def state_timestamp(state):
    return str(len(state.history.bbl_addrs))