import hou,sys
from pxr import Usd,UsdGeom
print(hou.applicationVersionString())
st=hou.node('/stage')
c=st.createNode('reference','c');c.parm('primpath').set('/World/Props/Crate');c.parm('primpath1').set('/World/Props/Crate');c.parm('filepath1').set('X:/Assets/HDAs/Arraytron/dist/test_assets/crate.usda');c.parm('filerefprim1').set('defaultPrim')
b=st.createNode('reference','b');b.setInput(0,c);b.parm('primpath').set('/World/Props/Barrel');b.parm('primpath1').set('/World/Props/Barrel');b.parm('filepath1').set('X:/Assets/HDAs/Arraytron/dist/test_assets/barrel.usda');b.parm('filerefprim1').set('defaultPrim')
n=st.createNode('instancer','inst');n.setInput(0,b)
n.parm('primpath').set('/World/Arraytron');n.parm('method').set('pointinstancer');n.parm('transformsourcemode').set('intsop')
n.parm('protosourcemode').set('first');n.parm('protopattern').set('/World/Props/Crate /World/Props/Barrel');n.parm('protoreftype').set('prim')
n.parm('protoindexsrc').set('indexattr');n.parm('indexattr').set('protoindex');n.parm('attribs').set('myid')
print('children after setup',[x.name() for x in n.children()])
try:
    sop=n.node('sopnet') or None
except Exception:sop=None
# find internal sop network
inner=n.children()
print('inner',[(x.name(),x.type().name()) for x in inner])
try:
    w=n.createNode('attribwrangle','gen');w.parm('class').set(0)
    w.parm('snippet').set('addpoint(0,{0,0,0});') if False else None
    print('created inner',w.path())
    g=n.createNode('python','pts')
    g.parm('python').set("geo=hou.pwd().geometry()\ngeo.addAttrib(hou.attribType.Point,'protoindex',0);geo.addAttrib(hou.attribType.Point,'id',0);geo.addAttrib(hou.attribType.Point,'orient',(0.0,0.0,0.0,1.0));geo.addAttrib(hou.attribType.Point,'scale',(1.0,1.0,1.0));geo.addAttrib(hou.attribType.Point,'myid',7)\nfor k in range(5):\n    p=geo.createPoint();p.setPosition((k,0,0));p.setAttribValue('protoindex',k%2);p.setAttribValue('id',100+k);p.setAttribValue('scale',(1.0,1.0,1.0));p.setAttribValue('myid',k)\n")
    o=n.createNode('output','OUT');o.setInput(0,g);o.setDisplayFlag(True);o.setRenderFlag(True)
    s=n.stage();print('errors',n.errors(),[x.errors() for x in n.children()])
    pi=UsdGeom.PointInstancer(s.GetPrimAtPath('/World/Arraytron'));print('pi valid',bool(pi))
    print([str(p.GetPath()) for p in s.Traverse()][:20])
    if pi:print('pos',len(pi.GetPositionsAttr().Get(1) or []),'ids',pi.GetIdsAttr().Get(1),'proto',pi.GetProtoIndicesAttr().Get(1),'targets',[str(t) for t in pi.GetPrototypesRel().GetTargets()],'orient',len(pi.GetOrientationsAttr().Get(1) or []),'pv',[p.GetName() for p in UsdGeom.PrimvarsAPI(pi.GetPrim()).GetPrimvars()],'invis',pi.GetInvisibleIdsAttr().Get(1))
except Exception as e:
    import traceback;traceback.print_exc()
