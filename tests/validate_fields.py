"""Field Stack (v0.7.0) validation in real Houdini: hython tests/validate_fields.py
Points are injected through Paint mode (exact positions and ids) and the stack is read back from the PointInstancer. The expected weights come from
independent re-implementations (plain Python / brute force): Height and Slope bands, Distance to a curve and to a mesh, Exclusion of a closed box
(analytic point-to-box distance), the image gradient, the noise against the Mask module, every Combine operation, Invert, both effects and the
per-id random number (own splitmix64). Env ARRAYTRON_MUTATE=<name> breaks the module; the suite must FAIL."""
from pathlib import Path
import hou, json, math, os, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom, Gf
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
TN=versions.tab_names(VID)
PREVIOUS={'v0.7.0':'v0.6.0','v0.8.0':'v0.7.0','v0.9.0':'v0.8.0','v1.0.0':'v0.9.0','v1.1.0':'v1.0.0','v1.5.0':'v1.1.0','v1.6.0':'v1.5.0','v1.6.1':'v1.6.0','v1.6.2':'v1.6.1','v1.7.0':'v1.6.2','v1.8.0':'v1.7.0','v1.9.0':'v1.8.0','v1.10.0':'v1.9.0','v1.11.0':'v1.10.0','v1.12.0':'v1.11.0','v1.13.0':'v1.12.0','v1.14.0':'v1.13.0','v1.15.0':'v1.14.0','v1.16.0':'v1.15.0','v1.17.0':'v1.16.0','v1.18.0':'v1.17.0','v1.19.0':'v1.18.0','v1.9.0':'v1.8.0','v1.10.0':'v1.9.0','v1.11.0':'v1.10.0','v1.12.0':'v1.11.0','v1.13.0':'v1.12.0','v1.14.0':'v1.13.0','v1.15.0':'v1.14.0'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_fields_'))
checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE');M64=(1<<64)-1
def ref_hash(i,seed,stream=0):
    z=(i*0x9E3779B97F4A7C15+seed*0xD1B54A32D192ED03+(stream+1)*0x8CB92BA72F3D8DD7)&M64
    z=((z^(z>>30))*0xBF58476D1CE4E5B9)&M64;z=((z^(z>>27))*0x94D049BB133111EB)&M64;z=z^(z>>31)
    return (z>>11)/float(1<<53)
def smooth(x):
    x=min(max(x,0.0),1.0);return x*x*(3-2*x)
def write_assets():
    path=WORK/'fields.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    UsdGeom.Xform.Define(s,'/World/Props/Ball');UsdGeom.Sphere.Define(s,'/World/Props/Ball/S').CreateRadiusAttr(0.1)
    def quad(name,pts):
        m=UsdGeom.Mesh.Define(s,'/World/Ground/'+name);m.CreatePointsAttr([tuple(p) for p in pts]);m.CreateFaceVertexCountsAttr([4]);m.CreateFaceVertexIndicesAttr([0,1,2,3]);m.CreateOrientationAttr('rightHanded')
    # counter-clockwise seen from above so the normal points up: x to the right, z towards the viewer
    quad('Flat',[(-10,0,5),(-1,0,5),(-1,0,-5),(-10,0,-5)])                       # slope 0
    quad('Ramp',[(1,0,5),(6,5,5),(6,5,-5),(1,0,-5)])                              # rises 5 over 5: 45 degrees
    cube=UsdGeom.Cube.Define(s,'/World/Block/Cube');cube.CreateSizeAttr(2.0);UsdGeom.Xformable(cube).AddTranslateOp().Set(Gf.Vec3d(20,1,0))   # [19,21] x [0,2] x [-1,1]
    c=UsdGeom.BasisCurves.Define(s,'/World/Road/Curve');c.CreateTypeAttr('linear');c.CreateCurveVertexCountsAttr([2]);c.CreatePointsAttr([(0,0,-10),(0,0,10)])
    s.GetRootLayer().Save()
    import OpenImageIO as oiio                                                         # a float image whose red value is u (0 left, 1 right)
    w=h=64;img=np.tile(((np.arange(w)+0.5)/w).astype(np.float32),(h,1))[:,:,None];buf=oiio.ImageBuf(oiio.ImageSpec(w,h,1,'float'));buf.set_pixels(oiio.ROI(0,w,0,h,0,1,0,1),img);buf.write(str(WORK/'grad.exr'))
    return path.as_posix(),(WORK/'grad.exr').as_posix()
SCENE,GRAD=write_assets()
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True)
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
def painted(stage,source,P,name='Fields',typ=None,**values):
    """An Arraytron in Paint mode holding exactly the points P (ids 0..n-1, normal +Y)."""
    P=np.asarray(P,dtype=float).reshape(-1,3);a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Ball')
    a.parm('mode').set(6);a.parm('paint_prim').set('');a.parm('paint_align').set(0.0)
    m=a.hdaModule();table=np.column_stack([P,np.tile([0.0,1.0,0.0],(len(P),1)),np.arange(len(P))]);a.parm('paint_data').set(m.paint_encode({'pts':table,'dab':1,'next':len(P)}))
    for k,v in values.items():a.parmTuple(k).set(v if isinstance(v,(tuple,list)) else (v,))
    if typ is None and MUTATE:mutate(a)
    return a
