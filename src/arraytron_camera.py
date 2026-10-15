# Camera-aware controls, LOD / proxy prototypes and extended primvars (v0.9.0). Appended to the PythonModule; the Python LOP camera_optimize
# (src/camera_optimize.py) calls these functions. The pure numpy functions (frustum tests, density, LOD levels) are tested without a stage.
# Everything is reversible and USD-native: instances are hidden through invisibleIds (never deleted) and level of detail is a change of protoIndices
# to LOD prototypes that sit after the hero prototypes in the PointInstancer's prototype list. With the Camera section off nothing changes.
import numpy as np

LOD_LEVELS=('LOD 1','LOD 2','Proxy')
PRIMVAR_TOGGLES=(('pv_id','arraytron_id'),('pv_proto','prototype_id'),('pv_random','random'),('pv_mask','mask'),('pv_density','density'),('pv_cluster','cluster'),('pv_srcid','source_id'))

# ---------------------------------------------------------------- LOD prototypes (bank rows)
def lod_entries(asset):
    """[(row, level 1..3, prim path)] for every enabled bank row that has LOD 1 / LOD 2 / Proxy prims, in row then level order."""
    out=[]
    for r in bank_rows(asset):
        for level,name in ((1,'proto_lod1'),(2,'proto_lod2'),(3,'proto_proxy')):
            p=asset.parm('%s%d'%(name,r))
            if p is not None and p.eval().strip():out.append((r,level,p.eval().strip()))
    return out

def lod_table(asset,entries=None):
    """{hero ordinal: {level: prototype index}} for the PointInstancer's prototype list: the heroes first (bank order), then the LOD prims in lod_entries order."""
    heroes=resolve(asset) if entries is None else entries;rows=[e['row'] for e in heroes];n=len(heroes);table={k:{} for k in range(n)}
    for j,(row,level,path) in enumerate(lod_entries(asset)):
        if row in rows:table[rows.index(row)][level]=n+j
    return table

def check_lod_paths(asset,heroes):
    """Every LOD prim must be distinct from the heroes and from each other."""
    seen={e['path']:'prototype %d'%e['row'] for e in heroes}
    for row,level,path in lod_entries(asset):
        if path in seen:raise hou.NodeError('Prototype %d %s (%s) is already used by %s.'%(row,LOD_LEVELS[level-1],path,seen[path]))
        seen[path]='prototype %d %s'%(row,LOD_LEVELS[level-1])

def lod_pattern_extra(asset):
    return [path for row,level,path in lod_entries(asset)]

def available_level(wanted,have):
    """Highest defined level <= wanted (0 = the hero); a missing level falls back to the next finer one."""
    for level in range(min(wanted,3),0,-1):
        if level in have:return level
    return 0

# ---------------------------------------------------------------- camera maths
def view_space(P,view):
    """World positions (N,3) to view space with a row-vector 4x4 view matrix (the USD / Gf convention): +x right, +y up, the camera looks along -z."""
    P=np.asarray(P,dtype=np.float64);h=np.column_stack([P,np.ones(len(P))]);return (h@np.asarray(view,dtype=np.float64))[:,:3]

def frustum_outside(v,radius,hx,hy,near,far,margin=0.0,orthographic=False):
    """True where a sphere (view-space centre v (N,3), radius (N,)) lies completely outside the camera frustum of half-extents hx, hy (the tangent of the half
    field of view for a perspective camera, the half width / height for an orthographic one) and clipping range near..far, with the side planes opened by
    `margin` (a fraction of the half-extents). Points behind the camera are outside too."""
    v=np.asarray(v,dtype=np.float64);r=np.asarray(radius,dtype=np.float64);depth=-v[:,2];hx=hx*(1.0+margin);hy=hy*(1.0+margin)
    if orthographic:
        out=(np.abs(v[:,0])>hx+r)|(np.abs(v[:,1])>hy+r)
    else:
        nx=np.sqrt(1.0+hx*hx);ny=np.sqrt(1.0+hy*hy)
        out=((hx*depth-v[:,0])/nx<-r)|((hx*depth+v[:,0])/nx<-r)|((hy*depth-v[:,1])/ny<-r)|((hy*depth+v[:,1])/ny<-r)
    return out|(depth+r<near)|(depth-r>far)

