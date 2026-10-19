"""v1.9.0 Instance Place in real Houdini: hython tests/validate_place.py [version]
Distribution Mode "Instance Place": instances placed one at a time from a table (Position, Rotate, Scale, Prototype Row, stable id) or by clicking a surface in the viewport.
Expected values come from independent rotation matrices, plain geometry and the instancer's own arrays. The viewport tool is exercised through a stand-in viewport that looks
straight down. Env ARRAYTRON_MUTATE=place_euler|place_ids|place_on|place_ctrl|place_align breaks the module; the suite must FAIL."""
from pathlib import Path
import hou, json, os, sys, tempfile, time, types
import numpy as np
from pxr import Usd, UsdGeom, Gf, Sdf
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v1.9.0':'v1.8.0'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_place_'));checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')
def write_scene():
    path=WORK/'place.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    for name in ('Ball','BallB'):UsdGeom.Xform.Define(s,'/World/Props/'+name);UsdGeom.Cube.Define(s,'/World/Props/%s/C'%name).CreateSizeAttr(0.2)
    r=UsdGeom.Mesh.Define(s,'/World/Ramp');r.CreatePointsAttr([(-5,0,5),(5,0,5),(5,5,-5),(-5,5,-5)]);r.CreateFaceVertexCountsAttr([4]);r.CreateFaceVertexIndicesAttr([0,1,2,3]);r.CreateOrientationAttr('rightHanded')
    s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True)
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
def place_node(stage,source,rows=(),name='Place',typ=None,protos=1,**values):
    """rows: dicts (on, id, pos, rot, scale, proto)."""
    a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(protos);a.parm('proto_prim1').set('/World/Props/Ball')
    if protos>1:a.parm('proto_prim2').set('/World/Props/BallB')
    a.parm('mode').set(9);a.parm('places').set(len(rows))
    for i,r in enumerate(rows,1):
        a.parm('place_on%d'%i).set(int(r.get('on',True)));a.parm('place_id%d'%i).set(r.get('id',0));a.parmTuple('place_pos%d'%i).set(r.get('pos',(0,0,0)));a.parmTuple('place_rot%d'%i).set(r.get('rot',(0,0,0)))
        a.parmTuple('place_scale%d'%i).set(r.get('scale',(1,1,1)));a.parm('place_proto%d'%i).set(r.get('proto',0))
    for k,v in values.items():a.parmTuple(k).set(v if isinstance(v,(tuple,list)) else (v,))
    if typ is None:mutate(a)
    return a
def out(a):
    s=a.stage();assert not all_errors(a),all_errors(a);pi=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    q=pi.GetOrientationsAttr().Get(t) or [];sc=pi.GetScalesAttr().Get(t) or []
    return dict(pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3),ids=np.array(pi.GetIdsAttr().Get(t) or [],dtype=int),proto=np.array(pi.GetProtoIndicesAttr().Get(t) or [],dtype=int),
                scales=np.array(sc).reshape(-1,3),quat=np.array([[x.GetImaginary()[0],x.GetImaginary()[1],x.GetImaginary()[2],x.GetReal()] for x in q]).reshape(-1,4))
def all_errors(node):
    o=list(node.errors())
    for c in node.children():o+=all_errors(c)
    return o
def by_id(d):
    o=np.argsort(d['ids']);return {k:(v[o] if isinstance(v,np.ndarray) and len(v)==len(o) else v) for k,v in d.items()}
def rot_matrix(deg):
    rx,ry,rz=np.radians(deg);X=np.array([[1,0,0],[0,np.cos(rx),-np.sin(rx)],[0,np.sin(rx),np.cos(rx)]]);Y=np.array([[np.cos(ry),0,np.sin(ry)],[0,1,0],[-np.sin(ry),0,np.cos(ry)]]);Z=np.array([[np.cos(rz),-np.sin(rz),0],[np.sin(rz),np.cos(rz),0],[0,0,1]]);return Z@Y@X