def row(a,i,**values):
    a.parm('fields').set(max(a.evalParm('fields'),i))
    for k,v in values.items():a.parmTuple('%s%d'%(k,i)).set(v if isinstance(v,(tuple,list)) else (v,))
def out(a):
    s=a.stage();assert not a.errors(),a.errors()
    pi=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    return dict(pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3),ids=np.array(pi.GetIdsAttr().Get(t) or [],dtype=int),scales=np.array(pi.GetScalesAttr().Get(t) or []).reshape(-1,3))
def scale_by_id(a,n):
    d=out(a);res=np.full(n,np.nan)
    for i,s in zip(d['ids'],d['scales'][:,0]):res[i]=s
    return res
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
    if MUTATE=='field_height':
        good=g['band'];g['band']=lambda x,lo,hi,fall:good(x,lo,hi,0.0)
    elif MUTATE=='field_slope':g['slope_degrees']=lambda normals:np.degrees(np.arccos(np.clip(np.asarray(normals)[:,2],-1.0,1.0)))
    elif MUTATE=='field_op':
        good=g['combine'];g['combine']=lambda values,ops:good(values,[4 if o==3 else 3 if o==4 else o for o in ops])
    elif MUTATE=='field_order':
        good=g['combine'];g['combine']=lambda values,ops:good(values[::-1],ops[::-1])
    elif MUTATE=='field_dist':
        good=g['distance_to_triangles'];g['distance_to_triangles']=lambda P,tris,limit,axes=1:good(P,tris,limit,1)
    elif MUTATE=='field_inside':g['inside_closed']=lambda P,tris:np.zeros(len(P),dtype=bool)
    elif MUTATE=='field_smooth':g['smooth01']=lambda x:np.clip(np.asarray(x,dtype=float),0.0,1.0)
    elif MUTATE=='field_density':
        good=g['scatter_hash'];g['scatter_hash']=lambda ids,seed,stream=0:good(ids,seed,stream+1 if stream==21 else stream)
    else:raise SystemExit('unknown mutation '+MUTATE)
def box_distance(p,lo=np.array([19.0,0.0,-1.0]),hi=np.array([21.0,2.0,1.0])):
    d=np.maximum(np.maximum(lo-p,p-hi),0.0);return float(np.linalg.norm(d))
def inside_box(p,lo=np.array([19.0,0.0,-1.0]),hi=np.array([21.0,2.0,1.0])):return bool(np.all(p>lo) and np.all(p<hi))

