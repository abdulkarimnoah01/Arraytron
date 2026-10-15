# Mask pipeline (v0.5.0): one reusable "how much here?" value per point, from procedural noise, an image, or a primvar painted on a mesh.
# Appended to arraytron_module.py + arraytron_physics.py + arraytron_scatter.py by the builder (it reuses scatter_hash, shape helpers and the
# triangulation idea of the scatter module). The pure numpy functions are tested directly; the Houdini part (sop_mask) runs in MASK_PROCESSOR.
import math
import numpy as np
try:scatter_hash
except NameError:from arraytron_scatter import scatter_hash

# ---------------------------------------------------------------- noise
def _lattice(ix,iy,iz,seed):
    key=(ix.astype(np.int64)*1000003+iy.astype(np.int64))*1000033+iz.astype(np.int64)
    return scatter_hash(key.astype(np.uint64),seed,7)

def value_noise(p,seed=1):
    """3D value noise in [0,1]: random values on the integer lattice, smoothstep-interpolated (p: (N,3))."""
    p=np.asarray(p,dtype=np.float64);i=np.floor(p);f=p-i;s=f*f*(3-2*f)
    out=np.zeros(len(p))
    for dx in (0,1):
        for dy in (0,1):
            for dz in (0,1):
                w=(s[:,0] if dx else 1-s[:,0])*(s[:,1] if dy else 1-s[:,1])*(s[:,2] if dz else 1-s[:,2])
                out+=w*_lattice(i[:,0]+dx,i[:,1]+dy,i[:,2]+dz,seed)
    return out

def fbm_noise(p,frequency,offset,octaves,roughness,seed):
    """Fractal sum of value noise, normalised to [0,1]: octave k has frequency x2^k and amplitude roughness^k."""
    p=np.asarray(p,dtype=np.float64)*frequency+np.asarray(offset,dtype=np.float64);total=0.0;amp=1.0;value=np.zeros(len(p))
    for k in range(max(1,int(octaves))):
        value+=amp*value_noise(p*(2.0**k),seed+k);total+=amp;amp*=roughness
    return value/total

# ---------------------------------------------------------------- images
_IMAGES={}
def read_image(path,channel):
    """(H,W) float array of one channel (0 luminance, 1 R, 2 G, 3 B, 4 A) of an image file, values as stored (no colour transform), row 0 = top."""
    import os, OpenImageIO as oiio
    key=(path,os.path.getmtime(path),channel)
    if key not in _IMAGES:
        buf=oiio.ImageBuf(path)
        if not buf.read():raise ValueError('cannot read %s: %s'%(path,buf.geterror()))
        px=np.asarray(buf.get_pixels(oiio.FLOAT),dtype=np.float64);px=px.reshape(px.shape[0],px.shape[1],-1);c=px.shape[2]
        if channel==0:img=px[:,:,0] if c<3 else 0.2126*px[:,:,0]+0.7152*px[:,:,1]+0.0722*px[:,:,2]
        else:
            if channel-1>=c:raise ValueError('%s has no channel %s'%(path,'RGBA'[channel-1]))
            img=px[:,:,channel-1]
        if len(_IMAGES)>8:_IMAGES.clear()
        _IMAGES[key]=img
    return _IMAGES[key]

def sample_image(img,u,v,outside=0):
    """Bilinear lookup at (u,v) in [0,1]^2, u to the right, v down from the top row. outside: 0 black, 1 repeat, 2 clamp edge pixels."""
    h,w=img.shape;u=np.asarray(u,dtype=np.float64);v=np.asarray(v,dtype=np.float64);inside=(u>=0)&(u<=1)&(v>=0)&(v<=1)
    if outside==1:u=u-np.floor(u);v=v-np.floor(v)
    x=u*w-0.5;y=v*h-0.5;x0=np.floor(x);y0=np.floor(y);fx=x-x0;fy=y-y0
    def px(ix,iy):
        if outside==1:return img[np.mod(iy,h).astype(int),np.mod(ix,w).astype(int)]
        return img[np.clip(iy,0,h-1).astype(int),np.clip(ix,0,w-1).astype(int)]
    val=(px(x0,y0)*(1-fx)*(1-fy)+px(x0+1,y0)*fx*(1-fy)+px(x0,y0+1)*(1-fx)*fy+px(x0+1,y0+1)*fx*fy)
    return val if outside!=0 else np.where(inside,val,0.0)

