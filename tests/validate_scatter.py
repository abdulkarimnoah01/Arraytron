"""Curve (v0.4.5) and Surface Scatter (v0.4.6) validation in real Houdini: hython tests/validate_scatter.py [v0.4.5|v0.4.6]
All results are read from the USD stage Karma would render: PointInstancer positions, and instance matrices from ComputeInstanceTransformsAtTime.
Expected values are derived by hand or by independent numpy code, never by calling the generator being tested.
Env ARRAYTRON_MUTATE=<name> deliberately breaks the Python module in memory; the suite must then FAIL."""
from pathlib import Path
import hou, json, math, os, re, shutil, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom, Gf, Vt
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'src'))
import versions
import arraytron_physics as P
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
SURFACE=VID in ('v0.4.6','v0.5.0','v0.5.1','v0.5.2','v0.6.0','v0.7.0','v0.8.0','v0.9.0','v1.0.0','v1.1.0','v1.5.0','v1.6.0','v1.6.1','v1.6.2','v1.7.0','v1.8.0','v1.9.0','v1.10.0','v1.11.0','v1.12.0','v1.13.0','v1.14.0','v1.15.0','v1.16.0','v1.17.0','v1.18.0')
PREVIOUS={'v0.4.5':'v0.4.0','v0.4.6':'v0.4.5','v0.5.0':'v0.4.6','v0.5.1':'v0.5.0','v0.5.2':'v0.5.1','v0.6.0':'v0.5.2','v0.7.0':'v0.6.0','v0.8.0':'v0.7.0','v0.9.0':'v0.8.0','v1.0.0':'v0.9.0','v1.1.0':'v1.0.0','v1.5.0':'v1.1.0','v1.6.0':'v1.5.0','v1.6.1':'v1.6.0','v1.6.2':'v1.6.1','v1.7.0':'v1.6.2','v1.8.0':'v1.7.0','v1.9.0':'v1.8.0','v1.10.0':'v1.9.0','v1.11.0':'v1.10.0','v1.12.0':'v1.11.0','v1.13.0':'v1.12.0','v1.14.0':'v1.13.0','v1.15.0':'v1.14.0','v1.16.0':'v1.15.0','v1.17.0':'v1.16.0','v1.18.0':'v1.17.0','v1.9.0':'v1.8.0','v1.10.0':'v1.9.0','v1.11.0':'v1.10.0','v1.12.0':'v1.11.0','v1.13.0':'v1.12.0','v1.14.0':'v1.13.0','v1.15.0':'v1.14.0'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_scatter_'))
STONE=(ROOT/'dist/test_assets/stone.usda').as_posix()
checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')

# ------------------------------------------------------------------ assets
def write_stage(name,build):
    path=WORK/(name+'.usda');s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/'+name);s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    build(s,'/'+name);s.GetRootLayer().Save();return path.as_posix()
def curves(s,path,pts,counts,kind='linear',basis=None,wrap='nonperiodic',translate=None,name='C'):
    c=UsdGeom.BasisCurves.Define(s,path+'/'+name);c.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*map(float,p)) for p in pts]));c.CreateCurveVertexCountsAttr(Vt.IntArray(counts))
    c.CreateTypeAttr(kind);c.CreateWrapAttr(wrap)
    if basis:c.CreateBasisAttr(basis)
    if translate:UsdGeom.Xformable(c).AddTranslateOp().Set(Gf.Vec3d(*translate))
    return c
LPOLY=[(0,0,0),(2,0,0),(2,0,3)]                                   # an L: 2 along +X, then 3 along +Z
BEZ=[(0,0,0),(1,2,0),(3,2,0),(4,0,0)]
SQUARE=[(0,0,0),(2,0,0),(2,0,2),(0,0,2)]
CURVE_L=write_stage('CurveL',lambda s,r:curves(s,r,LPOLY,[3],translate=(1,0.5,-1)))
CURVE_BEZ=write_stage('CurveBez',lambda s,r:curves(s,r,BEZ,[4],'cubic','bezier'))
CURVE_SQ=write_stage('CurveSq',lambda s,r:curves(s,r,SQUARE,[4],'cubic','catmullRom','periodic'))
CURVE_TWO=write_stage('CurveTwo',lambda s,r:curves(s,r,[(0,0,0),(1,0,0),(5,0,0),(5,0,2),(5,0,4)],[2,3]))
CURVE_NURBS=write_stage('CurveNurbs',lambda s,r:UsdGeom.NurbsCurves.Define(s,r+'/N'))
EMPTY_XF=write_stage('NoCurves',lambda s,r:None)

# ------------------------------------------------------------------ scene helpers
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True)
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));return hou.node('/stage')
def ref(stage,name,prim,path,source=None):
    n=stage.createNode('reference',name)
    if source:n.setInput(0,source)
    n.parm('primpath').set(prim);n.parm('primpath1').set(prim);n.parm('filepath1').set(path);n.parm('filerefprim1').set('defaultPrim');return n
def setv(a,**values):
    for key,value in values.items():a.parmTuple(key).set(value if isinstance(value,(tuple,list)) else (value,))
    return a
def arraytron(stage,source,typ=None,name='Arraytron',**values):
    a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Stone')
    if typ is None and MUTATE:mutate(a)
    return setv(a,**values)
def curve_scene(path=CURVE_L,prim='/World/Curve',**values):
    st=new_scene('curve');stone=ref(st,'stone','/World/Props/Stone',STONE);c=ref(st,'curve',prim,path,stone)
    values.setdefault('curve_prim',prim)
    return st,arraytron(st,c,mode=4,**values)
def data(a):
    s=a.stage();assert not a.errors(),a.errors()
    pi=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    mats=pi.ComputeInstanceTransformsAtTime(t,t,UsdGeom.PointInstancer.IncludeProtoXform);world=UsdGeom.Xformable(pi).ComputeLocalToWorldTransform(t)
    return dict(stage=s,pos=np.array([np.array(m*world).reshape(4,4)[3,:3] for m in mats]),rot=np.array([np.array(m*world).reshape(4,4)[:3,:3] for m in mats]),
                ids=list(pi.GetIdsAttr().Get(t) or []),proto=list(pi.GetProtoIndicesAttr().Get(t) or []),scales=np.array(pi.GetScalesAttr().Get(t) or []))
