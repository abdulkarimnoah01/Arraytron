# Viewport brush (v0.6.0): stroke storage, brush maths and the Paint generator. Appended to the PythonModule after the scatter module (it uses
# scatter_hash, normal_alignment, stage_surface and _emit). The pure functions take and return numpy arrays and are tested without a viewport;
# the interactive part (mouse, drawing) lives in src/arraytron_paint_state.py (the Python Viewer State) and only calls these functions.
import base64, zlib
import numpy as np

PAINT_MAX=20000                  # painted points per node (the string parm stays a few hundred kB)
PAINT_COLUMNS=7                  # x y z nx ny nz id
FALLOFFS=('Linear','Smooth','Gaussian','Hard')

# ---------------------------------------------------------------- storage
def paint_empty():
    return {'pts':np.zeros((0,PAINT_COLUMNS)),'dab':0,'next':0}

def paint_encode(data):
    """Compact text for the hidden parm: 'p1:' + base64(zlib(float32 table)) + counters. Positions keep float32 precision (about 1e-6 relative)."""
    pts=np.asarray(data['pts'],dtype=np.float64)
    ids=pts[:,6].astype(np.int64).astype(np.float64)
    blob=zlib.compress(np.ascontiguousarray(pts[:,:6],dtype=np.float32).tobytes()+np.ascontiguousarray(ids,dtype=np.int64).tobytes(),6)
    return 'p1:%d:%d:%d:%s'%(len(pts),data['dab'],data['next'],base64.b64encode(blob).decode('ascii'))

def paint_decode(text):
    text=(text or '').strip()
    if not text:return paint_empty()
    head=text.split(':',4)
    if len(head)!=5 or head[0]!='p1':raise ValueError('Paint data is not in the p1 format (clear the paint to start again).')
    count,dab,nxt=int(head[1]),int(head[2]),int(head[3])
    raw=zlib.decompress(base64.b64decode(head[4]))
    if len(raw)!=count*(6*4+8):raise ValueError('Paint data is damaged (size does not match the point count).')
    xyz=np.frombuffer(raw[:count*24],dtype=np.float32).reshape(count,6).astype(np.float64)
    ids=np.frombuffer(raw[count*24:],dtype=np.int64).astype(np.float64)
    return {'pts':np.column_stack([xyz,ids]) if count else np.zeros((0,PAINT_COLUMNS)),'dab':dab,'next':nxt}

# ---------------------------------------------------------------- brush
def falloff_weight(t,kind):
    """Brush weight 1 at the centre to 0 at the rim for t = distance / radius in [0, 1]. Linear 1-t; Smooth smoothstep; Gaussian exp(-4.5 t^2) (cut to 0 at t > 1); Hard 1 everywhere inside."""
    t=np.clip(np.asarray(t,dtype=np.float64),0.0,None);inside=t<=1.0+1e-12
    kind=int(kind)
    if kind==0:w=1.0-t
    elif kind==1:w=1.0-t*t*(3.0-2.0*t)
    elif kind==2:w=np.exp(-4.5*t*t)
    else:w=np.ones_like(t)
    return np.where(inside,np.clip(w,0.0,1.0),0.0)

def tangent_frame(normal):
    n=np.asarray(normal,dtype=np.float64);n=n/np.linalg.norm(n)
    helper=np.array([0.0,0.0,1.0]) if abs(n[1])>0.9 else np.array([0.0,1.0,0.0])
    u=np.cross(helper,n);u/=np.linalg.norm(u);v=np.cross(n,u);return u,v

def dab_candidates(center,normal,radius,density,seed,dab):
    """Candidate positions of one dab on the brush disc (uniform over the disc) with their normalised distance. The number is density * disc area (rounded
    stochastically from the dab hash, so a low density still paints sometimes), at most 2000. Fully determined by (center, normal, radius, density, seed, dab)."""
    area=np.pi*radius*radius;expected=max(density,0.0)*area
    n=int(expected)+(1 if scatter_hash(np.array([dab]),seed,9)[0]<expected-int(expected) else 0);n=min(n,2000)
    if n==0:return np.zeros((0,3)),np.zeros(0)
    ids=np.arange(n)+dab*100003
    r=radius*np.sqrt(scatter_hash(ids,seed,10));a=2*np.pi*scatter_hash(ids,seed,11);u,v=tangent_frame(normal)
    pos=np.asarray(center,dtype=np.float64)+np.outer(r*np.cos(a),u)+np.outer(r*np.sin(a),v)
    return pos,r/radius

