"""Imported Points (v1.5.0) validation in real Houdini (22 and 20.5 / 21): hython tests/validate_imported.py
The source is a VEX-generated "simulation" (animated points with id, pscale, v, N, orient, Cd, age) in a SOP network, and USD Points / PointInstancer
prims written to a test scene. Expected values come from the same closed-form formulas in plain Python, own splitmix64 hashes and rotation matrices.
Env ARRAYTRON_MUTATE=<name> breaks the module; the suite must FAIL."""
from pathlib import Path
import hou, json, math, os, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom, Gf, Vt
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v1.5.0':'v1.1.0','v1.6.0':'v1.5.0','v1.6.1':'v1.6.0','v1.6.2':'v1.6.1','v1.7.0':'v1.6.2'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_imported_'));checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE');M64=(1<<64)-1
def ref_hash(i,seed,stream=0):
    z=(i*0x9E3779B97F4A7C15+seed*0xD1B54A32D192ED03+(stream+1)*0x8CB92BA72F3D8DD7)&M64
    z=((z^(z>>30))*0xBF58476D1CE4E5B9)&M64;z=((z^(z>>27))*0x94D049BB133111EB)&M64;z=z^(z>>31)
    return (z>>11)/float(1<<53)
N=40
def sim_formula(n,frame):
    """The source points as the VEX below computes them (closed form)."""
    k=np.arange(n);p0=np.column_stack([(k*37%500)/100.0,(k*11%200)/100.0,(k*53%500)/100.0]);vel=np.column_stack([np.sin(k*1.0),np.full(n,0.5),np.cos(k*1.0)])
    nm=np.column_stack([np.cos(k*0.7),np.ones(n),np.sin(k*0.7)]);nm/=np.linalg.norm(nm,axis=1)[:,None];axis=np.array([0,1,0.5]);axis=axis/np.linalg.norm(axis);ang=np.radians(k*10.0)
    q=np.column_stack([axis[0]*np.sin(ang/2),axis[1]*np.sin(ang/2),axis[2]*np.sin(ang/2),np.cos(ang/2)])
    return dict(P=p0+vel*(frame-1)*0.1,id=1000+((k*13)%n)*7,pscale=0.5+(k%5)*0.25,v=vel,N=nm,Cd=np.column_stack([(k%3)/2.0,(k%5)/4.0,np.full(n,0.5)]),age=k*0.5+frame,orient=q)
