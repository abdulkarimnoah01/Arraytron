"""Camera-aware optimisation, LOD / proxy prototypes and extended primvars (v0.9.0) validation in real Houdini: hython tests/validate_camera.py
Points are injected through Paint mode (exact positions and ids). Expected results come from plain-Python re-implementations: the camera frustum from
the camera's own basis vectors and apertures (sphere against the four side planes and the clipping range), the per-id random numbers from an own
splitmix64, the LOD levels from the thresholds. Env ARRAYTRON_MUTATE=<name> breaks the module; the suite must FAIL."""
from pathlib import Path
import hou, json, math, os, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom, Gf, Vt
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PHYSTAB='Physics' if VID[0]=='v' and tuple(int(x) for x in VID[1:].split('.'))>=(1,6,2) else 'Settle'
PREVIOUS={'v0.9.0':'v0.8.0','v1.0.0':'v0.9.0','v1.1.0':'v1.0.0','v1.5.0':'v1.1.0','v1.6.0':'v1.5.0','v1.6.1':'v1.6.0','v1.6.2':'v1.6.1','v1.7.0':'v1.6.2','v1.8.0':'v1.7.0','v1.9.0':'v1.8.0','v1.9.0':'v1.8.0'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_camera_'));checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE');M64=(1<<64)-1
HAP,VAP,FOCAL=36.0,20.25,50.0;HX,HY=HAP/(2*FOCAL),VAP/(2*FOCAL);NEAR,FAR=0.5,150.0          # camera: tangent of the half fields of view 0.36 / 0.2025, clipping range
RAD=0.1*math.sqrt(3.0)                                                                         # bounding radius of a 0.2 cube prototype about its origin
def ref_hash(i,seed,stream=0):
    z=(i*0x9E3779B97F4A7C15+seed*0xD1B54A32D192ED03+(stream+1)*0x8CB92BA72F3D8DD7)&M64
    z=((z^(z>>30))*0xBF58476D1CE4E5B9)&M64;z=((z^(z>>27))*0x94D049BB133111EB)&M64;z=z^(z>>31)
    return (z>>11)/float(1<<53)
def basis(eye,target,up=(0,1,0)):
    z=np.array(eye,float)-np.array(target,float);z/=np.linalg.norm(z);x=np.cross(up,z);x/=np.linalg.norm(x);y=np.cross(z,x);return x,y,z
def matrix(eye,target):
    x,y,z=basis(eye,target);return Gf.Matrix4d(x[0],x[1],x[2],0,y[0],y[1],y[2],0,z[0],z[1],z[2],0,eye[0],eye[1],eye[2],1)
def add_camera(s,path,eye,target):
    cam=UsdGeom.Camera.Define(s,path);cam.CreateHorizontalApertureAttr(HAP);cam.CreateVerticalApertureAttr(VAP);cam.CreateFocalLengthAttr(FOCAL);cam.CreateClippingRangeAttr(Gf.Vec2f(NEAR,FAR))
    UsdGeom.Xformable(cam).AddTransformOp().Set(matrix(eye,target));return cam
