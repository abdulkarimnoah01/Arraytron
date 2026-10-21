"""Clustering (v0.8.0) validation in real Houdini: hython tests/validate_cluster.py
Cluster centres are compared with Surface Scatter's own sampler, the members with independent per-cluster expectations (count range, radius, radial
distribution, surface membership, ids). Env ARRAYTRON_MUTATE=<name> breaks the module; the suite must FAIL."""
from pathlib import Path
import hou, json, math, os, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom, Gf
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v0.8.0':'v0.7.0','v0.9.0':'v0.8.0','v1.0.0':'v0.9.0','v1.1.0':'v1.0.0','v1.5.0':'v1.1.0','v1.6.0':'v1.5.0','v1.6.1':'v1.6.0','v1.6.2':'v1.6.1','v1.7.0':'v1.6.2','v1.8.0':'v1.7.0','v1.9.0':'v1.8.0','v1.10.0':'v1.9.0','v1.11.0':'v1.10.0','v1.12.0':'v1.11.0','v1.13.0':'v1.12.0','v1.14.0':'v1.13.0','v1.15.0':'v1.14.0','v1.16.0':'v1.15.0','v1.17.0':'v1.16.0','v1.18.0':'v1.17.0','v1.19.0':'v1.18.0','v1.20.0':'v1.19.0','v1.21.0':'v1.20.0','v1.21.1':'v1.21.0','v1.21.1':'v1.21.0','v1.9.0':'v1.8.0','v1.10.0':'v1.9.0','v1.11.0':'v1.10.0','v1.12.0':'v1.11.0','v1.13.0':'v1.12.0','v1.14.0':'v1.13.0','v1.15.0':'v1.14.0'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_cluster_'));checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')
def write_scene():
    path=WORK/'cluster.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    UsdGeom.Xform.Define(s,'/World/Props/Ball');UsdGeom.Sphere.Define(s,'/World/Props/Ball/S').CreateRadiusAttr(0.05)
    UsdGeom.Sphere.Define(s,'/World/Dome').CreateRadiusAttr(2.0)
    m=UsdGeom.Mesh.Define(s,'/World/Ground');m.CreatePointsAttr([(-5,0,5),(5,0,5),(5,0,-5),(-5,0,-5)]);m.CreateFaceVertexCountsAttr([4]);m.CreateFaceVertexIndicesAttr([0,1,2,3]);m.CreateOrientationAttr('rightHanded')
    s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True)
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
def cl(stage,source,name='C',typ=None,**values):
    a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Ball')
    if typ is None:a.parm('mode').set(7)
    for k,v in values.items():a.parmTuple(k).set(v if isinstance(v,(tuple,list)) else (v,))
    if typ is None and MUTATE:mutate(a)
    return a
def out(a):
    s=a.stage();assert not a.errors(),a.errors()
    pi=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    return dict(pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3),ids=np.array(pi.GetIdsAttr().Get(t) or [],dtype=np.int64),quat=np.array([[q.GetImaginary()[0],q.GetImaginary()[1],q.GetImaginary()[2],q.GetReal()] for q in (pi.GetOrientationsAttr().Get(t) or [])]).reshape(-1,4),scales=np.array(pi.GetScalesAttr().Get(t) or []).reshape(-1,3))
def all_errors(node):
    o=list(node.errors())
    for c in node.children():o+=all_errors(c)
    return o
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()
def module(a=None):
    if a is None:
        st,sc=new_scene('mod');a=cl(st,sc)
    return a,a.hdaModule()
