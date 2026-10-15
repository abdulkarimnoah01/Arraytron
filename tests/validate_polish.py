"""v1.0.0 production features in real Houdini: hython tests/validate_polish.py
Manual instance overrides (Delete / Move / Rotate / Scale / Prototype keyed on stable ids), the refined Paint workflow (Replace and Relax), the debug views
(guide-purpose prims), the USD export, and an audit that every Distribution Mode gives stable, deterministic ids. Expected values come from independent
re-implementations (rotation matrices, brute-force distances). Env ARRAYTRON_MUTATE=<name> breaks the module; the suite must FAIL."""
from pathlib import Path
import hou, json, math, os, sys, tempfile, time, types
import numpy as np
from pxr import Usd, UsdGeom, Gf, Sdf
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v1.0.0':'v0.9.0','v1.1.0':'v1.0.0','v1.5.0':'v1.1.0','v1.6.0':'v1.5.0','v1.6.1':'v1.6.0'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_polish_'));checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')
def write_scene():
    path=WORK/'polish.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    for name in ('Ball','BallB'):UsdGeom.Xform.Define(s,'/World/Props/'+name);UsdGeom.Cube.Define(s,'/World/Props/%s/C'%name).CreateSizeAttr(0.2)
    m=UsdGeom.Mesh.Define(s,'/World/Ground');m.CreatePointsAttr([(-5,0,5),(5,0,5),(5,0,-5),(-5,0,-5)]);m.CreateFaceVertexCountsAttr([4]);m.CreateFaceVertexIndicesAttr([0,1,2,3]);m.CreateOrientationAttr('rightHanded')
    ht=UsdGeom.Mesh.Define(s,'/World/Hill');ht.CreatePointsAttr([(-3,0,3),(3,0,3),(3,1.5,-3),(-3,1.5,-3)]);ht.CreateFaceVertexCountsAttr([4]);ht.CreateFaceVertexIndicesAttr([0,1,2,3]);ht.CreateOrientationAttr('rightHanded')
    s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True)
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
def painted(stage,source,P,name='Fin',typ=None,**values):
    P=np.asarray(P,dtype=float).reshape(-1,3);a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Ball')
    a.parm('mode').set(6);a.parm('paint_prim').set('');a.parm('paint_align').set(0.0);m=a.hdaModule();table=np.column_stack([P,np.tile([0.0,1.0,0.0],(len(P),1)),np.arange(len(P))]);a.parm('paint_data').set(m.paint_encode({'pts':table,'dab':1,'next':len(P)}))
    for k,v in values.items():a.parmTuple(k).set(v if isinstance(v,(tuple,list)) else (v,))
    if typ is None and MUTATE:mutate(a)
    return a
def out(a,time_=None):
    s=a.stage();assert not a.errors(),a.errors();prim=s.GetPrimAtPath(a.evalParm('outputpath'));pi=UsdGeom.PointInstancer(prim);t=hou.frame() if time_ is None else time_
    q=pi.GetOrientationsAttr().Get(t) or []
    return dict(pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3),ids=np.array(pi.GetIdsAttr().Get(t) or [],dtype=int),proto=np.array(pi.GetProtoIndicesAttr().Get(t) or [],dtype=int),scales=np.array(pi.GetScalesAttr().Get(t) or []).reshape(-1,3),
                quat=np.array([[x.GetImaginary()[0],x.GetImaginary()[1],x.GetImaginary()[2],x.GetReal()] for x in q]).reshape(-1,4),hidden=sorted(int(i) for i in (pi.GetInvisibleIdsAttr().Get(t) or [])),prim=prim,stage=s)
def by_id(d):
    o=np.argsort(d['ids']);return {k:(v[o] if isinstance(v,np.ndarray) and len(v)==len(o) else v) for k,v in d.items()}
