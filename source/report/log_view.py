import re
import copy
from graphviz import Digraph
import os
import json
from ansi2html import Ansi2HTMLConverter
from jinja2 import Markup
from termcolor import colored
import copy
from .type_info import desc_dict, key_replace_dict

# converter for ansi input    
conv = Ansi2HTMLConverter()
def escape_ansi(line):
    ansi_escape = re.compile(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', line)

def html_format(dict):
    global conv
    result = {}
    # set message color
    if dict["level"] == "warning":
        dict["message"] = colored(dict["message"], "red")
    # drop useless item
    dict.pop("name", None)
    dict.pop("level", None)
    # add desc
    if "type" in dict:
        result["Description"] = desc_dict[dict["type"]]
    dict.pop("type", None)
    # html and color format
    for key, val in dict.items():
        if isinstance(val, str):
            dict[key] = conv.convert(val, full=False)
        elif isinstance(val, int):
            dict[key] = hex(val)
        dict[key] = dict[key].replace("\n", "<br/>")
        dict[key] = dict[key].replace("\t", "&emsp;"*2)
    # replace some key name to be more neat
    for k,v in dict.items():
        if k=='message'or k=='type'or k=='level':
            result[k] = v
            continue
        if k in key_replace_dict:
            k = key_replace_dict[k]
            result[k] = v
            continue
        k = k.replace("_", "&nbsp")
        if len(k)>1:
            k = k[0].upper()+k[1:]
        result[k] = v
    return result

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
    #result = "\n" + result 
    return result+"<br/>"


def overflow_heap_info(node_info, overflow_info):
    '''
    judge which heap is overflow point
    :param node_info: a list of heap info
    :param overflow_info: a node which is overflow
    :return: the node which is overflow point
    '''
    for info in node_info:
        start = info['addr']-0x10
        end = start + info['size']
        overflow_start = overflow_info['addr']
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

def no_message_tips(output_list):
    if output_list == []:
        output_list.append({"message":"Not enabled or nothing to report."})
    return output_list

class report_log(object):
    def __init__(self, log_path):
        self.log_path = log_path
        self.heap_log_list, self.call_log_list,\
             self.leak_log_list, self.got_log_list,\
                 self.heap_log_list_dot , self.warning_statestamp_list = self.__parse_log_file()

    def __parse_log_file(self):
        heap_log_list_html = []
        call_log_list_html = []
        leak_log_list_html = []
        got_log_list_html = []
        heap_log_list_dot = []
        warnging_statestamp_list = []

        f = open(self.log_path, 'r')
        lines = f.readlines()
        for line in lines:
            dict = json.loads(line[:-1])
            del dict['logger_factory']
            del dict['timestamp']
            del dict['logger']
            name = dict['name']

            if 'state_timestamp' in dict.keys():
                dict['message'] = '[%s] %s' % (dict['state_timestamp'], dict['message'])
                # if dict['level'] == 'warning':
                warnging_statestamp_list.append([dict['type'], (dict['state_timestamp'])])

            dict_bak = copy.deepcopy(dict)
            dict = html_format(dict)
            if name == 'heap_analysis':
                heap_log_list_html.append(dict)
                dot_dict = (dict_bak)
                heap_log_list_dot.append(dot_dict)
            elif name == 'call_analysis':
                call_log_list_html.append(dict)
            elif name == 'got_analysis':
                got_log_list_html.append(dict)
            elif name == 'leak_analysis':
                leak_log_list_html.append(dict)
        f.close()
        return heap_log_list_html, call_log_list_html, leak_log_list_html, \
               got_log_list_html, heap_log_list_dot, warnging_statestamp_list


    def get_leak_output(self):
        return no_message_tips(self.leak_log_list)

    def get_got_output(self):
        return no_message_tips(self.got_log_list)

    def get_call_output(self):
        return no_message_tips(self.call_log_list)

    def get_heap_output(self):
        return no_message_tips(self.heap_log_list)

    def get_warning_statestamp(self):
        return self.warning_statestamp_list

    def get_heap_graph(self):

        def _heap_trans_list(list):
            heap_infos = []
            node_info = []
            for dict in list:
                dict = fix_br_format(dict)
                type = dict['type']
                if type == 'malloc':
                    content = '[%s] %s' % (dict['state_timestamp'], dict['message'])
                    malloc_info = {'addr': dict['addr'], \
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
                    calloc_info = {'addr': dict['addr'], \
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

        def _generate_heap_node_label(heap_info):
            label_dot = '''<<table border="0" cellborder="1" cellspacing="0" cellpadding="4">'''

            # when the node is empty
            if len(heap_info["node"])==0:
                label_dot += "<tr><td>......</td></tr></table>>"
                return label_dot

            # construct the heap node graph ande highlight the overflow part
            for info in heap_info['node']:
                if info['type'] == "heap_overflow":
                    label_dot += '''<tr><td bgcolor="lightgrey"><font color="red">%s size:%s</font></td></tr>''' % (
                        info['addr'], info['size'])
                    continue
                label_dot += '''<tr><td>%s size:%s</td></tr>''' % (info['addr'], info['size'])
            label_dot += '''</table>>'''
            return label_dot


        heap_infos = _heap_trans_list(self.heap_log_list_dot)
        dot = Digraph(name="heapPictruce")
        index = 0
        dot.node(name="n0", shape="record", label="......")
        for heap_info in heap_infos:
            index += 1


            if "node" in heap_info.keys():
                dot.node(name="n%s"%index, label=_generate_heap_node_label(heap_info), shape='none')

            # when the node is the overflow one
            if heap_info['type'] == "heap_overflow":
                dot.node("n%s_%s"%(index,index), shape="box", label="<%s>"%heap_info["memory"])
                with dot.subgraph() as s:
                    s.attr(rank="same")
                    s.edge("n%s"%index, "n%s_%s"%(index, index), style="dotted", label="memory content")

            # when the node is the mem write one
            if heap_info['type'] == 'redzone_write':
                dot.node("n%s"%index, shape="box", label="<%s>"%heap_info["memory"])
                dot.node("n%s_%s"%(index,index), shape="box", label="<%s>"%heap_info["backtrace"])
                dot.edge("n%s"%(index-1), "n%s"%index, sytle="dotted", label=heap_info["content"])
                with dot.subgraph() as s:
                    s.attr(rank="same")
                    s.edge("n%s"%index, "n%s_%s"%(index, index), style="dotted")
                continue

            dot.edge("n%s"%(index-1), "n%s"%index, label=heap_info["content"])


        dot.render("/tmp/HeapChange.dot")
        os.system("dot /tmp/HeapChange.dot -Tpng -o /tmp/HeapChange.png")
        return "/tmp/HeapChange.svg"



