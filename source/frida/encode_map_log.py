import json
import os
import base64

def content_base64_encode(log_path, binary):
    f = open(log_path, 'rb')
    lines = f.readlines()
    f.close()
    index = log_path.index('.')
    # name = binary.split('/')
    base64_file = log_path[0:index+1] + binary.split('/')[-1] + log_path[index:]
    f = open(base64_file, 'w')
    for line in lines:
        dict = json.loads(line[:-1])
        content = dict['content']
        if content != '':
            content = content.encode()
            dict['content'] = bytes(base64.b64encode(content)).decode('utf8')
        f.write(json.dumps(dict) + '\n')
        f.flush()
    f.close()
    # if os.path.exists(log_path):
    #     os.remove(log_path)
    return base64_file


content_base64_encode('map.30830', 'test')