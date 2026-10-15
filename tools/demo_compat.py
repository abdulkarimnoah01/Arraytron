"""Houdini 22 / 20.5 differences the demo builders share. Houdini 22 has the karmarendersettings LOP (a resolution tuple); Houdini 20.5 / 21 have
karmarenderproperties with the same engine / camera / samples / picture parameters but resolutionx / resolutiony."""
import hou
def karma_settings(stage,source,name='karma_xpu'):
    """Karma render settings LOP wired after source, authoring /Render/<name> in both Houdini generations."""
    modern=hou.nodeType(hou.lopNodeTypeCategory(),'karmarendersettings') is not None
    node=stage.createNode('karmarendersettings' if modern else 'karmarenderproperties',name);node.setInput(0,source)
    if not modern:node.parm('primpath').set('/Render/'+name)
    return node
def set_resolution(node,size):
    if node.parmTuple('resolution') is not None:node.parmTuple('resolution').set(size)
    else:node.parm('resolutionx').set(size[0]);node.parm('resolutiony').set(size[1])
