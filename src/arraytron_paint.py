# Viewport brush (v0.6.0): stroke storage, brush maths and the Paint generator. Appended to the PythonModule after the scatter module (it uses
# scatter_hash, normal_alignment, stage_surface and _emit). The pure functions take and return numpy arrays and are tested without a viewport;
# the interactive part (mouse, drawing) lives in src/arraytron_paint_state.py (the Python Viewer State) and only calls these functions.
import base64, struct, zlib
import numpy as np

PAINT_MAX=200000                 # painted points per node (v1.36.0; 20 000 before): about 6 MB of compressed text at the limit
PAINT_COLUMNS=7                  # x y z nx ny nz id (the p1 / p2 table)
PAINT_EXTRA=('fall','edit','yaw','combed','proto')          # Paint Engine 2.0 (v1.36.0, the p3 table): the Scale Falloff of the stroke, the artist's scale edits (Grow / Shrink), the heading (radians about the up)
PAINT_EXTRA_DEFAULT=(1.0,1.0,0.0,0.0,0.0)                    # and whether it is set (Orient / Comb), the Prototype Bank row (Swap; 0 = the Prototype Assignment's choice)
PAINT_WIDE=PAINT_COLUMNS+len(PAINT_EXTRA)
PAINT_MAX_STROKES=2000           # stroke paths kept for the Falloff (v1.13.0)
PAINT_STROKE_CENTRES=400         # dab centres kept per stroke
FALLOFFS=('Linear','Smooth','Gaussian','Hard')

# ---------------------------------------------------------------- storage
def paint_empty():
    return {'pts':np.zeros((0,PAINT_WIDE)),'dab':0,'next':0,'strokes':[]}

def paint_rows(pos,nrm,ids,fall=None):
    """Rows of the wide table (x y z nx ny nz id fall edit yaw combed proto) for new points: the Scale Falloff multiplier fall (1 when None), the rest at their defaults."""
    n=len(pos);rows=np.tile(np.array([0.0]*PAINT_COLUMNS+list(PAINT_EXTRA_DEFAULT)),(n,1))
    if n:rows[:,0:3]=pos;rows[:,3:6]=nrm;rows[:,6]=ids
    if fall is not None and n:rows[:,7]=fall
    return rows

def paint_wide(pts):
    """The table with the Paint Engine 2.0 columns (padded with their defaults when it has only x y z nx ny nz id)."""
    pts=np.asarray(pts,dtype=np.float64)
    if pts.ndim==2 and pts.shape[1]>=PAINT_WIDE:return pts
    out=np.tile(np.array([0.0]*PAINT_COLUMNS+list(PAINT_EXTRA_DEFAULT)),(len(pts),1))
    if len(pts):out[:,:pts.shape[1]]=pts
    return out

def paint_encode(data):
    """Compact text for the hidden parm: 'p1:' + base64(zlib(float32 table)) + counters. Positions keep float32 precision (about 1e-6 relative). When the data holds stroke paths (the viewport
    tool records them for the Falloff) the format is 'p2:' (the same table followed by the strokes: per stroke its brush radius, its number of centres and the centres); without strokes the text is
    exactly the p1 text, so painted scenes that never used a stroke are unchanged."""
    pts=paint_wide(data['pts'])
    ids=pts[:,6].astype(np.int64).astype(np.float64)
    raw=np.ascontiguousarray(pts[:,:6],dtype=np.float32).tobytes()+np.ascontiguousarray(ids,dtype=np.int64).tobytes()
    strokes=data.get('strokes') or []
    if len(pts) and not np.allclose(pts[:,PAINT_COLUMNS:],np.array(PAINT_EXTRA_DEFAULT)[None]):                        # v1.36.0: 'p3' adds the Paint Engine 2.0 columns; a paint without edits stays p1 / p2, bit for bit
        parts=[raw,np.ascontiguousarray(pts[:,PAINT_COLUMNS:],dtype=np.float32).tobytes()]
        for radius,centres in strokes[-PAINT_MAX_STROKES:]:
            centres=np.ascontiguousarray(np.asarray(centres,dtype=np.float32).reshape(-1,3));parts.append(struct.pack('<fi',float(radius),len(centres)));parts.append(centres.tobytes())
        blob=zlib.compress(b''.join(parts),6);return 'p3:%d:%d:%d:%d:%s'%(len(pts),data['dab'],data['next'],min(len(strokes),PAINT_MAX_STROKES),base64.b64encode(blob).decode('ascii'))
    if not strokes:
        blob=zlib.compress(raw,6);return 'p1:%d:%d:%d:%s'%(len(pts),data['dab'],data['next'],base64.b64encode(blob).decode('ascii'))
    parts=[raw]
    for radius,centres in strokes[-PAINT_MAX_STROKES:]:
        centres=np.ascontiguousarray(np.asarray(centres,dtype=np.float32).reshape(-1,3));parts.append(struct.pack('<fi',float(radius),len(centres)));parts.append(centres.tobytes())
    blob=zlib.compress(b''.join(parts),6);return 'p2:%d:%d:%d:%d:%s'%(len(pts),data['dab'],data['next'],min(len(strokes),PAINT_MAX_STROKES),base64.b64encode(blob).decode('ascii'))

