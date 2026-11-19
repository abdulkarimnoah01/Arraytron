# Edit tab (v1.35.0): the selection and Edit mode of Arraytron Stamp for the generated instances, a real-time edit system of its own (not the Override Database). The viewer state (src/arraytron_paint_state.py) selects instances (click, Shift+click, box)
# and drags Houdini's own edit handle; here are the functions behind it. What the handle does is stored in the Override Database (the multiparm `overrides`, one row per instance id), so an edit keeps working
# when other settings change, and Reset Selected Edits removes exactly those rows. The selection is kept in the hidden parameter `edit_ids` (sorted ids). Plain numpy functions are tested without a viewport.
import numpy as np

def edit_qmul(a,b):
    """Hamilton product of quaternions (x, y, z, w), (n,4) or (4,): the rotation b followed by the rotation a."""
    a=np.asarray(a,dtype=np.float64);b=np.asarray(b,dtype=np.float64);ax,ay,az,aw=a[...,0],a[...,1],a[...,2],a[...,3];bx,by,bz,bw=b[...,0],b[...,1],b[...,2],b[...,3]
    return np.stack([aw*bx+ax*bw+ay*bz-az*by,aw*by-ax*bz+ay*bw+az*bx,aw*bz+ax*by-ay*bx+az*bw,aw*bw-ax*bx-ay*by-az*bz],axis=-1)

def edit_conj(q):
    q=np.asarray(q,dtype=np.float64);return q*np.array([-1.0,-1.0,-1.0,1.0])

def edit_quat(degrees):
    """Quaternions of rotations about X, then Y, then Z (degrees, R = Rz Ry Rx: the convention of the override rows). degrees: (3,) or (n, 3)."""
    d=np.radians(np.asarray(degrees,dtype=np.float64))*0.5;z=np.zeros(d.shape[:-1])
    qx=np.stack([np.sin(d[...,0]),z,z,np.cos(d[...,0])],axis=-1);qy=np.stack([z,np.sin(d[...,1]),z,np.cos(d[...,1])],axis=-1);qz=np.stack([z,z,np.sin(d[...,2]),np.cos(d[...,2])],axis=-1)
    return edit_qmul(qz,edit_qmul(qy,qx))

def edit_eulers(q):
    """Degrees (n, 3) of quaternions (n, 4) in the convention of edit_quat."""
    q=np.asarray(q,dtype=np.float64).reshape(-1,4);q=q/np.linalg.norm(q,axis=1)[:,None];x,y,z,w=q[:,0],q[:,1],q[:,2],q[:,3]
    r20=2*(x*z-w*y);ry=-np.arcsin(np.clip(r20,-1.0,1.0));lock=np.abs(r20)>=0.999999
    rx=np.where(lock,0.0,np.arctan2(2*(y*z+w*x),1-2*(x*x+y*y)));rz=np.where(lock,np.arctan2(-2*(x*y-w*z),1-2*(x*x+z*z)),np.arctan2(2*(x*y+w*z),1-2*(y*y+z*z)))
    return np.degrees(np.stack([rx,ry,rz],axis=1))

def edit_matrix_quat(M):
    """The quaternion (x, y, z, w) of a rotation matrix (3, 3)."""
    M=np.asarray(M,dtype=np.float64);t=M[0,0]+M[1,1]+M[2,2]
    if t>0:s=np.sqrt(t+1.0)*2;q=[(M[2,1]-M[1,2])/s,(M[0,2]-M[2,0])/s,(M[1,0]-M[0,1])/s,0.25*s]
    elif M[0,0]>M[1,1] and M[0,0]>M[2,2]:s=np.sqrt(1.0+M[0,0]-M[1,1]-M[2,2])*2;q=[0.25*s,(M[0,1]+M[1,0])/s,(M[0,2]+M[2,0])/s,(M[2,1]-M[1,2])/s]
    elif M[1,1]>M[2,2]:s=np.sqrt(1.0+M[1,1]-M[0,0]-M[2,2])*2;q=[(M[0,1]+M[1,0])/s,0.25*s,(M[1,2]+M[2,1])/s,(M[0,2]-M[2,0])/s]
    else:s=np.sqrt(1.0+M[2,2]-M[0,0]-M[1,1])*2;q=[(M[0,2]+M[2,0])/s,(M[1,2]+M[2,1])/s,0.25*s,(M[1,0]-M[0,1])/s]
    q=np.array(q,dtype=np.float64);return q/np.linalg.norm(q)

