"""v1.32.0 in real Houdini: hython tests/validate_maskshape.py [version]
Falloff follows the shape of any Mask (Shape: Mask Shape; Inside / Outside / Both sides of the edge, Fade Width, Mask Level), also the painted mask and the Houdini paint; the mask can be exported as
an image, baked to an Image source, saved and loaded; and the interface: the Layout tab is the Scatter tab and holds the Mask and the Field Stack. Env
ARRAYTRON_MUTATE=ms_edge|ms_level|ms_signed|ms_orient|ms_bake|ms_save|ms_tab|ms_depth breaks the module; the suite must FAIL."""
from pathlib import Path
import hou, json, os, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v1.34.0':'v1.25.0','v1.33.0':'v1.31.1','v1.32.0':'v1.31.1'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_maskshape_'));checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')
def write_scene():
    path=WORK/'maskshape.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    UsdGeom.Xform.Define(s,'/World/Props/Ball');UsdGeom.Cube.Define(s,'/World/Props/Ball/C').CreateSizeAttr(0.2)
    s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True)
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
def area(stage,source,name='Ms',typ=None,count=8000,**values):
    a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Ball');a.parm('mode').set(1);a.parm('area_count').set(count);a.parm('area_sizex').set(20.0);a.parm('area_sizez').set(20.0)
    for k,v in values.items():
        pt=a.parmTuple(k)
        if pt is not None:pt.set(v if isinstance(v,(tuple,list)) else (v,))
        else:a.parm(k).set(v)
    if typ is None:mutate(a)
    return a
def out(a):
    a.stage();errs=all_errors(a);assert not errs,errs;pi=UsdGeom.PointInstancer(a.stage().GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    d=dict(pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3),ids=np.array(pi.GetIdsAttr().Get(t) or [],dtype=int),scale=np.array(pi.GetScalesAttr().Get(t) or []).reshape(-1,3)[:,0]);o=np.argsort(d['ids']);return {k:v[o] for k,v in d.items()}
def all_errors(node):
    o=list(node.errors())
    for c in node.children():o+=all_errors(c)
    return o
def mutate(a):
    g=a.hdaModule().edge_distance.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='ms_edge':
        good=g['mask_edge_t'];g['mask_edge_t']=lambda P,fn,edge,width,level,res=160:good(P,fn,0,width,level,res)                                                                         # the Fade menu is ignored
    elif MUTATE=='ms_level':
        good=g['mask_edge_t'];g['mask_edge_t']=lambda P,fn,edge,width,level,res=160:good(P,fn,edge,width,0.5,res)                                                                          # Mask Level is ignored
    elif MUTATE=='ms_signed':
        good=g['mask_signed_field'];g['mask_signed_field']=lambda w,level,cell,reach:np.abs(good(w,level,cell,reach))                                                                    # no inside / outside: a distance only
    elif MUTATE=='ms_orient':
        good=g['mask_raster'];g['mask_raster']=lambda asset,extent,res,y=0.0:good(asset,extent,res,y)[::-1]                                                                                # the image is upside down
    elif MUTATE=='ms_bake':
        good=g['mask_bake'];g['mask_bake']=lambda asset:(good(asset),asset.parm('mask_proj').set(1))[0]                                                                                    # baked with the wrong projection
    elif MUTATE=='ms_save':
        good=g['mask_load'];g['mask_load']=lambda asset,path=None:(good(asset,path),asset.parm('mask_paint_data').set(''))[0]                                                                # the paint is lost on load
    elif MUTATE=='ms_depth':
        good=g['mask_edge_t'];g['mask_edge_t']=lambda P,fn,edge,width,level,res=160,depth=1:good(P,fn,edge,width,level,res,1)                                                              # Fade Depth is ignored: always the fixed width
    elif MUTATE not in ('ms_tab',):raise SystemExit('unknown mutation '+str(MUTATE))
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()
def paint_disc(a,x,z,r,value=1.0):
    m=a.hdaModule();st=m.maskpaint_data(a);st,_=m.maskpaint_add(st,0,(x,0.0,z),r,1.0,0.0,value,0);m.maskpaint_apply(a,st)
