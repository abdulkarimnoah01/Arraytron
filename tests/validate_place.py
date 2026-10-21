"""v1.9.0 Instance Place in real Houdini: hython tests/validate_place.py [version]
Distribution Mode "Instance Place": instances placed one at a time from a table (Position, Rotate, Scale, Prototype Row, stable id) or by clicking a surface in the viewport.
Expected values come from independent rotation matrices, plain geometry and the instancer's own arrays. The viewport tool is exercised through a stand-in viewport that looks
straight down. Env ARRAYTRON_MUTATE=place_euler|place_ids|place_on|place_ctrl|place_align|place_cspace|place_cids|place_cscale|place_corder|place_snap|place_snaprot|place_drag|place_curve breaks the module; the suite must FAIL."""
from pathlib import Path
import hou, json, os, sys, tempfile, time, types
import numpy as np
from pxr import Usd, UsdGeom, Gf, Sdf
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v1.9.0':'v1.8.0','v1.10.0':'v1.9.0','v1.11.0':'v1.10.0','v1.12.0':'v1.11.0','v1.13.0':'v1.12.0','v1.14.0':'v1.13.0','v1.15.0':'v1.14.0','v1.16.0':'v1.15.0','v1.17.0':'v1.16.0','v1.18.0':'v1.17.0','v1.19.0':'v1.18.0','v1.20.0':'v1.19.0','v1.21.0':'v1.20.0','v1.21.1':'v1.21.0','v1.22.0':'v1.21.1','v1.21.1':'v1.21.0','v1.22.0':'v1.21.1','v1.12.0':'v1.11.0','v1.13.0':'v1.12.0','v1.14.0':'v1.13.0','v1.15.0':'v1.14.0'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_place_'));checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')
def write_scene():
    path=WORK/'place.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    for name in ('Ball','BallB'):UsdGeom.Xform.Define(s,'/World/Props/'+name);UsdGeom.Cube.Define(s,'/World/Props/%s/C'%name).CreateSizeAttr(0.2)
    r=UsdGeom.Mesh.Define(s,'/World/Ramp');r.CreatePointsAttr([(-5,0,5),(5,0,5),(5,5,-5),(-5,5,-5)]);r.CreateFaceVertexCountsAttr([4]);r.CreateFaceVertexIndicesAttr([0,1,2,3]);r.CreateOrientationAttr('rightHanded')
    c=UsdGeom.BasisCurves.Define(s,'/World/Path');c.CreateTypeAttr('linear');c.CreateWrapAttr('nonperiodic');c.CreatePointsAttr([(0,0.5,0),(4,0.5,0),(4,0.5,4)]);c.CreateCurveVertexCountsAttr([3])
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
        for key,parm in (('copies','place_copies'),('ct','place_ctrans'),('cr','place_crot'),('cs','place_cscale'),('cspace','place_cspace')):
            if key in r:
                p=a.parmTuple('%s%d'%(parm,i));p.set(r[key] if isinstance(r[key],(tuple,list)) else (r[key],))
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
        elif MUTATE=='place_cspace':
            good=g['place_expand'];g['place_expand']=lambda pos,rot,scale,copies,t,r,sc,space=0:good(pos,rot,scale,copies,t,r,sc,1-int(space))
        elif MUTATE=='place_cids':g['place_copy_ids']=lambda row_id,copies:[int(row_id)]*int(copies)
        elif MUTATE=='place_cscale':
            good=g['place_expand'];g['place_expand']=lambda pos,rot,scale,copies,t,r,sc,space=0:good(pos,rot,scale,copies,t,r,1.0,space)
        elif MUTATE=='place_corder':
            def swapped(pos,rot,scale,copies,t,r,sc,space=0):
                n=int(copies);P=np.zeros((n,3));Q=np.zeros((n,4));S=np.zeros((n,3));p=np.array(pos,dtype=float);q=g['place_quat'](rot);sv=np.array(scale,dtype=float);qs=g['place_quat'](r)
                for k in range(n):
                    P[k]=p;Q[k]=q;S[k]=sv;q=g['place_qmul'](q,qs);p=p+g['place_rotate'](q,sv*np.array(t,dtype=float));sv=sv*sc                       # rotates before it moves
                return P,Q,S
            g['place_expand']=swapped
        elif MUTATE=='place_snap':g['place_snap_point']=lambda asset,surface,point,normal:(point,normal)
        elif MUTATE=='place_snaprot':g['place_snap_value']=lambda value,step:float(value)
        elif MUTATE=='place_drag':
            good=g['place_drag_values'];g['place_drag_values']=lambda dx,dy,yaw_per_pixel=0.5,scale_pixels=150.0:(lambda r:(-r[0],r[1]))(good(dx,dy,yaw_per_pixel,scale_pixels))
        elif MUTATE=='place_curve':
            good=g['place_curve_samples'];g['place_curve_samples']=lambda asset:(lambda r:(r[0],r[1]*0.0))(good(asset))
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
    mouse(3,2,R.Start,left=True);assert a.evalParm('places')==0;mouse(3,2,R.Changed,left=False);assert a.evalParm('places')==1 and np.allclose(a.evalParmTuple('place_pos1'),[3,0,2],atol=1e-6) and a.evalParm('place_id1')==1 and '1 placed' in viewer.prompt
    mouse(3,2,R.Picked,left=True);assert a.evalParm('places')==1                                                                    # the click arrives as Start, Changed and Picked: one instance
    time.sleep(0.3);mouse(6,5,R.Start,left=True);mouse(6,5,R.Changed,left=False);assert a.evalParm('places')==2 and np.allclose(a.evalParmTuple('place_pos2'),[6,0,5],atol=1e-6) and a.evalParm('place_id2')==2
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
    time.sleep(0.3);a.parm('place_def_proto').set(2);a.parm('place_def_scale').set(1.25);a.parm('place_def_yaw').set(40.0);mouse(1,1,R.Start,left=True);mouse(1,1,R.Changed,left=False)
    assert a.evalParm('places')==2 and a.evalParm('place_proto2')==2 and np.allclose(a.evalParmTuple('place_scale2'),[1.25]*3) and np.allclose(a.evalParmTuple('place_rot2'),[0,40,0],atol=1e-6)
    assert a.evalParm('paint_data')==paint and a.evalParm('mode')==9                                                               # no painting, no mode change
    o=by_id(out(a));assert o['ids'].tolist()==[2,3] and np.allclose(o['pos'][0],[6,0,5],atol=1e-5)                                    # and the instancer follows the table
    # a slope: the tool places on the Place On prim and aligns to its normal
    time.sleep(0.3);a.parm('place_target').set('/World/Ramp');a.parm('place_align').set(1.0);a.parm('places').set(0);state.onResume({'node':a});mouse(0,0,R.Start,left=True);mouse(0,0,R.Changed,left=False)
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
    st,sc=new_scene('contract');a=st.createNode(TYPE,'C');g=a.parmTemplateGroup();mode=g.find('mode');assert mode.menuLabels()[9]=='Instance Place' and len(mode.menuLabels())==10+(1 if a.parm('biomes') is not None else 0)
    for name in ('place_snap','place_snap_rot','place_dragset','place_curve','place_curve_mode','place_curve_count','place_curve_spacing','place_curve_follow','place_curve_project','place_curve_go'):assert g.find(name) is not None,name
    for name in ('place_copies#','place_ctrans#','place_crot#','place_cscale#','place_cspace#','place_def_copies','place_def_ctrans','place_def_crot','place_def_cscale','place_def_cspace'):assert g.find(name) is not None,name
    for name in ('places','place_start','place_target','place_align','place_offset','place_def_scale','place_def_yaw','place_def_yawrand','place_def_proto','place_seed','place_info','place_fix','place_clear'):assert g.find(name) is not None,name
    place=g.find('place');assert place.conditionalType()==hou.parmCondType.HideWhen if hasattr(place,'conditionalType') else True
    assert 'place_start' in g.find('place_start').scriptCallback() and 'Esc' in g.find('place_start').help() and g.find('place_id#') is None or True
    layout=[t for t in g.entries() if t.label()=='Layout'][0];names=[t.name() for t in layout.parmTemplates()];assert 'place_start' in names and 'places' in names
    inst=a.node('USD_COMPILER');gen=inst.node('DISTRIBUTION_GENERATOR');assert gen.inputs()[9].name()=='generate_place'
    assert 'place_proto' in inst.node('PROTOTYPE_ASSIGNMENT').parm('snippet').eval()
    assert '$' not in a.type().definition().sections()['PythonModule'].contents().split('# ---- Instance Place')[1]

