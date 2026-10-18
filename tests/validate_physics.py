"""Physics Settle (v0.4.0) validation in real Houdini: hython tests/validate_physics.py [v0.4.0]
Everything is measured on the USD stage that Karma would render: the settled instance transforms are read back with
UsdGeom.PointInstancer.ComputeInstanceTransformsAtTime, the stone meshes are re-read from the prototype prims with pxr and re-hulled with
the pure-numpy quickhull, and pair penetration is measured with a separating-axis test. None of this reuses the module's own
position/orientation conversion, so a convention error (pivot, scale, quaternion order, proto transform) shows up as penetration.
Env ARRAYTRON_MUTATE=<name> deliberately breaks the Python module in memory; the suite must then FAIL."""
from pathlib import Path
import hou, json, math, os, shutil, sys, tempfile, time, itertools
import numpy as np
from pxr import Usd, UsdGeom, Gf, Vt, Sdf
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'src'))
import versions
import arraytron_physics as P                 # pure functions only (hull, SAT, stacking); Houdini parts run from the HDA module
import make_test_assets_v04 as assets
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name('v0.3.6')
WORK=Path(tempfile.mkdtemp(prefix='arraytron_phys_'))
HDA_PATH=versions.hda(VID)
CACHE=(WORK/'cache').as_posix()
checks=[];timings={}
STONE=(ROOT/'dist/test_assets/stone.usda').as_posix()

# ------------------------------------------------------------------ test assets
def write_stone_xform():
    """Prototype whose ROOT carries translate, rotate and scale, with an off-centre mesh: the proxy must follow all of it."""
    verts,faces=assets.stone_mesh(5)
    path=WORK/'stone_xform.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/StoneX');s.SetDefaultPrim(root.GetPrim())
    UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y);x=UsdGeom.Xformable(root)
    x.AddTranslateOp().Set(Gf.Vec3d(0.01,0.02,-0.01));x.AddRotateXYZOp().Set(Gf.Vec3f(10,35,5));x.AddScaleOp().Set(Gf.Vec3f(1.3,1.0,0.9))
    m=UsdGeom.Mesh.Define(s,'/StoneX/Shape');m.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*map(float,v)) for v in verts]))
    m.CreateFaceVertexCountsAttr(Vt.IntArray([3]*len(faces)));m.CreateFaceVertexIndicesAttr(Vt.IntArray([int(i) for i in faces.ravel()]))
    s.GetRootLayer().Save();return path.as_posix()
def write_box_proto():
    """A 6 x 3 x 4 cm box as a USD Cube prim (implicit shape) with a size-2 cube scaled by an op, origin at its centre."""
    path=WORK/'pebblebox.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/PebbleBox');s.SetDefaultPrim(root.GetPrim())
    UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y);c=UsdGeom.Cube.Define(s,'/PebbleBox/Body');c.CreateSizeAttr(2.0)
    UsdGeom.Xformable(c).AddScaleOp().Set(Gf.Vec3f(0.03,0.015,0.02));s.GetRootLayer().Save();return path.as_posix()
def write_collider(name,builder):
    path=WORK/(name+'.usda');s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/'+name);s.SetDefaultPrim(root.GetPrim())
    UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y);builder(s,'/'+name);s.GetRootLayer().Save();return path.as_posix()
def trough(s,root):
    """V-shaped trough: two 20 degree slopes meeting along z at x=0, 1 m square, plus walls at z=+-0.5. Returns nothing; planes are known to the test."""
    t=math.tan(math.radians(20));pts=[(-0.5,0.5*t,-0.5),(0,0,-0.5),(0,0,0.5),(-0.5,0.5*t,0.5),(0.5,0.5*t,-0.5),(0.5,0.5*t,0.5)]
    m=UsdGeom.Mesh.Define(s,root+'/Slopes');m.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*p) for p in pts]))
    m.CreateFaceVertexCountsAttr(Vt.IntArray([4,4]));m.CreateFaceVertexIndicesAttr(Vt.IntArray([0,1,2,3, 1,4,5,2]))
    w=[(-0.5,0.5*t,-0.5),(0.5,0.5*t,-0.5),(0.5,1.0,-0.5),(-0.5,1.0,-0.5),(-0.5,0.5*t,0.5),(0.5,0.5*t,0.5),(0.5,1.0,0.5),(-0.5,1.0,0.5)]
    # walls close the ends of the valley (they cut across the slopes' top edges so the stones cannot roll out along +-z)
    ends=[(-0.5,0,-0.5),(0.5,0,-0.5),(0.5,0.5,-0.5),(-0.5,0.5,-0.5),(-0.5,0,0.5),(0.5,0,0.5),(0.5,0.5,0.5),(-0.5,0.5,0.5)]
    e=UsdGeom.Mesh.Define(s,root+'/Walls');e.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*p) for p in ends]))
    e.CreateFaceVertexCountsAttr(Vt.IntArray([4,4]));e.CreateFaceVertexIndicesAttr(Vt.IntArray([0,1,2,3, 5,4,7,6]))
def slab(s,root):
    c=UsdGeom.Cube.Define(s,root+'/Slab');c.CreateSizeAttr(1.0);x=UsdGeom.Xformable(c)
    x.AddTranslateOp().Set(Gf.Vec3d(0,0.1,0));x.AddScaleOp().Set(Gf.Vec3f(1.4,0.2,1.4))        # top face at y = 0.2
TROUGH_N=[(0.0,1.0,0.0)]
STONEX=write_stone_xform();BOX=write_box_proto();TROUGH=write_collider('Trough',trough);SLAB=write_collider('SlabFloor',slab)

# ------------------------------------------------------------------ scene helpers
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True)
    for path in (HDA_PATH,versions.hda('v0.3.6')):hou.hda.installFile(str(path),force_use_assets=True)          # clearing the session unloads the libraries
    hou.hipFile.save(str(WORK/(name+'.hip')))
    return hou.node('/stage')
def ref(stage,name,prim,path,source=None):
    n=stage.createNode('reference',name)
    if source:n.setInput(0,source)
    n.parm('primpath').set(prim);n.parm('primpath1').set(prim);n.parm('filepath1').set(path);n.parm('filerefprim1').set('defaultPrim');return n
