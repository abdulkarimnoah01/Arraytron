# Built-in LOD generator (v1.8.0). Appended to the PythonModule; the Python LOP LOD_GENERATOR (src/lod_generate.py) calls lodgen_author(). For every enabled Prototype Bank row
# and every level (LOD 1, LOD 2, Proxy) that has no LOD prim of its own, a reduced copy of the hero prim is written next to the other prims of the stream and used as that level.
# The reduction is vertex clustering with a quadric-error position per cluster (a uniform grid whose cell size is searched until the triangle count meets the target), plain numpy:
# the same result in Houdini 22 and 20.5 / 21, deterministic, no Houdini nodes. Primvars (uv, colour ...) are carried over; the hero is never touched.
import hashlib
import numpy as np

LODGEN_PARMS=(('lodg_1','proto_lod1',1),('lodg_2','proto_lod2',2),('lodg_3','proto_proxy',3))
_LODGEN_CACHE={}
_LODGEN_STATS={}

def lodgen_root(asset):
    return asset.evalParm('outputpath').rstrip('/')+'_LOD'

def lodgen_path(asset,row,level):
    """Prim path of the generated LOD of a bank row: <output>_LOD/Proto01_LOD1 (level 3 is the proxy)."""
    return '%s/Proto%02d_%s'%(lodgen_root(asset),row,'PROXY' if level==3 else 'LOD%d'%level)

# ---------------------------------------------------------------- the reduction (numpy only)
def lodgen_triangulate(counts,indices):
    """Fan triangulation. Returns (vertex ids (T,3), corner indices (T,3) into the face-varying arrays, source face (T,))."""
    counts=np.asarray(counts,dtype=np.int64);indices=np.asarray(indices,dtype=np.int64)
    per=np.maximum(counts-2,0);starts=np.concatenate([[0],np.cumsum(counts)[:-1]]) if len(counts) else np.zeros(0,dtype=np.int64)
    face=np.repeat(np.arange(len(counts)),per);first=np.cumsum(per)-per;j=np.arange(len(face))-first[face];s=starts[face]
    corner=np.stack([s,s+j+1,s+j+2],axis=1) if len(face) else np.zeros((0,3),dtype=np.int64)
    return indices[corner],corner,face

def _cluster_key(P,low,size):
    q=np.floor((P-low)/size).astype(np.int64);dims=q.max(axis=0)+1
    return (q[:,0]*dims[1]+q[:,1])*dims[2]+q[:,2]

def _kept(tri,key):
    """Indices of the triangles that survive the clustering: not collapsed, and the first of every set of identical ones."""
    c=key[tri];ok=(c[:,0]!=c[:,1])&(c[:,1]!=c[:,2])&(c[:,0]!=c[:,2]);where=np.nonzero(ok)[0]
    if len(where)==0:return where
    _,first=np.unique(np.sort(c[where],axis=1),axis=0,return_index=True)
    return where[np.sort(first)]

