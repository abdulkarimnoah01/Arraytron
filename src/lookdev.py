# Embedded in the Python LOP `lookdev` (v1.35.0), after the camera optimisation: the Lookdev tab (materials and per-instance variation). See src/arraytron_lookdev.py.
import hou
node=hou.pwd()
asset=node.parent()
stage=node.editableStage()
text=asset.hdaModule().lookdev_apply(stage,asset)
node.setUserData('arraytron_lookdev',text)