SIM_VEX="""int n = %d;
for (int k = 0; k < n; k++) {
    vector p0 = set((k*37%%500)/100.0, (k*11%%200)/100.0, (k*53%%500)/100.0);
    vector vel = set(sin(k*1.0), 0.5, cos(k*1.0));
    int pt = addpoint(0, p0 + vel*(@Frame-1)*0.1);
    setpointattrib(0, "id", pt, 1000 + ((k*13)%%n)*7);
    setpointattrib(0, "pscale", pt, 0.5 + (k%%5)*0.25);
    setpointattrib(0, "v", pt, vel);
    setpointattrib(0, "N", pt, normalize(set(cos(k*0.7), 1.0, sin(k*0.7))));
    setpointattrib(0, "Cd", pt, set((k%%3)/2.0, (k%%5)/4.0, 0.5));
    setpointattrib(0, "age", pt, k*0.5 + @Frame);
    setpointattrib(0, "orient", pt, quaternion(radians(k*10.0), normalize(set(0.0, 1.0, 0.5))));
}
"""
def write_scene():
    path=WORK/'imported.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y);s.SetStartTimeCode(1);s.SetEndTimeCode(10)
    for name in ('Ball','BallB'):UsdGeom.Xform.Define(s,'/World/Props/'+name);UsdGeom.Cube.Define(s,'/World/Props/%s/C'%name).CreateSizeAttr(0.2)
    n=30;k=np.arange(n);pos=np.column_stack([k*0.3,np.zeros(n),(k%7)*0.2]);pos2=pos+np.array([2.0,0.0,0.0])
    xf=UsdGeom.Xform.Define(s,'/World/Sim');UsdGeom.Xformable(xf).AddTranslateOp().Set(Gf.Vec3d(10,0,0));UsdGeom.Xformable(xf).AddRotateYOp().Set(90.0)             # a transformed parent: points are read in world space
    pt=UsdGeom.Points.Define(s,'/World/Sim/Points');pt.CreatePointsAttr().Set(Vt.Vec3fArray([Gf.Vec3f(*p) for p in pos]),1);pt.GetPointsAttr().Set(Vt.Vec3fArray([Gf.Vec3f(*p) for p in pos2]),10)
    pt.CreateWidthsAttr(Vt.FloatArray([0.2+0.1*(i%4) for i in range(n)]));pt.CreateIdsAttr(Vt.Int64Array([500+3*i for i in range(n)]));pt.CreateVelocitiesAttr(Vt.Vec3fArray([Gf.Vec3f(0,0,1)]*n));pt.CreateNormalsAttr(Vt.Vec3fArray([Gf.Vec3f(0,1,0)]*n))
    age=UsdGeom.PrimvarsAPI(pt.GetPrim()).CreatePrimvar('age',Sdf_Float(),UsdGeom.Tokens.vertex);age.Set(Vt.FloatArray([float(i)*0.5 for i in range(n)]))
    pi=UsdGeom.PointInstancer.Define(s,'/World/SimInst');UsdGeom.Cube.Define(s,'/World/SimInst/Protos/A').CreateSizeAttr(0.1);pi.GetPrototypesRel().AddTarget('/World/SimInst/Protos/A')
    pi.CreatePositionsAttr(Vt.Vec3fArray([Gf.Vec3f(*p) for p in pos[:20]]));pi.CreateProtoIndicesAttr(Vt.IntArray([0]*20));pi.CreateIdsAttr(Vt.Int64Array([200+i for i in range(20)]))
    pi.CreateOrientationsAttr(Vt.QuathArray([Gf.Quath(math.cos(math.radians(i)),0,math.sin(math.radians(i)),0) for i in range(20)]));pi.CreateScalesAttr(Vt.Vec3fArray([Gf.Vec3f(1+0.1*i,1,2) for i in range(20)]));pi.CreateVelocitiesAttr(Vt.Vec3fArray([Gf.Vec3f(1,0,0)]*20))
    UsdGeom.Mesh.Define(s,'/World/Ground').CreatePointsAttr([(0,0,0)]);UsdGeom.Cube.Define(s,'/World/NotPoints').CreateSizeAttr(1.0)
    s.GetRootLayer().Save();return path.as_posix()
def Sdf_Float():
    from pxr import Sdf;return Sdf.ValueTypeNames.FloatArray
SCENE=write_scene()
def new_scene(name='scene',n=N):
    hou.hipFile.clear(suppress_save_prompt=True)
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    ref=st.createNode('reference','scene');ref.parm('primpath').set('/World');ref.parm('primpath1').set('/World');ref.parm('filepath1').set(SCENE);ref.parm('filerefprim1').set('defaultPrim')
    geo=hou.node('/obj').createNode('geo','fx');w=geo.createNode('attribwrangle','sim');w.parm('class').set(0);w.parm('snippet').set(SIM_VEX%n);w.setDisplayFlag(True);w.setRenderFlag(True);return st,ref
def imported(stage,source,name='Imp',typ=None,**values):
    a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Ball');a.parm('mode').set(8);a.parm('imp_sop').set('/obj/fx/sim')
    for k,v in values.items():a.parmTuple(k).set(v if isinstance(v,(tuple,list)) else (v,))
    if typ is None and MUTATE:mutate(a)
    return a
def out(a,frame=None):
    if frame is not None:hou.setFrame(frame)
    s=a.stage();assert not a.errors(),a.errors();prim=s.GetPrimAtPath(a.evalParm('outputpath'));pi=UsdGeom.PointInstancer(prim);t=hou.frame();q=pi.GetOrientationsAttr().Get(t) or []
    return dict(pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3),ids=np.array(pi.GetIdsAttr().Get(t) or [],dtype=int),proto=np.array(pi.GetProtoIndicesAttr().Get(t) or [],dtype=int),scales=np.array(pi.GetScalesAttr().Get(t) or []).reshape(-1,3),
                quat=np.array([[x.GetImaginary()[0],x.GetImaginary()[1],x.GetImaginary()[2],x.GetReal()] for x in q]).reshape(-1,4),hidden=sorted(int(i) for i in (pi.GetInvisibleIdsAttr().Get(t) or [])),prim=prim,stage=s)
