# Embedded in a Python LOP (LOD_GENERATOR), between SOURCE_RESOLVER and USD_COMPILER. With Generate LODs off this node does not touch the stage and does not depend on time.
# With it on, reduced copies of the prototypes that have no LOD prim of their own are written next to the other prims (see src/arraytron_lodgen.py); the heroes are not changed.
import hou
node=hou.pwd()
asset=node.parent()
if asset.evalParm('lodg_on'):
    asset.hdaModule().lodgen_author(asset,node.editableStage())
