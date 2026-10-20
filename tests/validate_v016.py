"""Cook the v0.16 / v0.2 / v0.21 / v0.3 HDA in real Houdini. Usage: hython tests/validate_v016.py [v0.1.6|v0.2.0|v0.2.1|v0.3.0|v0.3.5|v0.3.6|v0.4.0|v0.4.5|v0.4.6|v0.5.0|v0.5.1|v0.5.2]  (default v0.1.6; the old tags v016 v02 v021 v03 v035 still work).
v02 = v0.16 plus the Grid / Matrix distribution; v021 = v02 plus the Scale Instances toggle; v03 = v021 plus the Prototype Bank on the modular network; v035 = v03 plus the Circle / Radial distribution; v0.3.6 = v0.3.5 plus the variation extras (Yaw Only, Min / Max scale, Non-Uniform). Every earlier check also runs on later versions (v0.4.0 = v0.3.6 plus Physics Settle, off by default; its own checks are in tests/validate_physics.py). Does not save the HIP."""
from pathlib import Path
import hou, json, math, re, sys
from pxr import UsdGeom, Gf
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else 'v0.1.6')     # new id (v0.3.5) or old tag (v035)
TN=versions.tab_names(VID)
PHYSTAB='Physics' if VID[0]=='v' and tuple(int(x) for x in VID[1:].split('.'))>=(1,6,2) else 'Settle'
TAG=VID
versions.ensure_installed(VID)          # Houdini 20.5 / 21 demo scenes do not record the HDA: it comes from here
hou.hipFile.load(str(versions.demo(VID)),suppress_save_prompt=True)
a=hou.node('/stage/Arraytron');checks=[]
GRID=a.parm('grid_countx') is not None
SCALEINST=a.parm('bound_scale_instances') is not None
BANK=a.parm('protos') is not None
CIRCLE=a.parm('circle_radius') is not None
VAREXTRAS=a.parm('yaw_random') is not None
assert GRID==(VID!='v0.1.6') and SCALEINST==(VID in ('v0.2.1','v0.3.0','v0.3.5','v0.3.6','v0.4.0','v0.4.5','v0.4.6','v0.5.0','v0.5.1','v0.5.2','v0.6.0','v0.7.0','v0.8.0','v0.9.0','v1.0.0','v1.1.0','v1.5.0','v1.6.0','v1.6.1','v1.6.2','v1.7.0','v1.8.0','v1.9.0','v1.10.0','v1.11.0','v1.12.0','v1.13.0','v1.14.0','v1.15.0','v1.16.0')) and BANK==(VID in ('v0.3.0','v0.3.5','v0.3.6','v0.4.0','v0.4.5','v0.4.6','v0.5.0','v0.5.1','v0.5.2','v0.6.0','v0.7.0','v0.8.0','v0.9.0','v1.0.0','v1.1.0','v1.5.0','v1.6.0','v1.6.1','v1.6.2','v1.7.0','v1.8.0','v1.9.0','v1.10.0','v1.11.0','v1.12.0','v1.13.0','v1.14.0','v1.15.0','v1.16.0')) and CIRCLE==(VID in ('v0.3.5','v0.3.6','v0.4.0','v0.4.5','v0.4.6','v0.5.0','v0.5.1','v0.5.2','v0.6.0','v0.7.0','v0.8.0','v0.9.0','v1.0.0','v1.1.0','v1.5.0','v1.6.0','v1.6.1','v1.6.2','v1.7.0','v1.8.0','v1.9.0','v1.10.0','v1.11.0','v1.12.0','v1.13.0','v1.14.0','v1.15.0','v1.16.0')) and VAREXTRAS==(VID in ('v0.3.6','v0.4.0','v0.4.5','v0.4.6','v0.5.0','v0.5.1','v0.5.2','v0.6.0','v0.7.0','v0.8.0','v0.9.0','v1.0.0','v1.1.0','v1.5.0','v1.6.0','v1.6.1','v1.6.2','v1.7.0','v1.8.0','v1.9.0','v1.10.0','v1.11.0','v1.12.0','v1.13.0','v1.14.0','v1.15.0','v1.16.0')),(VID,GRID,SCALEINST,BANK,CIRCLE,VAREXTRAS)
COMPILER='USD_COMPILER' if BANK else 'build_pointinstancer'
VARIATION='VARIATION_PROCESSOR' if BANK else 'modify_point_transforms'
ASSIGNMENT='PROTOTYPE_ASSIGNMENT'
import os
MUTATE=os.environ.get('ARRAYTRON_MUTATE')   # self-test: deliberately break the VEX in memory; the suite must then FAIL
if MUTATE:
    a.allowEditingOfContents()
    edits={'fold':(VARIATION,'return m <= 2.0*h ? m - h : 3.0*h - m;','return clamp(x,-h,h);'),
           'grid':('generate_grid','start + set(float(i)*step.x, float(j)*step.y, float(k)*step.z)','start + set(float(i)*step.x, float(j)*step.y, float(k)*step.z*1.01)'),
           'scaleinst':(VARIATION,'chv("../../bound_s"));','chv("../../bound_s"))*1.1;'),
           'line':('generate_line','count = clamp(int(floor(length/step + 1e-6)) + 1, 1, 10000);','count = clamp(int(floor(length/step)) + 2, 1, 10000);')}
    if BANK:
        edits.update({'cycle':(ASSIGNMENT,'pick = i@id % n;','pick = (i@id + 1) % n;'),'cdf':(ASSIGNMENT,'t < cumulative','t <= cumulative - 0.2*weight[k]'),
                      'protoscale':(ASSIGNMENT,'v@scale *= pscale[pick]','v@scale *= 1.0'),'protorot':(ASSIGNMENT,'p@orient = qmultiply(p@orient, poff[pick]);','p@orient = p@orient;'),
                      'rowid':(ASSIGNMENT,'rowid[pick] : 0','pick+1 : 0')})
    if VAREXTRAS:
        edits.update({'yawmode':(VARIATION,'set(0.0, angles.y*chf("../../yaw_random"), 0.0)','set(0.0, angles.x*chf("../../yaw_random"), 0.0)'),
                      'scalerange':(VARIATION,'s = base*lerp(lo, hi, u);','s = base*lerp(lo, hi, u*0.5);'),
                      'nustream':(VARIATION,'rand(set(i@id,seed,33))','rand(set(i@id,seed,32))'),
                      'nuaxis':(VARIATION,'*spreadscale.z);','*spreadscale.x);')})
    if CIRCLE:
        edits.update({'circle':('generate_circle','vector radial = cos(t)*u + sin(t)*v;','vector radial = cos(t)*u - sin(t)*v;'),
                      'arcstep':('generate_circle','2.0*PI/float(count) :','2.0*PI/float(count - 1) :'),
                      'facing':('generate_circle','atan2(dot(dir, refside), dot(dir, ref))','atan2(dot(dir, ref), dot(dir, refside))'),
                      'align':(VARIATION,'qmultiply(p@align, p@orient)','qmultiply(p@orient, p@align)')})
    node,old,new=edits[MUTATE];n=a.node(COMPILER+'/'+node);snippet=n.parm('snippet').eval();assert old in snippet
    n.parm('snippet').set(snippet.replace(old,new))
GUIDE='/World/Arraytron/Bounds_Guide'
def check(name,func):
    func();checks.append(name);print('PASS '+name)
def reset():
    if BANK:a.parm('protos').revertToDefaults()
    for p in a.parms():
        if p.parmTemplate().type() not in (hou.parmTemplateType.Folder,hou.parmTemplateType.FolderSet):p.revertToDefaults()
def read():
    s=a.stage();assert not a.errors(),a.errors()
    p=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')));assert p
    t=hou.frame()
    data={k:getattr(p,'Get'+k+'Attr')().Get(t) for k in ('Positions','Orientations','Scales','Ids','ProtoIndices')}
    n=len(data['Positions']);assert all(len(v)==n for v in data.values())
    assert list(data['Ids'])==sorted(data['Ids']) and sorted(data['Ids'])==list(range(n))
    targets=p.GetPrototypesRel().GetTargets()
    if BANK:
        assert len(targets)==len(a.hdaModule().bank_rows(a)) and all(0<=i<len(targets) for i in data['ProtoIndices'])
    else:
        assert len(targets)==1 and list(data['ProtoIndices'])==[0]*n
    assert all(UsdGeom.Imageable(s.GetPrimAtPath(x)).ComputeVisibility(t)=='inherited' for x in targets)
    assert sum(pr.IsA(UsdGeom.PointInstancer) for pr in s.Traverse())==1
    extent=p.GetExtentAttr().Get(t);computed=p.ComputeExtentAtTime(t,t)
    assert all(abs(extent[j][k]-computed[j][k])<.001 for j in range(2) for k in range(3))
    world=UsdGeom.Xformable(p).ComputeLocalToWorldTransform(t)
    data['WorldPositions']=[world.Transform(Gf.Vec3d(v)) for v in data['Positions']]
    data['Stage']=s
    return data
def close(u,v,tol=1e-5): return max(abs(u[k]-v[k]) for k in range(3))<tol
def fold(x,h):
    if h<=0:return 0.0
    m=(x+h)%(4*h)
    return m-h if m<=2*h else 3*h-m

# ---------------------------------------------------------------- UI contract
NEWUI=a.parm('grow_on') is not None               # v0.5.2: six workflow tabs instead of one tab per feature
def flat(entries):
    """Parameter names in order, looking inside tabs and collapsible sections (not into multiparm blocks); headings and hints (ui_*) are skipped."""
    out=[]
    for t in entries:
        if t.type()==hou.parmTemplateType.Folder and t.folderType()!=hou.folderType.MultiparmBlock:out+=flat(t.parmTemplates())
        elif not t.name().startswith('ui_'):out.append(t.name())
    return out
