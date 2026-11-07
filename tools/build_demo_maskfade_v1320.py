"""Build the Edge Fade demo (v1.32.0): hython tools/build_demo_maskfade_v1320.py
A soft S-shaped stroke like the one painted with Houdini's Attribute Paint brush (a baked Houdini Paint map), scattered in Area mode with the built-in test sphere, three times side by side:
  A  the mask as painted: Mask Effect Density + Scale, Min Scale 0: the density IS the mask value and the scale IS the mask value (the soft painted slope).
  B  Edge Fade, Fade Width 0.8: the same stroke with a crisp edge (a narrow fade), whatever softness it was painted with.
  C  Edge Fade, Fade Width 4, Fade Curve Smooth: a long, even slope, with a Scale Response curve that keeps the instances big until the mask is low.
Asserts what the picture should show. Writes dist/Arraytron_<version>_maskfade_demo.hip or the Houdini 20.5 / 21 equivalent."""
from pathlib import Path
import sys, hou, json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
from pxr import UsdGeom
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'maskfade')
hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID);hou.hipFile.save(str(HIP))
stage=hou.node('/stage')
def stroke(a):
    m=a.hdaModule();gx=np.linspace(-11,11,220);gz=np.linspace(-8,8,160);X,Z=np.meshgrid(gx,gz);P=np.stack([X.ravel(),np.zeros(X.size),Z.ravel()],1)
    centre=4.0*np.sin(P[:,0]*0.38);d=np.abs(P[:,2]-centre);soft=np.clip(1.0-np.clip(d-0.6,0.0,None)/2.2,0.0,1.0);soft=soft*soft*(3.0-2.0*soft)         # 1 on the line, a soft slope 2.2 wide
    grid,spec=m.hpaint_grid(P,soft,0.0,220);a.parm('mask_hpaint_data').set(m.hpaint_encode(grid,spec));a.parm('mask_source').set(5)
def node(name,out,comment,x,**values):
    a=stage.createNode(TYPE,name);assert a.hdaModule().test_setup(a);a.parm('outputpath').set(out);a.parm('mode').set(1);a.parm('area_count').set(14000);a.parm('area_sizex').set(24.0);a.parm('area_sizez').set(18.0)
    a.parm('scale_min').set(0.12);a.parm('scale_max').set(0.2);stroke(a);a.parm('mask_effect').set(2);a.parm('mask_minscale').set(0.0)
    for k,v in values.items():
        if isinstance(v,(tuple,list)):a.parmTuple(k).set(v)
        else:a.parm(k).set(v)
    a.setPosition((x,0));a.setComment(comment);a.setGenericFlag(hou.nodeFlag.DisplayComment,True);return a
a=node('Arraytron_A_AsPainted','/World/ArraytronA','A: the mask as painted (Houdini Paint), Mask Effect Density + Scale, Min Scale 0: the density and the scale follow the mask value.',0)
b=node('Arraytron_B_CrispFade','/World/ArraytronB','B: Edge Fade, Fade Width 0.8: the same stroke with a crisp edge, whatever softness it was painted with.',4,mask_fade_on=1,mask_fade_width=0.8,mask_fade_curve=1)
c=node('Arraytron_C_LongFade','/World/ArraytronC','C: Edge Fade, Fade Width 4, Smooth, with a Scale Response curve that keeps the instances big until the mask is low.',8,mask_fade_on=1,mask_fade_width=4.0,mask_fade_curve=1,mask_scale_curve_on=1)
c.parm('mask_scale_curve').set(hou.Ramp((hou.rampBasis.Linear,hou.rampBasis.Linear,hou.rampBasis.Linear),(0.0,0.35,1.0),(0.0,0.9,1.0)))
merge=stage.createNode('merge','merge_all')
for i,n in enumerate((a,b,c)):merge.setInput(i,n)
merge.setDisplayFlag(True)
def inst(n):
    s=n.stage();pi=UsdGeom.PointInstancer(s.GetPrimAtPath(n.evalParm('outputpath')));t=hou.frame()
    return np.array(pi.GetPositionsAttr().Get(t)).reshape(-1,3),np.array(pi.GetScalesAttr().Get(t)).reshape(-1,3)[:,0]
for n in (a,b,c):assert not n.errors(),(n.name(),n.errors())
(pa,sa),(pb,sb),(pc,sc_)=inst(a),inst(b),inst(c);m=a.hdaModule();wa=m.mask_weights(a,m.mask_values(a,pa,np.arange(len(pa))))
xs_=np.linspace(-11,11,900);line=np.stack([xs_,4.0*np.sin(xs_*0.38)],1)
cs=lambda p:np.sqrt(((p[:,None,[0,2]]-line[None,:,:])**2).sum(axis=2)).min(axis=1)                      # the distance of every instance to the centre line of the stroke
assert len(pa)>600 and np.corrcoef(sa,wa)[0,1]>0.99 and np.abs(sa-wa).max()<1e-3,'the scale IS the mask value'
assert cs(pb).max()<cs(pa).max()-0.3 and cs(pc).max()>cs(pa).max()+0.3,(cs(pa).max(),cs(pb).max(),cs(pc).max())      # B has the crisp edge, A the soft slope, C the long one
stage.layoutChildren();hou.hipFile.save(str(HIP))
print(json.dumps({'saved':hou.hipFile.path(),'A':len(pa),'B':len(pb),'C':len(pc),'half_width_A_B_C':[round(float(cs(p).max()),2) for p in (pa,pb,pc)]}))