def all_errors(node):
    out=list(node.errors())
    for c in node.children():out+=all_errors(c)
    return out
def expect_error(a,fragment):
    try:a.cook(force=True)
    except hou.OperationFailed:pass
    text=' | '.join(all_errors(a));assert fragment in text,(fragment,text)
def dist_to_polyline(points,poly):
    d=[]
    for p in points:
        best=1e9
        for a,b in zip(poly[:-1],poly[1:]):
            ab=b-a;t=np.clip(np.dot(p-a,ab)/max(np.dot(ab,ab),1e-18),0,1);best=min(best,np.linalg.norm(p-(a+t*ab)))
        d.append(best)
    return np.array(d)
M64=(1<<64)-1
def ref_hash(i,seed,stream=0):
    """The splitmix64 finaliser of scatter_hash written with plain Python integers (an independent implementation of the documented formula)."""
    z=(i*0x9E3779B97F4A7C15+seed*0xD1B54A32D192ED03+(stream+1)*0x8CB92BA72F3D8DD7)&M64
    z=((z^(z>>30))*0xBF58476D1CE4E5B9)&M64;z=((z^(z>>27))*0x94D049BB133111EB)&M64;z=z^(z>>31)
    return (z>>11)/float(1<<53)
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()

def mutate(a):
    g=a.hdaModule().sop_curve.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='curve_arclength':
        good=g['sample_polyline'];g['sample_polyline']=lambda poly,s:good(poly,np.asarray(s)*0.9)
    elif MUTATE=='curve_tangent':
        good=g['frames_from_tangent'];g['frames_from_tangent']=lambda t,up,roll=0.0:good(-np.asarray(t),up,roll)
    elif MUTATE=='curve_bezier':
        g['_bezier']=lambda c,t:(lambda a,b,cc,d:((1-t)**2)[:,None]*a+(2*(1-t)*t)[:,None]*b+(t*t)[:,None]*cc)(*c)
    elif MUTATE=='curve_random':
        good=g['scatter_hash'];g['scatter_hash']=lambda ids,seed,stream=0:good(np.asarray(ids)+1,seed,stream)
    elif MUTATE=='surface_area':
        good=g['surface_points'];g['surface_points']=lambda P_,T,area,normals,vn,*rest:good(P_,T,np.ones_like(area),normals,vn,*rest)
    elif MUTATE=='surface_normal':
        good=g['normal_alignment'];g['normal_alignment']=lambda n,amount:good(np.asarray(n)*np.array([1,1,-1]),amount)
    elif MUTATE=='surface_slope':
        good=g['surface_points'];g['surface_points']=lambda P_,T,area,normals,vn,count,seed,smooth,lo,hi,*rest:good(P_,T,area,normals,vn,count,seed,smooth,0,180,*rest)
    elif MUTATE=='surface_offset':
        good=g['surface_points'];g['surface_points']=lambda P_,T,area,normals,vn,count,seed,smooth,lo,hi,off,al:good(P_,T,area,normals,vn,count,seed,smooth,lo,hi,0.0,al)
    else:raise SystemExit('unknown mutation '+MUTATE)

# ------------------------------------------------------------------ curve groups
def ui_contract():
    st,a=curve_scene()
    g=a.parmTemplateGroup()
    if g.find('ui_pivot'):assert g.find('curve_prim').conditionals()[hou.parmCondType.HideWhen]=='{ mode != 4 }'
    else:
        folder=[t for t in g.entries() if t.name()=='curve'][0];assert folder.label()=='Curve' and folder.conditionals()[hou.parmCondType.HideWhen]=='{ mode != 4 }'
    menu=g.find('mode');assert menu.menuLabels()[:5]==('Line','Area','Grid / Matrix','Circle / Radial','Curve') and menu.menuItems()[:5]==('0','1','2','3','4'),menu.menuLabels()
    cond=lambda n,k=hou.parmCondType.HideWhen:re.sub(r'(?<=\})\s*\{ mode != \d \}$','',g.find(n).conditionals().get(k) or '')
    assert cond('curve_count')=='{ curve_spacemode == 1 }' and cond('curve_spacing')=='{ curve_spacemode != 1 }' and cond('curve_seed')=='{ curve_spacemode != 2 }'
    assert cond('curve_upmode')=='{ curve_align == 0 }' and cond('curve_up')=='{ curve_align == 0 } { curve_upmode != 1 }' and cond('curve_roll')=='{ curve_align == 0 }'
    assert cond('curve_info',hou.parmCondType.DisableWhen)=='{ mode >= 0 }'
    d=dict(curve_prim='/World/Curve',curve_index=-1,curve_spacemode=0,curve_count=10,curve_spacing=1.0,curve_seed=1,curve_reverse=0,curve_align=1,curve_upmode=0,curve_roll=0.0)
    for k,v in d.items():assert a.evalParm(k)==v,(k,a.evalParm(k))
    assert tuple(a.evalParmTuple('curve_up'))==(0,1,0)
    for n in d:assert g.find(n).help().strip(),n
    assert 'curve(s)' in a.evalParm('curve_info') and '10 points' in a.evalParm('curve_info'),a.evalParm('curve_info')
    assert a.type().definition().sections()['ArraytronVersion'].contents().startswith(VID)
    assert 'Curve' in a.type().definition().sections()['ArraytronVersion'].contents()
    assert [n.name() for n in a.node('USD_COMPILER/DISTRIBUTION_GENERATOR').inputs()][:6]==['generate_line','generate_area','generate_grid','generate_circle','generate_curve']+(['generate_surface'] if SURFACE else [])

