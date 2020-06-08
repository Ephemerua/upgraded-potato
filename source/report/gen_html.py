from jinja2 import Environment, FileSystemLoader
from report.log_view import *
from report.env_view import *
import time

def generate_report(binary_path, template_name="template.html", report_name = "report.html", \
                    analysis_path = ""):
    '''
    the report will be generated in ../../html/
    :param binary_path:
    :param template_name:
    :param report_name:
    :param analysis_path:
    :return:
    '''

    path = __file__[:__file__.rfind("/")+1]

    checksec_info = get_checksec_info(binary_path).replace("\n", "<br/>")
    os_info = get_os_info()

    report = report_log(analysis_path)

    got_output = report.get_got_output()
    leak_output = report.get_leak_output()
    call_output = report.get_call_output()
    heap_output = report.get_heap_output()
    heap_image_path = report.get_heap_graph()


    def generate_html(got_output=[], heap_image_path="/tmp/HeapChange.png", heap_output=[] , leak_output=[], call_output=[]):
        '''
        :param got_table:
        :param image_path:
        :param leak_table:
        :return:
        '''
        path = __file__[:__file__.rfind("/")]
        work_path = os.getcwd()
        print(work_path)
        os.system("cp -rf %s/html %s"%(path, work_path))
        html_path = os.getcwd()+"/html/"
        if os.access(heap_image_path,os.F_OK):
            os.system("cp -f %s %s" % (heap_image_path, html_path))
            heap_image_path = "./HeapChange.png"
        else:
            print("Heap change image not found!")
            heap_image_path = ""
        print(html_path)

        env = Environment(loader=FileSystemLoader(html_path))
        template = env.get_template(template_name)

        report_time = time.strftime('%Y.%m.%d', time.localtime(time.time()))
        with open(os.path.join(html_path, report_name), 'w+') as fout:
            html_content = template.render(osinfo=os_info, \
                                           checksecinfo=checksec_info, \
                                           reporttime=report_time, \
                                           gotoutput=got_output, \
                                           img_path=heap_image_path, \
                                           leakoutput=leak_output, \
                                           heapoutput=heap_output, \
                                           calloutput=call_output)
            fout.write(html_content)

    generate_html(got_output, heap_image_path, heap_output, leak_output, call_output)

if __name__ == '__main__':
    generate_report("../../test/packed_heap_sample/easyheap", report_name="report_new.html", \
                    analysis_path="../../test/packed_heap_sample/analysis.log")