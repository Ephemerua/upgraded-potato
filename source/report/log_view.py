import re
import copy
from graphviz import Source
import os
import json


def set_html_color(dict, color):
    for key, val in dict.items():
        dict[key] = '''<font color="%s">%s</font>''' % (color, val)
    return dict

def fix_br_format(dict):
    for key, val in dict.items():
        if isinstance(val, str):
            dict[key] = val.replace('\n', '<br/>')
    return dict

def fix_format(dict):
    if 'backtrace' in dict.keys():
        dict['backtrace'] = '\n' + dict['backtrace']
    for key, val in dict.items():
        if isinstance(val, int):
            dict[key] = "%s" % hex(val)
    return dict

def memory_color_htmlformat(str):
    '''
    replace the ansi format, only red and yellow
    :param str: memory str
    :return: memory str with html format
    '''
    def _replace_format(matched):
        if matched.group('yellow') is not None:
            num = re.match('\\u001b\\[33m([0-9a-fA-F]{0,2})\\u001b\\[0m', matched.group('yellow'))
            # print(num.group(1))
            return "<font color='#EACE00'>%s</font>" % num.group(1)
        elif matched.group('red') is not None:
            num = re.match('\\u001b\\[33m\\u001b\\[31m([0-9a-fA-F]{0,2})\\u001b\\[0m\\u001b\\[0m', matched.group('red'))
            # print(num.group(1))
            return "<font color='red'>%s</font>" % num.group(1)

    result = re.sub('(?P<yellow>\\u001b\\[33m[0-9a-fA-F]{0,2}\\u001b\\[0m)|(?P<red>\\u001b\\[33m\\u001b\\[31m[0-9a-fA-F]{0,2}\\u001b\\[0m\\u001b\\[0m)', _replace_format, str)
    result = '\n' + result
    return result

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
            info['type'] = overflow_info['type']
            break
    return node_info

def free_heap_info(node_info, free_info):
    '''
    delete the released heap
    :param node_info: a list of heap info
    :param free_info: a node which will be free
    :return: the node which will be free in heap info
    '''
    index = 0
    for info in node_info:
        if info['addr'] == free_info['addr']:
            del node_info[index]
            return node_info
        index += 1
    return node_info

