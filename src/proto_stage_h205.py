# Embedded in a Python LOP (PROTO_STAGE, Houdini 20.5 / 21 build only): the second input of the instancer. It adds one top-level prim per
# prototype that specializes the bank prim, because the older instancer copies a prototype to <output>/Prototypes/<its path>; a top-level
# prim therefore lands at <output>/Prototypes/<name> exactly like the Houdini 22 build. (Specialize and not Reference: no relocation warning. The prim has no type of its own, so a gprim source, a Cube for example, keeps its type.)
import hou
from pxr import Sdf
node=hou.pwd()
asset=node.parent()
module=asset.hdaModule()
stage=node.editableStage()
for source,flat in zip(module.pattern(asset).split(),module.flat_paths(asset)):
    if source==flat:continue
    if stage.GetPrimAtPath(flat):
        raise hou.NodeError('The Houdini 20.5 / 21 build needs the top-level name %s for the prototype %s, but a prim already exists there: rename or move that prim.'%(flat,source))
    stage.DefinePrim(Sdf.Path(flat)).GetSpecializes().AddSpecialize(Sdf.Path(source))
