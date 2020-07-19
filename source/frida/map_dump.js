// this func has some problems
//function bytesToBase64(e) {
//    var base64EncodeChars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
//    var r, a, c, h, o, t;
//    for (c = e.length, a = 0, r = ''; a < c;) {
//        if (h = 255 & e[a++], a == c) {
//            r += base64EncodeChars.charAt(h >> 2),
//            r += base64EncodeChars.charAt((3 & h) << 4),
//            r += '==';
//            break
//        }
//        if (o = e[a++], a == c) {
//            r += base64EncodeChars.charAt(h >> 2),
//            r += base64EncodeChars.charAt((3 & h) << 4 | (240 & o) >> 4),
//            r += base64EncodeChars.charAt((15 & o) << 2),
//            r += '=';
//            break
//        }
//        t = e[a++],
//        r += base64EncodeChars.charAt(h >> 2),
//        r += base64EncodeChars.charAt((3 & h) << 4 | (240 & o) >> 4),
//        r += base64EncodeChars.charAt((15 & o) << 2 | (192 & t) >> 6),
//        r += base64EncodeChars.charAt(63 & t)
//    }
//    return r
//}


function get_prot(rwx) {
    var prot = 0;
    if(rwx[0] == 'r')
        prot += 4;
    if(rwx[1] == 'w')
        prot += 2;
    if(rwx[2] == 'x')
        prot += 1;
    return prot;
}

function get_obj(file) {
    var obj = file.substring(file.lastIndexOf('/') + 1);
//    console.log(obj)
    return obj;
}

function get_content(addr, size) {
    var base = new NativePointer(addr)
//    console.log(addr+' content in')
    var content = Memory.readCString(base, size);
//    console.log('ininin')

//    base64 = bytesToBase64(content)
//    var buff = new Buffer('hello world')
//    console.log(buff.toString('base64'))
//    return base64;
    return content
}

function parse(lists) {
    var f = new File('map.' + Process.id, 'wb');
    console.log(lists.length)
    for(var i=0;i<lists.length;i++) {
        if(lists[i].hasOwnProperty('file') == false)
            continue
        var map = {}
        console.log(i+lists[i]['base']);
        map['start'] = parseInt(lists[i]['base'])
        map['end'] = map['start'] + lists[i]['size']
        map['prot'] = get_prot(lists[i]['protection'])
        map['obj'] = get_obj(lists[i]['file']['path'])
        map['content'] = ''
        if(lists[i]['protection'][1] == 'w')
            map['content'] = get_content(lists[i]['base'], lists[i]['size'])
        f.write(JSON.stringify(map) + '\n');
    }
    f.flush();
    f.close();
}

function hook() {
    console.log(DebugSymbol.fromName('init'));
    console.log(DebugSymbol.fromName('__libc_start_main'));
    console.log('Tracing initiated');
    Interceptor.attach(DebugSymbol.fromName('main').address, {
        onEnter: function(args) {
            console.log("in" + this.returnAddress);
//            var maps = {}
            //maps['modules'] = Process.enumerateModules();
//            console.log(JSON.stringify(Process.enumerateModules()))
            //maps['pid'] = Process.id;
            //maps['arch'] = Process.arch;
            //maps['platform'] = Process.platform;
            //maps['mallocranges'] = Process.enumerateRanges('---');
            var lists = Process.enumerateRanges('---');
            var lists2 = Process.enumerateModules();
//            console.log(JSON.stringify(lists));
            parse(lists)
            //maps['backtrace'] =  Thread.backtrace(this.context, Backtracer.ACCURATE);
            //maps['bp'] = this.context.rbp;
            console.log('rbp '+this.context.rbp);
            //maps['context'] = this.context;
            //console.log(maps);
//            send(maps);
        },
        onLeave: function(retval){
            console.log("out" + retval.toInt32());
        }
    });
}

//function hook_scanf() {
//    console.log(DebugSymbol.fromName('__isoc99_scanf'));
//    console.log(DebugSymbol.fromName('output'))
////    var st = Memory.allocUtf8String("TESTMEPLZ!");
////    var printf = new NativeFunction(DebugSymbol.getFunctionByName('printf'), 'int', ['pointer']);
////    printf(st);
//    Interceptor.attach(DebugSymbol.fromName('output').address, {
//        onEnter: function(args) {
//            console.log()
//
//        },
//        onLeave: function(retval){
//            console.log("out scanf" + retval.toInt32());
//        }
//    });
//}

//setImmediate(hook)
hook()
//setImmediate(hook_scanf)
//hook_scanf()