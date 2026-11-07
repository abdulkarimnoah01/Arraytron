"""v1.33.0 in real Houdini: hython tests/validate_blast.py [version]
Blast (Scatter tab): an overall selection of instances (Id Pattern, Random, Region, Prototype), with Invert, that is deleted or transformed all together (move, rotate, scale about the selection centre, each instance,
the world origin or a custom pivot). Checked against independent numpy expectations from the same scatter with Blast off. Env ARRAYTRON_MUTATE=bl_invert|bl_pivot|bl_step|bl_region breaks the module;
the suite must FAIL."""
from pathlib import Path
import hou, json, os, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v1.33.0':'v1.32.0'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_blast_'));checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')
def write_scene():
    path=WORK/'blast.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    for name in ('Ball','Box'):UsdGeom.Xform.Define(s,'/World/Props/'+name);UsdGeom.Cube.Define(s,'/World/Props/%s/C'%name).CreateSizeAttr(0.2)
    s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True)
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
def node(stage,source,name='Bl',typ=None,protos=1,count=3000,**values):
    a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(protos);a.parm('proto_prim1').set('/World/Props/Ball')
    if protos>1:a.parm('proto_prim2').set('/World/Props/Box')
    a.parm('mode').set(1);a.parm('area_count').set(count);a.parm('area_sizex').set(20.0);a.parm('area_sizez').set(20.0)
    for k,v in values.items():
        pt=a.parmTuple(k)
        if pt is not None:pt.set(v if isinstance(v,(tuple,list)) else (v,))
        else:a.parm(k).set(v)
    if typ is None:mutate(a)
    return a
def all_errors(n):
    o=list(n.errors())
    for c in n.children():o+=all_errors(c)
    return o
def out(a):
    a.stage();errs=all_errors(a);assert not errs,errs;pi=UsdGeom.PointInstancer(a.stage().GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    ids=np.array(pi.GetIdsAttr().Get(t) or [],dtype=int);pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3);sc=np.array(pi.GetScalesAttr().Get(t) or []).reshape(-1,3)
    q=pi.GetOrientationsAttr().Get(t) or [];orient=np.array([[x.GetImaginary()[0],x.GetImaginary()[1],x.GetImaginary()[2],x.GetReal()] for x in q]).reshape(-1,4);pr=np.array(pi.GetProtoIndicesAttr().Get(t) or [],dtype=int)
    o=np.argsort(ids);return dict(ids=ids[o],pos=pos[o],scale=sc[o],orient=orient[o],proto=pr[o])
def mutate(a):
    g=a.hdaModule().select_ids.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='bl_invert':
        good=g['sop_blast'];g['sop_blast']=lambda geo,asset:(asset.parm('blast_invert').set(0),good(geo,asset))[1]                                                                          # Invert ignored
    elif MUTATE=='bl_pivot':
        good=g['transform_group'];g['transform_group']=lambda P,o,s,sel,mv,rot,u,pm,pv:good(P,o,s,sel,mv,rot,u,2,pv)                                                                      # always the world origin
    elif MUTATE=='bl_step':
        good=g['parse_ids'];g['parse_ids']=lambda text:(lambda r:(r[0],[(lo,hi,1) for lo,hi,st in r[1]],r[2]))(good(text))                                                                 # the step of a range is ignored
    elif MUTATE=='bl_region':
        good=g['select_region'];g['select_region']=lambda P,shape,c,size:good(P,1-shape,c,size)                                                                                           # sphere and box swapped
    elif MUTATE:raise SystemExit('unknown mutation '+MUTATE)
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()