def arraytron(stage,source,prim='/World/Props/Stone',typ=None,name='Arraytron',**values):
    a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(1);a.parm('proto_prim1').set(prim)
    a.parm('mode').set(1);a.parm('area_sizex').set(0.4);a.parm('area_sizez').set(0.4);a.parm('area_count').set(60)
    a.parmTuple('rotation_random').set((180,180,180));a.parm('scale_random').set(0.2)
    if typ is None:
        a.parm('phys_cachedir').set(CACHE)
        if MUTATE and MUTATE not in NODE_MUTATIONS:mutate_module(a)
    return setv(a,**values)
def setv(a,**values):
    for key,value in values.items():a.parmTuple(key).set(value if isinstance(value,(tuple,list)) else (value,))
    return a
def stone_scene(name='stone',**values):
    st=new_scene(name);r=ref(st,'stone','/World/Props/Stone',STONE);return st,r,arraytron(st,r,**values)
def instances(a):
    """Instance data read back from the stage: world 4x4 matrices (with the prototype root transform), ids, protoindex."""
    s=a.stage();assert not a.errors(),a.errors()
    pi=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    mats=pi.ComputeInstanceTransformsAtTime(t,t,UsdGeom.PointInstancer.IncludeProtoXform)
    world=UsdGeom.Xformable(pi).ComputeLocalToWorldTransform(t)
    return dict(stage=s,pi=pi,mats=[np.array(m*world).reshape(4,4) for m in mats],ids=list(pi.GetIdsAttr().Get(t)),proto=list(pi.GetProtoIndicesAttr().Get(t)),
                positions=np.array(pi.GetPositionsAttr().Get(t)),orient=np.array([[q.GetImaginary()[0],q.GetImaginary()[1],q.GetImaginary()[2],q.GetReal()] for q in pi.GetOrientationsAttr().Get(t)]),
                scales=np.array(pi.GetScalesAttr().Get(t)))
def proto_local_points(stage,prim_path):
    """Mesh points of a prototype prim expressed in the prototype root's local frame, from pxr only (cube prims from their size and ops)."""
    root=stage.GetPrimAtPath(prim_path);xc=UsdGeom.XformCache();inv=xc.GetLocalToWorldTransform(root).GetInverse();out=[]
    for prim in Usd.PrimRange(root):
        if prim.IsA(UsdGeom.Mesh):pts=np.array(UsdGeom.Mesh(prim).GetPointsAttr().Get(),dtype=float).reshape(-1,3)
        elif prim.IsA(UsdGeom.Cube):h=0.5*UsdGeom.Cube(prim).GetSizeAttr().Get();pts=np.array([(x,y,z) for x in (-h,h) for y in (-h,h) for z in (-h,h)],dtype=float)
        else:continue
        m=np.array(xc.GetLocalToWorldTransform(prim)*inv).reshape(4,4);out.append(pts@m[:3,:3]+m[3,:3])
    return np.vstack(out)
def world_hulls(a):
    d=instances(a);targets=[t for t in d['pi'].GetPrototypesRel().GetTargets()]
    local=[proto_local_points(d['stage'],t.pathString) for t in targets];hulls=[P.quickhull(p) for p in local];out=[]
    for k,m in enumerate(d['mats']):
        verts,faces=hulls[d['proto'][k]];out.append((verts@m[:3,:3]+m[3,:3],faces))
    return out,d
def measure(hulls,ground=0.0,box=None):
    """worst pair penetration (SAT, <0), lowest vertex over ground, stones not connected to the ground through contacts."""
    cen=np.array([v.mean(axis=0) for v,_ in hulls]);rad=np.array([np.linalg.norm(v-v.mean(axis=0),axis=1).max() for v,_ in hulls])
    edges={}
    def e(i):
        if i not in edges:edges[i]=P.hull_edges(hulls[i][1])
        return edges[i]
    worst=0.0;pairs=[]
    for i,j in itertools.combinations(range(len(hulls)),2):
        if np.linalg.norm(cen[i]-cen[j])>rad[i]+rad[j]+0.01:continue
        sep=P.sat_separation(hulls[i][0],hulls[i][1],hulls[j][0],hulls[j][1],e(i),e(j));worst=min(worst,sep);pairs.append((i,j,sep))
    low=np.array([v[:,1].min()-ground for v,_ in hulls])
    return worst,low,pairs
def floating(low,pairs,tol):
    """Indices of stones with no chain of contacts (gap <= tol) down to the ground."""
    n=len(low);supported=set(np.nonzero(low<=tol)[0].tolist());adj={i:[] for i in range(n)}
    for i,j,sep in pairs:
        if sep<=tol:adj[i].append(j);adj[j].append(i)
    frontier=list(supported)
    while frontier:
        i=frontier.pop()
        for j in adj[i]:
            if j not in supported:supported.add(j);frontier.append(j)
    return sorted(set(range(n))-supported)
def phys_state(a):
    """State authored on the PointInstancer prim (customData arraytron:physics), read from the stage."""
    prim=a.stage().GetPrimAtPath(a.evalParm('outputpath'));d=prim.GetCustomDataByKey('arraytron:physics');return d['state'] if d else None
def bake(a):
    t=time.time();r=a.hdaModule().bake(a);r['wall']=time.time()-t
    try:a.cook(force=True)          # errors() reports the last cook: recook so an old error is not reported (Houdini 20.5 / 21 do not do it implicitly)
    except hou.OperationFailed:pass
    assert not a.errors(),a.errors();return r
def check(name,func):
    t=time.time();func();checks.append(name);timings[name]=round(time.time()-t,1);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()
MUTATE=os.environ.get('ARRAYTRON_MUTATE')

# ------------------------------------------------------------------ mutation self-test
# Module mutations patch the PythonModule's globals in memory. Node mutations edit a throw-away copy of the HDA, so the real file is never touched.
NODE_MUTATIONS={'world','friction','gravity','groundheight','nocolliders'}
def setup_mutation():
    global HDA_PATH
    if MUTATE in NODE_MUTATIONS:
        tmp=WORK/'mutated.hda';shutil.copy2(HDA_PATH,tmp);HDA_PATH=tmp
        st,r,a=stone_scene('mutate');a.allowEditingOfContents();inst=a.node('USD_COMPILER');solver=inst.node('PHYSICS_SOLVER')
        if MUTATE=='world':
            n=inst.node('PHYSICS_WORLD');code=n.parm('snippet').eval();assert 'qrotate(q, @P - pivot)' in code;n.parm('snippet').set(code.replace('qrotate(q, @P - pivot)','(@P - pivot)'))
        elif MUTATE=='friction':solver.parm('friction').deleteAllKeyframes();solver.parm('friction').set(1.0)
        elif MUTATE=='gravity':solver.parm('gravityy').deleteAllKeyframes();solver.parm('gravityy').set(-9.80665)
        elif MUTATE=='groundheight':solver.parm('ground_posy').deleteAllKeyframes();solver.parm('ground_posy').set(0.0)
        elif MUTATE=='nocolliders':solver.parm('usecollisions').set(0)
        a.type().definition().updateFromNode(a);return
    return

