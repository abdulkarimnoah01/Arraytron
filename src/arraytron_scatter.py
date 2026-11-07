# Curve (v0.4.5) and Surface Scatter (v0.4.6) generators. Appended to arraytron_module.py + arraytron_physics.py by the builder, so the Houdini
# parts reach shape_mesh(), triangulate() and quat_from_matrix() from the physics module. The pure functions (curve tessellation, arc-length
# sampling, frames, triangle sampling) take and return numpy arrays and are tested directly.
import math
import numpy as np
try:quat_from_matrix
except NameError:from arraytron_physics import quat_from_matrix,triangulate,shape_mesh

MAX_POINTS=10000

def scatter_hash(ids,seed,stream=0):
    """Deterministic number in [0,1) per integer id, seed and stream (splitmix64 finaliser): adding points never reshuffles earlier ones."""
    with np.errstate(over='ignore'):
        z=np.asarray(ids,dtype=np.uint64)*np.uint64(0x9E3779B97F4A7C15)+np.uint64(seed)*np.uint64(0xD1B54A32D192ED03)+np.uint64(stream+1)*np.uint64(0x8CB92BA72F3D8DD7)
        z=(z^(z>>np.uint64(30)))*np.uint64(0xBF58476D1CE4E5B9);z=(z^(z>>np.uint64(27)))*np.uint64(0x94D049BB133111EB);z=z^(z>>np.uint64(31))
    return (z>>np.uint64(11)).astype(np.float64)/float(1<<53)

# ---------------------------------------------------------------- curves
def _bezier(c,t):
    a,b,cc,d=c;u=1-t;return (u**3)[:,None]*a+(3*u*u*t)[:,None]*b+(3*u*t*t)[:,None]*cc+(t**3)[:,None]*d
def _bspline(c,t):
    a,b,cc,d=c;return ((1-t)**3)[:,None]*a/6+((3*t**3-6*t*t+4)/6)[:,None]*b+((-3*t**3+3*t*t+3*t+1)/6)[:,None]*cc+(t**3/6)[:,None]*d
def _catmull(c,t):
    a,b,cc,d=c;return 0.5*(2*b+(-a+cc)*t[:,None]+(2*a-5*b+4*cc-d)*(t*t)[:,None]+(-a+3*b-3*cc+d)*(t**3)[:,None])