def by_id(d):
    o=np.argsort(d['ids']);return {k:(v[o] if isinstance(v,np.ndarray) and len(v)==len(o) else v) for k,v in d.items()}
def pv(d,name):return np.array(UsdGeom.PrimvarsAPI(d['prim']).GetPrimvar(name).Get(hou.frame()))
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
    if MUTATE=='imp_ids':g['choose_ids']=lambda ids,count,mode:(np.arange(count,dtype=np.int64),1)
    elif MUTATE=='imp_percent':
        good=g['percent_keep'];g['percent_keep']=lambda ids,percent,seed:~good(ids,percent,seed) if percent<100 else good(ids,percent,seed)
    elif MUTATE=='imp_scale':g['source_scale']=lambda attr,mult:None if attr is None else np.maximum(np.column_stack([attr,attr,attr]),1e-4)
    elif MUTATE=='imp_velocity':
        good=g['source_alignment'];g['source_alignment']=lambda mode,n,orient=None,velocity=None,normal=None:good(mode,n,orient,None if velocity is None else -np.asarray(velocity),normal)
    elif MUTATE=='imp_normal':
        good=g['source_alignment'];g['source_alignment']=lambda mode,n,orient=None,velocity=None,normal=None:good(mode,n,orient,velocity,None if normal is None else np.asarray(normal)*[1,-1,1])
    elif MUTATE=='imp_widths':
        good=g['read_usd_points'];g['read_usd_points']=lambda asset:(lambda r:(r['attrs'].__setitem__('pscale',r['attrs']['pscale']*2) if 'pscale' in r['attrs'] else None,r)[1])(good(asset))
    elif MUTATE=='imp_idattr':
        good=g['sop_imported'];g['sop_imported']=lambda geo,asset:good(geo,asset)
        g['IMPORT_RESERVED']=g['IMPORT_RESERVED']+('Cd','age')                                                  # Copy Attributes can no longer copy them
    else:raise SystemExit('unknown mutation '+MUTATE)
def qmat(q):
    x,y,z,w=q;return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])

# ------------------------------------------------------------------ groups
def ui_contract():
    st,sc=new_scene('ui');a=imported(st,sc);g=a.parmTemplateGroup();mode=g.find('mode');assert mode.menuLabels()[8]=='Imported Points' and len(mode.menuItems())==9 and mode.defaultValue()==0
    for name in ('imp_source','imp_sop','imp_prim','imp_offset','imp_percent','imp_seed','imp_idmode','imp_idattr','imp_scale','imp_scale_attr','imp_scale_mult','imp_orient','imp_orient_attr','imp_vel_attr','imp_normal_attr','imp_copy','imp_info','imp_frame','pv_srcid','pv_copy','proto_percent'):
        t=g.find(name);assert t is not None,name
    for name,cond in (('imp_sop','{ imp_source != 0 }'),('imp_prim','{ imp_source != 1 }'),('imp_offset','{ imp_source != 1 }'),('imp_idattr','{ imp_idmode != 0 }'),('imp_scale_attr','{ imp_scale == 0 }'),('imp_orient_attr','{ imp_orient != 1 }'),('imp_vel_attr','{ imp_orient != 2 }'),('imp_normal_attr','{ imp_orient != 3 }')):assert cond in g.find(name).conditionals()[hou.parmCondType.HideWhen],name
    assert g.find('imp_frame').isHidden() and g.find('imp_percent').defaultValue()==(100.0,) and g.find('imp_idattr').defaultValue()==('id',) and g.find('imp_orient').menuLabels()==('Upright','From Orient Attribute','Along Velocity','From Normal')
    assert g.find('proto_mode').menuLabels()==('Random','Weighted Random','Sequential','Cycle','Even Percent') and g.find('proto_mode').defaultValue()==1
    layout=[t for t in g.entries() if t.label()=='Layout'][0];names=[t.name() for t in layout.parmTemplates()];assert names.index('imp_source')>names.index('cluster_prim') and 'IMPORTED POINTS' in [t.columnLabels()[0] for t in layout.parmTemplates() if t.name().startswith('ui_head')]
    assert a.node('USD_COMPILER/DISTRIBUTION_GENERATOR').inputs()[8].name()=='generate_imported' and a.node('USD_COMPILER/generate_imported').inputs()[0].name()=='imported_source' and a.node('USD_COMPILER/imported_source').type().name()=='object_merge'
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
    st,sc=new_scene('defaults');rng=np.random.default_rng(2)
    for values in (dict(mode=0,line_count=9),dict(mode=1,area_count=40,area_seed=3),dict(mode=7,cluster_prim='',cluster_count=4,cluster_per=10),dict(mode=1,area_count=60,proto_mode=3),dict(mode=1,area_count=60,proto_mode=2)):
        def mk(typ,name):
            a=st.createNode(typ,name);a.setInput(0,sc);a.parm('protos').set(2);a.parm('proto_prim1').set('/World/Props/Ball');a.parm('proto_prim2').set('/World/Props/BallB')
            for k,v in values.items():a.parmTuple(k).set(v if isinstance(v,(tuple,list)) else (v,))
            return a
        a=mk(TYPE,'n%d'%len(values));b=mk(OLD_TYPE,'o%d'%len(values));x,y=out(a),out(b)
        assert len(x['pos'])==len(y['pos'])>0 and np.array_equal(x['ids'],y['ids']) and np.allclose(x['pos'],y['pos'],atol=1e-6) and np.array_equal(x['proto'],y['proto']) and np.allclose(x['scales'],y['scales']) and np.allclose(x['quat'],y['quat'],atol=2e-3)