# ------------------------------------------------------------------ groups
def ui_contract():
    st,sc=new_scene('ui');a=painted(st,sc,[[0,0,0]]);g=a.parmTemplateGroup()
    bank=g.find('fields');assert bank.folderType()==hou.folderType.MultiparmBlock and bank.defaultValue()==0
    assert g.find('field_type#').menuLabels()==('Height','Slope','Noise','Image','Distance','Exclusion') and g.find('field_op#').menuLabels()==('Multiply','Add','Subtract','Min','Max')
    assert g.find('field_effect').menuLabels()==('Density','Scale','Density + Scale') and g.find('field_effect').defaultValue()==0
    for name in ('field_on#','field_invert#','field_hmin#','field_hmax#','field_hfall#','field_prim#','field_smin#','field_smax#','field_sfall#','field_nfreq#','field_noffset#','field_noct#','field_nrough#','field_ncontrast#','field_nseed#',
                 'field_image#','field_channel#','field_proj#','field_icenter#','field_isize#','field_ioutside#','field_dnear#','field_dfar#','field_daxes#','field_xmargin#','field_xfall#','field_minscale','field_seed','field_info'):assert g.find(name) is not None,name
    look=[t for t in g.entries() if t.label()==TN['look']][0];names=[t.name() for t in look.parmTemplates()]
    assert names.index('fields')>names.index('mask_info') and 'FIELD STACK' in [t.columnLabels()[0] for t in look.parmTemplates() if t.name().startswith('ui_head')]
    inner=a.node('USD_COMPILER');chain=['MASK_PROCESSOR','FIELD_STACK']+(['FALLOFF'] if inner.node('FALLOFF') else [])+['VARIATION_PROCESSOR'];assert [inner.node(n).inputs()[0].name() for n in chain[1:]]==chain[:-1]
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
        if t.type()==hou.parmTemplateType.Menu:assert n.menuItems()[:len(t.menuItems())]==t.menuItems() and (n.menuLabels()[:len(t.menuLabels())]==t.menuLabels() or name=='overlap_mode'),name
def defaults_unchanged():
    st,sc=new_scene('defaults')
    for values in (dict(mode=0,line_count=7),dict(mode=1,area_count=40,area_seed=3),dict(mode=5,surface_prim='/World/Ground',surface_count=50,surface_seed=2)):
        a=st.createNode(TYPE,'n%d'%len(values));a.setInput(0,sc);a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Ball')
        b=st.createNode(OLD_TYPE,'o%d'%len(values));b.setInput(0,sc);b.parm('protos').set(1);b.parm('proto_prim1').set('/World/Props/Ball')
        for n in (a,b):
            for k,v in values.items():n.parmTuple(k).set(v if isinstance(v,(tuple,list)) else (v,))
        x,y=out(a),out(b);assert len(x['pos'])==len(y['pos'])>0 and np.array_equal(x['ids'],y['ids']) and np.allclose(x['pos'],y['pos'],atol=1e-6) and np.allclose(x['scales'],y['scales'])
    # an empty stack and a stack whose rows are all switched off change nothing either
    P=np.random.default_rng(1).uniform(-5,5,(30,3));a=painted(st,sc,P,'pa');b=painted(st,sc,P,'pb');row(b,1,field_on=0,field_type=0);row(b,2,field_on=0,field_type=2)
    assert np.array_equal(out(a)['ids'],out(b)['ids']) and 'No field is switched on' in b.parm('field_info').eval() and 'empty' in a.parm('field_info').eval()