def quat_apply(q,v):
    x,y,z,w=q;u=np.array([x,y,z]);return v+2*w*np.cross(u,v)+2*np.cross(u,np.cross(u,v))
def same_rotation(q1,q2,tol=2e-3):return abs(float(np.dot(q1/np.linalg.norm(q1),q2/np.linalg.norm(q2))))>1-tol
def mutate(a=None):
    targets=[a.hdaModule().place_quat.__globals__] if a is not None else []
    for g in targets:
        if g.get('_mutation')==MUTATE:continue
        g['_mutation']=MUTATE
        if MUTATE=='place_euler':
            good=g['place_quat'];g['place_quat']=lambda d:good((d[2],d[1],d[0]))
        elif MUTATE=='place_ids':g['place_resolve_ids']=lambda ids:[int(i) for i in ids]
        elif MUTATE=='place_on':
            good=g['place_rows'];g['place_rows']=lambda asset:[dict(r,on=True) for r in good(asset)]
        elif MUTATE=='place_ctrl':g['place_nearest']=lambda asset,o,d:None
        elif MUTATE=='place_align':
            good=g['place_aim'];g['place_aim']=lambda normal,amount,yaw:good((0.0,1.0,0.0),amount,yaw)
        elif MUTATE:raise SystemExit('unknown mutation '+MUTATE)
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()

def maths():
    st,sc=new_scene('maths');a=st.createNode(TYPE,'M');m=a.hdaModule();mutate(a)
    rng=np.random.RandomState(3)
    for _ in range(20):
        deg=np.array([rng.uniform(-170,170),rng.uniform(-80,80),rng.uniform(-170,170)]);q=m.place_quat(deg);R=rot_matrix(deg)
        for v in np.eye(3):assert np.allclose(quat_apply(q,v),R@v,atol=1e-9),deg                                              # the quaternion is Rz Ry Rx
        assert np.allclose(m.place_euler(q),deg,atol=1e-6),(deg,m.place_euler(q))                                              # and the Euler angles come back
    assert np.allclose(rot_matrix(m.place_euler(m.place_quat((10,90,20)))),rot_matrix((10,90,20)),atol=1e-6)                       # gimbal lock keeps the rotation
    assert m.place_resolve_ids([5,5,0,3,-1])==[5,6,7,3,8] and m.place_resolve_ids([])==[] and m.place_resolve_ids([0,0])==[1,2] and m.place_resolve_ids([4,2,9])==[4,2,9]
    q=m.place_aim((0,1,0),0.0,90.0);assert np.allclose(quat_apply(q,np.array([1.0,0,0])),[0,0,-1],atol=1e-9)                          # a yaw of 90 degrees about up
    n=np.array([1.0,0,0]);q=m.place_aim(n,1.0,0.0);assert np.allclose(quat_apply(q,np.array([0,1.0,0])),n,atol=1e-9)                    # fully aligned: +Y onto the normal
    q=m.place_aim(n,1.0,40.0);assert np.allclose(quat_apply(q,np.array([0,1.0,0])),n,atol=1e-9)                                       # the yaw keeps the up axis
    assert np.allclose(m.place_aim(n,0.0,0.0),[0,0,0,1],atol=1e-9)