def all_errors(node):
    o=list(node.errors())
    for c in node.children():o+=all_errors(c)
    return o
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()
def mutate(a):
    g=a.hdaModule().paint_decode.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='ovr_euler':
        good=g['euler_to_quat'];g['euler_to_quat']=lambda d:good((d[2],d[1],d[0]))
    elif MUTATE=='ovr_qorder':
        good=g['qmul'];g['qmul']=lambda a_,b_:good(b_,a_)
    elif MUTATE=='ovr_delete':
        good=g['apply_overrides'];g['apply_overrides']=lambda *a_,**k:(lambda r:(r[0],r[1],r[2],r[3],np.zeros_like(r[4]),r[5]))(good(*a_,**k))
    elif MUTATE=='ovr_scale':
        good=g['apply_overrides'];g['apply_overrides']=lambda ids,P,orient,scale,proto,rows,po:good(ids,P,orient,scale,proto,[dict(r,scale=1.0) for r in rows],po)
    elif MUTATE=='ovr_proto':
        good=g['apply_overrides'];g['apply_overrides']=lambda ids,P,orient,scale,proto,rows,po:good(ids,P,orient,scale,proto,rows,{k:v+1 for k,v in po.items()})
    elif MUTATE=='relax_push':
        good=g['brush_relax'];g['brush_relax']=lambda data,center,radius,falloff,strength,spacing,project,iterations=6:good(data,center,radius,falloff,-strength,spacing,project,iterations)
    elif MUTATE=='replace_keep':
        g['brush_replace']=lambda data,center,normal,radius,density,spacing,falloff,strength,seed,project:(lambda r:(r[0],r[1],0))(g['brush_add'](data,center,normal,radius,density,spacing,falloff,strength,seed,project)+(0,))
    elif MUTATE=='export_ids':
        good=g['export_instances'];g['export_instances']=lambda asset,path=None:(lambda r:(_drop_ids(r[0]),r[1]))(good(asset,path))
    else:raise SystemExit('unknown mutation '+MUTATE)
def _drop_ids(path):
    s=Usd.Stage.Open(path);pi=UsdGeom.PointInstancer(s.GetPrimAtPath(next(p.GetPath() for p in s.Traverse() if p.IsA(UsdGeom.PointInstancer))));pi.GetIdsAttr().Clear();s.GetRootLayer().Save();return path
def rot_matrix(deg):
    rx,ry,rz=(math.radians(v) for v in deg)
    Rx=np.array([[1,0,0],[0,math.cos(rx),-math.sin(rx)],[0,math.sin(rx),math.cos(rx)]]);Ry=np.array([[math.cos(ry),0,math.sin(ry)],[0,1,0],[-math.sin(ry),0,math.cos(ry)]]);Rz=np.array([[math.cos(rz),-math.sin(rz),0],[math.sin(rz),math.cos(rz),0],[0,0,1]])
    return Rz@Ry@Rx
def quat_matrix(q):
    x,y,z,w=q;return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])

# ------------------------------------------------------------------ groups
def ui_contract():
    st,sc=new_scene('ui');a=painted(st,sc,[[0,0,0]]);g=a.parmTemplateGroup()
    assert [t.label() for t in g.entries()]==['Source','Layout','Look','Spacing','Settle','Animate','Optimize','Finish']
    ov=g.find('overrides');assert ov.folderType()==hou.folderType.MultiparmBlock and ov.defaultValue()==0
    for name in ('ovr_id#','ovr_delete#','ovr_move#','ovr_rot#','ovr_scale#','ovr_proto#','ovr_info','ovr_clear','dbg_on','dbg_generated','dbg_rejected','dbg_color','dbg_axes','dbg_radius','dbg_centres','dbg_size','export_path','export_usd','cache_info'):assert g.find(name) is not None,name
    assert g.find('dbg_on').defaultValue() is False and g.find('dbg_color').menuLabels()==('Off','Prototype','Id','Weight') and '{ ovr_delete# == 1 }' in g.find('ovr_move#').conditionals()[hou.parmCondType.HideWhen]
    assert g.find('paint_op').menuLabels()==('Add','Remove','Replace','Relax')
    heads=[t.columnLabels()[0] for t in g.entries()[7].parmTemplates() if t.name().startswith('ui_head')];assert heads==['INSTANCE OVERRIDES','DEBUG','EXPORT AND CACHE']
    order=[];n=a.node('USD_COMPILER/OUT_POINTS')
    while n is not None:order.append(n.name());n=n.inputs()[0] if n.inputs() else None
    order=[x for x in order if x!='PROTO_PATH']
    assert order[:4]==['OUT_POINTS','PRIMVARS','GROW','OVERRIDES'] and order[4]=='PHYSICS_SWITCH',order
    assert a.node('OUT_ARRAYTRON').inputs()[0].name()=='debug_guide' and a.node('debug_guide').inputs()[0].name()=='camera_optimize'
    old=hou.hda.definitionsInFile(str(versions.hda(PREVIOUS)))[0].parmTemplateGroup()
    def flat(group):
        res={}
        def walk(ts):
            for t in ts:
                if t.type()==hou.parmTemplateType.Folder and t.folderType()!=hou.folderType.MultiparmBlock:walk(t.parmTemplates())
                else:res[t.name()]=t
        walk(group.entries());return res
    fo,fn=flat(old),flat(g)
    for name,t in fo.items():
        if name.startswith(('ui_','tab_')):continue
        n=fn[name];assert n.type()==t.type() and n.numComponents()==t.numComponents(),name
        if hasattr(t,'defaultValue'):assert n.defaultValue()==t.defaultValue(),name
        if t.type()==hou.parmTemplateType.Menu:assert n.menuItems()[:len(t.menuItems())]==t.menuItems() and n.menuLabels()[:len(t.menuLabels())]==t.menuLabels(),name
