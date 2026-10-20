# Instance Place (v1.9.0): Distribution Mode "Instance Place". Instances are placed one at a time, like the transforms of a Copy and Transform SOP: a table of
# individual instances (the multiparm `places`), each with its own Position, Rotate, Scale and Prototype Row, filled by hand or by the Place Instances viewport
# tool (click a surface). Every row has a stable id, so Variation, Mask, overrides, primvars and Grow treat a placed instance like any other and keep it when rows are
# added or removed. Positions are world space (like Paint). Appended to the PythonModule after the Pick module (uses paint / scatter helpers and pick_nearest).
# The pure numpy functions are tested directly.
import numpy as np

PLACE_MAX=100000
PLACE_ID_BASE=1
PLACE_COPY_ID_BASE=1000000000          # the id space of the copies of a row (see place_copy_ids)
PLACE_MAX_COPIES=9999
PLACE_MAX_ROW_ID=99999                 # a row that makes copies needs an id below this

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

def place_rotate(q,v):
    """The vector v turned by the quaternion q (x, y, z, w)."""
    q=np.asarray(q,dtype=np.float64);u=q[:3];v=np.asarray(v,dtype=np.float64);return v+2*q[3]*np.cross(u,v)+2*np.cross(u,np.cross(u,v))

def place_copy_ids(row_id,copies):
    """The ids of the copies of a row: copy 0 keeps the row id (so a row without copies is unchanged), copy k >= 1 gets 1000000000 + row id * 10000 + k. Stable when other rows come and go."""
    row_id=int(row_id);return [row_id]+[PLACE_COPY_ID_BASE+row_id*10000+k for k in range(1,int(copies))]

def place_expand(pos,rot,scale,copies,step_translate,step_rotate,step_scale,space=0):
    """The copies of one row, like the Copy and Transform SOP: copy 0 is the row itself, every next copy is the previous one moved by one more step.
    space 0 (Local): the step is applied in the frame of the previous copy, M(k+1) = M(k) * Step, so the translation turns and shrinks with it (spirals, stairs, fans).
    space 1 (World): the translation is in world axes, the rotation turns the copy about its own position in world axes, the scale multiplies the copy.
    Returns positions (n,3), quaternions (n,4) and scales (n,3). step_scale is a uniform multiplier per copy."""
    n=int(copies);P=np.zeros((n,3));Q=np.zeros((n,4));S=np.zeros((n,3))
    p=np.asarray(pos,dtype=np.float64).copy();q=place_quat(rot);s=np.asarray(scale,dtype=np.float64).copy();t=np.asarray(step_translate,dtype=np.float64);qs=place_quat(step_rotate)
    for k in range(n):
        P[k]=p;Q[k]=q;S[k]=s
        if int(space)==0:p=p+place_rotate(q,s*t);q=place_qmul(q,qs)
        else:p=p+t;q=place_qmul(qs,q)
        q=q/np.linalg.norm(q);s=s*float(step_scale)
    return P,Q,S

def place_snap_value(value,step):
    """value rounded to the nearest multiple of step (step <= 0 leaves it alone)."""
    return float(value) if step<=0 else float(np.round(float(value)/step)*step)

def place_hit_at(surface,x,z,y_hint=0.0):
    """The surface point straight below (x, y_hint + 1000, z) and its normal, or None when there is nothing there. Used to keep a snapped point on the surface."""
    P,T,area,normals,vn=surface;t,j=ray_triangles(np.array([x,y_hint+1000.0,z]),np.array([0.0,-1.0,0.0]),P,T)
    if j[0]<0:return None
    n=normals[j[0]]
    if n[1]<0:n=-n
    return np.array([x,y_hint+1000.0-t[0],z]),n

def place_snap_point(asset,surface,point,normal):
    """The Snap Position grid applied to a surface point: X and Z are rounded to the grid, then the point is put back on the surface (Y and the normal come from it). Returns (point, normal)."""
    g=asset.evalParm('place_snap')
    if g<=0 or surface is None:return point,normal
    x=place_snap_value(point[0],g);z=place_snap_value(point[2],g);hit=place_hit_at(surface,x,z,float(point[1]))
    return (hit[0],hit[1]) if hit is not None else (point,normal)

def place_drag_values(dx,dy,yaw_per_pixel=0.5,scale_pixels=150.0):
    """What dragging after the press does: dx pixels to the right turn the new instance by dx * yaw_per_pixel degrees, dy pixels up scale it by 2 ** (dy / scale_pixels)."""
    return float(dx)*yaw_per_pixel,2.0**(float(dy)/scale_pixels)

