"""Build Arraytron Stamp 0.9.3, the light one: hython tools/build_stamp_light.py   (hython 22 or 20.5)
A LOP HDA of its own (arraytron::stamp::0.9.3), not the Arraytron network: ONE Python LOP inside, the stamps in ONE text parameter, a small viewer state and the Stamp Gallery panel.
Writes dist/Arraytron_Stamp_v0.9.3.hda, or otls_h205/Arraytron_Stamp_v0.9.3_H205.hda with hython 20.5."""
import sys, json, re
from pathlib import Path
import hou
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
STAMP_VERSION='0.9.3';TYPE='arraytron::stamp::%s'%STAMP_VERSION;STATE='arraytron_stamp_'+STAMP_VERSION.replace('.','')
H205=versions.is_h205()
HDA=ROOT/('otls_h205' if H205 else 'dist')/('Arraytron_Stamp_v%s%s.hda'%(STAMP_VERSION,'_H205' if H205 else ''))

def callback(template,code):
    template.setScriptCallback(code);template.setScriptCallbackLanguage(hou.scriptLanguage.Python);return template

def bank():
    """The Prototype Bank: the rows of Arraytron's bank (same parameter names, so the Asset Library adds to it) without the SOP Geometry type and the LOD prims."""
    tags={'script_action':'import soputils\nkwargs[\'node\'] = hou.pwd()\nkwargs[\'parms\'] = kwargs[\'parmtuple\']\nkwargs[\'script_parm\'] = kwargs[\'parmtuple\'][0]\nsoputils.selectPrimsFromParm(kwargs)','script_action_help':'Select a prim in the Scene Viewer.','script_action_icon':'BUTTONS_reselect'}
    def hide(template,cond):
        template.setConditional(hou.parmCondType.HideWhen,cond);return template
    entry=(
        hou.ToggleParmTemplate('proto_on#','Enable',default_value=True,help='Disabled entries are ignored: not instanced, not drawn at random.'),
        hou.MenuParmTemplate('proto_type#','Source Type',('0','1','2','3'),('Prim Path','Input Connection','USD File','Group Children'),help='Where this prototype comes from. Prim Path: a prim of the first input (empty: a built-in sphere). Input Connection: wire any LOP into Prototype Input 2 / 3 / 4. USD File: a USD file on disk, staged hidden. Group Children: every child prim of a group becomes its own prototype (Prim Path /Group/* or /Group; a name pattern such as /Group/rock* picks some of them); a stamp takes one of them.'),
        hide(hou.StringParmTemplate('proto_prim#','Prim Path',1,default_value=('',),tags=tags,help='One exact prim of the incoming stage (the first input and the Prototype Inputs, merged). Empty: the built-in sphere. For Group Children: the group (/Group, or /Group/*), or a name pattern inside it (/Group/rock*).'),'{ proto_type# != 0 proto_type# != 3 }'),
        hide(hou.MenuParmTemplate('proto_input#','Input',('0','1','2'),('Input 2','Input 3','Input 4'),help='Which Prototype Input to take the prototype from.'),'{ proto_type# != 1 }'),
        hide(hou.StringParmTemplate('proto_inprim#','Prim Path (optional)',1,default_value=('',),tags=tags,help='Leave empty to pick the prim automatically: the only top-level prim, followed down single-child chains to the first component or geometry.'),'{ proto_type# != 1 }'),
        hide(hou.StringParmTemplate('proto_file#','USD File',1,default_value=('',),string_type=hou.stringParmType.FileReference,tags={'filechooser_pattern':'*.usd,*.usda,*.usdc,*.usdz','filechooser_mode':'read'},help='USD file to reference as the prototype.'),'{ proto_type# != 2 }'),
        hide(hou.StringParmTemplate('proto_fileprim#','Prim Path (optional)',1,default_value=('',),help='Prim inside the file. Empty uses the file default prim.'),'{ proto_type# != 2 }'),
        hou.FloatParmTemplate('proto_weight#','Weight',1,default_value=(1,),min=0,max=10,min_is_strict=True,help='Relative weight: Random Prototype draws this row by it (1 and 2 mean the same as 10 and 20); 0 never draws it.'),
        hou.FloatParmTemplate('proto_scale#','Scale',1,default_value=(1,),min=0.0001,max=10,min_is_strict=True,help='Size multiplier for this prototype only, on top of the stamp\'s own scale.'),
        hou.FloatParmTemplate('proto_scalevar#','Scale Random',1,default_value=(0,),min=0,max=0.99,min_is_strict=True,max_is_strict=True,help='Extra random size variation for this prototype only, as a fraction: scale x (1 +/- amount).'),
        hou.FloatParmTemplate('proto_rot#','Rotation Offset (deg)',3,default_value=(0,0,0),min=-180,max=180,help='Turns this prototype itself (XYZ Euler degrees) FIRST, before the stamp\'s rotation. Use it to correct a model authored facing the wrong way.'))
    return hou.FolderParmTemplate('protos','Prototype Bank',folder_type=hou.folderType.MultiparmBlock,default_value=1,parm_templates=entry)