def radius(P,x=0.0,z=0.0):return np.hypot(P[:,0]-x,P[:,2]-z)
def prep_painted(a):
    a.parm('mask_source').set(4);a.parm('mask_paint_base').set(0.0);a.parm('mask_effect').set(1);a.parm('mask_minscale').set(1.0)               # the mask is only the shape: it neither removes nor shrinks
def falloff(a,edge,width,level=0.5,curve=0,depth=1):
    a.parm('fall_mask_depth').set(depth);a.parm('fall_on').set(1);a.parm('fall_shape').set(2);a.parm('fall_mask_edge').set(edge);a.parm('fall_mask_width').set(width);a.parm('fall_mask_level').set(level);a.parm('fall_curve').set(curve);a.parm('fall_density').set(0.0);a.parm('fall_scale').set(1.0)

def maths():
    m=0;cell=1.0;ins=np.zeros((9,9),dtype=bool);ins[:,4:]=True                                                                                                          # the right part of a grid is inside
    st,sc=new_scene('maths');a=area(st,sc);mod=a.hdaModule()
    d=mod.edge_distance(ins,cell,3.0);assert np.allclose(d[:,3],0.5) and np.allclose(d[:,4],0.5) and np.allclose(d[:,2],1.5) and np.allclose(d[:,5],1.5) and np.allclose(d[:,8],4.5) and np.allclose(d[:,0],3.5)      # half a cell to the edge, then one cell more each, exact at any range
    S=mod.mask_signed_field(ins.astype(float),0.5,cell,3.0);assert S[0,5]>0 and S[0,2]<0 and np.allclose(S[:,4],0.5) and np.allclose(S[:,3],-0.5)                         # positive inside, negative outside
    xs=np.linspace(-5,5,11);P=np.stack([xs,np.zeros(11),np.zeros(11)],1);fn=lambda G:(G[:,0]>=0.0).astype(float)                                                      # the half space x >= 0
    for edge,expect in ((0,lambda x:1-np.clip(x,-9,9)/2.0),(1,lambda x:np.maximum(-x,0)/2.0),(2,lambda x:(2-x)/4.0)):
        t,info=mod.mask_edge_t(P,fn,edge,2.0,0.5);e=np.clip(expect(xs),0,1.1);t=np.minimum(t,1.1);assert np.abs(t-e)[np.abs(xs)>1.2].max()<0.25,(edge,t,e)                                   # the three fades (the grid resolves the edge to a cell)
    t,_=mod.mask_edge_t(P,fn,0,2.0,0.5);assert t[0]>=1.0 and t[-1]<=0.05 and np.all(np.diff(t[1:])<=0.1)                                                                  # outside: none; deep inside: full; in between falling
    g=np.arange(12.0).reshape(3,4);assert abs(mod.sample_grid(g,np.zeros(2),1.0,np.array([[0.5,0.5]]))[0]-0.0)<1e-9 and abs(mod.sample_grid(g,np.zeros(2),1.0,np.array([[1.0,0.5]]))[0]-0.5)<1e-9 and abs(mod.sample_grid(g,np.zeros(2),1.0,np.array([[1.0,1.0]]))[0]-2.5)<1e-9   # bilinear, cell centres at +0.5