def edit_matrices(q):
    """Rotation matrices (n, 3, 3) of quaternions (n, 4)."""
    q=np.asarray(q,dtype=np.float64).reshape(-1,4);q=q/np.linalg.norm(q,axis=1)[:,None];x,y,z,w=q[:,0],q[:,1],q[:,2],q[:,3];m=np.empty((len(q),3,3))
    m[:,0,0]=1-2*(y*y+z*z);m[:,0,1]=2*(x*y-z*w);m[:,0,2]=2*(x*z+y*w);m[:,1,0]=2*(x*y+z*w);m[:,1,1]=1-2*(x*x+z*z);m[:,1,2]=2*(y*z-x*w);m[:,2,0]=2*(x*z-y*w);m[:,2,1]=2*(y*z+x*w);m[:,2,2]=1-2*(x*x+y*y);return m

def edit_handle_delta(parms):
    """Houdini's edit handle (Move / Rotate / Scale about a pivot, world space) as dict(t, q, s, c): translate, rotation quaternion, scale, pivot."""
    g=lambda k,d=0.0:float(parms.get(k,d))
    return dict(t=np.array([g('tx'),g('ty'),g('tz')]),q=edit_quat((g('rx'),g('ry'),g('rz'))),s=np.array([g('sx',1.0),g('sy',1.0),g('sz',1.0)]),c=np.array([g('px'),g('py'),g('pz')]))

def edit_world(W):
    """The local-to-world matrix W (4x4, row vectors: the translation is the last row) as dict(A (3,3), t, qw (quaternion of its rotation), k (its uniform scale))."""
    W=np.asarray(W,dtype=np.float64).reshape(4,4);A=W[:3,:3];k=float(np.cbrt(abs(np.linalg.det(A)))) or 1.0
    return dict(A=A,t=W[3,:3].copy(),qw=edit_matrix_quat((A/k).T),k=k)                                     # A is the row-vector form (p @ A): its rotation as a quaternion is that of the transpose

EDIT_IDENTITY=edit_world(np.eye(4))

def edit_apply(P,orient,scale,d,world=None):
    """The instances (positions P (n,3), orientations (n,4), scales (n,3), all in the space the points are generated in) moved, turned and scaled by a handle delta (edit_handle_delta, in world space): positions about the
    pivot, orientations turned by the same rotation, scales multiplied. world: edit_world() of the transform from that space to the world (identity when None). Returns the new (P, orient, scale)."""
    w=world or EDIT_IDENTITY;R=edit_matrices(np.asarray(d['q'])[None])[0];P=np.asarray(P,dtype=np.float64);Pw=P@w['A']+w['t']
    Pn=((Pw-d['c'])*d['s'])@R.T+d['c']+d['t'];Pl=(Pn-w['t'])@np.linalg.inv(w['A'])
    q=edit_qmul(edit_conj(w['qw']),edit_qmul(d['q'],w['qw']));o=edit_qmul(q,np.asarray(orient,dtype=np.float64));o=o/np.linalg.norm(o,axis=1)[:,None]
    return Pl,o,np.asarray(scale,dtype=np.float64)*d['s']

def edit_rows_between(pre,post):
    """The override values that turn the generated instances `pre` into `post` (both dict(P, orient, scale), same order): move (n,3), rotation in degrees (n,3), scale (n,) (the mean of the three ratios)."""
    move=np.asarray(post['P'])-np.asarray(pre['P']);rot=edit_eulers(edit_qmul(edit_conj(pre['orient']),post['orient']))
    ratio=np.asarray(post['scale'])/np.maximum(np.abs(np.asarray(pre['scale'])),1e-12);return move,rot,ratio.mean(axis=1)

def edit_select_in_rays(points,rays):
    """Box select: the indices of the points inside the volume the four corner rays of a screen box bound ([(origin, direction)] in order round the box), in front of the camera."""
    P=np.asarray(points,dtype=np.float64).reshape(-1,3)
    if not len(P):return []
    O=np.array([np.asarray(tuple(o),dtype=np.float64) for o,d in rays]);D=np.array([np.asarray(tuple(d),dtype=np.float64) for o,d in rays]);D/=np.linalg.norm(D,axis=1)[:,None]
    L=float(np.abs(P-O.mean(0)).max())+1.0;far=O+D*L;mid=far.mean(0);inside=np.ones(len(P),dtype=bool)
    for i in range(4):
        j=(i+1)%4;n=np.cross(far[i]-O[i],far[j]-O[i])
        if n@(mid-O[i])<0:n=-n
        inside&=(P-O[i])@n>=0
    c=D.mean(0);return np.nonzero(inside&((P-O.mean(0))@c>0))[0].tolist()