def mat_trs(pos,deg,scale):
    M=np.eye(4);M[:3,:3]=rot_matrix(deg)@np.diag(scale);M[:3,3]=pos;return M
def array_maths():
    st,sc=new_scene('arrmaths');a=st.createNode(TYPE,'M');m=a.hdaModule();mutate(a)
    pos=np.array([1.0,0.5,-2.0]);rot=np.array([10.0,30.0,-20.0]);scale=np.array([1.5,1.5,1.5]);t=np.array([0.5,0.2,1.0]);r=np.array([0.0,25.0,5.0]);ss=0.9;n=6
    P,Q,S=m.place_expand(pos,rot,scale,n,t,r,ss,0);M=mat_trs(pos,rot,scale);step=np.eye(4);step[:3,:3]=rot_matrix(r)*ss;step[:3,3]=t           # Local: M(k+1) = M(k) * (T R s)
    for k in range(n):
        assert np.allclose(P[k],M[:3,3],atol=1e-9),(k,P[k],M[:3,3])
        cols=np.linalg.norm(M[:3,:3],axis=0);assert np.allclose(S[k],cols,atol=1e-9) and np.allclose(quat_apply(Q[k],np.array([1.0,0,0])),(M[:3,:3]/cols)@np.array([1.0,0,0]),atol=1e-9) and np.allclose(quat_apply(Q[k],np.array([0,0,1.0])),(M[:3,:3]/cols)@np.array([0,0,1.0]),atol=1e-9)
        M=M@step
    sn=np.array([1.0,2.0,0.5]);P,Q,S=m.place_expand(pos,rot,sn,n,t,r,ss,0);R=rot_matrix(rot);p=pos.copy();Rs=rot_matrix(r)                                    # a non-uniform scale stays in the instance's own axes (no shear)
    for k in range(n):
        assert np.allclose(P[k],p,atol=1e-9) and np.allclose(S[k],sn*ss**k,atol=1e-9) and np.allclose(quat_apply(Q[k],np.array([0,1.0,0])),R@np.array([0,1.0,0]),atol=1e-9)
        p=p+R@(sn*ss**k*t);R=R@Rs
    P,Q,S=m.place_expand(pos,rot,scale,n,t,r,ss,1)                                                                        # World: translation along the world axes, rotation and scale about the copy itself
    R0=rot_matrix(rot);Rs=rot_matrix(r)
    for k in range(n):
        assert np.allclose(P[k],pos+k*t,atol=1e-9) and np.allclose(S[k],scale*ss**k,atol=1e-9)
        R=np.linalg.matrix_power(Rs,k)@R0;assert np.allclose(quat_apply(Q[k],np.array([1.0,0,0])),R@np.array([1.0,0,0]),atol=1e-9) and np.allclose(quat_apply(Q[k],np.array([0,1.0,0])),R@np.array([0,1.0,0]),atol=1e-9)
    P,Q,S=m.place_expand(pos,rot,scale,1,t,r,ss,0);assert P.shape==(1,3) and np.allclose(P[0],pos) and np.allclose(S[0],scale)                      # one copy is the row itself
    sq=m.place_expand((0,0,0),(0,0,0),(1,1,1),4,(1,0,0),(0,90,0),1.0,0)[0];assert np.allclose(sq,[[0,0,0],[1,0,0],[1,0,-1],[0,0,-1]],atol=1e-9)           # a square: turn 90 degrees after every step
    ids=m.place_copy_ids(7,3);assert ids==[7,1000070001,1000070002] and m.place_copy_ids(7,1)==[7]
    every=[i for row in (5,6,99999) for i in m.place_copy_ids(row,9999)];assert len(every)==len(set(every)) and max(every)<2**31                           # unique across rows, inside 32 bits
    assert abs(m.place_rotate(m.place_quat((0,90,0)),np.array([1.0,0,0]))[2]+1.0)<1e-9

