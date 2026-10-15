# Physics Settle helpers (v0.4.0). Appended to arraytron_module.py by the builder, so they are reachable as hdaModule().<name>.
# The pure geometry functions (quickhull, SAT, stacking) take and return numpy arrays and do not need Houdini, so the test
# suite imports this file directly. The Houdini parts (bake, cache, proxies) are at the bottom.
import hashlib, math, os
import numpy as np

# ---------------------------------------------------------------- convex hull (farthest-point incremental quickhull)
def _tetra(p,eps):
    ex=[int(np.argmin(p[:,0])),int(np.argmax(p[:,0])),int(np.argmin(p[:,1])),int(np.argmax(p[:,1])),int(np.argmin(p[:,2])),int(np.argmax(p[:,2]))]
    best=(-1.0,0,0)
    for i in ex:
        for j in ex:
            d=float(np.linalg.norm(p[i]-p[j]))
            if d>best[0]:best=(d,i,j)
    if best[0]<=eps:return None
    a,b=best[1],best[2]
    ab=p[b]-p[a];ab/=np.linalg.norm(ab)
    rel=p-p[a];perp=rel-np.outer(rel@ab,ab);d2=np.linalg.norm(perp,axis=1)
    c=int(np.argmax(d2))
    if d2[c]<=eps:return None
    n=np.cross(p[b]-p[a],p[c]-p[a]);n/=np.linalg.norm(n)
    dist=(p-p[a])@n;d=int(np.argmax(np.abs(dist)))
    if abs(dist[d])<=eps:return None
    return a,b,c,d

def quickhull(points,max_vertices=0,eps=None):
    """Convex hull of an (N,3) array: returns (vertices (V,3) float64, faces (F,3) int, outward CCW). Farthest point first, so
    max_vertices (>=4, 0 = unlimited) keeps the best V-vertex approximation. Flat or line-like input is thickened to a box."""
    p=np.unique(np.asarray(points,dtype=np.float64).reshape(-1,3),axis=0)
    span=float(np.max(p.max(axis=0)-p.min(axis=0))) if len(p) else 0.0
    if len(p)<4 or span<=0:return _box_hull(p)
    eps=span*1e-9 if eps is None else eps
    t=_tetra(p,eps*10)
    if t is None:return _box_hull(p)
    a,b,c,d=t
    centroid=p[[a,b,c,d]].mean(axis=0)
    faces=[]
    def add(i,j,k):
        n=np.cross(p[j]-p[i],p[k]-p[i])
        if np.dot(n,centroid-p[i])>0:j,k=k,j
        faces.append((i,j,k))
    add(a,b,c);add(a,b,d);add(a,c,d);add(b,c,d)
    used={a,b,c,d}
    limit=max_vertices if max_vertices>=4 else 10**9
    while len(used)<limit:
        f=np.array(faces);v0=p[f[:,0]];n=np.cross(p[f[:,1]]-v0,p[f[:,2]]-v0)
        n/=np.linalg.norm(n,axis=1)[:,None];off=(n*v0).sum(axis=1)
        dist=p@n.T-off                                            # (N,F) signed distance to every face plane
        far=dist.max(axis=1);far[list(used)]=-1.0
        q=int(np.argmax(far))
        if far[q]<=eps*10:break
        visible=dist[q]>eps*10
        edges={}
        for index in np.nonzero(visible)[0]:
            i,j,k=faces[index]
            for e in ((i,j),(j,k),(k,i)):edges[e]=True
        horizon=[e for e in edges if (e[1],e[0]) not in edges]
        faces=[fc for fc,vis in zip(faces,visible) if not vis]
        for i,j in horizon:faces.append((i,j,q))
        used.add(q)
    f=np.array(faces);keep=sorted(set(f.ravel().tolist()));remap={old:new for new,old in enumerate(keep)}
    return p[keep].copy(),np.array([[remap[i] for i in tri] for tri in f.tolist()],dtype=np.int64)

def _box_hull(p):
    """Degenerate input (a point, a line, a flat card): hull of its bounding box padded to at least 1% of its span on every axis."""
    if len(p)==0:p=np.zeros((1,3))
    lo,hi=p.min(axis=0),p.max(axis=0);span=max(float(np.max(hi-lo)),1e-6)
    pad=np.maximum(0.01*span-(hi-lo),0.0)*0.5;lo=lo-pad;hi=hi+pad
    corners=np.array([[x,y,z] for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])])
    return quickhull(corners)

def hull_planes(verts,faces):
    """Outward unit normals (F,3) and offsets (F,) of a hull: inside means normal.x <= offset."""
    v0=verts[faces[:,0]];n=np.cross(verts[faces[:,1]]-v0,verts[faces[:,2]]-v0)
    n/=np.linalg.norm(n,axis=1)[:,None]
    return n,(n*v0).sum(axis=1)

def hull_volume(verts,faces):
    c=verts.mean(axis=0);v=verts-c
    return float(abs(np.einsum('ij,ij->i',v[faces[:,0]],np.cross(v[faces[:,1]],v[faces[:,2]])).sum())/6.0)

