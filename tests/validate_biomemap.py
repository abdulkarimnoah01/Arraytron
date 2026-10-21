"""v1.20.0 Painted biome map in real Houdini: hython tests/validate_biomemap.py [version]
Paint where a biome grows and where it stays out. The stamps of the brush (row, +1 paint / -1 erase, position, radius, strength, falloff) live in the hidden biome_map_data; at cook time every row whose
Painted Map is not Off turns its stamps into a grid over the terrain (applied in the order painted: paint = maximum, erase = minimum), samples it at its candidates and combines it with the weight of its
conditions (Add And Erase: union with the paint, shrunk to 0 by the erase; Only Where Painted: product with the paint). The expected survivors are recomputed from the same stable candidates. The viewport
tool is exercised through a stand-in viewport that looks straight down. Env ARRAYTRON_MUTATE=bm_order|bm_erase|bm_only|bm_row breaks the module; the suite must FAIL."""
from pathlib import Path
import hou, json, math, os, sys, tempfile, time, types
import numpy as np
from pxr import Usd, UsdGeom
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v1.20.0':'v1.19.0','v1.21.0':'v1.20.0','v1.21.1':'v1.21.0','v1.22.0':'v1.21.1','v1.21.1':'v1.21.0','v1.22.0':'v1.21.1'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_biomemap_'));checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')
STRIDE=1000000
def write_scene():
    path=WORK/'biome.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    for name in ('Tree','Bush'):UsdGeom.Xform.Define(s,'/World/Props/'+name);UsdGeom.Cube.Define(s,'/World/Props/%s/C'%name).CreateSizeAttr(0.2)
    n=40;xs=np.linspace(-20,20,n+1);pts=[]
    for z in xs:
        for x in xs:pts.append((float(x),float(12.0*math.exp(-(x*x+z*z)/(2*7.0*7.0))),float(z)))
    idx=[]
    for j in range(n):
        for i in range(n):a=j*(n+1)+i;idx+=[a,a+n+1,a+n+2,a+1]
    m=UsdGeom.Mesh.Define(s,'/World/Terrain');m.CreatePointsAttr(pts);m.CreateFaceVertexCountsAttr([4]*(n*n));m.CreateFaceVertexIndicesAttr(idx);m.CreateOrientationAttr('rightHanded');m.CreateSubdivisionSchemeAttr('none')
    s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True)
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
KEYS=(('map','biome_map','i'),('name','biome_name','s'),('density','biome_density','f'),('mix','biome_mix','s'),('h','biome_hrange','t'),('s','biome_srange','t'),('layer','biome_layer','i'),('clear','biome_clear','f'),('scale','biome_scale','t'),('on','biome_on','i'))
def biome_node(stage,source,rows,typ=None,name='Map',**values):
    a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(2)
    for k,pr in enumerate(('Tree','Bush'),1):a.parm('proto_prim%d'%k).set('/World/Props/'+pr)
    a.parm('mode').set(10);a.parm('biomes').set(len(rows));a.parm('biome_seed').set(3);a.parm('biome_normal').set(0);a.parm('biome_moist_mode').set(0);a.parm('biome_moist_const').set(0.5)
    for i,r in enumerate(rows,1):
        for key,parm,kind in KEYS:
            if key in r:
                if kind=='t':a.parmTuple('%s%d'%(parm,i)).set(r[key])
                else:a.parm('%s%d'%(parm,i)).set(r[key])
    for k,v in values.items():a.parm(k).set(v)
    if typ is None:mutate(a)
    return a
def out(a):
    s=a.stage();assert not list(a.errors()),a.errors();pi=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    d=dict(pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3),ids=np.array(pi.GetIdsAttr().Get(t) or [],dtype=int))
    o=np.argsort(d['ids']);return {k:v[o] for k,v in d.items()}
