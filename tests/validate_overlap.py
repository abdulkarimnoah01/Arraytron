"""No Overlap (v0.5.1) validation in real Houdini: hython tests/validate_overlap.py
Prototypes are USD Sphere prims of radius 0.5 (the bounding sphere is exact), so the expected required distance of two instances is
Spacing x (0.5 s1 + 0.5 s2) with the instance scales read back from the stage. Expected survivors come from an independent plain-Python greedy
implementation; Push Apart is checked by brute-force pair distances on the output. Env ARRAYTRON_MUTATE=<name> breaks the module; the suite must FAIL."""
from pathlib import Path
import hou, json, math, os, shutil, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom, Gf, Vt
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v0.5.1':'v0.5.0','v0.5.2':'v0.5.1','v0.6.0':'v0.5.2','v0.7.0':'v0.6.0','v0.8.0':'v0.7.0','v0.9.0':'v0.8.0','v1.0.0':'v0.9.0','v1.1.0':'v1.0.0','v1.5.0':'v1.1.0','v1.6.0':'v1.5.0','v1.6.1':'v1.6.0','v1.6.2':'v1.6.1','v1.7.0':'v1.6.2','v1.8.0':'v1.7.0','v1.9.0':'v1.8.0','v1.10.0':'v1.9.0','v1.11.0':'v1.10.0','v1.12.0':'v1.11.0','v1.13.0':'v1.12.0','v1.14.0':'v1.13.0','v1.15.0':'v1.14.0','v1.16.0':'v1.15.0','v1.17.0':'v1.16.0','v1.18.0':'v1.17.0','v1.19.0':'v1.18.0','v1.20.0':'v1.19.0','v1.21.0':'v1.20.0','v1.21.1':'v1.21.0','v1.22.0':'v1.21.1','v1.23.0':'v1.22.0','v1.24.0':'v1.23.0','v1.25.0':'v1.24.0','v1.25.1':'v1.25.0','v1.21.1':'v1.21.0','v1.22.0':'v1.21.1','v1.23.0':'v1.22.0','v1.24.0':'v1.23.0','v1.25.0':'v1.24.0','v1.25.1':'v1.25.0','v1.9.0':'v1.8.0','v1.10.0':'v1.9.0','v1.11.0':'v1.10.0','v1.12.0':'v1.11.0','v1.13.0':'v1.12.0','v1.14.0':'v1.13.0','v1.15.0':'v1.14.0'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_overlap_'))
checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')
def write_balls():
    path=WORK/'balls.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    for name,r in (('Big',0.5),('Small',0.25)):
        x=UsdGeom.Xform.Define(s,'/World/Props/'+name);sp=UsdGeom.Sphere.Define(s,'/World/Props/%s/S'%name);sp.CreateRadiusAttr(r)
    s.GetRootLayer().Save();return path.as_posix()
BALLS=write_balls()
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True)
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));return hou.node('/stage')
def ball_scene():
    st=new_scene('ov');n=st.createNode('reference','balls');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(BALLS);n.parm('filerefprim1').set('defaultPrim');return st,n
def setv(a,**values):
    for key,value in values.items():a.parmTuple(key).set(value if isinstance(value,(tuple,list)) else (value,))
    return a
def arraytron(stage,source,typ=None,name='Arraytron',**values):
    a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Big')
    if typ is None and MUTATE:mutate(a)
    return setv(a,**values)
def data(a):
    s=a.stage();assert not a.errors(),a.errors()
    pi=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    return dict(pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3),ids=list(pi.GetIdsAttr().Get(t) or []),scales=np.array(pi.GetScalesAttr().Get(t) or []).reshape(-1,3),proto=list(pi.GetProtoIndicesAttr().Get(t) or []))
def all_errors(node):
    out=list(node.errors())
    for c in node.children():out+=all_errors(c)
    return out
def all_warnings(node):
    out=list(node.warnings())
    for c in node.children():out+=all_warnings(c)
    return out
