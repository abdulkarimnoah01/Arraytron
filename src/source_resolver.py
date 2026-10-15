# Embedded in a Python LOP: SOURCE_RESOLVER. Validates the Prototype Bank and stages USD File entries as hidden
# references next to the output prim. Never creates points or geometry. (Input Connection prims arrive through the
# Merge LOP and SOP Geometry entries through the SOP Import stagers upstream of this node.)
import hou
from pxr import Sdf, UsdGeom
node=hou.pwd()
asset=node.parent()
module=asset.hdaModule()
entries=module.resolve(asset)
dest=Sdf.Path(asset.evalParm('outputpath'))
if not Sdf.Path.IsValidPathString(asset.evalParm('outputpath')) or not dest.IsAbsolutePath() or not dest.IsPrimPath() or dest==Sdf.Path.absoluteRootPath:
    raise hou.NodeError('outputpath must be an absolute USD prim path.')
if dest.ContainsPrimVariantSelection():
    raise hou.NodeError('outputpath must not contain a variant selection.')
stage=node.editableStage()
for e in entries:
    path=Sdf.Path(e['path'])
    if not Sdf.Path.IsValidPathString(e['path']) or not path.IsAbsolutePath() or not path.IsPrimPath() or path==Sdf.Path.absoluteRootPath or path.ContainsPrimVariantSelection():
        raise hou.NodeError('Prototype %d: %s is not an absolute USD prim path.'%(e['row'],e['path']))
    if dest.HasPrefix(path) or path.HasPrefix(dest):
        raise hou.NodeError('Prototype %d: the Output Prim Path must be outside the prototype hierarchy.'%e['row'])
    if e['type']==module.TYPE_FILE:
        layer=Sdf.Layer.FindOrOpen(e['file'])
        if layer is None:raise hou.NodeError('Prototype %d: cannot open the USD file %s.'%(e['row'],e['file']))
        if e['fileprim']:
            if not layer.GetPrimAtPath(e['fileprim']):raise hou.NodeError('Prototype %d: %s does not exist in %s.'%(e['row'],e['fileprim'],e['file']))
        elif not layer.defaultPrim:
            raise hou.NodeError('Prototype %d: %s has no default prim; type its Prim Path.'%(e['row'],e['file']))
        stage.DefinePrim(Sdf.Path(module.sources_root(asset)),'Scope')
        prim=stage.DefinePrim(path,'Xform')
        refs=prim.GetReferences();refs.ClearReferences()
        refs.AddReference(e['file'],Sdf.Path(e['fileprim'])) if e['fileprim'] else refs.AddReference(e['file'])
    prim=stage.GetPrimAtPath(path)
    if not prim or not prim.IsActive():
        raise hou.NodeError('Prototype %d: %s does not exist or is inactive in the incoming stage.'%(e['row'],e['path']))
existing=stage.GetPrimAtPath(dest)
if existing and not existing.IsA(UsdGeom.PointInstancer):
    raise hou.NodeError('Output Prim Path already exists and is not a PointInstancer.')
