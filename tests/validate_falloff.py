"""v1.12.0 Falloff in real Houdini: hython tests/validate_falloff.py [version]
The Layout tab FALLOFF: the scatter is full size and densest in the centre and fades towards the edges (scale and density), for every Distribution Mode. Expected values come from independent
re-implementations of the curves and of the distance (the survival of a point uses the same id-keyed hash as the Mask, so it is checked statistically and as a subset). Env
ARRAYTRON_MUTATE=fall_curve|fall_scale|fall_density|fall_shape|fall_axes|fall_inner breaks the module; the suite must FAIL."""
from pathlib import Path
import hou, json, math, os, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v1.12.0':'v1.11.0'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_falloff_'));checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')
def write_scene():
    path=WORK/'falloff.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    UsdGeom.Xform.Define(s,'/World/Props/Ball');UsdGeom.Cube.Define(s,'/World/Props/Ball/C').CreateSizeAttr(0.2)
    g=UsdGeom.Mesh.Define(s,'/World/Ground');g.CreatePointsAttr([(-10,0,10),(10,0,10),(10,0,-10),(-10,0,-10)]);g.CreateFaceVertexCountsAttr([4]);g.CreateFaceVertexIndicesAttr([0,1,2,3]);g.CreateOrientationAttr('rightHanded')
    s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True)
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
def scatter(stage,source,name='Fall',typ=None,**values):
    a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Ball')
    for k,v in values.items():
        pt=a.parmTuple(k)
        if pt is not None:pt.set(v if isinstance(v,(tuple,list)) else (v,))
        else:a.parm(k).set(v)
    if typ is None:mutate(a)
    return a
def out(a):
    s=a.stage();assert not all_errors(a),all_errors(a);pi=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    return dict(pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3),ids=np.array(pi.GetIdsAttr().Get(t) or [],dtype=int),scales=np.array(pi.GetScalesAttr().Get(t) or []).reshape(-1,3),proto=np.array(pi.GetProtoIndicesAttr().Get(t) or [],dtype=int))
def all_errors(node):
    o=list(node.errors())
    for c in node.children():o+=all_errors(c)
    return o
def by_id(d):
    o=np.argsort(d['ids']);return {k:(v[o] if isinstance(v,np.ndarray) and len(v)==len(o) else v) for k,v in d.items()}
def mutate(a=None):
    if a is None:return
    g=a.hdaModule().falloff_curve.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='fall_curve':
        good=g['falloff_curve'];g['falloff_curve']=lambda t,kind,inner=0.0:good(t,0,inner)                                                   # always linear
    elif MUTATE=='fall_scale':g['falloff_scale']=lambda w,edge_scale:np.ones_like(np.asarray(w,dtype=np.float64))
    elif MUTATE=='fall_density':g['falloff_keep']=lambda ids,w,edge_density,seed:np.ones(len(ids),dtype=bool)
    elif MUTATE=='fall_shape':
        good=g['falloff_distance'];g['falloff_distance']=lambda P,shape,axes,c,R,half:good(P,0,axes,c,R,half)
    elif MUTATE=='fall_axes':
        good=g['falloff_axes'];g['falloff_axes']=lambda P,axes:good(P,1)
    elif MUTATE=='fall_inner':
        good=g['falloff_curve'];g['falloff_curve']=lambda t,kind,inner=0.0:good(t,kind,0.0)
    elif MUTATE:raise SystemExit('unknown mutation '+MUTATE)
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()
# independent re-implementations
def w_curve(t,kind,inner=0.0):
    u=max((t-inner)/(1.0-inner),0.0)
    if u>1.0:return 0.0
    return 1.0-u if kind==0 else (1.0-u*u*(3.0-2.0*u) if kind==1 else math.exp(-4.5*u*u))
def region(P,axes):
    A=P[:,[0,2]] if axes==0 else P;lo,hi=A.min(axis=0),A.max(axis=0);c=(lo+hi)/2;R=np.linalg.norm(A-c,axis=1).max();return A,c,R,(hi-lo)/2
def t_of(P,shape,axes):
    A,c,R,half=region(P,axes)
    if shape==0:return np.linalg.norm(A-c,axis=1)/R
    ok=half>1e-9;return np.max(np.abs(A[:,ok]-c[ok])/half[ok],axis=1)

