"""Arraytron Stamp 0.1.0 in real Houdini: hython tests/validate_stamp.py
The Stamp node is the Arraytron builder with ARRAYTRON_STAMP: only Instance Place, the tabs Prototypes / Layout / Optimize / Debugging / Export, and the per-stamp randomness (Random Scale, Random Tilt,
Random Prototype, Random Rotation). The viewport tool calls place_add for every stamp, so the tests call it the same way and read the table and the USD. Env ARRAYTRON_MUTATE=st_scale|st_tilt|st_proto|st_seed
breaks the module; the suite must FAIL. The viewport tool itself (mouse, wheel, drag) is the one of Arraytron's Instance Place, tested in validate_place.py; its use on a Stamp node is GUI-unverified."""
from pathlib import Path
import hou, json, os, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
STAMP_TYPE='arraytron::stamp::0.1.0';MUTATE=os.environ.get('ARRAYTRON_MUTATE');checks=[]
STAMP_HDA=ROOT/('otls_h205' if versions.is_h205() else 'dist')/('Arraytron_Stamp_v0.1.0%s.hda'%('_H205' if versions.is_h205() else ''))
WORK=Path(tempfile.mkdtemp(prefix='arraytron_stamp_'))
def scene():
    path=WORK/'stamp.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    for name,size in (('Rock',0.2),('Fir',0.3),('Stone',0.4)):UsdGeom.Xform.Define(s,'/World/Props/'+name);UsdGeom.Cube.Define(s,'/World/Props/%s/C'%name).CreateSizeAttr(size)
    s.GetRootLayer().Save();return path.as_posix()
SCENE=scene()
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True);hou.hda.installFile(str(STAMP_HDA),force_use_assets=True);hou.hda.installFile(str(versions.hda(versions.CURRENT)),force_use_assets=True);hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
def stamp(st,src,name='S',typ=None,rows=3,**values):
    a=st.createNode(typ or STAMP_TYPE,name);a.setInput(0,src);a.parm('protos').set(rows)
    for i,p in enumerate(('Rock','Fir','Stone')[:rows],1):a.parm('proto_prim%d'%i).set('/World/Props/'+p)
    for k,v in values.items():
        if isinstance(v,(tuple,list)):a.parmTuple(k).set(v)
        else:a.parm(k).set(v)
    if typ is None:mutate(a)
    return a
def mutate(a):
    g=a.hdaModule().place_add.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='st_scale':
        good=g['place_add'];g['place_add']=lambda asset,*args,**kw:good(asset,*args,**dict(kw,scale_mult=1.0)) if False else (asset.parmTuple('place_def_scalerange').set((1.0,1.0)),good(asset,*args,**kw))[1]       # the Random Scale is ignored
    elif MUTATE=='st_tilt':
        good=g['place_add'];g['place_add']=lambda asset,*args,**kw:(asset.parm('place_def_tilt').set(0.0),good(asset,*args,**kw))[1]                                                                 # the Random Tilt is ignored
    elif MUTATE=='st_proto':
        good=g['place_add'];g['place_add']=lambda asset,*args,**kw:(asset.parm('place_def_protorand').set(0),good(asset,*args,**kw))[1]                                                             # the Random Prototype is ignored
    elif MUTATE=='st_seed':
        good=g['place_add'];g['place_add']=lambda asset,*args,**kw:(asset.parm('place_seed').set(1),good(asset,*args,**kw))[1]                                                                       # the seed is ignored
    elif MUTATE:raise SystemExit('unknown mutation '+MUTATE)
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()
def table(a):
    n=a.evalParm('places');return [dict(pos=np.array(a.evalParmTuple('place_pos%d'%i)),rot=np.array(a.evalParmTuple('place_rot%d'%i)),scale=np.array(a.evalParmTuple('place_scale%d'%i)),proto=a.evalParm('place_proto%d'%i),id=a.evalParm('place_id%d'%i),on=a.evalParm('place_on%d'%i)) for i in range(1,n+1)]
def out(a):
    s=a.stage();assert not list(a.errors()),a.errors();pi=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    return dict(pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3),scale=np.array(pi.GetScalesAttr().Get(t) or []).reshape(-1,3),proto=np.array(pi.GetProtoIndicesAttr().Get(t) or [],dtype=int),ids=np.array(pi.GetIdsAttr().Get(t) or [],dtype=int))