def planar_uv(P,projection,center,size):
    """u,v for a planar projection. 0 Top: u along +X, v along +Z (the image top is -Z, as seen from above with X to the right); 1 Front: u along +X, the image top is +Y."""
    P=np.asarray(P,dtype=np.float64);sx=max(size[0],1e-9);sy=max(size[1],1e-9)
    if projection==0:return (P[:,0]-center[0])/sx+0.5,(P[:,2]-center[1])/sy+0.5
    return (P[:,0]-center[0])/sx+0.5,0.5-(P[:,1]-center[1])/sy

# ---------------------------------------------------------------- mesh primvars looked up from above
def fan_triangles(counts,n_indices):
    """Fan triangles of polygon faces as face-vertex index triples (T,3) and the face number of each triangle."""
    counts=np.asarray(counts,dtype=np.int64);starts=np.concatenate(([0],np.cumsum(counts)[:-1]));tris=[];faces=[]
    for k in range(int(counts.max())-2 if len(counts) else 0):
        sel=np.nonzero(counts>k+2)[0];tris.append(np.stack([starts[sel],starts[sel]+k+1,starts[sel]+k+2],axis=1));faces.append(sel)
    if not tris:return np.zeros((0,3),dtype=np.int64),np.zeros(0,dtype=np.int64)
    return np.vstack(tris),np.concatenate(faces)

class TopDownField:
    """A primvar of one or more meshes, interpolated at (x, z) positions by looking from +Y down onto the mesh triangles (the highest
    triangle wins). values (V,D) per mesh corner; points outside every triangle get `outside`."""
    def __init__(self,meshes):
        self.tri=[];self.val=[]                                                  # triangle corner positions (T,3,3) and corner values (T,3,D)
        for pts,corner_points,corner_values,tris in meshes:
            self.tri.append(pts[corner_points[tris]]);self.val.append(corner_values[tris])
        self.tri=np.vstack(self.tri) if self.tri else np.zeros((0,3,3));self.val=np.vstack(self.val) if self.val else np.zeros((0,3,1))
        self.dim=self.val.shape[2];n=len(self.tri)
        if n:
            lo=self.tri[:,:,[0,2]].min(axis=1);hi=self.tri[:,:,[0,2]].max(axis=1);self.cell=max(float(np.median(hi-lo))*1.5,1e-6);self.grid={}
            for t in range(n):
                for cx in range(int(math.floor(lo[t,0]/self.cell)),int(math.floor(hi[t,0]/self.cell))+1):
                    for cz in range(int(math.floor(lo[t,1]/self.cell)),int(math.floor(hi[t,1]/self.cell))+1):self.grid.setdefault((cx,cz),[]).append(t)
    def lookup(self,P,outside=0.0):
        P=np.asarray(P,dtype=np.float64);out=np.full((len(P),self.dim),float(outside))
        if not len(self.tri):return out
        for k,(x,z) in enumerate(P[:,[0,2]]):
            cand=self.grid.get((int(math.floor(x/self.cell)),int(math.floor(z/self.cell))))
            if not cand:continue
            t=self.tri[cand];ax,az=t[:,0,0],t[:,0,2];v0x,v0z=t[:,1,0]-ax,t[:,1,2]-az;v1x,v1z=t[:,2,0]-ax,t[:,2,2]-az
            den=v0x*v1z-v1x*v0z;ok=np.abs(den)>1e-14;den=np.where(ok,den,1.0)
            b1=((x-ax)*v1z-v1x*(z-az))/den;b2=(v0x*(z-az)-(x-ax)*v0z)/den;b0=1-b1-b2;eps=-1e-9
            hit=ok&(b0>=eps)&(b1>=eps)&(b2>=eps)
            if not hit.any():continue
            height=b0*t[:,0,1]+b1*t[:,1,1]+b2*t[:,2,1];best=np.nonzero(hit)[0][np.argmax(np.where(hit,height,-np.inf)[hit])];c=cand[best]
            out[k]=b0[best]*self.val[c,0]+b1[best]*self.val[c,1]+b2[best]*self.val[c,2]
        return out