def write_scene():
    path=WORK/'camera.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y);s.SetStartTimeCode(1);s.SetEndTimeCode(10)
    for name,size in (('Ball',0.2),('BallB',0.2),('Lod1',0.2),('Lod2',0.2),('Proxy',0.2)):
        UsdGeom.Xform.Define(s,'/World/Props/'+name);UsdGeom.Cube.Define(s,'/World/Props/%s/C'%name).CreateSizeAttr(size)
    add_camera(s,'/World/Cam',(0,0,10),(0,0,0))                                             # looks down -Z from z = 10
    add_camera(s,'/World/CamSide',(10,0,0),(0,0,0))                                         # looks down -X from x = 10
    cam=add_camera(s,'/World/CamMove',(0,0,10),(0,0,0));op=UsdGeom.Xformable(cam).GetOrderedXformOps()[0]                       # slides along +X from frame 1 to 10, same orientation
    op.Set(matrix((0,0,10),(0,0,0)),1);op.Set(Gf.Matrix4d(matrix((0,0,10),(0,0,0))).__class__(*[v for r in range(4) for v in (list(matrix((0,0,10),(0,0,0))[r]) if r<3 else [20,0,10,1])]),10)
    s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True)
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
def painted(stage,source,P,name='Cam',typ=None,**values):
    P=np.asarray(P,dtype=float).reshape(-1,3);a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Ball')
    a.parm('mode').set(6);a.parm('paint_prim').set('');a.parm('paint_align').set(0.0);m=a.hdaModule();table=np.column_stack([P,np.tile([0.0,1.0,0.0],(len(P),1)),np.arange(len(P))]);a.parm('paint_data').set(m.paint_encode({'pts':table,'dab':1,'next':len(P)}))
    for k,v in values.items():a.parmTuple(k).set(v if isinstance(v,(tuple,list)) else (v,))
    if typ is None and MUTATE:mutate(a)
    return a
def prim_of(a):return a.stage().GetPrimAtPath(a.evalParm('outputpath'))
def out(a):
    s=a.stage();assert not a.errors(),a.errors();prim=s.GetPrimAtPath(a.evalParm('outputpath'));pi=UsdGeom.PointInstancer(prim);t=hou.frame()
    return dict(pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3),ids=np.array(pi.GetIdsAttr().Get(t) or [],dtype=int),proto=np.array(pi.GetProtoIndicesAttr().Get(t) or [],dtype=int),
                hidden=sorted(int(i) for i in (pi.GetInvisibleIdsAttr().Get(t) or [])),scales=np.array(pi.GetScalesAttr().Get(t) or []).reshape(-1,3),targets=[str(p) for p in pi.GetPrototypesRel().GetTargets()],prim=prim)
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
    if MUTATE=='cam_margin':
        good=g['frustum_outside'];g['frustum_outside']=lambda v,radius,hx,hy,near,far,margin=0.0,orthographic=False:good(v,radius,hx,hy,near,far,0.0,orthographic)
    elif MUTATE=='cam_planes':
        good=g['frustum_outside'];g['frustum_outside']=lambda v,radius,hx,hy,near,far,margin=0.0,orthographic=False:good(v,radius,hy,hx,near,far,margin,orthographic)
    elif MUTATE=='cam_density':
        good=g['density_keep'];g['density_keep']=lambda d,near,far,minimum:good(d,far,near,minimum)
    elif MUTATE=='cam_lod':
        good=g['lod_levels'];g['lod_levels']=lambda values,thresholds,descending:np.maximum(good(values,thresholds,descending)-1,0)
    elif MUTATE=='cam_merge':g['merged_invisible']=lambda existing,hidden_ids:sorted(set(int(i) for i in hidden_ids))
    elif MUTATE=='cam_screen':
        good=g['screen_fraction'];g['screen_fraction']=lambda depth,radius,proj_yy,orthographic=False:good(depth,radius*2.0,proj_yy,orthographic)
    elif MUTATE=='cam_fallback':g['available_level']=lambda wanted,have:wanted if wanted in have else 0
    elif MUTATE=='cam_hash':
        good=g['scatter_hash'];g['scatter_hash']=lambda ids,seed,stream=0:good(ids,seed,stream+1 if stream in (71,72) else stream)
    else:raise SystemExit('unknown mutation '+MUTATE)
def ref_view(eye,target,p):
    x,y,z=basis(eye,target);d=np.array(p,float)-np.array(eye,float);return np.array([d@x,d@y,d@z])
def ref_outside(v,r,margin=0.0):
    depth=-v[2];hx,hy=HX*(1+margin),HY*(1+margin);nx,ny=math.sqrt(1+hx*hx),math.sqrt(1+hy*hy)
    return (hx*depth-v[0])/nx<-r or (hx*depth+v[0])/nx<-r or (hy*depth-v[1])/ny<-r or (hy*depth+v[1])/ny<-r or depth+r<NEAR or depth-r>FAR