def old_modes_unchanged():
    """Modes 0 to 3 (and physics off) must stay bit-for-bit what the previous release made."""
    st=new_scene('same');stone=ref(st,'stone','/World/Props/Stone',STONE);box=ref(st,'x','/World/Props/Other',STONE.replace('stone','stone'),stone)
    new=arraytron(st,stone,name='new');old=arraytron(st,stone,typ=OLD_TYPE,name='old')
    def snap(n):
        s=n.stage();assert not n.errors(),n.errors();pi=UsdGeom.PointInstancer(s.GetPrimAtPath('/World/Arraytron'));t=hou.frame()
        return {k:list(getattr(pi,'Get'+k+'Attr')().Get(t)) for k in ('Positions','Orientations','Scales','Ids','ProtoIndices')}
    cases=[dict(mode=0,line_count=40,position_random=(.1,.1,.1),random_seed=5),dict(mode=1,area_count=120,bound_t=(1,2,3),bound_r=(10,20,30),bound_s=(1,2,.5),bound_p=(.1,.2,.3)),
           dict(mode=2,grid_count=(3,3,3),scale_random_mode=1,scale_min=.7,scale_max=1.4),dict(mode=3,circle_facing=1,circle_count=20,rotation_random_mode=1,yaw_random=90),
           dict(mode=1,area_count=50,bound_scale_instances=1,bound_s=(2,1,1)),dict(mode=1,area_count=30,phys_on=1)]
    for k,values in enumerate(cases):
        for n in (new,old):
            for p in n.parms():
                if p.parmTemplate().type() not in (hou.parmTemplateType.Folder,hou.parmTemplateType.FolderSet) and not p.isMultiParmInstance() and p.name()!='protos':p.revertToDefaults()
            n.parm('protos').set(1);n.parm('proto_prim1').set('/World/Props/Stone');setv(n,**values)
        assert snap(new)==snap(old),('case',k,values)

def curve_by_count():
    st,a=curve_scene(curve_count=6,curve_align=0);d=data(a)
    expect=np.array([[0,0],[1,0],[2,0],[2,1],[2,2],[2,3]],float)+np.array([1,-1])           # the L at arc lengths 0..5, moved by the prim's translate (1, 0.5, -1)
    assert np.allclose(d['pos'][:,[0,2]],expect,atol=1e-5) and np.allclose(d['pos'][:,1],0.5,atol=1e-5),d['pos']
    assert d['ids']==list(range(6)) and d['proto']==[0]*6
    setv(a,curve_count=1);assert np.allclose(data(a)['pos'],[[1,0.5,-1]],atol=1e-5),'one point sits at the start'
    setv(a,curve_count=2);assert np.allclose(data(a)['pos'],[[1,0.5,-1],[3,0.5,2]],atol=1e-5),'two points: both ends'
    setv(a,curve_count=11);p=data(a)['pos']
    arc=np.concatenate(([0],np.cumsum(np.abs(np.diff(p[:,0]))+np.abs(np.diff(p[:,2])))));assert np.allclose(arc,np.arange(11)*0.5,atol=1e-4),'even arc length spacing across the corner'
    setv(a,curve_reverse=1);r=data(a)['pos'];assert np.allclose(r[0],[3,0.5,2],atol=1e-5) and np.allclose(r[-1],[1,0.5,-1],atol=1e-5),'Reverse walks from the end'
    assert a.evalParm('curve_info').startswith('1 curve(s), total length 5')

def curve_by_spacing():
    st,a=curve_scene(curve_spacemode=1,curve_spacing=2.0,curve_align=0);p=data(a)['pos']
    assert len(p)==3 and np.allclose(p[:,[0,2]],np.array([[0,0],[2,0],[2,2]])+[1,-1],atol=1e-5),p       # floor(5/2)+1 points every 2 units
    setv(a,curve_spacing=5.0);assert len(data(a)['pos'])==2,'the last point sits exactly at the end'
    setv(a,curve_spacing=5.001);assert len(data(a)['pos'])==1
    setv(a,curve_spacing=0.0005);assert len(data(a)['pos'])==5001,'spacing is clamped to 0.001'
    st,b=curve_scene(CURVE_SQ,curve_spacemode=1,curve_spacing=1.0,curve_align=0);assert len(data(b)['pos'])>=8
    t=np.linspace(0,1,20001)[:,None];B=np.array(BEZ,float);bez=(1-t)**3*B[0]+3*(1-t)**2*t*B[1]+3*(1-t)*t**2*B[2]+t**3*B[3];L=np.linalg.norm(np.diff(bez,axis=0),axis=1).sum()
    st,c=curve_scene(CURVE_BEZ,curve_spacemode=1,curve_spacing=0.5,curve_align=0);assert len(data(c)['pos'])==int(math.floor(L/0.5))+1,(len(data(c)['pos']),L)

def curve_random():
    st,a=curve_scene(curve_spacemode=2,curve_count=5,curve_seed=3,curve_align=0);p5=data(a)['pos']
    poly=np.array(LPOLY,float)+[1,0.5,-1];assert dist_to_polyline(p5,poly).max()<1e-4,'random points lie on the curve'
    for i in range(5):                                                         # exact: the id-keyed hash, then the position on the L at that arc length
        sv=5.0*ref_hash(i,3);q=np.array([sv,0,0]) if sv<2 else np.array([2,0,sv-2]);assert np.allclose(p5[i],q+[1,0.5,-1],atol=1e-4),(i,p5[i],q)
    setv(a,curve_count=9);p9=data(a)['pos'];assert np.allclose(p5,p9[:5],atol=1e-6),'raising Count keeps the earlier points'
    setv(a,curve_seed=4);assert not np.allclose(p5,data(a)['pos'][:5]),'the seed changes the positions'
    setv(a,curve_count=2000);p=data(a)['pos'];s=np.array([np.abs(q[0]-1)+np.abs(q[2]+1) for q in p]);assert abs(s.mean()-2.5)<0.15 and s.min()<0.05 and s.max()>4.9,'uniform along the 5 units'

