"""v1.8.0 built-in LOD generator in real Houdini: hython tests/validate_lodgen.py [version]
The reduction (vertex clustering with quadric positions) is checked against geometry facts (triangle targets, no degenerate or duplicate triangles, distance to the sphere, area,
planarity, determinism, primvars carried over with their interpolation), then on the node: the generated prims in the stream (hierarchy, transforms, materials, primvars), the
prototype list, the camera LOD switch with the generated levels, explicit LOD prims winning, and Generate LODs off reproducing the previous release.
Env ARRAYTRON_MUTATE=lodgen_ratio|lodgen_explicit|lodgen_st|lodgen_dup|lodgen_level breaks the module; the suite must FAIL."""
from pathlib import Path
import hou, importlib.util, json, os, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom, Gf, Sdf, Vt
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v1.8.0':'v1.7.0','v1.9.0':'v1.8.0','v1.10.0':'v1.9.0','v1.11.0':'v1.10.0','v1.12.0':'v1.11.0','v1.13.0':'v1.12.0','v1.14.0':'v1.13.0','v1.15.0':'v1.14.0','v1.10.0':'v1.9.0','v1.11.0':'v1.10.0','v1.12.0':'v1.11.0','v1.13.0':'v1.12.0','v1.14.0':'v1.13.0','v1.15.0':'v1.14.0'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_lodgen_'));checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')
spec=importlib.util.spec_from_file_location('lodgen_src',str(ROOT/'src/arraytron_lodgen.py'));LG=importlib.util.module_from_spec(spec);spec.loader.exec_module(LG)   # the pure functions, no Houdini needed

def icosphere(level=4):
    t=(1+5**0.5)/2;V=[(-1,t,0),(1,t,0),(-1,-t,0),(1,-t,0),(0,-1,t),(0,1,t),(0,-1,-t),(0,1,-t),(t,0,-1),(t,0,1),(-t,0,-1),(-t,0,1)]
    F=[(0,11,5),(0,5,1),(0,1,7),(0,7,10),(0,10,11),(1,5,9),(5,11,4),(11,10,2),(10,7,6),(7,1,8),(3,9,4),(3,4,2),(3,2,6),(3,6,8),(3,8,9),(4,9,5),(2,4,11),(6,2,10),(8,6,7),(9,8,1)]
    V=[np.array(v,dtype=float)/np.linalg.norm(v) for v in V]
    for _ in range(level):
        cache={};new=[]
        def mid(a,b):
            k=(min(a,b),max(a,b))
            if k not in cache:
                m=V[a]+V[b];V.append(m/np.linalg.norm(m));cache[k]=len(V)-1
            return cache[k]
        for a,b,c in F:
            ab,bc,ca=mid(a,b),mid(b,c),mid(c,a);new+=[(a,ab,ca),(b,bc,ab),(c,ca,bc),(ab,bc,ca)]
        F=new
    return np.array(V),np.array(F,dtype=np.int64)
def grid(n=40):
    xs=np.linspace(0,4,n+1);P=np.array([(x,0.0,z) for z in xs for x in xs]);Q=[]
    for j in range(n):
        for i in range(n):a=j*(n+1)+i;Q.append((a,a+1,a+n+2,a+n+1))
    return P,np.array(Q,dtype=np.int64)
def tri_area(P,tri):
    return float(0.5*np.linalg.norm(np.cross(P[tri[:,1]]-P[tri[:,0]],P[tri[:,2]]-P[tri[:,0]]),axis=1).sum())

