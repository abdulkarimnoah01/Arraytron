"""v1.26.0 Painted mask and full mask remap in real Houdini: hython tests/validate_maskpaint.py [version]
Mask Source Painted: the stamps of the brush (operation, position, radius, strength, feather, value, curve) live in the hidden mask_paint_data; at cook time they become a grid over the painted area (applied in
the order painted: Paint moves the map towards the brush value, Erase towards 0, Add / Subtract change it), optionally blurred, and are read at the points. The survivors are checked against the unmasked
scatter of the same node (the mask never moves a point, it only removes some), and the maths against brute force. The remap (Gamma, Remap Curve, Output Range) is checked on mask_weights directly and on a
node. The viewport tool is exercised through a stand-in viewport that looks straight down. Env ARRAYTRON_MUTATE=mp_order|mp_feather|mp_base|mp_blur|mp_gamma|mp_range|mp_live|mp_ctrl breaks the module;
the suite must FAIL."""
from pathlib import Path
import hou, json, math, os, sys, tempfile, time, types
import numpy as np
from pxr import Usd, UsdGeom
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v1.34.0':'v1.33.0','v1.33.0':'v1.32.0','v1.32.0':'v1.31.1','v1.31.1':'v1.31.0','v1.31.0':'v1.30.1','v1.30.1':'v1.30.0','v1.30.0':'v1.29.0','v1.26.0':'v1.25.2','v1.27.0':'v1.26.0','v1.28.0':'v1.27.0','v1.29.0':'v1.28.0'}[VID]
FULL=tuple(int(x) for x in VID[1:].split('.'))>=(1,27,0)                                  # v1.27.0: the full brush (Foreground / Background, Shift and Ctrl operations, Smooth, Sample, symmetry, Fill)
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_maskpaint_'));checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')
def write_scene():
    path=WORK/'maskpaint.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    UsdGeom.Xform.Define(s,'/World/Props/Tree');UsdGeom.Cube.Define(s,'/World/Props/Tree/C').CreateSizeAttr(0.2)
    m=UsdGeom.Mesh.Define(s,'/World/Terrain');m.CreatePointsAttr([(-20,0,-20),(20,0,-20),(20,0,20),(-20,0,20)]);m.CreateFaceVertexCountsAttr([4]);m.CreateFaceVertexIndicesAttr([0,3,2,1]);m.CreateSubdivisionSchemeAttr('none')
    s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
def install():
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True);install();hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
def scatter(stage,source,typ=None,name='Mask',**values):
    a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Tree');a.parm('mode').set(1)
    a.parmTuple('area_sizex').set((10.0,));a.parmTuple('area_sizez').set((10.0,));a.parm('area_count').set(400);a.parm('area_seed').set(3)
    for k,v in values.items():
        if isinstance(v,(tuple,list)):a.parmTuple(k).set(v)
        else:a.parm(k).set(v)
    if typ is None:mutate(a)
    return a
def out(a):
    s=a.stage();assert not list(a.errors()),a.errors();pi=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    d=dict(pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3),ids=np.array(pi.GetIdsAttr().Get(t) or [],dtype=int))
    o=np.argsort(d['ids']);return {k:v[o] for k,v in d.items()}
def mutate(a):
    g=a.hdaModule().maskpaint_raster.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='mp_order':
        good=g['maskpaint_raster'];g['maskpaint_raster']=lambda stamps,spec,base=0.0,blur=0.0:good(np.asarray(stamps).reshape(-1,9)[::-1],spec,base,blur)                      # the stamps are applied in the wrong order
    elif MUTATE=='mp_feather':
        good=g['maskpaint_profile'];g['maskpaint_profile']=lambda t,feather,curve:good(t,0.0,curve)                                                                       # the feather does nothing: always a hard disc
    elif MUTATE=='mp_base':
        good=g['maskpaint_values'];g['maskpaint_values']=lambda stamps,xz,res,base=0.0,blur=0.0:good(stamps,xz,res,0.0,blur)                                               # the unpainted value is ignored
    elif MUTATE=='mp_blur':
        g['maskpaint_blur']=lambda grid,sigma:grid                                                                                                                        # the map feather does nothing
    elif MUTATE=='mp_gamma':
        good=g['mask_weights'];g['mask_weights']=lambda asset,raw:(lambda w:w**(asset.evalParm('mask_gamma')**2) if asset.evalParm('mask_gamma')!=1.0 else w)(good(asset,raw))   # the gamma bends the wrong way
    elif MUTATE=='mp_range':
        good=g['mask_weights'];g['mask_weights']=lambda asset,raw:(lambda w,o:(w-o[0])/(o[1]-o[0]) if o!=(0.0,1.0) else w)(good(asset,raw),asset.evalParmTuple('mask_outrange'))   # the output range is undone
    elif MUTATE=='mp_smooth':
        g['_smooth_window']=lambda grid,iz0,iz1,ix0,ix1,sigma:grid[iz0:iz1+1,ix0:ix1+1].copy()                                                                           # Smooth does nothing
    elif MUTATE=='mp_sym':
        g['maskpaint_mirrors']=lambda pos,sx,sz,center:[tuple(pos)]                                                                                                       # no mirror images
    elif MUTATE=='mp_stamp':
        good=g['maskpaint_stamp_for'];g['maskpaint_stamp_for']=lambda menu,fg,bg:(lambda r:(r[0],fg) if r is not None and int(menu)==8 else r)(good(menu,fg,bg))           # Paint Background paints the Foreground
    elif MUTATE and MUTATE not in ('mp_live','mp_ctrl','mp_shift','mp_heavy'):raise SystemExit('unknown mutation '+MUTATE)
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()
def module():
    st,sc=new_scene('mod');a=scatter(st,sc);return a,a.hdaModule()
def stamp(op,x,z,r,strength=1.0,feather=0.0,value=1.0,curve=1,y=0.0):return [op,x,y,z,r,strength,feather,value,curve]
def text(*stamps):
    """The mask_paint_data text of some stamps, written independently of the module (so the format is tested too)."""
    return json.dumps({'v':1,'stamps':[[int(s[0])]+[float(v) for v in s[1:8]]+[int(s[8])] for s in stamps]})

