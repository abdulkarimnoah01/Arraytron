"""Separation and Collision (v0.8.0: No Overlap merged with Priority and Avoid Geometry) validation in real Houdini: hython tests/validate_avoid.py
Points are injected through Paint mode (exact positions and ids). The expected results come from plain-Python re-implementations: the greedy removal
in every Priority order, and the analytic distance to a box (clearance, inside test, push direction). Env ARRAYTRON_MUTATE=<name> breaks the module; the suite must FAIL."""
from pathlib import Path
import hou, json, math, os, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom, Gf
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v0.8.0':'v0.7.0','v0.9.0':'v0.8.0','v1.0.0':'v0.9.0','v1.1.0':'v1.0.0','v1.5.0':'v1.1.0','v1.6.0':'v1.5.0','v1.6.1':'v1.6.0','v1.6.2':'v1.6.1','v1.7.0':'v1.6.2','v1.8.0':'v1.7.0','v1.9.0':'v1.8.0','v1.10.0':'v1.9.0','v1.11.0':'v1.10.0','v1.12.0':'v1.11.0','v1.13.0':'v1.12.0','v1.14.0':'v1.13.0','v1.15.0':'v1.14.0','v1.16.0':'v1.15.0','v1.17.0':'v1.16.0','v1.9.0':'v1.8.0','v1.10.0':'v1.9.0','v1.11.0':'v1.10.0','v1.12.0':'v1.11.0','v1.13.0':'v1.12.0','v1.14.0':'v1.13.0','v1.15.0':'v1.14.0'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_avoid_'));checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')
LO=np.array([19.0,0.0,-1.0]);HI=np.array([21.0,2.0,1.0]);R0=0.3          # the box and the fixed instance radius
def write_scene():
    path=WORK/'avoid.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    UsdGeom.Xform.Define(s,'/World/Props/Ball');UsdGeom.Sphere.Define(s,'/World/Props/Ball/S').CreateRadiusAttr(0.1)
    cube=UsdGeom.Cube.Define(s,'/World/Hero/Cube');cube.CreateSizeAttr(2.0);UsdGeom.Xformable(cube).AddTranslateOp().Set(Gf.Vec3d(20,1,0))
    s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True)
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
def painted(stage,source,P,name='Sep',typ=None,**values):
    P=np.asarray(P,dtype=float).reshape(-1,3);a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Ball')
    a.parm('mode').set(6);a.parm('paint_prim').set('');a.parm('paint_align').set(0.0);m=a.hdaModule();table=np.column_stack([P,np.tile([0.0,1.0,0.0],(len(P),1)),np.arange(len(P))]);a.parm('paint_data').set(m.paint_encode({'pts':table,'dab':1,'next':len(P)}))
    a.parm('overlap_size').set(1);a.parm('overlap_radius').set(R0)
    for k,v in values.items():a.parmTuple(k).set(v if isinstance(v,(tuple,list)) else (v,))
    if typ is None and MUTATE:mutate(a)
    return a
def out(a):
    s=a.stage();assert not a.errors(),a.errors()
    pi=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    return dict(pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3),ids=np.array(pi.GetIdsAttr().Get(t) or [],dtype=int),scales=np.array(pi.GetScalesAttr().Get(t) or []).reshape(-1,3),
                quat=np.array([[q.GetImaginary()[0],q.GetImaginary()[1],q.GetImaginary()[2],q.GetReal()] for q in (pi.GetOrientationsAttr().Get(t) or [])]).reshape(-1,4))
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
    if MUTATE=='avoid_margin':
        good=g['avoid_geometry'];g['avoid_geometry']=lambda c,r,margin,tris,axes,mode,iterations=20:good(c,r,0.0,tris,axes,mode,iterations)
    elif MUTATE=='avoid_inside':g['inside_closed']=lambda P,tris:np.zeros(len(P),dtype=bool)
    elif MUTATE=='avoid_push':
        good=g['avoid_geometry'];g['avoid_geometry']=lambda c,r,margin,tris,axes,mode,iterations=20:(lambda k,d,res:(k,-d,res))(*good(c,r,margin,tris,axes,mode,iterations))
    elif MUTATE=='avoid_axes':
        good=g['avoid_geometry'];g['avoid_geometry']=lambda c,r,margin,tris,axes,mode,iterations=20:good(c,r,margin,tris,1,mode,iterations)
    elif MUTATE=='avoid_priority':g['visiting_order']=lambda r,ids,priority,seed=1:np.arange(len(r))
    elif MUTATE=='avoid_random':
        good=g['visiting_order'];g['visiting_order']=lambda r,ids,priority,seed=1:good(r,ids,priority,seed+1)
    else:raise SystemExit('unknown mutation '+MUTATE)
