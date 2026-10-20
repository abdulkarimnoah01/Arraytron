# Falloff (v1.12.0): the Layout tab section FALLOFF. A scatter is full size and densest in the centre of its layout and fades towards the edges: the scale shrinks and the density thins out.
# It works on every Distribution Mode (Line, Area, Grid, Circle, Curve, Surface, Cluster, Imported ...): the FALLOFF Python SOP runs after the Mask and the Field Stack and before the
# Variation, measures every point's normalised distance t (0 in the centre, 1 at the edge) from the centre and the reach of the layout, turns it into a weight w with a curve, then
#   * density: a point survives when its own id-keyed random number is below  edge density + (1 - edge density) * w  (so a higher density only ever adds points, like the Mask),
#   * scale:   f@maskscale is multiplied by  edge scale + (1 - edge scale) * w  (the Prototype Assignment applies it last, with the Mask Scale).
# Positions are in the space the points are generated in (the layout space of Line / Area / Grid / Circle, world space of Surface / Cluster / Imported), like the Field Stack.
# Appended to the PythonModule after the Cluster module (uses scatter_hash). The pure numpy functions are tested directly.
import numpy as np

FALL_STREAM=95

def falloff_axes(P,axes):
    """The coordinates the falloff looks at: X and Z (the ground plane) or all three, as an (n, k) array."""
    P=np.asarray(P,dtype=np.float64).reshape(-1,3);return P[:,[0,2]] if int(axes)==0 else P

def falloff_region(P,axes,center_mode,center,radius_mode,radius):
    """(centre (k,), reach) of the layout: automatic = the middle of the bounding box and the distance of the farthest point (box shape: the half sizes of the bounding box), custom = the
    given centre and radius. reach is an array of k half sizes for the box shape and a float for the radial one: returns (centre, radial reach, box half sizes)."""
    A=falloff_axes(P,axes)
    if len(A)==0:return np.zeros(2 if int(axes)==0 else 3),1.0,np.ones(2 if int(axes)==0 else 3)
    lo=A.min(axis=0);hi=A.max(axis=0)
    if int(center_mode)==1:
        c=np.asarray(center,dtype=np.float64).reshape(3);c=c[[0,2]] if int(axes)==0 else c
    else:c=(lo+hi)*0.5
    if int(radius_mode)==1:R=max(float(radius),1e-9);half=np.full(len(c),R)
    else:
        R=float(np.max(np.linalg.norm(A-c,axis=1)));R=R if R>1e-9 else 1.0
        half=np.maximum((hi-lo)*0.5,0.0)
    return c,R,half

def falloff_distance(P,shape,axes,c,R,half):
    """Normalised distance t of every point: 0 at the centre, 1 at the edge. shape 0 radial (distance / reach), 1 box (the largest of |offset| / half size over the axes that have a size,
    so every edge of a rectangle fades, not only its corners)."""
    A=falloff_axes(P,axes);d=A-c
    if int(shape)==0:return np.linalg.norm(d,axis=1)/R
    ok=half>1e-9
    if not np.any(ok):return np.zeros(len(A))
    return np.max(np.abs(d[:,ok])/half[ok],axis=1)

def falloff_curve(t,kind,inner=0.0):
    """Weight w in [0, 1] from the normalised distance t: 1 inside the flat centre (inner, a fraction 0..0.95 of the reach), then Linear 1 - u, Smooth smoothstep or Gaussian exp(-4.5 u^2) of the
    rest u = (t - inner) / (1 - inner); 0 beyond the edge."""
    t=np.asarray(t,dtype=np.float64);inner=min(max(float(inner),0.0),0.95);u=np.clip((t-inner)/(1.0-inner),0.0,None);kind=int(kind);inside=u<=1.0+1e-12
    if kind==0:w=1.0-u
    elif kind==1:w=1.0-u*u*(3.0-2.0*u)
    else:w=np.exp(-4.5*u*u)
    return np.where(inside,np.clip(w,0.0,1.0),0.0)