def maths():
    a,m=module();s=np.array([stamp(0,0,0,2),stamp(1,1,1,3,0.5,0.3,0.7,2)]);t=m.maskpaint_encode(s);d=m.maskpaint_decode(t)
    assert d.shape==(2,9) and np.allclose(d,s) and m.maskpaint_decode('').shape==(0,9) and m.maskpaint_encode(np.zeros((0,9)))=='' and json.loads(t)['v']==1
    for bad in ('nope','{"stamps":[[1,2,3]]}','{"x":1}'):
        try:m.maskpaint_decode(bad);assert False,bad
        except ValueError as e:assert 'cannot be read' in str(e)
    arr,added=m.maskpaint_add(np.zeros((0,9)),0,(0,0,0),2.0,1.0,0.5,1.0,1);assert added and len(arr)==1
    assert not m.maskpaint_add(arr,0,(0.1,0,0.1),2.0,1.0,0.5,1.0,1)[1]                                                                                              # too close to the last stamp: skipped
    for kw in (dict(op=1),dict(radius=3.0),dict(feather=0.2),dict(value=0.5)):
        args=dict(op=0,radius=2.0,feather=0.5,value=1.0);args.update(kw);assert m.maskpaint_add(arr,args['op'],(0.1,0,0.1),args['radius'],1.0,args['feather'],args['value'],1)[1],kw   # a different brush: a new stamp
    assert m.maskpaint_add(arr,0,(0.6,0,0),2.0,1.0,0.5,1.0,1)[1] and len(m.maskpaint_add(np.zeros((m.MASKPAINT_MAX,9)),0,(5,0,5),1.0,1.0,0.5,1.0,1)[0])==m.MASKPAINT_MAX
    t=np.linspace(0,1.2,121)                                                                                                                                         # the brush profile
    for curve in (0,1,2):
        hard=m.maskpaint_profile(t,0.0,curve);assert (hard[t<=1.0]==1.0).all() and (hard[t>1.0]==0.0).all()                                                       # feather 0: a hard disc
        full=m.maskpaint_profile(t,1.0,curve);assert abs(full[0]-1.0)<1e-12 and abs(full[100])<1e-12 and (np.diff(full[:101])<=1e-12).all() and (full[t>1.0]==0.0).all()  # feather 1: from the middle to the rim
        half=m.maskpaint_profile(t,0.5,curve);assert (half[t<=0.5]==1.0).all() and abs(half[100])<1e-12 and (np.diff(half[50:101])<=1e-12).all() and 0<half[75]<1        # a core of radius 0.5, then the fade
    assert abs(m.maskpaint_profile(np.array([0.75]),0.5,0)[0]-0.5)<1e-12 and abs(m.maskpaint_profile(np.array([0.75]),0.5,1)[0]-0.5)<1e-12                      # linear and smooth cross 0.5 in the middle of the fade
    spec=m.maskpaint_spec(np.array([stamp(0,0,0,4)]),81,0.0);x0,z0,cell,nx,nz=spec;assert x0<-4 and z0<-4 and abs(cell*(81-1)-(8*1.02))<0.2 and nx>=81 and nz>=81 and nx==nz
    bounds_cover=m.maskpaint_spec(np.array([stamp(0,10,0,2),stamp(0,-10,5,3)]),100,0.0);assert bounds_cover[0]<-13 and bounds_cover[0]+(bounds_cover[3]-1)*bounds_cover[2]>12   # the grid covers every stamp and its radius
    wide=m.maskpaint_spec(np.array([stamp(0,0,0,2)]),100,5.0);narrow=m.maskpaint_spec(np.array([stamp(0,0,0,2)]),100,0.0);assert wide[3]*wide[2]>narrow[3]*narrow[2]+30    # room for the blur
    res=161;st=np.array([stamp(0,0,0,4)]);spec=m.maskpaint_spec(st,res);x0,z0,cell,nx,nz=spec;xs=x0+np.arange(nx)*cell;zs=z0+np.arange(nz)*cell;X,Z=np.meshgrid(xs,zs);Rr=np.hypot(X,Z)
    g=m.maskpaint_raster(st,spec,0.0);assert np.array_equal(g,(Rr<=4.0).astype(float))                                                                                # a hard Paint disc against brute force
    g=m.maskpaint_raster(np.array([stamp(0,0,0,4,0.5)]),spec,0.0);assert np.allclose(g,0.5*(Rr<=4.0))                                                                  # strength 0.5: one pass reaches half
    two=m.maskpaint_raster(np.array([stamp(0,0,0,4,0.5),stamp(0,0.0001,0.0001,4,0.5)]),spec,0.0);assert np.allclose(two,0.75*(Rr<=4.0))                          # an airbrush: two passes reach 0.75
    g=m.maskpaint_raster(np.array([stamp(0,0,0,4,1.0,0.0,0.4)]),spec,0.0);assert np.allclose(g,0.4*(Rr<=4.0))                                                          # Paint moves towards the Brush Value
    g=m.maskpaint_raster(np.array([stamp(0,0,0,4,1.0,0.0,0.4)]),spec,0.9);assert np.allclose(g,np.where(Rr<=4.0,0.4,0.9))                                            # ... down as well as up, from the unpainted value
    order=m.maskpaint_raster(np.array([stamp(0,0,0,4),stamp(1,0,0,2)]),spec,0.0);assert (order[Rr<=1.9]==0.0).all() and (order[(Rr>2.1)&(Rr<=4.0)]==1.0).all()          # Erase after Paint: a hole
    order=m.maskpaint_raster(np.array([stamp(1,0,0,2),stamp(0,0,0,4)]),spec,0.0);assert (order[Rr<=4.0]==1.0).all()                                                   # Paint after Erase: painted again
    add=m.maskpaint_raster(np.array([stamp(2,0,0,4,1.0,0.0,0.3)]*1+[stamp(2,0.0001,0,4,1.0,0.0,0.3)]*3),spec,0.0);assert np.allclose(add[Rr<=3.9],min(1.0,4*0.3))   # Add raises by the Brush Value each pass, clipped at 1
    sub=m.maskpaint_raster(np.array([stamp(0,0,0,4),stamp(3,0,0,4,1.0,0.0,0.3)]),spec,0.0);assert np.allclose(sub[Rr<=3.9],0.7)                                      # Subtract lowers it
    assert m.maskpaint_raster(np.array([stamp(3,0,0,4,1.0,0.0,1.0)]),spec,0.0).max()==0.0 and m.maskpaint_raster(np.array([stamp(2,0,0,4,1.0,0.0,1.0)]),spec,1.0).max()==1.0   # never outside 0 to 1
    soft=m.maskpaint_raster(np.array([stamp(0,0,0,4,1.0,1.0,1.0,0)]),spec,0.0);assert abs(soft[nz//2,nx//2]-1.0)<1e-9 and soft[Rr>4.0001].max()==0.0 and 0<soft[nz//2,nx//2+40]<1   # a feathered brush
    flat=m.maskpaint_raster(np.zeros((0,9)),spec,0.37);assert np.allclose(flat,0.37)                                                                                  # no paint: the unpainted value
    blur_in=m.maskpaint_raster(st,spec,0.0)
    spec_b=m.maskpaint_spec(st,res,0.5);bx0,bz0,bcell,bnx,bnz=spec_b;BX,BZ=np.meshgrid(bx0+np.arange(bnx)*bcell,bz0+np.arange(bnz)*bcell);BR=np.hypot(BX,BZ)                # the Map Feather (the grid has room for it)
    plain=m.maskpaint_raster(st,spec_b,0.0);soft=m.maskpaint_raster(st,spec_b,0.0,0.5)
    assert soft.max()<=1.0 and soft.min()>=0.0 and abs(soft.sum()-plain.sum())<0.005*plain.sum() and (soft[(BR>4.0)&(BR<4.4)]>0).all() and soft[bnz//2,bnx//2]>0.99 and soft[(BR>3.0)&(BR<4.0)].min()<1.0 and (soft[BR>5.5]<0.01).all()   # soft edges, same volume, the middle intact
    assert np.allclose(m.maskpaint_blur(np.full((20,20),0.6),3.0),0.6) and m.maskpaint_blur(blur_in,0.1) is blur_in and abs(m.maskpaint_blur(plain,5.0).max()-plain.max())<0.5                                                # flat stays flat; a tiny blur is skipped
    sm=m.maskpaint_sample(blur_in,spec,np.array([[xs[nx//2],zs[nz//2]],[xs[nx//2]+cell/2,zs[nz//2]],[99.0,99.0],[-99.0,0.0]]),0.25);assert abs(sm[0]-1.0)<1e-12 and abs(sm[1]-1.0)<1e-12 and sm[2]==0.25 and sm[3]==0.25   # exact at a cell, bilinear between, `outside` beyond the grid
    edge=np.array([[xs[nx//2+40]+cell/2,zs[nz//2]]]);k=nx//2+40;assert abs(m.maskpaint_sample(blur_in,spec,edge,0.0)[0]-0.5*(blur_in[nz//2,k]+blur_in[nz//2,k+1]))<1e-12
    cache=m._MASKPAINT_CACHE;cache.clear();m.maskpaint_values(st,np.zeros((3,2)),res,0.0,0.0);m.maskpaint_values(st,np.ones((3,2)),res,0.0,0.0);assert len(cache)==1             # the map is kept
    m.maskpaint_values(st,np.zeros((3,2)),res,0.2,0.0);m.maskpaint_values(st,np.zeros((3,2)),res,0.2,1.0);assert len(cache)==3                                      # ... and rebuilt when the base or the blur change
    assert np.allclose(m.maskpaint_values(np.zeros((0,9)),np.zeros((4,2)),res,0.6,0.0),0.6)

def painted_node():
    st,sc=new_scene('painted');base=out(scatter(st,sc,name='None',mask_source=0));assert len(base['ids'])==400
    P=base['pos'];dist=np.hypot(P[:,0],P[:,2]);R=3.0;cell=(2*R*1.02)/511
    hard=scatter(st,sc,name='Hard',mask_source=4,mask_paint_data=text(stamp(0,0,0,R)));oh=out(hard)
    assert hard.evalParm('mask_source')==4 and len(oh['ids'])>60 and set(oh['ids'].tolist())<=set(base['ids'].tolist())
    ids_in=set(base['ids'][dist<R-3*cell].tolist());assert len(ids_in)>60 and ids_in<=set(oh['ids'].tolist())                                                         # every point well inside the disc grows (weight 1) ...
    assert (np.hypot(oh['pos'][:,0],oh['pos'][:,2])<=R+3*cell).all()                                                                                                   # ... and nothing outside it
    assert np.array_equal(oh['pos'],P[np.isin(base['ids'],oh['ids'])])                                                                                                 # the mask never moves a point
    half=out(scatter(st,sc,name='Half',mask_source=4,mask_paint_data=text(stamp(0,0,0,R,1.0,0.0,0.5))));sh=set(half['ids'].tolist());assert sh<=set(oh['ids'].tolist()) and 0.3<len(sh&ids_in)/len(ids_in)<0.7   # Brush Value 0.5: about half
    weak=out(scatter(st,sc,name='Weak',mask_source=4,mask_paint_data=text(stamp(0,0,0,R,0.25))));assert set(weak['ids'].tolist())<=set(oh['ids'].tolist()) and 0.1<len(set(weak['ids'].tolist())&ids_in)/len(ids_in)<0.45   # strength 0.25: about a quarter
    hole=out(scatter(st,sc,name='Hole',mask_source=4,mask_paint_base=1.0,mask_paint_data=text(stamp(1,0,0,R))));sx=set(hole['ids'].tolist())
    assert not sx&ids_in and set(base['ids'][dist>R+3*cell].tolist())<=sx and len(sx)>150                                                                             # Unpainted Value 1 and Erase: a hole in a full scatter
    erased=out(scatter(st,sc,name='Gone',mask_source=4,mask_paint_data=text(stamp(0,0,0,R),stamp(1,0,0,R*0.5))));ring=(dist>R*0.5+3*cell)&(dist<R-3*cell);se=set(erased['ids'].tolist())
    assert not se&set(base['ids'][dist<R*0.5-3*cell].tolist()) and set(base['ids'][ring].tolist())<=se                                                                 # painted, then erased in the middle: a ring
    nobase=out(scatter(st,sc,name='Empty',mask_source=4));assert len(nobase['ids'])==0                                                                                 # nothing painted, base 0: no scatter
    full=out(scatter(st,sc,name='Full',mask_source=4,mask_paint_base=1.0));assert np.array_equal(full['ids'],base['ids'])                                              # base 1: the scatter as generated
    mid=out(scatter(st,sc,name='Mid',mask_source=4,mask_paint_base=0.5));assert 0.35<len(mid['ids'])/400<0.65
    soft=out(scatter(st,sc,name='Soft',mask_source=4,mask_paint_data=text(stamp(0,0,0,R,1.0,1.0,1.0,0))));ss=set(soft['ids'].tolist())
    assert ss<=set(oh['ids'].tolist())                                                                                                                                 # feathered weights are never above the hard ones
    rings=[((dist>=a*R)&(dist<b*R)) for a,b in ((0,0.34),(0.34,0.67),(0.67,1.0))];frac=[len(set(base['ids'][r].tolist())&ss)/max(int(r.sum()),1) for r in rings]
    assert frac[0]>frac[1]>frac[2] and frac[0]>0.7 and frac[2]<0.5,frac                                                                                                # linear feather 1: the weight falls from the middle to the rim
    nofeather=out(scatter(st,sc,name='Edge',mask_source=4,mask_paint_data=text(stamp(0,0,0,R,1.0,0.0,1.0,0))));assert np.array_equal(nofeather['ids'],oh['ids'])      # the curve is irrelevant at feather 0
    blurred=out(scatter(st,sc,name='Blur',mask_source=4,mask_paint_blur=1.5,mask_paint_data=text(stamp(0,0,0,R))));sb=set(blurred['ids'].tolist())
    assert len(sb)>0 and (sb-set(oh['ids'].tolist())) and (set(oh['ids'].tolist())-sb) and (np.hypot(blurred['pos'][:,0],blurred['pos'][:,2])<=R+1.5*4.5).all()          # Map Feather: the edge spreads outside and thins inside
    near_edge=(dist>R-0.3)&(dist<R+0.3);assert len(set(base['ids'][dist<R-3.0].tolist())-sb)<5                                                                         # ... the middle of the disc stays full
    r64=out(scatter(st,sc,name='R64',mask_source=4,mask_paint_res=64,mask_paint_data=text(stamp(0,0,0,R))));assert 0.8<len(r64['ids'])/len(oh['ids'])<1.25           # the resolution only sharpens the border
    two=out(scatter(st,sc,name='Two',mask_source=4,mask_paint_data=text(stamp(0,-3,0,1.5),stamp(0,3,0,1.5))));assert (np.abs(np.abs(two['pos'][:,0])-3)<1.6).all() and len(two['ids'])>10   # two blobs far apart share one map
    eff=scatter(st,sc,name='Scale',mask_source=4,mask_effect=1,mask_minscale=0.25,mask_paint_data=text(stamp(0,0,0,R,1.0,0.0,0.5)));oe=out(eff);assert len(oe['ids'])==400                      # the Scale effect keeps every point
    s=eff.stage();pi=UsdGeom.PointInstancer(s.GetPrimAtPath(eff.evalParm('outputpath')));sc_=np.array(pi.GetScalesAttr().Get(hou.frame())).reshape(-1,3)
    o=np.argsort(np.array(pi.GetIdsAttr().Get(hou.frame())));sc_=sc_[o];inner=dist<R-3*cell;outer=dist>R+3*cell
    assert inner.sum()>50 and outer.sum()>50 and np.allclose(sc_[inner][:,0]/sc_[inner][:,0].max(),sc_[inner][:,0]/sc_[inner][:,0].max()) and sc_[inner][:,0].mean()>sc_[outer][:,0].mean()*1.4   # the weight scales the instances

def remap():
    st,sc=new_scene('remap');a=scatter(st,sc,name='Weights',mask_source=4,mask_paint_base=1.0);m=a.hdaModule();raw=np.linspace(0.0,1.0,11)
    assert np.array_equal(m.mask_weights(a,raw),raw)                                                                                                                   # defaults: the weight is the mask
    a.parm('mask_invert').set(1);a.parm('mask_low').set(0.2);a.parm('mask_high').set(0.8);base_w=np.clip(((1.0-raw)-0.2)/0.6,0.0,1.0);assert np.allclose(m.mask_weights(a,raw),base_w,atol=1e-12)   # Invert and Low / High as before
    a.parm('mask_invert').set(0);a.parm('mask_low').set(0.0);a.parm('mask_high').set(1.0)
    a.parm('mask_gamma').set(2.0);assert np.allclose(m.mask_weights(a,raw),raw**0.5)                                                                                    # gamma 2 lifts the middle
    a.parm('mask_gamma').set(0.5);assert np.allclose(m.mask_weights(a,raw),raw**2.0)                                                                                    # gamma 0.5 lowers it
    a.parm('mask_gamma').set(1.0);a.parmTuple('mask_outrange').set((0.2,0.8));assert np.allclose(m.mask_weights(a,raw),0.2+0.6*raw)                                    # the output range
    a.parmTuple('mask_outrange').set((1.0,0.0));assert np.allclose(m.mask_weights(a,raw),1.0-raw)                                                                       # ... flips with the numbers reversed
    a.parmTuple('mask_outrange').set((0.0,1.0));a.parm('mask_curve_on').set(1);assert np.allclose(m.mask_weights(a,raw),raw,atol=1e-9)                                  # the default curve is the identity
    a.parm('mask_curve').set(hou.Ramp((hou.rampBasis.Linear,)*3,(0.0,0.5,1.0),(0.0,1.0,0.0)));w=m.mask_weights(a,np.array([0.0,0.25,0.5,0.75,1.0]));assert np.allclose(w,[0.0,0.5,1.0,0.5,0.0],atol=0.02)   # a peak curve
    a.parm('mask_curve').set(hou.Ramp((hou.rampBasis.Constant,)*3,(0.0,0.5,1.0),(0.0,1.0,1.0)));w=m.mask_weights(a,np.array([0.1,0.49,0.51,0.9]));assert np.allclose(w,[0.0,0.0,1.0,1.0],atol=0.01)   # a threshold
    a.parm('mask_curve').set(hou.Ramp((hou.rampBasis.Linear,)*2,(0.0,1.0),(0.0,1.0)));a.parm('mask_gamma').set(2.0);a.parmTuple('mask_outrange').set((0.0,0.5));a.parm('mask_curve').set(hou.Ramp((hou.rampBasis.Linear,)*2,(0.0,1.0),(1.0,0.0)))
    assert np.allclose(m.mask_weights(a,raw),0.5*(1.0-raw**0.5),atol=0.01)                                                                                              # the order: gamma, then the curve, then the output range
    a.parm('mask_curve_on').set(0);assert np.allclose(m.mask_weights(a,raw),0.5*raw**0.5)                                                                               # the curve off: it is not applied
    base=out(scatter(st,sc,name='Plain',mask_source=0));P=base['pos'];dist=np.hypot(P[:,0],P[:,2])
    on=out(scatter(st,sc,name='Range',mask_source=4,mask_paint_base=1.0,mask_paint_data=text(stamp(1,0,0,0.0001)),mask_outrange=(0.0,0.4)));assert 0.3<len(on['ids'])/400<0.5   # on a node: output range 0 to 0.4 keeps about 40 percent
    g=out(scatter(st,sc,name='Gamma',mask_source=4,mask_paint_base=0.5,mask_gamma=2.0));assert len(g['ids'])/400>0.55 and set(g['ids'].tolist())>=set(out(scatter(st,sc,name='G1',mask_source=4,mask_paint_base=0.5))['ids'].tolist())   # gamma 2 on a 0.5 mask: more points, and the old ones stay
    flip=out(scatter(st,sc,name='Flip',mask_source=4,mask_paint_data=text(stamp(0,0,0,3.0)),mask_outrange=(1.0,0.0)));inside=base['ids'][dist<2.6];assert not set(inside.tolist())&set(flip['ids'].tolist()) and len(flip['ids'])>200   # flipped: the disc is empty, the rest full
    noise=scatter(st,sc,name='Noise',mask_source=1,mask_noise_freq=0.6,mask_gamma=1.5,mask_curve_on=1);assert not noise.errors() and 0<len(out(noise)['ids'])<400            # the remap works for every mask source

def persistence_and_info():
    st,sc=new_scene('persist');a=scatter(st,sc,name='Info',mask_source=4);m=a.hdaModule();assert 'Nothing painted' in m.maskpaint_info(a)
    stamps=np.array([stamp(0,0,0,2),stamp(1,1,1,2),stamp(0,3,3,2),stamp(2,4,3,2)]);m.maskpaint_apply(a,stamps)
    info=m.maskpaint_info(a);assert '4 stamps' in info and '2 paint' in info and '1 erase' in info and '1 add' in info and 'Painted extent' in info and 'Kept' in m.mask_info(a)
    path=str(WORK/'persist.hip');hou.hipFile.save(path);hou.hipFile.load(path,suppress_save_prompt=True);b=hou.node('/stage/Info');assert np.allclose(b.hdaModule().maskpaint_data(b),stamps)       # saved with the scene
    assert b.hdaModule().maskpaint_clear(b)==4 and len(b.hdaModule().maskpaint_data(b))==0 and b.evalParm('mask_paint_data')==''
    b.parm('mask_paint_data').set('garbage');assert 'cannot be read' in b.hdaModule().maskpaint_info(b)
    try:b.hdaModule().maskpaint_data(b);assert False
    except hou.NodeError as e:assert 'cannot be read' in str(e)
    b.parm('mask_source').set(0);assert 'No mask' in b.hdaModule().mask_info(b)

class StubDrawable(object):
    def __init__(self,*a,**k):self.geo=None;self.shown=False;self.params={}
    def setParams(self,p):self.params.update(p)
    def setGeometry(self,g):self.geo=g
    def show(self,v):self.shown=v
    def draw(self,handle,params=None):self.drawn=True
class StubViewer(object):
    def __init__(self):self.prompt=None
    def setPromptMessage(self,m,t=None):self.prompt=m
    def clearPromptMessage(self):self.prompt=None
class Device(object):
    def __init__(self,x,y,left=False,ctrl=False,key='',shift=False,wheel=0):self.x,self.y,self.left,self.ctrl,self.key,self.shift,self.wheel=x,y,left,ctrl,key,shift,wheel
    def isShiftKey(self):return self.shift
    def mouseWheel(self):return self.wheel
    def mouseX(self):return self.x
    def mouseY(self):return self.y
    def isLeftButton(self):return self.left
    def isCtrlKey(self):return self.ctrl
    def isMiddleButton(self):return False
    def isAltKey(self):return False
    def keyString(self):return self.key
class Event(object):
    """A viewport that looks straight down from y = 50: pixel (x, y) is the ray from (x/10, 50, y/10) along -Y."""
    def __init__(self,device,reason):self.d,self.r=device,reason
    def device(self):return self.d
    def reason(self):return self.r
    def ray(self):x,y=self.d.mouseX(),self.d.mouseY();return hou.Vector3((x/10.0,50.0,y/10.0)),hou.Vector3((0,-1,0))
def make_state(a):
    ns=types.SimpleNamespace(**{k:getattr(hou,k) for k in ('Vector4','Vector3','Geometry','drawableGeometryType','uiEventReason','promptMessageType','Error','lopNodeTypeCategory','ViewerStateTemplate','undos')});ns.GeometryDrawable=StubDrawable
    glob={'hou':ns,'np':np,'__name__':'arraytron_maskpaint_state_test'};exec(compile((ROOT/'src/arraytron_paint_state.py').read_text().replace('import hou'+chr(10),'',1),'arraytron_paint_state.py','exec'),glob);glob['STRICT']=True
    if MUTATE=='mp_live':glob['PaintState']._mask_live=lambda self,force=False:None                                                                                    # the paint is never written while the stroke goes on
    if MUTATE=='mp_ctrl':glob['PaintState']._mask_op=lambda self,dev=None:min(self.node.evalParm('mask_brush_op'),3)                                                   # Ctrl does nothing
    if MUTATE=='mp_heavy':glob['MASK_HEAVY']=()                                                                                                                       # the full operations are written live too
    if MUTATE=='mp_shift':
        good=glob['PaintState']._mask_op;glob['PaintState']._mask_op=lambda self,dev=None:good(self,None if dev is not None and dev.isShiftKey() and not dev.isCtrlKey() else dev)   # Shift does nothing
    return glob,glob['PaintState']('arraytron_maskpaint_test',StubViewer())
def viewer_tool():
    st,sc=new_scene('tool');a=scatter(st,sc,name='Tool',mask_brush_radius=1.0,mask_brush_feather=0.4);m=a.hdaModule();assert a.evalParm('mask_source')==0;a.parm('mask_source').set(4)
    glob,state=make_state(a);viewer=state.scene_viewer;R=hou.uiEventReason
    state.onEnter({'node':a});assert not state.maskpaint and viewer.prompt is None                                                                                      # selecting the node does nothing by itself
    assert state.onMouseEvent({'ui_event':Event(Device(150,150,left=True),R.Start)}) is False and a.evalParm('mask_paint_data')==''
    a.setUserData('arraytron_maskpaint','1');state.onMouseEvent({'ui_event':Event(Device(150,150),R.Located)});assert state.maskpaint and a.evalParm('mode')==1 and not a.userData('arraytron_maskpaint')   # the tool never changes the Distribution Mode
    assert 'Arraytron Mask Paint [Paint]' in viewer.prompt and 'radius 1' in viewer.prompt and 'feather 0.40 (Smooth)' in viewer.prompt and 'value 1.00' in viewer.prompt and 'live' in viewer.prompt and 'Esc / Enter: finish' in viewer.prompt
    assert state.mhit is not None and abs(state.mhit[0][0]-15.0)<1e-9 and abs(state.mhit[0][2]-15.0)<1e-9 and state.brush.shown and state.core.shown                          # the brush follows the ground plane (no surface in Area mode), with the inner ring
    assert a.userData('arraytron_maskviz') and a.evalParm('mask_viz')==1                                                                                                # the mask is shown on the surface while painting
    assert state.onMouseEvent({'ui_event':Event(Device(150,150,left=True),R.Start)}) is True and state.mpainting and len(state.mdata)==1 and state.mdirty
    first=m.maskpaint_decode(a.evalParm('mask_paint_data'));assert len(first)==1                                                                                        # REALTIME: written at once, while the mouse is still down
    state.onMouseEvent({'ui_event':Event(Device(200,150,left=True),R.Active)});assert len(state.mdata)==2 and len(m.maskpaint_decode(a.evalParm('mask_paint_data')))==1   # at most about ten writes a second ...
    time.sleep(0.15);state.onMouseEvent({'ui_event':Event(Device(250,150,left=True),R.Active)});assert len(m.maskpaint_decode(a.evalParm('mask_paint_data')))==3           # ... and the next one has them all
    state.onMouseEvent({'ui_event':Event(Device(260,150,left=True),R.Active)});assert len(state.mdata)==4 and len(m.maskpaint_decode(a.evalParm('mask_paint_data')))==3   # a dab inside the throttle: not written yet
    state.onMouseEvent({'ui_event':Event(Device(260,150,left=False),R.Changed)});saved=m.maskpaint_data(a);assert len(saved)==4 and not state.mpainting and not state.mdirty and len(saved)==len(state.mdata)   # the end of the stroke writes everything
    assert (saved[:,0]==0).all() and np.allclose(saved[:,1],[15,20,25,26]) and np.allclose(saved[:,3],15) and np.allclose(saved[:,4],1.0) and np.allclose(saved[:,5],1.0) and np.allclose(saved[:,6],0.4) and np.allclose(saved[:,7],1.0) and (saved[:,8]==1).all()
    state.onMouseEvent({'ui_event':Event(Device(-150,-150,left=True,ctrl=True),R.Start)});assert 'Erase' in viewer.prompt;state.onMouseEvent({'ui_event':Event(Device(-150,-150,left=True,ctrl=True),R.Changed)})
    two=m.maskpaint_data(a);assert len(two)==5 and two[4,0]==1 and np.allclose(two[4,[1,3]],[-15,-15])                                                                   # Ctrl: Erase instead of Paint
    a.parm('mask_brush_op').set(1);state.onMouseEvent({'ui_event':Event(Device(300,300,left=True,ctrl=True),R.Picked)});assert m.maskpaint_data(a)[5,0]==0                  # with Erase in the menu, Ctrl paints (a plain click: one dab, committed)
    state.onKeyEvent({'ui_event':Event(Device(0,0,key='3'),R.Changed)});assert a.evalParm('mask_brush_op')==2 and '[Add]' in viewer.prompt
    state.onKeyEvent({'ui_event':Event(Device(0,0,key='4'),R.Changed)});assert a.evalParm('mask_brush_op')==3 and '[Subtract]' in viewer.prompt
    state.onKeyEvent({'ui_event':Event(Device(0,0,key='1'),R.Changed)});assert a.evalParm('mask_brush_op')==0
    r0=a.evalParm('mask_brush_radius');assert state.onKeyEvent({'ui_event':Event(Device(0,0,key=']'),R.Changed)}) and a.evalParm('mask_brush_radius')>r0
    s0=a.evalParm('mask_brush_strength');state.onKeyEvent({'ui_event':Event(Device(0,0,key='-'),R.Changed)});assert abs(a.evalParm('mask_brush_strength')-(s0-0.05))<1e-9 and 'strength 0.95' in viewer.prompt
    f0=a.evalParm('mask_brush_feather');state.onKeyEvent({'ui_event':Event(Device(0,0,key='.'),R.Changed)});assert abs(a.evalParm('mask_brush_feather')-(f0+0.05))<1e-9 and 'feather 0.45' in viewer.prompt
    state.onKeyEvent({'ui_event':Event(Device(0,0,key=','),R.Changed)});state.onKeyEvent({'ui_event':Event(Device(0,0,key=','),R.Changed)});assert abs(a.evalParm('mask_brush_feather')-(f0-0.05))<1e-9
    v0=a.evalParm('mask_brush_value');state.onKeyEvent({'ui_event':Event(Device(0,0,key='9'),R.Changed)});assert abs(a.evalParm('mask_brush_value')-(v0-0.1))<1e-9 and 'value 0.90' in viewer.prompt
    state.onKeyEvent({'ui_event':Event(Device(0,0,key='0'),R.Changed)});state.onKeyEvent({'ui_event':Event(Device(0,0,key='0'),R.Changed)});assert a.evalParm('mask_brush_value')==1.0                  # kept inside 0 to 1
    c0=a.evalParm('mask_brush_curve');state.onKeyEvent({'ui_event':Event(Device(0,0,key='f'),R.Changed)});assert a.evalParm('mask_brush_curve')==(c0+1)%3 and 'Gaussian' in viewer.prompt
    r1=a.evalParm('mask_brush_radius');state.onMouseWheelEvent({'ui_event':Event(Device(0,0,wheel=1,shift=True),R.Changed)});assert a.evalParm('mask_brush_radius')>r1
    s1=a.evalParm('mask_brush_strength');state.onMouseWheelEvent({'ui_event':Event(Device(0,0,wheel=-1,ctrl=True),R.Changed)});assert a.evalParm('mask_brush_strength')<s1
    f1=a.evalParm('mask_brush_feather');state.onMouseWheelEvent({'ui_event':Event(Device(0,0,wheel=1,ctrl=True,shift=True),R.Changed)});assert a.evalParm('mask_brush_feather')>f1                # Ctrl + Shift + wheel: the feather
    assert state.onKeyEvent({'ui_event':Event(Device(0,0,key='z'),R.Changed)}) is False and state.onMouseWheelEvent({'ui_event':Event(Device(0,0,wheel=1),R.Changed)}) is False
    state.onKeyEvent({'ui_event':Event(Device(0,0,key='h'),R.Changed)});assert 'Esc / Enter: finish' not in viewer.prompt
    a.parm('mask_paint_live').set(0);n_before=len(m.maskpaint_data(a));state.onMouseEvent({'ui_event':Event(Device(400,400,left=True),R.Start)});state.onMouseEvent({'ui_event':Event(Device(450,400,left=True),R.Active)})
    time.sleep(0.15);state.onMouseEvent({'ui_event':Event(Device(500,400,left=True),R.Active)});assert len(m.maskpaint_data(a))==n_before and len(state.mdata)==n_before+3 and 'live' not in viewer.prompt   # Live Update off: nothing written while dragging
    state.onMouseEvent({'ui_event':Event(Device(500,400,left=False),R.Changed)});assert len(m.maskpaint_data(a))==n_before+3                                                      # ... but at the end of the stroke
    state.onExit({});assert viewer.prompt is None and not state.maskpaint and not a.userData('arraytron_maskviz') and a.evalParm('mask_viz')==0                          # the mask display is switched off again
    a.parm('mask_viz').set(2);a.setUserData('arraytron_maskpaint','1');state.onEnter({'node':a});state.onMouseEvent({'ui_event':Event(Device(150,150),R.Located)});assert a.evalParm('mask_viz')==2 and not a.userData('arraytron_maskviz')   # Visualize already on: left alone
    state.onExit({});assert a.evalParm('mask_viz')==2
    a.parm('mask_viz').set(0);a.parm('mask_paint_show').set(0);a.setUserData('arraytron_maskpaint','1');state.onEnter({'node':a});state.onMouseEvent({'ui_event':Event(Device(150,150),R.Located)});assert a.evalParm('mask_viz')==0   # Show Mask While Painting off
    state.onExit({});a.parm('mask_paint_show').set(1)
    a.parm('mode').set(5);a.parm('surface_prim').set('/World/Nothing');a.setUserData('arraytron_maskpaint','1');state.onEnter({'node':a});state.onMouseEvent({'ui_event':Event(Device(150,150),R.Located)})
    assert state.mwarn and 'ground plane' in viewer.prompt and state.mhit is not None                                                                                   # a missing surface: painting on the ground plane, with a note
    state.onExit({});a.parm('surface_prim').set('/World/Terrain');a.setUserData('arraytron_maskpaint','1');state.onEnter({'node':a});state.onMouseEvent({'ui_event':Event(Device(150,150),R.Located)});assert not state.mwarn and state.mhit is not None   # the Surface Prim of the mode
    state.onExit({});a.parm('mask_paint_prim').set('/World/Terrain');a.setUserData('arraytron_maskpaint','1');state.onEnter({'node':a});state.onMouseEvent({'ui_event':Event(Device(150,150),R.Located)});assert not state.mwarn and state.mhit is not None   # an explicit Paint Surface
    state.onExit({});glob['PaintState']('x',StubViewer()).onEnter({'node':a})

def contract():
    st,sc=new_scene('contract');a=scatter(st,sc,name='C');g=a.parmTemplateGroup()
    for n in ('mask_paint_start','mask_paint_clear','mask_brush_op','mask_brush_radius','mask_brush_strength','mask_brush_feather','mask_brush_value','mask_brush_curve','mask_paint_base','mask_paint_blur','mask_paint_res','mask_paint_live','mask_paint_show','mask_paint_prim','mask_paint_data','mask_gamma','mask_curve_on','mask_curve','mask_outrange'):assert g.find(n) is not None,n
    assert g.find('mask_source').menuLabels()[:5]==('None','Noise','Image','Mesh Primvar','Painted') and a.evalParm('mask_source')==0
    d=lambda n:g.find(n).defaultValue()
    assert d('mask_brush_radius')==(2.0,) and d('mask_brush_strength')==(1.0,) and d('mask_brush_feather')==(0.5,) and d('mask_brush_value')==(1.0,) and d('mask_paint_base')==(0.0,) and d('mask_paint_blur')==(0.0,) and d('mask_paint_res')==(512,)
    assert d('mask_brush_op')==0 and d('mask_brush_curve')==1 and d('mask_paint_live')==True and d('mask_paint_show')==True and d('mask_paint_prim')==('',) and d('mask_gamma')==(1.0,) and d('mask_curve_on')==False and d('mask_outrange')==(0.0,1.0)
    assert g.find('mask_brush_op').menuLabels()[:4]==('Paint','Erase','Add','Subtract') and len(g.find('mask_brush_op').menuLabels())==(11 if FULL else 4) and g.find('mask_brush_curve').menuLabels()==('Linear','Smooth','Gaussian') and g.find('mask_curve').type()==hou.parmTemplateType.Ramp
    assert a.evalParm('mask_paint_data')=='' and g.find('mask_paint_data').isHidden() and g.find('mask_paint_start').scriptCallback().endswith("maskpaint_start(kwargs['node'])") and g.find('mask_paint_clear').scriptCallback().endswith("maskpaint_clear(kwargs['node'])")
    assert a.parm('mask_curve').evalAsRamp().lookup(0.5)==a.parm('mask_curve').evalAsRamp().lookup(0.5)
    text_=a.type().definition().sections()['PythonModule'].contents();assert '$' not in text_.split('# ---- Painted mask')[1]
    state=a.type().definition().sections()['ViewerStateModule'].contents();assert 'self.maskpaint' in state and 'mask_brush_feather' in state
    for n in ('maskpaint_decode','maskpaint_encode','maskpaint_add','maskpaint_profile','maskpaint_spec','maskpaint_raster','maskpaint_blur','maskpaint_sample','maskpaint_values','maskpaint_field','maskpaint_apply','maskpaint_clear','maskpaint_start','maskpaint_info','maskpaint_surface','maskpaint_data'):assert hasattr(a.hdaModule(),n),n
    a.parm('mask_source').set(4)
    try:a.hdaModule().maskpaint_start(a);assert False
    except hou.NodeError as e:assert 'Houdini interface' in str(e)                                                                                                       # no interface in hython
    b=scatter(st,sc,name='Start');b.hdaModule()
    try:b.hdaModule().maskpaint_start(b)
    except hou.NodeError:pass
    assert b.evalParm('mask_source')==4                                                                                                                                # the button switches the Mask Source to Painted first

def full_maths():
    """v1.27.0: Smooth, Multiply, Maximum, Minimum on the map, the menu entries, the mirror images."""
    a,m=module();res=161;st=np.array([stamp(0,0,0,4,1.0,0.0,0.8)]);spec=m.maskpaint_spec(st,res);x0,z0,cell,nx,nz=spec;X,Z=np.meshgrid(x0+np.arange(nx)*cell,z0+np.arange(nz)*cell);Rr=np.hypot(X,Z)
    mult=m.maskpaint_raster(np.vstack([st,[stamp(5,0,0,4,1.0,0.0,0.5)]]),spec,0.0);assert np.allclose(mult[Rr<=3.9],0.4) and np.allclose(mult[Rr>4.1],0.0)                       # Multiply: 0.8 x 0.5
    half=m.maskpaint_raster(np.vstack([st,[stamp(5,0,0,4,0.5,0.0,0.5)]]),spec,0.0);assert np.allclose(half[Rr<=3.9],0.6)                                                  # ... half way at strength 0.5
    mx=m.maskpaint_raster(np.vstack([st,[stamp(6,0,0,4,1.0,0.0,0.95)]]),spec,0.0);assert np.allclose(mx[Rr<=3.9],0.95);keep=m.maskpaint_raster(np.vstack([st,[stamp(6,0,0,4,1.0,0.0,0.5)]]),spec,0.0);assert np.allclose(keep[Rr<=3.9],0.8)   # Maximum raises, never lowers
    mn=m.maskpaint_raster(np.vstack([st,[stamp(7,0,0,4,1.0,0.0,0.5)]]),spec,0.0);assert np.allclose(mn[Rr<=3.9],0.5);keep=m.maskpaint_raster(np.vstack([st,[stamp(7,0,0,4,1.0,0.0,0.95)]]),spec,0.0);assert np.allclose(keep[Rr<=3.9],0.8)   # Minimum lowers, never raises
    hard=m.maskpaint_raster(np.array([stamp(0,0,0,3,1.0,0.0,1.0)]),spec,0.0);sm=m.maskpaint_raster(np.array([stamp(0,0,0,3,1.0,0.0,1.0),stamp(4,0,0,4.6,1.0,0.0)]),spec,0.0)   # Smooth over the edge of a hard disc
    gy=lambda g:np.abs(np.diff(g,axis=1)).max();assert gy(sm)<0.6*gy(hard) and abs(sm.sum()-hard.sum())<0.01*hard.sum() and (sm[Rr>4.9]==hard[Rr>4.9]).all() and sm[Rr<=1.0].min()>0.99   # the edge is softer, the volume kept, nothing outside the brush, the middle intact
    flat=m.maskpaint_raster(np.array([stamp(4,0,0,3,1.0)]),spec,0.37);assert np.allclose(flat,0.37)                                                                      # smoothing a flat map changes nothing
    none=m.maskpaint_raster(np.array([stamp(0,0,0,3,1.0,0.0,1.0),stamp(4,0,0,3.4,0.0,0.0)]),spec,0.0);assert np.array_equal(none,hard)                                    # strength 0: nothing
    assert m.maskpaint_stamp_for(0,0.7,0.2)==(0,0.7) and m.maskpaint_stamp_for(1,0.7,0.2)==(1,0.7) and m.maskpaint_stamp_for(4,0.7,0.2)==(4,0.7) and m.maskpaint_stamp_for(7,0.7,0.2)==(7,0.7)
    assert m.maskpaint_stamp_for(8,0.7,0.2)==(0,0.2) and m.maskpaint_stamp_for(9,0.7,0.2) is None and m.maskpaint_stamp_for(10,0.7,0.2) is None                                    # Paint Background uses the Background value; the samplers paint nothing
    assert m.maskpaint_mirrors((3,1,2),False,False,(0,0))==[(3,1,2)] and m.maskpaint_mirrors((3,1,2),True,False,(0,0))==[(3,1,2),(-3,1,2)] and m.maskpaint_mirrors((3,1,2),False,True,(0,0))==[(3,1,2),(3,1,-2)]
    four=m.maskpaint_mirrors((3,1,2),True,True,(1,-1));assert sorted((round(p[0],6),round(p[2],6)) for p in four)==[(-1.0,-4.0),(-1.0,2.0),(3.0,-4.0),(3.0,2.0)] and all(p[1]==1 for p in four)   # four-way, about the Symmetry Center
    assert len(m.maskpaint_mirrors((0,0,5),True,False,(0,0)))==1 and len(m.maskpaint_mirrors((0,0,0),True,True,(0,0)))==1                                                    # a dab on a mirror plane is not doubled
    assert len(m.MASKPAINT_OPS)==8 and len(m.MASKPAINT_MENU)==11 and m.MASKPAINT_MENU[:4]==('Paint','Erase','Add','Subtract')

def full_node():
    st,sc=new_scene('full');base=out(scatter(st,sc,name='None',mask_source=0));P=base['pos'];dist=np.hypot(P[:,0],P[:,2]);R=3.0
    c=scatter(st,sc,name='C');g=c.parmTemplateGroup();d=lambda n:g.find(n).defaultValue()                                                                                    # the contract of the full brush
    for n in ('mask_brush_bg','mask_brush_op_shift','mask_brush_op_ctrl','mask_sym_x','mask_sym_z','mask_sym_center','mask_paint_fill'):assert g.find(n) is not None,n
    assert d('mask_brush_bg')==(0.0,) and d('mask_brush_op_shift')==4 and d('mask_brush_op_ctrl')==11 and d('mask_sym_x')==False and d('mask_sym_z')==False and d('mask_sym_center')==(0.0,0.0)
    assert g.find('mask_brush_op').menuLabels()[4:]==('Smooth','Multiply','Maximum','Minimum','Paint Background','Sample Foreground','Sample Background') and g.find('mask_brush_op_ctrl').menuLabels()[-1]=='Opposite' and len(g.find('mask_brush_op_shift').menuLabels())==12
    assert g.find('mask_brush_value').label()=='Foreground Value' and g.find('mask_paint_fill').scriptCallback().endswith("maskpaint_fill(kwargs['node'])") and g.find('mask_brush_op').menuLabels()[:4]==('Paint','Erase','Add','Subtract')
    for n in ('maskpaint_stamp_for','maskpaint_mirrors','maskpaint_fill','maskpaint_value_at'):assert hasattr(c.hdaModule(),n),n
    a=scatter(st,sc,name='Fill',mask_source=4,mask_brush_value=1.0,mask_paint_data=text(stamp(0,0,0,R)));m=a.hdaModule();assert m.maskpaint_fill(a)==1 and a.evalParm('mask_paint_data')=='' and a.evalParm('mask_paint_base')==1.0   # Fill: the Foreground everywhere
    assert np.array_equal(out(a)['ids'],base['ids'])                                                                                                                       # ... a full scatter
    a.parm('mask_paint_data').set(text(stamp(1,0,0,R)));hole=out(a);assert not set(hole['ids'].tolist())&set(base['ids'][dist<R-0.1].tolist()) and len(hole['ids'])>150      # then Erase a hole in it
    b=scatter(st,sc,name='Fg',mask_source=4,mask_brush_value=0.5);b.hdaModule().maskpaint_fill(b);assert 0.35<len(out(b)['ids'])/400<0.65                                  # Fill with 0.5: half the scatter
    smooth=out(scatter(st,sc,name='Smooth',mask_source=4,mask_paint_data=text(stamp(0,0,0,R,1.0,0.0,1.0),stamp(4,0,0,R*1.2,1.0,0.0))));plain=out(scatter(st,sc,name='Hard',mask_source=4,mask_paint_data=text(stamp(0,0,0,R,1.0,0.0,1.0))))
    assert len(smooth['ids'])>0 and set(smooth['ids'].tolist())!=set(plain['ids'].tolist()) and (np.hypot(smooth['pos'][:,0],smooth['pos'][:,2])<=R+0.8).all()              # a smoothed edge on a node
    same=st.createNode(OLD_TYPE,'Old');same.setInput(0,sc);same.parm('protos').set(1);same.parm('proto_prim1').set('/World/Props/Tree');same.parm('mode').set(1);same.parmTuple('area_sizex').set((10.0,));same.parmTuple('area_sizez').set((10.0,));same.parm('area_count').set(400);same.parm('area_seed').set(3)
    same.parm('mask_source').set(4);same.parm('mask_paint_data').set(text(stamp(0,0,0,R,0.7,0.4),stamp(1,1,1,1.5),stamp(2,-2,0,2,0.5,0.5,0.4),stamp(3,0,-2,2,0.5,0.5,0.4)));new=scatter(st,sc,name='New',mask_source=4,mask_paint_data=same.evalParm('mask_paint_data'))
    po=out(same);pn=out(new);assert np.array_equal(po['ids'],pn['ids']) and np.array_equal(po['pos'],pn['pos'])                                                          # a v1.26.0 painting (the old four operations) gives the same scatter

def full_tool():
    st,sc=new_scene('fulltool');a=scatter(st,sc,name='Tool',mask_source=4,mask_brush_radius=1.0,mask_brush_feather=0.0,mask_brush_value=0.3,mask_brush_bg=0.1,mask_paint_live=0);m=a.hdaModule()
    glob,state=make_state(a);viewer=state.scene_viewer;R=hou.uiEventReason;a.setUserData('arraytron_maskpaint','1');state.onEnter({'node':a});state.onMouseEvent({'ui_event':Event(Device(150,150),R.Located)});assert state.maskpaint
    click=lambda x,y,**k:(state.onMouseEvent({'ui_event':Event(Device(x,y,left=True,**k),R.Picked)}),m.maskpaint_data(a))[1]
    d=click(150,150);assert len(d)==1 and d[0,0]==0 and abs(d[0,7]-0.3)<1e-9                                                                                                   # Paint: the Foreground value
    a.parm('mask_brush_op').set(8);d=click(-150,150);assert len(d)==2 and d[1,0]==0 and abs(d[1,7]-0.1)<1e-9 and '[Paint Background]' in viewer.prompt                           # Paint Background: the Background value
    a.parm('mask_brush_value').set(0.9);a.parm('mask_brush_op').set(9);n0=len(m.maskpaint_data(a));d=click(150,150);assert len(d)==n0 and abs(a.evalParm('mask_brush_value')-0.3)<1e-3 and state.msampled is not None   # Sample Foreground: reads 0.3 off the mask, paints nothing
    a.parm('mask_brush_op').set(10);d=click(900,900);assert len(d)==n0 and abs(a.evalParm('mask_brush_bg')-0.0)<1e-9                                                           # Sample Background: 0 where nothing is painted
    state.onKeyEvent({'ui_event':Event(Device(0,0,key='x'),R.Changed)});assert abs(a.evalParm('mask_brush_value')-0.0)<1e-9 and abs(a.evalParm('mask_brush_bg')-0.3)<1e-3          # X swaps Foreground and Background
    state.onKeyEvent({'ui_event':Event(Device(0,0,key='x'),R.Changed)})
    for key,menu in (('5',4),('6',8),('7',9),('8',10),('1',0)):state.onKeyEvent({'ui_event':Event(Device(0,0,key=key),R.Changed)});assert a.evalParm('mask_brush_op')==menu       # keys 1 to 8
    n1=len(m.maskpaint_data(a));assert a.evalParm('mask_brush_op_shift')==4 and a.evalParm('mask_brush_op_ctrl')==11
    d=click(300,300,shift=True);assert len(d)==n1+1 and d[-1,0]==4 and 'Smooth' in viewer.prompt                                                                              # Shift: Smooth
    a.parm('mask_brush_op_ctrl').set(8);d=click(400,300,ctrl=True);assert len(d)==n1+2 and d[-1,0]==0 and abs(d[-1,7]-a.evalParm('mask_brush_bg'))<1e-9                           # a Ctrl menu entry of its own: Paint Background
    a.parm('mask_brush_op_ctrl').set(11);d=click(500,300,ctrl=True);assert d[-1,0]==1                                                                                          # Opposite: Erase
    a.parm('mask_brush_op_ctrl').set(9);n2=len(d);d=click(150,150,ctrl=True);assert len(d)==n2 and abs(a.evalParm('mask_brush_value')-0.3)<1e-3;a.parm('mask_brush_op_ctrl').set(11)   # Ctrl can sample too
    n3=len(m.maskpaint_data(a));a.parm('mask_sym_x').set(1);a.parmTuple('mask_sym_center').set((0.0,0.0));d=click(600,200);assert len(d)==n3+2 and sorted(np.round(d[-2:,1],6).tolist())==[-60.0,60.0] and np.allclose(d[-2:,3],20.0)   # Symmetry X: two dabs
    a.parm('mask_sym_z').set(1);d2=click(700,200);assert len(d2)==len(d)+4 and 'symmetry X Z' in viewer.prompt                                                                    # both planes: four dabs
    a.parm('mask_sym_x').set(0);a.parm('mask_sym_z').set(0);r0=a.evalParm('mask_brush_radius');n4=len(m.maskpaint_data(a))
    state.onMouseEvent({'ui_event':Event(Device(100,100,left=True,ctrl=True,shift=True),R.Start)});state.onMouseEvent({'ui_event':Event(Device(250,100,left=True,ctrl=True,shift=True),R.Active)})
    assert abs(a.evalParm('mask_brush_radius')-2.0*r0)<1e-6 and not state.mpainting and 'radius 2' in viewer.prompt;state.onMouseEvent({'ui_event':Event(Device(250,100,left=False),R.Changed)})
    assert state.mresize is None and len(m.maskpaint_data(a))==n4                                                                                                              # Ctrl+Shift drag resizes the brush, paints nothing
    state.onMouseEvent({'ui_event':Event(Device(150,150),R.Located)});assert 'mask here 0.30' in viewer.prompt                                                                 # the mask value under the brush is shown
    a.parm('mask_paint_live').set(1);a.parm('mask_brush_op').set(4);n5=len(m.maskpaint_data(a))                                                                                  # the full operations are not live, only applied at the end of the stroke
    state.onMouseEvent({'ui_event':Event(Device(300,300,left=True),R.Start)});time.sleep(0.15);state.onMouseEvent({'ui_event':Event(Device(400,300,left=True),R.Active)})
    assert len(state.mdata)==n5+2 and len(m.maskpaint_data(a))==n5;state.onMouseEvent({'ui_event':Event(Device(400,300,left=False),R.Changed)});assert len(m.maskpaint_data(a))==n5+2
    a.parm('mask_brush_op').set(0);state.onMouseEvent({'ui_event':Event(Device(300,500,left=True),R.Start)});assert len(m.maskpaint_data(a))==n5+3;state.onMouseEvent({'ui_event':Event(Device(300,500,left=False),R.Changed)})   # Paint is still live
    state.onExit({})

def unchanged():
    st,sc=new_scene('same');values=dict(mask_source=1,mask_noise_freq=0.6,mask_noise_contrast=2.5,mask_low=0.2,mask_high=0.9,mask_effect=2,mask_minscale=0.3,mask_invert=1)
    pa=out(scatter(st,sc,name='N',**values));ob=st.createNode(OLD_TYPE,'O');ob.setInput(0,sc);ob.parm('protos').set(1);ob.parm('proto_prim1').set('/World/Props/Tree');ob.parm('mode').set(1)
    ob.parmTuple('area_sizex').set((10.0,));ob.parmTuple('area_sizez').set((10.0,));ob.parm('area_count').set(400);ob.parm('area_seed').set(3)
    for k,v in values.items():ob.parm(k).set(v)
    pb=out(ob);assert len(pa['ids'])>50 and np.array_equal(pa['ids'],pb['ids']) and np.array_equal(pa['pos'],pb['pos'])                                                 # the defaults of the new controls: the previous release exactly
    pc=out(scatter(st,sc,name='Plain',mask_source=0));pd=st.createNode(OLD_TYPE,'P');pd.setInput(0,sc);pd.parm('protos').set(1);pd.parm('proto_prim1').set('/World/Props/Tree');pd.parm('mode').set(1)
    pd.parmTuple('area_sizex').set((10.0,));pd.parmTuple('area_sizez').set((10.0,));pd.parm('area_count').set(400);pd.parm('area_seed').set(3);pe=out(pd);assert np.array_equal(pc['pos'],pe['pos'])   # no mask: the same too

def main():
    for name,func in (('Maths: the stamps (text, spacing, limit), the brush profile (feather, curves), the map against brute force, paint / erase / add / subtract in order, airbrush, base, blur, sampling, cache',maths),
                      ('On a node: Paint, Brush Value, strength, Unpainted Value, Erase, feather, Map Feather, resolution, Scale effect',painted_node),
                      ('The remap: Gamma, Remap Curve, Output Range on the weights and on nodes, for every source',remap),
                      ('The text saved with the scene, the read-out, clearing, a broken text',persistence_and_info),
                      ('The viewport tool through a stand-in viewport: idle until asked, brush, REALTIME writes while dragging, commit, Ctrl, operations, keys, wheel, Live Update off, mask display, surfaces',viewer_tool),
                      ('Contract: parameters, defaults, hidden data, module functions, no dollar signs, no interface',contract),
                      ('The previous release unchanged with the new controls at their defaults',unchanged))+(((
                      ('Full brush maths: Multiply, Maximum, Minimum, Smooth on the map, the menu entries, the mirror images',full_maths),
                      ('Full brush on nodes: Fill, a smoothed edge, a v1.26.0 painting gives the same scatter',full_node),
                      ('Full brush tool: Foreground / Background, Sample, swap, keys, Shift and Ctrl menus, symmetry, drag-resize, the value under the brush',full_tool)) if FULL else ())):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_maskpaint_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
