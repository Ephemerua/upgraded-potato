// algorithm from https://en.wikibooks.org/wiki/Algorithm_Implementation/Miscellaneous/Base64#Javascript
function base64_encode (s)
{
  var base64chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  var r = ""; 
  var p = ""; 
  var c = s.length % 3;

  if (c > 0) { 
    for (; c < 3; c++) { 
      p += '='; 
      s += "\0"; 
    } 
  }

  for (c = 0; c < s.length; c += 3) {
    if (c > 0 && (c / 3 * 4) % 76 == 0) { 
      r += "\r\n"; 
    }

    var n = (s.charCodeAt(c) << 16) + (s.charCodeAt(c+1) << 8) + s.charCodeAt(c+2);
    n = [(n >>> 18) & 63, (n >>> 12) & 63, (n >>> 6) & 63, n & 63];
    r += base64chars[n[0]] + base64chars[n[1]] + base64chars[n[2]] + base64chars[n[3]];
  }
  return r.substring(0, r.length - p.length) + p;
}

const PROT_READ = 1
const PROT_WRITE = 2
const PROT_EXEC = 4


function get_prot(rwx) {
    var prot = 0;
    if(rwx[0] === 'r')
        prot += 1;
    if(rwx[1] === 'w')
        prot += 2;
    if(rwx[2] === 'x')
        prot += 4;
    return prot;
}

function get_obj(file) {
    var obj = file.substring(file.lastIndexOf('/') + 1);
    return obj;
}

function get_content(addr, size) {
    var base = new NativePointer(addr);
    var content = base.readCString(size);
    var encoded = base64_encode(String(content));
    return encoded;
}

function parse(lists, context) {
    var f = new File('map.' + Process.id, 'wb');
//    console.log(lists.length)
    var memory_dump = {'context': context};
    var json_lists=[]
    for(var i=0;i<lists.length;i++) {
        if(lists[i].hasOwnProperty('file') == false)
            continue
        var map = {}
//        console.log(i+lists[i]['base']);
        map['start'] = parseInt(lists[i]['base'])
        map['end'] = map['start'] + lists[i]['size']
        var prot = map['prot'] = get_prot(lists[i]['protection'])
        map['obj'] = get_obj(lists[i]['file']['path'])
        map['content'] = ''
        if( prot & 2)
            map['content'] = get_content(map['start'], lists[i]['size'])
        json_lists.push(map)
    }
    memory_dump['mem'] = json_lists;
    f.write(JSON.stringify(memory_dump));
    f.flush();
    f.close();
}

function hook() {
    console.log('Dump initiated');
    Interceptor.attach(Module.getExportByName(null, '__libc_start_main'), {
        onEnter: function(args) {
            var lists = Process.enumerateRanges('---');
//            var lists2 = Process.enumerateModules();
            parse(lists, this.context)
            console.log('rbp '+this.context.rbp);
        },
        onLeave: function(retval){
//            console.log("out" + retval.toInt32());
        }
    });
}

//setImmediate(hook)
hook()