def paint_decode(text):
    text=(text or '').strip()
    if not text:return paint_empty()
    head=text.split(':',5 if text.startswith(('p2:','p3:')) else 4)
    if head[0]=='p1' and len(head)==5:
        count,dab,nxt=int(head[1]),int(head[2]),int(head[3]);nstrokes=0;payload=head[4]
    elif head[0] in ('p2','p3') and len(head)==6:
        count,dab,nxt,nstrokes=int(head[1]),int(head[2]),int(head[3]),int(head[4]);payload=head[5]
    else:raise ValueError('Paint data is not in the p1 format (clear the paint to start again).')
    raw=zlib.decompress(base64.b64decode(payload));extra=count*len(PAINT_EXTRA)*4 if head[0]=='p3' else 0;need=count*(6*4+8)+extra
    if len(raw)<need or (head[0]=='p1' and len(raw)!=need):raise ValueError('Paint data is damaged (size does not match the point count).')
    xyz=np.frombuffer(raw[:count*24],dtype=np.float32).reshape(count,6).astype(np.float64)
    ids=np.frombuffer(raw[count*24:count*32],dtype=np.int64).astype(np.float64);strokes=[];at=need
    ext=np.frombuffer(raw[count*32:need],dtype=np.float32).reshape(count,len(PAINT_EXTRA)).astype(np.float64) if extra else None
    try:
        for _ in range(nstrokes):
            radius,n=struct.unpack_from('<fi',raw,at);at+=8;centres=np.frombuffer(raw[at:at+n*12],dtype=np.float32).reshape(n,3).astype(np.float64);at+=n*12;strokes.append((float(radius),centres))
    except (struct.error,ValueError):raise ValueError('Paint data is damaged (the stroke paths are cut off).')
    pts=paint_wide(np.column_stack([xyz,ids])) if count else np.zeros((0,PAINT_WIDE))
    if ext is not None and count:pts[:,PAINT_COLUMNS:]=ext
    return {'pts':pts,'dab':dab,'next':nxt,'strokes':strokes}

def paint_thin(centres,radius):
    """The dab centres of one stroke thinned for storage: no two closer than a quarter of the radius (the last one always kept), at most PAINT_STROKE_CENTRES."""
    c=np.asarray(centres,dtype=np.float64).reshape(-1,3)
    if len(c)<=2:return c
    keep=[0];last=c[0]
    for k in range(1,len(c)-1):
        if np.linalg.norm(c[k]-last)>=0.25*radius:keep.append(k);last=c[k]
    keep.append(len(c)-1);c=c[keep]
    if len(c)>PAINT_STROKE_CENTRES:c=c[np.unique(np.round(np.linspace(0,len(c)-1,PAINT_STROKE_CENTRES)).astype(int))]
    return c