def density_keep(distance,near,far,minimum):
    """Fraction of instances kept at a camera distance: 1 up to `near`, falling linearly to `minimum` at `far` and beyond."""
    d=np.asarray(distance,dtype=np.float64)
    if far<=near:return np.where(d>near,float(minimum),1.0)
    t=np.clip((d-near)/(far-near),0.0,1.0);return 1.0+(float(minimum)-1.0)*t

def screen_fraction(depth,radius,proj_yy,orthographic=False):
    """Fraction of the image height covered by the diameter of a sphere of `radius` at view depth `depth` (proj_yy = the projection matrix entry [1][1])."""
    depth=np.maximum(np.asarray(depth,dtype=np.float64),1e-9);radius=np.asarray(radius,dtype=np.float64)
    return radius*proj_yy*np.ones_like(depth) if orthographic else radius*proj_yy/depth

def lod_levels(values,thresholds,descending):
    """Level of every value: the highest k (1 = LOD 1, 2 = LOD 2, 3 = Proxy) whose threshold it has passed, 0 if none. descending False (distance): values >= t_k;
    True (screen size): values < t_k. thresholds in order LOD 1, 2, Proxy; they need not be sorted (a Proxy distance below the LOD 2 distance skips LOD 2)."""
    v=np.asarray(values,dtype=np.float64);level=np.zeros(len(v),dtype=np.int64)
    for k,t in enumerate(thresholds,1):level=np.where((v<t) if descending else (v>=t),k,level)
    return level

def remap_proto_indices(proto_index,level,table):
    """New protoIndices: each instance with hero ordinal k and requested level uses the finest defined LOD <= level (0 keeps the hero). Returns (indices, applied levels)."""
    idx=np.asarray(proto_index,dtype=np.int64).copy();applied=np.zeros(len(idx),dtype=np.int64)
    for k,have in table.items():
        sel=np.nonzero(np.asarray(proto_index)==k)[0]
        if not len(sel) or not have:continue
        for lv in np.unique(level[sel]):
            use=available_level(int(lv),have);m=sel[level[sel]==lv];applied[m]=use
            if use:idx[m]=have[use]
    return idx,applied

def merged_invisible(existing,hidden_ids):
    """Sorted union of already hidden ids (for example Grow's) and the ids hidden by the camera."""
    return sorted(set(int(i) for i in existing)|set(int(i) for i in hidden_ids))

# ---------------------------------------------------------------- Houdini side
import hou

def primvar_attribs(asset):
    """Space separated point attributes the PointInstancer copies to primvars: the ticked ones of the Primvars section."""
    names=[name for toggle,name in PRIMVAR_TOGGLES if asset.parm(toggle) is not None and asset.evalParm(toggle)]
    if asset.parm('imp_copy') is not None and asset.evalParm('mode')==8:names+=[n for n in asset.evalParm('imp_copy').replace(',',' ').split() if n and n not in names]     # the source attributes asked for in Imported Points
    return ' '.join(names)

def camera_info(asset):
    """Read-only text for the Camera section: what the last cook did."""
    if asset.evalParm('cam_on')==0:return 'Camera optimisation is off.'
    try:
        prim=asset.node('OUT_ARRAYTRON').stage().GetPrimAtPath(asset.evalParm('outputpath'));d=prim.GetCustomDataByKey('arraytron:camera')
    except Exception as exc:return 'Cannot read the stage: %s'%exc
    if not d:return 'No camera data yet (is the Camera Prim in the stream?).'
    text='%d of %d instances visible (%d hidden: %d outside the frustum, %d too far, %d thinned by distance, %d behind the camera).'%(d['visible'],d['total'],d['hidden'],d['frustum'],d['far'],d['density'],d['behind'])
    if d.get('lod'):text+=' LOD: hero %d, LOD 1 %d, LOD 2 %d, proxy %d.'%tuple(d['lod'])
    return text
