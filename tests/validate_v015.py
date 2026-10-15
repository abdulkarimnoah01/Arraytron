"""Cook the v0.15 HDA in real Houdini: UI contract, shared Bounds Transform, guide, handle, USD output.
Run with hython. Does not save the HIP."""
from pathlib import Path
import hou, json, math, re
from pxr import UsdGeom, Gf
ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0,str(ROOT/'tools'))
import versions
hou.hipFile.load(str(versions.demo('v0.1.5')),suppress_save_prompt=True)
a=hou.node('/stage/Arraytron');checks=[]
GUIDE='/World/Arraytron/Bounds_Guide'
def check(name,func):
    func();checks.append(name);print('PASS '+name)
def reset():
    for p in a.parms():
        if p.parmTemplate().type() not in (hou.parmTemplateType.Folder,hou.parmTemplateType.FolderSet):p.revertToDefaults()
def read():
    s=a.stage();assert not a.errors(),a.errors()
    p=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')));assert p
    t=hou.frame()
    data={k:getattr(p,'Get'+k+'Attr')().Get(t) for k in ('Positions','Orientations','Scales','Ids','ProtoIndices')}
    n=len(data['Positions']);assert all(len(v)==n for v in data.values())
    assert list(data['Ids'])==list(range(n)) and list(data['ProtoIndices'])==[0]*n
    targets=p.GetPrototypesRel().GetTargets();assert len(targets)==1
    assert UsdGeom.Imageable(s.GetPrimAtPath(targets[0])).ComputeVisibility(t)=='inherited'
    assert sum(pr.IsA(UsdGeom.PointInstancer) for pr in s.Traverse())==1
    extent=p.GetExtentAttr().Get(t);computed=p.ComputeExtentAtTime(t,t)
    assert all(abs(extent[j][k]-computed[j][k])<.001 for j in range(2) for k in range(3))
    world=UsdGeom.Xformable(p).ComputeLocalToWorldTransform(t)
    data['WorldPositions']=[world.Transform(Gf.Vec3d(v)) for v in data['Positions']]
    data['Stage']=s
    return data
def close(u,v,tol=1e-5): return max(abs(u[k]-v[k]) for k in range(3))<tol

def ui_contract():
    g=a.parmTemplateGroup()
    # Folder conditionals compare against numbers, so every menu they read must use numeric tokens.
    for name in ('mode','line_axis'):
        t=g.find(name);assert t.menuItems()==tuple(str(i) for i in range(len(t.menuItems()))),(name,t.menuItems())
    assert g.find('mode').menuLabels()==('Line','Area')
    assert g.find('line_axis').menuLabels()==('X','Y','Z','Custom')
    cond={n:g.find(n).conditionals()[hou.parmCondType.HideWhen] for n in ('line','area','line_direction')}
    assert cond=={'line':'{ mode != 0 }','area':'{ mode != 1 }','line_direction':'{ line_axis != 3 }'},cond
    # Every artist-facing parm must live in a visible top-level folder.
    labels=[e.label() for e in g.entries()]
    assert labels==['Source','Distribution','Line','Area','Bounds Transform','Instance Transform','Randomize'],labels
    bounds=[t.name() for t in g.find('bounds').parmTemplates()]
    assert bounds==['bound_t','bound_r','bound_s','bound_p','show_bounds','reset_bounds'],bounds
    assert g.find('bound_r').minValue()==-180 and g.find('bound_r').maxValue()==180
    for name in ('prototype','outputpath'):assert g.find(name).tags().get('sidefx::usdpathtype')=='prim'
def spacing_display():
    reset();g=a.parmTemplateGroup()
    assert [t.name() for t in g.find('line').parmTemplates()]==['line_axis','line_direction','line_count','line_length','line_center','line_spacing']
    assert g.find('line_spacing').conditionals()[hou.parmCondType.DisableWhen]=='{ line_count > 0 }'
    for count,length in ((1,10),(2,10),(10,18),(101,10),(5,0)):
        a.parm('line_count').set(count);a.parm('line_length').set(length)
        expected=length/(count-1) if count>1 else 0
        assert abs(a.parm('line_spacing').eval()-expected)<1e-9,(count,length)
        d=read()['Positions']
        if count>1:assert abs((hou.Vector3(d[1])-hou.Vector3(d[0])).length()-a.parm('line_spacing').eval())<1e-5
    reset();assert a.parm('line_spacing').eval()==10/9
def handle_binding():
    text=a.type().definition().sections()['DialogScript'].contents()
    lines=re.findall(r'^\s*bindhandle (\w+) lopxform "Transformer" (\w+) ""',text,re.M)
    expected=[(f'bound_{g}{x}',f'{g}{x}') for g in 'trsp' for x in 'xyz']
    assert sorted(lines)==sorted(expected),lines
    for parm,_ in lines:assert a.parm(parm),parm
