"""Write two more test USD prototypes next to crate.usda so the Prototype Bank has distinct shapes to select between.
Run with hython (or any Python with pxr): barrel.usda (default prim /Barrel), rock.usda (default prim /Rock)."""
from pathlib import Path
from pxr import Usd, UsdGeom, UsdShade, Gf, Sdf, Kind
ROOT=Path(__file__).resolve().parents[1]
assets=ROOT/'dist/test_assets';assets.mkdir(exist_ok=True)
def material(stage,path,color,roughness=.5):
    m=UsdShade.Material.Define(stage,path);shader=UsdShade.Shader.Define(stage,path+'/Surface')
    shader.CreateIdAttr('UsdPreviewSurface');shader.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color))
    shader.CreateInput('roughness',Sdf.ValueTypeNames.Float).Set(roughness)
    m.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(),'surface');return m
def new(name):
    s=Usd.Stage.CreateNew(str(assets/f'{name.lower()}.usda'));root=UsdGeom.Xform.Define(s,'/'+name)
    s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y);UsdGeom.SetStageMetersPerUnit(s,1)
    Usd.ModelAPI(root).SetKind(Kind.Tokens.component);return s
# Barrel: a tall green cylinder with two bands, origin at its base.
s=new('Barrel');body=material(s,'/Barrel/Looks/Body',(.12,.38,.2));band=material(s,'/Barrel/Looks/Band',(.75,.75,.78),.3)
c=UsdGeom.Cylinder.Define(s,'/Barrel/Body');c.CreateRadiusAttr(.3);c.CreateHeightAttr(.8);c.CreateAxisAttr('Y')
UsdGeom.Xformable(c).AddTranslateOp().Set(Gf.Vec3d(0,.4,0));UsdShade.MaterialBindingAPI.Apply(c.GetPrim()).Bind(body)
for name,y in (('BandLow',.18),('BandHigh',.62)):
    b=UsdGeom.Cylinder.Define(s,'/Barrel/'+name);b.CreateRadiusAttr(.32);b.CreateHeightAttr(.06);b.CreateAxisAttr('Y')
    UsdGeom.Xformable(b).AddTranslateOp().Set(Gf.Vec3d(0,y,0));UsdShade.MaterialBindingAPI.Apply(b.GetPrim()).Bind(band)
s.GetRootLayer().Save()
# Rock: a squashed grey sphere sitting on the ground.
s=new('Rock');stone=material(s,'/Rock/Looks/Stone',(.45,.45,.42),.85)
r=UsdGeom.Sphere.Define(s,'/Rock/Stone');r.CreateRadiusAttr(.35)
x=UsdGeom.Xformable(r);x.AddTranslateOp().Set(Gf.Vec3d(0,.2,0));x.AddScaleOp().Set(Gf.Vec3f(1.2,.6,.9))
UsdShade.MaterialBindingAPI.Apply(r.GetPrim()).Bind(stone);s.GetRootLayer().Save()
print('wrote',sorted(p.name for p in assets.iterdir()))
