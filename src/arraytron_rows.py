# Rows (v1.14.0): the linear Distribution Modes (Line, Circle / Radial, Curve) scatter along ONE path; Rows lays the same path out as several parallel rows (Line: next to each other, Circle:
# concentric rings, Curve: copies of the curve pushed to the side) and can randomise between them. The ROWS Python SOP runs right after the distribution switch, so the Mask, the Field Stack,
# the Falloff, the Variation, the Separation and everything after it work on every row like on any other point. Count means the points of ONE row.
# Row 0 keeps its ids; row k gets id + k * 20,000,000, so changing the number of rows never renames a point. The sideways direction is horizontal (X, Z), perpendicular to the path; for a Circle it is
# the radial direction in the circle's plane. Appended to the PythonModule after the Falloff module (uses scatter_hash). The pure numpy functions are tested directly.
import numpy as np

ROWS_ID_STRIDE=20000000
ROWS_MAX=50
ROWS_MODES=(0,3,4)                # Line, Circle, Curve
ROWS_STREAM=96

def rows_offsets(count,spacing,centered):
    """Sideways offset of every row: centered rows are spread around the path (the middle one on it for an odd count), otherwise the path is the first row and the others follow on one side."""
    return (np.arange(int(count))-(0.5*(int(count)-1) if centered else 0.0))*float(spacing)

def _unit(v,fallback):
    v=np.asarray(v,dtype=np.float64);n=np.linalg.norm(v,axis=1);out=np.where(n[:,None]>1e-9,v/np.maximum(n,1e-12)[:,None],np.asarray(fallback,dtype=np.float64)[None,:]);return out

def rows_directions(mode,P,line_axis=0,line_direction=(1.0,0.0,0.0),circle_plane=0,pathdir=None):
    """(along (n,3), side (n,3)): the unit direction of the path at every point and the unit sideways direction the rows are offset along."""
    P=np.asarray(P,dtype=np.float64).reshape(-1,3);n=len(P);up=np.array([0.0,1.0,0.0])
    if mode==0:
        d=np.eye(3)[int(line_axis)] if int(line_axis)<3 else np.asarray(line_direction,dtype=np.float64)
        d=d/np.linalg.norm(d) if np.linalg.norm(d)>1e-9 else np.array([1.0,0.0,0.0]);along=np.tile(d,(n,1));side=np.cross(up,along)
        side=_unit(side,(1.0,0.0,0.0));return along,side
    if mode==3:
        normal=np.eye(3)[(1,2,0)[int(circle_plane)]];mask=np.array([1.0,1.0,1.0])-np.abs(normal);radial=_unit(P*mask[None,:],(0.0,1.0,0.0) if abs(normal[0])>0.5 else (1.0,0.0,0.0))
        along=_unit(np.cross(normal[None,:],radial),(0.0,0.0,1.0));return along,radial
    along=_unit(np.zeros((n,3)) if pathdir is None else pathdir,(0.0,0.0,1.0));side=_unit(np.cross(up[None,:],along),(1.0,0.0,0.0));return along,side

def rows_gap(P,ids):
    """The typical distance between neighbours along the path (the median distance between consecutive points in id order); 0 for fewer than two points."""
    P=np.asarray(P,dtype=np.float64).reshape(-1,3)
    if len(P)<2:return 0.0
    d=np.linalg.norm(np.diff(P[np.argsort(ids,kind='stable')],axis=0),axis=1);d=d[d>1e-9];return float(np.median(d)) if len(d) else 0.0

def rows_expand(P,ids,along,side,count,spacing,centered,random,shift,stagger,seed):
    """The points of all rows. Returns (source index (m,), new positions (m,3), new ids (m,), row number (m,)): row k of source point i is at P + side * offset(k) (+ a random offset across the row of up
    to random * spacing / 2, + a random shift along the path of up to shift * gap / 2, + half a gap along the path on every odd row when staggered), with id + k * ROWS_ID_STRIDE. The random numbers
    are keyed on the new id and the seed, so a point never changes when the number of rows changes."""
    P=np.asarray(P,dtype=np.float64).reshape(-1,3);ids=np.asarray(ids,dtype=np.int64);n=len(P);count=int(count);off=rows_offsets(count,spacing,centered);gap=rows_gap(P,ids)
    src=np.tile(np.arange(n),count);row=np.repeat(np.arange(count),n);new_ids=ids[src]+row*ROWS_ID_STRIDE
    pos=P[src]+side[src]*off[row][:,None]
    if random>0:pos=pos+side[src]*((scatter_hash(new_ids,seed,ROWS_STREAM)*2.0-1.0)*0.5*float(random)*float(spacing))[:,None]
    if shift>0 and gap>0:pos=pos+along[src]*((scatter_hash(new_ids,seed,ROWS_STREAM+1)*2.0-1.0)*0.5*float(shift)*gap)[:,None]
    if stagger and gap>0:pos=pos+along[src]*(float(stagger)*gap*(row%2))[:,None]                                  # stagger: the fraction of the gap (the old tick was 0.5)
    return src,pos,new_ids,row