def mutate_module(a):
    """Patch the PythonModule of this HDA instance in memory (once per loaded module: a new scene reloads the library)."""
    g=a.hdaModule().bake.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='quat':
        good=g['quat_from_matrix'];g['quat_from_matrix']=lambda m:good(np.asarray(m).T)                   # inverse rotation written to the cache
    elif MUTATE=='noscale':
        good=g['read_points'];g['read_points']=lambda geo:(lambda d:None if d is None else dict(d,scale=np.ones_like(d['scale'])))(good(geo))   # proxies built at scale 1
    elif MUTATE=='protoframe':
        good=g['proto_points'];g['proto_points']=lambda stage,path:good(stage,path)-np.array([0.0,0.02,0.0])       # proxy shifted against the real mesh (pivot ignored)
    elif MUTATE=='nostack':
        g['stack_spawn']=lambda centers,radii,order,drop,gap=1.05:np.asarray(centers)+np.array([0.0,drop,0.0])
    elif MUTATE=='key':
        g['stable_hash']=lambda *arrays:'constant'                                                       # fingerprint ignores everything
    elif MUTATE=='hull':
        g['quickhull']=lambda points,max_vertices=0,eps=None:P.quickhull(np.asarray(points)*0.5,max_vertices)    # proxies half size
    else:raise SystemExit('unknown mutation '+MUTATE)

# ------------------------------------------------------------------ groups
def ui_contract():
    st,r,a=stone_scene('ui')
    names=['phys_on','phys_status','phys_spawn','phys_bake','phys_clear','phys_drop','phys_stack','phys_seed','phys_gravity','phys_density','phys_friction','phys_bounce','phys_drag','phys_duration','phys_quality','phys_ground','phys_ground_height','phys_colliders','phys_strict','phys_cachedir','phys_cache_rev']
    for n in names:assert a.parm(n) is not None,n
    assert a.evalParm('phys_friction')==0.9 and a.evalParm('phys_on')==0 and a.evalParm('phys_stack')==1 and a.evalParm('phys_quality')==1 and a.evalParm('phys_ground')==1
    assert abs(a.evalParm('phys_gravity')-9.80665)<1e-9 and a.evalParm('phys_drop')==0.3 and a.evalParm('phys_duration')==10.0 and a.evalParm('phys_density')==2600 and a.evalParm('phys_drag')==5
    assert a.parm('phys_cache_rev').parmTemplate().isHidden()
    g=a.parmTemplateGroup()
    for n in names:
        cond=g.find(n).conditionals().get(hou.parmCondType.DisableWhen) if g.find(n).conditionals() else None
        if n in ('phys_on','phys_cache_rev'):assert not cond,n
        elif n in ('phys_status','phys_spawn'):assert cond=='{ mode >= 0 }',n                                   # read only, always
        else:assert cond=='{ phys_on == 0 }',(n,cond)                                          # greyed out while Physics Settle is off
    assert 'off' in a.evalParm('phys_status').lower()
    assert a.evalParm('phys_spawn').startswith('60 stones spawn from the Area 0.4 x 0.4'),a.evalParm('phys_spawn')
    a.parm('mode').set(3);a.parm('circle_count').set(12);assert a.evalParm('phys_spawn').startswith('12 stones spawn from the Circle'),a.evalParm('phys_spawn')
    a.parm('mode').set(1)
    a.parm('phys_on').set(1)
    assert 'Spawn heights' in a.evalParm('phys_spawn'),a.evalParm('phys_spawn')
    assert a.parm('phys_duration').parmTemplate().label()=='Maximum Sim Time (s)' and a.evalParm('phys_strict')==0
    for n in ('phys_gravity','phys_density','phys_friction','phys_bounce','phys_drag','phys_drop','phys_duration','phys_quality','phys_ground','phys_stack','phys_colliders','phys_cachedir','phys_bake'):
        assert a.parm(n).parmTemplate().help().strip(),'no help on '+n
    menu=a.parm('phys_quality').parmTemplate();assert menu.menuLabels()==('Draft','Standard','High')
    folder=[t for t in a.parmTemplateGroup().entries() if t.name() in ('physics','tab_source_4')][0];assert folder.label() in ('Physics Settle','Settle','Physics')
    assert a.type().definition().sections()['ArraytronVersion'].contents().startswith(VID)
    m=a.hdaModule();assert all(hasattr(m,n) for n in ('bake','clear_cache','sop_apply','sop_spawn','sop_proxies','sop_colliders','physics_status','quickhull'))

