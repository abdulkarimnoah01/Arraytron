import hou, json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
stage=hou.node('/stage')
data={'version':hou.applicationVersionString()}
for typ in ('pointinstancer','instancer','sopcreate','camera','karmarendersettings','domelight','usd_rop','subnet'):
    try:
        n=stage.createNode(typ,'inspect_'+typ)
        data[typ]={'type':n.type().name(),'children':[(c.path(),c.type().name()) for c in n.allSubChildren()],
                   'parms':[{ 'name':p.name(),'label':p.description(),'value':p.eval(),
                             'menu':list(p.parmTemplate().menuItems()) if isinstance(p.parmTemplate(),(hou.MenuParmTemplate,hou.StringParmTemplate)) else []}
                            for p in n.parms()]}
    except Exception as e: data[typ]={'error':str(e)}
(root/'tests'/'node_inventory.json').write_text(json.dumps(data,indent=2,default=str))
print('Inventory saved; Houdini '+data['version'])
