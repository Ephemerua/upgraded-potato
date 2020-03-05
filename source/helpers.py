# -*- coding:utf-8 -*-
import claripy
import angr
from pwnlib import elf


def parse_maps(maps, target):
    """
    parse mmap_dump's memory map to angr.loaders's opts

    Args:
        maps: str, logged mmap content
        target: target file name
        #TODO: now target can't be a path
    
    Returns:
        angr.loader's main_opts and lib_opts
    """
    lib_opts = {}
    main_opts = {}
    maps = maps.split("\n")
    if "got bp" in maps[0]:
        bp = maps[0].split(" ")[-1].strip()
        bp = int(bp, 16)
    else:
        puts("No stack pointer recorded?")
        exit(0)
    for line in maps[1:]:
        if line == "":
            continue
        
        parts = line.split(" ")
        start_addr, end_addr = [int(x, 16) for x in parts[0].split("-")]
        mod = parts[1]
        path = parts[-1]
        #set main_opts first
        if main_opts == {}:
            if path.split("/")[-1] == target:
                main_opts["base_addr"] = start_addr
                continue
        #than lib opts
            # use first addr as base
        if path not in lib_opts:
            # don't parse other segments of target
            if path.split("/")[-1] == target:
                continue
            # don't parse mapped memory
            if path == "":
                continue
            # don't parse misc segs like [heap]
            if path[0] == "[":
                continue
            lib_opts[path] = {"base_addr":start_addr}
    return main_opts, lib_opts, bp

def parse_maps_from_file(path, target):
    """
    wrapper for parse_maps

    Returns:
        tuple(main_opts, lib_opts), both angr.loader's options
    """
    with open(path, "r") as f:
        return parse_maps(f.read(), target)


#define LOGGER_PROMPT "$LOGGER$"
LOGGER_PROMPT = b"$LOGGER$"
#python3 version
def parse_log(log):
    """
    parse tee's logged stdin to sim_file

    Args:
        log: logged file content
    
    Returns:
        angr.SimPackets
    """
    #FIXME: input always has a 0 at beginning... don't use that
    packets = log.split(LOGGER_PROMPT+b"\x00")[1:]
    # prevent packet size unsat
    packets = [bytes(packet) for packet in packets]
    sim_file = angr.SimPackets("sim-stream", content = packets)
    return sim_file


def parse_log_from_file(path):
    """
    wrapper for parse_log
    
    Returns:
        angr.SimPackets
    """
    with open(path, "rb") as f:
        return parse_log(f.read())

#python2 version
# def parse_log(log):
#     """
#     parse tee's logged stdin to sim_file

#     Args:
#         log: logged file content
    
#     Returns:
#         angr.SimPackets
#     """
#     #FIXME: input always has a 0 at beginning... don't use that
#     packets = log.split(LOGGER_PROMPT+"\x00")[1:]
#     # prevent packet size unsat
#     #packets = [claripy.BVV(i, len(i)*8) for i in packets]
#     sim_file = angr.SimPackets("sim-stream", content = packets)
#     return sim_file


# def parse_log_from_file(path):
#     """
#     wrapper for parse_log
    
#     Returns:
#         angr.SimPackets
#     """
#     with open(path, "r") as f:
#         return parse_log(f.read())

