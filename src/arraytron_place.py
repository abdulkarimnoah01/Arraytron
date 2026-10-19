# Instance Place (v1.9.0): Distribution Mode "Instance Place". Instances are placed one at a time, like the transforms of a Copy and Transform SOP: a table of
# individual instances (the multiparm `places`), each with its own Position, Rotate, Scale and Prototype Row, filled by hand or by the Place Instances viewport
# tool (click a surface). Every row has a stable id, so Variation, Mask, overrides, primvars and Grow treat a placed instance like any other and keep it when rows are
# added or removed. Positions are world space (like Paint). Appended to the PythonModule after the Pick module (uses paint / scatter helpers and pick_nearest).
# The pure numpy functions are tested directly.
import numpy as np

PLACE_MAX=100000
PLACE_ID_BASE=1

# ---------------------------------------------------------------- pure functions
def place_qmul(a,b):
    """Hamilton product (x, y, z, w): the rotation b followed by a."""
    a=np.asarray(a,dtype=np.float64);b=np.asarray(b,dtype=np.float64);ax,ay,az,aw=a[...,0],a[...,1],a[...,2],a[...,3];bx,by,bz,bw=b[...,0],b[...,1],b[...,2],b[...,3]
    return np.stack([aw*bx+ax*bw+ay*bz-az*by,aw*by-ax*bz+ay*bw+az*bx,aw*bz+ax*by-ay*bx+az*bw,aw*bw-ax*bx-ay*by-az*bz],axis=-1)

def place_quat(degrees):
    """Quaternion (x, y, z, w) of a rotation about X, then Y, then Z (degrees, fixed axes: R = Rz Ry Rx), the same convention as the Instance Overrides."""
    rx,ry,rz=(np.radians(float(v))*0.5 for v in degrees)
    qx=np.array([np.sin(rx),0,0,np.cos(rx)]);qy=np.array([0,np.sin(ry),0,np.cos(ry)]);qz=np.array([0,0,np.sin(rz),np.cos(rz)])
    return place_qmul(qz,place_qmul(qy,qx))

def place_euler(q):
    """Degrees (rx, ry, rz) of a quaternion (x, y, z, w) in the convention of place_quat (R = Rz Ry Rx). The inverse of place_quat for angles with |ry| < 90."""
    x,y,z,w=(float(v) for v in np.asarray(q,dtype=np.float64)/np.linalg.norm(q))
    r20=2*(x*z-w*y);ry=-np.arcsin(np.clip(r20,-1.0,1.0))
    if abs(r20)<0.999999:rx=np.arctan2(2*(y*z+w*x),1-2*(x*x+y*y));rz=np.arctan2(2*(x*y+w*z),1-2*(y*y+z*z))
    else:rx=0.0;rz=np.arctan2(-2*(x*y-w*z),1-2*(x*x+z*z))                                           # gimbal lock: all the twist goes to Z
    return np.degrees([rx,ry,rz])

def place_resolve_ids(ids):
    """The ids the instances really get. An id that is a positive integer and unique in the table is kept; a row with no id yet (0), a negative one or a repeated one gets
    the next free number (largest valid id + 1, counting up, in row order). The result is deterministic, and every valid id is stable when rows are added or removed."""
    ids=[int(i) for i in ids];seen=set();out=[0]*len(ids);bad=[]
    for k,i in enumerate(ids):
        if i>0 and i not in seen:seen.add(i);out[k]=i
        else:bad.append(k)
    nxt=max(seen)+1 if seen else PLACE_ID_BASE
    for k in bad:out[k]=nxt;nxt+=1
    return out

def place_aim(normal,amount,yaw):
    """Quaternion of a new instance: the shortest rotation taking +Y onto the surface normal (blended by amount, 0 = upright), then a rotation of yaw degrees about its own up axis."""
    A=normal_alignment(np.asarray(normal,dtype=np.float64).reshape(1,3),amount)[0];Y=place_quat((0.0,yaw,0.0));return place_qmul(A,Y)

# ---------------------------------------------------------------- the table
def place_rows(asset):
    """The Placed Instances as a list of dicts in row order: on, id (as typed), pos, rot (degrees), scale (3), proto (bank row number, 0 = chosen by the Selection Mode)."""
    rows=[]
    for i in range(1,asset.evalParm('places')+1):
        rows.append(dict(on=bool(asset.evalParm('place_on%d'%i)),id=asset.evalParm('place_id%d'%i),pos=np.array(asset.evalParmTuple('place_pos%d'%i),dtype=np.float64),rot=np.array(asset.evalParmTuple('place_rot%d'%i),dtype=np.float64),
                         scale=np.array(asset.evalParmTuple('place_scale%d'%i),dtype=np.float64),proto=asset.evalParm('place_proto%d'%i)))
    return rows

def place_arrays(asset):
    """The enabled rows as arrays: ids (n,), P (n,3), orient (n,4), scale (n,3), proto (n,), and the row number of each (n,)."""
    rows=place_rows(asset);ids=place_resolve_ids([r['id'] for r in rows]);keep=[k for k,r in enumerate(rows) if r['on']]
    if not keep:return dict(ids=np.zeros(0,dtype=np.int64),P=np.zeros((0,3)),orient=np.zeros((0,4)),scale=np.zeros((0,3)),proto=np.zeros(0,dtype=np.int64),row=np.zeros(0,dtype=np.int64))
    return dict(ids=np.array([ids[k] for k in keep],dtype=np.int64),P=np.array([rows[k]['pos'] for k in keep]),orient=np.array([place_quat(rows[k]['rot']) for k in keep]),
                scale=np.maximum(np.array([rows[k]['scale'] for k in keep]),1e-4),proto=np.array([rows[k]['proto'] for k in keep],dtype=np.int64),row=np.array([k+1 for k in keep],dtype=np.int64))