def radius(d,small=0.25):
    base=np.array([0.5 if p==0 else small for p in d['proto']]);return base*d['scales'].max(axis=1)
def metric(P,axes):return P[:,[0,2]] if axes==0 else P
def greedy(P,r,tol,axes):
    m=metric(P,axes);keep=[]
    for j in range(len(m)):
        if all(np.linalg.norm(m[i]-m[j])>=tol*(r[i]+r[j]) for i in keep):keep.append(j)
    return keep
def pair_stats(P,r,tol,axes):
    m=metric(P,axes);d=np.linalg.norm(m[:,None]-m[None],axis=2);need=tol*(r[:,None]+r[None]);np.fill_diagonal(d,np.inf);return d,need
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()
def mutate(a):
    g=a.hdaModule().sop_overlap.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='overlap_order':
        good=g['greedy_remove'];g['greedy_remove']=lambda c,r,tol,axes:good(np.asarray(c)[::-1],np.asarray(r)[::-1],tol,axes)[::-1]
    elif MUTATE=='overlap_tol':
        good=g['overlapping_pairs'];g['overlapping_pairs']=lambda c,r,tol,axes:good(c,r,1.0,axes)
    elif MUTATE=='overlap_scale':
        good=g['instance_spheres_for'];g['instance_spheres_for']=lambda asset,geo:(lambda s,c,r:(s,c,r/np.maximum(s['scale'].max(axis=1),1e-9)))(*good(asset,geo))
    elif MUTATE=='overlap_axes':
        g['_metric']=lambda c,axes:c
    elif MUTATE=='push_sign':
        good=g['push_apart'];g['push_apart']=lambda *a,**k:(lambda d,res:(-d,res))(*good(*a,**k))
    else:raise SystemExit('unknown mutation '+MUTATE)

def ui_contract():
    st,src=ball_scene();a=arraytron(st,src,mode=1);g=a.parmTemplateGroup();names=[t.name() for t in g.entries()]
    if g.find('ui_solver'):assert [e.label() for e in g.entries()][3]=='Spacing' and g.find('ui_solver').label()=='Solver Settings'
    else:assert names.index('overlap')==names.index('mask')+1 and [t for t in g.entries() if t.name()=='overlap'][0].label()=='No Overlap',names
    d=dict(overlap_mode=0,overlap_size=0,overlap_radius=0.5,overlap_tolerance=1.0,overlap_axes=1,overlap_iterations=30,overlap_strength=0.5)
    for k,v in d.items():assert a.evalParm(k)==v,(k,a.evalParm(k));assert g.find(k).help().strip(),k
    hide=lambda n:g.find(n).conditionals().get(hou.parmCondType.HideWhen)
    assert hide('overlap_radius')=='{ overlap_size != 1 }' and hide('overlap_iterations')=='{ overlap_mode != 2 }' and hide('overlap_strength')=='{ overlap_mode != 2 }'
    assert g.find('overlap_mode').menuLabels()==('Off','Remove Overlapping','Push Apart') and g.find('overlap_axes').menuLabels()==('XZ (ground plane)','XYZ (3D)')
    assert a.evalParm('overlap_info') in ('No Overlap is off.','Separation and Avoid Geometry are off.') and 'No Overlap' in a.type().definition().sections()['ArraytronVersion'].contents()
    order=[];n=a.node('USD_COMPILER/OUT_POINTS')
    while n is not None:order.append(n.name());n=n.inputs()[0] if n.inputs() else None
    expected=['OUT_POINTS']+(['PROTO_PATH'] if a.node('USD_COMPILER/PROTO_PATH') else [])+(['PRIMVARS'] if a.node('USD_COMPILER/PRIMVARS') else [])+(['GROW'] if a.node('USD_COMPILER/GROW') else [])+(['OVERRIDES'] if a.node('USD_COMPILER/OVERRIDES') else [])+['PHYSICS_SWITCH','NO_OVERLAP','PROTOTYPE_ASSIGNMENT'];assert order[:len(expected)]==expected,order
    assert [n.name() for n in a.node('USD_COMPILER/PHYSICS_SWITCH').inputs()]==['NO_OVERLAP','PHYSICS_APPLY']

