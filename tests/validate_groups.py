"""v1.29.0 Prototype Bank source type Group Children in real Houdini: hython tests/validate_groups.py [version]
A row of type Group Children stands for every child prim of a group (Prim Path /Group/* or /Group, or a name pattern like /Group/r*): resolve() gives one entry per child, all with the row number, the
PointInstancer gets one prototype per child, and the row's Weight, Scale and Rotation apply to each. Expected values are computed from the same stage and the same ids. Env ARRAYTRON_MUTATE=gr_all|gr_pattern|
gr_row|gr_expand|gr_scale breaks the module; the suite must FAIL."""
from pathlib import Path
import hou, json, os, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom, Gf
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v1.38.3':'v1.38.2','v1.38.2':'v1.38.1','v1.38.1':'v1.38.0','v1.38.0':'v1.37.0','v1.37.0':'v1.36.0','v1.36.0':'v1.35.0','v1.35.0':'v1.34.1','v1.34.1':'v1.34.0','v1.34.0':'v1.33.0','v1.33.0':'v1.32.0','v1.32.0':'v1.31.1','v1.31.1':'v1.31.0','v1.31.0':'v1.30.1','v1.30.1':'v1.30.0','v1.30.0':'v1.29.0','v1.29.0':'v1.28.0'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_groups_'));checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')
def write_scene():
    path=WORK/'groups.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    UsdGeom.Xform.Define(s,'/World/Props/Tree');UsdGeom.Cube.Define(s,'/World/Props/Tree/C').CreateSizeAttr(0.2)
    UsdGeom.Xform.Define(s,'/World/Group')
    for name,size in (('Rock',0.2),('Fir',0.3),('Stone',0.4),('Reed',0.1)):
        UsdGeom.Xform.Define(s,'/World/Group/'+name);UsdGeom.Cube.Define(s,'/World/Group/%s/C'%name).CreateSizeAttr(size)
    s.DefinePrim('/World/Group/Mat','Material');UsdGeom.Xform.Define(s,'/World/Group/Off').GetPrim().SetActive(False);UsdGeom.Xform.Define(s,'/World/Group/Fir/Deep')       # not drawable / inactive / deeper: never prototypes
    UsdGeom.Xform.Define(s,'/World/Other/Pine');UsdGeom.Cube.Define(s,'/World/Other/Pine/C').CreateSizeAttr(0.2)
    s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
def install():
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True);install();hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
def scatter(stage,source,rows,typ=None,name='Gr',**values):
    """rows: list of dicts (type, prim, weight, scale ...) for the Prototype Bank."""
    a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(len(rows));a.parm('mode').set(1);a.parmTuple('area_sizex').set((10.0,));a.parmTuple('area_sizez').set((10.0,));a.parm('area_count').set(600);a.parm('area_seed').set(3)
    for i,r in enumerate(rows,1):
        for key,v in r.items():
            parm={'type':'proto_type','prim':'proto_prim','weight':'proto_weight','scale':'proto_scale','on':'proto_on','lod1':'proto_lod1'}[key]
            a.parm('%s%d'%(parm,i)).set(v)
    for k,v in values.items():a.parm(k).set(v)
    if typ is None:mutate(a)
    return a
def out(a):
    s=a.stage();assert not list(a.errors()),a.errors();pi=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    d=dict(pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3),ids=np.array(pi.GetIdsAttr().Get(t) or [],dtype=int),proto=np.array(pi.GetProtoIndicesAttr().Get(t) or [],dtype=int),scale=np.array(pi.GetScalesAttr().Get(t) or []).reshape(-1,3),
           targets=[p.pathString for p in pi.GetPrototypesRel().GetTargets()])
    o=np.argsort(d['ids']);return {k:(v[o] if k!='targets' else v) for k,v in d.items()}
def mutate(a):
    g=a.hdaModule().resolve.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='gr_all':
        import fnmatch;good=g['group_children']
        def bad(asset,row,text):
            stage=g['stream_stage'](asset);group=stage.GetPrimAtPath(text.strip().rstrip('/*') or '/');return [c.GetPath().pathString for c in group.GetChildren()]                              # inactive and not drawable children too
        g['group_children']=bad
    elif MUTATE=='gr_pattern':
        good=g['group_children'];g['group_children']=lambda asset,row,text:good(asset,row,text.rstrip('/*?').rsplit('/',1)[0]+'/*' if '*' in text.rsplit('/',1)[1] or '?' in text.rsplit('/',1)[1] else text)        # the name pattern is ignored
    elif MUTATE=='gr_row':
        good=g['resolve'];g['resolve']=lambda asset:[dict(e,row=e['row']+(e.get('child',0) if e.get('group') else 0)) for e in good(asset)]                                                     # a child carries its own number, not the row's
    elif MUTATE=='gr_expand':g['sop_proto_expand']=lambda geo,asset:None                                                                                                                       # the assignment is not told the rows of the prototypes
    elif MUTATE=='gr_scale':
        good=g['group_children'];g['group_children']=lambda asset,row,text:good(asset,row,text)[:1]                                                                                           # only the first child
    elif MUTATE:raise SystemExit('unknown mutation '+MUTATE)
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()
GROUP=dict(type=4,prim='/World/Group/*');TREE=dict(type=0,prim='/World/Props/Tree')
NAMES=['/World/Group/Rock','/World/Group/Fir','/World/Group/Stone','/World/Group/Reed']