def defaults_unchanged():
    st,sc=new_scene('defaults');P=np.random.default_rng(1).uniform(-3,3,(50,3))
    for values in (dict(),dict(overlap_mode=1,overlap_size=1,overlap_radius=0.3),dict(scale_random_mode=1,scale_min=0.5,scale_max=2.0)):
        a=painted(st,sc,P,'n%d'%len(values),**values);b=painted(st,sc,P,'o%d'%len(values),typ=OLD_TYPE,**values);x,y=out(a),out(b)
        assert len(x['pos'])==len(y['pos'])>0 and np.array_equal(x['ids'],y['ids']) and np.allclose(x['pos'],y['pos'],atol=1e-6) and np.array_equal(x['proto'],y['proto']) and np.allclose(x['scales'],y['scales']) and np.allclose(x['quat'],y['quat'],atol=2e-3)
        assert not x['prim'].GetChild('Debug').IsValid()
def override_maths():
    st,sc=new_scene('om');a=painted(st,sc,[[0,0,0]]);m=a.hdaModule();rng=np.random.default_rng(3)
    for deg in ((30,0,0),(0,45,0),(0,0,60),(20,-35,70),(0,0,0)):
        q=m.euler_to_quat(deg);assert abs(np.linalg.norm(q)-1)<1e-12 and np.allclose(quat_matrix(q),rot_matrix(deg),atol=1e-12),deg                     # fixed axes: R = Rz Ry Rx
    qa=m.euler_to_quat((10,20,30));qb=m.euler_to_quat((-40,5,15));assert np.allclose(quat_matrix(m.qmul(qa,qb)),quat_matrix(qa)@quat_matrix(qb),atol=1e-12)           # Hamilton product = the matrix product (b first, then a)
    ids=np.array([5,9,2,7]);P=rng.normal(size=(4,3));Q=np.tile([0,0,0,1.0],(4,1));S=np.ones((4,3));pr=np.array([0,1,0,1])
    rows=[dict(id=9,delete=True),dict(id=5,move=(1,2,3),rot=(0,90,0),scale=2.0,proto=2),dict(id=77,move=(1,0,0)),dict(id=2,proto=9),dict(id=7,scale=0.5)]
    P2,Q2,S2,pr2,dele,st_=m.apply_overrides(ids,P,Q,S,pr,rows,{1:0,2:1})
    assert list(dele)==[False,True,False,False] and np.allclose(P2[0],P[0]+[1,2,3]) and np.allclose(P2[1:],P[1:]) and np.allclose(S2[0],2) and np.allclose(S2[3],0.5) and pr2[0]==1 and pr2[2]==0 and np.allclose(quat_matrix(Q2[0]),rot_matrix((0,90,0)),atol=1e-12)
    assert st_==dict(rows=5,missing=1,deleted=1,moved=1,rotated=1,scaled=2,reproto=1,badproto=1),st_
    both=[dict(id=5,delete=True),dict(id=5,move=(9,9,9))];P3,_,_,_,d3,s3=m.apply_overrides(ids,P,Q,S,pr,both,{1:0});assert d3[0] and s3['deleted']==1                    # a deleted instance stays deleted