def write_scene():
    path=WORK/'lodgen.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    ball=UsdGeom.Xform.Define(s,'/World/Props/Ball');ball.AddTranslateOp().Set((0,0.25,0))
    V,F=icosphere(4);m=UsdGeom.Mesh.Define(s,'/World/Props/Ball/Sphere');m.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(V.astype(np.float32)));m.CreateFaceVertexCountsAttr([3]*len(F));m.CreateFaceVertexIndicesAttr(F.reshape(-1).tolist())
    m.CreateNormalsAttr(Vt.Vec3fArray.FromNumpy(V.astype(np.float32)));m.SetNormalsInterpolation('vertex');m.CreateSubdivisionSchemeAttr('none')
    st=UsdGeom.PrimvarsAPI(m).CreatePrimvar('st',Sdf.ValueTypeNames.TexCoord2fArray,UsdGeom.Tokens.faceVarying);st.Set(Vt.Vec2fArray.FromNumpy(np.array([(V[i][0],V[i][2]) for i in F.reshape(-1)],dtype=np.float32)))
    dc=UsdGeom.PrimvarsAPI(m).CreatePrimvar('displayColor',Sdf.ValueTypeNames.Color3fArray,UsdGeom.Tokens.vertex);dc.Set(Vt.Vec3fArray.FromNumpy(((V+1)/2).astype(np.float32)))
    UsdGeom.Scope.Define(s,'/World/Looks');mat=s.DefinePrim('/World/Looks/Red','Material')
    from pxr import UsdShade
    UsdShade.MaterialBindingAPI.Apply(m.GetPrim());UsdShade.MaterialBindingAPI(m.GetPrim()).Bind(UsdShade.Material(mat))
    UsdGeom.Xform.Define(s,'/World/Props/Box');b=UsdGeom.Mesh.Define(s,'/World/Props/Box/Mesh');b.CreatePointsAttr([(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)])
    b.CreateFaceVertexCountsAttr([4]*6);b.CreateFaceVertexIndicesAttr([0,3,2,1,4,5,6,7,0,1,5,4,2,3,7,6,0,4,7,3,1,2,6,5])
    UsdGeom.Xform.Define(s,'/World/Props/Hand');h=UsdGeom.Mesh.Define(s,'/World/Props/Hand/Mesh');h.CreatePointsAttr([(0,0,0),(1,0,0),(1,1,0),(0,1,0)]);h.CreateFaceVertexCountsAttr([4]);h.CreateFaceVertexIndicesAttr([0,1,2,3])
    cam=UsdGeom.Camera.Define(s,'/World/Cam');cam.CreateFocalLengthAttr(35.0)
    s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True)
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim')
    return st,n
def painted(stage,source,P,name='Gen',typ=None,**values):
    P=np.asarray(P,dtype=float).reshape(-1,3);a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Ball')
    a.parm('mode').set(6);a.parm('paint_prim').set('');a.parm('paint_align').set(0.0);m=a.hdaModule();table=np.column_stack([P,np.tile([0.0,1.0,0.0],(len(P),1)),np.arange(len(P))]);a.parm('paint_data').set(m.paint_encode(dict(pts=table,next=len(P),dab=1)))
    for k,v in values.items():a.parmTuple(k).set(v if isinstance(v,(tuple,list)) else (v,))
    if typ is None:mutate(a)
    return a
def out(a):
    s=a.stage();assert not all_errors(a),all_errors(a);pi=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    return dict(pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3),ids=np.array(pi.GetIdsAttr().Get(t) or [],dtype=int),proto=np.array(pi.GetProtoIndicesAttr().Get(t) or [],dtype=int),
                targets=[str(x) for x in pi.GetPrototypesRel().GetTargets()],hidden=sorted(int(i) for i in (pi.GetInvisibleIdsAttr().Get(t) or [])))
def all_errors(node):
    o=list(node.errors())
    for c in node.children():o+=all_errors(c)
    return o
def mesh_arrays(stage,path):
    m=UsdGeom.Mesh(stage.GetPrimAtPath(path));assert m,path;return np.array(m.GetPointsAttr().Get()).reshape(-1,3),np.array(m.GetFaceVertexCountsAttr().Get()),np.array(m.GetFaceVertexIndicesAttr().Get())
