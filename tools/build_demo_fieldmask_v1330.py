"""Build the Mask field demo (v1.33.0): hython tools/build_demo_fieldmask_v1330.py
A soft S-shaped stroke like the one painted with Houdini's Attribute Paint brush (a baked Houdini Paint map, Mask Effect None so the paint only gives the SHAPE) scattered in Area mode with the built-in test
sphere, three times side by side with one Field Stack row of the new Mask field:
  A  Keep Off The Mask (Exclude), Margin 0.5: the paint is a hole in the scatter, with a margin around it.
  B  Scatter On The Mask: the instances only where the paint is.
  C  Scatter Around The Mask: a ring of instances a Gap off the edge of the paint, never on it, with a Softness at its edges.
Asserts what the picture should show. Writes dist/Arraytron_<version>_fieldmask_demo.hip or the Houdini 20.5 / 21 equivalent."""
from pathlib import Path
import sys, hou, json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
from pxr import UsdGeom
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'fieldmask')
hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID);hou.hipFile.save(str(HIP))
stage=hou.node('/stage')
CENTRE=lambda x:4.0*np.sin(x*0.38)
def stroke(a):
    m=a.hdaModule();gx=np.linspace(-11,11,220);gz=np.linspace(-8,8,160);X,Z=np.meshgrid(gx,gz);P=np.stack([X.ravel(),np.zeros(X.size),Z.ravel()],1)
    d=np.abs(P[:,2]-CENTRE(P[:,0]));soft=np.clip(1.0-np.clip(d-0.6,0.0,None)/2.2,0.0,1.0);soft=soft*soft*(3.0-2.0*soft)
    grid,spec=m.hpaint_grid(P,soft,0.0,220);a.parm('mask_hpaint_data').set(m.hpaint_encode(grid,spec));a.parm('mask_source').set(5)
def node(name,out,comment,x,mode,**field):
    a=stage.createNode(TYPE,name);assert a.hdaModule().test_setup(a);a.parm('outputpath').set(out);a.parm('mode').set(1);a.parm('area_count').set(14000);a.parm('area_sizex').set(24.0);a.parm('area_sizez').set(18.0)
    a.parm('scale_min').set(0.12);a.parm('scale_max').set(0.2);stroke(a);a.parm('mask_effect').set(3)
    a.parm('fields').set(1);a.parm('field_type1').set(6);a.parm('field_mmode1').set(mode)
    for k,v in field.items():a.parm(k).set(v)
    a.setPosition((x,0));a.setComment(comment);a.setGenericFlag(hou.nodeFlag.DisplayComment,True);return a
a=node('Arraytron_A_KeepOff','/World/ArraytronA','A: Field Stack > Mask > Keep Off The Mask (Margin 0.5): the Houdini Paint is a hole in the scatter. Mask Effect None: the paint only gives the shape.',0,1,field_mgrow1=0.5)
b=node('Arraytron_B_OnMask','/World/ArraytronB','B: Field Stack > Mask > Scatter On The Mask: instances only where the paint is.',4,0)
c=node('Arraytron_C_Around','/World/ArraytronC','C: Field Stack > Mask > Scatter Around The Mask: a ring a Gap (0.6) off the edge, 1.8 wide, softly faded, never on the paint.',8,2,field_mgap1=0.6,field_mring1=1.8,field_msoft1=0.5)
merge=stage.createNode('merge','merge_all')
for i,n in enumerate((a,b,c)):merge.setInput(i,n)
merge.setDisplayFlag(True)
def inst(n):
    s=n.stage();pi=UsdGeom.PointInstancer(s.GetPrimAtPath(n.evalParm('outputpath')));t=hou.frame();return np.array(pi.GetPositionsAttr().Get(t)).reshape(-1,3)
for n in (a,b,c):assert not n.errors(),(n.name(),n.errors())
pa,pb,pc=inst(a),inst(b),inst(c);pa,pb,pc=[p[np.abs(p[:,0])<10.0] for p in (pa,pb,pc)]                  # the stroke runs from X = -11 to 11: judge the points well inside it
cs=lambda p:np.abs(p[:,2]-CENTRE(p[:,0]))                                                         # the distance of every instance to the centre line of the stroke, along Z
assert len(pa)>3000 and len(pb)>600 and len(pc)>600,(len(pa),len(pb),len(pc))
assert cs(pa).min()>1.5 and cs(pb).max()<3.2 and cs(pc).min()>1.5 and cs(pc).max()>cs(pb).max(),(cs(pa).min(),cs(pb).max(),cs(pc).min(),cs(pc).max())      # A leaves the stroke bare, B sits on it, C rings it
stage.layoutChildren();hou.hipFile.save(str(HIP))
print(json.dumps({'saved':hou.hipFile.path(),'A':len(pa),'B':len(pb),'C':len(pc)}))