def lodgen_reduce(P,counts,indices,ratio,min_tris=12):
    """Reduce a polygon mesh to about ratio (0..1) of its triangles, never fewer than min_tris. P (N,3) points. Returns None when nothing has to be reduced, else a dict:
    points (M,3), tri (K,3) new vertex ids, src_tri (K,) the original triangle each one came from, src_corner (K,3) the original face-varying corner of each new corner,
    src_face (K,), vertex_src (M,) an original vertex of every new vertex, triangles (original count)."""
    P=np.asarray(P,dtype=np.float64).reshape(-1,3);tri,corner,face=lodgen_triangulate(counts,indices);T=len(tri)
    target=int(max(min_tris,np.ceil(ratio*T)))
    if T==0 or target>=T:return None
    low=P.min(axis=0);diag=float(np.linalg.norm(P.max(axis=0)-low))
    if diag<=0:return None
    # search the cell size: the largest triangle count that is not above the target
    lo,hi=diag*1e-4,diag;best=None
    for _ in range(22):
        size=float(np.sqrt(lo*hi));keep=_kept(tri,_cluster_key(P,low,size))
        if len(keep)>target:lo=size
        else:
            hi=size
            if best is None or len(keep)>len(best[1]):best=(size,keep)
    if best is None:
        keep=_kept(tri,_cluster_key(P,low,diag*2.0));best=(diag*2.0,keep)
    size,keep=best;key=_cluster_key(P,low,size)
    used,inverse=np.unique(key,return_inverse=True)                                             # a compact number for every occupied cell
    cluster=inverse                                                                              # cluster of every original vertex
    # quadric error position of every cluster: sum of the plane quadrics (area weighted) of the triangles touching its vertices
    A,B,C=P[tri[:,0]],P[tri[:,1]],P[tri[:,2]];n=np.cross(B-A,C-A);area2=np.linalg.norm(n,axis=1);good=area2>1e-20
    nn=np.zeros_like(n);nn[good]=n[good]/area2[good,None];d=-np.einsum('ij,ij->i',nn,A);w=np.where(good,area2*0.5,0.0)
    m=len(used);Q=np.zeros((m,3,3));b=np.zeros((m,3));W=np.zeros(m);cen=np.zeros((m,3));cnt=np.zeros(m)
    outer=w[:,None,None]*nn[:,:,None]*nn[:,None,:];rhs=-(w*d)[:,None]*nn
    for k in range(3):
        c=cluster[tri[:,k]];np.add.at(Q,c,outer);np.add.at(b,c,rhs);np.add.at(W,c,w)
    np.add.at(cen,cluster,P);np.add.at(cnt,cluster,1.0);cen/=np.maximum(cnt,1.0)[:,None]
    lam=0.05*np.maximum(W,1e-30);Q=Q+lam[:,None,None]*np.eye(3)[None];b=b+lam[:,None]*cen
    X=np.linalg.solve(Q,b[:,:,None])[:,:,0];X=np.clip(X,cen-0.75*size,cen+0.75*size)         # stay near the cell
    ct=cluster[tri[keep]];present=np.unique(ct);remap=-np.ones(m,dtype=np.int64);remap[present]=np.arange(len(present))
    first_vertex=np.full(m,-1,dtype=np.int64);order=np.arange(len(P))[::-1];first_vertex[cluster[order]]=order                  # the lowest original vertex of every cluster
    return dict(points=X[present],tri=remap[ct],src_tri=keep,src_corner=corner[keep],src_face=face[keep],vertex_src=first_vertex[present],triangles=T)

def lodgen_normals(points,tri):
    """Area weighted smooth vertex normals of a triangle mesh."""
    n=np.cross(points[tri[:,1]]-points[tri[:,0]],points[tri[:,2]]-points[tri[:,0]]);out=np.zeros_like(points)
    for k in range(3):np.add.at(out,tri[:,k],n)
    length=np.linalg.norm(out,axis=1);out[length>0]/=length[length>0,None];return out

def lodgen_transfer(values,interpolation,res):
    """Carry a primvar over to the reduced mesh, keeping its interpolation."""
    v=np.asarray(values)
    if interpolation=='constant':return v
    if interpolation=='uniform':return v[res['src_face']]
    if interpolation=='faceVarying':return v[res['src_corner'].reshape(-1)]
    return v[res['vertex_src']]                                                                  # vertex / varying

def lodgen_cached(P,counts,indices,ratio,min_tris):
    key=(hashlib.blake2b(np.ascontiguousarray(P,dtype=np.float64).tobytes()+np.ascontiguousarray(counts,dtype=np.int64).tobytes()+np.ascontiguousarray(indices,dtype=np.int64).tobytes(),digest_size=16).hexdigest(),round(float(ratio),6),int(min_tris))
    if key not in _LODGEN_CACHE:
        if len(_LODGEN_CACHE)>64:_LODGEN_CACHE.clear()
        _LODGEN_CACHE[key]=lodgen_reduce(P,counts,indices,ratio,min_tris)
    return _LODGEN_CACHE[key]