def ui_contract():
    g=a.parmTemplateGroup()
    for name in ('mode','line_axis','line_spacemode')+(('grid_spacemode',) if GRID else ()):
        t=g.find(name);assert t.menuItems()==tuple(str(i) for i in range(len(t.menuItems()))),(name,t.menuItems())
    assert g.find('mode').menuLabels()==(('Line','Area','Grid / Matrix','Circle / Radial')+(('Curve',) if a.parm('curve_prim') is not None else ())+(('Surface',) if a.parm('surface_prim') is not None else ())+(('Paint',) if a.parm('paint_prim') is not None else ())+(('Cluster',) if a.parm('cluster_prim') is not None else ())+(('Imported Points',) if a.parm('imp_sop') is not None else ())+(('Instance Place',) if a.parm('places') is not None else ())+(('Biome',) if a.parm('biomes') is not None else ()) if CIRCLE else ('Line','Area','Grid / Matrix') if GRID else ('Line','Area'))
    assert g.find('line_axis').menuLabels()==('X','Y','Z','Custom') and g.find('line_spacemode').menuLabels()==('By Count','By Spacing')
    def hide(n):
        c=g.find(n).conditionals()[hou.parmCondType.HideWhen]
        return re.sub(r'(?<=\})\s*\{ mode != \d \}$','',c) if NEWUI else c      # v0.5.2 adds the mode group to the parameters of a mode panel
    if NEWUI:
        assert hide('line_direction')=='{ line_axis != 3 }' and g.find('line_axis').conditionals()[hou.parmCondType.HideWhen]=='{ mode != 0 }' and g.find('area_sizex').conditionals()[hou.parmCondType.HideWhen]=='{ mode != 1 }'
    else:
        assert (hide('line'),hide('area'),hide('line_direction'))==('{ mode != 0 }','{ mode != 1 }','{ line_axis != 3 }')
    assert (hide('line_count'),hide('line_spacing'),hide('line_spacing_out'),hide('line_count_out'),hide('line_span_out'))==(
        '{ line_spacemode != 0 }','{ line_spacemode != 1 }','{ line_spacemode != 0 }','{ line_spacemode != 1 }','{ line_spacemode != 1 }')
    assert g.find('area_keepinside').conditionals()[hou.parmCondType.HideWhen]=='{ mode != 1 }'
    for name in ('line_spacing_out','line_count_out','line_span_out'):
        assert g.find(name).conditionals()[hou.parmCondType.DisableWhen]=='{ mode >= 0 }',name
    labels=[e.label() for e in g.entries()]
    if NEWUI:assert labels==[TN['source'],'Layout',TN['look'],'Spacing',PHYSTAB,'Animate']+(['Optimize'] if a.parm('cam_on') is not None else [])+([TN['finish']] if a.parm('dbg_on') is not None else [])+([TN['export']] if TN['export'] and a.parm('export_usd') is not None else []),labels
    else:assert labels==['Source','Distribution','Line','Area']+(['Grid'] if GRID else [])+(['Circle'] if CIRCLE else [])+(['Curve'] if a.parm('curve_prim') is not None else [])+(['Surface'] if a.parm('surface_prim') is not None else [])+['Bounds Transform','Instance Transform','Randomize']+(['Mask'] if a.parm('mask_source') is not None else [])+(['No Overlap'] if a.parm('overlap_mode') is not None else [])+(['Physics Settle'] if a.parm('phys_on') is not None else []),labels
    names_in=lambda prefix:[n for n in flat(g.entries()) if n.startswith(prefix)]
    assert (names_in('line_') if NEWUI else [t.name() for t in g.find('line').parmTemplates()])==['line_axis','line_direction','line_spacemode','line_count','line_length','line_spacing','line_center','line_spacing_out','line_count_out','line_span_out']
    if VAREXTRAS:
        assert ([n for n in flat(g.entries()) if n in ('random_seed','position_random','area_keepinside','rotation_random_mode','rotation_random','yaw_random','scale_random_mode','scale_random','scale_min','scale_max','scale_range_warn','scale_nonuniform')] if NEWUI else [t.name() for t in g.find('randomize').parmTemplates()])==['random_seed','position_random','area_keepinside','rotation_random_mode','rotation_random','yaw_random','scale_random_mode','scale_random','scale_min','scale_max','scale_range_warn','scale_nonuniform']
        assert g.find('rotation_random_mode').menuLabels()==('Euler XYZ','Yaw Only') and g.find('scale_random_mode').menuLabels()==('Fraction +/-','Min / Max')
        assert g.find('rotation_random_mode').menuItems()==('0','1') and g.find('scale_random_mode').menuItems()==('0','1')
        assert (hide('rotation_random'),hide('yaw_random'),hide('scale_random'),hide('scale_min'),hide('scale_max'))==('{ rotation_random_mode != 0 }','{ rotation_random_mode != 1 }','{ scale_random_mode != 0 }','{ scale_random_mode != 1 }','{ scale_random_mode != 1 }')
        assert hide('scale_range_warn')=='{ scale_random_mode != 1 } { scale_min <= scale_max }'
        assert g.find('scale_min').label()=='Minimum Multiplier' and g.find('scale_max').label()=='Maximum Multiplier' and g.find('scale_nonuniform').label()=='Non-Uniform (0 = locked)'
        assert g.find('scale_range_warn').columnLabels()[0].startswith('Minimum is larger than Maximum')
        reset();assert (a.parm('rotation_random_mode').eval(),a.parm('scale_random_mode').eval(),tuple(a.parmTuple('scale_nonuniform').eval()),a.parm('yaw_random').eval(),a.parm('scale_min').eval(),a.parm('scale_max').eval())==(0,0,(0,0,0),0,.8,1.2)
    else:
        assert [t.name() for t in g.find('randomize').parmTemplates()]==['random_seed','position_random','area_keepinside','rotation_random','scale_random']
    if NEWUI:assert [n for n in flat(g.entries()) if n.startswith('bound_') or n in ('show_bounds','reset_bounds')]==['bound_t','bound_r','bound_s','bound_scale_instances','reset_bounds','bound_p','show_bounds']
    else:assert [t.name() for t in g.find('bounds').parmTemplates()]==['bound_t','bound_r','bound_s']+(['bound_scale_instances'] if SCALEINST else [])+['bound_p','show_bounds','reset_bounds']
    if SCALEINST:
        t=g.find('bound_scale_instances');assert t.defaultValue()==False and t.label()=='Scale Instances'
        assert a.parm('bound_scale_instances').eval()==0,'a fresh node must not stretch instances by accident'
    if GRID:
        assert (names_in('grid_') if NEWUI else [t.name() for t in g.find('grid').parmTemplates()])==['grid_spacemode','grid_count','grid_size','grid_spacing','grid_center','grid_spacing_out','grid_count_out','grid_span_out','grid_total','grid_warn']
        assert ((g.find('grid_spacemode').conditionals()[hou.parmCondType.HideWhen].replace('{ mode != 2 }','{ mode != 2 }') if NEWUI else hide('grid')),hide('grid_count'),hide('grid_spacing'),hide('grid_spacing_out'),hide('grid_count_out'),hide('grid_span_out'),hide('grid_warn'))==(
            '{ mode != 2 }','{ grid_spacemode != 0 }','{ grid_spacemode != 1 }','{ grid_spacemode != 0 }','{ grid_spacemode != 1 }','{ grid_spacemode != 1 }','{ grid_total < 100000 }')
    else:
        assert g.find('grid') is None
    if CIRCLE:
        c=g.find('circle_plane') if NEWUI else g.find('circle');assert c.conditionals()[hou.parmCondType.HideWhen]=='{ mode != 3 }'
        assert (names_in('circle_') if NEWUI else [t.name() for t in c.parmTemplates()])==['circle_plane','circle_radius','circle_count','circle_arc','circle_start','circle_facing','circle_step_out','circle_spacing_out']
        assert g.find('circle_plane').menuLabels()==('XZ (ground)','XY','YZ') and g.find('circle_facing').menuLabels()==('None','Outward','Center','Tangent')
        assert g.find('circle_plane').menuItems()==('0','1','2') and g.find('circle_facing').menuItems()==('0','1','2','3')
        for name in ('circle_step_out','circle_spacing_out'):assert g.find(name).conditionals()[hou.parmCondType.DisableWhen]=='{ mode >= 0 }',name
        reset();assert (a.parm('circle_radius').eval(),a.parm('circle_count').eval(),a.parm('circle_arc').eval(),a.parm('circle_start').eval(),a.parm('circle_plane').eval(),a.parm('circle_facing').eval())==(5,12,360,0,0,0)
    if BANK:assert g.find('prototype') is None and g.find('outputpath').tags().get('sidefx::usdpathtype')=='prim'
    else:
        for name in ('prototype','outputpath'):assert g.find(name).tags().get('sidefx::usdpathtype')=='prim'
    assert g.find('bound_r').minValue()==-180 and g.find('bound_r').maxValue()==180
def handle_binding():
    text=a.type().definition().sections()['DialogScript'].contents()
    lines=re.findall(r'^\s*bindhandle (\w+) lopxform "Transformer" (\w+) ""',text,re.M)
    expected=[(f'bound_{g}{x}',f'{g}{x}') for g in 'trsp' for x in 'xyz']
    assert sorted(lines)==sorted(expected),lines
    for parm,_ in lines:assert a.parm(parm),parm

# ---------------------------------------------------------------- Line
def line_by_count():
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
def line_by_spacing():
    reset();a.parm('line_spacemode').set(1)
    for axis in range(3):
        for length in (0,.4,10,11.5,50):
            for spacing in (.5,1,3,20):
                for centered in (0,1):
                    a.parm('line_axis').set(axis);a.parm('line_length').set(length);a.parm('line_spacing').set(spacing)
                    a.parm('line_center').set(centered);a.parmTuple('bound_t').set((1,2,3))
                    n=int(math.floor(length/spacing+1e-6))+1
                    d=read();assert len(d['Positions'])==n==a.parm('line_count_out').eval(),(axis,length,spacing,n)
                    assert abs(a.parm('line_span_out').eval()-(n-1)*spacing)<1e-9
                    for j,p in enumerate(d['WorldPositions']):
                        expected=[1,2,3];expected[axis]+=j*spacing-(0.5*(n-1)*spacing if centered else 0)
                        assert close(p,expected),(axis,length,spacing,centered,j,p,expected)
    # custom direction, and the 10000 point cap with the 0.001 spacing floor
    reset();a.parm('line_spacemode').set(1);a.parm('line_axis').set(3);a.parmTuple('line_direction').set((1,2,-3))
    a.parm('line_length').set(9);a.parm('line_spacing').set(2);d=read();direction=hou.Vector3(1,2,-3).normalized()
    assert len(d['Positions'])==5
    assert all((hou.Vector3(p)-direction*(j*2-4)).length()<1e-5 for j,p in enumerate(d['Positions']))
    a.parm('line_length').set(50);a.parm('line_spacing').set(.001)
    assert a.parm('line_count_out').eval()==10000 and len(read()['Positions'])==10000
    a.parm('line_spacing').set(0)   # UI minimum is 0.001; a scripted 0 must not hang or divide by zero
    assert len(read()['Positions'])==10000
    reset()
def line_readouts_by_count():
    reset()
    for count,length in ((1,10),(2,10),(10,18),(101,10),(5,0)):
        a.parm('line_count').set(count);a.parm('line_length').set(length)
        expected=length/(count-1) if count>1 else 0
        assert abs(a.parm('line_spacing_out').eval()-expected)<1e-9,(count,length)
        d=read()['Positions']
        if count>1:assert abs((hou.Vector3(d[1])-hou.Vector3(d[0])).length()-a.parm('line_spacing_out').eval())<1e-5
    reset();assert a.parm('line_spacing_out').eval()==10/9
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

# ---------------------------------------------------------------- Area
def area_contract():
    reset();a.parm('mode').set(1)
    for count in (1,100,1000):
        for seed in (1,2,77):
            a.parm('area_count').set(count);a.parm('area_seed').set(seed)
            d=read();assert len(d['Positions'])==count and d['Positions']==read()['Positions']
            assert all(-5<=p[0]<=5 and p[1]==0 and -5<=p[2]<=5 for p in d['Positions'])
    first=read();a.parm('area_seed').set(78);assert first['Positions']!=read()['Positions']
    a.parm('area_seed').set(77);a.parmTuple('bound_t').set((7,2,-3));moved=read()
    assert all(close(q,tuple(p[k]+(7,2,-3)[k] for k in range(3))) for p,q in zip(first['WorldPositions'],moved['WorldPositions']))
    a.parm('area_sizex').set(0);a.parm('area_sizez').set(0)
    assert all(tuple(p)==(7,2,-3) for p in read()['WorldPositions'])
    reset()
def keep_inside():
    reset();a.parm('mode').set(1);a.parm('area_count').set(400);a.parm('area_sizex').set(10);a.parm('area_sizez').set(6)
    a.parmTuple('position_random').set((20,0,20))
    off=read();assert any(abs(p[0])>5 or abs(p[2])>3 for p in off['Positions']),'jitter must overshoot for this test to mean anything'
    a.parm('area_keepinside').set(1);on=read()
    assert all(abs(p[0])<=5+1e-5 and abs(p[2])<=3+1e-5 for p in on['Positions'])
    for p,q in zip(off['Positions'],on['Positions']):
        assert abs(q[0]-fold(p[0],5))<1e-4 and abs(q[2]-fold(p[2],3))<1e-4 and abs(q[1]-p[1])<1e-6,(p,q)
    assert on==read(),'deterministic'
    # Reflection, not clamping: the edge must not collect a pile of points.
    edge=sum(1 for p in on['Positions'] if abs(abs(p[0])-5)<1e-4)
    assert edge<=2,edge
    # In-bounds results are untouched; Y jitter is free; random streams of rotation/scale are unchanged.
    a.parmTuple('position_random').set((.5,1.5,.5))
    a.parm('area_keepinside').set(0);base=read();a.parm('area_keepinside').set(1);kept=read()
    for p,q in zip(base['Positions'],kept['Positions']):
        if abs(p[0])<=5 and abs(p[2])<=3:assert close(p,q,1e-6)
    assert any(abs(p[1])>.5 for p in kept['Positions']) and all(abs(p[1])<=1.5+1e-6 for p in kept['Positions'])
    assert list(base['Scales'])==list(kept['Scales']) and list(base['Orientations'])==list(kept['Orientations'])
    # Zero-size Area collapses to the centre; the toggle never changes Line (or Grid) points.
    a.parmTuple('position_random').set((3,0,3));a.parm('area_sizex').set(0);a.parm('area_sizez').set(0)
    assert all(abs(p[0])<1e-6 and abs(p[2])<1e-6 for p in read()['Positions'])
    reset();a.parmTuple('position_random').set((2,0,2));line_off=read()['Positions'];a.parm('area_keepinside').set(1)
    assert read()['Positions']==line_off,'Line must ignore Keep Inside Area'
    if GRID:
        a.parm('mode').set(2);a.parm('area_keepinside').set(0);grid_off=read()['Positions'];a.parm('area_keepinside').set(1)
        assert read()['Positions']==grid_off,'Grid must ignore Keep Inside Area'
    if CIRCLE:
        a.parm('mode').set(3);a.parm('area_keepinside').set(0);circle_off=read()['Positions'];a.parm('area_keepinside').set(1)
        assert read()['Positions']==circle_off,'Circle must ignore Keep Inside Area'
    reset()