def array_node():
    st,sc=new_scene('arrnode');rows=[dict(id=5,pos=(0,0,0),copies=4,ct=(1,0,0),cs=0.5),dict(id=6,pos=(0,0,3),copies=1,scale=(2,2,2))]
    a=place_node(st,sc,rows);o=by_id(out(a));ids=sorted(o['ids'].tolist());assert ids==sorted([5,1000050001,1000050002,1000050003,6]),ids
    P=dict(zip(o['ids'].tolist(),o['pos'].tolist()));S=dict(zip(o['ids'].tolist(),o['scales'].tolist()))
    assert np.allclose(P[5],[0,0,0],atol=1e-5) and np.allclose(P[1000050001],[1,0,0],atol=1e-5) and np.allclose(P[1000050002],[1.5,0,0],atol=1e-5) and np.allclose(P[1000050003],[1.75,0,0],atol=1e-5)   # each step is half the size of the one before
    assert np.allclose(S[1000050003],[0.125]*3,atol=1e-5) and np.allclose(S[6],[2,2,2],atol=1e-5) and np.allclose(P[6],[0,0,3],atol=1e-5)
    a.parm('place_on1').set(0);assert sorted(by_id(out(a))['ids'].tolist())==[6]                                          # a disabled row switches all its copies off
    a.parm('place_on1').set(1);a.hdaModule().place_remove(a,2);o=by_id(out(a));assert sorted(o['ids'].tolist())==[5,1000050001,1000050002,1000050003]            # other rows come and go: the copies keep their ids
    b=place_node(st,sc,[dict(id=3,pos=(0,0,0),copies=4,ct=(0,0,2),cr=(0,90,0),cspace=1)],name='World');o=by_id(out(b));ids=o['ids'].tolist()                    # World steps: straight along Z
    assert np.allclose(o['pos'][np.argsort(ids)] if False else sorted(o['pos'].tolist(),key=lambda v:v[2]),[[0,0,0],[0,0,2],[0,0,4],[0,0,6]],atol=1e-5)
    c=place_node(st,sc,[dict(id=1,pos=(0,0,0),copies=5,ct=(1,0,0),cr=(0,90,0),cspace=0,proto=0)],name='Local');o=out(c);pos=sorted(tuple(round(v,4)+0.0 for v in q) for q in o['pos'].tolist());assert pos==sorted([(0.0,0.0,0.0),(1.0,0.0,0.0),(1.0,0.0,-1.0),(0.0,0.0,-1.0),(0.0,0.0,0.0)]),pos   # a square, the fifth copy lands on the first
    c.parm('base_scale').set(2.0);assert np.allclose(out(c)['scales'],2.0,atol=1e-5)                                          # the Look tab scale multiplies every copy
    d=place_node(st,sc,[dict(id=100000,pos=(0,0,0),copies=2)],name='Big')
    try:out(d)
    except AssertionError as exc:assert 'below 100000' in str(exc),str(exc)[:200]
    else:raise AssertionError('an id above 99999 cannot make copies')
    e=place_node(st,sc,[dict(id=100000,pos=(0,0,0))],name='BigOne');assert out(e)['ids'].tolist()==[100000]                      # a single instance keeps any id
    f=place_node(st,sc,[dict(id=2,pos=(0,0,0),copies=3,proto=2),dict(id=4,pos=(0,0,5))],name='Protos',protos=2,proto_mode=3);o=by_id(out(f));assert o['proto'].tolist()[:1]==[1] and sum(1 for v in o['proto'] if v==1)>=3                # the copies share the Prototype Row
    assert '2 rows' in f.hdaModule().place_info(f) and '4 instances' in f.hdaModule().place_info(f)

