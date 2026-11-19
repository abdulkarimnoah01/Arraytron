"""v1.17.0 Mode Palette in real Houdini: hython tests/validate_modepanel.py [version]
The Distribution Mode palette (big icon cells with the title under each, shown on top of the node's parameters as a Python Panel in the Parameters pane) is Qt and is judged in the GUI. What can be
proved without the interface: the HDA carries the panel code and every icon, the icons are valid SVG, every mode of the menu has a title and an icon (lit and dim), the installer builds a valid
.pypanel for this node type with showInParametersPane, the OnCreated / OnLoaded hooks call it, nothing changes in the node's parameters or output (the previous release is compared), and the node
still works with no interface. Env ARRAYTRON_MUTATE=palette_title|palette_icon|palette_install|palette_hook breaks the product; the suite must FAIL."""
from pathlib import Path
import hou, json, os, sys, tempfile, time, types
import xml.etree.ElementTree as ET
import numpy as np
from pxr import Usd, UsdGeom
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v1.38.3':'v1.38.2','v1.38.2':'v1.38.1','v1.38.1':'v1.38.0','v1.38.0':'v1.37.0','v1.37.0':'v1.36.0','v1.36.0':'v1.35.0','v1.35.0':'v1.34.1','v1.34.1':'v1.34.0','v1.34.0':'v1.33.0','v1.33.0':'v1.32.0','v1.32.0':'v1.31.1','v1.31.1':'v1.31.0','v1.31.0':'v1.30.1','v1.30.1':'v1.30.0','v1.30.0':'v1.29.0','v1.17.0':'v1.16.0','v1.18.0':'v1.17.0','v1.19.0':'v1.18.0','v1.20.0':'v1.19.0','v1.21.0':'v1.20.0','v1.21.1':'v1.21.0','v1.22.0':'v1.21.1','v1.23.0':'v1.22.0','v1.24.0':'v1.23.0','v1.25.0':'v1.24.0','v1.25.1':'v1.25.0','v1.21.1':'v1.21.0','v1.22.0':'v1.21.1','v1.23.0':'v1.22.0','v1.24.0':'v1.23.0','v1.25.0':'v1.24.0','v1.25.1':'v1.25.0'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_modepanel_'));checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')
KEYS=('line','area','grid','circle','curve','surface','paint','cluster','imported','place','biome')
def write_scene():
    path=WORK/'modes.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    UsdGeom.Xform.Define(s,'/World/Props/Ball');UsdGeom.Cube.Define(s,'/World/Props/Ball/C').CreateSizeAttr(0.2);s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True)
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
def node(stage,source,typ=None,name='Modes',**values):
    a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Ball')
    for k,v in values.items():a.parm(k).set(v)
    return a
def out(a):
    s=a.stage();assert not list(a.errors()),a.errors();pi=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    return dict(pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3),ids=np.array(pi.GetIdsAttr().Get(t) or [],dtype=int))
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()
def definition(typ=TYPE):return hou.nodeType(hou.lopNodeTypeCategory(),typ).definition()
def panel_text():
    text=definition().sections()['ModePalette.py'].contents()
    if MUTATE=='palette_title':text=text.replace("'Biome': 'biome'","'Biome': 'nobiome'")
    if MUTATE=='palette_icon':text=text.replace("'paint_on'","'paint_x'",1)
    return text
def run_panel_module():
    """Execute the panel module (PySide imports included, no widget is created) and return its namespace."""
    ns=types.ModuleType('arraytron_panel_under_test');exec(compile(panel_text(),'ModePalette.py','exec'),ns.__dict__);return ns

def panel_and_icons():
    d=definition();assert 'ModePalette.py' in d.sections()
    ns=run_panel_module()
    for name in ('ModePalette','ParmPanel','onCreateInterface','onNodePathChanged','onActivateInterface','onDestroyInterface','is_arraytron'):assert hasattr(ns,name),name
    assert sorted(ns.ICONS)==sorted('%s_%s'%(k,s) for k in KEYS for s in ('on','off')),sorted(ns.ICONS)
    for name,text in ns.ICONS.items():
        root=ET.fromstring(text);assert root.tag.endswith('svg') and root.get('viewBox')=='0 0 64 64',name
        assert len(list(root.iter()))>4,name
    a=ns.ICONS['biome_on'];b=ns.ICONS['biome_off'];assert a!=b and a.count('<rect')>b.count('<rect')                                  # lit is a different, glowing tile
    labels=hou.nodeType(hou.lopNodeTypeCategory(),TYPE).parmTemplateGroup().find('mode').menuLabels()
    assert len(labels)==11
    for label in labels:assert ns.TITLES.get(label) in KEYS or label=='Place (retired)',label                                                             # every mode has a title and an icon
    shown=[l for l in labels if l!='Place (retired)'];assert len(set(ns.TITLES[l] for l in shown))==len(shown)==10 and all(('%s_on'%k in ns.ICONS and '%s_off'%k in ns.ICONS) for k in (ns.TITLES[l] for l in shown))                      # the palette has ten modes: Place is retired