# ---------------------------------------------------------------- writing the prims
_SKIP_ON_MESH={'points','faceVertexCounts','faceVertexIndices','normals','extent','subdivisionScheme','holeIndices','cornerIndices','cornerSharpnesses','creaseIndices','creaseLengths','creaseSharpnesses','creaseIndices'}

def lodgen_copy_prim(src,dst,skip=()):
    """Copy the authored attributes, relationships, applied schemas and kind of a prim onto another prim."""
    for attr in src.GetAuthoredAttributes():
        name=attr.GetName()
        if name in skip or (name.startswith('primvars:') and 'Mesh' in skip):continue
        new=dst.CreateAttribute(name,attr.GetTypeName(),attr.IsCustom())
        for key in ('interpolation',):
            if attr.HasMetadata(key):new.SetMetadata(key,attr.GetMetadata(key))
        times=attr.GetTimeSamples()
        if times:
            for t in times:new.Set(attr.Get(t),t)
        elif attr.HasValue():new.Set(attr.Get())
    for rel in src.GetAuthoredRelationships():
        new=dst.CreateRelationship(rel.GetName(),rel.IsCustom());new.SetTargets(rel.GetTargets())
    for schema in src.GetAppliedSchemas():dst.AddAppliedSchema(schema)
    from pxr import Usd
    kind=Usd.ModelAPI(src).GetKind()
    if kind:Usd.ModelAPI(dst).SetKind(kind)

def lodgen_mesh(stage,src,path,ratio,min_tris):
    """A reduced copy of one Mesh prim. Returns (triangles before, triangles after)."""
    from pxr import Sdf,Usd,UsdGeom,Vt
    mesh=UsdGeom.Mesh(src);P=np.array(mesh.GetPointsAttr().Get(Usd.TimeCode.EarliestTime()) or [],dtype=np.float64).reshape(-1,3)
    counts=np.array(mesh.GetFaceVertexCountsAttr().Get(Usd.TimeCode.EarliestTime()) or [],dtype=np.int64);indices=np.array(mesh.GetFaceVertexIndicesAttr().Get(Usd.TimeCode.EarliestTime()) or [],dtype=np.int64)
    new=UsdGeom.Mesh.Define(stage,path);lodgen_copy_prim(src,new.GetPrim(),skip=_SKIP_ON_MESH|{'Mesh'})
    before=int(np.maximum(counts-2,0).sum());res=lodgen_cached(P,counts,indices,ratio,min_tris) if len(P) and len(counts) else None
    if res is None:                                                                              # nothing to reduce: an exact copy
        new.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(P.astype(np.float32)) if len(P) else Vt.Vec3fArray());new.CreateFaceVertexCountsAttr(Vt.IntArray.FromNumpy(counts.astype(np.int32)));new.CreateFaceVertexIndicesAttr(Vt.IntArray.FromNumpy(indices.astype(np.int32)))
        for name in ('normals',):
            a=src.GetAttribute(name)
            if a and a.HasValue():
                n=new.GetPrim().CreateAttribute(name,a.GetTypeName());n.Set(a.Get())
                if a.HasMetadata('interpolation'):n.SetMetadata('interpolation',a.GetMetadata('interpolation'))
        for pv in UsdGeom.PrimvarsAPI(src).GetAuthoredPrimvars():
            if pv.GetPrimvarName()=='normals':continue
            out=UsdGeom.PrimvarsAPI(new).CreatePrimvar(pv.GetPrimvarName(),pv.GetTypeName(),pv.GetInterpolation());out.Set(pv.ComputeFlattened())
        after=before
    else:
        pts=res['points'];tri=res['tri'];after=len(tri)
        new.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(pts.astype(np.float32)));new.CreateFaceVertexCountsAttr(Vt.IntArray.FromNumpy(np.full(after,3,dtype=np.int32)));new.CreateFaceVertexIndicesAttr(Vt.IntArray.FromNumpy(tri.reshape(-1).astype(np.int32)))
        new.CreateSubdivisionSchemeAttr('none')
        if src.GetAttribute('normals').HasValue() or UsdGeom.PrimvarsAPI(src).GetPrimvar('normals'):
            normals=lodgen_normals(pts,tri);new.CreateNormalsAttr(Vt.Vec3fArray.FromNumpy(normals.astype(np.float32)));new.SetNormalsInterpolation('vertex')
        for pv in UsdGeom.PrimvarsAPI(src).GetAuthoredPrimvars():
            name=pv.GetPrimvarName()
            if name=='normals':continue
            interp=pv.GetInterpolation();flat=pv.ComputeFlattened()
            if flat is None:continue
            values=lodgen_transfer(np.array(flat),interp,res)
            out=UsdGeom.PrimvarsAPI(new).CreatePrimvar(name,pv.GetTypeName(),interp)
            try:out.Set(type(flat).FromNumpy(np.ascontiguousarray(values)))
            except Exception:out.Set(type(flat)(values.tolist()))
    lo,hi=(pts.min(axis=0),pts.max(axis=0)) if res is not None else ((P.min(axis=0),P.max(axis=0)) if len(P) else (np.zeros(3),np.zeros(3)))
    new.CreateExtentAttr([tuple(float(x) for x in lo),tuple(float(x) for x in hi)])
    return before,after