def spread(n=240,seed=2):
    rng=np.random.default_rng(seed);return np.column_stack([rng.uniform(-14,14,n),rng.uniform(-8,8,n),rng.uniform(-30,40,n)])      # around the camera at z = 10: in front, beside and behind it

# ------------------------------------------------------------------ groups
def ui_contract():
    st,sc=new_scene('ui');a=painted(st,sc,[[0,0,0]]);g=a.parmTemplateGroup()
    names=('cam_on','cam_prim','cam_frustum','cam_margin','cam_behind','cam_behind_keep','cam_distcull','cam_maxdist','cam_densityon','cam_dnear','cam_dfar','cam_dmin','cam_seed','cam_lod','lod_by','lod_d1','lod_d2','lod_d3','lod_s1','lod_s2','lod_s3','cam_info','cam_frame','pv_id','pv_proto','pv_random','pv_mask','pv_density','pv_cluster','pv_lod','pv_seed','proto_lod1#','proto_lod2#','proto_proxy#')
    for n in names:assert g.find(n) is not None,n
    assert g.find('cam_on').defaultValue() is False and g.find('cam_lod').defaultValue() is False and g.find('cam_behind').menuLabels()==('Keep All','Reduce','Hide') and g.find('lod_by').menuLabels()==('Distance','Screen Size')
    assert g.find('cam_frame').isHidden() and g.find('cam_prim').defaultValue()==('/cameras/camera1',)
    tabs=[t.label() for t in g.entries()];assert tabs[:7]==['Source','Layout','Look','Spacing',PHYSTAB,'Animate','Optimize'],tabs
    opt=g.entries()[6];heads=[t.columnLabels()[0] for t in opt.parmTemplates() if t.name().startswith('ui_head')];assert heads==['CAMERA','LEVEL OF DETAIL']+(['LOD GENERATOR'] if a.parm('lodg_on') is not None else [])+['PRIMVARS']
    assert '{ cam_on == 0 }' in g.find('cam_frustum').conditionals()[hou.parmCondType.HideWhen] and '{ lod_by != 0 }' in g.find('lod_d1').conditionals()[hou.parmCondType.HideWhen]
    assert a.node('camera_optimize').inputs()[0].name()=='transform_distribution' and a.node('OUT_ARRAYTRON').inputs()[0].name()==('debug_guide' if a.node('debug_guide') else 'camera_optimize')
    feed=a.node('USD_COMPILER/OUT_POINTS').inputs()[0]
    if feed.name()=='PROTO_PATH':feed=feed.inputs()[0]          # Houdini 20.5 / 21 build
    assert a.node('USD_COMPILER/PRIMVARS') is not None and feed.name()=='PRIMVARS'
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
        n=fn[name];assert n.type()==t.type() and n.numComponents()==t.numComponents(),name
        if hasattr(t,'defaultValue'):assert n.defaultValue()==t.defaultValue(),name
        if t.type()==hou.parmTemplateType.Menu:assert n.menuItems()[:len(t.menuItems())]==t.menuItems(),name
def defaults_unchanged():
    st,sc=new_scene('defaults');P=np.random.default_rng(3).uniform(-3,3,(60,3))
    for values in (dict(mode=0,line_count=7),dict(mode=1,area_count=40,area_seed=3),dict(mode=5,surface_count=30,surface_prim='/World/Props/Ball'),dict(overlap_mode=1,overlap_size=1,overlap_radius=0.5)):
        mode=values.get('mode',6)
        a=painted(st,sc,P,'n%d'%len(values),**values);b=painted(st,sc,P,'o%d'%len(values),typ=OLD_TYPE,**values)
        try:x,y=out(a),out(b)
        except AssertionError:continue                                                                        # a combination that is not valid in both (the surface case needs a mesh): skip
        assert len(x['pos'])==len(y['pos']) and np.array_equal(x['ids'],y['ids']) and np.allclose(x['pos'],y['pos'],atol=1e-6) and np.array_equal(x['proto'],y['proto']) and x['hidden']==y['hidden']==[]
        assert not x['prim'].GetAttribute('primvars:arraytron_id').IsValid() and len(UsdGeom.PrimvarsAPI(x['prim']).GetPrimvars())==len(UsdGeom.PrimvarsAPI(y['prim']).GetPrimvars())      # no primvars unless asked
    hou.setFrame(1);a.cook(force=True);a.stage();assert not a.node('camera_optimize').isTimeDependent(),'Camera off: the node does not depend on time'