def off_matches_previous():
    """Physics Settle off must leave every output array bit-for-bit equal to the real v0.3.6 HDA."""
    st=new_scene('off');r=ref(st,'stone','/World/Props/Stone',STONE);b=ref(st,'box','/World/Props/Box',BOX,r)
    new=arraytron(st,b,name='new');old=arraytron(st,b,typ=OLD_TYPE,name='old')
    def snap(n):
        s=n.stage();assert not n.errors(),n.errors();pi=UsdGeom.PointInstancer(s.GetPrimAtPath('/World/Arraytron'));t=hou.frame()
        return {k:list(getattr(pi,'Get'+k+'Attr')().Get(t)) for k in ('Positions','Orientations','Scales','Ids','ProtoIndices')}
    cases=[dict(mode=0,line_count=40,position_random=(.1,.1,.1),random_seed=5),dict(mode=1,area_count=120,bound_t=(1,2,3),bound_r=(10,20,30),bound_s=(1,2,.5),bound_p=(.1,.2,.3)),
           dict(mode=2,grid_count=(3,3,3),scale_random_mode=1,scale_min=.7,scale_max=1.4),dict(mode=3,circle_facing=1,circle_count=20,rotation_random_mode=1,yaw_random=90),
           dict(mode=1,area_count=50,bound_scale_instances=1,bound_s=(2,1,1),protos=2,proto_prim2='/World/Props/Box',proto_mode=1,proto_weight1=2)]
    for n in (new,old):n.parm('protos').set(2);n.parm('proto_prim2').set('/World/Props/Box')
    for k,values in enumerate(cases):
        for n in (new,old):
            for p in n.parms():
                if p.parmTemplate().type() not in (hou.parmTemplateType.Folder,hou.parmTemplateType.FolderSet) and not p.isMultiParmInstance() and not p.name().startswith('phys_') and p.name() not in ('protos',):p.revertToDefaults()
            n.parm('protos').set(2);n.parm('proto_prim1').set('/World/Props/Stone');n.parm('proto_prim2').set('/World/Props/Box');setv(n,**values)
        assert snap(new)==snap(old),('case',k,values)
    # and the physics nodes must not cook (or fail) while it is off: no warnings, no errors, display chain untouched
    assert not new.warnings() and not new.errors()

def settle_basic():
    st,r,a=stone_scene('basic',phys_on=1,area_count=160,area_sizex=0.3,area_sizez=0.3)
    d0=instances(a);assert len(d0['ids'])==160;assert phys_state(a)=='missing',phys_state(a)
    spawn_hulls,_=world_hulls(a);spawn_worst,spawn_low,_=measure(spawn_hulls)
    assert spawn_worst>=-1e-6,'spawn must not start interpenetrating (got %.5f)'%spawn_worst
    assert spawn_low.min()>=0.3-1e-6-0.0,'lowest stone must start at least Drop Height above the plane (%.4f)'%spawn_low.min()
    res=bake(a);assert res['settled'],res
    hulls,d=world_hulls(a);worst,low,pairs=measure(hulls);dmin=res['plan']['dmin'];margin=res['plan']['margin']
    assert worst>=-0.05*dmin,('pair penetration',worst,dmin);assert low.min()>=-0.05*dmin,('ground penetration',low.min())
    assert not floating(low,pairs,0.12*dmin),'floating stones: %s'%floating(low,pairs,0.12*dmin)
    assert 'came to rest' in a.hdaModule().physics_status(a) and phys_state(a)=='settled',(a.hdaModule().physics_status(a),phys_state(a))
    # at least some stones really rest on others (it is a pile, not a single layer) and every instance really moved from its spawn state
    assert (low>0.5*dmin).sum()>=5,'expected a pile: stones resting on other stones (%d)'%(low>0.5*dmin).sum()
    moved=np.linalg.norm(d['positions']-d0['positions'],axis=1);assert (moved>0.05).sum()>0.9*len(moved)
    timings['basic_pen_mm']=round(-worst*1000,3);timings['basic_ground_mm']=round(-low.min()*1000,3);timings['basic_dmin_mm']=round(dmin*1000,2)
    return a
def bake_is_deterministic():
    runs=[]
    for k in range(2):
        st,r,a=stone_scene('det%d'%k,phys_on=1,area_count=40);res=bake(a);d=instances(a);runs.append((res['key'],d['positions'].tolist(),d['orient'].tolist(),res['frames']))
    assert runs[0]==runs[1],'two bakes of the same scene differ'
def prototype_frames():
    """Root transform, off-centre pivot and non-uniform scale: the proxy must match the mesh the instancer actually draws."""
    st=new_scene('frames');r=ref(st,'stonex','/World/Props/StoneX',STONEX)
    a=arraytron(st,r,prim='/World/Props/StoneX',phys_on=1,area_count=50,scale_nonuniform=(.25,.25,.25))
    res=bake(a);hulls,d=world_hulls(a);worst,low,pairs=measure(hulls);dmin=res['plan']['dmin']
    assert worst>=-0.05*dmin,('penetration',worst,dmin);assert low.min()>=-0.05*dmin,low.min();assert not floating(low,pairs,0.12*dmin)
    assert max(abs(s[0]-s[1])+abs(s[1]-s[2]) for s in d['scales'])>0.05,'expected non-uniform scales'
    timings['frames_pen_mm']=round(-worst*1000,3)
def multi_prototype():
    st=new_scene('multi');r=ref(st,'stone','/World/Props/Stone',STONE);b=ref(st,'box','/World/Props/Box',BOX,r)
    a=arraytron(st,b,phys_on=1,area_count=60,protos=2,proto_prim2='/World/Props/Box',proto_mode=3)               # Cycle: even ids stone, odd ids box
    a.parmTuple('proto_scale2').set((1.2,))
    before=instances(a);res=bake(a);hulls,d=world_hulls(a)
    assert d['proto']==before['proto'] and d['ids']==before['ids'] and np.allclose(d['scales'],before['scales']),'ids, prototype assignment and scales must pass through the physics unchanged'
    assert sorted(set(d['proto']))==[0,1]
    worst,low,pairs=measure(hulls);dmin=res['plan']['dmin']
    assert worst>=-0.05*dmin,('penetration',worst);assert low.min()>=-0.05*dmin;assert not floating(low,pairs,0.12*dmin)
    timings['multi_pen_mm']=round(-worst*1000,3)
def per_row_scale_and_offset():
    st=new_scene('rows');r=ref(st,'stone','/World/Props/Stone',STONE)
    a=arraytron(st,r,phys_on=1,area_count=40);a.parmTuple('proto_scale1').set((1.6,));a.parmTuple('proto_rot1').set((20,40,60));a.parm('scale_random_mode').set(1);setv(a,scale_min=.6,scale_max=1.5)
    res=bake(a);hulls,d=world_hulls(a);worst,low,pairs=measure(hulls);dmin=res['plan']['dmin']
    assert worst>=-0.05*dmin and low.min()>=-0.05*dmin and not floating(low,pairs,0.12*dmin),(worst,low.min())
    assert max(s[0] for s in d['scales'])>1.6*1.2