def paint_stroke_add(data,centres,radius):
    """The data with one more stroke path (the dab centres of an Add or Replace stroke and the brush radius): what the Falloff follows. The input is not modified."""
    new=dict(data);strokes=list(data.get('strokes') or []);c=paint_thin(centres,radius)
    if len(c):strokes.append((float(radius),c))
    new['strokes']=strokes[-PAINT_MAX_STROKES:];return new

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
    pts=paint_wide(data['pts']);dab=data['dab']
    cand,t=dab_candidates(center,normal,radius,density,seed,dab)
    new={'pts':pts,'dab':dab+1,'next':data['next'],'strokes':data.get('strokes',[])}
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
    new['pts']=np.vstack([pts,paint_rows(pos,nrm,ids)]);new['next']=data['next']+len(pos)
    return new,len(pos)

def brush_remove(data,center,radius,falloff,strength,seed):
    """One Remove dab: a point inside the radius is removed when the hash of its id and this dab is below strength * falloff weight."""
    pts=data['pts'];dab=data['dab'];new={'pts':pts,'dab':dab+1,'next':data['next'],'strokes':data.get('strokes',[])}
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
    pts=data['pts'].copy();c=np.asarray(center,dtype=np.float64);new={'pts':pts,'dab':data['dab']+1,'next':data['next'],'strokes':data.get('strokes',[])}
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

def paint_align_quats(pts,amount):
    """The alignment of painted points: the surface normal (Align to Normal), then the heading of the Orient / Comb brush about the instance's up (yaw 0: unchanged)."""
    q=normal_alignment(pts[:,3:6],amount)
    yaw=pts[:,9] if pts.shape[1]>9 else np.zeros(len(pts))
    if np.any(yaw!=0):
        up=bc_qrot(q,np.array([0.0,1.0,0.0]));q=bc_qnorm(bc_qmul(bc_qaxis(up/np.maximum(np.linalg.norm(up,axis=1,keepdims=True),1e-12),yaw),q))
    return q

def paint_points(asset):
    """Positions, normals, ids and alignment quaternions of the painted points (offset along the normal applied)."""
    data=paint_data(asset);pts=paint_wide(data['pts'])
    if not len(pts):return np.zeros((0,3)),np.zeros((0,3)),np.zeros(0,dtype=np.int64),np.zeros((0,4))
    n=pts[:,3:6];pos=pts[:,:3]+n*asset.evalParm('paint_offset')
    return pos,n,pts[:,6].astype(np.int64),paint_align_quats(pts,asset.evalParm('paint_align'))

def sop_paint(geo,asset):
    """generate_paint: the painted points. The painted ids are kept, so a later Remove never renames the other points (the variation, mask and overlap stages key on id)."""
    pos,n,ids,quat=paint_points(asset);geo.clear();geo.addAttrib(hou.attribType.Point,'id',0);geo.addAttrib(hou.attribType.Point,'align',(0.0,0.0,0.0,1.0))
    pts=paint_wide(paint_data(asset)['pts']) if len(pos) else np.zeros((0,PAINT_WIDE))
    extra=len(pts) and not np.allclose(pts[:,PAINT_COLUMNS:],np.array(PAINT_EXTRA_DEFAULT)[None])
    if extra:                                                                                             # v1.36.0: what the brushes changed, through the hooks of the variation stage
        geo.addAttrib(hou.attribType.Point,'srcscale',(1.0,1.0,1.0));geo.addAttrib(hou.attribType.Point,'place_proto',0);geo.addAttrib(hou.attribType.Point,'paint_combed',0)
    if not len(pos):return
    geo.createPoints([tuple(v) for v in pos.tolist()]);geo.setPointIntAttribValues('id',ids.tolist());geo.setPointFloatAttribValues('align',quat.ravel().tolist())
    if extra:
        geo.setPointFloatAttribValues('srcscale',np.repeat(np.maximum(pts[:,7]*pts[:,8],1e-4),3).tolist());geo.setPointIntAttribValues('place_proto',pts[:,11].astype(np.int64).tolist())
        geo.setPointIntAttribValues('paint_combed',(pts[:,10]>0.5).astype(np.int64).tolist())

def paint_info(asset):
    try:data=paint_decode(asset.evalParm('paint_data'))
    except ValueError as exc:return 'Cannot read the paint: %s'%exc
    count=len(data['pts'])
    if not count:return 'Nothing painted yet. Press Start Painting, then drag over the Paint Target. Ctrl-drag erases; C in the viewport opens the brushes.'
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