def pure_functions():
    st,sc=new_scene('pure');a=imported(st,sc);m=a.hdaModule();rng=np.random.default_rng(3)
    ids,how=m.choose_ids(np.array([5,9,2.0]),3,0);assert list(ids)==[5,9,2] and how==0
    ids,how=m.choose_ids(None,4,0);assert list(ids)==[0,1,2,3] and how==2
    ids,how=m.choose_ids(np.array([1,2,2,3]),4,0);assert list(ids)==[0,1,2,3] and how==3
    ids,how=m.choose_ids(np.array([7,8,9]),3,1);assert list(ids)==[0,1,2] and how==1
    idv=np.arange(500)*7+3;seed=4;ref=np.array([ref_hash(int(i),seed,91)*100.0<30.0 for i in idv]);assert np.array_equal(m.percent_keep(idv,30.0,seed),ref) and 100<ref.sum()<200 and m.percent_keep(idv,100.0,seed).all() and not m.percent_keep(idv,0.0,seed).any()
    lo=m.percent_keep(idv,20.0,seed);hi=m.percent_keep(idv,60.0,seed);assert np.all(hi[lo])                                    # a higher percent only adds ids
    assert np.allclose(m.source_scale(np.array([0.5,1.0]),2.0),[[1,1,1],[2,2,2]]) and np.allclose(m.source_scale(np.array([[1,2,3.0]]),0.5),[[0.5,1.0,1.5]]) and m.source_scale(None,3.0) is None and np.all(m.source_scale(np.array([0.0]),1.0)>=1e-4)
    q=m.source_alignment(0,3);assert np.allclose(q,[[0,0,0,1]]*3)
    ori=rng.normal(size=(5,4));q=m.source_alignment(1,5,orient=ori);assert np.allclose(np.linalg.norm(q,axis=1),1) and np.allclose(q*np.linalg.norm(ori,axis=1)[:,None],ori)
    vel=np.array([[0,0,2.0],[1,0,0],[0,0,0],[0.3,-0.4,0.5]]);q=m.source_alignment(2,4,velocity=vel)
    for k in range(4):
        sp=np.linalg.norm(vel[k])
        if sp<1e-9:assert np.allclose(q[k],[0,0,0,1]);continue
        R=qmat(q[k]);assert np.allclose(R@[0,0,1],vel[k]/sp,atol=1e-9) and abs(np.linalg.norm(R@[0,1,0])-1)<1e-9                      # +Z follows the velocity
    nrm=np.array([[0,1,0],[1,0,0],[0.2,0.9,0.3],[0,0,0]]);q=m.source_alignment(3,4,normal=nrm)
    for k in range(3):assert np.allclose(qmat(q[k])@[0,1,0],nrm[k]/np.linalg.norm(nrm[k]),atol=1e-9)                                  # +Y follows the normal
    assert np.allclose(q[3],[0,0,0,1])
