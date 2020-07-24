
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
    return obj;
}

function get_content(addr, size) {
  var base = new NativePointer(addr);
  var content = Buffer.alloc(size)
  for(var i=0;i<size;i++) {
    var pos = new NativePointer(addr+i);
    content[i] = pos.readCString(1).charCodeAt();
  }
  var base64 = content.toString('base64');
  return base64;
}

function parse(lists) {
    var f = new File('map.' + Process.id, 'wb');
//    console.log(lists.length)
    var json_lists=[]
    for(var i=0;i<lists.length;i++) {
        if(lists[i].hasOwnProperty('file') == false)
            continue
        var map = {}
//        console.log(i+lists[i]['base']);
        map['start'] = parseInt(lists[i]['base'])
        map['end'] = map['start'] + lists[i]['size']
        map['prot'] = get_prot(lists[i]['protection'])
        map['obj'] = get_obj(lists[i]['file']['path'])
        map['content'] = ''
        if(lists[i]['protection'][1] == 'w')
            map['content'] = get_content(map['start'], lists[i]['size'])
        json_lists.push(map)
    }
    f.write(JSON.stringify(json_lists));
    f.flush();
    f.close();
}

function hook() {
    console.log('Dump initiated');
    Interceptor.attach(DebugSymbol.fromName('main').address, {
        onEnter: function(args) {
            var lists = Process.enumerateRanges('---');
//            var lists2 = Process.enumerateModules();
            parse(lists)
            console.log('rbp '+this.context.rbp);
        },
        onLeave: function(retval){
//            console.log("out" + retval.toInt32());
        }
    });
}

//setImmediate(hook)
hook()