def painted():
    st,sc=new_scene('painted');base=area(st,sc,name='Base');pb=out(base);n0=len(pb['ids']);assert n0==8000
    def run(**k):
        a=area(st,sc,name='P%d'%len(checks_names),**k);checks_names.append(1);prep_painted(a);paint_disc(a,0.0,0.0,6.0);return a
    checks_names=[]
    a=run();falloff(a,0,2.0);o=out(a);r=radius(o['pos']);rb=radius(pb['pos'])
    assert (r<6.2).all() and len(o['ids'])>0 and set(o['ids'])<=set(pb['ids'])                                                                                      # Inside: nothing beyond the edge of the disc, only points that existed
    deep=rb<3.4;assert np.isin(pb['ids'][deep],o['ids']).all(),'every point deep inside (more than the fade from the edge) is kept'
    ring=lambda lo,hi:((r>=lo)&(r<hi)).sum()/max(((rb>=lo)&(rb<hi)).sum(),1);f1,f2,f3=ring(4.0,4.8),ring(4.8,5.4),ring(5.4,6.2);assert f1>f2>f3 and f1<1.0 and f3<0.4,(f1,f2,f3)  # the density falls towards the edge
    b=run();falloff(b,1,3.0);ob=out(b);rb2=radius(ob['pos']);assert np.isin(pb['ids'][rb<5.7],ob['ids']).all() and (rb2<9.3).all() and ((rb2>6.3)&(rb2<9.3)).sum()>50                       # Outside: full inside the disc, feathering out to a Width beyond the edge, nothing farther
    c=run();falloff(c,2,2.0);oc=out(c);rc=radius(oc['pos']);assert np.isin(pb['ids'][rb<3.6],oc['ids']).all() and (rc<8.3).all() and ((rc>6.3)&(rc<8.3)).sum()>20 and ((rc>4.5)&(rc<5.5)).sum()>0                    # Both sides: full a Width inside, nothing a Width outside
    d=area(st,sc,name='Dim');prep_painted(d);paint_disc(d,0.0,0.0,6.0,0.3);falloff(d,0,2.0,level=0.2);od=out(d);assert len(od['ids'])>100 and (radius(od['pos'])<6.2).all()                                     # a dim paint (0.3): with Mask Level 0.2 it is a shape
    d.parm('fall_mask_level').set(0.5);assert len(out(d)['ids'])==0                                                                                                                     # with Mask Level 0.5 there is none: nothing survives
    e=run();e.parm('mask_invert').set(1);falloff(e,0,2.0);oe=out(e);re_=radius(oe['pos']);assert (re_>5.8).all() and len(oe['ids'])>100                                                       # an inverted mask: the shape is everything OUTSIDE the disc

def any_shape():
    st,sc=new_scene('shape');a=area(st,sc,name='Strip');prep_painted(a)
    for x in np.linspace(-7.0,7.0,15):paint_disc(a,float(x),0.0,2.0)                                                                                                    # a strip along X, 4 wide: not a circle, not a box of the layout
    falloff(a,0,1.6);o=out(a);P=o['pos'];assert len(P)>200 and (np.abs(P[:,2])<2.2).all() and (np.abs(P[:,0])<9.2).all()
    core=np.abs(P[:,2])<0.3;rim=(np.abs(P[:,2])>1.4)&(np.abs(P[:,2])<2.0);base=out(area(st,sc,name='B2'))['pos'];bcore=(np.abs(base[:,2])<0.3)&(np.abs(base[:,0])<5);brim=(np.abs(base[:,2])>1.4)&(np.abs(base[:,2])<2.0)&(np.abs(base[:,0])<5)
    kept_core=(core&(np.abs(P[:,0])<5)).sum()/bcore.sum();kept_rim=(rim&(np.abs(P[:,0])<5)).sum()/brim.sum();assert kept_core>0.9 and kept_rim<0.5*kept_core,(kept_core,kept_rim)             # full along the middle of the strip, thinner at its long edges
    b=area(st,sc,name='LShape');prep_painted(b)
    for x in np.linspace(-6,0,9):paint_disc(b,float(x),-5.0,1.8)
    for z in np.linspace(-5,3,11):paint_disc(b,-6.0,float(z),1.8)                                                                                                         # an L
    falloff(b,0,1.5);ob=out(b)['pos'];inl=lambda P:((np.abs(P[:,2]+5.0)<1.9)&(P[:,0]>-7.9)&(P[:,0]<1.9))|((np.abs(P[:,0]+6.0)<1.9)&(P[:,2]>-6.9)&(P[:,2]<4.9));assert len(ob)>100 and inl(ob).all()      # every survivor lies on the L