def parms():
    """Brush / Edit / Options tabs like the Layout tool's pane; Randomization / Asset / Placement / Paint / Group inside Brush. the parameter mode1 (the tab set of the first folder, mode) holds the current tab: 0 Brush, 1 Edit, 2 Options (Edit is the Edit mode of the tool)."""
    f=hou.FloatParmTemplate;i=hou.IntParmTemplate;t=hou.ToggleParmTemplate;s=hou.StringParmTemplate;b=hou.ButtonParmTemplate
    def hidden(template):
        template.hide(True);return template
    def tab(name,label,templates):
        return hou.FolderParmTemplate(name,label,folder_type=hou.folderType.Tabs,parm_templates=tuple(templates))
    def call(name):
        return "m=kwargs['node'].hdaModule();m.%s(kwargs['node'])"%name
    info=s('selinfo','Selection',1,default_value=('',),help='Read only. How many stamps are selected.');info.setDefaultExpression(('hou.pwd().hdaModule().stamp_selection_info(hou.pwd())',));info.setDefaultExpressionLanguage((hou.scriptLanguage.Python,));info.setConditional(hou.parmCondType.DisableWhen,'{ seed >= 0 }')
    panestatus=s('panestatus','Parameters Pane',1,default_value=('',),help='Read only. Whether the Stamp\'s own Parameters pane (cards, stamps table, Asset Library) is loaded; if it is not, this plain dialog is what you see.');panestatus.setDefaultExpression(('hou.pwd().hdaModule().stamp_pane_text(hou.pwd())',));panestatus.setDefaultExpressionLanguage((hou.scriptLanguage.Python,));panestatus.setConditional(hou.parmCondType.DisableWhen,'{ seed >= 0 }')
    transform=[f('align','Align To Surface',1,default_value=(1.0,),min=0,max=1,help='1 (the default) turns the up axis (+Y) of every stamp to the up of the surface where it lands (a smooth normal, see Smooth Normals); 0 keeps stamps upright in the world; in between blends.'),
               f('offset','Offset',1,default_value=(0.0,),min=-10,max=10,help='Moves a new stamp along the surface normal.'),
               f('scale','Uniform Scale',1,default_value=(1.0,),min=0.0001,max=100,help='The scale of every new stamp, before the random scale below (Shift + mousewheel, [ and ] in the viewport).'),
               f('scalerange','Random Scale Min / Max',2,default_value=(1.0,1.0),min=0.0001,max=1000,help='Every stamp is scaled by a random number in this range on top of Uniform Scale: 0.8 / 1.3 makes each stamp 80 % to 130 % of it (the same seed gives the same stamps).'),
               f('yaw','Rotate',1,default_value=(0.0,),min=-360,max=360,help='The turn of every new stamp about its up axis, degrees, before the random turn below (Ctrl + mousewheel, or , and . in the viewport).'),
               f('yawrand','Random Rotate (+/- deg)',1,default_value=(0.0,),min=0,max=180,help='Every stamp is turned about its up axis by a random angle between minus and plus this (180 = any direction).'),
               f('tilt','Random Tilt (+/- deg)',1,default_value=(0.0,),min=0,max=90,help='Every stamp leans off its up axis by a random angle up to this, in any direction.'),
               i('seed','Seed',1,default_value=(1,),min=0,max=100000,help='Changes the whole random sequence; more stamps never change the earlier ones.')]
    asset=[bank(),
           i('proto','Prototype Row',1,default_value=(0,),min=0,max=999,help='The prototype a new stamp uses: its row number in the Prototype Bank (0 = the first enabled row). The mousewheel cycles the working set, the keys 1 to 9 pick a row.'),
           t('protorand','Random Prototype',default_value=False,help='Every stamp takes a random prototype: one of the selected cards (the stamp cycle; every enabled row when none is selected), by its Weight in the Prototype Bank. Same as the Random button of the shelf.')]
    advanced=[f('snap','Snap Position',1,default_value=(0.0,),min=0,max=1000,help='Snap new stamps to a grid of this size (X and Z); the point is put back on the surface. 0 = off.'),
              f('snaprot','Snap Rotation (deg)',1,default_value=(0.0,),min=0,max=180,help='Round the turn of a new stamp to a multiple of this (the Ctrl drag of the Place brush uses 15 degrees when this is 0). 0 = off.'),
              t('dragset','Drag Sets Rotation And Scale',default_value=True,help='On: press sets the position, dragging turns (sideways) and scales, release places. Off: a click places at once.')]
    paint=[f('paint_radius','Radius',1,default_value=(1.0,),min=0.01,max=50,help='The radius of the Paint brush, in scene units (Shift + mousewheel, [ and ] in the viewport).'),
           f('paint_density','Density',1,default_value=(2.0,),min=0,max=100,help='Stamps per unit area that a dab tries to place (Ctrl + mousewheel). The Spacing keeps the paint from piling up, so painting over the same spot fills it up to the Spacing and then stops.'),
           f('paint_spacing','Spacing',1,default_value=(0.4,),min=0,max=10,help='The least distance between two stamps painted or already there (0 = off).'),
           f('paint_falloff','Edge Falloff (classic)',1,default_value=(0.5,),min=0,max=1,help='The classic rim thinning of the dab brush: 0 is even, 1 leaves almost nothing at the edge. Used while Density Falloff and Scale Falloff are both off (so old scenes paint as they did); with either on, the Density Profile below does this and this is ignored.')]
    def dis(template,cond):
        template.setConditional(hou.parmCondType.DisableWhen,cond);return template
    def hid(template,cond):
        template.setConditional(hou.parmCondType.HideWhen,cond);return template
    def menu(name,label,items,labels,default,help):
        return hou.MenuParmTemplate(name,label,menu_items=items,menu_labels=labels,default_value=default,help=help)
    CURVES=('linear','smoothstep','smootherstep','ease_in','ease_out','custom');CURVE_LABELS=('Linear','Smoothstep','Smootherstep','Ease In','Ease Out','Custom Ramp')
    def profile(p,name,center_max):
        on=f'{{ paint_{p}_on == 0 }}'
        items=[dis(f('paint_%s_min'%p,'Edge Minimum (%)',1,default_value=(0.0 if p=='dens' else 30.0,),min=0,max=100,help=('The density at the rim of the brush, as a percentage of the Density: 0 leaves nothing at the edge.' if p=='dens' else 'The scale at the rim of the brush, as a percentage of the stamp\'s scale: 30 makes the stamps at the rim 30 % of their size.')),on)]
        if center_max:items.append(dis(f('paint_scale_max','Center Maximum (%)',1,default_value=(100.0,),min=0,max=300,help='The scale at the plateau of the brush, as a percentage of the stamp\'s scale. 100 keeps the stamps in the middle at their size; more makes them bigger there.'),on))
        items+=[dis(f('paint_%s_width'%p,'Falloff Width (%)',1,default_value=(100.0,),min=0,max=100,help='How much of the radius the fall takes, counted from the rim inwards: 100 starts at the centre, 40 keeps the inner 60 % at full value, 0 is a hard edge.'),on),
                dis(f('paint_%s_strength'%p,'Falloff Strength (%)',1,default_value=(100.0,),min=0,max=100,help='How much of the fall is used: 0 is no falloff, 100 the whole fall down to the Edge Minimum.'),on),
                dis(menu('paint_%s_curve'%p,'Curve',CURVES,CURVE_LABELS,1,'The shape of the fall. Smoothstep and Smootherstep look natural; Ease In stays full longer and drops at the rim, Ease Out drops early; Custom Ramp is yours.'),on),
                dis(hid(hou.RampParmTemplate('paint_%s_ramp'%p,'Custom Ramp',hou.rampParmType.Float,default_value=2,help='The fall by hand: left is the rim, right the inner edge of the fall, up is full. A straight ramp from 0 to 1 is a linear fall.'),'{ paint_%s_curve != 5 }'%p),on)]
        return hou.FolderParmTemplate('paint_f_%s'%p,name,folder_type=hou.folderType.Simple,parm_templates=tuple(items))
    paint+=[hou.FolderParmTemplate('paint_f_falloff','Falloff',folder_type=hou.folderType.Simple,parm_templates=(
                callback(menu('paint_preset','Preset',('uniform','soft','sparse','growth','dense','custom'),('Uniform (no falloff)','Soft Natural','Sparse Edges','Growth','Dense Center','Custom'),0,'Sets the falloff parameters below: Uniform has none, Soft Natural thins and shrinks gradually, Sparse Edges thins strongly and shrinks mildly, Growth shrinks strongly and thins moderately, Dense Center keeps the stamps in the middle. Edit any parameter to make your own.'),"m=kwargs['node'].hdaModule();m.stamp_paint_preset(kwargs['node'])"),
                t('paint_dens_on','Enable Density Falloff',default_value=False,help='The number of stamps falls towards the rim of the brush, from the Density in the middle to the Edge Minimum at the rim. Painted as a continuous ribbon: no circles at the dabs, the same at any mouse speed.'),
                t('paint_scale_on','Enable Scale Falloff',default_value=False,help='The stamps get smaller towards the rim of the brush. The scale is multiplied into the stamp\'s scale after the Random Scale (and the bank row\'s Scale at the cook): final = scale x falloff.'))),
            profile('dens','Density Profile',False),profile('scale','Scale Profile',True)]
    def box(name,label,templates):
        return hou.FolderParmTemplate(name,label,folder_type=hou.folderType.Simple,parm_templates=tuple(templates))
    protorand=asset.pop(2)                                                                                       # Randomization tab: what changes between one stamp and the next, in three boxes (the prototype, the scale, the rotation) and the Seed
    random=[box('rnd_proto','Prototype',[protorand]),box('rnd_scale','Scale',transform[2:4]),box('rnd_rot','Rotation',transform[4:7]),box('rnd_seed','Seed',transform[7:8])]
    placement=transform[0:2]+[t('sit','Sit On Surface',default_value=True,help='The bottom of the prototype touches the surface, instead of its pivot: a prototype with its origin in the middle (a character, a ball) stands on the ground or on top of another stamp and does not sink into it. Off: the pivot goes on the surface.'),
                             t('smooth','Smooth Normals',default_value=True,help='Up follows the smooth normal of the surface under the mouse (between the vertices, creases over 60 degrees stay sharp); off uses the flat normal of the face.')]+advanced                                                                            # where and how a stamp lands: Align To Surface, Offset, the snaps, the drag
    ginfo=s('groupinfo','Group',1,default_value=('',),help='Read only. What the Group brush places.');ginfo.setDefaultExpression(('hou.pwd().hdaModule().stamp_group_info(hou.pwd())',));ginfo.setDefaultExpressionLanguage((hou.scriptLanguage.Python,));ginfo.setConditional(hou.parmCondType.DisableWhen,'{ seed >= 0 }')
    group=[ginfo,
           callback(b('group_capture','Set Layout From Selected Stamps',help='Make the stamps selected in the Edit mode (or in the table) the layout of the Group brush: it then stamps copies of that cluster. Place the stamps by hand, select them, press this. Hotkey G in the Edit mode.'),call('stamp_group_capture_selected')),
           callback(b('group_reset','Reset To Radial Layout',help='The Group brush places one stamp per selected card on a ring.'),call('stamp_group_reset')),
           hou.MenuParmTemplate('group_layout','Layout',menu_items=('radial','square','hexagon','cluster','line','spiral','custom'),menu_labels=('Radial','Square','Hexagon','Random Cluster','Line','Spiral','Custom (from selected stamps)'),default_value=0,help='How the members of a group stand: a ring, a grid, a hexagonal lattice, a random cluster, a line, a spiral, or the layout of stamps you placed (Set Layout From Selected Stamps switches to Custom). One member per selected card; Count places more.'),
           f('group_spacing','Spacing',1,default_value=(1.15,),min=0.1,max=10,help='Radial layout: how far apart the members stand, as a multiple of their footprints (1 = just touching).'),
           i('group_count','Count',1,default_value=(0,),min=0,max=64,help='Radial layout: 0 places one stamp of each selected card. A number places that many, each drawn from the selected cards by Weight (random for every group).'),
           t('group_shuffle','Shuffle Order',default_value=False,help='Radial layout: the members stand in a different order for every group.'),
           t('group_match','Match Member Sizes',default_value=True,help='On: every member of a radial / grid / cluster layout is scaled to the same size (the median of the selected prototypes), so a small prototype is not lost next to a big one. Off: every prototype keeps its own size.'),
           f('group_scalerange','Random Group Scale Min / Max',2,default_value=(1.0,1.0),min=0.0001,max=1000,help='Every group is scaled by a random number in this range. 1 / 1 (the default) does not randomize: all groups are the same size, whatever the Random Scale of the Randomization tab says (that one is for single stamps). Dragging still sets the size.'),
           f('group_member_scale','Random Member Scale Min / Max',2,default_value=(1.0,1.0),min=0.0001,max=1000,help='Every member of a group is scaled by its own random number in this range. 1 / 1 (the default): the members are alike.'),
           f('group_member_rot','Random Member Rotation (+/- deg)',1,default_value=(0.0,),min=0,max=180,help='Every member is turned about its up axis by a random angle up to this. 0 (the default): none.'),
           t('group_conform','Conform To Surface',default_value=True,help='Every member is dropped onto the ground under it (hills, slopes); off keeps the group flat.')]
    edit=[info,
          callback(b('sel_all','Select All'),call('stamp_select_all')),callback(b('sel_none','Select None'),call('stamp_select_none')),callback(b('sel_invert','Invert Selection'),call('stamp_select_invert')),
          callback(b('sel_dup','Duplicate Selected',help='Copy the selected stamps (the copies become the selection). In the viewport: hold Z while dragging the edit handle.'),call('stamp_duplicate_selected')),
          callback(b('sel_del','Delete Selected',help='Remove the selected stamps (undoable). In the viewport: Del.'),call('stamp_delete_selected')),
          hou.SeparatorParmTemplate('sep_edit'),
          callback(b('clear','Clear All Stamps',help='Remove every stamp (undoable).'),call('stamp_clear'))]
    options=[callback(b('start','Place Instances',help='Enter the viewport tool (Esc leaves). Entering the node\'s tool does the same.'),call('stamp_start')),
             s('target','Place On',1,default_value=('',),help='What the tool places on: prim paths of the incoming stage, space separated (the meshes and basic shapes under them). Empty: the ground plane Y = 0.'),
             t('onstamps','Place On Stamps',default_value=True,help='New stamps also land on the stamps already placed (stack them, put a rock on a rock). Off: they go through the stamps to Place On. The Delete brush and Edit mode always see the stamps.'),
             s('outputpath','Output Prim',1,default_value=('/World/Stamps',),help='Where the PointInstancer is written.'),
             t('hidesrc','Make Prototype Source Primitives Invisible',default_value=True,help='Make the prims the prototypes come from invisible (the stamps show them; the originals would also show where they are). USD files are always staged hidden.'),
             hou.SeparatorParmTemplate('sep_pane'),
             panestatus,
             callback(b('reload_pane','Reload Stamp Pane',help='Register the Stamp\'s Parameters pane (the cards, the stamps table, the Asset Library) again, then select the node again. Use it when the pane below says it is not loaded.'),call('stamp_reload_pane'))]
    return hou.ParmTemplateGroup((
        hidden(s('stamps','Stamps',1,default_value=('',),tags={'editor':'1','editorlines':'8-30'},help='One line per stamp: x y z  rx ry rz  sx sy sz  prototype row  on (1 / 0). Edit it in the Stamps table of the Parameters pane; the tool adds a line per click.')),
        hidden(s('selection','Selection',1,default_value=('',),help='The selected stamps (line numbers). Written by the Edit mode.')),
        hidden(s('group','Group Layout',1,default_value=('',),tags={'editor':'1','editorlines':'4-20'},help='The custom layout of the Group brush: one line per member, bank row, x y z offset, rx ry rz, scale. Empty = a ring of the selected cards. Set it with Brush > Group > Set Layout From Selected Stamps.')),
        hidden(s('workset','Working Set',1,default_value=('',),help='The bank rows of the selected cards: the mousewheel cycles them and Random Prototype draws from them.')),
        hidden(s('favorites','Favorites',1,default_value=('',),help='The starred cards (bank rows).')),
        hidden(i('brush','Brush',1,default_value=(0,),min=0,max=3,help='0 Place, 1 Delete, 2 Paint, 3 Group.')),
        hou.FolderParmTemplate('mode','Brush',folder_type=hou.folderType.Tabs,parm_templates=(tab('brush_random','Randomization',random),tab('brush_asset','Asset',asset),tab('brush_advanced','Placement',placement),tab('brush_paint','Paint',paint),tab('brush_group','Group',group))),
        hou.FolderParmTemplate('mode_edit','Edit',folder_type=hou.folderType.Tabs,parm_templates=tuple(edit)),
        hou.FolderParmTemplate('mode_options','Options',folder_type=hou.folderType.Tabs,parm_templates=tuple(options))))