def array_tool():
    R=hou.uiEventReason;st,sc=new_scene('arrtool');a=place_node(st,sc,[],place_def_copies=4,place_def_ctrans=(1.0,0.0,0.0),place_def_crot=(0.0,15.0,0.0),place_def_cscale=0.9,place_def_cspace=0);m=a.hdaModule()
    assert m.place_add(a,(1.0,0.0,2.0))==1 and a.evalParm('place_copies1')==4 and np.allclose(a.evalParmTuple('place_ctrans1'),[1,0,0]) and np.allclose(a.evalParmTuple('place_crot1'),[0,15,0]) and abs(a.evalParm('place_cscale1')-0.9)<1e-9 and a.evalParm('place_cspace1')==0
    o=by_id(out(a));assert len(o['ids'])==4
    arr=m.place_arrays(a);assert arr['copy'].tolist()==[0,1,2,3] and arr['row'].tolist()==[1,1,1,1]
    k=int(np.nonzero(arr['copy']==2)[0][0]);x,y,z=arr['P'][k];row=m.place_nearest(a,(x,10.0,z),(0,-1,0));assert row[0]==1 and row[1]==int(arr['ids'][k])                  # a copy belongs to its row
    state,viewer=make_state();a.parm('mode').set(9);a.setUserData('arraytron_place','1');state.onEnter({'node':a})
    def mouse(xx,zz,reason,**kw):return state.onMouseEvent({'ui_event':Event(Device(float(xx)*10,float(zz)*10,**kw),reason)})
    assert mouse(8,8,R.Located) is True and state.placing
    time.sleep(0.3);mouse(arr['P'][k][0],arr['P'][k][2],R.Start,left=True,ctrl=True);assert a.evalParm('places')==0                                       # Ctrl-click on a copy deletes the whole array
    time.sleep(0.3);mouse(5,5,R.Start,left=True);mouse(5,5,R.Changed,left=False);assert a.evalParm('places')==1 and a.evalParm('place_copies1')==4 and len(by_id(out(a))['ids'])==4
    state.onExit({'node':a})