# ---------------------------------------------------------------- Paint Engine 2.0 (v1.36.0): the Arraytron adapter of BrushCore
# The brush maths is BrushCore's (src/brushcore.py, at the top of the PythonModule, shared with Arraytron Stamp). A stroke works on the painted points in memory (the viewport shows them as they
# change) and is written once, on release (one undo step); Esc drops it. Ids are kept and never reused; the extra columns (Scale Falloff, scale edits, heading, prototype) reach the instances through
# the hooks of the variation stage (srcscale, align, place_proto; paint_combed drops the random yaw of a combed point).
PAINT_OPS=('add','remove','replace','relax','scale','push','swap','orient','clone')
PAINT_OP_LABELS=('Paint','Erase','Repaint','Relax','Grow / Shrink','Push / Attract','Swap Prototype','Orient / Comb','Clone')
PAINT_OP_BRUSH={'add':'paint','remove':'erase','replace':'repaint','relax':'relax','scale':'scale','push':'push','swap':'replace','orient':'orient','clone':'clone'}      # BrushCore's registry keys (colours, hints)

_PGEO={}
def paint_geo(surface):
    """A hou.Geometry of the paint surface for ray casts (Houdini's own acceleration structure), built once per surface (the old brush tested every triangle with numpy on every mouse move)."""
    P,T=surface[0],surface[1];key=(id(P),len(T))
    hit=_PGEO.get('key')
    if hit is not None and hit[0]==key:return hit[1]
    g=hou.Geometry();g.createPoints([tuple(v) for v in np.asarray(P,dtype=np.float64).tolist()]);g.createPolygons(np.asarray(T,dtype=np.int64).tolist())
    _PGEO['key']=(key,g,surface);return g

def paint_hit(surface,origin,direction,smooth=True):
    """(point, normal facing the ray) where a ray meets the paint surface, or None."""
    g=paint_geo(surface);o=np.asarray(origin,dtype=np.float64);d=np.asarray(direction,dtype=np.float64);d=d/np.linalg.norm(d)
    pos=hou.Vector3();nrm=hou.Vector3();uvw=hou.Vector3();pr=g.intersect(hou.Vector3(tuple(o)),hou.Vector3(tuple(d)),pos,nrm,uvw)
    if pr<0:return None
    p=np.array(tuple(pos));n=_paint_normal(surface,pr,uvw,np.array(tuple(nrm)),smooth)
    if n@d>0:n=-n
    return p,n

def _paint_normal(surface,k,uvw,face,smooth):
    if smooth and len(surface)>4 and surface[4] is not None and len(surface[4]):
        T=surface[1][k];u,v=float(uvw[0]),float(uvw[1]);n=surface[4][T[0]]*(1-u-v)+surface[4][T[1]]*u+surface[4][T[2]]*v;L=np.linalg.norm(n)
        if L>1e-12:return n/L
    L=np.linalg.norm(face);return face/L if L>1e-12 else np.array([0.0,1.0,0.0])

def paint_cast(surface,limit=np.inf,smooth=True):
    """BrushCore's cast for the paint surface: each origin cast along the direction (a hou.Geometry intersect, smooth vertex normals); farther than limit is a miss."""
    g=paint_geo(surface);pos=hou.Vector3();nrm=hou.Vector3();uvw=hou.Vector3()
    def cast(O,d):
        O=np.asarray(O,dtype=np.float64);d=np.asarray(d,dtype=np.float64);d=d/np.linalg.norm(d);P=np.zeros_like(O);N=np.zeros_like(O);ok=np.zeros(len(O),dtype=bool);hd=hou.Vector3(tuple(d))
        for k in range(len(O)):
            pr=g.intersect(hou.Vector3(tuple(O[k])),hd,pos,nrm,uvw)
            if pr<0:continue
            p=np.array(tuple(pos))
            if np.linalg.norm(p-O[k])>limit:continue
            n=_paint_normal(surface,pr,uvw,np.array(tuple(nrm)),smooth)
            if n@d>0:n=-n
            P[k]=p;N[k]=n;ok[k]=True
        return P,N,ok
    return cast

