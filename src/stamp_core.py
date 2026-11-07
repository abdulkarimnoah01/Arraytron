# Arraytron Stamp 0.9.3 (the light one): the PythonModule of arraytron::stamp::0.9.3.
# The stamps are ONE text parameter (a line per stamp: x y z  rx ry rz  sx sy sz  proto  on), the node is ONE Python LOP that turns them into a UsdGeomPointInstancer.
# Placing a stamp appends a line (one parameter write, no rows to build); the cook parses the text with numpy and writes the arrays.
import hou
import re
import time
import numpy as np
from pxr import Usd, UsdGeom, Sdf, Gf, Vt

STAMP_STATE='arraytron_stamp'
STAMP_TYPE='arraytron::stamp::0.9.3'
STAMP_COLS=11
TC=Usd.TimeCode.EarliestTime()                                          # the pose of the first sample: an animated asset (a rig, a walk) is measured and drawn at its first frame
STAMP_NAMES=('x','y','z','rx','ry','rz','sx','sy','sz','proto','on')

# ---------------------------------------------------------------- pure functions (tested without a viewport)
def stamp_qmul(a,b):
    """Hamilton product (x, y, z, w): the rotation b followed by a. Works on single quaternions and on arrays of them."""
    a=np.asarray(a,dtype=np.float64);b=np.asarray(b,dtype=np.float64);ax,ay,az,aw=a[...,0],a[...,1],a[...,2],a[...,3];bx,by,bz,bw=b[...,0],b[...,1],b[...,2],b[...,3]
    return np.stack([aw*bx+ax*bw+ay*bz-az*by,aw*by-ax*bz+ay*bw+az*bx,aw*bz+ax*by-ay*bx+az*bw,aw*bw-ax*bx-ay*by-az*bz],axis=-1)

def stamp_quat(degrees):
    """Quaternions (x, y, z, w) of rotations about X, then Y, then Z (degrees, R = Rz Ry Rx). degrees: (3,) or (n, 3)."""
    d=np.radians(np.asarray(degrees,dtype=np.float64))*0.5;z=np.zeros(d.shape[:-1])
    qx=np.stack([np.sin(d[...,0]),z,z,np.cos(d[...,0])],axis=-1);qy=np.stack([z,np.sin(d[...,1]),z,np.cos(d[...,1])],axis=-1);qz=np.stack([z,z,np.sin(d[...,2]),np.cos(d[...,2])],axis=-1)
    return stamp_qmul(qz,stamp_qmul(qy,qx))

def stamp_euler(q):
    """Degrees (rx, ry, rz) of one quaternion (x, y, z, w) in the convention of stamp_quat."""
    x,y,z,w=(float(v) for v in np.asarray(q,dtype=np.float64)/np.linalg.norm(q))
    r20=2*(x*z-w*y);ry=-np.arcsin(np.clip(r20,-1.0,1.0))
    if abs(r20)<0.999999:rx=np.arctan2(2*(y*z+w*x),1-2*(x*x+y*y));rz=np.arctan2(2*(x*y+w*z),1-2*(y*y+z*z))
    else:rx=0.0;rz=np.arctan2(-2*(x*y-w*z),1-2*(x*x+z*z))
    return np.degrees([rx,ry,rz])

def stamp_align(normal,amount):
    """Quaternion of the shortest rotation taking +Y onto the normal, blended from the identity by amount (0 = upright)."""
    n=np.asarray(normal,dtype=np.float64);n=n/np.linalg.norm(n);amount=min(max(float(amount),0.0),1.0)
    if amount<=0.0:return np.array([0.0,0.0,0.0,1.0])
    axis=np.cross([0.0,1.0,0.0],n);d=float(n[1]);q=np.array([axis[0],axis[1],axis[2],1.0+d])
    if 1.0+d<1e-9:q=np.array([1.0,0.0,0.0,0.0])
    q=q/np.linalg.norm(q)
    if amount<1.0:
        if q[3]<0:q=-q
        q=q*amount+np.array([0.0,0.0,0.0,1.0])*(1-amount);q=q/np.linalg.norm(q)
    return q

def stamp_snap(value,step):
    return float(value) if step<=0 else float(np.round(float(value)/step)*step)

def stamp_rows(text):
    """The stamps of the text as an (n, 11) float array; lines that are empty or start with # are skipped. A line without exactly 11 numbers is an error."""
    if '#' in text:text='\n'.join(l for l in text.splitlines() if not l.lstrip().startswith('#'))
    tokens=text.split()
    if not tokens:return np.zeros((0,STAMP_COLS))
    try:a=np.array(tokens,dtype=np.float64)
    except ValueError:raise hou.NodeError('Placed Stamps: every value must be a number.')
    if len(a)%STAMP_COLS:raise hou.NodeError('Placed Stamps: every line needs %d numbers (%s), %d values do not fit.'%(STAMP_COLS,' '.join(STAMP_NAMES),len(a)))
    return a.reshape(-1,STAMP_COLS)

def stamp_line(pos,rot,scale,proto,on=1):
    return '%.4f %.4f %.4f  %.3f %.3f %.3f  %.4f %.4f %.4f  %d %d'%(tuple(pos)+tuple(rot)+tuple(scale)+(int(proto),int(on)))

_COUNT=['',0]
def stamp_count(text):
    """How many stamps the text has (len(stamp_lines(text))) without parsing all of it again: the text of the last call is remembered, and a text that only grew by lines at the end costs the new lines."""
    last,n=_COUNT
    if text==last:return n
    n=(n+len(stamp_lines(text[len(last):]))) if last and text.startswith(last) and (last.endswith('\n') or text[len(last):len(last)+1]=='\n') else len(stamp_lines(text))
    _COUNT[0]=text;_COUNT[1]=n;return n

def stamp_lines(text):
    """The non-empty, non-comment lines of the text, as written."""
    return [l for l in text.splitlines() if l.strip() and not l.lstrip().startswith('#')]

# ---------------------------------------------------------------- the Prototype Bank: the same rows as Arraytron's (parameter names included, so the Asset Library adds to it)
TYPE_PRIM,TYPE_INPUT,TYPE_FILE,TYPE_GROUP=range(4)                                          # the menu indices (Arraytron's SOP Geometry is not in the Stamp, so Group Children is 3 here)
TYPE_NAMES=('Prim Path','Input Connection','USD File','Group Children')

def bank_rows(asset):
    """1-based multiparm row numbers of the enabled prototypes, in bank order."""
    return [r for r in range(1,asset.evalParm('protos')+1) if asset.evalParm('proto_on%d'%r)]

def _leaf(text):
    text=text.strip().rstrip('/*').rstrip('/');return text.split('/')[-1] if text else ''

def bank_key(asset):
    """Everything the bank holds, as a tuple (cheap to read: the tool compares it on each mouse move)."""
    return tuple((r,asset.evalParm('proto_type%d'%r),asset.evalParm('proto_prim%d'%r),asset.evalParm('proto_file%d'%r),asset.evalParm('proto_fileprim%d'%r),asset.evalParm('proto_inprim%d'%r),asset.evalParm('proto_input%d'%r),
                  asset.evalParm('proto_weight%d'%r),asset.evalParm('proto_scale%d'%r),asset.evalParm('proto_scalevar%d'%r),tuple(asset.evalParmTuple('proto_rot%d'%r))) for r in bank_rows(asset))

def stamp_labels(asset):
    """[(row, label, type, weight, source text)] of the enabled bank rows, from the parameters only (no stage): what the gallery and the HUD show."""
    out=[]
    for r in bank_rows(asset):
        t=asset.evalParm('proto_type%d'%r)
        if t==TYPE_FILE:src=asset.evalParm('proto_file%d'%r).strip();label=_leaf(re.split(r'[\\/?]',src)[-1].rsplit('.',1)[0]) if src else 'USD File'
        elif t==TYPE_INPUT:src=asset.evalParm('proto_inprim%d'%r).strip();label=_leaf(src) or 'Input %d'%(asset.evalParm('proto_input%d'%r)+2)
        else:src=asset.evalParm('proto_prim%d'%r).strip();label=_leaf(src) or 'Built-in sphere'
        out.append((r,label,t,max(asset.evalParm('proto_weight%d'%r),0.0),src))
    return out

def merged_stage(asset):
    """The stage the bank looks into: the first input and the prototype inputs, merged (the node STAMPS reads it too)."""
    node=asset.node('STAMPS');inputs=node.inputs() if node is not None else ()
    try:return inputs[0].stage() if inputs and inputs[0] is not None else None
    except hou.Error:return None

def _group(stage,row,text):
    """The child prims a group row stands for: /Group, /Group/* or /Group/name* (with * and ? as wildcards); only active prims that can be drawn."""
    import fnmatch
    text=text.strip().rstrip('/')
    if not text:raise hou.NodeError('Prototype %d: Prim Path is empty.'%row)
    parent,_,last=text.rpartition('/')
    if not any(c in last for c in '*?['):parent,last=text,'*'
    group=stage.GetPrimAtPath(parent or '/') if stage is not None else None
    if not group:raise hou.NodeError('Prototype %d: the group %s does not exist in the incoming stage.'%(row,parent or '/'))
    out=[str(c.GetPath()) for c in group.GetChildren() if fnmatch.fnmatchcase(c.GetName(),last) and c.IsActive() and c.IsA(UsdGeom.Imageable) and c.GetName()!='HoudiniLayerInfo']
    if not out:raise hou.NodeError('Prototype %d: no active prim under %s matches %s.'%(row,group.GetPath(),last))
    return out

def _auto_prim(stage):
    tops=[p for p in stage.GetPseudoRoot().GetChildren() if p.GetName()!='HoudiniLayerInfo']
    if not tops:raise hou.NodeError('The connected input has no primitives.')
    if len(tops)>1:raise hou.NodeError('The connected input has several top-level primitives (%s): type the Prim Path.'%', '.join(p.GetName() for p in tops[:4]))
    cur=tops[0]
    while True:
        if Usd.ModelAPI(cur).GetKind() in ('component','assembly') or cur.IsA(UsdGeom.Gprim):return cur
        kids=cur.GetChildren()
        if len(kids)!=1:return cur
        cur=kids[0]

def stamp_entries(asset,stage=None):
    """The enabled bank rows resolved: [dict(row, type, weight, scale, scalevar, rot, srcs)]; srcs is a list of ('sphere',) (an empty Prim Path: the built-in sphere), ('stage', prim path) or
    ('file', file, prim path in it): one for a prim, a file or an input, one per child for a group. Raises hou.NodeError with the row number when a row cannot be used."""
    stage=merged_stage(asset) if stage is None else stage;out=[]
    for r in bank_rows(asset):
        t=asset.evalParm('proto_type%d'%r)
        e=dict(row=r,type=t,weight=max(asset.evalParm('proto_weight%d'%r),0.0),scale=asset.evalParm('proto_scale%d'%r),scalevar=asset.evalParm('proto_scalevar%d'%r),rot=np.array(asset.evalParmTuple('proto_rot%d'%r),dtype=np.float64),srcs=[])
        if t in (TYPE_PRIM,TYPE_GROUP):
            path=asset.evalParm('proto_prim%d'%r).strip()
            if t==TYPE_PRIM and not path:e['srcs']=[('sphere',)]
            elif t==TYPE_GROUP or path.endswith('/*') or any(c in path.rsplit('/',1)[-1] for c in '*?['):e['srcs']=[('stage',p) for p in _group(stage,r,path)]
            else:
                if stage is not None and not stage.GetPrimAtPath(path).IsValid():raise hou.NodeError('Prototype %d: %s is not a prim of the stage.'%(r,path))
                e['srcs']=[('stage',path)]
        elif t==TYPE_INPUT:
            index=asset.evalParm('proto_input%d'%r)+1;inputs=asset.inputs();node=inputs[index] if index<len(inputs) else None
            if node is None:raise hou.NodeError('Prototype %d uses Input %d, which is not connected.'%(r,index+1))
            ins=node.stage()
            if ins is None:raise hou.NodeError('Prototype %d: Input %d has no stage.'%(r,index+1))
            typed=asset.evalParm('proto_inprim%d'%r).strip()
            if typed:
                if not ins.GetPrimAtPath(typed):raise hou.NodeError('Prototype %d: %s does not exist in Input %d.'%(r,typed,index+1))
                e['srcs']=[('stage',typed)]
            else:e['srcs']=[('stage',str(_auto_prim(ins).GetPath()))]
        elif t==TYPE_FILE:
            file=asset.evalParm('proto_file%d'%r).strip()
            if not file:raise hou.NodeError('Prototype %d: USD File is empty.'%r)
            e['srcs']=[('file',file,asset.evalParm('proto_fileprim%d'%r).strip())]
        out.append(e)
    if not out:raise hou.NodeError('The Prototype Bank has no enabled prototypes.')
    return out