def brush_add(data,center,normal,radius,density,spacing,falloff,strength,seed,project):
    """One Add dab. `project(points, normal)` returns (positions, normals, valid) on the target surface (see make_projector). A candidate is kept
    when its hash is below strength * falloff weight and no stored or earlier accepted point lies within `spacing`. New points get consecutive ids,
    so painting more never renames the points that are already there. Returns the new data (the input is not modified) and the number added."""
    pts=data['pts'];dab=data['dab']
    cand,t=dab_candidates(center,normal,radius,density,seed,dab)
    new={'pts':pts,'dab':dab+1,'next':data['next']}
    if not len(cand):return new,0
    pos,nrm,valid=project(cand,normal)
    keep=valid&(scatter_hash(np.arange(len(cand))+dab*100003,seed,12)<strength*falloff_weight(t,falloff)-1e-12)
    pos,nrm=pos[keep],nrm[keep]
    if len(pos) and spacing>0:
        chosen=[]
        near=pts[np.linalg.norm(pts[:,:3]-np.asarray(center),axis=1)<radius+spacing][:,:3] if len(pts) else np.zeros((0,3))
        for k in range(len(pos)):
            others=np.vstack([near]+([pos[chosen]] if chosen else []))
            if len(others) and np.min(np.linalg.norm(others-pos[k],axis=1))<spacing:continue
            chosen.append(k)
        pos,nrm=pos[chosen],nrm[chosen]
    room=max(PAINT_MAX-len(pts),0);pos,nrm=pos[:room],nrm[:room]
    if not len(pos):return new,0
    ids=np.arange(data['next'],data['next']+len(pos))
    new['pts']=np.vstack([pts,np.column_stack([pos,nrm,ids])]);new['next']=data['next']+len(pos)
    return new,len(pos)

def brush_remove(data,center,radius,falloff,strength,seed):
    """One Remove dab: a point inside the radius is removed when the hash of its id and this dab is below strength * falloff weight."""
    pts=data['pts'];dab=data['dab'];new={'pts':pts,'dab':dab+1,'next':data['next']}
    if not len(pts):return new,0
    t=np.linalg.norm(pts[:,:3]-np.asarray(center,dtype=np.float64),axis=1)/radius
    gone=(t<=1.0)&(scatter_hash(pts[:,6].astype(np.int64),seed,13+dab%1000)<strength*falloff_weight(t,falloff)-1e-12)
    new['pts']=pts[~gone];return new,int(gone.sum())

def brush_replace(data,center,normal,radius,density,spacing,falloff,strength,seed,project):
    """Replace: clear the points under the brush (like Remove, weighted by strength x falloff) and paint new ones there (like Add). Returns (data, added, removed)."""
    cleared,removed=brush_remove(data,center,radius,falloff,strength,seed);new,added=brush_add(cleared,center,normal,radius,density,spacing,falloff,strength,seed,project)
    new['dab']=data['dab']+1;return new,added,removed