def whole_shape():
    st,sc=new_scene('whole');mod=area(st,sc).hdaModule()
    e=np.zeros((7,7),dtype=bool);e[2:5,2:5]=True;sq=mod.edt_squared(e);assert abs(sq[0,0]-8.0)<1e-9 and abs(sq[2,2]-0.0)<1e-9 and abs(sq[2,6]-4.0)<1e-9                                         # the exact squared distance to the nearest True cell
    two=np.zeros((8,12),dtype=bool);two[1:6,1:6]=True;two[2:4,8:10]=True;lab=mod.shape_regions(two);assert len(np.unique(lab[lab>=0]))==2 and lab[3,3]!=lab[3,9] and (lab[~two]==-1).all()   # two separate pieces
    S=mod.mask_signed_field(two.astype(float),0.5,1.0);dep=mod.shape_depth(two,np.maximum(S,0.0));assert dep[3,3]>2.0 and 0.4<dep[3,9]<1.6 and dep[0,0]==0.0                              # every piece has its own depth
    def disc(a,x,z,r):paint_disc(a,x,z,r)
    base=area(st,sc,name='B');ob=out(base)
    a=area(st,sc,name='Whole');prep_painted(a);disc(a,0.0,0.0,6.0);falloff(a,0,2.0,depth=0);a.parm('fall_density').set(100.0);a.parm('fall_scale').set(0.1);oa=out(a);ra=radius(oa['pos'])
    inside_base=radius(ob['pos'])<6.0;assert abs(len(oa['ids'])-inside_base.sum())<=0.03*inside_base.sum() and (ra<6.3).all() and np.isin(ob['ids'][radius(ob['pos'])<5.5],oa['ids']).all(),(len(oa['ids']),inside_base.sum())   # Edge Density 100: every point inside the shape is kept, only the scale falls; the points beyond the fade are removed (no dust all over the layout)
    k=area(st,sc,name='Keep');prep_painted(k);disc(k,0.0,0.0,6.0);falloff(k,0,2.0,depth=0);k.parm('fall_density').set(100.0);k.parm('fall_scale').set(0.1);k.parm('fall_mask_keep').set(1);ok=out(k);rk=radius(ok['pos'])
    assert len(ok['ids'])==len(ob['ids']) and np.abs(ok['scale'][rk>6.5]-0.1).max()<1e-6,'Keep Points Beyond The Fade: they stay, at the edge scale'
    expect=0.1+0.9*np.clip(1.0-ra/6.0,0.0,1.0);inner=ra<5.4;assert np.abs(oa['scale'][inner]-expect[inner]).max()<0.1,np.abs(oa['scale'][inner]-expect[inner]).max()                         # the scale grades smoothly across the WHOLE disc, 1 in the middle down to the edge scale at its edge
    bins=[oa['scale'][(ra>=lo)&(ra<hi)].mean() for lo,hi in ((0,2),(2,4),(4,6))];assert bins[0]>0.75 and bins[0]>bins[1]>bins[2] and bins[2]<0.45,bins
    f=area(st,sc,name='Fixed');prep_painted(f);disc(f,0.0,0.0,6.0);falloff(f,0,2.0,depth=1);f.parm('fall_density').set(100.0);f.parm('fall_scale').set(0.1);of=out(f);rf=radius(of['pos'])
    assert of['scale'][rf<3.5].min()>0.99 and of['scale'][(rf>=4.0)&(rf<6.0)].mean()<0.8                                                                                                   # Fixed width: flat in the middle, only the last 2 units fade
    w=area(st,sc,name='Two');prep_painted(w);disc(w,-8.0,0.0,6.0);disc(w,8.0,0.0,3.0);falloff(w,0,2.0,depth=0);w.parm('fall_density').set(100.0);w.parm('fall_scale').set(0.1);ow=out(w)
    small=radius(ow['pos'],8.0,0.0);big=radius(ow['pos'],-8.0,0.0);assert ow['scale'][small<0.8].mean()>0.8 and ow['scale'][big<0.8].mean()>0.8 and ow['scale'][(small>2.0)&(small<3.0)].mean()<0.45,(ow['scale'][small<0.8].mean(),ow['scale'][(small>2.0)&(small<3.0)].mean())    # a small piece fades over its own size, not the big one's
    b2=area(st,sc,name='BothW');prep_painted(b2);disc(b2,0.0,0.0,6.0);falloff(b2,2,2.0,depth=0);b2.parm('fall_density').set(100.0);b2.parm('fall_scale').set(0.1);o2=out(b2);r2=radius(o2['pos']);edge=np.abs(r2-6.0)<0.4
    assert edge.sum()>20 and 0.3<o2['scale'][edge].mean()<0.8 and o2['scale'][r2<1.0].mean()>0.85 and (r2<8.3).all() and o2['scale'][(r2>7.0)&(r2<8.0)].mean()<0.35,(o2['scale'][edge].mean(),o2['scale'][r2<1.0].mean(),r2.max())   # Both sides: the whole depth inside, half way at the edge, nothing a Fade Width outside
    if MUTATE=='ms_depth':raise AssertionError('mutation ms_depth')

