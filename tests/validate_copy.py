"""v1.23.0 Copy settings in real Houdini: hython tests/validate_copy.py [version]
Copies the settings of one Arraytron node onto another (any versions) from code (copy_settings) and with the Import Settings button (import_settings). Expected values come from the source node itself
(every setting parameter equal, the same instances in USD) and from a node of the first release (v0.1.5: one Prototype parameter instead of the bank). Env
ARRAYTRON_MUTATE=copy_counter|copy_alias|copy_readout|copy_auto|copy_keys breaks the module; the suite must FAIL."""
from pathlib import Path
import hou, json, os, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v1.23.0':'v1.22.0','v1.24.0':'v1.23.0','v1.25.0':'v1.24.0','v1.24.0':'v1.23.0','v1.25.0':'v1.24.0'}[VID];LEGACY='v0.1.5'
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS);LEGACY_TYPE=versions.type_name(LEGACY)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_copy_'));MUTATE=os.environ.get('ARRAYTRON_MUTATE');checks=[]
def write_scene():
    path=WORK/'copy.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    for name in ('Ball','BallB','BallC'):UsdGeom.Xform.Define(s,'/World/Props/'+name);UsdGeom.Cube.Define(s,'/World/Props/%s/C'%name).CreateSizeAttr(0.2)
    s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True)
    for v in (VID,PREVIOUS,LEGACY):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
def mutate(node):
    if not MUTATE:return
    g=node.hdaModule().copy_settings.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='copy_counter':g['copy_counters']=lambda node:[]                                                                  # the rows of the Prototype Bank are not made first
    elif MUTATE=='copy_alias':g['COPY_ALIASES']=()                                                                               # the single Prototype of the first releases is lost
    elif MUTATE=='copy_readout':g['copy_is_setting']=lambda parm:True                                                            # buttons and read-outs are copied too
    elif MUTATE=='copy_auto':
        good=g['copy_find_source'];g['copy_find_source']=lambda node:sorted([n for n in node.parent().children() if n!=node and n.type().name().startswith('arraytron::instancer')],key=lambda n:n.name())[-1]
    elif MUTATE=='copy_keys':
        good=g['copy_set'];g['copy_set']=lambda dp,sp,report:(dp.set(sp.eval()),report['copied'].append(dp.name()))                # animation becomes a frozen value
    else:raise SystemExit('unknown mutation '+MUTATE)
def node(stage,source,typ,name,**values):
    a=stage.createNode(typ,name);a.setInput(0,source)
    for k,v in values.items():
        pt=a.parmTuple(k)
        if pt is not None:pt.set(v if isinstance(v,(tuple,list)) else (v,))
        else:a.parm(k).set(v)
    mutate(a) if typ==TYPE else None;return a
def all_errors(n):
    o=list(n.errors())
    for c in n.children():o+=all_errors(c)
    return o
def points(a):
    s=a.stage();assert not all_errors(a),all_errors(a);pi=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')))
    t=hou.frame();ids=np.array(pi.GetIdsAttr().Get(t) or [],dtype=int);o=np.argsort(ids)
    return np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3)[o],np.array(pi.GetProtoIndicesAttr().Get(t) or [],dtype=int)[o]
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()