def pure():
    st,sc=new_scene('pure');a=node(st,sc);m=a.hdaModule();ids=np.arange(200)
    assert m.select_ids(ids,'0-9').sum()==10 and list(np.nonzero(m.select_ids(ids,'5-20:5'))[0])==[5,10,15,20] and list(np.nonzero(m.select_ids(ids,'3 7, 9'))[0])==[3,7,9] and m.select_ids(ids,'*').all()
    assert list(np.nonzero(m.select_ids(ids,'-3--1 4'))[0])==[4]                                                                                  # no negative ids exist: nothing but 4 (the pattern is still read)
    P=np.random.default_rng(3).uniform(-5,5,(500,3));c=(1.0,0.0,-1.0);sphere=m.select_region(P,0,c,(2.5,0,0));box=m.select_region(P,1,c,(4.0,6.0,3.0))
    assert (sphere==(np.linalg.norm(P-np.array(c),axis=1)<=2.5)).all() and (box==((np.abs(P[:,0]-1)<=2)&(np.abs(P[:,1])<=3)&(np.abs(P[:,2]+1)<=1.5))).all()
    R=m.quat_to_matrix(m.euler_to_quat((0,90,0)));assert np.allclose(R@np.array([1.0,0,0]),[0,0,-1],atol=1e-9)                                     # 90 degrees about Y takes +X to -Z
    P=np.random.default_rng(4).uniform(-3,3,(40,3));q=np.tile([0,0,0,1.0],(40,1));s=np.ones((40,3));sel=np.arange(40)<25
    P2,q2,s2=m.transform_group(P,q,s,sel,(1,2,3),(0,90,0),2.0,0,None);cen=P[sel].mean(axis=0);want=cen+2.0*(P[sel]-cen)@R.T+np.array([1,2,3])
    assert np.allclose(P2[sel],want) and np.allclose(P2[~sel],P[~sel]) and np.allclose(s2[sel],2.0) and np.allclose(s2[~sel],1.0) and np.allclose(m.quat_to_matrix(q2[sel][0]),R)
    P3,_,s3=m.transform_group(P,q,s,sel,(1,0,0),(0,0,0),3.0,1,None);assert np.allclose(P3[sel],P[sel]+[1,0,0]) and np.allclose(s3[sel],3.0)                  # each instance: only the shared move
    P4,_,_=m.transform_group(P,q,s,sel,(0,0,0),(0,90,0),1.0,3,(5,0,5));assert np.allclose(P4[sel],np.array([5,0,5])+(P[sel]-[5,0,5])@R.T)

def delete_ids():
    st,sc=new_scene('del');ref=node(st,sc,name='Ref');base=out(ref);n=len(base['ids']);assert n==3000 and (base['ids']==np.arange(3000)).all()
    a=node(st,sc,name='Del',blast_on=1,blast_select=0,blast_ids='0-99 500 1000-1100:10',blast_action=0);o=out(a);gone=set(range(100))|{500}|set(range(1000,1101,10))
    assert set(o['ids'])==set(range(3000))-gone and len(o['ids'])==n-len(gone),(len(o['ids']),n-len(gone))
    keep=np.isin(base['ids'],o['ids']);assert np.allclose(o['pos'],base['pos'][keep],atol=1e-5) and (o['ids']==base['ids'][keep]).all()                         # the survivors are untouched, ids included
    inv=node(st,sc,name='Inv',blast_on=1,blast_select=0,blast_ids='0-99 500 1000-1100:10',blast_action=0,blast_invert=1);oi=out(inv);assert set(oi['ids'])==gone,(len(oi['ids']),len(gone))
    assert '%d of %d'%(len(gone),n) in a.hdaModule().blast_info(a) and 'inverted' in inv.hdaModule().blast_info(inv)

def random_pick():
    st,sc=new_scene('rand');a=node(st,sc,name='R',blast_on=1,blast_select=1,blast_random=30.0,blast_seed=3,blast_action=0);o=out(a);gone=3000-len(o['ids'])
    assert abs(gone/3000-0.30)<0.03,gone
    b=node(st,sc,name='R2',blast_on=1,blast_select=1,blast_random=30.0,blast_seed=3,blast_action=0);assert (out(b)['ids']==o['ids']).all()                          # the same instances every time
    c=node(st,sc,name='R3',blast_on=1,blast_select=1,blast_random=30.0,blast_seed=4,blast_action=0);assert not np.array_equal(out(c)['ids'],o['ids'])             # another seed picks others
    big=node(st,sc,name='R4',count=4500,blast_on=1,blast_select=1,blast_random=30.0,blast_seed=3,blast_action=0);ob=out(big)
    assert np.isin(o['ids'],ob['ids']).sum()>=len(o['ids'])-10,'the earlier choices must not reshuffle'

def region():
    st,sc=new_scene('region');ref=node(st,sc,name='Ref');base=out(ref)
    s=node(st,sc,name='S',blast_on=1,blast_select=2,blast_shape=0,blast_center=(2.0,0.0,-3.0),blast_radius=4.0,blast_action=0);o=out(s);d=np.linalg.norm(o['pos']-np.array([2.0,0.0,-3.0]),axis=1)
    assert d.min()>4.0-1e-4 and len(o['ids'])==int((np.linalg.norm(base['pos']-np.array([2.0,0.0,-3.0]),axis=1)>4.0).sum())
    b=node(st,sc,name='B',blast_on=1,blast_select=2,blast_shape=1,blast_center=(0.0,0.0,0.0),blast_size=(6.0,2.0,4.0),blast_action=0,blast_invert=1);ob=out(b)
    assert (np.abs(ob['pos'][:,0])<=3+1e-4).all() and (np.abs(ob['pos'][:,2])<=2+1e-4).all() and len(ob['ids'])>100                                          # the inverted box keeps only what is inside

