"""v1.18.0 Asset Library in real Houdini: hython tests/validate_library.py [version]
The library (a per-user JSON file with custom categories, assets from the Solaris Asset Catalog, USD files and folders, and "Add to Bank") is code in the HDA's PythonModule; its Qt section is judged in
the GUI. What is proved here: categories (default, add, rename, delete moves the assets to Uncategorized, order), assets (dedupe, search by name and tag, rename, tags, move), the file (a round trip,
an atomic save, a broken file kept aside, the ARRAYTRON_LIBRARY folder), importing (USD files, a folder, an Asset Catalog data source with thumbnails and non-USD items skipped), Add to Bank on a real node
(the default row replaced, new rows, a chosen row, the prototype really comes from the file and the node cooks), the panel code in the HDA section, and the previous release unchanged.
Env ARRAYTRON_MUTATE=lib_category|lib_dedupe|lib_persist|lib_bank breaks the product; the suite must FAIL."""
from pathlib import Path
import hou, json, os, shutil, sys, tempfile, time, types
import numpy as np
from pxr import Usd, UsdGeom
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v1.18.0':'v1.17.0','v1.19.0':'v1.18.0','v1.20.0':'v1.19.0','v1.21.0':'v1.20.0','v1.21.1':'v1.21.0','v1.21.1':'v1.21.0'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_library_'));checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')
LIB=WORK/'lib';os.environ['ARRAYTRON_LIBRARY']=str(LIB)
def make_usd(name,prim,size):
    path=WORK/'assets'/(name+'.usda');path.parent.mkdir(exist_ok=True);s=Usd.Stage.CreateNew(str(path));UsdGeom.Xform.Define(s,'/'+prim);s.SetDefaultPrim(s.GetPrimAtPath('/'+prim))
    UsdGeom.Cube.Define(s,'/%s/Body'%prim).CreateSizeAttr(size);s.GetRootLayer().Save();return path.as_posix()
ROCK=make_usd('rock','Rock',0.3);TREE=make_usd('tree','Tree',1.0);FERN=make_usd('fern','Fern',0.2)
def write_scene():
    path=WORK/'lib.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    UsdGeom.Xform.Define(s,'/World/Props/Ball');UsdGeom.Cube.Define(s,'/World/Props/Ball/C').CreateSizeAttr(0.2);s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True)
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
def fresh_node(stage,source,typ=None,name='Lib',**values):
    a=stage.createNode(typ or TYPE,name);a.setInput(0,source)
    for k,v in values.items():a.parm(k).set(v)
    return a
def module(a=None):
    if a is None:
        st,sc=new_scene('mod');a=fresh_node(st,sc)
    m=a.hdaModule();g=m.add_category.__globals__
    if MUTATE=='lib_category' and not g.get('_mutated'):
        g['_mutated']=True;good=g['delete_category']
        def bad(data,name):
            if name not in data['categories']:return False
            data['categories']=[c for c in data['categories'] if c!=name];return True                      # the assets keep a category that no longer exists
        g['delete_category']=bad
    if MUTATE=='lib_dedupe' and not g.get('_mutated2'):
        g['_mutated2']=True;good=g['add_asset']
        def bad(data,file_path,**kw):
            kw.pop('source',None);a=good(dict(data,assets=[]),file_path,**kw);data['assets'].append(a);return a      # the same file is added again
        g['add_asset']=bad
    if MUTATE=='lib_persist' and not g.get('_mutated3'):
        g['_mutated3']=True;good=g['save_library']
        g['save_library']=lambda data,folder=None:good(dict(data,assets=[]),folder)                          # the assets are not written
    if MUTATE=='lib_bank' and not g.get('_mutated4'):
        g['_mutated4']=True;good=g['add_to_bank']
        def bad(node,asset,row=None):
            r=good(node,asset,row);node.parm('proto_type%d'%r).set(0);return r                              # the row stays a Prim Path row
        g['add_to_bank']=bad
    return m
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()
def out(a):
    s=a.stage();assert not list(a.errors()),a.errors();pi=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    return pi,dict(pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3),ids=np.array(pi.GetIdsAttr().Get(t) or [],dtype=int))
def clean():
    shutil.rmtree(LIB,ignore_errors=True)

