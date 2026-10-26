# Noise family for the Mask (v1.25.0): the Mask Source Noise can use the same fifteen noise types as the Noise Positional Shift (Perlin, Simplex, Random, Curl, Value, Alligator, Worley,
# Voronoi, Ridged, Billow, Turbulence, FBM, Domain Warp, Flow, Periodic). Pure numpy, so the Mask and the Visualize display evaluate it at any position. The patterns follow the same ideas as
# the VEX of the Noise stage but are not bit for bit the same. Type 4 (Value) is the original fractal value noise of the Mask, unchanged. Appended after the Mask module (uses scatter_hash,
# _lattice, value_noise and fbm_noise of it).
NOISE_TYPES=('Perlin','Simplex','Random (per point)','Curl (flowing)','Value (smooth)','Alligator (irregular cells)','Worley / Cellular','Voronoi (cell borders)','Ridged Multifractal','Billow (puffy)','Turbulence','FBM (multiscale)','Domain Warp','Flow (evolving)','Periodic (tiling)')

def _grad(ix,iy,iz,seed):
    key=((ix.astype(np.int64)*1000003+iy.astype(np.int64))*1000033+iz.astype(np.int64)).astype(np.uint64)
    g=np.column_stack([scatter_hash(key,seed,11),scatter_hash(key,seed,12),scatter_hash(key,seed,13)])*2.0-1.0
    return g/np.maximum(np.linalg.norm(g,axis=1),1e-9)[:,None]

def gradient_noise(p,seed=1,period=None):
    """Perlin style gradient noise in about -1..1 (p: (N,3)). period: a whole number of lattice cells after which the pattern repeats (None: no repeat)."""
    p=np.asarray(p,dtype=np.float64);i=np.floor(p);f=p-i;u=f*f*f*(f*(f*6-15)+10);out=np.zeros(len(p))
    for dx in (0,1):
        for dy in (0,1):
            for dz in (0,1):
                c=np.column_stack([i[:,0]+dx,i[:,1]+dy,i[:,2]+dz])
                if period is not None:c=np.mod(c,period)
                g=_grad(c[:,0],c[:,1],c[:,2],seed);d=f-np.array([dx,dy,dz])
                w=(u[:,0] if dx else 1-u[:,0])*(u[:,1] if dy else 1-u[:,1])*(u[:,2] if dz else 1-u[:,2])
                out+=w*np.einsum('ij,ij->i',g,d)
    return np.clip(out*1.6,-1.0,1.0)

_ROT=np.array([[0.36,0.48,-0.8],[-0.8,0.6,0.0],[0.48,0.64,0.6]])               # a fixed turn: Simplex samples the gradient noise on turned, skewed coordinates
def simplex_like(p,seed=1):return gradient_noise(np.asarray(p)@_ROT.T*1.15+np.asarray(p).sum(axis=1,keepdims=True)*0.33,seed+5)

def worley(p,seed=1):
    """(F1, F2): the distances to the nearest and the second nearest jittered feature point."""
    p=np.asarray(p,dtype=np.float64);i=np.floor(p);f1=np.full(len(p),9.0);f2=np.full(len(p),9.0)
    for dz in (-1,0,1):
        for dy in (-1,0,1):
            for dx in (-1,0,1):
                c=i+np.array([dx,dy,dz]);key=((c[:,0].astype(np.int64)*1000003+c[:,1].astype(np.int64))*1000033+c[:,2].astype(np.int64)).astype(np.uint64)
                j=np.column_stack([scatter_hash(key,seed,21),scatter_hash(key,seed,22),scatter_hash(key,seed,23)]);d=np.linalg.norm(c+j-p,axis=1)
                f2=np.where(d<f1,f1,np.where(d<f2,d,f2));f1=np.minimum(f1,d)
    return f1,f2

