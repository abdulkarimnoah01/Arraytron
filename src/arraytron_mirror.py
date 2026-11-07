# Mirror (v1.34.0): mirrors the finished scatter. A list of operations (the multiparm Mirror Operations) works one after the other on everything the operations before it made, so one Plane
# operation doubles the instances, two give four, three eight, and so on; a Radial operation makes N turned copies about an axis (with a mirror in every slice as a kaleidoscope if asked).
# It runs in the MIRROR Python SOP after the Override Database and before Grow, so the copies are of the instances that are really there and Grow reveals the mirrored half too. Appended to
# the PythonModule after Blast. Names start with mirror_ / mir_ (one namespace). The pure numpy functions are tested directly.
import math
import numpy as np

MIRROR_TYPES=('Plane X (the YZ plane)','Plane Y (the XZ plane)','Plane Z (the XY plane)','Custom Plane','Radial')
MIRROR_AXES=('X','Y','Z','Custom')
MIRROR_VECTORS=('N','v','up')           # point vector attributes that follow the mirror (polar vectors)

def mir_unit(v,fallback=(1.0,0.0,0.0)):
    v=np.asarray(v,dtype=np.float64);n=float(np.linalg.norm(v))
    return v/n if n>1e-12 else np.asarray(fallback,dtype=np.float64)

def mir_qmul(a,b):
    """Hamilton product a * b of quaternions stored as (x, y, z, w); (N,4) arrays or one quaternion each."""
    a=np.asarray(a,dtype=np.float64);b=np.asarray(b,dtype=np.float64);a,b=np.broadcast_arrays(a,b)
    av,aw,bv,bw=a[...,:3],a[...,3:],b[...,:3],b[...,3:]
    return np.concatenate([aw*bv+bw*av+np.cross(av,bv),aw*bw-np.sum(av*bv,axis=-1,keepdims=True)],axis=-1)

def mir_plane(row_type,normal,axis_choice=None):
    """The unit normal of the mirror plane: Plane X / Y / Z are the axes, Custom Plane is the normal given."""
    if row_type==0:return np.array([1.0,0.0,0.0])
    if row_type==1:return np.array([0.0,1.0,0.0])
    if row_type==2:return np.array([0.0,0.0,1.0])
    return mir_unit(normal)

def mir_axis(axis_choice,custom):
    """The unit axis of a Radial operation: X, Y, Z or the custom vector."""
    return (np.array([1.0,0.0,0.0]),np.array([0.0,1.0,0.0]),np.array([0.0,0.0,1.0]))[axis_choice] if axis_choice<3 else mir_unit(custom,(0.0,1.0,0.0))

def mir_reflect(s,n,centre,flip_shape):
    """The mirror image of the instances s (dict P (N,3), orient (N,4), scale (N,3), plus optional vectors) in the plane through `centre` with unit normal n. flip_shape: the instances are mirrored
    too (the orientation is turned 180 degrees about n and the scale is negated, which is exactly the reflection of the whole instance); off: only the placement is mirrored, every instance keeps
    its own handedness (the orientation is reflected as a rotation, the scale is kept)."""
    out=dict(s);P=np.asarray(s['P'],dtype=np.float64);out['P']=P-2.0*np.einsum('ij,j->i',P-centre,n)[:,None]*n[None,:]
    q=np.asarray(s['orient'],dtype=np.float64)
    if flip_shape:out['orient']=mir_qmul(np.append(n,0.0),q);out['scale']=-np.asarray(s['scale'],dtype=np.float64)
    else:
        v=q[:,:3];out['orient']=np.concatenate([-v+2.0*np.einsum('ij,j->i',v,n)[:,None]*n[None,:],q[:,3:]],axis=1)
    for name in MIRROR_VECTORS:
        if name in s:x=np.asarray(s[name],dtype=np.float64);out[name]=x-2.0*np.einsum('ij,j->i',x,n)[:,None]*n[None,:]
    return out

