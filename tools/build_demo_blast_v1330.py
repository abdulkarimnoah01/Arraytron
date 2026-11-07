"""Build the Blast demo (v1.33.0): hython tools/build_demo_blast_v1330.py
Seven Area scatters side by side with the built-in test sphere, each with Blast (Scatter tab) switched on:
  A  Select By Region (a sphere), Delete: a round clearing.
  B  Select By Random 35 percent, Delete, Invert: only that random third stays.
  C  Select By Region (a box), Transform: the selected instances are lifted, turned and scaled together about their own centre, as one group.
  D  Select By Id Pattern 0-1999:2, Delete: every second instance of the first two thousand.
  E  Select By Region (Hexagon), Delete; F  Region Star (7 tips); G  Region Metaballs (5 melting balls), Delete.
  H  Select By Custom: the instances inside a lasso (the ids of a hand selection made with Select In Viewport), Transform: lifted together.
Asserts what the picture should show. Writes dist/Arraytron_<version>_blast_demo.hip or the Houdini 20.5 / 21 equivalent."""
from pathlib import Path
import sys, hou, json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
from pxr import UsdGeom
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'blast')
hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID);hou.hipFile.save(str(HIP))
stage=hou.node('/stage')
def node(name,out,comment,x,**values):
    a=stage.createNode(TYPE,name);assert a.hdaModule().test_setup(a);a.parm('outputpath').set(out);a.parm('mode').set(1);a.parm('area_count').set(4000);a.parm('area_sizex').set(12.0);a.parm('area_sizez').set(12.0)
    a.parm('scale_min').set(0.12);a.parm('scale_max').set(0.2);a.parm('bound_tx').set(x*14.0);a.parm('blast_on').set(1)
    for k,v in values.items():
        if isinstance(v,(tuple,list)):a.parmTuple(k).set(v)
        else:a.parm(k).set(v)
    a.setPosition((x*4,0));a.setComment(comment);a.setGenericFlag(hou.nodeFlag.DisplayComment,True);return a
def read(n):
    pi=UsdGeom.PointInstancer(n.stage().GetPrimAtPath(n.evalParm('outputpath')));t=hou.frame();return np.array(pi.GetIdsAttr().Get(t),dtype=int),np.array(pi.GetPositionsAttr().Get(t)).reshape(-1,3),np.array(pi.GetScalesAttr().Get(t)).reshape(-1,3)[:,0]
a=node('Arraytron_A_RegionClearing','/World/ArraytronA','A: Scatter tab > Blast > Select By Region (sphere, radius 3), Delete: a round clearing.',0,blast_select=2,blast_shape=0,blast_radius=3.0,blast_action=0)
b=node('Arraytron_B_RandomKeep','/World/ArraytronB','B: Select By Random 35 percent + Invert Selection, Delete: only that random third stays.',1,blast_select=1,blast_random=35.0,blast_seed=2,blast_invert=1,blast_action=0)
c=node('Arraytron_C_GroupTransform','/World/ArraytronC','C: Select By Region (box 6 x 6) + Transform: the selected instances are lifted, turned and scaled together as one group about their centre.',2,blast_select=2,blast_shape=1,blast_size=(6.0,100.0,6.0),blast_action=1,blast_move=(0.0,1.5,0.0),blast_rot=(0.0,45.0,0.0),blast_scale=1.5,blast_pivot=0)
d=node('Arraytron_D_EverySecond','/World/ArraytronD','D: Select By Id Pattern 0-1999:2, Delete: every second instance of the first two thousand.',3,blast_select=0,blast_ids='0-1999:2',blast_action=0)
e=node('Arraytron_E_Hexagon','/World/ArraytronE','E: Select By Region > Hexagon (radius 4, turned 15 degrees), Delete: a hexagonal clearing. Triangle, Polygon (your Sides) and Star work the same.',4,blast_select=2,blast_shape=3,blast_radius=4.0,blast_rotate=15.0,blast_action=0)
f=node('Arraytron_F_Star','/World/ArraytronF','F: Select By Region > Star (7 tips, inner radius 45 percent), Delete: a star shaped clearing.',5,blast_select=2,blast_shape=5,blast_radius=5.0,blast_points=7,blast_inner=0.45,blast_action=0)
g=node('Arraytron_G_Metaballs','/World/ArraytronG','G: Select By Region > Metaballs (5 balls that melt into each other), Delete: an organic clearing.',6,blast_select=2,blast_shape=6,blast_radius=2.2,blast_blobs=5,blast_spread=2.5,blast_threshold=0.25,blast_blobseed=3,blast_action=0)
h=node('Arraytron_H_Custom','/World/ArraytronH','H: Select By Custom: the picked ids (made by hand with Select In Viewport: Box, Lasso, Brush or Laser) are lifted and turned together. Here the ids were picked by a lasso in a top view.',7,blast_select=4,blast_action=1,blast_move=(0.0,1.2,0.0),blast_rot=(0.0,30.0,0.0),blast_pivot=0)
ids_h,pos_h,_=read(h)
inside=(pos_h[:,0]-1.0)**2+(pos_h[:,2]+2.0)**2<9.0
h.parm('blast_picked').set(h.hdaModule().ids_to_text(ids_h[inside]))
merge=stage.createNode('merge','merge_all')
for i,n in enumerate((a,b,c,d,e,f,g,h)):merge.setInput(i,n)
merge.setDisplayFlag(True)
for n in (a,b,c,d,e,f,g,h):assert not n.errors(),(n.name(),n.errors())
ia,pa,_=read(a);ib,pb,_=read(b);ic,pc,sc=read(c);id_,pd,_=read(d)
assert len(ia)<4000 and np.linalg.norm(pa[:,[0,2]],axis=1).min()>=3.0-1e-3,(len(ia),np.linalg.norm(pa[:,[0,2]],axis=1).min())
assert 1200<len(ib)<1600,len(ib);assert len(ic)==4000 and (pc[:,1]>1.0).sum()>100 and sc.max()>0.25,((pc[:,1]>1.0).sum(),sc.max());assert len(id_)==4000-1000
ie,pe,_=read(e);if_,pf,_=read(f);ig,pg,_=read(g);ih,ph,sh=read(h)
assert len(ie)<4000 and len(if_)<4000 and len(ig)<4000 and len(ie)>2000 and len(ig)>2000,(len(ie),len(if_),len(ig))
assert inside.sum()>100 and (ph[:,1]>1.0).sum()==inside.sum()
stage.layoutChildren();hou.hipFile.save(str(HIP))
print(json.dumps({'saved':hou.hipFile.path(),'A':len(ia),'B':len(ib),'C_lifted':int((pc[:,1]>1.0).sum()),'D':len(id_),'E':len(ie),'F':len(if_),'G':len(ig),'H_lifted':int((ph[:,1]>1.0).sum())}))