def edit_ids_text(ids):
    return ' '.join(str(int(i)) for i in sorted({int(j) for j in ids}))

def edit_ids_parse(text):
    try:ids=np.unique(np.array(str(text).split(),dtype=np.int64))
    except ValueError:ids=np.array(sorted({int(v) for v in str(text).split() if v.lstrip('-').isdigit()}),dtype=np.int64)
    return ids

# ---------------------------------------------------------------- Houdini side
import hou

def edit_get_selection(asset):
    """The selected instance ids (sorted numbers)."""
    return edit_ids_parse(asset.evalParm('edit_ids')) if asset.parm('edit_ids') is not None else np.zeros(0,dtype=np.int64)

def edit_set_selection(asset,ids):
    """Select instances by id. Not an undo step (a selection is not an edit)."""
    text=edit_ids_text(ids)
    if asset.parm('edit_ids') is not None and text!=asset.evalParm('edit_ids'):
        with hou.undos.disabler():asset.parm('edit_ids').set(text)

def edit_world_matrix(asset):
    """The local-to-world matrix of the instancer prim (4x4, identity without a stage)."""
    try:
        from pxr import UsdGeom,Usd
        stage=asset.stage();root=asset.evalParm('outputpath').rstrip('/') or '/'
        for p in stage.Traverse():
            if p.IsA(UsdGeom.PointInstancer) and (str(p.GetPath())+'/').startswith(root+'/'):
                m=UsdGeom.Xformable(p).ComputeLocalToWorldTransform(Usd.TimeCode.Default());return np.array([[m[i][j] for j in range(4)] for i in range(4)],dtype=np.float64)
    except Exception:pass
    return np.eye(4)

def _state(geo):
    n=geo.intrinsicValue('pointcount')
    if n==0:return None
    return dict(P=np.array(geo.pointFloatAttribValues('P')).reshape(-1,3),orient=np.array(geo.pointFloatAttribValues('orient')).reshape(-1,4),scale=np.array(geo.pointFloatAttribValues('scale')).reshape(-1,3),id=np.array(geo.pointIntAttribValues('id'),dtype=np.int64))

def edit_display(asset):
    """The instances as they are rendered, read from the node's own stage (what the viewport shows is what is selected): dict(ids, pos (world positions), xf (n,4,4 local matrices), proto, lo / hi (the box of each prototype),
    radius (of each instance, for picking), W (local to world)). The instances hidden by the camera optimisation or Grow are not in it. None without instances."""
    from pxr import Usd,UsdGeom
    stage=asset.stage()
    if stage is None:return None
    root=asset.evalParm('outputpath').rstrip('/') or '/';prim=None
    for p in stage.Traverse():
        if p.IsA(UsdGeom.PointInstancer) and (str(p.GetPath())+'/').startswith(root+'/'):prim=p;break
    if prim is None:return None
    inst=UsdGeom.PointInstancer(prim);t=Usd.TimeCode(hou.frame());xf=inst.ComputeInstanceTransformsAtTime(t,t)
    if not xf:return None
    n=len(xf);xf=np.asarray(xf,dtype=np.float64).reshape(n,4,4);attr=inst.GetIdsAttr();ids=attr.Get(t) if attr and attr.HasValue() else None
    ids=np.array(list(ids),dtype=np.int64) if ids is not None and len(ids)==n else np.arange(n,dtype=np.int64);pa=inst.GetProtoIndicesAttr().Get(t);proto=np.array(list(pa),dtype=np.int64) if pa is not None and len(pa)==n else np.zeros(n,dtype=np.int64)
    mask=inst.ComputeMaskAtTime(t)
    if mask and len(mask)==n:
        keep=np.array(list(mask),dtype=bool);xf=xf[keep];ids=ids[keep];proto=proto[keep]
    W=edit_world_matrix(asset);w=edit_world(W);targets=inst.GetPrototypesRel().GetTargets();cache=UsdGeom.BBoxCache(Usd.TimeCode.Default(),[UsdGeom.Tokens.default_,UsdGeom.Tokens.render,UsdGeom.Tokens.proxy],useExtentsHint=True)
    lo=np.full((max(len(targets),int(proto.max())+1 if len(proto) else 1),3),-0.5);hi=-lo
    for k,path in enumerate(targets):
        try:
            rng=cache.ComputeLocalBound(stage.GetPrimAtPath(path)).ComputeAlignedRange()
            if not rng.IsEmpty() and all(rng.GetMax()[i]>rng.GetMin()[i] for i in range(3)):lo[k]=np.array(rng.GetMin());hi[k]=np.array(rng.GetMax())
        except Exception:pass
    pos=xf[:,3,:3]@w['A']+w['t'];scale=np.linalg.norm(xf[:,:3,:3],axis=2).max(axis=1)*w['k']
    return dict(ids=ids,pos=pos,xf=xf,proto=proto,lo=lo,hi=hi,radius=0.5*np.linalg.norm(hi-lo,axis=1)[proto]*scale,W=W,world=w)