def falloff_keep(ids,w,edge_density,seed):
    """Boolean keep mask: a point survives when its own number (hash of the id and the seed) is below edge + (1 - edge) * w, so a higher weight or a higher edge density only adds points."""
    prob=edge_density+(1.0-edge_density)*np.asarray(w,dtype=np.float64);return scatter_hash(np.asarray(ids,dtype=np.int64),seed,FALL_STREAM)<prob

def falloff_scale(w,edge_scale):
    """Scale multiplier of every weight: the edge scale at the edge, 1 in the centre."""
    return edge_scale+(1.0-edge_scale)*np.asarray(w,dtype=np.float64)

# ---------------------------------------------------------------- the stage
def falloff_parameters(asset):
    return dict(shape=asset.evalParm('fall_shape'),axes=asset.evalParm('fall_axes'),curve=asset.evalParm('fall_curve'),inner=asset.evalParm('fall_inner')/100.0,edge_density=asset.evalParm('fall_density')/100.0,
                edge_scale=asset.evalParm('fall_scale'),center_mode=asset.evalParm('fall_center_mode'),center=asset.evalParmTuple('fall_center'),radius_mode=asset.evalParm('fall_radius_mode'),radius=asset.evalParm('fall_radius'),seed=asset.evalParm('fall_seed'))

def falloff_weights(P,q):
    """(w, t, centre, reach) for the points P with the parameters q (a dict of falloff_parameters)."""
    c,R,half=falloff_region(P,q['axes'],q['center_mode'],q['center'],q['radius_mode'],q['radius']);t=falloff_distance(P,q['shape'],q['axes'],c,R,half);return falloff_curve(t,q['curve'],q['inner']),t,c,R

def sop_falloff(geo,asset):
    """FALLOFF: thin out and shrink the points towards the edge of the layout. Ids are never changed; a deleted point only ever disappears."""
    for name,default in (('fall_before',0),('fall_after',0),('fall_reach',0.0),('fall_cx',0.0),('fall_cy',0.0),('fall_cz',0.0)):geo.addAttrib(hou.attribType.Global,name,default)
    n=geo.intrinsicValue('pointcount');geo.setGlobalAttribValue('fall_before',n);geo.setGlobalAttribValue('fall_after',n)
    if not asset.evalParm('fall_on') or n==0:return
    q=falloff_parameters(asset);P=np.array(geo.pointFloatAttribValues('P')).reshape(-1,3);ids=np.array(geo.pointIntAttribValues('id'))
    w,t,c,R=falloff_weights(P,q);geo.setGlobalAttribValue('fall_reach',float(R))
    cc=np.zeros(3)
    if len(c)==2:cc[[0,2]]=c
    else:cc=np.asarray(c,dtype=np.float64)
    geo.setGlobalAttribValue('fall_cx',float(cc[0]));geo.setGlobalAttribValue('fall_cy',float(cc[1]));geo.setGlobalAttribValue('fall_cz',float(cc[2]))
    if q['edge_scale']<1.0:
        mult=falloff_scale(w,q['edge_scale'])
        if geo.findPointAttrib('maskscale') is not None:mult=mult*np.array(geo.pointFloatAttribValues('maskscale'))
        else:geo.addAttrib(hou.attribType.Point,'maskscale',1.0)
        geo.setPointFloatAttribValues('maskscale',mult.tolist())
    if q['edge_density']<1.0:
        drop=np.nonzero(~falloff_keep(ids,w,q['edge_density'],q['seed']))[0]
        if len(drop):geo.deletePoints([geo.point(int(i)) for i in drop])
        geo.setGlobalAttribValue('fall_after',n-len(drop))

def falloff_info(asset):
    """Read-only text for the Falloff section."""
    if not asset.evalParm('fall_on'):return 'Off: the scatter keeps one density and one scale all over.'
    try:
        g=asset.node('USD_COMPILER/FALLOFF').geometry()
        return 'Centre (%.3g, %.3g, %.3g), reach %.3g. Kept %d of %d points; scale %.2g at the edge.'%(g.attribValue('fall_cx'),g.attribValue('fall_cy'),g.attribValue('fall_cz'),g.attribValue('fall_reach'),g.attribValue('fall_after'),g.attribValue('fall_before'),asset.evalParm('fall_scale'))
    except Exception as exc:return 'Cannot evaluate: %s'%exc
