# Blast (v1.33.0): an overall selection of instances (by id pattern, random fraction, region or prototype, or picked by hand with Houdini's own selection tools), with an Invert option, that is deleted or
# transformed all together (a move, a rotation and a scale about one pivot, as one group). It runs in the BLAST Python SOP after the distribution, variation, prototype assignment,
# separation and physics, just before the Override Database, so it selects the instances that are really there. Appended to the PythonModule after the Field Stack and
# the overrides (it reuses scatter_hash, read_points, resolve, bank_rows, qmul, euler_to_quat and pick_instances). The pure numpy functions are tested directly.
import math
import time
import numpy as np

BLAST_SELECT=('Id Pattern','Random','Region','Prototype','Custom (Houdini selection)')
BLAST_REGION=('Sphere','Box','Triangle','Hexagon','Polygon','Star','Metaballs')
BLAST_ACTION=('Delete','Transform')
BLAST_PIVOT=('Selection Center','Each Instance','World Origin','Custom')
BLAST_OPS=('Replace','Add','Remove','Toggle')

# ---------------------------------------------------------------- id patterns
def parse_ids(text):
    """The ids named by a pattern of tokens separated by spaces or commas: `7`, `10-20`, `0-100:5` (every 5th of 0 to 100), `*` (all). Returns (explicit ids, ranges, all); a range is (lo, hi, step)."""
    ids=set();ranges=[];every=False
    for tok in str(text).replace(',',' ').split():
        if tok=='*':every=True;continue
        step=1
        if ':' in tok:tok,s=tok.split(':',1);step=max(int(s),1)
        if '-' in tok[1:]:
            a,b=tok[0]+tok[1:].split('-',1)[0],tok[1:].split('-',1)[1];lo,hi=int(a),int(b);ranges.append((min(lo,hi),max(lo,hi),step))
        else:ids.add(int(tok))
    return ids,ranges,every

def select_ids(ids,text):
    """Boolean mask: which of the instance ids the pattern names."""
    ids=np.asarray(ids,dtype=np.int64);sel=np.zeros(len(ids),dtype=bool);named,ranges,every=parse_ids(text)
    if every:return np.ones(len(ids),dtype=bool)
    if named:sel|=np.isin(ids,np.array(sorted(named),dtype=np.int64))
    for lo,hi,step in ranges:sel|=(ids>=lo)&(ids<=hi)&((ids-lo)%step==0)
    return sel

def ids_to_text(ids):
    """The shortest pattern that names exactly these ids: runs of consecutive ids become `a-b`, the rest are single numbers (`3 7-10 15`)."""
    v=np.unique(np.asarray(ids,dtype=np.int64))
    if len(v)==0:return ''
    cut=np.nonzero(np.diff(v)!=1)[0]+1;parts=[]
    for run in np.split(v,cut):parts.append(str(int(run[0])) if len(run)==1 else '%d-%d'%(run[0],run[-1]))
    return ' '.join(parts)

def combine_picks(current,hits,op):
    """The picked ids after a viewport selection: op 0 Replace (the hits), 1 Add, 2 Remove, 3 Toggle (the hits that were picked are dropped, the others added). Arrays of ids in, sorted unique ids out."""
    current=np.unique(np.asarray(current,dtype=np.int64));hits=np.unique(np.asarray(hits,dtype=np.int64))
    if op==0:return hits
    if op==1:return np.union1d(current,hits)
    if op==2:return np.setdiff1d(current,hits)
    return np.setxor1d(current,hits)

# ---------------------------------------------------------------- region shapes
def select_region(P,shape,centre,size):
    """Boolean mask of the points inside a sphere (size[0] is the radius) or an axis aligned box (size is the full width, height and depth) around the centre."""
    P=np.asarray(P,dtype=np.float64);d=P-np.asarray(centre,dtype=np.float64)
    if shape==0:return np.einsum('ij,ij->i',d,d)<=float(size[0])**2
    return np.all(np.abs(d)<=0.5*np.asarray(size,dtype=np.float64),axis=1)

