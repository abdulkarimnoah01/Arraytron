"""v1.25.0 Test setup in real Houdini: hython tests/validate_testsetup.py [version]
A new Arraytron node made in the interface is a working test run: the built-in sphere (a USD file inside the HDA) scattered on a Grid. The hook runs only when the interface is available, so scripts and tests
that create nodes get the plain defaults. test_setup(node) is the function the hook calls: it acts only on a node with nothing wired in that is still at its defaults. Env
ARRAYTRON_MUTATE=ts_inputs|ts_changed|ts_mode|ts_path breaks the module; the suite must FAIL."""
from pathlib import Path
import hou, json, os, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
TYPE=versions.type_name(VID);MUTATE=os.environ.get('ARRAYTRON_MUTATE');checks=[];WORK=Path(tempfile.mkdtemp(prefix='arraytron_testsetup_'))
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True);hou.hda.installFile(str(versions.hda(VID)),force_use_assets=True);hou.hipFile.save(str(WORK/(name+'.hip')));return hou.node('/stage')
def mutate(a):
    if not MUTATE:return
    g=a.hdaModule().test_setup.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='ts_inputs':
        src=g['test_setup'];code="def test_setup(node):\n    node.parm('proto_type1').set(2);node.parm('proto_file1').set(builtin_sphere_path(node));node.parm('proto_fileprim1').set('');node.parm('mode').set(2);return True\n";exec(code,g)
    elif MUTATE=='ts_changed':
        code="def test_setup(node):\n    if node.parm('proto_type1') is None or any(node.inputs()):return False\n    node.parm('proto_type1').set(2);node.parm('proto_file1').set(builtin_sphere_path(node));node.parm('proto_fileprim1').set('');node.parm('mode').set(2);return True\n";exec(code,g)
    elif MUTATE=='ts_mode':
        code="def test_setup(node):\n    if node.parm('proto_type1') is None or any(node.inputs()):return False\n    if not all(p.isAtDefault() for p in node.parms() if p.name() not in ('copy_info',) and not p.name().startswith('viz_ramp')):return False\n    node.parm('proto_type1').set(2);node.parm('proto_file1').set(builtin_sphere_path(node));node.parm('proto_fileprim1').set('');return True\n";exec(code,g)
    elif MUTATE=='ts_path':g['BUILTIN_SPHERE']='missing.usda'
    else:raise SystemExit('unknown mutation '+MUTATE)
def all_errors(n):
    o=list(n.errors())
    for c in n.children():o+=all_errors(c)
    return o
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()

def spawn():
    st=new_scene('spawn');a=st.createNode(TYPE,'A');assert a.evalParm('mode')==0 and a.evalParm('proto_type1')==0                      # a script or a test gets the plain defaults
    mutate(a);m=a.hdaModule();assert m.test_setup(a) is True and a.evalParm('mode')==2 and a.evalParm('proto_type1')==2 and a.evalParm('proto_file1').startswith('opdef:/') and a.evalParm('proto_file1').endswith('?builtin_sphere.usda')
    s=a.stage();assert not all_errors(a),all_errors(a);pi=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')));assert pi
    pos=np.array(pi.GetPositionsAttr().Get(hou.frame())).reshape(-1,3);assert len(pos)==25 and abs(np.ptp(pos[:,0])-10.0)<1e-4 and np.allclose(pos[:,1],0)                  # the default 5 x 5 grid over 10 x 10 units
    protos=pi.GetPrototypesRel().GetTargets();assert len(protos)==1;proto=s.GetPrimAtPath(protos[0]);spheres=[p for p in Usd.PrimRange(proto,Usd.TraverseInstanceProxies(Usd.PrimDefaultPredicate)) if p.IsA(UsdGeom.Sphere)]
    assert len(spheres)==1 and abs(UsdGeom.Sphere(spheres[0]).GetRadiusAttr().Get()-0.5)<1e-9                                                                                # the built-in sphere
    sec=a.type().definition().sections()[ 'builtin_sphere.usda'].contents();layer=Usd.Stage.CreateInMemory();assert layer.GetRootLayer().ImportFromString(sec) and layer.GetDefaultPrim().GetName()=='Sphere'
    hook=a.type().definition().sections()['OnCreated'].contents();assert 'isUIAvailable' in hook and 'test_setup' in hook                                                       # only in the interface

def only_new():
    st=new_scene('new');ground=st.createNode('null','ground');a=st.createNode(TYPE,'Wired');a.setInput(0,ground);mutate(a);m=a.hdaModule()
    assert m.test_setup(a) is False and a.evalParm('mode')==0 and a.evalParm('proto_type1')==0                                                                              # something is wired in
    b=st.createNode(TYPE,'Changed');b.parm('line_count').set(7);assert m.test_setup(b) is False and b.evalParm('mode')==0 and b.evalParm('proto_type1')==0                      # a setting was changed
    c=st.createNode(TYPE,'Again');assert m.test_setup(c) is True and m.test_setup(c) is False                                                                              # twice does nothing more
    d=st.createNode(TYPE,'Prim');d.parm('proto_prim1').set('/World/Props/Rock');assert m.test_setup(d) is False                                                          # a prototype was typed

def main():
    for name,func in (('A new node with nothing wired in becomes a 5 x 5 grid of built-in spheres, no errors, only in the interface',spawn),
                      ('Only a new node: not when something is wired in, not when a setting was changed, not twice',only_new)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_testsetup_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
