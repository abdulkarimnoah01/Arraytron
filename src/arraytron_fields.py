# Field Stack (v0.7.0): an ordered list of fields (Height, Slope, Noise, Image, Distance, Exclusion), each a 0..1 value per point, combined with
# Multiply / Add / Subtract / Min / Max into one weight that removes points (Density) and / or scales them. Appended to the PythonModule after the
# mask module (it reuses fbm_noise, read_image, sample_image, planar_uv, TopDownField, scatter_hash, stage_surface, stage_curves). The pure numpy
# functions are tested directly against brute force; sop_fields runs in the FIELD_STACK Python SOP between MASK_PROCESSOR and VARIATION_PROCESSOR.
import math
import numpy as np

FIELD_TYPES=('Height','Slope','Noise','Image','Distance','Exclusion')
FIELD_OPS=('Multiply','Add','Subtract','Min','Max')

# ---------------------------------------------------------------- shaping
def smooth01(x):
    x=np.clip(np.asarray(x,dtype=np.float64),0.0,1.0);return x*x*(3.0-2.0*x)

def band(x,lo,hi,fall):
    """1 inside [lo, hi] (swapped if given the wrong way round), falling to 0 over `fall` outside it (smoothstep); fall 0 is a hard edge."""
    lo,hi=min(lo,hi),max(lo,hi);x=np.asarray(x,dtype=np.float64);out=np.maximum(lo-x,x-hi)
    if fall<=0:return (out<=0).astype(np.float64)
    return 1.0-smooth01(out/fall)

def ramp(d,near,far):
    """0 at or below `near`, 1 at or above `far`, smoothstep between (distance fields: clear around a road, full density away from it)."""
    d=np.asarray(d,dtype=np.float64)
    if far<=near:return (d>near).astype(np.float64)
    return smooth01((d-near)/(far-near))

def combine(values,ops):
    """Fold the field values (list of (N,) arrays in stack order) with the operation of each row after the first: Multiply, Add, Subtract (acc - value),
    Min, Max; the running value is clamped to [0, 1] after every step."""
    acc=np.clip(np.asarray(values[0],dtype=np.float64),0.0,1.0)
    for v,op in zip(values[1:],ops[1:]):
        v=np.asarray(v,dtype=np.float64)
        if op==0:acc=acc*v
        elif op==1:acc=acc+v
        elif op==2:acc=acc-v
        elif op==3:acc=np.minimum(acc,v)
        else:acc=np.maximum(acc,v)
        acc=np.clip(acc,0.0,1.0)
    return acc

# ---------------------------------------------------------------- geometry distances
def seg_dist(p,A,B):
    """Distance from point p (3,) to each segment A[k]-B[k] ((K,3) arrays)."""
    d=B-A;l2=np.einsum('ij,ij->i',d,d);t=np.where(l2>1e-18,np.einsum('ij,ij->i',p-A,d)/np.where(l2>1e-18,l2,1.0),0.0);t=np.clip(t,0.0,1.0)
    return np.linalg.norm(p-(A+d*t[:,None]),axis=1)

def tri_dist(p,A,B,C):
    """Exact distance from p to each triangle (A,B,C: (K,3)); degenerate triangles (a segment, a point) reduce to their edges."""
    best=np.minimum(np.minimum(seg_dist(p,A,B),seg_dist(p,B,C)),seg_dist(p,C,A))
    n=np.cross(B-A,C-A);nn=np.linalg.norm(n,axis=1);ok=nn>1e-12
    if ok.any():
        nu=np.where(ok[:,None],n/np.where(ok,nn,1.0)[:,None],0.0);h=np.einsum('ij,ij->i',p-A,nu);q=p-h[:,None]*nu
        s0=np.einsum('ij,ij->i',np.cross(B-A,q-A),nu);s1=np.einsum('ij,ij->i',np.cross(C-B,q-B),nu);s2=np.einsum('ij,ij->i',np.cross(A-C,q-C),nu)
        inside=ok&(s0>=-1e-12)&(s1>=-1e-12)&(s2>=-1e-12);best=np.where(inside,np.minimum(best,np.abs(h)),best)
    return best