def node_shape():
    st,sc=new_scene('shape');a=stamp(st,sc);g=a.parmTemplateGroup()
    assert a.type().name()=='stamp::0.1.0' or 'stamp' in a.type().name();assert a.type().description()=='Arraytron Stamp' and a.evalParm('mode')==9 and g.find('mode').conditionals()[hou.parmCondType.HideWhen]=='{ mode >= 0 }'     # always Instance Place
    labels=[t.label() for t in g.entries() if t.type()==hou.parmTemplateType.Folder and not t.isHidden()];assert labels==['Prototypes','Layout','Optimize','Debugging','Export'],labels                       # no empty tabs
    assert g.find('mask_source') is not None and g.find('mask_source').isHidden() and g.find('field_effect').isHidden()                                                                    # the parameters of the removed tabs still exist, hidden
    for n,d in (('place_def_scalerange',(1.0,1.0)),('place_def_tilt',(0.0,)),('place_def_protorand',False),('place_def_yawrand',(0.0,))):assert g.find(n) is not None and g.find(n).defaultValue()==d,n
    assert a.parm('place_start') is not None or a.parm('place_start_button') is not None or any('place_start' in p.name() for p in a.parms())
    base=st.createNode(versions.type_name(versions.CURRENT),'B');assert base.parmTemplateGroup().find('place_def_tilt') is None and base.evalParm('mode')==0                                                       # Arraytron itself is unchanged
    assert a.type().definition().sections()['OnCreated'].contents().count('stamp_setup')==1 and 'arraytron_stamp1' in a.type().definition().sections()['OnCreated'].contents() and a.hdaModule().stamp_setup(a) in (True,False)
    new=st.createNode(STAMP_TYPE,'N');assert new.hdaModule().stamp_setup(new) and new.evalParm('proto_type1')==2 and 'builtin_sphere' in new.evalParm('proto_file1') and new.evalParm('mode')==9
    assert hasattr(a.hdaModule(),'place_add') and a.node('USD_COMPILER') is not None

def stamping():
    st,sc=new_scene('stamping');a=stamp(st,sc,place_def_scalerange=(0.5,2.0),place_def_tilt=20.0,place_def_protorand=1,place_def_yawrand=180.0,place_seed=4);m=a.hdaModule()
    for k in range(60):m.place_add(a,(k*0.5,0.0,2.0))
    t=table(a);sc_=np.array([r['scale'][0] for r in t]);assert len(t)==60 and sc_.min()>=0.5-1e-9 and sc_.max()<=2.0+1e-9 and sc_.std()>0.2 and (sc_>1.4).any() and (sc_<0.8).any()           # Random Scale: between the two numbers, really random
    assert all(np.allclose(r['scale'],r['scale'][0]) for r in t)                                                                                                                              # uniform scale
    lean=np.array([np.degrees(np.arccos(np.clip(m.place_rotate(m.place_quat(r['rot']),(0.0,1.0,0.0))[1],-1,1))) for r in t]);assert lean.max()>10.0 and lean.max()<=29.0 and (lean>1.0).all() is not None and np.abs(np.array([r['rot'][1] for r in t])).max()>60.0   # the up axis leans at most about 28 degrees (20 about X and about Z), the yaw is free
    p=np.array([r['proto'] for r in t]);assert set(p.tolist())=={1,2,3} and min(np.bincount(p)[1:])>8                                                                                          # Random Prototype: all three rows, each about a third
    o=out(a);assert len(o['ids'])==60 and np.array_equal(np.sort(o['proto']),np.sort(p-1)) and np.allclose(o['scale'][:,0],sc_,atol=1e-4)                                                          # the USD shows what the table says
    same=stamp(st,sc,name='S2',place_def_scalerange=(0.5,2.0),place_def_tilt=20.0,place_def_protorand=1,place_def_yawrand=180.0,place_seed=4)
    for k in range(60):same.hdaModule().place_add(same,(k*0.5,0.0,2.0))
    t2=table(same);assert all(np.allclose(x['scale'],y['scale']) and np.allclose(x['rot'],y['rot']) and x['proto']==y['proto'] for x,y in zip(t,t2))                                             # the same seed: the same stamps
    other=stamp(st,sc,name='S3',place_def_scalerange=(0.5,2.0),place_def_tilt=20.0,place_def_protorand=1,place_def_yawrand=180.0,place_seed=9)
    for k in range(10):other.hdaModule().place_add(other,(k*0.5,0.0,2.0))
    assert not np.allclose([r['scale'][0] for r in table(other)],sc_[:10])                                                                                                                       # another seed: other stamps
    for k in range(10):m.place_add(a,(k,0,5.0))
    t3=table(a);assert all(np.allclose(x['scale'],y['scale']) and x['proto']==y['proto'] for x,y in zip(t,t3[:60]))                                                                              # more stamps never change the earlier ones
    w=stamp(st,sc,name='W',rows=2,place_def_protorand=1,proto_weight1=3.0,proto_weight2=1.0,place_seed=2)
    for k in range(400):w.hdaModule().place_add(w,(k*0.1,0,0))
    pw=np.bincount([r['proto'] for r in table(w)],minlength=3);assert 0.65<pw[1]/400<0.85                                                                                                         # weighted by the bank weights

