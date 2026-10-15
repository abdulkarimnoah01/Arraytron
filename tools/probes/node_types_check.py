import hou,json,sys,os
out=os.path.join(os.path.dirname(os.path.abspath(__file__)),'node_types.json')
if hou.applicationVersion()[0]==22:
    hou.hda.installFile('X:/Assets/HDAs/Arraytron/dist/Arraytron_v1.0.0.hda');a=hou.node('/stage').createNode('arraytron::instancer::1.0.0');a.allowEditingOfContents()
    s=set()
    def walk(n):
        for c in n.children():
            s.add((c.type().category().name(),c.type().name()));walk(c)
    walk(a);json.dump(sorted(s),open(out,'w'));print(len(s),'types');sys.exit(0)
types=json.load(open(out));missing=[]
for cat,name in types:
    c=hou.nodeTypeCategories()[cat]
    if name not in c.nodeTypes():missing.append((cat,name))
print(hou.applicationVersionString(),'missing node types:',missing)
