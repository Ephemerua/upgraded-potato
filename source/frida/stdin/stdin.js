var fd, buf_addr, length;
var out_file = new File('stdin.dump', 'wb');

Interceptor.attach(
    DebugSymbol.fromName('read').address, 
    {
        onEnter: function(args) {
            fd = args[0].toInt32();
            buf_addr = args[1];
            length = args[2].toInt32();
        },
        onLeave: function(ret_val) {
            if (fd == 0) {
                var buffer = buf_addr.readByteArray(length);
                // console.log(buffer);
                out_file.write(buffer);
            }
        }
    }
);

// TODO: out_file needs to be closed after the process has terminated