def line_contract():
    reset()
    for axis in range(3):
        for count in (1,2,10,101):
            for centered in (0,1):
                for length in (0,10):
                    a.parm('line_axis').set(axis);a.parm('line_count').set(count)
                    a.parm('line_center').set(centered);a.parm('line_length').set(length)
                    a.parmTuple('bound_t').set((1,2,3))
                    d=read();assert len(d['Positions'])==count
                    for j,p in enumerate(d['WorldPositions']):
                        expected=[1,2,3]
                        if count>1:expected[axis]+=j*length/(count-1)-(length/2 if centered else 0)
                        assert close(p,expected),(axis,count,centered,length,j,p,expected)
    reset()
def custom_direction():
    reset();a.parm('line_axis').set(3)
    for vector in ((1,2,-3),(-5,0,0),(0,0,0)):
        for centered in (0,1):
            for length in (0,.4,11.5):
                a.parm('line_center').set(centered);a.parm('line_length').set(length);a.parmTuple('line_direction').set(vector)
                d=read();v=hou.Vector3(vector);direction=v.normalized() if v.length()>1e-6 else hou.Vector3(1,0,0)
                assert (hou.Vector3(d['Positions'][-1])-hou.Vector3(d['Positions'][0])-direction*length).length()<1e-5
                start=-direction*length*.5 if centered else hou.Vector3(0,0,0)
                assert (hou.Vector3(d['Positions'][0])-start).length()<1e-5
    reset()
def area_contract():
    reset();a.parm('mode').set(1)
    for count in (1,100,1000):
        for seed in (1,2,77):
            a.parm('area_count').set(count);a.parm('area_seed').set(seed)
            d=read();assert len(d['Positions'])==count
            assert d['Positions']==read()['Positions'],'same seed must give same points'
            assert all(-5<=p[0]<=5 and p[1]==0 and -5<=p[2]<=5 for p in d['Positions'])
    first=read();a.parm('area_seed').set(78);assert first['Positions']!=read()['Positions']
    a.parm('area_seed').set(77);a.parmTuple('bound_t').set((7,2,-3));moved=read()
    assert all(close(q,tuple(p[k]+(7,2,-3)[k] for k in range(3))) for p,q in zip(first['WorldPositions'],moved['WorldPositions']))
    a.parm('area_sizex').set(0);a.parm('area_sizez').set(0)
    assert all(tuple(p)==(7,2,-3) for p in read()['WorldPositions'])
    reset()
def bounds_transform():
    # Shared transform: identical expected SRT-about-pivot result in Line mode and in Area mode.
    for mode in (0,1):
        reset();a.parm('mode').set(mode)
        initial=read();position=hou.Vector3(7,-2,3);rotation=(25,40,15);scale=(2,.5,1.4);pivot=hou.Vector3(1,.25,-.75)
        a.parmTuple('bound_t').set(tuple(position));a.parmTuple('bound_r').set(rotation)
        a.parmTuple('bound_s').set(scale);a.parmTuple('bound_p').set(tuple(pivot))
        actual=read();assert actual['Positions']==initial['Positions'],'transform must not touch local points'
        sr=hou.hmath.buildScale(scale)*hou.hmath.buildRotate(rotation)
        for local,world in zip(initial['Positions'],actual['WorldPositions']):
            expected=(hou.Vector3(local)-pivot)*sr+pivot+position
            assert close(world,expected),(mode,world,expected)
        pi=UsdGeom.PointInstancer(actual['Stage'].GetPrimAtPath('/World/Arraytron'))
        root=UsdGeom.Xformable(pi).ComputeLocalToWorldTransform(hou.frame())
        inst=pi.ComputeInstanceTransformsAtTime(hou.frame(),hou.frame())[0]*root
        for row,factor in ((0,2),(1,.5),(2,1.4)):assert abs(Gf.Vec3d(inst[row][:3]).GetLength()-factor)<1e-5
        reset();a.parm('mode').set(mode);a.parmTuple('bound_p').set((9,8,7))
        assert read()['WorldPositions']==initial['WorldPositions'],'pivot alone must not move an identity transform'
        a.parmTuple('bound_s').set((0,-2,2));read()
        root=UsdGeom.Xformable(a.stage().GetPrimAtPath('/World/Arraytron')).ComputeLocalToWorldTransform(hou.frame())
        assert abs(Gf.Vec3d(root[0][:3]).GetLength()-.0001)<1e-7 and abs(Gf.Vec3d(root[2][:3]).GetLength()-2)<1e-5
    reset()