def mutate(a=None):
    targets=[LG.__dict__]+([a.hdaModule().lodgen_reduce.__globals__] if a is not None else [])
    for g in targets:
        if g.get('_mutation')==MUTATE:continue
        g['_mutation']=MUTATE
        if MUTATE=='lodgen_ratio':
            good=g['lodgen_reduce'];g['lodgen_reduce']=lambda P,c,i,ratio,min_tris=12:good(P,c,i,0.9,min_tris)
        elif MUTATE=='lodgen_explicit':
            good=g['lod_entries'] if 'lod_entries' in g else None
            if good:g['lod_entries']=lambda asset:[(r,l,g['lodgen_path'](asset,r,l)) for r,l,p in good(asset)]
        elif MUTATE=='lodgen_st':
            good=g['lodgen_transfer'];g['lodgen_transfer']=lambda v,i,res:good(v,'vertex' if i=='faceVarying' else i,res)
        elif MUTATE=='lodgen_dup':
            g['_kept']=lambda tri,key:(lambda c:np.nonzero((c[:,0]!=c[:,1])&(c[:,1]!=c[:,2])&(c[:,0]!=c[:,2]))[0])(key[tri])
        elif MUTATE=='lodgen_level':
            good=g['lodgen_path'];g['lodgen_path']=lambda asset,row,level:good(asset,row,min(level,2))
        elif MUTATE:raise SystemExit('unknown mutation '+MUTATE)
if MUTATE:mutate()
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()

def reduce_maths():
    V,F=icosphere(4);T=len(F);counts=np.full(T,3);idx=F.reshape(-1);area0=tri_area(V,F);assert T==5120
    for ratio,dev,area_lo in ((0.5,0.06,0.9),(0.2,0.12,0.8),(0.05,0.25,0.5)):
        res=LG.lodgen_reduce(V,counts,idx,ratio,12);K=len(res['tri']);target=int(np.ceil(ratio*T))
        assert 0.5*target<=K<=target,(ratio,K,target)                                                                   # meets the target, not far below it
        tri=res['tri'];P=res['points'];assert tri.min()>=0 and tri.max()<len(P) and len(P)==len(np.unique(tri))          # every point is used
        assert np.all((tri[:,0]!=tri[:,1])&(tri[:,1]!=tri[:,2])&(tri[:,0]!=tri[:,2])),'degenerate'
        assert len(np.unique(np.sort(tri,axis=1),axis=0))==K,'duplicate triangles'
        r=np.linalg.norm(P,axis=1);assert np.abs(r-1).max()<dev,(ratio,np.abs(r-1).max())                                # the points stay on the surface
        a=tri_area(P,tri)/area0;assert area_lo<=a<=1.01,(ratio,a)                                                       # about the same area (a coarser mesh is a bit smaller)
        assert np.all(P.max(axis=0)<=1.01) and np.all(P.min(axis=0)>=-1.01) and np.all(P.max(axis=0)>0.7) and np.all(P.min(axis=0)<-0.7)   # the bounding box is kept
        again=LG.lodgen_reduce(V,counts,idx,ratio,12);assert np.array_equal(again['tri'],tri) and np.array_equal(again['points'],P)         # deterministic
    tiny=LG.lodgen_reduce(V,counts,idx,0.0001,12);assert 4<=len(tiny['tri'])<=12                                             # the minimum triangles
    cube=np.array([(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)],dtype=float)
    assert LG.lodgen_reduce(cube,[4]*6,[0,3,2,1,4,5,6,7,0,1,5,4,2,3,7,6,0,4,7,3,1,2,6,5],0.5,12) is None                      # 12 triangles: already at the minimum
    P,Q=grid(40);res=LG.lodgen_reduce(P,np.full(len(Q),4),Q.reshape(-1),0.1,12);K=len(res['tri'])
    assert 0.5*320<=K<=320 and np.allclose(res['points'][:,1],0.0,atol=1e-9)                                                  # quads are triangulated; a flat plane stays flat
    assert abs(tri_area(res['points'],res['tri'])/16.0-1.0)<0.2
    P,Q=grid(40);two=np.vstack([P,P+np.array([0.0,0.001,0.0])]);Q2=np.vstack([Q,Q[:,[0,3,2,1]]+len(P)])                              # a thin double-sided sheet: front and back collapse onto the same triangles
    res=LG.lodgen_reduce(two,np.full(len(Q2),4),Q2.reshape(-1),0.1,12);K=len(res['tri']);assert K<=640 and len(np.unique(np.sort(res['tri'],axis=1),axis=0))==K,'the two layers must not leave duplicate triangles'
    n=LG.lodgen_normals(V,F);assert np.allclose(n,V,atol=0.02)                                                              # smooth normals of a sphere point outwards