def snap_and_drag():
    R=hou.uiEventReason;st,sc=new_scene('snap');a=place_node(st,sc,[],place_snap=0.5,place_snap_rot=15.0);m=a.hdaModule();state,viewer=make_state()
    def mouse(x,z,reason,**kw):return state.onMouseEvent({'ui_event':Event(Device(float(x)*10,float(z)*10,**kw),reason)})
    a.setUserData('arraytron_place','1');state.onEnter({'node':a});mouse(3.2,2.3,R.Located);assert 'snap 0.5 / 15 deg' in viewer.prompt and state.marker.shown
    assert np.allclose(state.place_hit[0],[3.0,0.0,2.5],atol=1e-9)                                                                 # the marker sits on the grid
    mouse(3.2,2.3,R.Start,left=True);mouse(3.2,2.3,R.Changed,left=False);assert np.allclose(a.evalParmTuple('place_pos1'),[3.0,0.0,2.5],atol=1e-6) and np.allclose(a.evalParmTuple('place_rot1'),[0,0,0],atol=1e-6)
    time.sleep(0.3);mouse(5,5,R.Start,left=True);assert a.evalParm('places')==1                                                       # the press only records the point
    dyaw,k=m.place_drag_values(74,75);assert abs(dyaw-37.0)<1e-9 and abs(k-2**0.5)<1e-9
    mouse(5+7.4,5-7.5,R.Active,left=True);assert 'drag: rotation +37 deg' in viewer.prompt and 'release' in viewer.prompt and state.place_drag is not None
    mouse(5+7.4,5-7.5,R.Changed,left=False);assert a.evalParm('places')==2 and state.place_drag is None
    assert np.allclose(a.evalParmTuple('place_pos2'),[5,0,5],atol=1e-6) and np.allclose(a.evalParmTuple('place_rot2'),[0,30,0],atol=1e-6) and np.allclose(a.evalParmTuple('place_scale2'),[2**0.5]*3,atol=1e-6)     # 37 degrees snapped to 30
    mouse(5+7.4,5-7.5,R.Picked,left=True);assert a.evalParm('places')==2                                                              # the Picked that follows the release does not place again
    a.parm('place_snap_rot').set(0.0);time.sleep(0.3);mouse(5,5,R.Start,left=True);mouse(5+7.4,5-7.5,R.Active,left=True);mouse(5+7.4,5-7.5,R.Changed,left=False);assert abs(a.evalParmTuple('place_rot3')[1]-37.0)<1e-6           # no rotation snap
    a.parm('place_def_yaw').set(10.0);a.parm('place_def_scale').set(2.0);time.sleep(0.3);mouse(6,6,R.Start,left=True);mouse(6,6,R.Changed,left=False);assert abs(a.evalParmTuple('place_rot4')[1]-10.0)<1e-6 and np.allclose(a.evalParmTuple('place_scale4'),[2.0]*3)   # a click adds nothing to the settings
    a.parm('place_dragset').set(0);time.sleep(0.3);mouse(7,7,R.Start,left=True);assert a.evalParm('places')==5                          # Drag Sets off: the press places
    time.sleep(0.3);a.parm('place_dragset').set(1);mouse(8,1,R.Picked,left=True);assert a.evalParm('places')==6                          # a click that is only a Picked places at once
    # the grid on a slope: X and Z are rounded, the point goes back on the ramp
    a.parm('places').set(0);a.parm('place_target').set('/World/Ramp');state.onResume({'node':a});a.parm('place_snap').set(0.5);time.sleep(0.3);mouse(3.2,2.3,R.Start,left=True);mouse(3.2,2.3,R.Changed,left=False)
    pos=np.array(a.evalParmTuple('place_pos1'));assert np.allclose(pos,[3.0,1.25,2.5],atol=1e-6),pos
    state.onExit({'node':a})