def sop_source():
    st,sc=new_scene('sop');a=imported(st,sc)
    for frame in (1,7,3,12,1):                                                                                                       # out of order: every frame is its own answer
        d=by_id(out(a,frame));f=sim_formula(N,frame);o=np.argsort(f['id']);assert np.array_equal(d['ids'],f['id'][o]) and np.allclose(d['pos'],f['P'][o],atol=1e-4),frame
    d=out(a,1);assert len(d['ids'])==N and 'N points' not in a.parm('imp_info').eval() and '40 points in the source, 40 used; ids from the source attribute' in a.parm('imp_info').eval(),a.parm('imp_info').eval()
    assert a.node('USD_COMPILER/generate_imported').isTimeDependent()
    # stable look: a point keeps its prototype and variation as it moves
    a.parm('protos').set(2);a.parm('proto_prim2').set('/World/Props/BallB');a.parm('scale_random_mode').set(1);a.parm('scale_min').set(0.5);a.parm('scale_max').set(2.0);a.parm('rotation_random_mode').set(1);a.parm('yaw_random').set(180)
    d1=by_id(out(a,1));d9=by_id(out(a,9));assert np.array_equal(d1['proto'],d9['proto']) and np.allclose(d1['scales'],d9['scales'],atol=1e-6) and np.allclose(d1['quat'],d9['quat'],atol=2e-3) and not np.allclose(d1['pos'],d9['pos'])
def id_modes():
    st,sc=new_scene('ids');a=imported(st,sc,imp_idmode=1);d=by_id(out(a,1));f=sim_formula(N,1);assert list(d['ids'])==list(range(N)) and np.allclose(d['pos'],f['P'],atol=1e-4)               # Point Number: id = ptnum
    a.parm('imp_idmode').set(0);a.parm('imp_idattr').set('nope');d=by_id(out(a,1));assert list(d['ids'])==list(range(N)) and any('no point attribute "nope"' in w for n in a.allSubChildren() for w in n.warnings()) and 'point numbers (the source has no id attribute)' in a.parm('imp_info').eval()
    a.parm('imp_idattr').set('age');d=by_id(out(a,1));assert len(set(d['ids']))==N                                                      # age = k*0.5+1 -> int cast duplicates
    a.parm('imp_idattr').set('id')
    st2,sc2=new_scene('ids2');w=hou.node('/obj/fx/sim');w.parm('snippet').set(SIM_VEX.replace('1000 + ((k*13)%%n)*7','1000').replace('%%','%')%N if False else (SIM_VEX%N).replace('1000 + ((k*13)%n)*7','1000'))     # every id equal
    b=imported(st2,sc2);d=out(b,1);assert 'not unique' in b.parm('imp_info').eval() and sorted(d['ids'].tolist())==list(range(N))
def percent_use():
    st,sc=new_scene('pct',200);a=imported(st,sc,imp_percent=100.0,imp_seed=3);full=by_id(out(a,1));assert len(full['ids'])==200
    f=sim_formula(200,1);ids=np.sort(f['id']);a.parm('imp_percent').set(30.0);d=by_id(out(a,1));want=[i for i in ids if ref_hash(int(i),3,91)*100.0<30.0];assert d['ids'].tolist()==want and 30<len(want)<90
    assert '200 points in the source, %d used'%len(want) in a.parm('imp_info').eval()
    a.parm('imp_percent').set(60.0);d2=by_id(out(a,1));assert set(d['ids'].tolist())<set(d2['ids'].tolist())                                  # only ever adds
    for i in d['ids']:j=list(d2['ids']).index(i);k=list(d['ids']).index(i);assert np.allclose(d2['pos'][j],d['pos'][k],atol=1e-6)
    a.parm('imp_percent').set(0.0);assert len(out(a,1)['ids'])==0
def scale_modes():
    st,sc=new_scene('scale');a=imported(st,sc,base_scale=1.0);d=by_id(out(a,1));assert np.allclose(d['scales'],1.0,atol=1e-6)                       # Off: the source scale is ignored
    f=sim_formula(N,1);o=np.argsort(f['id']);a.parm('imp_scale').set(1);a.parm('imp_scale_mult').set(2.0);d=by_id(out(a,1));assert np.allclose(d['scales'],np.repeat((f['pscale'][o]*2.0)[:,None],3,axis=1),atol=1e-5)
    a.parm('base_scale').set(1.5);d=by_id(out(a,1));assert np.allclose(d['scales'],np.repeat((f['pscale'][o]*2.0*1.5)[:,None],3,axis=1),atol=1e-5)    # times the Look tab scale
    a.parm('base_scale').set(1.0);a.parm('imp_scale').set(0);d=by_id(out(a,1));assert np.allclose(d['scales'],2.0,atol=1e-6)                       # Off + multiplier: every instance
    a.parm('imp_scale').set(1);a.parm('imp_scale_attr').set('Cd');d=by_id(out(a,1));assert np.allclose(d['scales'],np.maximum(f['Cd'][o]*2.0,1e-4),atol=1e-5)                 # a vector attribute
    a.parm('imp_scale_attr').set('nothing');d=by_id(out(a,1));assert np.allclose(d['scales'],2.0,atol=1e-6) and any('no point attribute "nothing"' in w for n in a.allSubChildren() for w in n.warnings())