def curve_shapes():
    """Cubic curves lie exactly on their analytic shape."""
    t=np.linspace(0,1,2001)[:,None];B=np.array(BEZ,float)
    bez=(1-t)**3*B[0]+3*(1-t)**2*t*B[1]+3*(1-t)*t**2*B[2]+t**3*B[3]
    st,a=curve_scene(CURVE_BEZ,curve_count=40,curve_align=0);p=data(a)['pos']
    assert np.allclose(p[0],B[0],atol=1e-5) and np.allclose(p[-1],B[3],atol=1e-5),'a bezier starts and ends on its end control points'
    assert dist_to_polyline(p,bez).max()<2e-3,'bezier points lie on the analytic curve'
    seg=np.linalg.norm(np.diff(bez,axis=0),axis=1);arc=np.concatenate(([0],np.cumsum(seg)));L=arc[-1]
    # even arc length: the analytic curve parameter of point k sits at arc length k*L/39
    idx=[np.argmin(np.linalg.norm(bez-q,axis=1)) for q in p];assert np.allclose(arc[idx],np.arange(40)*L/39,atol=0.02),'bezier points are evenly spaced by arc length'
    # catmullRom periodic square: passes through its control points and closes without repeating the first point
    st,b=curve_scene(CURVE_SQ,curve_count=8,curve_align=0);q=data(b)['pos'];S=np.array(SQUARE,float)
    assert len(q)==8 and not np.allclose(q[0],q[-1]);d=np.array([np.min(np.linalg.norm(q-c,axis=1)) for c in S]);assert d.max()<0.35,'closed curve passes near its control points'
    st,b2=curve_scene(CURVE_SQ,curve_count=4,curve_align=0);q4=data(b2)['pos'];assert np.allclose(q4[0],[0,0,0],atol=1e-5) or np.linalg.norm(q4[0])<2.5
    # the closed curve's points are spaced evenly around the loop (the wrap segment included)
    ring=np.vstack([q,q[:1]]);gaps=np.linalg.norm(np.diff(ring,axis=0),axis=1);assert gaps.std()/gaps.mean()<0.25,gaps

def curve_alignment():
    st,a=curve_scene(curve_count=7);d=data(a)       # 7 points: arc lengths 0, 5/6 ... no point on the corner (s = 2)
    s=np.arange(7)*5/6;want=np.array([[1,0,0] if v<2 else [0,0,1] for v in s],float)
    fwd=np.array([np.array([0,0,1.])@r for r in d['rot']]);up=np.array([np.array([0,1.,0])@r for r in d['rot']])
    assert np.allclose(fwd,want,atol=2e-3),(fwd,want);assert np.allclose(up,[0,1,0],atol=2e-3),'the up axis stays on World Y along a flat curve'
    assert np.allclose([np.linalg.det(r) for r in d['rot']],1,atol=1e-3)
    setv(a,curve_reverse=1);d2=data(a);f2=np.array([np.array([0,0,1.])@r for r in d2['rot']]);assert np.allclose(f2,-want[::-1],atol=2e-3),'Reverse flips the tangent'
    setv(a,curve_reverse=0,curve_roll=90);d3=data(a);u3=np.array([np.array([0,1.,0])@r for r in d3['rot']]);f3=np.array([np.array([0,0,1.])@r for r in d3['rot']])
    assert np.allclose(f3,want,atol=2e-3) and np.allclose(np.einsum('ij,ij->i',u3,np.array([[0,1,0]]*7)),0,atol=2e-3),'Roll 90 turns the up axis a quarter about the tangent'
    setv(a,curve_roll=0,curve_upmode=1,curve_up=(0,0,1));d4=data(a);u4=np.array([np.array([0,1.,0])@r for r in d4['rot']])
    assert np.allclose(u4[:2],[0,0,1],atol=2e-3),'Custom Up (0,0,1) on the +X leg'
    setv(a,curve_upmode=0,curve_align=0);d5=data(a);assert all(np.allclose(r,np.eye(3),atol=2e-3) for r in d5['rot']),'Alignment None keeps the prototype orientation'
    # the alignment is applied AFTER the instance rotation (as Circle Facing): a base yaw of 90 turns the prototype first
    setv(a,curve_align=1,base_rotation=(0,90,0));d6=data(a);fwd6=np.array([np.array([0,0,1.])@r for r in d6['rot']]);assert not np.allclose(fwd6,want,atol=1e-2)
    assert all(abs(np.linalg.det(r)-1)<1e-3 for r in d6['rot'])
    setv(a,base_rotation=(0,0,0))

def curve_prims():
    st=new_scene('multi');stone=ref(st,'stone','/World/Props/Stone',STONE);c=ref(st,'two','/World/Curve',CURVE_TWO,stone)
    a=arraytron(st,c,mode=4,curve_count=3,curve_align=0);p=data(a)['pos']
    assert len(p)==6 and np.allclose(p[:3,0],[0,0.5,1],atol=1e-5) and np.allclose(p[3:,2],[0,2,4],atol=1e-5) and np.allclose(p[3:,0],5),p        # per curve: 3 points on each
    assert data(a)['ids']==list(range(6)) and a.evalParm('curve_info').startswith('2 curve(s), total length 5'),a.evalParm('curve_info')
    setv(a,curve_index=1);p1=data(a)['pos'];assert len(p1)==3 and np.allclose(p1[:,2],[0,2,4],atol=1e-5)
    setv(a,curve_index=0);assert np.allclose(data(a)['pos'][:,2],0)
    setv(a,curve_index=2);expect_error(a,'only 2 curve(s)')
    setv(a,curve_index=-1);a.cook(force=True);assert not all_errors(a)
    setv(a,curve_count=10000);assert len(data(a)['pos'])==10000,'total capped at 10000'
    # a prim whose subtree holds the curves works too: the Xform parent
    st=new_scene('parent');stone=ref(st,'stone','/World/Props/Stone',STONE);c=ref(st,'curve','/World',CURVE_L,stone)
    a=arraytron(st,c,mode=4,curve_prim='/World',curve_count=3,curve_align=0);assert len(data(a)['pos'])==3

def curve_bounds_and_modes():
    st,a=curve_scene(curve_count=6,curve_align=0,bound_t=(0,10,0));p=data(a)['pos'];assert np.allclose(p[:,1],10.5,atol=1e-5),'the Bounds Transform moves the curve points like every mode'
    setv(a,bound_t=(0,0,0),bound_r=(0,90,0));q=data(a)['pos'];assert np.allclose(np.linalg.norm(q[:,[0,2]],axis=1),np.linalg.norm(p[:,[0,2]],axis=1),atol=1e-4) and np.allclose(q[:,1],0.5,atol=1e-5) and not np.allclose(q[:,[0,2]],p[:,[0,2]]),'Bounds Rotation turns the points about the pivot'
    setv(a,bound_r=(0,0,0),mode=1,area_count=7);assert len(data(a)['pos'])==7,'switching to Area leaves the curve alone'
    setv(a,mode=4);assert len(data(a)['pos'])==6
    setv(a,phys_on=1);assert len(data(a)['pos'])==6,'Physics Settle takes the curve points as its spawn state'
    setv(a,phys_on=0)

