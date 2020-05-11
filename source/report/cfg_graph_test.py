from graphviz import Source

'''
test
'''
code = """digraph G {
    n1[shape=record,label="{{0x603010 size:0x20}}"]
    n2[shape=record,label="{{0x603010 size:0x20}|{0x603030 size:0x190}}"]
    n3[shape=record,label="{{0x603010 size:0x20}|{0x603030 size:0x190}|{0x6031c0 size:0x20}}"]
    n4[shape=record,label="{{0x603010 size:0x20}|{0x603030 size:0x190}|{0x6031c0 size:0x20}|{0x6031e0 size:0x10}}"]
    n5[shape=record,label="{{0x603010 size:0x20}|{0x603030 size:0x190}|{0x6031c0 size:0x20}}"]
    n6[shape=record,label="{{0x603010 size:0x20}|{0x603030 size:0x190}}"]
    n7[shape=record,label="{{0x603010 size:0x20}}"]
    n8[shape=none, label=<<table border="0" cellborder="1" cellspacing="0" cellpadding="4">
    <tr><td bgcolor="lightgrey"><font color="red">0x603010 size:0x20</font></td></tr>
    <tr><td>0x603030 size:0x20</td></tr>
    </table>>]
    n9[shape=none, label=<<table border="0" cellborder="1" cellspacing="0" cellpadding="4">
    <tr><td bgcolor="lightgrey"><font color="red">0x603010 size:0x20</font></td></tr>
    <tr><td>0x603030 size:0x20</td></tr>
    </table>>]
    n1->n2[label="Malloc called with size 0x190, returns addr 0x603030"]
    {rank = same; n2->n8[style=dotted dir=none]}
    n2->n3[label="Malloc called with size 0x20, returns addr 0x6031c0"]
    {rank = same; n3->n9}
    n3->n4[label="Malloc called with size 0x10, returns addr 0x6031e0"]
    n4->n5[label="Free called to free 0x6031e0 with size 0x20"]
    n5->n6[label="Free called to free 0x6031c0 with size 0x20"]
    n6->n7[label="Free called to free 0x603030 with size 0x190"]
}"""

t = Source(code)
t.view()