def curves_and_distance():
    st,sc=new_scene('curves');a=scatter(st,sc);m=a.hdaModule()
    for kind in (0,1,2):
        for inner in (0.0,0.4):
            for t in (0.0,0.25,0.5,0.75,1.0,1.4):assert abs(float(m.falloff_curve(np.array([t]),kind,inner)[0])-w_curve(t,kind,inner))<1e-12,(kind,inner,t)
    assert abs(float(m.falloff_curve(np.array([0.5]),0,0)[0])-0.5)<1e-12 and abs(float(m.falloff_curve(np.array([0.25]),1,0)[0])-0.84375)<1e-12 and abs(float(m.falloff_curve(np.array([0.5]),2,0)[0])-math.exp(-1.125))<1e-12
    assert float(m.falloff_curve(np.array([0.5]),0,0.5)[0])==1.0 and float(m.falloff_curve(np.array([1.01]),1,0)[0])==0.0                      # a flat centre, nothing beyond the edge
    P=np.array([[2.0,5.0,0.0],[0.0,-3.0,1.0],[2.0,0.0,1.0],[1.0,9.0,0.5],[-2.0,0.0,-1.0]])                                           # a box of half sizes (2, 1) in X and Z
    c,R,half=m.falloff_region(P,0,0,(0,0,0),0,1.0);assert np.allclose(c,[0,0]) and abs(R-np.sqrt(5.0))<1e-12 and np.allclose(half,[2,1])
    tb=m.falloff_distance(P,1,0,c,R,half);assert np.allclose(tb,[1.0,1.0,1.0,0.5,1.0])                                               # the Chebyshev distance: every edge is at 1, the heights do not count
    tr=m.falloff_distance(P,0,0,c,R,half);assert np.allclose(tr,np.linalg.norm(P[:,[0,2]],axis=1)/np.sqrt(5.0))
    t3=m.falloff_distance(P,0,1,*m.falloff_region(P,1,0,(0,0,0),0,1.0)[:1],m.falloff_region(P,1,0,(0,0,0),0,1.0)[1],m.falloff_region(P,1,0,(0,0,0),0,1.0)[2]);assert abs(t3.max()-1.0)<1e-12     # X, Y and Z: the farthest point is at 1
    c,R,half=m.falloff_region(P,0,1,(1.0,0.0,0.5),1,3.0);assert np.allclose(c,[1.0,0.5]) and R==3.0 and np.allclose(half,[3.0,3.0])                # a custom centre and reach
    assert float(m.falloff_distance(np.array([[4.0,0,0.5]]),0,0,c,R,half)[0])==1.0
    ids=np.arange(20000);keep=m.falloff_keep(ids,np.full(20000,0.3),0.0,1);assert abs(keep.mean()-0.3)<0.01 and not m.falloff_keep(ids,np.zeros(20000),0.0,1).any() and m.falloff_keep(ids,np.zeros(20000),1.0,1).all()
    assert m.falloff_keep(ids,np.full(20000,0.6),0.0,1)[keep].all() and m.falloff_keep(ids,np.full(20000,0.3),0.5,1)[keep].all()                       # more weight or more edge density only adds points
    assert np.allclose(m.falloff_scale(np.array([0.0,0.5,1.0]),0.2),[0.2,0.6,1.0])
    e,e2,e3=m.falloff_region(np.zeros((0,3)),0,0,(0,0,0),0,1.0);assert e2==1.0                                                       # no points: no division by zero