def primvar_maths():
    P,Q=grid(40);counts=np.full(len(Q),4);idx=Q.reshape(-1);tri,corner,face=LG.lodgen_triangulate(counts,idx);assert tri.shape==(3200,3) and np.array_equal(face,np.repeat(np.arange(1600),2))
    res=LG.lodgen_reduce(P,counts,idx,0.1,12);st=np.array([(P[i][0],P[i][2]) for i in idx]);uni=np.arange(len(Q))*1.0;col=P.copy()
    fv=LG.lodgen_transfer(st,'faceVarying',res);assert fv.shape==(3*len(res['tri']),2)
    for t in range(len(res['tri'])):
        for c in range(3):assert np.allclose(fv[3*t+c],P[tri[res['src_tri'][t]][c]][[0,2]])                                    # the corner keeps the uv of the original corner
    vtx=LG.lodgen_transfer(col,'vertex',res);assert vtx.shape==res['points'].shape and np.allclose(vtx,P[res['vertex_src']])
    assert np.allclose(np.linalg.norm(vtx-res['points'],axis=1).max(),0.0,atol=0.6)                                          # a vertex colour comes from a vertex of its own cluster
    un=LG.lodgen_transfer(uni,'uniform',res);assert np.array_equal(un,face[res['src_tri']]*1.0)
    assert LG.lodgen_transfer(np.array([5.0]),'constant',res).tolist()==[5.0]

def stage_prims():
    st,sc=new_scene('stage');a=painted(st,sc,[(0,0,-3)],lodg_on=1);o=out(a);s=a.stage();m=a.hdaModule()
    assert len(o['targets'])==4,o['targets']                                                                              # the hero and three generated levels
    hero=mesh_arrays(s,'/World/Props/Ball/Sphere');assert len(hero[0])==2562 and len(hero[1])==5120                              # the hero is untouched
    got={}
    for level,name,ratio in ((1,'LOD1',0.5),(2,'LOD2',0.2),(3,'PROXY',0.05)):
        path='/World/Arraytron_LOD/Proto01_%s/Sphere'%name;P,counts,idx=mesh_arrays(s,path);K=len(counts);got[level]=K
        target=int(np.ceil(ratio*5120));assert 0.5*target<=K<=target and set(counts.tolist())=={3},(name,K,target)
        mesh=UsdGeom.Mesh(s.GetPrimAtPath(path));pv=UsdGeom.PrimvarsAPI(mesh)
        assert pv.GetPrimvar('st').GetInterpolation()=='faceVarying' and len(pv.GetPrimvar('st').ComputeFlattened())==3*K
        assert pv.GetPrimvar('displayColor').GetInterpolation()=='vertex' and len(pv.GetPrimvar('displayColor').ComputeFlattened())==len(P)
        n=mesh.GetNormalsAttr().Get();assert n is not None and len(n)==len(P) and mesh.GetNormalsInterpolation()=='vertex'
        assert np.allclose(np.linalg.norm(np.array(n),axis=1),1.0,atol=1e-3)
        assert [str(t) for t in UsdShadeBind(s.GetPrimAtPath(path))]==['/World/Looks/Red']                                    # the material binding is kept
        root=s.GetPrimAtPath('/World/Arraytron_LOD/Proto01_%s'%name);assert root.GetTypeName()=='Xform' and list(UsdGeom.Xformable(root).GetXformOpOrderAttr().Get())==['xformOp:translate'] and tuple(root.GetAttribute('xformOp:translate').Get())==(0,0.25,0)
    assert got[1]>got[2]>got[3]
    t=m.lod_table(a);assert t=={0:{1:1,2:2,3:3}},t                                                                          # hero 0, LOD prototypes 1, 2, 3
    info=m.lodgen_info(a);assert 'Prototype 1' in info and 'LOD 1' in info and 'Proxy' in info and '5,120' in info,info
    assert s.GetPrimAtPath('/World/Arraytron_LOD').GetTypeName()=='Scope'
    # a mesh with few triangles is copied as it is (the Box has 12)
    b=painted(st,sc,[(0,0,-3)],name='Box',lodg_on=1,proto_prim1='/World/Props/Box');out(b)
    P,counts,idx=mesh_arrays(b.stage(),'/World/Props/Box_LOD/Proto01_LOD1/Mesh') if False else mesh_arrays(b.stage(),'/World/Arraytron_LOD/Proto01_LOD1/Mesh');assert len(counts)==6 and len(P)==8

