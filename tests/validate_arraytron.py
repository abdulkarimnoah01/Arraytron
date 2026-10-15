"""Cook the packaged HDA in real Houdini, inspect SOP and composed USD."""
from pathlib import Path
import hou, json, math
from pxr import UsdGeom, Gf
ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0,str(ROOT/'tools'))
import versions
hou.hipFile.load(str(versions.demo('v0.1.0')),suppress_save_prompt=True)
a=hou.node('/stage/Arraytron');checks=[]
def check(name,func):
    func();checks.append(name);print('PASS '+name)
def read():
    s=a.stage()
    assert not a.errors(),a.errors()
    p=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')))
    assert p
    t=hou.frame()
    data={k:getattr(p,'Get'+k+'Attr')().Get(t) for k in ('Positions','Orientations','Scales','Ids','ProtoIndices')}
    n=len(data['Positions'])
    assert all(len(v)==n for v in data.values()),data
    assert list(data['Ids'])==list(range(n))
    assert list(data['ProtoIndices'])==[0]*n
    targets=p.GetPrototypesRel().GetTargets();assert len(targets)==1
    proto=s.GetPrimAtPath(targets[0]);assert proto and proto.HasAuthoredReferences()
    assert UsdGeom.Imageable(proto).ComputeVisibility(t)=='inherited'
    assert UsdGeom.Imageable(s.GetPrimAtPath('/World/Props/Crate')).ComputeVisibility(t)=='invisible'
    assert sum(pr.IsA(UsdGeom.PointInstancer) for pr in s.Traverse())==1
    assert all(math.isfinite(x) for v in data['Positions'] for x in v)
    assert all(math.isfinite(x) and x>0 for v in data['Scales'] for x in v)
    assert all(abs(q.GetLength()-1)<0.005 for q in data['Orientations'])
    extent=p.GetExtentAttr().Get(t);computed=p.ComputeExtentAtTime(t,t)
    assert extent and len(extent)==2 and len(computed)==2
    assert all(abs(extent[j][k]-computed[j][k])<.001 for j in range(2) for k in range(3))
    world=UsdGeom.Xformable(p).ComputeLocalToWorldTransform(t)
    data['WorldPositions']=[world.Transform(Gf.Vec3d(v)) for v in data['Positions']]
    return data
def line_contract():
    for axis in range(3):
        for count in (1,2,10,101):
            for centered in (0,1):
                for length in (0,10):
                    a.parm('line_axis').set(axis);a.parm('line_count').set(count)
                    a.parm('line_center').set(centered);a.parm('line_length').set(length)
                    a.parmTuple('line_offset').set((1,2,3))
                    d=read();assert len(d['Positions'])==count
                    for j,p in enumerate(d['WorldPositions']):
                        expected=[1,2,3]
                        if count>1:expected[axis]+=j*length/(count-1)-(length/2 if centered else 0)
                        assert max(abs(p[k]-expected[k]) for k in range(3))<1e-5
def reset():
    for p in a.parms():
        if p.parmTemplate().type() not in (hou.parmTemplateType.Folder,hou.parmTemplateType.FolderSet):p.revertToDefaults()
def paths():
    reset();a.parm('outputpath').set('/World/Replicas/Test')
    d=read();assert len(d['Positions'])==10
    reset()
def transform():
    reset();a.parmTuple('base_rotation').set((0,90,0));a.parm('base_scale').set(2)
    d=read();q=d['Orientations'][0]
    assert abs(float(q.GetReal())-math.sqrt(.5))<.003
    assert all(tuple(s)==(2,2,2) for s in d['Scales'])
    a.parmTuple('base_rotation').set((20,40,60));d=read()
    expected=hou.Quaternion(hou.hmath.buildRotate((20,40,60)).extractRotationMatrix3())
    actual=d['Orientations'][0];components=tuple(actual.GetImaginary())+(float(actual.GetReal()),)
    assert min(max(abs(components[k]-expected[k]) for k in range(4)),max(abs(components[k]+expected[k]) for k in range(4)))<.003
    a.parmTuple('position_random').set((.1,.2,.3));a.parmTuple('rotation_random').set((45,90,180));a.parm('scale_random').set(.99)
    first=read();second=read();assert first==second
    a.parm('random_seed').set(2);third=read();assert first['Positions']!=third['Positions']
    a.parm('random_seed').set(1);a.parm('line_count').set(12);more=read()
    assert list(first['Scales'])==list(more['Scales'])[:10]
    assert list(first['Orientations'])==list(more['Orientations'])[:10]
    assert all(.0199<=s[0]<=3.9801 for s in more['Scales'])
    reset()
def demo_baseline():
    s=hou.node('/stage/karma_xpu').stage()
    assert hou.node('/stage/reference_test_crate').evalParm('filepath1').endswith('/test_assets/crate.usda')
    for path,count in (('/World/Arraytron',10),('/World/ArraytronArea',60)):
        pi=UsdGeom.PointInstancer(s.GetPrimAtPath(path));assert len(pi.GetPositionsAttr().Get(hou.frame()))==count
        assert UsdGeom.Imageable(s.GetPrimAtPath(pi.GetPrototypesRel().GetTargets()[0])).ComputeVisibility()=='inherited'