def off_unchanged():
    st,src=ball_scene();new=arraytron(st,src,name='new');old=arraytron(st,src,typ=OLD_TYPE,name='old')
    def snap(n):
        pi=UsdGeom.PointInstancer(n.stage().GetPrimAtPath('/World/Arraytron'));t=hou.frame();assert not n.errors(),n.errors()
        return {k:list(getattr(pi,'Get'+k+'Attr')().Get(t)) for k in ('Positions','Orientations','Scales','Ids','ProtoIndices')}
    cases=[dict(mode=0,line_count=40,position_random=(.1,.1,.1)),dict(mode=1,area_count=120,bound_t=(1,2,3),bound_r=(10,20,30),mask_source=1),dict(mode=2,grid_count=(3,3,3),scale_random_mode=1),
           dict(mode=3,circle_facing=1,circle_count=20),dict(mode=1,area_count=60,protos=2,proto_prim2='/World/Props/Small',proto_mode=2),dict(mode=1,area_count=30,phys_on=1)]
    for k,values in enumerate(cases):
        for n in (new,old):
            for p in n.parms():
                if p.parmTemplate().type() not in (hou.parmTemplateType.Folder,hou.parmTemplateType.FolderSet) and not p.isMultiParmInstance() and p.name()!='protos':p.revertToDefaults()
            n.parm('protos').set(1);setv(n,proto_prim1='/World/Props/Big',**values)
        assert snap(new)==snap(old),('case',k,values)

def remove_exact():
    st,src=ball_scene();plain=arraytron(st,src,name='plain',mode=1,area_count=300,area_sizex=6,area_sizez=6,scale_random=0.3);full=data(plain)
    a=arraytron(st,src,mode=1,area_count=300,area_sizex=6,area_sizez=6,scale_random=0.3,overlap_mode=1,overlap_axes=0)
    d=data(a);r=radius(full);expect=greedy(full['pos'],r,1.0,0);assert d['ids']==expect,(len(d['ids']),len(expect))
    full_by_id={i:(p,s) for i,p,s in zip(full['ids'],full['pos'],full['scales'])};assert all(np.allclose(full_by_id[i][0],p,atol=1e-5) and np.allclose(full_by_id[i][1],s) for i,p,s in zip(d['ids'],d['pos'],d['scales'])),'survivors unchanged'
    dist,need=pair_stats(d['pos'],radius(d),1.0,0);assert (dist>=need-1e-4).all(),'no two survivors overlap (brute force)'
    assert 10<len(d['ids'])<100 and a.evalParm('overlap_info')=='Removed %d of 300 points.'%(300-len(d['ids'])),a.evalParm('overlap_info')
    # every removed point overlaps a kept earlier point (the removal is necessary, not over-eager)
    kept=set(d['ids']);m=metric(full['pos'],0)
    for j in set(full['ids'])-kept:assert any(np.linalg.norm(m[i]-m[j])<r[i]+r[j] for i in d['ids'] if i<j),j
    # Spacing and Fixed Radius
    for tol in (0.6,1.4):
        setv(a,overlap_tolerance=tol);dd=data(a);assert dd['ids']==greedy(full['pos'],r,tol,0),tol
    setv(a,overlap_tolerance=1.0);n1=len(data(a)['ids']);setv(a,overlap_tolerance=0.5);assert len(data(a)['ids'])>n1,'a smaller Spacing keeps more points'
    setv(a,overlap_size=1,overlap_radius=0.25,overlap_tolerance=1.0);rf=full['scales'].max(axis=1)*0.25;assert data(a)['ids']==greedy(full['pos'],rf,1.0,0),'Fixed Radius'
    # raising Count never changes earlier survivors
    setv(a,overlap_size=0,overlap_tolerance=1.0,area_count=150);s150=data(a)['ids'];setv(a,area_count=300);s300=data(a)['ids'];assert s300[:len(s150)]==s150 and len(s300)>=len(s150)

