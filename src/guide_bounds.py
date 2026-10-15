# Embedded in a Python LOP. Authors a guide-purpose preview of the Line/Area bounds
# in the distribution's local space, so the Bounds Transform moves it with the instances.
# Guides never render in Karma; point generation itself stays in VEX.
import hou
from pxr import Gf, Sdf, UsdGeom, Vt
node=hou.pwd()
asset=node.parent()
stage=node.editableStage()
root=Sdf.Path(asset.evalParm('outputpath'))
group=root.AppendChild('Bounds_Guide')
if not asset.evalParm('show_bounds'):
    existing=stage.GetPrimAtPath(group)
    if existing:
        existing.SetActive(False)
else:
    line=asset.evalParm('mode')==0
    segments=[]
    if line:
        axis=asset.evalParm('line_axis')
        length=max(0.0,asset.evalParm('line_length'))
        count=max(1,asset.evalParm('line_count'))
        if axis<3:
            direction=Gf.Vec3d(0,0,0);direction[axis]=1
        else:
            direction=Gf.Vec3d(*asset.evalParmTuple('line_direction'))
            direction=direction.GetNormalized() if direction.GetLength()>1e-6 else Gf.Vec3d(1,0,0)
        reference=Gf.Vec3d(0,1,0) if abs(direction[1])<.99 else Gf.Vec3d(0,0,1)
        side=Gf.Cross(direction,reference).GetNormalized()
        size=max(length*.05,.15)
        if count>1:
            start=direction*(-length*.5) if asset.evalParm('line_center') else Gf.Vec3d(0,0,0)
            end=start+direction*length
            segments.append([start,end])
            head=min(size*2,length*.25)
            segments.append([end-direction*head+side*head*.5,end,end-direction*head-side*head*.5])
            ticks=min(size*.5,length/count*.5) if length>0 else size*.5
            if count<=256:
                for i in range(count):
                    p=start+direction*(length*i/(count-1))
                    segments.append([p-side*ticks,p+side*ticks])
            else:
                for p in (start,end):
                    segments.append([p-side*ticks,p+side*ticks])
        else:
            segments.append([Gf.Vec3d(-size*.5,0,0),Gf.Vec3d(size*.5,0,0)])
            segments.append([Gf.Vec3d(0,0,-size*.5),Gf.Vec3d(0,0,size*.5)])
        color=Gf.Vec3f(1,.72,.1)
    else:
        hx=max(0.0,asset.evalParm('area_sizex'))*.5
        hz=max(0.0,asset.evalParm('area_sizez'))*.5
        segments.append([Gf.Vec3d(-hx,0,-hz),Gf.Vec3d(hx,0,-hz),Gf.Vec3d(hx,0,hz),Gf.Vec3d(-hx,0,hz),Gf.Vec3d(-hx,0,-hz)])
        size=max(min(hx,hz)*.1,.15)
        color=Gf.Vec3f(.2,.85,1)
    pivot=Gf.Vec3d(*asset.evalParmTuple('bound_p'))
    pivot_marker=[[pivot-Gf.Vec3d(size,0,0),pivot+Gf.Vec3d(size,0,0)],
                  [pivot-Gf.Vec3d(0,size,0),pivot+Gf.Vec3d(0,size,0)],
                  [pivot-Gf.Vec3d(0,0,size),pivot+Gf.Vec3d(0,0,size)]]
    top=UsdGeom.Xform.Define(stage,group)
    top.GetPurposeAttr().Set(UsdGeom.Tokens.guide)
    top.GetPrim().SetActive(True)
    def curves(name,paths,rgb,width):
        c=UsdGeom.BasisCurves.Define(stage,group.AppendChild(name))
        c.CreateTypeAttr(UsdGeom.Tokens.linear);c.CreateWrapAttr(UsdGeom.Tokens.nonperiodic)
        c.CreateCurveVertexCountsAttr(Vt.IntArray([len(p) for p in paths]))
        c.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(v) for p in paths for v in p]))
        c.CreateWidthsAttr(Vt.FloatArray([width]));c.SetWidthsInterpolation(UsdGeom.Tokens.constant)
        c.GetDisplayColorPrimvar().Set(Vt.Vec3fArray([rgb]))
        c.GetPurposeAttr().Set(UsdGeom.Tokens.guide)
    curves('Bounds',segments,color,size*.04)
    curves('Pivot',pivot_marker,Gf.Vec3f(1,.2,.8),size*.04)