def shaping():
    st,sc=new_scene('pure');a=painted(st,sc,[[0,0,0]]);m=a.hdaModule()
    x=np.linspace(-3,13,41)
    for lo,hi,fall in ((2.0,8.0,0.0),(2.0,8.0,1.5),(8.0,2.0,2.0)):
        ref=[]
        for v in x:
            l,h=min(lo,hi),max(lo,hi);d=max(l-v,v-h)
            ref.append((1.0 if d<=0 else 0.0) if fall<=0 else 1.0-smooth(d/fall))
        assert np.allclose(m.band(x,lo,hi,fall),ref)
    d=np.linspace(0,6,31)
    for near,far in ((1.0,3.0),(2.0,2.0)):
        ref=[(1.0 if v>near else 0.0) if far<=near else smooth((v-near)/(far-near)) for v in d];assert np.allclose(m.ramp(d,near,far),ref)
    rng=np.random.default_rng(3);vals=[rng.uniform(0,1,50) for _ in range(5)]
    for ops in ([0,0,0,0,0],[0,1,2,3,4],[9,4,4,3,2],[0,2,2,2,2],[0,3,3,3,3]):
        acc=np.clip(vals[0].copy(),0,1)
        for v,op in zip(vals[1:],ops[1:]):
            acc=[acc*v,acc+v,acc-v,np.minimum(acc,v),np.maximum(acc,v)][op];acc=np.clip(acc,0,1)
        assert np.allclose(m.combine(vals,ops),acc)
    assert np.allclose(m.combine([vals[0]],[2]),np.clip(vals[0],0,1))                  # a single row: its own value, whatever the Combine says
def geometry_distances():
    st,sc=new_scene('geo');a=painted(st,sc,[[0,0,0]]);m=a.hdaModule();rng=np.random.default_rng(7)
    A,B,C=(rng.normal(size=(40,3)) for _ in range(3));p=rng.normal(size=3)*2
    def brute_tri(p,a,b,c,n=70):
        best=np.inf
        for i in range(n+1):
            for j in range(n+1-i):
                q=a+(b-a)*i/n+(c-a)*j/n;best=min(best,np.linalg.norm(p-q))
        return best
    exact=m.tri_dist(p,A,B,C)
    for k in range(6):assert exact[k]<=brute_tri(p,A[k],B[k],C[k])+1e-9 and exact[k]>=brute_tri(p,A[k],B[k],C[k])-0.08,(k,exact[k])       # sampling can only be farther, and not by much
    seg=m.seg_dist(p,A,B);assert all(abs(seg[k]-min(np.linalg.norm(p-(A[k]+(B[k]-A[k])*t)) for t in np.linspace(0,1,4001)))<2e-3 for k in range(5))
    tris=np.stack([A,B,C],axis=1);P=rng.normal(size=(60,3))*2
    for axes in (0,1):
        q,t=(P*[1,0,1],tris*[1,0,1]) if axes==0 else (P,tris)
        ref=np.array([min(m.tri_dist(pp,t[:,0],t[:,1],t[:,2]).min(),1.5) for pp in q]);got=m.distance_to_triangles(P,tris,1.5,axes);assert np.allclose(got,ref),(axes,np.abs(got-ref).max())   # the grid never drops a triangle that matters
    cube=np.array([[[19,0,-1],[21,0,-1],[21,0,1]],[[19,0,-1],[21,0,1],[19,0,1]]],dtype=float)                       # a degenerate flat case: the floor of the box
    assert abs(m.distance_to_triangles(np.array([[20.0,3.0,0.0]]),cube,10.0,1)[0]-3.0)<1e-9 and abs(m.distance_to_triangles(np.array([[20.0,3.0,0.0]]),cube,10.0,0)[0])<1e-9