def legacy_node():
    """A node of the first release as the shots have them: one Prototype, a Line along a custom direction and an Area."""
    st,sc=new_scene('legacy')
    old=node(st,sc,LEGACY_TYPE,'Old',prototype='/World/Props/Ball',outputpath='/World/OldArray',line_axis=3,line_directionx=0.0,line_directionz=-1.0,line_length=100.0,line_center=0,area_sizex=35.01,area_sizez=34.73,area_count=19,area_seed=3)
    new=node(st,sc,TYPE,'New');m=new.hdaModule();assert new.evalParm('line_axis')!=3 and new.evalParm('outputpath')!='/World/OldArray'
    rep=m.import_settings(new,old);assert not rep['failed'] and 'prototype > proto_prim1' in rep['copied'],rep                                  # the explicit source
    assert new.evalParm('protos')==1 and new.evalParm('proto_prim1')=='/World/Props/Ball' and new.evalParm('outputpath')=='/World/OldArray'
    assert (new.evalParm('line_axis'),new.evalParm('line_directionz'),new.evalParm('line_length'),new.evalParm('line_center'),new.evalParm('area_count'),new.evalParm('area_seed'))==(3,-1.0,100.0,0,19,3) and abs(new.evalParm('area_sizex')-35.01)<1e-9
    assert rep['missing']==[] and 'prototype' not in rep['missing'] and new.parm('copy_info').eval().startswith('Imported from /stage/Old (0.15)')
    new.parm('mode').set(1);old.parm('mode').set(1)
    if not versions.is_h205():a=points(old);b=points(new);assert len(a[0])==19 and np.allclose(a[0],b[0],atol=1e-4) and np.array_equal(a[1],b[1])    # the same instances as the old node
    new2=node(st,sc,TYPE,'New2');rep2=new2.hdaModule().import_settings(new2);assert new2.evalParm('proto_prim1')=='/World/Props/Ball' and new2.evalParm('outputpath')=='/World/OldArray'         # found automatically
    back=node(st,sc,LEGACY_TYPE,'Back');rep3=new.hdaModule().copy_settings(back,new);assert 'proto_prim1' in rep3['missing'] and 'protos' in rep3['missing'] and back.evalParm('line_length')==100.0   # the other way: what the old node lacks is reported

def new_to_new():
    st,sc=new_scene('nn')
    src=node(st,sc,OLD_TYPE,'Src',protos=3,mode=1,area_count=40,area_seed=7,outputpath='/World/Cloned',base_scale=1.3,yaw_random=45.0,rows_count=1)
    for i,p in enumerate(('/World/Props/Ball','/World/Props/BallB','/World/Props/BallC'),1):src.parm('proto_prim%d'%i).set(p);src.parm('proto_weight%d'%i).set(float(i))
    src.parm('scale_random_mode').set(1);src.parm('scale_min').set(0.6);src.parm('scale_max').set(1.4);src.parm('bound_tx').set(2.5)
    src.parm('area_sizex').setKeyframe(hou.Keyframe(10.0));k=hou.Keyframe(20.0);k.setTime(hou.frameToTime(24));src.parm('area_sizex').setKeyframe(k)                      # animated
    dst=node(st,sc,TYPE,'Dst');m=dst.hdaModule();rep=m.copy_settings(dst,src)
    assert rep['failed']==[] and rep['missing']==[] and dst.evalParm('protos')==3 and dst.evalParm('proto_prim3')=='/World/Props/BallC' and dst.evalParm('proto_weight2')==2.0,rep
    for sp in src.parms():
        if m.copy_is_setting(sp):
            dp=dst.parm(sp.name());assert dp is not None and dp.eval()==sp.eval() and len(dp.keyframes())==len(sp.keyframes()),sp.name()                                # every setting equal, animation too
    assert len(dst.parm('area_sizex').keyframes())==2
    hou.setFrame(12);ps,pd=points(src),points(dst);assert len(ps[0])==40 and np.allclose(ps[0],pd[0],atol=1e-4) and np.array_equal(ps[1],pd[1])                                # the same instances
    assert dst.evalParm('copy_info')==''                                                                                                                                     # copy_settings does not touch the read-out
    ch=node(st,sc,TYPE,'OnlyChanged',protos=2,proto_prim1='/World/Props/BallC');cr=ch.hdaModule().copy_settings(ch,src,only_changed=True);assert 'tab_source1' not in cr['copied'] and ch.evalParm('protos')==3 and ch.evalParm('area_seed')==7
    keep=node(st,sc,TYPE,'Keep',area_seed=99,line_length=77.0);keep.hdaModule().copy_settings(keep,src,only_changed=True);assert keep.evalParm('line_length')==77.0 and keep.evalParm('area_seed')==7     # defaults of the source do not overwrite
    prm=dst.parmTemplateGroup()
    for n in ('copy_import','copy_source','copy_info'):assert prm.find(n) is not None

