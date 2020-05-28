import re
import copy
from graphviz import Source
import os
import json


def parse_log_file(path):
    log_lists = []
    f = open(path, 'r')
    lines = f.readlines()
    for line in lines:
        dict = json.loads(line[:-1])
        if "record" in dict.keys():
            log_lists.append(dict)
    return log_lists


class view_leak_log(object):
    def __init__(self, path):
        self.path = path

    def get_leak_table(self):
        '''
        :return: a list whose format is for jinja2
        '''
        # list = parse_log_file(self.path)
        list = parse_log_file(self.path)
        for dict in list:
            dict['name'] = dict['leakname']
            del dict['leakname']
        return list


class view_got_log(object):
    def __init__(self, path):
        self.path = path

    def get_got_change(self):
        '''
        :return: a list whose format is for jinja2
        '''
        list = parse_log_file(self.path)
        got_list = []
        for dict in list:
            got_dict = {}
            got_dict['mismatch'] = dict['mismatch'] + '[addr:' + dict['addr'] + ']'
            got_dict['function'] = dict['function'] + '[file:' + dict['file'] + ']'
            got_list.append(got_dict)

        return got_list


def overflow_heap_info(node_info, overflow_info):
    '''
    judge which heap is overflow point
    :param node_info: a list of heap info
    :param overflow_info: a node which is overflow
    :return: the node which is overflow point
    '''
    for info in node_info:
        start = int(info['addr'], 16)-0x10
        end = start + int(info['size'], 16)
        overflow_start = int(overflow_info['addr'], 16)
        if overflow_start >= start and overflow_start <= end:
            info['content'] = overflow_info['content']
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
        if info['addr'] == free_info['addr']:
            success = True
            break
        index += 1
    if success:
        del node_info[index]
        return node_info
    else:
        return node_info

def delete_color_format(str):
    return str.replace('[0m', '').replace('[33m', '').replace('[31m', '')

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
            node_info = []
            list = parse_log_file(path)
            for dict in list:
                if dict['type'] == 'malloc':
                    malloc_info = {'addr': dict['addr'], \
                                   'size': dict['size'], \
                                   'content': dict['content'], \
                                   'type': dict['type']}
                    node_info.append(malloc_info)
                    heap_infos.append({'content': dict['content'], \
                                       'type': dict['type'], \
                                       'node': copy.deepcopy(node_info)})
                    continue

                if dict['type'] == 'calloc':
                    calloc_info = {'addr': dict['addr'], \
                                   'size': dict['size'], \
                                   'content': dict['content'], \
                                   'type': dict['type']}
                    node_info.append(calloc_info)
                    heap_infos.append({'content': dict['content'], \
                                       'type': dict['type'], \
                                       'node': copy.deepcopy(node_info)})
                    continue

                if dict['type'] == 'free':
                    free_info = {'addr': dict['addr'], \
                                   'size': dict['size'], \
                                   'content': dict['content'], \
                                   'type': dict['type']}
                    node_info = free_heap_info(node_info, free_info)
                    heap_infos.append({'content': dict['content'], \
                                       'type': dict['type'], \
                                       'node': copy.deepcopy(node_info)})
                    continue

                if dict['type'] == 'overflow':
                    overflow_info = {'addr': dict['addr'], \
                                   'size': dict['size'], \
                                   'content': dict['content'], \
                                   'type': dict['type']}
                    node_info = overflow_heap_info(node_info, overflow_info)
                    # add the memory info by extract_memory()
                    heap_infos.append({'content': dict['content'], \
                                       'type': dict['type'], \
                                       'node': copy.deepcopy(node_info), \
                                       'memory': delete_color_format(dict['memory'])})
                    continue

                if dict['type'] == 'memwrite':
                    heap_infos.append({'content': dict['content'], \
                                       'type': dict['type'], \
                                       'memory': delete_color_format(dict['memory']), \
                                       'callstack': dict['callstack']})

            return heap_infos


        heap_infos = parse_heap_change_log(self.path)
        head_dot = '''digraph G {n0[shape=reocord,label="......"]'''
        tail_dot = "}"
        label_dot = ""
        edge_dot = ""
        index = 0
        for heap_info in heap_infos:
            index += 1

            # table format
            content = '''n%s[shape=none, label=<<table border="0" cellborder="1" cellspacing="0" cellpadding="4">''' % (
                index)
            # when the node is empty
            if 'node' in heap_info.keys():
                if len(heap_info['node']) == 0:
                    label_dot += '''n%s[shape=record,label="......"]''' % (index)
                    edge_dot += '''n%s->n%s[label="%s"]''' % (index-1, index, heap_info['content'])
                    continue

                # construct the heap node graph ande highlight the overflow part
                for info in heap_info['node']:
                    if info['type'] == "overflow":
                        content += '''<tr><td bgcolor="lightgrey"><font color="red">%s size:%s</font></td></tr>''' % (
                            info['addr'], info['size'])
                        continue
                    content += '''<tr><td>%s size:%s</td></tr>''' % (info['addr'], info['size'])

            # when the node is the overflow one
            if heap_info['type'] == "overflow":
                label_dot += '''n%s%s[shape=box,label="%s"]''' % (index, index, heap_info['memory'])
                edge_dot += '''{rank = same; n%s->n%s%s[style=dotted label="%s"]}''' % (index, index, index, "memory content")

            # when the node is the mem write one
            if heap_info['type'] == 'memwrite':
                label_dot += '''n%s[shape=box,label="%s"]''' % (index, heap_info['memory'])
                label_dot += '''n%s%s[shape=box,label="%s"]''' % (index, index, heap_info['callstack'])
                edge_dot += '''n%s->n%s[label="%s",style=dotted]''' % (index-1, index, heap_info['content'])
                edge_dot += '''{rank = same; n%s->n%s%s[style=dotted]}''' % (index, index, index)
                continue

            content += '''</table>>]'''
            label_dot += content
            edge_dot += '''n%s->n%s[label="%s"]''' % (index - 1, index, heap_info['content'])


        dot = head_dot + label_dot + edge_dot + tail_dot
        t = Source(dot)
        t.save("HeapChange.dot")
        os.system("dot ./HeapChange.dot -Tsvg -o ./HeapChange.svg")
        return os.path.join(os.getcwd(), 'HeapChange.svg')

class view_call_log(object):

    def __init__(self, path):
        self.path = path

    def get_rop_table(self):
        '''
        :return: a list whose format is for jinja2
        '''
        list = parse_log_file(self.path)
        for dict in list:
            dict['info'] = dict['info'].replace('\n','<br>')
            dict['jump'] = dict['jump'].replace('\n','<br>')
            dict['block'] = dict['block'].replace('\n','<br>')
            if dict['type'] == 'unrecorded':
                for key,value in dict.items():
                    dict[key] = '''<font color="green">''' + value + '''</font>'''
                continue
            if dict['type'] == 'overflow':
                for key,value in dict.items():
                    dict[key] = '''<font color="red">''' + value + '''</font>'''

        return list