def colliders():
    # (a) a Cube slab, no ground plane: the pile must rest on its top face at y = 0.2
    st=new_scene('slab');r=ref(st,'stone','/World/Props/Stone',STONE);sl=ref(st,'slab','/World/Floor',SLAB,r)
    a=arraytron(st,sl,phys_on=1,area_count=50,phys_ground=0,phys_colliders='/World/Floor');bake_res=bake(a)
    hulls,d=world_hulls(a);worst,low,pairs=measure(hulls,ground=0.2);dmin=bake_res['plan']['dmin']
    assert worst>=-0.05*dmin and low.min()>=-0.05*dmin,(worst,low.min());assert low.min()<0.2*dmin,'stones must reach the slab top, lowest %.4f above'%low.min()
    assert not floating(low,pairs,0.12*dmin)
    assert max(v[:,1].max() for v,_ in hulls)<0.6,'nothing may fall through the slab'
    # (b) a concave mesh trough with walls, ground off: every vertex must stay on the inner side of both slope planes
    st=new_scene('trough');r=ref(st,'stone','/World/Props/Stone',STONE);tr=ref(st,'trough','/World/Trough',TROUGH,r)
    a=arraytron(st,tr,phys_on=1,area_count=30,phys_ground=0,phys_colliders='/World/Trough/*',phys_drop=0.4,area_sizex=0.1,area_sizez=0.3)
    a.parm('bound_ty').set(0.1);res=bake(a);hulls,d=world_hulls(a);t=math.tan(math.radians(20));dmin=res['plan']['dmin']
    n1=np.array([t,1,0])/math.hypot(t,1);n2=np.array([-t,1,0])/math.hypot(t,1)                      # up-facing normals of the slopes (planes through the valley line x=0,y=0)
    depth=min(min((v@n1).min(),(v@n2).min()) for v,_ in hulls)
    assert depth>=-0.06*dmin,('stone below a slope plane',depth);assert max(abs(v[:,2]).max() for v,_ in hulls)<0.5+0.02,'stones must stay between the end walls'
    assert (np.array([v.mean(axis=0)[0] for v,_ in hulls])).std()<0.2
    assert phys_state(a)=='settled' and 'came to rest' in a.hdaModule().physics_status(a)
    timings['trough_depth_mm']=round(-depth*1000,3)
def bounds_world_space():
    """With Physics Settle on and the pile not yet simulated (drop 0, no stacking) the points must land exactly where the normal layout puts them."""
    st=new_scene('bounds');r=ref(st,'stone','/World/Props/Stone',STONE)
    off=arraytron(st,r,name='off');on=arraytron(st,r,name='on',phys_on=1,phys_drop=0,phys_stack=0);on.parm('outputpath').set('/World/Arraytron')
    for mode,extra in ((0,dict(line_count=15,line_length=3)),(1,dict(area_count=40)),(2,dict(grid_count=(3,2,3))),(3,dict(circle_count=9,circle_facing=1,circle_radius=1))):
        for t,rot,sc,pv in (((0,0,0),(0,0,0),(1,1,1),(0,0,0)),((1.5,-2,.5),(20,-35,50),(1.5,.6,2),(.3,-.2,.5)),((0,3,0),(0,90,0),(1,1,1),(0,0,0))):
            vals=dict(mode=mode,bound_t=t,bound_r=rot,bound_s=sc,bound_p=pv,random_seed=4,position_random=(.1,.05,.1),**extra)
            for n in (off,on):setv(n,**vals)
            a,b=instances(off),instances(on);assert len(a['ids'])==len(b['ids']) and a['ids']==b['ids']
            for ma,mb in zip(a['mats'],b['mats']):assert np.abs(ma-mb).max()<2e-3,(mode,t,rot,sc,pv,np.abs(ma-mb).max())
            assert np.abs(a['scales']-b['scales']).max()<1e-6,'physics must keep the instance size (no stretch)'
    # guide: world positions of the guide curves are the same with the xform LOP identity and the transform baked in
    for n in (off,on):setv(n,mode=1,area_sizex=2,area_sizez=1,bound_t=(1,2,3),bound_r=(10,20,30),bound_s=(1.5,1,2),bound_p=(.2,.1,.3),show_bounds=1)
    def guide(n):
        s=n.stage();xc=UsdGeom.XformCache();out=[]
        for name in ('Bounds','Pivot'):
            prim=s.GetPrimAtPath('/World/Arraytron/Bounds_Guide/'+name);m=np.array(xc.GetLocalToWorldTransform(prim)).reshape(4,4)
            out.append(np.array(UsdGeom.BasisCurves(prim).GetPointsAttr().Get(),dtype=float)@m[:3,:3]+m[3,:3])
        return out
    for ga,gb in zip(guide(off),guide(on)):assert np.abs(ga-gb).max()<1e-4,np.abs(ga-gb).max()
    # rotated layout, then simulate: the pile rests on the WORLD ground plane, not on a rotated one
    setv(on,mode=1,area_count=40,area_sizex=0.4,area_sizez=0.4,bound_t=(0,0,0),bound_r=(0,40,0),bound_s=(1,1,1),bound_p=(0,0,0),phys_drop=0.3,phys_stack=1)
    res=bake(on);hulls,d=world_hulls(on);worst,low,pairs=measure(hulls);dmin=res['plan']['dmin']
    assert low.min()>=-0.05*dmin and worst>=-0.05*dmin and not floating(low,pairs,0.12*dmin)