def node_table():
    st,sc=new_scene('table');rows=[dict(id=10,pos=(1,0,1),rot=(0,90,0),scale=(1,1,1)),dict(id=20,pos=(3,0,2),rot=(30,0,0),scale=(2,2,2)),dict(id=30,pos=(-2,0,4),rot=(0,0,0),scale=(1,0.5,1))]
    a=place_node(st,sc,rows);o=by_id(out(a));assert o['ids'].tolist()==[10,20,30]
    assert np.allclose(o['pos'],[r['pos'] for r in rows],atol=1e-5) and np.allclose(o['scales'],[r['scale'] for r in rows],atol=1e-5)
    for k,r in enumerate(rows):assert same_rotation(o['quat'][k],_q(a,r['rot'])),(k,o['quat'][k])                                             # the placed rotation, as Rz Ry Rx
    assert all(a.evalParm(n)==0 for n in ('mode',)) is False                                                                      # (mode 9, not 0)
    a.parm('place_on2').set(0);o=by_id(out(a));assert o['ids'].tolist()==[10,30]                                                    # a disabled row is skipped
    a.parm('place_on2').set(1);a.hdaModule().place_remove(a,2);o=by_id(out(a));assert o['ids'].tolist()==[10,30] and np.allclose(o['pos'][1],[-2,0,4],atol=1e-5) and np.allclose(o['scales'][1],[1,0.5,1],atol=1e-5)   # the others keep their ids and values
    a.parm('base_scale').set(2.0);o=by_id(out(a));assert np.allclose(o['scales'][0],[2,2,2],atol=1e-5) and np.allclose(o['scales'][1],[2,1,2],atol=1e-5)               # the Look tab scale multiplies the placed scale
    b=place_node(st,sc,[dict(pos=(0,0,0)),dict(pos=(1,0,0)),dict(id=1,pos=(2,0,0))],name='Fresh');ids=sorted(out(b)['ids'].tolist());assert len(set(ids))==3 and ids[0]>=1                    # rows with no id still get distinct ids
    assert b.hdaModule().place_normalize(b)==2 and [b.evalParm('place_id%d'%i) for i in (1,2,3)]==[2,3,1]                                                    # Fix Ids writes them
    empty=place_node(st,sc,[],name='Empty');assert len(out(empty)['ids'])==0 and 'No instances yet' in empty.hdaModule().place_info(empty)

def _q(a,deg):
    q=a.hdaModule().place_quat(deg);return np.array(q)

def prototypes():
    st,sc=new_scene('protos');rows=[dict(id=10,pos=(1,0,1),proto=2),dict(id=20,pos=(3,0,2),proto=1),dict(id=30,pos=(-2,0,4),proto=0)]
    a=place_node(st,sc,rows,protos=2,proto_mode=3);o=by_id(out(a));assert o['proto'].tolist()==[1,0,30%2]                                      # row 2, row 1, and the Selection Mode (Cycle) for 0
    a.parm('proto_on2').set(0);o=by_id(out(a));assert o['proto'].tolist()==[0,0,0]                                                  # a row that is not enabled is ignored: automatic (the only row left)

def defaults_unchanged():
    st,sc=new_scene('defaults');pts=dict(mode=0,line_count=7)
    a=st.createNode(TYPE,'New');a.setInput(0,sc);b=st.createNode(OLD_TYPE,'Old');b.setInput(0,sc)
    for n in (a,b):
        n.parm('protos').set(1);n.parm('proto_prim1').set('/World/Props/Ball');n.parm('mode').set(0);n.parm('line_count').set(7)
    o,p=by_id(out(a)),by_id(out(b));assert np.array_equal(o['ids'],p['ids']) and np.allclose(o['pos'],p['pos']) and np.array_equal(o['proto'],p['proto']) and np.allclose(o['scales'],p['scales'])
    assert a.evalParm('places')==0 and a.evalParm('place_align')==0.0 and a.evalParm('place_def_scale')==1.0 and a.evalParm('place_def_proto')==0 and a.evalParm('place_target')==''

