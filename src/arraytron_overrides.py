# Manual instance overrides (v1.0.0): "Generated Instance + Override Database = Final Instance". The database is the multiparm `overrides` (one row per
# instance id: Delete, Move, Rotate, Scale, Prototype), applied by the OVERRIDES Python SOP after the distribution, variation, selection, separation and
# physics, just before Grow, so a row always edits the instance that would otherwise be generated. Rows are keyed on the stable instance id: they keep
# working when other things (seed of the variation, weights, transforms, more points) change, and rows whose id does not exist are ignored (and counted).
# Appended to the PythonModule. The pure numpy functions are tested directly.
import numpy as np

def qmul(a,b):
    """Hamilton product of quaternions (x, y, z, w) (N,4) or (4,): the rotation b followed by the rotation a (the order of VEX qmultiply(a, b))."""
    a=np.asarray(a,dtype=np.float64);b=np.asarray(b,dtype=np.float64);ax,ay,az,aw=a[...,0],a[...,1],a[...,2],a[...,3];bx,by,bz,bw=b[...,0],b[...,1],b[...,2],b[...,3]
    return np.stack([aw*bx+ax*bw+ay*bz-az*by,aw*by-ax*bz+ay*bw+az*bx,aw*bz+ax*by-ay*bx+az*bw,aw*bw-ax*bx-ay*by-az*bz],axis=-1)

def euler_to_quat(degrees):
    """Quaternion (x, y, z, w) of a rotation about X, then Y, then Z (degrees, fixed axes: R = Rz Ry Rx)."""
    rx,ry,rz=(np.radians(float(v))*0.5 for v in degrees)
    qx=np.array([np.sin(rx),0,0,np.cos(rx)]);qy=np.array([0,np.sin(ry),0,np.cos(ry)]);qz=np.array([0,0,np.sin(rz),np.cos(rz)])
    return qmul(qz,qmul(qy,qx))

def apply_overrides(ids,P,orient,scale,proto,rows,proto_ordinals):
    """Apply override rows to point arrays. rows: list of dicts (id, delete, move (3), rot (3 degrees), scale (float), proto (bank row number, 0 = keep)).
    proto_ordinals: {bank row number: index into the enabled prototypes}. Returns (P, orient, scale, proto, delete mask, stats) as new arrays; stats counts the
    rows by kind and the ids and prototype rows that were not found."""
    ids=np.asarray(ids);P=np.array(P,dtype=np.float64);orient=np.array(orient,dtype=np.float64);scale=np.array(scale,dtype=np.float64);proto=np.array(proto,dtype=np.int64)
    delete=np.zeros(len(ids),dtype=bool);index={int(i):k for k,i in enumerate(ids)};stats=dict(rows=len(rows),missing=0,deleted=0,moved=0,rotated=0,scaled=0,reproto=0,badproto=0)
    for row in rows:
        k=index.get(int(row['id']))
        if k is None:stats['missing']+=1;continue
        if row.get('delete'):
            if not delete[k]:stats['deleted']+=1
            delete[k]=True;continue
        move=np.asarray(row.get('move',(0,0,0)),dtype=np.float64)
        if np.any(move!=0):P[k]+=move;stats['moved']+=1
        rot=row.get('rot',(0,0,0))
        if any(float(v)!=0 for v in rot):orient[k]=qmul(orient[k],euler_to_quat(rot));orient[k]/=np.linalg.norm(orient[k]);stats['rotated']+=1
        s=float(row.get('scale',1.0))
        if s!=1.0:scale[k]*=s;stats['scaled']+=1
        pr=int(row.get('proto',0))
        if pr:
            if pr in proto_ordinals:proto[k]=proto_ordinals[pr];stats['reproto']+=1
            else:stats['badproto']+=1
    return P,orient,scale,proto,delete,stats

# ---------------------------------------------------------------- Houdini side
import hou

def override_rows(asset):
    """The Override Database as a list of dicts, in row order."""
    rows=[]
    for i in range(1,asset.evalParm('overrides')+1):
        rows.append(dict(id=asset.evalParm('ovr_id%d'%i),delete=bool(asset.evalParm('ovr_delete%d'%i)),move=asset.evalParmTuple('ovr_move%d'%i),rot=asset.evalParmTuple('ovr_rot%d'%i),scale=asset.evalParm('ovr_scale%d'%i),proto=asset.evalParm('ovr_proto%d'%i)))
    return rows