def mir_rodrigues(x,axis,angle):
    """Vectors x (N,3) turned by `angle` radians about the unit axis."""
    c,sn=math.cos(angle),math.sin(angle)
    return x*c+np.cross(axis[None,:],x)*sn+axis[None,:]*np.einsum('ij,j->i',x,axis)[:,None]*(1.0-c)

def mir_rotate(s,axis,centre,angle):
    """The instances s turned `angle` radians about the axis through `centre` (positions, orientations and the vector attributes; the scale is kept)."""
    out=dict(s);P=np.asarray(s['P'],dtype=np.float64);out['P']=centre+mir_rodrigues(P-centre,axis,angle)
    out['orient']=mir_qmul(np.append(axis*math.sin(0.5*angle),math.cos(0.5*angle)),np.asarray(s['orient'],dtype=np.float64))
    for name in MIRROR_VECTORS:
        if name in s:out[name]=mir_rodrigues(np.asarray(s[name],dtype=np.float64),axis,angle)
    return out

def mir_slice_normal(axis,degrees):
    """The normal of the mirror plane of a kaleidoscope slice: the plane holds the axis and the direction `degrees` turned about the axis from a fixed start direction."""
    start=np.array([1.0,0.0,0.0]) if abs(axis[0])<0.9 else np.array([0.0,1.0,0.0]);u=mir_unit(start-axis*np.dot(start,axis))
    d=mir_rodrigues(u[None,:],axis,math.radians(degrees))[0];return mir_unit(np.cross(axis,d))

def mir_blocks(s,op):
    """The blocks one operation makes from the instances s: a list of dict, the first is s itself (kept when op['keep'], else None). op: type, normal, axis, centre, count, span, slice, angle, flip."""
    centre=np.asarray(op['centre'],dtype=np.float64)
    if op['type']!=4:
        n=mir_plane(op['type'],op['normal']);return [s if op['keep'] else None,mir_reflect(s,n,centre,op['flip'])]
    axis=mir_axis(op['axis'],op['normal']);count=max(int(op['count']),1);blocks=[s if op['keep'] else None]
    for k in range(count):
        a=math.radians(op['span'])*k/count
        if k>0:blocks.append(mir_rotate(s,axis,centre,a))
        if op['slice']:
            m=mir_reflect(s,mir_slice_normal(axis,op['angle']),centre,op['flip']);blocks.append(m if k==0 else mir_rotate(m,axis,centre,a))
    return blocks

def mir_apply(s,ops,max_points=20000000,id_limit=2147483647):
    """Run the operations one after the other. s: dict P, orient, scale, id, plus any other per-point arrays (tiled as they are). Returns (result dict, source index of every result point, copy number of every
    result point, note). Ids of copies are id + stride * copy number, so the originals keep their ids and a copy always has the same id."""
    n=len(s['P']);src=np.arange(n);copy=np.zeros(n,dtype=np.int64);cur=dict(s);cur['_src']=src;cur['_copy']=copy;note='';blocks_total=1
    top=int(np.max(s['id'])) if n else 0;stride=1<<20
    while stride<=top:stride<<=1
    for op in ops:
        if not op.get('on',True):continue
        count=len(cur['P']);per=(max(int(op['count']),1)*(2 if op['slice'] else 1)) if op['type']==4 else 2
        if count*per>max_points and op['keep']:note='stopped at %d instances (Max Instances)'%count;break
        if stride*blocks_total*per>id_limit:note='stopped: the ids would overflow';break
        parts=mir_blocks(cur,op);out={k:[] for k in cur};B=blocks_total
        for i,b in enumerate(parts):
            if b is None:continue
            for k in cur:
                v=b[k]
                if k=='_copy':v=v+i*B
                out[k].append(np.asarray(v))
        cur={k:np.concatenate(v,axis=0) for k,v in out.items()};blocks_total*=per
    cur['id']=np.asarray(s['id'],dtype=np.int64)[cur['_src']]+stride*cur['_copy']
    return cur,cur['_src'],cur['_copy'],note