def plan_uv(P,centre,rotation):
    """The XZ position of every point about the centre in the frame of a shape turned `rotation` degrees (measured from +X towards +Z): (u, v) and the height above the centre."""
    d=np.asarray(P,dtype=np.float64)-np.asarray(centre,dtype=np.float64);a=math.radians(rotation);c,s=math.cos(a),math.sin(a)
    return d[:,0]*c+d[:,2]*s,-d[:,0]*s+d[:,2]*c,d[:,1]

def polygon_mask(P,centre,radius,sides,rotation=0.0,height=1e9):
    """Inside a regular polygon of `sides` corners (3 a triangle, 6 a hexagon ...) in the XZ plane whose corners are `radius` from the centre, the first one `rotation` degrees from +X, extruded `height` tall
    (centred on the centre)."""
    n=max(int(sides),3);u,v,y=plan_uv(P,centre,rotation);phi=np.pi/n*(2*np.arange(n)+1);apothem=float(radius)*math.cos(math.pi/n)
    inside=np.all(u[:,None]*np.cos(phi)[None,:]+v[:,None]*np.sin(phi)[None,:]<=apothem,axis=1)
    return inside&(np.abs(y)<=0.5*float(height))

def inside_polygon(u,v,verts):
    """Crossing number test of the points (u, v) against a closed polygon `verts` (m, 2), any shape."""
    inside=np.zeros(len(u),dtype=bool);m=len(verts)
    for k in range(m):
        x0,y0=verts[k];x1,y1=verts[(k+1)%m]
        if y0==y1:continue
        crosses=((y0>v)!=(y1>v))&(u<(x1-x0)*(v-y0)/(y1-y0)+x0);inside^=crosses
    return inside

def star_vertices(outer,inner_ratio,points):
    """The corners of a star with `points` tips: alternating the outer radius and outer x inner_ratio, the first tip on +X."""
    n=max(int(points),3);ang=np.pi*np.arange(2*n)/n;r=np.where(np.arange(2*n)%2==0,float(outer),float(outer)*float(inner_ratio))
    return np.stack([r*np.cos(ang),r*np.sin(ang)],axis=1)

def star_mask(P,centre,outer,inner_ratio,points,rotation=0.0,height=1e9):
    """Inside a star in the XZ plane, extruded `height` tall."""
    u,v,y=plan_uv(P,centre,rotation);return inside_polygon(u,v,star_vertices(outer,inner_ratio,points))&(np.abs(y)<=0.5*float(height))

def blob_layout(centre,radius,count,spread,seed):
    """The metaballs: the first at the centre with the full radius, the others scattered by the seed inside a ball of radius `spread` with 60 to 100 percent of the radius. Returns (centres, radii)."""
    rng=np.random.default_rng(int(seed));n=max(int(count),1);centres=np.zeros((n,3));radii=np.full(n,float(radius))
    for k in range(1,n):
        d=rng.normal(size=3);d/=max(np.linalg.norm(d),1e-12);centres[k]=d*float(spread)*rng.random()**(1.0/3.0);radii[k]=float(radius)*(0.6+0.4*rng.random())
    return np.asarray(centre,dtype=np.float64)+centres,radii

def blob_field(P,centres,radii):
    """The metaball field: the sum of (1 - (d / r)^2)^3 of every ball (1 at its centre, 0 at its radius), so the balls melt into each other where they overlap."""
    P=np.asarray(P,dtype=np.float64);f=np.zeros(len(P))
    for c,r in zip(centres,radii):
        t2=np.einsum('ij,ij->i',P-c,P-c)/max(r*r,1e-18);f+=np.where(t2<1.0,(1.0-t2)**3,0.0)
    return f