# ---------------------------------------------------------------- the table
def place_rows(asset):
    """The Placed Instances as a list of dicts in row order: on, id (as typed), pos, rot (degrees), scale (3), proto (bank row number, 0 = chosen by the Selection Mode),
    and the copies of the row: copies, step_t (3), step_r (3, degrees), step_s (uniform multiplier), space (0 local, 1 world)."""
    rows=[]
    for i in range(1,asset.evalParm('places')+1):
        rows.append(dict(on=bool(asset.evalParm('place_on%d'%i)),id=asset.evalParm('place_id%d'%i),pos=np.array(asset.evalParmTuple('place_pos%d'%i),dtype=np.float64),rot=np.array(asset.evalParmTuple('place_rot%d'%i),dtype=np.float64),
                         scale=np.array(asset.evalParmTuple('place_scale%d'%i),dtype=np.float64),proto=asset.evalParm('place_proto%d'%i),copies=asset.evalParm('place_copies%d'%i),
                         step_t=np.array(asset.evalParmTuple('place_ctrans%d'%i),dtype=np.float64),step_r=np.array(asset.evalParmTuple('place_crot%d'%i),dtype=np.float64),step_s=asset.evalParm('place_cscale%d'%i),space=asset.evalParm('place_cspace%d'%i)))
    return rows

def place_arrays(asset):
    """The enabled rows, copies included, as arrays: ids (n,), P (n,3), orient (n,4), scale (n,3), proto (n,), the row number (n,) and the copy number (n,) of each."""
    rows=place_rows(asset);ids=place_resolve_ids([r['id'] for r in rows]);out=dict(ids=[],P=[],orient=[],scale=[],proto=[],row=[],copy=[])
    for k,r in enumerate(rows):
        if not r['on']:continue
        n=max(1,min(int(r['copies']),PLACE_MAX_COPIES))
        if n>1:
            if ids[k]>PLACE_MAX_ROW_ID:raise hou.NodeError('Placed instance row %d makes copies, so its Id must be below %d (it is %d).'%(k+1,PLACE_MAX_ROW_ID+1,ids[k]))
            P,Q,S=place_expand(r['pos'],r['rot'],r['scale'],n,r['step_t'],r['step_r'],r['step_s'],r['space']);cid=place_copy_ids(ids[k],n)
        else:P,Q,S=r['pos'][None,:],place_quat(r['rot'])[None,:],r['scale'][None,:];cid=[ids[k]]
        out['ids']+=cid;out['P'].append(P);out['orient'].append(Q);out['scale'].append(S);out['proto']+=[r['proto']]*n;out['row']+=[k+1]*n;out['copy']+=list(range(n))
    if not out['ids']:return dict(ids=np.zeros(0,dtype=np.int64),P=np.zeros((0,3)),orient=np.zeros((0,4)),scale=np.zeros((0,3)),proto=np.zeros(0,dtype=np.int64),row=np.zeros(0,dtype=np.int64),copy=np.zeros(0,dtype=np.int64))
    return dict(ids=np.array(out['ids'],dtype=np.int64),P=np.vstack(out['P']),orient=np.vstack(out['orient']),scale=np.maximum(np.vstack(out['scale']),1e-4),proto=np.array(out['proto'],dtype=np.int64),
                row=np.array(out['row'],dtype=np.int64),copy=np.array(out['copy'],dtype=np.int64))

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
    total=sum(max(1,min(int(r['copies']),PLACE_MAX_COPIES)) for r in rows if r['on'])
    if total!=on:text='%d rows, %d enabled, %d instances with their copies.'%(len(rows),on,total)
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