def hull_edges(faces):
    seen=set();out=[]
    for i,j,k in faces.tolist():
        for a,b in ((i,j),(j,k),(k,i)):
            key=(min(a,b),max(a,b))
            if key not in seen:seen.add(key);out.append(key)
    return np.array(out,dtype=np.int64)

# ---------------------------------------------------------------- separating axis test between two convex hulls
def sat_separation(va,fa,vb,fb,ea=None,eb=None):
    """Signed gap of two convex polyhedra in world space from the separating axis theorem: > 0 is a lower bound of the
    distance between them (exact for face contacts), < 0 is the exact penetration depth (minimum translation distance)."""
    na,_=hull_planes(va,fa);nb,_=hull_planes(vb,fb)
    ea=hull_edges(fa) if ea is None else ea;eb=hull_edges(fb) if eb is None else eb
    da=va[ea[:,1]]-va[ea[:,0]];db=vb[eb[:,1]]-vb[eb[:,0]]
    cross=np.cross(da[:,None,:],db[None,:,:]).reshape(-1,3)
    length=np.linalg.norm(cross,axis=1);cross=cross[length>1e-9]/length[length>1e-9][:,None]
    axes=np.vstack([na,nb,cross])
    pa=va@axes.T;pb=vb@axes.T
    gap=np.maximum(pb.min(axis=0)-pa.max(axis=0),pa.min(axis=0)-pb.max(axis=0))   # per axis, signed
    return float(gap.max())

def point_hull_depth(points,normals,offsets):
    """Penetration of points into a convex hull: depth (>0 means inside) = -max_f(n.x - d); 0 outside."""
    inside=(points@normals.T-offsets).max(axis=1)
    return np.maximum(-inside,0.0)

# ---------------------------------------------------------------- rotations
def quat_from_matrix(r):
    """Unit quaternion (x,y,z,w) of a row-vector rotation matrix r (v' = v @ r), the Houdini orient convention."""
    m=np.asarray(r,dtype=np.float64).T       # column-vector form
    t=m[0,0]+m[1,1]+m[2,2]
    if t>0:
        s=math.sqrt(t+1.0)*2;q=((m[2,1]-m[1,2])/s,(m[0,2]-m[2,0])/s,(m[1,0]-m[0,1])/s,0.25*s)
    elif m[0,0]>m[1,1] and m[0,0]>m[2,2]:
        s=math.sqrt(1.0+m[0,0]-m[1,1]-m[2,2])*2;q=(0.25*s,(m[0,1]+m[1,0])/s,(m[0,2]+m[2,0])/s,(m[2,1]-m[1,2])/s)
    elif m[1,1]>m[2,2]:
        s=math.sqrt(1.0+m[1,1]-m[0,0]-m[2,2])*2;q=((m[0,1]+m[1,0])/s,0.25*s,(m[1,2]+m[2,1])/s,(m[0,2]-m[2,0])/s)
    else:
        s=math.sqrt(1.0+m[2,2]-m[0,0]-m[1,1])*2;q=((m[0,2]+m[2,0])/s,(m[1,2]+m[2,1])/s,0.25*s,(m[1,0]-m[0,1])/s)
    q=np.array(q);return q/np.linalg.norm(q)

def matrix_from_quat(q):
    """Row-vector rotation matrix (v' = v @ r) of a unit quaternion (x,y,z,w)."""
    x,y,z,w=np.asarray(q,dtype=np.float64)/np.linalg.norm(q)
    m=np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
    return m.T

# ---------------------------------------------------------------- spawn stacking
def stack_spawn(centers,radii,order,drop,gap=1.05):
    """Raise sphere centres so that no two bounding spheres overlap at spawn: stones are processed in `order`, each one is lifted
    just clear of every earlier stone whose sphere it overlaps horizontally, and then `drop` is added on top. Returns the new
    (N,3) centres. A uniform grid on XZ keeps it near linear."""
    centers=np.asarray(centers,dtype=np.float64).copy();radii=np.asarray(radii,dtype=np.float64)
    n=len(centers)
    if n==0:return centers
    cell=max(2.0*float(radii.max())*gap,1e-9);grid={}
    placed=[]
    for i in order:
        cx,cz=centers[i,0],centers[i,2];gx,gz=int(math.floor(cx/cell)),int(math.floor(cz/cell))
        y=centers[i,1]
        for dx in (-1,0,1):
            for dz in (-1,0,1):
                for j in grid.get((gx+dx,gz+dz),()):
                    need=(radii[i]+radii[j])*gap;h2=(cx-centers[j,0])**2+(cz-centers[j,2])**2
                    if h2<need*need:y=max(y,centers[j,1]+math.sqrt(need*need-h2))
        centers[i,1]=y;grid.setdefault((gx,gz),[]).append(i)
    centers[:,1]+=drop
    return centers

def stable_hash(*arrays):
    h=hashlib.md5()
    for a in arrays:
        if isinstance(a,str):h.update(a.encode())
        else:h.update(np.ascontiguousarray(np.asarray(a,dtype=np.float64) if not isinstance(a,np.ndarray) else a).tobytes())
    return h.hexdigest()[:12]