class report_log(object):
    def __init__(self, log_path):
        self.log_path = log_path
        self.heap_log_list, self.call_log_list, self.leak_log_list, self.got_log_list = self.__parse_log_file()

    def __parse_log_file(self):
        heap_log_list = []
        call_log_list = []
        leak_log_list = []
        got_log_list = []
        f = open(self.log_path, 'r')
        lines = f.readlines()
        for line in lines:
            dict = json.loads(line[:-1])
            del dict['logger_factory']
            del dict['timestamp']
            del dict['logger']
            name = dict['name']
            if 'statestamp' in dict.keys():
                dict['message'] = '[%s] %s' % (hex(dict['statestamp']), dict['message'])
            fix_format(dict)
            if name == 'heap_analysis':
                heap_log_list.append(dict)
            elif name == 'call_analysis':
                call_log_list.append(dict)
            elif name == 'got_analysis':
                got_log_list.append(dict)
            elif name == 'leak_analysis':
                leak_log_list.append(dict)
        f.close()
        return heap_log_list, call_log_list, leak_log_list, got_log_list

    def get_leak_output(self):
        for dict in self.leak_log_list:
            fix_br_format(dict)
        return self.leak_log_list

    def get_got_output(self):
        for dict in self.got_log_list:
            fix_br_format(dict)
        return self.got_log_list

    def get_call_output(self):
        for dict in self.call_log_list:
            type = dict['type']
            if type == 'return_address_overwritten':
                set_html_color(dict, 'red')
            elif type == 'unrecorded_strange_return':
                set_html_color(dict, 'green')
            fix_br_format(dict)
        return self.call_log_list

    def get_heap_output(self):
        for dict in self.heap_log_list:
            if 'memory' in dict.keys():
                dict['memory'] = memory_color_htmlformat(dict['memory'])
            fix_br_format(dict)
        return self.heap_log_list

    def get_heap_graph(self):


        def _heap_trans_list(list):
            heap_infos = []
            node_info = []
            for dict in list:
                dict = fix_br_format(dict)
                type = dict['type']
                if type == 'malloc':
                    content = '[%s] %s' % (dict['state_timestamp'], dict['message'])
                    malloc_info = {'addr': dict['ret_addr'], \
                                   'size': dict['size'], \
                                   'statestamp': dict['state_timestamp'], \
                                   'content': content, \
                                   'type': dict['type']}
                    node_info.append(malloc_info)
                    heap_infos.append({'content': content, \
                                       'type': dict['type'], \
                                       'node': copy.deepcopy(node_info)})

                elif type == 'calloc':
                    content = '[%s] %s' % (dict['state_timestamp'], dict['message'])
                    calloc_info = {'addr': dict['ret_addr'], \
                                   'size': dict['size'], \
                                   'statestamp': dict['state_timestamp'], \
                                   'content': content, \
                                   'type': dict['type']}
                    node_info.append(calloc_info)
                    heap_infos.append({'content': content, \
                                       'type': dict['type'], \
                                       'node': copy.deepcopy(node_info)})

                elif type == 'free':
                    content = '[%s] %s' % (dict['state_timestamp'], dict['message'])
                    free_info = {'addr': dict['addr'], \
                                 'size': dict['size'], \
                                 'statestamp': dict['state_timestamp'], \
                                 'content': content, \
                                 'type': dict['type']}
                    node_info = free_heap_info(node_info, free_info)
                    heap_infos.append({'content': content, \
                                       'type': dict['type'], \
                                       'node': copy.deepcopy(node_info)})

                elif type == 'heap_overflow':
                    overflow_info = {'addr': dict['target_addr'], \
                                     'size': dict['target_size'], \
                                     'content': '[%s] %s' % (dict['state_timestamp'], dict['message']), \
                                     'type': dict['type']}
                    node_info = overflow_heap_info(node_info, overflow_info)
                    # add the memory info by extract_memory()
                    heap_infos.append({'content': '[%s] %s' % (dict['state_timestamp'], dict['message']), \
                                       'type': dict['type'], \
                                       'node': copy.deepcopy(node_info), \
                                       'memory': memory_color_htmlformat(dict['memory'])})

                elif type == 'redzone_write':
                    heap_infos.append({'content': '[%s] %s' % (dict['state_timestamp'], dict['message']), \
                                       'type': dict['type'], \
                                       'memory': memory_color_htmlformat(dict['memory']), \
                                       'backtrace': dict['backtrace']})
            return heap_infos


        heap_infos = _heap_trans_list(self.heap_log_list)
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
                    edge_dot += '''n%s->n%s[label="%s"]''' % (index - 1, index, heap_info['content'])
                    continue

                # construct the heap node graph ande highlight the overflow part
                for info in heap_info['node']:
                    if info['type'] == "heap_overflow":
                        content += '''<tr><td bgcolor="lightgrey"><font color="red">%s size:%s</font></td></tr>''' % (
                            info['addr'], info['size'])
                        continue
                    content += '''<tr><td>%s size:%s</td></tr>''' % (info['addr'], info['size'])

            # when the node is the overflow one
            if heap_info['type'] == "heap_overflow":
                label_dot += '''n%s%s[shape=box,label=<%s>]''' % (index, index, heap_info['memory'])
                edge_dot += '''{rank = same; n%s->n%s%s[style=dotted label="%s"]}''' % (
                index, index, index, "memory content")

            # when the node is the mem write one
            if heap_info['type'] == 'redzone_write':
                label_dot += '''n%s[shape=box,label=<%s>]''' % (index, heap_info['memory'])
                label_dot += '''n%s%s[shape=box,label=<%s>]''' % (index, index, heap_info['backtrace'])
                edge_dot += '''n%s->n%s[label="%s",style=dotted]''' % (index - 1, index, heap_info['content'])
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