def edit_corners(es,idx):
    """The eight corners (m, 8, 3), in world space, of the boxes of the instances idx (indices into the display): the box of the prototype turned and scaled like the instance."""
    idx=np.asarray(idx,dtype=np.int64).ravel();k=es['proto'][idx];lo=es['lo'][k];hi=es['hi'][k];X=es['xf'][idx];w=es['world']
    c=np.stack([np.stack([np.where(b&4,hi[:,0],lo[:,0]),np.where(b&2,hi[:,1],lo[:,1]),np.where(b&1,hi[:,2],lo[:,2])],-1) for b in range(8)],1)
    local=np.einsum('mki,mij->mkj',c,X[:,:3,:3])+X[:,3,:3][:,None,:];return local@w['A']+w['t']

def edit_move_corners(corners,d):
    """Boxes (m, 8, 3) moved, turned and scaled by a handle delta (edit_handle_delta): what the viewport shows while the handle drags."""
    R=edit_matrices(np.asarray(d['q'])[None])[0];return ((corners-d['c'])*d['s'])@R.T+d['c']+d['t']

def edit_under(es,origin,direction):
    """The instance under the mouse ray (index into the display) or None: the nearest one to the camera whose centre is closer to the ray than its radius."""
    o=np.asarray(origin,dtype=np.float64);d=np.asarray(direction,dtype=np.float64);d=d/np.linalg.norm(d);v=es['pos']-o;t=v@d
    perp=np.linalg.norm(v-t[:,None]*d[None,:],axis=1);ok=(t>1e-6)&(perp<=np.maximum(es['radius']*0.8,t*0.004))
    if not ok.any():return None
    c=np.nonzero(ok)[0];return int(c[np.argmin(t[c])])

# ---------------------------------------------------------------- the edit store (v1.35.0): one text parameter, one line per edited instance, like the stamps of Arraytron Stamp
# A line is: id  move x y z  rotation quaternion x y z w  scale x y z  on   (on 0 = deleted). Move is added to the position, the rotation turns the orientation (q * orient), the scales multiply.
# The EDITS stage applies it after the Override Database; ids that do not exist are ignored. A drag of the handle rewrites this one parameter, so the edit is live and is one undo step.
EDIT_COLS=12
_EDIT_CACHE=['',None]

def edits_parse(text):
    """The edit store as (ids (m,), rows (m, 11): move, quaternion, scale, on (m,) bool). Parsed once per text."""
    if text==_EDIT_CACHE[0] and _EDIT_CACHE[1] is not None:return _EDIT_CACHE[1]
    body=' '.join(l for l in str(text).splitlines() if l.strip() and not l.lstrip().startswith('#'))
    try:a=np.array(body.split(),dtype=np.float64).reshape(-1,EDIT_COLS) if body else np.zeros((0,EDIT_COLS))
    except ValueError:a=np.zeros((0,EDIT_COLS))
    ids,k=np.unique(a[:,0].astype(np.int64)[::-1],return_index=True);a=a[::-1][k]                    # an id written twice: the last line wins
    out=(ids,a[:,1:11].copy(),a[:,11]>0.5);_EDIT_CACHE[0]=text;_EDIT_CACHE[1]=out;return out

def edits_text(ids,rows,on):
    """The edit store as text (sorted by id)."""
    order=np.argsort(ids,kind='stable');f='%d'+' %.7g'*10+' %d'
    return '\n'.join(f%((int(i),)+tuple(r)+(int(o),)) for i,r,o in zip(np.asarray(ids)[order],np.asarray(rows)[order].tolist(),np.asarray(on)[order]))

