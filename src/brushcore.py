# ---------------------------------------------------------------- Arraytron BrushCore 2.0
# The brush maths shared by Arraytron (procedural paint points) and Arraytron Stamp (manual stamps). Pure numpy: no hou, no USD, so every function is tested
# without a viewport (tests/validate_brushcore.py). Both HDAs embed this file at the top of their PythonModule (the builders read it), each tool keeps an adapter
# that turns the arrays into its own data (Arraytron: paint_data, Stamp: the Stamps text). Names start with bc_ / Brush so they never collide with the tools' own.
#   Falloff        bc_curve, bc_lut, bc_profile, bc_multiplier, bc_brush_weight, BC_PRESETS            one definition of the curves for density, scale and the editing brushes
#   Stroke         BrushStroke (the swept field: density / scale falloff over the whole stroke, speed independent), BrushDabs (distance-based dabs for the editing brushes)
#   Spatial        BrushGrid (a uniform hash grid, numpy sorted cells: radius queries, pairs, incremental adds)
#   Brushes        bc_erase, bc_relax, bc_scale, bc_push, bc_orient, bc_replace, bc_clone_capture / bc_clone_place
#   Viewer         bc_cursor (the polylines of the cursor), BC_COLORS, BC_BRUSHES (the registry), bc_hud_rows, bc_prefs_load / bc_prefs_save
import json, math, os, time
import numpy as np

BC_VERSION='2.0.0'

# ---------------------------------------------------------------- hashing: the same numbers for the same cell / id, whatever order a stroke reaches it in
def bc_mix64(x):
    x=np.asarray(x,dtype=np.uint64)
    with np.errstate(over='ignore'):
        x=(x^(x>>np.uint64(30)))*np.uint64(0xbf58476d1ce4e5b9);x=(x^(x>>np.uint64(27)))*np.uint64(0x94d049bb133111eb);return x^(x>>np.uint64(31))

def bc_hash2(i,j,seed,k):
    """A 64 bit hash per grid cell (integer arrays i, j), per seed and stream k."""
    with np.errstate(over='ignore'):
        return bc_mix64(bc_mix64(np.asarray(i).astype(np.int64).astype(np.uint64)*np.uint64(0x9E3779B97F4A7C15)+np.asarray(j).astype(np.int64).astype(np.uint64)*np.uint64(0xC2B2AE3D27D4EB4F))+np.uint64((int(seed)*2654435761+int(k)*40503+1)%(2**64)))

def bc_hash1(ids,seed,k):
    """A 64 bit hash per id (instance id, dab number ...), per seed and stream k."""
    return bc_hash2(ids,np.zeros(np.shape(ids),dtype=np.int64)+int(k)*7919,seed,k)

def bc_unit(h):
    """Uniform numbers in [0, 1) from 64 bit hashes."""
    return (np.asarray(h,dtype=np.uint64)>>np.uint64(11)).astype(np.float64)*(1.0/9007199254740992.0)

# ---------------------------------------------------------------- falloff
# u is the place inside the transition (0 = its inner edge, 1 = the rim); a curve is how much of the fall is done at u. The influence is 1 - curve: 1 on the plateau, 0 at the rim.
BC_CURVES=('linear','smoothstep','smootherstep','ease_in','ease_out','custom','constant','gaussian')                   # the order of Arraytron Stamp's Curve menu (0.9.3) with two entries appended (2.0)
BC_CURVE_LABELS=('Linear','Smoothstep','Smootherstep','Ease In','Ease Out','Custom Ramp','Constant (hard edge)','Gaussian')
BC_LUT_U=np.linspace(0.0,1.0,257)
_GAUSS_K=4.5

def bc_curve(kind,u):
    """How much of the fall is done at u in [0, 1] (0 at the inner edge, 1 at the rim) for a named curve. Every curve is 0 at u = 0 and 1 at u = 1 except constant (0: no fall until the rim)."""
    u=np.clip(np.asarray(u,dtype=np.float64),0.0,1.0)
    if kind=='smoothstep':return u*u*(3.0-2.0*u)
    if kind=='smootherstep':return u*u*u*(u*(u*6.0-15.0)+10.0)
    if kind=='ease_in':return u*u
    if kind=='ease_out':return 1.0-(1.0-u)**2
    if kind=='constant':return np.zeros_like(u)
    if kind=='gaussian':return (1.0-np.exp(-_GAUSS_K*u*u))/(1.0-np.exp(-_GAUSS_K))                  # a bell scaled so it reaches exactly 0 influence at the rim (no clipping step)
    return u

def bc_lut(kind,ramp=None):
    """The influence (1 at the inner edge of the transition, 0 at the rim) at 257 steps of u. kind: a name of BC_CURVES or its index; ramp: a function of x in [0, 1]
    (x = 0 the rim, 1 the inner edge) for 'custom' (a Houdini ramp's lookup), a straight line when missing."""
    if not isinstance(kind,str):kind=BC_CURVES[min(max(int(kind),0),len(BC_CURVES)-1)]
    if kind=='custom':
        if ramp is None:return 1.0-BC_LUT_U
        return np.clip(np.array([float(ramp(1.0-float(u))) for u in BC_LUT_U],dtype=np.float64),0.0,1.0)
    return 1.0-bc_curve(kind,BC_LUT_U)

def bc_profile(on=True,minimum=0.0,maximum=1.0,width=1.0,strength=1.0,curve='smoothstep',lut=None):
    """One falloff channel as a dict, or None when it is off. minimum / maximum: the multiplier at the rim and on the plateau; width: the share of the radius the fall takes,
    from the rim inwards (1 starts at the centre, 0 is a hard edge); strength: how much of the fall is used (0 none)."""
    if not on:return None
    width=min(max(float(width),0.0),1.0)
    kind=curve if isinstance(curve,str) else BC_CURVES[min(max(int(curve),0),len(BC_CURVES)-1)]
    exact=kind if (lut is None and kind!='custom') else None
    return dict(min=float(minimum),max=float(maximum),inner=1.0-width,strength=min(max(float(strength),0.0),1.0),lut=bc_lut(kind) if lut is None else np.asarray(lut,dtype=np.float64),kind=exact)

def _infl(profile,u):
    """The influence at u: the exact curve when the profile names one, else its lookup table (a custom ramp)."""
    k=profile.get('kind')
    return 1.0-bc_curve(k,u) if k else np.interp(u,BC_LUT_U,profile['lut'])