def tessellate_curve(points,kind='linear',basis='bezier',wrap='nonperiodic',steps=64):
    """Dense polyline (M,3) of one USD BasisCurves curve and whether it is closed. kind linear|cubic, basis bezier|bspline|catmullRom,
    wrap nonperiodic|periodic|pinned. A pinned bspline repeats its end points twice and a pinned catmullRom once, so the curve starts and
    ends exactly on the first and last control point."""
    p=np.asarray(points,dtype=np.float64).reshape(-1,3);n=len(p)
    if kind=='linear':
        if wrap=='periodic' and n>2:return np.vstack([p,p[:1]]),True
        return p,False
    if basis=='bezier':
        if wrap=='periodic':
            segs=[[p[(3*k+j)%n] for j in range(4)] for k in range(n//3)]
        else:segs=[p[3*k:3*k+4] for k in range((n-1)//3)]
        evaluate=_bezier
    else:
        if wrap=='pinned':p=np.vstack([[p[0]]*(2 if basis=='bspline' else 1),p,[p[-1]]*(2 if basis=='bspline' else 1)]);n=len(p)
        if wrap=='periodic':segs=[[p[(k+j)%n] for j in range(4)] for k in range(n)]
        else:segs=[p[k:k+4] for k in range(n-3)]
        evaluate=_bspline if basis=='bspline' else _catmull
    if not segs:return p,False
    out=[];t=np.linspace(0.0,1.0,steps,endpoint=False)
    for s in segs:out.append(evaluate(s,t))
    closed=wrap=='periodic'
    out.append(np.array(segs[-1][-1:]) if basis=='bezier' and not closed else np.zeros((0,3)))   # exact end of an open bezier
    if basis!='bezier' and not closed:                                                            # open bspline / catmullRom: close the last segment at t = 1
        out.append(evaluate(segs[-1],np.array([1.0])))
    poly=np.vstack(out)
    if closed:poly=np.vstack([poly,poly[:1]])
    return poly,closed

def arclength(poly):
    seg=np.linalg.norm(np.diff(poly,axis=0),axis=1);return np.concatenate(([0.0],np.cumsum(seg)))

def sample_polyline(poly,s):
    """Positions (K,3) and unit tangents (K,3) at arc lengths s along a polyline (clamped to its ends)."""
    cum=arclength(poly);L=cum[-1]
    if L<=0:return np.repeat(poly[:1],len(s),axis=0),np.tile([0.0,0.0,1.0],(len(s),1))
    s=np.clip(np.asarray(s,dtype=np.float64),0.0,L);i=np.clip(np.searchsorted(cum,s,side='right')-1,0,len(poly)-2)
    seg=poly[i+1]-poly[i];length=np.maximum(cum[i+1]-cum[i],1e-12);f=((s-cum[i])/length)[:,None]
    # unit direction of every polyline segment; zero-length ones (repeated control points) borrow the nearest real direction
    d=np.diff(poly,axis=0);norm=np.linalg.norm(d,axis=1);valid=norm>1e-12;dirs=d/np.maximum(norm,1e-12)[:,None]
    index=np.where(valid,np.arange(len(d)),-1);forward=np.maximum.accumulate(index)
    first=np.argmax(valid);forward=np.where(forward<0,first,forward)                # leading zero-length segments use the first real one
    return poly[i]+seg*f,dirs[forward[i]]

def curve_parameters(length,closed,mode,count,spacing,ids,seed):
    """Arc lengths along one curve. mode 0 By Count (ends included, a closed curve does not repeat its start), 1 By Spacing, 2 Random (keyed on ids)."""
    if mode==0:
        n=max(1,count)
        if n==1:return np.array([0.0])
        return length*np.arange(n)/(n if closed else n-1)
    if mode==1:
        step=max(spacing,1e-3);n=int(math.floor(length/step+1e-9))+(0 if closed else 1)
        return step*np.arange(max(1,n))
    return length*scatter_hash(ids,seed,0)

def frames_from_tangent(tangent,up,roll=0.0):
    """Quaternions (K,4; x,y,z,w) whose rotation sends +Z to the tangent and +Y as close to `up` as possible (then rolled about the tangent)."""
    t=np.asarray(tangent,dtype=np.float64);t=t/np.maximum(np.linalg.norm(t,axis=1),1e-12)[:,None];up=np.asarray(up,dtype=np.float64)
    out=np.zeros((len(t),4));c,s_=math.cos(math.radians(roll)),math.sin(math.radians(roll))
    for k in range(len(t)):
        u=up if abs(np.dot(t[k],up/np.linalg.norm(up)))<0.999 else np.array([1.0,0.0,0.0]) if abs(t[k][0])<0.9 else np.array([0.0,0.0,1.0])
        x=np.cross(u,t[k]);x/=np.linalg.norm(x);y=np.cross(t[k],x)               # x = side, y = up
        x,y=c*x+s_*y,-s_*x+c*y
        out[k]=quat_from_matrix(np.array([x,y,t[k]]))                               # rows = images of +X, +Y, +Z (row-vector convention)
    return out

# ---------------------------------------------------------------- surfaces
def triangles_world(meshes):
    """Merge (points, counts, indices) meshes into world triangles: points (N,3), tris (T,3), per-triangle area and unit normal, vertex normals."""
    P=[];T=[];base=0
    for points,counts,indices,flip in meshes:
        tri=triangulate(counts,indices)
        if not len(tri):continue
        if flip:tri=tri[:,::-1]
        P.append(points);T.append(tri+base);base+=len(points)
    if not P:return np.zeros((0,3)),np.zeros((0,3),dtype=np.int64),np.zeros(0),np.zeros((0,3)),np.zeros((0,3))
    return mesh_attributes(np.vstack(P),np.vstack(T))

def mesh_attributes(P,T):
    """Triangles (T, after dropping the degenerate ones), per-triangle area and unit normal and the area weighted vertex normals of a triangle mesh. Returns P,T,area,normals,vn."""
    c=np.cross(P[T[:,1]]-P[T[:,0]],P[T[:,2]]-P[T[:,0]]);twice=np.linalg.norm(c,axis=1)
    keep=twice>1e-14;T=T[keep];c=c[keep];twice=twice[keep]
    normals=c/twice[:,None];vn=np.zeros_like(P)
    for j in range(3):                                                             # area weighted: the cross product's length is twice the area (np.add.at took 6 s on 8 million triangles, bincount 0.3 s)
        for k in range(3):vn[:,k]+=np.bincount(T[:,j],weights=c[:,k],minlength=len(P))
    vn/=np.maximum(np.linalg.norm(vn,axis=1),1e-12)[:,None]
    return P,T,0.5*twice,normals,vn

def direction_weights(normals,direction,spread,soft=0.0,opposite=False):
    """Keep By Direction (v1.30.0): the weight 0..1 of every triangle by the angle between its normal and `direction` (one vector, or one per triangle). Within `spread` degrees the weight is 1 (a hard
    cone, soft = 0); with soft > 0 the weight is 1 up to spread x (1 - soft) and falls smoothly to 0 at `spread`. With `opposite` the opposite direction counts as well (a normal 180 degrees away is a match)."""
    n=np.asarray(normals,dtype=np.float64);d=np.asarray(direction,dtype=np.float64)
    d=d/np.maximum(np.linalg.norm(d,axis=-1,keepdims=True),1e-12)
    ang=np.degrees(np.arccos(np.clip(np.sum(n*d,axis=1),-1.0,1.0)))
    if opposite:ang=np.minimum(ang,180.0-ang)
    spread=float(spread);soft=min(max(float(soft),0.0),1.0)
    if soft<=0.0:return (ang<=spread+1e-9).astype(np.float64)
    inner=spread*(1.0-soft);t=np.clip((ang-inner)/max(spread-inner,1e-9),0.0,1.0)
    return 1.0-t*t*(3.0-2.0*t)

def _cluster_mesh(P,T,cell,lo):
    """One vertex clustering pass: every vertex goes to the cell of a grid (size `cell`) it lies in, the vertices of a cell are merged into their mean, triangles that collapse or repeat are dropped."""
    q=np.floor((P-lo)/cell).astype(np.int64);dims=q.max(axis=0)+1
    key=(q[:,0]*dims[1]+q[:,1])*dims[2]+q[:,2]
    uniq,inv=np.unique(key,return_inverse=True);n=len(uniq);cnt=np.bincount(inv,minlength=n)
    Q=np.stack([np.bincount(inv,weights=P[:,k],minlength=n)/cnt for k in range(3)],axis=1)
    t=inv[T];t=t[(t[:,0]!=t[:,1])&(t[:,1]!=t[:,2])&(t[:,0]!=t[:,2])]
    if len(t) and n<2000000:                                                       # the same corners in another order: one triangle only (keeps the first, so the winding is kept)
        s=np.sort(t,axis=1);_,first=np.unique((s[:,0]*n+s[:,1])*n+s[:,2],return_index=True);t=t[np.sort(first)]
    used,inv2=np.unique(t,return_inverse=True)
    return Q[used],inv2.reshape(-1,3)

def reduce_mesh(P,T,target,total_area=None):
    """Poly reduce (v1.31.0): a triangle mesh of about `target` triangles that follows the shape of (P,T), made by vertex clustering on a grid (fast, numpy only: 8 million triangles in about 3 seconds).
    The cell size comes from the surface area (about two triangles per occupied cell) and is corrected up to twice so the result lands within 40 percent of the target. A mesh that is already at or below the
    target comes back unchanged. The winding is kept; the points of the result are the means of the merged vertices, so they lie close to the original surface, within one cell size."""
    target=max(int(target),8)
    if len(T)<=target:return P,T
    if total_area is None:
        c=np.cross(P[T[:,1]]-P[T[:,0]],P[T[:,2]]-P[T[:,0]]);total_area=0.5*float(np.linalg.norm(c,axis=1).sum())
    lo=P.min(axis=0);cell=max(float(np.sqrt(2.0*total_area/target)),1e-9);best=None
    for _ in range(3):
        Q,t=_cluster_mesh(P,T,cell,lo);err=abs(len(t)-target)
        if best is None or err<best[0]:best=(err,Q,t)
        if 0.6*target<=len(t)<=1.4*target or len(t)==0:break
        cell*=float(np.sqrt(max(len(t),1)/target))
    return best[1],best[2]

def surface_points(P,T,area,normals,vn,count,seed,smooth,slope_min,slope_max,offset,align,tri_weight=None):
    """Count stable points on a triangle mesh. Point i uses only hash(i, seed): triangle by area-weighted CDF, then a uniform barycentric draw.
    Triangles outside [slope_min, slope_max] degrees from world up are excluded from the CDF; tri_weight (v1.30.0, one number per triangle) scales the area of each triangle in the CDF. Returns positions, normals, quaternions."""
    up_dot=np.clip(normals[:,1],-1.0,1.0);slope=np.degrees(np.arccos(up_dot));ok=(slope>=slope_min-1e-9)&(slope<=slope_max+1e-9)
    weights=np.where(ok,area,0.0)
    if tri_weight is not None:weights=weights*tri_weight
    if weights.sum()<=0 or count<=0:return np.zeros((0,3)),np.zeros((0,3)),np.zeros((0,4))
    cdf=np.cumsum(weights);cdf/=cdf[-1];ids=np.arange(count)
    tri=np.minimum(np.searchsorted(cdf,scatter_hash(ids,seed,1),side='right'),len(cdf)-1)
    r1=np.sqrt(scatter_hash(ids,seed,2));r2=scatter_hash(ids,seed,3);a,b,c=1-r1,r1*(1-r2),r1*r2
    A,B,C=P[T[tri,0]],P[T[tri,1]],P[T[tri,2]];pos=A*a[:,None]+B*b[:,None]+C*c[:,None]
    if smooth:
        n=vn[T[tri,0]]*a[:,None]+vn[T[tri,1]]*b[:,None]+vn[T[tri,2]]*c[:,None];n/=np.maximum(np.linalg.norm(n,axis=1),1e-12)[:,None]
    else:n=normals[tri]
    pos=pos+n*offset
    return pos,n,normal_alignment(n,align)

def normal_alignment(n,amount):
    """Quaternions (x,y,z,w) of the shortest rotation taking +Y to each normal, blended from the identity by amount (0..1)."""
    n=np.asarray(n,dtype=np.float64);up=np.array([0.0,1.0,0.0]);axis=np.cross(np.broadcast_to(up,n.shape),n);d=n@up
    q=np.zeros((len(n),4));q[:,:3]=axis;q[:,3]=1+d
    flip=(1+d)<1e-9                                                                # normal points straight down: turn half a circle about +X
    q[flip]=[1.0,0.0,0.0,0.0]
    q/=np.linalg.norm(q,axis=1)[:,None]
    amount=min(max(amount,0.0),1.0)
    if amount<1.0:                                                                  # nlerp towards the identity: exact for 0 and 1, close in between
        ident=np.array([0.0,0.0,0.0,1.0]);sign=np.where(q[:,3:4]<0,-1.0,1.0);q=q*sign
        q=q*amount+ident*(1-amount);q/=np.linalg.norm(q,axis=1)[:,None]
    return q

# ---------------------------------------------------------------- Houdini side
import fnmatch
import hou
from pxr import Usd, UsdGeom

def _local_root(asset,name,path=None):
    path=(asset.evalParm(name) if path is None else path).strip()
    if not path:raise hou.NodeError('The %s is empty: type or pick a prim path.'%asset.parm(name).description())
    stage=asset.node('SOURCE_RESOLVER').stage()
    if stage is None:raise hou.NodeError('The Source Resolver has no stage.')
    prim=stage.GetPrimAtPath(path)
    if not prim or not prim.IsValid():raise hou.NodeError('%s does not exist in the incoming stage.'%path)
    return stage,prim

def stage_curves(asset,path=None):
    """[(dense polyline in world space, closed)] for every BasisCurves curve under the Curve Prim (traversal order), after the Curve Index filter."""
    stage,root=_local_root(asset,'curve_prim',path);xc=UsdGeom.XformCache(Usd.TimeCode.Default());out=[]
    for prim in Usd.PrimRange(root):
        if prim.IsA(UsdGeom.NurbsCurves) or prim.IsA(UsdGeom.HermiteCurves):raise hou.NodeError('%s is a %s: only BasisCurves are supported.'%(prim.GetPath(),prim.GetTypeName()))
        if not prim.IsA(UsdGeom.BasisCurves) or UsdGeom.Imageable(prim).GetPurposeAttr().Get() in ('guide','proxy'):continue
        c=UsdGeom.BasisCurves(prim);pts=c.GetPointsAttr().Get();counts=c.GetCurveVertexCountsAttr().Get()
        if not pts or not counts:continue
        m=np.array(xc.GetLocalToWorldTransform(prim),dtype=np.float64).reshape(4,4);p=np.array(pts,dtype=np.float64).reshape(-1,3)@m[:3,:3]+m[3,:3]
        kind=str(c.GetTypeAttr().Get() or 'cubic');basis=str(c.GetBasisAttr().Get() or 'bezier');wrap=str(c.GetWrapAttr().Get() or 'nonperiodic');start=0
        for count in counts:
            out.append(tessellate_curve(p[start:start+count],kind,basis,wrap));start+=count
    if not out:raise hou.NodeError('No BasisCurves found under %s.'%root.GetPath())
    index=asset.evalParm('curve_index') if path is None else -1                   # the Curve Index filter belongs to the Curve distribution only
    if index>=0:
        if index>=len(out):raise hou.NodeError('Curve Index %d: only %d curve(s) under %s.'%(index,len(out),root.GetPath()))
        out=[out[index]]
    return out

def curve_points(asset):
    """Positions (N,3), quaternions (N,4), curve number (N,), parameter 0..1 (N,) and the unit tangent (N,3) of every point for the Curve distribution."""
    mode=asset.evalParm('curve_spacemode');count=asset.evalParm('curve_count');spacing=asset.evalParm('curve_spacing');seed=asset.evalParm('curve_seed')
    align=asset.evalParm('curve_align');up=np.array(asset.evalParmTuple('curve_up')) if asset.evalParm('curve_upmode')==1 else np.array([0.0,1.0,0.0])
    if np.linalg.norm(up)<1e-6:up=np.array([0.0,1.0,0.0])
    roll=asset.evalParm('curve_roll');rev=asset.evalParm('curve_reverse')
    P=[];Q=[];C=[];U=[];T=[];total=0
    for k,(poly,closed) in enumerate(stage_curves(asset)):
        L=arclength(poly)[-1]
        if mode==1:n_est=int(L/max(spacing,1e-3))+2
        else:n_est=count
        if total+n_est>MAX_POINTS+1:n_est=max(0,MAX_POINTS+1-total)
        ids=np.arange(total,total+max(n_est,1))
        s=curve_parameters(L,closed,mode,count,spacing,ids,seed)[:max(0,MAX_POINTS-total)]
        if rev:s=L-s
        pos,tan=sample_polyline(poly,s)
        if rev:tan=-tan
        T.append(tan)
        P.append(pos);Q.append(frames_from_tangent(tan,up,roll) if align else np.tile([0.0,0.0,0.0,1.0],(len(s),1)));C.append(np.full(len(s),k));U.append(s/L if L>0 else np.zeros(len(s)));total+=len(s)
    return np.vstack(P),np.vstack(Q),np.concatenate(C),np.concatenate(U),np.vstack(T)

SURFACE_CACHE={}                                  # (node, prim, output prim) -> (cook count of the incoming stage, tuple of read-only arrays), the most recent few; see stage_surface
SURFACE_CACHE_BYTES=3*2**30

def _cache_put(cache,key,entry):
    cache.pop(key,None);cache[key]=entry
    while len(cache)>1 and sum(e[2] for e in cache.values())>SURFACE_CACHE_BYTES:cache.pop(next(iter(cache)))
    return entry

def surface_cache_clear():
    SURFACE_CACHE.clear()

def stage_surface(asset,parm='surface_prim',path=None):
    """Triangles of every mesh or basic shape under the Surface Prim, in world space (see triangles_world). v1.31.0: a surface of millions of triangles took 9 s to read, on every
    cook and every time the node was selected (the Surface info text); now it is read once and kept (read-only arrays) until the incoming stage cooks again or the prim changes."""
    stage,root=_local_root(asset,parm,path);key=(asset.path(),root.GetPath().pathString,asset.evalParm('outputpath'))
    try:count=asset.node('SOURCE_RESOLVER').cookCount()
    except Exception:count=None
    hit=SURFACE_CACHE.get(key)
    if hit is not None and count is not None and hit[0]==count:return hit[1]
    out=_read_surface(asset,stage,root)
    for a in out:a.setflags(write=False)
    if count is not None:_cache_put(SURFACE_CACHE,key,(count,out,sum(a.nbytes for a in out)))
    return out

def _read_surface(asset,stage,root):
    xc=UsdGeom.XformCache(Usd.TimeCode.Default());own=asset.evalParm('outputpath').rstrip('/');meshes=[]
    for prim in Usd.PrimRange(root):
        path=prim.GetPath().pathString
        if path==own or path.startswith(own+'/') or not prim.IsA(UsdGeom.Gprim) or UsdGeom.Imageable(prim).GetPurposeAttr().Get() in ('guide','proxy'):continue
        shape=shape_mesh(prim)
        if shape is None:continue
        m=np.array(xc.GetLocalToWorldTransform(prim),dtype=np.float64).reshape(4,4)
        flip=prim.IsA(UsdGeom.Mesh) and str(UsdGeom.Mesh(prim).GetOrientationAttr().Get())=='leftHanded'
        if np.linalg.det(m[:3,:3])<0:flip=not flip
        meshes.append((shape[0]@m[:3,:3]+m[3,:3],shape[1],shape[2],flip))
    out=triangles_world(meshes)
    if not len(out[1]):raise hou.NodeError('No mesh or basic shape (cube, sphere, ...) found under %s.'%root.GetPath())
    return out

def surface_light_directions(asset,centers):
    """The direction from each triangle centre towards the Light Prim (v1.30.0), (n, 3) unit vectors. A DistantLight shines along its -Z axis, so the way towards it is its +Z axis for every triangle; any other
    light (sphere, disk, rect, cylinder ...) is a place: the vector from the triangle to the light's position. A DomeLight has no direction and is refused."""
    path=asset.evalParm('surface_light').strip()
    if not path:raise hou.NodeError('Keep By Direction: the Light Prim is empty.')
    stage=asset.node('SOURCE_RESOLVER').stage();prim=stage.GetPrimAtPath(path) if stage else None
    if not prim or not prim.IsValid():raise hou.NodeError('Keep By Direction: the light %s does not exist in the incoming stage.'%path)
    kind=prim.GetTypeName()
    if 'Dome' in kind:raise hou.NodeError('Keep By Direction: %s is a dome light, which has no direction. Use a distant light, or a Direction Vector.'%path)
    m=np.array(UsdGeom.XformCache(Usd.TimeCode.Default()).GetLocalToWorldTransform(prim),dtype=np.float64).reshape(4,4)
    if kind=='DistantLight':
        z=m[2,:3]/max(np.linalg.norm(m[2,:3]),1e-12);return np.tile(z,(len(centers),1))
    v=m[3,:3][None,:]-np.asarray(centers,dtype=np.float64);return v/np.maximum(np.linalg.norm(v,axis=1,keepdims=True),1e-12)

def surface_selection(asset,P,T,normals):
    """The Keep By Direction weight of every triangle (None when it is off or the node is an older release): the triangles whose normal lies within Spread Angle of the direction (a vector, or towards a light)."""
    if asset.parm('surface_dirsel') is None or not asset.evalParm('surface_dirsel'):return None
    if asset.evalParm('surface_dirsrc')==1:d=surface_light_directions(asset,P[T].mean(axis=1))
    else:
        d=np.array(asset.evalParmTuple('surface_dir'),dtype=np.float64)
        if np.linalg.norm(d)<1e-9:raise hou.NodeError('Keep By Direction: the Direction is the zero vector.')
    return direction_weights(normals,d,asset.evalParm('surface_spread'),asset.evalParm('surface_soft'),bool(asset.evalParm('surface_opp')))

def selected_area(area,w):
    """The area By Density counts: all of it, or (Keep By Direction) the area of every triangle times its weight."""
    return float(area.sum() if w is None else (area*w).sum())

PROXY_CACHE={}                                    # (node, Target Triangles) -> (the surface arrays it was made from, the reduced mesh arrays + the area factor)
INFO_LIMIT=200000                                 # the Surface text of a bigger surface waits for the first cook (reading it takes seconds)

def surface_proxy_on(asset):
    return asset.parm('surface_proxy') is not None and bool(asset.evalParm('surface_proxy'))

def surface_proxy_mesh(asset):
    """The reduced copy of the Surface Prim the Reduced Proxy mode scatters on (v1.31.0): (P,T,area,normals,vn) of about Target Triangles triangles, kept until the surface or the target changes, and the factor
    original area / reduced area (a reduced mesh is a little smaller: the Density counts the area of the ORIGINAL surface, so the amount of points does not depend on the reduction)."""
    base=stage_surface(asset);target=int(asset.evalParm('surface_proxy_tris'));key=(asset.path(),target)
    hit=PROXY_CACHE.get(key)
    if hit is not None and hit[0] is base[0]:return hit[1]
    total=float(base[2].sum());Q,t=reduce_mesh(base[0],base[1],target,total)
    if len(t)==0 or len(t)>=len(base[1]):out=base
    else:out=mesh_attributes(Q,t)
    for a in out:a.setflags(write=False)
    entry=(base[0],(out,total/max(float(out[2].sum()),1e-12)))
    PROXY_CACHE.pop(key,None)
    for k in [k for k in PROXY_CACHE if k[0]==key[0]]:PROXY_CACHE.pop(k)           # one proxy per node
    PROXY_CACHE[key]=entry;return entry[1]

def surface_scatter_mesh(asset):
    """(P,T,area,normals,vn,area factor) of the mesh the scatter runs on: the Surface Prim, or its reduced proxy."""
    if surface_proxy_on(asset):
        mesh,k=surface_proxy_mesh(asset);return mesh+(k,)
    return stage_surface(asset)+(1.0,)

def surface_total_area(asset):
    P,T,area,normals,vn,k=surface_scatter_mesh(asset);return selected_area(area,surface_selection(asset,P,T,normals))*k

SURFACE_REQUEST={}                                # node path -> (points the settings ask for, points made): the Scattered counter says so when a limit cut the number

def surface_limit(asset):
    """The most points Surface mode makes: the Point Limit parameter (v1.31.0, default 10000, the old fixed cap), or 10000 on an older node."""
    return int(asset.evalParm('surface_limit')) if asset.parm('surface_limit') is not None else MAX_POINTS

def surface_count(asset,area=None):
    if asset.evalParm('surface_countmode')==1:
        area=surface_total_area(asset) if area is None else area;want=int(round(area*asset.evalParm('surface_density')))
    else:want=int(asset.evalParm('surface_count'))
    got=int(min(surface_limit(asset),want));SURFACE_REQUEST[asset.path()]=(want,got);return got

def surface_samples(asset):
    P,T,area,normals,vn,k=surface_scatter_mesh(asset);w=surface_selection(asset,P,T,normals);count=surface_count(asset,selected_area(area,w)*k)
    return surface_points(P,T,area,normals,vn,count,asset.evalParm('surface_seed'),asset.evalParm('surface_normal')==1,asset.evalParm('surface_slope_min'),asset.evalParm('surface_slope_max'),asset.evalParm('surface_offset'),asset.evalParm('surface_align'),w)

def _emit(geo,pos,quat,extra=None):
    geo.clear();geo.addAttrib(hou.attribType.Point,'id',0);geo.addAttrib(hou.attribType.Point,'align',(0.0,0.0,0.0,1.0))
    if len(pos)==0:return
    geo.createPoints([(0.0,0.0,0.0)]*len(pos));geo.setPointFloatAttribValues('P',np.asarray(pos,dtype=np.float64).ravel().tolist())          # (a list of 1 million tuples of the positions took 0.6 s)
    geo.setPointIntAttribValues('id',list(range(len(pos))));geo.setPointFloatAttribValues('align',quat.ravel().tolist())
    for name,(kind,values) in (extra or {}).items():
        geo.addAttrib(hou.attribType.Point,name,0 if kind=='int' else 0.0)
        (geo.setPointIntAttribValues if kind=='int' else geo.setPointFloatAttribValues)(name,values.tolist())

def sop_curve(geo,asset):
    """generate_curve: points along the Curve Prim with the tangent alignment in p@align."""
    pos,quat,curve,u,tan=curve_points(asset);_emit(geo,pos,quat,{'curve':('int',curve),'curveu':('float',u)})
    if len(pos):geo.addAttrib(hou.attribType.Point,'pathdir',(0.0,0.0,1.0));geo.setPointFloatAttribValues('pathdir',tan.ravel().tolist())                    # the direction of the path: Rows offsets sideways from it

def sop_surface(geo,asset):
    """generate_surface: stable scatter on the Surface Prim with the normal alignment in p@align."""
    pos,n,quat=surface_samples(asset);_emit(geo,pos,quat)
    if len(pos)==0:hou.pwd().addWarning('Surface Scatter: no triangle lies inside the slope limits%s (downward faces count as 90 to 180 degrees), so there are no points.'%(' and faces the Keep By Direction cone' if asset.parm('surface_dirsel') is not None and asset.evalParm('surface_dirsel') else ''))

def curve_guide_lines(asset):
    """Polylines for the viewport guide of the Curve mode (world space), or [] when the curve cannot be read."""
    try:return [poly for poly,_ in stage_curves(asset)]
    except hou.Error:return []

def curve_info(asset):
    """Read-only text for the Curve folder."""
    try:
        curves=stage_curves(asset);lengths=[arclength(p)[-1] for p,_ in curves]
    except hou.Error as exc:return 'Cannot read the curve: %s'%exc
    mode=asset.evalParm('curve_spacemode');counts=[]
    for (poly,closed),L in zip(curves,lengths):counts.append(len(curve_parameters(L,closed,mode,asset.evalParm('curve_count'),asset.evalParm('curve_spacing'),np.arange(asset.evalParm('curve_count')),0)))
    return '%d curve(s), total length %.4g, %d points (%s).'%(len(curves),sum(lengths),sum(counts),', '.join(str(c) for c in counts[:6])+(' ...' if len(counts)>6 else ''))

def _estimate_triangles(root):
    """About how many triangles lie under the prim, from the face counts only (no vertex data is read): fast even for a surface of millions of triangles."""
    total=0
    for prim in Usd.PrimRange(root):
        if prim.IsA(UsdGeom.Mesh):
            counts=UsdGeom.Mesh(prim).GetFaceVertexCountsAttr().Get();total+=int(np.sum(np.maximum(np.asarray(counts,dtype=np.int64)-2,0))) if counts is not None else 0
        elif prim.IsA(UsdGeom.Gprim):total+=600
    return total

def surface_info(asset):
    """Read-only text of the Surface section. It is evaluated whenever the node is selected, so it never reads a big surface itself (v1.31.0): a surface of more than INFO_LIMIT triangles that is not yet in
    the cache shows its estimated size, and the numbers appear once the node has cooked."""
    try:
        stage,root=_local_root(asset,'surface_prim')
        try:cached=SURFACE_CACHE.get((asset.path(),root.GetPath().pathString,asset.evalParm('outputpath')))
        except Exception:cached=None
        if cached is None or cached[0]!=asset.node('SOURCE_RESOLVER').cookCount():
            est=_estimate_triangles(root)
            if est>INFO_LIMIT:return 'About %d triangles. The area and the number of points appear once the node has cooked (a surface this big is read once and kept).'%est
        P,T,area,normals,vn=stage_surface(asset);count=surface_count(asset,float(area.sum()))
    except hou.Error as exc:return 'Cannot read the surface: %s'%exc
    slope=np.degrees(np.arccos(np.clip(normals[:,1],-1,1)));ok=(slope>=asset.evalParm('surface_slope_min')-1e-9)&(slope<=asset.evalParm('surface_slope_max')+1e-9)
    text='%d triangles, area %.4g (%.4g inside the slope limits), %d points.'%(len(T),area.sum(),area[ok].sum(),count if ok.any() else 0)
    try:w=surface_selection(asset,P,T,normals)
    except hou.Error as exc:return text+'\nKeep By Direction: %s'%exc
    if w is not None:
        kept=ok&(w>0);text='%d triangles, area %.4g (%.4g inside the slope limits), %d points.\nKeep By Direction: %d of %d triangles kept, area %.4g.'%(len(T),area.sum(),area[ok].sum(),count if kept.any() else 0,int(kept.sum()),len(T),float((area*w)[ok].sum()))
    if surface_proxy_on(asset):
        hit=PROXY_CACHE.get((asset.path(),int(asset.evalParm('surface_proxy_tris'))))
        text+='\nReduced Proxy: '+('%d triangles (from %d); the points are scattered on it.'%(len(hit[1][0][1]),len(T)) if hit is not None and hit[0] is P else 'about %d triangles; it is built at the next cook.'%int(asset.evalParm('surface_proxy_tris')))
    return text