def mutate(a):
    g=a.hdaModule().biomemap_raster.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='bm_order':
        good=g['biomemap_raster'];g['biomemap_raster']=lambda stamps,row,bounds,res:good(np.asarray(stamps).reshape(-1,8)[::-1],row,bounds,res)           # the stamps are applied in the wrong order
    elif MUTATE=='bm_erase':
        good=g['biomemap_combine'];g['biomemap_combine']=lambda w,v,mode:good(w,np.clip(v,0.0,1.0),mode)                                                    # the erase does nothing
    elif MUTATE=='bm_only':
        good=g['biomemap_combine'];g['biomemap_combine']=lambda w,v,mode:good(w,v,1 if mode==2 else mode)                                                   # Only Where Painted acts as Add
    elif MUTATE=='bm_row':
        good=g['biomemap_raster'];g['biomemap_raster']=lambda stamps,row,bounds,res:good(np.where(np.arange(len(np.asarray(stamps).reshape(-1,8)))[:,None]>=0,np.asarray(stamps).reshape(-1,8)*np.array([0,1,1,1,1,1,1,1])+np.array([row,0,0,0,0,0,0,0]),0),row,bounds,res)   # every row sees all the paint
    elif MUTATE:raise SystemExit('unknown mutation '+MUTATE)
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()
def module():
    st,sc=new_scene('mod');a=biome_node(st,sc,[dict(density=10.0)]);return a,a.hdaModule()
def stamp(row,sign,x,z,r,strength=1.0,fall=3,y=0.0):return [row,sign,x,y,z,r,strength,fall]
def paint_text(*stamps):
    """The biome_map_data text of some stamps, written independently of the module (so the format is tested too)."""
    return json.dumps({'v':1,'stamps':[[int(x[0]),int(x[1]),x[2],x[3],x[4],x[5],x[6],int(x[7])] for x in stamps]})