def mode_switch_keeps_transform():
    reset();a.parmTuple('bound_t').set((3,1,-2));a.parmTuple('bound_r').set((0,30,0))
    line=read()['WorldPositions'];a.parm('mode').set(1);area=read()
    root=UsdGeom.Xformable(area['Stage'].GetPrimAtPath('/World/Arraytron')).ComputeLocalToWorldTransform(hou.frame())
    assert close(root.ExtractTranslation(),(3,1,-2)),'Area must inherit the same Bounds Transform'
    a.parm('mode').set(0);assert read()['WorldPositions']==line
    reset()
def reset_button():
    reset();a.parmTuple('bound_t').set((1,2,3));a.parmTuple('bound_r').set((4,5,6));a.parmTuple('bound_s').set((2,2,2));a.parmTuple('bound_p').set((7,8,9))
    a.parm('reset_bounds').pressButton()
    assert a.parmTuple('bound_t').eval()==(0,0,0) and a.parmTuple('bound_r').eval()==(0,0,0)
    assert a.parmTuple('bound_s').eval()==(1,1,1) and a.parmTuple('bound_p').eval()==(0,0,0)
def guide_points(stage,name):
    c=UsdGeom.BasisCurves(stage.GetPrimAtPath(GUIDE+'/'+name));assert c,name
    pts=c.GetPointsAttr().Get();counts=c.GetCurveVertexCountsAttr().Get()
    out=[];i=0
    for n in counts:out.append([hou.Vector3(*pts[i+k]) for k in range(n)]);i+=n
    return out
def guide():
    reset();d=read();s=d['Stage']
    g=s.GetPrimAtPath(GUIDE);assert g and g.IsActive()
    for path in (GUIDE,GUIDE+'/Bounds',GUIDE+'/Pivot'):
        assert UsdGeom.Imageable(s.GetPrimAtPath(path)).ComputePurpose()=='guide',path
    # Line 10 / length 10 / centered X: main segment spans -5..5, ten ticks, arrow head, three pivot axes.
    curves=guide_points(s,'Bounds');assert len(curves)==2+10
    assert (curves[0][0]-hou.Vector3(-5,0,0)).length()<1e-5 and (curves[0][1]-hou.Vector3(5,0,0)).length()<1e-5
    assert len(guide_points(s,'Pivot'))==3
    a.parm('line_center').set(0);a.parm('line_axis').set(2)
    curves=guide_points(read()['Stage'],'Bounds')
    assert (curves[0][0]-hou.Vector3(0,0,0)).length()<1e-5 and (curves[0][1]-hou.Vector3(0,0,10)).length()<1e-5
    # The guide follows the pivot marker and rides under the transformed instancer.
    a.parmTuple('bound_p').set((1,2,3));pivots=guide_points(read()['Stage'],'Pivot')
    assert (pivots[0][0]+pivots[0][1])/2==hou.Vector3(1,2,3) and (pivots[2][0]+pivots[2][1])/2==hou.Vector3(1,2,3)
    reset();a.parm('mode').set(1);a.parm('area_sizex').set(8);a.parm('area_sizez').set(4)
    rect=guide_points(read()['Stage'],'Bounds');assert len(rect)==1 and len(rect[0])==5
    xs=sorted({round(p[0],5) for p in rect[0]});zs=sorted({round(p[2],5) for p in rect[0]})
    assert xs==[-4,4] and zs==[-2,2] and rect[0][0]==rect[0][-1] and all(p[1]==0 for p in rect[0])
    a.parm('show_bounds').set(0);off=read()['Stage'].GetPrimAtPath(GUIDE)
    assert not off or not off.IsActive(),'guide must be inactive when toggled off'
    a.parm('show_bounds').set(1);assert read()['Stage'].GetPrimAtPath(GUIDE).IsActive()
    reset()
def guide_not_in_prototype_or_render_purpose():
    s=hou.node('/stage/karma_xpu').stage()
    rs=s.GetPrimAtPath('/Render/karma_xpu');assert 'guide' not in list(rs.GetAttribute('includedPurposes').Get())
    assert UsdGeom.Imageable(s.GetPrimAtPath(GUIDE)).ComputePurpose()=='guide'