def curve_errors():
    st,a=curve_scene(curve_prim='/World/Nope');expect_error(a,'/World/Nope does not exist')
    setv(a,curve_prim='');expect_error(a,'Curve Prim is empty')
    st=new_scene('nurbs');stone=ref(st,'stone','/World/Props/Stone',STONE);c=ref(st,'n','/World/Curve',CURVE_NURBS,stone)
    a=arraytron(st,c,mode=4);expect_error(a,'only BasisCurves are supported')
    st=new_scene('none');stone=ref(st,'stone','/World/Props/Stone',STONE);c=ref(st,'x','/World/Curve',EMPTY_XF,stone)
    a=arraytron(st,c,mode=4);expect_error(a,'No BasisCurves found')
    st,a=curve_scene();assert 'Cannot read' not in a.evalParm('curve_info');setv(a,curve_prim='/World/Nope');assert a.evalParm('curve_info').startswith('Cannot read the curve')

def curve_guide():
    st,a=curve_scene(CURVE_BEZ,curve_count=5);s=a.stage();g='/World/Arraytron/Bounds_Guide/'
    prim=s.GetPrimAtPath(g+'Bounds');assert prim
    pts=np.array(UsdGeom.BasisCurves(prim).GetPointsAttr().Get(),float);B=np.array(BEZ,float);assert np.allclose(pts[0],B[0],atol=1e-4) and np.allclose(pts[-1],B[3],atol=1e-4) and len(pts)>10,'the guide draws the tessellated curve'
    setv(a,show_bounds=0);grp=a.stage().GetPrimAtPath('/World/Arraytron/Bounds_Guide');assert not grp or not grp.IsActive(),'toggle off deactivates the guide'


# ------------------------------------------------------------------ surface assets and groups (v0.4.6)
def mesh(s,path,pts,counts,idx,translate=None,rotate=None,left=False,scale=None):
    m=UsdGeom.Mesh.Define(s,path);m.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*map(float,q)) for q in pts]));m.CreateFaceVertexCountsAttr(Vt.IntArray(counts));m.CreateFaceVertexIndicesAttr(Vt.IntArray(idx))
    if left:m.CreateOrientationAttr('leftHanded')
    x=UsdGeom.Xformable(m)
    if translate:x.AddTranslateOp().Set(Gf.Vec3d(*translate))
    if rotate:x.AddRotateXYZOp().Set(Gf.Vec3f(*rotate))
    if scale:x.AddScaleOp().Set(Gf.Vec3f(*scale))
    return m
QUAD=[(0,0,0),(4,0,0),(4,0,2),(0,0,2)]                 # 4 x 2, normal +Y with the winding below
QIDX=[0,3,2,1]
PLANE=write_stage('Plane',lambda s,r:mesh(s,r+'/M',QUAD,[4],QIDX,translate=(0,1,0)))
TILT=write_stage('Tilt',lambda s,r:mesh(s,r+'/M',QUAD,[4],QIDX,rotate=(0,0,30)))
DOWN=write_stage('Down',lambda s,r:mesh(s,r+'/M',QUAD,[4],QIDX,rotate=(180,0,0)))
LEFT=write_stage('Left',lambda s,r:mesh(s,r+'/M',QUAD,[4],QIDX[::-1],left=True))        # reversed winding + leftHanded = still up
MIRROR=write_stage('Mirror',lambda s,r:mesh(s,r+'/M',QUAD,[4],QIDX,scale=(-1,1,1)))       # a negative scale flips the winding: the normal is corrected
def two(s,r):                                                                                # a 1 x 1 square and a 3 x 3 square apart: areas 1 and 9
    mesh(s,r+'/Small',[(0,0,0),(1,0,0),(1,0,1),(0,0,1)],[4],QIDX);mesh(s,r+'/Big',[(10,0,0),(13,0,0),(13,0,3),(10,0,3)],[4],QIDX)
TWO=write_stage('Two',two)
def slopes(s,r):                                                                             # a flat 2 x 2 patch and a 60 degree bank next to it
    mesh(s,r+'/Flat',[(0,0,0),(2,0,0),(2,0,2),(0,0,2)],[4],QIDX)
    h=0.5*math.tan(math.radians(60));mesh(s,r+'/Bank',[(2,0,0),(2.5,h,0),(2.5,h,2),(2,0,2)],[4],QIDX)
SLOPES=write_stage('Slopes',slopes)
SPHERE=write_stage('SphereS',lambda s,r:(lambda sp:(sp.CreateRadiusAttr(1.0),UsdGeom.Xformable(sp).AddTranslateOp().Set(Gf.Vec3d(0,1,0))))(UsdGeom.Sphere.Define(s,r+'/S')))
CUBE=write_stage('CubeS',lambda s,r:(lambda c:(c.CreateSizeAttr(2.0),))(UsdGeom.Cube.Define(s,r+'/C')))
TERRAIN=(ROOT/'dist/test_assets/terrain.usda').as_posix()

def surface_scene(path=PLANE,prim='/World/Surface',**values):
    st=new_scene('surface');stone=ref(st,'stone','/World/Props/Stone',STONE);c=ref(st,'surface',prim,path,stone)
    values.setdefault('surface_prim',prim);return st,arraytron(st,c,mode=5,**values)