def matrices_from_quats(q):
    """Row-vector rotation matrices (N,3,3) of unit quaternions (N,4) as x,y,z,w (vectorised matrix_from_quat)."""
    q=np.asarray(q,dtype=np.float64).reshape(-1,4);q=q/np.linalg.norm(q,axis=1)[:,None]
    x,y,z,w=q[:,0],q[:,1],q[:,2],q[:,3];m=np.empty((len(q),3,3))
    m[:,0,0]=1-2*(y*y+z*z);m[:,0,1]=2*(x*y-z*w);m[:,0,2]=2*(x*z+y*w)
    m[:,1,0]=2*(x*y+z*w);m[:,1,1]=1-2*(x*x+z*z);m[:,1,2]=2*(y*z-x*w)
    m[:,2,0]=2*(x*z-y*w);m[:,2,1]=2*(y*z+x*w);m[:,2,2]=1-2*(x*x+y*y)
    return np.transpose(m,(0,2,1))

def unit_hash(ids,seed):
    """Deterministic number in [0,1) per integer id and seed (splitmix64 finaliser): stable when other points are added."""
    with np.errstate(over='ignore'):                                  # 64-bit wrap-around is the point of the mixer
        z=(np.asarray(ids,dtype=np.uint64)+np.uint64(seed)*np.uint64(0x9E3779B97F4A7C15)+np.uint64(0x9E3779B97F4A7C15))
        z=(z^(z>>np.uint64(30)))*np.uint64(0xBF58476D1CE4E5B9);z=(z^(z>>np.uint64(27)))*np.uint64(0x94D049BB133111EB);z=z^(z>>np.uint64(31))
    return (z>>np.uint64(11)).astype(np.float64)/float(1<<53)

def extreme_points(points,directions=256,block=20000):
    """Cheap hull prefilter for very dense meshes: the points that are extreme along a spread of directions."""
    points=np.asarray(points,dtype=np.float64)
    if len(points)<=2000:return points
    k=np.arange(directions)+0.5;phi=np.arccos(1-2*k/directions);theta=np.pi*(1+5**0.5)*k
    d=np.c_[np.cos(theta)*np.sin(phi),np.sin(theta)*np.sin(phi),np.cos(phi)]
    best=np.full(directions,-np.inf);arg=np.zeros(directions,dtype=np.int64);bestn=np.full(directions,np.inf);argn=np.zeros(directions,dtype=np.int64)
    for s in range(0,len(points),block):
        proj=points[s:s+block]@d.T
        hi=proj.max(axis=0);better=hi>best;best[better]=hi[better];arg[better]=proj.argmax(axis=0)[better]+s
        lo=proj.min(axis=0);worse=lo<bestn;bestn[worse]=lo[worse];argn[worse]=proj.argmin(axis=0)[worse]+s
    return points[np.unique(np.r_[arg,argn])]

# ---------------------------------------------------------------- Houdini side
import contextlib, fnmatch, time
import hou
from pxr import Gf, Usd, UsdGeom

QUALITY=({'name':'Draft','hull':24,'margin':0.04,'substeps':4,'iters':4,'step':0.6},
         {'name':'Standard','hull':96,'margin':0.015,'substeps':12,'iters':10,'step':0.3},
         {'name':'High','hull':256,'margin':0.006,'substeps':24,'iters':20,'step':0.2})
# hull: proxy vertex cap; margin: collision padding as a fraction of the thinnest stone; substeps: minimum per frame; step: the largest
# distance a stone may travel in one substep as a fraction of its thinnest size (this sets the substeps while the stones are fast).
# Rest test (same for every quality): over half a second a stone may move at most REST_DRIFT x the median stone size and turn at most
# REST_TURN radians, and at most REST_QUIET of the stones may still exceed that (a few stones always keep rocking on others).
REST_DRIFT=0.08;REST_TURN=0.15;REST_QUIET=0.02;REST_CHECKS=3   # the test must pass on REST_CHECKS consecutive checkpoints (6 frames apart) before the bake stops
CACHE_VERSION='arraytron-physics-8'
_HULLS={}

def lathe(profile,axis,segments=24):
    """Quad mesh from a (radius, height) profile turned about an axis ('X','Y' or 'Z'): points (n,3), counts, indices."""
    ring=np.linspace(0.0,2.0*math.pi,segments,endpoint=False);pts=[];index=[]
    for r,h in profile:
        for a in ring:pts.append((r*math.cos(a),h,r*math.sin(a)))
    pts=np.array(pts,dtype=np.float64)
    for k in range(len(profile)-1):
        for j in range(segments):
            a=k*segments+j;b=k*segments+(j+1)%segments;index+=[a,a+segments,b+segments,b]
    axis=axis if axis in ('X','Y','Z') else 'Y';perm={'Y':(0,1,2),'X':(1,0,2),'Z':(0,2,1)}[axis]
    quads=np.array(index,dtype=np.int64).reshape(-1,4)
    if axis!='Y':quads=quads[:,::-1]                                    # swapping two coordinates mirrors the shape: reverse the winding to keep the normals outward
    return pts[:,perm],np.full(len(quads),4,dtype=np.int64),quads.ravel()