def installer():
    st,sc=new_scene('installer');a=node(st,sc);m=a.hdaModule();f=m.install_parm_panel;g=f.__globals__
    assert f(a.type()) is False                                                                  # no interface in hython
    seen=[]
    class Pypanel:
        def installFile(self,path):seen.append(path)
    class Proxy:
        def __getattr__(self,name):return getattr(hou,name)
        isUIAvailable=staticmethod(lambda:True);pypanel=Pypanel()
    real=g['hou'];g['hou']=Proxy();g['_PARM_PANEL_DONE'].clear()
    if MUTATE=='palette_install':g['_PARM_PANEL_DONE'].add(a.type().nameWithCategory())
    try:
        assert f(a.type()) is True and len(seen)==1,seen
        root=ET.parse(seen[0]).getroot();iface=root.find('interface');assert iface.get('name').startswith('arraytron_parms_')
        show=iface.find('showInParametersPane');assert show is not None and show.get('optype')==a.type().nameWithCategory() and 'Lop/' in show.get('optype') and TYPE.split('::')[-1] in show.get('optype')
        script=iface.find('script').text;assert script==definition().sections()['ModePalette.py'].contents()
        compile(script,'pypanel','exec')
        assert f(a.type()) is True and len(seen)==1                                              # installed once
        os.environ['ARRAYTRON_NO_PARM_PANEL']='1';g['_PARM_PANEL_DONE'].clear()
        try:assert f(a.type()) is False and len(seen)==1                                         # the kill switch keeps Houdini's plain dialog
        finally:del os.environ['ARRAYTRON_NO_PARM_PANEL']
    finally:g['hou']=real;g['_PARM_PANEL_DONE'].clear()

def hooks():
    d=definition();sec=d.sections()
    created=sec['OnCreated'].contents();loaded=sec['OnLoaded'].contents()
    if MUTATE=='palette_hook':loaded=loaded.replace('install_parm_panel','nothing')
    for text in (created,loaded):
        compile(text,'hook','exec');assert 'install_parm_panel' in text
    assert "setName('arraytron1'" in created                                                    # the rename of the node is still there
    opts=d.extraFileOptions();assert opts.get('OnLoaded/IsPython') is True and opts.get('OnCreated/IsPython') is True
    st,sc=new_scene('hooks');a=st.createNode(TYPE);assert a.name().startswith('arraytron'),a.name()      # OnCreated runs without an interface and does not fail

def unchanged():
    st,sc=new_scene('same')
    new=hou.nodeType(hou.lopNodeTypeCategory(),TYPE).parmTemplateGroup();old=hou.nodeType(hou.lopNodeTypeCategory(),OLD_TYPE).parmTemplateGroup()
    def names(g):
        o=[]
        def walk(ts):
            for t in ts:
                o.append(t.name())
                if t.type()==hou.parmTemplateType.Folder or t.type()==hou.parmTemplateType.FolderSet:walk(t.parmTemplates()) if hasattr(t,'parmTemplates') else None
        walk(g.entries());return o
    assert set(n for n in names(old) if not n.startswith('ui_'))<=set(names(new)) and all(n.startswith(('proto_import','paint_engine','paint_noise','paint_preset','paint_dens_','paint_scale_','paint_f_','brush_','erase_soft','scale_mode','scale_target','push_mode','orient_mode','paint_swap_row','clone_','paint_clone','edit_','lk_','tab_edit','tab_lookdev','mirror','tab_mirror','tab_source','biome_','noise_','view_mode','copy_','viz_','mask_viz','mask_noise','ui_','mask_brush','mask_paint','mask_hpaint','mask_gamma','mask_curve','mask_outrange','mask_sym','surface_dir','surface_light','surface_spread','surface_soft','surface_opp','bound_gizmo','surface_proxy','surface_ghost','scatter_info','surface_limit','field_m','blast_','fall_mask_','mask_fade_','mask_scale_curve','mask_export_','mask_bake_go','mask_save_go','mask_load_go','mstage_','mup_')) for n in set(names(new))-set(names(old)))                    # nothing removed or moved; a later release may add Biome fields only                                                              # not one parameter added, removed or moved
    n=new.find('mode');o=old.find('mode');assert [('Instance Place' if x=='Place (retired)' else x) for x in n.menuLabels()]==[('Instance Place' if x=='Place (retired)' else x) for x in o.menuLabels()] and n.defaultValue()==o.defaultValue() and n.menuItems()==o.menuItems()
    for mode,extra in ((0,dict(line_count=12)),(1,dict(area_count=30)),(2,{}),(3,dict(circle_count=9))):
        a=out(node(st,sc,name='N%d'%mode,mode=mode,**extra));b=out(node(st,sc,typ=OLD_TYPE,name='O%d'%mode,mode=mode,**extra))
        assert len(a['ids'])>0 and np.array_equal(a['ids'],b['ids']) and np.array_equal(a['pos'],b['pos']),mode

def main():
    for name,func in (('Panel code and icons: section, hooks, 22 valid SVGs, a title and a lit / dim icon for every mode',panel_and_icons),
                      ('Installer: a valid .pypanel for this node type in the Parameters pane, once, kill switch, nothing without an interface',installer),
                      ('OnCreated / OnLoaded hooks call the installer; the node is still renamed arraytron1',hooks),
                      ('The previous release unchanged: same parameters, mode menu and output',unchanged)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_modepanel_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