def box_info(p):
    """(inside, distance to the box surface) of point p: analytic."""
    inside=bool(np.all(p>LO) and np.all(p<HI))
    if inside:return True,float(min(np.min(p-LO),np.min(HI-p)))
    d=np.maximum(np.maximum(LO-p,p-HI),0.0);return False,float(np.linalg.norm(d))
def footprint_distance(p):
    """Distance in the XZ plane to the box footprint (0 inside it)."""
    d=np.maximum(np.maximum(LO[[0,2]]-p[[0,2]],p[[0,2]]-HI[[0,2]]),0.0);return float(np.linalg.norm(d))
def ref_greedy(P,r,tol,order,axes=1):
    """Plain-Python greedy removal visiting points in `order`: keep a point unless a kept point visited earlier overlaps it."""
    m=P if axes==1 else P[:,[0,2]];kept=[];keep=np.zeros(len(P),dtype=bool)
    for j in order:
        if all(np.linalg.norm(m[i]-m[j])>=tol*(r[i]+r[j]) for i in kept):kept.append(j);keep[j]=True
    return keep
def ref_order(r,ids,priority,seed,hash_fn):
    idx=list(range(len(r)))
    if priority==1:return sorted(idx,key=lambda i:(-r[i],i))
    if priority==2:return sorted(idx,key=lambda i:(r[i],i))
    if priority==3:return sorted(idx,key=lambda i:(hash_fn(int(ids[i]),seed,23),i))
    return idx
M64=(1<<64)-1
def ref_hash(i,seed,stream=0):
    z=(i*0x9E3779B97F4A7C15+seed*0xD1B54A32D192ED03+(stream+1)*0x8CB92BA72F3D8DD7)&M64
    z=((z^(z>>30))*0xBF58476D1CE4E5B9)&M64;z=((z^(z>>27))*0x94D049BB133111EB)&M64;z=z^(z>>31)
    return (z>>11)/float(1<<53)

# ------------------------------------------------------------------ groups
def ui_contract():
    st,sc=new_scene('ui');a=painted(st,sc,[[0,0,0]]);g=a.parmTemplateGroup()
    assert g.find('overlap_mode').label()=='Separation' and g.find('overlap_mode').menuLabels()==('Off','Remove Overlapping','Push Apart') and a.node('USD_COMPILER/NO_OVERLAP') is not None
    assert g.find('overlap_priority').menuLabels()==('Id Order','Biggest First','Smallest First','Random') and g.find('overlap_priority').defaultValue()==0
    assert g.find('avoid_mode').menuLabels()==('Off','Remove','Push Out') and g.find('avoid_mode').defaultValue()==0 and g.find('avoid_axes').defaultValue()==1
    assert '{ overlap_mode != 1 }' in g.find('overlap_priority').conditionals()[hou.parmCondType.HideWhen] and '{ avoid_mode == 0 }' in g.find('avoid_prim').conditionals()[hou.parmCondType.HideWhen] and '{ avoid_mode != 2 }' in g.find('avoid_iterations').conditionals()[hou.parmCondType.HideWhen]
    spacing=[t for t in g.entries() if t.label()=='Spacing'][0];names=[t.name() for t in spacing.parmTemplates()];heads=[t.columnLabels()[0] for t in spacing.parmTemplates() if t.name().startswith('ui_head')]
    assert heads==['SEPARATION','AVOID GEOMETRY'] and names.index('avoid_mode')>names.index('overlap_axes') and names[-1]=='overlap_info'
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
        if t.type()==hou.parmTemplateType.Menu:assert n.menuItems()[:len(t.menuItems())]==t.menuItems(),name
def defaults_unchanged():
    st,sc=new_scene('defaults');P=np.random.default_rng(2).uniform(-2,2,(120,3))
    for values in (dict(),dict(overlap_mode=1),dict(overlap_mode=2,overlap_iterations=12),dict(overlap_mode=1,overlap_axes=0,overlap_tolerance=1.4)):
        a=painted(st,sc,P,'n%d'%len(values),**values);b=painted(st,sc,P,'o%d'%len(values),typ=OLD_TYPE,**values);x,y=out(a),out(b)
        assert len(x['pos'])==len(y['pos'])>0 and np.array_equal(x['ids'],y['ids']) and np.allclose(x['pos'],y['pos'],atol=1e-6) and np.allclose(x['scales'],y['scales']),values   # Id Order, Avoid off = v0.7.0 No Overlap exactly