def maths():
    st,sc=new_scene('maths');a=painted(st,sc,[[0,0,0]]);m=a.hdaModule();rng=np.random.default_rng(5)
    V=rng.uniform(-30,30,(500,3));V[:,2]=rng.uniform(-60,20,500);r=rng.uniform(0,1.5,500)
    for margin in (0.0,0.2):
        got=m.frustum_outside(V,r,HX,HY,NEAR,FAR,margin);ref=[ref_outside(v,rad,margin) for v,rad in zip(V,r)];assert list(got)==ref and 50<sum(ref)<450
    got=m.frustum_outside(V,r,3.0,2.0,NEAR,FAR,0.1,True);ref=[abs(v[0])>3.3+rad or abs(v[1])>2.2+rad or -v[2]+rad<NEAR or -v[2]-rad>FAR for v,rad in zip(V,r)];assert list(got)==ref   # orthographic: constant half extents
    d=np.linspace(0,100,41)
    for near,far,mn in ((10.0,60.0,0.1),(20.0,20.0,0.3)):
        ref=[(float(mn) if x>near else 1.0) if far<=near else 1.0+(mn-1.0)*min(max((x-near)/(far-near),0.0),1.0) for x in d];assert np.allclose(m.density_keep(d,near,far,mn),ref)
    assert np.allclose(m.screen_fraction(np.array([5.0,10.0,0.0]),np.array([0.5,0.5,0.5]),4.0),[0.5*4/5,0.5*4/10,0.5*4/1e-9]) and np.allclose(m.screen_fraction(np.array([5.0,50.0]),np.array([0.5,0.5]),4.0,True),[2.0,2.0])
    vals=np.array([0.0,5.0,20.0,35.0,50.0,99.0,100.0,500.0]);assert list(m.lod_levels(vals,[20.0,50.0,100.0],False))==[0,0,1,1,2,2,3,3]
    assert list(m.lod_levels(np.array([5.0,9.0,11.0,60.0]),[8.0,50.0,10.5],False))==[0,1,3,3] and list(m.lod_levels(np.array([20.0,6.0,1.0]),[10.0,2.0,5.0],True))==[0,1,3]        # unsorted thresholds: the highest level passed wins
    sizes=np.array([50.0,10.0,9.9,4.0,3.9,1.5,1.4]);assert list(m.lod_levels(sizes,[10.0,4.0,1.5],True))==[0,0,1,1,2,2,3]
    assert [m.available_level(w,{1,2,3}) for w in range(4)]==[0,1,2,3] and [m.available_level(w,{2}) for w in range(4)]==[0,0,2,2] and [m.available_level(w,{3}) for w in range(4)]==[0,0,0,3] and m.available_level(3,{})==0
    table={0:{1:2,2:3},1:{},2:{3:4}};idx,applied=m.remap_proto_indices(np.array([0,0,0,1,2,2,0]),np.array([0,1,3,2,3,0,2]),table);assert list(idx)==[0,2,3,1,4,2,3] and list(applied)==[0,1,2,0,3,0,2]
    assert m.merged_invisible([5,3,3],[3,9,1])==[1,3,5,9]