def categories_and_assets():
    clean();m=module();d=m.load_library();assert d['categories']==['Trees','Plants','Rocks','Props'] and d['assets']==[]
    assert m.add_category(d,'  Grass   Tufts ')=='Grass Tufts' and m.add_category(d,'grass tufts')=='Grass Tufts' and d['categories'].count('Grass Tufts')==1 and m.add_category(d,'')is None and m.add_category(d,'uncategorized') is None
    assert m.rename_category(d,'Grass Tufts','Grass') and 'Grass' in d['categories'] and not m.rename_category(d,'Grass','Rocks') and not m.rename_category(d,'Nope','X')
    a=m.add_asset(d,ROCK,category='Rocks',prim='/Rock',tags=['Big','mossy','big']);b=m.add_asset(d,TREE,name='Pine',category='Trees',prim='/Tree')
    assert a['name']=='rock' and a['tags']==['big','mossy'] and b['name']=='Pine' and a['id']!=b['id'] and len(d['assets'])==2
    again=m.add_asset(d,ROCK,category='Props',prim='/Rock');assert again is a and len(d['assets'])==2 and a['category']=='Props'                         # the same file and prim is one asset
    assert [x['name'] for x in m.query_assets(d)]==['Pine','rock'] and [x['name'] for x in m.query_assets(d,'Trees')]==['Pine'] and [x['name'] for x in m.query_assets(d,text='moss')]==['rock']
    assert [x['name'] for x in m.query_assets(d,text='big rock')]==['rock'] and m.query_assets(d,text='zzz')==[] and [x['name'] for x in m.query_assets(d,text='PINE')]==['Pine']
    assert m.set_asset(d,a['id'],name='Boulder',tags=['Stone'],category='Rocks') and a['name']=='Boulder' and a['tags']==['stone'] and a['category']=='Rocks'
    assert m.delete_category(d,'Rocks') and 'Rocks' not in d['categories'] and a['category']==m.UNCATEGORIZED and len(d['assets'])==2                       # the assets are never deleted with a category
    assert m.set_asset(d,a['id'],category='Plants') and a['category']=='Plants' and m.set_asset(d,a['id'],category=m.UNCATEGORIZED) and a['category']==m.UNCATEGORIZED
    d['categories']=['A','B','C'];assert m.move_category(d,'C',-2) and d['categories']==['C','A','B'] and m.move_category(d,'C',99) and d['categories']==['A','B','C']
    assert m.remove_asset(d,b['id']) and m.find_asset(d,b['id']) is None and not m.remove_asset(d,'nope')

def file_roundtrip():
    clean();m=module();assert str(LIB)==m.library_dir()
    d=m.load_library();m.add_asset(d,ROCK,category='Rocks',prim='/Rock');m.add_category(d,'Mine')
    path=m.save_library(d);assert os.path.isfile(path) and not os.path.exists(path+'.tmp') and path==m.library_file()
    e=m.load_library();assert e['assets']==d['assets'] and e['categories']==d['categories'],(e,d)                                                       # a round trip
    json.loads(open(path,encoding='utf8').read())
    open(path,'w',encoding='utf8').write('{ this is not json');f=m.load_library();assert f['assets']==[] and f['categories']==list(m.DEFAULT_CATEGORIES) and os.path.exists(path+'.broken')   # kept aside, a new library
    open(path,'w',encoding='utf8').write('[1,2,3]');assert m.load_library()['assets']==[]
    other=WORK/'other';os.environ['ARRAYTRON_LIBRARY']=str(other)
    try:assert m.library_dir()==str(other) and m.load_library()['assets']==[]
    finally:os.environ['ARRAYTRON_LIBRARY']=str(LIB)