def overrides_node():
    st,sc=new_scene('on');P=np.random.default_rng(2).uniform(-3,3,(30,3));a=painted(st,sc,P,scale_random_mode=1,scale_min=0.5,scale_max=1.5)
    a.parm('protos').set(2);a.parm('proto_prim2').set('/World/Props/BallB');base=by_id(out(a));assert 'No overrides' in a.parm('ovr_info').eval()
    a.parm('overrides').set(5)
    a.parm('ovr_id1').set(3);a.parm('ovr_delete1').set(1)
    a.parm('ovr_id2').set(7);a.parmTuple('ovr_move2').set((1.0,0.5,-2.0))
    a.parm('ovr_id3').set(11);a.parmTuple('ovr_rot3').set((0.0,90.0,0.0));a.parm('ovr_scale3').set(3.0)
    a.parm('ovr_id4').set(13);a.parm('ovr_proto4').set(2 if base['proto'][list(base['ids']).index(13)]==0 else 1)
    a.parm('ovr_id5').set(999)
    d=by_id(out(a));assert len(d['ids'])==29 and 3 not in d['ids']
    keep=np.array([i for i in base['ids'] if i!=3]);b=by_id(dict(base));
    idx=lambda arr,i:list(arr['ids']).index(i)
    assert np.allclose(d['pos'][idx(d,7)],base['pos'][idx(base,7)]+[1.0,0.5,-2.0],atol=1e-5)
    for i in keep:                                                                                                                        # everything else untouched
        if i in (7,11,13):continue
        assert np.allclose(d['pos'][idx(d,i)],base['pos'][idx(base,i)],atol=1e-6) and np.allclose(d['scales'][idx(d,i)],base['scales'][idx(base,i)]) and d['proto'][idx(d,i)]==base['proto'][idx(base,i)]
    q0=quat_matrix(base['quat'][idx(base,11)]);q1=quat_matrix(d['quat'][idx(d,11)]);assert np.allclose(q1,q0@rot_matrix((0,90,0)),atol=3e-3) and np.allclose(d['scales'][idx(d,11)],3*base['scales'][idx(base,11)],atol=1e-5)     # local rotation, scale multiplier
    assert d['proto'][idx(d,13)]!=base['proto'][idx(base,13)]
    info=a.parm('ovr_info').eval();assert '5 row(s): 1 deleted, 1 moved, 1 rotated, 1 scaled, 1 re-assigned' in info and '1 row(s) name an id that does not exist' in info,info
    # stable ids: other settings do not change which instance a row edits
    a.parm('proto_seed').set(9);a.parm('proto_weight1').set(3.0);a.parm('base_scale').set(1.5)
    d2=by_id(out(a));assert np.array_equal(d2['ids'],d['ids']) and np.allclose(d2['pos'][idx(d2,7)],base['pos'][idx(base,7)]+[1.0,0.5,-2.0],atol=1e-5) and 3 not in d2['ids']
    a.parm('ovr_proto4').set(7);assert '1 row(s) name a Prototype Bank row that is not enabled' in a.parm('ovr_info').eval() and len(out(a)['ids'])==29
    a.parm('overrides').set(0);assert len(out(a)['ids'])==30 and np.allclose(by_id(out(a))['pos'],base['pos'],atol=1e-6)            # removing the rows brings the generated instances back
def override_api():
    st,sc=new_scene('api');P=np.random.default_rng(5).uniform(-3,3,(20,3));a=painted(st,sc,P);m=a.hdaModule();base=by_id(out(a))
    assert m.override_set(a,4,move=(0.0,1.0,0.0))==1 and m.override_set(a,6,delete=True)==2 and m.override_set(a,4,scale=2.0)==1 and a.evalParm('overrides')==2 and a.evalParm('ovr_scale1')==2.0
    d=by_id(out(a));assert len(d['ids'])==19 and np.allclose(d['pos'][list(d['ids']).index(4)],base['pos'][4]+[0,1,0],atol=1e-5)
    m.override_delete_ids(a,[8,9,10]);assert len(out(a)['ids'])==16 and a.evalParm('overrides')==5
    hou.undos.performUndo();assert a.evalParm('overrides')==2 if hou.undos.areEnabled() else True
    m.override_clear(a);assert a.evalParm('overrides')==0 and len(out(a)['ids'])==20
