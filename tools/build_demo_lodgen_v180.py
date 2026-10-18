"""Build the LOD generator demo (v1.8.0): hython tools/build_demo_lodgen_v180.py
A dense rock (about 5,000 triangles, written once as test_assets/rock_dense.usda) in two uses, both with Generate LODs on and no LOD prim anywhere in the bank:
* a LADDER of four rocks in the foreground, each forced to one level (hero, LOD 1 at 40%, LOD 2 at 12%, Proxy at 3%) so the reduction shows in the silhouettes;
* a FIELD of 380 rocks on the ground whose level follows the camera distance.
Writes dist/Arraytron_<version>_lodgen_demo.hip (and the render USD) or the Houdini 20.5 / 21 equivalent."""
from pathlib import Path
import sys, hou, json, shutil
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions, demo_compat
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'lodgen');ASSETS=versions.assets_ref(VID);RENDERS=versions.renders_ref(VID)
from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf, Vt
def icosphere(level):
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
def rock_dense(path):
    """A lumpy rock: an icosphere with smooth pseudo random bumps, resting on its base (origin at the bottom), smooth normals, UVs, a grey colour and a material."""
    V,F=icosphere(4);rng=np.random.RandomState(7);d=np.zeros(len(V))
    for _ in range(36):
        c=rng.normal(size=3);c/=np.linalg.norm(c);w=rng.uniform(0.04,0.2);h=rng.uniform(-0.2,0.22);d+=h*np.exp(-((1-V@c)/w))
    R=1.0+d;P=V*R[:,None]*np.array([1.0,0.72,0.9]);P[:,1]-=P[:,1].min()
    st=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(st,'/RockDense');st.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(st,UsdGeom.Tokens.y)
    mesh=UsdGeom.Mesh.Define(st,'/RockDense/Mesh');mesh.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(P.astype(np.float32)));mesh.CreateFaceVertexCountsAttr([3]*len(F));mesh.CreateFaceVertexIndicesAttr(F.reshape(-1).tolist());mesh.CreateSubdivisionSchemeAttr('none')
    n=np.zeros_like(P)
    for k in range(3):np.add.at(n,F[:,k],np.cross(P[F[:,1]]-P[F[:,0]],P[F[:,2]]-P[F[:,0]]))
    n/=np.linalg.norm(n,axis=1)[:,None];mesh.CreateNormalsAttr(Vt.Vec3fArray.FromNumpy(n.astype(np.float32)));mesh.SetNormalsInterpolation('vertex')
    uv=UsdGeom.PrimvarsAPI(mesh).CreatePrimvar('st',Sdf.ValueTypeNames.TexCoord2fArray,UsdGeom.Tokens.faceVarying);uv.Set(Vt.Vec2fArray.FromNumpy(np.array([(P[i][0]*0.5+0.5,P[i][2]*0.5+0.5) for i in F.reshape(-1)],dtype=np.float32)))
    mat=UsdShade.Material.Define(st,'/RockDense/Looks/M');sh=UsdShade.Shader.Define(st,'/RockDense/Looks/M/Surface');sh.CreateIdAttr('UsdPreviewSurface');sh.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.46,0.44,0.40));sh.CreateInput('roughness',Sdf.ValueTypeNames.Float).Set(0.85)
    mat.CreateSurfaceOutput().ConnectToSource(sh.ConnectableAPI(),'surface');UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim());UsdShade.MaterialBindingAPI(mesh.GetPrim()).Bind(mat)
    st.GetRootLayer().Save()
for folder in (ROOT/'dist/test_assets',ROOT/'otls_h205/test_assets'):
    if folder.exists() and not (folder/'rock_dense.usda').exists():rock_dense(folder/'rock_dense.usda')
hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID);hou.hipFile.save(str(HIP))
hou.playbar.setFrameRange(1,120);hou.setFrame(1)
stage=hou.node('/stage')
def reference(name,path,file,source=None):
    n=stage.createNode('reference',name)
    if source:n.setInput(0,source)
    n.parm('primpath').set(path);n.parm('primpath1').set(path);n.parm('filepath1').set(file);n.parm('filerefprim1').set('defaultPrim');return n
rock=reference('reference_rock','/World/Props/RockDense',ASSETS+'/rock_dense.usda')
ground=reference('reference_ground','/World/Ground',ASSETS+'/paint_ground.usda',rock)
camera=stage.createNode('camera','render_camera');camera.setInput(0,ground)
camera.parm('primpath').set('/World/Camera');camera.parm('projection').set('perspective');camera.parm('horizontalAperture').set(36);camera.parm('focalLength').set(35);camera.parmTuple('aspectratio').set((16,9))
camera.parm('clippingRange1').set(0.01);camera.parm('clippingRange2').set(200);camera.parmTuple('t').set((0.0,3.4,12.5));camera.parm('lookatenable').set(1);camera.parmTuple('lookatposition').set((0.0,0.4,0.5))
def setup(node,out):
    node.parm('outputpath').set(out);node.parm('protos').set(1);node.parm('proto_prim1').set('/World/Props/RockDense')
    node.parm('cam_on').set(1);node.parm('cam_prim').set('/World/Camera');node.parm('cam_frustum').set(0);node.parm('cam_lod').set(1);node.parm('lod_by').set(0)
    node.parm('lodg_on').set(1);node.parm('lodg_1').set(40.0);node.parm('lodg_2').set(12.0);node.parm('lodg_3').set(3.0)
