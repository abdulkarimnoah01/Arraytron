
# The Mode Palette installer: the panel code is the HDA section ModePalette.py (src/arraytron_modepanel.py with the icons filled in). install_parm_panel registers it as a Python Panel that
# Houdini shows in the Parameters pane for this node type (<showInParametersPane>), like the Paint Instances node does: the mode cells on top, the node's own parameters below.
# It runs from the OnCreated / OnLoaded scripts. Set ARRAYTRON_NO_PARM_PANEL=1 to keep Houdini's plain parameter dialog. Nothing here touches the points or the stage.
_PARM_PANEL_DONE = set()

def install_parm_panel(node_type):
    import os, tempfile
    if os.environ.get('ARRAYTRON_NO_PARM_PANEL') or not hou.isUIAvailable():
        return False
    name = node_type.nameWithCategory()
    if name in _PARM_PANEL_DONE:
        return True
    section = node_type.definition().sections().get('ModePalette.py')
    if section is None:
        return False
    tag = ''.join(ch if ch.isalnum() else '_' for ch in node_type.name())
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<pythonPanelDocument>\n  <interface name="%s" label="Arraytron Parameters" icon="MISC_python" showNetworkNavigationBar="false" help_url="">\n'
           '    <script><![CDATA[%s]]></script>\n    <showInParametersPane optype="%s"/>\n  </interface>\n</pythonPanelDocument>\n') % ('arraytron_parms_' + tag, section.contents(), name)
    path = os.path.join(tempfile.gettempdir(), 'arraytron_parms_%s.pypanel' % tag)
    with open(path, 'w', encoding='utf8') as handle:
        handle.write(xml)
    hou.pypanel.installFile(path)
    _PARM_PANEL_DONE.add(name)
    return True
