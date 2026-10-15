# Separation and Collision (v0.5.1 No Overlap, extended in v0.8.0): keep instances from sitting on top of each other (Remove / Push Apart, with a
# visiting Priority) and out of scene geometry (Avoid Geometry: Remove / Push Out). Appended after the other modules by the builder.
# Every instance is treated as a bounding sphere (centre = its prototype's bounding-sphere centre placed with the instance's position, orientation
# and scale; radius = the prototype's bounding radius x the instance scale) and two instances overlap when their centres are closer than
# Spacing x (r1 + r2). The pure functions are numpy only and tested directly.
import numpy as np
try:scatter_hash
except NameError:from arraytron_scatter import scatter_hash

def neighbor_pairs(c,cell):
    """All index pairs (i < j) whose points lie in the same or neighbouring cells of a uniform grid of size `cell` (candidate pairs for a distance test).
    c: (N,D) coordinates, D 2 or 3."""
    n,d=c.shape
    if n<2:return np.zeros(0,dtype=np.int64),np.zeros(0,dtype=np.int64)
    g=np.floor(c/cell).astype(np.int64);g-=g.min(axis=0)-1;dims=g.max(axis=0)+2
    def key(a):
        k=a[:,0].copy()
        for t in range(1,d):k=k*dims[t]+a[:,t]
        return k
    keys=key(g);order=np.argsort(keys,kind='stable');sk=keys[order];ii=[];jj=[]
    offsets=np.array(np.meshgrid(*([[-1,0,1]]*d),indexing='ij')).reshape(d,-1).T
    for off in offsets:
        nk=key(g+off);lo=np.searchsorted(sk,nk,side='left');hi=np.searchsorted(sk,nk,side='right');cnt=hi-lo
        if not cnt.sum():continue
        src=np.repeat(np.arange(n),cnt);start=np.repeat(lo,cnt);pos=np.arange(cnt.sum())-np.repeat(np.cumsum(cnt)-cnt,cnt);other=order[start+pos]
        keep=src<other;ii.append(src[keep]);jj.append(other[keep])
    return (np.concatenate(ii),np.concatenate(jj)) if ii else (np.zeros(0,dtype=np.int64),np.zeros(0,dtype=np.int64))

def _metric(c,axes):
    return c[:,[0,2]] if axes==0 else c

def overlapping_pairs(c,r,tolerance,axes):
    """(i, j, dist, need) of every pair closer than tolerance x (r_i + r_j), measured in the XZ plane (axes 0) or in 3D (axes 1)."""
    m=_metric(np.asarray(c,dtype=np.float64),axes);r=np.asarray(r,dtype=np.float64)
    if len(m)<2:return (np.zeros(0,dtype=np.int64),)*2+(np.zeros(0),)*2
    i,j=neighbor_pairs(m,max(2.0*float(r.max())*tolerance,1e-9));dist=np.linalg.norm(m[i]-m[j],axis=1);need=tolerance*(r[i]+r[j]);hit=dist<need
    return i[hit],j[hit],dist[hit],need[hit]

def visiting_order(r,ids,priority,seed=1):
    """Permutation of point indices in the order the greedy removal visits them (earlier = more likely to survive). 0: index order; 1: biggest radius
    first; 2: smallest first; 3: random (a hash of the id). Ties keep index order."""
    n=len(r);idx=np.arange(n)
    if priority==1:return np.lexsort((idx,-np.asarray(r)))
    if priority==2:return np.lexsort((idx,np.asarray(r)))
    if priority==3:return np.lexsort((idx,scatter_hash(np.asarray(ids,dtype=np.int64),seed,23)))
    return idx

def greedy_remove(c,r,tolerance,axes,order=None):
    """Boolean keep mask: points are visited in `order` (default: index order, the id order) and a point is dropped when an EARLIER VISITED, KEPT point
    overlaps it, so the first points always survive and adding points at the end never changes the earlier survivors."""
    n=len(c);keep=np.ones(n,dtype=bool);c=np.asarray(c);r=np.asarray(r)
    if order is not None:
        order=np.asarray(order);sub=greedy_remove(c[order],r[order],tolerance,axes);keep[order]=sub;return keep
    i,j,_,_=overlapping_pairs(c,r,tolerance,axes)
    if not len(i):return keep
    order=np.argsort(j,kind='stable');i,j=i[order],j[order];start=np.searchsorted(j,np.arange(n+1))
    for k in range(n):
        for e in range(start[k],start[k+1]):
            if keep[i[e]]:keep[k]=False;break
    return keep