def cache_semantics():
    st,r,a=stone_scene('cache',phys_on=1,area_count=30);res=bake(a);files=lambda:sorted(os.listdir(CACHE))
    n0=len([f for f in files() if f.startswith('Arraytron_')]);assert n0>=1
    settled=instances(a)['positions'].tolist();assert 'settled' in a.hdaModule().physics_status(a) and phys_state(a)=='settled'
    # any setting that changes the fingerprint leaves the previous result visible, marked STALE; reverting makes it settled again without a new file
    for name,value in (('phys_friction',0.5),('phys_gravity',5.0),('phys_bounce',0.3),('phys_drag',0.0),('phys_duration',3.0),('phys_quality',0),('phys_density',1500.0),('phys_ground_height',0.01),('random_seed',9),('phys_colliders','/World/Props/Stone'),('phys_seed',5),('phys_drop',0.5)):
        old=a.parm(name).eval();a.parm(name).set(value);status=a.hdaModule().physics_status(a)
        assert phys_state(a)=='stale' and 'STALE' in status,(name,phys_state(a),status);assert instances(a)['positions'].tolist()==settled,('the old result must stay visible',name)
        a.parm(name).set(old);assert phys_state(a)=='settled' and 'settled from cache' in a.hdaModule().physics_status(a) and instances(a)['positions'].tolist()==settled,('revert',name)
    assert len([f for f in files() if f.startswith('Arraytron_')])==n0,'reverting a setting must reuse the cache, not create files'
    # a different number of stones cannot reuse the old result: back to the spawn state
    a.parm('area_count').set(31);assert phys_state(a)=='missing' and 'Not simulated' in a.hdaModule().physics_status(a);assert instances(a)['positions'].tolist()!=settled
    a.parm('area_count').set(30);assert phys_state(a)=='settled'
    removed=a.hdaModule().clear_cache(a);assert removed==n0 and 'Not simulated' in a.hdaModule().physics_status(a) and phys_state(a)=='missing'
    res2=bake(a);assert res2['key']==res['key'];assert instances(a)['positions'].tolist()==settled,'a re-bake after Clear Cache must give the same result'
    hip=str(WORK/'cache_roundtrip.hip');hou.hipFile.save(hip);hou.hipFile.load(hip,suppress_save_prompt=True);b=hou.node('/stage/Arraytron')
    assert 'settled' in b.hdaModule().physics_status(b) and instances(b)['positions'].tolist()==settled,'the cache must survive saving and loading the scene'
    b.parm('phys_cachedir').set((WORK/'elsewhere').as_posix());assert 'Not simulated' in b.hdaModule().physics_status(b) and phys_state(b)=='missing'
def strict_mode():
    """Error If Not Simulated: a missing or stale cache stops the node instead of rendering the wrong pile."""
    st,r,a=stone_scene('strict',phys_on=1,area_count=20,phys_strict=1)
    try:a.cook(force=True)
    except hou.OperationFailed:pass
    assert any('Error If Not Simulated' in e for e in all_errors(a)),all_errors(a)         # nothing simulated yet
    a.parm('phys_strict').set(0);bake(a);a.parm('phys_strict').set(1);a.cook(force=True);assert not all_errors(a) and phys_state(a)=='settled'
    a.parm('phys_friction').set(0.4)
    try:a.cook(force=True)
    except hou.OperationFailed:pass
    assert any('Error If Not Simulated' in e for e in all_errors(a)),'a stale cache is an error in strict mode'
    a.parm('phys_friction').set(0.9);a.cook(force=True);assert not all_errors(a)
def guide_physics():
    st,r,a=stone_scene('pguide',phys_on=1,phys_drop=0.4,phys_ground_height=0.1);s=a.stage();g='/World/Arraytron/Bounds_Guide/'
    for n in ('Bounds','Pivot','Drop','Ground'):assert s.GetPrimAtPath(g+n),n
    ground=np.array(UsdGeom.BasisCurves(s.GetPrimAtPath(g+'Ground')).GetPointsAttr().Get());assert np.allclose(ground[:,1],0.1) and ground[:,0].max()>0.2 and ground[:,2].max()>0.2   # wider than the 0.4 x 0.4 spawn, at the ground height
    bounds=np.array(UsdGeom.BasisCurves(s.GetPrimAtPath(g+'Bounds')).GetPointsAttr().Get());drop=np.array(UsdGeom.BasisCurves(s.GetPrimAtPath(g+'Drop')).GetPointsAttr().Get())
    assert np.allclose(drop-bounds,[0,0.4,0]),'the Drop curves are the bounds lifted by Drop Height'
    a.parm('phys_ground').set(0);s=a.stage();assert not s.GetPrimAtPath(g+'Ground') and s.GetPrimAtPath(g+'Drop'),'ground off: no ground outline, drop outline stays'
    a.parm('phys_on').set(0);s=a.stage();assert not s.GetPrimAtPath(g+'Drop') and not s.GetPrimAtPath(g+'Ground') and s.GetPrimAtPath(g+'Bounds'),'no physics guides while Physics Settle is off'
def physics_laws():
    """The solver really obeys the settings: free fall distance, bounce height, friction on a slope."""
    def one(**v):
        st=new_scene('law');r=ref(st,'stone','/World/Props/Stone',STONE);a=arraytron(st,r,phys_on=1,area_count=1,area_sizex=0,area_sizez=0,rotation_random=(0,0,0),scale_random=0,phys_stack=0,**v);return st,a
    # free fall: no ground, 2 m up, 0.5 s later the stone dropped 1/2 g t^2
    for g in (9.80665,4.0):
        st,a=one(phys_ground=0,phys_drop=2.0,phys_gravity=g,phys_duration=1.0,phys_drag=0);inst=a.node('USD_COMPILER');a.hdaModule().bake(a)
        solver=inst.node('PHYSICS_SOLVER');t=12;y0=solver.geometryAtFrame(1).points()[0].position()[1];y1=solver.geometryAtFrame(1+t).points()[0].position()[1]
        expected=0.5*g*(t/hou.fps())**2;assert abs((y0-y1)-expected)<0.02*expected,(g,y0-y1,expected)
    # air drag: the fall speed levels off at sqrt(g / drag)
    for k in (2.0,8.0):
        st,a=one(phys_ground=0,phys_drop=100.0,phys_duration=3.0,phys_drag=k);a.hdaModule().bake(a);solver=a.node('USD_COMPILER/PHYSICS_SOLVER')
        speed=abs(solver.geometryAtFrame(1+60).points()[0].attribValue('v')[1]);expected=math.sqrt(9.80665/k);assert abs(speed-expected)<0.04*expected,(k,speed,expected)
    # bounce: peak after the first impact
    peaks={}
    for bounce in (0.0,0.9):
        st,a=one(phys_ground=1,phys_drop=0.5,phys_bounce=bounce,phys_duration=2.0,phys_drag=0);a.hdaModule().bake(a);solver=a.node('USD_COMPILER/PHYSICS_SOLVER')
        ys=[solver.geometryAtFrame(1+f).points()[0].position()[1] for f in range(0,48)];hit=min(range(len(ys)),key=lambda i:ys[i]);peaks[bounce]=max(ys[hit:])-min(ys)
    assert peaks[0.9]>peaks[0.0]+0.05,peaks
    # friction: one stone on a 20 degree slope (a rotated Cube slab, ground off) slides much further with friction 0
    path=write_collider('Ramp',lambda s,root:(lambda c:(UsdGeom.Xformable(c).AddRotateZOp().Set(20.0),UsdGeom.Xformable(c).AddScaleOp().Set(Gf.Vec3f(3,0.1,3))))(UsdGeom.Cube.Define(s,root+'/Plane')))
    dist={}
    for mu in (0.0,2.0):
        st=new_scene('mu');r=ref(st,'stone','/World/Props/Stone',STONE);ramp=ref(st,'ramp','/World/Ramp',path,r)
        a=arraytron(st,ramp,phys_on=1,area_count=1,area_sizex=0,area_sizez=0,rotation_random=(0,0,0),scale_random=0,phys_stack=0,phys_ground=0,phys_colliders='/World/Ramp',phys_drop=0.3,phys_friction=mu,phys_duration=2.0)
        a.parmTuple('bound_t').set((0,0.1,0));start=instances(a)['positions'][0].copy();res=bake(a);end=instances(a)['positions'][0];dist[mu]=float(np.linalg.norm(end-start))
    assert dist[0.0]>dist[2.0]+0.2,dist
    timings['laws']=dict(bounce_peak_0=round(peaks[0.0],4),bounce_peak_09=round(peaks[0.9],4),slide_mu0=round(dist[0.0],3),slide_mu2=round(dist[2.0],3))