def bc_influence(profile,r):
    """0..1 at the normalised distance r from the stroke (0 on it, 1 at the rim): 1 on the plateau, falling along the curve to 0 at the rim, 0 outside."""
    r=np.asarray(r,dtype=np.float64)
    if profile is None:return np.where(r<=1.0,1.0,0.0)
    u=np.clip((r-profile['inner'])/max(1.0-profile['inner'],1e-6),0.0,1.0);return np.where(r<=1.0+1e-12,_infl(profile,u),0.0)

def bc_multiplier(profile,r):
    """The multiplier of a channel at the normalised distance r: lerp(min, max, influence) blended with 1 by strength; 1 when the channel is off (None).
    r beyond the rim reads as the rim. Pure function of r: evaluating it again never compounds (the painted scale never shrinks twice)."""
    r=np.asarray(r,dtype=np.float64)
    if profile is None:return np.ones_like(r)
    u=np.clip((r-profile['inner'])/max(1.0-profile['inner'],1e-6),0.0,1.0);m=profile['min']+(profile['max']-profile['min'])*_infl(profile,u)
    return 1.0+profile['strength']*(m-1.0)

def bc_brush_weight(r,curve='smoothstep',hardness=0.0):
    """The weight of the editing brushes (Erase, Relax, Scale, Push, Orient, Replace) at r = distance / radius: 1 inside hardness, the curve down to 0 at the rim, 0 outside."""
    return bc_influence(bc_profile(True,0.0,1.0,1.0-min(max(hardness,0.0),0.999),1.0,curve),r)

# Presets: values of the parameters (percentages, as the tools' parameters hold them); the same parameters the artist edits, not a second system.
BC_PRESETS=('uniform','soft','sparse','growth','dense','custom','hard','taper','organic')                                  # Stamp 0.9.3 order, new ones appended so saved menus keep their entry
BC_PRESET_LABELS=('Uniform Scatter (no falloff)','Soft Natural','Sparse Edges','Growth','Dense Center','Custom','Hard Stamp','Edge Taper','Sparse Organic')
BC_PRESET_VALUES={'uniform':dict(dens_on=0,scale_on=0),
 'soft':dict(dens_on=1,dens_min=5,dens_width=75,dens_strength=100,dens_curve=2,scale_on=1,scale_min=35,scale_max=100,scale_width=85,scale_strength=100,scale_curve=1),
 'sparse':dict(dens_on=1,dens_min=0,dens_width=80,dens_strength=100,dens_curve=2,scale_on=1,scale_min=70,scale_max=100,scale_width=60,scale_strength=100,scale_curve=1),
 'growth':dict(dens_on=1,dens_min=30,dens_width=60,dens_strength=70,dens_curve=1,scale_on=1,scale_min=12,scale_max=100,scale_width=100,scale_strength=100,scale_curve=1),
 'dense':dict(dens_on=1,dens_min=0,dens_width=100,dens_strength=100,dens_curve=4,scale_on=1,scale_min=85,scale_max=100,scale_width=100,scale_strength=60,scale_curve=1),
 'hard':dict(dens_on=1,dens_min=0,dens_width=4,dens_strength=100,dens_curve=0,scale_on=0),
 'taper':dict(dens_on=0,scale_on=1,scale_min=25,scale_max=100,scale_width=55,scale_strength=100,scale_curve=2),
 'organic':dict(dens_on=1,dens_min=0,dens_width=80,dens_strength=100,dens_curve=1,scale_on=1,scale_min=25,scale_max=100,scale_width=55,scale_strength=100,scale_curve=2)}      # the default of a new node

