# Imported points (v1.5.0): Distribution Mode "Imported Points". The instances go on points that come from somewhere else: a SOP network (an FX / POP /
# Vellum / FLIP simulation, a scatter, a point cloud ...) through the Object Merge SOP `imported_source`, or a USD Points / PointInstancer prim of the
# stream (an FX cache imported as USD). Everything else works on them like on any distribution: prototype percentages, Variation, Mask, Field Stack,
# Separation, Physics, overrides, Grow, camera optimisation, primvars. Ids come from the source (its own id attribute) so a simulated point keeps its
# prototype, its random look and its overrides from frame to frame. Appended to the PythonModule after the cluster module (uses scatter_hash,
# normal_alignment, frames_from_tangent, stage helpers). The pure numpy functions are tested directly.
import numpy as np

IMPORT_RESERVED=('P','id','align','srcscale','source_id','orient','scale','protoindex','proto_id','maskweight','fieldweight','cluster','protopath')
IMPORT_MAX_POINTS=2000000

# ---------------------------------------------------------------- pure functions
def choose_ids(ids,count,mode):
    """(ids, how). mode 0 uses the imported id attribute when it is present, integer and unique, otherwise the point number; mode 1 always the point number.
    how: 0 imported, 1 point number by choice, 2 attribute missing, 3 not unique (fallback to the point number)."""
    if mode==1:return np.arange(count,dtype=np.int64),1
    if ids is None:return np.arange(count,dtype=np.int64),2
    ids=np.asarray(ids).astype(np.int64)
    if len(np.unique(ids))!=len(ids):return np.arange(count,dtype=np.int64),3
    return ids,0

def percent_keep(ids,percent,seed):
    """Boolean keep mask: an id is used when its own number (hash of the id and the seed) is below percent / 100, so a higher percent only ever adds ids."""
    if percent>=100.0:return np.ones(len(ids),dtype=bool)
    return scatter_hash(np.asarray(ids,dtype=np.int64),seed,91)*100.0<percent

def source_scale(attr,mult):
    """Scale (N,3) from a float (N,) or vector (N,3) attribute times a multiplier, never below 0.0001; None gives the multiplier alone."""
    if attr is None:return None
    a=np.asarray(attr,dtype=np.float64)
    if a.ndim==1:a=np.column_stack([a,a,a])
    return np.maximum(a[:,:3]*float(mult),1e-4)

def source_alignment(mode,n,orient=None,velocity=None,normal=None):
    """Quaternions (N,4; x,y,z,w) for the orientation mode: 0 upright (identity); 1 the source orient attribute; 2 +Z along the velocity (up as close to +Y as possible; a
    point with no speed stays upright); 3 +Y onto the normal."""
    q=np.tile([0.0,0.0,0.0,1.0],(n,1))
    if mode==1 and orient is not None:
        o=np.asarray(orient,dtype=np.float64).reshape(n,-1)[:,:4];norm=np.linalg.norm(o,axis=1);ok=norm>1e-12;q[ok]=o[ok]/norm[ok][:,None]
    elif mode==2 and velocity is not None:
        v=np.asarray(velocity,dtype=np.float64).reshape(n,-1)[:,:3];speed=np.linalg.norm(v,axis=1);moving=speed>1e-9
        if moving.any():q[moving]=frames_from_tangent(v[moving]/speed[moving][:,None],np.array([0.0,1.0,0.0]))
    elif mode==3 and normal is not None:
        nn=np.asarray(normal,dtype=np.float64).reshape(n,-1)[:,:3];norm=np.linalg.norm(nn,axis=1);ok=norm>1e-12
        if ok.any():q[ok]=normal_alignment(nn[ok]/norm[ok][:,None],1.0)
    return q

# ---------------------------------------------------------------- Houdini side
import hou
from pxr import Usd, UsdGeom

def _read_float_attr(geo,name,size=None):
    a=geo.findPointAttrib(name)
    if a is None:return None
    t=a.dataType();n=a.size()
    if t==hou.attribData.Float:vals=np.array(geo.pointFloatAttribValues(name),dtype=np.float64)
    elif t==hou.attribData.Int:vals=np.array(geo.pointIntAttribValues(name),dtype=np.float64)
    else:return None
    return vals if n==1 else vals.reshape(-1,n)

def read_sop_points(geo,asset):
    """The source attributes of the Object Merge geometry as numpy arrays: P (N,3) and every float / int point attribute by name."""
    n=geo.intrinsicValue('pointcount')
    if n==0:return dict(n=0,P=np.zeros((0,3)),attrs={})
    attrs={};P=np.array(geo.pointFloatAttribValues('P')).reshape(-1,3)
    for a in geo.pointAttribs():
        name=a.name()
        if name=='P':continue
        v=_read_float_attr(geo,name)
        if v is not None:attrs[name]=v
    return dict(n=n,P=P,attrs=attrs)