def quality_presets():
    rows={}
    for q,name in enumerate(('Draft','Standard','High')):
        st,r,a=stone_scene('q%d'%q,phys_on=1,area_count=70,phys_quality=q,phys_duration=10.0);res=bake(a);hulls,d=world_hulls(a);worst,low,pairs=measure(hulls);dmin=res['plan']['dmin']
        allowed=res['plan']['margin']+0.05*dmin
        assert worst>=-allowed and low.min()>=-allowed,(name,worst,low.min(),allowed);fl=floating(low,pairs,0.12*dmin+res['plan']['margin']);assert not fl,(name,fl)
        rows[name]=dict(seconds=round(res['wall'],1),frames=res['frames'],settled=res['settled'],penetration_mm=round(-worst*1000,3),ground_mm=round(-low.min()*1000,3),margin_mm=round(res['plan']['margin']*1000,3),substeps=res['plan']['substeps'],hull_vertices=len(a.hdaModule().proto_proxies(a)[0]['verts']))
    timings['quality']=rows
def all_errors(node):
    out=list(node.errors())
    for c in node.children():out+=all_errors(c)
    return out
def errors_and_edges():
    st,r,a=stone_scene('err',phys_on=1)
    # a missing prototype prim is reported (by the Source Resolver, before any physics runs)
    a.parm('proto_prim1').set('/World/Props/Nope')
    try:a.cook(force=True)
    except hou.OperationFailed:pass
    assert any('Nope' in e for e in all_errors(a)),all_errors(a)
    try:a.hdaModule().bake(a);raise AssertionError('bake must fail while the prototype is missing')
    except hou.Error as e:assert 'Nope' in str(e) or 'exist' in str(e),str(e)
    a.parm('proto_prim1').set('/World/Props/Stone');a.cook(force=True);assert not all_errors(a)
    # baking with Physics Settle off is refused with a clear message
    a.parm('phys_on').set(0)
    try:a.hdaModule().bake(a);raise AssertionError('bake with physics off must fail')
    except hou.Error as e:assert 'Turn Physics Settle on' in str(e),str(e)
    a.parm('phys_on').set(1)
    # a single stone settles
    a.parm('area_count').set(1);res=bake(a);assert res['count']==1 and res['settled'] and phys_state(a)=='settled'
    # collider patterns that match nothing, or only a prototype's own subtree, change nothing and break nothing
    a.parm('phys_colliders').set('/World/Nothing*');assert phys_state(a)=='settled' and not all_errors(a)
    a.parm('phys_colliders').set('')
    # a prototype with nothing to hull: an Xform without any gprim
    empty=WORK/'empty.usda';sx=Usd.Stage.CreateNew(str(empty));UsdGeom.Xform.Define(sx,'/Nothing');sx.SetDefaultPrim(sx.GetPrimAtPath('/Nothing'));sx.GetRootLayer().Save()
    st2=new_scene('empty');x=ref(st2,'empty','/World/Props/Stone',empty.as_posix());b=arraytron(st2,x,phys_on=1,area_count=5)
    try:b.hdaModule().bake(b);raise AssertionError('a prototype without geometry must be refused')
    except hou.Error as e:assert 'no mesh or basic shape' in str(e),str(e)
    # physics off on the same prototype is untouched (the instancer does not need geometry)
    b.parm('phys_on').set(0);assert len(instances(b)['ids'])==5
def source_types_physics():
    """USD File, SOP Geometry and Input Connection prototypes all get proxies."""
    st=new_scene('sources');r=ref(st,'stone','/World/Props/Stone',STONE)
    geo=hou.node('/obj').createNode('geo','proto_box');box=geo.createNode('box','box');box.parmTuple('size').set((0.05,0.03,0.04));out=geo.createNode('null','OUT');out.setInput(0,box);out.setDisplayFlag(True)
    pb=ref(st,'pebblebox','/World/Props/PebbleBox',BOX)
    a=arraytron(st,r,phys_on=1,area_count=45);a.setInput(1,pb);a.parm('protos').set(3);a.parm('proto_mode').set(3)           # Cycle
    setv(a,proto_type1=2,proto_file1=STONE,proto_type2=3,proto_sop2=out.path(),proto_type3=1,proto_input3=0)
    assert a.hdaModule().resolve(a),'bank must resolve'
    res=bake(a);hulls,d=world_hulls(a);assert sorted(set(d['proto']))==[0,1,2]
    worst,low,pairs=measure(hulls);dmin=res['plan']['dmin']
    assert worst>=-0.05*dmin and low.min()>=-0.05*dmin and not floating(low,pairs,0.12*dmin),(worst,low.min())
    sizes=[len(h[0]) for h in hulls];assert len(set(sizes))>1,'each source type must use its own proxy shape'
def ground_height():
    st,r,a=stone_scene('gh',phys_on=1,area_count=40,phys_ground_height=0.15);res=bake(a);hulls,d=world_hulls(a);worst,low,pairs=measure(hulls,ground=0.15);dmin=res['plan']['dmin']
    assert low.min()>=-0.05*dmin and low.min()<0.1*dmin and worst>=-0.05*dmin and not floating(low,pairs,0.12*dmin),(low.min(),worst)
    a.parm('phys_ground').set(0);assert phys_state(a)=='stale'          # no ground: a different simulation, the old result is only a stale stand-in