# ---- the ladder: one rock per level (a distance of 0 switches to that level at once, 1e6 never)
source=camera;ladder=[]
for k,(name,x,thresholds) in enumerate((('Hero',-3.9,(1e6,1e6,1e6)),('LOD1_40pct',-1.3,(0.0,1e6,1e6)),('LOD2_12pct',1.3,(0.0,0.0,1e6)),('Proxy_3pct',3.9,(0.0,0.0,0.0)))):
    n=stage.createNode(TYPE,'Arraytron_Ladder_%s'%name);n.setInput(0,source);setup(n,'/World/Ladder/%s'%name)
    n.parm('mode').set(0);n.parm('line_count').set(1);n.parm('bound_tx').set(x);n.parm('bound_tz').set(3.2);n.parm('proto_scale1').set(0.55)
    for parm,value in zip(('lod_d1','lod_d2','lod_d3'),thresholds):n.parm(parm).set(value)
    n.parm('scale_random_mode').set(0);n.parm('scale_random').set(0.0)
    if k==0:n.setComment('LOD GENERATOR - the ladder: the same dense rock as the hero, LOD 1 (40% of the triangles), LOD 2 (12%) and the Proxy (3%). Optimize tab: Generate LODs, the three percentages and the Minimum Triangles; no LOD prim is set in the Prototype Bank. Each ladder node is forced to one level (LOD distance 0); the field behind switches by camera distance.');n.setGenericFlag(hou.nodeFlag.DisplayComment,True)
    ladder.append(n);source=n
# ---- the field: 380 rocks on the ground, the level follows the distance to the camera
field=stage.createNode(TYPE,'Arraytron_Field');field.setInput(0,source);setup(field,'/World/Field')
field.parm('mode').set(5);field.parm('surface_prim').set('/World/Ground');field.parm('surface_count').set(380);field.parm('surface_seed').set(3);field.parm('surface_normal').set(0)
field.parm('lod_d1').set(9.0);field.parm('lod_d2').set(13.0);field.parm('lod_d3').set(17.0);field.parm('scale_random_mode').set(1);field.parm('scale_min').set(0.06);field.parm('scale_max').set(0.2);field.parm('rotation_random_mode').set(1);field.parm('yaw_random').set(180)
field.parm('pv_lod').set(1);field.parm('pv_id').set(1)
field.setComment('LOD GENERATOR - 380 rocks, the level by camera distance (LOD 1 from 9, LOD 2 from 13, Proxy from 17). primvars:arraytron_lod holds the level of every instance.');field.setGenericFlag(hou.nodeFlag.DisplayComment,True)
def intensity(light,value):light.parm('xn__inputsintensity_control_jeb').set('set');light.parm('xn__inputsintensity_i0a').set(value)
dome=stage.createNode('domelight','render_dome');dome.setInput(0,field);intensity(dome,0.7)
sun=stage.createNode('distantlight','render_sun');sun.setInput(0,dome);intensity(sun,2.4);sun.parmTuple('r').set((-45,40,0))
settings=demo_compat.karma_settings(stage,sun);settings.parm('engine').set('xpu');settings.parm('camera').set('/World/Camera');settings.parm('pathtracedsamples').set(128)
settings.parm('picture').set(f'{RENDERS}/{versions.render_name(VID,"lodgen")}.$F4.exr');settings.parm('res_mode').set('manual');settings.parm('res_mode').pressButton();demo_compat.set_resolution(settings,(960,540))
field.setDisplayFlag(True)
errors={n.name():n.errors() for n in (rock,ground,camera,field,settings,*ladder)}
rs=settings.stage();assert rs and not any(n.errors() for n in (field,settings,*ladder)),errors
tris={}
for k,name in enumerate(('Hero','LOD1_40pct','LOD2_12pct','Proxy_3pct')):
    pi=UsdGeom.PointInstancer(rs.GetPrimAtPath('/World/Ladder/%s'%name));t=pi.GetProtoIndicesAttr().Get(1);assert list(t)==[k],(name,list(t))      # hero 0, then LOD 1, LOD 2, Proxy
    target=pi.GetPrototypesRel().GetTargets()[k];mesh=[p for p in Usd.PrimRange(rs.GetPrimAtPath(target)) if p.IsA(UsdGeom.Mesh)][0];tris[name]=len(UsdGeom.Mesh(mesh).GetFaceVertexCountsAttr().Get())
assert tris['Hero']>tris['LOD1_40pct']>tris['LOD2_12pct']>tris['Proxy_3pct'],tris
pf=UsdGeom.PointInstancer(rs.GetPrimAtPath('/World/Field'));levels=np.bincount(np.array(pf.GetProtoIndicesAttr().Get(1)),minlength=4);assert levels.sum()>300 and (levels[1:]>0).any(),levels
print(field.parm('lodg_info').eval());print(tris,levels.tolist())
rs.Export(str(versions.render_usd(VID,'lodgen')))
render=stage.createNode('usdrender_rop','RENDER_DEMO_XPU');render.parm('loppath').set('../karma_xpu');render.parm('rendersettings').set('/Render/karma_xpu');render.parm('rendercommand').set('husk --engine xpu')
stage.layoutChildren();hou.hipFile.save(str(HIP));print(json.dumps({'saved':hou.hipFile.path(),'triangles':tris,'field_levels':levels.tolist()}))
