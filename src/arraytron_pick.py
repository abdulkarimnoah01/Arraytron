"""Pick Instance (Finish tab): click an instance in the viewport and its id becomes an override row.

The instances are read from the node's own USD stage (the PointInstancer it writes), so what is picked is what is rendered: the positions are in world space and the
instances hidden by camera optimisation, Grow or the Delete overrides are skipped. The viewer state (src/arraytron_paint_state.py) draws the marker and calls
override_set(). Plain numpy functions here, so they are tested without a viewport.
"""

PICK_TOLERANCE=0.045                     # largest angle (radians, about 2.6 degrees) between the mouse ray and the direction to an instance

def pick_instances(asset):
    """The visible instances of this node: dict(ids=int array, P=(n,3) world positions). Empty arrays when there is no instancer yet."""
    from pxr import Usd,UsdGeom,Gf
    empty=dict(ids=np.zeros(0,dtype=np.int64),P=np.zeros((0,3)))
    stage=asset.stage()
    if stage is None:return empty
    root=asset.evalParm('outputpath').rstrip('/') or '/'
    prim=None
    for p in stage.Traverse():
        if p.IsA(UsdGeom.PointInstancer) and (str(p.GetPath())+'/').startswith(root+'/'):prim=p;break
    if prim is None:return empty
    inst=UsdGeom.PointInstancer(prim);time=Usd.TimeCode(hou.frame()) if hasattr(hou,'frame') else Usd.TimeCode.Default()
    xf=inst.ComputeInstanceTransformsAtTime(time,time)
    if not xf:return empty
    ids_attr=inst.GetIdsAttr();ids=ids_attr.Get(time) if ids_attr and ids_attr.HasValue() else None
    n=len(xf);ids=np.array(list(ids),dtype=np.int64) if ids is not None and len(ids)==n else np.arange(n,dtype=np.int64)
    local=np.array([[m[3][0],m[3][1],m[3][2]] for m in xf],dtype=float)                 # USD matrices are row-major: the translation is the last row
    to_world=UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(time)
    P=np.array([[*to_world.Transform(Gf.Vec3d(*row))] for row in local],dtype=float)
    mask=inst.ComputeMaskAtTime(time)
    if mask and len(mask)==n:
        keep=np.array([bool(v) for v in mask]);ids=ids[keep];P=P[keep]
    return dict(ids=ids,P=P)

def pick_nearest(origin,direction,P,ids,tolerance=PICK_TOLERANCE):
    """The instance closest (in angle) to the mouse ray, or None. Returns (id, position, distance along the ray)."""
    if len(ids)==0:return None
    d=np.asarray(direction,dtype=float);d=d/np.linalg.norm(d);v=P-np.asarray(origin,dtype=float);t=v@d
    perp=np.linalg.norm(v-t[:,None]*d[None,:],axis=1);angle=np.where(t>1e-6,perp/np.maximum(t,1e-6),np.inf)
    best=angle.min()
    if not np.isfinite(best) or best>tolerance:return None
    tied=np.nonzero(angle<=best+1e-9)[0];k=int(tied[np.argmin(t[tied])])                 # the same line of sight: the instance nearest the camera
    return int(ids[k]),P[k].copy(),float(t[k])

def pick_row(asset,instance_id):
    """The override row (1 based) of an id, or 0."""
    return next((i for i,r in enumerate(override_rows(asset),1) if r['id']==int(instance_id)),0)

def pick_add(asset,instance_id,delete=False):
    """Click on an instance: create its override row (or reuse the existing one); Ctrl-click also ticks Delete. Returns the row number."""
    kw={'delete':True} if delete else {}
    return override_set(asset,instance_id,**kw)

def pick_state_name(asset):
    return paint_state_name(asset)

def pick_start(asset):
    """Pick Instance button: make this node current and enter the viewport tool in picking mode (Esc finishes)."""
    if not hou.isUIAvailable():raise hou.NodeError('Picking needs the Houdini interface (a Scene Viewer).')
    viewer=hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
    if viewer is None:raise hou.NodeError('Open a Scene Viewer pane to pick instances.')
    asset.setUserData('arraytron_pick','1')
    asset.setCurrent(True,clear_all_selected=True);viewer.setCurrentState(paint_state_name(asset))