def edits_merge(base,ids,rows,on):
    """The store `base` (edits_parse) with the rows of these ids replaced or added."""
    bi,br,bo=base;ids=np.asarray(ids,dtype=np.int64);keep=~np.isin(bi,ids)
    return np.concatenate([bi[keep],ids]),np.concatenate([br[keep],np.asarray(rows,dtype=np.float64).reshape(-1,10)]),np.concatenate([bo[keep],np.asarray(on,dtype=bool)])

def edits_apply(ids,P,orient,scale,store):
    """Apply the store to point arrays (numpy, every point at once). Returns (P, orient, scale, drop mask, number of edited points)."""
    eids,rows,on=store;P=np.array(P,dtype=np.float64);orient=np.array(orient,dtype=np.float64);scale=np.array(scale,dtype=np.float64);ids=np.asarray(ids,dtype=np.int64);drop=np.zeros(len(ids),dtype=bool)
    if not len(eids) or not len(ids):return P,orient,scale,drop,0
    j=np.clip(np.searchsorted(eids,ids),0,len(eids)-1);hit=eids[j]==ids;k=j[hit]
    P[hit]+=rows[k,0:3];o=edit_qmul(rows[k,3:7],orient[hit]);orient[hit]=o/np.linalg.norm(o,axis=1)[:,None];scale[hit]*=rows[k,7:10];drop[hit]=~on[k]
    return P,orient,scale,drop,int(hit.sum())

def edits_between(pre,post):
    """Store rows (n, 10) that turn the instances `pre` into `post` (dict(P, orient, scale), same order)."""
    q=edit_qmul(np.asarray(post['orient']),edit_conj(np.asarray(pre['orient'])));q=q/np.linalg.norm(q,axis=1)[:,None]
    return np.concatenate([np.asarray(post['P'])-np.asarray(pre['P']),q,np.asarray(post['scale'])/np.where(np.abs(pre['scale'])<1e-12,1.0,pre['scale'])],axis=1)

def edit_store(asset):
    return edits_parse(asset.evalParm('edit_data')) if asset.parm('edit_data') is not None else (np.zeros(0,dtype=np.int64),np.zeros((0,10)),np.zeros(0,dtype=bool))

def sop_edits(geo,asset):
    """EDITS: the edit store applied to the points (after the Override Database). Ids are never changed; deleted instances are removed."""
    geo.addAttrib(hou.attribType.Global,'edit_count',0)
    if not asset.evalParm('edit_on') or not asset.evalParm('edit_data').strip():return
    n=geo.intrinsicValue('pointcount')
    if n==0:return
    s=_state(geo);P,o,sc,drop,count=edits_apply(s['id'],s['P'],s['orient'],s['scale'],edit_store(asset))
    geo.setGlobalAttribValue('edit_count',count)
    if not count:return
    geo.setPointFloatAttribValues('P',P.ravel().tolist());geo.setPointFloatAttribValues('orient',o.ravel().tolist());geo.setPointFloatAttribValues('scale',sc.ravel().tolist())
    idx=np.nonzero(drop)[0]
    if len(idx):geo.deletePoints([geo.point(int(i)) for i in idx])

def edit_snapshot(asset):
    """The instances as the EDITS stage sees them: `pre` (what reaches it) and `cur` (what it makes of them), by id, plus the transform to the world. None when there are no instances."""
    ed=asset.node('USD_COMPILER/EDITS')
    if ed is None:raise hou.NodeError('This node has no EDITS stage.')
    cur=_state(ed.geometry());pre=_state(ed.inputs()[0].geometry())
    if cur is None or pre is None:return None
    order=np.argsort(pre['id']);sp=pre['id'][order];j=np.clip(np.searchsorted(sp,cur['id']),0,len(sp)-1);ok=sp[j]==cur['id'];k=order[j[ok]]
    cur={key:v[ok] for key,v in cur.items()};pre={key:v[k] for key,v in pre.items()};W=edit_world_matrix(asset);w=edit_world(W)
    return dict(pre=pre,cur=cur,ids=cur['id'],world=w,W=W,pos=cur['P']@w['A']+w['t'])