def paint_refine():
    st,sc=new_scene('pr');a=painted(st,sc,[[0,0,0]],paint_prim='/World/Ground');m=a.hdaModule();surface=m.paint_surface(a);n=np.array([0.0,1.0,0.0]);c=np.zeros(3)
    d,_=m.brush_add(m.paint_empty(),c,n,1.0,200.0,0.0,3,1.0,1,m.make_projector(surface,c,1.0,True));base=d['pts'].copy();assert len(base)>400
    # Replace: the old points under the brush are gone and new ones (new ids) take their place; points outside are untouched
    r,added,removed=m.brush_replace(d,c,n,0.5,100.0,0.05,3,1.0,2,m.make_projector(surface,c,0.5,True));inside=np.linalg.norm(base[:,:3],axis=1)<=0.5
    assert removed==inside.sum() and added>0 and np.array_equal(r['pts'][:len(base)-removed],base[~inside]) and np.all(r['pts'][len(base)-removed:,6]>=len(base)) and np.all(np.linalg.norm(r['pts'][len(base)-removed:,:3],axis=1)<=0.5+1e-6) and r['dab']==d['dab']+1
    # Relax: points under the brush spread out, the others (and every id) stay
    tight=m.paint_empty()
    tight,_=m.brush_add(tight,c,n,0.6,300.0,0.0,3,1.0,4,m.make_projector(surface,c,0.6,True));pts=tight['pts'].copy();target=0.04
    def nn(p):
        D=np.linalg.norm(p[:,None,:3]-p[None,:,:3],axis=2);np.fill_diagonal(D,np.inf);return D.min(axis=1)
    rel,moved=m.brush_relax(tight,c,0.6,3,1.0,target,m.make_projector(surface,c,0.9,True),20)
    assert moved>20 and np.array_equal(rel['pts'][:,6],pts[:,6]) and np.allclose(rel['pts'][:,1],0.0,atol=1e-6) and np.allclose(rel['pts'][:,3:6],[0,1,0]) and rel['dab']==tight['dab']+1                    # ids kept, still on the ground
    assert nn(rel['pts']).mean()>nn(pts).mean()+0.01 and (nn(rel['pts'])<target-1e-9).sum()<(nn(pts)<target-1e-9).sum()*0.7                                                       # more even: fewer pairs closer than the target
    far,m2=m.brush_relax(tight,np.array([4.0,0,4.0]),0.5,3,1.0,target,m.make_projector(surface,np.array([4.0,0,4.0]),0.8,True));assert m2==0 and np.array_equal(far['pts'],pts)
    half,m3=m.brush_relax(tight,c,0.6,3,0.0,target,m.make_projector(surface,c,0.9,True));assert m3==0 and np.array_equal(half['pts'],pts)                                          # strength 0: nothing moves
    again,_=m.brush_relax(tight,c,0.6,3,1.0,target,m.make_projector(surface,c,0.9,True),20);assert np.array_equal(again['pts'],rel['pts'])                                              # deterministic
    # the viewer state: Operation picks the tool, Ctrl inverts it
    ns=types.SimpleNamespace(**{k:getattr(hou,k) for k in ('Vector4','Vector3','Geometry','drawableGeometryType','uiEventReason','promptMessageType','Error','lopNodeTypeCategory','ViewerStateTemplate')});ns.GeometryDrawable=Stub
    glob={'hou':ns,'np':np};exec(compile((ROOT/'src/arraytron_paint_state.py').read_text().replace('import hou'+chr(10),'',1),'s','exec'),glob);glob['STRICT']=True;R=hou.uiEventReason
    a.parm('paint_prim').set('');a.parm('paint_radius').set(0.5);a.parm('paint_density').set(150.0);a.parm('paint_spacing').set(0.0);a.parm('paint_falloff').set(3)
    for op,ctrl,expect in ((2,False,'replace'),(3,False,'relax'),(2,True,'remove'),(1,True,'add'),(0,True,'remove'),(0,False,'add')):
        a.parm('paint_op').set(op);a.parm('paint_data').set('');state=glob['PaintState']('x',Viewer());a.parm('mode').set(6);state.onEnter({'node':a})
        state.onMouseEvent({'ui_event':Event(Device(30,20,left=True,ctrl=ctrl),R.Start)});assert state.kind==expect,(op,ctrl,state.kind,expect)
        state.onMouseEvent({'ui_event':Event(Device(30,20,left=True,ctrl=ctrl),R.Changed)})
    a.parm('paint_op').set(2);state=glob['PaintState']('x',Viewer());a.parm('paint_data').set(m.paint_encode(d));a.parm('mode').set(6);state.onEnter({'node':a});first_new=m.paint_decode(a.evalParm('paint_data'))['next']
    state.onMouseEvent({'ui_event':Event(Device(0,0,left=True),R.Start)});state.onMouseEvent({'ui_event':Event(Device(0,0,left=True),R.Changed)});after=m.paint_decode(a.evalParm('paint_data'))
    assert after['next']>first_new and np.all(np.linalg.norm(after['pts'][after['pts'][:,6]>=first_new][:,[0,2]],axis=1)<=0.5+1e-6) and len(after['pts'][after['pts'][:,6]>=first_new])>0       # the viewer state ran Replace: new ids inside the brush