def prototype():
    st,sc=new_scene('proto');ref=node(st,sc,name='Ref',protos=2);base=out(ref);assert set(base['proto'])=={0,1}
    a=node(st,sc,name='P',protos=2,blast_on=1,blast_select=3,blast_proto=2,blast_action=0);o=out(a);assert len(o['ids'])==int((base['proto']==0).sum()) and (o['proto']==0).all()

def transform():
    st,sc=new_scene('xf');ref=node(st,sc,name='Ref');base=out(ref);sel=base['ids']<1000
    a=node(st,sc,name='T',blast_on=1,blast_select=0,blast_ids='0-999',blast_action=1,blast_move=(1.0,0.5,-2.0),blast_rot=(0.0,90.0,0.0),blast_scale=2.0,blast_pivot=0);o=out(a)
    m=a.hdaModule();P,q,s=m.transform_group(base['pos'],base['orient'],base['scale'],sel,(1.0,0.5,-2.0),(0.0,90.0,0.0),2.0,0,None)
    assert (o['ids']==base['ids']).all() and np.allclose(o['pos'],P,atol=1e-3) and np.allclose(o['scale'],s,atol=1e-4)
    dots=np.abs((o['orient']*q).sum(axis=1));assert (dots>1-2e-3).all(),dots.min()                                                                 # the same rotation up to the sign of the quaternion (USD keeps half floats)
    assert np.allclose(o['pos'][~sel],base['pos'][~sel]) and np.allclose(o['scale'][~sel],base['scale'][~sel])                                      # the rest is untouched
    cen=base['pos'][sel].mean(axis=0);assert np.allclose(o['pos'][sel].mean(axis=0),cen+np.array([1.0,0.5,-2.0]),atol=1e-3)                          # a rotation and a scale about the centre keep the centre; only the move shifts it
    each=node(st,sc,name='E',blast_on=1,blast_select=0,blast_ids='0-999',blast_action=1,blast_move=(0.0,3.0,0.0),blast_rot=(0.0,0.0,0.0),blast_scale=0.5,blast_pivot=1);oe=out(each)
    assert np.allclose(oe['pos'][sel],base['pos'][sel]+[0,3,0],atol=1e-3) and np.allclose(oe['scale'][sel],base['scale'][sel]*0.5,atol=1e-4)
    inv=node(st,sc,name='I',blast_on=1,blast_select=0,blast_ids='0-999',blast_invert=1,blast_action=1,blast_move=(0.0,3.0,0.0),blast_pivot=1);oi=out(inv)
    assert np.allclose(oi['pos'][~sel],base['pos'][~sel]+[0,3,0],atol=1e-3) and np.allclose(oi['pos'][sel],base['pos'][sel])

def off_and_interface():
    st,sc=new_scene('ui');a=node(st,sc,name='Off');old=node(st,sc,name='Old',typ=OLD_TYPE);o,p=out(a),out(old)
    assert (o['ids']==p['ids']).all() and np.allclose(o['pos'],p['pos'],atol=1e-5) and 'off' in a.hdaModule().blast_info(a)                                  # Blast off is the previous release
    g=a.parmTemplateGroup();tab=[t for t in g.entries() if t.label()=='Scatter'][0];names=[x.name() for x in tab.parmTemplates()]
    assert names.index('blast_on')>names.index('fall_on')>names.index('fields') and 'blast_on' not in [x.name() for t in g.entries() if t.label()=='Variation' for x in t.parmTemplates()]
    for k in ('blast_select','blast_ids','blast_random','blast_seed','blast_shape','blast_center','blast_radius','blast_size','blast_proto','blast_invert','blast_action','blast_move','blast_rot','blast_scale','blast_pivot','blast_pivotpos','blast_info'):assert k in names,k
    assert a.node('USD_COMPILER/BLAST') is not None and [c.name() for c in a.node('USD_COMPILER/OVERRIDES').inputs()]==['BLAST']                           # it runs just before the Override Database

for n,f in (('selection and transform functions against numpy',pure),('Delete by id pattern, and Invert',delete_ids),('Random: the share, repeatable, stable when points are added',random_pick),
            ('Region: sphere and inverted box',region),('Prototype: the instances of one row',prototype),('Transform all together: pivots, Invert, the rest untouched',transform),
            ('Blast off is the previous release; the section sits after the Falloff in the Scatter tab, before the overrides',off_and_interface)):check(n,f)
result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
if not MUTATE:(ROOT/'tests'/('validation_blast_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
print('ALL PASSED %d'%len(checks));print(json.dumps(checks))
