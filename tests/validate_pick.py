"""v1.7.0 Pick Instance in real Houdini: hython tests/validate_pick.py [version]
The instances are read from the node's USD stage in world space, the mouse ray picks the instance closest in angle (the nearest to the camera on a tie), hidden and deleted
instances cannot be picked, a click creates (or finds) the override row and Ctrl-click ticks Delete; the viewer state (stand-in viewport) shows the marker and the prompt, never
touches the paint or the mode, and is entered by the Pick Instance button's flag. Expected values come from the instancer's own arrays and plain geometry.
Env ARRAYTRON_MUTATE=pick_angle|pick_tie|pick_world|pick_mask|pick_ctrl breaks the module; the suite must FAIL."""
from pathlib import Path
import hou, json, os, sys, tempfile, time, types
import numpy as np
from pxr import Usd, UsdGeom, Gf
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v1.7.0':'v1.6.2','v1.8.0':'v1.7.0','v1.9.0':'v1.8.0','v1.10.0':'v1.9.0','v1.9.0':'v1.8.0','v1.10.0':'v1.9.0'}[VID]
TYPE=versions.type_name(VID)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_pick_'));checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')
def write_scene():
    path=WORK/'pick.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    UsdGeom.Xform.Define(s,'/World/Props/Ball');UsdGeom.Cube.Define(s,'/World/Props/Ball/C').CreateSizeAttr(0.2)
    s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True);hou.hda.installFile(str(versions.hda(VID)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
def painted(stage,source,P,name='Pick',**values):
    P=np.asarray(P,dtype=float).reshape(-1,3);a=stage.createNode(TYPE,name);a.setInput(0,source);a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Ball')
    a.parm('mode').set(6);a.parm('paint_prim').set('');a.parm('paint_align').set(0.0);m=a.hdaModule();table=np.column_stack([P,np.tile([0.0,1.0,0.0],(len(P),1)),np.arange(len(P))]);a.parm('paint_data').set(m.paint_encode(dict(pts=table,next=len(P),dab=1)))
    for k,v in values.items():a.parmTuple(k).set(v if isinstance(v,(tuple,list)) else (v,))
    mutate(a);return a
def line_node(stage,source,count=6,name='Line'):
    a=stage.createNode(TYPE,name);a.setInput(0,source);a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Ball');a.parm('mode').set(0);a.parm('line_count').set(count);mutate(a);return a
def out(a):
    s=a.stage();assert not a.errors(),a.errors();pi=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    return dict(pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3),ids=np.array(pi.GetIdsAttr().Get(t) or [],dtype=int),hidden=sorted(int(i) for i in (pi.GetInvisibleIdsAttr().Get(t) or [])))
def mutate(a):
    g=a.hdaModule().pick_nearest.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='pick_angle':
        good=g['pick_nearest'];g['pick_nearest']=lambda o,d,P,ids,tolerance=0.045:good(o,d,P,ids,10.0)                              # anything is a hit
    elif MUTATE=='pick_tie':
        def far(o,d,P,ids,tolerance=0.045):
            d=np.asarray(d,dtype=float);d=d/np.linalg.norm(d);v=P-np.asarray(o,dtype=float);t=v@d;perp=np.linalg.norm(v-t[:,None]*d[None,:],axis=1);ang=perp/np.maximum(t,1e-6)
            near=np.nonzero(ang<=ang.min()+1e-6)[0];k=near[np.argmax(t[near])]                                                      # the farthest of the tied ones
            return (int(ids[k]),P[k].copy(),float(t[k])) if ang[k]<=tolerance else None
        g['pick_nearest']=far
    elif MUTATE=='pick_world':
        good=g['pick_instances'];g['pick_instances']=lambda asset:(lambda r:dict(ids=r['ids'],P=r['P']-np.array([asset.evalParm('bound_tx'),asset.evalParm('bound_ty'),asset.evalParm('bound_tz')])))(good(asset))   # local, not world
    elif MUTATE=='pick_mask':
        good=g['pick_instances']
        def all_instances(asset):
            stage=asset.stage()
            if stage is None or not stage.GetPrimAtPath(asset.evalParm('outputpath')).IsValid():return good(asset)
            prim=stage.GetPrimAtPath(asset.evalParm('outputpath'))
            pi=UsdGeom.PointInstancer(prim);t=hou.frame();P=np.array(pi.GetPositionsAttr().Get(t)).reshape(-1,3)+np.array([asset.evalParm('bound_t'+c) for c in 'xyz'])
            return dict(ids=np.array(pi.GetIdsAttr().Get(t),dtype=np.int64),P=P)                                                        # hidden ids are not skipped
        g['pick_instances']=all_instances
    elif MUTATE=='pick_ctrl':
        good=g['pick_add'];g['pick_add']=lambda asset,iid,delete=False:good(asset,iid,False)
    elif MUTATE:raise SystemExit('unknown mutation '+MUTATE)
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()
GRID=[(1,0,1),(3,0,1),(1,0,3),(3,0,3)]
def ray_down(x,z,y=10.0):return (x,y,z),(0.0,-1.0,0.0)

def instances_world():
    st,sc=new_scene('world');a=painted(st,sc,GRID);m=a.hdaModule();o=out(a);inst=m.pick_instances(a)
    order=np.argsort(inst['ids']);assert list(inst['ids'][order])==sorted(o['ids'].tolist())==[0,1,2,3] and np.allclose(inst['P'][order],o['pos'][np.argsort(o['ids'])],atol=1e-6)
    a.parm('bound_tx').set(2.0);a.parm('bound_tz').set(-1.0);o=out(a);inst=m.pick_instances(a);order=np.argsort(inst['ids'])
    assert np.allclose(inst['P'][order],o['pos'][np.argsort(o['ids'])]+np.array([2.0,0.0,-1.0]),atol=1e-6),(inst['P'],o['pos'])                              # the Bounds Transform is in the world position
    empty=st.createNode(TYPE,'Empty');empty.setInput(0,sc);e=empty.hdaModule().pick_instances(empty);assert len(e['ids'])==0 and e['P'].shape==(0,3)       # no instancer yet: nothing to pick

def ray_picking():
    st,sc=new_scene('ray');a=painted(st,sc,GRID);m=a.hdaModule();inst=m.pick_instances(a)
    for i,(x,y,z) in enumerate(GRID):
        hit=m.pick_nearest(*ray_down(x,z),inst['P'],inst['ids']);assert hit is not None and hit[0]==i and np.allclose(hit[1],[x,y,z],atol=1e-6) and abs(hit[2]-10.0)<1e-6,(i,hit)
    assert m.pick_nearest(*ray_down(8.0,8.0),inst['P'],inst['ids']) is None                                                         # a miss
    assert m.pick_nearest(*ray_down(1.2,1.0),inst['P'],inst['ids'])[0]==0                                                           # 0.2 off at distance 10: inside the tolerance
    assert m.pick_nearest(*ray_down(2.0,1.0),inst['P'],inst['ids']) is None                                                         # 1.0 off: outside it
    assert m.pick_nearest((1.0,10.0,1.0),(0.0,1.0,0.0),inst['P'],inst['ids']) is None                                              # looking away: nothing behind the camera
    near=m.pick_nearest(*ray_down(1.0,1.0,y=0.5),inst['P'],inst['ids']);assert near is not None and near[0]==0 and abs(near[2]-0.5)<1e-9
    tied=np.array([[1.0,0.0,1.0],[1.0,0.8,1.0]]);hit=m.pick_nearest(*ray_down(1.0,1.0),tied,np.array([7,9]));assert hit[0]==9                      # same line of sight: the one nearest the camera
    assert m.pick_nearest(*ray_down(1.0,1.0),np.zeros((0,3)),np.zeros(0,dtype=np.int64)) is None

def hidden_and_deleted():
    st,sc=new_scene('hidden');a=painted(st,sc,GRID);m=a.hdaModule()
    m.override_set(a,2,delete=True);inst=m.pick_instances(a);assert sorted(inst['ids'].tolist())==[0,1,3]                                  # a deleted instance cannot be picked
    assert m.pick_nearest(*ray_down(1.0,3.0),inst['P'],inst['ids']) is None
    b=painted(st,sc,[(i*0.5,0,1.0) for i in range(30)],name='Grow',grow_on=1,grow_start=1.0,grow_sweep=48.0,grow_time=12.0);hou.setFrame(30);o=out(b);assert len(o['hidden'])>0 and len(o['hidden'])<30,o['hidden']
    inst=b.hdaModule().pick_instances(b);assert len(inst['ids'])==30-len(o['hidden']) and not set(inst['ids'].tolist())&set(o['hidden'])                  # not grown yet: not pickable

def pick_rows():
    st,sc=new_scene('rows');a=painted(st,sc,GRID);m=a.hdaModule();assert m.pick_row(a,2)==0
    assert m.pick_add(a,2)==1 and m.pick_row(a,2)==1 and a.evalParm('overrides')==1 and a.evalParm('ovr_id1')==2 and a.evalParm('ovr_delete1')==0
    assert m.pick_add(a,2)==1 and a.evalParm('overrides')==1                                                                      # a second click finds the row
    assert m.pick_add(a,3,delete=True)==2 and a.evalParm('ovr_id2')==3 and a.evalParm('ovr_delete2')==1 and sorted(out(a)['ids'].tolist())==[0,1,2]   # Ctrl-click: Delete
    assert m.pick_add(a,2,delete=True)==1 and a.evalParm('ovr_delete1')==1 and a.evalParm('overrides')==2                       # Ctrl-click on an existing row ticks Delete too
    hou.undos.performUndo();assert a.evalParm('ovr_delete1')==0                                                                  # one undo step per click

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
    viewer=StubViewer();return glob['PaintState']('arraytron_pick_test',viewer),viewer

def viewer_pick():
    R=hou.uiEventReason;st,sc=new_scene('state');a=painted(st,sc,GRID);m=a.hdaModule();state,viewer=make_state();paint_before=a.evalParm('paint_data')
    def mouse(x,z,reason,**kw):return state.onMouseEvent({'ui_event':Event(Device(float(x)*10,float(z)*10,**kw),reason)})
    a.setUserData('arraytron_pick','1');state.onEnter({'node':a})                                                                   # the Pick Instance button
    assert state.picking and a.userData('arraytron_pick') is None and a.evalParm('mode')==6
    assert mouse(1,1,R.Located) is True and 'instance id 0' in viewer.prompt and state.marker.shown and 'Esc' in viewer.prompt
    assert mouse(8,8,R.Located) is True and 'no instance' in viewer.prompt and not state.marker.shown
    mouse(1,3,R.Start,left=True);assert m.pick_row(a,2)==1 and a.evalParm('ovr_delete1')==0 and 'override row 1' in viewer.prompt                      # a click: the row appears
    mouse(1,3,R.Picked,left=True);assert a.evalParm('overrides')==1                                                               # the click comes twice (Start and Picked): still one row
    mouse(3,3,R.Start,left=True,ctrl=True);assert a.evalParm('overrides')==2 and a.evalParm('ovr_id2')==3 and a.evalParm('ovr_delete2')==1
    mouse(3,3,R.Located);assert 'no instance' in viewer.prompt                                                                    # the deleted instance is gone from the list
    mouse(1,1,R.Changed,left=False);assert a.evalParm('overrides')==2                                                              # a release does nothing
    assert state.onMouseWheelEvent({'ui_event':Event(Device(0,0,wheel=1,shift=True),R.Changed)}) is False and state.onKeyEvent({'ui_event':Event(Device(0,0,key=']'),R.Changed)}) is False
    assert a.evalParm('paint_radius')==0.5*0+a.evalParm('paint_radius') and a.evalParm('paint_data')==paint_before and a.evalParm('mode')==6          # no painting, no brush changes
    state.onExit({'node':a});assert not state.picking and viewer.prompt is None and not state.marker.shown
    mouse(1,1,R.Start,left=True);assert a.evalParm('overrides')==2                                                                  # idle again (Paint mode, the paint tool would paint here): picking is over
    # the state is already current when the button is pressed (the node was selected): the flag is found on the next mouse event; another Distribution Mode
    l=line_node(st,sc,6);hou.setFrame(1);o=out(l);state,viewer=make_state();state.onEnter({'node':l})
    assert state.onMouseEvent({'ui_event':Event(Device(0,0),R.Located)}) is False and viewer.prompt is None and not state.picking and l.evalParm('mode')==0       # idle: nothing changes
    l.setUserData('arraytron_pick','1');x,_,z=o['pos'][np.argmin(o['ids'])];assert mouse(x,z,R.Located) is True and state.picking and 'instance id %d'%o['ids'].min() in viewer.prompt and l.evalParm('mode')==0
    state.onExit({'node':l})

def contract():
    st,sc=new_scene('contract');a=st.createNode(TYPE,'C');g=a.parmTemplateGroup();b=g.find('ovr_pick');assert b is not None and b.label()=='Pick Instance in Viewport'
    assert 'pick_start' in b.scriptCallback() and b.scriptCallbackLanguage()==hou.scriptLanguage.Python
    finish=[t for t in g.entries() if t.label()=='Finish'][0];names=[t.name() for t in finish.parmTemplates()];assert names.index('ovr_pick')<names.index('overrides')               # the button sits above the table
    m=a.hdaModule();assert all(hasattr(m,n) for n in ('pick_instances','pick_nearest','pick_add','pick_row','pick_start','pick_state_name'))
    assert b.help() and 'Ctrl-click' in b.help()
    src=a.type().definition().sections()['ViewerStateModule'].contents();assert 'arraytron_pick' in src and '_pick_mouse' in src and "'$'" not in src
    assert '$' not in a.type().definition().sections()['PythonModule'].contents().split('# ---- Pick Instance')[1]                                               # embedded scripts have no dollar sign

def main():
    for name,func in (('Instances are read from the stage in world space (Bounds Transform included); no instancer: empty',instances_world),
                      ('Mouse ray: closest in angle, nearest on a tie, tolerance, misses, behind the camera',ray_picking),
                      ('Deleted and not yet grown instances cannot be picked',hidden_and_deleted),
                      ('Click: the override row is created or found; Ctrl-click ticks Delete; one undo step',pick_rows),
                      ('Viewer state: button flag, marker, prompt, click, Ctrl-click, no painting, exit, idle in other modes',viewer_pick),
                      ('Contract: Pick Instance button above the table, module functions, state source, no dollar signs',contract)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_pick_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