def seg_closest(p,A,B):
    """Closest point of each segment A[k]-B[k] to p, and its distance."""
    d=B-A;l2=np.einsum('ij,ij->i',d,d);t=np.where(l2>1e-18,np.einsum('ij,ij->i',p-A,d)/np.where(l2>1e-18,l2,1.0),0.0);t=np.clip(t,0.0,1.0)
    q=A+d*t[:,None];return np.linalg.norm(p-q,axis=1),q

def tri_closest(p,A,B,C):
    """Closest point on each triangle to p and its distance: the nearest of the three edge points and (when it falls inside) the plane projection."""
    d0,q0=seg_closest(p,A,B);d1,q1=seg_closest(p,B,C);d2,q2=seg_closest(p,C,A)
    best=d0.copy();q=q0.copy();m=d1<best;best[m]=d1[m];q[m]=q1[m];m=d2<best;best[m]=d2[m];q[m]=q2[m]
    n=np.cross(B-A,C-A);nn=np.linalg.norm(n,axis=1);ok=nn>1e-12
    if ok.any():
        nu=np.where(ok[:,None],n/np.where(ok,nn,1.0)[:,None],0.0);h=np.einsum('ij,ij->i',p-A,nu);proj=p-h[:,None]*nu
        s0=np.einsum('ij,ij->i',np.cross(B-A,proj-A),nu);s1=np.einsum('ij,ij->i',np.cross(C-B,proj-B),nu);s2=np.einsum('ij,ij->i',np.cross(A-C,proj-C),nu)
        inside=ok&(s0>=-1e-12)&(s1>=-1e-12)&(s2>=-1e-12)&(np.abs(h)<best);best=np.where(inside,np.abs(h),best);q=np.where(inside[:,None],proj,q)
    return best,q

class TriGrid:
    """Triangles (K,3,3) bucketed by their XZ bounding boxes in square cells, to find the few that can matter near a point."""
    def __init__(self,tris,cell):
        self.tris=np.asarray(tris,dtype=np.float64).reshape(-1,3,3);self.cell=max(float(cell),1e-9);self.cells={}
        if len(self.tris):
            lo=self.tris[:,:,[0,2]].min(axis=1);hi=self.tris[:,:,[0,2]].max(axis=1)
            for k in range(len(self.tris)):
                for cx in range(int(math.floor(lo[k,0]/self.cell)),int(math.floor(hi[k,0]/self.cell))+1):
                    for cz in range(int(math.floor(lo[k,1]/self.cell)),int(math.floor(hi[k,1]/self.cell))+1):self.cells.setdefault((cx,cz),[]).append(k)
    def near(self,x,z,r):
        c=self.cell;found=set()
        for cx in range(int(math.floor((x-r)/c)),int(math.floor((x+r)/c))+1):
            for cz in range(int(math.floor((z-r)/c)),int(math.floor((z+r)/c))+1):found.update(self.cells.get((cx,cz),()))
        return np.fromiter(found,dtype=np.int64,count=len(found))

def distance_to_triangles(P,tris,limit,axes=1):
    """Distance of every point to the nearest triangle, but never more than `limit` (anything farther returns `limit`): only triangles whose XZ box
    comes within `limit` are tested. axes 0 measures in the XZ plane only (heights ignored), 1 in 3D."""
    P=np.asarray(P,dtype=np.float64);tris=np.asarray(tris,dtype=np.float64).reshape(-1,3,3)
    if axes==0:P=P*np.array([1.0,0.0,1.0]);tris=tris*np.array([1.0,0.0,1.0])
    out=np.full(len(P),float(limit))
    if not len(tris):return out
    ext=tris[:,:,[0,2]].max(axis=1)-tris[:,:,[0,2]].min(axis=1);grid=TriGrid(tris,max(limit,float(np.median(ext))*1.5,1e-6))
    for k,p in enumerate(P):
        cand=grid.near(p[0],p[2],limit)
        if len(cand):out[k]=min(limit,float(tri_dist(p,tris[cand,0],tris[cand,1],tris[cand,2]).min()))
    return out