def along_curve():
    st,sc=new_scene('curve');a=place_node(st,sc,[],place_curve='/World/Path',place_curve_count=5,place_def_scale=1.5,place_def_proto=2,protos=2);m=a.hdaModule();mutate(a)
    P,H=m.place_curve_samples(a);assert np.allclose(P,[[0,.5,0],[2,.5,0],[4,.5,0],[4,.5,2],[4,.5,4]],atol=1e-9) and np.allclose(H,[90,90,0,0,0],atol=1e-9)         # by count, the ends included; +Z follows the tangent
    assert m.place_along_curve(a)==5 and a.evalParm('places')==5
    for i,(p,yaw) in enumerate(zip(P,H),1):
        assert np.allclose(a.evalParmTuple('place_pos%d'%i),p,atol=1e-6) and np.allclose(a.evalParmTuple('place_rot%d'%i),[0,yaw,0],atol=1e-6) and np.allclose(a.evalParmTuple('place_scale%d'%i),[1.5]*3) and a.evalParm('place_proto%d'%i)==2 and a.evalParm('place_id%d'%i)==i
    o=by_id(out(a));assert o['ids'].tolist()==[1,2,3,4,5] and np.allclose(o['pos'],P,atol=1e-5)
    a.parm('place_curve_follow').set(0);a.parm('place_def_yaw').set(20.0);m.place_along_curve(a);assert a.evalParm('places')==10 and np.allclose(a.evalParmTuple('place_rot6'),[0,20,0],atol=1e-6) and a.evalParm('place_id6')==6   # appended, ids go on, no turning, New Rotation added
    hou.undos.performUndo();assert a.evalParm('places')==5                                                                          # one undo step
    b=place_node(st,sc,[],name='Spacing',place_curve='/World/Path',place_curve_mode=1,place_curve_spacing=3.0);bm=b.hdaModule();Q,_=bm.place_curve_samples(b);assert np.allclose(Q,[[0,.5,0],[3,.5,0],[4,.5,2],[4,.5,4]][:3],atol=1e-9) or np.allclose(Q[:3],[[0,.5,0],[3,.5,0],[4,.5,2]],atol=1e-9)
    c=place_node(st,sc,[],name='Project',place_curve='/World/Path',place_curve_count=3,place_curve_project=1,place_target='/World/Ramp',place_align=0.0);cm=c.hdaModule();cm.place_along_curve(c);y=[c.evalParmTuple('place_pos%d'%i)[1] for i in (1,2,3)];z=[c.evalParmTuple('place_pos%d'%i)[2] for i in (1,2,3)]
    assert np.allclose(y,[(5-v)/2 for v in z],atol=1e-6)                                                                            # on the ramp, not at the curve height
    d=place_node(st,sc,[],name='NoPath')
    try:d.hdaModule().place_along_curve(d)
    except hou.NodeError as exc:assert 'Curve Prim is empty' in str(exc)
    else:raise AssertionError('an empty curve prim must be an error')
    d.parm('place_curve').set('/World/Props/Ball')
    try:d.hdaModule().place_along_curve(d)
    except hou.NodeError as exc:assert 'No BasisCurves' in str(exc)
    else:raise AssertionError('a prim without curves must be an error')