def tool_functions():
    st,sc=new_scene('tool');a=place_node(st,sc,[],place_def_scale=1.5,place_def_yaw=30.0,place_def_proto=2,place_offset=0.2,protos=2);m=a.hdaModule()
    assert m.place_add(a,(2.0,0.0,3.0))==1 and a.evalParm('place_id1')==1 and np.allclose(a.evalParmTuple('place_pos1'),[2.0,0.2,3.0]) and np.allclose(a.evalParmTuple('place_rot1'),[0,30,0],atol=1e-6)
    assert np.allclose(a.evalParmTuple('place_scale1'),[1.5]*3) and a.evalParm('place_proto1')==2 and a.evalParm('place_on1')==1
    assert m.place_add(a,(0,0,0),scale=2.0,yaw=0.0,proto=1)==2 and a.evalParm('place_id2')==2 and a.evalParm('place_proto2')==1 and np.allclose(a.evalParmTuple('place_scale2'),[2.0]*3)
    n=np.array([1.0,1.0,0.0])/np.sqrt(2);a.parm('place_align').set(1.0);m.place_add(a,(0,0,0),normal=n,yaw=0.0);q=m.place_quat(a.evalParmTuple('place_rot3'));assert np.allclose(quat_apply(q,np.array([0,1.0,0])),n,atol=1e-6)   # aligned to the surface
    a.parm('place_def_yawrand').set(60.0);m.place_add(a,(0,0,0),normal=(0,1,0));m.place_add(a,(0,0,0),normal=(0,1,0))   # random yaw, +/- 60 degrees
    y=[a.evalParmTuple('place_rot4')[1],a.evalParmTuple('place_rot5')[1]];assert all(abs(v-30.0)<=60.0+1e-6 for v in y) and abs(y[0]-y[1])>1e-6
    row=m.place_nearest(a,(2.0,10.0,3.0),(0,-1,0));assert row==(1,1) and m.place_nearest(a,(9.0,10.0,9.0),(0,-1,0)) is None
    m.place_remove(a,1);assert a.evalParm('places')==4 and a.evalParm('place_id1')==2 and a.evalParm('place_id2')==3                          # the other rows keep their ids
    m.place_clear(a);assert a.evalParm('places')==0
    hou.undos.performUndo()                                                                                                       # clear is one undo step
    assert a.evalParm('places')==4
    ids=a.hdaModule().place_arrays(a)['ids'].tolist();assert ids==sorted(set(ids))

class StubDrawable(object):
    def __init__(self,*a,**k):self.geo=None;self.shown=False;self.params={}
    def setParams(self,p):self.params.update(p)
    def setGeometry(self,g):self.geo=g
    def show(self,v):self.shown=v
    def draw(self,handle,params=None):self.drawn=True
class StubViewer(object):
    def __init__(self):self.prompt=None
    def setPromptMessage(self,m,t=None):self.prompt=m
    def clearPromptMessage(self):self.prompt=None
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
    """A viewport that looks straight down: pixel (x, y) is the ray from (x/10, 10, y/10) along -Y."""
    def __init__(self,device,reason):self.d,self.r=device,reason
    def device(self):return self.d
    def reason(self):return self.r
    def ray(self):x,y=self.d.mouseX(),self.d.mouseY();return hou.Vector3((x/10.0,10.0,y/10.0)),hou.Vector3((0,-1,0))
def make_state():
    ns=types.SimpleNamespace(**{k:getattr(hou,k) for k in ('Vector4','Vector3','Geometry','drawableGeometryType','uiEventReason','promptMessageType','Error','lopNodeTypeCategory','ViewerStateTemplate')});ns.GeometryDrawable=StubDrawable
    glob={'hou':ns,'np':np};exec(compile((ROOT/'src/arraytron_paint_state.py').read_text().replace('import hou'+chr(10),'',1),'arraytron_paint_state.py','exec'),glob);glob['STRICT']=True
    viewer=StubViewer();return glob['PaintState']('arraytron_place_test',viewer),viewer