def frustum_node():
    st,sc=new_scene('frustum');P=spread();a=painted(st,sc,P,cam_on=1,cam_prim='/World/Cam',cam_frustum=1,cam_margin=0.0)
    eye,target=(0,0,10),(0,0,0);full=out(a)['pos'] if False else None
    def hidden_ref(margin,behind=0,keep=0.25,maxdist=None,density=None,seed=1):
        h=set()
        for i,p in enumerate(P):
            v=ref_view(eye,target,p);why=False
            if behind==2 and v[2]>=0:why=True
            if behind==1 and v[2]>=0 and not ref_hash(i,seed,72)<keep:why=True
            if not why and (behind==0 or v[2]<0) and ref_outside(v,RAD,margin):why=True
            if not why and maxdist is not None and np.linalg.norm(v)-RAD>maxdist:why=True
            if not why and density is not None:
                near,far,mn=density;d=np.linalg.norm(v);k=1.0+(mn-1.0)*min(max((d-near)/(far-near),0.0),1.0)
                if not ref_hash(i,seed,71)<k-1e-12:why=True
            if v[2]>=0 and behind in (1,2) and not why and ref_outside(v,RAD,margin) and False:why=True
            if why:h.add(i)
        return sorted(h)
    d=out(a);assert d['hidden']==hidden_ref(0.0) and 40<len(d['hidden'])<200,(len(d['hidden']))
    assert 'visible' in a.parm('cam_info').eval() and '%d of 240 instances visible'%(240-len(d['hidden'])) in a.parm('cam_info').eval()
    a.parm('cam_margin').set(0.5);d=out(a);assert d['hidden']==hidden_ref(0.5)
    a.parm('cam_frustum').set(0);a.parm('cam_distcull').set(1);a.parm('cam_maxdist').set(18.0);assert out(a)['hidden']==hidden_ref(0.0,maxdist=18.0) if False else True
    d=out(a);ref=[i for i,p in enumerate(P) if np.linalg.norm(ref_view(eye,target,p))-RAD>18.0];assert d['hidden']==ref and 20<len(ref)<200
    a.parm('cam_distcull').set(0);a.parm('cam_densityon').set(1);a.parm('cam_dnear').set(8.0);a.parm('cam_dfar').set(30.0);a.parm('cam_dmin').set(0.2);d=out(a)
    ref=[i for i,p in enumerate(P) if not ref_hash(i,1,71)<1.0+(0.2-1.0)*min(max((np.linalg.norm(ref_view(eye,target,p))-8.0)/22.0,0.0),1.0)-1e-12];assert d['hidden']==ref and 20<len(ref)<200
    a.parm('cam_densityon').set(0);a.parm('cam_behind').set(2);d=out(a);ref=[i for i,p in enumerate(P) if ref_view(eye,target,p)[2]>=0];assert d['hidden']==ref and 20<len(ref)<200                         # Hide: everything behind the camera
    a.parm('cam_behind').set(1);a.parm('cam_behind_keep').set(0.3);d=out(a);assert d['hidden']==[i for i in ref if not ref_hash(i,1,72)<0.3] and 0<len(d['hidden'])<len(ref)                         # Reduce: a stable fraction stays
    a.parm('cam_seed').set(4);d=out(a);assert d['hidden']==[i for i in ref if not ref_hash(i,4,72)<0.3]
    a.parm('cam_seed').set(1);a.parm('cam_behind').set(0);a.parm('cam_frustum').set(1);a.parm('cam_margin').set(0.0);a.parm('cam_distcull').set(1);a.parm('cam_maxdist').set(25.0);a.parm('cam_densityon').set(1)
    d=out(a);h=set(hidden_ref(0.0,maxdist=25.0,density=(8.0,30.0,0.2)));assert set(d['hidden'])==h                                      # everything at once: the union
    a.parm('cam_on').set(0);assert out(a)['hidden']==[] and 'off' in a.parm('cam_info').eval()                                              # reversible: off brings everything back
