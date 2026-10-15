# Production finishing (v1.0.0): export of the final instances to a USD layer (the caching strategy: freeze a result, reference it, or hand it to the next
# department) and the readable cache overview. Appended to the PythonModule.
import os
import hou
from pxr import Sdf, Usd, UsdGeom

def export_path(asset):
    path=hou.text.expandString(asset.evalParm('export_path').strip())
    if not path:raise hou.NodeError('Export File is empty.')
    return path

def export_instances(asset,path=None):
    """Write the instancer of this node (positions, orientations, scales, ids, protoIndices, invisibleIds, primvars, and its prototypes) to a self-contained
    USD layer at `path` (default: the Export File parameter). The debug guides are left out. Returns (path, number of instances)."""
    path=path or export_path(asset);stage=asset.node('OUT_ARRAYTRON').stage()
    if stage is None:raise hou.NodeError('The node has no stage to export.')
    root=Sdf.Path(asset.evalParm('outputpath'));prim=stage.GetPrimAtPath(root)
    if not prim or not prim.IsValid():raise hou.NodeError('%s is not on the stage.'%root)
    flat=stage.Flatten();folder=os.path.dirname(path)
    if folder:os.makedirs(folder,exist_ok=True)
    layer=Sdf.Layer.CreateAnonymous('arraytron_export.usda')
    for p in root.GetPrefixes():
        if p!=root:Sdf.CreatePrimInLayer(layer,p).specifier=Sdf.SpecifierDef;layer.GetPrimAtPath(p).typeName='Xform'
    Sdf.CopySpec(flat,root,layer,root)
    debug=root.AppendChild('Debug')
    if layer.GetPrimAtPath(debug):
        parent=layer.GetPrimAtPath(root);del parent.nameChildren['Debug']
    layer.defaultPrim=root.GetPrefixes()[0].name;layer.customLayerData={'arraytron:exported':True,'arraytron:type':asset.type().name()}
    up=UsdGeom.GetStageUpAxis(stage);layer.comment='Arraytron export of %s'%asset.path()
    layer.Export(path);out=Usd.Stage.Open(path);UsdGeom.SetStageUpAxis(out,up);UsdGeom.SetStageMetersPerUnit(out,UsdGeom.GetStageMetersPerUnit(stage));out.GetRootLayer().Save()
    pi=UsdGeom.PointInstancer(out.GetPrimAtPath(root));count=len(pi.GetPositionsAttr().Get(hou.frame()) or pi.GetPositionsAttr().Get() or [])
    return path,count

def cache_overview(asset):
    """Read-only text: what is cached or stored on this node and where."""
    lines=[]
    if asset.parm('phys_on') is not None:
        lines.append('Physics Settle: %s'%(asset.evalParm('phys_status') if asset.parm('phys_status') is not None else 'n/a'))
    if asset.parm('paint_data') is not None:
        n=len(paint_decode(asset.evalParm('paint_data'))['pts']) if asset.evalParm('paint_data') else 0;lines.append('Painted points stored in the node: %d'%n)
    if asset.parm('overrides') is not None:lines.append('Override rows stored in the node: %d'%asset.evalParm('overrides'))
    lines.append('Export File: %s'%asset.evalParm('export_path'))
    return '\n'.join(lines)