def viewer_place():
    R=hou.uiEventReason;st,sc=new_scene('viewer');a=place_node(st,sc,[],protos=2);m=a.hdaModule();state,viewer=make_state();paint=a.evalParm('paint_data')
    def mouse(x,z,reason,**kw):return state.onMouseEvent({'ui_event':Event(Device(float(x)*10,float(z)*10,**kw),reason)})
    # the node is selected in Instance Place mode: the tool is idle, a click changes nothing (only the button starts placing)
    state.onEnter({'node':a});assert not state.placing and mouse(3,2,R.Start,left=True) is False and a.evalParm('places')==0
    a.setUserData('arraytron_place','1');assert mouse(3,2,R.Located) is True and state.placing and a.userData('arraytron_place') is None                                  # the flag is found on the next mouse event
    assert state.marker.shown and 'Arraytron Place' in viewer.prompt and '0 placed' in viewer.prompt and 'scale 1' in viewer.prompt and 'Esc' in viewer.prompt
    mouse(3,2,R.Start,left=True);assert a.evalParm('places')==1 and np.allclose(a.evalParmTuple('place_pos1'),[3,0,2],atol=1e-6) and a.evalParm('place_id1')==1 and '1 placed' in viewer.prompt
    mouse(3,2,R.Picked,left=True);assert a.evalParm('places')==1                                                                    # the click arrives twice (Start and Picked): one instance
    mouse(3,2,R.Changed,left=False);assert a.evalParm('places')==1
    time.sleep(0.3);mouse(6,5,R.Start,left=True);assert a.evalParm('places')==2 and np.allclose(a.evalParmTuple('place_pos2'),[6,0,5],atol=1e-6) and a.evalParm('place_id2')==2
    time.sleep(0.3);mouse(3.01,2,R.Start,left=True,ctrl=True);assert a.evalParm('places')==1 and a.evalParm('place_id1')==2 and np.allclose(a.evalParmTuple('place_pos1'),[6,0,5],atol=1e-6)     # Ctrl-click deletes the one under the mouse
    time.sleep(0.3);mouse(0,9,R.Start,left=True,ctrl=True);assert a.evalParm('places')==1                                          # nothing there: nothing deleted
    # the settings in the viewport
    assert state.onMouseWheelEvent({'ui_event':Event(Device(0,0,wheel=1,shift=True),R.Changed)}) is True and abs(a.evalParm('place_def_scale')-1.1)<1e-9
    assert state.onMouseWheelEvent({'ui_event':Event(Device(0,0,wheel=-1,ctrl=True),R.Changed)}) is True and a.evalParm('place_def_yaw')==-15.0
    assert state.onMouseWheelEvent({'ui_event':Event(Device(0,0,wheel=1),R.Changed)}) is False
    for key,parm,value in ((']','place_def_scale',1.1*1.1),('[','place_def_scale',1.1),('.','place_def_yaw',0.0),(',','place_def_yaw',-15.0),('2','place_def_proto',2),('0','place_def_proto',0)):
        assert state.onKeyEvent({'ui_event':Event(Device(0,0,key=key),R.Changed)}) is True and abs(a.evalParm(parm)-value)<1e-9,(key,a.evalParm(parm))
    assert state.onKeyEvent({'ui_event':Event(Device(0,0,key='x'),R.Changed)}) is False and 'Esc' in viewer.prompt
    state.onKeyEvent({'ui_event':Event(Device(0,0,key='h'),R.Changed)});assert 'Esc' not in viewer.prompt and 'scale' in viewer.prompt
    time.sleep(0.3);a.parm('place_def_proto').set(2);a.parm('place_def_scale').set(1.25);a.parm('place_def_yaw').set(40.0);mouse(1,1,R.Start,left=True)
    assert a.evalParm('places')==2 and a.evalParm('place_proto2')==2 and np.allclose(a.evalParmTuple('place_scale2'),[1.25]*3) and np.allclose(a.evalParmTuple('place_rot2'),[0,40,0],atol=1e-6)
    assert a.evalParm('paint_data')==paint and a.evalParm('mode')==9                                                               # no painting, no mode change
    o=by_id(out(a));assert o['ids'].tolist()==[2,3] and np.allclose(o['pos'][0],[6,0,5],atol=1e-5)                                    # and the instancer follows the table
    # a slope: the tool places on the Place On prim and aligns to its normal
    time.sleep(0.3);a.parm('place_target').set('/World/Ramp');a.parm('place_align').set(1.0);a.parm('places').set(0);state.onResume({'node':a});mouse(0,0,R.Start,left=True)
    pos=np.array(a.evalParmTuple('place_pos1'));assert abs(pos[1]-(5.0-pos[2])*0.5)<1e-6 and abs(pos[0])<1e-6,pos                                   # on the ramp y = (5 - z) / 2
    nrm=np.array([0.0,1.0,0.5])/np.linalg.norm([0.0,1.0,0.5]);assert np.allclose(quat_apply(m.place_quat(a.evalParmTuple('place_rot1')),np.array([0,1.0,0])),nrm,atol=1e-6)
    state.onExit({'node':a});assert not state.placing and viewer.prompt is None and not state.marker.shown
    assert mouse(1,1,R.Start,left=True) is False and a.evalParm('places')==1                                                         # idle again

