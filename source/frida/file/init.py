import sys
import time
import frida


def on_message(message, data):
    print(message)


pid = frida.spawn(['./test'])
session = frida.attach(pid)

js = r"""
var cnt = 0;

function copy_file(fd, path) {
    // FIXME: this step often fails
    var uis = new UnixInputStream(fd);

    // Only leave file name for absolute path
    var out_file_name = path.substr(path.lastIndexOf('/') + 1) + (cnt++).toString() + '.dump';
    console.log('out_file_name: ', out_file_name);
    var out_file = new File(out_file_name, "wb");

    // FIXME: we get nothing in out_file
    var buffer = uis.read(5);
    out_file.write(buffer);
    console.log('buffer: ', buffer);
    
    // while (buffer = uis.read(1024)) {
    //     out_file.write(buffer);
    // }
    out_file.close();
}

var files = {}; // {fd1: file_name1, fd2: file_name2, ...}
var path, fd;

Interceptor.attach(DebugSymbol.fromName('open').address, {
    onEnter: function(args) {
        // only ACSII is supported
        path = args[0].readCString();
    },
    onLeave: function(ret_val) {
        fd = ret_val.toInt32();
        console.log('opened  fd:', fd, 'path:', path);
        if (fd > 0) {
            files[fd.toString()] = path;
        }
    }
});

Interceptor.attach(DebugSymbol.fromName('openat').address, {
    onEnter: function(args) {
        fd = args[0].toInt32();
        path = args[1].readCString();
        if (fd > 0) {
            files[fd.toString()] = path;
        }
    }
});

Interceptor.attach(DebugSymbol.fromName('close').address, {
    onEnter: function(args) {
        fd = args[0].toInt32();
        copy_file(fd, files[fd.toString()]);
    },
    onLeave: function(ret_vat){
        delete files[fd.toString()];
        console.log(files);
    }
});

// TODO: what if the program does NOT call close?

"""

script = session.create_script(js)
script.on('message', on_message)
script.load()
time.sleep(5)
frida.resume(pid)

sys.stdin.read()
frida.kill(pid)