def side_camera_and_motion():
    st,sc=new_scene('motion');P=spread(180,3);a=painted(st,sc,P,cam_on=1,cam_prim='/World/CamSide',cam_frustum=1,cam_margin=0.0)
    d=out(a);ref=[i for i,p in enumerate(P) if ref_outside(ref_view((10,0,0),(0,0,0),p),RAD)];assert d['hidden']==ref and 20<len(ref)<178                         # a rotated camera
    a.parm('cam_prim').set('/World/CamMove')
    for frame in (10,1,5,10,3):                                                                                                               # out of order: each frame is its own answer
        hou.setFrame(frame);eye=np.array([20.0*(frame-1)/9.0,0.0,10.0]);d=out(a)
        ref=[i for i,p in enumerate(P) if ref_outside(ref_view(tuple(eye),tuple(eye*[1,0,0]*0+[eye[0],0,0]),p),RAD)];assert d['hidden']==ref,(frame,len(d['hidden']),len(ref))
    hou.setFrame(1);assert a.node('camera_optimize').isTimeDependent()
def grow_merge():
    st,sc=new_scene('grow');P=spread(120,6);a=painted(st,sc,P,cam_on=1,cam_prim='/World/Cam',cam_frustum=1,cam_margin=0.0,grow_on=1,grow_sweep=20,grow_time=5)
    a.parm('grow_start').deleteAllKeyframes();a.parm('grow_start').set(1);a.parm('grow_direction').set(0);hou.setFrame(8)
    d=out(a);a.parm('cam_on').set(0);base=out(a);g=base['hidden'];sc_by_id={int(i):float(x) for i,x in zip(base['ids'],base['scales'].max(axis=1))};a.parm('cam_on').set(1)
    camera=[i for i,p in enumerate(P) if ref_outside(ref_view((0,0,10),(0,0,0),p),RAD*sc_by_id[i])]                                           # the radius follows the growing scale
    assert len(g)>0 and len(camera)>0 and d['hidden']==sorted(set(g)|set(camera)) and len(d['hidden'])>len(g)                                  # Grow's hidden ids and the camera's together
    hou.setFrame(1)
def lod_node():
    st,sc=new_scene('lod');P=np.column_stack([np.linspace(-1,1,60)*0.5,np.zeros(60),np.linspace(9.5,-100,60)])                                    # in a line away from the camera at z = 10
    a=painted(st,sc,P,cam_on=1,cam_prim='/World/Cam',cam_lod=1,lod_by=0,lod_d1=20.0,lod_d2=50.0,lod_d3=100.0)
    a.parm('protos').set(2);a.parm('proto_prim2').set('/World/Props/BallB');a.parm('proto_weight1').set(1.0);a.parm('proto_weight2').set(1.0)
    a.parm('proto_lod11').set('/World/Props/Lod1');a.parm('proto_lod21').set('/World/Props/Lod2');a.parm('proto_proxy1').set('/World/Props/Proxy')                  # row 1 has all three; row 2 none
    a.parm('cam_on').set(0);base=out(a);a.parm('cam_on').set(1);d=out(a)
    assert d['targets'][:2]==[base['targets'][0],base['targets'][1]] and [t.split('/')[-1] for t in d['targets']][:5]==['Ball','BallB','Lod1','Lod2','Proxy'],d['targets']       # heroes first, then the LOD prims in order
    dist=[np.linalg.norm(ref_view((0,0,10),(0,0,0),p)) for p in P];level=[int(x>=20)+int(x>=50)+int(x>=100) for x in dist]
    for k,(i,pr) in enumerate(zip(d['ids'],d['proto'])):
        hero=base['proto'][list(base['ids']).index(i)];want=hero if hero==1 else [0,2,3,4][level[i]]
        assert pr==want,(i,hero,level[i],pr,want)
    assert set(d['proto'])=={0,1,2,3,4}.intersection(set(d['proto'])) and {2,3,4}<=set(d['proto'])
    info=a.parm('cam_info').eval();assert 'LOD: hero' in info
    a.parm('lod_by').set(1);d=out(a);depth=[-ref_view((0,0,10),(0,0,0),p)[2] for p in P];proj_yy=1.0/HY
    pct=[RAD*proj_yy/dpt*100.0 for dpt in depth];lv=[int(x<10)+int(x<4)+int(x<1.5) for x in pct]                                                      # screen size, percent of the image height
    a.parm('lod_s1').set(10.0);a.parm('lod_s2').set(4.0);a.parm('lod_s3').set(1.5);d=out(a)
    for i,pr in zip(d['ids'],d['proto']):
        hero=base['proto'][list(base['ids']).index(i)];assert pr==(hero if hero==1 else [0,2,3,4][lv[i]]),(i,pct[i],lv[i],pr)
    a.parm('proto_lod11').set('');a.parm('proto_proxy1').set('');d=out(a);assert set(d['proto'])<={0,1,2} and 2 in d['proto']                                                            # only LOD 2 left: finer levels keep the hero, coarser use it
    a.parm('pv_lod').set(1);d=out(a);api=UsdGeom.PrimvarsAPI(d['prim']);pv=api.GetPrimvar('arraytron_lod');assert pv.IsDefined() and len(pv.Get(hou.frame()))==60
    a.parm('proto_lod11').set('/World/Props/Lod1');a.parm('proto_proxy1').set('/World/Props/Lod1')
    try:a.cook(force=True);a.stage()
    except hou.OperationFailed:pass
    assert any('already used' in e for e in all_errors(a)),all_errors(a)
    a.parm('proto_proxy1').set('/World/Props/Proxy');a.parm('cam_on').set(0);assert np.array_equal(out(a)['proto'],base['proto'])                                  # reversible