def module_text():
    core=(ROOT/'src/stamp_core.py').read_text().replace("STAMP_STATE='arraytron_stamp'","STAMP_STATE=%r"%STATE,1).replace("STAMP_TYPE='arraytron::stamp::0.9.3'","STAMP_TYPE=%r"%TYPE,1)
    return core

PANEL_HEADER='''import hou
import numpy as np
try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:                                           # Houdini 20.5
    from PySide2 import QtCore, QtGui, QtWidgets
'''

def panel_text():
    """The Parameters pane of the node: Qt imports, the Asset Library of Arraytron (library + panel, shared), then the Stamp's cards, panel and entry points."""
    gallery=(ROOT/'src/stamp_gallery.py').read_text(encoding='utf8').replace("STAMP_TYPE = 'arraytron::stamp::0.9.3'","STAMP_TYPE = %r"%TYPE,1)
    return PANEL_HEADER+(ROOT/'src/arraytron_library.py').read_text(encoding='utf8')+'\n'+(ROOT/'src/arraytron_libpanel.py').read_text(encoding='utf8')+'\n'+gallery

HELP='''<html><body><h1>Arraytron Stamp %s</h1>
<p>Place instances by hand, like Houdini's Layout / Paint Instances tool: a <b>Brush</b> mode with a Place, a Delete and a Paint brush, an <b>Edit</b> mode that selects the placed stamps and moves, turns and scales them with Houdini's edit handle. The node is one Python LOP that writes a <b>UsdGeomPointInstancer</b>; the stamps are one text parameter.</p>
<h2>Quick start</h2>
<ol><li>Wire the scene (the ground and the props) into the <b>first input</b>; models for Input Connection rows into inputs 2 to 4.</li>
<li>Select the node and press Enter in the Solaris viewport (or a brush on the shelf of the Parameters pane).</li>
<li>Fill the <b>Prototype Bank</b> (Brush &gt; Asset), or add USD files from the <b>Asset Library</b> with Add to Bank. A new node starts with a built-in sphere.</li>
<li>Click to place; press and drag to turn and scale.</li></ol>
<h2>Place brush</h2>
<ul><li><b>LMB</b> places; <b>LMB drag</b> sets rotation and scale (a dial shows both). <b>Shift + LMB drag</b> scales only, <b>Ctrl + LMB drag</b> orients to increments, <b>Ctrl + Shift + LMB drag</b> orients freely.</li>
<li><b>Mousewheel</b> cycles the working set (the selected cards); Shift / Ctrl + wheel scales / rotates the next stamp; the keys 1 to 9 pick a row.</li>
<li>New stamps land on the stamps already placed (Options &gt; Place On Stamps), so they stack.</li></ul>
<h2>Group brush</h2><p>One click stamps several prototypes in a layout (Brush &gt; Group &gt; Layout: radial, square, hexagon, random cluster, line, spiral) of the selected cards, all the same size unless you set the group's own randomization (Spacing, Count, Shuffle Order, Match Member Sizes, Random Group / Member Scale, Conform To Surface), or the layout of stamps you placed (Edit mode: select them, press <b>G</b> or Brush &gt; Group &gt; Set Layout From Selected Stamps). Drag turns and scales the whole group. The <b>Random</b> button on the shelf takes a random selected card for every stamp.</p><h2>Sheet</h2><p>A cell you edit in the STAMPS table changes every selected stamp, or all stamps (Edit: All stamps), with Set, Add or Multiply.</p><h2>Paint brush</h2><p>Drag to paint stamps inside a disc (Brush &gt; Paint: Radius, Density, Spacing, Edge Falloff); <b>Ctrl + drag</b> erases the stamps inside it. Shift / Ctrl + mousewheel change the radius / density. The stamps take the Brush &gt; Transform randomness and the working set; one undo step per stroke. Place shows the prototype itself as a ghost under the mouse.</p>
<h2>Delete brush</h2><p>Click, or drag over several stamps and release: they are deleted in one undo step.</p>
<h2>Edit mode (Shift + B)</h2>
<ul><li>Click selects a stamp, Shift + click adds or removes, drag on nothing box selects. The edit handle moves, rotates and scales the selection about its centre; hold <b>Z</b> while dragging it to duplicate. <b>Del</b> deletes the selection.</li>
<li>The <b>STAMPS</b> table of the Parameters pane lists every stamp; edit a cell to edit the stamp. Its selection is the viewport selection.</li></ul>
<h2>Hotkeys and menus</h2><p><b>C</b> brush menu, <b>B</b> options menu, <b>Shift + B</b> Brush / Edit, <b>Z</b> duplicate, <b>Del</b> delete, <b>Enter</b> finish, [ ] scale, , . rotate. They are Houdini hotkeys (Hotkey Editor, "arraytron_stamp Operation"). The hints are the viewer's HUD panel (Shift + F1).</p>
<h2>Parameters pane</h2><p>Above the parameters: the brush shelf, the prototype cards (thumbnails; List / Grid / Large; search; favourite stars; filters for the favourites and the working set), the STAMPS table and the Asset Library shared with Arraytron. If the pane below says it is not loaded, Options &gt; Reload Stamp Pane.</p>
<p>Documentation: docs/ARRAYTRON_STAMP.md next to the HDA project.</p></body></html>'''