def maths():
    a,m=module();s=np.array([stamp(1,1,0,0,2),stamp(2,-1,1,1,3,0.5,2)]);t=m.biomemap_encode(s);d=m.biomemap_decode(t)
    assert d.shape==(2,8) and np.allclose(d,s) and m.biomemap_decode('').shape==(0,8) and m.biomemap_encode(np.zeros((0,8)))=='' and json.loads(t)['v']==1
    for bad in ('nope','{"stamps":[[1,2,3]]}','{"x":1}'):
        try:m.biomemap_decode(bad);assert False,bad
        except ValueError as e:assert 'cannot be read' in str(e)
    arr,added=m.biomemap_add(np.zeros((0,8)),1,1,(0,0,0),2.0,1.0,1);assert added and len(arr)==1
    arr2,added=m.biomemap_add(arr,1,1,(0.1,0,0.1),2.0,1.0,1);assert not added and len(arr2)==1                                                          # too close to the last stamp: skipped
    assert m.biomemap_add(arr,1,1,(0.6,0,0),2.0,1.0,1)[1] and m.biomemap_add(arr,2,1,(0.1,0,0),2.0,1.0,1)[1] and m.biomemap_add(arr,1,-1,(0.1,0,0),2.0,1.0,1)[1] and m.biomemap_add(arr,1,1,(0.1,0,0),3.0,1.0,1)[1]
    assert len(m.biomemap_add(np.zeros((m.BIOMEMAP_MAX,8)),1,1,(5,0,5),1.0,1.0,1)[0])==m.BIOMEMAP_MAX                                                  # the number of stamps is limited
    P=np.array([[-5,0,-5],[5,0,5],[0,3,0]],dtype=float);b=m.biomemap_bounds(P);assert b[0]<-5 and b[1]<-5 and b[2]>5 and b[3]>5
    bounds=(-10.0,-10.0,10.0,10.0);res=81;cell=20.0/80
    stamps=np.array([stamp(1,1,0,0,4,1.0,3),stamp(1,1,3,0,4,0.5,3),stamp(2,1,-5,-5,3,1.0,3)]);g=m.biomemap_raster(stamps,1,bounds,res)
    xs=np.linspace(-10,10,res);X,Z=np.meshgrid(xs,xs);expect=np.zeros_like(X)
    for s_ in stamps[:2]:expect=np.maximum(expect,np.where(np.hypot(X-s_[2],Z-s_[4])<=s_[5],1.0,0.0)*s_[6])                                                  # a hard brush, brute force
    assert np.allclose(g,expect) and g.max()==1.0 and g.min()==0.0
    assert m.biomemap_raster(stamps,2,bounds,res)[np.hypot(X+5,Z+5)<=3].min()==1.0 and m.biomemap_raster(stamps,3,bounds,res).max()==0.0                           # every row has its own map
    e=np.vstack([stamps[:1],[stamp(1,-1,0,0,2,1.0,3)]]);ge=m.biomemap_raster(e,1,bounds,res)
    assert (ge[np.hypot(X,Z)<=2]==-1.0).all() and (ge[(np.hypot(X,Z)>2.2)&(np.hypot(X,Z)<=4)]==1.0).all()                                              # erase after paint: a hole of -1
    pe=np.vstack([[stamp(1,-1,0,0,2,1.0,3)],[stamp(1,1,0,0,4,1.0,3)]]);gp=m.biomemap_raster(pe,1,bounds,res);assert (gp[np.hypot(X,Z)<=4]==1.0).all()          # paint after erase: painted again
    ss=m.biomemap_raster(np.array([stamp(1,1,0,0,5,0.4,3)]),1,bounds,res);assert abs(ss.max()-0.4)<1e-12
    for fall in (0,1,2):
        f=m.biomemap_raster(np.array([stamp(1,1,0,0,5,1.0,fall)]),1,bounds,res);r=np.hypot(X,Z);assert abs(f[40,40]-1.0)<1e-12 and f[r>5.0001].max()==0.0 and (np.diff(f[40,40:70])<=1e-12).all() and 0<f[40,52]<1   # fading
    sm=m.biomemap_sample(g,bounds,np.array([[xs[40],xs[40]],[xs[10],xs[10]],[0.0,0.0]]));assert np.allclose(sm,[g[40,40],g[10,10],g[40,40]])                         # exact at the cells
    half=m.biomemap_sample(g,bounds,np.array([[xs[40]+cell/2,xs[40]]]));assert abs(half[0]-0.5*(g[40,40]+g[40,41]))<1e-12                                          # bilinear between them
    assert np.allclose(m.biomemap_sample(g,bounds,np.array([[-99.0,-99.0],[99.0,99.0]])),[g[0,0],g[-1,-1]])                                                         # outside: the border value
    w=np.array([0.0,0.3,1.0,0.5]);v=np.array([1.0,0.5,-0.5,-1.0])
    assert np.allclose(m.biomemap_combine(w,v,1),[1.0,1-(0.7*0.5),0.5,0.0]) and np.allclose(m.biomemap_combine(w,v,2),[0.0,0.15,0.0,0.0]) and np.allclose(m.biomemap_combine(w,v,0),w)
    cache=m._BIOMEMAP_CACHE;cache.clear();m.biomemap_values(stamps,1,bounds,res,np.zeros((3,2)));m.biomemap_values(stamps,1,bounds,res,np.ones((3,2)));assert len(cache)==1                    # the raster is kept