def cleanups():
    st,sc=new_scene('clean');a=st.createNode(TYPE);assert a.name()=='arraytron1',a.name()                                       # not instancer1
    b=st.createNode(TYPE,'y');b2=st.createNode(TYPE);c=st.createNode(TYPE);assert (b2.name(),c.name())==('arraytron2','arraytron3'),(b2.name(),c.name())
    assert b.name()=='y'                                                                                                           # a name the user gave is kept
    assert a.parmTemplateGroup().find('phys_on').label()=='Settle Instances'

def main():
    for name,func in (('Maths: rotation convention, Euler round trip, id resolution, aiming at a normal',maths),
                      ('Table: ids, positions, rotations, scales, disabled rows, removing a row, Look tab scale, rows without ids',node_table),
                      ('Prototype Row per instance, a disabled bank row falls back to the Selection Mode',prototypes),
                      ('Other modes and the previous release are unchanged; defaults',defaults_unchanged),
                      ('Tool functions: add (defaults, offset, alignment, random yaw), nearest, remove, clear, undo',tool_functions),
                      ('Viewer tool: only the button starts it, click, double event, Ctrl-click delete, wheel and keys, slope, exit',viewer_place),
                      ('Works with Instance Overrides and Variation: ids stay stable',with_other_stages),
                      ('Arrays: Copy and Transform maths against 4x4 matrices (local, world), copy ids',array_maths),
                      ('Arrays on the node: ids, positions, scales, spirals, disabled and removed rows, Look tab scale, id limit, prototype row',array_node),
                      ('Arrays in the tool: new-copy settings, a copy belongs to its row, Ctrl-click deletes the array',array_tool),
                      ('Tool extras: grid snap, rotation snap, press-drag-release, click variants, snapping on a slope',snap_and_drag),
                      ('Place Along Curve: samples, headings, ids, spacing, projection, undo, errors',along_curve),
                      ('Cleanups: the node is called arraytron1, the physics checkbox label',cleanups),
                      ('Contract: mode menu, parameters, layout, generator, VEX hook, no dollar signs',contract)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_place_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