def priorities():
    a,m=(lambda st,sc:(lambda n:(n,n.hdaModule()))(painted(st,sc,[[0,0,0]])))(*new_scene('pri'))
    rng=np.random.default_rng(5);r=rng.uniform(0.1,0.6,40);r[5]=r[9]=r[20]=0.3;ids=rng.permutation(1000)[:40]                        # ties on purpose
    for pr in range(4):assert list(m.visiting_order(r,ids,pr,3))==ref_order(r,ids,pr,3,ref_hash),pr
    P=rng.uniform(-2,2,(40,3))*np.array([1,0.2,1])
    for axes in (0,1):
        for tol in (1.0,0.7,1.3):
            for pr in range(4):
                order=ref_order(r,ids,pr,3,ref_hash);keep=m.greedy_remove(P,r,tol,axes,m.visiting_order(r,ids,pr,3));assert np.array_equal(keep,ref_greedy(P,r,tol,order,axes)),(axes,tol,pr)
            assert np.array_equal(m.greedy_remove(P,r,tol,axes),m.greedy_remove(P,r,tol,axes,np.arange(40)))             # no order = index order
def avoid_pure():
    st,sc=new_scene('pure');a=painted(st,sc,[[0,0,0]]);m=a.hdaModule();P0,T0,area,normals,vn=m.stage_surface(a,'surface_prim','/World/Hero');tris=P0[T0];assert len(tris)==12
    rng=np.random.default_rng(9);C=np.column_stack([rng.uniform(16,24,200),rng.uniform(-2,4,200),rng.uniform(-3,3,200)]);r=rng.uniform(0.1,0.5,200);margin=0.15
    keep,delta,res=m.avoid_geometry(C,r,margin,tris,1,0);assert np.allclose(delta,0)
    for p,rad,k in zip(C,r,keep):
        inside,d=box_info(p);assert k==(not inside and d>=rad+margin) or abs(d-(rad+margin))<1e-9,(p,rad,k,inside,d)
    keep3,delta,res=m.avoid_geometry(C,r,margin,tris,1,1,30);assert keep3.all()
    for p,rad,dl in zip(C,r,delta):
        q=p+dl;inside,d=box_info(p);inside2,d2=box_info(q)
        if not inside and d>=rad+margin:assert np.allclose(dl,0),(p,dl)                                                    # clear points are not touched
        else:assert not inside2 and d2>=rad+margin-1e-6,(p,q,d2)                                                            # everything else ends up clear
    assert res<1e-6
    p=np.array([[18.9,1.0,0.0]]);k,dl,_=m.avoid_geometry(p,np.array([0.3]),0.1,tris,1,1,10);assert np.allclose((p+dl)[0],[18.6,1.0,0.0],atol=1e-6)         # outside, near the -x face: out along -x to r + margin
    p=np.array([[20.6,1.0,0.0]]);k,dl,_=m.avoid_geometry(p,np.array([0.3]),0.1,tris,1,1,10);assert np.allclose((p+dl)[0],[21.4,1.0,0.0],atol=1e-6)         # inside, nearest face +x: out through it
    p=np.array([[20.0,5.0,0.0]]);k,dl,_=m.avoid_geometry(p,np.array([0.3]),0.1,tris,0,1,10)                                  # XZ: above the box, inside its footprint: pushed sideways out of the footprint
    q=(p+dl)[0];assert footprint_distance(q)>=0.4-1e-6 and abs(q[1]-5.0)<1e-9
    k,dl,_=m.avoid_geometry(np.array([[20.0,5.0,0.0],[21.3,5.0,0.0],[21.5,5.0,0.0],[22.0,9.0,5.0]]),np.array([0.3]*4),0.1,tris,0,0);assert list(k)==[False,False,True,True]        # XZ Remove: inside the footprint, 0.3 away (< 0.4), 0.5 away, far