_FILES={}
def _src_prim(stage,src):
    """The prim a source stands for, or None: in the stage, or in the USD file (opened once)."""
    if src[0]=='stage':
        prim=stage.GetPrimAtPath(src[1]) if stage is not None else None
        return prim if prim is not None and prim.IsValid() else None
    if src[0]=='file':
        s=_FILES.get(src[1])
        if s is None:
            try:s=Usd.Stage.Open(src[1])
            except Exception:s=False
            _FILES[src[1]]=s
        if not s:return None
        prim=s.GetPrimAtPath(src[2]) if src[2] else s.GetDefaultPrim()
        return prim if prim is not None and prim.IsValid() else None
    return None

def stamp_hash(ids,seed):
    """A number in [0, 1) per id and seed (the same in the cook and in the tool)."""
    return ((np.asarray(ids,dtype=np.int64)*2654435761+int(seed)*40503)%1000003)/1000003.0

def stamp_effective(r,ids,eidx,entries,seed):
    """(orientations (n, 4) x y z w, scales (n, 3)) of stamps with the per-prototype Scale, Scale Random and Rotation Offset of the bank applied: the offset turns the prototype first, then the stamp.
    r: the stamp rows, ids their ids, eidx the entry (index into entries) of each."""
    sc=np.array([e['scale'] for e in entries]);sv=np.array([e['scalevar'] for e in entries]);rot=np.array([e['rot'] for e in entries])
    mult=sc[eidx]*(1.0+sv[eidx]*(2.0*stamp_hash(ids,seed+7)-1.0))
    return stamp_qmul(stamp_quat(r[:,3:6]),stamp_quat(rot[eidx])),r[:,6:9]*mult[:,None]

def stamp_nearest(rows,origin,direction,tolerance=0.03):
    """Index of the stamp closest to the mouse ray (angular tolerance, like Pick Instance), or None."""
    if not len(rows):return None
    o=np.asarray(origin,dtype=np.float64);d=np.asarray(direction,dtype=np.float64);d=d/np.linalg.norm(d);v=rows[:,:3]-o;t=v@d;ok=t>1e-6
    if not ok.any():return None
    dist=np.linalg.norm(v-np.outer(t,d),axis=1);ang=np.where(ok,dist/np.maximum(t,1e-6),np.inf);k=int(np.argmin(ang))
    return k if ang[k]<=tolerance else None

# ---------------------------------------------------------------- editing (one parameter write, one undo step each)
def stamp_settings(asset,group=False):
    """Everything a new stamp draws from, read once (the paint brush makes hundreds of stamps per dab): dict(seed, yaw, yawrand, scale, scalerange, align, tilt, offset, protorand, proto, rows, pool)."""
    labels=stamp_labels(asset);ws=stamp_workset(asset);pool=[l for l in labels if l[0] in ws] or labels                    # Random Prototype draws among the working set (the selected cards), else every enabled row
    cfg=dict(seed=asset.evalParm('seed'),yaw=asset.evalParm('yaw'),yawrand=asset.evalParm('yawrand'),scale=asset.evalParm('scale'),scalerange=tuple(asset.evalParmTuple('scalerange')),align=asset.evalParm('align'),tilt=asset.evalParm('tilt'),
                offset=asset.evalParm('offset'),protorand=asset.evalParm('protorand'),proto=asset.evalParm('proto'),rows=[l[0] for l in labels] or [1],pool=[(l[0],l[3]) for l in pool])
    if group and asset.parm('group_scalerangex') is not None:cfg['scalerange']=tuple(asset.evalParmTuple('group_scalerange'))                              # the Group brush has a Random Scale of its own (off: 1 / 1), not the one of the single stamps
    return cfg

def stamp_make(cfg,n,normal=(0.0,1.0,0.0),yaw=None,scale=None,yaw_add=0.0,scale_mult=1.0,snap_rot=None,proto=None):
    """Stamp number n (1-based) from the settings: dict(n, proto, scale, yaw, quat). Random Rotation / Scale / Tilt / Prototype draw from the Seed and n: the same seed gives the same stamps, more stamps never change
    the earlier ones. yaw / scale given (the drag of the tool sets them): exact, Random Rotation and Random Scale are not applied. yaw_add / scale_mult come on top."""
    r=np.random.RandomState(int(n*104729+cfg['seed']*31+5)%(2**32)).rand(5)
    yaw=(cfg['yaw']+cfg['yawrand']*(2*r[0]-1) if yaw is None else float(yaw))+yaw_add
    if snap_rot:yaw=stamp_snap(yaw,snap_rot)
    if scale is None:lo,hi=cfg['scalerange'];k=cfg['scale']*(lo+(hi-lo)*r[1])
    else:k=float(scale)
    k*=scale_mult
    q=stamp_qmul(stamp_align(normal,cfg['align']),stamp_quat((0.0,yaw,0.0)));tilt=cfg['tilt']
    if tilt>0:q=stamp_qmul(q,stamp_quat((tilt*(2*r[2]-1),0.0,tilt*(2*r[3]-1))))
    rows=cfg['rows']
    if proto is None:
        w=np.array([p[1] for p in cfg['pool']])
        if cfg['protorand'] and len(w) and w.sum()>0:proto=cfg['pool'][int(min(np.searchsorted(np.cumsum(w)/w.sum(),r[4],side='right'),len(w)-1))][0]
        else:proto=cfg['proto'] or rows[0]
    if int(proto) not in rows:proto=rows[0]
    return dict(n=n,proto=int(proto),scale=k,yaw=yaw,quat=q)

def stamp_next(asset,normal=(0.0,1.0,0.0),yaw=None,scale=None,yaw_add=0.0,scale_mult=1.0,snap_rot=None,proto=None,text=None,group=False):
    """What the next stamp will be, with the same random draws stamp_add makes (so the tool can show it before the click): dict(n, proto, scale, yaw, quat) (see stamp_make)."""
    text=asset.evalParm('stamps') if text is None else text
    return stamp_make(stamp_settings(asset,group),stamp_count(text)+1,normal,yaw=yaw,scale=scale,yaw_add=yaw_add,scale_mult=scale_mult,snap_rot=snap_rot,proto=proto)

def stamp_sit(asset,nx,bounds):
    """Sit On Surface: the vector that moves a stamp along its own up axis so the bottom of its prototype's box (bank row Scale included, times the stamp's scale) touches the spot instead of the pivot of the prototype:
    a prototype whose origin is in its middle (a character, a ball) stands on the surface instead of sinking into it, and on top of another stamp it sits on it. Zero when Sit On Surface is off or bounds is None.
    bounds: stamp_proto_bounds. The preview, the click, the paint brush and the group all use this one function."""
    zero=np.zeros(3)
    if bounds is None or asset.parm('sit') is None or not asset.evalParm('sit'):return zero
    b=bounds.get(nx['proto'])
    if b is None:return zero
    up=_quat_matrices(np.asarray(nx['quat'],dtype=np.float64)[None])[0]@np.array([0.0,1.0,0.0]);return up*(-float(b[0][1])*float(nx['scale']))

def stamp_add(asset,position,normal=(0.0,1.0,0.0),yaw_add=0.0,scale_mult=1.0,snap_rot=None,proto=None,rot=None,scale=None,yaw=None,bounds=None):
    """Append one stamp (see stamp_next for the rotation, scale and prototype). rot (degrees) replaces the rotation. Returns the number of the stamp."""
    text=asset.evalParm('stamps');nx=stamp_next(asset,normal,yaw=yaw,scale=scale,yaw_add=yaw_add,scale_mult=scale_mult,snap_rot=snap_rot,proto=proto,text=text)
    degrees=stamp_euler(nx['quat']) if rot is None else rot;k=nx['scale']
    pos=np.asarray(position,dtype=np.float64)+np.asarray(normal,dtype=np.float64)*asset.evalParm('offset')+stamp_sit(asset,nx,bounds)
    line=stamp_line(pos,degrees,(k,k,k),nx['proto'])
    with hou.undos.group('Arraytron Stamp: place'):asset.parm('stamps').set((text.rstrip('\n')+'\n' if text.strip() else '')+line)
    return nx['n']

def stamp_workset(asset):
    """The bank rows of the working set (the selected cards), in bank order: only enabled rows; empty = no working set (every enabled row is in play)."""
    if asset.parm('workset') is None:return []
    live=set(bank_rows(asset));ws={int(v) for v in asset.evalParm('workset').split() if v.isdigit()};return sorted(ws&live)

def stamp_set_workset(asset,rows,proto=None):
    """Set the working set (one undo step with the Prototype Row when proto is given): the cards the wheel cycles through and Random Prototype draws from."""
    rows=sorted({int(r) for r in rows});text=' '.join(str(r) for r in rows)
    with hou.undos.group('Arraytron Stamp: working set'):
        asset.parm('workset').set(text)
        if proto is not None:asset.parm('proto').set(int(proto))
        elif rows and asset.evalParm('proto') not in rows:asset.parm('proto').set(rows[0])

def stamp_cycle(asset,step):
    """The mouse wheel of the Place brush: the next (step 1) or previous (step -1) prototype of the working set (every enabled row when it is empty). Returns the new bank row."""
    rows=stamp_workset(asset) or [l[0] for l in stamp_labels(asset)]
    if not rows:return None
    cur=asset.evalParm('proto') or rows[0];k=rows.index(cur) if cur in rows else 0;new=rows[(k+int(step))%len(rows)]
    with hou.undos.group('Arraytron Stamp: prototype'):asset.parm('proto').set(new)
    return new

# ---- selection and editing of the placed stamps (Edit mode, the table)
def stamp_eulers(q):
    """Degrees (n, 3) of quaternions (n, 4) in the convention of stamp_quat (the vectorised stamp_euler)."""
    q=np.asarray(q,dtype=np.float64).reshape(-1,4);q=q/np.linalg.norm(q,axis=1)[:,None];x,y,z,w=q[:,0],q[:,1],q[:,2],q[:,3]
    r20=2*(x*z-w*y);ry=-np.arcsin(np.clip(r20,-1.0,1.0));lock=np.abs(r20)>=0.999999
    rx=np.where(lock,0.0,np.arctan2(2*(y*z+w*x),1-2*(x*x+y*y)));rz=np.where(lock,np.arctan2(-2*(x*y-w*z),1-2*(x*x+z*z)),np.arctan2(2*(x*y+w*z),1-2*(y*y+z*z)))
    return np.degrees(np.stack([rx,ry,rz],axis=1))

def stamp_get_selection(asset,count=None):
    """The selected stamps (indices of the lines, sorted). Kept in the hidden parameter `selection`."""
    if asset.parm('selection') is None:return np.zeros(0,dtype=np.int64)
    sel=np.array(sorted({int(v) for v in asset.evalParm('selection').split() if v.isdigit()}),dtype=np.int64)
    return sel if count is None else sel[sel<count]

def stamp_set_selection(asset,indices):
    """Select stamps. Not an undo step (a selection is not an edit)."""
    text=' '.join(str(int(i)) for i in sorted({int(j) for j in indices}))
    if asset.parm('selection') is not None and text!=asset.evalParm('selection'):
        with hou.undos.disabler():asset.parm('selection').set(text)

def stamp_handle_delta(parms):
    """The edit handle of Houdini (Move / Rotate / Scale about a pivot, world space, scale then rotate then translate) as dict(t, q, s, c): translate, rotation quaternion, scale and pivot."""
    g=lambda k,d=0.0:float(parms.get(k,d))
    return dict(t=np.array([g('tx'),g('ty'),g('tz')]),q=stamp_quat((g('rx'),g('ry'),g('rz'))),s=np.array([g('sx',1.0),g('sy',1.0),g('sz',1.0)]),c=np.array([g('px'),g('py'),g('pz')]))

def stamp_delta_rows(rows,d):
    """The stamp rows (n, 11) moved, turned and scaled by a handle delta (stamp_handle_delta): positions about the pivot, orientations turned by the same rotation, scales multiplied."""
    R=_quat_matrices(np.asarray(d['q'],dtype=np.float64)[None])[0];out=np.array(rows,dtype=np.float64,copy=True)
    out[:,0:3]=((rows[:,0:3]-d['c'])*d['s'])@R.T+d['c']+d['t'];out[:,3:6]=stamp_eulers(stamp_qmul(d['q'],stamp_quat(rows[:,3:6])));out[:,6:9]=rows[:,6:9]*d['s'];return out

def stamp_selection_pivot(rows,sel):
    """The centre of the selected stamps (where the edit handle sits)."""
    return rows[sel,0:3].mean(axis=0) if len(sel) else np.zeros(3)

def stamp_write_row(lines,rows,i):
    """Replace line i of a list of lines by the row i of an array."""
    r=rows[i];lines[i]=stamp_line(r[0:3],r[3:6],r[6:9],int(r[9]),int(r[10]))

def stamp_select_in_box(asset,project,x0,y0,x1,y1):
    """The stamps whose position projects into the screen box; project(position) -> (x, y) in viewport pixels."""
    rows=stamp_rows(asset.evalParm('stamps'));lo=(min(x0,x1),min(y0,y1));hi=(max(x0,x1),max(y0,y1));out=[]
    for i,r in enumerate(rows):
        p=project(r[0:3])
        if p is not None and lo[0]<=p[0]<=hi[0] and lo[1]<=p[1]<=hi[1]:out.append(i)
    return out