# ---------------------------------------------------------------- the stage
def sop_linerows(geo,asset):
    """ROWS: replicate the path into several rows (and randomise). Every attribute of a point is copied to its copies (the alignment of a Circle, the curve number ...)."""
    for name,default in (('rows_before',0),('rows_after',0),('rows_gap',0.0)):geo.addAttrib(hou.attribType.Global,name,default)
    n=geo.intrinsicValue('pointcount');geo.setGlobalAttribValue('rows_before',n);geo.setGlobalAttribValue('rows_after',n);mode=asset.evalParm('mode')
    count=asset.evalParm('rows_count');random=asset.evalParm('rows_random');shift=asset.evalParm('rows_shift');stagger=asset.evalParm('rows_stagger')*(0.5 if asset.parm('rows_stagger').parmTemplate().type()==hou.parmTemplateType.Toggle else 1.0)
    if mode not in ROWS_MODES or n==0 or (count<=1 and random<=0 and shift<=0 and not stagger):return
    count=min(count,ROWS_MAX);P=np.array(geo.pointFloatAttribValues('P')).reshape(-1,3);ids=np.array(geo.pointIntAttribValues('id'),dtype=np.int64)
    pathdir=np.array(geo.pointFloatAttribValues('pathdir')).reshape(-1,3) if mode==4 and geo.findPointAttrib('pathdir') is not None else None
    along,side=rows_directions(mode,P,asset.evalParm('line_axis'),asset.evalParmTuple('line_direction'),asset.evalParm('circle_plane'),pathdir)
    src,pos,new_ids,row=rows_expand(P,ids,along,side,count,asset.evalParm('rows_spacing'),asset.evalParm('rows_center'),random,shift,stagger,asset.evalParm('rows_seed'))
    saved=[]
    for a in geo.pointAttribs():
        name=a.name()
        if name=='P':continue
        t=a.dataType();size=a.size()
        if t==hou.attribData.Float:values=np.array(geo.pointFloatAttribValues(name)).reshape(n,size)
        elif t==hou.attribData.Int:values=np.array(geo.pointIntAttribValues(name)).reshape(n,size)
        else:continue
        saved.append((name,t,size,a.defaultValue(),values))
    geo.clear()
    for name,t,size,default,values in saved:geo.addAttrib(hou.attribType.Point,name,default)
    geo.addAttrib(hou.attribType.Global,'rows_before',0);geo.addAttrib(hou.attribType.Global,'rows_after',0);geo.addAttrib(hou.attribType.Global,'rows_gap',0.0)
    geo.createPoints([tuple(v) for v in pos.tolist()])
    for name,t,size,default,values in saved:
        v=values[src]
        if name=='id':v=new_ids.reshape(-1,1)
        (geo.setPointFloatAttribValues if t==hou.attribData.Float else geo.setPointIntAttribValues)(name,v.ravel().tolist())
    geo.setGlobalAttribValue('rows_before',n);geo.setGlobalAttribValue('rows_after',len(pos));geo.setGlobalAttribValue('rows_gap',rows_gap(P,ids))

def rows_info(asset):
    """Read-only text for the Rows section."""
    if asset.evalParm('mode') not in ROWS_MODES:return 'Rows work with the Line, Circle and Curve modes.'
    try:
        g=asset.node('USD_COMPILER/ROWS').geometry();b,a=g.attribValue('rows_before'),g.attribValue('rows_after')
        if a==b:return 'One row: %d points (set Rows above 1, or a random offset, to use this).'%b
        return '%d rows of %d points = %d points (gap along the path %.3g).'%(asset.evalParm('rows_count'),b,a,g.attribValue('rows_gap'))
    except Exception as exc:return 'Cannot evaluate: %s'%exc