# ---------------------------------------------------------------- Grid (v0.2)
def expected_grid(count,size,spacing,bysp,centered):
    cnt=[];step=[]
    for k in range(3):
        if bysp:
            n=min(100,int(math.floor(size[k]/max(.001,spacing[k])+1e-6))+1);cnt.append(n);step.append(max(.001,spacing[k]))
        else:
            n=min(100,max(1,count[k]));cnt.append(n);step.append(size[k]/(n-1) if n>1 else 0.0)
    start=[(-0.5*(cnt[k]-1)*step[k] if centered else 0.0) for k in range(3)]
    pts={}
    for k in range(cnt[2]):
        for j in range(cnt[1]):
            for i in range(cnt[0]):
                pts[i+cnt[0]*(j+cnt[1]*k)]=(start[0]+i*step[0],start[1]+j*step[1],start[2]+k*step[2])
    return cnt,pts
# Codex's hand-derived cases (team/v02-codex-grid/response.md), re-derived by Claude:
# (spacemode, centered, count, size, spacing, result counts, total, first, last, (sample ijk, id))
GRID_CASES=[
 (0,1,(5,1,5),(10,10,10),None,(5,1,5),25,(-5,0,-5),(5,0,5),((2,0,3),17)),
 (0,1,(6,1,4),(10,10,6),None,(6,1,4),24,(-5,0,-3),(5,0,3),((5,0,2),17)),
 (0,1,(3,3,3),(4,4,4),None,(3,3,3),27,(-2,-2,-2),(2,2,2),((1,2,1),16)),
 (0,0,(2,2,2),(4,6,8),None,(2,2,2),8,(0,0,0),(4,6,8),((0,1,1),6)),
 (0,1,(1,1,1),(10,20,30),None,(1,1,1),1,(0,0,0),(0,0,0),((0,0,0),0)),
 (0,1,(1,3,2),(99,4,6),None,(1,3,2),6,(0,-2,-3),(0,2,3),((0,2,1),5)),
 (0,1,(3,2,2),(0,4,0),None,(3,2,2),12,(0,-2,0),(0,2,0),((2,1,1),11)),
 (1,1,None,(10,10,10),(2,2,2),(6,6,6),216,(-5,-5,-5),(5,5,5),((1,2,3),121)),
 (1,1,None,(10,0,6),(2,2,2),(6,1,4),24,(-5,0,-3),(5,0,3),((5,0,2),17)),
 (1,0,None,(1,2,3),(2,3,4),(1,1,1),1,(0,0,0),(0,0,0),((0,0,0),0)),
 (1,1,None,(10,4,0),(3,3,2),(4,2,1),8,(-4.5,-1.5,0),(4.5,1.5,0),((2,1,0),6)),
 (1,0,None,(10,4,0),(3,3,2),(4,2,1),8,(0,0,0),(9,3,0),((2,1,0),6)),
 (1,1,None,(1000,0,0),(1,1,1),(100,1,1),100,(-49.5,0,0),(49.5,0,0),((99,0,0),99)),
]
def set_grid(case):
    mode,centered,count,size,spacing=case[:5]
    reset();a.parm('mode').set(2);a.parm('grid_spacemode').set(mode);a.parm('grid_center').set(centered)
    if count:a.parmTuple('grid_count').set(count)
    a.parmTuple('grid_size').set(size)
    if spacing:a.parmTuple('grid_spacing').set(spacing)
def grid_cases():
    for n,case in enumerate(GRID_CASES,1):
        _,_,_,_,_,counts,total,first,last,(ijk,sid)=case
        set_grid(case);d=read();pos=d['Positions']
        assert len(pos)==total,(n,len(pos),total)
        assert tuple(a.parmTuple('grid_count_out' if case[0]==1 else 'grid_count').eval())==counts,n
        assert a.parm('grid_total').eval()==total,n
        assert close(pos[0],first) and close(pos[-1],last),(n,tuple(pos[0]),tuple(pos[-1]))
        assert sid==ijk[0]+counts[0]*(ijk[1]+counts[1]*ijk[2])
        assert d['Ids'][sid]==sid
        # independent full-grid formula check, every point
        cnt,pts=expected_grid(case[2],case[3],case[4],case[0]==1,case[1])
        assert tuple(cnt)==counts and len(pts)==total
        assert all(close(pos[i],pts[i],1e-5) for i in range(total)),n
    reset()
def grid_readouts():
    reset();a.parm('mode').set(2)
    assert tuple(a.parmTuple('grid_spacing_out').eval())==(2.5,0,2.5),'default 5x1x5 over size 10: spacing 2.5, 0 on the flat axis'
    assert a.parm('grid_total').eval()==25
    a.parm('grid_spacemode').set(1);a.parmTuple('grid_size').set((10,4,0));a.parmTuple('grid_spacing').set((3,3,2))
    assert tuple(a.parmTuple('grid_count_out').eval())==(4,2,1) and tuple(a.parmTuple('grid_span_out').eval())==(9,3,0) and a.parm('grid_total').eval()==8
    g=a.parmTemplateGroup();warn=g.find('grid_warn')
    assert warn.columnLabels()[0].startswith('More than 100,000 instances')
    a.parm('grid_spacemode').set(0)
    a.parmTuple('grid_count').set((50,2,2));assert a.parm('grid_total').eval()==200
    a.parmTuple('grid_count').set((50,50,50));assert a.parm('grid_total').eval()==125000>=100000   # the warning's hide condition is then false
    reset()
def grid_cap():
    # 100 per axis, 1,000,000 points: checked at SOP level (a USD read of 1M points would only test Python speed).
    reset();a.parm('mode').set(2);a.parmTuple('grid_count').set((100,100,100));a.parmTuple('grid_size').set((99,99,99))
    geo=a.node(COMPILER+'/generate_grid').geometry()
    n=len(geo.points());assert n==1000000,n
    p=geo.point(30201);assert p.intAttribValue('id')==30201
    assert (hou.Vector3(p.position())-hou.Vector3(-49.5+1,-49.5+2,-49.5+3)).length()<1e-4
    a.parmTuple('grid_count').set((500,1,1));assert a.parm('grid_total').eval()==500
    assert len(a.node(COMPILER+'/generate_grid').geometry().points())==100,'count must be capped at 100 per axis'
    reset()
def grid_ids_stable():
    reset();a.parm('mode').set(2);a.parmTuple('grid_count').set((3,3,2));a.parmTuple('grid_size').set((4,4,2))
    pos=read()['Positions'];ids_before=list(range(18))
    a.parmTuple('grid_count').set((3,3,3));a.parmTuple('grid_size').set((4,4,4));more=read()['Positions']
    assert len(more)==27 and ids_before==list(range(18))
    # adding a Z layer keeps (i,j) ordering of the first layers (positions change only because Size re-spaces z)
    assert all(abs(more[i][0]-pos[i][0])<1e-6 and abs(more[i][1]-pos[i][1])<1e-6 for i in range(18))
    reset()

# ---------------------------------------------------------------- shared transform, guide, rest
def modes():return (0,1,2,3) if CIRCLE else (0,1,2) if GRID else (0,1)
def bounds_transform():
    for mode in modes():
      for scale_instances in ((1,0) if SCALEINST else (1,)):
        reset();a.parm('mode').set(mode)
        if SCALEINST:a.parm('bound_scale_instances').set(scale_instances)
        if mode==2:a.parmTuple('grid_count').set((3,2,2));a.parmTuple('grid_size').set((4,2,2))
        a.parm('base_scale').set(2)     # instance size of its own, to tell which scale reaches the instances
        initial=read();position=hou.Vector3(7,-2,3);rotation=(25,40,15);scale=(2,.5,1.4);pivot=hou.Vector3(1,.25,-.75)
        a.parmTuple('bound_t').set(tuple(position));a.parmTuple('bound_r').set(rotation)
        a.parmTuple('bound_s').set(scale);a.parmTuple('bound_p').set(tuple(pivot))
        actual=read()
        if scale_instances:assert actual['Positions']==initial['Positions'],'USD transform carries the scale; local points untouched'
        else:
            for p0,p1 in zip(initial['Positions'],actual['Positions']):
                assert close(p1,[pivot[k]+(p0[k]-pivot[k])*scale[k] for k in range(3)],1e-5),'Scale Instances off: positions are scaled about the pivot'
        sr=hou.hmath.buildScale(scale)*hou.hmath.buildRotate(rotation)
        for local,world in zip(initial['Positions'],actual['WorldPositions']):
            expected=(hou.Vector3(local)-pivot)*sr+pivot+position
            assert close(world,expected),(mode,scale_instances,world,expected)   # identical placement either way
        pi=UsdGeom.PointInstancer(actual['Stage'].GetPrimAtPath('/World/Arraytron'))
        root=UsdGeom.Xformable(pi).ComputeLocalToWorldTransform(hou.frame())
        inst=pi.ComputeInstanceTransformsAtTime(hou.frame(),hou.frame())[0]*root
        rows=[Gf.Vec3d(inst[r][:3]) for r in range(3)]
        for row,factor in zip(rows,(4,1,2.8) if scale_instances else (2,2,2)):assert abs(row.GetLength()-factor)<1e-5,(mode,scale_instances,row.GetLength(),factor)
        if not scale_instances:
            assert all(abs(Gf.Dot(rows[u],rows[w]))<1e-5 for u,w in ((0,1),(0,2),(1,2))),'instances must stay un-sheared'
            assert all(abs(Gf.Vec3d(root[r][:3]).GetLength()-1)<1e-5 for r in range(3)),'USD transform must carry no scale'
        reset();a.parm('mode').set(mode)
        if SCALEINST:a.parm('bound_scale_instances').set(scale_instances)
        if mode==2:a.parmTuple('grid_count').set((3,2,2));a.parmTuple('grid_size').set((4,2,2))
        base=read()['WorldPositions'];a.parmTuple('bound_p').set((9,8,7))
        assert all(close(u,v,1e-5) for u,v in zip(read()['WorldPositions'],base)),'pivot alone must not move an identity transform'
        a.parmTuple('bound_s').set((0,-2,2));after=read()      # scripted nonpositive scale is clamped to 0.0001
        root=UsdGeom.Xformable(a.stage().GetPrimAtPath('/World/Arraytron')).ComputeLocalToWorldTransform(hou.frame())
        if scale_instances:assert abs(Gf.Vec3d(root[0][:3]).GetLength()-.0001)<1e-7 and abs(Gf.Vec3d(root[2][:3]).GetLength()-2)<1e-5
        else:
            for b,w in zip(base,after['WorldPositions']):
                assert close(w,[9+(b[0]-9)*.0001,8+(b[1]-8)*.0001,7+(b[2]-7)*2],1e-4),(b,w)
    reset()
def scale_instances_toggle():
    # Same layout, different instance size: positions identical, only the instance scale differs.
    reset();a.parm('mode').set(0);a.parmTuple('bound_s').set((3,1,1));a.parmTuple('bound_t').set((1,2,3))
    a.parm('bound_scale_instances').set(1);on=read();a.parm('bound_scale_instances').set(0);off=read()
    assert all(close(p,q,1e-5) for p,q in zip(on['WorldPositions'],off['WorldPositions']))
    pi=UsdGeom.PointInstancer(off['Stage'].GetPrimAtPath('/World/Arraytron'));root=UsdGeom.Xformable(pi).ComputeLocalToWorldTransform(hou.frame())
    inst=pi.ComputeInstanceTransformsAtTime(hou.frame(),hou.frame())[0]*root
    assert abs(Gf.Vec3d(inst[0][:3]).GetLength()-1)<1e-5,'x of a crate must stay 1 with Scale 3 and Scale Instances off'
    # The layout extent grows by the scale in both states (the bounds are scaled either way).
    for result in (on,off):
        xs=[p[0] for p in result['WorldPositions']];assert abs((max(xs)-min(xs))-30)<1e-4
    # The reset button leaves the toggle alone (a preference, not a transform value).
    a.parm('bound_scale_instances').set(1);a.parm('reset_bounds').pressButton()
    assert a.parm('bound_scale_instances').eval()==1 and a.parmTuple('bound_s').eval()==(1,1,1)
    # Keep Inside Area still bounds the jitter in LOCAL space before the layout scale, in both states.
    reset();a.parm('mode').set(1);a.parm('area_keepinside').set(1);a.parmTuple('position_random').set((20,0,20));a.parmTuple('bound_s').set((2,1,3))
    for toggle in (1,0):
        a.parm('bound_scale_instances').set(toggle);d=read()
        assert all(abs(p[0])<=5*2+1e-3 and abs(p[2])<=5*3+1e-3 for p in d['WorldPositions'])
    reset()