def tri_expected(i,seed,pts,idx_fan):
    """Independent expectation for one quad: area-weighted triangle choice (two equal triangles, fan from vertex 0) and the uniform barycentric draw."""
    tris=[(idx_fan[0],idx_fan[1],idx_fan[2]),(idx_fan[0],idx_fan[2],idx_fan[3])]
    A=[np.linalg.norm(np.cross(np.array(pts[b])-pts[a],np.array(pts[c])-pts[a]))/2 for a,b,c in tris];cdf=np.cumsum(A)/sum(A)
    t=0 if ref_hash(i,seed,1)<cdf[0] else 1;r1=math.sqrt(ref_hash(i,seed,2));r2=ref_hash(i,seed,3);a,b,c=tris[t]
    return np.array(pts[a])*(1-r1)+np.array(pts[b])*(r1*(1-r2))+np.array(pts[c])*(r1*r2)

def surface_ui():
    st,a=surface_scene();g=a.parmTemplateGroup()
    if g.find('ui_pivot'):assert g.find('surface_prim').conditionals()[hou.parmCondType.HideWhen]=='{ mode != 5 }'
    else:
        f=[t for t in g.entries() if t.name()=='surface'][0];assert f.label()=='Surface' and f.conditionals()[hou.parmCondType.HideWhen]=='{ mode != 5 }'
    assert g.find('mode').menuLabels()[:6]==('Line','Area','Grid / Matrix','Circle / Radial','Curve','Surface') and g.find('mode').menuItems()[:6]==('0','1','2','3','4','5')
    cond=lambda n:re.sub(r'(?<=\})\s*\{ mode != \d \}$','',g.find(n).conditionals().get(hou.parmCondType.HideWhen) or '')
    assert cond('surface_count')=='{ surface_countmode != 0 }' and cond('surface_density')=='{ surface_countmode != 1 }'
    d=dict(surface_prim='/World/Surface',surface_countmode=0,surface_count=100,surface_density=100.0,surface_seed=1,surface_normal=0,surface_align=1.0,surface_offset=0.0,surface_slope_min=0.0,surface_slope_max=90.0)
    for k,v in d.items():assert a.evalParm(k)==v,(k,a.evalParm(k));assert g.find(k).help().strip(),k
    assert a.parmTemplateGroup().find('surface_info').conditionals()[hou.parmCondType.DisableWhen]=='{ mode >= 0 }'
    assert a.evalParm('surface_info')=='2 triangles, area 8 (8 inside the slope limits), 100 points.',a.evalParm('surface_info')
    assert 'Surface Scatter' in a.type().definition().sections()['ArraytronVersion'].contents() and a.node('USD_COMPILER/generate_surface')
    st,b=curve_scene();assert b.evalParm('curve_prim')=='/World/Curve'

def curves_unchanged():
    """The Curve distribution of the previous release is untouched."""
    st=new_scene('cu');stone=ref(st,'stone','/World/Props/Stone',STONE);c=ref(st,'curve','/World/Curve',CURVE_BEZ,stone)
    new=arraytron(st,c,name='new',mode=4,curve_count=17,curve_roll=20);old=arraytron(st,c,typ=OLD_TYPE,name='old',mode=4,curve_count=17,curve_roll=20)
    def snap(n):
        pi=UsdGeom.PointInstancer(n.stage().GetPrimAtPath('/World/Arraytron'));t=hou.frame();return {k:list(getattr(pi,'Get'+k+'Attr')().Get(t)) for k in ('Positions','Orientations','Scales','Ids','ProtoIndices')}
    assert snap(new)==snap(old)
    for n in (new,old):setv(n,curve_spacemode=2,curve_count=30,curve_seed=4)
    assert snap(new)==snap(old)

def surface_exact_points():
    st,a=surface_scene(surface_count=60,surface_seed=5,surface_align=0);d=data(a)
    assert d['ids']==list(range(60)) and d['proto']==[0]*60
    for i in range(60):
        want=tri_expected(i,5,QUAD,QIDX)+[0,1,0];assert np.allclose(d['pos'][i],want,atol=1e-4),(i,d['pos'][i],want)       # every point equals the independent computation
    assert all(abs(q-np.eye(3)).max()<2e-3 for q in d['rot']),'Align 0 keeps the prototype upright'
    setv(a,surface_count=200);p=data(a)['pos'];assert np.allclose(p[:60],d['pos'],atol=1e-6),'raising Count keeps the earlier points'
    setv(a,surface_seed=6);assert not np.allclose(data(a)['pos'][:60],d['pos'])
    setv(a,surface_seed=5,surface_count=4000);p=data(a)['pos'];assert abs(p[:,0].mean()-2)<0.1 and abs(p[:,2].mean()-1)<0.06 and p[:,0].min()>=-1e-5 and p[:,0].max()<=4+1e-5,'uniform over the 4 x 2 quad'
    q=[((p[:,0]<2)&(p[:,2]<1)).sum(),((p[:,0]>=2)&(p[:,2]<1)).sum(),((p[:,0]<2)&(p[:,2]>=1)).sum(),((p[:,0]>=2)&(p[:,2]>=1)).sum()];assert min(q)>850 and max(q)<1150,q

def surface_area_weighting():
    st,a=surface_scene(TWO,surface_count=4000,surface_align=0);p=data(a)['pos'];small=(p[:,0]<5).sum()
    assert abs(small-400)<60,('1 of 10 area units is the small square',small)
    assert 'area 10' in a.evalParm('surface_info')
    # a world transform on the mesh and a Surface Prim that is a parent of several meshes both work
    st,b=surface_scene(TWO,prim='/World',surface_count=100,surface_align=0);assert len(data(b)['pos'])==100

def surface_transforms():
    st,a=surface_scene(PLANE,surface_count=300,surface_align=0);p=data(a)['pos'];assert np.allclose(p[:,1],1.0,atol=1e-5),'the prim translate (0,1,0) is applied'
    st,a=surface_scene(TILT,surface_count=200,surface_align=0);p=data(a)['pos'];n=np.array([-0.5,math.sqrt(3)/2,0])
    assert np.abs((p-0)@n).max()<1e-4,'points lie on the 30 degree tilted plane'
    st,a=surface_scene(MIRROR,surface_count=100,surface_align=1);d=data(a);assert np.allclose([np.array([0,1.,0])@r for r in d['rot']],[0,1,0],atol=2e-3),'a negative scale flips the winding but the normal stays up'
    assert d['pos'][:,0].max()<=1e-4 and d['pos'][:,0].min()>=-4-1e-4,'mirrored in X'