def blob_mask(P,centre,radius,count,spread,threshold,seed):
    """Inside the metaball shape: where the field of the balls is at least `threshold` (a lower threshold fattens the shape and joins the balls)."""
    c,r=blob_layout(centre,radius,count,spread,seed);return blob_field(P,c,r)>=float(threshold)

def region_selection(P,p):
    """Boolean mask of the points inside the Region shape described by the dict p (shape, centre, radius, size, rotation, height, sides, points, inner, blobs, spread, threshold, seed)."""
    shape=int(p['shape'])
    if shape==0:return select_region(P,0,p['centre'],(p['radius'],0.0,0.0))
    if shape==1:
        size=np.asarray(p['size'],dtype=np.float64)
        if p.get('rotation',0.0)==0.0:return select_region(P,1,p['centre'],size)
        u,v,y=plan_uv(P,p['centre'],p['rotation']);return (np.abs(u)<=0.5*size[0])&(np.abs(y)<=0.5*size[1])&(np.abs(v)<=0.5*size[2])
    if shape in (2,3,4):return polygon_mask(P,p['centre'],p['radius'],{2:3,3:6}.get(shape,p['sides']),p['rotation'],p['height'])
    if shape==5:return star_mask(P,p['centre'],p['radius'],p['inner'],p['points'],p['rotation'],p['height'])
    return blob_mask(P,p['centre'],p['radius'],p['blobs'],p['spread'],p['threshold'],p['seed'])

def transform_group(P,orient,scale,sel,move,rot_degrees,uniform,pivot_mode,pivot):
    """Move, rotate and scale the selected instances together. Pivot 0 Selection Center, 2 World Origin and 3 Custom: the group is rotated (about the pivot, rotation about X, then Y, then Z in degrees, fixed axes) and scaled
    (about the pivot, the instances grow with it) as one body, then moved; 1 Each Instance: every instance turns and scales about its own position, and the move is shared. Returns new (P, orient, scale)."""
    P=np.array(P,dtype=np.float64);orient=np.array(orient,dtype=np.float64);scale=np.array(scale,dtype=np.float64);sel=np.asarray(sel,dtype=bool)
    if not sel.any():return P,orient,scale
    q=euler_to_quat(rot_degrees);R=quat_to_matrix(q);move=np.asarray(move,dtype=np.float64);s=float(uniform)
    if pivot_mode==1:centre=P[sel]
    else:centre=np.asarray(pivot,dtype=np.float64) if pivot_mode==3 else (np.zeros(3) if pivot_mode==2 else P[sel].mean(axis=0))
    if pivot_mode==1:P[sel]=P[sel]+move
    else:P[sel]=centre+(s*(P[sel]-centre))@R.T+move
    new=qmul(np.broadcast_to(q,(int(sel.sum()),4)),orient[sel]);orient[sel]=new/np.linalg.norm(new,axis=1,keepdims=True);scale[sel]*=s
    return P,orient,scale

def quat_to_matrix(q):
    """3x3 rotation matrices of quaternions (x, y, z, w) (N,4) or (4,)."""
    q=np.asarray(q,dtype=np.float64);q=q/np.linalg.norm(q,axis=-1,keepdims=True);x,y,z,w=q[...,0],q[...,1],q[...,2],q[...,3]
    return np.stack([np.stack([1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],axis=-1),np.stack([2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],axis=-1),np.stack([2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)],axis=-1)],axis=-2)

# ---------------------------------------------------------------- Houdini side
import hou

def region_parameters(asset):
    """The Region shape of the node as the dict region_selection takes."""
    return dict(shape=asset.evalParm('blast_shape'),centre=asset.evalParmTuple('blast_center'),radius=asset.evalParm('blast_radius'),size=asset.evalParmTuple('blast_size'),rotation=asset.evalParm('blast_rotate'),
                height=asset.evalParm('blast_height'),sides=asset.evalParm('blast_sides'),points=asset.evalParm('blast_points'),inner=asset.evalParm('blast_inner'),blobs=asset.evalParm('blast_blobs'),
                spread=asset.evalParm('blast_spread'),threshold=asset.evalParm('blast_threshold'),seed=asset.evalParm('blast_blobseed'))

