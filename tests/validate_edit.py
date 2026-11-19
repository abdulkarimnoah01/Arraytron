"""v1.35.0 in real Houdini: hython tests/validate_edit.py [version]
The Edit tab: a real-time edit store (one text parameter, one line per instance: move, rotation, scale, on) applied by the EDITS stage after the Override Database. Checked: with no edits the node is the release
before; the store text (parse, write, last line wins); a handle delta (Move / Rotate / Scale about a pivot in world space, also under a Bounds Transform) against independent numpy matrices; two drags compose;
delete, reset, restore, reset all, Apply Edits off; edits follow the instance id when the scatter changes; the selection functions; the boxes and the pick under the mouse; the Override Database is not touched.
Env ARRAYTRON_MUTATE=ed_rot|ed_del|ed_ids|ed_pivot breaks the module; the suite must FAIL."""
from pathlib import Path
import hou, json, os, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v1.38.3':'v1.34.1','v1.38.2':'v1.34.1','v1.38.1':'v1.34.1','v1.38.0':'v1.34.1','v1.37.0':'v1.34.1','v1.36.0':'v1.34.1','v1.35.0':'v1.34.1'}[VID]          # the version before the Edit tab
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_edit_'));checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')
def write_scene():
    path=WORK/'edit.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    for name,size in (('Ball',0.2),('Box',0.4)):UsdGeom.Xform.Define(s,'/World/Props/'+name);UsdGeom.Cube.Define(s,'/World/Props/%s/C'%name).CreateSizeAttr(size)
    s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True)
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
def node(stage,source,name='Ed',typ=None,count=300,**values):
    a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(2);a.parm('proto_prim1').set('/World/Props/Ball');a.parm('proto_prim2').set('/World/Props/Box')
    a.parm('mode').set(1);a.parm('area_count').set(count);a.parm('area_sizex').set(8.0);a.parm('area_sizez').set(6.0);a.parmTuple('rotation_random').set((20.0,180.0,20.0));a.parm('scale_random').set(0.3)
    for k,v in values.items():
        pt=a.parmTuple(k)
        if pt is not None:pt.set(v if isinstance(v,(tuple,list)) else (v,))
        else:a.parm(k).set(v)
    if typ is None:mutate(a)
    return a
def all_errors(a):return [e for c in [a]+list(a.allSubChildren()) for e in c.errors()]
def out(a):
    """The instances in world space, sorted by id: ids, world positions, world 3x3 matrices (rotation x scale, column vectors), prototypes."""
    a.stage();errs=all_errors(a);assert not errs,errs;prim=a.stage().GetPrimAtPath(a.evalParm('outputpath'));pi=UsdGeom.PointInstancer(prim);t=hou.frame()
    ids=np.array(pi.GetIdsAttr().Get(t) or [],dtype=np.int64);pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3);sc=np.array(pi.GetScalesAttr().Get(t) or []).reshape(-1,3)
    q=pi.GetOrientationsAttr().Get(t) or [];orient=np.array([[x.GetImaginary()[0],x.GetImaginary()[1],x.GetImaginary()[2],x.GetReal()] for x in q]).reshape(-1,4);pr=np.array(pi.GetProtoIndicesAttr().Get(t) or [],dtype=int)
    W=np.array(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default()),dtype=np.float64).reshape(4,4);A=W[:3,:3].T            # column-vector form of the instancer transform
    world=pos@W[:3,:3]+W[3,:3];M=np.einsum('ij,njk->nik',A,mat(orient,sc));o=np.argsort(ids)
    return dict(ids=ids[o],pos=world[o],M=M[o],proto=pr[o],scale=sc[o])
def mat(q,s):
    q=q/np.linalg.norm(q,axis=1)[:,None];x,y,z,w=q.T;R=np.stack([np.stack([1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],-1),np.stack([2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],-1),np.stack([2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)],-1)],1)
    return R*s[:,None,:]