def remove_axes_and_protos():
    st,src=ball_scene()
    a=arraytron(st,src,mode=2,grid_count=(4,3,4),grid_size=(6,2.4,6),overlap_mode=1,overlap_axes=0)     # columns of 3 points, 1.2 apart vertically, 2 apart sideways
    assert len(data(a)['ids'])==16,'XZ: points above each other overlap, only the first of every column survives'
    setv(a,overlap_axes=1);assert len(data(a)['ids'])==48,'XYZ: the 1.2 vertical gap clears the unit spheres'
    setv(a,overlap_tolerance=1.3);assert len(data(a)['ids'])==32,'Spacing 1.3 needs 1.3 > 1.2: layers 0 and 2 survive in every column'
    b=arraytron(st,src,name='mix',mode=0,line_count=10,line_length=6.3,protos=2,proto_prim2='/World/Props/Small',proto_mode=3,overlap_mode=1)          # Cycle: big, small, big ...; spacing 0.7
    plain=arraytron(st,src,name='mixplain',mode=0,line_count=10,line_length=6.3,protos=2,proto_prim2='/World/Props/Small',proto_mode=3);f=data(plain);r=radius(f)
    d=data(b);assert d['ids']==greedy(f['pos'],r,1.0,1) and 0<len(d['ids'])<10,(d['ids'],greedy(f['pos'],r,1.0,1));assert all(p==i%2 for p,i in zip(d['proto'],d['ids'])),'prototype assignment follows the id'
    dist,need=pair_stats(d['pos'],radius(d),1.0,1);assert (dist>=need-1e-4).all()

def push_apart_checks():
    st,src=ball_scene();plain=arraytron(st,src,name='plain',mode=1,area_count=40,area_sizex=6,area_sizez=6);full=data(plain);r=radius(full)
    a=arraytron(st,src,mode=1,area_count=40,area_sizex=6,area_sizez=6,overlap_mode=2,overlap_axes=0,overlap_iterations=80);d=data(a)
    assert d['ids']==full['ids'] and len(d['pos'])==40,'Push Apart keeps every point and id';assert np.allclose(d['pos'][:,1],full['pos'][:,1]),'XZ: heights never change'
    dist,need=pair_stats(d['pos'],r,1.0,0);assert (dist>=0.97*need).all(),(np.min(dist/need));assert np.abs(d['pos']-full['pos']).max()>0.1
    dist0,need0=pair_stats(full['pos'],r,1.0,0);assert (dist0<need0).any(),'the plain layout does overlap'
    far=arraytron(st,src,name='far',mode=0,line_count=3,line_length=40,overlap_mode=2);df=data(far);pf=data(arraytron(st,src,name='farplain',mode=0,line_count=3,line_length=40))['pos'];assert np.array_equal(df['pos'],pf) and far.evalParm('overlap_info')=='Moved 0 of 3 points; the worst overlap left is 0.0% of the required distance.','points that overlap nothing do not move'
    assert 'Moved' in a.evalParm('overlap_info') and 'of 40 points' in a.evalParm('overlap_info')
    assert np.allclose(data(a)['pos'],d['pos']),'deterministic'
    nn=lambda P:np.sort(pair_stats(P,r,1.0,0)[0],axis=1)[:,0].mean()
    setv(a,overlap_tolerance=1.3,overlap_iterations=150);d13=data(a);dd,nd=pair_stats(d13['pos'],r,1.3,0);assert (dd>=0.95*nd).all() and nn(d13['pos'])>nn(d['pos'])+0.05,'Spacing 1.3 spreads the layout further'
    # crowded: not everything fits; the residual is reported and matches the output
    setv(a,overlap_tolerance=1.0,overlap_iterations=40,area_count=400);dc=data(a);assert np.isfinite(dc['pos']).all() and len(dc['ids'])==400
    dist,need=pair_stats(dc['pos'],radius(dc),1.0,0);worst=float(((need-dist)/need).max());shown=float(a.evalParm('overlap_info').split('overlap left is ')[1].split('%')[0])/100
    assert worst>0.01 and abs(worst-shown)<0.01,(worst,shown)
    setv(a,overlap_iterations=1,overlap_strength=0.1,area_count=40);r1=float(a.evalParm('overlap_info').split('overlap left is ')[1].split('%')[0]);setv(a,overlap_iterations=80,overlap_strength=0.5);r2=float(a.evalParm('overlap_info').split('overlap left is ')[1].split('%')[0])
    assert r1>20 and r2<5,(r1,r2)
    # XYZ: a coincident pair separates in 3D, nothing is NaN
    c=arraytron(st,src,name='co',mode=2,grid_count=(2,1,1),grid_size=(0,0,0),overlap_mode=2,overlap_axes=1,overlap_strength=1.0);dco=data(c);assert np.isfinite(dco['pos']).all() and np.linalg.norm(dco['pos'][0]-dco['pos'][1])>=0.99,dco['pos']