def UsdShadeBind(prim):
    from pxr import UsdShade
    return UsdShade.MaterialBindingAPI(prim).GetDirectBindingRel().GetTargets()

def lod_switch():
    st,sc=new_scene('switch')
    pts=[(0,0,-3),(0,0,-10),(0,0,-30),(0,0,-100)]
    a=painted(st,sc,pts,lodg_on=1,cam_on=1,cam_prim='/World/Cam',cam_lod=1,lod_by=0,lod_d1=5.0,lod_d2=20.0,lod_d3=60.0,cam_frustum=0);o=out(a)
    order=np.argsort(o['ids']);assert o['ids'][order].tolist()==[0,1,2,3] and o['proto'][order].tolist()==[0,1,2,3],(o['ids'],o['proto'])      # hero, LOD 1, LOD 2, Proxy by distance
    [a.parm(n).set(1000.0) for n in ('lod_d1','lod_d2','lod_d3')];o=out(a);assert set(o['proto'].tolist())=={0}                                                  # nothing is far enough

def explicit_wins():
    st,sc=new_scene('explicit');a=painted(st,sc,[(0,0,-3)],lodg_on=1,proto_lod11='/World/Props/Hand');o=out(a);s=a.stage();m=a.hdaModule()
    assert len(o['targets'])==4 and m.lod_entries(a)[0]==(1,1,'/World/Props/Hand') and m.lod_entries(a)[1][2].endswith('Proto01_LOD2')
    assert not s.GetPrimAtPath('/World/Arraytron_LOD/Proto01_LOD1').IsValid() and s.GetPrimAtPath('/World/Arraytron_LOD/Proto01_LOD2').IsValid() and s.GetPrimAtPath('/World/Arraytron_LOD/Proto01_PROXY').IsValid()
    a.parm('proto_lod21').set('/World/Props/Hand')                                                                                 # the same prim twice is still refused
    try:out(a)
    except AssertionError as exc:assert 'already used' in str(exc),str(exc)[:200]
    else:raise AssertionError('the same prim for two levels must be an error')

def off_reproduces():
    st,sc=new_scene('off');pts=[(0,0,-3),(1,0,-10),(-1,0,-30),(2,0,-100)];a=painted(st,sc,pts);o=out(a);b=painted(st,sc,pts,name='Old',typ=OLD_TYPE);p=out(b)
    assert not a.stage().GetPrimAtPath('/World/Arraytron_LOD').IsValid() and len(o['targets'])==1
    assert np.array_equal(o['ids'],p['ids']) and np.allclose(o['pos'],p['pos']) and np.array_equal(o['proto'],p['proto']) and [t.split('/')[-1] for t in o['targets']]==[t.split('/')[-1] for t in p['targets']]
    assert a.evalParm('lodg_on')==0 and a.evalParm('lodg_1')==50.0 and a.evalParm('lodg_2')==20.0 and a.evalParm('lodg_3')==5.0 and a.evalParm('lodg_min')==12