def paint_project(surface):
    """project(points (n, 3), normal, lift) -> points on the surface (cast along -normal from lift above; a miss keeps the point): positions only, no normals, for the cursor rings."""
    g=paint_geo(surface);pos=hou.Vector3();nrm=hou.Vector3();uvw=hou.Vector3()
    def project(P,normal,lift):
        P=np.asarray(P,dtype=np.float64);n=np.asarray(normal,dtype=np.float64);d=hou.Vector3(tuple(-n));O=P+n*lift;out=P.copy()
        for k in range(len(P)):
            if g.intersect(hou.Vector3(tuple(O[k])),d,pos,nrm,uvw)>=0:out[k]=pos[0],pos[1],pos[2]
        return out
    return project

def paint_profile(asset,prefix):
    """A falloff channel of the Paint brush ('dens' or 'scale') as a BrushCore profile, or None (the same parameters as Arraytron Stamp's)."""
    p='paint_%s_'%prefix
    if asset.parm(p+'on') is None or not asset.evalParm(p+'on'):return None
    i=int(asset.evalParm(p+'curve'));kind=BC_CURVES[min(max(i,0),len(BC_CURVES)-1)];lut=None
    if kind=='custom':
        try:lut=bc_lut('custom',asset.parm(p+'ramp').evalAsRamp().lookup)
        except Exception:kind='smoothstep'
    return bc_profile(True,asset.evalParm(p+'min')/100.0,1.0 if prefix=='dens' else asset.evalParm(p+'max')/100.0,asset.evalParm(p+'width')/100.0,asset.evalParm(p+'strength')/100.0,kind,lut=lut)

def paint_preset(asset,name=None):
    """Set the falloff parameters of a preset (BrushCore's BC_PRESETS): the parameters the artist edits, not a second system; Custom changes nothing. name: a key, or None for the Preset menu."""
    idx=BC_PRESETS.index(name) if name is not None else min(max(int(asset.evalParm('paint_preset')),0),len(BC_PRESETS)-1);kind=BC_PRESETS[idx]
    with hou.undos.group('Arraytron paint preset'):
        if name is not None:asset.parm('paint_preset').set(idx)
        for k,v in BC_PRESET_VALUES.get(kind,{}).items():
            if asset.parm('paint_'+k) is not None:asset.parm('paint_'+k).set(v)
    return kind

def paint_falloff_text(asset):
    out=[]
    for name,prefix in (('Density','dens'),('Scale','scale')):
        p=paint_profile(asset,prefix)
        if p is not None:out.append('%s %g>%g%%'%(name,round(100*(1.0+p['strength']*(p['max']-1.0))),round(100*(1.0+p['strength']*(p['min']-1.0)))))
    return '  '.join(out) or 'uniform'

def paint_engine_on(asset):
    """True with Paint Engine 2.0 (Brush Engine Continuous Stroke, the default of v1.36.0); False: the classic dab brush of v0.6.0."""
    return asset.parm('paint_engine') is not None and int(asset.evalParm('paint_engine'))==0

def _pp(asset,name,default):
    return asset.evalParm(name) if asset.parm(name) is not None else default

class PaintStroke(object):
    """Paint on BrushCore's swept field: move(position) for each mouse position, finish() at the end, points() the table as it is now (the base and the new rows), result() the paint data to write.
    The new points get consecutive new ids and their Scale Falloff multiplier in the fall column; the old ones are not touched."""
    def __init__(self,asset,data,surface,normal=(0.0,1.0,0.0)):
        self.data=dict(data);self.base=paint_wide(data['pts']);self.R=max(float(asset.evalParm('paint_radius')),1e-4);self.new=[];self.next=int(data['next']);self.added=0
        self.engine=BrushStroke(self.R,max(float(asset.evalParm('paint_density')),1e-6),float(asset.evalParm('paint_spacing')),int(asset.evalParm('paint_seed')),normal,paint_profile(asset,'dens'),paint_profile(asset,'scale'),
                                self.base[:,0:3],paint_cast(surface,max(self.R*20.0,50.0)),strength=_pp(asset,'paint_strength',1.0),noise=_pp(asset,'paint_noise',0.0))
        self._cache=None
    def _take(self,out):
        P,N,M,K=out;room=max(PAINT_MAX-len(self.base)-self.added,0);k=min(len(P),room)
        if k:self.new.append(paint_rows(P[:k],N[:k],np.arange(self.next,self.next+k),fall=M[:k]));self.next+=k;self.added+=k;self._cache=None
        return k
    def move(self,position,normal=None):return self._take(self.engine.move(position))
    def finish(self):return self._take(self.engine.finish())
    def points(self):
        if self._cache is None:self._cache=np.vstack([self.base]+self.new) if self.new else self.base
        return self._cache
    def result(self):
        d=dict(self.data);d['pts']=self.points();d['next']=self.next;d['dab']=int(self.data['dab'])+1;return d