def stamp_duplicate(asset,indices):
    """Copy stamps (the copies are appended and become the selection, which is returned). One undo step."""
    lines=stamp_lines(asset.evalParm('stamps'));idx=[int(i) for i in sorted(set(indices)) if 0<=int(i)<len(lines)]
    if not idx:return []
    new=list(range(len(lines),len(lines)+len(idx)))
    with hou.undos.group('Arraytron Stamp: duplicate'):asset.parm('stamps').set('\n'.join(lines+[lines[i] for i in idx]))
    stamp_set_selection(asset,new);return new

def stamp_delete_many(asset,indices):
    """Remove stamps (one undo step); the selection is cleared. Returns how many went."""
    lines=stamp_lines(asset.evalParm('stamps'));gone={int(i) for i in indices if 0<=int(i)<len(lines)}
    if not gone:return 0
    stamp_set_lines(asset,[l for i,l in enumerate(lines) if i not in gone],'Arraytron Stamp: delete');stamp_set_selection(asset,[]);return len(gone)

def stamp_edit_rows(asset,indices,op='set',**values):
    """Change fields (x, y, z, rx, ry, rz, sx, sy, sz, proto, on) of MANY stamps in one parameter write and one undo step: the table of the Parameters pane edits the selected stamps or all of them.
    op 'set' puts the value in, 'add' adds it to each stamp's own value, 'mul' multiplies it (the prototype row and the on flag are always set). Only the lines that change are rewritten. Returns how many stamps."""
    text=asset.evalParm('stamps');lines=stamp_lines(text);rows=stamp_rows(text);idx=sorted({int(i) for i in indices if 0<=int(i)<len(lines)})
    if not idx or not values:return 0
    a=np.array(idx,dtype=np.int64)
    for k,v in values.items():
        c=STAMP_NAMES.index(k);v=float(v);o=op if c<9 else 'set'
        rows[a,c]=v if o=='set' else rows[a,c]+v if o=='add' else rows[a,c]*v
    for i in idx:stamp_write_row(lines,rows,i)
    stamp_set_lines(asset,lines,'Arraytron Stamp: edit %d'%len(idx));return len(idx)

def stamp_edit_row(asset,index,**values):
    """Change fields of one stamp (see stamp_edit_rows). One undo step."""
    return stamp_edit_rows(asset,[index],**values)>0

# ---- favourites and thumbnails of the cards
def stamp_favorites(asset):
    """The favourite bank rows (the stars of the cards; only rows that still exist)."""
    if asset.parm('favorites') is None:return set()
    return {int(v) for v in asset.evalParm('favorites').split() if v.isdigit()}&set(range(1,asset.evalParm('protos')+1))

def stamp_set_favorite(asset,row,on):
    """Star or unstar a card. Not an undo step (it is a view setting)."""
    favs=stamp_favorites(asset)
    favs.add(int(row)) if on else favs.discard(int(row))
    text=' '.join(str(r) for r in sorted(favs))
    if asset.parm('favorites') is not None and text!=asset.evalParm('favorites'):
        with hou.undos.disabler():asset.parm('favorites').set(text)

def stamp_thumb_sources(asset):
    """{bank row: its first source} (a group row: its first child) for the thumbnails of the cards; {} when the bank cannot be resolved (the cards then keep their drawn icons)."""
    try:return {e['row']:e['srcs'][0] for e in stamp_entries(asset)}
    except hou.Error:return {}

def stamp_thumb_key(src):
    """What a thumbnail of a source depends on (a file also on its modification time), as a string."""
    import os
    if src[0]=='file':
        try:stamp=os.path.getmtime(src[1])
        except OSError:stamp=0
        return 'file|%s|%s|%s'%(src[1],src[2],stamp)
    return '|'.join(str(v) for v in src)

def stamp_decimate(P,T,C,limit):
    """A lighter copy of a mesh (points, triangles, colours): the points are merged on a grid whose cell is the smallest that leaves at most `limit` triangles (the triangles that collapse go, the duplicates
    go). The silhouette stays whole, which skipping every n-th triangle does not give (it leaves holes)."""
    if len(T)<=limit:return P,T,C
    lo=P.min(0);ext=float((P.max(0)-lo).max()) or 1.0;fine,coarse=ext/1500.0,ext;best=None
    def cluster(size):
        k=np.floor((P-lo)/size).astype(np.int64);flat=(k[:,0]*2048+k[:,1])*2048+k[:,2];_,inv=np.unique(flat,return_inverse=True);n=int(inv.max())+1;cnt=np.bincount(inv,minlength=n)
        T2=inv[T];ok=(T2[:,0]!=T2[:,1])&(T2[:,1]!=T2[:,2])&(T2[:,0]!=T2[:,2]);T2=T2[ok]
        if len(T2):_,first=np.unique(np.sort(T2,axis=1),axis=0,return_index=True);T2=T2[np.sort(first)]
        return inv,n,cnt,T2
    for _ in range(10):
        size=float(np.sqrt(fine*coarse));inv,n,cnt,T2=cluster(size)
        if len(T2)<=limit:best=(inv,n,cnt,T2);coarse=size
        else:fine=size
    if best is None:best=cluster(coarse)
    inv,n,cnt,T2=best;P2=np.stack([np.bincount(inv,P[:,a],minlength=n)/cnt for a in range(3)],axis=1);C2=np.stack([np.bincount(inv,C[:,a],minlength=n)/cnt for a in range(3)],axis=1)
    used=np.unique(T2);remap=np.full(n,-1,dtype=np.int64);remap[used]=np.arange(len(used));return P2[used],remap[T2],C2[used]

def stamp_thumb_triangles(asset,src,limit=3000):
    """(points (n, 3), triangles (t, 3), colour (3,)) of one source in the prototype's own space for a thumbnail; None when there is nothing to draw. Decimated to about `limit` triangles."""
    stage=merged_stage(asset)
    if src[0]=='sphere':P,T=_sphere(0.5);return P,T,(0.35,0.6,1.0)
    prim=_src_prim(stage,src)
    if prim is None:return None
    parent=prim.GetParent();P,T=prim_triangles(prim,_matrix(parent) if parent and parent.GetPath()!=Sdf.Path('/') else None)
    if not len(T):return None
    if len(T)>limit:P,T,_=stamp_decimate(P,T,np.zeros_like(P),limit)
    color=(0.62,0.70,0.56)
    for p in Usd.PrimRange(prim,Usd.TraverseInstanceProxies()):
        if p.IsA(UsdGeom.Gprim):
            try:
                shown=UsdGeom.Gprim(p).GetDisplayColorAttr().Get()
                if shown:color=(float(shown[0][0]),float(shown[0][1]),float(shown[0][2]));break
            except Exception:pass
    return P,T,color

GHOST_TRIANGLES=6000

def stamp_ghost_arrays(asset,src,limit=GHOST_TRIANGLES):
    """(points (n, 3), triangles (t, 3), colours (n, 3)) of one source in the prototype's own space, for the ghost under the mouse: the prototype itself (a colour per prim), decimated to about `limit`
    triangles (a dense asset is shown as a lighter copy of itself). None when there is nothing."""
    if src[0]=='sphere':
        P,T=_sphere(0.5);return P,T,np.tile((0.35,0.6,1.0),(len(P),1))
    prim=_src_prim(merged_stage(asset),src)
    if prim is None:return None
    parent=prim.GetParent();P,T,C=prim_triangles(prim,_matrix(parent) if parent and parent.GetPath()!=Sdf.Path('/') else None,colors=True)
    if not len(T):return None
    P,T,C=stamp_decimate(P,T,C,limit)
    tri=P[T];fn=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);vn=np.zeros_like(P)                         # a fixed light baked into the colours (the face drawable is unshaded): two-sided, smooth normals
    for k in range(3):np.add.at(vn,T[:,k],fn)
    ln=np.linalg.norm(vn,axis=1);ln[ln==0]=1.0;light=np.array([0.35,0.8,0.5]);light/=np.linalg.norm(light)
    C=C*(0.38+0.62*np.abs(vn/ln[:,None]@light))[:,None]
    return P,T,C

def stamp_ghost_geo(arrays):
    """A hou.Geometry (polygons, a colour Cd per point) from stamp_ghost_arrays."""
    P,T,C=arrays;geo=hou.Geometry();geo.addAttrib(hou.attribType.Point,'Cd',(1.0,1.0,1.0))
    geo.createPoints([tuple(v) for v in P.tolist()]);geo.createPolygons(T.tolist());geo.setPointFloatAttribValues('Cd',C.ravel().tolist());return geo

def stamp_xform(pos,quat,scale):
    """A hou.Matrix4 (row vectors: scale, then rotate, then translate) of a stamp: position, quaternion (x, y, z, w), scale (3)."""
    R=_quat_matrices(np.asarray(quat,dtype=np.float64)[None])[0];s=np.broadcast_to(np.asarray(scale,dtype=np.float64),(3,));A=np.diag(s)@R.T
    return hou.Matrix4((A[0,0],A[0,1],A[0,2],0.0,A[1,0],A[1,1],A[1,2],0.0,A[2,0],A[2,1],A[2,2],0.0,float(pos[0]),float(pos[1]),float(pos[2]),1.0))

def stamp_next_xform(asset,nx,position,normal,entries=None):
    """What the next stamp will look like for the ghost: (bank row, child index, hou.Matrix4). nx is stamp_next; the bank row's Scale, Scale Random and Rotation Offset are included, as the cook applies them."""
    entries=stamp_entries(asset) if entries is None else entries;rowmap={e['row']:i for i,e in enumerate(entries)};i=rowmap.get(nx['proto'],0);e=entries[i]
    ident=nx['n']-1;seed=asset.evalParm('seed');child=int((ident*2654435761+seed)%len(e['srcs']))
    rows=np.zeros((1,STAMP_COLS));rows[0,3:6]=stamp_euler(nx['quat']);rows[0,6:9]=nx['scale'];q,S=stamp_effective(rows,np.array([ident]),np.array([i]),entries,seed)
    pos=np.asarray(position,dtype=np.float64)+np.asarray(normal,dtype=np.float64)*asset.evalParm('offset')
    return nx['proto'],child,stamp_xform(pos,q[0],S[0])

def gallery_status(node_type):
    """(loaded, text): whether the Stamp's Parameters pane is registered for this node type; the text says what to do when it is not."""
    import os
    if not hou.isUIAvailable():return True,'Parameters pane: no interface.'
    if os.environ.get('ARRAYTRON_NO_PARM_PANEL'):return False,'Parameters pane: switched off (ARRAYTRON_NO_PARM_PANEL), the plain dialog is shown.'
    tag=''.join(ch if ch.isalnum() else '_' for ch in node_type.name())
    try:
        if hou.pypanel.interfaceByName('arraytron_stamp_%s'%tag) is not None and node_type.nameWithCategory() in _PANEL_DONE:return True,'Parameters pane: loaded.'
    except Exception:pass
    return False,'Parameters pane: NOT loaded, this is the plain dialog (no cards, no stamps table). Press Reload Stamp Pane, then select the node again.'

def stamp_reload_pane(asset):
    """Options > Reload Stamp Pane: register the pane again for this node type."""
    _PANEL_DONE.discard(asset.type().nameWithCategory());return gallery_install(asset.type())

def stamp_pane_text(asset):
    return gallery_status(asset.type())[1]

def stamp_selection_info(asset):
    """'3 of 120 stamps selected': the read-only line of the Edit tab."""
    n=len(stamp_lines(asset.evalParm('stamps')));k=len(stamp_get_selection(asset,n))
    return 'No stamps yet.' if not n else '%d of %d stamp%s selected.'%(k,n,'' if n==1 else 's')

def stamp_select_all(asset):
    stamp_set_selection(asset,range(len(stamp_lines(asset.evalParm('stamps')))))

def stamp_select_none(asset):
    stamp_set_selection(asset,[])

def stamp_select_invert(asset):
    n=len(stamp_lines(asset.evalParm('stamps')));sel=set(stamp_get_selection(asset,n).tolist());stamp_set_selection(asset,[i for i in range(n) if i not in sel])

def stamp_counts(asset,text=None):
    """{bank row: how many stamps use it}: the counts of the cards."""
    try:rows=stamp_rows(asset.evalParm('stamps') if text is None else text)
    except hou.Error:return {}
    if not len(rows):return {}
    keys,counts=np.unique(rows[:,9].astype(np.int64),return_counts=True);return {int(k):int(c) for k,c in zip(keys,counts)}

def stamp_select_proto(asset,row):
    """Select every stamp of a prototype (the Edit mode shows them, the table highlights them). Returns how many."""
    rows=stamp_rows(asset.evalParm('stamps'));idx=np.nonzero(rows[:,9].astype(np.int64)==int(row))[0] if len(rows) else []
    stamp_set_selection(asset,idx);return len(idx)

def stamp_delete_proto(asset,row):
    """Remove every stamp of a prototype (one undo step). Returns how many."""
    rows=stamp_rows(asset.evalParm('stamps'));idx=np.nonzero(rows[:,9].astype(np.int64)==int(row))[0] if len(rows) else []
    return stamp_delete_many(asset,idx) if len(idx) else 0