def cache_and_updates():
    st,sc=new_scene('cache');a=painted(st,sc,[(0,0,-3)],lodg_on=1);m=a.hdaModule();out(a);P1=mesh_arrays(a.stage(),'/World/Arraytron_LOD/Proto01_LOD1/Sphere')
    g=m.lodgen_reduce.__globals__;assert len(g['_LODGEN_CACHE'])>=3
    a.parm('lodg_1').set(50.0);out(a);P2=mesh_arrays(a.stage(),'/World/Arraytron_LOD/Proto01_LOD1/Sphere');assert all(np.array_equal(x,y) for x,y in zip(P1,P2))                    # same settings, same mesh
    a.parm('lodg_1').set(30.0);out(a);K=len(mesh_arrays(a.stage(),'/World/Arraytron_LOD/Proto01_LOD1/Sphere')[1]);target=int(np.ceil(0.3*5120));assert 0.5*target<=K<=target
    a.parm('lodg_min').set(2000);a.parm('lodg_3').set(1.0);out(a);K=len(mesh_arrays(a.stage(),'/World/Arraytron_LOD/Proto01_PROXY/Sphere')[1]);assert 1000<=K<=2000,K     # the minimum wins over a tiny percentage
    a.parm('lodg_on').set(0);o=out(a);assert len(o['targets'])==1 and not a.stage().GetPrimAtPath('/World/Arraytron_LOD').IsValid()                                         # off again: the stream is clean

def contract():
    st,sc=new_scene('contract');a=st.createNode(TYPE,'C');g=a.parmTemplateGroup()
    for name in ('lodg_on','lodg_1','lodg_2','lodg_3','lodg_min','lodg_info'):assert g.find(name) is not None,name
    assert g.find('lodg_1').conditionalType()==hou.parmCondType.HideWhen and 'lodg_on' in g.find('lodg_1').conditionalValue(hou.parmCondType.HideWhen) if hasattr(g.find('lodg_1'),'conditionalValue') else True
    opt=[t for t in g.entries() if t.label()=='Optimize'][0];names=[t.name() for t in opt.parmTemplates()];assert names.index('lodg_on')>names.index('cam_lod') and names.index('lodg_on')<names.index('pv_id')
    assert a.node('LOD_GENERATOR') is not None and a.node('USD_COMPILER').inputs()[0].name()=='LOD_GENERATOR' and a.node('LOD_GENERATOR').inputs()[0].name()=='SOURCE_RESOLVER'
    if versions.is_h205():assert a.node('PROTO_STAGE').inputs()[0].name()=='LOD_GENERATOR'
    assert '$' not in a.node('LOD_GENERATOR').parm('python').eval() and '$' not in a.type().definition().sections()['PythonModule'].contents().split('# ---- LOD generator')[1]
    assert g.find('lodg_on').help() and 'never changed' in g.find('lodg_on').help()

def main():
    for name,func in (('Reduction: triangle targets, no degenerate or duplicate triangles, surface distance, area, bounding box, planarity, determinism, minimum',reduce_maths),
                      ('Primvars: face-varying, vertex, uniform and constant carried over to the reduced mesh',primvar_maths),
                      ('On the node: generated prims (hierarchy, transform, material, primvars, normals), hero untouched, prototype list, read-out',stage_prims),
                      ('Level of detail switch uses the generated levels by camera distance',lod_switch),
                      ('A prim of its own wins over the generated level',explicit_wins),
                      ('Generate LODs off reproduces the previous release and writes no prims',off_reproduces),
                      ('Cache, determinism, percentage and minimum changes, switching off cleans the stream',cache_and_updates),
                      ('Contract: parameters, Optimize tab placement, LOD_GENERATOR in the network, no dollar signs',contract)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_lodgen_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