# ---------------------------------------------------------------- Houdini side
import os
import hou
from pxr import Usd, UsdGeom

def _mesh_field(asset,name,dim):
    """TopDownField of one primvar of every Mesh under the Mask Prim."""
    path=asset.evalParm('mask_prim').strip()
    if not path:raise hou.NodeError('The Mask Prim is empty: pick the mesh that carries the primvar.')
    stage=asset.node('SOURCE_RESOLVER').stage();root=stage.GetPrimAtPath(path) if stage else None
    if not root or not root.IsValid():raise hou.NodeError('%s does not exist in the incoming stage.'%path)
    xc=UsdGeom.XformCache(Usd.TimeCode.Default());meshes=[]
    for prim in Usd.PrimRange(root):
        if not prim.IsA(UsdGeom.Mesh) or UsdGeom.Imageable(prim).GetPurposeAttr().Get() in ('guide','proxy'):continue
        mesh=UsdGeom.Mesh(prim);pv=UsdGeom.PrimvarsAPI(prim).GetPrimvar(name)
        if not pv or not pv.HasValue():continue
        m=np.array(xc.GetLocalToWorldTransform(prim),dtype=np.float64).reshape(4,4);pts=np.array(mesh.GetPointsAttr().Get(),dtype=np.float64).reshape(-1,3)@m[:3,:3]+m[3,:3]
        counts=np.array(mesh.GetFaceVertexCountsAttr().Get(),dtype=np.int64);idx=np.array(mesh.GetFaceVertexIndicesAttr().Get(),dtype=np.int64)
        vals=np.array(pv.ComputeFlattened(),dtype=np.float64);vals=vals.reshape(len(vals),-1)
        if vals.shape[1]<dim:raise hou.NodeError('Primvar %s on %s has %d component(s), %d needed.'%(name,prim.GetPath(),vals.shape[1],dim))
        vals=vals[:,:dim];interp=str(pv.GetInterpolation());tris,faces=fan_triangles(counts,len(idx))
        if interp in ('vertex','varying'):corner_points=idx;corner_values=vals[idx]
        elif interp=='faceVarying':corner_points=idx;corner_values=vals
        elif interp=='uniform':corner_points=idx;corner_values=vals[np.minimum(np.repeat(np.arange(len(counts)),counts),len(vals)-1)]
        else:corner_points=idx;corner_values=np.repeat(vals[:1],len(idx),axis=0)
        meshes.append((pts,corner_points,corner_values,tris))
    if not meshes:raise hou.NodeError('No mesh under %s has a primvar called %s.'%(path,name))
    return TopDownField(meshes)