def resolving():
    st,sc=new_scene('resolve');a=scatter(st,sc,[GROUP]);m=a.hdaModule();e=m.resolve(a)
    assert [x['path'] for x in e]==NAMES and all(x['group'] and x['row']==1 and x['type']==4 for x in e) and [x['child'] for x in e]==[0,1,2,3]                                              # the four drawable, active children, in stage order (not Mat, Off, Deep)
    assert m.pattern(a).split()==NAMES
    s=m.summary(a);assert s.count('Group Children')==4 and '(child 1)' in s and '(child 4)' in s and '/World/Group/Stone' in s and '[row 1]' in s
    for text,want in (('/World/Group',NAMES),('/World/Group/',NAMES),('/World/Group/R*',['/World/Group/Rock','/World/Group/Reed']),('/World/Group/?ir',['/World/Group/Fir']),('/World/Group/[RS]*',['/World/Group/Rock','/World/Group/Stone','/World/Group/Reed']),('/World/Other/*',['/World/Other/Pine'])):
        a.parm('proto_prim1').set(text);assert [x['path'] for x in m.resolve(a)]==want,(text,[x['path'] for x in m.resolve(a)])                                                         # a group, with or without /*, and name patterns
    for text,err in (('/World/Nothing/*','does not exist'),('/World/Group/zzz*','no active prim'),('','empty')):
        a.parm('proto_prim1').set(text)
        try:m.resolve(a);assert False,text
        except hou.NodeError as ex:assert err in str(ex) and 'Prototype 1' in str(ex),(text,str(ex))
    a.parm('proto_prim1').set('/World/Group/*');a.parm('outputpath').set('/World/Group/Arraytron');assert [x['path'] for x in m.resolve(a)]==NAMES                                              # the output prim inside the group is not a prototype
    a.parm('outputpath').set('/World/Group/Rock/Arraytron');assert [x['path'] for x in m.resolve(a)]==NAMES[1:]
    b=scatter(st,sc,[TREE,GROUP],name='Mixed');mb=b.hdaModule();eb=mb.resolve(b);assert [x['path'] for x in eb]==['/World/Props/Tree']+NAMES and [x['row'] for x in eb]==[1,2,2,2,2] and not eb[0].get('group')   # a normal row and a group row
    c=scatter(st,sc,[GROUP,GROUP],name='Twice')
    try:c.hdaModule().resolve(c);assert False
    except hou.NodeError as ex:assert 'resolve to the same prim' in str(ex)                                                                                                                  # the same children twice are refused as before
    d=scatter(st,sc,[dict(GROUP,on=0),TREE],name='Off');assert [x['path'] for x in d.hdaModule().resolve(d)]==['/World/Props/Tree']                                                          # a disabled group row adds nothing

def cooking():
    st,sc=new_scene('cook');a=scatter(st,sc,[GROUP],proto_mode=3);o=out(a);assert len(o['ids'])==600 and [t.rsplit('/',1)[1] for t in o['targets']]==['Rock','Fir','Stone','Reed']
    assert np.array_equal(o['proto'],o['ids']%4) and not a.errors()                                                                                                                              # Cycle: the four children take turns
    r=scatter(st,sc,[GROUP],name='Rand',proto_mode=0);orr=out(r);counts=np.bincount(orr['proto'],minlength=4);assert (counts>600*0.18).all() and (counts<600*0.32).all()                           # Random: each child about a quarter
    w=scatter(st,sc,[dict(TREE,weight=4.0),dict(GROUP,weight=1.0)],name='Weighted',proto_mode=1,proto_seed=2);ow=out(w);cw=np.bincount(ow['proto'],minlength=5)/600.0
    assert len(ow['targets'])==5 and abs(cw[0]-4.0/8.0)<0.07 and all(abs(cw[k]-1.0/8.0)<0.05 for k in range(1,5)),cw                                                                           # row weights are per prototype: 4 : 1 : 1 : 1 : 1
    sw=scatter(st,sc,[dict(TREE),dict(GROUP,scale=2.0)],name='Scaled',proto_mode=3);os_=out(sw)
    base=out(scatter(st,sc,[dict(TREE),dict(GROUP,scale=1.0)],name='Unscaled',proto_mode=3));hero=os_['proto']==0;assert hero.sum()>100 and np.allclose(os_['scale'][~hero]/base['scale'][~hero],2.0) and np.allclose(os_['scale'][hero],base['scale'][hero])   # the row's Scale applies to every child, not to the others
    assert np.array_equal(os_['pos'],base['pos'])                                                                                                                                                # positions never depend on the prototypes
    one=scatter(st,sc,[dict(GROUP,prim='/World/Group/Rock')],name='One');oo=out(one);assert len(oo['targets'])==1 and (oo['proto']==0).all()                                                     # a pattern that matches one child: a single prototype
    ids=out(scatter(st,sc,[TREE],name='Plain',proto_mode=3)); same=out(scatter(st,sc,[dict(TREE,type=0)],name='Plain2',proto_mode=3));assert np.array_equal(ids['pos'],same['pos'])

