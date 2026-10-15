"""Write dist/test_assets/curve_s.usda (an S shaped cubic bezier curve) and terrain.usda (a bumpy 6 x 6 m height-field mesh with a steep bank)
for the Curve (v0.4.5) and Surface Scatter (v0.4.6) demos: hython tools/make_test_assets_v045.py"""
from pathlib import Path
import math
import numpy as np
from pxr import Usd, UsdGeom, UsdShade, Gf, Sdf, Vt
ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'dist/test_assets'

def material(s,path,color,roughness):
    m=UsdShade.Material.Define(s,path);sh=UsdShade.Shader.Define(s,path+'/Surface');sh.CreateIdAttr('UsdPreviewSurface')
    sh.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*color));sh.CreateInput('roughness',Sdf.ValueTypeNames.Float).Set(roughness)
    m.CreateSurfaceOutput().ConnectToSource(sh.ConnectableAPI(),'surface');return m

def write_curve(path):
    """Two cubic bezier segments (7 control points) in the XZ plane: an S bend 6 m long, a little above the ground."""
    s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/CurveS');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    pts=[(-3,0.05,-1),(-2,0.05,-3),(-1,0.05,-3),(0,0.05,-1),(1,0.05,1),(2,0.05,1),(3,0.05,-1)]
    c=UsdGeom.BasisCurves.Define(s,'/CurveS/Path');c.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*p) for p in pts]));c.CreateCurveVertexCountsAttr(Vt.IntArray([7]))
    c.CreateTypeAttr('cubic');c.CreateBasisAttr('bezier');c.CreateWrapAttr('nonperiodic');c.CreateWidthsAttr(Vt.FloatArray([0.03]));c.SetWidthsInterpolation(UsdGeom.Tokens.constant)
    s.GetRootLayer().Save()

def height(x,z):
    return 0.45*math.sin(0.9*x)*math.cos(0.7*z)+0.2*math.sin(2.1*x+1.3*z)+0.35*max(0.0,x-1.8)**2

def write_terrain(path,n=60,size=6.0):
    s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/Terrain');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    xs=np.linspace(-size/2,size/2,n+1);pts=[(float(x),float(height(x,z)),float(z)) for z in xs for x in xs]
    counts=[4]*(n*n);idx=[]
    for j in range(n):
        for i in range(n):
            a=j*(n+1)+i;idx+=[a,a+n+1,a+n+2,a+1]                  # counter-clockwise seen from +Y: normals point up
    m=UsdGeom.Mesh.Define(s,'/Terrain/Ground');m.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(*p) for p in pts]));m.CreateFaceVertexCountsAttr(Vt.IntArray(counts));m.CreateFaceVertexIndicesAttr(Vt.IntArray(idx))
    m.CreateSubdivisionSchemeAttr('none');UsdShade.MaterialBindingAPI.Apply(m.GetPrim()).Bind(material(s,'/Terrain/Looks/Soil',(0.16,0.13,0.10),0.95));s.GetRootLayer().Save()

def write_fir(path):
    """A little fir tree, origin at the BASE of the trunk (instances grow about their origin): a trunk cylinder and two green cones, about 0.55 m tall."""
    s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/Fir');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    bark=material(s,'/Fir/Looks/Bark',(0.25,0.15,0.08),0.9);leaf=material(s,'/Fir/Looks/Needles',(0.06,0.32,0.12),0.8)
    def prim(kind,name,radius,height,y,mat):
        c=kind.Define(s,'/Fir/'+name);c.CreateRadiusAttr(radius);c.CreateHeightAttr(height);c.CreateAxisAttr('Y');UsdGeom.Xformable(c).AddTranslateOp().Set(Gf.Vec3d(0,y,0));UsdShade.MaterialBindingAPI.Apply(c.GetPrim()).Bind(mat)
    prim(UsdGeom.Cylinder,'Trunk',0.025,0.16,0.08,bark);prim(UsdGeom.Cone,'Lower',0.15,0.30,0.30,leaf);prim(UsdGeom.Cone,'Upper',0.10,0.25,0.48,leaf)
    s.GetRootLayer().Save()

def write_mask_blob(path,n=128):
    """A soft white blob on black (a radial falloff, 128 x 128 float EXR): a Top-view mask for the 6 x 6 m terrain."""
    import OpenImageIO as oiio
    y,x=np.mgrid[0:n,0:n];r=np.hypot((x+0.5)/n-0.5,(y+0.5)/n-0.5)*2;v=np.clip(1-r,0,1);v=v*v*(3-2*v)
    arr=np.repeat(v[:,:,None],3,axis=2).astype(np.float32);buf=oiio.ImageBuf(oiio.ImageSpec(n,n,3,oiio.FLOAT));buf.set_pixels(oiio.ROI(0,n,0,n,0,1,0,3),arr);assert buf.write(str(path)),buf.geterror()

if __name__=='__main__':
    write_curve(ASSETS/'curve_s.usda');write_terrain(ASSETS/'terrain.usda');write_mask_blob(ASSETS/'mask_blob.exr');write_fir(ASSETS/'fir.usda');print('wrote curve_s.usda, terrain.usda, mask_blob.exr in',ASSETS)
