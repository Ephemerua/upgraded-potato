import re
import copy
from graphviz import Source
import os



class view_leak_log(object):
    def __init__(self, path):
        self.path = path

    def get_leak_table(self):
        '''
        :return: a list whose format is for jinja2
        '''
        def parse_info_from_log(path):
            '''
            parse the leak analysis log file
            :param path: leak analysis log file path
            :return: a list whose format is for jinja2
            '''

            leak_list = []
            f = open(path, "r")
            while True:
                node_info = {}
                line = f.readline()
                if not line:
                    break
                obj = re.match("Found leaked addr: (.*) (.*) in lib (.*)", line)
                if obj:
                    node_info['name'] = obj.group(1)
                    node_info['addr'] = obj.group(2)
                    node_info['lib'] = obj.group(3)
                    leak_list.append(copy.deepcopy(node_info))
            f.close()
            return leak_list

        return parse_info_from_log(self.path)

class view_got_log(object):
    def __init__(self, path):
        self.path = path

    def get_got_change(self):
        '''
        :return: a list whose format is for jinja2
        '''

        def parse_info_from_log(path):
            '''
            parse the got analysis log file
            :param path: got analysis log file path
            :return: a list whose format is for jinja2
            '''
            f = open(path, "r")
            got_change = []
            lines = f.readlines()
            for i in range(len(lines)):
                node_info = {}
                misobj = re.match("Found got mismatch: (.*)", lines[i])
                if misobj:
                    node_info['mismatch'] = misobj.group(1)
                    if i == len(lines) - 1:
                        continue
                    if lines[i + 1].startswith("which is func"):
                        obj = re.match("which is func (.*)", lines[i + 1])
                        node_info['function'] = obj.group(1)
                    else:
                        # node_info.append("")
                        node_info['function'] = ""
                    got_change.append(copy.deepcopy(node_info))
            f.close()
            return got_change

        return parse_info_from_log(self.path)


def overflow_heap_info(node_info, overflow_info):
    '''
    judge which heap is overflow point
    :param node_info: a list of heap info
    :param overflow_info: a node which is overflow
    :return: the node which is overflow point
    '''
    for info in node_info:
        start = int(info[0], 16)-0x10
        end = start + int(info[1], 16)
        overflow_start = int(overflow_info[0], 16)
        if overflow_start >= start and overflow_start <= end:
            info[2] = overflow_info[2]
            break
    return node_info

def free_heap_info(node_info, free_info):
    '''
    delete the released heap
    :param node_info: a list of heap info
    :param free_info: a node which will be free
    :return: the node which will be free in heap info
    '''
    success = False
    index = 0
    for info in node_info:
        if info[0] == free_info[0]:
            success = True
            break
        index += 1
    if success:
        del node_info[index]
        return node_info
    else:
        return node_info

def extract_memory(f):
    res = ""
    while True:
        line = f.readline()
        if line is not '\n':
            res += \
                line.replace('[0m', '').replace('[33m', '').replace('[31m', '')
            break
    while True:
        line = f.readline()
        if line is '\n':
            break
        res += \
            line.replace('[0m', '').replace('[33m', '').replace('[31m', '')
    return res

def extract_stack(f):
    res = ""
    while True:
        line = f.readline()
        if "stack:" in line or line=="":
            break

    while True:
        line = f.readline()
        if line == '\n'or line=="":
            break
        res += line

    return res if res is not "" else "None"