def mode_switch_keeps_transform():
    reset();a.parmTuple('bound_t').set((3,1,-2));a.parmTuple('bound_r').set((0,30,0))
    line=read()['WorldPositions']
    for mode in modes()[1:]:
        a.parm('mode').set(mode);r=read()
        root=UsdGeom.Xformable(r['Stage'].GetPrimAtPath('/World/Arraytron')).ComputeLocalToWorldTransform(hou.frame())
        assert close(root.ExtractTranslation(),(3,1,-2)),f'mode {mode} must inherit the same Bounds Transform'
    a.parm('mode').set(0);assert read()['WorldPositions']==line
    reset()
def reset_button():
    reset();a.parmTuple('bound_t').set((1,2,3));a.parmTuple('bound_r').set((4,5,6));a.parmTuple('bound_s').set((2,2,2));a.parmTuple('bound_p').set((7,8,9))
    a.parm('reset_bounds').pressButton()
    assert a.parmTuple('bound_t').eval()==(0,0,0) and a.parmTuple('bound_r').eval()==(0,0,0)
    assert a.parmTuple('bound_s').eval()==(1,1,1) and a.parmTuple('bound_p').eval()==(0,0,0)
def guide_curves(stage,name):
    c=UsdGeom.BasisCurves(stage.GetPrimAtPath(GUIDE+'/'+name));assert c,name
    pts=c.GetPointsAttr().Get();out=[];i=0
    for n in c.GetCurveVertexCountsAttr().Get():out.append([hou.Vector3(*pts[i+k]) for k in range(n)]);i+=n
    return out
def mid(c):return (c[0]+c[1])/2
def guide():
    reset();s=read()['Stage']
    g=s.GetPrimAtPath(GUIDE);assert g and g.IsActive()
    for path in (GUIDE,GUIDE+'/Bounds',GUIDE+'/Pivot'):assert UsdGeom.Imageable(s.GetPrimAtPath(path)).ComputePurpose()=='guide',path
    curves=guide_curves(s,'Bounds');assert len(curves)==2+10      # segment, arrow head, ten ticks
    assert (curves[0][0]-hou.Vector3(-5,0,0)).length()<1e-5 and (curves[0][1]-hou.Vector3(5,0,0)).length()<1e-5
    assert len(guide_curves(s,'Pivot'))==3
    a.parm('line_center').set(0);a.parm('line_axis').set(2)
    curves=guide_curves(read()['Stage'],'Bounds')
    assert curves[0][0].length()<1e-5 and (curves[0][1]-hou.Vector3(0,0,10)).length()<1e-5
    # By Spacing: points -4.5..4.5, two Length-limit caps at +/-5 between the arrow and the ticks
    reset();a.parm('line_spacemode').set(1);a.parm('line_spacing').set(3);curves=guide_curves(read()['Stage'],'Bounds')
    assert len(curves)==2+2+4,len(curves)
    assert (curves[0][0]-hou.Vector3(-4.5,0,0)).length()<1e-5 and (curves[0][1]-hou.Vector3(4.5,0,0)).length()<1e-5
    assert sorted(round(mid(c)[0],5) for c in curves[2:4])==[-5,5]
    assert [round(mid(c)[0],5) for c in curves[4:]]==[-4.5,-1.5,1.5,4.5]
    a.parmTuple('bound_p').set((1,2,3));pivots=guide_curves(read()['Stage'],'Pivot')
    assert all(mid(c)==hou.Vector3(1,2,3) for c in pivots)
    reset();a.parm('mode').set(1);a.parm('area_sizex').set(8);a.parm('area_sizez').set(4)
    rect=guide_curves(read()['Stage'],'Bounds');assert len(rect)==1 and len(rect[0])==5
    assert sorted({round(p[0],5) for p in rect[0]})==[-4,4] and sorted({round(p[2],5) for p in rect[0]})==[-2,2]
    assert rect[0][0]==rect[0][-1] and all(p[1]==0 for p in rect[0])
    if GRID:
        reset();a.parm('mode').set(2);curves=guide_curves(read()['Stage'],'Bounds')
        assert len(curves)==4+25*3,len(curves)          # flat grid: 4 box edges + a cross per point
        box=curves[:4];assert all(p[1]==0 for c in box for p in c)
        assert sorted({round(p[0],5) for c in box for p in c})==[-5,5] and sorted({round(p[2],5) for c in box for p in c})==[-5,5]
        a.parmTuple('grid_count').set((2,2,2));a.parmTuple('grid_size').set((4,4,4));curves=guide_curves(read()['Stage'],'Bounds')
        assert len(curves)==12+8*3,len(curves)
        assert sorted({round(p[k],5) for c in curves[:12] for p in c for k in (0,1,2)})==[-2,2]
        a.parmTuple('grid_count').set((20,20,1));a.parmTuple('grid_size').set((10,10,0));curves=guide_curves(read()['Stage'],'Bounds')
        assert len(curves)==4,len(curves)               # 400 points: box only, no crosses
    if CIRCLE:
        set_circle(0,4,12,360,0);curves=guide_curves(read()['Stage'],'Bounds');ring=curves[0]
        assert len(curves)==1+12 and len(ring)==73 and all(abs(hou.Vector3(p[0],0,p[2]).length()-4)<1e-4 and abs(p[1])<1e-6 for p in ring),'full circle plus a tick per point'
        assert (ring[0]-ring[-1]).length()<1e-4,'a full circle closes'
        lengths=[(c[1]-c[0]).length() for c in curves[1:]];assert lengths[0]>lengths[1]+1e-6 and all(abs(l-lengths[1])<1e-6 for l in lengths[1:]),'the Start tick is longer'
        set_circle(0,4,5,90,0);curves=guide_curves(read()['Stage'],'Bounds');ring=curves[0]
        assert (ring[0]-hou.Vector3(4,0,0)).length()<1e-4 and (ring[-1]-hou.Vector3(0,0,-4)).length()<1e-4 and len(curves)==1+5
        for plane in (1,2):
            set_circle(plane,4,8,360,0);ring=guide_curves(read()['Stage'],'Bounds')[0]
            assert all(abs(p[NIDX[plane]])<1e-6 for p in ring),plane
        set_circle(0,4,300,360,0);assert len(guide_curves(read()['Stage'],'Bounds'))==1+2,'over 256 points: only the circle and two end ticks'
    reset();a.parm('show_bounds').set(0);off=read()['Stage'].GetPrimAtPath(GUIDE)
    assert not off or not off.IsActive(),'guide must be inactive when toggled off'
    a.parm('show_bounds').set(1);assert read()['Stage'].GetPrimAtPath(GUIDE).IsActive()
    reset()
def guide_scale():
    # The guide must land on the instances' world extents whether or not the USD transform carries the scale.
    for toggle in (0,1):
        reset();a.parm('bound_scale_instances').set(toggle);a.parmTuple('bound_s').set((2,1,1));a.parmTuple('bound_p').set((1,2,3));a.parmTuple('bound_t').set((10,0,0))
        d=read();s=d['Stage'];bounds=guide_curves(s,'Bounds')
        start,end=bounds[0][0],bounds[0][1]
        # local guide x: scaled about the pivot when the USD transform has no scale, unscaled otherwise
        want=(1+(-5-1)*2,1+(5-1)*2) if toggle==0 else (-5,5)
        assert abs(start[0]-want[0])<1e-4 and abs(end[0]-want[1])<1e-4,(toggle,tuple(start),tuple(end))
        world=UsdGeom.Xformable(s.GetPrimAtPath(GUIDE+'/Bounds')).ComputeLocalToWorldTransform(hou.frame())
        ends=[world.Transform(Gf.Vec3d(*p)) for p in (start,end)]
        xs=sorted(p[0] for p in d['WorldPositions'])
        assert abs(ends[0][0]-xs[0])<1e-4 and abs(ends[1][0]-xs[-1])<1e-4,(toggle,ends,xs[0],xs[-1])
        assert all(mid(c)==hou.Vector3(1,2,3) for c in guide_curves(s,'Pivot'))
    reset()
def guide_purpose():
    s=hou.node('/stage/karma_xpu').stage()
    rs=s.GetPrimAtPath('/Render/karma_xpu');assert 'guide' not in list(rs.GetAttribute('includedPurposes').Get())
    assert UsdGeom.Imageable(s.GetPrimAtPath(GUIDE)).ComputePurpose()=='guide'
def paths_and_overwrite():
    PRIM='proto_prim1' if BANK else 'prototype'
    reset();a.parm('outputpath').set('/World/Replicas/Test');assert len(read()['Positions'])==10;reset()
    for name,value in ((PRIM,'/World/Missing'),(PRIM,'/World/Props/*'),('outputpath','relative'),('outputpath','/World/Props'),('outputpath','/World/Props/Crate/Nested'),('outputpath','/World/Props/Crate'),('outputpath','/')):
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
    c.destroy()
    if GRID:
        e=hou.node('/stage').createNode(a.type().name(),'test_chained_grid');e.setInput(0,a);e.parm('mode').set(2);e.parm('outputpath').set('/World/ChainedGrid')
        s=e.stage();assert not e.errors(),e.errors()
        for path,count in (('/World/Arraytron',10),('/World/ChainedGrid',25)):
            pi=UsdGeom.PointInstancer(s.GetPrimAtPath(path));assert len(pi.GetPositionsAttr().Get(hou.frame()))==count
        e.destroy()
    reset()
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

# ---------------------------------------------------------------- Prototype Bank (v0.3)
import os, tempfile
from collections import Counter
STAGE=hou.node('/stage')
def errors_text():
    return ' | '.join(' '.join(c.errors()) for c in a.children() if c.errors())
def expect_error(fragment):
    try:a.cook(force=True)
    except hou.OperationFailed:pass
    text=errors_text()
    assert fragment in text,(fragment,text)
def picks(indices=None):
    d=read();return list(d['ProtoIndices']),d
def set_rows(rows):
    """rows: list of dicts of proto_<key>N values. Resets the bank first."""
    reset();a.parm('protos').set(len(rows))
    for n,values in enumerate(rows,1):
        for key,value in values.items():
            a.parmTuple(f'proto_{key}{n}').set(value if isinstance(value,(tuple,list)) else (value,))
CRATE={'type':0,'prim':'/World/Props/Crate'}
BARREL={'type':0,'prim':'/World/Props/Barrel'}     # merged in from Prototype Input 2 in the demo
ROCK={'type':2,'file':str(ROOT/'dist/test_assets/rock.usda')}
def bank_ui():
    g=a.parmTemplateGroup();src=g.find('tab_source') if NEWUI else g.find('source')
    assert (flat(src.parmTemplates()) if NEWUI else [t.name() for t in src.parmTemplates()])==(['protos','proto_mode']+(['proto_percent'] if a.parm('imp_sop') is not None else [])+['proto_summary','proto_seed','outputpath'] if NEWUI else ['outputpath','protos','proto_mode','proto_seed','proto_summary'])
    bank=g.find('protos');assert bank.folderType()==hou.folderType.MultiparmBlock and bank.defaultValue()==1
    names=[t.name() for t in bank.parmTemplates()]
    assert names==['proto_on#','proto_type#','proto_prim#','proto_input#','proto_inprim#','proto_file#','proto_fileprim#','proto_sop#','proto_weight#','proto_scale#','proto_scalevar#','proto_rot#']+(['proto_lod1#','proto_lod2#','proto_proxy#'] if a.parm('cam_on') is not None else []),names
    hide={t.name():(t.conditionals().get(hou.parmCondType.HideWhen) if t.conditionals() else None) for t in bank.parmTemplates()}
    a_has_lod=a.parm('cam_on') is not None
    assert hide=={'proto_on#':None,'proto_type#':None,'proto_prim#':'{ proto_type# != 0 }','proto_input#':'{ proto_type# != 1 }','proto_inprim#':'{ proto_type# != 1 }','proto_file#':'{ proto_type# != 2 }','proto_fileprim#':'{ proto_type# != 2 }','proto_sop#':'{ proto_type# != 3 }','proto_weight#':None,'proto_scale#':None,'proto_scalevar#':None,'proto_rot#':None,**({'proto_lod1#':None,'proto_lod2#':None,'proto_proxy#':None} if a_has_lod else {})},hide
    t=bank.parmTemplates()
    weight=[x for x in t if x.name()=='proto_weight#'][0]
    assert weight.conditionals()[hou.parmCondType.DisableWhen]=='{ proto_mode == 0 } { proto_mode == 3 }','Weight is greyed out in Random and Cycle, which ignore it'
    kinds={x.name():x for x in t}
    assert kinds['proto_type#'].menuLabels()==('Prim Path','Input Connection','USD File','SOP Geometry') and kinds['proto_type#'].menuItems()==('0','1','2','3')
    assert kinds['proto_input#'].menuLabels()==('Input 2','Input 3','Input 4')
    assert kinds['proto_file#'].stringType()==hou.stringParmType.FileReference and kinds['proto_sop#'].stringType()==hou.stringParmType.NodeReference
    assert kinds['proto_sop#'].tags()['opfilter']=='!!SOP!!' and kinds['proto_prim#'].tags().get('sidefx::usdpathtype')=='prim'
    mode=g.find('proto_mode');assert mode.menuLabels()[:4]==('Random','Weighted Random','Sequential','Cycle') and mode.menuLabels()[4:] in ((),('Even Percent',)) and mode.defaultValue()==1
    reset();assert a.parm('protos').eval()==1 and a.parm('proto_prim1').eval()=='/World/Props/Crate' and a.parm('proto_weight1').eval()==1
    assert a.type().definition().sections()['DialogScript'].contents().count('inputlabel')>=4
    labels=re.findall(r'inputlabel\s+\d+\s+"([^"]*)"',a.type().definition().sections()['DialogScript'].contents())
    assert labels[:4]==(['Scene Stream: terrain, curve, models','Input 2: extra prototype (optional)','Input 3: extra prototype (optional)','Input 4: extra prototype (optional)'] if a.parm('paint_prim') is not None else ['Main Stream','Prototype Input 2','Prototype Input 3','Prototype Input 4']),labels
    assert a.type().maxNumInputs()==4 and a.type().minNumInputs()==1