def sop_place(geo,asset):
    """generate_place: one point per enabled row. P, the stable id, the placed rotation (align), the placed scale (srcscale) and the Prototype Row (place_proto, 0 = auto)."""
    a=place_arrays(asset);geo.clear()
    geo.addAttrib(hou.attribType.Point,'id',0);geo.addAttrib(hou.attribType.Point,'align',(0.0,0.0,0.0,1.0));geo.addAttrib(hou.attribType.Point,'srcscale',(1.0,1.0,1.0));geo.addAttrib(hou.attribType.Point,'place_proto',0)
    if not len(a['ids']):return
    if len(a['ids'])>PLACE_MAX:raise hou.NodeError('Instance Place holds at most %d instances.'%PLACE_MAX)
    geo.createPoints([tuple(v) for v in a['P'].tolist()]);geo.setPointIntAttribValues('id',a['ids'].tolist());geo.setPointFloatAttribValues('align',a['orient'].ravel().tolist())
    geo.setPointFloatAttribValues('srcscale',a['scale'].ravel().tolist());geo.setPointIntAttribValues('place_proto',a['proto'].tolist())

def place_info(asset):
    rows=place_rows(asset)
    if not rows:return 'No instances yet. Press Place Instances in Viewport and click a surface, or add a row with the + button of the table.'
    ids=[r['id'] for r in rows];real=place_resolve_ids(ids);fixed=sum(1 for a,b in zip(ids,real) if a!=b);on=sum(1 for r in rows if r['on'])
    text='%d placed instance(s), %d enabled.'%(len(rows),on)
    if fixed:text+=' %d row(s) have no unique id yet and get a temporary one: press Fix Ids.'%fixed
    return text

# ---------------------------------------------------------------- editing (one undo step each)
def place_surface(asset):
    """The triangles under the Place On prim (a Mesh, a basic shape or a hierarchy), or the ground plane Y = 0 when it is empty."""
    if not asset.evalParm('place_target').strip():return plane_surface(1000.0,0.0)
    return stage_surface(asset,'place_target')

def place_normalize(asset):
    """Write the real ids into the table (rows with no unique id get one): they are stable from then on."""
    rows=place_rows(asset);real=place_resolve_ids([r['id'] for r in rows])
    if real==[r['id'] for r in rows]:return 0
    with hou.undos.group('Arraytron fix placed ids'):
        for i,(a,b) in enumerate(zip([r['id'] for r in rows],real),1):
            if a!=b:asset.parm('place_id%d'%i).set(b)
    return sum(1 for a,b in zip([r['id'] for r in rows],real) if a!=b)

def place_add(asset,position,normal=(0.0,1.0,0.0),scale=None,yaw=None,proto=None,id=None,rot=None):
    """Add one instance row at a world position: rotation from the surface normal (Align To Surface) and the yaw, scale and prototype of the New Instance settings unless given
    (rot: explicit degrees). Returns the new row number."""
    place_normalize(asset)
    with hou.undos.group('Arraytron place instance'):
        rows=place_rows(asset);n=len(rows)+1;scale=asset.evalParm('place_def_scale') if scale is None else scale
        if yaw is None:
            yaw=asset.evalParm('place_def_yaw')+(asset.evalParm('place_def_yawrand')*(np.random.RandomState(int(n*7919+asset.evalParm('place_seed'))).rand()*2.0-1.0))
        degrees=place_euler(place_aim(normal,asset.evalParm('place_align'),yaw)) if rot is None else rot
        pos=np.asarray(position,dtype=np.float64)+np.asarray(normal,dtype=np.float64)*asset.evalParm('place_offset')
        asset.parm('places').set(n);i=n
        asset.parm('place_on%d'%i).set(1);asset.parm('place_id%d'%i).set(max([r['id'] for r in rows]+[0])+1 if id is None else int(id))
        asset.parmTuple('place_pos%d'%i).set(tuple(float(v) for v in pos));asset.parmTuple('place_rot%d'%i).set(tuple(float(v) for v in degrees))
        asset.parmTuple('place_scale%d'%i).set((float(scale),)*3);asset.parm('place_proto%d'%i).set(asset.evalParm('place_def_proto') if proto is None else int(proto))
    return n

def place_remove(asset,row):
    """Remove one row (the other rows keep their values and ids)."""
    with hou.undos.group('Arraytron remove placed instance'):asset.parm('places').removeMultiParmInstance(int(row)-1)

def place_clear(asset):
    with hou.undos.group('Arraytron clear placed instances'):asset.parm('places').set(0)

def place_nearest(asset,origin,direction):
    """(row number, id) of the placed instance closest to the mouse ray (the same angular tolerance as Pick Instance), or None."""
    a=place_arrays(asset)
    if not len(a['ids']):return None
    hit=pick_nearest(origin,direction,a['P'],a['ids'])
    if hit is None:return None
    k=int(np.nonzero(a['ids']==hit[0])[0][0]);return int(a['row'][k]),int(hit[0])

def place_start(asset):
    """Place Instances button: Instance Place mode, this node current, the viewport tool in placing mode (Esc finishes)."""
    if asset.evalParm('mode')!=9:asset.parm('mode').set(9)
    if not hou.isUIAvailable():raise hou.NodeError('Placing needs the Houdini interface (a Scene Viewer).')
    viewer=hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
    if viewer is None:raise hou.NodeError('Open a Scene Viewer pane to place instances.')
    asset.setUserData('arraytron_place','1');asset.setCurrent(True,clear_all_selected=True);viewer.setCurrentState(paint_state_name(asset))