def footprint_outline(tris):
    """Outline of the XZ footprint of a triangle set as degenerate triangles (A, B, B) at y = 0: the edges that are not shared by two triangles facing
    the same way seen from above (silhouette edges of a closed mesh, boundary edges of an open one, every edge of a curve segment)."""
    tris=np.asarray(tris,dtype=np.float64).reshape(-1,3,3)
    if not len(tris):return np.zeros((0,3,3))
    ny=np.cross(tris[:,1]-tris[:,0],tris[:,2]-tris[:,0])[:,1];sign=np.where(np.abs(ny)<1e-12,0,np.sign(ny));key=lambda v:tuple(np.round(v*1e6).astype(np.int64));edges={}
    for k in range(len(tris)):
        for a_,b_ in ((0,1),(1,2),(2,0)):
            ek=tuple(sorted((key(tris[k,a_]),key(tris[k,b_]))));edges.setdefault(ek,[]).append((k,a_,b_))
    out=[]
    for ek,users in edges.items():
        signs={int(sign[k]) for k,_,_ in users}
        if len(users)==1 or 0 in signs or len(signs)>1:
            k,a_,b_=users[0];A=tris[k,a_]*np.array([1.0,0.0,1.0]);B=tris[k,b_]*np.array([1.0,0.0,1.0]);out.append([A,B,B])
    return np.array(out) if out else np.zeros((0,3,3))

def covered_xz(P,tris):
    """True for points whose XZ position lies inside the XZ projection of any triangle (vertical triangles project to nothing)."""
    P=np.asarray(P,dtype=np.float64);tris=np.asarray(tris,dtype=np.float64).reshape(-1,3,3);out=np.zeros(len(P),dtype=bool)
    if not len(tris):return out
    ext=tris[:,:,[0,2]].max(axis=1)-tris[:,:,[0,2]].min(axis=1);grid=TriGrid(tris,max(float(np.median(ext))*1.5,1e-6))
    for k,p in enumerate(P):
        cand=grid.near(p[0],p[2],0.0)
        if not len(cand):continue
        t=tris[cand];ax,az=t[:,0,0],t[:,0,2];v0x,v0z=t[:,1,0]-ax,t[:,1,2]-az;v1x,v1z=t[:,2,0]-ax,t[:,2,2]-az;den=v0x*v1z-v1x*v0z;ok=np.abs(den)>1e-14;den=np.where(ok,den,1.0)
        b1=((p[0]-ax)*v1z-v1x*(p[2]-az))/den;b2=(v0x*(p[2]-az)-(p[0]-ax)*v0z)/den;b0=1-b1-b2;out[k]=bool(np.any(ok&(b0>=0)&(b1>=0)&(b2>=0)))
    return out

def avoid_geometry(c,r,margin,tris,axes,mode,iterations=20):
    """Keep instance spheres (centres c, radii r) out of triangle geometry. Distance is centre to the nearest triangle (XZ plane when axes is 0). A sphere
    collides when it is inside a closed mesh (3D only) or closer than r + margin. Returns (keep, displacement, residual). mode 0 (Remove): the keep mask, no
    displacement; mode 1 (Push Out): all True and the displacement (N,3): each pass moves a colliding centre away from its closest point on the geometry by the missing distance (out through the
    nearest surface when it is inside); residual = the largest remaining violation as a fraction of the required distance."""
    c0=np.asarray(c,dtype=np.float64);r=np.asarray(r,dtype=np.float64);tris=np.asarray(tris,dtype=np.float64).reshape(-1,3,3);n=len(c0)
    limit=float(r.max())+margin+1e-3 if n else 1.0
    shape=footprint_outline(tris) if axes==0 else tris                                  # XZ: the outline of the footprint, plus a covered test for points above or below it
    def state(pos):
        d,q=closest_on_triangles(pos,shape,limit,axes);flat=pos*np.array([1.0,0.0,1.0]) if axes==0 else pos
        inside=inside_closed(pos,tris) if axes==1 else covered_xz(pos,tris)
        reach=limit;span=float(np.ptp(shape.reshape(-1,3),axis=0).max()) if len(shape) else 0.0
        while True:                                                                        # a point inside the geometry can be farther from its surface than `limit`: widen the search for those
            lost=np.nonzero(inside&(d>=reach-1e-12))[0] if reach<=max(span,limit)*2.0 else np.zeros(0,dtype=np.int64)
            if not len(lost):break
            reach*=2.0;d2,q2=closest_on_triangles(pos[lost],shape,reach,axes);d[lost]=d2;q[lost]=q2
        return d,q,flat,inside
    if mode==0:
        d,q,flat,inside=state(c0);return ~(inside|(d<r+margin)),np.zeros((n,3)),0.0
    pos=c0.copy();residual=0.0
    for it in range(max(1,int(iterations))):
        d,q,flat,inside=state(pos);need=r+margin;bad=inside|(d<need)
        residual=float((np.where(inside,need+d,need-d)[bad]/need[bad]).max()) if bad.any() else 0.0
        if not bad.any():break
        away=np.where(inside[:,None],q-flat,flat-q);L=np.linalg.norm(away,axis=1);degenerate=L<1e-9
        if degenerate.any():away[degenerate]=np.array([0.0,1.0,0.0]);L[degenerate]=1.0                    # sitting exactly on a surface: out along +Y
        move=np.where(bad,np.where(inside,d+need,need-d),0.0)[:,None]*(away/L[:,None]);pos=pos+move*(np.array([1.0,0.0,1.0]) if axes==0 else 1.0)
    else:
        d,q,flat,inside=state(pos);need=r+margin;bad=inside|(d<need);residual=float((np.where(inside,need+d,need-d)[bad]/need[bad]).max()) if bad.any() else 0.0
    return np.ones(n,dtype=bool),pos-c0,residual