def shape_mesh(prim):
    """(points, face counts, face indices) in the prim's own space for a Mesh or an implicit gprim (Cube, Sphere, Cylinder, Cone,
    Capsule), else None. Implicit shapes are tessellated at 24 segments."""
    if prim.IsA(UsdGeom.Mesh):
        mesh=UsdGeom.Mesh(prim);points=mesh.GetPointsAttr().Get()
        if not points:return None
        return np.array(points,dtype=np.float64).reshape(-1,3),np.array(mesh.GetFaceVertexCountsAttr().Get(),dtype=np.int64),np.array(mesh.GetFaceVertexIndicesAttr().Get(),dtype=np.int64)
    if prim.IsA(UsdGeom.Cube):
        h=0.5*float(UsdGeom.Cube(prim).GetSizeAttr().Get() or 2.0)
        pts=np.array([(x,y,z) for x in (-h,h) for y in (-h,h) for z in (-h,h)],dtype=np.float64)
        quads=[(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)]
        return pts,np.full(6,4,dtype=np.int64),np.array(quads,dtype=np.int64).ravel()
    if prim.IsA(UsdGeom.Sphere):
        r=float(UsdGeom.Sphere(prim).GetRadiusAttr().Get() or 1.0)
        return lathe([(r*math.sin(t),-r*math.cos(t)) for t in np.linspace(0.0,math.pi,13)],'Y')
    if prim.IsA(UsdGeom.Cylinder):
        c=UsdGeom.Cylinder(prim);r=float(c.GetRadiusAttr().Get());h=0.5*float(c.GetHeightAttr().Get())
        return lathe([(0.0,-h),(r,-h),(r,h),(0.0,h)],str(c.GetAxisAttr().Get()))
    if prim.IsA(UsdGeom.Cone):
        c=UsdGeom.Cone(prim);r=float(c.GetRadiusAttr().Get());h=0.5*float(c.GetHeightAttr().Get())
        return lathe([(0.0,-h),(r,-h),(0.0,h)],str(c.GetAxisAttr().Get()))
    if prim.IsA(UsdGeom.Capsule):
        c=UsdGeom.Capsule(prim);r=float(c.GetRadiusAttr().Get());h=0.5*float(c.GetHeightAttr().Get())
        quarter=np.linspace(0.0,0.5*math.pi,7)
        profile=[(r*math.sin(t),-h-r*math.cos(t)) for t in quarter]+[(r*math.cos(t),h+r*math.sin(t)) for t in quarter]
        return lathe(profile,str(c.GetAxisAttr().Get()))
    return None

def proto_points(stage,path):
    """Vertices of every mesh under a prototype prim, in the prototype's own frame (its own transform kept, its parents' dropped):
    exactly the space the PointInstancer places instances in."""
    root=stage.GetPrimAtPath(path)
    if not root or not root.IsValid():raise hou.NodeError('Physics Settle: prototype prim %s does not exist.'%path)
    xc=UsdGeom.XformCache(Usd.TimeCode.Default());parent=root.GetParent()
    inverse=xc.GetLocalToWorldTransform(parent).GetInverse() if parent and not parent.IsPseudoRoot() else Gf.Matrix4d(1.0)
    chunks=[]
    for prim in Usd.PrimRange(root):
        if not prim.IsA(UsdGeom.Gprim) or UsdGeom.Imageable(prim).GetPurposeAttr().Get() in ('guide','proxy'):continue
        shape=shape_mesh(prim)
        if shape is None:continue
        m=np.array(xc.GetLocalToWorldTransform(prim)*inverse,dtype=np.float64).reshape(4,4)
        chunks.append(shape[0]@m[:3,:3]+m[3,:3])
    if not chunks:raise hou.NodeError('Physics Settle: %s contains no mesh or basic shape (cube, sphere, cylinder, cone, capsule) to build a collision proxy from.'%path)
    return np.vstack(chunks)

def proto_proxies(asset):
    """One convex proxy per enabled bank entry, in protoindex order: dict(row, path, verts, faces, center, radius, extent)."""
    stage=asset.node('SOURCE_RESOLVER').stage()
    if stage is None:raise hou.NodeError('Physics Settle: the Source Resolver has no stage.')
    cap=QUALITY[asset.evalParm('phys_quality')]['hull'];out=[]
    for e in resolve(asset):
        points=proto_points(stage,e['path']);key=(stable_hash(points),cap)
        hull=_HULLS.get(key)
        if hull is None:
            verts,faces=quickhull(extreme_points(points),cap)
            center=0.5*(verts.min(axis=0)+verts.max(axis=0))
            hull=dict(verts=verts,faces=faces,center=center,radius=float(np.linalg.norm(verts-center,axis=1).max()),extent=verts.max(axis=0)-verts.min(axis=0))
            if len(_HULLS)>64:_HULLS.clear()
            _HULLS[key]=hull
        out.append(dict(row=e['row'],path=e['path'],**hull))
    return out