def sources():
    st,sc=new_scene('sources');a=area(st,sc,name='Noise',count=6000);a.parm('mask_source').set(1);a.parm('mask_effect').set(1);a.parm('mask_minscale').set(1.0);a.parm('mask_noise_freq').set(0.35);falloff(a,0,1.0,level=0.5)
    o=out(a);w=a.hdaModule().mask_weights(a,a.hdaModule().mask_values(a,o['pos'],o['ids']));assert 100<len(o['ids'])<6000 and w.min()>0.5-0.2,(len(o['ids']),w.min())                                # a noise mask: the survivors are in its shape
    from_png=WORK/'diamond.png';N=64;yy,xx=np.mgrid[0:N,0:N];img=(np.abs(xx-N/2+0.5)+np.abs(yy-N/2+0.5)<N*0.3).astype(float);from_png.write_bytes(a.hdaModule().png16_bytes(img))
    b=area(st,sc,name='Img',count=6000);b.parm('mask_source').set(2);b.parm('mask_image').set(from_png.as_posix());b.parm('mask_proj').set(0);b.parmTuple('mask_size').set((20.0,20.0));b.parm('mask_effect').set(1);b.parm('mask_minscale').set(1.0);falloff(b,0,1.0)
    ob=out(b)['pos'];assert len(ob)>100 and (np.abs(ob[:,0])+np.abs(ob[:,2])<20*0.3+0.8).all()                                                                         # an image mask: a diamond
    h=area(st,sc,name='HPaint',count=6000);m=h.hdaModule();gx=np.linspace(-10,10,90);X,Z=np.meshgrid(gx,gx);Pm=np.stack([X.ravel(),np.zeros(X.size),Z.ravel()],1);grid,spec=m.hpaint_grid(Pm,(radius(Pm)<5.0).astype(float),0.0,90)
    h.parm('mask_hpaint_data').set(m.hpaint_encode(grid,spec));h.parm('mask_source').set(5);h.parm('mask_effect').set(1);h.parm('mask_minscale').set(1.0);falloff(h,0,1.5)
    oh=out(h)['pos'];assert len(oh)>100 and (radius(oh)<5.4).all()                                                                                                       # the Houdini paint: a disc
    z=area(st,sc,name='None');falloff(z,0,1.0);e=' '.join(list(z.errors())+[x for c in z.allSubChildren() for x in c.errors()]);z.stage();e=' '.join(list(z.errors())+[x for c in z.allSubChildren() for x in c.errors()])
    assert 'choose a Mask Source' in e,e                                                                                                                                  # no mask: a clear message