def mutate(a):
    g=a.hdaModule().paint_decode.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='cluster_falloff':
        good=g['member_offsets'];g['member_offsets']=lambda ids,radius,falloff,seed:good(ids,radius,0.0,seed)
    elif MUTATE=='cluster_stride':g['CLUSTER_ID_STRIDE']=64
    elif MUTATE=='cluster_jitter':
        good=g['cluster_shape'];g['cluster_shape']=lambda count,per,jitter,seed:good(count,per,0.0,seed)
    elif MUTATE=='cluster_project':
        g['make_projector']=lambda surface,center,radius,smooth=True:(lambda pts,normal:(np.asarray(pts),np.tile(np.asarray(normal,dtype=float),(len(pts),1)),np.ones(len(pts),dtype=bool)))
    elif MUTATE=='cluster_centres':
        good=g['surface_points'];g['surface_points']=lambda P,T,area,normals,vn,count,seed,*r:good(P,T,area,normals,vn,count,seed+1,*r)
    elif MUTATE=='cluster_radius':
        good=g['cluster_points'];g['cluster_points']=lambda surface,count,per,radius,falloff,jitter,seed,smooth=True:good(surface,count,per,radius*0.5,falloff,jitter,seed,smooth)
    else:raise SystemExit('unknown mutation '+MUTATE)

# ------------------------------------------------------------------ groups
def ui_contract():
    st,sc=new_scene('ui');a=cl(st,sc);g=a.parmTemplateGroup();mode=g.find('mode')
    assert mode.menuLabels()[7]=='Cluster' and len(mode.menuItems())>=8 and mode.defaultValue()==0
    for name in ('cluster_prim','cluster_area','cluster_count','cluster_per','cluster_radius','cluster_falloff','cluster_jitter','cluster_seed','cluster_normal','cluster_align','cluster_offset','cluster_info'):
        t=g.find(name);assert t is not None,name
        if name!='cluster_area':assert '{ mode != 7 }' in t.conditionals()[hou.parmCondType.HideWhen],name
    layout=[t for t in g.entries() if t.label()=='Layout'][0];names=[t.name() for t in layout.parmTemplates()];assert names.index('cluster_prim')>names.index('paint_prim')
    assert 'CLUSTER SETTINGS' in [t.columnLabels()[0] for t in layout.parmTemplates() if t.name().startswith('ui_head')]
    assert a.node('USD_COMPILER/DISTRIBUTION_GENERATOR').inputs()[7].name()=='generate_cluster'
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
        if name=='rows_stagger' and tuple(int(x) for x in VID[1:].split('.'))>=(1,18,0):continue       # v1.18.0: Stagger Rows became a 0 to 1 slider (the old tick meant 0.5), the one parameter whose type changed
        n=fn[name];assert n.type()==t.type() and n.numComponents()==t.numComponents(),name
        if hasattr(t,'defaultValue'):assert n.defaultValue()==t.defaultValue(),name
        if t.type()==hou.parmTemplateType.Menu:assert n.menuItems()[:len(t.menuItems())]==t.menuItems(),name
def defaults_unchanged():
    st,sc=new_scene('defaults')
    for values in (dict(mode=0,line_count=7),dict(mode=1,area_count=40,area_seed=3),dict(mode=5,surface_prim='/World/Ground',surface_count=50,surface_seed=2)):
        a=cl(st,sc,'n%d'%len(values),**values);b=cl(st,sc,'o%d'%len(values),typ=OLD_TYPE,**values);x,y=out(a),out(b)
        assert len(x['pos'])==len(y['pos'])>0 and np.array_equal(x['ids'],y['ids']) and np.allclose(x['pos'],y['pos'],atol=1e-6) and np.allclose(x['quat'],y['quat'],atol=2e-3)
def shapes():
    a,m=module();c,rf=m.cluster_shape(200,20,0.3,5);assert c.min()>=14 and c.max()<=26 and rf.min()>=0.7-1e-9 and rf.max()<=1.3+1e-9 and c.std()>1 and len(set(c.tolist()))>5
    c2,rf2=m.cluster_shape(200,20,0.3,5);assert np.array_equal(c,c2) and np.array_equal(rf,rf2)
    c3,rf3=m.cluster_shape(300,20,0.3,5);assert np.array_equal(c3[:200],c) and np.allclose(rf3[:200],rf)                    # more clusters never reshuffle the earlier ones
    c0,rf0=m.cluster_shape(50,20,0.0,5);assert np.all(c0==20) and np.allclose(rf0,1.0)
    cj,_=m.cluster_shape(50,5000,0.0,1);assert cj.max()==999                                                              # at most 999 members (the id stride)
    ids=np.arange(40000);ones=np.zeros(1)
    for fall,expected in ((0.0,2/3),(1.0,1/3),(0.5,1/(0.5+0.75+1))):                                                    # E[u^p] = 1/(p+1), p = 0.5 + 1.5 falloff
        r,ang=m.member_offsets(ids,1.0,fall,3);assert abs(r.mean()-expected)<0.01 and r.min()>=0 and r.max()<=1.0 and abs(ang.mean()-np.pi)<0.05,(fall,r.mean(),expected)