def place_add(asset,position,normal=(0.0,1.0,0.0),scale=None,yaw=None,proto=None,id=None,rot=None,yaw_add=0.0,scale_mult=1.0,snap_rot=None):
    """Add one instance row at a world position: rotation from the surface normal (Align To Surface) and the yaw, scale and prototype of the New Instance settings unless given
    (rot: explicit degrees); yaw_add and scale_mult come on top of them (the drag of the tool), snap_rot rounds the final yaw to a multiple of that many degrees. Returns the new row number."""
    place_normalize(asset)
    with hou.undos.group('Arraytron place instance'):
        rows=place_rows(asset);n=len(rows)+1;scale=asset.evalParm('place_def_scale') if scale is None else scale
        if yaw is None:
            yaw=asset.evalParm('place_def_yaw')+(asset.evalParm('place_def_yawrand')*(np.random.RandomState(int(n*7919+asset.evalParm('place_seed'))).rand()*2.0-1.0))
        yaw=yaw+yaw_add
        if snap_rot:yaw=place_snap_value(yaw,snap_rot)
        scale=scale*scale_mult
        degrees=place_euler(place_aim(normal,asset.evalParm('place_align'),yaw)) if rot is None else rot
        pos=np.asarray(position,dtype=np.float64)+np.asarray(normal,dtype=np.float64)*asset.evalParm('place_offset')
        asset.parm('places').set(n);i=n
        asset.parm('place_on%d'%i).set(1);asset.parm('place_id%d'%i).set(max([r['id'] for r in rows]+[0])+1 if id is None else int(id))
        asset.parmTuple('place_pos%d'%i).set(tuple(float(v) for v in pos));asset.parmTuple('place_rot%d'%i).set(tuple(float(v) for v in degrees))
        asset.parmTuple('place_scale%d'%i).set((float(scale),)*3);asset.parm('place_proto%d'%i).set(asset.evalParm('place_def_proto') if proto is None else int(proto))
        asset.parm('place_copies%d'%i).set(asset.evalParm('place_def_copies'));asset.parmTuple('place_ctrans%d'%i).set(asset.evalParmTuple('place_def_ctrans'));asset.parmTuple('place_crot%d'%i).set(asset.evalParmTuple('place_def_crot'))
        asset.parm('place_cscale%d'%i).set(asset.evalParm('place_def_cscale'));asset.parm('place_cspace%d'%i).set(asset.evalParm('place_def_cspace'))
    return n

def place_curve_samples(asset):
    """Positions (n,3) and headings (n, degrees about up) along the BasisCurves under the Along Curve prim: by count or by spacing, ends included. The heading turns +Z onto the tangent."""
    path=asset.evalParm('place_curve').strip()
    if not path:raise hou.NodeError('Along Curve: the Curve Prim is empty. Pick a BasisCurves prim of the Scene Stream.')
    P=[];H=[]
    for poly,closed in stage_curves(asset,path):
        L=arclength(poly)[-1];s=curve_parameters(L,closed,asset.evalParm('place_curve_mode'),asset.evalParm('place_curve_count'),asset.evalParm('place_curve_spacing'),np.arange(asset.evalParm('place_curve_count')),0)
        pos,tan=sample_polyline(poly,s);P.append(pos);H.append(np.degrees(np.arctan2(tan[:,0],tan[:,2])))
    return np.vstack(P),np.concatenate(H)

def place_along_curve(asset):
    """Along Curve button: add one instance per sample of the curve (appended to the table, one undo step). They are upright, turned to follow the curve when Follow Curve is on,
    and put on the Place On surface when Project On Surface is on. Scale, rotation offset (New Rotation) and Prototype Row come from the New settings. Returns the number of rows added."""
    P,H=place_curve_samples(asset);surface=place_surface(asset) if asset.evalParm('place_curve_project') else None
    if len(P)>PLACE_MAX:raise hou.NodeError('Along Curve would place %d instances; the table holds at most %d.'%(len(P),PLACE_MAX))
    place_normalize(asset)
    with hou.undos.group('Arraytron place along curve'):
        first=asset.evalParm('places');top=max([r['id'] for r in place_rows(asset)]+[0]);asset.parm('places').set(first+len(P))
        for k,(p,h) in enumerate(zip(P,H),1):
            n=np.array([0.0,1.0,0.0])
            if surface is not None:
                hit=place_hit_at(surface,float(p[0]),float(p[2]),float(p[1]))
                if hit is not None:p,n=hit
            yaw=(float(h) if asset.evalParm('place_curve_follow') else 0.0)+asset.evalParm('place_def_yaw');i=first+k
            degrees=place_euler(place_aim(n,asset.evalParm('place_align'),yaw));pos=np.asarray(p,dtype=np.float64)+n*asset.evalParm('place_offset')
            asset.parm('place_on%d'%i).set(1);asset.parm('place_id%d'%i).set(top+k);asset.parmTuple('place_pos%d'%i).set(tuple(float(v) for v in pos));asset.parmTuple('place_rot%d'%i).set(tuple(float(v) for v in degrees))
            asset.parmTuple('place_scale%d'%i).set((float(asset.evalParm('place_def_scale')),)*3);asset.parm('place_proto%d'%i).set(asset.evalParm('place_def_proto'))
    return len(P)

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