def surface_alignment():
    st,a=surface_scene(TILT,surface_count=50);d=data(a);n=np.array([-0.5,math.sqrt(3)/2,0])
    ups=np.array([np.array([0,1.,0])@r for r in d['rot']]);assert np.allclose(ups,n,atol=2e-3),'the up axis follows the surface normal'
    assert np.allclose([np.linalg.det(r) for r in d['rot']],1,atol=1e-3)
    setv(a,surface_align=0.5);u=np.array([np.array([0,1.,0])@r for r in data(a)['rot']]);ang=np.degrees(np.arccos(np.clip(u[:,1],-1,1)));assert np.allclose(ang,15,atol=0.3),ang[:3]
    setv(a,surface_align=0);assert all(abs(r-np.eye(3)).max()<2e-3 for r in data(a)['rot'])
    # yaw about the normal: Yaw Only 180 spins the instances about the surface normal, which stays the up axis
    setv(a,surface_align=1,rotation_random_mode=1,yaw_random=180);d2=data(a);u2=np.array([np.array([0,1.,0])@r for r in d2['rot']]);assert np.allclose(u2,n,atol=3e-3)
    f2=np.array([np.array([0,0,1.])@r for r in d2['rot']]);assert f2.std(axis=0).max()>0.3 and np.abs(f2@n).max()<3e-3,'forward axes are spread around the normal'
    setv(a,rotation_random_mode=0,yaw_random=0)
    st,b=surface_scene(DOWN,surface_count=20,surface_slope_max=180);ub=np.array([np.array([0,1.,0])@r for r in data(b)['rot']]);assert np.allclose(ub,[0,-1,0],atol=2e-3),'a ceiling: the up axis turns upside down'
    st,c=surface_scene(LEFT,surface_count=20);uc=np.array([np.array([0,1.,0])@r for r in data(c)['rot']]);assert np.allclose(uc,[0,1,0],atol=2e-3),'a leftHanded mesh keeps its drawn normal'

def surface_normals_smooth():
    st,a=surface_scene(SPHERE,surface_count=600,surface_normal=0);d=data(a);c=np.array([0,1,0.]);radial=d['pos']-c;radial/=np.linalg.norm(radial,axis=1)[:,None]
    assert np.abs(np.linalg.norm(d['pos']-c,axis=1)-1).max()<0.04,'points lie on the (24 x 12 tessellated) sphere'
    err_face=np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i',np.array([np.array([0,1.,0])@r for r in d['rot']]),radial),-1,1))).mean()
    setv(a,surface_normal=1);d2=data(a);err_smooth=np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i',np.array([np.array([0,1.,0])@r for r in d2['rot']]),radial),-1,1))).mean()
    assert err_smooth<err_face*0.7 and err_smooth<6,(err_face,err_smooth)

def surface_offset_slope():
    st,a=surface_scene(TILT,surface_count=100,surface_align=1,surface_offset=0.4);n=np.array([-0.5,math.sqrt(3)/2,0]);p=data(a)['pos']
    assert np.allclose(p@n,0.4,atol=1e-4),'Offset moves the points along the normal';setv(a,surface_offset=-0.25);assert np.allclose(data(a)['pos']@n,-0.25,atol=1e-4)
    st,b=surface_scene(SLOPES,surface_count=500,surface_align=0,surface_slope_max=45);p=data(b)['pos'];assert len(p)==500 and p[:,0].max()<=2+1e-5,'only the flat patch (0 degrees) is used'
    setv(b,surface_slope_min=45,surface_slope_max=90);p=data(b)['pos'];assert len(p)==500 and p[:,0].min()>=2-1e-5 and p[:,1].max()>0.5,'only the 60 degree bank'
    assert abs(b.evalParmTuple('surface_slope_min')[0]-45)<1e-9 and 'inside the slope limits' in b.evalParm('surface_info')
    setv(b,surface_slope_min=0,surface_slope_max=90);assert (data(b)['pos'][:,0]>2).any() and (data(b)['pos'][:,0]<2).any()
    setv(b,surface_slope_min=70,surface_slope_max=80);b.cook(force=True);assert len(data(b)['pos'])==0 and not all_errors(b) and b.evalParm('surface_info').endswith('0 points.'),'no triangle in range: no points'

def surface_density_cap():
    st,a=surface_scene(PLANE,surface_countmode=1,surface_density=12.5,surface_align=0);assert len(data(a)['pos'])==100,'8 units of area x 12.5'
    setv(a,surface_density=100000);assert len(data(a)['pos'])==10000,'capped at 10000'
    setv(a,surface_countmode=0,surface_count=10000);assert len(data(a)['pos'])==10000
    st,b=surface_scene(TWO,surface_countmode=1,surface_density=3,surface_slope_max=90);assert len(data(b)['pos'])==30

def surface_shapes():
    st,a=surface_scene(CUBE,surface_count=600,surface_align=0,surface_slope_max=180);p=data(a)['pos'];on=np.isclose(np.abs(p),1,atol=1e-5).any(axis=1);assert on.all() and (np.abs(p)<=1+1e-5).all(),'points on the 2 x 2 x 2 cube prim'
    faces=[(p[:,k]>0.99).sum() for k in range(3)]+[(p[:,k]<-0.99).sum() for k in range(3)];assert min(faces)>60,faces
    st,b=surface_scene(CUBE,surface_count=600,surface_slope_max=180);u=np.array([np.array([0,1.,0])@r for r in data(b)['rot']]);pp=data(b)['pos'];axis=np.argmax(np.abs(pp),axis=1);n=np.zeros_like(pp);n[np.arange(len(pp)),axis]=np.sign(pp[np.arange(len(pp)),axis])
    assert np.allclose(u,n,atol=3e-3),'the up axis follows the outward cube face normals'
    st,c=surface_scene(TERRAIN,surface_count=300,surface_normal=1);assert len(data(c)['pos'])==300 and 'triangles' in c.evalParm('surface_info')

