from jinja2 import Environment, FileSystemLoader
from source.report.log_view import *
import time

def generate_report(template_path, report_path = "report.html", got_log_path = "", heap_log_path = "", leak_log_path = ""):
    '''

    :param template_path:
    :param report_path:
    :param got_log_path:
    :param heap_log_path:
    :param leak_log_path:
    :return:
    '''
    def generate_html(template_path, report_path, got_table="", image_path="", leak_table=""):
        '''

        :param template_path:
        :param report_path:
        :param got_table:
        :param image_path:
        :param leak_table:
        :return:
        '''
        env = Environment(loader=FileSystemLoader('./'))
        template = env.get_template(template_path)

        report_time = time.strftime('%Y.%m.%d', time.localtime(time.time()))
        with open(report_path, 'w+') as fout:
            html_content = template.render(reporttime=report_time,
                                           gottable=got_table,
                                           img_path=image_path,
                                           leaktable=leak_table)
            fout.write(html_content)

    image_path = ""
    got_table = []
    leak_table = []
    if got_table is not "":
        got_table = view_got_log(got_log_path).get_got_change()

    if heap_log_path is not "":
        image_path = view_heap_log(heap_log_path).gen_heap_change_png()

    if leak_table is not "":
        leak_table = view_leak_log(leak_log_path).get_leak_table()

    generate_html(template_path, report_path, got_table, image_path, leak_table)

if __name__ == '__main__':
    generate_report("./template.html", "./report_new2.html", got_log_path="../../test/sample/got_analy.log", heap_log_path="../../test/sample/heap_analy.log",
                    leak_log_path="../../test/sample/leak_analy.log")