def blast_selection(asset,s):
    """Boolean mask of the instances the Blast section selects (before Invert) for the point dict `s` of read_points."""
    kind=asset.evalParm('blast_select');ids=s['id']
    if kind==0:return select_ids(ids,asset.evalParm('blast_ids'))
    if kind==1:return scatter_hash(ids,asset.evalParm('blast_seed'),31)<asset.evalParm('blast_random')/100.0
    if kind==2:return region_selection(s['P'],region_parameters(asset))
    if kind==4:return select_ids(ids,asset.evalParm('blast_picked'))
    try:bank=[e['row'] for e in resolve(asset)]
    except hou.NodeError:bank=bank_rows(asset)
    rows=np.array(bank+[0])[np.minimum(s['protoindex'],len(bank))] if bank else np.zeros(len(ids),dtype=np.int64)
    return rows==asset.evalParm('blast_proto')

def sop_blast(geo,asset):
    """BLAST: select instances (Select By), Invert the selection if asked, then Delete them or Transform them all together. Ids are never changed."""
    for name,default in (('blast_before',0),('blast_selected',0),('blast_after',0)):geo.addAttrib(hou.attribType.Global,name,default)
    n=geo.intrinsicValue('pointcount');geo.setGlobalAttribValue('blast_before',n);geo.setGlobalAttribValue('blast_after',n)
    if not asset.evalParm('blast_on') or n==0:return
    s=read_points(geo);sel=blast_selection(asset,s)
    if asset.evalParm('blast_invert'):sel=~sel
    geo.setGlobalAttribValue('blast_selected',int(sel.sum()))
    if not sel.any():return
    if asset.evalParm('blast_action')==0:
        geo.deletePoints([geo.point(int(i)) for i in np.nonzero(sel)[0]]);geo.setGlobalAttribValue('blast_after',n-int(sel.sum()));return
    P,orient,scale=transform_group(s['P'],s['orient'],s['scale'],sel,asset.evalParmTuple('blast_move'),asset.evalParmTuple('blast_rot'),asset.evalParm('blast_scale'),asset.evalParm('blast_pivot'),asset.evalParmTuple('blast_pivotpos'))
    geo.setPointFloatAttribValues('P',P.ravel().tolist());geo.setPointFloatAttribValues('orient',orient.ravel().tolist());geo.setPointFloatAttribValues('scale',scale.ravel().tolist())

def blast_info(asset):
    """Read-only text for the Blast section."""
    if not asset.evalParm('blast_on'):return 'Blast is off: every instance is kept as it is.'
    try:
        g=asset.node('USD_COMPILER/BLAST').geometry();what='deleted' if asset.evalParm('blast_action')==0 else 'transformed together'
        return '%d of %d instances selected%s: %s. %d left.'%(g.attribValue('blast_selected'),g.attribValue('blast_before'),' (inverted)' if asset.evalParm('blast_invert') else '',what,g.attribValue('blast_after'))
    except Exception as exc:return 'Cannot evaluate Blast: %s'%exc

# ---------------------------------------------------------------- Houdini's own selection (the buttons)
# Select In Houdini builds a helper geometry object in /obj (<node name>_blast_select) that holds one point per instance (the same positions as the viewport shows) and asks Houdini's own point selection
# (hou.SceneViewer.selectGeometry): the Box, Lasso, Brush and Laser tools of the select toolbar, with all their modifiers, Enter to finish. The selected points are mapped back to instance ids and stored in blast_picked.
BLAST_HELPER_SUFFIX='_blast_select'

