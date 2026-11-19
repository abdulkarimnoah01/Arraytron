"""Prototype sockets in both HDAs: Arraytron v1.37.0 and Arraytron Stamp 0.12.0 (Import Prototype Inputs, src/proto_import.py).
  hython tests/validate_protoimport.py [v1.37.0]        (hython 22 or 20.5; build both HDAs first)
Groups per HDA: the scan (stage order, several sockets, a group of kind group expanded, materials and lights skipped, an inactive prim skipped, a single-child chain), the bank rows (Input Connection, Prim Path,
defaults, the blank default row reused, the artist's weight kept on a second click, Replace The Bank, one undo step), the Asset Library (the original USD file for a reference, a standalone file for a procedural prim, the same
name on a second run, an existing asset keeps its category, the toggle), the cook (no errors, every prototype used) and the errors (no socket wired, nothing drawable)."""
import sys, os, json, tempfile
from pathlib import Path
import hou
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
os.environ.pop('ARRAYTRON_STAMP',None)
VID=versions.resolve(sys.argv[1]) if len(sys.argv)>1 else versions.CURRENT;H205=versions.is_h205();folder=ROOT/('otls_h205' if H205 else 'dist')
A_HDA=folder/('Arraytron_%s%s.hda'%(VID,'_H205' if H205 else ''));S_HDA=folder/('Arraytron_Stamp_v0.12.0%s.hda'%('_H205' if H205 else ''))
TYPES=(('Arraytron',versions.type_name(VID),A_HDA),('Stamp','arraytron::stamp::0.12.0',S_HDA))
LIB=tempfile.mkdtemp(prefix='protoimport_lib_');os.environ['ARRAYTRON_LIBRARY']=LIB
for _,_,f in TYPES:hou.hda.installFile(str(f),force_use_assets=True)
ASSETS=(ROOT/'dist'/'test_assets').as_posix()
fails=[];passed=[0]
def check(name,ok,detail=''):
    if ok:print('PASS',name);passed[0]+=1
    else:print('FAIL',name,'->',detail);fails.append(name)
stage=hou.node('/stage')
def reference(name,file):
    n=stage.createNode('reference',name);n.parm('primpath').set('/'+name);n.parm('filepath1').set('%s/%s'%(ASSETS,file));return n
def script(name,code):
    n=stage.createNode('pythonscript',name);n.parm('python').set(code);return n
GROUND=("from pxr import UsdGeom, Vt, Gf\nstage=hou.pwd().editableStage()\nm=UsdGeom.Mesh.Define(stage,'/World/Ground')\n"
        "m.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(-10,0,-10),Gf.Vec3f(10,0,-10),Gf.Vec3f(10,0,10),Gf.Vec3f(-10,0,10)]));m.CreateFaceVertexCountsAttr(Vt.IntArray([4]));m.CreateFaceVertexIndicesAttr(Vt.IntArray([0,3,2,1]))\n")
BALL="from pxr import UsdGeom\nstage=hou.pwd().editableStage()\nUsdGeom.Sphere.Define(stage,'/ball').CreateRadiusAttr(0.5)\n"
MIXED=("from pxr import UsdGeom, UsdShade, UsdLux, Usd, Sdf\nstage=hou.pwd().editableStage()\n"
       "UsdGeom.Xform.Define(stage,'/Kit');Usd.ModelAPI(stage.GetPrimAtPath('/Kit')).SetKind('group')\n"
       "for nm in ('Post','Plank'):\n    UsdGeom.Cube.Define(stage,'/Kit/'+nm)\n"
       "UsdGeom.Scope.Define(stage,'/Looks');UsdShade.Material.Define(stage,'/Looks/Wood')\n"
       "UsdLux.DistantLight.Define(stage,'/Sun')\n"
       "UsdGeom.Xform.Define(stage,'/Chain');UsdGeom.Xform.Define(stage,'/Chain/Inner');UsdGeom.Sphere.Define(stage,'/Chain/Inner/Orb')\n"
       "g=UsdGeom.Cube.Define(stage,'/Hidden');g.GetPrim().SetActive(False)\n")
ground=script('ground',GROUND)
fir=reference('fir','fir.usda');rock=reference('rock','rock.usda');ball=script('ball',BALL);mixed=script('mixed',MIXED);crate=reference('crate','crate.usda')
merge=stage.createNode('merge','sock2');[merge.setNextInput(x) for x in (fir,rock,ball)]
merge_mixed=stage.createNode('merge','sock3');merge_mixed.setNextInput(mixed)
def node(kind,name,sockets=(None,None,None)):
    n=stage.createNode(kind,name);n.setInput(0,ground)
    for i,s in enumerate(sockets):
        if s is not None:n.setInput(i+1,s)
    return n