class PaintEditStroke(object):
    """An editing brush over the painted points (Erase, Relax, Grow / Shrink, Push / Attract, Swap Prototype, Orient / Comb): BrushCore dabs every fifth of the radius along the path, the points under
    a dab from a hash grid, BrushCore's maths on the table in memory. Erase removes points (ids are never reused); moved points are cast back onto the surface (their normal follows it).
    op: the variant ('hard' / 'soft', BC_SCALE_MODES, BC_PUSH_MODES, BC_ORIENT_MODES), None = the brush's own parameter."""
    def __init__(self,asset,data,surface,kind,normal=(0.0,1.0,0.0),op=None):
        self.data=dict(data);self.pts=paint_wide(data['pts']).copy();self.alive=np.ones(len(self.pts),dtype=bool);self.kind=kind;self.asset=asset
        self.R=max(float(asset.evalParm('paint_radius')),1e-4);self.strength=min(max(float(asset.evalParm('paint_strength')),0.0),1.0);self.amount=float(_pp(asset,'brush_amount',0.3))
        self.curve=BC_CURVES[min(max(int(_pp(asset,'brush_curve',1)),0),len(BC_CURVES)-1)];self.hard=float(_pp(asset,'brush_hardness',0.2));self.seed=int(asset.evalParm('paint_seed'))
        modes={'remove':('hard','soft'),'scale':BC_SCALE_MODES,'push':BC_PUSH_MODES,'orient':BC_ORIENT_MODES}
        if op is None and kind in modes:
            if kind=='remove':op='soft' if _pp(asset,'erase_soft',0) else 'hard'
            else:op=modes[kind][min(max(int(_pp(asset,kind+'_mode',0)),0),len(modes[kind])-1)]
        self.op=op;n=np.asarray(normal,dtype=np.float64);self.axis=int(np.argmax(np.abs(n)));self.sign=1.0 if n[self.axis]>=0 else -1.0;self.plane=[a for a in (0,1,2) if a!=self.axis]
        self.cast=paint_cast(surface,max(self.R*20.0,50.0));self.dabs=BrushDabs(self.R*0.2);self.changed=0;self.target=None;self.align=float(asset.evalParm('paint_align'));self._grid()
        self.spacing=float(asset.evalParm('paint_spacing'))
        if kind=='swap':
            rows=paint_swap_pool(asset);self.pool=(np.array([r for r,w in rows]),[w for r,w in rows]) if rows else None
    def _grid(self):
        self.grid=BrushGrid(self.pts[:,self.plane] if len(self.pts) else np.zeros((0,2)),max(self.R*0.5,1e-3));self.moved=0.0
    def _under(self,c,reach=1.0):
        idx=self.grid.query(c[self.plane],self.R*reach+self.moved)
        if len(idx):idx=idx[self.alive[idx]]
        if not len(idx):return idx,np.zeros(0)
        r=np.linalg.norm(self.pts[idx][:,self.plane]-c[self.plane],axis=1)/self.R;k=r<=reach;return idx[k],r[k]
    def move(self,position,normal=None):
        for c in self.dabs.move(np.asarray(position,dtype=np.float64)):self._dab(c)
        return self.changed
    def finish(self):return self.changed
    def _settle(self,idx,new):
        """Moved points back on the surface: cast down at their new place in the stroke plane (from above their old height)."""
        O=self.pts[idx,0:3].copy();O[:,self.plane]=new[:,self.plane];O[:,self.axis]+=self.sign*self.R*2.0;d=np.zeros(3);d[self.axis]=-self.sign;P,N,ok=self.cast(O,d)
        out=self.pts[idx,0:6].copy();out[ok,0:3]=P[ok];out[ok,3:6]=N[ok]
        mv=float(np.max(np.linalg.norm(out[:,0:3]-self.pts[idx,0:3],axis=1))) if len(idx) else 0.0;self.pts[idx,0:6]=out;self.moved+=mv
        if self.moved>self.R*0.25:self._grid()
    def _dab(self,c):
        k=self.kind;dab=self.dabs.count
        if k=='relax':
            idx,r=self._under(c,1.6)
            if len(idx)<2:return
            if self.target is None:self.target=self.spacing if self.spacing>0 else bc_relax_target(self.pts[idx][:,self.plane])
            w=bc_brush_weight(r,self.curve,self.hard)*self.strength;P=self.pts[idx,0:3];new=P.copy();new[:,self.plane]=bc_relax(P[:,self.plane],w,self.target,1.0,2)
            moved=np.linalg.norm(new-P,axis=1)>1e-9
            if moved.any():self._settle(idx[moved],new[moved]);self.changed+=int(moved.sum())
            return
        idx,r=self._under(c)
        if not len(idx):return
        w=bc_brush_weight(r,self.curve,self.hard)*self.strength
        if k=='remove':
            gone=bc_erase(self.pts[idx,6].astype(np.int64),w*min(self.amount,1.0),1.0,self.seed,dab,soft=True) if self.op=='soft' else (w>0)
            self.alive[idx[gone]]=False;self.changed+=int(gone.sum())
        elif k=='scale':
            self.pts[idx,8]=bc_scale(self.pts[idx,8],w,self.op,self.amount*0.25,target=float(_pp(self.asset,'scale_target',1.0)),base=np.ones(len(idx)),neighbors=self.pts[idx,8]);self.changed+=len(idx)
        elif k=='push':
            P=self.pts[idx,0:3];new=bc_push(P,c,w,self.R,self.op,self.amount*0.5,direction=self.dabs.direction(),plane=self.plane);moved=np.linalg.norm(new-P,axis=1)>1e-9
            if moved.any():self._settle(idx[moved],new[moved]);self.changed+=int(moved.sum())
        elif k=='swap':
            if self.pool is None:return
            go,new=bc_replace(self.pts[idx,6].astype(np.int64),w,self.pool[0],self.pool[1],self.strength,self.seed,dab);self.pts[idx[go],11]=new[go];self.changed+=int(go.sum())
        elif k=='orient':
            rows=self.pts[idx];q0=normal_alignment(rows[:,3:6],self.align);Q=paint_align_quats(rows,self.align);up=bc_qrot(q0,np.array([0.0,1.0,0.0]))
            if self.op=='restore':
                on=w>0;self.pts[idx[on],9]=0.0;self.pts[idx[on],10]=0.0;self.changed+=int(on.sum());return
            new=bc_orient(Q,up,w,self.op,self.amount,direction=self.dabs.direction(),center=c,P=rows[:,0:3],ids=rows[:,6].astype(np.int64)*7919+dab,seed=self.seed)
            f0=bc_qrot(q0,np.array([0.0,0.0,1.0]));f1=bc_qrot(new,np.array([0.0,0.0,1.0]))
            yaw=np.arctan2(np.sum(np.cross(f0,f1)*up,axis=1),np.sum(f0*f1,axis=1));on=w>0;self.pts[idx[on],9]=yaw[on];self.pts[idx[on],10]=1.0;self.changed+=int(on.sum())
    def points(self):return self.pts[self.alive]
    def result(self):
        d=dict(self.data);d['pts']=self.pts[self.alive];d['dab']=int(self.data['dab'])+1;return d

