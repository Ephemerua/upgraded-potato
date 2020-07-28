/* 
 * On opening a file, we create two files: $path.read.dump and $path.write.dump
 * The File objects are stored in a dictionary where the key is the file descriptor
 * On reading a file we save the buffer in $path.read.dump
 * On writing to a file we save the buffer in $path.write.dump
 * On closing a file we close the two File objects
 * 
 * 
 * TODO: this module can merge into stdin.js
 */

var files = {};     //{fd1: [rd1, wr1], fd2: [rd2, wr2], ...}
var cnt = 1;

function create_file(path) {
    var f1 = new File(path + '.' + cnt.toString() + '.read.dump', 'wb');
    var f2 = new File(path + '.' + cnt.toString() + '.write.dump', 'wb');
    ++cnt;  //防止重名
    return [f1, f2];
}

Interceptor.attach(
    Module.getExportByName(null, 'open'), 
    {
        onEnter: function(args) {
            this.path = args[0].readCString();
        }, 
        onLeave: function(retval) {
            this.fd = retval.toInt32();
            if (this.fd > 0) {
                files[this.fd.toString()] = create_file(this.path);
            }
        }
    }
);

Interceptor.attach(
    Module.getExportByName(null, 'openat'), 
    {
        onEnter: function(args) {
            this.path = args[1].readCString();
        }, 
        onLeave: function(retval) {
            this.fd = retval.toInt32();
            if (this.fd > 0) {
                files[this.fd.toString()] = create_file(this.path);
            }
        }
    }
);

Interceptor.attach(
    Module.getExportByName(null, 'close'), 
    {
        onEnter: function(args) {
            this.fd = args[0].toInt32();
        }, 
        onLeave: function(retval) {
            if (retval.toInt32() != -1) {
                files[this.fd.toString()][0].flush();
                files[this.fd.toString()][1].flush();
                files[this.fd.toString()][0].close();
                files[this.fd.toString()][1].close();
                delete files[this.fd.toString()];
            }
        }
    }
);

Interceptor.attach(
    Module.getExportByName(null, 'read'), 
    {
        onEnter: function(args) {
            this.fd = args[0].toInt32();
            this.buf_addr = args[1];
        }, 
        onLeave: function(retval) {
            var length = retval.toInt32();
            if (length != -1) {
                var buffer = this.buf_addr.readByteArray(length);
                console.log(buffer);
                files[this.fd.toString()][0].write(buffer);
            }
        }
    }
);

Interceptor.attach(
    Module.getExportByName(null, 'write'), 
    {
        onEnter: function(args) {
            this.fd = args[0].toInt32();
            this.buf_addr = args[1];
        }, 
        onLeave: function(retval) {
            var length = retval.toInt32();
            if (length != -1) {
                var buffer = this.buf_addr.readByteArray(length);
                console.log(buffer);
                files[this.fd.toString()][1].write(buffer);
            }
        }
    }
);