def read_usd_points(asset):
    """P (N,3) and attributes from a USD Points or PointInstancer prim of the stream, at the current frame plus the Time Offset, in world space."""
    stage=asset.node('SOURCE_RESOLVER').stage();path=asset.evalParm('imp_prim').strip()
    if stage is None:raise hou.NodeError('The Source Resolver has no stage.')
    if not path:raise hou.NodeError('The Imported Prim is empty: pick a Points or PointInstancer prim of the stream.')
    prim=stage.GetPrimAtPath(path)
    if not prim or not prim.IsValid():raise hou.NodeError('%s does not exist in the incoming stage.'%path)
    time=Usd.TimeCode(asset.evalParm('imp_frame')+asset.evalParm('imp_offset'));M=np.array(UsdGeom.XformCache(time).GetLocalToWorldTransform(prim),dtype=np.float64).reshape(4,4);R=M[:3,:3];attrs={}
    def arr(v,dim=None):
        a=np.array(v if v is not None else [],dtype=np.float64);return a.reshape(len(a),-1) if dim is None and a.ndim>1 else a
    if prim.IsA(UsdGeom.PointInstancer):
        pi=UsdGeom.PointInstancer(prim);P=arr(pi.GetPositionsAttr().Get(time));n=len(P)
        ids=pi.GetIdsAttr().Get(time)
        if ids is not None and len(ids)==n:attrs['id']=np.array(ids,dtype=np.float64)
        o=pi.GetOrientationsAttr().Get(time)
        if o is not None and len(o)==n:attrs['orient']=np.array([[q.GetImaginary()[0],q.GetImaginary()[1],q.GetImaginary()[2],q.GetReal()] for q in o],dtype=np.float64)
        s=pi.GetScalesAttr().Get(time)
        if s is not None and len(s)==n:attrs['scale']=np.array(s,dtype=np.float64).reshape(n,3)
        v=pi.GetVelocitiesAttr().Get(time)
        if v is not None and len(v)==n:attrs['v']=np.array(v,dtype=np.float64).reshape(n,3)@R
        pr=pi.GetProtoIndicesAttr().Get(time)
        if pr is not None and len(pr)==n:attrs['source_proto']=np.array(pr,dtype=np.float64)
    elif prim.IsA(UsdGeom.Points):
        pt=UsdGeom.Points(prim);P=arr(pt.GetPointsAttr().Get(time));n=len(P)
        ids=pt.GetIdsAttr().Get(time)
        if ids is not None and len(ids)==n:attrs['id']=np.array(ids,dtype=np.float64)
        w=pt.GetWidthsAttr().Get(time)
        if w is not None and len(w)==n:attrs['pscale']=np.array(w,dtype=np.float64)*0.5                       # USD widths are diameters, pscale is a radius
        v=pt.GetVelocitiesAttr().Get(time)
        if v is not None and len(v)==n:attrs['v']=np.array(v,dtype=np.float64).reshape(n,3)@R
        nm=pt.GetNormalsAttr().Get(time)
        if nm is not None and len(nm)==n:attrs['N']=np.array(nm,dtype=np.float64).reshape(n,3)@R
    else:
        raise hou.NodeError('%s is a %s: the Imported Prim must be a Points or PointInstancer prim.'%(path,prim.GetTypeName() or 'prim'))
    if n==0:return dict(n=0,P=np.zeros((0,3)),attrs={})
    P=np.column_stack([P,np.ones(n)])@M;P=P[:,:3]
    for pv in UsdGeom.PrimvarsAPI(prim).GetPrimvars():
        name=pv.GetPrimvarName();val=pv.ComputeFlattened(time) if hasattr(pv,'ComputeFlattened') else pv.Get(time)
        if val is None or name in attrs or name in IMPORT_RESERVED:continue
        try:a=np.array(val,dtype=np.float64)
        except Exception:continue
        if len(a)==n:attrs[name]=a
    return dict(n=n,P=P,attrs=attrs)

