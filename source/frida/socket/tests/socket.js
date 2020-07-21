// var fd, buffer_addr, buffer, length;
var connections = {};   // {fd1: out_file1, fd2: out_file2, ...}
var cnt = 0;    // 防止输出文件重名

Interceptor.attach(
    DebugSymbol.fromName('accept').address,
    {
        onLeave: function(retval) {
            var fd = retval.toInt32();
            if (fd > 0) {
                // file name format: socket.$fd.$cnt.dump
                var out_file_name = 'socket.' + fd.toString() + '.' + (cnt++).toString() + '.dump';
                var out_file = new File(out_file_name, 'wb');
                connections[fd.toString()] = out_file;
            }
        }
    }
);

Interceptor.attach(
    Module.getExportByName(null, 'connect'),
    {
        onEnter: function(args) {
            this.fd = args[0].toInt32();
        },
        onLeave: function(retval) {
            if (retval.toInt32() != -1) {
                var out_file_name = 'socket.' + this.fd.toString() + '.' + (cnt++).toString() + '.dump';
                var out_file = new File(out_file_name, 'wb');
                connections[this.fd.toString()] = out_file;
            }
        }
    }
);

Interceptor.attach(
    Module.getExportByName(null, 'recvfrom'),
    {
        onEnter: function(args) {
            this.fd = args[0].toInt32();
            this.buffer_addr = args[1];
            this.new_connection = !args[4].isNull();
        },
        onLeave: function(retval) {
            if (retval.toInt32() != -1) {
                if (this.new_connection) {
                    var out_file_name = 'socket.' + this.fd.toString() + '.' + (cnt++).toString() + '.dump';
                    var out_file = new File(out_file_name, 'wb');
                    connections[this.fd.toString()] = out_file;
                }
                var buffer = this.buffer_addr.readByteArray(retval.toInt32());
                console.log(buffer);
                connections[this.fd.toString()].write(buffer);
            }
        }
    }
);

Interceptor.attach(
    DebugSymbol.fromName('recv').address, 
    {
        onEnter: function(args) {
            this.fd = args[0].toInt32();
            this.buffer_addr = args[1];
        },
        onLeave: function(retval) {
            if (retval.toInt32() != -1) {                
                var buffer = this.buffer_addr.readByteArray(retval.toInt32());
                console.log(buffer);
                connections[this.fd.toString()].write(buffer);
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
            if (retval != -1) {
                connections[this.fd.toString()].flush();
                connections[this.fd.toString()].close();
                delete connections[this.fd.toString()];
            }
        }
    }
);

// TODO: add function hook for recvmsg