def importing():
    clean();m=module();d=m.load_library()
    assert m.default_prim_of(ROCK)=='/Rock' and m.default_prim_of(str(WORK/'missing.usda'))==''
    got=m.import_files(d,[ROCK,str(WORK/'assets'),str(WORK/'notes.txt')],category='Rocks');assert len(d['assets'])==3 and {a['name'] for a in d['assets']}=={'rock','tree','fern'} and all(a['prim'] for a in d['assets'])
    assert [a for a in d['assets'] if a['name']=='rock'][0]['category']=='Rocks'                                                                       # the same file twice is one asset
    png=b'\x89PNG\r\n\x1a\n'+b'0'*40
    class Source:
        ids=['a','b','c','d']
        def itemIds(self):return list(self.ids)
        def filePath(self,i):return {'a':TREE,'b':str(WORK/'snap.png'),'c':'/obj/geo1/node','d':FERN}[i]
        def label(self,i):return {'a':'Pine Tree','b':'Snapshot','c':'Node','d':'Fern Plant'}[i]
        def thumbnail(self,i):return png if i=='a' else b''
        def tags(self,i):return ['Forest','Conifer'] if i=='a' else []
    found=m.gallery_assets(Source());assert [x['name'] for x in found]==['Pine Tree','Fern Plant'] and found[0]['tags']==['Forest','Conifer']                  # snapshots and node references are skipped
    d2=m.empty_library();added=m.import_gallery(d2,Source(),category='Trees');assert len(added)==2 and all(a['category']=='Trees' for a in added) and added[0]['source']=='gallery' and added[0]['prim']=='/Tree'
    assert added[0]['thumb'].startswith('thumbs/') and added[0]['thumb'].endswith('.png') and os.path.isfile(os.path.join(m.library_dir(),added[0]['thumb'])) and added[1]['thumb']==''
    one=m.import_gallery(m.empty_library(),Source(),item_ids={'d'});assert [a['name'] for a in one]==['Fern Plant']
    assert m.remove_asset(d2,added[0]['id']) and not os.path.isfile(os.path.join(m.library_dir(),added[0]['thumb']))                              # the thumbnail goes with the asset

def bank():
    clean();st,sc=new_scene('bank');a=fresh_node(st,sc,mode=0,line_count=6,line_length=4.0);m=module(a);d=m.load_library()
    rock=m.add_asset(d,ROCK,prim='/Rock');tree=m.add_asset(d,TREE,prim='/Tree');fern=m.add_asset(d,FERN,prim='')
    assert a.evalParm('protos')==1 and a.evalParm('proto_type1')==0
    r1=m.add_to_bank(a,rock);assert r1==1 and a.evalParm('protos')==1                                                                                     # the untouched default row is replaced
    assert a.evalParm('proto_type1')==2 and a.evalParm('proto_file1')==ROCK and a.evalParm('proto_fileprim1')=='/Rock' and a.evalParm('proto_on1')==1
    r2=m.add_to_bank(a,tree);assert r2==2 and a.evalParm('protos')==2 and a.evalParm('proto_file2')==TREE and a.evalParm('proto_type2')==2             # a new row at the end
    r3=m.add_to_bank(a,fern,row=1);assert r3==1 and a.evalParm('protos')==2 and a.evalParm('proto_file1')==FERN and a.evalParm('proto_fileprim1')==''    # a chosen row is replaced
    assert [(x[0],x[1]) for x in m.library_bank_rows(a)]==[(1,2),(2,2)]
    pi,o=out(a);targets=[str(t) for t in pi.GetPrototypesRel().GetTargets()];assert len(targets)==2 and len(o['ids'])==6                                  # the node cooks with both prototypes
    s=a.stage();bodies=[p for p in s.Traverse() if p.GetName()=='Body'];assert len(bodies)>=2 and all(s.GetPrimAtPath(t).IsValid() for t in targets)
    sizes=sorted(UsdGeom.Cube(b).GetSizeAttr().Get() for b in bodies);assert 0.2 in sizes and 1.0 in sizes                                                  # really the geometry of the two files
    b=fresh_node(st,sc,name='Edited',mode=0,line_count=3);b.parm('proto_prim1').set('/World/Props/Ball');b.parm('proto_scale1').set(2.0)
    r=m.add_to_bank(b,rock);assert r==2 and b.evalParm('protos')==2 and b.evalParm('proto_prim1')=='/World/Props/Ball'                                      # an edited default row is kept