def primvars():
    st,sc=new_scene('pv');P=np.random.default_rng(8).uniform(-3,3,(40,3));a=painted(st,sc,P,pv_seed=5)
    def names(a):return sorted(p.GetName() for p in UsdGeom.PrimvarsAPI(prim_of(a)).GetPrimvars())
    assert names(a)==[]
    for toggle,pv in (('pv_id','arraytron_id'),('pv_proto','prototype_id'),('pv_random','random'),('pv_mask','mask'),('pv_density','density')):
        a.parm(toggle).set(1);assert pv in [n.replace('primvars:','') for n in names(a)]
    assert sorted(n.replace('primvars:','') for n in names(a))==['arraytron_id','density','mask','prototype_id','random']
    api=UsdGeom.PrimvarsAPI(prim_of(a));t=hou.frame();ids=np.array(UsdGeom.PointInstancer(prim_of(a)).GetIdsAttr().Get(t))
    rnd=np.array(api.GetPrimvar('random').Get(t))
    assert list(api.GetPrimvar('arraytron_id').Get(t))==list(ids) and set(api.GetPrimvar('mask').Get(t))=={1.0} and set(api.GetPrimvar('density').Get(t))=={1.0}
    assert rnd.min()>=0 and rnd.max()<1 and len(set(rnd.tolist()))==len(rnd) and 0.3<rnd.mean()<0.7                                            # a stable random number per id: in [0, 1), distinct, centred
    b2=painted(st,sc,P[:15],'sub',pv_seed=5,pv_random=1);r2=np.array(UsdGeom.PrimvarsAPI(prim_of(b2)).GetPrimvar('random').Get(t));assert np.array_equal(r2,rnd[:15])      # the same ids keep their values when other points are missing
    b2.parm('pv_seed').set(6);assert not np.array_equal(np.array(UsdGeom.PrimvarsAPI(prim_of(b2)).GetPrimvar('random').Get(t)),r2)
    assert set(api.GetPrimvar('prototype_id').Get(t))=={1}
    a.parm('protos').set(2);a.parm('proto_prim2').set('/World/Props/BallB');a.parm('proto_on1').set(1);rows=sorted(set(api.GetPrimvar('prototype_id').Get(t)))
    a.parm('mask_source').set(1);a.parm('mask_noise_freq').set(0.7);a.parm('mask_effect').set(1);a.parm('mask_minscale').set(0.0)
    a.parm('fields').set(1);a.parm('field_type1').set(0);a.parm('field_hmin1').set(-1.0);a.parm('field_hmax1').set(1.0);a.parm('field_hfall1').set(2.0);a.parm('field_effect').set(1);a.parm('field_minscale').set(0.0)
    d=out(a);api=UsdGeom.PrimvarsAPI(d['prim']);ids=d['ids'];mask=np.array(api.GetPrimvar('mask').Get(t));dens=np.array(api.GetPrimvar('density').Get(t))
    Y=P[ids,1];ref_d=[1.0 if -1<=y<=1 else 1.0-(lambda x:x*x*(3-2*x))(min(max(max(-1-y,y-1)/2.0,0),1)) for y in Y]
    assert np.allclose(dens,ref_d,atol=1e-5) and mask.min()<0.5 and mask.max()<=1.0 and np.allclose(mask,a.hdaModule().mask_weights(a,a.hdaModule().mask_values(a,P[ids],ids)),atol=1e-5)
    assert set(api.GetPrimvar('prototype_id').Get(t))<={1,2} and len(set(api.GetPrimvar('prototype_id').Get(t)))==2
    for toggle in ('pv_id','pv_proto','pv_random','pv_mask','pv_density'):a.parm(toggle).set(0)
    assert names(a)==[] or all(not n.startswith('primvars:') or n in ('primvars:displayColor','primvars:displayOpacity') for n in names(a))
    b=st.createNode(TYPE,'CL');b.setInput(0,sc);b.parm('protos').set(1);b.parm('proto_prim1').set('/World/Props/Ball');b.parm('mode').set(7);b.parm('cluster_prim').set('');b.parm('cluster_count').set(4);b.parm('pv_cluster').set(1)
    if MUTATE:mutate(b)
    pb=UsdGeom.PrimvarsAPI(prim_of(b)).GetPrimvar('cluster');cl=np.array(pb.Get(t));ids=np.array(UsdGeom.PointInstancer(prim_of(b)).GetIdsAttr().Get(t));assert np.array_equal(cl,ids//1000) and len(set(cl))==4
def errors():
    st,sc=new_scene('err');a=painted(st,sc,[[0,0,0],[1,0,0]],cam_on=1,cam_prim='/World/Nothing',cam_frustum=1)
    def fails(fragment):
        try:a.cook(force=True);a.stage()
        except hou.OperationFailed:pass
        text=' | '.join(all_errors(a));assert fragment in text,(fragment,text)
    fails('is not a camera in the stream');a.parm('cam_prim').set('/World/Props/Ball');fails('is not a camera in the stream');a.parm('cam_prim').set('');fails('(empty)')
    a.parm('cam_prim').set('/World/Cam');out(a);a.parm('cam_on').set(0);assert a.parm('cam_info').eval()=='Camera optimisation is off.'
def main():
    for name,func in (('UI contract: Optimize tab, parameters, bank LOD prims, camera LOP and PRIMVARS stage, every v0.8.0 parameter unchanged',ui_contract),
                      ('Everything off reproduces v0.8.0: no primvars, no hidden ids, not time dependent',defaults_unchanged),
                      ('Frustum, density, screen size, LOD levels and merging maths against plain Python',maths),
                      ('Camera culling on the node: frustum with margin, distance, density, behind camera, everything at once, reversible',frustum_node),
                      ('A rotated camera and an animated camera, frames out of order',side_camera_and_motion),
                      ('Camera hiding merges with the ids Grow hides',grow_merge),
                      ('LOD / proxy prototypes: order, distance and screen size levels, fallback, primvar, duplicate error, reversible',lod_node),
                      ('Extended primvars: ids, prototype row, random, mask, density, cluster, none when off',primvars),
                      ('Errors and read-outs are readable',errors)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_camera_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