def closed_mesh():
    st,sc=new_scene('box');a=painted(st,sc,[[0,0,0]]);m=a.hdaModule();P0,T0,area,normals,vn=m.stage_surface(a,'surface_prim','/World/Block');tris=P0[T0];assert len(tris)==12
    rng=np.random.default_rng(2);P=np.column_stack([rng.uniform(17,23,300),rng.uniform(-1,3,300),rng.uniform(-3,3,300)]);ins=m.inside_closed(P,tris)
    assert all(bool(i)==inside_box(p) for i,p in zip(ins,P)) and ins.sum()>10
    for margin,fall in ((0.0,0.0),(0.3,0.0),(0.3,0.8)):
        got=m.exclusion_value(P,tris,margin,fall)
        for p,v in zip(P,got):
            d=0.0 if inside_box(p) else box_distance(p);ref=(1.0 if d>margin else 0.0) if fall<=0 else float(smooth((d-margin)/fall))
            assert abs(v-ref)<1e-9,(p,v,ref,d)
def height_field():
    st,sc=new_scene('h');P=np.column_stack([np.linspace(-1,9,41),np.linspace(-1,9,41),np.zeros(41)]);P[:,0]=np.arange(41)*0.2;P[:,1]=np.linspace(-1,9,41)
    a=painted(st,sc,P,field_effect=1,field_minscale=0.0);row(a,1,field_type=0,field_hmin=2.0,field_hmax=6.0,field_hfall=2.0)
    w=[1.0 if 2<=y<=6 else 1.0-smooth(max(2-y,y-6)/2.0) for y in P[:,1]];assert np.allclose(scale_by_id(a,41),w,atol=1e-5)
    row(a,1,field_hfall=0.0);assert np.allclose(scale_by_id(a,41),[1.0 if 2<=y<=6 else 0.0 for y in P[:,1]],atol=1e-5)
    row(a,1,field_invert=1);assert np.allclose(scale_by_id(a,41),[0.0 if 2<=y<=6 else 1.0 for y in P[:,1]],atol=1e-5)
def slope_field():
    st,sc=new_scene('s');P=np.array([[-5,0.7,0],[-3,0.2,2],[2,1.0,0],[4,3.0,3],[8,0,0],[0,9,0]],dtype=float)             # flat, flat, ramp, ramp, beyond both, between them
    a=painted(st,sc,P,field_effect=1,field_minscale=0.0);row(a,1,field_type=1,field_prim='/World/Ground',field_smin=0.0,field_smax=30.0,field_sfall=0.0)
    assert np.allclose(scale_by_id(a,6),[1,1,0,0,1,1],atol=1e-5)                                                          # not above the prim: not judged
    row(a,1,field_smin=40.0,field_smax=50.0);assert np.allclose(scale_by_id(a,6),[0,0,1,1,1,1],atol=1e-5)
    row(a,1,field_smin=0.0,field_smax=30.0,field_sfall=30.0);w=scale_by_id(a,6);assert abs(w[2]-(1-smooth(15/30.0)))<2e-3 and w[0]==1.0                  # 45 degrees, 15 over the band, falloff 30
def noise_field():
    st,sc=new_scene('n');P=np.random.default_rng(4).uniform(-6,6,(80,3))
    a=painted(st,sc,P,field_effect=1,field_minscale=0.0,mask_source=1,mask_noise_freq=0.6,mask_noise_octaves=2,mask_noise_rough=0.4,mask_noise_contrast=2.0,mask_seed=5,mask_effect=1,mask_minscale=0.0)
    row(a,1,field_type=2,field_nfreq=0.6,field_noct=2,field_nrough=0.4,field_ncontrast=2.0,field_nseed=5);m=a.hdaModule()
    assert np.allclose(m.field_values(a,1,P,np.arange(80)),m.mask_values(a,P,np.arange(80)))                              # the same noise as the Mask
    w=m.field_values(a,1,P,np.arange(80));assert w.min()<0.2 and w.max()>0.8 and np.allclose(scale_by_id(a,80),w*np.clip(w,0,1),atol=1e-5)      # Mask Scale x Field Scale multiply