def find_source():
    st,sc=new_scene('find');other=st.createNode('null','other');n=node(st,sc,TYPE,'Me');m=n.hdaModule()
    try:m.copy_find_source(n);raise AssertionError('no other node must raise')
    except hou.OperationFailed as exc:assert 'no other Arraytron node' in str(exc)
    plain=node(st,sc,OLD_TYPE,'Plain');busy=node(st,sc,OLD_TYPE,'Busy',area_seed=5,line_length=3.0,mode=1)
    assert m.copy_find_source(n)==busy                                                                                                  # most changed settings
    elsewhere=node(st,other,OLD_TYPE,'Elsewhere',area_seed=5,line_length=3.0,mode=1,area_count=3,outputpath='/x');assert m.copy_find_source(n)==busy                          # wired to the same input first
    n.parm('copy_source').set('../Plain');assert m.copy_find_source(n)==plain                                                               # the Source Node parameter wins
    n.parm('copy_source').set('../Nope')
    try:m.copy_find_source(n);raise AssertionError('missing source must raise')
    except hou.OperationFailed as exc:assert 'does not exist' in str(exc)
    n.parm('copy_source').set('')
    try:m.copy_settings(n,n);raise AssertionError('self copy must raise')
    except hou.OperationFailed:pass
    a=node(st,sc,OLD_TYPE,'A',area_seed=2);b=node(st,sc,TYPE,'B',area_seed=2);c=node(st,sc,OLD_TYPE,'C',area_seed=2)
    for x in (plain,busy,elsewhere):x.destroy()
    assert m.copy_find_source(n) in (a,c,b) and m.copy_find_source(n)!=n and m.copy_version(m.copy_find_source(n))==max(m.copy_version(a),m.copy_version(b),m.copy_version(c))   # equal changes: the newest version

def contract():
    st,sc=new_scene('contract');a=node(st,sc,TYPE,'C');g=a.parmTemplateGroup()
    for n in ('copy_source','copy_import','copy_info'):assert g.find(n) is not None,n
    assert g.find('copy_source').defaultValue()==('',) and 'kwargs' in g.find('copy_import').scriptCallback() and 'import_settings' in g.find('copy_import').scriptCallback()
    assert g.find('copy_info').conditionals()[hou.parmCondType.DisableWhen]=='{ mode >= 0 }'
    tabs=dict((t.label(),[x.name() for x in t.parmTemplates()]) for t in g.entries() if t.type()==hou.parmTemplateType.Folder);names=tabs[versions.tab_names(VID)['source']]
    assert names.index('copy_source')>names.index('outputpath') and names.index('copy_import')>names.index('copy_source')                                                       # at the end of the Prototypes tab
    code=a.type().definition().sections()['PythonModule'].contents();assert 'def copy_settings(' in code and 'def import_settings(' in code and '$' not in code.split('# ---- Copy settings')[1].split('# ----')[0]
    m=a.hdaModule();assert m.copy_is_setting(a.parm('mode')) and not m.copy_is_setting(a.parm('copy_import')) and not m.copy_is_setting(a.parm('copy_info')) and not m.copy_is_setting(a.parm('rows_info'))   # buttons and read-outs are no settings
    assert 'protos' in m.copy_counters(a) and 'ovr_count' in m.copy_counters(a) or 'overrides' in m.copy_counters(a)
    old=node(st,sc,LEGACY_TYPE,'Old');assert old.parm('copy_import') is None

def main():
    for name,func in (('First release: one Prototype becomes row 1 of the bank, every parameter, the same instances; automatic source; the other way is reported',legacy_node),
                      ('New to new: every setting, the bank rows, animation, the same instances; only_changed',new_to_new),
                      ('Automatic source: wired to the same input, most changed settings, newest; Source Node wins; errors',find_source),
                      ('Contract: parameters, button callback, Prototypes tab, read-outs are no settings',contract)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_copy_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