def stage_prims():
    return {p.GetPath().pathString for p in read()['Stage'].Traverse()}
def source_types():
    # 1. Prim in Stream, including a prim that arrives through Prototype Input 2 (merged into the stream)
    set_rows([CRATE,BARREL]);d=read();s=d['Stage']
    targets=[x.pathString for x in UsdGeom.PointInstancer(s.GetPrimAtPath('/World/Arraytron')).GetPrototypesRel().GetTargets()]
    assert targets==['/World/Arraytron/Prototypes/Crate','/World/Arraytron/Prototypes/Barrel'],targets
    for original in ('/World/Props/Crate','/World/Props/Barrel'):assert UsdGeom.Imageable(s.GetPrimAtPath(original)).ComputeVisibility()=='invisible'
    # 2. Input Connection: automatic prim, explicit prim, errors
    set_rows([CRATE,{'type':1,'input':0}]);d=read()
    assert a.hdaModule().resolve(a)[1]['path']=='/World/Props/Barrel' and 'Input Connection (Input 2)  /World/Props/Barrel' in a.parm('proto_summary').eval()
    assert 'Barrel' in [x.pathString.split('/')[-1] for x in UsdGeom.PointInstancer(d['Stage'].GetPrimAtPath('/World/Arraytron')).GetPrototypesRel().GetTargets()]
    set_rows([CRATE,{'type':1,'input':0,'inprim':'/World/Props/Barrel'}]);read()
    set_rows([CRATE,{'type':1,'input':0,'inprim':'/World/Props/Nope'}]);expect_error('/World/Props/Nope does not exist in Input 2')
    set_rows([CRATE,{'type':1,'input':1}]);expect_error('Input 3, which is not connected')
    ambiguous=STAGE.createNode('pythonscript','test_ambiguous');ambiguous.parm('python').set('from pxr import UsdGeom\ns=hou.pwd().editableStage()\nUsdGeom.Cube.Define(s,"/X/A");UsdGeom.Cube.Define(s,"/Y/B")')
    a.setInput(2,ambiguous);set_rows([CRATE,{'type':1,'input':1}]);expect_error('several top-level primitives')
    set_rows([CRATE,{'type':1,'input':1,'inprim':'/Y/B'}]);read()
    single=STAGE.createNode('pythonscript','test_single');single.parm('python').set('from pxr import UsdGeom\ns=hou.pwd().editableStage()\nUsdGeom.Xform.Define(s,"/Wrap");UsdGeom.Xform.Define(s,"/Wrap/Inner");UsdGeom.Cube.Define(s,"/Wrap/Inner/Shape")')
    a.setInput(2,single);set_rows([CRATE,{'type':1,'input':1}]);assert a.hdaModule().resolve(a)[1]['path']=='/Wrap/Inner/Shape','auto pick descends single-child chains to the gprim'
    a.setInput(2,None);ambiguous.destroy();single.destroy()
    # 3. USD File: default prim, explicit prim, staged hidden reference, errors
    set_rows([CRATE,ROCK]);d=read();s=d['Stage'];staged='/World/Arraytron_Sources/Proto_02_rock'
    assert staged in stage_prims() and s.GetPrimAtPath(staged).HasAuthoredReferences()
    assert UsdGeom.Imageable(s.GetPrimAtPath(staged)).ComputeVisibility()=='invisible' and a.hdaModule().resolve(a)[1]['path']==staged
    set_rows([CRATE,dict(ROCK,fileprim='/Rock')]);read()
    set_rows([CRATE,dict(ROCK,file=str(ROOT/'dist/test_assets/missing.usda'))]);expect_error('cannot open the USD file')
    set_rows([CRATE,dict(ROCK,fileprim='/Nope')]);expect_error('/Nope does not exist')
    temp=tempfile.mkdtemp();nodefault=os.path.join(temp,'nodefault.usda')
    from pxr import Usd
    ts=Usd.Stage.CreateNew(nodefault);UsdGeom.Cube.Define(ts,'/Thing');ts.GetRootLayer().Save()
    set_rows([CRATE,dict(ROCK,file=nodefault)]);expect_error('has no default prim')
    set_rows([CRATE,dict(ROCK,file=nodefault,fileprim='/Thing')]);read()
    set_rows([CRATE,dict(ROCK,file='')]);expect_error('USD File is empty')
    # 4. SOP Geometry
    geo=hou.node('/obj').createNode('geo','test_proto_geo');box=geo.createNode('box','b');box.setDisplayFlag(True);box.setRenderFlag(True)
    set_rows([CRATE,{'type':3,'sop':box.path()}]);d=read();sp='/World/Arraytron_Sources/Proto_02_b'
    assert sp in stage_prims() and UsdGeom.Mesh(d['Stage'].GetPrimAtPath(sp+'/mesh_0')) and UsdGeom.Imageable(d['Stage'].GetPrimAtPath(sp)).ComputeVisibility()=='invisible'
    set_rows([CRATE,{'type':3,'sop':''}]);expect_error('SOP Path is empty')
    set_rows([CRATE]+[{'type':3,'sop':box.path()}]*4);d=read();assert len(d['Stage'].GetPrimAtPath('/World/Arraytron/Prototypes').GetChildren())==5     # four SOP slots + the crate
    set_rows([CRATE]+[{'type':3,'sop':box.path()}]*5);expect_error('at most 4 SOP Geometry')
    geo.destroy();reset()
def bank_rules():
    set_rows([CRATE,CRATE]);expect_error('resolve to the same prim /World/Props/Crate: change the source of one of them')
    set_rows([CRATE,{'type':0,'prim':''}]);expect_error('Prim Path is empty')
    set_rows([CRATE,{'type':0,'prim':'/World/Props/Missing'}]);expect_error('/World/Props/Missing does not exist or is inactive')
    set_rows([dict(CRATE,on=0)]);expect_error('no enabled prototypes')
    set_rows([CRATE,{'type':0,'prim':'','on':0},{'type':2,'file':'','on':0},{'type':1,'input':1,'on':0}]);d=read()      # disabled rows with empty or invalid sources are ignored
    assert len(UsdGeom.PointInstancer(d['Stage'].GetPrimAtPath('/World/Arraytron')).GetPrototypesRel().GetTargets())==1
    set_rows([CRATE,dict(BARREL,on=0)]);d=read();assert len(UsdGeom.PointInstancer(d['Stage'].GetPrimAtPath('/World/Arraytron')).GetPrototypesRel().GetTargets())==1
    assert set(d['ProtoIndices'])=={0} and UsdGeom.Imageable(d['Stage'].GetPrimAtPath('/World/Props/Barrel')).ComputeVisibility()=='inherited','a disabled entry is neither instanced nor hidden'
    set_rows([dict(CRATE,on=0),BARREL]);d=read();assert set(d['ProtoIndices'])=={0}
    a.parm('outputpath').set('/World/Props/Crate/Out');set_rows([CRATE]);a.parm('outputpath').set('/World/Props/Crate/Out');expect_error('outside the prototype hierarchy')
    reset()
    # two prototypes with the same leaf name under different parents: Houdini renames the second, order is kept
    dup=STAGE.createNode('pythonscript','test_dup');dup.parm('python').set('from pxr import UsdGeom\ns=hou.pwd().editableStage()\nUsdGeom.Cube.Define(s,"/A/Rock");UsdGeom.Sphere.Define(s,"/B/Rock")')
    saved=a.inputs()[0];dup.setInput(0,saved);a.setInput(0,dup)
    set_rows([{'type':0,'prim':'/A/Rock'},{'type':0,'prim':'/B/Rock'}]);d=read()
    names=[x.pathString for x in UsdGeom.PointInstancer(d['Stage'].GetPrimAtPath('/World/Arraytron')).GetPrototypesRel().GetTargets()]
    assert names==['/World/Arraytron/Prototypes/Rock','/World/Arraytron/Prototypes/Rock2'],names
    a.setInput(0,saved);dup.destroy();reset()
def with_points(count):
    a.parm('line_count').set(count);a.parm('line_length').set(0)
def selection_cycle_sequential():
    set_rows([CRATE,BARREL,ROCK]);a.parm('proto_mode').set(3);with_points(10)
    assert picks()[0]==[i%3 for i in range(10)],'Cycle is round robin in id order'
    set_rows([CRATE,dict(BARREL,on=0),ROCK]);a.parm('proto_mode').set(3);with_points(7)
    assert picks()[0]==[i%2 for i in range(7)],'disabled rows are skipped by the cycle'
    # Sequential: blocks in id order sized by weight. 30 points, weights 2:1 -> ids 0..19 then 20..29
    set_rows([dict(CRATE,weight=2),dict(BARREL,weight=1)]);a.parm('proto_mode').set(2);with_points(30)
    assert picks()[0]==[0]*20+[1]*10
    set_rows([dict(CRATE,weight=1),dict(BARREL,weight=0),dict(ROCK,weight=1)]);a.parm('proto_mode').set(2);with_points(10)
    assert picks()[0]==[0]*5+[2]*5,'weight 0 gets no block'
    set_rows([dict(CRATE,weight=0),dict(BARREL,weight=0)]);a.parm('proto_mode').set(2);with_points(200)
    c=Counter(picks()[0]);assert set(c)=={0,1} and abs(c[0]-100)<30,'all weights zero falls back to a uniform choice'
    reset()
def selection_random():
    set_rows([dict(CRATE,weight=1),dict(BARREL,weight=2),dict(ROCK,weight=7)]);a.parm('proto_mode').set(1);with_points(4000)
    idx,d=picks();c=Counter(idx);n=len(idx)
    for k,want in enumerate((.1,.2,.7)):assert abs(c[k]/n-want)<.03,(k,c[k]/n,want)
    assert idx==picks()[0],'deterministic'
    a.parm('proto_seed').set(2);assert picks()[0]!=idx,'seed changes the draw'
    a.parm('proto_seed').set(1)
    # stability: more points keeps every earlier pick; a small weight change moves only the points that cross a boundary
    with_points(4500);assert picks()[0][:4000]==idx,'adding points keeps earlier picks'
    with_points(4000);a.parm('proto_weight3').set(7.5);moved=sum(1 for p,q in zip(idx,picks()[0]) if p!=q)/4000
    assert 0<moved<.04,moved                       # expected about 1.9%
    a.parm('proto_weight3').set(7)
    # Random ignores weights; weight 0 never selected by Weighted Random
    a.parm('proto_mode').set(0);a.parm('proto_weight1').set(0);a.parm('proto_weight2').set(0);c=Counter(picks()[0]);assert all(abs(c[k]/4000-1/3)<.04 for k in range(3))
    a.parm('proto_mode').set(1);a.parm('proto_weight1').set(0);a.parm('proto_weight2').set(0);a.parm('proto_weight3').set(5);assert set(picks()[0])=={2}
    a.parm('proto_weight1').set(0);a.parm('proto_weight2').set(3);a.parm('proto_weight3').set(0);assert set(picks()[0])=={1}
    reset()