def surface_shape_windings():
    """Implicit shapes (cylinder on every axis, capsule, cone) are tessellated with outward normals: every sampled point's up axis points away from the shape's axis."""
    def shape(kind,axis):
        def build(st,r):
            c={'Cylinder':UsdGeom.Cylinder,'Capsule':UsdGeom.Capsule,'Cone':UsdGeom.Cone}[kind].Define(st,r+'/S');c.CreateRadiusAttr(1.0);c.CreateHeightAttr(2.0);c.CreateAxisAttr(axis)
        return write_stage('%s%s'%(kind,axis),build)
    for kind in ('Cylinder','Capsule','Cone'):
        for axis in 'XYZ':
            st,a=surface_scene(shape(kind,axis),surface_count=300,surface_slope_max=180,surface_normal=0);d=data(a);k='XYZ'.index(axis)
            up=np.array([np.array([0,1.,0])@r for r in d['rot']]);rad=d['pos'].copy();rad[:,k]=0;n=np.linalg.norm(rad,axis=1);side=(np.abs(d['pos'][:,k])<0.5)&(n>0.45)
            assert side.sum()>20,(kind,axis)
            outward=rad[side]/n[side][:,None];dot=np.einsum('ij,ij->i',up[side],outward)
            assert (dot>0.4).all(),(kind,axis,dot.min())               # a cone's slanted side tilts the normal, never inward

def surface_bounds_modes_physics():
    st,a=surface_scene(PLANE,surface_count=50,surface_align=0,bound_t=(0,5,0));assert np.allclose(data(a)['pos'][:,1],6,atol=1e-5),'the Bounds Transform moves the points like every mode'
    setv(a,bound_t=(0,0,0),mode=0,line_count=7);assert len(data(a)['pos'])==7;setv(a,mode=5);assert len(data(a)['pos'])==50
    setv(a,phys_on=1);assert len(data(a)['pos'])==50,'Physics Settle takes the scatter as its spawn state';setv(a,phys_on=0)
    d=data(a);assert d['ids']==list(range(50))
    s=a.stage();assert s.GetPrimAtPath('/World/Arraytron/Bounds_Guide/Bounds'),'the guide draws the surface bounding box'
    pts=np.array(UsdGeom.BasisCurves(s.GetPrimAtPath('/World/Arraytron/Bounds_Guide/Bounds')).GetPointsAttr().Get(),float);assert np.allclose(pts.min(axis=0),[0,1,0]) and np.allclose(pts.max(axis=0),[4,1,2])

def surface_errors():
    st,a=surface_scene(prim='/World/Surface',surface_prim='/World/Nope');expect_error(a,'/World/Nope does not exist');assert a.evalParm('surface_info').startswith('Cannot read the surface')
    setv(a,surface_prim='');expect_error(a,'Surface Prim is empty')
    st=new_scene('nomesh');stone=ref(st,'stone','/World/Props/Stone',STONE);c=ref(st,'x','/World/Surface',EMPTY_XF,stone);b=arraytron(st,c,mode=5,surface_prim='/World/Surface');expect_error(b,'No mesh or basic shape')
    st=new_scene('own');stone=ref(st,'stone','/World/Props/Stone',STONE);c=ref(st,'p','/World/Surface',PLANE,stone);b=arraytron(st,c,mode=5,surface_prim='/World',surface_count=20,outputpath='/World/Arraytron')
    assert len(data(b)['pos'])==20,'the output prim and its prototypes are never used as the surface (a parent prim is fine)'

# ------------------------------------------------------------------ run
check('Curve UI contract: mode menu, folder, conditionals, defaults, help, read-out, generator wiring',ui_contract)
check('Modes 0-3 and physics off: every output array equals the real %s HDA bit for bit'%PREVIOUS,old_modes_unchanged)
check('Curve By Count: hand-derived points on an L with a corner, ends, one point, even arc length, Reverse',curve_by_count)
check('Curve By Spacing: floor(Length/Spacing)+1, the end included, the 0.001 floor, closed curves',curve_by_spacing)
check('Curve Random: on the curve, stable under Count, seed, uniform in arc length',curve_random)
check('Cubic curves: bezier and catmullRom lie on their analytic shape, even arc spacing, closed loop',curve_shapes)
check('Curve alignment: forward follows the tangent, up stays on World Y, Reverse, Roll, Custom Up, None, applied after the instance rotation',curve_alignment)
check('Several curves, Curve Index, the cap, a parent prim',curve_prims)
check('Curve points follow the Bounds Transform and mode switching',curve_bounds_and_modes)
check('Curve errors: missing prim, empty path, NurbsCurves, nothing found',curve_errors)
check('Curve guide draws the tessellated curve',curve_guide)
if SURFACE:
    check('Curves of the previous release are untouched (by count and random)',curves_unchanged)
    check('Surface UI contract: Surface mode, folder, conditionals, defaults, help, read-out',surface_ui)
    check('Surface scatter: every point equals the independent triangle / barycentric computation, uniform over the quad, stable under Count and Seed',surface_exact_points)
    check('Surface scatter is area weighted across meshes and under a parent prim',surface_area_weighting)
    check('Mesh world transforms: translate, tilt, negative scale',surface_transforms)
    check('Align to Normal: up axis on the normal, Amount blend, Yaw Only turns about the normal, ceilings and leftHanded meshes',surface_alignment)
    check('Smooth normals follow a sphere much closer than face normals',surface_normals_smooth)
    check('Offset along the normal and slope limits keep the count exact; an empty range gives no points',surface_offset_slope)
    check('Count by Density and the 10000 cap',surface_density_cap)
    check('Basic shapes (cube prim) and the demo terrain',surface_shapes)
    check('Implicit shapes have outward normals on every axis (cylinder, capsule, cone)',surface_shape_windings)
    check('Surface points follow the Bounds Transform, mode switching, Physics Settle and the bounding box guide',surface_bounds_modes_physics)
    check('Surface errors: missing prim, empty path, no mesh, the output prim is skipped',surface_errors)
out=ROOT/'tests'/('validation_scatter_%s.json'%versions.tag(VID))
out.write_text(json.dumps({'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'passed':True},indent=2))
shutil.rmtree(WORK,ignore_errors=True)
print('ALL PASSED',len(checks))
