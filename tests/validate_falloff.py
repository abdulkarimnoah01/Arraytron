"""v1.12.0 Falloff in real Houdini: hython tests/validate_falloff.py [version]
The Layout tab FALLOFF: the scatter is full size and densest in the centre and fades towards the edges (scale and density), for every Distribution Mode. Expected values come from independent
re-implementations of the curves and of the distance (the survival of a point uses the same id-keyed hash as the Mask, so it is checked statistically and as a subset). Env
ARRAYTRON_MUTATE=fall_curve|fall_scale|fall_density|fall_shape|fall_axes|fall_inner|fall_region|fall_cluster|fall_stroke|fall_grid breaks the module; the suite must FAIL."""
from pathlib import Path
import hou, json, math, os, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v1.12.0':'v1.11.0','v1.13.0':'v1.12.0','v1.13.0':'v1.12.0'}[VID]
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
    elif MUTATE=='fall_region':g['falloff_method']=lambda asset,geo:(0,None)                                                              # always the whole layout
    elif MUTATE=='fall_cluster':
        good=g['falloff_distance_regions'];g['falloff_distance_regions']=lambda P,axes,shape,centres,radii:good(P,axes,shape,np.tile(np.asarray(P).mean(axis=0),(len(P),1)),radii)     # one centre for all clusters
    elif MUTATE=='fall_stroke':
        good=g['falloff_distance_strokes'];g['falloff_distance_strokes']=lambda P,axes,strokes,chunk=2000:good(P,axes,[(r*2.0,c) for r,c in strokes],chunk)
    elif MUTATE=='fall_grid':g['falloff_axes_value']=lambda asset:asset.evalParm('fall_axes')
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
    assert a.evalParm('fall_axes')==0 and a.evalParm('fall_region')==0 and a.evalParm('fall_center_mode')==0 and a.evalParm('fall_radius_mode')==0 and 'Off' in a.hdaModule().falloff_info(a)

def contract():
    st,sc=new_scene('contract');a=st.createNode(TYPE,'C');g=a.parmTemplateGroup()
    assert g.find('fall_axes').menuItems()==('0','1') and g.find('fall_region').menuLabels()==('Automatic (follows the mode)','Whole layout')
    for name in ('fall_on','fall_region','fall_shape','fall_curve','fall_inner','fall_density','fall_scale','fall_axes','fall_center_mode','fall_center','fall_radius_mode','fall_radius','fall_seed','fall_info'):assert g.find(name) is not None,name
    layout=[t for t in g.entries() if t.label()=='Layout'][0];names=[t.name() for t in layout.parmTemplates()];assert names.index('fall_on')>names.index('bound_t') and names.index('fall_info')>names.index('fall_scale')
    assert g.find('fall_shape').menuLabels()==('Radial (circle)','Box (every edge)') and g.find('fall_curve').menuLabels()==('Linear','Smooth','Gaussian') and g.find('fall_axes').menuLabels()==('X and Z (ground plane)','X, Y and Z')
    compiler=a.node('USD_COMPILER');chain=[];n=compiler.node('PROTOTYPE_ASSIGNMENT')
    while n is not None and len(chain)<12:chain.append(n.name());n=n.inputs()[0] if n.inputs() else None
    assert chain[:4]==['PROTOTYPE_ASSIGNMENT','VARIATION_PROCESSOR','FALLOFF','FIELD_STACK'] and 'MASK_PROCESSOR' in chain and chain.index('FIELD_STACK')<chain.index('MASK_PROCESSOR'),chain      # after the Mask and the Field Stack, before Variation
    assert '$' not in a.type().definition().sections()['PythonModule'].contents().split('# ---- Falloff')[1].split('# ----')[0] and g.find('fall_on').help() and 'every Distribution Mode' in g.find('fall_on').help()

def seg_distance(p,a,b):
    ab=b-a;L2=float(ab@ab)
    if L2<=1e-18:return float(np.linalg.norm(p-a))
    u=min(max(float((p-a)@ab)/L2,0.0),1.0);return float(np.linalg.norm(p-(a+u*ab)))
def stroke_t(P,strokes,axes=0):
    """Independent distance of every point to the nearest stroke path, divided by that stroke's radius."""
    out=[]
    for p in P:
        q=p[[0,2]] if axes==0 else p;best=np.inf
        for radius,c in strokes:
            c2=c[:,[0,2]] if axes==0 else c
            d=float(np.linalg.norm(q-c2[0])) if len(c2)==1 else min(seg_distance(q,c2[k],c2[k+1]) for k in range(len(c2)-1))
            best=min(best,d/radius)
        out.append(best)
    return np.array(out)