def add_icon(definition):
    """icon/Arraytron-Stamp.svg embedded as the section Icon.svg; the node and the heads-up panel use it (opdef:)."""
    definition.addSection('Icon.svg',(ROOT/'icon'/'Arraytron-Stamp.svg').read_text(encoding='utf8'))
    definition.setIcon('opdef:/'+definition.nodeType().nameWithCategory()+'?Icon.svg')

def add_viewer_state(definition):
    code=(ROOT/'src/stamp_state.py').read_text().replace("STATE_NAME='arraytron_stamp'","STATE_NAME=%r"%STATE,1)
    definition.addSection('ViewerStateModule',code);definition.addSection('DefaultState',STATE);definition.addSection('ViewerStateName.orig',STATE)
    definition.addSection('ViewerStateInstall',"__import__('viewerstate.utils', fromlist=[None]).register_pystate_embedded(kwargs['type'])")
    definition.addSection('ViewerStateUninstall',"__import__('viewerstate.utils', fromlist=[None]).unregister_pystate_embedded(kwargs['type'])")
    for name in ('ViewerStateModule','ViewerStateInstall','ViewerStateUninstall'):
        definition.setExtraFileOption(name+'/IsPython',True);definition.setExtraFileOption(name+'/IsScript',True)
    definition.setExtraFileOption('ViewerStateInstall/IsViewerState',True);definition.setExtraFileOption('ViewerStateUninstall/IsViewerState',True)
    definition.setExtraFileOption('ViewerStateName.orig/IsPython',True);definition.setExtraFileOption('ViewerStateName.orig/IsExpr',False)