def blast_snapshot(asset):
    """The instances Blast can select, as dict(ids, P): the points that reach the BLAST node (the scatter before Blast acts, so the ones Blast deletes can still be selected), in world space."""
    node=asset.node('USD_COMPILER/BLAST');inputs=node.inputs();geo=inputs[0].geometry() if inputs else None
    empty=dict(ids=np.zeros(0,dtype=np.int64),P=np.zeros((0,3)))
    if geo is None or geo.intrinsicValue('pointcount')==0:return empty
    ids=np.array(geo.pointIntAttribValues('id'),dtype=np.int64);P=np.array(geo.pointFloatAttribValues('P'),dtype=np.float64).reshape(-1,3)
    W=np.eye(4)
    try:
        from pxr import Usd,UsdGeom
        stage=asset.stage();root=asset.evalParm('outputpath').rstrip('/') or '/'
        prim=next((p for p in stage.Traverse() if p.IsA(UsdGeom.PointInstancer) and (str(p.GetPath())+'/').startswith(root+'/')),None) if stage is not None else None
        if prim is not None:
            m=UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode(hou.frame()));W=np.array([[m[i][j] for j in range(4)] for i in range(4)],dtype=float)
    except Exception:pass
    return dict(ids=ids,P=P@W[:3,:3]+W[3,:3])

def sop_blast_snapshot(geo,asset):
    """The Python SOP of the helper: one point per instance with its id (int attribute `id`), red (Cd) where it is picked already."""
    snap=blast_snapshot(asset);geo.clear();geo.addAttrib(hou.attribType.Point,'id',0);geo.addAttrib(hou.attribType.Point,'Cd',(0.75,0.75,0.75))
    if len(snap['ids'])==0:return
    geo.createPoints([tuple(row) for row in snap['P'].tolist()]);geo.setPointIntAttribValues('id',snap['ids'].tolist())
    picked=np.isin(snap['ids'],blast_picked_ids(asset));cd=np.where(picked[:,None],np.array([[1.0,0.25,0.15]]),np.array([[0.75,0.75,0.75]]))
    geo.setPointFloatAttribValues('Cd',cd.ravel().tolist())

def blast_helper(asset):
    """The selection helper (a geo object in /obj with one Python SOP SNAPSHOT), made new each time."""
    old=hou.node('/obj/'+asset.name()+BLAST_HELPER_SUFFIX)
    if old is not None:old.destroy()
    geo=hou.node('/obj').createNode('geo',asset.name()+BLAST_HELPER_SUFFIX)
    for child in geo.children():child.destroy()
    snap=geo.createNode('python','SNAPSHOT');snap.parm('python').set("asset=hou.node('%s')\nasset.hdaModule().sop_blast_snapshot(hou.pwd().geometry(),asset)\n"%asset.path());snap.setDisplayFlag(True);snap.setRenderFlag(True);geo.layoutChildren()
    return geo

def blast_selection_text(selection):
    """The point numbers of a hou.GeometrySelection of the helper as text (read while the helper still exists); '' when nothing is selected."""
    if selection is None:return ''
    text=selection.mergedSelectionString(empty_string_selects_all=False)
    return '' if not text or text.strip()=='*' else text

def blast_points_from_text(text):
    """The point numbers a selection string names, as an array."""
    return ids_from_text(text) if text.strip() else np.zeros(0,dtype=np.int64)