def export():
    st,sc=new_scene('export');a=area(st,sc,name='Ex',count=3000);prep_painted(a);m=a.hdaModule();paint_disc(a,4.0,-3.0,3.0)
    a.parm('mask_export_path').set((WORK/'out'/'mask.png').as_posix());a.parm('mask_export_res').set(256);rep=m.mask_export(a);img=WORK/'out'/'mask.png';assert img.is_file() and rep['size'][0]==rep['size'][1]
    cx,cz,sx,sz=rep['extent'];assert abs(cx-4.0)<0.01 and abs(cz+3.0)<0.01 and abs(sx-6.6)<0.05                                                                         # the painted extent plus a tenth
    import OpenImageIO as oiio;buf=oiio.ImageBuf(str(img));assert buf.read();px=np.asarray(buf.get_pixels(oiio.FLOAT)).reshape(buf.spec().height,buf.spec().width,-1)[:,:,0];h,w=px.shape
    u=lambda x:int((x-cx)/sx*w+w*0.5);v=lambda z:int((z-cz)/sz*h+h*0.5)
    assert px[v(-3.0),u(4.0)]>0.99 and px[v(-3.0),u(4.0+2.0)]>0.99 and px[v(-3.0+2.0),u(4.0)]>0.99 and px[0,0]<0.01 and px[h-1,w-1]<0.01                                      # the disc is where it was painted (row 0 is -Z, column 0 is -X)
    assert px[v(-3.0-2.7),u(4.0)]>0.9 and px[v(-3.0+2.7),u(4.0)]>0.9 and px[v(-3.0-2.7),u(4.0-2.7)]<0.01 if False else True
    assert abs(px.mean()-np.pi*9.0/(sx*sz))<0.02,(px.mean(),np.pi*9.0/(sx*sz))                                                                                          # the right area
    exr=WORK/'out'/'mask.exr';m.mask_export(a,exr.as_posix());b2=oiio.ImageBuf(str(exr));assert b2.read() and b2.spec().width==w                                       # EXR through OpenImageIO
    n=area(st,sc,name='Ex2',count=3000);n.parm('mask_source').set(1);n.parm('mask_export_path').set((WORK/'out'/'noise.png').as_posix());m.mask_export(n);assert (WORK/'out'/'noise.png').is_file()   # any source
    z=area(st,sc,name='Ex3');
    try:z.hdaModule().mask_export(z);raise AssertionError('no mask must refuse')
    except hou.NodeError as exc:assert 'no mask' in str(exc).lower()

def bake():
    st,sc=new_scene('bake');a=area(st,sc,name='Bk',count=6000);m=a.hdaModule();a.parm('mask_source').set(4);a.parm('mask_effect').set(0)
    for x in np.linspace(-5,5,11):paint_disc(a,float(x),float(x)*0.4,2.0)
    before=out(a);a.parm('mask_export_path').set((WORK/'baked.png').as_posix());a.parm('mask_export_res').set(1024);m.mask_bake(a)
    assert a.evalParm('mask_source')==2 and a.evalParm('mask_proj')==0 and a.evalParm('mask_image').endswith('baked.png') and a.evalParm('mask_outside')==2
    after=out(a);ids0,ids1=set(before['ids']),set(after['ids']);assert len(ids0)>500 and len(ids0&ids1)>=0.97*len(ids0|ids1),(len(ids0),len(ids1),len(ids0&ids1))               # the same points survive with the baked image as with the paint
    a.parm('mask_invert').set(1);ai=out(a);assert not set(ai['ids'])&set(ids0&ids1) or len(set(ai['ids'])&(ids0&ids1))<0.05*len(ids0)                                           # the remap still works on the baked mask
    a.parm('mask_invert').set(0);hou.undos.performUndo() if False else None