def paint_scene(a,strokes_spec,record=True,extra=()):
    """Paint with the brush functions: strokes_spec = [(polyline points, radius)]; extra = unrecorded dabs (centre, radius)."""
    m=a.hdaModule();surface=m.paint_surface(a);data=m.paint_empty()
    for pts,radius in strokes_spec:
        pts=[np.array(v,dtype=float) for v in pts];steps=[]
        for k in range(len(pts)-1):
            n=max(2,int(np.linalg.norm(pts[k+1]-pts[k])/(0.3*radius)));steps+=[pts[k]+(pts[k+1]-pts[k])*t for t in np.linspace(0,1,n,endpoint=False)]
        steps.append(pts[-1])
        for c in steps:data,_=m.brush_add(data,c,np.array([0.0,1.0,0.0]),radius,60.0,0.0,3,1.0,1,m.make_projector(surface,c,radius,True))
        if record:data=m.paint_stroke_add(data,steps,radius)
    for c,radius in extra:data,_=m.brush_add(data,np.array(c,dtype=float),np.array([0.0,1.0,0.0]),radius,60.0,0.0,3,1.0,1,m.make_projector(surface,np.array(c,dtype=float),radius,True))
    m.paint_apply(a,data);return data

def region_cluster():
    st,sc=new_scene('cluster');kw=dict(mode=7,cluster_prim='',cluster_count=5,cluster_per=80,cluster_radius=1.4,cluster_falloff=0.3,cluster_jitter=0.4,cluster_seed=4,cluster_area=(14.0,14.0))
    b=by_id(out(scatter(st,sc,name='Base',**kw)));f=dict(fall_on=1,fall_curve=0,fall_density=100.0,fall_scale=0.2,fall_shape=0)
    a=scatter(st,sc,name='Cluster',**kw,**f);o=by_id(out(a));m=a.hdaModule();g=m.cluster_points.__globals__;stride=g['CLUSTER_ID_STRIDE']
    centres,radii=m.cluster_regions(m.cluster_surface(a),5,80,1.4,0.4,4,True);assert len(centres)==5 and len(np.unique(radii))>1                                       # every cluster has its own radius (jitter)
    c=(o['ids']//stride).astype(int);t=np.linalg.norm(o['pos'][:,[0,2]]-centres[c][:,[0,2]],axis=1)/radii[c];assert t.max()<=1.0+1e-6
    assert len(o['ids'])==len(b['ids']) and np.allclose(o['scales'][:,0],b['scales'][:,0]*(0.2+0.8*(1-t)),atol=1e-4)                                              # every member fades to ITS cluster's boundary
    for k in range(5):
        sel=c==k;assert sel.sum()>10 and o['scales'][sel][:,0].max()>0.85*b['scales'][sel][:,0].max() and o['scales'][sel][:,0].min()<0.5*b['scales'][sel][:,0].max(),k          # every cluster has a full size centre
    whole=by_id(out(scatter(st,sc,name='Whole',fall_region=1,**kw,**f)));assert not np.allclose(whole['scales'],o['scales'],atol=1e-3)                                          # the whole layout region treats the clusters as one blob
    far=np.argmax(np.linalg.norm(centres[:,[0,2]]-centres[:,[0,2]].mean(axis=0),axis=1));sel=c==far;assert o['scales'][sel][:,0].max()>0.85*b['scales'][sel][:,0].max() and whole['scales'][sel][:,0].max()<0.7*b['scales'][sel][:,0].max()   # the outermost cluster is full size in its own centre, not at the edge of the blob
    d=scatter(st,sc,name='Dens',fall_on=1,fall_curve=0,fall_density=0.0,fall_scale=1.0,fall_shape=0,**kw);od=by_id(out(d));assert set(od['ids'].tolist())<=set(b['ids'].tolist()) and len(od['ids'])<len(b['ids'])
    cd=(od['ids']//stride).astype(int);td=np.linalg.norm(od['pos'][:,[0,2]]-centres[cd][:,[0,2]],axis=1)/radii[cd];cb=(b['ids']//stride).astype(int);tb=np.linalg.norm(b['pos'][:,[0,2]]-centres[cb][:,[0,2]],axis=1)/radii[cb]
    kept=np.isin(b['ids'],od['ids']);assert kept[tb<0.15].mean()>0.8 and kept[tb>0.85].mean()<0.3                                                                          # the density thins out towards each cluster's edge
    box=by_id(out(scatter(st,sc,name='Box',**{**kw,**f,'fall_shape':1})));tbx=np.max(np.abs(o['pos'][:,[0,2]]-centres[c][:,[0,2]]),axis=1)/radii[c];assert np.allclose(box['scales'][:,0],b['scales'][:,0]*(0.2+0.8*(1-tbx)),atol=1e-4)      # a square of the cluster radius
    assert 'Every cluster to its own boundary' in a.hdaModule().falloff_info(a)

def region_grid():
    st,sc=new_scene('grid');flat=dict(mode=2,grid_countx=9,grid_county=1,grid_countz=7);deep=dict(mode=2,grid_countx=8,grid_county=6,grid_countz=8);f=dict(fall_on=1,fall_shape=1,fall_curve=0,fall_density=100.0,fall_scale=0.2)
    bd=by_id(out(scatter(st,sc,name='DeepBase',**deep)));assert np.ptp(bd['pos'][:,1])>0.5                                                                                  # a 3D matrix
    auto=by_id(out(scatter(st,sc,name='Auto',**deep,**f)));xyz=by_id(out(scatter(st,sc,name='XYZ',fall_axes=1,**deep,**f)));xz=by_id(out(scatter(st,sc,name='XZ',fall_axes=0,fall_region=1,**deep,**f)))
    t3=t_of(bd['pos'],1,1);assert np.allclose(auto['scales'][:,0],bd['scales'][:,0]*(0.2+0.8*(1-t3)),atol=1e-4) and np.allclose(auto['scales'],xyz['scales'],atol=1e-6) and not np.allclose(auto['scales'],xz['scales'],atol=1e-3)   # Automatic: all three axes for a 3D grid
    ring=(np.abs(bd['pos'][:,1])>=bd['pos'][:,1].max()-1e-6);assert auto['scales'][ring][:,0].max()<=0.2*bd['scales'][:,0].max()*1.0001+1e-6                                  # the top layer is at the boundary: edge scale
    assert xz['scales'][ring][:,0].max()>0.4*bd['scales'][:,0].max()                                                                                                           # the XZ falloff ignores the layers
    bf=by_id(out(scatter(st,sc,name='FlatBase',**flat)));af=by_id(out(scatter(st,sc,name='FlatAuto',**flat,**f)));xzf=by_id(out(scatter(st,sc,name='FlatXZ',fall_axes=0,**flat,**f)))
    assert np.allclose(af['scales'],xzf['scales'],atol=1e-6) and np.allclose(af['scales'][:,0],bf['scales'][:,0]*(0.2+0.8*(1-t_of(bf['pos'],1,0))),atol=1e-4)                       # one layer: the ground plane, as before
    a=scatter(st,sc,name='Info',**deep,**f);out(a);assert 'Whole layout' in a.hdaModule().falloff_info(a)

def region_paint():
    st,sc=new_scene('paint');kw=dict(mode=6,paint_prim='',paint_radius=1.0,paint_density=60.0);f=dict(fall_on=1,fall_curve=0,fall_density=100.0,fall_scale=0.2,fall_shape=0)
    a=scatter(st,sc,name='Strokes',**kw,**f);data=paint_scene(a,[([(-4,0,0),(4,0,0)],1.0),([(0,0,-3),(0,0,3)],1.0)]);m=a.hdaModule();dec=m.paint_decode(a.evalParm('paint_data'));assert len(dec['strokes'])==2 and dec['strokes'][0][0]==1.0 and a.evalParm('paint_data').startswith('p2:')
    base=scatter(st,sc,name='Base',fall_on=0,**kw);paint_scene(base,[([(-4,0,0),(4,0,0)],1.0),([(0,0,-3),(0,0,3)],1.0)]);b=by_id(out(base));o=by_id(out(a));assert np.array_equal(b['ids'],o['ids']) and len(b['ids'])>300
    t=np.minimum(stroke_t(b['pos'],dec['strokes']),1.0);assert np.allclose(o['scales'][:,0],b['scales'][:,0]*(0.2+0.8*(1-t)),atol=1e-4),(o['scales'][:3,0],(0.2+0.8*(1-t))[:3])               # across the width of the nearest stroke, full size on the path
    on_path=t<0.1;assert on_path.sum()>50 and o['scales'][on_path][:,0].min()>0.85*b['scales'][on_path][:,0].min() and o['scales'][t>0.85][:,0].max()<0.4*b['scales'][:,0].max()
    whole=by_id(out(scatter(st,sc,name='Whole',fall_region=1,**{**kw,**f})))
    paint_scene(hou.node(a.parent().path()+'/Whole'),[([(-4,0,0),(4,0,0)],1.0),([(0,0,-3),(0,0,3)],1.0)]);whole=by_id(out(hou.node(a.parent().path()+'/Whole')));assert not np.allclose(whole['scales'],o['scales'],atol=1e-3)         # the whole layout region ignores the paths
    assert 'Along the stroke paths' in a.hdaModule().falloff_info(a)
    dens=scatter(st,sc,name='Dens',mode=6,paint_prim='',paint_radius=1.0,paint_density=60.0,fall_on=1,fall_curve=0,fall_density=0.0,fall_scale=1.0,fall_shape=0);paint_scene(dens,[([(-4,0,0),(4,0,0)],1.0),([(0,0,-3),(0,0,3)],1.0)]);od=by_id(out(dens));kept=np.isin(b['ids'],od['ids'])
    assert set(od['ids'].tolist())<=set(b['ids'].tolist()) and kept[t<0.15].mean()>0.8 and kept[t>0.85].mean()<0.35                                                                    # the density thins towards the edge of the stroke
    old=scatter(st,sc,name='Old',mode=6,paint_prim='',paint_radius=1.0,paint_density=60.0,fall_on=1,fall_curve=0,fall_density=100.0,fall_scale=0.2,fall_shape=0);paint_scene(old,[([(-4,0,0),(4,0,0)],1.0)],record=False)         # painted without recorded strokes (an older scene)
    oo=by_id(out(old));assert old.evalParm('paint_data').startswith('p1:') and 'Whole layout' in old.hdaModule().falloff_info(old) and oo['scales'][:,0].min()<0.5*oo['scales'][:,0].max()
    mixed=scatter(st,sc,name='Mixed',mode=6,paint_prim='',paint_radius=1.0,paint_density=60.0,fall_on=1,fall_curve=0,fall_density=100.0,fall_scale=0.2,fall_shape=0);paint_scene(mixed,[([(-4,0,0),(4,0,0)],1.0)],extra=[((0.0,0.0,6.0),0.8)])   # a dab nobody recorded
    mo=by_id(out(mixed));far=mo['pos'][:,2]>4.5;assert far.sum()>5 and np.allclose(mo['scales'][far][:,0],mo['scales'][:,0].max(),atol=0.35*mo['scales'][:,0].max()) and 'not made by a recorded stroke' in mixed.hdaModule().falloff_info(mixed)
    one=scatter(st,sc,name='One',mode=6,paint_prim='',paint_radius=1.0,paint_density=60.0,fall_on=1,fall_curve=0,fall_density=100.0,fall_scale=0.2,fall_shape=0);paint_scene(one,[([(2,0,2)],0.8)]);oo1=by_id(out(one));d1=np.linalg.norm(oo1['pos'][:,[0,2]]-np.array([2.0,2.0]),axis=1)/0.8
    assert len(oo1['ids'])>30 and oo1['scales'][d1<0.2][:,0].max()>0.85*oo1['scales'][:,0].max()                                                                                        # a single dab is a stroke with one centre

def whole_layout_is_v1120():
    st,sc=new_scene('v1120');cases=(dict(mode=1,area_count=900,area_sizex=10.0,area_sizez=7.0,area_seed=2),dict(mode=2,grid_countx=8,grid_county=4,grid_countz=8),dict(mode=7,cluster_prim='',cluster_count=4,cluster_per=50,cluster_radius=1.2,cluster_area=(12.0,12.0),cluster_seed=3))
    f=dict(fall_on=1,fall_shape=1,fall_curve=2,fall_inner=20.0,fall_density=30.0,fall_scale=0.3)
    for i,kw in enumerate(cases):
        old=scatter(st,sc,name='Old%d'%i,typ=OLD_TYPE,**{**kw,**f});new=scatter(st,sc,name='New%d'%i,fall_region=1,**{**kw,**f});o,n=by_id(out(old)),by_id(out(new))
        assert np.array_equal(o['ids'],n['ids']) and np.allclose(o['pos'],n['pos']) and np.allclose(o['scales'],n['scales'],atol=1e-6),i                                                    # Whole layout (and XZ for the grid) is exactly v1.12.0

def main():
    for name,func in (('Curves, flat centre, radial / box / XYZ distance, custom centre and reach, id keyed survival, scale multiplier',curves_and_distance),
                      ('Area: scale and density fall from the centre (formula, subset, survivors fixed, density follows the weight, density only / scale only, flat centre, Gaussian)',node_area),
                      ('Box shape fades every edge of a rectangle; radial differs',node_box),
                      ('Line, Grid, Circle and Surface (custom centre and reach in world space), larger reach only adds points, read-out',other_modes),
                      ('Works with the Mask (scales multiply, removals stay); off reproduces the previous release; defaults',with_mask_and_defaults),
                      ('Cluster: every cluster fades to its own boundary (radial and box), density per cluster, the outermost cluster is full size in its centre',region_cluster),
                      ('Grid: Region Automatic uses all three axes for a 3D matrix, the ground plane for one layer',region_grid),
                      ('Paint: across the width of every stroke path, density, nearest of several strokes, no recorded strokes fall back, unrecorded dabs keep full size, single dab',region_paint),
                      ('Region Whole layout reproduces v1.12.0 for Area, Grid and Cluster',whole_layout_is_v1120),
                      ('Contract: parameters, Layout tab, stage order after Mask and Field Stack, no dollar signs',contract)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_falloff_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