def blast_hselect(asset,selection_func=None):
    """Select In Houdini: switch Blast to Custom, show the helper points and let the user select them with Houdini's own selection tools (Enter finishes, Esc cancels). The Operation menu decides how the
    selection joins the list (Replace, Add, Remove, Toggle). `selection_func(helper)` stands in for the viewer in the tests. Returns the number of picked ids."""
    viewer=None
    if selection_func is None:
        if not hou.isUIAvailable():raise hou.NodeError('Selecting needs the Houdini interface (a Scene Viewer).')
        viewer=hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
        if viewer is None:raise hou.NodeError('Open a Scene Viewer pane to select instances.')
    with hou.undos.group('Arraytron Blast selection'):
        asset.parm('blast_on').set(1);asset.parm('blast_select').set(4)
    helper=blast_helper(asset);snap_node=helper.node('SNAPSHOT');snap_node.cook(force=True);geo=snap_node.geometry()
    if geo.intrinsicValue('pointcount')==0:
        helper.destroy();raise hou.NodeError('There are no instances to select.')
    ids=np.array(geo.pointIntAttribValues('id'),dtype=np.int64);text=None
    try:
        if selection_func is not None:selection=selection_func(helper)
        else:
            old=viewer.pwd();viewer.setPwd(helper);snap_node.setCurrent(True,clear_all_selected=True)
            try:
                try:selection=viewer.selectGeometry("Select the instances with Houdini's select tools (Box, Lasso, Brush, Laser; Shift adds, Ctrl removes). Enter: done   Esc: cancel",use_existing_selection=False,geometry_types=(hou.geometryType.Points,),allow_drag=True,quick_select=False)
                except TypeError:selection=viewer.selectGeometry('Select the instances. Enter: done   Esc: cancel')
                text=blast_selection_text(selection)                                                          # read before the helper goes: the selection belongs to its node
            finally:
                viewer.setPwd(old);asset.setCurrent(True,clear_all_selected=True)
        if text is None:text=blast_selection_text(selection)
    finally:helper.destroy()
    if selection is None:return len(blast_picked_ids(asset))
    pts=blast_points_from_text(text);pts=pts[(pts>=0)&(pts<len(ids))];new=combine_picks(blast_picked_ids(asset),ids[pts],asset.evalParm('blast_pick_op'))
    blast_pick_write(asset,new);return len(new)

_BLAST_BUSY={'on':False,'last':0.0}

def blast_hselect_deferred(path):
    """Runs the selection outside the button callback (a selection session runs its own event loop, which a parm callback must not)."""
    asset=hou.node(path)
    if asset is None:return
    _BLAST_BUSY['on']=True
    try:blast_hselect(asset)
    except hou.Error as exc:
        print('Arraytron Blast: %s'%exc)
        try:hou.ui.setStatusMessage('Arraytron Blast: %s'%exc,severity=hou.severityType.Error)
        except Exception:pass
    finally:_BLAST_BUSY['on']=False;_BLAST_BUSY['last']=time.time()

def blast_pick_start(asset):
    """The Select In Houdini button. With the interface the selection is started after the callback returns; pressing Enter to finish it must not press the button again (the focus may still be on it), so a press
    while a selection runs, or within a second of its end, is ignored."""
    if _BLAST_BUSY['on'] or time.time()-_BLAST_BUSY['last']<1.0:return 0
    if not hou.isUIAvailable():return blast_hselect(asset)                                                  # raises: there is no viewer
    import hdefereval
    path=asset.path();_BLAST_BUSY['on']=True;_BLAST_BUSY['last']=time.time()
    hdefereval.executeDeferred(lambda:blast_hselect_deferred(path));return 0

def ids_from_text(text):
    """The ids a pattern names, as a sorted array (ranges expanded with numpy; `*` is not an id list)."""
    named,ranges,every=parse_ids(text);parts=[np.array(sorted(named),dtype=np.int64)]+[np.arange(lo,hi+1,step,dtype=np.int64) for lo,hi,step in ranges]
    return np.unique(np.concatenate(parts))

def blast_picked_ids(asset):
    """The ids picked by hand, as an array."""
    return ids_from_text(asset.evalParm('blast_picked'))

def blast_pick_write(asset,ids):
    """Store the picked ids in the node (one undo step)."""
    with hou.undos.group('Arraytron Blast selection'):asset.parm('blast_picked').set(ids_to_text(ids))

def blast_pick_clear(asset):
    """Clear Selection button."""
    blast_pick_write(asset,[])

def blast_pick_all(asset):
    """Select All button: every instance that reaches Blast."""
    blast_pick_write(asset,blast_snapshot(asset)['ids'])
