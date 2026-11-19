"""Build the Select And Edit demo (v1.35.0): hython tools/build_demo_edit_v1350.py
Three Area scatters side by side with the built-in test sphere. Edit tab > Edit Instances is the Edit tool (like the Edit mode of Arraytron Stamp): click an instance (Shift adds or removes),
drag a box, move / rotate / scale with the handle, Del deletes. Every change goes into the node's own edit store (one parameter, live while you drag), not the Override Database. The demo makes the same edits with the functions behind the tool:
  A  a box of instances selected and lifted, turned and scaled with a handle delta (the edit store holds one line per instance), the selection stays selected.
  B  a disc of instances selected and deleted (a round clearing), every other instance keeps its id.
  C  untouched, with a few instances selected: press Edit tab > Edit Instances here and try it yourself.
Asserts what the picture should show. Writes dist/Arraytron_<version>_edit_demo.hip or the Houdini 20.5 / 21 equivalent."""
from pathlib import Path
import sys, hou, json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
from pxr import UsdGeom
VID=versions.BUILD
TYPE=versions.type_name(VID);HIP=versions.demo(VID,'edit')
hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID);hou.hipFile.save(str(HIP))
stage=hou.node('/stage')
def node(name,out,comment,x):
    a=stage.createNode(TYPE,name);assert a.hdaModule().test_setup(a);a.parm('outputpath').set(out);a.parm('mode').set(1);a.parm('area_count').set(3000);a.parm('area_sizex').set(12.0);a.parm('area_sizez').set(12.0)
    a.parm('scale_min').set(0.12);a.parm('scale_max').set(0.2);a.parm('bound_tx').set(x*14.0);a.setPosition((x*4,0));a.setComment(comment);a.setGenericFlag(hou.nodeFlag.DisplayComment,True);return a
def read(n):
    pi=UsdGeom.PointInstancer(n.stage().GetPrimAtPath(n.evalParm('outputpath')));t=hou.frame();return np.array(pi.GetIdsAttr().Get(t),dtype=int),np.array(pi.GetPositionsAttr().Get(t)).reshape(-1,3),np.array(pi.GetScalesAttr().Get(t)).reshape(-1,3)[:,0]
a=node('Arraytron_A_MoveSelection','/World/ArraytronA','A: a box of instances selected, then lifted, turned 45 degrees and scaled 1.6x together with the edit handle (Edit tab).',0)
b=node('Arraytron_B_DeleteSelection','/World/ArraytronB','B: a disc of instances selected and deleted with Del: a round clearing, every other instance keeps its id.',1)
c=node('Arraytron_C_TryIt','/World/ArraytronC','C: untouched. Edit tab > Edit Instances, click or box select, drag the handle, Del deletes, Esc finishes.',2)
for n in (a,b,c):assert not n.errors(),(n.name(),n.errors())
ma=a.hdaModule();ia,pa,sa=read(a);base_n=len(ia)
# A: the instances in a 6 x 6 box, a handle delta about their centre
box=(np.abs(pa[:,0])<3.0)&(np.abs(pa[:,2])<3.0);ids=ia[box];assert box.sum()>100,box.sum()
ma.edit_set_selection(a,ids);assert list(ma.edit_get_selection(a))==sorted(int(i) for i in ids)
snap=ma.edit_snapshot(a);assert snap is not None and len(snap['ids'])==base_n
sel=np.isin(snap['ids'],ids);centre=snap['pos'][sel].mean(axis=0)
delta=dict(t=np.array([0.0,1.5,0.0]),q=ma.edit_quat((0.0,45.0,0.0)),s=np.array([1.6,1.6,1.6]),c=centre)
rows=ma.edit_apply_to_asset(a,snap,ids,delta);assert rows==len(ids),(rows,len(ids))
ia2,pa2,sa2=read(a);order=np.argsort(ia2);pos_by_id=dict(zip(ia2.tolist(),pa2.tolist()));expect,_,_=ma.edit_apply(snap['cur']['P'][sel],snap['cur']['orient'][sel],snap['cur']['scale'][sel],delta,snap['world'])
got=np.array([pos_by_id[int(i)] for i in snap['ids'][sel]]);want=expect@snap['world']['A']+snap['world']['t']
assert np.abs(got-want).max()<1e-3,np.abs(got-want).max()
assert (pa2[np.isin(ia2,ids)][:,1]>1.0).sum()>len(ids)*0.9
untouched=~np.isin(ia2,ids);assert np.abs(pa2[untouched]-pa[np.isin(ia,ia2[untouched])]).max()<1e-6
# a second drag on the same selection adds to the rows (the instances are never edited twice into two rows)
snap2=ma.edit_snapshot(a);rows2=ma.edit_apply_to_asset(a,snap2,ids,dict(t=np.array([0.0,-1.5,0.0]),q=np.array([0.0,0.0,0.0,1.0]),s=np.ones(3),c=centre));assert len(ma.edit_store(a)[0])==len(ids) and a.evalParm('overrides')==0,(len(ma.edit_store(a)[0]),a.evalParm('overrides'))
# B: a disc, deleted
ib,pb,_=read(b);disc=pb[:,0]**2+pb[:,2]**2<9.0;n_disc=int(disc.sum());assert n_disc>50
mb=b.hdaModule();mb.edit_set_selection(b,ib[disc]);removed=mb.edit_delete_selected(b);ib2,pb2,_=read(b)
assert len(ib2)==len(ib)-n_disc and not np.isin(ib2,ib[disc]).any() and len(mb.edit_get_selection(b))==0,(len(ib2),len(ib),n_disc)
# reset brings them back
mb.edit_reset_ids(b,ib[disc]);ib3,_,_=read(b);assert len(ib3)==len(ib)
mb.edit_delete_ids(b,ib[disc])
# C: a few selected, ready
ic,pc,_=read(c);near=np.argsort(np.linalg.norm(pc[:,[0,2]],axis=1))[:25];c.hdaModule().edit_set_selection(c,ic[near])
merge=stage.createNode('merge','merge_all')
for i,n in enumerate((a,b,c)):merge.setInput(i,n)
merge.setDisplayFlag(True);stage.layoutChildren();hou.hipFile.save(str(HIP))
print(json.dumps({'saved':hou.hipFile.path(),'A_edited':len(ma.edit_store(a)[0]),'B_deleted':n_disc,'B_left':len(ib2),'C_selected':len(c.hdaModule().edit_get_selection(c))}))