def mask_values(asset,P,ids):
    """Raw mask value in [0,1] (before Invert and the Low / High remap) for each point position."""
    source=asset.evalParm('mask_source');seed=asset.evalParm('mask_seed')
    if source==1:
        n=fbm_noise(P,asset.evalParm('mask_noise_freq'),np.array(asset.evalParmTuple('mask_noise_offset')),asset.evalParm('mask_noise_octaves'),asset.evalParm('mask_noise_rough'),seed)
        return np.clip((n-0.5)*asset.evalParm('mask_noise_contrast')+0.5,0.0,1.0)       # fractal noise clusters around 0.5: stretch it to use the whole range
    if source==2:
        path=asset.evalParm('mask_image').strip()
        if not path:raise hou.NodeError('The Mask Image is empty.')
        path=hou.text.expandString(path)
        if not os.path.isfile(path):raise hou.NodeError('Mask image %s does not exist.'%path)
        try:img=read_image(path,asset.evalParm('mask_channel'))
        except ValueError as exc:raise hou.NodeError(str(exc))
        proj=asset.evalParm('mask_proj')
        if proj==2:
            uv=_mesh_field(asset,asset.evalParm('mask_uvname').strip() or 'st',2).lookup(P,-1.0);u,v=uv[:,0],1.0-uv[:,1];val=sample_image(img,u,v,asset.evalParm('mask_outside'))
            return np.where(uv[:,0]<-0.5,0.0,val)                                  # outside the mesh: 0
        u,v=planar_uv(P,proj,asset.evalParmTuple('mask_center'),asset.evalParmTuple('mask_size'));return sample_image(img,u,v,asset.evalParm('mask_outside'))
    if source==3:
        name=asset.evalParm('mask_primvar').strip()
        if not name:raise hou.NodeError('The Mask Primvar name is empty.')
        return _mesh_field(asset,name,1).lookup(P,asset.evalParm('mask_mesh_outside'))[:,0]
    return np.ones(len(P))

def mask_weights(asset,raw):
    """Invert, then remap [Low, High] to [0, 1] (clamped)."""
    m=1.0-raw if asset.evalParm('mask_invert') else raw;lo=asset.evalParm('mask_low');hi=asset.evalParm('mask_high')
    return np.clip((m-lo)/max(hi-lo,1e-9),0.0,1.0)

def sop_mask(geo,asset):
    """MASK_PROCESSOR: Density removes points with probability 1 - weight (a point survives if weight > its own id-keyed random number, so a
    higher weight only ever adds points); Scale writes f@maskscale = MinScale + (1 - MinScale) x weight for the Prototype Assignment stage."""
    for name,default in (('mask_before',0),('mask_after',0),('mask_min',0.0),('mask_mean',0.0),('mask_max',0.0)):geo.addAttrib(hou.attribType.Global,name,default)
    n=geo.intrinsicValue('pointcount');geo.setGlobalAttribValue('mask_before',n);geo.setGlobalAttribValue('mask_after',n)
    if asset.evalParm('mask_source')==0 or n==0:return
    P=np.array(geo.pointFloatAttribValues('P')).reshape(-1,3);ids=np.array(geo.pointIntAttribValues('id'))
    raw=mask_values(asset,P,ids);w=mask_weights(asset,raw);effect=asset.evalParm('mask_effect')
    geo.addAttrib(hou.attribType.Point,'maskweight',1.0);geo.setPointFloatAttribValues('maskweight',w.tolist())              # copied to the mask primvar when asked for
    geo.setGlobalAttribValue('mask_min',float(w.min()));geo.setGlobalAttribValue('mask_mean',float(w.mean()));geo.setGlobalAttribValue('mask_max',float(w.max()))
    if effect in (1,2):
        floor=asset.evalParm('mask_minscale');geo.addAttrib(hou.attribType.Point,'maskscale',1.0);geo.setPointFloatAttribValues('maskscale',(floor+(1.0-floor)*w).tolist())
    if effect in (0,2):
        drop=np.nonzero(~(w>scatter_hash(ids,asset.evalParm('mask_seed'),11)))[0]
        if len(drop):geo.deletePoints([geo.point(int(i)) for i in drop])
        geo.setGlobalAttribValue('mask_after',n-len(drop))

def mask_info(asset):
    """Read-only text for the Mask folder."""
    if asset.evalParm('mask_source')==0:return 'No mask: every point is used as generated.'
    try:
        g=asset.node('USD_COMPILER/MASK_PROCESSOR').geometry()
        return 'Mask weight min %.3g, mean %.3g, max %.3g. Kept %d of %d points.'%(g.attribValue('mask_min'),g.attribValue('mask_mean'),g.attribValue('mask_max'),g.attribValue('mask_after'),g.attribValue('mask_before'))
    except Exception as exc:return 'Cannot evaluate the mask: %s'%exc