def selection_ids():
    set_rows([CRATE,dict(BARREL,on=0),ROCK]);a.parm('proto_mode').set(3);with_points(6)
    geo=a.node(COMPILER+'/'+ASSIGNMENT).geometry();rows=[p.intAttribValue('proto_id') for p in geo.points()];idx=[p.intAttribValue('protoindex') for p in geo.points()]
    assert rows==[1,3,1,3,1,3] and idx==[0,1,0,1,0,1],'proto_id is the bank row (stable when other rows are disabled), protoindex the enabled ordinal'
    reset()
def per_prototype():
    # scale: row scale multiplies, row scale random stays inside +/- amount
    set_rows([dict(CRATE,scale=2),dict(BARREL,scale=.5)]);a.parm('proto_mode').set(3);with_points(6);a.parm('base_scale').set(2)
    d=read()
    for i,sc in enumerate(d['Scales']):assert abs(sc[0]-(4 if i%2==0 else 1))<1e-5 and abs(sc[0]-sc[2])<1e-6
    set_rows([dict(CRATE,scale=3,scalevar=.5)]);with_points(300);d=read()
    xs=[sc[0] for sc in d['Scales']];assert min(xs)>=3*.5-1e-4 and max(xs)<=3*1.5+1e-4 and max(xs)-min(xs)>1.0,(min(xs),max(xs))
    assert xs==[sc[0] for sc in read()['Scales']]
    # rotation offset: the prototype turns first, then the instance rotation (USD rows are left to right)
    set_rows([dict(CRATE,rot=(90,0,0))]);with_points(1);a.parmTuple('base_rotation').set((0,90,0))
    pi=UsdGeom.PointInstancer(read()['Stage'].GetPrimAtPath('/World/Arraytron'));m=pi.ComputeInstanceTransformsAtTime(hou.frame(),hou.frame())[0]
    expected=hou.hmath.buildRotate((90,0,0))*hou.hmath.buildRotate((0,90,0))
    for r in range(3):
        for c in range(3):assert abs(m[r][c]-expected.at(r,c))<2e-4,(r,c,m[r][c],expected.at(r,c))
    set_rows([dict(CRATE,rot=(0,0,0))]);with_points(1);a.parmTuple('base_rotation').set((0,90,0))
    m0=UsdGeom.PointInstancer(read()['Stage'].GetPrimAtPath('/World/Arraytron')).ComputeInstanceTransformsAtTime(hou.frame(),hou.frame())[0]
    assert max(abs(m0[r][c]-m[r][c]) for r in range(3) for c in range(3))>.5,'the offset must actually change the orientation'
    reset()
def summary_text():
    set_rows([CRATE,BARREL]);text=a.parm('proto_summary').eval()
    assert text.splitlines()[0].startswith('0  [row 1] Prim Path  /World/Props/Crate  (weight 1)') and text.splitlines()[1].startswith('1  [row 2] Prim Path  /World/Props/Barrel')
    set_rows([CRATE,CRATE]);assert a.parm('proto_summary').eval().startswith('Cannot resolve the bank: Prototypes 1 and 2 resolve to the same prim')
    set_rows([dict(CRATE,on=0)]);assert 'no enabled prototypes' in a.parm('proto_summary').eval()
    reset()
def modular_network():
    assert [c.name() for c in a.children() if c.name() in ('merge_inputs','SOURCE_RESOLVER','USD_COMPILER','ensure_prototype_visible','bounds_guide','transform_distribution','OUT_ARRAYTRON')]==['merge_inputs','SOURCE_RESOLVER','USD_COMPILER','ensure_prototype_visible','bounds_guide','transform_distribution','OUT_ARRAYTRON']
    assert [c.name() for c in a.children() if c.name().startswith('sop_stage_')]==['sop_stage_1','sop_stage_2','sop_stage_3','sop_stage_4']
    inner=[c.name() for c in a.node('USD_COMPILER').children()]
    for name in ('generate_line','generate_area','generate_grid','DISTRIBUTION_GENERATOR','VARIATION_PROCESSOR','PROTOTYPE_ASSIGNMENT','OUT_POINTS'):assert name in inner,name
    compiler=a.node('USD_COMPILER')
    order=[]
    node=compiler.node('OUT_POINTS')
    while node is not None:
        order.append(node.name());node=node.inputs()[0] if node.inputs() else None
    if a.parm('phys_on') is not None:
        # Physics Settle (v0.4.0): PROTOTYPE_ASSIGNMENT > PHYSICS_WORLD > PHYSICS_SPAWN > PHYSICS_APPLY, selected by PHYSICS_SWITCH (input 0 = the unchanged path);
        # the solver branch (PROXIES > SOLVER, COLLIDERS) is not on the output path, so it only cooks while simulating
        overlap=a.node(COMPILER+'/NO_OVERLAP') is not None
        grow=a.node(COMPILER+'/GROW') is not None;expected=['OUT_POINTS']+(['PROTO_PATH'] if a.node(COMPILER+'/PROTO_PATH') else [])+(['PRIMVARS'] if a.node(COMPILER+'/PRIMVARS') else [])+(['GROW'] if grow else [])+(['OVERRIDES'] if a.node(COMPILER+'/OVERRIDES') else [])+['PHYSICS_SWITCH']+(['NO_OVERLAP'] if overlap else [])+['PROTOTYPE_ASSIGNMENT','VARIATION_PROCESSOR']+(['FALLOFF'] if a.node(COMPILER+'/FALLOFF') else [])+(['FIELD_STACK'] if a.node(COMPILER+'/FIELD_STACK') else [])+(['MASK_PROCESSOR'] if a.node(COMPILER+'/MASK_PROCESSOR') else [])+(['ROWS'] if a.node(COMPILER+'/ROWS') else [])+(['DISTRIBUTION_GENERATOR'] if a.node(COMPILER+'/MASK_PROCESSOR') else [])
        assert order[:len(expected)]==expected,order
        switch=compiler.node('PHYSICS_SWITCH');top='NO_OVERLAP' if overlap else 'PROTOTYPE_ASSIGNMENT';assert [n.name() for n in switch.inputs()]==[top,'PHYSICS_APPLY']
        chain=[];node=compiler.node('PHYSICS_APPLY')
        while node.name()!=top:chain.append(node.name());node=node.inputs()[0]
        assert chain==['PHYSICS_APPLY','PHYSICS_SPAWN','PHYSICS_WORLD'],chain
        assert [n.name() for n in compiler.node('PHYSICS_PROXIES').inputs()]==['PHYSICS_SPAWN'] and compiler.node('PHYSICS_SOLVER').type().name()=='rbdbulletsolver'
        assert [n.name() if n else None for n in compiler.node('PHYSICS_SOLVER').inputs()]==['PHYSICS_PROXIES',None,None,'PHYSICS_COLLIDERS']
        assert compiler.node('OUT_POINTS').isDisplayFlagSet()
    else:
        assert order==['OUT_POINTS','PROTOTYPE_ASSIGNMENT','VARIATION_PROCESSOR','DISTRIBUTION_GENERATOR','generate_line'] or order[:4]==['OUT_POINTS','PROTOTYPE_ASSIGNMENT','VARIATION_PROCESSOR','DISTRIBUTION_GENERATOR'],order
    assert [n.name() for n in compiler.node('DISTRIBUTION_GENERATOR').inputs()]==['generate_line','generate_area','generate_grid']+(['generate_circle'] if CIRCLE else [])+(['generate_curve'] if a.node(COMPILER+'/generate_curve') else [])+(['generate_surface'] if a.node(COMPILER+'/generate_surface') else [])+(['generate_paint'] if a.node(COMPILER+'/generate_paint') else [])+(['generate_cluster'] if a.node(COMPILER+'/generate_cluster') else [])+(['generate_imported'] if a.node(COMPILER+'/generate_imported') else [])+(['generate_place'] if a.node(COMPILER+'/generate_place') else [])+(['generate_biome'] if a.node(COMPILER+'/generate_biome') else [])
    # LOP side order: merge > SOP stagers > resolver > compiler > visibility > guide > transform > output
    lop=[];node=a.node('OUT_ARRAYTRON')
    while node is not None and not node.type().name()=='merge':
        lop.append(node.name());node=node.inputs()[0] if node.inputs() else None
    assert lop==['OUT_ARRAYTRON']+(['debug_guide'] if a.node('debug_guide') else [])+(['camera_optimize'] if a.node('camera_optimize') else [])+['transform_distribution','bounds_guide','ensure_prototype_visible']+(['PROTO_NORMALIZE'] if a.node('PROTO_NORMALIZE') else [])+['USD_COMPILER']+(['LOD_GENERATOR'] if a.node('LOD_GENERATOR') else [])+['SOURCE_RESOLVER','sop_stage_4','sop_stage_3','sop_stage_2','sop_stage_1'],lop
    # the Source Resolver creates no points and no geometry; it only validates and stages hidden file references
    assert a.node('SOURCE_RESOLVER').type().name()=='pythonscript'

# ---------------------------------------------------------------- Circle / Radial (v0.35)
NIDX=(1,2,0)                                    # plane normal axis per Plane menu entry: XZ -> Y, XY -> Z, YZ -> X
BASIS=(((1,0,0),(0,0,-1)),((1,0,0),(0,1,0)),((0,1,0),(0,0,1)))
def expected_circle(plane,radius,count,arc,start):
    u,v=BASIS[plane];full=arc>=359.9999;step=(2*math.pi/count if full else math.radians(arc)/(count-1)) if count>1 else 0.0
    out=[]
    for i in range(count):
        t=math.radians(start)+i*step;out.append(tuple(radius*(math.cos(t)*u[k]+math.sin(t)*v[k]) for k in range(3)))
    return out
def set_circle(plane=0,radius=2,count=4,arc=360,start=0,facing=0):
    reset();a.parm('mode').set(3);a.parm('circle_plane').set(plane);a.parm('circle_radius').set(radius);a.parm('circle_count').set(count)
    a.parm('circle_arc').set(arc);a.parm('circle_start').set(start);a.parm('circle_facing').set(facing)
# (plane, radius, count, arc, start) -> hand-derived points
CIRCLE_CASES=[
 ((0,2,4,360,0),[(2,0,0),(0,0,-2),(-2,0,0),(0,0,2)]),
 ((1,2,4,360,0),[(2,0,0),(0,2,0),(-2,0,0),(0,-2,0)]),
 ((2,2,4,360,0),[(0,2,0),(0,0,2),(0,-2,0),(0,0,-2)]),
 ((0,2,3,180,90),[(0,0,-2),(-2,0,0),(0,0,2)]),
 ((0,2,5,90,0),[(2,0,0),(1.84776,0,-.76537),(1.41421,0,-1.41421),(.76537,0,-1.84776),(0,0,-2)]),
 ((0,3,1,360,30),[(2.59808,0,-1.5)]),
 ((0,2,1,360,-90),[(0,0,2)]),
 ((0,0,5,360,0),[(0,0,0)]*5),
 ((0,2,3,0,90),[(0,0,-2)]*3),
 ((0,1,12,360,0),None),
 ((0,5,2,360,0),[(5,0,0),(-5,0,0)]),
 ((1,5,4,270,0),[(5,0,0),(0,5,0),(-5,0,0),(0,-5,0)]),
 ((1,3,1,360,45),[(2.12132,2.12132,0)]),
 ((0,5,12,359,0),None),
]
def circle_cases():
    for args,points in CIRCLE_CASES:
        set_circle(*args);d=read();pos=d['Positions']
        assert len(pos)==args[2],(args,len(pos))
        want=points or expected_circle(*args)
        assert all(close(p,q,2e-5) for p,q in zip(pos,want)),(args,[tuple(p) for p in pos],want)
        assert list(d['Ids'])==list(range(args[2]))
    # twelve points on a full circle never repeat the first point: the last one is at 330 degrees
    set_circle(0,1,12,360,0);last=read()['Positions'][-1];assert close(last,(math.cos(math.radians(330)),0,.5),2e-5)
    # independent formula check on larger sets, every plane
    for plane in (0,1,2):
        for count,arc,start,radius in ((101,360,0,3),(101,90,17,2.5),(64,270,-120,7),(2,45,10,1)):
            set_circle(plane,radius,count,arc,start);pos=read()['Positions'];want=expected_circle(plane,radius,count,arc,start)
            assert all(close(p,q,3e-5) for p,q in zip(pos,want)),(plane,count,arc,start)
            assert all(abs(tuple(p)[NIDX[plane]])<1e-5 for p in pos),'points stay in the plane'
    # count cap (UI maximum is soft; the VEX clamps to 10000)
    set_circle(0,1,20000,360,0);assert len(read()['Positions'])==10000
    reset()