def solver_wiring():
    """Every artist setting reaches the solver, and the fixed ones are what the help says."""
    st,r,a=stone_scene('wire',phys_on=1,area_count=20);setv(a,phys_gravity=3.3,phys_density=1234.0,phys_friction=0.45,phys_bounce=0.33,phys_ground_height=0.07,phys_quality=2,phys_drag=2.5)
    s=a.node('USD_COMPILER/PHYSICS_SOLVER');plan=a.node('USD_COMPILER/PHYSICS_PROXIES').geometry();ap=lambda n:plan.attribValue('plan_'+n)
    assert abs(s.evalParm('density')-1234.0)<1e-9 and abs(s.evalParm('friction')-0.45)<1e-9 and abs(s.evalParm('bounce')-0.33)<1e-9
    assert [round(x,9) for x in s.evalParmTuple('gravity')]==[0.0,-3.3,0.0] and s.evalParm('useground')==1 and abs(s.evalParmTuple('ground_pos')[1]-0.07)<1e-9
    for n in ('margin','collision_margin','ground_margin'):
        if s.parm(n) is None:assert n=='ground_margin' and versions.is_h205(),n;continue          # ground_margin does not exist in Houdini 20.5 / 21
        assert abs(s.evalParm(n)-ap('margin'))<1e-12,n
    assert s.parm('substeps').evalAtFrame(1)==ap('substeps') and s.parm('substeps').evalAtFrame(1000)==ap('substeps_late') and ap('substeps')>=ap('substeps_late')>=24
    assert s.evalParm('adddrag')==1 and abs(s.evalParm('drag_airresist')-2.5)<1e-9 and s.evalParm('drag_ignoremass')==1;a.parm('phys_drag').set(0);assert s.evalParm('adddrag')==0;a.parm('phys_drag').set(2.5)
    assert s.evalParm('numiteration')==20 and s.evalParm('collision_bullet_georep')=='concave' and s.evalParm('usecollisions')==1 and s.evalParm('startframe')==1
    for n in ('ground_friction','collision_friction','ground_bounce','collision_bounce'):assert s.evalParm(n)==1,n
    a.parm('phys_ground').set(0);assert s.evalParm('useground')==0
    # the proxy packs one packed prim per stone, named by id, with the baked-in hull
    g=a.node('USD_COMPILER/PHYSICS_PROXIES').geometry();assert len(g.prims())==20 and sorted(p.attribValue('name') for p in g.prims())==sorted('stone%d'%i for i in range(20))
    # the collider branch is empty without patterns and carries triangles with them
    assert len(a.node('USD_COMPILER/PHYSICS_COLLIDERS').geometry().prims())==0
    a.parm('phys_colliders').set('/World/Props/Stone');assert len(a.node('USD_COMPILER/PHYSICS_COLLIDERS').geometry().prims())==30,'the 30 triangles of the stone mesh'
def performance():
    st,r,a=stone_scene('perf',phys_on=1,area_count=300,area_sizex=0.7,area_sizez=0.7,phys_duration=12.0);res=bake(a);hulls,d=world_hulls(a);worst,low,pairs=measure(hulls)
    timings['perf300']=dict(seconds=round(res['wall'],1),frames=res['frames'],settled=res['settled'],penetration_mm=round(-worst*1000,3),dmin_mm=round(res['plan']['dmin']*1000,2),stones=res['count'],substeps=res['plan']['substeps'])
    assert worst>=-0.05*res['plan']['dmin'] and low.min()>=-0.05*res['plan']['dmin']

# ------------------------------------------------------------------ run
if MUTATE:
    setup_mutation()
check('UI contract: every physics parm, defaults, help text, disabled while off, hidden revision counter, version stamp',ui_contract)
check('Physics off: all output arrays equal the real v0.3.6 HDA bit for bit (line, area, grid, circle, bank, bounds, variation)',off_matches_previous)
check('Settle (Standard): no spawn overlap, no pair or ground penetration, no floating stones, came to rest, every stone moved',settle_basic)
check('Deterministic: two separate bakes of the same scene are identical',bake_is_deterministic)
check('Prototype frames: root translate/rotate/scale, off-centre pivot and non-uniform scale respected',prototype_frames)
check('Multiple prototypes (mesh + Cube prim): ids, prototype assignment and scales pass through unchanged; each stone uses its own hull',multi_prototype)
check('Per-prototype scale, rotation offset and Min/Max scale variation are respected by the proxies',per_row_scale_and_offset)
check('Colliders: Cube slab and concave mesh trough, ground plane off; stones stay on the right side',colliders)
check('Prototype sources: USD File, SOP Geometry and Input Connection rows each get their own proxy',source_types_physics)
check('Ground Height moves the ground plane; switching the ground off is a different simulation',ground_height)
check('Solver wiring: every setting reaches the Bullet solver, fixed surface values, late-phase substeps, proxy and collider branches',solver_wiring)
check('Bounds Transform: world-space points equal the normal layout for every mode, guide matches, rotated pile rests on the world ground',bounds_world_space)
check('Cache: fingerprint changes with every setting (old result stays visible as STALE), revert reuses the file, different count falls back, Clear Cache, re-bake identical, survives save/load',cache_semantics)
check('Error If Not Simulated: a missing or stale cache is an error, a matching one is not',strict_mode)
check('Physics guides: ground plane at Ground Height, spawn bounds lifted by Drop Height, gone when off',guide_physics)
check('Solver laws: free-fall distance for two gravities, bounce height, friction on a slope',physics_laws)
check('Collision Quality presets: Draft / Standard / High all settle within their own margin',quality_presets)
check('Errors and edge cases: physics off bake, single stone, empty prototype',errors_and_edges)
check('Performance: 300 stones',performance)
out=ROOT/'tests'/('validation_physics_%s.json'%versions.tag(VID))
out.write_text(json.dumps({'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'measurements':timings,'passed':True},indent=2))
shutil.rmtree(WORK,ignore_errors=True)
print('ALL PASSED',len(checks));print(json.dumps(timings,indent=1))