def brush_relax(data,center,radius,falloff,strength,spacing,project,iterations=6):
    """Relax (smooth): spread the painted points inside the brush towards an even spacing. Pairs closer than the target distance (Min Spacing, or the mean
    nearest-neighbour distance when that is 0) are pushed apart along the line between them by strength x falloff x half of the shortfall, for a few
    iterations, then every moved point is projected back onto the surface (a point that cannot be projected stays where it was). Ids never change. Returns (data, moved)."""
    pts=data['pts'].copy();c=np.asarray(center,dtype=np.float64);new={'pts':pts,'dab':data['dab']+1,'next':data['next']}
    if len(pts)<2:return new,0
    inside=np.nonzero(np.linalg.norm(pts[:,:3]-c,axis=1)<=radius)[0]
    if len(inside)<2:return new,0
    w=falloff_weight(np.linalg.norm(pts[inside,:3]-c,axis=1)/radius,falloff)*strength;P0=pts[inside,:3].copy();P=P0.copy()
    if spacing>0:d0=spacing
    else:
        dm=np.linalg.norm(P[:,None]-P[None],axis=2);np.fill_diagonal(dm,np.inf);d0=float(dm.min(axis=1).mean())
    for _ in range(max(1,int(iterations))):
        d=P[None]-P[:,None];L=np.linalg.norm(d,axis=2);np.fill_diagonal(L,np.inf);short=np.maximum(d0-L,0.0);near=short>0
        if not near.any():break
        dirn=np.where(near[...,None],d/np.where(L[...,None]>1e-12,L[...,None],1.0),0.0);push=-(short[...,None]*0.5*dirn).sum(axis=1)*w[:,None];P=P+push
    moved=np.linalg.norm(P-P0,axis=1)>1e-9
    if moved.any():
        normal=np.mean(pts[inside,3:6],axis=0);normal=normal/max(np.linalg.norm(normal),1e-12);pos,nrm,ok=project(P[moved],normal);rows=inside[moved]
        pts[rows[ok],:3]=pos[ok];pts[rows[ok],3:6]=nrm[ok];moved=int(ok.sum())
    else:moved=0
    new['pts']=pts;return new,moved

# ---------------------------------------------------------------- surface access
def ray_triangles(origins,directions,P,T):
    """Moeller-Trumbore, every ray against every triangle (numpy). Returns distance t (inf where nothing is hit) and the triangle index, per ray.
    Both faces count. Use it with a pre-filtered triangle subset when there are many triangles."""
    origins=np.atleast_2d(np.asarray(origins,dtype=np.float64));directions=np.atleast_2d(np.asarray(directions,dtype=np.float64))
    t_out=np.full(len(origins),np.inf);idx=np.full(len(origins),-1,dtype=np.int64)
    if not len(T):return t_out,idx
    A=P[T[:,0]];E1=P[T[:,1]]-A;E2=P[T[:,2]]-A
    for k in range(len(origins)):
        d=directions[k] if len(directions)>1 else directions[0]
        h=np.cross(d,E2);det=np.einsum('ij,ij->i',E1,h);ok=np.abs(det)>1e-12
        inv=np.where(ok,1.0/np.where(ok,det,1.0),0.0);s=origins[k]-A
        u=np.einsum('ij,ij->i',s,h)*inv;q=np.cross(s,E1);v=(q@d)*inv;t=np.einsum('ij,ij->i',E2,q)*inv
        hit=ok&(u>=-1e-9)&(v>=-1e-9)&(u+v<=1+1e-9)&(t>1e-9)
        if hit.any():
            tt=np.where(hit,t,np.inf);j=int(np.argmin(tt));t_out[k]=tt[j];idx[k]=j
    return t_out,idx

def plane_surface(size=1000.0,height=0.0):
    """A big ground quad at Y = height, for painting when no Paint Target is set (two triangles, normal +Y)."""
    P=np.array([[-size,height,-size],[size,height,-size],[size,height,size],[-size,height,size]],dtype=np.float64)
    T=np.array([[0,2,1],[0,3,2]],dtype=np.int64)
    return P,T,np.zeros(2),np.tile([0.0,1.0,0.0],(2,1)),np.tile([0.0,1.0,0.0],(4,1))

def make_projector(surface,center,radius,smooth=True):
    """Build project(points, normal) for one dab: points are moved along the brush normal onto the surface (rays start radius above, go down, and
    also look up) using only the triangles near the dab. Returns positions, normals (face or smooth vertex normals), validity flags."""
    P,T,area,normals,vn=surface;c=np.asarray(center,dtype=np.float64)
    if len(T):
        cen=(P[T[:,0]]+P[T[:,1]]+P[T[:,2]])/3.0;ext=np.maximum(np.linalg.norm(P[T[:,0]]-cen,axis=1),np.maximum(np.linalg.norm(P[T[:,1]]-cen,axis=1),np.linalg.norm(P[T[:,2]]-cen,axis=1)))
        near=np.where(np.linalg.norm(cen-c,axis=1)<3.0*radius+ext)[0]
    else:near=np.zeros(0,dtype=np.int64)
    Tn=T[near]
    def project(points,normal):
        n=np.asarray(normal,dtype=np.float64);n=n/np.linalg.norm(n);m=len(points)
        pos=np.zeros((m,3));nrm=np.zeros((m,3));ok=np.zeros(m,dtype=bool)
        for k in range(m):
            t,j=ray_triangles(points[k]+n*radius*1.5,-n,P,Tn)
            if j[0]<0:continue
            tri=Tn[j[0]];hit=points[k]+n*radius*1.5-n*t[0]
            if smooth:
                a,b,cc=P[tri[0]],P[tri[1]],P[tri[2]];ab=b-a;ac=cc-a;ap=hit-a;d00=ab@ab;d01=ab@ac;d11=ac@ac;d20=ap@ab;d21=ap@ac;den=d00*d11-d01*d01
                v=(d11*d20-d01*d21)/den if den!=0 else 0.0;w=(d00*d21-d01*d20)/den if den!=0 else 0.0
                nn=vn[tri[0]]*(1-v-w)+vn[tri[1]]*v+vn[tri[2]]*w;nn=nn/max(np.linalg.norm(nn),1e-12)
            else:nn=normals[near[j[0]]]
            pos[k]=hit;nrm[k]=nn;ok[k]=True
        return pos,nrm,ok
    return project

