"""Mask pipeline (v0.5.0) validation in real Houdini: hython tests/validate_mask.py
Everything is read from the USD stage: instance positions, ids, scales. Expected values come from hand-made images and meshes whose result is known
exactly (a checkerboard image sampled at pixel centres, a ramp primvar on a plane) or from an independent plain-Python noise implementation.
Env ARRAYTRON_MUTATE=<name> breaks the Python module in memory; the suite must then FAIL."""
from pathlib import Path
import hou, json, math, os, shutil, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom, UsdShade, Gf, Vt, Sdf
import OpenImageIO as oiio
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v0.5.0':'v0.4.6','v0.5.1':'v0.5.0','v0.5.2':'v0.5.1','v0.6.0':'v0.5.2','v0.7.0':'v0.6.0','v0.8.0':'v0.7.0','v0.9.0':'v0.8.0','v1.0.0':'v0.9.0','v1.1.0':'v1.0.0','v1.5.0':'v1.1.0','v1.6.0':'v1.5.0','v1.6.1':'v1.6.0','v1.6.2':'v1.6.1','v1.7.0':'v1.6.2','v1.8.0':'v1.7.0'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_mask_'))
STONE=(ROOT/'dist/test_assets/stone.usda').as_posix()
checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')

# ------------------------------------------------------------------ assets
def write_image(name,array):
    """Float EXR (exact values, row 0 = top) from an (H,W) or (H,W,C) array."""
    a=np.asarray(array,dtype=np.float32);a=a.reshape(a.shape[0],a.shape[1],-1);h,w,c=a.shape
    buf=oiio.ImageBuf(oiio.ImageSpec(w,h,c,oiio.FLOAT));buf.set_pixels(oiio.ROI(0,w,0,h,0,1,0,c),a);path=WORK/(name+'.exr');assert buf.write(str(path)),buf.geterror();return path.as_posix()
CHECK=np.array([[1,0,1,0],[0,1,0,1],[1,0,1,0],[0,1,0,1.]])                  # 4x4 checkerboard, pixel (row 0, col 0) = 1
IMG_CHECK=write_image('check',CHECK)
RAMP=np.tile(np.linspace(0,1,5)[None,:],(2,1))                              # 2x5: values 0, .25, .5, .75, 1 left to right
IMG_RAMP=write_image('ramp',RAMP)
RGB=np.zeros((2,2,3));RGB[:,:,0]=[[1,0],[0,1]];RGB[:,:,1]=[[0,1],[1,0]];RGB[:,:,2]=0.5     # R and G are complementary, B is flat
IMG_RGB=write_image('rgb',RGB)
GRAY=write_image('gray',np.full((2,2),0.5))
def write_stage(name,build):
    path=WORK/(name+'.usda');s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/'+name);s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    build(s,'/'+name);s.GetRootLayer().Save();return path.as_posix()
def grid_mesh(s,path,n=4,size=4.0,height=lambda x,z:0.0):
    """n x n quads over [0,size]^2 in XZ; returns the mesh (points x fastest)."""
    xs=np.linspace(0,size,n+1);pts=[(float(x),float(height(x,z)),float(z)) for z in xs for x in xs];idx=[]
    for j in range(n):
        for i in range(n):
            a=j*(n+1)+i;idx+=[a,a+n+1,a+n+2,a+1]
    m=UsdGeom.Mesh.Define(s,path);m.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*p) for p in pts]));m.CreateFaceVertexCountsAttr(Vt.IntArray([4]*(n*n)));m.CreateFaceVertexIndicesAttr(Vt.IntArray(idx));return m,np.array(pts),np.array(idx).reshape(-1,4)