def edit_drag_text(base,snap,ids,d):
    """The store text after the handle delta d on these instances (from the snapshot taken when the drag began)."""
    sel=np.nonzero(np.isin(snap['ids'],np.asarray(ids,dtype=np.int64)))[0]
    if not len(sel):return edits_text(*base)
    cur=snap['cur'];pre=snap['pre'];P,o,s=edit_apply(cur['P'][sel],cur['orient'][sel],cur['scale'][sel],d,snap['world'])
    rows=edits_between(dict(P=pre['P'][sel],orient=pre['orient'][sel],scale=pre['scale'][sel]),dict(P=P,orient=o,scale=s))
    return edits_text(*edits_merge(base,snap['ids'][sel],rows,np.ones(len(sel),dtype=bool)))

def edit_set_data(asset,text,label=None):
    if text==asset.evalParm('edit_data'):return
    if label:
        with hou.undos.group(label):asset.parm('edit_data').set(text)
    else:asset.parm('edit_data').set(text)

def edit_apply_to_asset(asset,snap,ids,d):
    """The handle delta d applied to the instances (one undo step). Returns how many instances it edited."""
    edit_set_data(asset,edit_drag_text(edit_store(asset),snap,ids,d),'Arraytron edit instances');return int(np.isin(snap['ids'],np.asarray(ids,dtype=np.int64)).sum())

def edit_delete_ids(asset,ids):
    """Delete instances (their line says on 0, their other edits are kept). One undo step."""
    ids=np.unique(np.asarray(ids,dtype=np.int64))
    if not len(ids):return 0
    base=edit_store(asset);bi,br,bo=base;rows=np.tile(np.array([0,0,0,0,0,0,1,1,1,1],dtype=np.float64),(len(ids),1))
    j=np.clip(np.searchsorted(bi,ids),0,max(len(bi)-1,0))
    if len(bi):
        had=bi[j]==ids;rows[had]=br[j[had]]
    edit_set_data(asset,edits_text(*edits_merge(base,ids,rows,np.zeros(len(ids),dtype=bool))),'Arraytron delete instances');edit_set_selection(asset,[]);return len(ids)

def edit_reset_ids(asset,ids):
    """Remove the edits of the instances: they come back as generated. One undo step."""
    bi,br,bo=edit_store(asset);keep=~np.isin(bi,np.asarray(ids,dtype=np.int64))
    edit_set_data(asset,edits_text(bi[keep],br[keep],bo[keep]),'Arraytron reset edits');return int((~keep).sum())

def edit_clear(asset):edit_set_data(asset,'','Arraytron reset all edits')

def edit_select_all(asset):
    es=edit_display(asset);edit_set_selection(asset,[] if es is None else es['ids']);return 0 if es is None else len(es['ids'])

def edit_select_none(asset):edit_set_selection(asset,[])

def edit_select_invert(asset):
    es=edit_display(asset)
    if es is None:return 0
    ids=np.setdiff1d(es['ids'],edit_get_selection(asset));edit_set_selection(asset,ids);return len(ids)

def edit_delete_selected(asset):return edit_delete_ids(asset,edit_get_selection(asset))
def edit_reset_selected(asset):return edit_reset_ids(asset,edit_get_selection(asset))
def edit_deleted_ids(asset):
    bi,br,bo=edit_store(asset);return bi[~bo]
def edit_restore_deleted(asset):
    """Bring the deleted instances back (their other edits are kept). One undo step."""
    bi,br,bo=edit_store(asset);edit_set_data(asset,edits_text(bi,br,np.ones(len(bi),dtype=bool)),'Arraytron restore deleted');return int((~bo).sum())

def edit_info(asset):
    n=len(edit_get_selection(asset));bi,br,bo=edit_store(asset)
    head='%d instance%s selected.'%(n,'' if n==1 else 's') if n else 'Nothing selected.'
    return head+' %d edited, %d deleted.'%(int(bo.sum()),int((~bo).sum()))+('' if asset.evalParm('edit_on') else ' Apply Edits is off: the edits are kept but not used.')

def edit_start(asset):
    """Edit Instances button: make this node current and enter the viewport Edit tool (Esc finishes)."""
    if not hou.isUIAvailable():raise hou.NodeError('Editing needs the Houdini interface (a Scene Viewer).')
    viewer=hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
    if viewer is None:raise hou.NodeError('Open a Scene Viewer pane to edit instances.')
    asset.setUserData('arraytron_edit','1')
    asset.setCurrent(True,clear_all_selected=True);viewer.setCurrentState(paint_state_name(asset))
