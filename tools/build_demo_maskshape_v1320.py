"""Build the Falloff Mask Shape demo (v1.32.0): hython tools/build_demo_maskshape_v1320.py
A crescent painted with the mask brush (a list of stamps written by the same call the viewport brush uses), scattered in Area mode with the built-in test sphere, three times side by side:
  A  Falloff Shape Mask Shape, Fade Inside: full size and density deep inside the crescent, fading to nothing at its edge, none outside.
  B  Fade Both Sides of the edge, Fade Width 2: a soft border straddling the edge.
  C  The same mask baked to an image (Bake To Image): the paint is no longer evaluated, the Mask Source is an Image and the scatter is the same.
Asserts what the picture should show. Writes dist/Arraytron_<version>_maskshape_crescent_demo.hip (the _maskshape_demo.hip of the Houdini 20.5 folder is the simple setup the user saved: rubber toys on a grid, the Houdini painted crescent) or the Houdini 20.5 / 21 equivalent."""
from pathlib import Path
import sys, hou, json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
from pxr import UsdGeom
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'maskshape_crescent')
hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID);hou.hipFile.save(str(HIP))
stage=hou.node('/stage')
def crescent(a):
    m=a.hdaModule();st=m.maskpaint_data(a)
    for t in np.linspace(0.15*np.pi,0.85*np.pi,24):                                                  # an arc of dabs, a little thicker in the middle
        r=2.4+1.2*np.sin((t-0.15*np.pi)/(0.7*np.pi)*np.pi);st,_=m.maskpaint_add(st,0,(8.0*np.cos(t),0.0,8.0*np.sin(t)-3.0),r,1.0,0.0,1.0,0)
    m.maskpaint_apply(a,st)
def node(name,out,comment,x,**values):
    a=stage.createNode(TYPE,name);assert a.hdaModule().test_setup(a);a.parm('outputpath').set(out);a.parm('mode').set(1);a.parm('area_count').set(9000);a.parmTuple('area_size').set((22.0,16.0)) if a.parmTuple('area_size') else (a.parm('area_sizex').set(22.0),a.parm('area_sizez').set(16.0))
    a.parm('scale_min').set(0.18);a.parm('scale_max').set(0.3);a.parm('mask_source').set(4);a.parm('mask_effect').set(1);a.parm('mask_minscale').set(1.0);crescent(a)
    a.parm('fall_on').set(1);a.parm('fall_shape').set(2);a.parm('fall_mask_depth').set(0);a.parm('fall_density').set(100.0);a.parm('fall_scale').set(0.05);a.parm('fall_curve').set(1);a.parm('fall_inner').set(0.0)
    for k,v in values.items():
        if isinstance(v,(tuple,list)):a.parmTuple(k).set(v)
        else:a.parm(k).set(v)
    a.setPosition((x,0));a.setComment(comment);a.setGenericFlag(hou.nodeFlag.DisplayComment,True);return a
a=node('Arraytron_A_Inside','/World/ArraytronA','A: Falloff Mask Shape, Fade Depth Whole shape, Fade Inside, Edge Density 100, Edge Scale 0.05: the SCALE grades smoothly from the deepest point of the painted crescent to a fine dust at its edge, every point inside is kept and none beyond it.',0,fall_mask_edge=0,fall_mask_width=2.0)
b=node('Arraytron_B_BothSides','/World/ArraytronB','B: Fade Both Sides of the edge, Whole shape inside, Fade Width 1.5 outside: half size at the edge and a ring of tiny instances just beyond it.',4,fall_mask_edge=2,fall_mask_width=1.5)
c=node('Arraytron_C_Baked','/World/ArraytronC','C: the painted mask baked to an image (Bake To Image): no paint is evaluated, the same scatter.',8,fall_mask_edge=0,fall_mask_width=2.0)
c.parm('mask_export_path').set('$HIP/test_assets/arraytron_maskshape_demo.png');c.parm('mask_export_res').set(512);c.hdaModule().mask_bake(c)
merge=stage.createNode('merge','merge_all')
for i,n in enumerate((a,b,c)):merge.setInput(i,n)
merge.setDisplayFlag(True)
def pos(n):
    s=n.stage();return np.array(UsdGeom.PointInstancer(s.GetPrimAtPath(n.evalParm('outputpath'))).GetPositionsAttr().Get(hou.frame())).reshape(-1,3)
for n in (a,b,c):assert not n.errors(),(n.name(),n.errors())
pa,pb,pc=pos(a),pos(b),pos(c);assert c.evalParm('mask_source')==2
ids=lambda n:set(UsdGeom.PointInstancer(n.stage().GetPrimAtPath(n.evalParm('outputpath'))).GetIdsAttr().Get(hou.frame()))
assert len(pa)>300 and len(pb)>len(pa) and len(ids(a)&ids(c))>=0.9*len(ids(a))
sc=lambda n:np.array(UsdGeom.PointInstancer(n.stage().GetPrimAtPath(n.evalParm('outputpath'))).GetScalesAttr().Get(hou.frame())).reshape(-1,3)[:,0]
assert sc(a).max()/sc(a).min()>3.0,'the scale grades from the middle to the edge'
stage.layoutChildren();hou.hipFile.save(str(HIP))
print(json.dumps({'saved':hou.hipFile.path(),'A_inside':len(pa),'B_both_sides':len(pb),'C_baked':len(pc),'baked_same_points':round(len(ids(a)&ids(c))/max(len(ids(a)),1),3)}))