class Stub(object):
    def __init__(self,*a,**k):self.geo=None
    def setParams(self,p):pass
    def setGeometry(self,g):self.geo=g
    def show(self,v):self.shown=v
    def draw(self,h,params=None):pass
class Viewer(object):
    def setPromptMessage(self,m,t=None):pass
    def clearPromptMessage(self):pass
class Device(object):
    def __init__(self,x,y,left=False,ctrl=False,key='',shift=False,wheel=0):self.x,self.y,self.left,self.ctrl,self.key,self.shift,self.wheel=x,y,left,ctrl,key,shift,wheel
    def isShiftKey(self):return self.shift
    def mouseWheel(self):return self.wheel
    def mouseX(self):return self.x
    def mouseY(self):return self.y
    def isLeftButton(self):return self.left
    def isCtrlKey(self):return self.ctrl
    def isMiddleButton(self):return False
    def isAltKey(self):return False
    def keyString(self):return self.key
class Event(object):
    def __init__(self,device,reason):self.d,self.r=device,reason
    def device(self):return self.d
    def reason(self):return self.r
    def ray(self):x,y=self.d.mouseX(),self.d.mouseY();return hou.Vector3((x/10.0,10.0,y/10.0)),hou.Vector3((0,-1,0))
    def curViewport(self):
        class VP(object):
            def mapToWorld(s,x,y):return hou.Vector3((x/10.0,10.0,y/10.0)),hou.Vector3((0,-1,0))
        return VP()