def node_area():
    st,sc=new_scene('area');base=scatter(st,sc,name='Base',mode=1,area_count=4000,area_sizex=12.0,area_sizez=12.0,area_seed=3);b=by_id(out(base))
    a=scatter(st,sc,name='Fall',mode=1,area_count=4000,area_sizex=12.0,area_sizez=12.0,area_seed=3,fall_on=1,fall_curve=0,fall_density=0.0,fall_scale=0.2);o=by_id(out(a))
    assert set(o['ids'].tolist())<=set(b['ids'].tolist()) and 0.2*4000<len(o['ids'])<0.7*4000                                         # only ever removes points; about a third survives with a linear falloff
    idx=np.searchsorted(b['ids'],o['ids']);assert np.allclose(b['pos'][idx],o['pos'],atol=1e-6)                                         # the survivors did not move
    t=t_of(b['pos'],0,0);w=1.0-t;expected=0.2+0.8*w[idx]                                                                               # centre and reach come from the points as generated
    assert np.allclose(o['scales'][:,0],b['scales'][idx][:,0]*expected,atol=1e-4),(o['scales'][:3,0],expected[:3])
    assert o['scales'][:,0].max()>0.9*b['scales'][:,0].max() and o['scales'][:,0].min()<0.4*b['scales'][:,0].max()                         # the centre keeps the true scale, the edge shrinks
    bins=np.linspace(0,1,7);kept=np.zeros(len(b['ids']),dtype=bool);kept[idx]=True
    for lo,hi in zip(bins[:-1],bins[1:]):
        sel=(t>=lo)&(t<hi);assert sel.sum()>100 and abs(kept[sel].mean()-w[sel].mean())<0.07,(lo,hi,kept[sel].mean(),w[sel].mean())                 # the density follows the weight
    assert kept[t<0.1].mean()>0.85 and kept[t>0.9].mean()<0.2
    a.parm('fall_density').set(100.0);o2=by_id(out(a));assert len(o2['ids'])==4000 and o2['scales'][:,0].min()<0.4*b['scales'][:,0].max()      # density untouched, scale still falls
    a.parm('fall_density').set(0.0);a.parm('fall_scale').set(1.0);o3=by_id(out(a));assert np.allclose(o3['scales'][:,0],b['scales'][np.searchsorted(b['ids'],o3['ids'])][:,0],atol=1e-6) and len(o3['ids'])<0.7*4000   # scale untouched, density still falls
    a.parm('fall_scale').set(0.2);a.parm('fall_curve').set(1);a.parm('fall_inner').set(50.0);o4=by_id(out(a));i4=np.searchsorted(b['ids'],o4['ids']);flat=t[i4]<=0.5;assert flat.sum()>100 and np.allclose(o4['scales'][flat][:,0],b['scales'][i4][flat][:,0],atol=1e-4)   # a flat centre keeps the true scale
    assert (t<=0.5).sum()==flat.sum()+((~np.isin(b['ids'],o4['ids']))&(t<=0.5)).sum() and np.isin(b['ids'][t<=0.5],o4['ids']).all()           # and every point of it
    a.parm('fall_inner').set(0.0);a.parm('fall_curve').set(2);o5=by_id(out(a));assert 0.05*4000<len(o5['ids'])<len(o['ids']) and np.isin(o5['ids'],b['ids']).all()    # Gaussian: faster than linear

def node_box():
    st,sc=new_scene('box');b=by_id(out(scatter(st,sc,name='Base',mode=1,area_count=5000,area_sizex=20.0,area_sizez=6.0,area_seed=5)))
    a=scatter(st,sc,name='Box',mode=1,area_count=5000,area_sizex=20.0,area_sizez=6.0,area_seed=5,fall_on=1,fall_shape=1,fall_curve=0,fall_density=100.0,fall_scale=0.1);o=by_id(out(a));idx=np.searchsorted(b['ids'],o['ids']);assert len(o['ids'])==5000
    t=t_of(b['pos'],1,0);assert np.allclose(o['scales'][:,0],b['scales'][idx][:,0]*(0.1+0.9*(1-t[idx])),atol=1e-4)                           # a rectangle fades at every edge
    near_long=np.abs(b['pos'][:,2])>2.85;near_short=np.abs(b['pos'][:,0])>9.5;far=(np.abs(b['pos'][:,2])<0.5)&(np.abs(b['pos'][:,0])<2.0)
    assert o['scales'][near_long][:,0].mean()<0.35*b['scales'][near_long][:,0].mean() and o['scales'][near_short][:,0].mean()<0.35*b['scales'][near_short][:,0].mean() and o['scales'][far][:,0].mean()>0.8*b['scales'][far][:,0].mean()
    r=scatter(st,sc,name='Radial',mode=1,area_count=5000,area_sizex=20.0,area_sizez=6.0,area_seed=5,fall_on=1,fall_shape=0,fall_curve=0,fall_density=100.0,fall_scale=0.1);ro=by_id(out(r));tr=t_of(b['pos'],0,0)
    assert np.allclose(ro['scales'][:,0],b['scales'][:,0]*(0.1+0.9*(1-tr)),atol=1e-4) and not np.allclose(ro['scales'][:,0],o['scales'][:,0],atol=1e-3)      # the radial shape differs

