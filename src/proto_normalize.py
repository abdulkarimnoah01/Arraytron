# Embedded in a Python LOP (PROTO_NORMALIZE, Houdini 20.5 / 21 build only), right after the instancer: the older instancer sorts the prototype
# list, so the targets are put back in bank order (hero prototypes, then LOD / proxy prims) and protoIndices follow, and the source prims are
# hidden like the Houdini 22 pointinstancer does. Afterwards index k is bank ordinal k, as the rest of Arraytron and its tests expect.
import hou
from pxr import Sdf, Usd, UsdGeom, Vt
node=hou.pwd()
asset=node.parent()
module=asset.hdaModule()
stage=node.editableStage()
out=asset.evalParm('outputpath').rstrip('/')
prim=stage.GetPrimAtPath(out)
if prim and prim.IsValid() and prim.IsA(UsdGeom.PointInstancer):
    pi=UsdGeom.PointInstancer(prim)
    sources=module.pattern(asset).split()
    want=[out+'/Prototypes/'+flat.lstrip('/') for flat in module.flat_paths(asset)]
    have=[t.pathString for t in pi.GetPrototypesRel().GetTargets()]
    if have!=want and sorted(have)==sorted(want):
        where={p:i for i,p in enumerate(want)};perm=[where[p] for p in have]          # old index -> bank ordinal
        pi.GetPrototypesRel().SetTargets([Sdf.Path(p) for p in want])
        attr=pi.GetProtoIndicesAttr()
        times=attr.GetTimeSamples() if attr.GetNumTimeSamples() else [None]
        for t in times:
            values=attr.Get() if t is None else attr.Get(Usd.TimeCode(t))
            if values is None:continue
            fixed=Vt.IntArray([perm[int(i)] for i in values])
            attr.Set(fixed) if t is None else attr.Set(fixed,Usd.TimeCode(t))
    area=stage.GetPrimAtPath(out+'/Prototypes')
    if area and area.IsValid():area.SetChildrenReorder([flat.lstrip('/') for flat in module.flat_paths(asset)])          # child prims in bank order, as Houdini 22 lists them
    for source in sources:
        src=stage.GetPrimAtPath(source)
        if src and src.IsValid():UsdGeom.Imageable(src).CreateVisibilityAttr().Set(UsdGeom.Tokens.invisible)