def stamp_duplicate_selected(asset):
    return stamp_duplicate(asset,stamp_get_selection(asset,len(stamp_lines(asset.evalParm('stamps')))))

def stamp_delete_selected(asset):
    return stamp_delete_many(asset,stamp_get_selection(asset,len(stamp_lines(asset.evalParm('stamps')))))

def stamp_add_batch(asset,positions,normals,snap_rot=None,cfg=None,bounds=None):
    """Append many stamps with one parameter write (the paint brush): each one is the stamp it would be if placed by a click (same draws, in order). Returns how many."""
    positions=np.asarray(positions,dtype=np.float64).reshape(-1,3);normals=np.asarray(normals,dtype=np.float64).reshape(-1,3)
    if not len(positions):return 0
    text=asset.evalParm('stamps');cfg=cfg or stamp_settings(asset);n0=stamp_count(text);new=[]
    for k in range(len(positions)):
        nx=stamp_make(cfg,n0+k+1,normals[k],snap_rot=snap_rot);s=nx['scale']
        new.append(stamp_line(positions[k]+normals[k]*cfg['offset']+stamp_sit(asset,nx,bounds),stamp_euler(nx['quat']),(s,s,s),nx['proto']))
    with hou.undos.group('Arraytron Stamp: paint'):asset.parm('stamps').set((text.rstrip('\n')+'\n' if text.strip() else '')+'\n'.join(new))
    return len(new)

# ---- the Group brush: several prototypes stamped at once, in a radial layout or in the layout of stamps the artist placed
GROUP_COLS=8                                                                                  # a custom member: bank row, x y z offset from the group, rx ry rz, scale

GROUP_LAYOUTS=('radial','square','hexagon','cluster','line','spiral','custom')
GROUP_LAYOUT_LABELS=('Radial','Square','Hexagon','Random Cluster','Line','Spiral','Custom (from selected stamps)')

def stamp_group_data(asset):
    """The custom layout kept in the hidden parameter `group` as an (n, 8) array: bank row, x y z (from the centre of the group, y from its lowest member), rx ry rz, scale. Empty: nothing captured."""
    none=np.zeros((0,GROUP_COLS))
    if asset.parm('group') is None:return none
    try:a=np.array(asset.evalParm('group').split(),dtype=np.float64)
    except ValueError:return none
    return a.reshape(-1,GROUP_COLS) if len(a) and len(a)%GROUP_COLS==0 else none

def stamp_group_layout(asset):
    """The layout in use: one of GROUP_LAYOUTS ('custom' only when stamps were captured, else the radial one)."""
    k=min(max(int(asset.evalParm('group_layout')),0),len(GROUP_LAYOUTS)-1) if asset.parm('group_layout') is not None else 0
    return 'radial' if GROUP_LAYOUTS[k]=='custom' and not len(stamp_group_data(asset)) else GROUP_LAYOUTS[k]

def stamp_group_custom(asset):
    """The captured layout when it is the one in use (Layout: Custom), else an empty array."""
    return stamp_group_data(asset) if stamp_group_layout(asset)=='custom' else np.zeros((0,GROUP_COLS))

def stamp_group_capture(asset,indices=None):
    """Make the layout of the selected stamps (or of indices) the layout of the Group brush (Layout: Custom): their positions around their centre, their rotations and scales. One undo step. Returns how many members (0: nothing selected)."""
    rows=stamp_rows(asset.evalParm('stamps'));sel=stamp_get_selection(asset,len(rows)) if indices is None else np.array([int(i) for i in indices if 0<=int(i)<len(rows)],dtype=np.int64)
    if not len(sel):return 0
    r=rows[sel];centre=np.array([r[:,0].mean(),r[:,1].min(),r[:,2].mean()]);out=[]
    for k in range(len(r)):
        o=r[k,0:3]-centre;out.append('%d %.4f %.4f %.4f  %.3f %.3f %.3f  %.4f'%((int(r[k,9]),)+tuple(o)+tuple(r[k,3:6])+(float(r[k,6:9].mean()),)))
    with hou.undos.group('Arraytron Stamp: group layout'):
        asset.parm('group').set('\n'.join(out))
        if asset.parm('group_layout') is not None:asset.parm('group_layout').set(GROUP_LAYOUTS.index('custom'))
    return len(out)

def stamp_group_capture_selected(asset):
    """The button and the hotkey: the layout of the Group brush from the selected stamps; says so when nothing is selected."""
    n=stamp_group_capture(asset)
    if n:
        with hou.undos.disabler():asset.parm('brush').set(3);asset.parm('mode1').set(0)
    elif hou.isUIAvailable():hou.ui.setStatusMessage('Arraytron Stamp: select stamps first (Edit mode), then set the group layout from them.',severity=hou.severityType.Warning)
    return n

def stamp_group_reset(asset):
    """Back to the radial layout (the captured layout is forgotten)."""
    with hou.undos.group('Arraytron Stamp: radial group'):
        if asset.parm('group') is not None and asset.evalParm('group').strip():asset.parm('group').set('')
        if asset.parm('group_layout') is not None and asset.evalParm('group_layout')!=0:asset.parm('group_layout').set(0)

def stamp_group_info(asset):
    """'Group: radial, 3 prototypes' or 'Group: custom layout, 5 stamps': what the Group brush places (the HUD, the Group tab)."""
    c=stamp_group_custom(asset)
    if len(c):return 'Group: custom layout, %d stamps'%len(c)
    cnt=asset.evalParm('group_count') if asset.parm('group_count') is not None else 0;ws=stamp_workset(asset);k=cnt or max(len(ws),1)
    return 'Group: %s, %d prototype%s%s'%(GROUP_LAYOUT_LABELS[GROUP_LAYOUTS.index(stamp_group_layout(asset))].lower(),k,'' if k==1 else 's',' (random draw)' if cnt else '')