def warnings_and_combinations():
    st,src=ball_scene()
    a=arraytron(st,src,mode=1,area_count=100,area_sizex=6,area_sizez=6,mask_source=1,mask_noise_freq=0.3,overlap_mode=1);d=data(a);assert 0<len(d['ids'])<100 and not all_errors(a)
    setv(a,phys_on=1);assert len(data(a)['ids'])==len(d['ids']),'Physics Settle takes the thinned points as its spawn state';setv(a,phys_on=0)
    setv(a,overlap_mode=2);assert len(data(a)['ids'])<=100
    # empty input: nothing to do
    b=arraytron(st,src,name='none',mode=1,area_count=100,mask_source=1,mask_low=1.0,mask_high=1.0,mask_noise_contrast=0.1,overlap_mode=1);assert len(data(b)['ids'])==0 and not all_errors(b)
    # Push Apart on a Curve warns (it would leave the curve)
    cv=WORK/'c.usda';s=Usd.Stage.CreateNew(str(cv));UsdGeom.Xform.Define(s,'/C');s.SetDefaultPrim(s.GetPrimAtPath('/C'));cc=UsdGeom.BasisCurves.Define(s,'/C/P');cc.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(0,0,0),Gf.Vec3f(4,0,0)]));cc.CreateCurveVertexCountsAttr(Vt.IntArray([2]));cc.CreateTypeAttr('linear');s.GetRootLayer().Save()
    ref=st.createNode('reference','curve');ref.setInput(0,src);ref.parm('primpath').set('/World/Curve');ref.parm('primpath1').set('/World/Curve');ref.parm('filepath1').set(cv.as_posix());ref.parm('filerefprim1').set('defaultPrim')
    e=arraytron(st,ref,name='cv',mode=4,curve_prim='/World/Curve',curve_count=8,overlap_mode=2);data(e);assert any('moves points off the curve' in w for w in all_warnings(e)),all_warnings(e)
    setv(e,overlap_mode=1);data(e);assert not any('moves points off' in w for w in all_warnings(e))

check('No Overlap UI contract: folder, menus, defaults, help, conditionals, read-out, network order',ui_contract)
check('Off: every output array equals the previous release (all modes, bank, mask, physics)',off_unchanged)
check('Remove Overlapping: survivors equal an independent greedy, no two overlap, every removal is justified, Spacing and Fixed Radius, stable under Count',remove_exact)
check('Remove Overlapping: XZ against XYZ metric on stacked grids, per-prototype radii, prototype ids',remove_axes_and_protos)
check('Push Apart: keeps ids, no overlap when feasible, isolated points stay, deterministic, Spacing, reported residual matches, coincident points',push_apart_checks)
check('Warnings and combinations: Push Apart on a curve warns, mask, Physics Settle, empty input',warnings_and_combinations)
out=ROOT/'tests'/('validation_overlap_%s.json'%versions.tag(VID))
out.write_text(json.dumps({'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'passed':True},indent=2))
shutil.rmtree(WORK,ignore_errors=True)
print('ALL PASSED',len(checks))