def closest_on_triangles(P,tris,limit,axes=1):
    """(distance, closest point) of every point to the nearest triangle, with the distance capped at `limit` (a point farther away gets `limit` and
    its own position). axes 0 measures in the XZ plane: positions and the returned points are flattened to y = 0."""
    P=np.asarray(P,dtype=np.float64);tris=np.asarray(tris,dtype=np.float64).reshape(-1,3,3)
    if axes==0:P=P*np.array([1.0,0.0,1.0]);tris=tris*np.array([1.0,0.0,1.0])
    dist=np.full(len(P),float(limit));Q=P.copy()
    if not len(tris):return dist,Q
    ext=tris[:,:,[0,2]].max(axis=1)-tris[:,:,[0,2]].min(axis=1);grid=TriGrid(tris,max(limit,float(np.median(ext))*1.5,1e-6))
    for k,p in enumerate(P):
        cand=grid.near(p[0],p[2],limit)
        if len(cand):
            d,q=tri_closest(p,tris[cand,0],tris[cand,1],tris[cand,2]);j=int(np.argmin(d))
            if d[j]<limit:dist[k]=d[j];Q[k]=q[j]
    return dist,Q

def polylines_to_segments(polys):
    segs=[]
    for poly in polys:
        poly=np.asarray(poly,dtype=np.float64).reshape(-1,3)
        if len(poly)>=2:segs.append(np.stack([poly[:-1],poly[1:],poly[1:]],axis=1))
    return np.vstack(segs) if segs else np.zeros((0,3,3))

def inside_closed(P,tris):
    """True for points inside a closed triangle mesh: an odd number of triangles above the point along +Y (XZ-containing, higher than the point)."""
    P=np.asarray(P,dtype=np.float64);tris=np.asarray(tris,dtype=np.float64).reshape(-1,3,3);out=np.zeros(len(P),dtype=bool)
    if not len(tris):return out
    ext=tris[:,:,[0,2]].max(axis=1)-tris[:,:,[0,2]].min(axis=1);grid=TriGrid(tris,max(float(np.median(ext))*1.5,1e-6))
    for k,p in enumerate(P):
        cand=grid.near(p[0],p[2],0.0)
        if not len(cand):continue
        p=p+np.array([0.6180339,0.0,0.4142136])*1e-7*(1.0+np.abs(p))                # a ray through a shared edge would count twice: nudge it off every edge
        t=tris[cand];ax,az=t[:,0,0],t[:,0,2];v0x,v0z=t[:,1,0]-ax,t[:,1,2]-az;v1x,v1z=t[:,2,0]-ax,t[:,2,2]-az
        den=v0x*v1z-v1x*v0z;ok=np.abs(den)>1e-14;den=np.where(ok,den,1.0)
        b1=((p[0]-ax)*v1z-v1x*(p[2]-az))/den;b2=(v0x*(p[2]-az)-(p[0]-ax)*v0z)/den;b0=1-b1-b2
        hit=ok&(b0>=0)&(b1>=0)&(b2>=0)&((b0>0)|(b1>0)|(b2>0));height=b0*t[:,0,1]+b1*t[:,1,1]+b2*t[:,2,1]
        out[k]=int(np.sum(hit&(height>p[1])))%2==1
    return out

