import hou
n=hou.node('/stage').createNode('instancer')
print(hou.applicationVersionString(),n.type().name(),[c.name() for c in n.children()],n.type().definition().nodeTypeName() if n.type().definition() else 'builtin')
for p in n.parms():
    t=p.parmTemplate();print(p.name(),'|',t.label(),'|',p.eval() if t.type()!=hou.parmTemplateType.Folder else '')