def debug_views():
    st,sc=new_scene('dbg');P=np.column_stack([np.linspace(-3,3,40),np.zeros(40),np.linspace(-2,2,40)]);a=painted(st,sc,P,mask_source=1,mask_noise_freq=1.0,mask_effect=0,mask_low=0.45,mask_high=0.55,overlap_size=1,overlap_radius=0.25)
    a.parm('protos').set(2);a.parm('proto_prim2').set('/World/Props/BallB')
    off=out(a);assert not off['prim'].GetChild('Debug').IsValid() and 5<len(off['ids'])<40
    a.parm('dbg_on').set(1);d=out(a);dbg=d['stage'].GetPrimAtPath(a.evalParm('outputpath')+'/Debug');assert dbg.IsValid() and UsdGeom.Imageable(dbg).GetPurposeAttr().Get()=='guide'
    for k in ('Generated','Rejected','Final','Axes','Radius','ClusterCentres'):assert not dbg.GetChild(k).IsValid() or UsdGeom.Imageable(dbg.GetChild(k)).GetPurposeAttr().Get()=='guide'
    gen=UsdGeom.Points(dbg.GetChild('Generated'));rej=UsdGeom.Points(dbg.GetChild('Rejected'));assert len(gen.GetPointsAttr().Get())==40 and len(rej.GetPointsAttr().Get())==40-len(d['ids']) and len(rej.GetPointsAttr().Get())>0
    kept=set(d['ids'].tolist());rp=np.array(rej.GetPointsAttr().Get());ref=np.array([P[i] for i in range(40) if i not in kept]);assert np.allclose(rp,ref,atol=1e-5)                                     # exactly the generated points that did not survive
    assert not dbg.GetChild('Final').IsValid() and not dbg.GetChild('Axes').IsValid()
    assert np.array_equal(d['ids'],off['ids']) and np.allclose(d['pos'],off['pos']) and d['hidden']==off['hidden']                                                             # debugging never changes the instances
    a.parm('dbg_color').set(1);a.parm('dbg_axes').set(1);a.parm('dbg_radius').set(1);a.parm('dbg_generated').set(0);a.parm('dbg_rejected').set(0);a.parm('dbg_size').set(0.1);d=out(a);dbg=d['stage'].GetPrimAtPath(a.evalParm('outputpath')+'/Debug')
    assert not dbg.GetChild('Generated').IsValid() and not dbg.GetChild('Rejected').IsValid();fin=UsdGeom.Points(dbg.GetChild('Final'));n=len(d['ids']);fp=np.array(fin.GetPointsAttr().Get());assert len(fp)==n and np.allclose(np.sort(fp[:,0]),np.sort(d['pos'][:,0]),atol=1e-5)
    cols=np.array(fin.GetDisplayColorPrimvar().Get());pr=np.array(a.node('USD_COMPILER/OUT_POINTS').geometry().pointIntAttribValues('protoindex'));assert len(set(pr.tolist()))==2 and np.allclose(cols,np.array([[0.2,0.6,1.0],[1.0,0.6,0.1],[0.3,0.9,0.3],[0.9,0.3,0.8],[0.9,0.9,0.2],[0.3,0.9,0.9]])[pr%6],atol=1e-5)
    assert abs(fin.GetWidthsAttr().Get()[0]-0.1)<1e-6
    axes=UsdGeom.BasisCurves(dbg.GetChild('Axes'));pts=np.array(axes.GetPointsAttr().Get());assert len(axes.GetCurveVertexCountsAttr().Get())==2*n and len(pts)==4*n
    for k in range(n):                                                                                                                                                           # up = +Y, forward = +Z for upright instances, length 4 x size
        assert np.allclose(pts[4*k+1]-pts[4*k],[0,0.4,0],atol=1e-4) and np.allclose(pts[4*k+3]-pts[4*k+2],[0,0,0.4],atol=1e-4)
    rad=UsdGeom.BasisCurves(dbg.GetChild('Radius'));rp=np.array(rad.GetPointsAttr().Get()).reshape(n,25,3);assert np.allclose(np.linalg.norm(rp[:,:,[0,2]]-rp[:,:1,[0,2]]*0-d['pos'][:,None,[0,2]],axis=2),0.25*d['scales'].max(axis=1)[:,None],atol=2e-3)                    # rings of the Separation sphere
    a.parm('dbg_color').set(3);d=out(a);dbg=d['stage'].GetPrimAtPath(a.evalParm('outputpath')+'/Debug');w=np.array(UsdGeom.Points(dbg.GetChild('Final')).GetDisplayColorPrimvar().Get());assert np.allclose(w[:,0]+w[:,1],1.0,atol=1e-4)
    a.parm('dbg_color').set(2);d=out(a);c2=np.array(UsdGeom.Points(d['stage'].GetPrimAtPath(a.evalParm('outputpath')+'/Debug').GetChild('Final')).GetDisplayColorPrimvar().Get());assert len({tuple(np.round(r,4)) for r in c2})==n
    b=st.createNode(TYPE,'CL');b.setInput(0,sc);b.parm('protos').set(1);b.parm('proto_prim1').set('/World/Props/Ball');b.parm('mode').set(7);b.parm('cluster_prim').set('');b.parm('cluster_count').set(5);b.parm('dbg_on').set(1);b.parm('dbg_centres').set(1)
    if MUTATE:mutate(b)
    ds=b.stage();cc=UsdGeom.Points(ds.GetPrimAtPath(b.evalParm('outputpath')+'/Debug/ClusterCentres'));assert len(cc.GetPointsAttr().Get())==5
def export_usd():
    st,sc=new_scene('exp');P=np.random.default_rng(7).uniform(-3,3,(40,3));a=painted(st,sc,P,scale_random_mode=1,scale_min=0.5,scale_max=2.0,pv_id=1,pv_random=1,dbg_on=1,cam_on=0)
    a.parm('protos').set(2);a.parm('proto_prim2').set('/World/Props/BallB');a.parm('export_path').set((WORK/'exports'/'inst.usd').as_posix());m=a.hdaModule()
    path,count=m.export_instances(a);assert count==40 and os.path.isfile(path);live=by_id(out(a));s=Usd.Stage.Open(path)
    pr=s.GetPrimAtPath(a.evalParm('outputpath'));pi=UsdGeom.PointInstancer(pr);assert pr.IsValid() and pi
    ids=np.array(pi.GetIdsAttr().Get());o=np.argsort(ids);pos=np.array(pi.GetPositionsAttr().Get())[o];sc_=np.array(pi.GetScalesAttr().Get())[o];proto=np.array(pi.GetProtoIndicesAttr().Get())[o]
    assert np.array_equal(ids[o],live['ids']) and np.allclose(pos,live['pos'],atol=1e-6) and np.allclose(sc_,live['scales'],atol=1e-6) and np.array_equal(proto,live['proto'])
    q=np.array([[x.GetImaginary()[0],x.GetImaginary()[1],x.GetImaginary()[2],x.GetReal()] for x in pi.GetOrientationsAttr().Get()])[o];assert np.allclose(q,live['quat'],atol=2e-3)
    assert not pr.GetChild('Debug').IsValid() and UsdGeom.GetStageUpAxis(s)=='Y' and s.GetDefaultPrim().GetName()=='World' and s.GetRootLayer().customLayerData.get('arraytron:exported') is True
    pv=UsdGeom.PrimvarsAPI(pr);assert list(np.array(pv.GetPrimvar('arraytron_id').Get())[o])==list(live['ids']) and pv.GetPrimvar('random').IsDefined()
    targets=pi.GetPrototypesRel().GetTargets();assert len(targets)==2 and all(s.GetPrimAtPath(t).IsValid() for t in targets) and not any(p.GetPath().pathString.startswith('/World/Props') for p in s.Traverse())        # self contained: the prototypes travel with it
    assert 'arraytron' in s.GetRootLayer().comment.lower()
    path2,count2=m.export_instances(a);assert count2==40 and path2==path                                                                                                   # overwriting works
    a.parm('export_path').set('')
    try:m.export_instances(a);raise AssertionError('empty path accepted')
    except hou.NodeError as exc:assert 'Export File is empty' in str(exc)
    assert 'Export File' in a.parm('cache_info').eval() and 'Painted points stored in the node: 40' in a.parm('cache_info').eval()