class view_heap_log(object):

    def __init__(self, path):
        self.path = path

    def gen_heap_change_png(self):
        '''
        generate dot file and png file
        :return:
        '''

        def parse_heap_change_log(path):
            '''
            Record heap change information
            :param path: heap analysis log file path
            :return: a list of heap info change
            '''

            heap_infos = []
            f = open(path, "r")
            node_info = []
            while True:
                line = f.readline()
                if not line:
                    break

                mallocobj = re.match("Malloc called with size (.*), returns addr (.*)", line)
                if mallocobj:
                    malloc_info = [mallocobj.group(2), mallocobj.group(1), mallocobj.group()]
                    node_info.append(malloc_info)
                    heap_infos.append([mallocobj.group(), copy.deepcopy(node_info)])
                    continue

                callocobj = re.match("Calloc called with size (.*), returns addr (.*)", line)
                if callocobj:
                    calloc_info = [callocobj.group(2), callocobj.group(1), callocobj.group()]
                    node_info.append(calloc_info)
                    heap_infos.append([callocobj.group(), copy.deepcopy(node_info)])
                    continue

                freeobj = re.match("Free called to free (.*) with size (.*)", line)
                if freeobj:
                    # print("free:" + freeobj.group(1) + " " + freeobj.group(2))
                    free_info = [freeobj.group(1), freeobj.group(2), freeobj.group()]
                    node_info = free_heap_info(node_info, free_info)
                    heap_infos.append([freeobj.group(), copy.deepcopy(node_info)])
                    continue

                overflowobj = re.match(
                    "Found overflow in chunk at (.*), size (.*) with write starts at (.*), size (.*)!\n",
                    line)
                if overflowobj:
                    # print("overflow:" + overflowobj.group(1) + " " + overflowobj.group(2))
                    overlength = f.readline()
                    overflow_info = [overflowobj.group(3), overflowobj.group(4), overflowobj.group() + overlength]
                    node_info = overflow_heap_info(node_info, overflow_info)
                    # add the memory info by extract_memory()
                    heap_infos.append([overflowobj.group() + overlength, copy.deepcopy(node_info), extract_memory(f)])

                memobj = re.match("Mem write to chunk header (.*) start at (.*) with size (.*): <(.*)>", line)
                if memobj:
                    heap_infos.append([memobj.group(),extract_memory(f), extract_stack(f)])

            f.close()
            # print(self.heap_infos)
            return heap_infos


        heap_infos = parse_heap_change_log(self.path)
        head_dot = '''digraph G {n0[shape=reocord,label="......"]'''
        tail_dot = "}"
        label_dot = ""
        edge_dot = ""
        index = 0
        for heap_info in heap_infos:
            index += 1

            # when the node is empty
            if len(heap_info[1]) == 0:
                label_dot += '''n%s[shape=record,label="......"]''' % (index)
                edge_dot += '''n%s->n%s[label="%s"]''' % (index-1, index, heap_info[0])
                continue

            # table format
            content = '''n%s[shape=none, label=<<table border="0" cellborder="1" cellspacing="0" cellpadding="4">''' % (index)

            # when the node is the overflow one
            if heap_info[0].startswith("Found overflow") and len(heap_info) == 3:
                label_dot += '''n%s%s[shape=box,label="%s"]''' % (index, index, heap_info[2])
                edge_dot += '''{rank = same; n%s->n%s%s[style=dotted label="%s"]}''' % (index, index, index, "memory content")

            # when the node is the mem write one
            if heap_info[0].startswith("Mem write"):
                label_dot += '''n%s[shape=box,label="%s"]''' % (index, heap_info[1])
                label_dot += '''n%s%s[shape=box,label="%s"]''' % (index, index, heap_info[2])
                edge_dot += '''n%s->n%s[label="%s"]''' % (index-1, index, heap_info[0])
                edge_dot += '''{rank = same; n%s->n%s%s[style=dotted label="%s"]}''' % (index, index, index, "Stack")
                continue

            # construct the heap node graph ande highlight the overflow part
            for info in heap_info[1]:
                if len(info) < 3:
                        break
                if info[2].startswith("Found overflow"):
                    content += '''<tr><td bgcolor="lightgrey"><font color="red">%s size:%s</font></td></tr>''' % (
                        info[0], info[1])
                    continue
                content += '''<tr><td>%s size:%s</td></tr>''' % (info[0], info[1])

            content += '''</table>>]'''
            label_dot += content
            edge_dot += '''n%s->n%s[label="%s"]''' % (index - 1, index, heap_info[0])


        dot = head_dot + label_dot + edge_dot + tail_dot
        t = Source(dot)
        t.save("HeapChange.dot")
        os.system("dot ./HeapChange.dot -T png -o ./HeapChange.png")
        return os.path.join(os.getcwd(), 'HeapChange.png')


def extract_strange_rop(headline, f):
    '''
    :param headline: the first line
    :param f: file stream
    :return:
    '''
    strange_info = {}
    strange_info['situation'] = headline[:-2]
    obj = re.match("From (.*) to (.*)", f.readline())
    if obj:
        strange_info['jump'] = (obj.group(1) + "->\n" + obj.group(2)).replace('\n', '<br>')

    while not f.readline().startswith("Args:"):
        pass

    args = ""
    while True:
        line = f.readline()
        if line is '\n':
            break
        args += line
    strange_info['info'] = ("args:\n" + args[:-1]).replace('\n', '<br>')
    return strange_info

def extract_overflow_rop(headline, f):
    '''
    for overflow info, highlight with red color
    :param headline: the first line
    :param f: file stream
    :return:
    '''
    overflow_info = {}
    sitobj = re.match('(.*) changed from (.*) to (.*)', headline)
    if sitobj:
        overflow_info['situation'] = '''<font color="red">''' + \
                                     sitobj.group(1) + \
                                     '''</font>'''
        overflow_info['jump'] = '''<font color="red">change:''' \
                                + sitobj.group(2) + "-><br>" + sitobj.group(3) + \
                                '''</font>'''

    info = ""
    while True:
        line = f.readline()
        if line is '\n':
            break
        info += line

    overflow_info['info'] = '''<font color="red">''' + \
                            info.replace('\n', '<br>') + \
                            '''</font>'''
    return overflow_info

def extract_unrecord_rop(headline, f):
    '''
    for unrecord info, highligth with green color
    :param headline: the first line
    :param f: file stream
    :return:
    '''
    unrecord_info = {}
    unrecord_info['situation'] = '''<font color="green">''' + headline[:-1] + '''</font>'''
    obj = re.match("From (.*) to (.*)", f.readline())
    if obj:
        unrecord_info['jump'] = '''<font color="green">''' + \
                                (obj.group(1) + "->\n" + obj.group(2)).replace('\n', '<br>') + \
                                '''</font>'''
    while not f.readline().startswith("Args:"):
        pass

    args = ""
    while True:
        line = f.readline()
        if line is '\n':
            break
        args += line
    unrecord_info['info'] = '''<font color="green">''' + \
                            ("args:\n" + args[:-1]).replace('\n', '<br>') + \
                            '''</font>'''
    return unrecord_info


class view_call_log(object):

    def __init__(self, path):
        self.path = path

    def get_rop_table(self):
        '''
        :return: a list whose format is for jinja2
        '''
        f = open(self.path, 'r')
        rop_list = []
        while True:
            line = f.readline()
            if not line:
                break

            if line.startswith("Strange return to"):
                rop_list.append(copy.deepcopy(extract_strange_rop(line, f)))
                continue

            if line.startswith("address "):
                rop_list.append(copy.deepcopy(extract_overflow_rop(line, f)))
                continue

            if line.startswith("Unrecorded return to"):
                rop_list.append(copy.deepcopy(extract_unrecord_rop(line, f)))

        return rop_list