def paint_swap_pool(asset):
    """[(bank row, weight)] the Swap Prototype brush draws from: the Swap To row, or (0) every enabled row by its Weight."""
    row=int(_pp(asset,'paint_swap_row',0))
    if row>0:return [(row,1.0)]
    out=[]
    for r in range(1,asset.evalParm('protos')+1):
        if asset.parm('proto_on%d'%r) is not None and asset.evalParm('proto_on%d'%r):out.append((r,max(float(asset.evalParm('proto_weight%d'%r)),0.0)))
    return out

def paint_clone_capture(asset,data,center,normal,radius=None):
    """The painted points within the brush radius of center become the Clone source (hidden parameter paint_clone, JSON; one undo step). Returns how many."""
    import json
    pts=paint_wide(data['pts']);R=float(radius if radius is not None else asset.evalParm('paint_radius'))
    if not len(pts):return 0
    idx=np.nonzero(np.linalg.norm(pts[:,0:3]-np.asarray(center,dtype=np.float64),axis=1)<=R)[0]
    if not len(idx):return 0
    q=paint_align_quats(pts[idx],1.0);cl=bc_clone_capture(pts[idx,0:3],q,np.ones(len(idx)),idx,center,normal)
    out=dict(off=cl['off'].round(5).tolist(),fall=pts[idx,7].round(5).tolist(),edit=pts[idx,8].round(5).tolist(),yaw=pts[idx,9].round(5).tolist(),combed=pts[idx,10].astype(int).tolist(),proto=pts[idx,11].astype(int).tolist(),radius=cl['radius'])
    with hou.undos.group('Arraytron paint: clone source'):asset.parm('paint_clone').set(json.dumps(out))
    return len(idx)