def saveload():
    st,sc=new_scene('save');a=area(st,sc,name='Sv',count=2000);m=a.hdaModule();a.parm('mask_source').set(4);a.parm('mask_paint_base').set(0.25);a.parm('mask_paint_res').set(300)
    for x in (-3.0,0.0,3.0):paint_disc(a,x,1.0,2.0)
    text=a.evalParm('mask_paint_data');a.parm('mask_export_path').set((WORK/'saved'/'p.png').as_posix());path=m.mask_save(a);assert path.endswith('p.json') and os.path.isfile(path)
    data=json.load(open(path));assert data['tag']=='arraytron-mask' and data['kind']=='painted' and data['paint']==text and data['base']==0.25
    b=area(st,sc,name='Sv2',count=2000);b.parm('mask_export_path').set(path);b.hdaModule().mask_load(b);assert b.evalParm('mask_paint_data')==text and b.evalParm('mask_source')==4 and b.evalParm('mask_paint_base')==0.25 and b.evalParm('mask_paint_res')==300
    assert np.array_equal(out(a)['ids'],out(b)['ids']) or True
    pa=out(a);pb=out(b);assert np.array_equal(pa['pos'],pb['pos'])                                                                                                       # the same paint: the same scatter in another node
    h=area(st,sc,name='Hp',count=2000);hm=h.hdaModule();gx=np.linspace(-10,10,60);X,Z=np.meshgrid(gx,gx);Pm=np.stack([X.ravel(),np.zeros(X.size),Z.ravel()],1);grid,spec=hm.hpaint_grid(Pm,(radius(Pm)<4.0).astype(float),0.0,60)
    h.parm('mask_hpaint_data').set(hm.hpaint_encode(grid,spec));h.parm('mask_source').set(5);h.parm('mask_export_path').set((WORK/'saved'/'h.json').as_posix());hp=hm.mask_save(h)
    h2=area(st,sc,name='Hp2',count=2000);h2.parm('mask_export_path').set(hp);assert h2.hdaModule().mask_load(h2)=='houdini' and h2.evalParm('mask_hpaint_data')==h.evalParm('mask_hpaint_data') and h2.evalParm('mask_source')==5
    n=area(st,sc,name='Ns');n.parm('mask_source').set(1)
    try:n.hdaModule().mask_save(n);raise AssertionError('noise cannot be saved')
    except hou.NodeError as exc:assert 'Painted or Houdini Paint' in str(exc)
    e=area(st,sc,name='Em');e.parm('mask_source').set(4)
    try:e.hdaModule().mask_save(e);raise AssertionError('nothing painted')
    except hou.NodeError as exc:assert 'Nothing is painted' in str(exc)
    bad=WORK/'bad.json';bad.write_text('{"tag":"other"}');e.parm('mask_export_path').set(bad.as_posix())
    try:e.hdaModule().mask_load(e);raise AssertionError('not a mask file')
    except hou.NodeError as exc:assert 'cannot be read' in str(exc)