def stable_ids():
    st,sc=new_scene('ids');modes={0:dict(line_count=30),1:dict(area_count=60,area_seed=3),2:dict(),3:dict(),4:None,5:dict(surface_prim='/World/Hill',surface_count=80,surface_seed=2),7:dict(cluster_prim='/World/Ground',cluster_count=4,cluster_per=15)}
    for mode,values in modes.items():
        if values is None:continue
        def build(name):
            a=st.createNode(TYPE,name);a.setInput(0,sc);a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Ball');a.parm('mode').set(mode)
            for k,v in values.items():a.parmTuple(k).set(v if isinstance(v,(tuple,list)) else (v,))
            return a
        a=build('A%d'%mode);b=build('B%d'%mode);x,y=by_id(out(a)),by_id(out(b));assert len(set(x['ids'].tolist()))==len(x['ids'])>0 and np.array_equal(x['ids'],y['ids']) and np.allclose(x['pos'],y['pos'],atol=1e-6),mode      # unique and deterministic
        a.parm('scale_random_mode').set(1);a.parm('scale_min').set(0.5);a.parm('scale_max').set(2.0);a.parm('rotation_random_mode').set(1);a.parm('yaw_random').set(180);a.parm('proto_seed').set(5);a.parm('base_scale').set(1.7)   # none of this may move or rename a point
        a.parm('protos').set(2);a.parm('proto_prim2').set('/World/Props/BallB');a.parm('proto_weight2').set(4.0);a.parm('mask_source').set(1);a.parm('mask_effect').set(1)
        z=by_id(out(a));assert np.array_equal(z['ids'],x['ids']) and np.allclose(z['pos'],x['pos'],atol=1e-5),mode
        a.parm('mask_effect').set(0);a.parm('mask_noise_freq').set(2.0);zz=out(a);assert set(zz['ids'].tolist())<=set(x['ids'].tolist()),mode                                    # a density mask only ever removes ids
        a.parm('protos').set(1);a.parm('mask_source').set(0)
def main():
    for name,func in (('UI contract: Finish tab, overrides, debug and export parameters, stage order, every v0.9.0 parameter unchanged',ui_contract),
                      ('Everything off reproduces v0.9.0 (and no Debug prim)',defaults_unchanged),
                      ('Override maths: rotation order, quaternion product, statistics against matrices',override_maths),
                      ('Overrides on the node: delete, move, rotate, scale, prototype; ids stay stable; missing rows counted; removable',overrides_node),
                      ('Override functions: create / update rows, delete many, clear',override_api),
                      ('Paint refinement: Replace, Relax (ids, surface, evenness, determinism) and the Operation menu in the viewer state',paint_refine),
                      ('Debug views: guide purpose, generated, rejected, colours, axes, radius, cluster centres; never change the instances',debug_views),
                      ('USD export: arrays, ids, prototypes, primvars, no debug guides, self contained, overwrite, error',export_usd),
                      ('Stable ids in every Distribution Mode: unique, deterministic, untouched by variation, selection, scale and mask changes',stable_ids)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_polish_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