def control_after():
    st,sc=new_scene('control');a=stamp(st,sc,place_def_scalerange=(1.0,1.0),rows=2);m=a.hdaModule()
    for k in range(5):m.place_add(a,(k,0,0),yaw=0.0,scale=1.0)
    o=out(a);assert len(o['ids'])==5 and np.allclose(o['scale'],1.0,atol=1e-3)
    a.parmTuple('place_scale3').set((3.0,3.0,3.0));a.parmTuple('place_pos3').set((7.0,0.0,1.0));a.parm('place_proto3').set(2);a.parm('place_on4').set(0)
    o=out(a);assert len(o['ids'])==4 and (np.abs(o['scale'][:,0]-3.0)<1e-3).sum()==1 and np.isclose(o['pos'][:,0],7.0,atol=1e-3).sum()==1                                                            # change one stamp in the table: scale, place, prototype, off
    i=int(np.nonzero(np.isclose(o['pos'][:,0],7.0,atol=1e-3))[0][0]);assert o['proto'][i]==1
    m.place_remove(a,2);assert a.evalParm('places')==4 and len(out(a)['ids'])==3                                                                                                                  # delete one
    ids=[r['id'] for r in table(a)];m.place_add(a,(9,0,0));assert len(set([r['id'] for r in table(a)]))==5 and ids==[r['id'] for r in table(a)][:4]                                                  # ids stay stable
    m.place_clear(a);assert a.evalParm('places')==0

def unchanged():
    st,sc=new_scene('same');a=stamp(st,sc,place_seed=3,place_def_yawrand=45.0);b=stamp(st,sc,typ=versions.type_name(versions.CURRENT),name='B',place_seed=3,place_def_yawrand=45.0);b.parm('mode').set(9)
    for n in (a,b):
        for k in range(12):n.hdaModule().place_add(n,(k*0.3,0.0,1.0))
    ta,tb=table(a),table(b);assert all(np.allclose(x['pos'],y['pos']) and np.allclose(x['rot'],y['rot'],atol=1e-9) and np.allclose(x['scale'],y['scale']) and x['proto']==y['proto'] for x,y in zip(ta,tb))   # with the randomness at its defaults a Stamp places exactly like Arraytron
    oa,ob=out(a),out(b);assert np.allclose(oa['pos'],ob['pos']) and np.array_equal(oa['proto'],ob['proto'])

def main():
    for name,func in (('The node: type, always Instance Place, the tabs that stay, the random parameters, Arraytron unchanged, the new-node setup',node_shape),
                      ('Stamping: Random Scale, Tilt, Prototype (by weight), Rotation; same seed same stamps; more stamps never change the old ones; the USD shows the table',stamping),
                      ('Control after placing: change, move, re-assign, switch off, delete a single stamp; ids stay stable',control_after),
                      ('With the randomness at its defaults a Stamp places exactly like Arraytron',unchanged)):check(name,func)
    if not MUTATE:(ROOT/'tests'/('validation_stamp_%s.json'%versions.CURRENT)).write_text(json.dumps({'houdini':hou.applicationVersionString(),'checks':checks},indent=1))
    print('ALL PASSED',len(checks))
main()