def exclusion_value(P,tris,margin,fall):
    """0 inside the mesh or within `margin` of it, rising to 1 over `fall` beyond that (a hard edge when fall is 0)."""
    P=np.asarray(P,dtype=np.float64);limit=margin+max(fall,0.0)+1e-3                                  # a cap just beyond where the weight reaches 1
    d=distance_to_triangles(P,tris,limit,1);inside=inside_closed(P,tris)
    d=np.where(inside,0.0,d)
    if fall<=0:return (d>margin).astype(np.float64)
    return ramp(d,margin,margin+fall)

# ---------------------------------------------------------------- Houdini side
import hou

def _row(asset,name,i):return asset.evalParm('%s%d'%(name,i))
def _row_tuple(asset,name,i):return asset.evalParmTuple('%s%d'%(name,i))

def slope_degrees(normals):
    return np.degrees(np.arccos(np.clip(np.asarray(normals)[:,1],-1.0,1.0)))

def _slope_field(asset,path):
    P,T,area,normals,vn=stage_surface(asset,'field_prim1',path)
    slope=slope_degrees(normals)
    corner=np.repeat(slope,3)[:,None];tri=np.arange(len(T)*3).reshape(-1,3)
    return TopDownField([(P,T.reshape(-1),corner,tri)])

def _prim_geometry(asset,path):
    """Triangles (K,3,3) of every mesh or shape under the prim plus segments (K,3,3 with a repeated end) of every curve; both in world space."""
    tris=np.zeros((0,3,3));segs=np.zeros((0,3,3));found=False
    try:
        P,T,area,normals,vn=stage_surface(asset,'field_prim1',path);tris=P[T];found=True
    except hou.NodeError as exc:
        if 'does not exist' in str(exc) or 'is empty' in str(exc):raise
    try:
        segs=polylines_to_segments([poly for poly,_ in stage_curves(asset,path)]);found=found or len(segs)>0
    except hou.NodeError as exc:
        if 'does not exist' in str(exc) or 'is empty' in str(exc):raise
    if not found:raise hou.NodeError('No mesh, shape or curve found under %s.'%path)
    return tris,segs

def field_values(asset,i,P,ids):
    """Value in [0,1] of row i (before Invert) for every point."""
    kind=_row(asset,'field_type',i)
    if kind==0:return band(P[:,1],_row(asset,'field_hmin',i),_row(asset,'field_hmax',i),_row(asset,'field_hfall',i))
    if kind==1:
        path=_row(asset,'field_prim',i).strip()
        if not path:raise hou.NodeError('Field %d (Slope): the Prim is empty.'%i)
        slope=_slope_field(asset,path).lookup(P,-1.0)[:,0]
        return np.where(slope<-0.5,1.0,band(slope,_row(asset,'field_smin',i),_row(asset,'field_smax',i),_row(asset,'field_sfall',i)))        # not above the prim: not judged
    if kind==2:
        n=fbm_noise(P,_row(asset,'field_nfreq',i),np.array(_row_tuple(asset,'field_noffset',i)),_row(asset,'field_noct',i),_row(asset,'field_nrough',i),_row(asset,'field_nseed',i))
        return np.clip((n-0.5)*_row(asset,'field_ncontrast',i)+0.5,0.0,1.0)
    if kind==3:
        path=_row(asset,'field_image',i).strip()
        if not path:raise hou.NodeError('Field %d (Image): the Image is empty.'%i)
        path=hou.text.expandString(path)
        if not os.path.isfile(path):raise hou.NodeError('Field %d image %s does not exist.'%(i,path))
        try:img=read_image(path,_row(asset,'field_channel',i))
        except ValueError as exc:raise hou.NodeError(str(exc))
        u,v=planar_uv(P,_row(asset,'field_proj',i),_row_tuple(asset,'field_icenter',i),_row_tuple(asset,'field_isize',i));return sample_image(img,u,v,_row(asset,'field_ioutside',i))
    path=_row(asset,'field_prim',i).strip()
    if not path:raise hou.NodeError('Field %d (%s): the Prim is empty.'%(i,FIELD_TYPES[kind]))
    tris,segs=_prim_geometry(asset,path)
    if kind==4:
        near,far=_row(asset,'field_dnear',i),_row(asset,'field_dfar',i);axes=_row(asset,'field_daxes',i);limit=max(far,near)+1e-6
        d=np.minimum(distance_to_triangles(P,tris,limit,axes),distance_to_triangles(P,segs,limit,axes))
        return ramp(d,near,far)
    return exclusion_value(P,np.vstack([tris,segs]) if len(segs) else tris,_row(asset,'field_xmargin',i),_row(asset,'field_xfall',i))