def orient_modes():
    st,sc=new_scene('orient');a=imported(st,sc);f=sim_formula(N,1);o=np.argsort(f['id'])
    d=by_id(out(a,1));assert np.allclose(d['quat'],[0,0,0,1],atol=2e-3)
    a.parm('imp_orient').set(1);d=by_id(out(a,1))
    for k,q in enumerate(d['quat']):assert np.allclose(qmat(q),qmat(f['orient'][o][k]),atol=3e-3)
    a.parm('imp_orient').set(2);d=by_id(out(a,1))
    for k,q in enumerate(d['quat']):v=f['v'][o][k];assert np.allclose(qmat(q)@[0,0,1],v/np.linalg.norm(v),atol=3e-3)
    a.parm('imp_orient').set(3);d=by_id(out(a,1))
    for k,q in enumerate(d['quat']):assert np.allclose(qmat(q)@[0,1,0],f['N'][o][k],atol=3e-3)
    a.parm('imp_orient').set(2);a.parm('rotation_random_mode').set(1);a.parm('yaw_random').set(180);d=by_id(out(a,1))                          # Randomize turns the instance in its own frame, after the source alignment
    assert any(not np.allclose(qmat(q)@[0,0,1],f['v'][o][k]/np.linalg.norm(f['v'][o][k]),atol=1e-2) for k,q in enumerate(d['quat']))
def usd_sources():
    st,sc=new_scene('usd');a=imported(st,sc,imp_source=1,imp_prim='/World/Sim/Points',imp_scale=1,imp_orient=2,imp_copy='age')
    n=30;k=np.arange(n);pos=np.column_stack([k*0.3,np.zeros(n),(k%7)*0.2])
    def world(p):                                                                                                       # parent: translate (10,0,0), rotate Y 90 degrees
        c,s=0.0,1.0;R=np.array([[c,0,s],[0,1,0],[-s,0,c]]);return p@R.T+np.array([10.0,0,0]) if False else np.array([[c*x+s*z,y,-s*x+c*z] for x,y,z in p])+np.array([10.0,0,0])
    d=by_id(out(a,1));assert np.array_equal(d['ids'],np.array([500+3*i for i in range(n)])) and np.allclose(d['pos'],world(pos),atol=1e-5)
    assert np.allclose(d['scales'],np.repeat(((0.2+0.1*(k%4))*0.5)[:,None],3,axis=1),atol=1e-5)                          # USD widths are diameters: pscale = width / 2
    assert np.allclose(qmat(d['quat'][0])@[0,0,1],[1,0,0],atol=3e-3)                                                      # velocity (0,0,1) in the parent's frame -> world (1,0,0)
    mid=by_id(out(a,5.5));t=(5.5-1)/9.0;assert np.allclose(mid['pos'],world(pos+t*np.array([2.0,0,0])),atol=1e-4)           # time samples are interpolated
    a.parm('imp_offset').set(-3.0);off=by_id(out(a,5.5));t=(2.5-1)/9.0;assert np.allclose(off['pos'],world(pos+t*np.array([2.0,0,0])),atol=1e-4)
    a.parm('imp_offset').set(0.0);a.parm('pv_copy').set('age');dd=out(a,1);o=np.argsort(dd['ids']);assert np.allclose(pv(dd,'age')[o],np.array([i*0.5 for i in range(n)]),atol=1e-5)               # primvars become attributes
    b=imported(st,sc,'Inst',imp_source=1,imp_prim='/World/SimInst',imp_scale=1,imp_orient=1);d=by_id(out(b,1));assert np.array_equal(d['ids'],np.arange(200,220)) and np.allclose(d['pos'],np.column_stack([np.arange(20)*0.3,np.zeros(20),(np.arange(20)%7)*0.2]),atol=1e-5)
    assert np.allclose(d['scales'][:,0],1+0.1*np.arange(20),atol=1e-5) and np.allclose(d['scales'][:,2],2.0)
    for i in (0,5,13):assert np.allclose(qmat(d['quat'][i]),qmat([0,math.sin(math.radians(i)),0,math.cos(math.radians(i))]),atol=3e-3)
    for path,frag in (('','is empty'),('/World/Nothing','does not exist'),('/World/NotPoints','must be a Points or PointInstancer')):
        c=imported(st,sc,'E',imp_source=1,imp_prim=path)
        try:c.cook(force=True);c.stage()
        except hou.OperationFailed:pass
        assert any(frag in e for e in all_errors(c)),(path,all_errors(c))
        c.destroy()