def other_modes():
    st,sc=new_scene('modes')
    for name,kw in (('Line',dict(mode=0,line_count=300)),('Grid',dict(mode=2,grid_countx=30,grid_countz=30)),('Circle',dict(mode=3,circle_count=800,circle_radius=6.0))):
        b=by_id(out(scatter(st,sc,name=name+'B',**kw)));a=scatter(st,sc,name=name,fall_on=1,fall_curve=0,fall_density=100.0,fall_scale=0.25,**kw);o=by_id(out(a));assert len(o['ids'])==len(b['ids']),name
        t=t_of(b['pos'],0,0);assert np.allclose(o['scales'][:,0],b['scales'][:,0]*(0.25+0.75*(1-t)),atol=1e-4),(name,o['scales'][:3,0])
        if name=='Circle':assert np.allclose(t,1.0,atol=1e-3) and np.allclose(o['scales'][:,0]/b['scales'][:,0],0.25,atol=2e-3)                                 # a ring is all at the same distance from its centre: the radial falloff makes it uniformly small
        else:assert abs(o['scales'][:,0].max()/b['scales'][:,0].max()-1.0)<0.1 and o['scales'][:,0].min()<0.4*b['scales'][:,0].max(),name                  # the centre is true scale, the ends / rim are small
    ground=dict(mode=5,surface_prim='/World/Ground',surface_count=3000,surface_seed=2,surface_normal=0)
    b=by_id(out(scatter(st,sc,name='SurfB',**ground)));a=scatter(st,sc,name='Surf',fall_on=1,fall_curve=0,fall_density=0.0,fall_scale=0.3,fall_center_mode=1,fall_center=(4.0,0.0,-3.0),fall_radius_mode=1,fall_radius=5.0,**ground);o=by_id(out(a))
    d=np.linalg.norm(o['pos'][:,[0,2]]-np.array([4.0,-3.0]),axis=1);assert len(o['ids'])>50 and d.max()<=5.0+1e-6                                      # nothing beyond the custom reach (density 0 at the edge)
    idx=np.searchsorted(b['ids'],o['ids']);assert np.allclose(b['pos'][idx],o['pos'],atol=1e-6) and set(o['ids'].tolist())<=set(b['ids'].tolist())
    assert np.allclose(o['scales'][:,0],b['scales'][idx][:,0]*(0.3+0.7*(1-d/5.0)),atol=1e-4)                                              # world space centre and radius
    a.parm('fall_radius').set(8.0);o2=by_id(out(a));assert len(o2['ids'])>len(o['ids']) and np.isin(o['ids'],o2['ids']).all()                  # a larger reach only adds points
    assert 'Centre (4, 0, -3), reach 8' in a.hdaModule().falloff_info(a) and 'Kept %d of'%len(o2['ids']) in a.hdaModule().falloff_info(a)