def sop_overrides(geo,asset):
    """OVERRIDES: edit the points listed in the Override Database. Ids are never changed; deleted points are removed."""
    for name,default in (('ovr_rows',0),('ovr_missing',0),('ovr_deleted',0),('ovr_moved',0),('ovr_rotated',0),('ovr_scaled',0),('ovr_reproto',0),('ovr_badproto',0)):geo.addAttrib(hou.attribType.Global,name,default)
    rows=override_rows(asset);n=geo.intrinsicValue('pointcount');geo.setGlobalAttribValue('ovr_rows',len(rows))
    if not rows or n==0:return
    s=read_points(geo);ords={r:k for k,r in enumerate(bank_rows(asset))};has_row=geo.findPointAttrib('proto_id') is not None
    P,orient,scale,proto,delete,stats=apply_overrides(s['id'],s['P'],s['orient'],s['scale'],s['protoindex'],rows,ords)
    geo.setPointFloatAttribValues('P',P.ravel().tolist());geo.setPointFloatAttribValues('orient',orient.ravel().tolist());geo.setPointFloatAttribValues('scale',scale.ravel().tolist());geo.setPointIntAttribValues('protoindex',proto.tolist())
    if has_row:
        row_of=np.array(bank_rows(asset)+[0])[np.minimum(proto,len(bank_rows(asset)))] if bank_rows(asset) else np.zeros(n,dtype=np.int64);geo.setPointIntAttribValues('proto_id',row_of.tolist())
    for key,attr in (('missing','ovr_missing'),('deleted','ovr_deleted'),('moved','ovr_moved'),('rotated','ovr_rotated'),('scaled','ovr_scaled'),('reproto','ovr_reproto'),('badproto','ovr_badproto')):geo.setGlobalAttribValue(attr,stats[key])
    drop=np.nonzero(delete)[0]
    if len(drop):geo.deletePoints([geo.point(int(i)) for i in drop])

def override_info(asset):
    n=asset.evalParm('overrides')
    if n==0:return 'No overrides. Add a row with the + button (or use the override functions) to delete, move, rotate, scale or re-assign one instance by its id.'
    try:
        g=asset.node('USD_COMPILER/OVERRIDES').geometry()
        text='%d row(s): %d deleted, %d moved, %d rotated, %d scaled, %d re-assigned.'%(g.attribValue('ovr_rows'),g.attribValue('ovr_deleted'),g.attribValue('ovr_moved'),g.attribValue('ovr_rotated'),g.attribValue('ovr_scaled'),g.attribValue('ovr_reproto'))
        if g.attribValue('ovr_missing'):text+=' %d row(s) name an id that does not exist (ignored).'%g.attribValue('ovr_missing')
        if g.attribValue('ovr_badproto'):text+=' %d row(s) name a Prototype Bank row that is not enabled (ignored).'%g.attribValue('ovr_badproto')
        return text
    except Exception as exc:return 'Cannot evaluate: %s'%exc

def override_set(asset,instance_id,**kw):
    """Create or update the override row of an instance id. kw: delete (bool), move (x,y,z), rot (x,y,z degrees), scale (float), proto (bank row number). One undo step."""
    with hou.undos.group('Arraytron override'):
        rows=override_rows(asset);idx=next((i for i,r in enumerate(rows,1) if r['id']==int(instance_id)),None)
        if idx is None:
            idx=len(rows)+1;asset.parm('overrides').set(idx);asset.parm('ovr_id%d'%idx).set(int(instance_id))
        for key,parm in (('delete','ovr_delete'),('scale','ovr_scale'),('proto','ovr_proto')):
            if key in kw:asset.parm('%s%d'%(parm,idx)).set(kw[key])
        for key,parm in (('move','ovr_move'),('rot','ovr_rot')):
            if key in kw:asset.parmTuple('%s%d'%(parm,idx)).set(tuple(float(v) for v in kw[key]))
    return idx

def override_delete_ids(asset,ids):
    """Mark many instances as deleted (one row each) in a single undo step."""
    with hou.undos.group('Arraytron delete instances'):
        for i in ids:override_set(asset,i,delete=True)

def override_clear(asset):
    with hou.undos.group('Arraytron clear overrides'):asset.parm('overrides').set(0)