def image_field():
    st,sc=new_scene('i');P=np.column_stack([np.linspace(-3.5,3.5,30),np.zeros(30),np.linspace(-2,2,30)])
    a=painted(st,sc,P,field_effect=1,field_minscale=0.0);row(a,1,field_type=3,field_image=GRAD,field_channel=1,field_proj=0,field_icenter=(0.0,0.0),field_isize=(8.0,8.0),field_ioutside=0)
    u=P[:,0]/8.0+0.5;assert np.allclose(scale_by_id(a,30),u,atol=1/64.0+1e-4)                                              # the gradient read back (bilinear, within one pixel)
    row(a,1,field_isize=(4.0,4.0),field_ioutside=0);w=scale_by_id(a,30);assert np.all(w[np.abs(P[:,0])>2.0]==0.0) and w.max()>0.8                       # outside the image: black
    row(a,1,field_proj=1,field_isize=(8.0,8.0));assert np.allclose(scale_by_id(a,30),u,atol=1/64.0+1e-4)                  # Front: the image u runs along X as well
def distance_field():
    st,sc=new_scene('d');P=np.array([[0.0,0,0],[0.5,0,3],[1.5,0,-4],[2.5,0,0],[4.0,0,5],[-6.0,0,0],[1.5,2.0,0],[0.0,3.0,-12],[1.0,0,15]])        # the road is the line x=0, y=0, z in [-10,10]
    a=painted(st,sc,P,field_effect=1,field_minscale=0.0);row(a,1,field_type=4,field_prim='/World/Road',field_dnear=1.0,field_dfar=3.0,field_daxes=0)
    def road(p,axes):
        q=p.copy();q[2]=min(max(q[2],-10),10);d=q-np.array([0,0,q[2]]) if axes==1 else None
        dx=np.array([p[0],0.0 if axes==0 else p[1],p[2]-q[2]]);return float(np.linalg.norm(dx))
    for axes in (0,1):
        row(a,1,field_daxes=axes);ref=[0.0 if road(p,axes)<=1.0 else (1.0 if road(p,axes)>=3.0 else smooth((road(p,axes)-1.0)/2.0)) for p in P];assert np.allclose(scale_by_id(a,len(P)),ref,atol=1e-5),(axes,scale_by_id(a,len(P)),ref)
    row(a,1,field_invert=1,field_daxes=1);assert np.allclose(scale_by_id(a,len(P)),[1-(0.0 if road(p,1)<=1.0 else (1.0 if road(p,1)>=3.0 else smooth((road(p,1)-1.0)/2.0))) for p in P],atol=1e-5)
    # a mesh target: the flat ground quad (x in [-10,-1], z in [-5,5], y 0)
    row(a,1,field_prim='/World/Ground/Flat',field_invert=0,field_dnear=0.5,field_dfar=2.5,field_daxes=1)
    def quad_d(p):
        c=np.array([min(max(p[0],-10),-1),0.0,min(max(p[2],-5),5)]);return float(np.linalg.norm(p-c))
    ref=[0.0 if quad_d(p)<=0.5 else (1.0 if quad_d(p)>=2.5 else smooth((quad_d(p)-0.5)/2.0)) for p in P];assert np.allclose(scale_by_id(a,len(P)),ref,atol=1e-5)
def exclusion_field():
    st,sc=new_scene('x');P=np.array([[20,1,0],[19.1,0.1,0.9],[18.9,1,0],[18.5,1,0],[22.5,1,0],[20,3.5,0],[20,6,0],[10,1,0],[21.2,2.2,1.2],[20,-0.25,0]],dtype=float)
    a=painted(st,sc,P,field_effect=1,field_minscale=0.0);row(a,1,field_type=5,field_prim='/World/Block',field_xmargin=0.3,field_xfall=0.0)
    ref=[0.0 if inside_box(p) or box_distance(p)<=0.3 else 1.0 for p in P];assert np.allclose(scale_by_id(a,len(P)),ref,atol=1e-5) and sum(ref)<len(P) and 0 in ref
    row(a,1,field_xmargin=0.3,field_xfall=1.0);ref=[0.0 if inside_box(p) else float(smooth((box_distance(p)-0.3)/1.0)) for p in P];assert np.allclose(scale_by_id(a,len(P)),ref,atol=1e-5)