def panel_and_module():
    d=hou.nodeType(hou.lopNodeTypeCategory(),TYPE).definition();text=d.sections()['ModePalette.py'].contents()
    ns=types.ModuleType('lib_panel');exec(compile(text,'ModePalette.py','exec'),ns.__dict__)
    for name in ('LibraryPanel','GalleryDialog','ParmPanel','load_library','save_library','import_gallery','add_to_bank','query_assets','_placeholder_icon'):assert hasattr(ns,name),name
    assert 'LibraryPanel(self)' in text
    for path,prim in ((ROCK,'/Rock'),(TREE,'/Tree'),(ROCK,'')):
        img=ns.render_usd_thumbnail(path,prim);assert img is not None and img.width()==128 and img.height()==128
        colors={img.pixel(x,y) for x in range(0,128,4) for y in range(0,128,4)};assert len(colors)>=3                                                       # a drawn solid on a background, not a blank
    shapes=WORK/'assets'/'shapes.usda';q=Usd.Stage.CreateNew(str(shapes));UsdGeom.Xform.Define(q,'/Shapes');UsdGeom.Sphere.Define(q,'/Shapes/S');cyl=UsdGeom.Cylinder.Define(q,'/Shapes/Cy');cyl.AddTranslateOp().Set((3,0,0));UsdGeom.Cone.Define(q,'/Shapes/Co').AddTranslateOp().Set((-3,0,0));UsdGeom.Capsule.Define(q,'/Shapes/Ca').AddTranslateOp().Set((0,0,3));q.GetRootLayer().Save()
    img=ns.render_usd_thumbnail(shapes.as_posix(),'/Shapes');assert img is not None and len({img.pixel(x,y) for x in range(0,128,3) for y in range(0,128,3)})>=5                  # spheres, cylinders, cones and capsules are drawn too
    empty=WORK/'assets'/'empty.usda';s=Usd.Stage.CreateNew(str(empty));UsdGeom.Xform.Define(s,'/Nothing');s.GetRootLayer().Save();assert ns.render_usd_thumbnail(empty.as_posix(),'/Nothing') is None   # nothing to draw
    st,sc=new_scene('pm');a=fresh_node(st,sc);m=a.hdaModule()
    for name in ('load_library','add_to_bank','import_files','query_assets','library_bank_rows'):assert hasattr(m,name),name
    assert callable(m.sop_biome) and callable(m.rows_expand)                                                                                                  # the other modules are not shadowed
    assert '$' not in d.sections()['PythonModule'].contents().split('# ---- Asset Library')[1].split('# ----')[0]

def unchanged():
    st,sc=new_scene('same');new=hou.nodeType(hou.lopNodeTypeCategory(),TYPE).parmTemplateGroup();old=hou.nodeType(hou.lopNodeTypeCategory(),OLD_TYPE).parmTemplateGroup()
    def names(g):
        o=[]
        def walk(ts):
            for t in ts:
                o.append(t.name())
                if t.type() in (hou.parmTemplateType.Folder,hou.parmTemplateType.FolderSet) and hasattr(t,'parmTemplates'):walk(t.parmTemplates())
        walk(g.entries());return o
    assert set(names(old))<=set(names(new)) and all(n.startswith('biome_') for n in set(names(new))-set(names(old)))                    # nothing removed or moved; a later release may add Biome fields only
    for mode,extra in ((0,dict(line_count=12)),(1,dict(area_count=30)),(3,dict(circle_count=9))):
        pa,a=out(fresh_node(st,sc,name='N%d'%mode,mode=mode,proto_prim1='/World/Props/Ball',**extra));pb,b=out(fresh_node(st,sc,typ=OLD_TYPE,name='O%d'%mode,mode=mode,proto_prim1='/World/Props/Ball',**extra))
        assert len(a['ids'])>0 and np.array_equal(a['ids'],b['ids']) and np.array_equal(a['pos'],b['pos']),mode

def main():
    for name,func in (('Categories and assets: defaults, add / rename / delete / order, dedupe, search by name and tag, edit, nothing lost with a category',categories_and_assets),
                      ('The file: round trip, atomic save, a broken file kept aside, ARRAYTRON_LIBRARY',file_roundtrip),
                      ('Importing: USD files and folders, an Asset Catalog data source with thumbnails (snapshots and nodes skipped), thumbnails removed with the asset',importing),
                      ('Add to Bank on a real node: default row replaced, new rows, a chosen row, the prototypes really come from the files, an edited row kept',bank),
                      ('Panel code in the HDA section and the module functions; no name clash',panel_and_module),
                      ('The previous release unchanged: same parameters and output',unchanged)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_library_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