def paths_and_overwrite():
    reset();a.parm('outputpath').set('/World/Replicas/Test');assert len(read()['Positions'])==10;reset()
    for name,value in (('prototype','/World/Missing'),('prototype','/World/Props/*'),('outputpath','relative'),('outputpath','/World/Props'),('outputpath','/World/Props/Crate/Nested'),('outputpath','/World/Props/Crate'),('outputpath','/')):
        a.parm(name).set(value)
        try:a.cook(force=True)
        except hou.OperationFailed:pass
        assert a.errors() or a.stage() is None,(name,value)
        reset();read()
    b=hou.node('/stage').createNode(a.type().name(),'test_overwrite');b.setInput(0,a)
    for count in (3,1):
        b.parm('line_count').set(count);s=b.stage();assert not b.errors(),b.errors()
        pi=UsdGeom.PointInstancer(s.GetPrimAtPath('/World/Arraytron'))
        assert len(pi.GetPositionsAttr().Get(hou.frame()))==count and len(pi.GetPrototypesRel().GetTargets())==1
    b.destroy()
    c=hou.node('/stage').createNode(a.type().name(),'test_chained');c.setInput(0,a);c.parm('mode').set(1);c.parm('outputpath').set('/World/ChainedArea')
    s=c.stage();assert not c.errors(),c.errors()
    for path,count in (('/World/Arraytron',10),('/World/ChainedArea',100)):
        pi=UsdGeom.PointInstancer(s.GetPrimAtPath(path));assert len(pi.GetPositionsAttr().Get(hou.frame()))==count
        assert UsdGeom.Imageable(s.GetPrimAtPath(pi.GetPrototypesRel().GetTargets()[0])).ComputeVisibility()=='inherited'
    c.destroy();reset()
def instance_transform_and_random():
    reset();a.parmTuple('base_rotation').set((0,90,0));a.parm('base_scale').set(2)
    d=read();assert abs(float(d['Orientations'][0].GetReal())-math.sqrt(.5))<.003 and all(tuple(s)==(2,2,2) for s in d['Scales'])
    a.parmTuple('position_random').set((.1,.2,.3));a.parmTuple('rotation_random').set((45,90,180));a.parm('scale_random').set(.99)
    first=read();again=read()
    assert first['Positions']==again['Positions'] and list(first['Scales'])==list(again['Scales'])
    a.parm('random_seed').set(2);assert first['Positions']!=read()['Positions']
    a.parm('random_seed').set(1);a.parm('line_count').set(12);more=read()
    assert list(first['Scales'])==list(more['Scales'])[:10] and list(first['Orientations'])==list(more['Orientations'])[:10]
    assert all(.0199<=s[0]<=3.9801 for s in more['Scales'])
    reset()
def demo_baseline():
    s=hou.node('/stage/karma_xpu').stage()
    assert hou.node('/stage/reference_test_crate').evalParm('filepath1').endswith('/test_assets/crate.usda')
    for path,count in (('/World/Arraytron',10),('/World/ArraytronArea',60)):
        pi=UsdGeom.PointInstancer(s.GetPrimAtPath(path));assert len(pi.GetPositionsAttr().Get(hou.frame()))==count
        assert UsdGeom.Imageable(s.GetPrimAtPath(pi.GetPrototypesRel().GetTargets()[0])).ComputeVisibility()=='inherited'
    assert hou.node('/stage/reference_demo_floor').isDisplayFlagSet(),'display flag must sit upstream of the Karma settings so the guide is visible'
check('Saved v0.15 demo: 10 Line + 60 Area instances, display flag upstream of Karma settings',demo_baseline)
check('UI contract: numeric menu tokens, matching folder conditionals, section layout, ranges, prim pickers',ui_contract)
check('Read-only Line Spacing matches Length/(Count-1) and the measured point gap',spacing_display)
check('Viewport handle: all 12 Bounds Transform parms bound to the stock LOP transform handle',handle_binding)
check('48 Line scenarios with Bounds Position, complete USD arrays and extents',line_contract)
check('Custom normalized Line direction, reverse direction, zero-vector fallback',custom_direction)
check('Area bounds, counts, seeds, position independence and zero size',area_contract)
check('Bounds Transform: SRT about pivot, identical for Line and Area, local points untouched, scale clamp',bounds_transform)
check('Switching Line/Area keeps the shared Bounds Transform',mode_switch_keeps_transform)
check('Reset Bounds Transform button restores defaults',reset_button)
check('Bounds guide: guide purpose, Line/Area geometry, pivot marker, toggle off deactivates',guide)
check('Guide purpose is excluded from Karma included purposes',guide_not_in_prototype_or_render_purpose)
check('Paths, overwrite and chained instancers (Line + Area) stay valid',paths_and_overwrite)
check('Instance rotation/scale, seeded jitter, stable random streams',instance_transform_and_random)
reset()
versions.validation_json('v0.1.5').write_text(json.dumps({'houdini':hou.applicationVersionString(),'checks':checks,'passed':True},indent=2))
print('ALL PASSED',len(checks))