def lodgen_clone(stage,src,dst_path,ratio,min_tris):
    """Copy the prim hierarchy of a prototype to dst_path, every Mesh reduced. Returns (triangles before, triangles after)."""
    from pxr import Sdf,Usd,UsdGeom
    base=str(src.GetPath());total=[0,0]
    for prim in Usd.PrimRange(src):
        if prim.GetTypeName()=='GeomSubset':continue                                          # material subsets are not carried over (see docs)
        path=Sdf.Path(dst_path+str(prim.GetPath())[len(base):])
        if prim.IsA(UsdGeom.Mesh):
            b,a=lodgen_mesh(stage,prim,path,ratio,min_tris);total[0]+=b;total[1]+=a;continue
        new=stage.DefinePrim(path,prim.GetTypeName());lodgen_copy_prim(prim,new)
    return tuple(total)

def lodgen_author(asset,stage):
    """The LOD_GENERATOR node: write the generated LOD prims for every bank row and level without a prim of its own. Hero prims are not touched."""
    from pxr import Sdf,UsdGeom
    if not asset.evalParm('lodg_on'):return
    entries=resolve(asset);minimum=asset.evalParm('lodg_min');stats={}
    if entries:UsdGeom.Scope.Define(stage,Sdf.Path(lodgen_root(asset)))
    for e in entries:
        src=stage.GetPrimAtPath(e['path'])
        if not src or not src.IsValid():continue
        row={}
        for parm,lod,level in LODGEN_PARMS:
            if asset.evalParm('%s%d'%(lod,e['row'])).strip():continue                        # a prim of its own wins
            before,after=lodgen_clone(stage,src,lodgen_path(asset,e['row'],level),asset.evalParm(parm)/100.0,minimum);row[0]=before;row[level]=after
        if row:stats[e['row']]=row
    _LODGEN_STATS[asset.path()]=stats

def lodgen_info(asset):
    if not asset.evalParm('lodg_on'):return 'Off. Turn on Generate LODs to write reduced copies of every prototype that has no LOD prim of its own.'
    stats=_LODGEN_STATS.get(asset.path())
    if not stats:return 'Cook the node to see the triangle counts.'
    lines=[]
    for row,levels in sorted(stats.items()):
        hero=levels.get(0,0);parts=['hero %s'%format(hero,',')]
        for level,name in ((1,'LOD 1'),(2,'LOD 2'),(3,'Proxy')):
            if level in levels:parts.append('%s %s (%d%%)'%(name,format(levels[level],','),round(100.0*levels[level]/hero) if hero else 100))
        lines.append('Prototype %d: %s triangles'%(row,', '.join(parts)))
    return '\n'.join(lines)