def mir_ops(asset):
    """The operations the multiparm holds, as a list of dict for mir_apply."""
    ops=[]
    for i in range(1,asset.evalParm('mirror_ops')+1):
        g=lambda name:asset.evalParm('%s%d'%(name,i))
        ops.append(dict(on=bool(g('mirror_en')),type=g('mirror_type'),axis=g('mirror_axis'),normal=tuple(asset.evalParmTuple('mirror_normal%d'%i)),centre=tuple(asset.evalParmTuple('mirror_center%d'%i)),
                        count=g('mirror_count'),span=g('mirror_span'),slice=bool(g('mirror_slice')),angle=g('mirror_angle'),flip=bool(g('mirror_flip')),keep=bool(g('mirror_keep'))))
    return ops

def sop_mirror(geo,asset):
    """MIRROR: run the Mirror Operations over the finished instances; the copies have new ids (id + stride * copy number)."""
    for name in ('mirror_before','mirror_after'):geo.addAttrib(hou.attribType.Global,name,0)
    geo.addAttrib(hou.attribType.Global,'mirror_note','')
    n=geo.intrinsicValue('pointcount');geo.setGlobalAttribValue('mirror_before',n);geo.setGlobalAttribValue('mirror_after',n)
    if not asset.evalParm('mirror_on') or n==0 or asset.evalParm('mirror_ops')==0:return
    s=read_points(geo);attrs=[]                     # the generic point attributes are tiled as they are; the ones the mirror changes are replaced
    for a in geo.pointAttribs():
        name=a.name()
        if name in ('P','orient','scale','id'):continue
        if a.dataType()==hou.attribData.Int:vals=np.array(geo.pointIntAttribValues(name)).reshape(n,-1);kind='i'
        elif a.dataType()==hou.attribData.Float:vals=np.array(geo.pointFloatAttribValues(name)).reshape(n,-1);kind='f'
        elif a.dataType()==hou.attribData.String:vals=np.array(geo.pointStringAttribValues(name),dtype=object).reshape(n,-1);kind='s'
        else:continue
        attrs.append((name,a.size(),kind));s['a_'+name]=vals
        if name in MIRROR_VECTORS and a.size()==3 and kind=='f':s[name]=vals
    res,srcidx,copy,note=mir_apply(s,mir_ops(asset),asset.evalParm('mirror_max'))
    m=len(res['P'])
    if m>n:geo.createPoints([(0.0,0.0,0.0)]*(m-n))
    elif m<n:geo.deletePoints([geo.point(i) for i in range(m,n)])
    geo.setPointFloatAttribValues('P',res['P'].ravel().tolist());geo.setPointFloatAttribValues('orient',res['orient'].ravel().tolist());geo.setPointFloatAttribValues('scale',res['scale'].ravel().tolist())
    geo.setPointIntAttribValues('id',res['id'].tolist())
    for name,size,kind in attrs:
        v=res[name] if name in MIRROR_VECTORS and kind=='f' and size==3 else res['a_'+name]
        if kind=='i':geo.setPointIntAttribValues(name,np.asarray(v).ravel().tolist())
        elif kind=='f':geo.setPointFloatAttribValues(name,np.asarray(v,dtype=np.float64).ravel().tolist())
        else:geo.setPointStringAttribValues(name,[str(x) for x in np.asarray(v,dtype=object).ravel()])
    geo.setGlobalAttribValue('mirror_after',m);geo.setGlobalAttribValue('mirror_note',note)

def mirror_info(asset):
    """Read-only text for the Mirror section."""
    if not asset.evalParm('mirror_on'):return 'Mirror is off: the scatter is kept as it is.'
    try:
        g=asset.node('USD_COMPILER/MIRROR').geometry();note=g.attribValue('mirror_note')
        return '%d operation(s): %d instances became %d.%s'%(asset.evalParm('mirror_ops'),g.attribValue('mirror_before'),g.attribValue('mirror_after'),(' '+note+'.') if note else '')
    except Exception as exc:return 'Cannot evaluate Mirror: %s'%exc
