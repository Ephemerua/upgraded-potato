import angr
import claripy
import json


class frida_mem_import(object):
    def __init__(self, dump_file):
        with open(dump_file, "r") as f:
            temp = json.load(f)

        self.context = temp['context']
        self.memory = temp['mem']

    def load_mem(self, state):



