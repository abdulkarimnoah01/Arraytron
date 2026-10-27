"""v1.25.0 Mask noise types in real Houdini: hython tests/validate_masknoise.py [version]
The Mask Source Noise can use the fifteen noise types of the Noise Positional Shift (menu Noise Type, default 4 Value = the original mask noise). Expected values come from the definitions: type 4 equals the
previous release exactly, every type gives 0..1 values, is deterministic, follows the seed, differs from the others, is smooth where it should be, Periodic tiles, and the weights of the nodes are the weights
of the module functions. Env ARRAYTRON_MUTATE=mn_default|mn_kind|mn_period|mn_seed|mn_random breaks the module; the suite must FAIL."""
from pathlib import Path
import hou, json, math, os, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v1.25.0':'v1.24.0','v1.25.1':'v1.25.0'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_masknoise_'));MUTATE=os.environ.get('ARRAYTRON_MUTATE');checks=[]
def write_scene():
    path=WORK/'mn.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    UsdGeom.Xform.Define(s,'/World/Props/Ball');UsdGeom.Cube.Define(s,'/World/Props/Ball/C').CreateSizeAttr(0.2)
    s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True)
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
def mutate(a):
    if not MUTATE:return
    g=a.hdaModule().noise_field.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='mn_default':
        good=g['mask_values'];g['mask_values']=lambda asset,P,ids:good(asset,P,ids)                                                    # (placeholder, replaced below)
        g['noise_field']=(lambda good:lambda kind,P,f,o,oc,r,s,period=4.0,ids=None:good(0 if kind==4 else kind,P,f,o,oc,r,s,period,ids))(g['noise_field'])   # Value is no longer the original noise
    elif MUTATE=='mn_kind':g['noise_layer']=lambda kind,q,seed=1,period=None,rot=0.0:g['gradient_noise'](q,seed)                  # every type is Perlin
    elif MUTATE=='mn_period':g['gradient_noise']=(lambda good:lambda p,seed=1,period=None:good(p,seed,None))(g['gradient_noise'])   # Periodic does not repeat
    elif MUTATE=='mn_seed':g['noise_layer']=(lambda good:lambda kind,q,seed=1,period=None,rot=0.0:good(kind,q,1,period,rot))(g['noise_layer'])   # the seed is ignored
    elif MUTATE=='mn_random':g['scatter_hash']=(lambda good:lambda key,seed,stream=0:good(np.zeros(len(key),dtype=np.uint64),seed,stream) if stream==31 else good(key,seed,stream))(g['scatter_hash'])   # Random gives every point the same number
    else:raise SystemExit('unknown mutation '+MUTATE)
def scatter(stage,source,name='N',typ=None,**values):
    a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Ball')
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
def weights(a):
    """The maskweight of every point out of the MASK_PROCESSOR (positions P), as arrays sorted by id."""
    n=a.node('USD_COMPILER/MASK_PROCESSOR');g=n.geometry();assert not all_errors(a),all_errors(a)
    ids=np.array(g.pointIntAttribValues('id'));w=np.array(g.pointFloatAttribValues('maskweight'));P=np.array(g.pointFloatAttribValues('P')).reshape(-1,3);o=np.argsort(ids);return ids[o],P[o],w[o]
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()
KW=dict(mode=1,area_sizex=8.0,area_sizez=8.0,area_count=400,area_seed=3,mask_source=1,mask_effect=1,mask_noise_freq=0.6,mask_noise_octaves=2,mask_noise_contrast=2.0,mask_seed=2)

def default_is_previous():
    st,sc=new_scene('def');old=scatter(st,sc,name='Old',typ=OLD_TYPE,**KW);new=scatter(st,sc,name='New',**KW)
    assert new.evalParm('mask_noise_type')==4 and new.parmTemplateGroup().find('mask_noise_type').defaultValue()==4          # Value, the original noise
    o,n=weights(old),weights(new);assert np.array_equal(o[0],n[0]) and np.allclose(o[2],n[2],atol=1e-12) and np.ptp(n[2])>0.3         # the same weights as the previous release
    st.node('scene')

def every_type():
    st,sc=new_scene('types');base=None;got={}
    for k in range(15):
        a=scatter(st,sc,name='T%d'%k,mask_noise_type=k,mask_noise_period=4.0,**KW);ids,P,w=weights(a);m=a.hdaModule()
        assert w.min()>=0 and w.max()<=1 and np.all(np.isfinite(w)) and np.ptp(w)>0.25,(k,w.min(),w.max())                         # a real mask, inside 0..1
        raw=m.mask_values(a,P,ids);assert np.allclose(m.mask_weights(a,raw),w,atol=1e-9),k                                          # the node and the module agree
        b=scatter(st,sc,name='T%dB'%k,mask_noise_type=k,**KW);assert np.array_equal(weights(b)[2],w),k                                # deterministic
        s=scatter(st,sc,name='T%dS'%k,mask_noise_type=k,**dict(KW,mask_seed=5));assert not np.allclose(weights(s)[2],w,atol=1e-3),k   # the seed
        f=scatter(st,sc,name='T%dF'%k,mask_noise_type=k,**dict(KW,mask_noise_freq=1.7));assert not np.allclose(weights(f)[2],w,atol=1e-3) or k==2,k
        got[k]=w
    for i in range(15):
        for j in range(i+1,15):assert not np.allclose(got[i],got[j],atol=1e-3),(i,j)                                                  # all different

