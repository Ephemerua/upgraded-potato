from jinja2 import Environment, FileSystemLoader
from report.log_view import *
from report.env_view import *
import time

def generate_report(binary_path, template_path, report_path = "report.html", \
                    got_log_path = "", heap_log_path = "", leak_log_path = "", \
                    call_log_path = ""):
    '''

    :param template_path:
    :param report_path:
    :param got_log_path:
    :param heap_log_path:
    :param leak_log_path:
    :return:
    '''
    checksec_info = get_checksec_info(binary_path).replace("\n", "<br>")
    os_info = get_os_info()
    image_path = ""
    got_table = []
    leak_table = []
    rop_table = []
    if got_log_path is not "":
        got_table = view_got_log(got_log_path).get_got_change()

    if heap_log_path is not "":
        image_path = view_heap_log(heap_log_path).gen_heap_change_png()

    if leak_log_path is not "":
        leak_table = view_leak_log(leak_log_path).get_leak_table()

    if call_log_path is not "":
        rop_table = view_call_log(call_log_path).get_rop_table()

    def generate_html(got_table=[], image_path=[], leak_table=[], rop_table=[]):
        '''
        :param got_table:
        :param image_path:
        :param leak_table:
        :return:
        '''
        env = Environment(loader=FileSystemLoader("../../html/"))
        template = env.get_template(template_path)

        report_time = time.strftime('%Y.%m.%d', time.localtime(time.time()))
        with open("../../html/" + report_path, 'w+') as fout:
            html_content = template.render(osinfo=os_info, \
                                           checksecinfo=checksec_info, \
                                           reporttime=report_time, \
                                           gottable=got_table, \
                                           img_path=image_path, \
                                           leaktable=leak_table, \
                                           calltable=rop_table)
            fout.write(html_content)

    generate_html(got_table, image_path, leak_table, rop_table)

if __name__ == '__main__':
    generate_report("../../test/sample/easyheap","./template.html", "./report_new.html", \
                    got_log_path="../../test/sample/got_analy.log", \
                    heap_log_path="../../test/sample/heap_analy.log", \
                    leak_log_path="../../test/sample/leak_analy.log", \
                    call_log_path="../../test/sample/call_analy.log")