def rows(n):
    return [(k,n.evalParm('proto_type%d'%k),n.evalParm('proto_input%d'%k),n.evalParm('proto_inprim%d'%k)) for k in range(1,n.evalParm('protos')+1)]
def library():
    return json.load(open(os.path.join(LIB,'library.json')))['assets'] if os.path.exists(os.path.join(LIB,'library.json')) else []

for label,kind,_ in TYPES:
    mod=None
    # ---- 1 the scan
    n=node(kind,label+'_scan',(merge,merge_mixed,crate));mod=n.hdaModule()
    found=mod.proto_scan(n);paths=[(f['socket'],f['path']) for f in found]
    check(label+' scan: every prototype of the sockets, in socket and stage order',paths[:3]==[(0,'/fir'),(0,'/rock'),(0,'/ball')] and paths[-1]==(2,'/crate'),paths)
    check(label+' scan: a group of kind group gives its children, a single-child chain is followed down',(1,'/Kit/Post') in paths and (1,'/Kit/Plank') in paths and (1,'/Chain/Inner/Orb') in paths,paths)
    check(label+' scan: materials, lights and an inactive prim are skipped',not any(p in ('/Looks','/Looks/Wood','/Sun','/Hidden') for _,p in paths) and len(paths)==7,paths)
    # ---- 2 the bank rows
    n=node(kind,label+'_rows',(merge,None,crate));mod=n.hdaModule()
    first_default=(n.evalParm('protos'),n.evalParm('proto_type1'))
    r=mod.proto_import(n,library=False)
    check(label+' import: one Input Connection row per prototype, the Prim Path set, the blank default row reused',r['added']==[1,2,3,4] and rows(n)==[(1,1,0,'/fir'),(2,1,0,'/rock'),(3,1,0,'/ball'),(4,1,2,'/crate')] and first_default[0]==1,(r,rows(n)))
    check(label+' import: Weight, Scale, Scale Random and Rotation Offset are on the rows at their defaults',all(n.evalParm('proto_weight%d'%k)==1 and n.evalParm('proto_scale%d'%k)==1 and n.evalParm('proto_scalevar%d'%k)==0 and tuple(n.evalParmTuple('proto_rot%d'%k))==(0,0,0) and n.evalParm('proto_on%d'%k)==1 for k in range(1,5)),rows(n))
    n.parm('proto_weight2').set(3.0);n.parm('proto_scale3').set(1.5)
    r2=mod.proto_import(n,library=False)
    check(label+' import: a second click adds nothing and keeps the artist\'s Weight and Scale',r2['added']==[] and sorted(r2['kept'])==[1,2,3,4] and n.evalParm('protos')==4 and n.evalParm('proto_weight2')==3.0 and n.evalParm('proto_scale3')==1.5,(r2,n.evalParm('protos')))
    n.setInput(2,merge_mixed)
    r3=mod.proto_import(n,library=False)
    check(label+' import: a prototype wired in later is added after the rows that are there',len(r3['added'])==3 and n.evalParm('protos')==7 and n.evalParm('proto_inprim5')=='/Kit/Post' and n.evalParm('proto_input5')==1,(r3,rows(n)))
    n.parm('proto_prim1').set('/x') if n.evalParm('proto_type1')==0 else None
    n.parm('proto_type1').set(0);n.parm('proto_prim1').set('/World/Ground')
    n.parm('proto_import_replace').set(1)
    r4=mod.proto_import(n,library=False)
    check(label+' import: Replace The Bank rebuilds the bank from the inputs only',n.evalParm('protos')==7 and all(t==1 for _,t,_,_ in rows(n)) and r4['added']==list(range(1,8)),rows(n))
    n.parm('proto_import_replace').set(0)
    # ---- 3 undo
    n2=node(kind,label+'_undo',(merge,));before=n2.evalParm('protos')
    mod.proto_import(n2,library=False);after=n2.evalParm('protos')
    hou.undos.performUndo()
    check(label+' import: one undo step takes the whole import back',after==3 and n2.evalParm('protos')==before and n2.evalParm('proto_type1')==0,(before,after,n2.evalParm('protos'),n2.evalParm('proto_type1')))
    # ---- 4 the Asset Library
    n3=node(kind,label+'_lib',(merge,));mod=n3.hdaModule()
    pre=library();os.makedirs(LIB,exist_ok=True)
    if not pre:
        data=mod.load_library();mod.add_asset(data,'%s/fir.usda'%ASSETS,name='fir',category='Trees',prim=mod.default_prim_of('%s/fir.usda'%ASSETS));mod.save_library(data)
    rl=mod.proto_import(n3,library=True)
    lib=library();byname={a['name']:a for a in lib}
    check(label+' library: a reference to a file adds that file itself, a procedural prim is written as a standalone file',byname['rock']['file']==ASSETS+'/rock.usda' and byname['rock']['prim']=='/Rock' and os.path.isfile(byname['ball']['file']) and 'prototypes' in byname['ball']['file'] and rl['exported']==['ball'],(rl,[(a['name'],a['file'][-30:]) for a in lib]))
    check(label+' library: new assets are in the category Imported, an asset that was there keeps its category',byname['rock']['category']=='Imported' and byname['fir']['category'] in ('Trees','Imported') and (byname['fir']['category']=='Trees' if not pre else True),[(a['name'],a['category']) for a in lib])
    n4=node(kind,label+'_lib2',(merge,));n4.hdaModule().proto_import(n4,library=True);lib2=library()
    check(label+' library: the same prototypes a second time add no asset and no new file',len(lib2)==len(lib) and sorted(a['file'] for a in lib2)==sorted(a['file'] for a in lib),(len(lib),len(lib2)))
    n5=node(kind,label+'_nolib',(crate,));before_lib=len(library());n5.parm('proto_import_library').set(0);n5.hdaModule().proto_import(n5)
    check(label+' library: the toggle switches the library step off',len(library())==before_lib and n5.evalParm('protos')==1 and n5.evalParm('proto_inprim1')=='/crate',len(library()))
    # ---- 5 the cook
    n6=node(kind,label+'_cook',(merge,crate))
    if kind.startswith('arraytron::instancer'):
        n6.parm('outputpath').set('/World/Cook');n6.parm('mode').set(5);n6.parm('surface_prim').set('/World/Ground');n6.parm('surface_count').set(40)
        if n6.parm('copy_test_ground') is not None:n6.parm('copy_test_ground').set(0)
    else:
        n6.parm('target').set('/World/Ground');n6.parm('outputpath').set('/World/Cook')
    n6.hdaModule().proto_import(n6,library=False)
    errs=n6.errors();st=n6.stage()
    if kind.startswith('arraytron::instancer'):
        from pxr import UsdGeom
        pi=UsdGeom.PointInstancer(st.GetPrimAtPath('/World/Cook'));used=sorted(set(pi.GetProtoIndicesAttr().Get() or []))
        check(label+' cook: no errors, four prototypes, instances use them all',not errs and len(pi.GetPrototypesRel().GetTargets())==4 and len(used)==4,(errs,used))
        summary=n6.parm('proto_summary').eval()
        check(label+' cook: the Resolved Prototypes text lists the imported rows',summary.count('Input Connection')==4 and '/crate' in summary,summary)
    else:
        entries=n6.hdaModule().stamp_entries(n6)
        check(label+' cook: no errors, the four rows resolve to the input prims',not errs and [e['srcs'][0][1] for e in entries]==['/fir','/rock','/ball','/crate'],(errs,[e['srcs'] for e in entries]))
    # ---- 6 errors
    n7=node(kind,label+'_none');mod=n7.hdaModule();msg=''
    try:mod.proto_import(n7)
    except hou.NodeError as exc:msg=exc.instanceMessage() if hasattr(exc,'instanceMessage') else str(exc)
    check(label+' errors: no Prototype Input wired gives a clear message and changes nothing',('No Prototype Input' in msg) and n7.evalParm('protos')==1,msg)
    only_light=script('only_light',"from pxr import UsdLux\nstage=hou.pwd().editableStage()\nUsdLux.DistantLight.Define(stage,'/Sun')\n")
    n8=node(kind,label+'_light',(only_light,));msg=''
    try:n8.hdaModule().proto_import(n8)
    except hou.NodeError as exc:msg=exc.instanceMessage() if hasattr(exc,'instanceMessage') else str(exc)
    check(label+' errors: inputs with nothing drawable give a message and change nothing',('nothing that can be drawn' in msg) and n8.evalParm('protos')==1,msg)
print('ALL PASSED' if not fails else 'FAILED',passed[0],fails)
sys.exit(1 if fails else 0)