def push_apart(c,r,tolerance,axes,iterations,strength,seed=1):
    """Displacements (N,3) that spread overlapping points: each iteration every overlapping pair is moved apart along the line between the centres by
    strength x half of its overlap (a coincident pair along a hashed direction). Axes 0 moves X and Z only. Returns (delta, residual) where residual is the
    largest remaining overlap as a fraction of the required distance."""
    c0=np.asarray(c,dtype=np.float64);c=c0.copy();r=np.asarray(r,dtype=np.float64);mask=np.array([1.0,0.0,1.0]) if axes==0 else np.ones(3);residual=0.0
    for it in range(max(1,int(iterations))):
        i,j,dist,need=overlapping_pairs(c,r,tolerance,axes)
        residual=float(((need-dist)/need).max()) if len(i) else 0.0
        if not len(i):break
        d=(c[j]-c[i])*mask;L=np.linalg.norm(d,axis=1);tiny=L<1e-9
        if tiny.any():
            a=scatter_hash(i[tiny]*7919+j[tiny],seed,21)*2*np.pi;fallback=np.stack([np.cos(a),np.zeros_like(a),np.sin(a)],axis=1)
            if axes==1:
                b=scatter_hash(i[tiny]*7919+j[tiny],seed,22)*np.pi;fallback=np.stack([np.sin(b)*np.cos(a),np.cos(b),np.sin(b)*np.sin(a)],axis=1)
            d[tiny]=fallback;L[tiny]=1.0
        push=(strength*0.5*(need-dist)/L)[:,None]*d
        move=np.zeros_like(c);np.add.at(move,i,-push);np.add.at(move,j,push);c+=move
    else:
        i,j,dist,need=overlapping_pairs(c,r,tolerance,axes);residual=float(((need-dist)/need).max()) if len(i) else 0.0
    return c-c0,residual

# ---------------------------------------------------------------- Houdini side
import hou

def instance_spheres_for(asset,geo):
    """Centres (N,3) and radii (N,) of the instance bounding spheres of the points of geo (after the Prototype Assignment)."""
    s=read_points(geo)
    if asset.evalParm('overlap_size')==1:
        return s,s['P'].copy(),np.full(len(s['id']),asset.evalParm('overlap_radius'))*s['scale'].max(axis=1)
    c,r=stone_spheres(s,proto_proxies(asset));return s,c,r

def _avoid_geometry_of(asset):
    path=asset.evalParm('avoid_prim').strip()
    if not path:raise hou.NodeError('Avoid Geometry: the Prim is empty.')
    tris,segs=_prim_geometry(asset,path);return np.vstack([tris,segs]) if len(segs) else tris