def combining():
    st,sc=new_scene('c');P=np.array([[x,y,0.0] for x in (0.0,1.0,2.0) for y in (0.0,1.0,2.0,3.0)])
    a=painted(st,sc,P,field_effect=1,field_minscale=0.0)
    row(a,1,field_type=0,field_hmin=0.0,field_hmax=1.0,field_hfall=2.0)                                                    # value A: height band
    row(a,2,field_type=2,field_nfreq=0.7,field_nseed=3);m=a.hdaModule();ids=np.arange(len(P))
    A=np.array([1.0 if 0<=y<=1 else 1-smooth(max(0-y,y-1)/2.0) for y in P[:,1]]);B=m.field_values(a,2,P,ids)
    for op,fn in enumerate((lambda x,y:x*y,lambda x,y:x+y,lambda x,y:x-y,np.minimum,np.maximum)):
        row(a,2,field_op=op);assert np.allclose(scale_by_id(a,len(P)),np.clip(fn(A,B),0,1),atol=1e-5),op
    row(a,1,field_op=2);row(a,2,field_op=0);assert np.allclose(scale_by_id(a,len(P)),np.clip(A*B,0,1),atol=1e-5)          # the first row ignores its Combine
    row(a,2,field_on=0);assert np.allclose(scale_by_id(a,len(P)),A,atol=1e-5)                                               # a switched-off row is left out
    row(a,2,field_on=1,field_op=2);row(a,1,field_type=0);row(a,3,field_type=0,field_hmin=0.0,field_hmax=0.0,field_hfall=1.0,field_op=1,field_invert=1)           # three rows: (A - B) + (1 - C), clamped after each step
    C=np.array([1.0-(1.0 if y==0 else 1-smooth(y/1.0)) for y in P[:,1]]);assert np.allclose(scale_by_id(a,len(P)),np.clip(np.clip(A-B,0,1)+C,0,1),atol=1e-5)
def effects():
    st,sc=new_scene('e');P=np.random.default_rng(6).uniform(-3,3,(400,3));P[:,1]=np.linspace(0,8,400)
    a=painted(st,sc,P,field_effect=0,field_seed=7);row(a,1,field_type=0,field_hmin=2.0,field_hmax=5.0,field_hfall=3.0)
    w=np.array([1.0 if 2<=y<=5 else 1-smooth(max(2-y,y-5)/3.0) for y in P[:,1]]);keep=[i for i in range(400) if w[i]>ref_hash(i,7,21)]
    assert sorted(out(a)['ids'].tolist())==keep and 100<len(keep)<300                                                       # Density: survive if weight > the id's own random number
    info=a.parm('field_info').eval();assert 'Kept %d of 400'%len(keep) in info,info
    row(a,1,field_hfall=6.0);keep2=set(out(a)['ids'].tolist());assert len(keep2)>len(keep) and set(keep)<=keep2
    a.parm('field_effect').set(2);a.parm('field_minscale').set(0.3);row(a,1,field_hfall=3.0);d=out(a);assert sorted(d['ids'].tolist())==keep
    expect={i:0.3+0.7*w[i] for i in keep};assert all(abs(s-expect[i])<1e-5 for i,s in zip(d['ids'],d['scales'][:,0]))     # Density + Scale: survivors scaled by Min Scale + (1 - Min Scale) x weight
    a.parm('field_seed').set(8);assert sorted(out(a)['ids'].tolist())==[i for i in range(400) if w[i]>ref_hash(i,8,21)]