def with_mask_and_defaults():
    st,sc=new_scene('mask');kw=dict(mode=1,area_count=1500,area_sizex=12.0,area_sizez=12.0,area_seed=7,mask_source=1,mask_effect=1,mask_minscale=0.4,mask_noise_freq=0.3)
    m0=by_id(out(scatter(st,sc,name='MaskOnly',**kw)));both=scatter(st,sc,name='Both',fall_on=1,fall_curve=0,fall_density=100.0,fall_scale=0.2,**kw);o=by_id(out(both))
    t=t_of(m0['pos'],0,0);assert len(o['ids'])==len(m0['ids']) and np.allclose(o['scales'][:,0],m0['scales'][:,0]*(0.2+0.8*(1-t)),atol=1e-4)           # Mask Scale and Falloff multiply
    d0=by_id(out(scatter(st,sc,name='MaskD',mode=1,area_count=1500,area_sizex=12.0,area_sizez=12.0,area_seed=7,mask_source=1,mask_effect=0,mask_noise_freq=0.3)));assert len(d0['ids'])<1500
    d1=by_id(out(scatter(st,sc,name='MaskDF',mode=1,area_count=1500,area_sizex=12.0,area_sizez=12.0,area_seed=7,mask_source=1,mask_effect=0,mask_noise_freq=0.3,fall_on=1,fall_curve=0,fall_density=0.0,fall_scale=1.0)))
    assert np.isin(d1['ids'],d0['ids']).all() and len(d1['ids'])<len(d0['ids'])                                                         # after the Mask: its removals stay removed
    base=dict(mode=1,area_count=700,area_sizex=12.0,area_sizez=12.0,area_seed=2,scale_random_mode=1,scale_min=0.8,scale_max=1.2)
    n=by_id(out(scatter(st,sc,name='Off',**base)));o2=by_id(out(scatter(st,sc,name='Old',typ=OLD_TYPE,**base)))                          # Falloff off reproduces the previous release
    assert np.array_equal(n['ids'],o2['ids']) and np.allclose(n['pos'],o2['pos']) and np.allclose(n['scales'],o2['scales']) and np.array_equal(n['proto'],o2['proto'])
    a=scatter(st,sc,name='Defaults');assert a.evalParm('fall_on')==0 and a.evalParm('fall_shape')==0 and a.evalParm('fall_curve')==1 and a.evalParm('fall_inner')==0 and a.evalParm('fall_density')==0 and abs(a.evalParm('fall_scale')-0.2)<1e-9
    assert a.evalParm('fall_axes')==0 and a.evalParm('fall_center_mode')==0 and a.evalParm('fall_radius_mode')==0 and 'Off' in a.hdaModule().falloff_info(a)

def contract():
    st,sc=new_scene('contract');a=st.createNode(TYPE,'C');g=a.parmTemplateGroup()
    for name in ('fall_on','fall_shape','fall_curve','fall_inner','fall_density','fall_scale','fall_axes','fall_center_mode','fall_center','fall_radius_mode','fall_radius','fall_seed','fall_info'):assert g.find(name) is not None,name
    layout=[t for t in g.entries() if t.label()=='Layout'][0];names=[t.name() for t in layout.parmTemplates()];assert names.index('fall_on')>names.index('bound_t') and names.index('fall_info')>names.index('fall_scale')
    assert g.find('fall_shape').menuLabels()==('Radial (circle)','Box (every edge)') and g.find('fall_curve').menuLabels()==('Linear','Smooth','Gaussian') and g.find('fall_axes').menuLabels()==('X and Z (ground plane)','X, Y and Z')
    compiler=a.node('USD_COMPILER');chain=[];n=compiler.node('PROTOTYPE_ASSIGNMENT')
    while n is not None and len(chain)<12:chain.append(n.name());n=n.inputs()[0] if n.inputs() else None
    assert chain[:4]==['PROTOTYPE_ASSIGNMENT','VARIATION_PROCESSOR','FALLOFF','FIELD_STACK'] and 'MASK_PROCESSOR' in chain and chain.index('FIELD_STACK')<chain.index('MASK_PROCESSOR'),chain      # after the Mask and the Field Stack, before Variation
    assert '$' not in a.type().definition().sections()['PythonModule'].contents().split('# ---- Falloff')[1].split('# ----')[0] and g.find('fall_on').help() and 'every Distribution Mode' in g.find('fall_on').help()

def main():
    for name,func in (('Curves, flat centre, radial / box / XYZ distance, custom centre and reach, id keyed survival, scale multiplier',curves_and_distance),
                      ('Area: scale and density fall from the centre (formula, subset, survivors fixed, density follows the weight, density only / scale only, flat centre, Gaussian)',node_area),
                      ('Box shape fades every edge of a rectangle; radial differs',node_box),
                      ('Line, Grid, Circle and Surface (custom centre and reach in world space), larger reach only adds points, read-out',other_modes),
                      ('Works with the Mask (scales multiply, removals stay); off reproduces the previous release; defaults',with_mask_and_defaults),
                      ('Contract: parameters, Layout tab, stage order after Mask and Field Stack, no dollar signs',contract)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_falloff_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
