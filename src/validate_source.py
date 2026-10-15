# Embedded in a Python LOP. Validation only; all point generation is VEX.
import hou
from pxr import Sdf, UsdGeom
node=hou.pwd()
asset=node.parent()
paths=[]
for name in ('prototype','outputpath'):
    value=asset.evalParm(name)
    if not Sdf.Path.IsValidPathString(value):
        raise hou.NodeError(name+' must be an absolute USD prim path.')
    path=Sdf.Path(value)
    if not path.IsAbsolutePath() or not path.IsPrimPath() or path==Sdf.Path.absoluteRootPath:
        raise hou.NodeError(name+' must be an absolute USD prim path.')
    if path.ContainsPrimVariantSelection():
        raise hou.NodeError(name+' must not contain a variant selection.')
    paths.append(path)
source,dest=paths
if dest.HasPrefix(source) or source.HasPrefix(dest):
    raise hou.NodeError('Output Prim Path must be outside the prototype hierarchy.')
stage=node.inputs()[0].stage()
if not stage or not stage.GetPrimAtPath(source) or not stage.GetPrimAtPath(source).IsActive():
    raise hou.NodeError('Prototype Prim does not exist or is inactive in the incoming stage.')
existing=stage.GetPrimAtPath(dest)
if existing and not existing.IsA(UsdGeom.PointInstancer):
    raise hou.NodeError('Output Prim Path already exists and is not a PointInstancer.')
# Establish a pass-through edit layer only after the input-stage reads.
stage=None
node.editableStage()