def paint_clone_source(asset):
    import json
    if asset.parm('paint_clone') is None:return None
    try:d=json.loads(asset.evalParm('paint_clone') or '{}')
    except Exception:return None
    if not d.get('off'):return None
    n=len(d['off']);return dict(off=np.array(d['off'],dtype=np.float64),quat=np.tile([0.0,0.0,0.0,1.0],(n,1)),scale=np.ones(n),proto=np.array(d['proto'],dtype=np.int64),fall=np.array(d['fall']),edit=np.array(d['edit']),yaw=np.array(d['yaw']),combed=np.array(d['combed']),radius=float(d['radius']))

def paint_clone_rows(asset,surface,clone,center,normal,next_id,copy=0):
    """The rows of one copy of the Clone source at center (turned by Clone Rotate, plus a random turn per copy, scaled by Clone Scale; every point cast onto the surface; new ids from next_id)."""
    yaw=float(_pp(asset,'clone_yaw',0.0));sc=float(_pp(asset,'clone_scale',1.0))
    if _pp(asset,'clone_random',1):yaw+=float(bc_unit(bc_hash1(np.array([int(copy)]),int(asset.evalParm('paint_seed')),41))[0])*360.0
    W,Q,S,proto=bc_clone_place(clone,center,normal,yaw,sc);n=np.asarray(normal,dtype=np.float64);n=n/np.linalg.norm(n);R=max(clone['radius'],1e-3)*sc
    P,N,ok=paint_cast(surface,R*8.0+2.0)(W+n*(R*2.0+1.0),-n)
    k=int(ok.sum())
    if not k:return np.zeros((0,PAINT_WIDE))
    rows=paint_rows(P[ok],N[ok],np.arange(next_id,next_id+k),fall=clone['fall'][ok]);rows[:,8]=clone['edit'][ok]*sc;rows[:,9]=np.where(clone['combed'][ok]>0,clone['yaw'][ok]+np.radians(yaw),0.0);rows[:,10]=clone['combed'][ok];rows[:,11]=clone['proto'][ok]
    return rows

def paint_brush_select(asset,name):
    """Choose a brush by BrushCore name (paint, erase, relax, scale, push, replace, orient, clone, repaint): the Operation menu. For scripts and the benchmark. Returns True."""
    inv={v:k for k,v in PAINT_OP_BRUSH.items()};op=inv.get(name,name)
    if op not in PAINT_OPS or (PAINT_OPS.index(op)>3 and asset.parm('paint_engine') is None):return None
    asset.parm('paint_op').set(PAINT_OPS.index(op));return True

def brush_select(asset,name):
    """The benchmark's hook (tools/bench_paint_engine.py): the same as paint_brush_select."""
    return paint_brush_select(asset,name)