def related():
    """The things that name a bank row: LOD prims (a group row has none), Biome mixes / Place / Overrides take the first child, the primvars."""
    st,sc=new_scene('related');a=scatter(st,sc,[dict(TREE,lod1='/World/Other/Pine'),dict(GROUP,lod1='/World/Other/Pine')],proto_mode=3);m=a.hdaModule()
    assert [(r,l) for r,l,p in m.lod_entries(a)]==[(1,1)]                                                                                                                                        # the LOD prim of the group row is ignored
    o=out(a);assert len(o['targets'])==6 and not a.errors() and o['targets'][-1].endswith('Pine')                                                                                                 # 1 + 4 heroes, then the one LOD prim
    t=m.lod_table(a);assert t[0]=={1:5} and all(t[k]=={} for k in range(1,5))
    g=scatter(st,sc,[TREE,GROUP],name='Over',proto_mode=3);mg=g.hdaModule();ords={};[ords.setdefault(r,k) for k,r in enumerate([e['row'] for e in mg.resolve(g)])];assert ords=={1:0,2:1}                  # a row number names the first child of a group row

def contract():
    st,sc=new_scene('contract');a=scatter(st,sc,[TREE]);g=a.parmTemplateGroup()
    assert g.find('proto_type#').menuLabels()==('Prim Path','Input Connection','USD File','SOP Geometry','Group Children') and g.find('proto_type#').defaultValue()==0 and a.evalParm('proto_type1')==0
    assert g.find('proto_prim#').conditionals()[hou.parmCondType.HideWhen]=='{ proto_type# != 0 proto_type# != 4 }' and 'Group Children' in g.find('proto_type#').help() and '/Group/*' in g.find('proto_prim#').help()
    for n in ('group_children','stream_stage','sop_proto_expand','resolve'):assert hasattr(a.hdaModule(),n),n
    inst=a.node('USD_COMPILER');assert inst.node('PROTO_EXPAND') is not None and inst.node('PROTOTYPE_ASSIGNMENT').inputs()[0].name()=='PROTO_EXPAND' and inst.node('PROTO_EXPAND').inputs()[0].name()=='VARIATION_PROCESSOR'
    snippet=inst.node('PROTOTYPE_ASSIGNMENT').parm('snippet').eval();assert 'pe_row' in snippet and 'foreach (int r; pe_row)' in snippet
    text_=a.type().definition().sections()['PythonModule'].contents();assert '$' not in text_.split('# ---- Group Children prototypes')[1] and 'TYPE_GROUP' in text_
    geo=inst.node('PROTO_EXPAND').geometry();assert geo.findGlobalAttrib('pe_row') is not None and list(geo.intListAttribValue('pe_row'))==[1]                                                       # the array of a normal bank: the rows themselves

def unchanged():
    st,sc=new_scene('same');rows=[dict(TREE,weight=2.0),dict(type=0,prim='/World/Other/Pine',weight=1.0,scale=1.5)]
    pa=out(scatter(st,sc,rows,proto_mode=1,proto_seed=4));ob=scatter(st,sc,rows,typ=OLD_TYPE,name='Old',proto_mode=1,proto_seed=4);pb=out(ob)
    assert len(pa['ids'])==600 and np.array_equal(pa['ids'],pb['ids']) and np.array_equal(pa['pos'],pb['pos']) and np.array_equal(pa['proto'],pb['proto']) and np.array_equal(pa['scale'],pb['scale']) and pa['targets']==pb['targets']   # no group row: the previous release exactly

def main():
    for name,func in (('Resolving: children in stage order, drawable and active only, /Group, /Group/* and name patterns, errors, the output prim, mixed with normal rows, duplicates, disabled',resolving),
                      ('Cooking: one prototype per child, Cycle, Random, row weights per prototype (4 : 1 : 1 : 1 : 1), the row Scale on every child, positions unchanged',cooking),
                      ('Related: no LODs for a group row, a row number names the first child',related),
                      ('Contract: menu, conditionals, help, module functions, PROTO_EXPAND before the assignment, the VEX, no dollar signs',contract),
                      ('The previous release unchanged without a group row',unchanged)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_groups_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