def rot(axis,deg):
    a=np.asarray(axis,dtype=float);a/=np.linalg.norm(a);t=np.radians(deg);K=np.array([[0,-a[2],a[1]],[a[2],0,-a[0]],[-a[1],a[0],0]]);return np.eye(3)+np.sin(t)*K+(1-np.cos(t))*K@K
def quat_of(R):
    """(x, y, z, w) of a rotation matrix (column vectors), for the handle delta."""
    w=np.sqrt(max(0.0,1+R[0,0]+R[1,1]+R[2,2]))/2;x=np.copysign(np.sqrt(max(0.0,1+R[0,0]-R[1,1]-R[2,2]))/2,R[2,1]-R[1,2]);y=np.copysign(np.sqrt(max(0.0,1-R[0,0]+R[1,1]-R[2,2]))/2,R[0,2]-R[2,0]);z=np.copysign(np.sqrt(max(0.0,1-R[0,0]-R[1,1]+R[2,2]))/2,R[1,0]-R[0,1])
    return np.array([x,y,z,w])
def mutate(a):
    g=a.hdaModule().edits_apply.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='ed_rot':
        good=g['edit_qmul'];g['edits_apply']=_wrap(g['edits_apply'],g,'edit_qmul',lambda a_,b_:good(b_,a_))                                                   # the rotation applied in the instance frame
    elif MUTATE=='ed_del':
        good=g['edits_apply'];g['edits_apply']=lambda *x:(lambda r:(r[0],r[1],r[2],np.zeros_like(r[3]),r[4]))(good(*x))                                         # Delete ignored
    elif MUTATE=='ed_ids':
        good=g['edits_apply'];g['edits_apply']=lambda ids,P,o,s,store:good(np.sort(ids)[::-1].copy(),P,o,s,store)                                               # the store applied to the wrong points
    elif MUTATE=='ed_pivot':
        good=g['edit_apply'];g['edit_apply']=lambda P,o,s,d,world=None:good(P,o,s,dict(d,c=np.zeros(3)),world)                                                  # the pivot ignored
def _wrap(func,g,name,replacement):
    def run(*x):
        old=g[name];g[name]=replacement
        try:return func(*x)
        finally:g[name]=old
    return run
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()
def delta(m,t=(0,0,0),R=np.eye(3),s=1.0,c=(0,0,0)):
    return dict(t=np.asarray(t,dtype=float),q=quat_of(R),s=np.full(3,float(s)),c=np.asarray(c,dtype=float))
def drag(a,ids,d):
    m=a.hdaModule();snap=m.edit_snapshot(a);return m.edit_apply_to_asset(a,snap,ids,d)
def expect(base,ids,d,R):
    """Independent: world positions about the pivot, world matrices turned and scaled, for the ids; everything else unchanged."""
    sel=np.isin(base['ids'],ids);P=base['pos'].copy();M=base['M'].copy()
    P[sel]=((P[sel]-d['c'])*d['s'])@R.T+d['c']+d['t'];M[sel]=np.einsum('ij,njk->nik',R,M[sel])*d['s'][0];return P,M

def defaults():
    st,src=new_scene('defaults');a=node(st,src);b=node(st,src,'Old',typ=OLD_TYPE)
    assert a.parm('edit_data') is not None and a.evalParm('edit_data')=='' and a.evalParm('edit_on')==1 and b.parm('edit_data') is None
    x,y=out(a),out(b)
    for k in ('ids','pos','M','proto'):assert np.allclose(x[k],y[k],atol=2e-3),k                                                                             # no edits: the release before
    names=[t.label() for t in a.parmTemplateGroup().entries() if t.type()==hou.parmTemplateType.Folder and t.folderType()==hou.folderType.Tabs]
    assert names.index('Edit')==names.index('Animate')+1 and names.index('Optimize')==names.index('Edit')+2,names                                            # Edit (then Lookdev) before Optimize
    order=[];n=a.node('USD_COMPILER/OUT_POINTS')
    while n.inputs():n=n.inputs()[0];order.append(n.name())
    assert order.index('EDITS')==order.index('OVERRIDES')-1 and order.index('MIRROR')==order.index('EDITS')-1,order                                       # after the Override Database, before Mirror