def read_points(geo):
    """The Arraytron point attributes as numpy arrays (None for an empty geometry)."""
    n=geo.intrinsicValue('pointcount')
    if n==0:return None
    return dict(P=np.array(geo.pointFloatAttribValues('P')).reshape(-1,3),orient=np.array(geo.pointFloatAttribValues('orient')).reshape(-1,4),
                scale=np.array(geo.pointFloatAttribValues('scale')).reshape(-1,3),id=np.array(geo.pointIntAttribValues('id')),
                protoindex=np.array(geo.pointIntAttribValues('protoindex')))

def stone_spheres(s,protos):
    """Bounding sphere centre (N,3) and radius (N,) of every stone in world space."""
    cen=np.array([p['center'] for p in protos])[s['protoindex']]*s['scale']
    rad=np.array([p['radius'] for p in protos])[s['protoindex']]*s['scale'].max(axis=1)
    return s['P']+np.einsum('ni,nij->nj',cen,matrices_from_quats(s['orient'])),rad

def sop_spawn(geo,asset):
    """PHYSICS_SPAWN: lift the points to the drop height and, if asked, stack them so no two stones overlap at spawn."""
    s=read_points(geo)
    if s is None:return
    drop=asset.evalParm('phys_drop')
    if asset.evalParm('phys_stack'):
        centers,radii=stone_spheres(s,proto_proxies(asset));offset=centers-s['P']
        lifted=centers.copy();lifted[:,1]=s['P'][:,1]+radii      # each bounding sphere sits on the distribution plane (the point's own height)
        order=np.argsort(unit_hash(s['id'],asset.evalParm('phys_seed')),kind='stable')
        P=stack_spawn(lifted,radii,order,drop)-offset
    else:
        P=s['P'].copy();P[:,1]+=drop
    geo.setPointFloatAttribValues('P',P.ravel().tolist())
    geo.addAttrib(hou.attribType.Global,'phys_ylo',0.0);geo.addAttrib(hou.attribType.Global,'phys_yhi',0.0)
    geo.setGlobalAttribValue('phys_ylo',float(P[:,1].min()));geo.setGlobalAttribValue('phys_yhi',float(P[:,1].max()))

def sim_plan(asset,s,protos):
    """Solver settings derived from the stones and the Collision Quality preset."""
    q=QUALITY[asset.evalParm('phys_quality')]
    extent=np.array([p['extent'] for p in protos])[s['protoindex']]*s['scale']
    dmin=float(extent.min());dmed=float(np.median(extent.mean(axis=1)))
    centers,radii=stone_spheres(s,protos)
    ground=asset.evalParm('phys_ground_height') if asset.evalParm('phys_ground') else float((centers[:,1]-radii).min())
    fall=max(0.05,float((centers[:,1]+radii).max())-ground)
    g=max(asset.evalParm('phys_gravity'),0.01);fps=hou.fps()
    drag=max(asset.evalParm('phys_drag'),0.0)
    vmax=math.sqrt(2.0*g*fall)
    if drag>0:vmax=min(vmax,math.sqrt(g/drag))                                 # terminal speed of the Air Drag
    def steps(speed):return int(min(64,max(q['substeps'],math.ceil(speed/(fps*q['step']*dmin)))))     # a stone must not travel more than q['step'] of its thinnest size per substep
    substeps=steps(vmax);late=steps(min(vmax,1.5))                              # fast while the stones fall, cheaper once the pile is only shuffling
    fall_frames=int(math.ceil(1.5*max(vmax/g,fall/max(vmax,1e-6))*fps))+12      # time to fall (accelerating, or at terminal speed) plus slack
    return dict(margin=q['margin']*dmin,substeps=substeps,substeps_late=late,fall_frames=fall_frames,iters=q['iters'],dmin=dmin,dmed=dmed,vtol=0.05*dmed,wtol=0.1,dtol=REST_DRIFT*dmed,atol=REST_TURN,allowed=int(REST_QUIET*len(s['id'])),
                frames=max(2,int(math.ceil(asset.evalParm('phys_duration')*fps))),count=len(s['id']),vmax=vmax)

def sop_proxies(geo,asset):
    """PHYSICS_PROXIES: replace the points by one packed convex proxy per stone (the prototype hull with the stone's scale baked in,
    placed at the stone's position and orientation) and record the solver plan as detail attributes."""
    s=read_points(geo)
    if s is None:return
    protos=proto_proxies(asset);plan=sim_plan(asset,s,protos)
    mats=matrices_from_quats(s['orient'])
    geo.clear()
    geo.addAttrib(hou.attribType.Prim,'name','')
    for key,value in plan.items():
        value=float(value) if isinstance(value,float) else int(value)
        geo.addAttrib(hou.attribType.Global,'plan_'+key,value);geo.setGlobalAttribValue('plan_'+key,value)
    for i in range(len(s['id'])):
        p=protos[int(s['protoindex'][i])];hull=hou.Geometry()
        pts=hull.createPoints([tuple(v) for v in (p['verts']*s['scale'][i]).tolist()])
        hull.createPolygons([(pts[a],pts[b],pts[c]) for a,b,c in p['faces'].tolist()])
        prim=geo.createPackedGeometry(hull);r=mats[i];t=s['P'][i]
        prim.setTransform(hou.Matrix4(((r[0,0],r[0,1],r[0,2],0),(r[1,0],r[1,1],r[1,2],0),(r[2,0],r[2,1],r[2,2],0),(t[0],t[1],t[2],1))))     # the translation lands in the point position
        prim.setAttribValue('name','stone%d'%int(s['id'][i]))