def node_remove_push():
    st,sc=new_scene('node');rng=np.random.default_rng(3);P=np.column_stack([rng.uniform(17,23,150),rng.uniform(-1,3.5,150),rng.uniform(-2.5,2.5,150)])
    a=painted(st,sc,P,avoid_mode=1,avoid_prim='/World/Hero',avoid_margin=0.2);d=out(a);need=R0+0.2
    want=[i for i,p in enumerate(P) if (lambda b:(not b[0]) and b[1]>=need)(box_info(p))]
    assert sorted(d['ids'].tolist())==want and 20<len(want)<130 and 'Avoid Geometry removed %d points'%(150-len(want)) in a.parm('overlap_info').eval()
    a.parm('avoid_mode').set(2);d=out(a);assert len(d['ids'])==150 and np.allclose(d['quat'],[0,0,0,1],atol=2e-3)
    order=np.argsort(d['ids']);Q=d['pos'][order]
    for i,(p,q) in enumerate(zip(P,Q)):
        inside,dist=box_info(p)
        if not inside and dist>=need:assert np.allclose(p,q,atol=1e-5),i
        else:inside2,d2=box_info(q);assert not inside2 and d2>=need-1e-4,(i,p,q,d2)
    moved=sum(1 for p,q in zip(P,Q) if np.linalg.norm(p-q)>1e-5);assert moved==150-len(want) and 'moved %d points'%moved in a.parm('overlap_info').eval()
    a.parm('avoid_axes').set(0);d=out(a);Q=d['pos'][np.argsort(d['ids'])]
    for i,(p,q) in enumerate(zip(P,Q)):
        if footprint_distance(p)>=need:assert np.allclose(p,q,atol=1e-5)
        else:assert footprint_distance(q)>=need-1e-4 and abs(q[1]-p[1])<1e-5,(i,p,q)                                      # footprint clearance, heights untouched
    # Separation Push Apart after Avoid Push Out: the geometry still wins
    a.parm('avoid_axes').set(1);a.parm('overlap_mode').set(2);a.parm('overlap_iterations').set(40);d=out(a);Q=d['pos'][np.argsort(d['ids'])]
    for q in Q:inside,dist=box_info(q);assert not inside and dist>=need-1e-3,(q,dist)
def node_priority():
    st,sc=new_scene('npri');rng=np.random.default_rng(4);P=rng.uniform(-1.5,1.5,(60,3))*np.array([1,0.0,1]);P[:,1]=0.0
    a=painted(st,sc,P,scale_random_mode=1,scale_min=0.5,scale_max=2.0,overlap_tolerance=1.0,overlap_axes=0);base=out(a);scale=np.zeros(60);scale[base['ids']]=base['scales'][:,0];r=R0*scale;assert r.max()/r.min()>2
    a.parm('overlap_mode').set(1);ids=np.arange(60)
    for pr in range(4):
        a.parm('overlap_priority').set(pr);want=ref_greedy(P,r,1.0,ref_order(r,ids,pr,1,ref_hash),0);d=out(a);assert sorted(d['ids'].tolist())==np.nonzero(want)[0].tolist(),pr
    a.parm('overlap_priority').set(1);big=out(a);a.parm('overlap_priority').set(2);small=out(a);rb=r[big['ids']];rs=r[small['ids']];assert rb.mean()>rs.mean() and len(big['ids'])<len(small['ids'])      # the big ones win, so fewer survive
def errors_and_info():
    st,sc=new_scene('err');a=painted(st,sc,[[20,1,0],[5,0,0]],avoid_mode=1,avoid_prim='')
    def fails(fragment):
        try:a.cook(force=True);a.stage()
        except hou.OperationFailed:pass
        text=' | '.join(all_errors(a));assert fragment in text,(fragment,text)
    fails('Avoid Geometry: the Prim is empty')
    a.parm('avoid_prim').set('/World/Nothing');fails('does not exist')
    a.parm('avoid_prim').set('/World/Hero');a.cook(force=True);a.stage();assert not all_errors(a)
    a.parm('avoid_mode').set(0);assert a.parm('overlap_info').eval()=='Separation and Avoid Geometry are off.'
    a.parm('overlap_mode').set(1);a.parm('overlap_radius').set(0.4);d=out(a);assert 'Removed' in a.parm('overlap_info').eval()
def main():
    for name,func in (('UI contract: Separation & Collision folder, Priority, Avoid Geometry, headings, every v0.7.0 parameter unchanged',ui_contract),
                      ('Priority Id Order and Avoid off reproduce v0.7.0 No Overlap exactly (Remove, Push Apart, XZ)',defaults_unchanged),
                      ('Priority orders and greedy removal against plain Python (ties, XZ and XYZ, spacing)',priorities),
                      ('Avoid Geometry maths against the analytic box: Remove, Push Out, inside, XZ footprint',avoid_pure),
                      ('Avoid Geometry on the node: survivors, clearance, untouched points, ids, Separation after Push Out',node_remove_push),
                      ('Priority on the node: the survivors of every order, bigger instances win',node_priority),
                      ('Errors and read-outs are readable',errors_and_info)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_avoid_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