def circle_readouts():
    set_circle(0,5,12,360,0);assert abs(a.parm('circle_step_out').eval()-30)<1e-9 and abs(a.parm('circle_spacing_out').eval()-5*math.pi/6)<1e-9
    a.parm('circle_count').set(5);a.parm('circle_arc').set(180);assert abs(a.parm('circle_step_out').eval()-45)<1e-9
    a.parm('circle_count').set(1);assert a.parm('circle_step_out').eval()==0 and a.parm('circle_spacing_out').eval()==0
    a.parm('circle_count').set(2);a.parm('circle_arc').set(90);assert abs(a.parm('circle_step_out').eval()-90)<1e-9
    set_circle(1,5,4,270,0);assert abs(a.parm('circle_step_out').eval()-90)<1e-9 and abs(a.parm('circle_spacing_out').eval()-5*math.pi/2)<1e-9
    set_circle(0,5,12,359,0);assert abs(a.parm('circle_step_out').eval()-359/11)<1e-9,'arc 359 uses Count - 1 intervals: the spacing jump the help describes'
    set_circle(0,5,12,360,0);assert abs(a.parm('circle_step_out').eval()-30)<1e-9
    set_circle(0,0,5,360,0);assert a.parm('circle_spacing_out').eval()==0
    set_circle(0,5,5,0,0);assert a.parm('circle_step_out').eval()==0 and a.parm('circle_spacing_out').eval()==0
    # the displayed arc length is the real distance along the arc between neighbours (chord <= arc length, close for small steps)
    set_circle(0,5,200,360,0);pos=read()['Positions'];chord=(hou.Vector3(pos[1])-hou.Vector3(pos[0])).length()
    assert chord<=a.parm('circle_spacing_out').eval()<chord*1.001
    reset()
def facing_matrix(m):return [hou.Vector3(m[r][0],m[r][1],m[r][2]) for r in range(3)]
def circle_facing():
    for plane in (0,1,2):
        n=hou.Vector3(*[1 if k==NIDX[plane] else 0 for k in range(3)]);ref_index=(NIDX[plane]+1)%3
        for facing in (1,2,3):
            set_circle(plane,3,6,300,20,facing);d=read()
            pi=UsdGeom.PointInstancer(d['Stage'].GetPrimAtPath('/World/Arraytron'));mats=pi.ComputeInstanceTransformsAtTime(hou.frame(),hou.frame())
            for p,m in zip(d['Positions'],mats):
                outward=hou.Vector3(p).normalized()
                want={1:outward,2:-outward,3:n.cross(outward)}[facing]
                got=facing_matrix(m)[ref_index]
                assert (got-want).length()<2e-3,(plane,facing,tuple(got),tuple(want))   # orientations are stored as half-precision quaternions
                rows=facing_matrix(m);assert all(abs(r.length()-1)<2e-3 for r in rows),'facing never scales'
        # None keeps the identity rotation
        set_circle(plane,3,6,300,20,0);pi=UsdGeom.PointInstancer(read()['Stage'].GetPrimAtPath('/World/Arraytron'))
        for m in pi.ComputeInstanceTransformsAtTime(hou.frame(),hou.frame()):
            assert all(abs(m[r][c]-(1 if r==c else 0))<2e-3 for r in range(3) for c in range(3))
    # composition: the instance rotation is applied first, then the facing (row vectors left to right)
    for plane in (0,1,2):
        set_circle(plane,3,5,360,0,1);a.parmTuple('base_rotation').set((0,90,0));d=read()
        pi=UsdGeom.PointInstancer(d['Stage'].GetPrimAtPath('/World/Arraytron'));mats=pi.ComputeInstanceTransformsAtTime(hou.frame(),hou.frame())
        n=hou.Vector3(*[1 if k==NIDX[plane] else 0 for k in range(3)]);ref=hou.Vector3(*[1 if k==(NIDX[plane]+1)%3 else 0 for k in range(3)]);side=n.cross(ref)
        for p,m in zip(d['Positions'],mats):
            outward=hou.Vector3(p).normalized();alpha=math.degrees(math.atan2(outward.dot(side),outward.dot(ref)))
            expected=hou.hmath.buildRotate((0,90,0))*hou.hmath.buildRotateAboutAxis(n,alpha)
            assert all(abs(m[r][c]-expected.at(r,c))<2e-3 for r in range(3) for c in range(3)),(plane,tuple(p))
    # Radius 0 stacks the points but facing still follows each point's angle (not a zero-length position vector)
    set_circle(0,0,4,360,0,1);pi=UsdGeom.PointInstancer(read()['Stage'].GetPrimAtPath('/World/Arraytron'))
    for i,m in enumerate(pi.ComputeInstanceTransformsAtTime(hou.frame(),hou.frame())):
        t=math.radians(90*i);assert (facing_matrix(m)[2]-hou.Vector3(math.cos(t),0,-math.sin(t))).length()<2e-3
    # the documented lamp example: a model authored facing +X needs Rotation Offset (0,-90,0) to face outward on the ground plane
    set_circle(0,3,6,360,0,1);a.parmTuple('proto_rot1').set((0,-90,0));d=read()
    pi=UsdGeom.PointInstancer(d['Stage'].GetPrimAtPath('/World/Arraytron'))
    for p,m in zip(d['Positions'],pi.ComputeInstanceTransformsAtTime(hou.frame(),hou.frame())):
        assert (facing_matrix(m)[0]-hou.Vector3(p).normalized()).length()<2e-3,'prototype +X axis points outward'
    # facing follows the Scale Instances / Bounds Transform: it is a local-space rotation, the layout rotation then turns everything
    set_circle(0,3,4,360,0,1);a.parmTuple('bound_r').set((0,90,0));d=read()
    root=UsdGeom.Xformable(UsdGeom.PointInstancer(d['Stage'].GetPrimAtPath('/World/Arraytron'))).ComputeLocalToWorldTransform(hou.frame())
    mats=UsdGeom.PointInstancer(d['Stage'].GetPrimAtPath('/World/Arraytron')).ComputeInstanceTransformsAtTime(hou.frame(),hou.frame())
    for p,w,m in zip(d['Positions'],d['WorldPositions'],mats):
        forward=root.TransformDir(Gf.Vec3d(*[m[2][k] for k in range(3)]));radial=(hou.Vector3(*w)).normalized()
        assert (hou.Vector3(*forward)-radial).length()<2e-3,'forward still points outward after the layout is rotated'
    reset()

# ---------------------------------------------------------------- Variation extras (v0.3.6)
def many(count=3000):
    """A stack of identical points, so the variation is the only thing that differs between instances."""
    reset();a.parm('mode').set(0);a.parm('line_count').set(count);a.parm('line_length').set(0)
def matrices(d):
    pi=UsdGeom.PointInstancer(d['Stage'].GetPrimAtPath('/World/Arraytron'));return pi.ComputeInstanceTransformsAtTime(hou.frame(),hou.frame())
def yaw_degrees(m):return math.degrees(math.atan2(-m[0][2],m[0][0]))
def snapshot(node):
    s=node.stage();assert not node.errors(),node.errors()
    pi=UsdGeom.PointInstancer(s.GetPrimAtPath('/World/Arraytron'));t=hou.frame()
    return {k:list(getattr(pi,'Get'+k+'Attr')().Get(t)) for k in ('Positions','Orientations','Scales','Ids','ProtoIndices')}
OLD_TYPE='arraytron::instancer::0.3.5'
def variation_defaults_match_v035():
    # With the new defaults (Euler XYZ, Fraction +/-, Non-Uniform 0) every output array must equal the real v0.3.5 HDA's, bit for bit.
    hou.hda.installFile(str(versions.hda('v0.3.5')))
    old=STAGE.createNode(OLD_TYPE,'test_v035');old.setInput(0,a.inputs()[0]);old.setInput(1,a.inputs()[1])
    configs=[
      ({'mode':0,'line_count':50,'position_random':(1,.5,2),'rotation_random':(30,60,90),'scale_random':.4,'base_rotation':(10,20,30),'base_scale':1.5,'random_seed':7},'line, all random on'),
      ({'mode':1,'area_count':120,'position_random':(2,0,2),'area_keepinside':1,'rotation_random':(0,180,0),'scale_random':.25,'random_seed':3},'area keep inside'),
      ({'mode':2,'position_random':(.3,.3,.3),'scale_random':.9,'rotation_random':(5,5,5)},'grid'),
      ({'mode':3,'circle_facing':1,'rotation_random':(0,20,0),'scale_random':.2,'circle_count':30,'random_seed':11},'circle facing outward'),
    ]
    for values,label in configs:
        reset();old_node=old
        for node in (a,old_node):
            if node is old_node:
                for p in node.parms():
                    if p.parmTemplate().type() not in (hou.parmTemplateType.Folder,hou.parmTemplateType.FolderSet) and not p.isMultiParmInstance():p.revertToDefaults()
            for key,value in values.items():node.parmTuple(key).set(value if isinstance(value,(tuple,list)) else (value,))
        assert snapshot(a)==snapshot(old_node),label
    # a prototype bank with per-row scale, scale random and rotation offset
    bank=[{'type':0,'prim':'/World/Props/Crate','weight':3,'scale':1.5,'scalevar':.3,'rot':(0,45,0)},{'type':0,'prim':'/World/Props/Barrel','weight':1,'scale':.8}]
    for node in (a,old):
        node.parm('protos').revertToDefaults();node.parm('protos').set(2);node.parm('mode').set(0);node.parm('line_count').set(80);node.parm('proto_mode').set(1)
        for n,row in enumerate(bank,1):
            for key,value in row.items():node.parmTuple(f'proto_{key}{n}').set(value if isinstance(value,(tuple,list)) else (value,))
        node.parmTuple('scale_random').set((.3,));node.parmTuple('rotation_random').set((10,20,30))
    assert snapshot(a)==snapshot(old),'prototype bank'
    old.destroy();reset()
def variation_yaw_only():
    many(400);a.parm('rotation_random_mode').set(1);a.parm('yaw_random').set(90);a.parmTuple('rotation_random').set((45,45,45))
    d=read();mats=matrices(d);yaws=[yaw_degrees(m) for m in mats]
    assert all(abs(m[1][0])<3e-3 and abs(m[1][1]-1)<3e-3 and abs(m[1][2])<3e-3 for m in mats),'Yaw Only keeps every instance level; the hidden X/Z amounts contribute nothing'
    assert min(yaws)>=-91 and max(yaws)<=91 and max(yaws)-min(yaws)>150 and abs(sum(yaws)/len(yaws))<12,(min(yaws),max(yaws))
    assert yaws==[yaw_degrees(m) for m in matrices(read())],'deterministic'
    # Yaw Only with yaw T is exactly Euler XYZ with (0, T, 0): same per-point random stream, same orientation, instance for instance
    many(400);a.parm('rotation_random_mode').set(1);a.parm('yaw_random').set(60);a.parmTuple('rotation_random').set((10,10,10));as_yaw=list(read()['Orientations'])
    a.parm('rotation_random_mode').set(0);a.parmTuple('rotation_random').set((0,60,0));as_euler=list(read()['Orientations'])
    assert as_yaw==as_euler,'Yaw Only must be the Euler Y draw'
    many(400);a.parm('rotation_random_mode').set(1);a.parm('yaw_random').set(90);a.parmTuple('rotation_random').set((45,45,45))
    # the yaw is added to the base Y angle
    a.parmTuple('base_rotation').set((0,30,0));yaws=[yaw_degrees(m) for m in matrices(read())]
    assert min(yaws)>=-61 and max(yaws)<=121 and abs(sum(yaws)/len(yaws)-30)<12,(min(yaws),max(yaws))
    # more points never reshuffles the earlier ones
    a.parm('line_count').set(450);more=[yaw_degrees(m) for m in matrices(read())]
    assert more[:400]==yaws[:400]
    # zero yaw: no random rotation at all
    a.parmTuple('base_rotation').set((0,0,0));a.parm('line_count').set(50);a.parm('yaw_random').set(0)
    assert all(all(abs(m[r][c]-(1 if r==c else 0))<3e-3 for r in range(3) for c in range(3)) for m in matrices(read()))
    # switching back to Euler brings the hidden X/Z amounts back; they were kept
    a.parm('rotation_random_mode').set(0);assert tuple(a.parmTuple('rotation_random').eval())==(45,45,45)
    tilted=[m for m in matrices(read()) if abs(m[1][2])>.05 or abs(m[1][0])>.05];assert len(tilted)>10,'Euler mode tilts again'
    # Euler with an axis amount of 0 locks that axis: only Z varies, so the Y axis image stays in the XY plane
    a.parmTuple('rotation_random').set((0,0,60));a.parm('line_count').set(300);ms=matrices(read())
    assert all(abs(m[1][2])<3e-3 and abs(m[0][2])<3e-3 for m in ms) and max(abs(m[0][1]) for m in ms)>.3
    reset()