def build():
    HDA.parent.mkdir(exist_ok=True);hou.hipFile.clear(suppress_save_prompt=True)
    stage=hou.node('/stage');asset=stage.createNode('subnet','Stamp');asset.setParmTemplateGroup(parms())
    for c in asset.children():c.destroy()
    asset=asset.createDigitalAsset(name=TYPE,hda_file_name=str(HDA),description='Arraytron Stamp',min_num_inputs=0,max_num_inputs=4)
    definition=asset.type().definition();definition.addSection('PythonModule',module_text());hou.hda.reloadFile(str(HDA))
    asset=hou.node('/stage/Stamp');definition=asset.type().definition();asset.allowEditingOfContents()
    merge=asset.createNode('merge','merge_inputs')
    for k,source in enumerate(asset.indirectInputs()[:4]):merge.setInput(k,source)
    cook=asset.createNode('pythonscript','STAMPS');cook.parm('python').set("asset=hou.pwd().parent()\nasset.hdaModule().stamp_cook(hou.pwd())\n");cook.setInput(0,merge)
    cook.setDisplayFlag(True);asset.layoutChildren()
    definition.setParmTemplateGroup(parms())
    definition.addSection('OnCreated',"node=kwargs['node']\nif node.name().startswith(('stamp','subnet')):\n    node.setName('arraytron_stamp1',unique_name=True)\n");definition.setExtraFileOption('OnCreated/IsPython',True)
    definition.addSection('StampPanel.py',panel_text())
    hook="try:\n    t=kwargs['node'].type() if 'node' in kwargs else kwargs['type']\n    t.hdaModule().gallery_install(t)\nexcept Exception as error:\n    print('Arraytron Stamp: the gallery in the Parameters pane is not available (%s)'%error)\n"
    definition.addSection('OnCreated',definition.sections()['OnCreated'].contents()+hook);definition.addSection('OnLoaded',hook);definition.setExtraFileOption('OnLoaded/IsPython',True)     # 0.8.0: the gallery is the Parameters pane of the node
    definition.addSection('Help',HELP%STAMP_VERSION)
    definition.updateFromNode(asset);asset.matchCurrentDefinition();add_viewer_state(definition);add_icon(definition)
    section=definition.sections()['DialogScript'];text=section.contents()
    for index,label in enumerate(('Scene (ground, props)','Prototype Input 2','Prototype Input 3','Prototype Input 4'),1):text=re.sub(r'^\s*inputlabel\s+%d\s+.*$'%index,'    inputlabel\t%d\t"%s"'%(index,label),text,flags=re.M)
    section.setContents(text)
    usd=asset.stage();errors=(asset.errors(),cook.errors());assert not any(errors),errors
    print(json.dumps({'hda':str(HDA),'type':TYPE,'errors':list(asset.errors())},indent=2))

if __name__=='__main__':build()