def even_percent():
    st,sc=new_scene('even',1000);a=imported(st,sc,proto_mode=4);a.parm('protos').set(2);a.parm('proto_prim2').set('/World/Props/BallB');a.parm('proto_weight1').set(3.0);a.parm('proto_weight2').set(7.0);a.parm('proto_seed').set(2)
    d=by_id(out(a,1));cnt=np.bincount(d['proto'],minlength=2);assert abs(cnt[0]-300)<=2 and abs(cnt[1]-700)<=2,cnt                                  # nearly exact, not statistical
    seed=2
    for i,pr in zip(d['ids'],d['proto']):
        h=(int(i)*0x9E3779B9+seed*1013904223)&0xFFFFFFFF;u=((h&0x7FFFFFFF)//256)/8388608.0;assert pr==(0 if u*10.0<3.0 else 1),(i,u,pr)                                   # independent of the VEX: the same golden-ratio rule
    assert a.parm('proto_percent').eval()=='Ball 30.0%  BallB 70.0%',a.parm('proto_percent').eval()
    a.parm('proto_mode').set(1);w=by_id(out(a,1));cw=np.bincount(w['proto'],minlength=2);assert 230<cw[0]<370                                    # Weighted Random: statistical
    a.parm('proto_mode').set(0);assert a.parm('proto_percent').eval()=='Ball 50.0%  BallB 50.0%'
    a.parm('proto_mode').set(4);a.parm('imp_percent').set(50.0);e=by_id(out(a,1));ce=np.bincount(e['proto'],minlength=2);assert len(e['ids'])>400 and abs(ce[0]/len(e['ids'])-0.3)<0.02                    # still on target after thinning the points
    keep=dict(zip(d['ids'],d['proto']));assert all(keep[i]==pr for i,pr in zip(e['ids'],e['proto']))                                                                   # every id keeps its prototype
def primvars_and_aov():
    st,sc=new_scene('pv');a=imported(st,sc,pv_id=1,pv_proto=1,pv_srcid=1,pv_copy='Cd age v');a.parm('imp_copy').set('Cd age v')
    for frame in (1,6):
        d=out(a,frame);o=np.argsort(d['ids']);f=sim_formula(N,frame);fo=np.argsort(f['id']);assert np.array_equal(pv(d,'arraytron_id')[o],f['id'][fo]) and np.array_equal(pv(d,'source_id')[o],f['id'][fo])
        assert np.allclose(np.array(pv(d,'displayColor'))[o],f['Cd'][fo],atol=1e-5) and np.allclose(pv(d,'age')[o],f['age'][fo],atol=1e-4) and np.allclose(np.array(pv(d,'velocities' if UsdGeom.PrimvarsAPI(d['prim']).HasPrimvar('velocities') else 'v'))[o],f['v'][fo],atol=1e-5)       # Houdini 22 names it velocities, 20.5 / 21 keep v
    a.parm('imp_idmode').set(1);d=out(a,1);o=np.argsort(d['ids']);f=sim_formula(N,1);assert list(pv(d,'arraytron_id')[o])==list(range(N)) and sorted(pv(d,'source_id').tolist())==sorted(f['id'].tolist())               # arraytron_id follows Instance Ids; source_id is always the source's own
    a.parm('pv_copy').set('');a.parm('imp_copy').set('');a.parm('pv_srcid').set(0);names=[p.GetName() for p in UsdGeom.PrimvarsAPI(out(a,1)['prim']).GetPrimvars()];assert 'primvars:displayColor' not in names and 'primvars:source_id' not in names
def downstream():
    st,sc=new_scene('down',120);a=imported(st,sc,imp_scale=1,imp_orient=2,mask_source=1,mask_noise_freq=0.8,mask_effect=0,mask_low=0.3,mask_high=0.7,overlap_mode=1,overlap_size=1,overlap_radius=0.05)
    a.parm('protos').set(2);a.parm('proto_prim2').set('/World/Props/BallB');d1=by_id(out(a,1));assert 5<len(d1['ids'])<120
    keep=set(d1['ids'].tolist());d2=by_id(out(a,6));assert set(d2['ids'].tolist())<=set(sim_formula(120,6)['id'].tolist())
    a.parm('overrides').set(2);a.parm('ovr_id1').set(int(d1['ids'][0]));a.parm('ovr_delete1').set(1);a.parm('ovr_id2').set(int(d1['ids'][1]));a.parm('ovr_scale2').set(3.0);d3=by_id(out(a,1));assert len(d3['ids'])==len(d1['ids'])-1 and np.allclose(d3['scales'][0],3*d1['scales'][1],atol=1e-5)    # overrides by the source id
    a.parm('overrides').set(0);a.parm('fields').set(1);a.parm('field_type1').set(0);a.parm('field_hmin1').set(0.0);a.parm('field_hmax1').set(1.0);a.parm('field_hfall1').set(0.0);a.parm('field_effect').set(0);d4=out(a,1);assert 0<len(d4['ids'])<=len(d1['ids'])
    a.parm('fields').set(0);a.parm('dbg_on').set(1);a.parm('dbg_generated').set(1);a.parm('dbg_rejected').set(1);dd=out(a,1);dbg=dd['stage'].GetPrimAtPath(a.evalParm('outputpath')+'/Debug');assert len(UsdGeom.Points(dbg.GetChild('Generated')).GetPointsAttr().Get())==120      # the debug view shows the imported points
def source_errors():
    st,sc=new_scene('err');a=imported(st,sc,imp_sop='')
    a.parm('imp_sop').set('');d=out(a,1);assert len(d['ids'])==0 and '0 points in the source' in a.parm('imp_info').eval()                       # an empty source gives no instances and no error
    a.parm('imp_sop').set('/obj/fx/nothing');d=out(a,1);assert len(d['ids'])==0                                                                  # a missing node is an empty source (Object Merge warns)
    a.parm('imp_sop').set('/obj/fx/sim');assert len(out(a,1)['ids'])==N
    b=st.createNode(TYPE,'Plain');b.setInput(0,sc);b.parm('protos').set(1);b.parm('proto_prim1').set('/World/Props/Ball');b.parm('mode').set(1);b.parm('area_count').set(5);assert len(out(b,1)['ids'])==5                                                                  # the other modes work as before (the source is never read)
def main():
    for name,func in (('UI contract: Imported Points mode, parameters, Even Percent, primvar toggles, Object Merge source, every v1.1.0 parameter unchanged',ui_contract),
                      ('Modes 0, 1, 7 and the selection modes reproduce v1.1.0 exactly',defaults_unchanged),
                      ('Pure functions: ids, percent, scale, alignment against rotation matrices',pure_functions),
                      ('SOP source follows the timeline (frames out of order), ids kept, look stays with the id',sop_source),
                      ('Id modes: source attribute, point number, missing attribute and duplicates fall back with a warning',id_modes),
                      ('Use Percent Of Points keyed on the id; a higher percent only adds points',percent_use),
                      ('Scale: attribute, vector attribute, multiplier, times the Look scale, warning for a missing attribute',scale_modes),
                      ('Orientation: upright, orient attribute, along velocity, from normal; Randomize on top',orient_modes),
                      ('USD Points and PointInstancer sources: world space, widths, ids, time samples, offset, primvars, readable errors',usd_sources),
                      ('Even Percent: counts almost exact, rule checked per id, percent read-out, stable after thinning',even_percent),
                      ('Primvars and AOV ids: arraytron_id, source_id, copied attributes per frame',primvars_and_aov),
                      ('Mask, Separation, overrides, Field Stack and Debug work on imported points',downstream),
                      ('Empty and missing sources are handled',source_errors)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_imported_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