if hou.node('/stage/reference_test_crate'):check('Saved reference-asset demo opens with 10 Line and 60 visible Area instances',demo_baseline)
check('48 Line scenarios: axes/counts/center/zero-length/offset, complete USD arrays and extents',line_contract)
check('Editable output path with referenced visible prototype',paths)
check('Quaternion, uniform positive scales, seeded jitter and stable random draws',transform)
def invalid_paths():
    reset()
    for name,value in (('prototype','/World/Missing'),('prototype','/World/Props/*'),('outputpath','relative'),('outputpath','/World/Props'),('outputpath','/World/Props/Crate/Nested'),('outputpath','/World/Props/Crate'),('outputpath','/')):
        a.parm(name).set(value)
        try:a.cook(force=True)
        except hou.OperationFailed:pass
        assert a.errors() or a.stage() is None,(name,value)
        reset();read()
check('Invalid/missing/wildcard/overlapping source and output paths report errors',invalid_paths)
def source_transforms():
    reset();original=a.inputs()[0]
    inject=hou.node('/stage').createNode('pythonscript','test_source_transforms');inject.setInput(0,original)
    inject.parm('python').set('from pxr import UsdGeom, Gf\ns=hou.pwd().editableStage()\nUsdGeom.Xformable(s.GetPrimAtPath("/World/Props")).AddTranslateOp(opSuffix="test_parent").Set(Gf.Vec3d(40,0,0))\nx=UsdGeom.Xformable(s.GetPrimAtPath("/World/Props/Crate"))\nx.AddTranslateOp(opSuffix="test_local").Set(Gf.Vec3d(1,2,3))\nx.AddScaleOp(opSuffix="test_scale").Set(Gf.Vec3f(2,2,2))')
    a.setInput(0,inject);a.parm('line_count').set(1)
    read();s=a.stage();pi=UsdGeom.PointInstancer(s.GetPrimAtPath('/World/Arraytron'))
    matrices=pi.ComputeInstanceTransformsAtTime(hou.frame(),hou.frame())
    assert len(matrices)==1
    m=matrices[0];assert (m.ExtractTranslation()-Gf.Vec3d(1,2,3)).GetLength()<1e-5,m
    assert abs(Gf.Vec3d(m[0][:3]).GetLength()-2)<1e-5,m
    a.setInput(0,original);inject.destroy();reset();read()
check('Source root transform retained once; source parent world placement excluded',source_transforms)
def descendant_visibility():
    reset();original=a.inputs()[0]
    inject=hou.node('/stage').createNode('pythonscript','test_descendant_visibility');inject.setInput(0,original)
    inject.parm('python').set('from pxr import UsdGeom\ns=hou.pwd().editableStage()\nUsdGeom.Imageable(s.GetPrimAtPath("/World/Props/Crate/Body")).CreateVisibilityAttr().Set("invisible")')
    a.setInput(0,inject);read();s=a.stage()
    assert UsdGeom.Imageable(s.GetPrimAtPath('/World/Arraytron/Prototypes/Crate/Body')).ComputeVisibility()=='invisible'
    a.setInput(0,original);inject.destroy();reset()
if hou.node('/stage/reference_test_crate'):check('Prototype root visibility override preserves hidden descendants',descendant_visibility)
def existing_instancer():
    reset();b=hou.node('/stage').createNode(a.type().name(),'test_overwrite');b.setInput(0,a)
    for count in (3,1):
        b.parm('line_count').set(count);s=b.stage();assert not b.errors(),b.errors()
        pi=UsdGeom.PointInstancer(s.GetPrimAtPath('/World/Arraytron'))
        assert len(pi.GetPositionsAttr().Get(hou.frame()))==count
        assert len(pi.GetPrototypesRel().GetTargets())==1
    b.destroy();reset()
check('Existing output PointInstancer overwrite removes old instances',existing_instancer)
def chained():
    reset();b=hou.node('/stage').createNode(a.type().name(),'test_chained');b.setInput(0,a)
    b.parm('mode').set(1);b.parm('outputpath').set('/World/ChainedArea')
    s=b.stage();assert not b.errors(),b.errors()
    for path,count in (('/World/Arraytron',10),('/World/ChainedArea',100)):
        pi=UsdGeom.PointInstancer(s.GetPrimAtPath(path));assert len(pi.GetPositionsAttr().Get(hou.frame()))==count
        prototype=s.GetPrimAtPath(pi.GetPrototypesRel().GetTargets()[0])
        assert UsdGeom.Imageable(prototype).ComputeVisibility(hou.frame())=='inherited'
    b.destroy();reset()