def stack_weights(asset,P,ids):
    """Combined weight of the enabled rows, or None when there is no enabled row."""
    values=[];ops=[]
    for i in range(1,asset.evalParm('fields')+1):
        if not _row(asset,'field_on',i):continue
        v=field_values(asset,i,P,ids)
        if _row(asset,'field_invert',i):v=1.0-v
        values.append(v);ops.append(_row(asset,'field_op',i))
    return combine(values,ops) if values else None

import os
def sop_fields(geo,asset):
    """FIELD_STACK: Density removes a point unless weight > its own id-keyed random number (a higher weight only ever adds points); Scale multiplies
    f@maskscale (the Mask's value, or 1) by Min Scale + (1 - Min Scale) x weight; Prototype Assignment applies it."""
    for name,default in (('field_before',0),('field_after',0),('field_min',0.0),('field_mean',0.0),('field_max',0.0),('field_rows',0)):geo.addAttrib(hou.attribType.Global,name,default)
    n=geo.intrinsicValue('pointcount');geo.setGlobalAttribValue('field_before',n);geo.setGlobalAttribValue('field_after',n)
    rows=sum(1 for i in range(1,asset.evalParm('fields')+1) if _row(asset,'field_on',i));geo.setGlobalAttribValue('field_rows',rows)
    if rows==0 or n==0:return
    P=np.array(geo.pointFloatAttribValues('P')).reshape(-1,3);ids=np.array(geo.pointIntAttribValues('id'))
    w=stack_weights(asset,P,ids);effect=asset.evalParm('field_effect')
    geo.addAttrib(hou.attribType.Point,'fieldweight',1.0);geo.setPointFloatAttribValues('fieldweight',w.tolist())          # copied to the density primvar when asked for
    geo.setGlobalAttribValue('field_min',float(w.min()));geo.setGlobalAttribValue('field_mean',float(w.mean()));geo.setGlobalAttribValue('field_max',float(w.max()))
    if effect in (1,2):
        floor=asset.evalParm('field_minscale');scale=floor+(1.0-floor)*w
        if geo.findPointAttrib('maskscale') is not None:scale=scale*np.array(geo.pointFloatAttribValues('maskscale'))
        else:geo.addAttrib(hou.attribType.Point,'maskscale',1.0)
        geo.setPointFloatAttribValues('maskscale',scale.tolist())
    if effect in (0,2):
        drop=np.nonzero(~(w>scatter_hash(ids,asset.evalParm('field_seed'),21)))[0]
        if len(drop):geo.deletePoints([geo.point(int(i)) for i in drop])
        geo.setGlobalAttribValue('field_after',n-len(drop))

def field_info(asset):
    """Read-only text for the Field Stack."""
    if asset.evalParm('fields')==0:return 'The stack is empty: every point is used as generated. Add a field with the + button.'
    try:
        g=asset.node('USD_COMPILER/FIELD_STACK').geometry()
        if g.attribValue('field_rows')==0:return 'No field is switched on.'
        return '%d field(s). Weight min %.3g, mean %.3g, max %.3g. Kept %d of %d points.'%(g.attribValue('field_rows'),g.attribValue('field_min'),g.attribValue('field_mean'),g.attribValue('field_max'),g.attribValue('field_after'),g.attribValue('field_before'))
    except Exception as exc:return 'Cannot evaluate the stack: %s'%exc