def stamp_group_offsets(kind,rad,sp,rng):
    """The ground offsets (m, 2: x, z) of m members of a layout, centred, at least their radii (rad) times sp apart. radial: a ring | square: a grid | hexagon: a hexagonal lattice from the middle out |
    cluster: random positions in a disc (from rng) | line: along X | spiral: a sunflower spiral."""
    m=len(rad);rmax=max(rad);pitch=2*rmax*sp
    if m==1:return np.zeros((1,2))
    if kind=='radial':
        R=max((rad[i]+rad[(i+1)%m])*sp for i in range(m))/(2*np.sin(np.pi/m));a=2*np.pi*np.arange(m)/m;return np.stack([R*np.sin(a),R*np.cos(a)],axis=1)
    if kind=='square':
        cols=int(np.ceil(np.sqrt(m)));P=np.array([[(k%cols)*pitch,(k//cols)*pitch] for k in range(m)],dtype=np.float64)
    elif kind=='hexagon':
        pts=sorted(((pitch*(q+r/2.0),pitch*r*np.sqrt(3.0)/2.0) for q in range(-6,7) for r in range(-6,7)),key=lambda p:(round(p[0]**2+p[1]**2,6),float(np.arctan2(p[1],p[0]))));P=np.array(pts[:m],dtype=np.float64)
    elif kind=='line':
        P=np.stack([np.concatenate([[0.0],np.cumsum([(rad[i]+rad[i+1])*sp for i in range(m-1)])]),np.zeros(m)],axis=1)
    elif kind=='spiral':
        k=np.arange(m);P=np.stack([pitch*0.7*np.sqrt(k)*np.sin(k*2.399963),pitch*0.7*np.sqrt(k)*np.cos(k*2.399963)],axis=1)
    else:
        R0=pitch*np.sqrt(m)*0.75;P=[];tries=0
        while len(P)<m:
            p=rng.uniform(-1.0,1.0,2);tries+=1
            if p@p>1.0:continue
            p=p*R0
            if all(np.linalg.norm(p-q)>=(rad[len(P)]+rad[j])*sp for j,q in enumerate(P)):P.append(p)
            elif tries%200==0:R0*=1.15
        P=np.array(P)
    P=P-P.mean(axis=0);worst=min(np.linalg.norm(P[i]-P[j])/((rad[i]+rad[j])*sp) for i in range(m) for j in range(i))
    return P/worst if worst<1.0-1e-9 else P

def stamp_group_items(asset,n,bounds,cfg=None):
    """The members of the Group brush for stamp number n: ([dict(row, off (3), quat, scale)], radius of the whole group). Layout Custom: as captured. Else one member per selected card (the current prototype when none is
    selected; Count > 0 draws that many from the selected cards by weight; Shuffle Order mixes them) placed by the Layout (stamp_group_offsets) far enough apart that their sizes times Spacing do not touch.
    Match Member Sizes (on) scales every member to the same size (the median of their sizes) so a tiny prototype is not lost next to a big one; Random Member Scale and Rotation vary them (off: all alike). All from the Seed and n."""
    cfg=cfg or stamp_settings(asset);rows=cfg['rows'];unit=lambda r:stamp_footprint(bounds[r]) if r in bounds else 0.5;custom=stamp_group_custom(asset);items=[]
    rng2=np.random.RandomState(int(n*104729+cfg['seed']*31+13)%(2**31));lo,hi=sorted(asset.evalParmTuple('group_member_scale'));turn=asset.evalParm('group_member_rot')
    def vary(it):
        it['scale']*=lo+(hi-lo)*rng2.rand()
        if turn>0:it['quat']=stamp_qmul(stamp_quat((0.0,turn*(2*rng2.rand()-1),0.0)),it['quat'])
        return it
    if len(custom):
        for c in custom:
            row=int(c[0]) if int(c[0]) in rows else rows[0];items.append(vary(dict(row=row,off=c[1:4].copy(),quat=stamp_quat(c[4:7]),scale=float(c[7]))))
        return items,max(float(np.hypot(it['off'][0],it['off'][2]))+unit(it['row'])*it['scale'] for it in items)
    rng=np.random.RandomState(int(n*104729+cfg['seed']*31+11)%(2**31));ws=stamp_workset(asset);count=int(asset.evalParm('group_count'))
    if count>0:
        pool=cfg['pool'];w=np.array([p[1] for p in pool],dtype=np.float64);p=w/w.sum() if w.sum()>0 else None;members=[pool[int(k)][0] for k in rng.choice(len(pool),count,p=p)]
    else:
        members=list(ws) or [cfg['proto'] if cfg['proto'] in rows else rows[0]]
        if asset.evalParm('group_shuffle'):rng.shuffle(members)
    by_row={r:(float(np.max(bounds[r][1]-bounds[r][0])) if r in bounds else 1.0) for r in set(members)};by_row={r:(s if s>1e-9 else 1.0) for r,s in by_row.items()};target=float(np.median(list(by_row.values())))      # the median over the different prototypes, not over the members (six firs and a stone would be matched to the fir)
    match=np.array([np.clip(target/by_row[r],0.05,20.0) for r in members]) if asset.evalParm('group_match') else np.ones(len(members))
    rad=[unit(r)*match[i]*max(hi,1e-3) for i,r in enumerate(members)];off=stamp_group_offsets(stamp_group_layout(asset),rad,max(asset.evalParm('group_spacing'),0.01),rng)
    for i,row in enumerate(members):items.append(vary(dict(row=int(row),off=np.array([off[i,0],0.0,off[i,1]]),quat=np.array([0.0,0.0,0.0,1.0]),scale=float(match[i]))))
    return items,max(float(np.hypot(it['off'][0],it['off'][2]))+unit(it['row'])*it['scale'] for it in items)

def stamp_group_place(asset,items,radius,nx,position,normal,surf=None,bounds=None):
    """Where the members of a group stamp go: [dict(proto, pos, quat, scale)]. nx is the stamp of the whole group (stamp_make: rotation and scale of the group, the Align To Surface frame); each member is moved by its offset in
    that frame and, with Conform To Surface, dropped onto the surface under it (the ground, not the stamps), keeping its height above the lowest member of a custom layout. The same function gives the preview and the stamps."""
    R=_quat_matrices(np.asarray(nx['quat'],dtype=np.float64)[None])[0];k=float(nx['scale']);nrm=np.asarray(normal,dtype=np.float64);nrm=nrm/np.linalg.norm(nrm);up=R@np.array([0.0,1.0,0.0]);pos0=np.asarray(position,dtype=np.float64)
    conform=bool(asset.evalParm('group_conform')) and surf is not None;lift=radius*k*1.5+0.2;off=asset.evalParm('offset');out=[];stamps=bool(asset.evalParm('onstamps'))
    if conform and stamps and len(items):                                                           # the rays of a group lie in one small area: they test the few stamps there, not every stamp
        ends=np.array([[pos0+R@np.array([it['off'][0]*k,0.0,it['off'][2]*k])+s*nrm*lift for it in items] for s in (1.0,-1.0)]).reshape(-1,3);surf=surf.near(ends[:,[0,2]].min(axis=0)-1e-6,ends[:,[0,2]].max(axis=0)+1e-6)
    for it in items:
        local=it['off']*k;p=pos0+R@np.array([local[0],0.0,local[2]])
        if conform:
            h=surf.hit(p+nrm*lift,-nrm,stamps=stamps)
            if h is not None and h[2]<=lift*2:p=np.asarray(h[0],dtype=np.float64)
        q=stamp_qmul(nx['quat'],it['quat']);sc=k*it['scale'];out.append(dict(proto=int(it['row']),pos=p+up*local[1]+nrm*off+stamp_sit(asset,dict(proto=int(it['row']),quat=q,scale=sc),bounds),quat=q,scale=sc))
    return out

def stamp_group_add(asset,surf,position,normal,yaw=None,scale=None,snap_rot=None,bounds=None,cfg=None):
    """Place a group: one stamp per member, one parameter write, one undo step. yaw / scale (the drag) set the rotation and scale of the whole group. Returns how many stamps."""
    text=asset.evalParm('stamps');cfg=cfg or stamp_settings(asset,True);bounds=stamp_proto_bounds(asset) if bounds is None else bounds
    nx=stamp_make(cfg,stamp_count(text)+1,normal,yaw=yaw,scale=scale,snap_rot=snap_rot);items,radius=stamp_group_items(asset,nx['n'],bounds,cfg)
    new=[stamp_line(p['pos'],stamp_euler(p['quat']),(p['scale'],)*3,p['proto']) for p in stamp_group_place(asset,items,radius,nx,position,normal,surf,bounds)]
    with hou.undos.group('Arraytron Stamp: place group'):asset.parm('stamps').set((text.rstrip('\n')+'\n' if text.strip() else '')+'\n'.join(new))
    return len(new)

def stamp_tangent(normal):
    """Two unit vectors on the plane of a normal."""
    n=np.asarray(normal,dtype=np.float64);n=n/np.linalg.norm(n);helper=np.array([0.0,0.0,1.0]) if abs(n[1])>0.9 else np.array([0.0,1.0,0.0])
    u=np.cross(helper,n);u/=np.linalg.norm(u);return u,np.cross(n,u)

def stamp_paint_dab(surf,center,normal,radius,density,spacing,falloff,rng,existing,fraction=0.5):
    """One dab of the Paint brush: new positions and normals on the surface under a disc of the given radius around the hit. The number of candidates is density (per unit area) x the area x fraction
    (stochastic rounding, at most 400); the edge falloff thins them towards the rim; each candidate is cast onto the surface along the normal (the stamps are not hit: paint goes on the ground, not on the
    stamps); a candidate closer than spacing to an existing stamp or to one accepted earlier is dropped. Returns (positions (n, 3), normals (n, 3))."""
    none=(np.zeros((0,3)),np.zeros((0,3)))
    expected=density*np.pi*radius*radius*fraction;k=int(expected)+(1 if rng.rand()<expected-int(expected) else 0);k=min(k,400)
    if k<=0 or radius<=0:return none
    u,v=stamp_tangent(normal);nrm=np.asarray(normal,dtype=np.float64);nrm=nrm/np.linalg.norm(nrm)
    rr=radius*np.sqrt(rng.rand(k));ang=2*np.pi*rng.rand(k);keep=rng.rand(k)>=falloff*(rr/radius)**2
    cand=np.asarray(center,dtype=np.float64)+np.outer(rr*np.cos(ang),u)+np.outer(rr*np.sin(ang),v);lift=radius*1.5+0.05
    ex=np.asarray(existing,dtype=np.float64).reshape(-1,3)
    if len(ex) and spacing>0:ex=ex[np.linalg.norm(ex-np.asarray(center),axis=1)<radius*2.0+spacing]
    pos=[];nor=[]
    for p in cand[keep]:
        h=surf.hit(p+nrm*lift,-nrm,stamps=False)
        if h is None or h[2]>lift+radius*1.5:continue
        q=h[0]
        if spacing>0:
            if len(ex) and np.min(np.linalg.norm(ex-q,axis=1))<spacing:continue
            if pos and np.min(np.linalg.norm(np.array(pos)-q,axis=1))<spacing:continue
        pos.append(q);nor.append(h[1])
    return (np.array(pos),np.array(nor)) if pos else none

# ---------------------------------------------------------------- Paint falloff: a Density and a Scale profile over the swept stroke
# The Paint brush can thin the stamps (Density Falloff) and shrink them (Scale Falloff) towards the rim of the brush. Both read ONE spatial field: the distance of a candidate stamp to the
# whole path of the stroke (not to the dab that happened to make it), so a stroke is a ribbon with a soft edge, with no circles at the dabs, and the same coverage at any mouse speed.
# The candidates are the points of a world-fixed jittered grid (one per 1 / Density of area, from the Seed), each with its own threshold: a candidate is made when its threshold is below the Density
# multiplier at its place, so thinning is statistical and nested, and painting the same place again finds the same candidates (the Spacing then keeps them from doubling up).
FALLOFF_CURVES=('linear','smoothstep','smootherstep','ease_in','ease_out','custom')
FALLOFF_CURVE_LABELS=('Linear','Smoothstep','Smootherstep','Ease In','Ease Out','Custom Ramp')
PAINT_PRESETS=('uniform','soft','sparse','growth','dense','custom')
PAINT_PRESET_LABELS=('Uniform (no falloff)','Soft Natural','Sparse Edges','Growth','Dense Center','Custom')
PAINT_PRESET_VALUES={'uniform':dict(dens_on=0,scale_on=0),
 'soft':dict(dens_on=1,dens_min=5,dens_width=75,dens_strength=100,dens_curve=2,scale_on=1,scale_min=35,scale_max=100,scale_width=85,scale_strength=100,scale_curve=1),
 'sparse':dict(dens_on=1,dens_min=0,dens_width=80,dens_strength=100,dens_curve=2,scale_on=1,scale_min=70,scale_max=100,scale_width=60,scale_strength=100,scale_curve=1),
 'growth':dict(dens_on=1,dens_min=30,dens_width=60,dens_strength=70,dens_curve=1,scale_on=1,scale_min=12,scale_max=100,scale_width=100,scale_strength=100,scale_curve=1),
 'dense':dict(dens_on=1,dens_min=0,dens_width=100,dens_strength=100,dens_curve=4,scale_on=1,scale_min=85,scale_max=100,scale_width=100,scale_strength=60,scale_curve=1)}
_LUT_U=np.linspace(0.0,1.0,257)

def falloff_curve(kind,u):
    """How much of the fall is done at u (0 = the inner edge of the transition, 1 = the rim), for the curve kinds (custom is not here: it is a ramp)."""
    u=np.clip(np.asarray(u,dtype=np.float64),0.0,1.0)
    if kind=='smoothstep':return u*u*(3.0-2.0*u)
    if kind=='smootherstep':return u*u*u*(u*(u*6.0-15.0)+10.0)
    if kind=='ease_in':return u*u
    if kind=='ease_out':return 1.0-(1.0-u)**2
    return u

def falloff_lut(asset,prefix):
    """The influence (1 at the inner edge of the transition, 0 at the rim) at 257 steps of u: the preset curve, or the Custom Ramp (its left is the rim, its right the inner edge; default a straight ramp)."""
    i=int(asset.evalParm('paint_%s_curve'%prefix));kind=FALLOFF_CURVES[min(max(i,0),len(FALLOFF_CURVES)-1)]
    if kind=='custom':
        try:ramp=asset.parm('paint_%s_ramp'%prefix).evalAsRamp();return np.clip(np.array([ramp.lookup(1.0-float(u)) for u in _LUT_U],dtype=np.float64),0.0,1.0)
        except Exception:kind='smoothstep'
    return 1.0-falloff_curve(kind,_LUT_U)

def stamp_falloff_profile(asset,prefix):
    """The settings of one channel ('dens' or 'scale') as a dict, or None when it is off: min, max (the multiplier at the rim and at the centre), inner (the radius where the fall starts, 0..1), strength, lut."""
    p='paint_%s_'%prefix
    if asset.parm(p+'on') is None or not asset.evalParm(p+'on'):return None
    mx=1.0 if prefix=='dens' else asset.evalParm(p+'max')/100.0
    return dict(min=asset.evalParm(p+'min')/100.0,max=mx,inner=1.0-min(max(asset.evalParm(p+'width')/100.0,0.0),1.0),strength=min(max(asset.evalParm(p+'strength')/100.0,0.0),1.0),lut=falloff_lut(asset,prefix))

def falloff_multiplier(profile,r):
    """The multiplier of a channel at the normalised distance r from the stroke (0 on it, 1 at the rim): lerp(min, max, influence), blended with 1 by Strength. None (off): 1.
    u = clamp((r - inner) / (1 - inner)) is the place inside the transition; influence = the curve at u."""
    r=np.asarray(r,dtype=np.float64)
    if profile is None:return np.ones_like(r)
    u=np.clip((r-profile['inner'])/max(1.0-profile['inner'],1e-6),0.0,1.0);m=profile['min']+(profile['max']-profile['min'])*np.interp(u,_LUT_U,profile['lut']);return 1.0+profile['strength']*(m-1.0)

def stamp_paint_active(asset):
    """True when the swept-field engine paints (Density or Scale Falloff on); False: the Paint brush works as before (dabs, the Edge Falloff)."""
    return asset.parm('paint_dens_on') is not None and bool(asset.evalParm('paint_dens_on') or asset.evalParm('paint_scale_on'))

def stamp_falloff_text(asset):
    """'Density 100 > 5 %   Scale 100 > 35 %' or 'off': the HUD line of the Paint brush."""
    if not stamp_paint_active(asset):return 'off (Edge Falloff %.2g)'%asset.evalParm('paint_falloff') if asset.parm('paint_falloff') is not None else 'off'
    out=[]
    for name,prefix in (('Density','dens'),('Scale','scale')):
        p=stamp_falloff_profile(asset,prefix)
        if p is not None:out.append('%s %g > %g %%'%(name,round(100*(1.0+p['strength']*(p['max']-1.0)),1),round(100*(1.0+p['strength']*(p['min']-1.0)),1)))
    return '   '.join(out)

def stamp_paint_preset(asset,name=None):
    """Set the falloff parameters of a preset (Uniform, Soft Natural, Sparse Edges, Growth, Dense Center): the same parameters the artist edits, not a second system; Custom changes nothing. name: a key of PAINT_PRESETS, or None to take the Preset menu."""
    idx=PAINT_PRESETS.index(name) if name is not None else min(max(int(asset.evalParm('paint_preset')),0),len(PAINT_PRESETS)-1);kind=PAINT_PRESETS[idx]
    with hou.undos.group('Arraytron Stamp: paint preset'):
        if name is not None:asset.parm('paint_preset').set(idx)
        for k,v in PAINT_PRESET_VALUES.get(kind,{}).items():asset.parm('paint_'+k).set(v)
    return kind

def _mix64(x):
    x=np.asarray(x,dtype=np.uint64)
    with np.errstate(over='ignore'):
        x=(x^(x>>np.uint64(30)))*np.uint64(0xbf58476d1ce4e5b9);x=(x^(x>>np.uint64(27)))*np.uint64(0x94d049bb133111eb);return x^(x>>np.uint64(31))

def _cell_hash(i,j,seed,k):
    """A 64 bit hash per grid cell (arrays i, j), for the Seed and the stream k: the same cell always gives the same numbers, whatever order the stroke reaches it in."""
    with np.errstate(over='ignore'):
        return _mix64(_mix64(i.astype(np.int64).astype(np.uint64)*np.uint64(0x9E3779B97F4A7C15)+j.astype(np.int64).astype(np.uint64)*np.uint64(0xC2B2AE3D27D4EB4F))+np.uint64(int(seed)*2654435761+k*40503+1))

def _unit(h):
    return (h>>np.uint64(11)).astype(np.float64)*(1.0/9007199254740992.0)

def stamp_paint_lines(asset,positions,normals,mults,nkeys,cfg,bounds=None):
    """The lines of the stamps made by the swept-field stroke: each is the stamp stamp_make draws for its own key (so it does not depend on the order of the stroke), scaled by its Scale Falloff multiplier,
    on the surface with Offset and Sit On Surface after the scale."""
    new=[];snap=asset.evalParm('snaprot') or None
    for p,n,m_,key in zip(positions,normals,mults,nkeys):
        nx=stamp_make(cfg,int(key),n,snap_rot=snap,scale_mult=float(m_));s=nx['scale'];new.append(stamp_line(np.asarray(p)+np.asarray(n)*cfg['offset']+stamp_sit(asset,nx,bounds),stamp_euler(nx['quat']),(s,s,s),nx['proto']))
    return new

def stamp_append_lines(asset,new):
    """Add lines to the Stamps text with one parameter write (one undo step). The write costs as much as the whole text is long (a parameter of 10 000 stamps: about 45 ms): a stroke writes as few times as it can."""
    if not new:return 0
    text=asset.evalParm('stamps')
    with hou.undos.group('Arraytron Stamp: paint'):asset.parm('stamps').set((text.rstrip('\n')+'\n' if text.strip() else '')+'\n'.join(new))
    return len(new)

class StampPaintStroke(object):
    """One Paint stroke with Density / Scale Falloff, processed incrementally: move(position, normal) for each mouse position (a segment of the path), finish() at the end. Only the new part of the path costs anything.
      * candidates: a world-fixed jittered grid in the plane of the two axes that are not the dominant axis of the surface normal where the stroke began (the ground: X and Z); one candidate per cell of area 1 / Density
      * the field: the distance r (in brush radii) of a candidate to the polyline of the stroke; a candidate inside the plateau of every channel is made at once (nothing can change it later), one in a transition
        waits until the brush has gone a radius past it (its distance to the path is then final) or the stroke ends, so the soft edge does not depend on how fast the mouse moved
      * made when its threshold < Density multiplier(r); scaled by Scale multiplier(r); cast onto the surface along the axis (not onto stamps); kept when no stamp, old or new, is closer than Spacing."""
    MAX_CELLS=40000
    FLUSH_S=0.0                                                                    # the tool sets 0.05: new stamps are written at most that often (and never more than a third of the time), the end of the stroke writes the rest
    def __init__(self,asset,surf,bounds=None,cfg=None,normal=(0.0,1.0,0.0)):
        self.asset=asset;self.surf=surf;self.bounds=bounds;self.cfg=cfg or stamp_settings(asset);self.R=max(float(asset.evalParm('paint_radius')),1e-4);density=max(float(asset.evalParm('paint_density')),1e-4);self.spacing=float(asset.evalParm('paint_spacing'))
        self.dens=stamp_falloff_profile(asset,'dens');self.scale=stamp_falloff_profile(asset,'scale');self.seed=int(asset.evalParm('seed'));n=np.asarray(normal,dtype=np.float64)
        self.axis=int(np.argmax(np.abs(n)));self.sign=1.0 if n[self.axis]>=0 else -1.0;self.ia,self.ib=[a for a in (0,1,2) if a!=self.axis];self.h=max(1.0/np.sqrt(density),self.R*0.02)
        self.inner=min([1.0]+[p['inner'] for p in (self.dens,self.scale) if p is not None]);self.lift=self.R*1.5+0.05
        text=asset.evalParm('stamps');rows=stamp_rows(text);self.ex=rows[:,0:3].copy() if len(rows) else np.zeros((0,3));self.V=[];self.H=[];self.known=set()
        self.pk=np.zeros(0,dtype=np.int64);self.pc=np.zeros((0,2));self.pt=np.zeros(0);self.pn=np.zeros(0,dtype=np.int64);self.added=0;self.moves=0;self.buf=[];self.last_write=0.0;self.write_s=0.0
    def _cells(self,a,b):
        """Add the candidates of the grid cells within a radius of the segment a-b that nobody has seen yet."""
        R=self.R;h=self.h;lo=np.minimum(a,b)-R;hi=np.maximum(a,b)+R;i0,i1=int(np.floor(lo[0]/h)),int(np.floor(hi[0]/h));j0,j1=int(np.floor(lo[1]/h)),int(np.floor(hi[1]/h))
        if (i1-i0+1)*(j1-j0+1)>self.MAX_CELLS:return
        I,J=np.meshgrid(np.arange(i0,i1+1),np.arange(j0,j1+1),indexing='ij');I=I.ravel();J=J.ravel();keys=I*1000003+J;fresh=np.array([k not in self.known for k in keys.tolist()],dtype=bool)
        if not fresh.any():return
        I,J,keys=I[fresh],J[fresh],keys[fresh];c=np.stack([(I+_unit(_cell_hash(I,J,self.seed,1)))*h,(J+_unit(_cell_hash(I,J,self.seed,2)))*h],axis=1)
        ab=b-a;L2=float(ab@ab);t=np.clip(((c-a)@ab)/L2,0.0,1.0) if L2>1e-18 else np.zeros(len(c));near=np.linalg.norm(c-(a+np.outer(t,ab)),axis=1)<=R
        if not near.any():return
        c=c[near];keys=keys[near];I=I[near];J=J[near];self.known.update(keys.tolist());hh=_cell_hash(I,J,self.seed,3)
        self.pk=np.concatenate([self.pk,keys]);self.pc=np.concatenate([self.pc,c]);self.pt=np.concatenate([self.pt,_unit(hh)]);self.pn=np.concatenate([self.pn,(hh%np.uint64(2**30)).astype(np.int64)+1])
    def move(self,position,normal=None):
        """The brush is at position: extend the path and make what that settles. Returns how many stamps were made."""
        pos=np.asarray(position,dtype=np.float64);p=np.array([pos[self.ia],pos[self.ib]])
        if self.V and np.linalg.norm(p-self.V[-1])<0.06*self.R:return 0
        a=self.V[-1] if self.V else p;self.V.append(p);self.H.append(float(pos[self.axis]));self.moves+=1;self._cells(a,p);return self._resolve(False)
    def finish(self):
        """The end of the stroke: every candidate still waiting is decided with the distance it has now, and everything not written yet is written."""
        n=self._resolve(True) if self.V else 0;self.flush();return n
    def flush(self):
        """Write the stamps made so far (one parameter write)."""
        if self.buf:
            t0=time.time();stamp_append_lines(self.asset,self.buf);self.buf=[];self.write_s=time.time()-t0;self.last_write=time.time()
    def _resolve(self,final):
        if not len(self.pk):return 0
        R=self.R;V=np.array(self.V);Hh=np.array(self.H);A=V[:-1] if len(V)>1 else V;B=V[1:] if len(V)>1 else V;HA=Hh[:-1] if len(V)>1 else Hh;HB=Hh[1:] if len(V)>1 else Hh;C=self.pc
        lo=C.min(axis=0)-R;hi=C.max(axis=0)+R;use=np.all(np.maximum(A,B)>=lo,axis=1)&np.all(np.minimum(A,B)<=hi,axis=1)
        if not use.any():use=np.ones(len(A),dtype=bool)
        A,B,HA,HB=A[use],B[use],HA[use],HB[use];AB=B-A;L2=np.maximum((AB**2).sum(axis=1),1e-18);t=np.clip(((C[:,None,:]-A[None])*AB[None]).sum(axis=2)/L2[None],0.0,1.0)
        D=np.linalg.norm(C[:,None,:]-(A[None]+t[:,:,None]*AB[None]),axis=2);k=D.argmin(axis=1);ix=np.arange(len(C));dmin=D[ix,k];href=HA[k]+t[ix,k]*(HB[k]-HA[k]);dh=np.linalg.norm(C-V[-1],axis=1);r=dmin/R
        far=dmin>R;decide=(~far)&((r<=self.inner+1e-12)|(dh>=R)|final);keep=(~far)&(~decide)
        if far.any():self.known.difference_update(self.pk[far].tolist())                        # not under the brush (any more): it may come back when the path does
        acc=decide&(self.pt<falloff_multiplier(self.dens,r))
        made=0
        if acc.any():
            order=np.argsort(self.pk[acc]);idx=np.nonzero(acc)[0][order];ms=falloff_multiplier(self.scale,r[idx]);P=[];N=[];M=[];K=[]
            ex=self.ex
            if self.spacing>0 and len(ex):
                lo2=C[idx].min(axis=0)-self.spacing;hi2=C[idx].max(axis=0)+self.spacing;ex=ex[(ex[:,self.ia]>=lo2[0])&(ex[:,self.ia]<=hi2[0])&(ex[:,self.ib]>=lo2[1])&(ex[:,self.ib]<=hi2[1])]
            for q,i in enumerate(idx):
                o=np.zeros(3);o[self.ia]=C[i,0];o[self.ib]=C[i,1];o[self.axis]=href[i]+self.sign*self.lift;d=np.zeros(3);d[self.axis]=-self.sign;hit=self.surf.hit(o,d,stamps=False)
                if hit is None or hit[2]>self.lift+R*1.5:continue
                p=np.asarray(hit[0],dtype=np.float64)
                if self.spacing>0 and len(ex) and np.min(np.linalg.norm(ex[:,[self.ia,self.ib]]-p[[self.ia,self.ib]],axis=1))<self.spacing:continue         # the Spacing is measured along the surface (the plane of the stroke), so Sit On Surface and Offset do not matter
                ex=np.vstack([ex,p[None]]) if self.spacing>0 else ex;P.append(p);N.append(np.asarray(hit[1],dtype=np.float64));M.append(ms[q]);K.append(self.pn[i])
            if P:
                self.buf+=stamp_paint_lines(self.asset,P,N,M,K,self.cfg,self.bounds);made=len(P);self.ex=np.vstack([self.ex,np.array(P)]);self.added+=made
                if time.time()-self.last_write>=max(self.FLUSH_S,2.0*self.write_s if self.FLUSH_S>0 else 0.0):self.flush()
        self.pk,self.pc,self.pt,self.pn=self.pk[keep],self.pc[keep],self.pt[keep],self.pn[keep];return made

def stamp_paint_path(asset,surf,points,bounds=None):
    """Paint a whole stroke through points (positions on the surface, or above it: the surface below each is used), as the Paint brush does: with Density / Scale Falloff on the swept-field engine, else the dabs and the Edge Falloff.
    One undo step is the caller's business. For scripts, the demo and the tests. Returns how many stamps were made."""
    pts=[np.asarray(p,dtype=np.float64) for p in points];hits=[]
    for p in pts:
        h=surf.hit(p+np.array([0.0,1000.0,0.0]),(0.0,-1.0,0.0),stamps=False)
        if h is not None:hits.append(h)
    if not hits:return 0
    if stamp_paint_active(asset):
        s=StampPaintStroke(asset,surf,bounds,normal=hits[0][1]);s.FLUSH_S=1e9;n=0                       # one write at the end
        for h in hits:n+=s.move(h[0],h[1])
        return n+s.finish()
    cfg=stamp_settings(asset);radius=max(asset.evalParm('paint_radius'),1e-4);text=asset.evalParm('stamps');n0=stamp_count(text);last=None;dab=0;added=0
    for h in hits:
        if last is None or np.linalg.norm(h[0]-last)>=0.35*radius:
            last=h[0];rng=np.random.RandomState(int((asset.evalParm('seed')*7919+n0*104729+dab*31+1)%(2**31)));new_pos,new_nrm=stamp_paint_dab(surf,h[0],h[1],radius,asset.evalParm('paint_density'),asset.evalParm('paint_spacing'),asset.evalParm('paint_falloff'),rng,stamp_rows(asset.evalParm('stamps'))[:,0:3])
            if len(new_pos):added+=stamp_add_batch(asset,new_pos,new_nrm,snap_rot=asset.evalParm('snaprot') or None,cfg=cfg,bounds=bounds)
            dab+=1
    return added

def stamp_erase_dab(asset,center,radius):
    """The Paint brush with Ctrl: delete the stamps within the radius (3D distance) of the hit. Returns how many."""
    rows=stamp_rows(asset.evalParm('stamps'))
    if not len(rows):return 0
    return stamp_delete_many(asset,np.nonzero(np.linalg.norm(rows[:,0:3]-np.asarray(center),axis=1)<=radius)[0])

def stamp_proto_bounds(asset,entries=None):
    """{bank row: (min (3,), max (3,))}: the box of each prototype in its own space (with its own transform, as the instancer uses it, and the row's Scale); a group is the union of its children.
    The built-in sphere is the box of radius 0.5; a prim that cannot be measured gets a unit box."""
    stage=merged_stage(asset);entries=stamp_entries(asset,stage) if entries is None else entries
    cache=UsdGeom.BBoxCache(TC,[UsdGeom.Tokens.default_,UsdGeom.Tokens.render,UsdGeom.Tokens.proxy],useExtentsHint=True);out={}
    for e in entries:
        lo=np.full(3,np.inf);hi=np.full(3,-np.inf)
        for src in e['srcs']:
            if src[0]=='sphere':lo=np.minimum(lo,-0.5);hi=np.maximum(hi,0.5);continue
            try:
                prim=_src_prim(stage,src)
                if prim is None:continue
                rng=cache.ComputeLocalBound(prim).ComputeAlignedRange()
                if not rng.IsEmpty():lo=np.minimum(lo,np.array(rng.GetMin()));hi=np.maximum(hi,np.array(rng.GetMax()))
            except Exception:pass
        if not np.all(np.isfinite(lo)) or not np.all(hi>lo-1e-12):lo,hi=np.full(3,-0.5),np.full(3,0.5)
        out[e['row']]=(lo*e['scale'],hi*e['scale'])
    return out

def stamp_footprint(bounds):
    """The radius of a prototype on the ground (half its larger X / Z size): dragging this far from the click gives scale 1, like the Layout tool's Place brush."""
    lo,hi=bounds;r=0.5*max(hi[0]-lo[0],hi[2]-lo[2])
    return r if r>1e-6 else 0.5

def stamp_drag(anchor,up,forward,right,point,footprint,snap_rot=0.0):
    """The Layout-style drag: the stamp at anchor turns to face point (yaw about up, 0 = forward) and is scaled so its footprint reaches point. Returns (yaw degrees, scale, distance)."""
    v=np.asarray(point,dtype=np.float64)-np.asarray(anchor,dtype=np.float64);v=v-up*(v@up);dist=float(np.linalg.norm(v))
    yaw=float(np.degrees(np.arctan2(v@right,v@forward))) if dist>1e-12 else 0.0
    if snap_rot:yaw=stamp_snap(yaw,snap_rot)
    return yaw,max(dist/footprint,1e-4),dist

def stamp_set_lines(asset,lines,label):
    with hou.undos.group(label):asset.parm('stamps').set('\n'.join(lines))

def stamp_delete(asset,index):
    """Remove stamp number index (0-based, in the order of the lines)."""
    lines=stamp_lines(asset.evalParm('stamps'))
    if 0<=index<len(lines):del lines[index];stamp_set_lines(asset,lines,'Arraytron Stamp: delete')

def stamp_delete_last(asset):
    lines=stamp_lines(asset.evalParm('stamps'))
    if lines:stamp_delete(asset,len(lines)-1)

def stamp_clear(asset):
    stamp_set_lines(asset,[],'Arraytron Stamp: clear')

def stamp_info(asset):
    rows=stamp_rows(asset.evalParm('stamps'));on=int((rows[:,10]>0.5).sum()) if len(rows) else 0
    return 'No stamps yet. Press Place Instances and click a surface.' if not len(rows) else '%d stamp(s), %d on.'%(len(rows),on)

# ---------------------------------------------------------------- the surface under the mouse (object aware since 0.8.0)
SHAPES=('Mesh','Sphere','Cube','Cone','Cylinder','Capsule')

def _fan(counts,idx):
    """Triangles of polygon faces (every face a fan)."""
    starts=np.cumsum(counts)-counts;tris=[]
    for c in np.unique(counts):
        if c<3:continue
        base=starts[counts==c]
        for k in range(1,int(c)-1):tris.append(np.stack([idx[base],idx[base+k],idx[base+k+1]],axis=1))
    return np.concatenate(tris) if tris else np.zeros((0,3),dtype=np.int64)

def _axis(P,axis):
    """Points built along +Z turned onto the shape's axis (X, Y or Z)."""
    return P if axis=='Z' else P[:,[2,0,1]] if axis=='X' else P[:,[1,2,0]]

def _round(radius,z0,z1,cap0,cap1,seg=16):
    """A cylinder-like surface along Z (radius at z0 / z1 may be 0: a cone), closed by caps when asked."""
    a=np.linspace(0,2*np.pi,seg,endpoint=False);ring=np.stack([np.cos(a),np.sin(a)],axis=1)
    P=np.concatenate([np.column_stack([ring*radius[0],np.full(seg,z0)]),np.column_stack([ring*radius[1],np.full(seg,z1)]),[[0,0,z0],[0,0,z1]]]);T=[]
    for i in range(seg):
        j=(i+1)%seg;T+=[[i,j,seg+j],[i,seg+j,seg+i]]
        if cap0:T.append([2*seg,j,i])
        if cap1:T.append([2*seg+1,seg+i,seg+j])
    return P,np.array(T,dtype=np.int64)

def _sphere(r,seg=16,rings=10):
    th=np.linspace(0,np.pi,rings+1);ph=np.linspace(0,2*np.pi,seg,endpoint=False)
    P=np.array([[r*np.sin(t)*np.cos(p),r*np.sin(t)*np.sin(p),r*np.cos(t)] for t in th for p in ph]);T=[]
    for i in range(rings):
        for j in range(seg):
            a=i*seg+j;b=i*seg+(j+1)%seg;T+=[[a,b,b+seg],[a,b+seg,a+seg]]
    return P,np.array(T,dtype=np.int64)

def shape_triangles(prim):
    """Local (points, triangles) of a Mesh or a basic shape (Sphere, Cube, Cone, Cylinder, Capsule, tessellated coarsely: they are for the mouse, not for the render)."""
    t=prim.GetTypeName();get=lambda name,default:(lambda v:default if v is None else v)(prim.GetAttribute(name).Get() if prim.GetAttribute(name) else None)
    if t=='Mesh':
        m=UsdGeom.Mesh(prim);pts=m.GetPointsAttr().Get(TC)
        if pts is None:return np.zeros((0,3)),np.zeros((0,3),dtype=np.int64)
        return np.array(pts,dtype=np.float64).reshape(-1,3),_fan(np.array(m.GetFaceVertexCountsAttr().Get(TC),dtype=np.int64),np.array(m.GetFaceVertexIndicesAttr().Get(TC),dtype=np.int64))
    if t=='Sphere':return _sphere(float(get('radius',1.0)))
    if t=='Cube':
        h=float(get('size',2.0))*0.5;P=np.array([[x,y,z] for x in (-h,h) for y in (-h,h) for z in (-h,h)])
        T=np.array([[0,1,3],[0,3,2],[4,6,7],[4,7,5],[0,4,5],[0,5,1],[2,3,7],[2,7,6],[0,2,6],[0,6,4],[1,5,7],[1,7,3]],dtype=np.int64);return P,T
    axis=str(get('axis','Z'))
    if t=='Cone':h=float(get('height',2.0));r=float(get('radius',1.0));P,T=_round((r,0.0),-h/2,h/2,True,False)
    elif t=='Cylinder':h=float(get('height',2.0));r=float(get('radius',1.0));P,T=_round((r,r),-h/2,h/2,True,True)
    elif t=='Capsule':h=float(get('height',1.0));r=float(get('radius',0.5));P,T=_round((r,r),-h/2-r,h/2+r,True,True)
    else:return np.zeros((0,3)),np.zeros((0,3),dtype=np.int64)
    return _axis(P,axis),T

def _matrix(prim):
    return np.array(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(TC),dtype=np.float64).reshape(4,4)

def _prim_color(prim):
    """The display colour of a prim (the first value), else a soft green."""
    try:
        shown=UsdGeom.Gprim(prim).GetDisplayColorAttr().Get(TC)
        if shown is not None and len(shown):return (float(shown[0][0]),float(shown[0][1]),float(shown[0][2]))
    except Exception:pass
    return (0.62,0.70,0.56)

def prim_triangles(prim,space=None,colors=False):
    """(points, triangles) of every Mesh / basic shape under prim (itself included), in world space, or in the space of the matrix space (a prim's parent, for prototypes).
    Prims that are not visible are skipped."""
    P=[];T=[];C=[];base=0;inv=np.linalg.inv(space) if space is not None else None
    for p in Usd.PrimRange(prim,Usd.TraverseInstanceProxies()):                      # also into instanceable prims (the Houdini sample assets are made of them)
        if p.GetTypeName() not in SHAPES:continue
        try:
            if UsdGeom.Imageable(p).ComputeVisibility()=='invisible':continue
        except Exception:pass
        pts,tris=shape_triangles(p)
        if not len(tris):continue
        M=_matrix(p)
        if inv is not None:M=M@inv
        P.append(pts@M[:3,:3]+M[3,:3]);T.append(tris+base);base+=len(pts)
        if colors:C.append(np.tile(_prim_color(p),(len(pts),1)))
    if colors:return (np.concatenate(P),np.concatenate(T),np.concatenate(C)) if P else (np.zeros((0,3)),np.zeros((0,3),dtype=np.int64),np.zeros((0,3)))
    return (np.concatenate(P),np.concatenate(T)) if P else (np.zeros((0,3)),np.zeros((0,3),dtype=np.int64))

def _geo(P,T):
    g=hou.Geometry();g.createPoints([tuple(v) for v in P.tolist()]);g.createPolygons(T.tolist());return g

def _quat_matrices(q):
    """Rotation matrices (n, 3, 3) of quaternions (n, 4) (x, y, z, w), column convention: v' = M v."""
    x,y,z,w=q[:,0],q[:,1],q[:,2],q[:,3]
    return np.stack([np.stack([1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],-1),np.stack([2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],-1),np.stack([2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)],-1)],1)

class _Smooth(object):
    """Smooth surface normals of a triangle mesh at a ray hit: the normal of each corner is the area weighted mean of the faces around it that lean less than the crease angle (60 degrees) from the face that was hit, so an
    organic surface (a body, a hill) gives a smoothly changing up, and the top of a cube stays flat; the three corner normals are blended by the barycentric weights of the hit."""
    def __init__(self,P,T,crease=60.0):
        P=np.asarray(P,dtype=np.float64);T=np.asarray(T,dtype=np.int64);fn=np.cross(P[T[:,1]]-P[T[:,0]],P[T[:,2]]-P[T[:,0]]);ar=np.linalg.norm(fn,axis=1);ok=ar>1e-20;fn[ok]/=ar[ok,None]
        self.P=P;self.T=T;self.fn=fn;self.ar=ar;self.cos=float(np.cos(np.radians(crease)));flat=T.ravel();self.faces=np.argsort(flat,kind='stable')//3
        self.start=np.concatenate([[0],np.cumsum(np.bincount(flat,minlength=len(P)))])
    def normal(self,k,p):
        """The smooth unit normal at the point p of triangle k (the face normal when the triangle is degenerate)."""
        T=self.T[k];n0=self.fn[k];v=self.P[T];e1=v[1]-v[0];e2=v[2]-v[0];d=np.asarray(p,dtype=np.float64)-v[0];d11=e1@e1;d12=e1@e2;d22=e2@e2;den=d11*d22-d12*d12
        if abs(den)<1e-30:return n0
        a=d@e1;b=d@e2;w1=(d22*a-d12*b)/den;w2=(d11*b-d12*a)/den;w=np.clip(np.array([1.0-w1-w2,w1,w2]),0.0,1.0);w=w/w.sum();n=np.zeros(3)
        for j in range(3):
            f=self.faces[self.start[T[j]]:self.start[T[j]+1]];f=f[(self.fn[f]@n0)>=self.cos];vn=(self.fn[f]*self.ar[f,None]).sum(axis=0);L=np.linalg.norm(vn);n+=w[j]*(vn/L if L>1e-20 else n0)
        L=np.linalg.norm(n);return n/L if L>1e-20 else n0

class StampSurface(object):
    """What the tool places on, nearest hit first:
      * the ground plane Y = 0 when Place On is empty, or the meshes and basic shapes under the Place On prims (several paths, space separated);
      * the stamps already placed (Place On Stamps): a ray is tested against the box of every stamp at once (numpy), and only the boxes it enters are tested against their
        prototype's own triangles, in the prototype's space (one hou.Geometry per prototype, built once). So stamps go on top of stamps, as many as there are, with no copy of their geometry.
    Every ray cast is a hou.Geometry.intersect (Houdini's own acceleration structure)."""
    def __init__(self,asset):
        self.asset=asset;self.target=asset.evalParm('target').strip();self.geo=None;self.stage=None;self.protos={};self.key=None;self.n=0;self.last_stamp=None;self.smooth=True;self._sm={};self.built=False;self.nlines=0;self.entries=None
        self.pos=hou.Vector3();self.nrm=hou.Vector3();self.uvw=hou.Vector3()
        self.stage=merged_stage(asset)
        if not self.target:return
        P=[];T=[];base=0
        for path in self.target.split():
            prim=self.stage.GetPrimAtPath(path) if self.stage is not None else None
            if prim is None or not prim.IsValid():raise hou.NodeError('Place On: %s is not a prim of the first input.'%path)
            p,t=prim_triangles(prim);P.append(p);T.append(t+base);base+=len(p)
        if not base or not sum(len(t) for t in T):raise hou.NodeError('Place On: %s has no mesh or basic shape under it.'%self.target)
        self.gP=np.concatenate(P);self.gT=np.concatenate(T);self.geo=_geo(self.gP,self.gT)
    # -- the stamps
    def _proto(self,src):
        """The ray-cast geometry and box of one prototype source prim, in the prototype's space (its parent's space, like the instancer)."""
        if src not in self.protos:
            prim=_src_prim(self.stage,src) if src[0]!='sphere' else None
            if src[0]=='sphere':P,T=_sphere(0.5)
            elif prim is not None:parent=prim.GetParent();P,T=prim_triangles(prim,_matrix(parent) if parent and parent.GetPath()!=Sdf.Path('/') else None)
            else:P,T=np.zeros((0,3)),np.zeros((0,3),dtype=np.int64)
            self.protos[src]=(_geo(P,T),P.min(0),P.max(0),P,T) if len(T) else None
        return self.protos[src]
    def _build(self,rows,line0,entries,seed):
        """The ray-cast data of the stamps of rows (the first is line number line0): dict(items, lines, P, S, M, lo, hi), or None when none of them can be hit."""
        sel=np.nonzero(rows[:,10]>0.5)[0] if len(rows) else np.zeros(0,dtype=np.int64)
        if not len(sel):return None
        r=rows[sel];lines=line0+sel;rowmap={e['row']:i for i,e in enumerate(entries)};eidx=np.array([rowmap.get(int(v),0) for v in r[:,9]],dtype=np.int64);items=[];keep=[]
        for k,(i,line) in enumerate(zip(eidx,lines)):
            kids=entries[i]['srcs'];src=kids[int((int(line)*2654435761+seed)%len(kids))];pg=self._proto(src)
            if pg is None:continue
            items.append(pg);keep.append(k)
        if not keep:return None
        keep=np.array(keep);r=r[keep];eidx=eidx[keep];lines=lines[keep];q,S=stamp_effective(r,lines,eidx,entries,seed);S=np.where(np.abs(S)<1e-9,1e-9,S);M=_quat_matrices(q)
        lo=np.array([it[1] for it in items]);hi=np.array([it[2] for it in items])
        corners=np.stack([np.stack([np.where(c&1,hi[:,0],lo[:,0]),np.where(c&2,hi[:,1],lo[:,1]),np.where(c&4,hi[:,2],lo[:,2])],-1) for c in range(8)],1)   # (n, 8, 3)
        world=np.einsum('nij,nkj->nki',M,corners*S[:,None,:])+r[:,None,0:3];return dict(items=items,lines=lines,P=r[:,0:3],S=S,M=M,lo=world.min(1),hi=world.max(1))
    def _set(self,d):
        self.items=d['items'];self.lines=d['lines'];self.P=d['P'];self.S=d['S'];self.M=d['M'];self.lo=d['lo'];self.hi=d['hi'];self.n=len(d['lines'])
    def update(self,asset=None,force=False):
        """Read the stamps again when the Stamps text changed (one string compare per mouse move otherwise). force: also when Place On Stamps is off (the Delete brush and Edit mode need them).
        A text that only grew at the end (a click, a group, a paint dab) costs the new stamps, not all of them."""
        asset=asset or self.asset;self.smooth=bool(asset.evalParm('smooth')) if asset.parm('smooth') is not None else False;text=asset.evalParm('stamps');on=1 if force else (asset.evalParm('onstamps') if asset.parm('onstamps') is not None else 0)
        key=(text,bank_key(asset),asset.evalParm('seed'),on)
        if key==self.key:return
        prev=self.key;self.key=key
        if not on:self.n=0;self.built=False;return
        seed=asset.evalParm('seed')
        if self.built and prev is not None and prev[1:]==key[1:] and text.startswith(prev[0]) and (prev[0].endswith('\n') or text[len(prev[0]):len(prev[0])+1]=='\n'):
            try:
                tail=stamp_rows(text[len(prev[0]):]);add=self._build(tail,self.nlines,self.entries,seed);self.nlines+=len(tail)
                if add is not None:
                    d=dict(items=self.items+add['items'])
                    for k in ('lines','P','S','M','lo','hi'):d[k]=np.concatenate([getattr(self,k),add[k]])
                    self._set(d)
                return
            except Exception:pass                                                    # anything odd: read everything again
        rows=stamp_rows(text);self.nlines=len(rows);self.n=0;self.built=False
        if not len(rows):return
        self.entries=stamp_entries(asset,self.stage);d=self._build(rows,0,self.entries,seed)
        if d is not None:self._set(d);self.built=True
    def near(self,lo,hi):
        """A view of this surface that only knows the stamps whose box touches the rectangle lo..hi on the ground plane (X, Z): the rays of a group lie in a small area, so they test the few stamps there, not every stamp."""
        if not self.n:return self
        import copy
        ok=np.nonzero((self.lo[:,0]<=hi[0])&(self.hi[:,0]>=lo[0])&(self.lo[:,2]<=hi[1])&(self.hi[:,2]>=lo[1]))[0];v=copy.copy(self)
        v.items=[self.items[i] for i in ok];v.lines=self.lines[ok];v.P=self.P[ok];v.S=self.S[ok];v.M=self.M[ok];v.lo=self.lo[ok];v.hi=self.hi[ok];v.n=len(ok);return v
    def _smooth_of(self,key,P,T):
        """The smooth normals of a mesh (built when first needed: a big ground costs a moment once)."""
        if key not in self._sm:self._sm[key]=_Smooth(P,T)
        return self._sm[key]
    def _stamps_hit(self,o,d,limit):
        """The nearest stamp hit closer than limit: (position, normal, distance, line) or None."""
        if not self.n:return None
        with np.errstate(divide='ignore',invalid='ignore'):
            inv=1.0/np.where(np.abs(d)<1e-12,1e-12,d);t0=(self.lo-o)*inv;t1=(self.hi-o)*inv
        tn=np.minimum(t0,t1).max(1);tf=np.maximum(t0,t1).min(1);cand=np.nonzero((tf>=np.maximum(tn,0.0))&(tn<limit))[0]
        best=None
        for k in cand[np.argsort(tn[cand])]:
            if best is not None and tn[k]>best[2]:break
            R=self.M[k];s=self.S[k];lo_=R.T@(o-self.P[k])/s;ld=R.T@d/s;geo=self.items[k][0]
            pr=geo.intersect(hou.Vector3(tuple(lo_)),hou.Vector3(tuple(ld)),self.pos,self.nrm,self.uvw)
            if pr<0:continue
            p=self.P[k]+R@(np.array(tuple(self.pos))*s);t=float((p-o)@d)
            if t<=1e-9 or t>=limit or (best is not None and t>=best[2]):continue
            ln=np.array(tuple(self.nrm))
            if self.smooth:
                try:ln=self._smooth_of(id(self.items[k]),self.items[k][3],self.items[k][4]).normal(pr,np.array(tuple(self.pos)));ln=ln if ln@ld<=0 else -ln
                except Exception:ln=np.array(tuple(self.nrm))
            n=R@(ln/s);n=n/(np.linalg.norm(n) or 1.0)
            if n@d>0:n=-n
            best=(p,n,t,int(self.lines[k]))
        return best
    def hit(self,origin,direction,stamps=True):
        """(position, normal facing the ray, distance) of the first thing the ray hits: the stamps (when stamps), the Place On prims or the ground plane. None when nothing.
        last_stamp is the line of the stamp that was hit (None when it was not a stamp)."""
        o=np.asarray(origin,dtype=np.float64);d=np.asarray(direction,dtype=np.float64);d=d/np.linalg.norm(d);best=None;self.last_stamp=None
        if self.geo is None:
            if abs(d[1])>1e-9:
                t=-o[1]/d[1]
                if t>1e-9:best=(o+d*t,np.array([0.0,1.0,0.0]) if d[1]<0 else np.array([0.0,-1.0,0.0]),float(t))
        elif (pr:=self.geo.intersect(hou.Vector3(tuple(o)),hou.Vector3(tuple(d)),self.pos,self.nrm,self.uvw))>=0:
            p=np.array(tuple(self.pos));n=np.array(tuple(self.nrm));n=n/(np.linalg.norm(n) or 1.0)
            if self.smooth:
                try:n=self._smooth_of('base',self.gP,self.gT).normal(pr,p)
                except Exception:pass
            if n@d>0:n=-n
            best=(p,n,float(np.linalg.norm(p-o)))
        if stamps:
            s=self._stamps_hit(o,d,best[2] if best is not None else np.inf)
            if s is not None:best=s[:3];self.last_stamp=s[3]
        return best
    def snapped(self,point,normal,step):
        """The hit with the Snap Position grid applied to X and Z (the point is put back on what is below it)."""
        if step<=0:return point,normal
        x=stamp_snap(point[0],step);z=stamp_snap(point[2],step);h=self.hit((x,point[1]+1000.0,z),(0.0,-1.0,0.0))
        return (h[0],h[1]) if h is not None else (point,normal)

def stamp_surface(asset):
    s=StampSurface(asset);s.update(asset);return s

# ---------------------------------------------------------------- the cook
def stamp_cook(node):
    """The Python LOP: the instancer of the stamps. The bank's sources are staged as prototypes under <output>/Prototypes (an internal reference to the prim, or to a USD file staged hidden
    under <output>_Sources); each stamp takes the prototype of its bank row (a group row: one of its children, by the id of the stamp) with the row's Scale, Scale Random and Rotation Offset."""
    asset=node.parent();stage=node.editableStage();out=asset.evalParm('outputpath').strip() or '/World/Stamps'
    rows=stamp_rows(asset.evalParm('stamps'));entries=stamp_entries(asset,stage);seed=asset.evalParm('seed')
    inst=UsdGeom.PointInstancer.Define(stage,out);root=out+'/Prototypes';stage.DefinePrim(root,'Scope');srcroot=out.rstrip('/')+'_Sources'
    for old in stage.GetPrimAtPath(root).GetChildren():stage.RemovePrim(old.GetPath())
    targets=[];first=[];count=[];hide=asset.evalParm('hidesrc')
    for k,e in enumerate(entries):
        first.append(len(targets));count.append(len(e['srcs']))
        for j,src in enumerate(e['srcs']):
            p=Sdf.Path('%s/p%d_%d'%(root,k+1,j))
            if src[0]=='sphere':
                s=UsdGeom.Sphere.Define(stage,p);s.CreateRadiusAttr(0.5);s.CreateDisplayColorAttr([Gf.Vec3f(0.35,0.6,1.0)])
            else:
                if src[0]=='file':
                    stage.DefinePrim(srcroot,'Scope');target=Sdf.Path('%s/Proto_%02d_%s'%(srcroot,e['row'],re.sub(r'\W+','_',_leaf(re.split(r'[\\/?]',src[1])[-1].rsplit('.',1)[0])).strip('_') or 'proto'))
                    sp=stage.DefinePrim(target);sp.GetReferences().AddReference(src[1].replace('\\','/'),Sdf.Path(src[2])) if src[2] else sp.GetReferences().AddReference(src[1].replace('\\','/'))
                    UsdGeom.Imageable(sp).MakeInvisible();shown=True
                else:
                    target=Sdf.Path(src[1]);shown=bool(hide)
                    if hide:UsdGeom.Imageable(stage.GetPrimAtPath(src[1])).MakeInvisible()
                prim=stage.DefinePrim(p);prim.GetReferences().AddInternalReference(target)
                if shown:UsdGeom.Imageable(prim).GetVisibilityAttr().Set('inherited')
            targets.append(p)
    inst.CreatePrototypesRel().SetTargets(targets)
    on=rows[:,10]>0.5 if len(rows) else np.zeros(0,dtype=bool);r=rows[on];n=len(r);ids=np.nonzero(on)[0].astype(np.int64)
    rowmap={e['row']:i for i,e in enumerate(entries)};eidx=np.array([rowmap.get(int(v),0) for v in r[:,9]],dtype=np.int64) if n else np.zeros(0,dtype=np.int64)
    first=np.array(first,dtype=np.int64);count=np.array(count,dtype=np.int64)
    index=first[eidx]+((ids*2654435761+seed)%count[eidx] if n else 0)                    # a group row picks one of its children, by the id of the stamp
    q,S=stamp_effective(r,ids,eidx,entries,seed) if n else (np.zeros((0,4)),np.zeros((0,3)))
    inst.CreatePositionsAttr().Set(Vt.Vec3fArray([Gf.Vec3f(*map(float,p)) for p in r[:,0:3]]) if n else Vt.Vec3fArray())
    inst.CreateOrientationsAttr().Set(Vt.QuathArray([Gf.Quath(float(w),float(x),float(y),float(z)) for x,y,z,w in q]) if n else Vt.QuathArray())
    inst.CreateScalesAttr().Set(Vt.Vec3fArray([Gf.Vec3f(*map(float,s)) for s in S]) if n else Vt.Vec3fArray())
    inst.CreateProtoIndicesAttr().Set(Vt.IntArray([int(v) for v in index]) if n else Vt.IntArray())
    inst.CreateIdsAttr().Set(Vt.Int64Array([int(v) for v in ids]) if n else Vt.Int64Array())

# ---------------------------------------------------------------- buttons
def stamp_start(asset):
    """Place Instances: this node current, the viewport tool entered."""
    if not hou.isUIAvailable():raise hou.NodeError('Placing needs the Houdini interface (a Scene Viewer).')
    viewer=hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
    if viewer is None:raise hou.NodeError('Open a Scene Viewer pane to place instances.')
    asset.setCurrent(True,clear_all_selected=True);viewer.setCurrentState(STAMP_STATE)

_PANEL_DONE=set()
def gallery_install(node_type):
    """Register the Parameters pane of this node type (the HDA section StampPanel.py as a Python Panel with <showInParametersPane>), once per session. Called by OnCreated / OnLoaded;
    ARRAYTRON_NO_PARM_PANEL=1 keeps the plain parameter dialog."""
    import os,tempfile
    if os.environ.get('ARRAYTRON_NO_PARM_PANEL') or not hou.isUIAvailable():return False
    name=node_type.nameWithCategory()
    if name in _PANEL_DONE:return True
    section=node_type.definition().sections().get('StampPanel.py')
    if section is None:return False
    tag=''.join(ch if ch.isalnum() else '_' for ch in node_type.name())
    xml=('<?xml version="1.0" encoding="UTF-8"?>\n<pythonPanelDocument>\n  <interface name="arraytron_stamp_%s" label="Arraytron Stamp" icon="MISC_python" showNetworkNavigationBar="false" help_url="">\n'
         '    <script><![CDATA[%s]]></script>\n    <showInParametersPane optype="%s"/>\n  </interface>\n</pythonPanelDocument>\n')%(tag,section.contents(),name)
    path=os.path.join(tempfile.gettempdir(),'arraytron_stamp_%s.pypanel'%tag)
    with open(path,'w',encoding='utf8') as f:f.write(xml)
    hou.pypanel.installFile(path);_PANEL_DONE.add(name);return True