def variation_scale_range():
    many(3000);a.parm('base_scale').set(2);a.parm('scale_random_mode').set(1);a.parm('scale_min').set(.6);a.parm('scale_max').set(1.5)
    d=read();xs=[sc[0] for sc in d['Scales']]
    assert all(abs(sc[0]-sc[1])<1e-6 and abs(sc[0]-sc[2])<1e-6 for sc in d['Scales']),'uniform on every axis'
    assert min(xs)>=1.2-1e-4 and max(xs)<=3.0+1e-4 and min(xs)<1.25 and max(xs)>2.95 and abs(sum(xs)/len(xs)-2.1)<.05,(min(xs),max(xs),sum(xs)/len(xs))
    assert xs==[sc[0] for sc in read()['Scales']],'deterministic'
    # Minimum above Maximum is swapped, giving the identical result
    a.parm('scale_min').set(1.5);a.parm('scale_max').set(.6);assert [sc[0] for sc in read()['Scales']]==xs
    # never below 0.0001 times the base scale (a scripted nonpositive Minimum is clamped)
    a.parm('scale_min').set(-3);a.parm('scale_max').set(1);ys=[sc[0] for sc in read()['Scales']]
    assert min(ys)>=2*.0001-1e-6 and max(ys)<=2+1e-4 and min(ys)>0
    # Min / Max values are ignored in Fraction mode, and Fraction mode still means base x (1 +/- amount)
    a.parm('scale_random_mode').set(0);a.parm('scale_min').set(5);a.parm('scale_max').set(9);a.parm('scale_random').set(.25)
    zs=[sc[0] for sc in read()['Scales']];assert min(zs)>=1.5-1e-4 and max(zs)<=2.5+1e-4 and max(zs)-min(zs)>.9
    # the uniform draw is the same stream in both modes: the same point is the smallest / largest in each
    a.parm('scale_random_mode').set(1);a.parm('scale_min').set(.75);a.parm('scale_max').set(1.25);rs=[sc[0] for sc in read()['Scales']]
    assert all(abs(p-q)<2e-4 for p,q in zip(zs,rs)),'0.75..1.25 of base equals +/-0.25 of base: identical per point'
    reset()
def variation_nonuniform():
    many(3000);a.parm('base_scale').set(2);a.parmTuple('scale_nonuniform').set((0,.25,0));d=read();sc=d['Scales']
    assert all(abs(v[0]-2)<1e-6 and abs(v[2]-2)<1e-6 for v in sc),'axes with 0 stay locked at Base Scale'
    ys=[v[1] for v in sc];assert min(ys)>=1.5-1e-4 and max(ys)<=2.5+1e-4 and min(ys)<1.55 and max(ys)>2.45
    # on top of the uniform variation: x and z share the uniform factor, y has its own extra factor
    a.parm('scale_random').set(.3);a.parmTuple('scale_nonuniform').set((0,.25,0));sc=read()['Scales']
    assert all(abs(v[0]-v[2])<1e-6 for v in sc) and all(.75-1e-3<=v[1]/v[0]<=1.25+1e-3 for v in sc)
    # enabling Non-Uniform leaves the uniform draw alone
    a.parmTuple('scale_nonuniform').set((0,0,0));plain=read()['Scales'];a.parmTuple('scale_nonuniform').set((0,.3,0));with_nu=read()['Scales']
    assert all(abs(p[0]-q[0])<1e-6 and abs(p[2]-q[2])<1e-6 for p,q in zip(plain,with_nu))
    # distinct amounts per axis: each axis follows ITS OWN amount (a swapped or shared amount would show up here)
    a.parm('scale_random').set(0);a.parmTuple('scale_nonuniform').set((.1,.3,.5));sc=read()['Scales']
    for k,amount in enumerate((.1,.3,.5)):
        ratios=[v[k]/2 for v in sc]
        assert min(ratios)>=1-amount-1e-3 and max(ratios)<=1+amount+1e-3 and min(ratios)<1-amount+.03 and max(ratios)>1+amount-.03,(k,amount,min(ratios),max(ratios))
    # all three axes vary independently, and each stays inside its own +/- amount (an amount above 0.99 is clamped)
    a.parm('scale_random').set(0);a.parmTuple('scale_nonuniform').set((.5,.5,.5));sc=read()['Scales']
    xs=[v[0]/2 for v in sc];ys=[v[1]/2 for v in sc];zs=[v[2]/2 for v in sc]
    mean=lambda v:sum(v)/len(v)
    corr=lambda u,v:sum((p-mean(u))*(q-mean(v)) for p,q in zip(u,v))/math.sqrt(sum((p-mean(u))**2 for p in u)*sum((q-mean(v))**2 for q in v))
    assert all(.5-1e-3<=t<=1.5+1e-3 for t in xs+ys+zs) and abs(corr(xs,ys))<.1 and abs(corr(ys,zs))<.1 and abs(corr(xs,zs))<.1
    a.parmTuple('scale_nonuniform').set((5,5,5));sc=read()['Scales'];assert all(2*.01-1e-4<=v[k]<=2*1.99+1e-4 for v in sc for k in range(3)) and min(v[0] for v in sc)<.1
    # stability: more points keep every earlier draw, also with Non-Uniform on
    a.parmTuple('scale_nonuniform').set((.3,.3,.3));a.parm('line_count').set(3000);first=read()['Scales'];a.parm('line_count').set(3300)
    assert read()['Scales'][:3000]==first
    # the Prototype Bank scale multiplies every axis and keeps the proportions
    reset();a.parm('mode').set(0);a.parm('line_count').set(60);a.parmTuple('scale_nonuniform').set((.2,.4,.1));base=read()['Scales']
    a.parm('protos').set(1);a.parmTuple('proto_scale1').set((2,));scaled=read()['Scales']
    assert all(abs(q[k]-2*p[k])<2e-5 for p,q in zip(base,scaled) for k in range(3))
    reset()
def variation_positions_untouched():
    # the new controls never move a point: jitter and the other random streams are unchanged by the modes
    many(200);a.parmTuple('position_random').set((1,2,3));p0=read()['Positions']
    a.parm('rotation_random_mode').set(1);a.parm('yaw_random').set(120);a.parm('scale_random_mode').set(1);a.parmTuple('scale_nonuniform').set((.2,.2,.2))
    assert read()['Positions']==p0
    reset()

def demo_baseline():
    s=hou.node('/stage/karma_xpu').stage()
    assert hou.node('/stage/reference_test_crate').evalParm('filepath1').endswith('/test_assets/crate.usda')
    wanted=[('/World/Arraytron',9),('/World/ArraytronArea',80 if BANK else 60)]+([('/World/ArraytronGrid',27)] if GRID else [])+([('/World/ArraytronCircle',14)] if CIRCLE else [])
    for path,count in wanted:
        pi=UsdGeom.PointInstancer(s.GetPrimAtPath(path));assert len(pi.GetPositionsAttr().Get(hou.frame()))==count,(path,count)
        assert UsdGeom.Imageable(s.GetPrimAtPath(pi.GetPrototypesRel().GetTargets()[0])).ComputeVisibility()=='inherited'
    assert hou.node('/stage/reference_demo_floor').isDisplayFlagSet(),'display flag must sit upstream of the Karma settings so the guide is visible'
    # The demo area uses Keep Inside Area with jitter 2: every instance must lie inside its 8 x 6 rectangle.
    area=hou.node('/stage/Arraytron_Area');assert area.evalParm('area_keepinside')==1
    pi=UsdGeom.PointInstancer(s.GetPrimAtPath('/World/ArraytronArea'))
    assert all(abs(p[0])<=4+1e-4 and abs(p[2])<=3+1e-4 for p in pi.GetPositionsAttr().Get(hou.frame()))

check(f'Saved {TAG} demo: instance counts, Keep Inside Area honoured, display flag upstream of Karma settings',demo_baseline)
check('UI contract: numeric menu tokens, folder/field conditionals, read-only fields, layout, prim pickers',ui_contract)
check('Viewport handle: all 12 Bounds Transform parms bound to the stock LOP transform handle',handle_binding)
check('Line By Count: 48 scenarios with Bounds Position, complete USD arrays and extents',line_by_count)
check('Line By Spacing: count = floor(Length/Spacing)+1, centred span, custom direction, 10000 cap, zero-spacing guard',line_by_spacing)
check('Line read-only Spacing matches Length/(Count-1) and the measured point gap',line_readouts_by_count)
check('Custom normalized Line direction, reverse direction, zero-vector fallback',custom_direction)
check('Area bounds, counts, seeds, position independence and zero size',area_contract)
check('Keep Inside Area: reflect-not-clamp, in-bounds points untouched, Y free, Line/Grid unaffected, deterministic',keep_inside)
if GRID:
    check('Grid: 13 hand-derived cases (counts, first/last, ids) plus a full formula check of every point',grid_cases)
    check('Grid read-only Spacing / Resulting Count / Occupied Size / Total Points and the high-count warning',grid_readouts)
    check('Grid caps at 100 per axis (1,000,000 points checked at SOP level)',grid_cap)
    check('Grid ids run X fastest and stay stable when Z layers are added',grid_ids_stable)
if CIRCLE:
    check('Circle: hand-derived points for XZ/XY/YZ, arcs, start angle, count 1, radius 0, no repeated point, formula check, cap',circle_cases)
    check('Circle read-only Angle Step and Spacing (local)',circle_readouts)
    check('Circle Facing: Outward/Center/Tangent on every plane against composed matrices, instance rotation first, survives the layout rotation',circle_facing)
check('Bounds Transform: SRT about pivot, identical for every mode'+(' and either Scale Instances state' if SCALEINST else '')+', scale clamp',bounds_transform)
if SCALEINST:
    check('Scale Instances toggle: same layout, instances keep their size when off, reset leaves it, Keep Inside unaffected',scale_instances_toggle)
check('Switching modes keeps the shared Bounds Transform',mode_switch_keeps_transform)
check('Reset Bounds Transform button restores defaults',reset_button)
check('Bounds guide: guide purpose, Line/By Spacing/Area'+('/Grid' if GRID else '')+' geometry, pivot marker, toggle off deactivates',guide)
if SCALEINST:
    check('Guide matches the instances in world space with Scale Instances on and off',guide_scale)
check('Guide purpose is excluded from Karma included purposes',guide_purpose)
if BANK:
    check('Prototype Bank UI contract: multiparm entries, source-type conditionals, tags, input labels, defaults',bank_ui)
    check('Four source methods: stream prim, wired input (auto/explicit prim), USD file, SOP geometry, with their errors',source_types)
    check('Bank rules: duplicates, empty, missing, disabled rows, output overlap, same-name prototypes',bank_rules)
    check('Selection: Cycle and Sequential give the exact blocks, zero weights, uniform fallback',selection_cycle_sequential)
    check('Selection: Random and Weighted Random distribution, determinism, seed, stability under change',selection_random)
    check('Stable bank ids: proto_id is the row, protoindex the enabled ordinal',selection_ids)
    check('Per-prototype scale, scale random and rotation offset',per_prototype)
    check('Resolved Prototypes summary and error text',summary_text)
    check('Modular network: named processor stages in the master-plan order',modular_network)
if VAREXTRAS:
    check('Variation extras: with the new defaults every output array equals the real v0.3.5 HDA bit for bit (line, area, grid, circle, prototype bank)',variation_defaults_match_v035)
    check('Variation extras: Yaw Only stays level, adds to the base Y angle, ignores hidden X/Z, is stable; Euler axis amount 0 locks the axis',variation_yaw_only)
    check('Variation extras: Scale Min / Max range, swapped bounds, 0.0001 floor, Fraction mode unchanged and the same draw',variation_scale_range)
    check('Variation extras: Non-Uniform scale per axis, locked at 0, independent, clamped, stable, stacks with the bank scale',variation_nonuniform)
    check('Variation extras never move a point',variation_positions_untouched)
check('Paths, overwrite and chained instancers stay valid',paths_and_overwrite)
check('Instance rotation/scale, seeded jitter, stable random streams',instance_transform_and_random)
reset()
versions.validation_json(VID).write_text(json.dumps({'houdini':hou.applicationVersionString(),'hda':a.type().name(),'checks':checks,'passed':True},indent=2))
print('ALL PASSED',len(checks))