def sop_imported(geo,asset):
    """generate_imported: the points of the source with the stable id, the orientation in p@align, the source scale in v@srcscale, the source id in i@source_id and the
    attributes asked for in Copy Attributes. With Time Offset / a changing source the node follows the timeline."""
    for name in ('imp_total','imp_used','imp_idhow'):geo.addAttrib(hou.attribType.Global,name,0)
    src=read_sop_points(geo,asset) if asset.evalParm('imp_source')==0 else read_usd_points(asset)
    if asset.evalParm('imp_source')==0:asset.evalParm('imp_frame')                                          # the timeline reaches the node
    n=src['n'];geo.clear();geo.addAttrib(hou.attribType.Global,'imp_total',0);geo.addAttrib(hou.attribType.Global,'imp_used',0);geo.addAttrib(hou.attribType.Global,'imp_idhow',0)
    geo.setGlobalAttribValue('imp_total',int(n))
    for name,default in (('id',0),('align',(0.0,0.0,0.0,1.0)),('srcscale',(1.0,1.0,1.0)),('source_id',0)):geo.addAttrib(hou.attribType.Point,name,default)
    if n==0:return
    if n>IMPORT_MAX_POINTS:raise hou.NodeError('The source has %d points; at most %d are supported.'%(n,IMPORT_MAX_POINTS))
    a=src['attrs'];idname=asset.evalParm('imp_idattr').strip() or 'id'
    ids,how=choose_ids(a.get(idname),n,asset.evalParm('imp_idmode'))
    if how==2:hou.pwd().addWarning('Imported Points: the source has no point attribute "%s"; the point number is used as the id (the ids then change when the source count changes).'%idname)
    if how==3:hou.pwd().addWarning('Imported Points: the ids in "%s" are not unique; the point number is used as the id.'%idname)
    keep=percent_keep(ids,asset.evalParm('imp_percent'),asset.evalParm('imp_seed'))
    sid=ids.copy();sel=np.nonzero(keep)[0];geo.setGlobalAttribValue('imp_idhow',int(how));geo.setGlobalAttribValue('imp_used',int(len(sel)))
    if not len(sel):return
    pts=geo.createPoints([tuple(v) for v in src['P'][sel].tolist()])
    geo.setPointIntAttribValues('id',ids[sel].tolist());geo.setPointIntAttribValues('source_id',(np.asarray(a[idname]).astype(np.int64)[sel] if idname in a else sid[sel]).tolist())
    mode=asset.evalParm('imp_orient');q=source_alignment(mode,n,a.get(asset.evalParm('imp_orient_attr').strip() or 'orient'),a.get(asset.evalParm('imp_vel_attr').strip() or 'v'),a.get(asset.evalParm('imp_normal_attr').strip() or 'N'))
    geo.setPointFloatAttribValues('align',q[sel].ravel().tolist())
    mult=asset.evalParm('imp_scale_mult');sc=None
    if asset.evalParm('imp_scale')==1:
        sname=asset.evalParm('imp_scale_attr').strip() or 'pscale'
        sc=source_scale(a.get(sname) if sname in a or sname!='pscale' else a.get('scale'),mult)                  # a PointInstancer source has `scale`, a Points one `pscale`: the default name finds either
        if sc is None:hou.pwd().addWarning('Imported Points: the source has no point attribute "%s" for the scale; the multiplier alone is used.'%(asset.evalParm('imp_scale_attr').strip() or 'pscale'))
    if sc is None:sc=np.tile([mult,mult,mult],(n,1)) if mult!=1.0 else None
    if sc is not None:geo.setPointFloatAttribValues('srcscale',sc[sel].ravel().tolist())
    for name in asset.evalParm('imp_copy').replace(',',' ').split():
        if name in IMPORT_RESERVED or name not in a:continue
        v=a[name];size=1 if v.ndim==1 else v.shape[1]
        geo.addAttrib(hou.attribType.Point,name,0.0 if size==1 else tuple([0.0]*size));geo.setPointFloatAttribValues(name,v[sel].ravel().tolist())

def imported_info(asset):
    """Read-only text for the Imported Points section."""
    try:
        g=asset.node('USD_COMPILER/generate_imported').geometry()
        if g is None:return 'Cannot read the source: see the error above.'
        total,used,how=g.attribValue('imp_total'),g.attribValue('imp_used'),g.attribValue('imp_idhow')
    except Exception as exc:return 'Cannot evaluate: %s'%exc
    ids={0:'ids from the source attribute',1:'ids = point numbers (by choice)',2:'ids = point numbers (the source has no id attribute)',3:'ids = point numbers (the source ids are not unique)'}[how]
    return '%d points in the source, %d used; %s.'%(total,used,ids)

def percent_text(asset):
    """Read-only text for the Prototype Bank: the share of the points every prototype gets under the Selection Mode."""
    try:entries=resolve(asset)
    except Exception:return 'Cannot resolve the bank.'
    mode=asset.evalParm('proto_mode');w=np.array([max(asset.evalParm('proto_weight%d'%e['row']),0.0) for e in entries]);equal=mode in (0,3) or w.sum()<=0
    share=np.full(len(entries),1.0/len(entries)) if equal else w/w.sum()
    return '  '.join('%s %.1f%%'%(e['path'].rstrip('/').split('/')[-1],100*s) for e,s in zip(entries,share))