def store():
    st,src=new_scene('store');a=node(st,src);m=a.hdaModule()
    ids,rows,on=m.edits_parse('5 1 2 3 0 0 0 1 1 1 1 1\n# a comment\n\n2 0 0 0 0 0 0 1 2 2 2 0\n5 9 9 9 0 0 0 1 1 1 1 1')
    assert list(ids)==[2,5] and np.allclose(rows[1,0:3],(9,9,9)) and list(on)==[False,True]                                                                 # sorted ids, the last line of an id wins
    text=m.edits_text(ids,rows,on);i2,r2,o2=m.edits_parse(text);assert np.array_equal(i2,ids) and np.allclose(r2,rows) and np.array_equal(o2,on)
    assert m.edits_parse('garbage')[0].size==0 and m.edits_parse('')[0].size==0
    q=m.edit_quat((10.0,20.0,30.0));assert np.allclose(m.edit_eulers(q)[0],(10,20,30),atol=1e-6)
    R=rot((0.3,1.0,0.2),70.0);assert np.allclose(m.edit_matrices(m.edit_matrix_quat(R)[None])[0],R,atol=1e-9)
    b=m.edits_merge((ids,rows,on),[5,7],np.zeros((2,10)),[True,False]);assert sorted(b[0].tolist())==[2,5,7] and len(b[0])==3

def handle():
    st,src=new_scene('handle')
    for name,extra in (('Plain',{}),('Bounds',dict(bound_t=(5.0,0.5,-2.0),bound_r=(0.0,30.0,0.0)))):
        a=node(st,src,name,**extra);m=a.hdaModule();base=out(a);ids=base['ids'][::4][:40];c=base['pos'][np.isin(base['ids'],ids)].mean(axis=0)
        R=rot((0.2,1.0,0.1),40.0);d=delta(m,(0.5,1.2,-0.3),R,1.5,c);n=drag(a,ids,d);assert n==len(ids),n
        res=out(a);P,M=expect(base,ids,d,R);assert np.array_equal(res['ids'],base['ids'])
        assert np.abs(res['pos']-P).max()<2e-3,np.abs(res['pos']-P).max();assert np.abs(res['M']-M).max()<3e-3,np.abs(res['M']-M).max()
        assert a.evalParm('overrides')==0 and len(m.edit_store(a)[0])==len(ids)                                                                          # the Override Database is not touched
        R2=rot((1.0,0.0,0.0),25.0);d2=delta(m,(0,-0.4,0),R2,0.8,c+np.array([0.2,0,0]));drag(a,ids,d2);res2=out(a);P2,M2=expect(res,ids,d2,R2)               # a second drag adds to the first
        assert np.abs(res2['pos']-P2).max()<2e-3 and np.abs(res2['M']-M2).max()<3e-3 and len(m.edit_store(a)[0])==len(ids)

def delete_reset():
    st,src=new_scene('delete');a=node(st,src);m=a.hdaModule();base=out(a);ids=base['ids'][10:60]
    drag(a,ids[:20],delta(m,(0,1,0)));m.edit_set_selection(a,ids);assert len(m.edit_get_selection(a))==len(ids)
    m.edit_delete_selected(a);res=out(a);assert len(res['ids'])==len(base['ids'])-len(ids) and not np.isin(res['ids'],ids).any() and len(m.edit_get_selection(a))==0
    assert np.allclose(res['pos'],base['pos'][~np.isin(base['ids'],ids)],atol=1e-6)                                                                         # the others stay where they were, with their ids
    assert len(m.edit_deleted_ids(a))==len(ids);m.edit_restore_deleted(a);res=out(a);assert len(res['ids'])==len(base['ids'])
    moved=np.isin(res['ids'],ids[:20]);assert np.allclose(res['pos'][moved],base['pos'][moved]+(0,1,0),atol=1e-4)                                            # restored, their move kept
    m.edit_reset_ids(a,ids[:10]);res=out(a);back=np.isin(res['ids'],ids[:10]);assert np.allclose(res['pos'][back],base['pos'][back],atol=1e-6) and np.allclose(res['pos'][np.isin(res['ids'],ids[10:20])],base['pos'][np.isin(base['ids'],ids[10:20])]+(0,1,0),atol=1e-4)
    a.parm('edit_on').set(0);assert np.allclose(out(a)['pos'],base['pos'],atol=1e-6);a.parm('edit_on').set(1)                                              # Apply Edits off: as generated, edits kept
    assert len(m.edit_store(a)[0])>0;m.edit_clear(a);assert a.evalParm('edit_data')=='' and np.allclose(out(a)['pos'],base['pos'],atol=1e-6)
    if hou.undos.areEnabled():hou.undos.performUndo();assert a.evalParm('edit_data')!=''                                                                   # Reset All Edits is undoable (when undo is on: the interface)

