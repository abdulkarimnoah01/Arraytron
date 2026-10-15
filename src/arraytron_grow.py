# Grow animation (v0.5.2): instances grow or pop up in a sweep across the layout, driven by the timeline. Appended after the other modules.
# Every instance gets a start frame from where it lies along the sweep direction (plus a random delay) and a growth fraction from the current
# frame; the fraction goes through an easing curve and becomes a scale (and optionally a rise out of the ground). Pure numpy functions are tested directly.
import numpy as np
try:scatter_hash
except NameError:from arraytron_scatter import scatter_hash

TINY=1e-5                                    # "not there yet": a scale this small is invisible but keeps the instance matrix valid

def ease(kind,x):
    """Easing of a 0..1 progress: 0 linear, 1 smooth (smoothstep), 2 overshoot (ease-out-back: rises past 1 and settles), 3 bounce (ease-out-bounce)."""
    x=np.clip(np.asarray(x,dtype=np.float64),0.0,1.0)
    if kind==0:return x
    if kind==1:return x*x*(3-2*x)
    if kind==2:
        c1=1.70158;c3=c1+1;return 1+c3*(x-1)**3+c1*(x-1)**2
    n1,d1=7.5625,2.75
    return np.where(x<1/d1,n1*x*x,np.where(x<2/d1,n1*(x-1.5/d1)**2+0.75,np.where(x<2.5/d1,n1*(x-2.25/d1)**2+0.9375,n1*(x-2.625/d1)**2+0.984375)))

def sweep_position(P,ids,mode,vector,reverse):
    """Where each point sits along the sweep, 0 (first to start) to 1 (last). mode 0 +X, 1 +Y, 2 +Z, 3 Custom vector, 4 Radial (distance from the centre in XZ),
    5 By Id (point order). A layout with no extent along the direction starts everything at 0."""
    P=np.asarray(P,dtype=np.float64);n=len(P)
    if mode==5:u=np.arange(n)/max(n-1,1)
    else:
        if mode==4:
            c=0.5*(P[:,[0,2]].min(axis=0)+P[:,[0,2]].max(axis=0));proj=np.linalg.norm(P[:,[0,2]]-c,axis=1)
        else:
            d=np.array([(1.0,0.0,0.0),(0.0,1.0,0.0),(0.0,0.0,1.0)][mode]) if mode<3 else np.asarray(vector,dtype=np.float64)
            length=np.linalg.norm(d);d=d/length if length>1e-9 else np.array([1.0,0.0,0.0]);proj=P@d
        lo,hi=float(proj.min()),float(proj.max());u=(proj-lo)/(hi-lo) if hi-lo>1e-12 else np.zeros(n)
    return 1.0-u if reverse else u

def growth(u,ids,frame,start,sweep,duration,delay,seed):
    """Linear growth fraction 0..1 of every instance at `frame`: it starts at start + u x sweep + random x delay and takes `duration` frames."""
    t0=start+np.asarray(u)*sweep+scatter_hash(ids,seed,31)*delay
    return np.clip((frame-t0)/max(duration,1e-6),0.0,1.0)

def apply_style(style,eased_kind,f,scale,P,rise):
    """New scales (N,3) and positions (N,3) for growth fractions f. style 0 Grow: uniform scale. 1 Plant: height first (first 70% of the time), width later
    (from 20%). 2 Rise: the instance climbs `rise` units out of the ground, scaling in over the first 30% so it does not show under the surface."""
    f=np.asarray(f,dtype=np.float64);e=np.where(f>=1.0,1.0,ease(eased_kind,f));scale=np.asarray(scale,dtype=np.float64).copy();P=np.asarray(P,dtype=np.float64).copy()   # finished instances are EXACTLY the normal result
    if style==0:scale*=np.maximum(e,TINY)[:,None]
    elif style==1:
        h=np.where(f>=0.7,1.0,ease(eased_kind,np.minimum(f/0.7,1.0)));w=np.where(f>=1.0,1.0,ease(eased_kind,np.clip((f-0.2)/0.8,0.0,1.0)))
        scale[:,1]*=np.maximum(h,TINY);scale[:,0]*=np.maximum(w,TINY);scale[:,2]*=np.maximum(w,TINY)
    else:
        P[:,1]-=(1.0-e)*rise;scale*=np.maximum(np.where(f>=0.3,1.0,ease(1,np.minimum(f/0.3,1.0))),TINY)[:,None]
    return scale,P

# ---------------------------------------------------------------- Houdini side
import hou

def sop_grow(geo,asset):
    """GROW: scale / move the points for the current frame. Off: nothing is read and the cook stays independent of time."""
    if not asset.evalParm('grow_on') or geo.intrinsicValue('pointcount')==0:return
    frame=asset.evalParm('grow_frame')                     # the time dependency: grow_frame is an expression on the frame number
    P=np.array(geo.pointFloatAttribValues('P')).reshape(-1,3);scale=np.array(geo.pointFloatAttribValues('scale')).reshape(-1,3);ids=np.array(geo.pointIntAttribValues('id'))
    u=sweep_position(P,ids,asset.evalParm('grow_direction'),asset.evalParmTuple('grow_vector'),asset.evalParm('grow_reverse'))
    sweep=asset.evalParm('grow_sweep');duration=asset.evalParm('grow_time')
    f=growth(u,ids,frame,asset.evalParm('grow_start'),sweep,duration,asset.evalParm('grow_delay')*(sweep+duration),asset.evalParm('grow_seed'))
    scale,P2=apply_style(asset.evalParm('grow_style'),asset.evalParm('grow_ease'),f,scale,P,asset.evalParm('grow_rise'))
    geo.setPointFloatAttribValues('scale',scale.ravel().tolist())
    if asset.evalParm('grow_style')==2:geo.setPointFloatAttribValues('P',P2.ravel().tolist())
    geo.addAttrib(hou.attribType.Point,'grow_hidden',0);geo.setPointIntAttribValues('grow_hidden',(f<=0.0).astype(int).tolist())      # not started yet: the guide script lists them as invisibleIds

def grow_info(asset):
    """Read-only text: the frame range of the whole animation."""
    if not asset.evalParm('grow_on'):return 'Grow is off.'
    start=asset.evalParm('grow_start');sweep=asset.evalParm('grow_sweep');duration=asset.evalParm('grow_time');end=start+(sweep+duration)*(1+asset.evalParm('grow_delay'))
    return 'The first instance starts at frame %g, the last one is full size at frame %g (now: frame %g).'%(start,end,asset.evalParm('grow_frame'))

def grow_guide_line(asset):
    """(start, end) world points of the sweep arrow for the viewport guide, or None (Radial and By Id have no straight arrow)."""
    mode=asset.evalParm('grow_direction')
    if not asset.evalParm('grow_on') or mode>=4:return None
    try:g=asset.node('USD_COMPILER/PHYSICS_SWITCH').geometry()
    except Exception:return None
    if g is None:return None                                                            # the points did not cook (an error above): no arrow
    P=np.array(g.pointFloatAttribValues('P')).reshape(-1,3)
    if len(P)<2:return None
    d=np.array([(1.0,0.0,0.0),(0.0,1.0,0.0),(0.0,0.0,1.0)][mode]) if mode<3 else np.array(asset.evalParmTuple('grow_vector'))
    if np.linalg.norm(d)<1e-9:return None
    d=d/np.linalg.norm(d);proj=P@d;c=P.mean(axis=0);a=c+d*(proj.min()-c@d);b=c+d*(proj.max()-c@d)
    return (b,a) if asset.evalParm('grow_reverse') else (a,b)