if a.parm('area_count'):check('Chained Line and Area keep both referenced prototypes visible',chained)
if a.parm('area_count'):
    def area_contract():
        reset();a.parm('mode').set(1)
        for count in (1,100,1000):
            for seed in (1,2,77):
                a.parm('area_count').set(count);a.parm('area_seed').set(seed)
                d=read();assert len(d['Positions'])==count
                assert all(-5<=p[0]<=5 and p[1]==0 and -5<=p[2]<=5 for p in d['Positions'])
                assert d==read()
        first=read();a.parm('area_seed').set(78);assert first['Positions']!=read()['Positions']
        a.parm('area_seed').set(77);a.parmTuple('area_offset').set((7,2,-3));offset=read()
        assert all(max(abs(q[k]-p[k]-(7,2,-3)[k]) for k in range(3))<1e-5 for p,q in zip(first['WorldPositions'],offset['WorldPositions']))
        a.parm('area_sizex').set(0);a.parm('area_sizez').set(0)
        assert all(tuple(p)==(7,2,-3) for p in read()['WorldPositions'])
        reset()
    check('Area bounds, counts, deterministic seeds, offset independence and zero size',area_contract)
def layout_transforms():
    # Independent expected SRT with a local pivot; inspect actual composed USD.
    for mode,prefix in ((0,'line'),(1,'area')):
        reset();a.parm('mode').set(mode)
        initial=read();position=hou.Vector3(7,-2,3);rotation=(25,40,15);scale=(2,.5,1.4);pivot=hou.Vector3(1,.25,-.75)
        a.parmTuple(prefix+'_offset').set(tuple(position));a.parmTuple(prefix+'_rotation').set(rotation)
        a.parmTuple(prefix+'_scale').set(scale);a.parmTuple(prefix+'_pivot').set(tuple(pivot))
        actual=read();assert actual['Positions']==initial['Positions']
        sr=hou.hmath.buildScale(scale)*hou.hmath.buildRotate(rotation)
        for local,world in zip(initial['Positions'],actual['WorldPositions']):
            expected=(hou.Vector3(local)-pivot)*sr+pivot+position
            assert max(abs(world[k]-expected[k]) for k in range(3))<1e-5,(mode,world,expected)
        # Whole-layout rotation/scale transforms actual instance geometry too.
        s=a.stage();pi=UsdGeom.PointInstancer(s.GetPrimAtPath('/World/Arraytron'))
        root=UsdGeom.Xformable(pi).ComputeLocalToWorldTransform(hou.frame())
        inst=pi.ComputeInstanceTransformsAtTime(hou.frame(),hou.frame())[0]*root
        assert abs(Gf.Vec3d(inst[0][:3]).GetLength()-2)<1e-5
        assert abs(Gf.Vec3d(inst[1][:3]).GetLength()-.5)<1e-5
        assert abs(Gf.Vec3d(inst[2][:3]).GetLength()-1.4)<1e-5
        reset();a.parm('mode').set(mode);a.parmTuple(prefix+'_pivot').set((9,8,7))
        assert read()['WorldPositions']==initial['WorldPositions']
        a.parmTuple(prefix+'_scale').set((0,-2,2));read()
        s=a.stage();root=UsdGeom.Xformable(s.GetPrimAtPath('/World/Arraytron')).ComputeLocalToWorldTransform(hou.frame())
        assert abs(Gf.Vec3d(root[0][:3]).GetLength()-.0001)<1e-7
        assert abs(Gf.Vec3d(root[1][:3]).GetLength()-.0001)<1e-7
        assert abs(Gf.Vec3d(root[2][:3]).GetLength()-2)<1e-5
    reset()
def custom_direction():
    reset();a.parm('line_axis').set(3)
    for vector in ((1,2,-3),(-5,0,0),(0,0,0)):
        for centered in (0,1):
            for length in (0,.4,11.5):
                a.parm('line_center').set(centered);a.parm('line_length').set(length)
                a.parmTuple('line_direction').set(vector);d=read()
                direction=hou.Vector3(vector).normalized() if hou.Vector3(vector).length()>1e-6 else hou.Vector3(1,0,0)
                assert (hou.Vector3(d['Positions'][-1])-hou.Vector3(d['Positions'][0])-direction*length).length()<1e-5
                start=-direction*length*.5 if centered else hou.Vector3(0,0,0)
                assert (hou.Vector3(d['Positions'][0])-start).length()<1e-5
    a.parm('line_count').set(1);a.parmTuple('line_offset').set((2,3,4))
    assert tuple(read()['WorldPositions'][0])==(2,3,4)
    reset()
check('Custom normalized Line direction, reverse direction, zero-vector fallback and single point',custom_direction)
if a.parm('area_count'):check('Whole Line/Area position, XYZ rotation/scale, local pivot and geometry transforms',layout_transforms)
reset()
versions.validation_json('v0.1.0').write_text(json.dumps({'houdini':hou.applicationVersionString(),'checks':checks,'passed':True},indent=2))