def sop_overlap(geo,asset):
    """NO_OVERLAP (Separation and Collision): first Avoid Geometry (Remove or Push Out), then Separation (Remove in Priority order, or Push Apart), then
    a last Push Out pass when both push. Ids and orientations are never touched; only points are deleted or moved."""
    for name,default in (('overlap_before',0),('overlap_after',0),('overlap_moved',0),('overlap_residual',0.0),('avoid_removed',0),('avoid_moved',0),('avoid_residual',0.0)):geo.addAttrib(hou.attribType.Global,name,default)
    n=geo.intrinsicValue('pointcount');geo.setGlobalAttribValue('overlap_before',n);geo.setGlobalAttribValue('overlap_after',n)
    mode=asset.evalParm('overlap_mode');avoid=asset.evalParm('avoid_mode') if asset.parm('avoid_mode') is not None else 0
    if (mode==0 and avoid==0) or n==0:return
    tol=asset.evalParm('overlap_tolerance');axes=asset.evalParm('overlap_axes')
    def push_out():
        s,c,r=instance_spheres_for(asset,geo)
        if not len(c):return
        keep,delta,residual=avoid_geometry(c,r,asset.evalParm('avoid_margin'),_avoid_geometry_of(asset),asset.evalParm('avoid_axes'),1,asset.evalParm('avoid_iterations'))
        moved=np.linalg.norm(delta,axis=1)>1e-12
        if moved.any():geo.setPointFloatAttribValues('P',(s['P']+delta).ravel().tolist())
        geo.setGlobalAttribValue('avoid_moved',int(moved.sum()));geo.setGlobalAttribValue('avoid_residual',float(residual))
    if avoid==1:
        s,c,r=instance_spheres_for(asset,geo);keep,_,_=avoid_geometry(c,r,asset.evalParm('avoid_margin'),_avoid_geometry_of(asset),asset.evalParm('avoid_axes'),0)
        drop=np.nonzero(~keep)[0]
        if len(drop):geo.deletePoints([geo.point(int(i)) for i in drop])
        geo.setGlobalAttribValue('avoid_removed',len(drop))
    elif avoid==2:push_out()
    if geo.intrinsicValue('pointcount')==0:return
    if mode==1:
        s,c,r=instance_spheres_for(asset,geo);before=len(c)
        keep=greedy_remove(c,r,tol,axes,visiting_order(r,s['id'],asset.evalParm('overlap_priority') if asset.parm('overlap_priority') is not None else 0))
        drop=np.nonzero(~keep)[0]
        if len(drop):geo.deletePoints([geo.point(int(i)) for i in drop])
        geo.setGlobalAttribValue('overlap_before',n-int(geo.attribValue('avoid_removed')));geo.setGlobalAttribValue('overlap_after',before-len(drop))
    elif mode==2:
        s,c,r=instance_spheres_for(asset,geo)
        if asset.evalParm('mode') in (4,5,6,7):hou.pwd().addWarning('Separation > Push Apart moves points off the curve or surface they were placed on; use Remove Overlapping to keep them on it.')
        delta,residual=push_apart(c,r,tol,axes,asset.evalParm('overlap_iterations'),asset.evalParm('overlap_strength'),1)
        moved=np.linalg.norm(delta,axis=1)>1e-12
        if moved.any():geo.setPointFloatAttribValues('P',(s['P']+delta).ravel().tolist())
        geo.setGlobalAttribValue('overlap_moved',int(moved.sum()));geo.setGlobalAttribValue('overlap_residual',residual)
        if avoid==2:push_out()                                                           # geometry wins: a last pass after the points were spread

def overlap_info(asset):
    mode=asset.evalParm('overlap_mode');avoid=asset.evalParm('avoid_mode') if asset.parm('avoid_mode') is not None else 0
    if mode==0 and avoid==0:return 'Separation and Avoid Geometry are off.'
    try:
        g=asset.node('USD_COMPILER/NO_OVERLAP').geometry();text=[]
        if avoid==1:text.append('Avoid Geometry removed %d points.'%g.attribValue('avoid_removed'))
        elif avoid==2:text.append('Avoid Geometry moved %d points (worst violation left %.1f%%).'%(g.attribValue('avoid_moved'),100*g.attribValue('avoid_residual')))
        if mode==1:text.append(('Separation removed' if avoid else 'Removed')+' %d of %d points.'%(g.attribValue('overlap_before')-g.attribValue('overlap_after'),g.attribValue('overlap_before')))
        elif mode==2:text.append(('Moved %d of %d points; the worst overlap left is %.1f%% of the required distance.' if not avoid else 'Separation moved %d of %d points; the worst overlap left is %.1f%% of the required distance.')%(g.attribValue('overlap_moved'),g.attribValue('overlap_before'),100*g.attribValue('overlap_residual')))
        return ' '.join(text)
    except Exception as exc:return 'Cannot evaluate: %s'%exc