def curl_magnitude(p,seed=1):
    """The size of the curl of a gradient-noise vector field, stretched to -1..1."""
    p=np.asarray(p,dtype=np.float64);e=1e-3;off=(np.array([31.4,17.7,5.3]),np.array([9.2,43.1,27.9]))
    def field(q):return np.column_stack([gradient_noise(q,seed),gradient_noise(q+off[0],seed+1),gradient_noise(q+off[1],seed+2)])
    d=[(field(p+np.eye(3)[a]*e)-field(p-np.eye(3)[a]*e))/(2*e) for a in range(3)]            # d[a] = dF/dx_a
    curl=np.column_stack([d[1][:,2]-d[2][:,1],d[2][:,0]-d[0][:,2],d[0][:,1]-d[1][:,0]])
    return np.clip(np.linalg.norm(curl,axis=1)*0.45,0.0,1.0)*2.0-1.0

def noise_layer(kind,q,seed=1,period=None,rot=0.0):
    """One layer of the noise `kind` at the positions q (N,3), in -1..1."""
    q=np.asarray(q,dtype=np.float64)
    if kind==0:return gradient_noise(q,seed)
    if kind==1:return simplex_like(q,seed)
    if kind==3:return curl_magnitude(q,seed)
    if kind==4:return value_noise(q,seed)*2.0-1.0
    if kind==5:return 1.0-2.0*np.clip(np.abs(gradient_noise(q,seed))/0.18,0.0,1.0)**2          # thin irregular veins, like cracked skin
    if kind in (6,7):
        f1,f2=worley(q,seed)
        return 1.0-2.0*np.clip(f1,0.0,1.0) if kind==6 else 1.0-2.0*np.clip((f2-f1)*3.0,0.0,1.0)
    if kind==8:return 1.0-2.0*np.abs(gradient_noise(q,seed))
    if kind==9:return 2.0*np.abs(value_noise(q,seed)*2.0-1.0)-1.0
    if kind==10:return 2.0*np.abs(simplex_like(q,seed))-1.0
    if kind==11:return gradient_noise(q+np.array([seed*0.31,seed*0.17,seed*0.23]),seed+3)
    if kind==12:
        w=np.column_stack([gradient_noise(q*0.7+np.array([5.2,1.3,8.1]),seed),gradient_noise(q*0.7+np.array([9.7,2.8,3.4]),seed),gradient_noise(q*0.7+np.array([1.9,7.5,6.2]),seed)])
        return gradient_noise(q+w*1.2,seed+1)
    if kind==13:
        c,s=math.cos(rot+0.6),math.sin(rot+0.6);x=q[:,0]*c-q[:,1]*s;y=q[:,0]*s+q[:,1]*c;return gradient_noise(np.column_stack([x,y,q[:,2]+rot]),seed+9)
    if kind==14:return gradient_noise(q,seed,period)
    raise ValueError('unknown noise type %s'%kind)

def noise_field(kind,P,frequency,offset,octaves,roughness,seed,period=4.0,ids=None):
    """The mask noise in 0..1 before Contrast: type 4 is the original fractal value noise; type 2 is a random number per point (keyed on its id); the others are fractal sums of noise_layer
    (octave k has frequency x2^k and amplitude roughness^k)."""
    P=np.asarray(P,dtype=np.float64)
    if kind==4:return fbm_noise(P,frequency,offset,octaves,roughness,seed)
    if kind==2:return scatter_hash(np.arange(len(P)) if ids is None else np.asarray(ids),seed,31)
    q=P*frequency+np.asarray(offset,dtype=np.float64);cells=max(1.0,math.floor(period*frequency+0.5));total=0.0;amp=1.0;value=np.zeros(len(P))
    for k in range(max(1,int(octaves))):
        value+=amp*noise_layer(kind,q*(2.0**k),seed+k,cells*(2.0**k),float(offset[0]) if len(offset) else 0.0);total+=amp;amp*=roughness
    return np.clip((value/total+1.0)*0.5,0.0,1.0)
