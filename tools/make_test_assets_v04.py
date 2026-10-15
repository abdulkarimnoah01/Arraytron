"""Write dist/test_assets/stone.usda, ballast_ground.usda and track.usda for the Physics Settle demo and tests: hython tools/make_test_assets_v04.py
An angular gravel stone: the convex hull of 22 random points on a squashed ellipsoid (about 6 x 4 x 5 cm, 20-odd flat faces), with the origin
at the BOTTOM of the stone rather than its centre, so the prototype pivot is deliberately off-centre."""
from pathlib import Path
import sys
import numpy as np
from pxr import Usd, UsdGeom, UsdShade, Gf, Sdf, Kind, Vt
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import arraytron_physics as P

def stone_mesh(seed=3):
    rng=np.random.RandomState(seed)
    d=rng.normal(size=(22,3));d/=np.linalg.norm(d,axis=1)[:,None]
    pts=d*np.array([0.030,0.018,0.024])*rng.uniform(0.85,1.0,size=(22,1))
    verts,faces=P.quickhull(pts)
    verts=verts-np.array([0.0,verts[:,1].min(),0.0])           # origin at the bottom of the stone
    return verts,faces

def write(path,seed=3):
    verts,faces=stone_mesh(seed)
    s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/Stone')
    s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y);UsdGeom.SetStageMetersPerUnit(s,1)
    Usd.ModelAPI(root).SetKind(Kind.Tokens.component)
    m=UsdShade.Material.Define(s,'/Stone/Looks/Granite');sh=UsdShade.Shader.Define(s,'/Stone/Looks/Granite/Surface')
    sh.CreateIdAttr('UsdPreviewSurface');sh.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(.30,.285,.265))
    sh.CreateInput('roughness',Sdf.ValueTypeNames.Float).Set(.8);m.CreateSurfaceOutput().ConnectToSource(sh.ConnectableAPI(),'surface')
    mesh=UsdGeom.Mesh.Define(s,'/Stone/Shape')
    mesh.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*map(float,v)) for v in verts]))
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray([3]*len(faces)));mesh.CreateFaceVertexIndicesAttr(Vt.IntArray([int(i) for i in faces.ravel()]))
    mesh.CreateSubdivisionSchemeAttr('none');mesh.CreateDoubleSidedAttr(True)
    UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(m);s.GetRootLayer().Save()
    return verts,faces

def material(s,path,color,roughness):
    m=UsdShade.Material.Define(s,path);sh=UsdShade.Shader.Define(s,path+'/Surface');sh.CreateIdAttr('UsdPreviewSurface')
    sh.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color));sh.CreateInput('roughness',Sdf.ValueTypeNames.Float).Set(roughness)
    m.CreateSurfaceOutput().ConnectToSource(sh.ConnectableAPI(),'surface');return m

def cube(s,path,size,center,mat):
    c=UsdGeom.Cube.Define(s,path);c.CreateSizeAttr(1.0);x=UsdGeom.Xformable(c)
    x.AddTranslateOp().Set(Gf.Vec3d(*center));x.AddScaleOp().Set(Gf.Vec3f(*size));UsdShade.MaterialBindingAPI.Apply(c.GetPrim()).Bind(mat);return c

def write_ground(path):
    """Soil bed whose top face is exactly y = 0, the default Ground Height of Physics Settle."""
    s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/Ground');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    cube(s,'/Ground/Bed',(3.0,0.2,3.0),(0,-0.1,0),material(s,'/Ground/Looks/Soil',(0.085,0.07,0.055),0.95));s.GetRootLayer().Save()

def write_track(path):
    """Three concrete sleepers (z = -0.45, 0, 0.45; 0.9 x 0.08 x 0.2 m) and two rails on them: static colliders for the ballast demo."""
    s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/Track');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    concrete=material(s,'/Track/Looks/Concrete',(0.50,0.47,0.42),0.9);steel=material(s,'/Track/Looks/Steel',(0.30,0.20,0.15),0.45)
    for k,z in enumerate((-0.45,0.0,0.45),1):cube(s,'/Track/Sleeper%d'%k,(0.9,0.08,0.2),(0,0.04,z),concrete)
    for name,x in (('RailL',-0.3),('RailR',0.3)):cube(s,'/Track/'+name,(0.07,0.07,1.8),(x,0.115,0),steel)
    s.GetRootLayer().Save()

def write_box(path):
    """An open wooden box, 0.5 x 0.5 m inside and 0.4 m tall (floor slab top at y = 0.04), five cubes: static colliders for the 'stones in a box' demo."""
    s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/Box');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    wood=material(s,'/Box/Looks/Wood',(0.42,0.27,0.14),0.7)
    cube(s,'/Box/Floor',(0.56,0.04,0.56),(0,0.02,0),wood)
    for name,x in (('WallW',-0.265),('WallE',0.265)):cube(s,'/Box/'+name,(0.03,0.4,0.56),(x,0.2,0),wood)
    for name,z in (('WallN',-0.265),('WallS',0.265)):cube(s,'/Box/'+name,(0.5,0.4,0.03),(0,0.2,z),wood)
    s.GetRootLayer().Save()

if __name__=='__main__':
    out=ROOT/'dist/test_assets/stone.usda';v,f=write(out)
    write_ground(ROOT/'dist/test_assets/ballast_ground.usda');write_track(ROOT/'dist/test_assets/track.usda');write_box(ROOT/'dist/test_assets/box.usda')
    print('wrote',out,len(v),'points',len(f),'triangles; height %.4f m'%v[:,1].max(),'+ ballast_ground.usda, track.usda, box.usda')