def flat_ground():
    st,sc=new_scene('flat');a=cl(st,sc,cluster_prim='',cluster_area=(10.0,10.0),cluster_count=8,cluster_per=30,cluster_radius=1.0,cluster_jitter=0.3,cluster_seed=4,cluster_align=0.0);m=a.hdaModule()
    d=out(a);ref=m.cluster_points(m.cluster_surface(a),8,30,1.0,0.5,0.3,4);P,N,ids,cn=ref
    order=np.argsort(d['ids']);got=d['pos'][order];want=P[np.argsort(ids)];assert len(d['pos'])==len(P)>100 and np.array_equal(d['ids'][order],np.sort(ids)) and np.allclose(got,want,atol=1e-5)
    assert np.allclose(d['pos'][:,1],0.0,atol=1e-6) and np.all(np.abs(d['pos'][:,[0,2]])<=5.0+1e-6) and np.allclose(d['quat'],[0,0,0,1],atol=2e-3)         # on the ground rectangle, upright (Align 0)
    # centres come from Surface Scatter's sampler; every member lies within its cluster's radius of its centre
    P0,T0,area,normals,vn=m.cluster_surface(a);centres,cnorm,_=m.surface_points(P0,T0,area,normals,vn,8,4,True,0.0,180.0,0.0,0.0);members,rf=m.cluster_shape(8,30,0.3,4)
    for c in range(8):
        sel=cn==c;assert abs(sel.sum()-members[c])<=members[c]*0.45+2                                                      # some members fall off the 10 x 10 rectangle at the edges
        assert np.all(np.linalg.norm(P[sel]-centres[c],axis=1)<=1.0*rf[c]+1e-6) and np.all(ids[sel]//1000==c) and len(set(ids[sel]))==sel.sum()
def stable_growth():
    st,sc=new_scene('grow');a=cl(st,sc,cluster_prim='',cluster_count=5,cluster_seed=2);d5=out(a);a.parm('cluster_count').set(9);d9=out(a)
    m5={int(i):p for i,p in zip(d5['ids'],d5['pos'])};m9={int(i):p for i,p in zip(d9['ids'],d9['pos'])}
    assert set(m5)<set(m9) and all(np.allclose(m5[i],m9[i],atol=1e-6) for i in m5)                                           # adding clusters leaves the first ones exactly as they were
    a.parm('cluster_count').set(5);a.parm('cluster_per').set(25);d=out(a);assert len(d['ids'])>len(d5['ids'])
    a.parm('cluster_seed').set(3);assert not np.array_equal(np.sort(out(a)['ids']),np.sort(d5['ids'])) or not np.allclose(np.sort(out(a)['pos'],axis=0),np.sort(d5['pos'],axis=0))
def falloff_shape():
    st,sc=new_scene('fall');a=cl(st,sc,cluster_prim='',cluster_area=(100.0,100.0),cluster_count=3,cluster_per=999,cluster_radius=2.0,cluster_jitter=0.0,cluster_seed=1);m=a.hdaModule()
    for fall,expected in ((0.0,2/3),(1.0,1/3)):
        a.parm('cluster_falloff').set(fall);P,N,ids,cn=m.cluster_points(m.cluster_surface(a),3,999,2.0,fall,0.0,1)
        P0,T0,area,normals,vn=m.cluster_surface(a);centres,_,_=m.surface_points(P0,T0,area,normals,vn,3,1,True,0.0,180.0,0.0,0.0)
        r=np.concatenate([np.linalg.norm(P[cn==c]-centres[c],axis=1) for c in range(3)])/2.0;assert abs(r.mean()-expected)<0.02,(fall,r.mean())
        d=out(a);assert len(d['ids'])==len(ids)
def on_surface():
    st,sc=new_scene('dome');a=cl(st,sc,cluster_prim='/World/Dome',cluster_count=6,cluster_per=40,cluster_radius=0.5,cluster_jitter=0.2,cluster_seed=3,cluster_normal=1);m=a.hdaModule();d=out(a);r=np.linalg.norm(d['pos'],axis=1)
    assert len(d['pos'])>150 and r.min()>1.9 and r.max()<=2.0+1e-5                                                         # on the (tessellated, inscribed) sphere
    quat=d['quat'];up=np.array([[2*(x*y-z*w),1-2*(x*x+z*z),2*(y*z+x*w)] for x,y,z,w in quat]);outward=d['pos']/r[:,None];assert np.all(np.einsum('ij,ij->i',up,outward)>0.95)       # Align 1: +Y onto the surface normal
    a.parm('cluster_align').set(0.0);assert np.allclose(out(a)['quat'],[0,0,0,1],atol=2e-3)
    a.parm('cluster_align').set(1.0);a.parm('cluster_offset').set(0.25);r2=np.linalg.norm(out(a)['pos'],axis=1);assert abs(np.median(r2-r)-0.25)<0.03
    a.parm('cluster_prim').set('/World/Nothing')
    try:a.cook(force=True);a.stage()
    except hou.OperationFailed:pass
    assert any('does not exist' in e for e in all_errors(a)) and 'Cannot read the surface' in a.parm('cluster_info').eval()
def integration():
    st,sc=new_scene('int');a=cl(st,sc,cluster_prim='',cluster_area=(10.0,10.0),cluster_count=10,cluster_per=60,cluster_radius=1.0,cluster_seed=7);full=out(a)
    a.parm('fields').set(1);a.parm('field_type1').set(0);a.parm('field_hmin1').set(-1.0);a.parm('field_hmax1').set(1.0);a.parm('field_hfall1').set(0.0)
    P=full['pos'];a.parm('field_type1').set(1);a.parm('field_prim1').set('/World/Ground')                                  # Slope field: flat ground is slope 0, all kept
    assert len(out(a)['ids'])==len(full['ids'])
    a.parm('field_type1').set(2);a.parm('field_nfreq1').set(0.8);a.parm('field_ncontrast1').set(3.0);thinned=out(a);assert 0.2*len(full['ids'])<len(thinned['ids'])<len(full['ids']) and set(thinned['ids'].tolist())<=set(full['ids'].tolist())
    a.parm('fields').set(0);a.parm('overlap_mode').set(1);a.parm('overlap_size').set(1);a.parm('overlap_radius').set(0.15);removed=out(a);assert 0<len(removed['ids'])<len(full['ids'])
    keep=set(removed['ids'].tolist());assert keep<=set(full['ids'].tolist())
    a.parm('overlap_mode').set(0);a.parm('grow_on').set(1);a.parm('grow_start').deleteAllKeyframes();a.parm('grow_start').set(1);a.parm('grow_sweep').set(10);a.parm('grow_time').set(5);hou.setFrame(40);assert len(out(a)['ids'])==len(full['ids']);hou.setFrame(1)   # Grow works on clusters too
def main():
    for name,func in (('UI contract: Cluster mode, parameters, Layout heading, switch input, every v0.7.0 parameter unchanged',ui_contract),
                      ('Modes 0, 1 and 5 identical to v0.7.0',defaults_unchanged),
                      ('Cluster shapes: member counts and radius factors, stable under more clusters, radial law',shapes),
                      ('Flat ground: centres from the Surface Scatter sampler, members inside their cluster radius, ids',flat_ground),
                      ('Adding clusters leaves the earlier ones untouched; members and seed change the result',stable_growth),
                      ('Falloff changes the radial distribution as predicted',falloff_shape),
                      ('Clusters on a curved surface: on it, aligned, offset, readable error for a missing prim',on_surface),
                      ('Field Stack, Separation and Grow work on clusters',integration)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_cluster_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