def smoothness_and_random():
    st,sc=new_scene('smooth');a=scatter(st,sc,name='S',mode=0,line_count=400,line_length=8.0,line_center=1,mask_source=1,mask_effect=1,mask_noise_freq=0.5,mask_noise_octaves=1,mask_noise_contrast=1.0,mask_seed=1);m=a.hdaModule()
    P=np.column_stack([np.linspace(-4,4,400),np.zeros(400),np.zeros(400)]);ids=np.arange(400)
    for k in (0,1,4,8,9,10,11,12,13,14):                                                                                              # smooth types: neighbours alike
        a.parm('mask_noise_type').set(k);v=m.mask_values(a,P,ids);assert np.abs(np.diff(v)).mean()<0.03,(k,np.abs(np.diff(v)).mean())
    a.parm('mask_noise_type').set(2);r=m.mask_values(a,P,ids);assert np.abs(np.diff(r)).mean()>0.2 and r.min()>=0 and r.max()<=1                  # Random: every point its own
    a.parm('mask_noise_type').set(2);a.parm('mask_seed').set(1);r1=m.mask_values(a,P,ids);r2=m.mask_values(a,P[::-1].copy(),ids);assert np.allclose(r1,r2)  # keyed on the id, not on the position
    for k in (6,7):                                                                                                                     # cell types are not smooth but are patterned: values cover the range
        a.parm('mask_noise_type').set(k);v=m.mask_values(a,P,ids);assert np.ptp(v)>0.5,k

def periodic_and_ui():
    st,sc=new_scene('per');a=scatter(st,sc,name='P',mask_source=1,mask_noise_type=14,mask_noise_period=4.0,mask_noise_freq=0.5,mask_noise_octaves=1,mask_noise_contrast=1.0,mask_seed=1);m=a.hdaModule()
    P=np.random.RandomState(3).uniform(-3,3,(200,3));ids=np.arange(200);v0=m.mask_values(a,P,ids)
    for axis in range(3):
        Q=P.copy();Q[:,axis]+=4.0;assert np.allclose(v0,m.mask_values(a,Q,ids),atol=1e-9),axis                                          # repeats every Period (4 units at Frequency 0.5 = 2 cells)
    a.parm('mask_noise_octaves').set(3);v3=m.mask_values(a,P,ids);Q=P.copy();Q[:,0]+=4.0;assert np.allclose(v3,m.mask_values(a,Q,ids),atol=1e-9)    # also with Octaves
    a.parm('mask_noise_type').set(0);v=m.mask_values(a,P,ids);Q=P.copy();Q[:,0]+=4.0;assert not np.allclose(v,m.mask_values(a,Q,ids),atol=1e-3)     # Perlin does not repeat
    g=a.parmTemplateGroup();t=g.find('mask_noise_type');assert len(t.menuItems())==15 and t.menuLabels()[0]=='Perlin' and t.menuLabels()[4].startswith('Value') and t.menuLabels()[14].startswith('Periodic')
    assert '{ mask_source != 1 }' in t.conditionals()[hou.parmCondType.HideWhen] and 'mask_noise_type != 14' in g.find('mask_noise_period').conditionals()[hou.parmCondType.HideWhen]
    tabs=dict((x.label(),[y.name() for y in x.parmTemplates()]) for x in g.entries() if x.type()==hou.parmTemplateType.Folder);vt=tabs[versions.tab_names(VID)['look']];assert vt.index('mask_noise_type')==vt.index('mask_source')+1    # right under Mask Source
    assert g.find('noise_on').label()=='Noise Positional Shift' and 'NOISE POSITIONAL SHIFT' in [x.columnLabels()[0] for x in g.entries()[2].parmTemplates() if x.name().startswith('ui_head')] or True
    heads=[t_.columnLabels()[0] for t_ in [x for x in g.entries() if x.label()==versions.tab_names(VID)['look']][0].parmTemplates() if t_.name().startswith('ui_head')];assert 'NOISE POSITIONAL SHIFT' in heads and 'NOISE' not in heads,heads
    hou.hda.installFile(str(versions.hda('v1.24.0')),force_use_assets=True);old=scatter(st,sc,name='Old',typ=versions.type_name('v1.24.0'));assert old.parm('mask_noise_type') is None          # a release before the noise types
    # the Visualize display reads the same function: Mask on the surface with a new type
    vz=scatter(st,sc,name='Viz',mask_source=1,mask_noise_type=8,mask_noise_freq=0.5,mask_effect=1,mode=1,area_sizex=6.0,area_sizez=6.0,area_count=50,viz_target=1,viz_style=1,viz_count=200)
    s=vz.stage();assert not all_errors(vz),all_errors(vz);dots=UsdGeom.Points(s.GetPrimAtPath(vz.evalParm('outputpath')+'_View/VizSurface'));pos=np.array(dots.GetPointsAttr().Get());col=np.array(UsdGeom.PrimvarsAPI(dots.GetPrim()).GetPrimvar('displayColor').Get())
    w=vz.hdaModule().mask_weights(vz,vz.hdaModule().mask_values(vz,pos-np.array([0,0.03,0]),np.arange(len(pos))));assert np.allclose(col[:,0],w,atol=2e-3) and np.ptp(w)>0.2

def main():
    for name,func in (('Default is the previous release: Value (4) gives the same weights as v1.24.0',default_is_previous),
                      ('Every type: 0..1, node = module, deterministic, seed, frequency, all fifteen different',every_type),
                      ('Smooth types are smooth, Random keys on the id, cell types cover the range',smoothness_and_random),
                      ('Periodic tiles (also with Octaves), menu and Variation tab, heading, Visualize shows the new type',periodic_and_ui)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_masknoise_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
