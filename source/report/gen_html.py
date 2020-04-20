from jinja2 import Environment, FileSystemLoader
from source.report.log_view import *

def generate_html(got_table, image_path, body, starttime, stoptime):
    env = Environment(loader=FileSystemLoader('./'))
    template = env.get_template('template.html')
    with open('report.html', 'w+') as fout:
        html_content = template.render(start_time=starttime,
                                       stop_time=stoptime,
                                       gottable=got_table,
                                       img_path=image_path,
                                       body=body)
        fout.write(html_content)

if __name__ == '__main__':
    body = []
    View_heap_log("../../test/sample/heap_analy.log").gen_heap_change_png()
    got_table = View_got_log("../../test/sample/got_analy.log").get_got_change()
    generate_html(got_table, "./HeapChange.png", body, 2019, 2020)