def collider_meshes(asset):
    """[(world points (n,3), face vertex counts, face vertex indices)] of every mesh matched by the Collider Prims patterns."""
    patterns=asset.evalParm('phys_colliders').split()
    if not patterns:return []
    stage=asset.node('SOURCE_RESOLVER').stage()
    if stage is None:return []
    own=asset.evalParm('outputpath').rstrip('/');xc=UsdGeom.XformCache(Usd.TimeCode.Default());seen=set();out=[]
    for prim in stage.Traverse():
        path=prim.GetPath().pathString
        if path==own or path.startswith(own+'/') or not any(fnmatch.fnmatchcase(path,pat) for pat in patterns):continue
        for sub in Usd.PrimRange(prim):
            sp=sub.GetPath().pathString
            if sp in seen or not sub.IsA(UsdGeom.Gprim):continue
            seen.add(sp)
            if UsdGeom.Imageable(sub).GetPurposeAttr().Get() in ('guide','proxy'):continue
            shape=shape_mesh(sub)
            if shape is None:continue
            m=np.array(xc.GetLocalToWorldTransform(sub),dtype=np.float64).reshape(4,4)
            out.append((shape[0]@m[:3,:3]+m[3,:3],shape[1],shape[2]))
    return out

def triangulate(counts,indices):
    """Fan triangulation of polygon faces (vectorised): (T,3) vertex index triples."""
    starts=np.concatenate(([0],np.cumsum(counts)[:-1]));tris=[]
    for k in range(int(counts.max())-2 if len(counts) else 0):
        sel=counts>k+2
        tris.append(np.stack([indices[starts[sel]],indices[starts[sel]+k+1],indices[starts[sel]+k+2]],axis=1))
    return np.vstack(tris) if tris else np.zeros((0,3),dtype=np.int64)

def sop_colliders(geo,asset):
    """PHYSICS_COLLIDERS: the Collider Prims meshes as static triangle geometry in world space."""
    for points,counts,indices in collider_meshes(asset):
        tris=triangulate(counts,indices)
        if not len(tris):continue
        pts=geo.createPoints([tuple(v) for v in points.tolist()])
        geo.createPolygons([(pts[a],pts[b],pts[c]) for a,b,c in tris.tolist()])

def state_key(asset,s,protos,plan):
    """Identity of a simulation: the spawn state, the proxies, the colliders and every solver setting. Any change gives a new
    cache file name, so a stale cache can never be applied by mistake."""
    colliders=[a for m in collider_meshes(asset) for a in (np.round(m[0],6),m[1],m[2])]
    settings=repr([asset.evalParm(n) for n in ('phys_gravity','phys_density','phys_friction','phys_bounce','phys_drag','phys_duration','phys_quality','phys_ground','phys_ground_height')]+[round(plan['margin'],9),plan['substeps'],plan['substeps_late'],plan['fall_frames'],plan['iters'],round(plan['dtol'],9),plan['atol']])
    return stable_hash(CACHE_VERSION,settings,np.round(s['P'],6),np.round(s['orient'],6),np.round(s['scale'],6),s['id'],s['protoindex'],*[np.round(p['verts'],6) for p in protos],*colliders)

def cache_dir(asset):
    return asset.evalParm('phys_cachedir').replace('\\','/').rstrip('/')

def cache_file(asset,key):
    return '%s/%s_%s.bgeo.sc'%(cache_dir(asset),clean(asset.name()),key)