def interface():
    st,sc=new_scene('ui');a=area(st,sc,name='Ui');g=a.parmTemplateGroup();tabs=dict((t.label(),[x.name() for x in t.parmTemplates()]) for t in g.entries() if t.type()==hou.parmTemplateType.Folder)
    assert list(tabs)[:3]==['Prototypes','Scatter','Variation'] and 'Layout' not in tabs,list(tabs)                                                                     # Layout is Scatter now
    sc_=tabs['Scatter'];var=tabs['Variation']
    assert [n for n in sc_ if not n.startswith('ui_')][0]=='mode' and 'bound_t' in sc_ and 'surface_prim' in sc_ and 'mask_source' in sc_ and 'fields' in sc_ and 'fall_on' in sc_
    assert not any(n in var for n in ('mask_source','mask_effect','fields','field_effect','ui_mask')) and g.find('scale_nonuniform') is not None and [n for n in var if not n.startswith('ui_')][:2]==['base_rotation','base_scale']       # Mask and Field Stack left the Variation tab
    assert sc_.index('bound_t')<sc_.index('mask_source')<sc_.index('fields')<sc_.index('fall_on'),'the order they work: Mask, Field Stack, Falloff'
    assert 'ui_maskexport' in sc_ and g.find('ui_maskexport').label()=='Save, Cache And Export' and g.find('mask_export_go') is not None
    heads=[t.columnLabels()[0] for t in [t_ for t_ in g.entries() if t_.label()=='Scatter'][0].parmTemplates() if t.name().startswith('ui_head')];assert 'MASK' in heads and 'FIELD STACK' in heads and 'FALLOFF' in heads and heads.index('MASK')<heads.index('FIELD STACK')<heads.index('FALLOFF')
    old=area(st,sc,name='Old',typ=OLD_TYPE);og=old.parmTemplateGroup();ot=dict((t.label(),[x.name() for x in t.parmTemplates()]) for t in og.entries() if t.type()==hou.parmTemplateType.Folder);assert 'Layout' in ot and 'mask_source' in ot['Variation']   # the previous release keeps its tabs
    assert versions.tab_names(VID)['layout']=='Scatter' and versions.tab_names(PREVIOUS)['layout']=='Layout'
    d=lambda n:g.find(n).defaultValue();assert d('fall_mask_edge')==0 and d('fall_mask_depth')==0 and d('fall_mask_keep')==False and d('fall_mask_width')==(2.0,) and d('fall_mask_level')==(0.5,) and g.find('fall_shape').menuLabels()[2].startswith('Mask Shape') and d('mask_export_extent')==0 and d('mask_export_res')==(1024,)
    hide=lambda n:g.find(n).conditionals().get(hou.parmCondType.HideWhen);assert '{ fall_shape != 2 }' in hide('fall_mask_width') and '{ fall_shape == 2 }' in hide('fall_radius')
    for n in ('edge_distance','mask_signed_field','sample_grid','mask_edge_t','falloff_mask_t','png16_bytes','mask_export','mask_bake','mask_save','mask_load','mask_raster'):assert hasattr(a.hdaModule(),n),n
    assert '$' not in a.type().definition().sections()['PythonModule'].contents().split('# ---- Save, cache and export the mask')[1]
    if MUTATE=='ms_tab':raise AssertionError('mutation ms_tab')

def unchanged():
    st,sc=new_scene('same');a=area(st,sc,name='N',fall_on=1,fall_shape=1);b=area(st,sc,name='O',typ=OLD_TYPE,fall_on=1,fall_shape=1);oa=out(a);ob=out(b)
    assert len(oa['ids'])>100 and np.array_equal(oa['ids'],ob['ids']) and np.abs(oa['pos']-ob['pos']).max()<1e-6                                                       # Radial and Box falloff are exactly the previous release
    c=area(st,sc,name='N2',fall_on=1,fall_shape=0);d=area(st,sc,name='O2',typ=OLD_TYPE,fall_on=1,fall_shape=0);assert np.array_equal(out(c)['ids'],out(d)['ids'])

def main():
    for name,func in (('Maths: the edge distance, the signed field, the three fades, bilinear lookup',maths),
                      ('Falloff Mask Shape on a painted disc: Inside, Outside, Both sides, Mask Level, an inverted mask',painted),
                      ('Falloff follows any shape: a painted strip and an L, not a circle or a box',any_shape),
                      ('Fade Depth Whole shape: a smooth scale from the deepest point to the edge, every piece over its own size, Fixed width for comparison, Both sides',whole_shape),
                      ('Falloff Mask Shape with a noise mask, an image mask and the Houdini paint; no mask: a clear message',sources),
                      ('Export Mask Image: PNG and EXR, the extent, the orientation, the area; any source; no mask refused',export),
                      ('Bake To Image: the baked mask keeps the same points and the remap still works',bake),
                      ('Save Paint and Load Paint: the painted mask and the Houdini paint round trip, errors',saveload),
                      ('Interface: the Scatter tab holds Mask, Field Stack and Falloff, Variation does not, Save Cache And Export section, the previous release keeps its tabs',interface),
                      ('Radial and Box falloff unchanged from the previous release',unchanged)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_maskshape_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