def paint_surface(asset):
    """The triangles under the Paint Target prim (like Surface Scatter), or the ground plane when the target is empty."""
    if not asset.evalParm('paint_prim').strip():return plane_surface(1000.0,0.0)
    return stage_surface(asset,'paint_prim')

# ---------------------------------------------------------------- Houdini side
def paint_data(asset):
    try:return paint_decode(asset.evalParm('paint_data'))
    except ValueError as exc:raise hou.NodeError(str(exc))

def paint_points(asset):
    """Positions, normals, ids and alignment quaternions of the painted points (offset along the normal applied)."""
    data=paint_data(asset);pts=data['pts']
    if not len(pts):return np.zeros((0,3)),np.zeros((0,3)),np.zeros(0,dtype=np.int64),np.zeros((0,4))
    n=pts[:,3:6];pos=pts[:,:3]+n*asset.evalParm('paint_offset')
    return pos,n,pts[:,6].astype(np.int64),normal_alignment(n,asset.evalParm('paint_align'))

def sop_paint(geo,asset):
    """generate_paint: the painted points. The painted ids are kept, so a later Remove never renames the other points (the variation, mask and overlap stages key on id)."""
    pos,n,ids,quat=paint_points(asset);geo.clear();geo.addAttrib(hou.attribType.Point,'id',0);geo.addAttrib(hou.attribType.Point,'align',(0.0,0.0,0.0,1.0))
    if not len(pos):return
    geo.createPoints([tuple(v) for v in pos.tolist()]);geo.setPointIntAttribValues('id',ids.tolist());geo.setPointFloatAttribValues('align',quat.ravel().tolist())

def paint_info(asset):
    try:data=paint_decode(asset.evalParm('paint_data'))
    except ValueError as exc:return 'Cannot read the paint: %s'%exc
    count=len(data['pts'])
    if not count:return 'Nothing painted yet. Press Start Painting, then drag over the Paint Target. Ctrl-drag removes.'
    lo=data['pts'][:,:3].min(axis=0);hi=data['pts'][:,:3].max(axis=0)
    return '%d painted points (limit %d), %d dabs. Extent %.3g x %.3g x %.3g.'%(count,PAINT_MAX,data['dab'],*(hi-lo))

def paint_apply(asset,data,label='Arraytron paint'):
    """Write the paint data to the node (one undo step)."""
    with hou.undos.group(label):asset.parm('paint_data').set(paint_encode(data))

def paint_state_name(asset):
    return asset.type().definition().sections()['DefaultState'].contents().strip()

def paint_start(asset):
    """Start Painting button: switch to Paint mode, make this node current and enter the viewport state."""
    if asset.evalParm('mode')!=6:asset.parm('mode').set(6)
    if not hou.isUIAvailable():raise hou.NodeError('The paint tool needs the Houdini interface (a Scene Viewer).')
    viewer=hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
    if viewer is None:raise hou.NodeError('Open a Scene Viewer pane to paint.')
    asset.setCurrent(True,clear_all_selected=True);viewer.setCurrentState(paint_state_name(asset))

def paint_clear(asset):
    with hou.undos.group('Arraytron clear paint'):asset.parm('paint_data').set('')