def sop_apply(geo,asset):
    """PHYSICS_APPLY: replace position and orientation by the cached settled result when it exists for exactly this state."""
    asset.evalParm('phys_cache_rev')                              # dependency: a bake or Clear Cache dirties this node
    s=read_points(geo)
    for name,default in (('phys_state',''),('phys_message',''),('phys_key',''),('phys_frames',0),('phys_settled',0),('phys_count',0),('phys_maxspeed',0.0),('phys_maxspin',0.0),('phys_active',0)):
        geo.addAttrib(hou.attribType.Global,name,default)
    if s is None:
        geo.setGlobalAttribValue('phys_state','empty');return
    protos=proto_proxies(asset);plan=sim_plan(asset,s,protos);key=state_key(asset,s,protos,plan);path=cache_file(asset,key)
    geo.setGlobalAttribValue('phys_key',key);geo.setGlobalAttribValue('phys_count',len(s['id']))
    state='settled'
    if not os.path.isfile(path):
        path=latest_cache(asset,len(s['id']))                       # settings changed since the last bake: show that bake, marked stale
        state='stale' if path else 'missing'
    if state=='missing' or load_cache(geo,s,path) is None:
        state='missing'
    if state in ('missing','stale'):
        folder=cache_dir(asset)
        message=('The settings changed since the last simulation: showing that old result. Press Simulate & Cache.' if state=='stale'
                 else 'Not simulated for the current settings: showing the spawn state. Press Simulate & Cache (cache folder %s).'%folder)
        if asset.evalParm('phys_strict'):raise hou.NodeError('Physics Settle: no simulation for the current settings in %s (Error If Not Simulated is on). Press Simulate & Cache.'%folder)
        hou.pwd().addWarning('Physics Settle: '+message)
    else:
        message='Settled result from the cache (%d frames).'%geo.attribValue('phys_frames')
    geo.setGlobalAttribValue('phys_state',state);geo.setGlobalAttribValue('phys_message',message)

def latest_cache(asset,count):
    """Newest cache file of this node with the right number of stones (for the stale display), or None."""
    folder=cache_dir(asset);prefix=clean(asset.name())+'_'
    if not os.path.isdir(folder):return None
    files=[os.path.join(folder,n) for n in os.listdir(folder) if n.startswith(prefix) and n.endswith('.bgeo.sc')]
    for path in sorted(files,key=os.path.getmtime,reverse=True):
        g=hou.Geometry();g.loadFromFile(path)
        if g.intrinsicValue('pointcount')==count:return path
    return None

def load_cache(geo,s,path):
    """Replace P and orient of geo (the points of s) by the cached ones matched by id and copy the statistics; None if the ids do not match."""
    cache=hou.Geometry();cache.loadFromFile(path)
    cid=np.array(cache.pointIntAttribValues('id'));order={int(v):k for k,v in enumerate(cid.tolist())}
    if len(cid)!=len(s['id']) or any(int(i) not in order for i in s['id'].tolist()):return None
    pick=np.array([order[int(i)] for i in s['id'].tolist()])
    P=np.array(cache.pointFloatAttribValues('P')).reshape(-1,3)[pick];Q=np.array(cache.pointFloatAttribValues('orient')).reshape(-1,4)[pick]
    geo.setPointFloatAttribValues('P',P.ravel().tolist());geo.setPointFloatAttribValues('orient',Q.ravel().tolist())
    for name in ('phys_frames','phys_settled','phys_maxspeed','phys_maxspin','phys_active'):geo.setGlobalAttribValue(name,cache.attribValue(name))
    return True

def physics_status(asset):
    """Read-only text for the Physics folder."""
    if not asset.evalParm('phys_on'):return 'Physics Settle is off.'
    try:
        g=asset.node('USD_COMPILER').node('PHYSICS_APPLY').geometry()
        state=g.attribValue('phys_state')
    except Exception as exc:return 'Cannot read the physics state: %s'%exc
    if state in ('settled','stale'):
        rest='came to rest' if g.attribValue('phys_settled') else 'NOT at rest: %d stone(s) were still moving (raise Maximum Sim Time or Collision Quality)'%g.attribValue('phys_active')
        head='%d stones settled from cache.'%g.attribValue('phys_count') if state=='settled' else 'STALE: the settings changed since this simulation. Press Simulate & Cache.'
        return '%s Simulated %d frames; %s. Largest movement in the last half second: %.2g m and %.2g rad.'%(head,g.attribValue('phys_frames'),rest,g.attribValue('phys_maxspeed'),g.attribValue('phys_maxspin'))
    return g.attribValue('phys_message') or state