# ---------------------------------------------------------------- spatial index
class BrushGrid(object):
    """A uniform hash grid over points (2 or 3 columns): radius queries and neighbour pairs in time proportional to the points near the query, not to all of them.
    The points are sorted by cell once (numpy); later adds go to a small list that is merged when it grows. Indices are positions in the array given (plus the adds, in order)."""
    def __init__(self,points,cell):
        P=np.asarray(points,dtype=np.float64);self.dim=P.shape[1] if P.ndim==2 and len(P) else (P.shape[1] if P.ndim==2 else 2);self.cell=max(float(cell),1e-9)
        self.P=P.reshape(-1,self.dim);self.extra=[];self._sort()
    def _keys(self,C):
        C=np.asarray(C,dtype=np.int64)
        with np.errstate(over='ignore'):
            k=C[:,0]*np.int64(73856093)
            for a in range(1,self.dim):k=k^(C[:,a]*np.int64((19349663,83492791)[a-1]))
        return k
    def _sort(self):
        self.C=np.floor(self.P/self.cell).astype(np.int64) if len(self.P) else np.zeros((0,self.dim),dtype=np.int64);k=self._keys(self.C) if len(self.P) else np.zeros(0,dtype=np.int64)
        self.order=np.argsort(k,kind='stable');self.sk=k[self.order]
    def __len__(self):return len(self.P)+len(self.extra)
    def add(self,points):
        """Add points (their indices follow the ones there are)."""
        for p in np.asarray(points,dtype=np.float64).reshape(-1,self.dim):self.extra.append(p)
        if len(self.extra)>max(256,len(self.P)//8):self.P=np.vstack([self.P,np.array(self.extra)]);self.extra=[];self._sort()
    def points(self):
        return np.vstack([self.P,np.array(self.extra)]) if self.extra else self.P
    def query(self,center,radius):
        """Indices of the points within radius of center (inclusive)."""
        c=np.asarray(center,dtype=np.float64)[:self.dim];r=float(radius);out=[]
        if len(self.P):
            lo=np.floor((c-r)/self.cell).astype(np.int64);hi=np.floor((c+r)/self.cell).astype(np.int64);span=hi-lo+1
            if np.prod(span)>4096:                                                                   # a radius far bigger than the cells: plain numpy over the points is cheaper
                idx=np.nonzero(((self.P-c)**2).sum(axis=1)<=r*r)[0];out.append(idx)
            else:
                grids=np.meshgrid(*[np.arange(lo[a],hi[a]+1) for a in range(self.dim)],indexing='ij');cells=np.stack([g.ravel() for g in grids],axis=1);keys=self._keys(cells)
                a=np.searchsorted(self.sk,keys,'left');b=np.searchsorted(self.sk,keys,'right');cand=np.concatenate([self.order[i:j] for i,j in zip(a,b) if j>i]) if np.any(b>a) else np.zeros(0,dtype=np.int64)
                if len(cand):cand=np.unique(cand);out.append(cand[((self.P[cand]-c)**2).sum(axis=1)<=r*r])
        if self.extra:
            E=np.array(self.extra);idx=np.nonzero(((E-c)**2).sum(axis=1)<=r*r)[0]+len(self.P);out.append(idx)
        return np.concatenate(out).astype(np.int64) if out else np.zeros(0,dtype=np.int64)
    def any_within(self,center,radius):
        return len(self.query(center,radius))>0

def bc_pairs(P,radius):
    """All index pairs (i < j) of points P (n, d) closer than radius, by a hash grid of that cell size (no n x n matrix). Returns (i, j) int arrays."""
    P=np.asarray(P,dtype=np.float64);n=len(P)
    if n<2 or radius<=0:return np.zeros(0,dtype=np.int64),np.zeros(0,dtype=np.int64)
    if n<=600:
        D=((P[:,None,:]-P[None,:,:])**2).sum(axis=2);i,j=np.nonzero(np.triu(D<radius*radius,1));return i,j
    d=P.shape[1];C=np.floor(P/radius).astype(np.int64);I=[];J=[]
    key=lambda X:sum(X[:,a]*np.int64((1,1000003,1000003**2)[a]) for a in range(d))
    k=key(C);order=np.argsort(k,kind='stable');sk=k[order]
    offs=np.stack([g.ravel() for g in np.meshgrid(*[np.arange(-1,2)]*d,indexing='ij')],axis=1)
    for off in offs:
        k2=key(C+off);a=np.searchsorted(sk,k2,'left');b=np.searchsorted(sk,k2,'right');cnt=b-a
        if not cnt.any():continue
        src=np.repeat(np.arange(n),cnt);dst=order[np.repeat(a,cnt)+np.arange(int(cnt.sum()))-np.repeat(np.cumsum(cnt)-cnt,cnt)]
        ok=src<dst;src,dst=src[ok],dst[ok];close=((P[src]-P[dst])**2).sum(axis=1)<radius*radius;I.append(src[close]);J.append(dst[close])
    if not I:return np.zeros(0,dtype=np.int64),np.zeros(0,dtype=np.int64)
    i=np.concatenate(I);j=np.concatenate(J);u=np.unique(i*np.int64(n)+j);return u//n,u%n

# ---------------------------------------------------------------- the swept-field stroke (Paint / Spray)
class BrushStroke(object):
    """One Paint stroke, processed incrementally: move(position) for each mouse position, finish() at the end. Only the new part of the path costs anything.
      * candidates: a world-fixed jittered grid in the plane of the two axes that are not the dominant axis of the surface normal where the stroke began (the ground: X and Z), one per cell of area 1 / density;
        each cell has its own hash: jitter, acceptance threshold and a key for the instance's own random numbers. The same cell gives the same numbers whatever order the stroke reaches it in.
      * the field: the distance r (in brush radii) of a candidate to the polyline of the whole stroke (not to a dab: a stroke is a ribbon with a soft edge, no dab circles, no round ends inside it);
        a candidate on the plateau of every channel is decided at once, one in a transition waits until the brush has moved a radius past it (its distance is then final) or the stroke ends,
        so the result does not depend on how fast the mouse moved or how often events arrive.
      * made when its threshold < strength x Density multiplier(r) x density noise; its Scale multiplier is returned (the tool multiplies its own scale: nothing compounds).
      * cast(origins (k, 3), direction (3,)) -> (positions (k, 3), normals (k, 3), ok (k,)) puts candidates on the surface (the tool's ray cast); spacing: no two instances, old or new,
        closer than spacing in the stroke plane (a BrushGrid, so a stroke over 100 000 instances only looks at the ones under it).
      * jitter < 1 makes a more regular layout; noise > 0 (Spatter) modulates the density with a soft value noise of about the brush size, for patchy irregular painting."""
    MAX_CELLS=40000
    def __init__(self,radius,density,spacing=0.0,seed=0,normal=(0.0,1.0,0.0),dens=None,scale=None,existing=None,cast=None,strength=1.0,noise=0.0,jitter=1.0,lift=None):
        self.R=max(float(radius),1e-4);density=max(float(density),1e-6);self.spacing=max(float(spacing),0.0);self.seed=int(seed);self.dens=dens;self.scale=scale;self.cast=cast
        self.strength=min(max(float(strength),0.0),1.0);self.noise=min(max(float(noise),0.0),1.0);self.jitter=min(max(float(jitter),0.0),1.0)
        n=np.asarray(normal,dtype=np.float64);self.axis=int(np.argmax(np.abs(n)));self.sign=1.0 if n[self.axis]>=0 else -1.0;self.ia,self.ib=[a for a in (0,1,2) if a!=self.axis]
        self.h=max(1.0/math.sqrt(density),self.R*0.02);self.inner=min([1.0]+[p['inner'] for p in (dens,scale) if p is not None]);self.lift=self.R*1.5+0.05 if lift is None else float(lift)
        ex=np.zeros((0,3)) if existing is None else np.asarray(existing,dtype=np.float64).reshape(-1,3)
        self.grid=BrushGrid(ex[:,[self.ia,self.ib]],max(self.spacing,1e-3)) if self.spacing>0 else None
        self.tail=None;self.V=[];self.H=[];self.known=set();self.pk=np.zeros(0,dtype=np.int64);self.pc=np.zeros((0,2));self.pt=np.zeros(0);self.pn=np.zeros(0,dtype=np.int64);self.made=0;self.moves=0
    def _noise(self,c):
        """A soft value noise in [-1, 1] over cells of 0.7 brush radius (bilinear between hashed corners), for the Spatter / Density Randomness."""
        s=self.R*0.7;g=c/s;i=np.floor(g).astype(np.int64);f=g-i;f=f*f*(3-2*f)
        v=lambda di,dj:bc_unit(bc_hash2(i[:,0]+di,i[:,1]+dj,self.seed,7))
        a=v(0,0)*(1-f[:,0])+v(1,0)*f[:,0];b=v(0,1)*(1-f[:,0])+v(1,1)*f[:,0];return (a*(1-f[:,1])+b*f[:,1])*2.0-1.0
    def _cells(self,a,b):
        R=self.R;h=self.h;lo=np.minimum(a,b)-R;hi=np.maximum(a,b)+R;i0,i1=int(np.floor(lo[0]/h)),int(np.floor(hi[0]/h));j0,j1=int(np.floor(lo[1]/h)),int(np.floor(hi[1]/h))
        if (i1-i0+1)*(j1-j0+1)>self.MAX_CELLS:                                                       # a jump far bigger than the brush: walk it in pieces
            L=float(np.linalg.norm(b-a));k=int(math.ceil(L/max(R,1e-9)))
            if k>1:
                for t in range(k):self._cells(a+(b-a)*(t/k),a+(b-a)*((t+1)/k))
            return
        I,J=np.meshgrid(np.arange(i0,i1+1),np.arange(j0,j1+1),indexing='ij');I=I.ravel();J=J.ravel();keys=I*1000003+J
        fresh=np.fromiter((k not in self.known for k in keys.tolist()),dtype=bool,count=len(keys))
        if not fresh.any():return
        I,J,keys=I[fresh],J[fresh],keys[fresh];jit=self.jitter
        c=np.stack([(I+0.5+jit*(bc_unit(bc_hash2(I,J,self.seed,1))-0.5))*h,(J+0.5+jit*(bc_unit(bc_hash2(I,J,self.seed,2))-0.5))*h],axis=1)
        ab=b-a;L2=float(ab@ab);t=np.clip(((c-a)@ab)/L2,0.0,1.0) if L2>1e-18 else np.zeros(len(c));near=np.linalg.norm(c-(a+np.outer(t,ab)),axis=1)<=R
        if not near.any():return
        c=c[near];keys=keys[near];I=I[near];J=J[near];self.known.update(keys.tolist());hh=bc_hash2(I,J,self.seed,3)
        self.pk=np.concatenate([self.pk,keys]);self.pc=np.concatenate([self.pc,c]);self.pt=np.concatenate([self.pt,bc_unit(hh)]);self.pn=np.concatenate([self.pn,(hh%np.uint64(2**30)).astype(np.int64)+1])
    def move(self,position):
        """The brush is at position: extend the path and decide what that settles. Returns (positions, normals, scale multipliers, keys) of the instances made now."""
        pos=np.asarray(position,dtype=np.float64);p=np.array([pos[self.ia],pos[self.ib]])
        if self.V and np.linalg.norm(p-self.V[-1])<0.06*self.R:self.tail=pos;return self._empty()          # too close to the last point to matter now; finish() still ends the path there
        self.tail=None;a=self.V[-1] if self.V else p;self.V.append(p);self.H.append(float(pos[self.axis]));self.moves+=1;self._cells(a,p);return self._resolve(False)
    def finish(self):
        """The end of the stroke: every candidate still waiting is decided with the distance it has now."""
        if self.tail is not None and self.V:
            pos=self.tail;p=np.array([pos[self.ia],pos[self.ib]]);self.tail=None
            if np.linalg.norm(p-self.V[-1])>1e-12:a=self.V[-1];self.V.append(p);self.H.append(float(pos[self.axis]));self._cells(a,p)
        return self._resolve(True) if self.V else self._empty()
    def cancel(self):
        """Forget the waiting candidates (a cancelled stroke makes nothing more)."""
        self.pk=self.pk[:0];self.pc=self.pc[:0];self.pt=self.pt[:0];self.pn=self.pn[:0]
    def _empty(self):return np.zeros((0,3)),np.zeros((0,3)),np.zeros(0),np.zeros(0,dtype=np.int64)
    def distances(self,C):
        """(normalised distance to the stroke path, height of the path there, distance to the brush) of plane points C (k, 2): the field, vectorised over the path segments near C."""
        R=self.R;V=np.array(self.V);Hh=np.array(self.H);A=V[:-1] if len(V)>1 else V;B=V[1:] if len(V)>1 else V;HA=Hh[:-1] if len(V)>1 else Hh;HB=Hh[1:] if len(V)>1 else Hh
        lo=C.min(axis=0)-R;hi=C.max(axis=0)+R;use=np.all(np.maximum(A,B)>=lo,axis=1)&np.all(np.minimum(A,B)<=hi,axis=1)
        if not use.any():use=np.ones(len(A),dtype=bool)
        A,B,HA,HB=A[use],B[use],HA[use],HB[use];AB=B-A;L2=np.maximum((AB**2).sum(axis=1),1e-18);out_r=np.empty(len(C));out_h=np.empty(len(C))
        for s in range(0,len(C),4096):                                                               # chunks keep the (candidates x segments) matrix small
            Cs=C[s:s+4096];t=np.clip(((Cs[:,None,:]-A[None])*AB[None]).sum(axis=2)/L2[None],0.0,1.0);D=np.linalg.norm(Cs[:,None,:]-(A[None]+t[:,:,None]*AB[None]),axis=2)
            k=D.argmin(axis=1);ix=np.arange(len(Cs));out_r[s:s+4096]=D[ix,k]/R;out_h[s:s+4096]=HA[k]+t[ix,k]*(HB[k]-HA[k])
        return out_r,out_h,np.linalg.norm(C-V[-1],axis=1)
    def _resolve(self,final):
        if not len(self.pk):return self._empty()
        R=self.R;C=self.pc;r,href,dh=self.distances(C)
        far=r>1.0;decide=(~far)&((r<=self.inner+1e-12)|(dh>=R)|final);keep=(~far)&(~decide)
        if far.any():self.known.difference_update(self.pk[far].tolist())                           # not under the brush (any more): it may come back when the path does
        mult=bc_multiplier(self.dens,r)*self.strength
        if self.noise>0:mult=mult*np.clip(1.0+self.noise*self._noise(C),0.0,2.0)
        acc=decide&(self.pt<mult)
        out=self._empty()
        if acc.any():
            idx=np.nonzero(acc)[0];idx=idx[np.argsort(self.pk[idx])];ms=bc_multiplier(self.scale,r[idx])
            O=np.zeros((len(idx),3));O[:,self.ia]=C[idx,0];O[:,self.ib]=C[idx,1];O[:,self.axis]=href[idx]+self.sign*self.lift;d=np.zeros(3);d[self.axis]=-self.sign
            if self.cast is not None:P,N,ok=self.cast(O,d)
            else:P=O.copy();P[:,self.axis]=href[idx];N=np.tile(-d,(len(idx),1));ok=np.ones(len(idx),dtype=bool)
            P=np.asarray(P,dtype=np.float64);N=np.asarray(N,dtype=np.float64);good=[]
            for q in range(len(idx)):
                if not ok[q]:continue
                if self.grid is not None:
                    pp=P[q,[self.ia,self.ib]]
                    if self.grid.any_within(pp,self.spacing*(1-1e-9)):continue                     # the Spacing is measured in the plane of the stroke, so Sit On Surface and Offset do not matter
                    self.grid.add(pp[None])
                good.append(q)
            if good:
                g=np.array(good);out=(P[g],N[g],ms[g],self.pn[idx[g]]);self.made+=len(g)
        self.pk,self.pc,self.pt,self.pn=self.pk[keep],self.pc[keep],self.pt[keep],self.pn[keep];return out

class BrushDabs(object):
    """Distance-based dabs for the editing brushes: move(position) returns the dab centres every `step` along the path since the last call (the first position is a dab), so the
    effect per unit of path is the same whether the mouse is slow or fast and whatever the event rate."""
    def __init__(self,step):
        self.step=max(float(step),1e-6);self.last=None;self.carry=0.0;self.count=0;self.prev=None
    def move(self,position):
        p=np.asarray(position,dtype=np.float64)
        if self.last is None:self.last=p.copy();self.prev=p.copy();self.count+=1;return [p.copy()]
        out=[];a=self.prev;seg=p-a;L=float(np.linalg.norm(seg))
        if L<=1e-12:return out
        d=self.step-self.carry
        while d<=L+1e-12:
            q=a+seg*(d/L);out.append(q);self.count+=1;d+=self.step
        self.carry=L-(d-self.step);self.prev=p.copy();self.last=out[-1] if out else self.last;return out
    def direction(self):
        """The direction of travel of the last dab (unit), or None."""
        if self.prev is None or self.last is None:return None
        v=self.prev-self.last;n=np.linalg.norm(v);return v/n if n>1e-12 else None

# ---------------------------------------------------------------- quaternions (x, y, z, w), the convention of both tools
def bc_qmul(a,b):
    a=np.asarray(a,dtype=np.float64);b=np.asarray(b,dtype=np.float64);ax,ay,az,aw=np.moveaxis(a,-1,0);bx,by,bz,bw=np.moveaxis(b,-1,0)
    return np.stack([aw*bx+ax*bw+ay*bz-az*by,aw*by-ax*bz+ay*bw+az*bx,aw*bz+ax*by-ay*bx+az*bw,aw*bw-ax*bx-ay*by-az*bz],axis=-1)

def bc_qrot(q,v):
    """Vectors v turned by quaternions q (broadcast)."""
    q=np.asarray(q,dtype=np.float64);v=np.asarray(v,dtype=np.float64);u=q[...,:3];w=q[...,3:4];t=2.0*np.cross(u,v);return v+w*t+np.cross(u,t)

def bc_qaxis(axis,angle):
    """Quaternions of angles (radians) about unit axes (broadcast)."""
    axis=np.asarray(axis,dtype=np.float64);angle=np.asarray(angle,dtype=np.float64);s=np.sin(angle*0.5)[...,None];return np.concatenate([axis*s,np.cos(angle*0.5)[...,None]],axis=-1)

def bc_qnorm(q):
    q=np.asarray(q,dtype=np.float64);return q/np.maximum(np.linalg.norm(q,axis=-1,keepdims=True),1e-12)

# ---------------------------------------------------------------- the editing brushes: pure functions over arrays of the instances under one dab
def bc_under(P,center,radius,plane=None):
    """Indices of the points within radius of center and their r = distance / radius. plane: (ia, ib) to measure in a plane (the stroke plane), else in 3D."""
    P=np.asarray(P,dtype=np.float64);c=np.asarray(center,dtype=np.float64)
    if not len(P):return np.zeros(0,dtype=np.int64),np.zeros(0)
    D=P[:,list(plane)]-c[list(plane)] if plane is not None else P-c;d=np.sqrt((D*D).sum(axis=1));idx=np.nonzero(d<=radius)[0];return idx,d[idx]/max(radius,1e-12)

def bc_erase(ids,w,strength=1.0,seed=0,dab=0,soft=False):
    """Which of the instances under a dab go (bool). Hard: every one with weight > 0 (strength 1) or those whose hash is below strength (a thinner sweep);
    soft (thinning): an instance goes when its hash for this dab is below strength x weight, so the rim thins less than the middle and repeated dabs keep thinning gently.
    Ids decide, not array order: survivors keep their ids."""
    ids=np.asarray(ids,dtype=np.int64);w=np.asarray(w,dtype=np.float64);s=min(max(float(strength),0.0),1.0)
    if not soft:return (w>0)&(bc_unit(bc_hash1(ids,seed,11))<s+1e-12)
    return bc_unit(bc_hash1(ids*np.int64(1000003)+int(dab),seed,12))<s*w

def bc_relax(P,w,target,strength=1.0,iterations=4,fixed=None):
    """Even out the spacing of points P (k, d) (the instances under a dab and their neighbours): pairs closer than target are pushed apart along the line between them by half of the shortfall
    x strength x their weight (fixed points and weight 0 do not move: the neighbours outside the brush hold the boundary, so the population keeps its footprint). Pairs come from a hash grid, never
    an all-pairs matrix. Returns the new positions."""
    P=np.asarray(P,dtype=np.float64).copy();w=np.clip(np.asarray(w,dtype=np.float64),0.0,1.0)*min(max(float(strength),0.0),1.0)
    if fixed is not None:w=np.where(fixed,0.0,w)
    if len(P)<2 or target<=0 or not np.any(w>0):return P
    target=float(target)*1.04                                                                   # a little past the target: the iteration settles just below its goal, so the pairs end at or above the spacing
    for _ in range(max(1,int(iterations))):
        i,j=bc_pairs(P,target)
        if not len(i):break
        d=P[j]-P[i];L=np.linalg.norm(d,axis=1);short=np.maximum(target-L,0.0);u=d/np.maximum(L,1e-12)[:,None]
        same=L<1e-12
        if same.any():ang=bc_unit(bc_hash1(i[same]*7+j[same],3,5))*2*np.pi;u[same]=0.0;u[same,0]=np.cos(ang);u[same,-1]=np.sin(ang)        # two at one spot: a fixed random direction
        push=np.zeros_like(P);np.add.at(push,i,-u*(0.5*short)[:,None]);np.add.at(push,j,u*(0.5*short)[:,None]);P=P+push*w[:,None]
    return P

def bc_relax_target(P,density=None):
    """A spacing target for Relax when the tool has none: the mean nearest-neighbour distance of the points (or 1 / sqrt(density))."""
    if density:return 1.0/math.sqrt(max(density,1e-9))
    P=np.asarray(P,dtype=np.float64)
    if len(P)<2:return 0.0
    g=BrushGrid(P,max(np.ptp(P,axis=0).max()/max(math.sqrt(len(P)),1.0),1e-6));nn=[]
    for k in range(min(len(P),400)):
        r=g.cell
        while True:
            idx=g.query(P[k],r);idx=idx[idx!=k]
            if len(idx) or r>1e9:break
            r*=2
        if len(idx):nn.append(np.sqrt(((P[idx]-P[k])**2).sum(axis=1)).min())
    return float(np.mean(nn)) if nn else 0.0

BC_SCALE_MODES=('grow','shrink','set','smooth','restore')
def bc_scale(S,w,mode='grow',amount=0.1,target=1.0,base=None,neighbors=None,lo=1e-3,hi=1e3):
    """New scales of the instances under a dab (S (k,) or (k, 3), weights w): grow / shrink multiply by exp(+/- amount x w) (relative, symmetric: a grow then a shrink is the identity),
    set eases towards target, smooth towards the mean of neighbors (their scales), restore towards base (the scale before any painting). Kept inside [lo, hi]: never negative, never zero."""
    S=np.asarray(S,dtype=np.float64);w=np.clip(np.asarray(w,dtype=np.float64),0.0,1.0);a=float(amount);ws=w.reshape((-1,)+(1,)*(S.ndim-1))
    if mode=='grow':out=S*np.exp(a*ws)
    elif mode=='shrink':out=S*np.exp(-a*ws)
    elif mode=='set':out=S+(float(target)-S)*np.clip(a*ws,0.0,1.0)
    elif mode=='smooth':m=np.mean(S if neighbors is None else np.asarray(neighbors,dtype=np.float64),axis=0);out=S+(m-S)*np.clip(a*ws,0.0,1.0)
    elif mode=='restore':out=S+(np.asarray(S if base is None else base,dtype=np.float64)-S)*np.clip(a*ws,0.0,1.0)
    else:raise ValueError('unknown scale mode %r'%mode)
    return np.clip(out,lo,hi)

BC_PUSH_MODES=('push','attract','drag','smooth')
def bc_push(P,center,w,radius,mode='push',amount=0.25,direction=None,plane=None):
    """New positions of the instances under a dab: push away from the centre, attract towards it (never past it), drag along the stroke direction, or smooth towards their mean.
    The move is amount x radius x weight per dab, in the stroke plane (plane = (ia, ib); the tool casts the result back onto the surface). Returns the new positions."""
    P=np.asarray(P,dtype=np.float64).copy();c=np.asarray(center,dtype=np.float64);w=np.clip(np.asarray(w,dtype=np.float64),0.0,1.0);step=float(amount)*float(radius)
    ax=list(plane) if plane is not None else [0,1,2];D=np.zeros_like(P);D[:,ax]=P[:,ax]-c[ax];L=np.linalg.norm(D,axis=1)
    if mode=='push':
        u=D/np.maximum(L,1e-12)[:,None];zero=L<1e-12
        if zero.any():u[zero]=0.0;u[np.ix_(np.nonzero(zero)[0],[ax[0]])]=1.0
        P=P+u*(step*w)[:,None]
    elif mode=='attract':
        move=np.minimum(step*w,L*0.9);P=P-D/np.maximum(L,1e-12)[:,None]*move[:,None]
    elif mode=='drag':
        if direction is None:return P
        dv=np.zeros(3);dv[ax]=np.asarray(direction,dtype=np.float64)[ax];n=np.linalg.norm(dv)
        if n>1e-12:P=P+(dv/n)[None]*(step*w)[:,None]
    elif mode=='smooth':
        m=P.mean(axis=0);P=P+(m-P)*np.clip(float(amount)*w,0.0,1.0)[:,None]*0.5
    else:raise ValueError('unknown push mode %r'%mode)
    return P

BC_ORIENT_MODES=('comb','toward','away','random','restore','smooth')
def bc_orient(Q,up,w,mode='comb',amount=0.5,direction=None,center=None,P=None,ids=None,seed=0,base=None):
    """New orientations (k, 4) of the instances under a dab, turned about their own up axis (so surface alignment stays): comb turns their heading (+Z) towards the stroke direction,
    toward / away towards or away from the centre, random adds a random turn (by id, the same every time), restore eases back to base, smooth towards the mean heading.
    The turn is the angle to the goal x amount x weight per dab (no overshoot)."""
    Q=bc_qnorm(Q);w=np.clip(np.asarray(w,dtype=np.float64),0.0,1.0);k=len(Q)
    if not k:return Q
    U=bc_qrot(Q,np.asarray(up,dtype=np.float64)) if np.ndim(up)==1 else np.asarray(up,dtype=np.float64);U=U/np.maximum(np.linalg.norm(U,axis=1,keepdims=True),1e-12)
    if mode=='restore':
        if base is None:return Q
        B=bc_qnorm(base);dot=np.sum(Q*B,axis=1);B=np.where(dot[:,None]<0,-B,B);t=np.clip(float(amount)*w,0.0,1.0)[:,None];return bc_qnorm(Q*(1-t)+B*t)
    F=bc_qrot(Q,np.array([0.0,0.0,1.0]));F=F-U*np.sum(F*U,axis=1,keepdims=True)
    if mode=='random':
        ang=(bc_unit(bc_hash1(np.arange(k) if ids is None else ids,seed,21))*2-1)*np.pi*float(amount)*w;return bc_qnorm(bc_qmul(bc_qaxis(U,ang),Q))
    if mode=='comb':G=np.tile(np.asarray(direction,dtype=np.float64),(k,1)) if direction is not None else None
    elif mode in ('toward','away'):G=(np.asarray(center,dtype=np.float64)[None]-np.asarray(P,dtype=np.float64))*(1.0 if mode=='toward' else -1.0)
    elif mode=='smooth':G=np.tile(F.mean(axis=0),(k,1))
    else:raise ValueError('unknown orient mode %r'%mode)
    if G is None:return Q
    G=G-U*np.sum(G*U,axis=1,keepdims=True);gn=np.linalg.norm(G,axis=1);fn=np.linalg.norm(F,axis=1);ok=(gn>1e-9)&(fn>1e-9)
    ang=np.zeros(k);Fu=F/np.maximum(fn,1e-12)[:,None];Gu=G/np.maximum(gn,1e-12)[:,None]
    ang[ok]=np.arctan2(np.sum(np.cross(Fu[ok],Gu[ok])*U[ok],axis=1),np.sum(Fu[ok]*Gu[ok],axis=1))
    return bc_qnorm(bc_qmul(bc_qaxis(U,ang*np.clip(float(amount)*w,0.0,1.0)),Q))

def bc_replace(ids,w,rows,weights,strength=1.0,seed=0,dab=0):
    """Prototype swaps under a dab: (which instances change (bool), their new rows). An instance changes when its hash for this dab is below strength x weight; its new row is drawn from rows
    by weights with a hash of its id (the same id always draws the same row: painting again does not shuffle it again). Position, rotation and scale are not touched."""
    ids=np.asarray(ids,dtype=np.int64);rows=np.asarray(rows);wt=np.maximum(np.asarray(weights,dtype=np.float64),0.0)
    if not len(ids) or not len(rows) or wt.sum()<=0:return np.zeros(len(ids),dtype=bool),np.zeros(len(ids),dtype=rows.dtype if len(rows) else np.int64)
    go=bc_unit(bc_hash1(ids*np.int64(1000003)+int(dab),seed,31))<min(max(float(strength),0.0),1.0)*np.asarray(w,dtype=np.float64)
    cdf=np.cumsum(wt)/wt.sum();pick=np.searchsorted(cdf,bc_unit(bc_hash1(ids,seed,32)),side='right');return go,rows[np.minimum(pick,len(rows)-1)]

def bc_frame(normal):
    """Two unit vectors on the plane of a normal (the tangent frame both tools use)."""
    n=np.asarray(normal,dtype=np.float64);n=n/np.linalg.norm(n);helper=np.array([0.0,0.0,1.0]) if abs(n[1])>0.9 else np.array([0.0,1.0,0.0])
    u=np.cross(helper,n);u/=np.linalg.norm(u);return u,np.cross(n,u)

def bc_clone_capture(P,Q,S,proto,center,normal=(0.0,1.0,0.0)):
    """A clone source: the instances' transforms relative to center, in the frame of the normal there (so the arrangement can be stamped on any slope). Returns a dict."""
    u,v=bc_frame(normal);n=np.asarray(normal,dtype=np.float64);n=n/np.linalg.norm(n);z=np.cross(u,n);M=np.stack([u,n,z])          # rows: local x (u), y (normal), z (u x normal): right handed
    D=np.asarray(P,dtype=np.float64)-np.asarray(center,dtype=np.float64)
    from_frame=_frame_quat(u,n,z)
    return dict(off=D@M.T,quat=bc_qmul(np.tile(_qconj(from_frame),(len(D),1)),bc_qnorm(Q)),scale=np.asarray(S,dtype=np.float64).copy(),proto=np.asarray(proto).copy(),radius=float(np.max(np.linalg.norm(D,axis=1))) if len(D) else 0.0)

def bc_clone_place(clone,center,normal=(0.0,1.0,0.0),yaw=0.0,scale=1.0):
    """World transforms of a clone stamped at center on the frame of normal, turned by yaw degrees about it and scaled: (positions, quaternions, scales, protos)."""
    u,v=bc_frame(normal);n=np.asarray(normal,dtype=np.float64);n=n/np.linalg.norm(n);turn=bc_qaxis(n,math.radians(float(yaw)));F=bc_qmul(turn,_frame_quat(u,n,np.cross(u,n)))
    off=np.asarray(clone['off'],dtype=np.float64)*float(scale);world=np.asarray(center,dtype=np.float64)+bc_qrot(np.tile(F,(len(off),1)),off)
    return world,bc_qnorm(bc_qmul(np.tile(F,(len(off),1)),clone['quat'])),np.asarray(clone['scale'],dtype=np.float64)*float(scale),clone['proto']

def _qconj(q):
    q=np.asarray(q,dtype=np.float64).copy();q[...,:3]*=-1;return q

def _frame_quat(x,y,z):
    """The quaternion of the rotation whose columns are the unit axes x, y, z."""
    m=np.stack([x,y,z],axis=1);t=np.trace(m)
    if t>0:s=math.sqrt(t+1.0)*2;return np.array([(m[2,1]-m[1,2])/s,(m[0,2]-m[2,0])/s,(m[1,0]-m[0,1])/s,0.25*s])
    i=int(np.argmax(np.diag(m)))
    if i==0:s=math.sqrt(1.0+m[0,0]-m[1,1]-m[2,2])*2;return np.array([0.25*s,(m[0,1]+m[1,0])/s,(m[0,2]+m[2,0])/s,(m[2,1]-m[1,2])/s])
    if i==1:s=math.sqrt(1.0+m[1,1]-m[0,0]-m[2,2])*2;return np.array([(m[0,1]+m[1,0])/s,0.25*s,(m[1,2]+m[2,1])/s,(m[0,2]-m[2,0])/s])
    s=math.sqrt(1.0+m[2,2]-m[0,0]-m[1,1])*2;return np.array([(m[0,2]+m[2,0])/s,(m[1,2]+m[2,1])/s,0.25*s,(m[1,0]-m[0,1])/s])

# ---------------------------------------------------------------- the brush registry and the viewer helpers
# One registry for both tools: the tool lists the brushes it supports (Stamp has Place / Group / Edit of its own, Arraytron the Mask brush). key: (label, colour, radial position, hint rows)
BC_COLORS={'paint':(0.25,0.85,0.65,1.0),'erase':(1.0,0.55,0.15,1.0),'relax':(0.35,0.6,1.0,1.0),'scale':(0.2,0.9,0.95,1.0),'push':(0.85,0.5,1.0,1.0),'orient':(1.0,0.85,0.3,1.0),
           'replace':(0.95,0.4,0.7,1.0),'clone':(0.6,0.95,0.35,1.0),'place':(0.2,1.0,0.4,1.0),'delete':(1.0,0.25,0.2,1.0),'group':(0.9,0.9,0.9,1.0),'repaint':(0.3,0.6,1.0,1.0),'mask':(0.3,1.0,0.4,1.0),
           'warn':(1.0,0.75,0.2,1.0),'select':(1.0,0.85,0.2,1.0),'inner':(1.0,1.0,1.0,0.55),'scale_ring':(0.2,0.9,0.95,0.6)}
BC_BRUSHES={
 'paint':('Paint','N',[('Paint','LMB drag'),('Erase','Ctrl LMB drag'),('Radius','Shift wheel  [ ]'),('Density','Ctrl wheel')],
          [('Falloff preset','F'),('Spray / Spatter','Shift F'),('Strength','- =')]),
 'erase':('Erase','NE',[('Erase (soft thinning with Shift)','LMB drag'),('Radius','Shift wheel  [ ]'),('Strength','Ctrl wheel')],[('Only the current prototype','P')]),
 'relax':('Relax','W',[('Even out the spacing','LMB drag'),('Radius','Shift wheel  [ ]'),('Strength','Ctrl wheel')],[('Keep the footprint (rim fixed)','default')]),
 'scale':('Grow / Shrink','SW',[('Grow','LMB drag'),('Shrink','Ctrl LMB drag'),('Smooth sizes','Shift LMB drag'),('Amount','Ctrl wheel')],[('Mode: Sculpt settings (grow, shrink, set, smooth)','')]),
 'push':('Push / Attract','E',[('Push away','LMB drag'),('Attract','Ctrl LMB drag'),('Drag along the stroke','Shift LMB drag'),('Amount','Ctrl wheel')],[]),
 'replace':('Replace','SE',[('Swap prototypes (keeps placement)','LMB drag'),('Strength','Ctrl wheel')],[('From the working set / bank weights','')]),
 'orient':('Orient / Comb','NW',[('Comb along the stroke','LMB drag'),('Random heading','Ctrl LMB drag'),('Restore (Arraytron) / smooth (Stamp)','Shift LMB drag'),('Amount','Ctrl wheel')],[('Mode: Sculpt settings','')]),
 'clone':('Clone','S',[('Pick the source (Ctrl click)','Ctrl LMB'),('Stamp copies','LMB / drag'),('Turn / scale the copy','Shift wheel / Ctrl wheel')],[('Random heading per copy','R')]),
}
BC_HUD_LEVELS=('minimal','standard','expanded','hidden')
BC_RADIAL=(('n','paint'),('nw','relax'),('ne','erase'),('w','scale'),('e','push'),('sw','clone'),('se','replace'))               # the radial menu (C): the main brushes; south is More (Orient and the tool's own brushes)

def bc_radial_layout(available,more=()):
    """{direction: brush key} of the radial menu for the brushes a tool has, and the list of the More submenu (the rest, then the tool's extras). Directions: n ne e se s sw w nw."""
    main={d:k for d,k in BC_RADIAL if k in available};rest=[k for k in available if k not in main.values()]+[k for k in more if k not in available]
    return main,rest

def bc_cursor(center,normal,radius,inners=(),segments=64,project=None,lift=0.01):
    """The cursor as polylines: the outer ring (the radius), a ring at each inner radius given (the start of a falloff), a small centre cross and a normal tick. project(points (n, 3))
    -> points puts the rings onto the surface (they then follow slopes). Returns a list of (n, 3) arrays."""
    c=np.asarray(center,dtype=np.float64);n=np.asarray(normal,dtype=np.float64);n=n/max(np.linalg.norm(n),1e-12);u,v=bc_frame(n);a=np.linspace(0,2*np.pi,segments+1)
    ring=lambda R:c[None]+R*(np.cos(a)[:,None]*u[None]+np.sin(a)[:,None]*v[None])
    def lay(pts):
        if project is not None:
            try:pts=np.asarray(project(pts),dtype=np.float64)
            except Exception:pass
        return pts+n*lift*max(radius,1e-3)
    out=[lay(ring(radius))]
    for r in inners:
        if 0.03<r<0.985:out.append(lay(ring(radius*r)))
    s=radius*0.06;p0=c+n*lift*max(radius,1e-3);out+=[np.array([p0-u*s,p0+u*s]),np.array([p0-v*s,p0+v*s]),np.array([p0,p0+n*radius*0.12])]
    return out

def bc_profile_lines(center,normal,radius,profile,side=1.0,height=0.35,lift=0.02):
    """The falloff profile standing on the surface along a spoke (density to one side, scale to the other): the height is the multiplier at that distance. Returns polylines."""
    if profile is None:return []
    c=np.asarray(center,dtype=np.float64);n=np.asarray(normal,dtype=np.float64);n=n/max(np.linalg.norm(n),1e-12);u,v=bc_frame(n);rs=np.linspace(0.0,1.0,17);vals=bc_multiplier(profile,rs)
    k=height*radius/max(1.0,float(np.max(vals)));base=c[None]+n*lift*radius+u[None]*side*radius*rs[:,None];top=base+n[None]*(vals*k)[:,None]
    return [top,base,np.array([base[0],top[0]]),np.array([base[-1],top[-1]])]

def bc_polylines_arrays(lines):
    """(points (n, 3) float32, polygon vertex lists) of polylines: what a tool needs to build one hou.Geometry of open polygons with a single bulk write."""
    pts=np.concatenate([np.asarray(l,dtype=np.float32).reshape(-1,3) for l in lines]) if lines else np.zeros((0,3),dtype=np.float32);polys=[];k=0
    for l in lines:
        m=len(l);polys.append(list(range(k,k+m)));k+=m
    return pts,polys

def bc_hud_rows(brush,level):
    """The hint rows of the HUD for one brush at one level: minimal shows the first row, standard the brush's rows, expanded adds the extra rows."""
    b=BC_BRUSHES.get(brush)
    if b is None or level=='hidden':return []
    rows=list(b[2])
    if level=='minimal':return rows[:1]
    if level=='expanded':rows+=list(b[3])
    return rows

BC_PREFS_DEFAULT={'hud':'standard','cursor_opacity':1.0,'compact':False,'preview_budget':20000}
def bc_prefs_path(home):
    return os.path.join(home,'arraytron_brush_prefs.json')

def bc_prefs_load(path):
    """The brush preferences shared by both tools (HUD level, cursor opacity, compact cursor, preview budget): a small JSON file in the Houdini user folder; defaults when missing or unreadable."""
    out=dict(BC_PREFS_DEFAULT)
    try:
        with open(path,'r',encoding='utf8') as f:data=json.load(f)
        if isinstance(data,dict):out.update({k:data[k] for k in BC_PREFS_DEFAULT if k in data})
    except Exception:pass
    if out['hud'] not in BC_HUD_LEVELS:out['hud']='standard'
    return out

def bc_prefs_save(path,prefs):
    try:
        os.makedirs(os.path.dirname(path),exist_ok=True)
        with open(path,'w',encoding='utf8') as f:json.dump({k:prefs.get(k,v) for k,v in BC_PREFS_DEFAULT.items()},f,indent=1)
        return True
    except Exception:return False

def bc_next_hud(level):
    """The HUD level after this one (H cycles minimal, standard, expanded, hidden)."""
    i=BC_HUD_LEVELS.index(level) if level in BC_HUD_LEVELS else 1;return BC_HUD_LEVELS[(i+1)%len(BC_HUD_LEVELS)]

class BrushTimer(object):
    """Throttles live parameter writes during a stroke: due() is True at most every `interval` seconds and never more than a third of the time (a write costs as long as the data is long)."""
    def __init__(self,interval=0.05):
        self.interval=float(interval);self.last=0.0;self.cost=0.0
    def due(self):
        return time.time()-self.last>=max(self.interval,2.0*self.cost)
    def wrote(self,started):
        self.cost=time.time()-started;self.last=time.time()