def painted(s,r):
    m,pts,quads=grid_mesh(s,r+'/M',4,4.0,lambda x,z:0.3*x)                      # a tilted plane: the highest triangle wins when looking from above
    pv=UsdGeom.PrimvarsAPI(m.GetPrim())
    ramp=pv.CreatePrimvar('mask',Sdf.ValueTypeNames.FloatArray,UsdGeom.Tokens.vertex);ramp.Set(Vt.FloatArray([float(p[0]/4) for p in pts]))          # vertex: x/4
    face=pv.CreatePrimvar('facemask',Sdf.ValueTypeNames.FloatArray,UsdGeom.Tokens.uniform);face.Set(Vt.FloatArray([float((i%4+i//4)%2) for i in range(16)]))      # uniform: a checkerboard of quads
    fv=pv.CreatePrimvar('fvmask',Sdf.ValueTypeNames.FloatArray,UsdGeom.Tokens.faceVarying);fv.Set(Vt.FloatArray([float(pts[i][2]/4) for q in quads for i in q]))   # faceVarying: z/4
    cst=pv.CreatePrimvar('cmask',Sdf.ValueTypeNames.FloatArray,UsdGeom.Tokens.constant);cst.Set(Vt.FloatArray([0.7]))
    st=pv.CreatePrimvar('st',Sdf.ValueTypeNames.TexCoord2fArray,UsdGeom.Tokens.faceVarying);st.Set(Vt.Vec2fArray([Gf.Vec2f(float(pts[i][0]/4),float(pts[i][2]/4)) for q in quads for i in q]))
PAINT=write_stage('Paint',painted)
FLAT=write_stage('Flat',lambda s,r:UsdGeom.Mesh.Define(s,r+'/M') and grid_mesh(s,r+'/G',4,4.0))   # a mesh without any primvar

# ------------------------------------------------------------------ scene helpers
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True)
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));return hou.node('/stage')
def ref(stage,name,prim,path,source=None):
    n=stage.createNode('reference',name)
    if source:n.setInput(0,source)
    n.parm('primpath').set(prim);n.parm('primpath1').set(prim);n.parm('filepath1').set(path);n.parm('filerefprim1').set('defaultPrim');return n
def setv(a,**values):
    for key,value in values.items():a.parmTuple(key).set(value if isinstance(value,(tuple,list)) else (value,))
    return a
def arraytron(stage,source,typ=None,name='Arraytron',**values):
    a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Stone')
    if typ is None and MUTATE:mutate(a)
    return setv(a,**values)
def grid_scene(**values):
    """A 4 x 4 grid of points at the CENTRES of the 4 x 4 image pixels: x, z = -1.5, -0.5, 0.5, 1.5 (centre 0, size 4)."""
    st=new_scene('mask');stone=ref(st,'stone','/World/Props/Stone',STONE)
    kw=dict(mode=2,grid_count=(4,1,4),grid_size=(3,0,3),grid_center=1,mask_size=(4,4));kw.update(values);a=arraytron(st,stone,**kw);return st,a
def data(a):
    s=a.stage();assert not a.errors(),a.errors()
    pi=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    return dict(pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3),ids=list(pi.GetIdsAttr().Get(t) or []),scales=np.array(pi.GetScalesAttr().Get(t) or []).reshape(-1,3),proto=list(pi.GetProtoIndicesAttr().Get(t) or []))
def all_errors(node):
    out=list(node.errors())
    for c in node.children():out+=all_errors(c)
    return out
def expect_error(a,fragment):
    try:a.cook(force=True)
    except hou.OperationFailed:pass
    text=' | '.join(all_errors(a));assert fragment in text,(fragment,text)
M64=(1<<64)-1
def ref_hash(i,seed,stream=0):
    z=(i*0x9E3779B97F4A7C15+seed*0xD1B54A32D192ED03+(stream+1)*0x8CB92BA72F3D8DD7)&M64
    z=((z^(z>>30))*0xBF58476D1CE4E5B9)&M64;z=((z^(z>>27))*0x94D049BB133111EB)&M64;z=z^(z>>31)
    return (z>>11)/float(1<<53)
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()
def mutate(a):
    g=a.hdaModule().sop_mask.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='mask_flip':
        good=g['mask_weights'];g['mask_weights']=lambda asset,raw:good(asset,1.0-np.asarray(raw))
    elif MUTATE=='mask_high':
        good=g['mask_weights'];g['mask_weights']=lambda asset,raw:np.clip((np.where(asset.evalParm('mask_invert'),1.0-raw,raw)-asset.evalParm('mask_low')),0,1)
    elif MUTATE=='mask_v':
        good=g['planar_uv'];g['planar_uv']=lambda P,proj,center,size:(lambda u,v:(u,1.0-v))(*good(P,proj,center,size))
    elif MUTATE=='mask_density':
        good=g['scatter_hash'];g['scatter_hash']=lambda ids,seed,stream=0:good(np.asarray(ids)+1,seed,stream)
    elif MUTATE=='mask_scale':
        good=g['mask_weights'];g['mask_weights']=lambda asset,raw:good(asset,raw)*0.5
    elif MUTATE=='mask_noise':
        good=g['value_noise'];g['value_noise']=lambda p,seed=1:good(np.asarray(p)+0.37,seed)
    else:raise SystemExit('unknown mutation '+MUTATE)

# ------------------------------------------------------------------ groups
def ui_contract():
    st,a=grid_scene();g=a.parmTemplateGroup()
    if g.find('ui_mask'):assert [e.label() for e in g.entries()][2]=='Look' and g.find('mask_source') and g.find('ui_mask').label()=='Mask Details'
    else:
        names=[t.name() for t in g.entries()];assert names.index('mask')==names.index('randomize')+1,names
        f=[t for t in g.entries() if t.name()=='mask'][0];assert f.label()=='Mask'
    d=dict(mask_source=0,mask_effect=0,mask_invert=0,mask_low=0.0,mask_high=1.0,mask_minscale=0.2,mask_seed=1,mask_noise_freq=1.0,mask_noise_octaves=3,mask_noise_rough=0.5,mask_noise_contrast=2.5,mask_image='',mask_channel=0,mask_proj=0,mask_outside=0,mask_uvname='st',mask_prim='/World/Terrain',mask_primvar='mask',mask_mesh_outside=0.0)
    for k,v in d.items():assert a.evalParm(k)==v,(k,a.evalParm(k));assert g.find(k).help().strip(),k
    assert tuple(a.evalParmTuple('mask_noise_offset'))==(0,0,0) and tuple(a.evalParmTuple('mask_center'))==(0,0) and tuple(a.parmTemplateGroup().find('mask_size').defaultValue())==(10,10)
    hide=lambda n:g.find(n).conditionals().get(hou.parmCondType.HideWhen)
    assert hide('mask_noise_freq')=='{ mask_source != 1 }' and hide('mask_image')=='{ mask_source != 2 }' and hide('mask_primvar')=='{ mask_source != 3 }' and hide('mask_minscale')=='{ mask_effect == 0 }'
    assert hide('mask_center')=='{ mask_source != 2 } { mask_proj == 2 }' and hide('mask_uvname')=='{ mask_source != 2 } { mask_proj != 2 }'
    assert hide('mask_prim')=='{ mask_source == 0 } { mask_source == 1 } { mask_source == 2 mask_proj != 2 }'
    assert g.find('mask_source').menuLabels()==('None','Noise','Image','Mesh Primvar') and g.find('mask_effect').menuLabels()==('Density','Scale','Density + Scale')
    assert a.evalParm('mask_info')=='No mask: every point is used as generated.'
    assert 'Mask' in a.type().definition().sections()['ArraytronVersion'].contents() and a.node('USD_COMPILER/MASK_PROCESSOR')
    order=[];n=a.node('USD_COMPILER/VARIATION_PROCESSOR')
    while n is not None:order.append(n.name());n=n.inputs()[0] if n.inputs() else None
    fields=['FIELD_STACK'] if a.node('USD_COMPILER/FIELD_STACK') else []
    assert order[:3+len(fields)]==['VARIATION_PROCESSOR']+fields+['MASK_PROCESSOR','DISTRIBUTION_GENERATOR'],order

def off_unchanged():
    """No mask: every output array equals the previous release, including Sequential selection with several prototypes."""
    st=new_scene('same');stone=ref(st,'stone','/World/Props/Stone',STONE);box=ref(st,'x','/World/Props/Other',STONE,stone)
    new=arraytron(st,box,name='new');old=arraytron(st,box,typ=OLD_TYPE,name='old')
    def snap(n):
        pi=UsdGeom.PointInstancer(n.stage().GetPrimAtPath('/World/Arraytron'));t=hou.frame();assert not n.errors(),n.errors()
        return {k:list(getattr(pi,'Get'+k+'Attr')().Get(t)) for k in ('Positions','Orientations','Scales','Ids','ProtoIndices')}
    cases=[dict(mode=0,line_count=40,position_random=(.1,.1,.1),random_seed=5),dict(mode=1,area_count=120,bound_t=(1,2,3),bound_r=(10,20,30),bound_s=(1,2,.5)),
           dict(mode=2,grid_count=(3,3,3),scale_random_mode=1,scale_min=.7,scale_max=1.4),dict(mode=3,circle_facing=1,circle_count=20,rotation_random_mode=1,yaw_random=90),
           dict(mode=1,area_count=90,protos=2,proto_mode=2,proto_prim2='/World/Props/Other',proto_weight1=2,proto_weight2=1),dict(mode=1,area_count=60,protos=2,proto_mode=1,proto_prim2='/World/Props/Other',proto_seed=3),
           dict(mode=1,area_count=30,phys_on=1)]
    for k,values in enumerate(cases):
        for n in (new,old):
            for p in n.parms():
                if p.parmTemplate().type() not in (hou.parmTemplateType.Folder,hou.parmTemplateType.FolderSet) and not p.isMultiParmInstance() and p.name()!='protos':p.revertToDefaults()
            n.parm('protos').set(1);setv(n,proto_prim1='/World/Props/Stone',**values)
        assert snap(new)==snap(old),('case',k,values)

def image_density():
    """A checkerboard sampled at pixel centres: Density keeps exactly the points on white pixels (top view: the image top is -Z)."""
    st,a=grid_scene(mask_source=2,mask_image=IMG_CHECK);d=data(a)
    # ids run X fastest: id = i + 4*k with x = -1.5 + i, z = -1.5 + k; pixel column i, row k (row 0 = top = -Z); white where (i + k) % 2 == 0
    keep=[i+4*k for k in range(4) for i in range(4) if CHECK[k,i]==1];assert d['ids']==keep,(d['ids'],keep)
    assert len(d['pos'])==8 and 'Kept 8 of 16' in a.evalParm('mask_info'),a.evalParm('mask_info')
    for q,i in zip(d['pos'],d['ids']):assert np.allclose(q,[-1.5+i%4,0,-1.5+i//4],atol=1e-4),(i,q)          # survivors keep their positions
    setv(a,mask_invert=1);assert data(a)['ids']==[i for i in range(16) if i not in keep],'Invert keeps the black pixels'
    setv(a,mask_invert=0,mask_proj=1,grid_count=(4,4,1),grid_size=(3,3,0))                                      # Front: x right, y up; the image top is +Y
    dd=data(a);want=[i+4*j for j in range(4) for i in range(4) if CHECK[3-j,i]==1];assert dd['ids']==want,(dd['ids'],want)
    setv(a,mask_proj=0,grid_count=(4,1,4),grid_size=(3,0,3),mask_center=(1,0));dc=data(a)           # the image slid one unit (one pixel) to +X: point column i reads pixel column i-1, column 0 is outside
    want=[i+4*k for k in range(4) for i in range(1,4) if CHECK[k,i-1]==1];assert dc['ids']==want,(dc['ids'],want)

def image_outside_and_channels():
    st,a=grid_scene(mask_source=2,mask_image=IMG_CHECK,mask_size=(2,2),mask_outside=0)                          # the image now covers only 2 x 2 units: the outer points are outside it
    ids=data(a)['ids'];inside=[i+4*k for k in range(4) for i in range(4) if abs(-1.5+i)<1 and abs(-1.5+k)<1];assert set(ids)<=set(inside),ids
    setv(a,mask_outside=1);rep=data(a)['ids'];setv(a,mask_outside=2);cl=data(a)['ids'];assert len(rep)>len(ids) and len(cl)>len(ids),(len(ids),len(rep),len(cl))
    st,b=grid_scene(mask_source=2,mask_image=IMG_RGB,mask_size=(2,2),mask_effect=1,mask_minscale=0.0,grid_count=(2,1,2),grid_size=(1,0,1),base_scale=1.0)
    for ch,expect in ((1,[1,0,0,1]),(2,[0,1,1,0]),(3,[.5]*4),(0,[0.2126*1+0+0.0722*.5,0.7152+0.0722*.5,0.7152+0.0722*.5,0.2126+0.0722*.5])):
        setv(b,mask_channel=ch);s=data(b)['scales'][:,0];assert np.allclose(s,expect,atol=1e-4),(ch,s,expect)
    setv(b,mask_image=GRAY,mask_channel=4);expect_error(b,'has no channel A')

def scale_effect_and_remap():
    st,a=grid_scene(mask_source=2,mask_image=IMG_CHECK,mask_effect=1,mask_minscale=0.25,base_scale=2.0);d=data(a)
    assert d['ids']==list(range(16)),'Scale never removes points'
    want=[2.0*(1.0 if CHECK[i//4,i%4]==1 else 0.25) for i in range(16)];assert np.allclose(d['scales'][:,0],want,atol=1e-4),d['scales'][:,0]
    assert np.allclose(d['scales'][:,0],d['scales'][:,1]) and np.allclose(d['scales'][:,0],d['scales'][:,2]),'uniform'
    # Low / High remap on the ramp image (values 0, .25, .5, .75, 1 at pixel centres): points x = -2, -1, 0, 1, 2 over a 5 unit wide image
    st=new_scene('ramp');stone=ref(st,'stone','/World/Props/Stone',STONE)
    b=arraytron(st,stone,mode=0,line_count=5,line_length=4,line_center=1,line_axis=0,mask_source=2,mask_image=IMG_RAMP,mask_size=(5,2),mask_effect=1,mask_minscale=0.0)
    s=data(b)['scales'][:,0];assert np.allclose(s,[0.0,0.25,0.5,0.75,1.0],atol=1e-4),s
    base=s.copy();setv(b,mask_low=0.25,mask_high=0.75);r=data(b)['scales'][:,0];assert np.allclose(r,np.clip((base-0.25)/0.5,0,1),atol=1e-4),r
    setv(b,mask_invert=1,mask_low=0,mask_high=1);assert np.allclose(data(b)['scales'][:,0],1-base,atol=1e-4)
    setv(b,mask_invert=0,mask_minscale=0.5,mask_low=0,mask_high=1);assert np.allclose(data(b)['scales'][:,0],0.5+0.5*base,atol=1e-4)
    setv(b,mask_effect=0);d0=data(b);assert d0['ids']==[i for i in range(5) if base[i]>ref_hash(i,1,11)],(d0['ids'],base)

def density_properties():
    """Density with noise: survivors keep id and position; lowering High only ever ADDS points; the survivor rate follows the weight."""
    st=new_scene('dens');stone=ref(st,'stone','/World/Props/Stone',STONE)
    a=arraytron(st,stone,mode=1,area_count=2000,area_sizex=20,area_sizez=20,mask_source=1,mask_noise_freq=0.15,mask_seed=4)
    base=arraytron(st,stone,name='plain',mode=1,area_count=2000,area_sizex=20,area_sizez=20);full=data(base);d1=data(a)
    assert 0.2<len(d1['ids'])/2000<0.8 and d1['ids']==sorted(d1['ids']),len(d1['ids'])
    pos={i:p for i,p in zip(full['ids'],full['pos'])};assert all(np.allclose(pos[i],p,atol=1e-5) for i,p in zip(d1['ids'],d1['pos'])),'survivors keep their positions'
    assert 'of 2000 points' in a.evalParm('mask_info')
    setv(a,mask_high=0.6);d2=data(a);assert set(d1['ids'])<=set(d2['ids']) and len(d2['ids'])>len(d1['ids']),'a higher weight only adds points'
    setv(a,mask_high=1.0,mask_seed=5);assert data(a)['ids']!=d1['ids'],'the seed changes the pattern'
    # exactness: every survivor decision equals w > hash(id, seed, 11) with the weights of the independent noise below
    setv(a,mask_seed=4,mask_noise_octaves=1,mask_noise_contrast=2.0);P=full['pos'];w=np.array([indep_weight(p,0.15,4,2.0) for p in P])
    expect=[i for i in full['ids'] if w[i]>ref_hash(i,4,11)];got=data(a)['ids'];assert got==expect,(len(got),len(expect))

def indep_weight(p,freq,seed,contrast):
    """Single-octave value noise written with plain Python (independent of the numpy implementation), then the Contrast stretch; Low 0, High 1."""
    q=[c*freq for c in p];i=[math.floor(c) for c in q];f=[c-math.floor(c) for c in q];s=[c*c*(3-2*c) for c in f];v=0.0
    for dx in (0,1):
        for dy in (0,1):
            for dz in (0,1):
                w=(s[0] if dx else 1-s[0])*(s[1] if dy else 1-s[1])*(s[2] if dz else 1-s[2])
                key=(((i[0]+dx)*1000003+(i[1]+dy))*1000033+(i[2]+dz));v+=w*ref_hash(key&M64,seed,7)
    return min(1.0,max(0.0,(v-0.5)*contrast+0.5))

def mesh_primvars():
    st=new_scene('pv');stone=ref(st,'stone','/World/Props/Stone',STONE);t=ref(st,'paint','/World/Terrain',PAINT,stone)
    # 5 x 5 points over the 4 x 4 plane at (0.5 + k * 0.75): the vertex ramp is x/4, looked up from above through the tilted plane
    a=arraytron(st,t,mode=2,grid_count=(5,1,5),grid_size=(3.5,0,3.5),grid_center=0,bound_t=(0.25,0,0.25),mask_source=3,mask_primvar='mask',mask_effect=1,mask_minscale=0.0)
    d=data(a);P=d['pos'];assert np.allclose(d['scales'][:,0],np.clip(P[:,0]/4,0,1),atol=2e-3),'vertex primvar interpolates linearly: x/4'
    setv(a,mask_primvar='fvmask');assert np.allclose(data(a)['scales'][:,0],np.clip(P[:,2]/4,0,1),atol=2e-3),'faceVarying primvar: z/4'
    setv(a,mask_primvar='cmask');assert np.allclose(data(a)['scales'][:,0],0.7,atol=1e-4),'constant'
    setv(a,mask_primvar='facemask');s=data(a)['scales'][:,0];quad=[(int(p[0]//1)%4,int(p[2]//1)%4) for p in P]       # uniform: the checkerboard value of the quad under the point
    inside=[(0<=p[0]<4 and 0<=p[2]<4) for p in P];assert all(abs(s[k]-float((q[0]+q[1])%2))<1e-4 for k,q in enumerate(quad) if inside[k] and abs(P[k][0]-round(P[k][0]))>1e-3 and abs(P[k][2]-round(P[k][2]))>1e-3),'uniform primvar: the face value'
    setv(a,mask_primvar='mask',grid_size=(6.5,0,3.5));dd=data(a);local=dd['pos']-[0.25,0,0.25];out=local[:,0]>4+1e-6          # the lookup happens before the Bounds Transform
    assert out.any() and np.allclose(dd['scales'][out][:,0],0.0),'outside the mesh: the Outside value'
    setv(a,mask_mesh_outside=1.0);assert np.allclose(data(a)['scales'][out][:,0],1.0),'Outside The Mesh = 1'
    setv(a,grid_size=(3.5,0,3.5),mask_mesh_outside=0.0)
    setv(a,mask_primvar='nope');expect_error(a,'No mesh under /World/Terrain has a primvar called nope')
    setv(a,mask_prim='/World/Nope');expect_error(a,'does not exist');setv(a,mask_prim='');expect_error(a,'Mask Prim is empty');setv(a,mask_prim='/World/Terrain',mask_primvar='')
    expect_error(a,'Mask Primvar name is empty')
    # Surface Scatter on the same mesh with the mask: the same points (by id) as without it, the survivors follow the ramp
    s2=arraytron(st,t,name='surf',mode=5,surface_prim='/World/Terrain',surface_count=2000,surface_align=0,mask_source=3,mask_primvar='mask');s0=arraytron(st,t,name='surf0',mode=5,surface_prim='/World/Terrain',surface_count=2000,surface_align=0)
    dm=data(s2);d0=data(s0);full={i:p for i,p in zip(d0['ids'],d0['pos'])};assert all(np.allclose(full[i],p,atol=1e-5) for i,p in zip(dm['ids'],dm['pos']))
    assert 0.35<len(dm['ids'])/2000<0.65 and dm['pos'][:,0].mean()>d0['pos'][:,0].mean()+0.4,'the surviving points favour the high end of the ramp'

def mesh_uv_image():
    st=new_scene('uv');stone=ref(st,'stone','/World/Props/Stone',STONE);t=ref(st,'paint','/World/Terrain',PAINT,stone)
    a=arraytron(st,t,mode=2,grid_count=(5,1,5),grid_size=(3.5,0,3.5),grid_center=0,bound_t=(0.25,0,0.25),mask_source=2,mask_image=IMG_RAMP,mask_proj=2,mask_effect=1,mask_minscale=0.0)
    d=data(a);P=d['pos'];u=np.clip(P[:,0]/4,0,1);expect=np.interp(np.clip(u*5-0.5,0,4),np.arange(5),np.linspace(0,1,5));assert np.allclose(d['scales'][:,0],expect,atol=2e-3),(d['scales'][:,0],expect)
    setv(a,mask_uvname='nouv');expect_error(a,'No mesh under /World/Terrain has a primvar called nouv')

def noise_and_selection():
    st,a=grid_scene(mask_source=1)
    setv(a,mode=1,area_count=300,area_sizex=10,area_sizez=10);d=data(a);assert d['ids']==sorted(d['ids']) and len(set(d['ids']))==len(d['ids']) and 0<len(d['ids'])<300
    # Sequential selection works on the point order, so the survivors still split into the weighted blocks
    st=new_scene('seq');stone=ref(st,'stone','/World/Props/Stone',STONE);other=ref(st,'o','/World/Props/Other',STONE,stone)
    b=arraytron(st,other,mode=1,area_count=200,protos=2,proto_prim2='/World/Props/Other',proto_mode=2,mask_source=1,mask_seed=2);p=data(b)['proto'];n=len(p)
    assert 0<n<200 and p==[0]*(n//2)+[1]*(n-n//2) or p==[0]*(n-n//2)+[1]*(n//2),(n,p[:5])
    setv(b,mask_source=0,mask_noise_freq=1);q=data(b)['proto'];assert q==[0]*100+[1]*100
    # Cycle keys on the id: the survivors keep the prototype they would have had
    setv(b,proto_mode=3,mask_source=1);full=data(b);setv(b,mask_source=0);whole=data(b);expect={i:pr for i,pr in zip(whole['ids'],whole['proto'])};assert all(expect[i]==pr for i,pr in zip(full['ids'],full['proto']))

def other_modes():
    st=new_scene('om');stone=ref(st,'stone','/World/Props/Stone',STONE)
    for mode,extra in ((0,dict(line_count=50)),(3,dict(circle_count=40)),(1,dict(area_count=80))):
        a=arraytron(st,stone,name='m%d'%mode,mode=mode,mask_source=1,mask_noise_freq=0.4,mask_effect=2,mask_minscale=0.3,**extra);d=data(a);full=data(setv(a,mask_source=0))
        assert 0<len(d['ids'])<len(full['ids']),mode;assert set(d['ids'])<=set(full['ids']);assert d['scales'].min()>=0.3*full['scales'].min()-1e-6 and d['scales'].max()<=full['scales'].max()+1e-6
    setv(a,mask_source=1,phys_on=1);assert len(data(a)['ids'])>0,'Physics Settle takes the masked points as its spawn state'

def errors_and_edges():
    st,a=grid_scene(mask_source=2,mask_image='');expect_error(a,'Mask Image is empty')
    setv(a,mask_image=(WORK/'nope.exr').as_posix());expect_error(a,'does not exist')
    bad=WORK/'bad.exr';bad.write_text('not an image');setv(a,mask_image=bad.as_posix());expect_error(a,'cannot read')
    setv(a,mask_image=IMG_CHECK,mask_low=0.6,mask_high=0.4);a.cook(force=True);assert not all_errors(a),'High below Low is tolerated (a hard threshold)'
    setv(a,mask_source=0,mask_low=0,mask_high=1);assert len(data(a)['ids'])==16
    setv(a,mask_source=2,mask_effect=0,mask_image=IMG_CHECK,mask_minscale=0);b=arraytron(a.parent(),a.inputs()[0],name='z',mode=2,grid_count=(2,1,2),mask_source=1,mask_low=1.0,mask_high=1.0,mask_noise_contrast=0.1)
    d=data(b);assert len(d['ids'])==0 and not all_errors(b),'every point removed: an empty instancer, not an error'

# ------------------------------------------------------------------ run
check('Mask UI contract: folder after Randomize, menus, defaults, help, conditionals, read-out, network order',ui_contract)
check('Mask off: every output array equals the previous release (all modes, Sequential and Random selection, physics)',off_unchanged)
check('Image mask: a checkerboard sampled at pixel centres keeps exactly the white pixels (Top and Front, Invert)',image_density)
check('Image mask: Outside modes and channel selection (R, G, B, luminance, missing alpha)',image_outside_and_channels)
check('Scale effect, Low / High remap, Invert and Min Scale are exact on a ramp image',scale_effect_and_remap)
check('Noise density: ids and positions of survivors unchanged, a higher weight only adds points, exact against an independent noise',density_properties)
check('Mesh primvars: vertex, faceVarying, uniform and constant, outside value, errors; Surface Scatter keeps its points',mesh_primvars)
check('Image through mesh UVs',mesh_uv_image)
check('Sequential selection follows the point order after removal; Cycle keeps the id-keyed prototype',noise_and_selection)
check('Line, Circle and Area with a mask (Density + Scale), Physics Settle spawn',other_modes)
check('Mask errors and edge cases: missing / unreadable image, no mesh, High < Low, everything removed',errors_and_edges)
out=ROOT/'tests'/('validation_mask_%s.json'%versions.tag(VID))
out.write_text(json.dumps({'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'passed':True},indent=2))
shutil.rmtree(WORK,ignore_errors=True)
print('ALL PASSED',len(checks))