def bake(asset):
    """Simulate & Cache: run the Bullet solver on the proxies frame by frame, stop when everything is at rest, freeze the last frame."""
    if not asset.evalParm('phys_on'):raise hou.Error('Turn Physics Settle on first.')
    inst=asset.node('USD_COMPILER')
    spawn=inst.node('PHYSICS_SPAWN').geometry()
    if spawn is None:                                                    # an upstream stage failed to cook: say why
        text=' | '.join(' '.join(n.errors()) for n in [asset.node('SOURCE_RESOLVER'),inst]+list(inst.children()) if n.errors())
        raise hou.Error('Cannot simulate: '+(text or 'the distribution did not cook.'))
    s=read_points(spawn)
    if s is None:raise hou.Error('There are no points to simulate.')
    protos=proto_proxies(asset);plan=sim_plan(asset,s,protos);key=state_key(asset,s,protos,plan)
    solver=inst.node('PHYSICS_SOLVER');solver.parm('resetsim').pressButton()
    start=int(solver.evalParm('startframe'));window=max(6,int(round(0.5*hou.fps())));frames=0;speed=drift=turn=0.0;active=0;settled=False;calm=0
    history={};stats=[];t0=time.time()
    progress=hou.InterruptableOperation('Arraytron: settling %d stones'%plan['count'],open_interrupt_dialog=True) if hou.isUIAvailable() else contextlib.nullcontext()
    with progress as op:                                          # the dialog has a Cancel button: hou.OperationInterrupted leaves no cache behind
        for step in range(1,plan['frames']+1):
            if op:op.updateProgress(step/float(plan['frames']))
            g=solver.geometryAtFrame(start+step);frames=step
            v=np.array(g.pointFloatAttribValues('v')).reshape(-1,3)
            speed=float(np.linalg.norm(v,axis=1).max()) if len(v) else 0.0
            if step%6==0:                                            # rest test: net movement over the last half second, not instantaneous jitter
                P=np.array(g.pointFloatAttribValues('P')).reshape(-1,3);R=np.array([pr.intrinsicValue('transform') for pr in g.prims()]).reshape(-1,3,3)
                R=R/np.linalg.norm(R,axis=2,keepdims=True)
                history[step]=(P,R)
                before=history.get(step-(window//6)*6)
                if before is not None and step>=window:
                    moves=np.linalg.norm(P-before[0],axis=1)
                    cos=np.clip((np.einsum('nij,nij->n',R,before[1])-1.0)*0.5,-1.0,1.0);turns=np.arccos(cos)
                    drift=float(moves.max());turn=float(turns.max())
                    active=int(((moves>plan['dtol'])|(turns>plan['atol'])).sum())                  # stones still moving more than the rest tolerance
                    stats.append((step,speed,drift,turn,active))
                    calm=calm+1 if active<=int(plan['allowed']) else 0
                    if calm>=REST_CHECKS:settled=True;break
    prims=g.prims()
    if len(prims)!=len(s['id']):raise hou.Error('The solver returned %d bodies for %d stones.'%(len(prims),len(s['id'])))
    P=np.zeros((len(prims),3));Q=np.zeros((len(prims),4))
    for k,pr in enumerate(prims):
        m=np.array(pr.fullTransform().asTuple(),dtype=np.float64).reshape(4,4)
        u,_,vt=np.linalg.svd(m[:3,:3]);r=u@vt
        P[k]=m[3,:3];Q[k]=quat_from_matrix(r)
    out=hou.Geometry();out.createPoints([tuple(p) for p in P.tolist()])
    out.addAttrib(hou.attribType.Point,'id',0);out.addAttrib(hou.attribType.Point,'orient',(0.0,0.0,0.0,1.0))
    out.setPointIntAttribValues('id',[int(i) for i in s['id'].tolist()]);out.setPointFloatAttribValues('orient',Q.ravel().tolist())
    for name,value in (('phys_frames',frames),('phys_settled',1 if settled else 0),('phys_maxspeed',drift),('phys_maxspin',turn),('phys_active',active),('phys_seconds',time.time()-t0)):
        out.addAttrib(hou.attribType.Global,name,value);out.setGlobalAttribValue(name,value)
    path=cache_file(asset,key);os.makedirs(os.path.dirname(path),exist_ok=True)
    out.saveToFile(path)
    asset.parm('phys_cache_rev').set(asset.evalParm('phys_cache_rev')+1)
    return dict(path=path,key=key,frames=frames,settled=settled,speed=speed,drift=drift,turn=turn,active=active,seconds=time.time()-t0,count=plan['count'],plan=plan,stats=stats)

def clear_cache(asset):
    folder=cache_dir(asset);prefix=clean(asset.name())+'_';removed=0
    if os.path.isdir(folder):
        for name in os.listdir(folder):
            if name.startswith(prefix) and name.endswith('.bgeo.sc'):os.remove(os.path.join(folder,name));removed+=1
    asset.parm('phys_cache_rev').set(asset.evalParm('phys_cache_rev')+1)
    return removed

def spawn_text(asset):
    """Read-only line for the Physics folder: where the stones come from (the Distribution settings are the spawn region and the count)."""
    mode=asset.evalParm('mode')
    try:
        if mode==0:
            count=asset.evalParm('line_count_out') if asset.evalParm('line_spacemode')==1 else asset.evalParm('line_count');where='Line, length %g'%asset.evalParm('line_length')
        elif mode==1:count=asset.evalParm('area_count');where='Area %g x %g'%(asset.evalParm('area_sizex'),asset.evalParm('area_sizez'))
        elif mode==2:count=asset.evalParm('grid_total');where='Grid / Matrix'
        else:count=asset.evalParm('circle_count');where='Circle, radius %g'%asset.evalParm('circle_radius')
    except hou.Error:return 'See the Distribution folder.'
    text='%d stones spawn from the %s distribution. Change the region and the count in Distribution; Drop Height lifts the whole spawn above its plane.'%(count,where)
    if asset.evalParm('phys_on'):
        try:
            g=asset.node('USD_COMPILER/PHYSICS_SPAWN').geometry();text+=' Spawn heights (stone origins): y = %.3g to %.3g.'%(g.attribValue('phys_ylo'),g.attribValue('phys_yhi'))
        except Exception:pass
    if count>2000:text+=' More than 2000 stones: simulating can take many minutes.'
    return text