def follows_id():
    st,src=new_scene('ids');a=node(st,src,count=200);m=a.hdaModule();base=out(a);ids=base['ids'][::5]
    drag(a,ids,delta(m,(0,2,0)));a.parm('area_count').set(320);res=out(a)
    gen=node(st,src,'Gen',count=320);ref=out(gen)
    edited=np.isin(res['ids'],ids);assert edited.sum()==len(ids) and np.array_equal(res['ids'],ref['ids'])
    assert np.allclose(res['pos'][edited],ref['pos'][edited]+(0,2,0),atol=1e-4) and np.allclose(res['pos'][~edited],ref['pos'][~edited],atol=1e-6)        # the same instances, by id, after the scatter changed

def selection():
    st,src=new_scene('select');a=node(st,src);m=a.hdaModule();base=out(a)
    assert m.edit_select_all(a)==len(base['ids']) and len(m.edit_get_selection(a))==len(base['ids'])
    m.edit_set_selection(a,base['ids'][:10]);assert m.edit_select_invert(a)==len(base['ids'])-10 and not np.isin(m.edit_get_selection(a),base['ids'][:10]).any()
    m.edit_select_none(a);assert len(m.edit_get_selection(a))==0 and 'Nothing selected' in m.edit_info(a)
    es=m.edit_display(a);assert np.array_equal(np.sort(es['ids']),base['ids'])
    k=17;p=es['pos'][k];under=m.edit_under(es,p+(0,20,0),(0,-1,0));assert under is not None and np.linalg.norm(es['pos'][under][[0,2]]-p[[0,2]])<=es['radius'][under]+1e-6   # the pick from above
    assert m.edit_under(es,(100,20,100),(0,-1,0)) is None
    C=m.edit_corners(es,[k]);assert C.shape==(1,8,3) and np.allclose(C[0].mean(axis=0),p,atol=0.25)                                                       # the box round the instance
    d=delta(m,(1,0,0));assert np.allclose(m.edit_move_corners(C,d),C+(1,0,0))
    pts=es['pos'];hit=m.edit_select_in_rays(pts,[((-1,10,-1),(0,-1,0)),((1,10,-1),(0,-1,0)),((1,10,1),(0,-1,0)),((-1,10,1),(0,-1,0))])                       # a box select seen from above
    inside=np.nonzero((np.abs(pts[:,0])<=1)&(np.abs(pts[:,2])<=1))[0];assert sorted(hit)==sorted(inside.tolist()) and len(hit)>0

def main():
    for name,func in (('No edits: the release before; the Edit tab before Optimize; EDITS after the Override Database',defaults),
                      ('The edit store: parse, write, the last line of an id wins, quaternion and Euler',store),
                      ('A handle delta (move, rotate, scale about a pivot), also under a Bounds Transform; two drags compose',handle),
                      ('Delete, Restore Deleted, Reset Selected, Apply Edits off, Reset All Edits (undoable)',delete_reset),
                      ('Edits follow the instance id when the scatter changes',follows_id),
                      ('Selection, boxes, the pick under the mouse, box select',selection)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_edit_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