def monotonic():
    st,sc=new_scene('m');P=np.random.default_rng(8).uniform(-3,3,(300,3));P[:,1]=np.linspace(0,6,300)
    a=painted(st,sc,P,field_effect=0);row(a,1,field_type=0,field_hmin=2.0,field_hmax=4.0,field_hfall=0.5);small=set(out(a)['ids'].tolist())
    row(a,1,field_hfall=2.0);big=set(out(a)['ids'].tolist());assert small<big                                              # a higher weight only ever adds points; the survivors keep their ids
    d=out(a);ref={i:p for i,p in enumerate(P)};assert all(np.allclose(ref[i],p,atol=1e-5) for i,p in zip(d['ids'],d['pos']))
def with_surface():
    st,sc=new_scene('surf');a=st.createNode(TYPE,'S');a.setInput(0,sc);a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Ball')
    a.parm('mode').set(5);a.parm('surface_prim').set('/World/Ground');a.parm('surface_count').set(400);a.parm('surface_seed').set(3);a.parm('field_effect').set(0)
    if MUTATE:mutate(a)
    full=out(a);row(a,1,field_type=1,field_prim='/World/Ground',field_smin=0.0,field_smax=20.0,field_sfall=0.0);d=out(a)
    m=a.hdaModule();P,T,area,normals,vn=m.surface_stage_dummy if False else m.stage_surface(a,'surface_prim');
    ramp_pts=full['pos'][:,0]>0.5;assert ramp_pts.any() and (~ramp_pts).any()
    assert len(d['ids'])==int((~ramp_pts).sum())>20 and np.all(d['pos'][:,0]<-0.5)                                         # slope under 20 degrees keeps the flat ground only
def errors_and_info():
    st,sc=new_scene('err');P=np.zeros((3,3));a=painted(st,sc,P)
    def fails(fragment):
        try:a.cook(force=True);a.stage()
        except hou.OperationFailed:pass
        text=' | '.join(all_errors(a));assert fragment in text,(fragment,text)
    row(a,1,field_type=1,field_prim='');fails('Prim is empty')
    row(a,1,field_type=4,field_prim='/World/Nothing');fails('does not exist')
    row(a,1,field_type=5,field_prim='/World/Props/Ball');a.cook(force=True);a.stage();assert not all_errors(a)           # a sphere shape is a closed mesh: fine
    row(a,1,field_type=3,field_image='');fails('Image is empty')
    row(a,1,field_image=str(WORK/'nope.exr'));fails('does not exist')
    row(a,1,field_type=0);a.cook(force=True);a.stage();assert not all_errors(a)
def main():
    for name,func in (('UI contract: multiparm, field types, Combine menu, effect, stage order, every v0.6.0 parameter unchanged',ui_contract),
                      ('Defaults reproduce v0.6.0 exactly; empty and all-off stacks change nothing',defaults_unchanged),
                      ('Band, ramp and Combine against plain Python',shaping),
                      ('Point-to-triangle / segment distance against sampling, the grid against brute force (XZ and XYZ)',geometry_distances),
                      ('Inside test and Exclusion value against the analytic box',closed_mesh),
                      ('Height field: band, falloff, hard edge, Invert',height_field),
                      ('Slope field: flat, ramp, off-surface points, falloff',slope_field),
                      ('Noise field equals the Mask noise; Mask Scale and Field Scale multiply',noise_field),
                      ('Image field: gradient read back, outside, projections',image_field),
                      ('Distance field: curve and mesh targets, XZ and XYZ, Invert',distance_field),
                      ('Exclusion field: inside, margin, falloff',exclusion_field),
                      ('Combine: Multiply, Add, Subtract, Min, Max, ignored first Combine, disabled rows, chained rows',combining),
                      ('Effects: Density keyed on ids, Scale, Density + Scale, Stack Seed, read-out',effects),
                      ('A higher weight only adds points; survivors keep ids and positions',monotonic),
                      ('Stack on Surface Scatter keeps only the flat ground',with_surface),
                      ('Errors and read-outs are readable',errors_and_info)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_fields_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