def painted_node():
    st,sc=new_scene('painted');R=6.0;rows=lambda **kw:[dict(name='B',density=60.0,mix='1',scale=(1.0,1.0),**kw)]
    far=dict(h=(100.0,200.0))                                                                                               # conditions that can never hold: nothing grows without paint
    base=out(biome_node(st,sc,rows(**far),name='None'));assert len(base['ids'])==0
    center=(12.0,12.0);paint=paint_text(stamp(1,1,center[0],center[1],R,1.0,3))
    off=out(biome_node(st,sc,rows(map=0,**far),name='Off',biome_map_data=paint));assert len(off['ids'])==0                                                    # Off: the paint is ignored
    add=biome_node(st,sc,rows(map=1,**far),name='Add',biome_map_data=paint);oa=out(add);cell=40.8/255
    assert len(oa['ids'])>10 and (np.hypot(oa['pos'][:,0]-center[0],oa['pos'][:,2]-center[1])<=R+2*cell).all()                                                  # grows inside the painted circle only
    free=biome_node(st,sc,rows(),name='Free',biome_map_data=paint,biome_map_res=256);free.parm('biome_map1').set(0);allp=out(free);inside=np.hypot(allp['pos'][:,0]-center[0],allp['pos'][:,2]-center[1])<R-2*cell
    assert inside.sum()>10 and set(allp['ids'][inside].tolist())<=set(oa['ids'].tolist())                                                                         # every candidate well inside grows (weight 1)
    only=biome_node(st,sc,rows(map=2),name='Only',biome_map_data=paint);oo=out(only);assert (np.hypot(oo['pos'][:,0]-center[0],oo['pos'][:,2]-center[1])<=R+2*cell).all()
    assert set(oo['ids'].tolist())<=set(allp['ids'].tolist()) and set(allp['ids'][inside].tolist())<=set(oo['ids'].tolist())                                           # only where painted: the conditions (open here) AND the paint
    er=paint_text(stamp(1,-1,12.0,12.0,R,1.0,3));ee=out(biome_node(st,sc,rows(map=1),name='Erase',biome_map_data=er));assert set(ee['ids'].tolist())<=set(allp['ids'].tolist())
    gone=np.hypot(allp['pos'][:,0]-12.0,allp['pos'][:,2]-12.0)<R-2*cell;assert gone.sum()>10 and not set(allp['ids'][gone].tolist())&set(ee['ids'].tolist())                  # erased: nothing grows there
    assert set(allp['ids'][np.hypot(allp['pos'][:,0]-12.0,allp['pos'][:,2]-12.0)>R+2*cell].tolist())<=set(ee['ids'].tolist())                                          # ... and the rest of the biome is untouched
    half=out(biome_node(st,sc,rows(map=2),name='Half',biome_map_data=paint_text(stamp(1,1,12.0,12.0,R,0.5,3))));sh=set(half['ids'].tolist());si=set(allp['ids'][inside].tolist())
    assert sh<=set(oo['ids'].tolist()) and 0.3<len(sh&si)/len(si)<0.7                                                                                            # strength 0.5: about half of the points
    other=out(biome_node(st,sc,[dict(name='A',density=60.0,mix='1',map=1,**far),dict(name='B',density=60.0,mix='2')],name='Rows',biome_map_data=paint));assert (other['ids']//STRIDE==1).sum()>50 and (other['ids']//STRIDE==0).sum()>10   # a row paints for itself
    ref=out(biome_node(st,sc,[dict(name='A',density=60.0,mix='1',map=0,**far),dict(name='B',density=60.0,mix='2')],name='RowsRef'));assert np.array_equal(other['ids'][other['ids']//STRIDE==1],ref['ids'][ref['ids']//STRIDE==1])   # the paint of row 1 never moves row 2
    two=out(biome_node(st,sc,[dict(name='A',density=60.0,mix='1',map=1,**far),dict(name='B',density=60.0,mix='2',map=1,**far)],name='Two',biome_map_data=paint_text(stamp(1,1,12.0,12.0,R,1.0,3),stamp(2,1,-12.0,-12.0,R,1.0,3))))
    assert (two['ids']//STRIDE==0).sum()>10 and (two['ids']//STRIDE==1).sum()>10 and (two['pos'][two['ids']//STRIDE==0][:,0]>0).all() and (two['pos'][two['ids']//STRIDE==1][:,0]<0).all()    # two rows, two paintings
    res64=out(biome_node(st,sc,rows(map=1,**far),name='R64',biome_map_data=paint,biome_map_res=64));assert 0.8<len(res64['ids'])/len(oa['ids'])<1.25                  # the resolution only sharpens the border
    layered=out(biome_node(st,sc,[dict(name='Top',density=60.0,mix='1',layer=1,clear=1.0,map=1,**far),dict(name='Low',density=200.0,mix='2',layer=2)],name='Lay',biome_map_data=paint));lo=layered['ids']//STRIDE==1
    assert lo.sum()>50 and not near(layered['pos'][layered['ids']//STRIDE==0],layered['pos'][lo],0.8).any()                                                   # painted biomes take part in the layers: no lower point within the smallest clearance (0.8 = 1.0 x the smallest scale)
def near(A,B,r):
    d=np.linalg.norm(B[:,None,:]-A[None,:,:],axis=2);return (d<r).any(axis=1)

def persistence_and_info():
    st,sc=new_scene('persist');rows=[dict(name='Meadow',density=30.0,mix='1',map=1,h=(100.0,200.0)),dict(name='Wood',density=30.0,mix='2',map=2)]
    a=biome_node(st,sc,rows,name='Info');m=a.hdaModule();assert 'Nothing painted' in m.biomemap_info(a)
    stamps=np.array([stamp(1,1,0,0,2),stamp(1,-1,1,1,2),stamp(2,1,3,3,2),stamp(2,1,4,3,2)]);m.biomemap_apply(a,stamps)
    info=m.biomemap_info(a);assert 'Row 1 Meadow: map Add And Erase, 1 paint and 1 erase' in info and 'Row 2 Wood: map Only Where Painted, 2 paint and 0 erase' in info
    a.parm('biome_map2').set(0);assert 'paint ignored: set Map' in m.biomemap_info(a);a.parm('biome_map2').set(2)
    path=str(WORK/'persist.hip');hou.hipFile.save(path);hou.hipFile.load(path,suppress_save_prompt=True);b=hou.node('/stage/Info');assert np.allclose(b.hdaModule().biomemap_data(b),stamps)                  # saved with the scene
    assert b.hdaModule().biomemap_clear(b,1)==2 and len(b.hdaModule().biomemap_data(b))==2 and set(b.hdaModule().biomemap_data(b)[:,0])=={2.0}                                  # one row's paint
    assert b.hdaModule().biomemap_clear(b)==2 and len(b.hdaModule().biomemap_data(b))==0 and b.evalParm('biome_map_data')==''
    b.parm('biome_map_data').set('garbage');assert 'cannot be read' in b.hdaModule().biomemap_info(b)
    try:
        b.hdaModule().biomemap_data(b);assert False
    except hou.NodeError as e:assert 'cannot be read' in str(e)
    b.parm('mode').set(0);assert b.hdaModule().biomemap_info(b)=='Switch Distribution Mode to Biome.'

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
    """A viewport that looks straight down from y = 50: pixel (x, y) is the ray from (x/10, 50, y/10) along -Y."""
    def __init__(self,device,reason):self.d,self.r=device,reason
    def device(self):return self.d
    def reason(self):return self.r
    def ray(self):x,y=self.d.mouseX(),self.d.mouseY();return hou.Vector3((x/10.0,50.0,y/10.0)),hou.Vector3((0,-1,0))
def viewer_tool():
    st,sc=new_scene('tool');rows=[dict(name='Meadow',density=30.0,mix='1',map=1,h=(100.0,200.0)),dict(name='Wood',density=30.0,mix='2',map=2)]
    a=biome_node(st,sc,rows,name='Tool',biome_brush_radius=1.0,biome_brush_falloff=3);m=a.hdaModule();a.parm('mode').set(0)
    ns=types.SimpleNamespace(**{k:getattr(hou,k) for k in ('Vector4','Vector3','Geometry','drawableGeometryType','uiEventReason','promptMessageType','Error','lopNodeTypeCategory','ViewerStateTemplate')});ns.GeometryDrawable=StubDrawable
    glob={'hou':ns,'np':np,'__name__':'arraytron_biomemap_state_test'};exec(compile((ROOT/'src/arraytron_paint_state.py').read_text().replace('import hou'+chr(10),'',1),'arraytron_paint_state.py','exec'),glob);glob['STRICT']=True
    viewer=StubViewer();state=glob['PaintState']('arraytron_biomemap_test',viewer);R=hou.uiEventReason
    state.onEnter({'node':a});assert not state.biomepaint and viewer.prompt is None                                                                                   # selecting the node does nothing by itself
    assert state.onMouseEvent({'ui_event':Event(Device(150,150,left=True),R.Start)}) is False and a.evalParm('biome_map_data')==''
    a.setUserData('arraytron_biomepaint','1');state.onMouseEvent({'ui_event':Event(Device(150,150),R.Located)});assert state.biomepaint and a.evalParm('mode')==0                                                                                                   # the tool never changes the Distribution Mode (the button does)
    assert 'Arraytron Biome Map' in viewer.prompt and 'row 1 Meadow' in viewer.prompt and 'Add And Erase' in viewer.prompt and 'radius 1' in viewer.prompt and 'LMB paint' in viewer.prompt and not a.userData('arraytron_biomepaint')
    assert state.bhit is not None and abs(state.bhit[0][0]-15.0)<1e-9 and abs(state.bhit[0][2]-15.0)<1e-9 and state.brush.shown                                              # the brush follows the terrain
    assert state.onMouseEvent({'ui_event':Event(Device(150,150,left=True),R.Start)}) is True and state.bpainting and len(state.bdata)==1 and state.bdirty
    assert a.evalParm('biome_map_data')==''                                                                                                                          # nothing written while dragging
    state.onMouseEvent({'ui_event':Event(Device(160,150,left=True),R.Active)});state.onMouseEvent({'ui_event':Event(Device(170,150,left=True),R.Active)});assert len(state.bdata)==3
    state.onMouseEvent({'ui_event':Event(Device(170,150,left=False),R.Changed)});saved=m.biomemap_data(a);assert len(saved)==3 and not state.bpainting and not state.bdirty                      # committed once, at the end of the stroke
    assert (saved[:,0]==1).all() and (saved[:,1]==1).all() and np.allclose(saved[:,2],[15,16,17]) and np.allclose(saved[:,4],15) and np.allclose(saved[:,5],1.0)
    state.onKeyEvent({'ui_event':Event(Device(0,0,key='2'),R.Changed)});assert a.evalParm('biome_brush_row')==2 and 'row 2 Wood' in viewer.prompt and 'Only Where Painted' in viewer.prompt
    state.onKeyEvent({'ui_event':Event(Device(0,0,key='9'),R.Changed)});assert a.evalParm('biome_brush_row')==2                                                           # not past the last row
    state.onMouseEvent({'ui_event':Event(Device(-150,-150,left=True,ctrl=True),R.Start)});state.onMouseEvent({'ui_event':Event(Device(-150,-150,left=True,ctrl=True),R.Changed)})
    two=m.biomemap_data(a);assert len(two)==4 and two[3,0]==2 and two[3,1]==-1 and np.allclose(two[3,[2,4]],[-15,-15])                                                  # Ctrl: erase, in the row picked with the key
    state.onMouseEvent({'ui_event':Event(Device(1500,1500,left=True),R.Picked)});assert len(m.biomemap_data(a))==4                                                       # a click off the terrain (a miss) paints nothing
    state.onMouseEvent({'ui_event':Event(Device(100,-100,left=True),R.Picked)});assert len(m.biomemap_data(a))==5                                                         # a plain click: one dab, committed
    r0=a.evalParm('biome_brush_radius');assert state.onKeyEvent({'ui_event':Event(Device(0,0,key=']'),R.Changed)}) and a.evalParm('biome_brush_radius')>r0
    s0=a.evalParm('biome_brush_strength');state.onKeyEvent({'ui_event':Event(Device(0,0,key='-'),R.Changed)});assert abs(a.evalParm('biome_brush_strength')-(s0-0.05))<1e-9 and 'strength 0.95' in viewer.prompt
    f0=a.evalParm('biome_brush_falloff');state.onKeyEvent({'ui_event':Event(Device(0,0,key='f'),R.Changed)});assert a.evalParm('biome_brush_falloff')==(f0+1)%4
    r1=a.evalParm('biome_brush_radius');state.onMouseWheelEvent({'ui_event':Event(Device(0,0,wheel=1,shift=True),R.Changed)});assert a.evalParm('biome_brush_radius')>r1
    s1=a.evalParm('biome_brush_strength');state.onMouseWheelEvent({'ui_event':Event(Device(0,0,wheel=-1,ctrl=True),R.Changed)});assert a.evalParm('biome_brush_strength')<s1
    assert state.onKeyEvent({'ui_event':Event(Device(0,0,key='x'),R.Changed)}) is False and state.onMouseWheelEvent({'ui_event':Event(Device(0,0,wheel=1),R.Changed)}) is False
    state.onKeyEvent({'ui_event':Event(Device(0,0,key='h'),R.Changed)});assert 'LMB paint' not in viewer.prompt
    state.onExit({});assert viewer.prompt is None and not state.biomepaint
    state.onEnter({'node':a});assert not state.biomepaint                                                                                                              # the flag was used up: a new selection does nothing
    glob['PaintState']('x',StubViewer()).onEnter({'node':a})

def contract():
    st,sc=new_scene('contract');a=biome_node(st,sc,[dict(density=5.0)],name='C');g=a.parmTemplateGroup()
    for n in ('biome_map#','biome_map_data','biome_map_res','biome_brush_row','biome_brush_radius','biome_brush_strength','biome_brush_falloff','biome_paint_start','biome_map_clear_row','biome_map_clear','biome_map_info'):assert g.find(n) is not None,n
    assert g.find('biome_map#').defaultValue()==0 and g.find('biome_map#').menuLabels()==('Off','Add And Erase','Only Where Painted') and g.find('biome_map_res').defaultValue()==(256,) and g.find('biome_brush_strength').defaultValue()==(1.0,) and g.find('biome_brush_falloff').defaultValue()==1
    assert a.evalParm('biome_map1')==0 and a.evalParm('biome_map_data')=='' and a.parm('biome_map_data').parmTemplate().isHidden()
    assert g.find('biome_paint_start').scriptCallback().endswith("biomemap_start(kwargs['node'])")
    text=a.type().definition().sections()['PythonModule'].contents();assert '$' not in text.split('# ---- Painted biome map')[1].split('# ----')[0]
    assert 'self.biomepaint' in a.type().definition().sections()['ViewerStateModule'].contents()
    for n in ('biomemap_decode','biomemap_encode','biomemap_add','biomemap_raster','biomemap_sample','biomemap_combine','biomemap_apply','biomemap_clear','biomemap_start','biomemap_info','biomemap_surface'):assert hasattr(a.hdaModule(),n),n
    st2=hou.node('/stage');a.parm('mode').set(10)
    try:a.hdaModule().biomemap_start(a);assert False
    except hou.NodeError as e:assert 'Houdini interface' in str(e)                                                                                                        # no interface in hython

def unchanged():
    st,sc=new_scene('same');rows=[dict(name='F',density=50.0,mix='1',s=(0,60)),dict(name='G',density=90.0,mix='2',scale=(0.5,0.9))]
    pa=out(biome_node(st,sc,rows,name='N',biome_map_data=paint_text(stamp(1,1,0,0,5))));ob=st.createNode(OLD_TYPE,'O');ob.setInput(0,sc);ob.parm('protos').set(2)
    for k,pr in enumerate(('Tree','Bush'),1):ob.parm('proto_prim%d'%k).set('/World/Props/'+pr)
    ob.parm('mode').set(10);ob.parm('biomes').set(2);ob.parm('biome_seed').set(3);ob.parm('biome_normal').set(0);ob.parm('biome_moist_mode').set(0);ob.parm('biome_moist_const').set(0.5)
    for i,r in enumerate(rows,1):
        ob.parm('biome_name%d'%i).set(r['name']);ob.parm('biome_density%d'%i).set(r['density']);ob.parm('biome_mix%d'%i).set(r['mix'])
        if 's' in r:ob.parmTuple('biome_srange%d'%i).set(r['s'])
        if 'scale' in r:ob.parmTuple('biome_scale%d'%i).set(r['scale'])
    pb=out(ob);assert len(pa['ids'])>50 and np.array_equal(pa['ids'],pb['ids']) and np.array_equal(pa['pos'],pb['pos'])                                           # Map Off: the previous release exactly, paint or not

def main():
    for name,func in (('Maths: the stamps (text, spacing, limit), the map against brute force, paint and erase in order, falloffs, sampling, combining, the cache',maths),
                      ('On a node: Off ignores the paint, Add grows only where painted, Erase keeps it out, Only Where Painted, strength, rows apart, layers',painted_node),
                      ('The text saved with the scene, the read-out, clearing a row and everything, a broken text',persistence_and_info),
                      ('The viewport tool through a stand-in viewport: idle until asked, brush, stroke committed once, Ctrl erase, row keys, radius, strength, falloff, wheel, help',viewer_tool),
                      ('Contract: parameters, defaults, hidden data, module functions, no dollar signs, no interface',contract),
                      ('The previous release unchanged with Map Off',unchanged)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_biomemap_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