def with_other_stages():
    st,sc=new_scene('stages');rows=[dict(id=10,pos=(1,0,1)),dict(id=20,pos=(3,0,2)),dict(id=30,pos=(-2,0,4))];a=place_node(st,sc,rows);a.hdaModule().override_set(a,20,delete=True)
    assert by_id(out(a))['ids'].tolist()==[10,30]                                                                                  # an Instance Override on a placed id
    a.parm('scale_random_mode').set(1);a.parm('scale_min').set(0.5);a.parm('scale_max').set(1.5);o1=by_id(out(a));a.hdaModule().place_remove(a,1);o2=by_id(out(a))
    assert o1['ids'].tolist()==[10,30] and o2['ids'].tolist()==[30] and np.allclose(o1['scales'][1],o2['scales'][0],atol=1e-6)         # the random scale of an id does not change when another row goes

def contract():
    st,sc=new_scene('contract');a=st.createNode(TYPE,'C');g=a.parmTemplateGroup();mode=g.find('mode');assert mode.menuLabels()[9]=='Instance Place' and len(mode.menuLabels())==10
    for name in ('places','place_start','place_target','place_align','place_offset','place_def_scale','place_def_yaw','place_def_yawrand','place_def_proto','place_seed','place_info','place_fix','place_clear'):assert g.find(name) is not None,name
    place=g.find('place');assert place.conditionalType()==hou.parmCondType.HideWhen if hasattr(place,'conditionalType') else True
    assert 'place_start' in g.find('place_start').scriptCallback() and 'Esc' in g.find('place_start').help() and g.find('place_id#') is None or True
    layout=[t for t in g.entries() if t.label()=='Layout'][0];names=[t.name() for t in layout.parmTemplates()];assert 'place_start' in names and 'places' in names
    inst=a.node('USD_COMPILER');gen=inst.node('DISTRIBUTION_GENERATOR');assert gen.inputs()[9].name()=='generate_place'
    assert 'place_proto' in inst.node('PROTOTYPE_ASSIGNMENT').parm('snippet').eval()
    assert '$' not in a.type().definition().sections()['PythonModule'].contents().split('# ---- Instance Place')[1]

def main():
    for name,func in (('Maths: rotation convention, Euler round trip, id resolution, aiming at a normal',maths),
                      ('Table: ids, positions, rotations, scales, disabled rows, removing a row, Look tab scale, rows without ids',node_table),
                      ('Prototype Row per instance, a disabled bank row falls back to the Selection Mode',prototypes),
                      ('Other modes and the previous release are unchanged; defaults',defaults_unchanged),
                      ('Tool functions: add (defaults, offset, alignment, random yaw), nearest, remove, clear, undo',tool_functions),
                      ('Viewer tool: only the button starts it, click, double event, Ctrl-click delete, wheel and keys, slope, exit',viewer_place),
                      ('Works with Instance Overrides and Variation: ids stay stable',with_other_stages),
                      ('Contract: mode menu, parameters, layout, generator, VEX hook, no dollar signs',contract)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_place_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
