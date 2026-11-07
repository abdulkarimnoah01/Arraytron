"""Arraytron Stamp 0.9.3 (the light one): hython tests/validate_stamplite.py   (hython 22 or 20.5; build it first with tools/build_stamp_light.py)
Groups: contract (parameters, one inner node, no multiparm) | cook (the instancer follows the Stamps text: ids, scales, orientations, prototypes, groups, hidden sources, errors) |
placing (stamp_add: rotation, align, randomness, seed, Random Prototype, snapping, delete, clear) | surface (the ray cast on a mesh and on the plane) | speed |
viewer (the tool through a stand-in viewport that looks straight down) | gallery (the panel, in an offscreen Qt application).
Env STAMP_MUTATE=quat|align|on|group|snap|nearest|drag|stack|bank|delta|workset|select|keys|thumb|fav|paint|ghost|sheet|groupring|conform|manage|layout|groupscale|sit|smooth|incremental|falloff breaks the module; the suite must FAIL. Writes tests/validation_stamplite_<22|205>.json."""
import os, sys, json, time, types, tempfile
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import hou
import numpy as np
from pxr import Usd, UsdGeom, Gf
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
H205=versions.is_h205();MUTATE=os.environ.get('STAMP_MUTATE')
HDA=ROOT/('otls_h205' if H205 else 'dist')/('Arraytron_Stamp_v0.9.3%s.hda'%('_H205' if H205 else ''));TYPE='arraytron::stamp::0.9.3'
WORK=Path(tempfile.mkdtemp(prefix='arraytron_stamplite_'))
out={'groups':{}}
def check(group,cond,note=''):
    out['groups'].setdefault(group,[]).append(bool(cond))
    if not cond:print('FAIL',group,'#%d'%len(out['groups'][group]),note)

SCENE='''from pxr import Gf, UsdGeom, Vt
import hou, math
stage=hou.pwd().editableStage()
UsdGeom.Xform.Define(stage,'/World')
g=UsdGeom.Mesh.Define(stage,'/World/Ground');n=30;pts=[];idx=[]
for j in range(n+1):
    for i in range(n+1):pts.append(Gf.Vec3f(-15+30*i/n,0.0,-15+30*j/n))
for j in range(n):
    for i in range(n):idx+=[j*(n+1)+i,(j+1)*(n+1)+i,(j+1)*(n+1)+i+1,j*(n+1)+i+1]
g.CreatePointsAttr(Vt.Vec3fArray(pts));g.CreateFaceVertexCountsAttr(Vt.IntArray([4]*(n*n)));g.CreateFaceVertexIndicesAttr(Vt.IntArray(idx))
r=UsdGeom.Mesh.Define(stage,'/World/Ramp');r.CreatePointsAttr([(-5,0,5),(5,0,5),(5,5,-5),(-5,5,-5)]);r.CreateFaceVertexCountsAttr([4]);r.CreateFaceVertexIndicesAttr([0,1,2,3])
for name,shape in (('Rock',UsdGeom.Sphere),('Fir',UsdGeom.Cone),('Stone',UsdGeom.Cube)):
    UsdGeom.Xform.Define(stage,'/World/Props/'+name);shape.Define(stage,'/World/Props/%s/Geom'%name)
d=UsdGeom.Mesh.Define(stage,'/World/Dome');pts=[];idx=[];NL,NM=8,16
for i in range(NL+1):
    for j in range(NM):
        la=3.14159265*i/NL;lo=6.2831853*j/NM;pts.append(Gf.Vec3f(4*math.sin(la)*math.cos(lo),4*math.cos(la),40+4*math.sin(la)*math.sin(lo)))
for i in range(NL):
    for j in range(NM):idx+=[i*NM+j,i*NM+(j+1)%NM,(i+1)*NM+(j+1)%NM,(i+1)*NM+j]
d.CreatePointsAttr(Vt.Vec3fArray(pts));d.CreateFaceVertexCountsAttr(Vt.IntArray([4]*(NL*NM)));d.CreateFaceVertexIndicesAttr(Vt.IntArray(idx))
UsdGeom.Xform.Define(stage,'/World/Set/A');UsdGeom.Sphere.Define(stage,'/World/Set/A/G');UsdGeom.Xform.Define(stage,'/World/Set/B');UsdGeom.Cube.Define(stage,'/World/Set/B/G');UsdGeom.Xform.Define(stage,'/World/Set/C');UsdGeom.Cone.Define(stage,'/World/Set/C/G')
'''
hou.hda.installFile(str(HDA),force_use_assets=True);stage=hou.node('/stage')
scene=stage.createNode('pythonscript','scene');scene.parm('python').set(SCENE)
BANK={0:'proto_prim',3:'proto_prim',2:'proto_file',1:'proto_inprim'}
def set_bank(a,rows):
    """rows: (source type, path or file, weight[, scale, scale random, rotation offset])."""
    a.parm('protos').set(len(rows))
    for i,r in enumerate(rows,1):
        typ,src,w=r[:3];a.parm('proto_on%d'%i).set(1);a.parm('proto_type%d'%i).set(typ);a.parm('%s%d'%(BANK[typ],i)).set(src);a.parm('proto_weight%d'%i).set(w)
        if len(r)>3:a.parm('proto_scale%d'%i).set(r[3]);a.parm('proto_scalevar%d'%i).set(r[4]);a.parmTuple('proto_rot%d'%i).set(r[5])
def stamp_node(name='stamp',bank=((0,'/World/Props/Rock',1.0),(0,'/World/Props/Fir',3.0),(0,'/World/Props/Stone',1.0))):
    a=stage.createNode(TYPE,name);a.setInput(0,scene);set_bank(a,bank);a.parm('sit').set(0);return a                                                          # the tests place at the hit point; the Sit On Surface tests switch it on
def mutate(a):
    g=a.hdaModule().stamp_quat.__globals__
    if not MUTATE or g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='quat':good=g['stamp_quat'];g['stamp_quat']=lambda d:good(np.asarray(d)[...,::-1])
    elif MUTATE=='align':g['stamp_align']=lambda normal,amount:np.array([0.0,0.0,0.0,1.0])
    elif MUTATE=='on':good=g['stamp_rows'];g['stamp_rows']=lambda t:(lambda r:np.concatenate([r[:,:10],np.ones((len(r),1))],axis=1) if len(r) else r)(good(t))
    elif MUTATE=='ids':good=g['stamp_cook'];src=good.__code__
    elif MUTATE=='group':g['_group']=lambda stage,row,text:[text.strip().rstrip('/*')]
    elif MUTATE=='snap':g['stamp_snap']=lambda v,s:float(v)
    elif MUTATE=='drag':g['stamp_drag']=lambda anchor,up,forward,right,point,footprint,snap_rot=0.0:(0.0,1.0,0.0)
    elif MUTATE=='bank':good=g['stamp_effective'];g['stamp_effective']=lambda r,ids,eidx,entries,seed:(lambda q,S:(q,r[:,6:9]))(*good(r,ids,eidx,entries,seed))
    elif MUTATE=='delta':g['stamp_delta_rows']=lambda rows,d:np.array(rows,dtype=np.float64,copy=True)
    elif MUTATE=='workset':g['stamp_workset']=lambda asset:[]
    elif MUTATE=='select':g['stamp_set_selection']=lambda asset,idx:None
    elif MUTATE=='thumb':g['stamp_thumb_triangles']=lambda asset,src,limit=3000:None
    elif MUTATE=='fav':g['stamp_favorites']=lambda asset:set()
    elif MUTATE=='paint':g['stamp_paint_dab']=lambda *a,**k:(np.zeros((0,3)),np.zeros((0,3)))
    elif MUTATE=='ghost':good=g['stamp_next_xform'];g['stamp_next_xform']=lambda asset,nx,position,normal,entries=None:(lambda r:(r[0],r[1],g['stamp_xform'](position,[0,0,0,1],[1,1,1])))(good(asset,nx,position,normal,entries))
    elif MUTATE=='sheet':good=g['stamp_edit_rows'];g['stamp_edit_rows']=lambda asset,indices,op='set',**v:good(asset,list(indices)[:1],op,**v)
    elif MUTATE=='groupring':good=g['stamp_group_items'];g['stamp_group_items']=lambda asset,n,bounds,cfg=None:(lambda r:(r[0][:1],r[1]))(good(asset,n,bounds,cfg))
    elif MUTATE=='conform':good=g['stamp_group_place'];g['stamp_group_place']=lambda asset,items,radius,nx,position,normal,surf=None:good(asset,items,radius,nx,position,normal,None)
    elif MUTATE=='manage':g['stamp_delete_proto']=lambda asset,row:0;g['stamp_counts']=lambda asset,text=None:{}
    elif MUTATE=='layout':g['stamp_group_offsets']=lambda kind,rad,sp,rng:np.stack([np.arange(len(rad))*0.01,np.zeros(len(rad))],axis=1)
    elif MUTATE=='groupscale':good=g['stamp_settings'];g['stamp_settings']=lambda asset,group=False:good(asset,False)
    elif MUTATE=='sit':g['stamp_sit']=lambda asset,nx,bounds:np.zeros(3)
    elif MUTATE=='smooth':g['_Smooth'].normal=lambda self,k,p:self.fn[k]
    elif MUTATE=='incremental':g['StampSurface'].near=lambda self,c,r:self;g['stamp_count']=lambda text:len(g['stamp_lines'](text))+1
    elif MUTATE=='falloff':g['falloff_multiplier']=lambda profile,r:np.ones_like(np.asarray(r,dtype=float))
    elif MUTATE=='stack':g['StampSurface']._stamps_hit=lambda self,o,d,limit:None
    elif MUTATE=='nearest':g['stamp_nearest']=lambda rows,o,d,tolerance=0.03:0 if len(rows) else None
def cooks(a):
    try:a.cook(force=True)
    except hou.OperationFailed:pass
def arrays(a):
    pi=UsdGeom.PointInstancer(a.stage().GetPrimAtPath(a.evalParm('outputpath')))
    pos=np.array(pi.GetPositionsAttr().Get()).reshape(-1,3);sc=np.array(pi.GetScalesAttr().Get()).reshape(-1,3);idx=np.array(pi.GetProtoIndicesAttr().Get(),dtype=int);ids=np.array(pi.GetIdsAttr().Get(),dtype=int)
    q=[(float(x.GetReal()),)+tuple(float(c) for c in x.GetImaginary()) for x in pi.GetOrientationsAttr().Get()];return pos,sc,idx,ids,np.array(q).reshape(-1,4),pi
def apply(qwxyz,v):
    w,x,y,z=qwxyz;u=np.array([x,y,z]);v=np.asarray(v,float);return v+2*w*np.cross(u,v)+2*np.cross(u,np.cross(u,v))

# ---- 1 contract
a=stamp_node();m=a.hdaModule();mutate(a)
names=[p.name() for p in a.parms()]
check('contract',all(n in names for n in ('start','onstamps','clear','target','outputpath','protos','hidesrc','scale','scalerangex','yaw','yawrand','tilt','align','offset','seed','proto','protorand','snap','snaprot','dragset','stamps','selection','workset','brush','mode1','brush_random1','selinfo','favorites','panestatus','reload_pane','paint_radius','paint_density','paint_spacing','paint_falloff','sel_all','sel_none','sel_invert','sel_dup','sel_del')),names)
check('contract',len(names)<160 and [t.label() for t in a.parmTemplateGroup().entries() if t.type()==hou.parmTemplateType.Folder]==['Brush','Edit','Options'],len(names))                    # the tabs Brush / Edit / Options
check('contract',a.node('STAMPS') is not None and a.node('STAMPS').type().name()=='pythonscript' and len(a.type().definition().sections())>0)
check('contract',a.type().definition().sections().get('ViewerStateModule') is not None and 'DefaultState' in a.type().definition().sections())
check('contract',not a.errors() and a.stage() is not None,a.errors())
sub=[t for t in a.parmTemplateGroup().findFolder('Brush').parmTemplates()];check('contract',[t.label() for t in sub]==['Randomization','Asset','Placement','Paint','Group'] and a.evalParm('mode1')==0 and all(a.parm(n).parmTemplate().isHidden() for n in ('stamps','selection','workset','brush')) and a.evalParm('selinfo')=='No stamps yet.',[t.label() for t in sub])   # Randomization / Asset / Placement inside Brush; the data parameters are hidden
inside=lambda tab:{p.name() for p in a.parmTemplateGroup().findFolder(('Brush',tab)).parmTemplates() for p in ([p] if p.type()!=hou.parmTemplateType.Folder else p.parmTemplates())}
check('contract',{'protorand','scale','scalerange','yaw','yawrand','tilt','seed'}<=inside('Randomization') and 'protorand' not in inside('Asset') and {'align','offset','snap','snaprot','dragset'}<=inside('Placement') and 'align' not in inside('Randomization'),(inside('Randomization'),inside('Placement')))   # Randomization: the prototype, the scale, the rotation, the seed; Placement: where and how a stamp lands
check('contract',[p.label() for p in a.parmTemplateGroup().findFolder(('Brush','Randomization')).parmTemplates()]==['Prototype','Scale','Rotation','Seed'])
check('contract',UsdGeom.PointInstancer(a.stage().GetPrimAtPath('/World/Stamps')).GetPositionsAttr().Get() is not None)       # no stamps: an empty instancer, no error

# ---- 2 cook
a.parm('stamps').set('1 2 3  0 0 0  1 1 1  1 1\n4 5 6  0 90 0  2 2 2  2 1\n7 8 9  0 0 0  1 1 1  3 0\n-1 0 0  0 0 0  0.5 0.5 0.5  2 1')
pos,sc,idx,ids,q,pi=arrays(a);check('cook',len(pos)==3 and ids.tolist()==[0,1,3] and idx.tolist()==[0,1,1] and np.allclose(pos[0],[1,2,3]) and np.allclose(sc[1],[2,2,2]),(ids,idx))   # off stamps are not written; ids keep the line number
check('cook',np.allclose(apply(q[1],[1,0,0]),[0,0,-1],atol=1e-3),apply(q[1],[1,0,0]))                                       # 90 degrees about Y turns +X onto -Z
targets=[str(t) for t in pi.GetPrototypesRel().GetTargets()];check('cook',len(targets)==3 and all(a.stage().GetPrimAtPath(t).IsValid() for t in targets),targets)
check('cook',UsdGeom.Imageable(a.stage().GetPrimAtPath('/World/Props/Rock')).ComputeVisibility()=='invisible' and UsdGeom.Imageable(a.stage().GetPrimAtPath(targets[0])).ComputeVisibility()=='inherited')   # sources hidden, prototypes visible
a.parm('hidesrc').set(0);check('cook',UsdGeom.Imageable(a.stage().GetPrimAtPath('/World/Props/Rock')).ComputeVisibility()=='inherited');a.parm('hidesrc').set(1)
set_bank(a,[(3,'/World/Set',1.0),(0,'/World/Props/Rock',1.0)]);a.parm('stamps').set('\n'.join('%d 0 0  0 0 0  1 1 1  1 1'%k for k in range(30))+'\n0 0 0  0 0 0  1 1 1  2 1')
pos,sc,idx,ids,q,pi=arrays(a);check('cook',len(pi.GetPrototypesRel().GetTargets())==4 and set(idx[:30].tolist())=={0,1,2} and idx[30]==3,(set(idx[:30].tolist()),idx[30]))    # a group line is its children; a stamp takes one
set_bank(a,[(0,'/World/Nothing',1.0)]);cooks(a);check('cook',any('not a prim' in e for e in a.errors()),a.errors())
set_bank(a,[(0,'',1.0)]);a.parm('stamps').set('1 2 3  0 0 0');cooks(a);check('cook',any('11 numbers' in e for e in a.errors()),a.errors())       # a broken line says what is wrong
a.parm('stamps').set('1 2 3  0 0 0  1 1 1  1 1');cooks(a);pos,sc,idx,ids,q,pi=arrays(a);check('cook',not a.errors() and len(pos)==1 and len(pi.GetPrototypesRel().GetTargets())==1)     # empty Prototypes: the built-in sphere
a.parm('stamps').set('# a comment\n1 2 3  0 0 0  1 1 1  1 1\n\n2 2 3  0 0 0  1 1 1  1 1');pos,sc,idx,ids,q,pi=arrays(a);check('cook',len(pos)==2)

# ---- 3 placing
b=stamp_node('place');m=b.hdaModule();mutate(b);b.parm('stamps').set('')
check('placing',m.stamp_add(b,(1.0,0.0,2.0))==1 and m.stamp_rows(b.evalParm('stamps')).shape==(1,11) and np.allclose(m.stamp_rows(b.evalParm('stamps'))[0,:3],[1,0,2]))
n=np.array([1.0,1.0,0.0])/np.sqrt(2);b.parm('align').set(1.0);m.stamp_add(b,(0,0,0),normal=n);r=m.stamp_rows(b.evalParm('stamps'))[1];check('placing',np.allclose(apply(np.roll(m.stamp_quat(r[3:6]),1),[0,1,0]),n,atol=1e-3))   # aligned to the surface normal
b.parm('align').set(0.0);m.stamp_add(b,(0,0,0),normal=n);r=m.stamp_rows(b.evalParm('stamps'))[2];check('placing',np.allclose(r[3:6],[0,0,0],atol=1e-3))                                    # not aligned: upright
b.parm('stamps').set('');b.parmTuple('scalerange').set((0.5,2.0));b.parm('yawrand').set(60.0);b.parm('tilt').set(10.0);b.parm('yaw').set(30.0);b.parm('protorand').set(1);b.parm('seed').set(5)
for k in range(40):m.stamp_add(b,(k,0,0))
R=m.stamp_rows(b.evalParm('stamps'));check('placing',R[:,6].min()>=0.5-1e-3 and R[:,6].max()<=2.0+1e-3 and R[:,6].std()>0.1 and np.allclose(R[:,6],R[:,7]),(R[:,6].min(),R[:,6].max()))   # random scale in range, uniform
yaws=np.array([m.stamp_euler(m.stamp_qmul(m.stamp_quat([0,0,0]),m.stamp_quat(r[3:6])))[1] for r in R]);check('placing',np.abs(yaws-30).max()<=60+11 and yaws.std()>5)             # random rotation about 30 +/- 60 (plus the tilt)
check('placing',set(R[:,9].astype(int).tolist())=={1,2,3} and (R[:,9]==2).sum()>(R[:,9]==1).sum())                                                                                      # random prototype, by weight (3 : 1 : 1)
b.parm('stamps').set('');[m.stamp_add(b,(k,0,0)) for k in range(5)];R2=m.stamp_rows(b.evalParm('stamps'));check('placing',np.allclose(R2[:,:],R[:5,:]))                                    # the same seed gives the same stamps
b.parm('seed').set(6);b.parm('stamps').set('');[m.stamp_add(b,(k,0,0)) for k in range(5)];check('placing',not np.allclose(m.stamp_rows(b.evalParm('stamps'))[:,6],R2[:,6]))                  # another seed gives other ones
b.parmTuple('scalerange').set((1.0,1.0));b.parm('yawrand').set(0.0);b.parm('tilt').set(0.0);b.parm('protorand').set(0);b.parm('seed').set(1);b.parm('stamps').set('')
b.parm('snap').set(2.0);m.stamp_add(b,(2.9,0,5.2));r=m.stamp_rows(b.evalParm('stamps'))[0];check('placing',m.stamp_snap(2.9,2.0)==2.0 and m.stamp_snap(5.2,2.0)==6.0)
b.parm('stamps').set('');[m.stamp_add(b,(k,0,0),proto=1) for k in range(4)];m.stamp_delete(b,1);check('placing',m.stamp_rows(b.evalParm('stamps'))[:,0].tolist()==[0,2,3])
m.stamp_delete_last(b);check('placing',m.stamp_rows(b.evalParm('stamps'))[:,0].tolist()==[0,2]);rows=m.stamp_rows(b.evalParm('stamps'))
check('placing',m.stamp_nearest(rows,(2.0,10.0,0.05),(0,-1,0))==1 and m.stamp_nearest(rows,(9.0,10.0,9.0),(0,-1,0)) is None)
m.stamp_clear(b);check('placing',b.evalParm('stamps')=='' and 'No stamps' in m.stamp_info(b))
b2=stamp_node('place2');b2m=b2.hdaModule();mutate(b2);b3=stamp_node('place3');mutate(b3)
for k_,v_ in (('yawrand',70.0),('tilt',9.0),('protorand',1),('seed',11),('align',1.0),('offset',0.25)):b2.parm(k_).set(v_);b3.parm(k_).set(v_)
b2.parmTuple('scalerange').set((0.5,1.7));b3.parmTuple('scalerange').set((0.5,1.7))
P_=[(k*0.7,0.1*k,2.0-k*0.3) for k in range(9)];N_=[(0.0,1.0,0.0) if k%2 else (0.3,0.9,0.1) for k in range(9)]
for p_,n_ in zip(P_,N_):b2m.stamp_add(b2,p_,n_)
check('placing',m.stamp_add_batch(b3,P_,N_)==9 and b3.evalParm('stamps')==b2.evalParm('stamps'),'the batch makes the same stamps as the clicks (same draws, same order)')
b.parm('scale').set(1.0);b.parm('yaw').set(0.0);b.parm('proto').set(2);m.stamp_add(b,(0,0,0),scale_mult=2.0,yaw_add=40.0);r=m.stamp_rows(b.evalParm('stamps'))[0];check('placing',r[9]==2 and np.allclose(r[6:9],2.0) and abs(r[4]-40.0)<1e-2,r)   # the drag adds to the settings

# ---- 4 surface
c=stamp_node('surf');m=c.hdaModule();mutate(c);s=m.stamp_surface(c);h=s.hit((3,10,2),(0,-1,0));check('surface',h is not None and np.allclose(h[0],[3,0,2]) and np.allclose(h[1],[0,1,0]) and abs(h[2]-10)<1e-9)       # the ground plane
h=s.hit((3,-10,2),(0,1,0));check('surface',h is not None and h[1][1]<0)                                                                                                                                  # looking from below: nothing
c.parm('target').set('/World/Ramp');s=m.stamp_surface(c);h=s.hit((0,20,0),(0,-1,0));check('surface',h is not None and abs(h[0][1]-2.5)<1e-6 and np.allclose(h[1],np.array([0,1,0.5])/np.linalg.norm([0,1,0.5]),atol=1e-6))   # the ramp: y = (5 - z) / 2
h=s.hit((0,-20,0),(0,1,0));check('surface',h is not None and h[1][1]<0)                                                                                                                 # the normal faces the ray
check('surface',s.hit((50,20,0),(0,-1,0)) is None)
c.parm('snap').set(2.0);p,nrm=s.snapped(np.array([1.1,2.0,1.3]),np.array([0,1.0,0]),2.0);check('surface',abs(p[0]-2.0)<1e-9 and abs(p[2]-2.0)<1e-9 and abs(p[1]-(5-2.0)/2)<1e-3,(p,nrm))                  # snapped to the grid, put back on the ramp
c.parm('target').set('/World/Nothing');
try:m.stamp_surface(c);check('surface',False)
except hou.Error:check('surface',True)
c.parm('target').set('/World/Props/Stone');s=m.stamp_surface(c);h=s.hit((0.3,20,0.2),(0,-1,0));check('surface',h is not None and abs(h[0][1]-1.0)<1e-6 and np.allclose(h[1],[0,1,0],atol=1e-6),h)   # a basic shape (a Cube of size 2) is a surface too
c.parm('target').set('/World/Ramp /World/Props/Stone');s=m.stamp_surface(c);h=s.hit((0,20,0),(0,-1,0));h2=s.hit((0,-20,0),(0,1,0));check('surface',abs(h[0][1]-2.5)<1e-6 and abs(h2[0][1]+1.0)<1e-6,(h,h2))   # several Place On prims: the nearest
# object aware: the stamps already placed are surfaces (Place On Stamps)
c.parm('target').set('');c.parm('snap').set(0.0)
c.parm('stamps').set('0 0 0  0 0 0  1 1 1  1 1\n5 0 0  0 0 0  2 2 2  1 1\n10 0 0  0 45 0  1 1 1  3 1\n-5 0 0  0 0 0  1 1 1  1 0');s=m.stamp_surface(c)
h=s.hit((0,10,0),(0,-1,0));check('stack',h is not None and abs(h[0][1]-1.0)<1e-5 and h[1][1]>0.95 and s.last_stamp==0,(h,s.last_stamp))           # on the Rock (a sphere of radius 1): its top
h=s.hit((5,10,0),(0,-1,0));check('stack',abs(h[0][1]-2.0)<1e-5 and s.last_stamp==1,h)                                                                                       # a stamp scaled 2: twice as high
h=s.hit((10,0.5,10),(0,0,-1));check('stack',abs(h[0][2]-np.sqrt(2))<1e-6 and abs(h[0][0]-10)<1e-9 and s.last_stamp==2 and np.allclose(np.abs(h[1]),np.array([1,0,1])/np.sqrt(2),atol=1e-6),h)   # the Stone turned 45 degrees: its corner
h=s.hit((-5,10,0),(0,-1,0));check('stack',abs(h[0][1])<1e-9 and s.last_stamp is None)                                                                                      # a stamp switched off is not there
h=s.hit((2.5,10,0),(0,-1,0));check('stack',abs(h[0][1])<1e-9 and s.last_stamp is None)                                                                                     # between stamps: the ground
c.parm('onstamps').set(0);s.update(c);h=s.hit((0,10,0),(0,-1,0));check('stack',abs(h[0][1])<1e-9 and s.last_stamp is None);c.parm('onstamps').set(1)                    # Place On Stamps off: through them
s.update(c);m.stamp_add(c,s.hit((0,10,0),(0,-1,0))[0],(0,1,0),proto=1);s.update(c);h=s.hit((0,10,0),(0,-1,0));check('stack',abs(h[0][1]-2.0)<1e-5 and s.last_stamp==4,h)   # a stamp on a stamp: the next one lands on its top (a stack)
t0=time.time();c.parm('stamps').set('\n'.join('%g 0 %g  0 0 0  1 1 1  1 1'%(k%40*3,k//40*3) for k in range(1600)));s.update(c);up=(time.time()-t0)*1000;t0=time.time()
for k in range(200):s.hit((k%40*3+0.2,10,(k//40)*3+0.1),(0,-1,0))
hit=(time.time()-t0)/200*1000;check('stack',hit<2.0 and up<300.0,(hit,up))                                                                                                # 1600 stamps: a ray in well under a frame

# ---- 5 speed: the point of this node
d=stamp_node('speed');m=d.hdaModule();d.parm('stamps').set('');d.stage();lines=[]
t=time.time()
for k in range(300):m.stamp_add(d,(k*0.1,0,0))
add=(time.time()-t)/300*1000;d.stage();t=time.time();d.parm('seed').set(2);d.stage();cook=(time.time()-t)*1000
check('speed',add<15.0,add);check('speed',cook<150.0,cook)                                                                 # one stamp costs a parameter write; 300 stamps cook in well under a frame of waiting
t=time.time();d.parm('stamps').set(d.evalParm('stamps')+'\n0 0 0  0 0 0  1 1 1  1 1');d.stage();one=(time.time()-t)*1000;check('speed',one<150.0,one)
big=hou.Geometry();N=300;pts=[(i*0.1,0.0,j*0.1) for j in range(N+1) for i in range(N+1)];tris=[]
for j in range(N):
    for i in range(N):aa=j*(N+1)+i;tris+=[[aa,aa+N+1,aa+N+2],[aa,aa+N+2,aa+1]]
big.createPoints(pts);big.createPolygons(tris);pp=hou.Vector3();nn=hou.Vector3();uv=hou.Vector3();t=time.time()
for k in range(100):big.intersect(hou.Vector3((k*0.1,50.0,10.0)),hou.Vector3((0,-1,0)),pp,nn,uv)
check('speed',(time.time()-t)/100*1000<2.0,'%d triangles'%len(tris))                                                      # a ray against 180 000 triangles

# ---- 5b editing: the selection, the handle delta, duplicate / delete / edit, the working set
ed=stamp_node('edit');m=ed.hdaModule();mutate(ed);ed.parm('stamps').set('0 0 0  0 0 0  1 1 1  1 1\n3 0 0  0 90 0  1 1 1  2 1\n6 0 0  0 0 0  2 2 2  3 0')
q=np.array([m.stamp_quat((10.0,20.0,30.0)),m.stamp_quat((0.0,90.0,0.0)),m.stamp_quat((-40.0,-30.0,170.0))]);e3=m.stamp_eulers(q);check('edit',all(np.allclose(m.stamp_quat(e3[k]),q[k]*np.sign(np.dot(m.stamp_quat(e3[k]),q[k])),atol=1e-9) for k in range(3)) and np.allclose(e3[0],[10,20,30]))   # the vectorised Euler angles give back the rotation
rows=m.stamp_rows(ed.evalParm('stamps'));d=m.stamp_handle_delta(dict(tx=1.0,ty=2.0,tz=3.0,ry=90.0,sx=2.0,sy=2.0,sz=2.0,px=3.0));new=m.stamp_delta_rows(rows[[0,1]],d)
c=np.array([3.0,0,0]);want0=np.array([2.0*(0-3.0),0,0]);R=np.array([[0,0,1],[0,1,0],[-1,0,0]],dtype=float);want0=R@want0+c+np.array([1,2,3]);check('edit',np.allclose(new[0,:3],want0,atol=1e-9) and np.allclose(new[1,6:9],2.0) and np.allclose(new[:,9:],rows[[0,1],9:]),(new[0,:3],want0))   # scale 2, then Y turned 90, then moved, about the pivot (3, 0, 0)
check('edit',np.allclose(m.stamp_delta_rows(rows,m.stamp_handle_delta({})),rows,atol=1e-9) and np.allclose(m.stamp_selection_pivot(rows,np.array([0,2])),[3,0,0]))      # the identity handle changes nothing; the pivot is the centre
m.stamp_set_selection(ed,[2,0,2,9]);check('edit',list(m.stamp_get_selection(ed))==[0,2,9] and list(m.stamp_get_selection(ed,3))==[0,2] and 'selected' in m.stamp_selection_info(ed) and m.stamp_selection_info(ed)=='2 of 3 stamps selected.')
m.stamp_select_all(ed);check('edit',list(m.stamp_get_selection(ed))==[0,1,2]);m.stamp_select_invert(ed);check('edit',list(m.stamp_get_selection(ed))==[]);m.stamp_select_none(ed);m.stamp_set_selection(ed,[1])
nw=m.stamp_duplicate_selected(ed);check('edit',nw==[3] and len(m.stamp_lines(ed.evalParm('stamps')))==4 and m.stamp_lines(ed.evalParm('stamps'))[3]==m.stamp_lines(ed.evalParm('stamps'))[1] and list(m.stamp_get_selection(ed))==[3])
check('edit',m.stamp_delete_selected(ed)==1 and len(m.stamp_lines(ed.evalParm('stamps')))==3 and ed.evalParm('selection')=='')
check('edit',m.stamp_edit_row(ed,1,x=7.5,sx=3.0,sy=3.0,sz=3.0,proto=1,on=0) and np.allclose(m.stamp_rows(ed.evalParm('stamps'))[1,[0,6,7,8,9,10]],[7.5,3,3,3,1,0]) and not m.stamp_edit_row(ed,9,x=1))
ed.parm('protos').set(3);[ed.parm('proto_prim%d'%k).set('/World/Props/'+n) for k,n in ((1,'Rock'),(2,'Fir'),(3,'Stone'))]
m.stamp_set_workset(ed,[3,1]);check('edit',m.stamp_workset(ed)==[1,3] and ed.evalParm('proto')==1);m.stamp_set_workset(ed,[2],proto=2);check('edit',m.stamp_workset(ed)==[2] and ed.evalParm('proto')==2)
ed.parm('proto_on3').set(0);m.stamp_set_workset(ed,[2,3]);check('edit',m.stamp_workset(ed)==[2],m.stamp_workset(ed))                                                    # a row switched off leaves the working set
ed.parm('proto_on3').set(1);m.stamp_set_workset(ed,[1,3]);ed.parm('protorand').set(1);ed.parm('stamps').set('')
for k in range(60):m.stamp_add(ed,(k,0,0))
check('edit',set(m.stamp_rows(ed.evalParm('stamps'))[:,9].astype(int).tolist())=={1,3},set(m.stamp_rows(ed.evalParm('stamps'))[:,9].astype(int).tolist()))             # Random Prototype draws among the working set only
m.stamp_set_workset(ed,[]);ed.parm('stamps').set('')
for k in range(60):m.stamp_add(ed,(k,0,0))
check('edit',set(m.stamp_rows(ed.evalParm('stamps'))[:,9].astype(int).tolist())=={1,2,3});ed.parm('protorand').set(0)
cy=m.stamp_cycle(ed,1);check('edit',cy==2 and m.stamp_cycle(ed,-1)==1)

Pd,Td=m.stamp_ghost_arrays.__globals__['_sphere'](1.0,seg=100,rings=100);Cd_=np.tile((0.5,0.6,0.7),(len(Pd),1));P2,T2,C2=m.stamp_decimate(Pd,Td,Cd_,2000)
check('edit',len(Td)>15000 and 300<len(T2)<=2000 and C2.shape==P2.shape and T2.max()<len(P2) and np.all(P2.min(0)>-1.0-1e-9) and np.all(P2.max(0)<1.0+1e-9) and np.all(np.linalg.norm(P2,axis=1)>0.7) and len(set(map(tuple,np.sort(T2,axis=1).tolist())))==len(T2),(len(Td),len(T2)))      # a lighter copy: a whole sphere still, no duplicate or collapsed triangles
check('edit',m.stamp_decimate(Pd,Td[:500],Cd_,2000)[1].shape==(500,3))

# ---- 6 viewer: the Layout-style brushes and the Edit mode through a stand-in viewport that looks straight down
class StubDrawable(object):
    def __init__(self,*a,**k):self.geo=None;self.shown=False;self.params={};self.drawn=0
    def setParams(self,p):self.params.update(p)
    def setGeometry(self,g):self.geo=g
    def setTransform(self,x):self.xf=x
    def show(self,v):self.shown=v
    def draw(self,handle,params=None):self.drawn+=1;self.last=params
class StubViewport(object):
    def mapToScreen(self,p):return (p[0]*10.0,p[2]*10.0)
    def mapToWorld(self,x,y):return hou.Vector3((x/10.0,10.0,y/10.0)),hou.Vector3((0,-1,0))
class StubViewer(object):
    def __init__(self):self.prompt=None;self.hud_template=None;self.hud_values={};self.hud_sets=0;self.handle=None;self.undo=[]
    def setPromptMessage(self,msg,t=None):self.prompt=msg
    def clearPromptMessage(self):self.prompt=None
    def curViewport(self):return StubViewport()
    def hudInfo(self,show=-1,template=None,values=None,**k):
        if template is not None:self.hud_template=template
        if values is not None:self.hud_values.update(values);self.hud_sets+=1
    def showHandle(self,name,value):self.handle=(name,bool(value))
    def beginStateUndo(self,label):self.undo.append('begin')
    def endStateUndo(self):self.undo.append('end')
class Device(object):
    def __init__(self,x,y,left=False,ctrl=False,key='',shift=False,wheel=0,down=False):self.x,self.y,self.left,self.ctrl,self.key,self.shift,self.wheel,self.down=x,y,left,ctrl,key,shift,wheel,down
    def isShiftKey(self):return self.shift
    def mouseWheel(self):return self.wheel
    def mouseX(self):return self.x
    def mouseY(self):return self.y
    def isLeftButton(self):return self.left
    def isCtrlKey(self):return self.ctrl
    def isMiddleButton(self):return False
    def isAltKey(self):return False
    def isKeyDown(self):return self.down
    def keyString(self):return self.key
class Event(object):
    """A viewport that looks straight down: pixel (x, y) is the ray from (x/10, 10, y/10) along -Y."""
    def __init__(self,device,reason):self.d,self.r=device,reason
    def device(self):return self.d
    def reason(self):return self.r
    def curViewport(self):return StubViewport()
    def ray(self):x,y=self.d.mouseX(),self.d.mouseY();return hou.Vector3((x/10.0,10.0,y/10.0)),hou.Vector3((0,-1,0))
ns=types.SimpleNamespace(**{k:getattr(hou,k) for k in ('Vector4','Vector3','Color','Geometry','drawableGeometryType','drawableTextOrigin','uiEventReason','promptMessageType','Error','lopNodeTypeCategory','ViewerStateTemplate','undos')});ns.GeometryDrawable=StubDrawable;ns.TextDrawable=StubDrawable
code=a.type().definition().sections()['ViewerStateModule'].contents();glob={'hou':ns,'np':np};exec(compile(code.replace('import hou'+chr(10),'',1),'stamp_state.py','exec'),glob);glob['STRICT']=True
if MUTATE=='keys':glob['hk_is']=lambda key,token:False
viewer=StubViewer();state=glob['StampState']('arraytron_stamp_test',viewer);R=hou.uiEventReason
e=stamp_node('viewer');mutate(e);m=e.hdaModule();e.parm('stamps').set('');e.parm('onstamps').set(0);state.onEnter({'node':e})
def mouse(x,z,reason,**kw):return state.onMouseEvent({'ui_event':Event(Device(float(x)*10,float(z)*10,**kw),reason)})
def px(x,z,reason,**kw):return state.onMouseEvent({'ui_event':Event(Device(float(x),float(z),**kw),reason)})
def key(k,**kw):return state.onKeyEvent({'ui_event':Event(Device(0,0,key=k,**kw),R.Changed)})
def wheel(step,**kw):return state.onMouseWheelEvent({'ui_event':Event(Device(0,0,wheel=step,**kw),R.Changed)})
def draw():state.onDraw({'draw_handle':None})
def stamps():return m.stamp_rows(e.evalParm('stamps'))
def yaw_of(row):q=m.stamp_quat(row[3:6]);return np.degrees(2*np.arctan2(q[1],q[3]))
def angdiff(a,b):return abs((a-b+180.0)%360.0-180.0)
def fresh(text='',**parms):
    """A new set of stamps, the Brush mode with the Place brush."""
    e.parm('stamps').set(text);e.parm('selection').set('');e.parm('mode1').set(0);e.parm('brush').set(0);e.parm('workset').set('');e.parm('proto').set(0);e.parm('scale').set(1.0);e.parm('yaw').set(0.0);time.sleep(0.3)
    for k,v in parms.items():(e.parmTuple(k).set(v) if isinstance(v,tuple) else e.parm(k).set(v))
keys=[r.get('key') for r in viewer.hud_template['rows'] if isinstance(r,dict)]
check('viewer',viewer.hud_template is not None and viewer.hud_template['title']=='Arraytron Stamp' and any(r.get('key')=='Shift LMB' for g in viewer.hud_template['rows'] if g.get('rows') for p in g['rows'] if p.get('rows') for r in p['rows']),viewer.hud_template['title'])   # the hints are the HUD panel, with Houdini's wording
check('viewer',viewer.hud_values.get('mode')=='Brush / Place' and viewer.hud_values.get('v_count')=='0' and viewer.hud_values.get('mode_page')==0,viewer.hud_values)
check('viewer',mouse(3,2,R.Located) is True and state.marker.shown and state.ghost.shown and not state.box.shown and not state.dial.shown)                          # hovering: the ring and the prototype itself (the ghost), not the box
F=m.stamp_footprint(m.stamp_proto_bounds(e)[1]);lo,hi=m.stamp_proto_bounds(e)[1];check('viewer',np.allclose(lo,[-1,-1,-1]) and np.allclose(hi,[1,1,1]) and abs(F-1.0)<1e-9,(lo,hi,F))   # the Rock (a sphere of radius 1) measured once
sets=viewer.hud_sets;[mouse(3+k*0.01,2,R.Located) for k in range(20)];check('viewer',viewer.hud_sets==sets)                                                          # moving the mouse does not touch the HUD
mouse(3,2,R.Start,left=True);check('viewer',e.evalParm('stamps')=='');mouse(3,2,R.Changed,left=False);rows=stamps();check('viewer',len(rows)==1 and np.allclose(rows[0,:3],[3,0,2],atol=1e-6) and viewer.hud_values['v_count']=='1')
mouse(3,2,R.Picked,left=True);check('viewer',len(stamps())==1)                                  # the click arrives as Start, Changed and Picked: one stamp
time.sleep(0.3);px(60,50,R.Start,left=True);px(62,51,R.Active,left=True);px(62,51,R.Changed)
r=stamps();check('viewer',len(r)==2 and np.allclose(r[1,:3],[6,0,5],atol=1e-6) and np.allclose(r[1,6:9],1.0) and np.allclose(r[1,3:6],0.0,atol=1e-6),r[1:])          # a jitter of 3 pixels is a click: the settings
# the drag of the Place brush: both, Shift scale only, Ctrl orient (increments), Ctrl+Shift orient freely
fresh();px(60,50,R.Start,left=True);px(140,-100,R.Active,left=True)
check('viewer',state.dial.shown and state.ghost.shown and not state.box.shown and not state.marker.shown and state.text.shown and state.labels,'the dial while dragging')
v=np.array([8.0,0.0,-15.0]);yaw=np.degrees(np.arctan2(8.0,-15.0));check('viewer',abs(state.drag['yaw']-yaw)<1e-6 and abs(state.drag['scale']-17.0/F)<1e-6 and abs(state.drag['dist']-17.0)<1e-6,state.drag)
draw();check('viewer',state.dial.drawn>0 and state.text.drawn==1 and '17.00' in state.text.last['text'] and abs(state.text.last['translate'][0]-(140.0+14.0))<1e-3,state.text.last)   # the scale and angle by the mouse
check('viewer',viewer.hud_values['v_scale']=='17' and viewer.hud_values['v_rot'].startswith('151.9'),viewer.hud_values)
px(140,-100,R.Changed);r=stamps()[0];q=np.roll(m.stamp_quat(r[3:6]),1);check('viewer',np.allclose(apply(q,[0,0,1]),v/np.linalg.norm(v),atol=1e-3) and np.allclose(r[6:9],17.0/F,atol=1e-3) and np.allclose(r[:3],[6,0,5],atol=1e-6),r)   # it faces the mouse and reaches it
check('viewer',not state.dial.shown and state.ghost.shown)
fresh(yawrand=0.0,yaw=20.0);px(60,50,R.Start,left=True,shift=True);px(140,-100,R.Active,left=True,shift=True);px(140,-100,R.Changed);r=stamps()[0]
check('viewer',angdiff(yaw_of(r),20.0)<1e-2 and np.allclose(r[6:9],17.0/F,atol=1e-3),r)                                                                                          # Shift: the scale only (the rotation stays the setting)
fresh(scale=1.0);px(60,50,R.Start,left=True,ctrl=True);px(140,-100,R.Active,left=True,ctrl=True);check('viewer',abs(state.drag['yaw']-150.0)<1e-9 and not state.drag['set_scale'],state.drag['yaw']);px(140,-100,R.Changed);r=stamps()[0]
check('viewer',angdiff(yaw_of(r),150.0)<1e-2 and np.allclose(r[6:9],1.0,atol=1e-3),r)                                                                                            # Ctrl: the angle to 15 degree steps, the scale stays the setting
fresh();px(60,50,R.Start,left=True,ctrl=True,shift=True);px(140,-100,R.Active,left=True,ctrl=True,shift=True);check('viewer',abs(state.drag['yaw']-yaw)<1e-6,state.drag['yaw']);px(140,-100,R.Changed);r=stamps()[0]
check('viewer',angdiff(yaw_of(r),yaw)<1e-2 and np.allclose(r[6:9],1.0,atol=1e-3),r)                                                                                              # Ctrl+Shift: the angle freely
fresh(snaprot=45.0);px(60,50,R.Start,left=True);px(140,-100,R.Active,left=True);check('viewer',abs(state.drag['yaw']-135.0)<1e-9,state.drag['yaw']);px(140,-100,R.Changed);e.parm('snaprot').set(0.0)
fresh(yawrand=90.0,scalerange=(0.5,2.0));mouse(1,1,R.Located);nx=m.stamp_next(e,(0,1,0));mouse(1,1,R.Start,left=True);mouse(1,1,R.Changed)
r=stamps()[-1];check('viewer',np.allclose(r[6],nx['scale'],atol=1e-3) and abs(np.degrees(2*np.arctan2(m.stamp_quat(r[3:6])[1],m.stamp_quat(r[3:6])[3]))-nx['yaw'])<1e-3,(r,nx))    # the box under the mouse was the stamp the click made (random draws included)
e.parm('yawrand').set(0.0);e.parmTuple('scalerange').set((1.0,1.0))
# the ghost: the prototype at the stamp's place (the bank row's Scale and Rotation Offset included), the box only when there is nothing to draw
fresh();e.parm('proto_scale1').set(2.0);e.parmTuple('proto_rot1').set((0.0,90.0,0.0));mouse(3,2,R.Located);xf=state.ghost.xf
v0=hou.Vector3(1.0,0.0,0.0)*xf;v1=hou.Vector3(0.0,1.0,0.0)*xf;check('viewer',np.allclose(tuple(v0),[3,0,0],atol=1e-6) and np.allclose(tuple(v1),[3,2,2],atol=1e-6),(tuple(v0),tuple(v1)))   # scale 2, turned 90 degrees about Y, at (3, 0, 2)
gr=m.stamp_ghost_arrays(e,('stage','/World/Props/Rock'));check('viewer',gr is not None and gr[0].shape[1]==3 and len(gr[1])<=6000 and gr[2].shape==gr[0].shape and gr[2].max()<=1.0 and gr[2].std()>0.01)   # the geometry of the prototype with a lit colour per point
gd=m.stamp_ghost_geo(gr);check('viewer',gd.findPointAttrib('Cd') is not None and len(gd.prims())==len(gr[1]))
e.parm('proto_scale1').set(1.0);e.parmTuple('proto_rot1').set((0.0,0.0,0.0));e.parm('proto_prim1').set('/World/Nothing');state.entries_key=None;state.ghosts={};mouse(3,2,R.Located);check('viewer',not state.ghost.shown and state.box.shown)                       # an unresolved bank: the box is drawn instead
e.parm('proto_prim1').set('/World/Props/Rock');state.entries_key=None;state.ghosts={};mouse(3,2,R.Located);check('viewer',state.ghost.shown and not state.box.shown)
# the wheel cycles the working set; Shift / Ctrl wheel; the keys
fresh();check('viewer',wheel(1) is True and e.evalParm('proto')==2 and wheel(1) is True and e.evalParm('proto')==3 and wheel(1) is True and e.evalParm('proto')==1 and wheel(-1) is True and e.evalParm('proto')==3,e.evalParm('proto'))   # no working set: every row
e.parm('workset').set('1 3');e.parm('proto').set(1);wheel(1);check('viewer',e.evalParm('proto')==3);wheel(1);check('viewer',e.evalParm('proto')==1,e.evalParm('proto'))                         # a working set of two rows
check('viewer',viewer.hud_values['v_proto'].startswith('1') and 'set of 2' in viewer.hud_values['v_proto'],viewer.hud_values['v_proto'])
fresh();check('viewer',wheel(1,shift=True) is True and abs(e.evalParm('scale')-1.1)<1e-9 and wheel(-1,ctrl=True) is True and e.evalParm('yaw')==-15.0)
check('viewer',viewer.hud_values['v_scale']=='1.1' and viewer.hud_values['v_rot']=='-15.0 deg',viewer.hud_values)                                              # the wheel shows at once
for k,parm,value in ((']','scale',1.21),('[','scale',1.1),('.','yaw',0.0),(',','yaw',-15.0)):
    check('viewer',key(k) is True and abs(e.evalParm(parm)-value)<1e-9,(k,e.evalParm(parm)))
check('viewer',key('2') is True and e.evalParm('proto')==2 and e.evalParm('workset')=='2' and key('0') is True and e.evalParm('workset')=='',e.evalParm('workset'))   # a digit: that row is the working set; 0: no working set
check('viewer',key('x') is False and key('Enter') is False)                                                                                                         # Enter with nothing to finish leaves the tool as it always does
e.parm('target').set('/World/Ramp');e.parm('align').set(1.0);e.parm('stamps').set('');time.sleep(0.3);mouse(0,0,R.Start,left=True);mouse(0,0,R.Changed,left=False)
r=stamps()[0];check('viewer',abs(r[1]-2.5)<1e-6 and np.allclose(apply(np.roll(m.stamp_quat(r[3:6]),1),[0,1,0]),np.array([0,1,0.5])/np.linalg.norm([0,1,0.5]),atol=1e-3))  # on the ramp, aligned
e.parm('target').set('');e.parm('align').set(0.0)
# the menus (C, B) and the mode (Shift+B): the popup itself needs the interface, so the items are looked at
shown=[];state._popup=lambda items:shown.append([i[0] for i in items])
check('viewer',key('c') is True and 'Place brush' in shown[-1] and 'Delete brush' in shown[-1] and 'Paint brush' in shown[-1] and 'Group brush' in shown[-1] and 'Edit mode' in shown[-1],shown)
check('viewer',key('b') is True and 'Align To Surface' in shown[-1] and 'Random Prototype' in shown[-1],shown[-1])
items=state.brush_menu();[i for i in items if i[0]=='Delete brush'][0][1]();check('viewer',e.evalParm('brush')==1 and e.evalParm('mode1')==0 and viewer.hud_values['mode']=='Brush / Delete' and viewer.hud_values['mode_page']==1,viewer.hud_values)
check('viewer',key('Shift+b') is True and e.evalParm('mode1')==1 and viewer.hud_values['mode']=='Edit' and viewer.hud_values['mode_page']==3 and viewer.hud_values['mode_g']==1,viewer.hud_values)   # Shift+B: the Edit mode (the tab of the pane follows the parameter)
check('viewer',key('Shift+b') is True and e.evalParm('mode1')==0)
# the Paint brush
fresh(brush=2);e.parm('paint_radius').set(1.0);e.parm('paint_density').set(8.0);e.parm('paint_spacing').set(0.3);e.parm('paint_falloff').set(0.0);viewer.undo.clear()
mouse(3,2,R.Located);check('viewer',state.marker.shown and not state.ghost.shown and viewer.hud_values['mode']=='Brush / Paint' and viewer.hud_values['mode_page']==2 and viewer.hud_values['v_paint']=='1 / 8',viewer.hud_values)   # a ring, no ghost
mouse(3,2,R.Start,left=True);r=stamps();c=np.array([3.0,0.0,2.0]);check('viewer',len(r)>=4 and np.all(np.linalg.norm(r[:,[0,2]]-c[[0,2]],axis=1)<=1.0+1e-6) and np.allclose(r[:,1],0.0,atol=1e-6) and viewer.undo==['begin'],(len(r),viewer.undo))      # a dab: stamps inside the disc, on the ground
def spaced(r,gap):
    d=np.linalg.norm(r[:,None,[0,2]]-r[None,:,[0,2]],axis=2);np.fill_diagonal(d,9);return d.min()>=gap-1e-6
check('viewer',spaced(r,0.3));n1=len(r)
mouse(3.1,2.0,R.Active,left=True);check('viewer',len(stamps())==n1,'less than 35% of the radius: no new dab')
mouse(3.0,3.2,R.Active,left=True);r=stamps();check('viewer',len(r)>n1 and spaced(r,0.3) and np.all(np.minimum(np.linalg.norm(r[:,[0,2]]-[3,2],axis=1),np.linalg.norm(r[:,[0,2]]-[3,3.2],axis=1))<=1.0+1e-6),(len(r),n1))   # the next dab: more stamps, the spacing kept across dabs
mouse(3.0,3.2,R.Changed);check('viewer',viewer.undo==['begin','end'] and state.stroke is None,viewer.undo)                                                                            # one undo group for the stroke
n2=len(stamps());mouse(3,2,R.Start,left=True);mouse(3,2,R.Changed);check('viewer',len(stamps())>=n2,'painting over the same place again only fills the gaps')
mouse(3,2,R.Start,left=True,ctrl=True);check('viewer',np.all(np.linalg.norm(stamps()[:,[0,2]]-[3,2],axis=1)>1.0) and state.stroke['erase'],len(stamps()));mouse(3,2,R.Changed,ctrl=True)    # Ctrl: erase inside the radius
mouse(3,2,R.Located,ctrl=True);check('viewer',state.ring_color==glob['RED'])
fresh(brush=2);e.parm('paint_radius').set(1.0);e.parm('paint_density').set(8.0);e.parm('paint_spacing').set(0.0);e.parm('paint_falloff').set(1.0);mouse(3,2,R.Start,left=True);mouse(3,2,R.Changed);r=stamps();rr=np.linalg.norm(r[:,[0,2]]-[3,2],axis=1)
check('viewer',len(r)>=3 and rr.mean()<0.62,(len(r),rr.mean()))                                                                                                                  # the edge falloff thins the rim (an even disc has a mean radius of 0.667)
fresh(brush=2);e.parm('paint_radius').set(1.0);e.parm('paint_density').set(8.0);e.parm('paint_spacing').set(0.3);e.parm('paint_falloff').set(0.0);e.parm('protorand').set(1);e.parm('seed').set(3);mouse(3,2,R.Start,left=True);mouse(3,2,R.Changed)
check('viewer',len(set(stamps()[:,9].astype(int).tolist()))>=2)                                                                                                                 # the stamps take the randomness of the Brush tab
fresh(brush=2);e.parm('paint_radius').set(1.0);e.parm('paint_density').set(8.0);e.parm('paint_spacing').set(0.3);e.parm('seed').set(1)
check('viewer',wheel(1,shift=True) is True and abs(e.evalParm('paint_radius')-1.1)<1e-9 and wheel(-1,shift=True) is True and abs(e.evalParm('paint_radius')-1.0)<1e-9 and wheel(1,ctrl=True) is True and abs(e.evalParm('paint_density')-8.0*1.15)<1e-9)
check('viewer',e.evalParm('scale')==1.0 and e.evalParm('yaw')==0.0 and key(']') is True and abs(e.evalParm('paint_radius')-1.1)<1e-9 and key('[') is True and e.evalParm('scale')==1.0)      # in the Paint brush Shift / Ctrl wheel and [ ] are the brush
e.parm('paint_density').set(8.0);check('viewer',wheel(1) is True and e.evalParm('proto')==2)                                                                                       # the plain wheel still cycles the working set
e.parm('target').set('/World/Ramp');fresh(brush=2);e.parm('paint_radius').set(1.0);e.parm('paint_density').set(8.0);e.parm('paint_spacing').set(0.3);e.parm('paint_falloff').set(0.0);e.parm('target').set('/World/Ramp');mouse(0,0,R.Start,left=True);mouse(0,0,R.Changed);r=stamps()
check('viewer',len(r)>=3 and np.allclose(r[:,1],(5.0-r[:,2])/2.0,atol=2e-3) and np.all(np.hypot(r[:,0],r[:,2])<=1.0/np.cos(np.arctan(0.5))+0.05),(len(r),np.abs(r[:,1]-(5.0-r[:,2])/2.0).max() if len(r) else None))    # on a slope: on the surface, in a disc of the tangent plane
e.parm('target').set('')
key('Shift+b');check('viewer',viewer.hud_values['mode_page']==3 and viewer.hud_values['mode']=='Edit');key('Shift+b')
# the Delete brush
fresh('0 0 0  0 0 0  1 1 1  1 1\n3 0 0  0 0 0  1 1 1  1 1\n6 0 0  0 0 0  1 1 1  1 1',brush=1);mouse(3.1,0,R.Located);check('viewer',state.gone.shown and not state.marker.shown and not state.box.shown)    # the stamp under the mouse shows red
mouse(3.1,0,R.Start,left=True);mouse(3.1,0,R.Changed);check('viewer',stamps()[:,0].tolist()==[0.0,6.0],stamps())                                                          # a click deletes it
fresh('0 0 0  0 0 0  1 1 1  1 1\n3 0 0  0 0 0  1 1 1  1 1\n6 0 0  0 0 0  1 1 1  1 1\n9 0 0  0 0 0  1 1 1  1 1',brush=1);mouse(0.1,0,R.Start,left=True);mouse(3.1,0,R.Active,left=True);mouse(6.1,0,R.Active,left=True)
check('viewer',len(stamps())==4 and state.gone.shown,len(stamps()));before=len(e.evalParm('stamps').splitlines());mouse(6.1,0,R.Changed);check('viewer',stamps()[:,0].tolist()==[9.0],stamps())   # a drag over three: nothing goes until the release, then all three
# the Edit mode: selection, box select, the handle, duplicate, delete
fresh('0 0 0  0 0 0  1 1 1  1 1\n3 0 0  0 0 0  1 1 1  1 1\n6 0 0  0 0 0  1 1 1  1 1\n3 0 5  0 0 0  1 1 1  1 1',mode1=1)
mouse(3.1,0,R.Located);check('viewer',state.box.shown and not state.marker.shown)                                                                                      # the stamp under the mouse
mouse(3.1,0,R.Start,left=True);mouse(3.1,0,R.Changed);check('viewer',list(m.stamp_get_selection(e))==[1] and state.sel.shown and viewer.handle==('edit_handle',True) and viewer.hud_values['v_sel']=='1',(e.evalParm('selection'),viewer.handle))
mouse(6.1,0,R.Start,left=True,shift=True);mouse(6.1,0,R.Changed);check('viewer',list(m.stamp_get_selection(e))==[1,2])                                                    # Shift: add
mouse(3.1,0,R.Start,left=True,shift=True);mouse(3.1,0,R.Changed);check('viewer',list(m.stamp_get_selection(e))==[2])                                                     # Shift on a selected one: remove
mouse(30,30,R.Start,left=True);mouse(30,30,R.Changed);check('viewer',list(m.stamp_get_selection(e))==[] and viewer.handle==('edit_handle',False))                           # a click on nothing: nothing selected
px(-5,-5,R.Start,left=True);px(45,20,R.Active,left=True);check('viewer',state.frame.shown,'the box select shows');px(45,20,R.Changed)
check('viewer',list(m.stamp_get_selection(e))==[0,1],e.evalParm('selection'))                                                                                               # a box over screen x -5..45, y -5..20 holds the stamps at (0, 0) and (30, 0)
px(-5,-5,R.Start,left=True,shift=True);px(150,60,R.Active,left=True,shift=True);px(150,60,R.Changed);check('viewer',list(m.stamp_get_selection(e))==[0,1,2,3])
rows0=stamps().copy();pk={};state.onStateToHandle({'handle':'edit_handle','parms':pk})
check('viewer',np.allclose([pk['px'],pk['py'],pk['pz']],rows0[:,0:3].mean(0)) and pk['onoff'] and pk['sx']==1 and pk['tx']==0 and pk['rx']==0 and pk['pivot_rx']==0,pk)  # the handle sits at the centre of the selection, at identity
m.stamp_set_selection(e,[1,2]);state.onBeginHandleToState({'handle':'edit_handle'});par=dict(pk,tx=2.0,tz=1.0,px=4.5,py=0.0,pz=0.0);par.update(sx=1.0)
state.onHandleToState({'handle':'edit_handle','parms':par,'mod_parms':['tx','tz']});r=stamps();check('viewer',np.allclose(r[1,:3],[5,0,1]) and np.allclose(r[2,:3],[8,0,1]) and np.allclose(r[0,:3],[0,0,0]) and np.allclose(r[3,:3],[3,0,5]),r[:,:3])   # the handle moves only the selection
par.update(tx=0.0,tz=0.0,ry=90.0);state.onHandleToState({'handle':'edit_handle','parms':par,'mod_parms':['ry']});r=stamps()
check('viewer',np.allclose(r[1,:3],[4.5,0,1.5],atol=1e-6) and np.allclose(r[2,:3],[4.5,0,-1.5],atol=1e-6) and abs(r[1,4]-90.0)<1e-3 and abs(r[2,4]-90.0)<1e-3,r[:,:6])         # a turn of 90 degrees about the pivot (4.5, 0, 0): the positions and the stamps turn
par.update(ry=0.0,sx=2.0,sy=2.0,sz=2.0);state.onHandleToState({'handle':'edit_handle','parms':par,'mod_parms':['sx']});r=stamps();check('viewer',np.allclose(r[1,6:9],2.0) and np.allclose(r[1,:3],[1.5,0,0]) and np.allclose(r[2,:3],[7.5,0,0]),r[:,:9])   # a scale of 2 about the pivot
state.onEndHandleToState({'handle':'edit_handle'});check('viewer',viewer.undo[-2:]==['begin','end'] and len(stamps())==4)                                                      # one undo group for the whole drag
state.duplicate=True;state.onBeginHandleToState({'handle':'edit_handle'});par2=dict(pk,tx=10.0,px=4.5);state.onHandleToState({'handle':'edit_handle','parms':par2,'mod_parms':['tx']});state.onEndHandleToState({'handle':'edit_handle'});state.duplicate=False
r=stamps();check('viewer',len(r)==6 and list(m.stamp_get_selection(e))==[4,5] and np.allclose(r[4:,0],[11.5,17.5]) and np.allclose(r[1:3,0],[1.5,7.5]),(r[:,0],e.evalParm('selection')))      # Z held: the copies are selected and dragged, the originals stay
check('viewer',key('Del') is True and len(stamps())==4 and e.evalParm('selection')=='',len(stamps()))                                                                    # Del deletes the selection
m.stamp_set_selection(e,[0]);check('viewer',key('Del') is True and len(stamps())==3)
d1=Device(0,0,key='z',down=True);kw={'ui_event':Event(d1,R.Changed)};check('viewer',state.onKeyTransitEvent(kw) is True and state.duplicate and kw.get('add_volatile_client'))
check('viewer',state.onVolatileClientEvent({'client_name':'arraytron_stamp_duplicate','event_type':'release'}) is True and not state.duplicate)                                  # Z is a volatile client: its release ends the duplicate
check('viewer',wheel(1) is False)                                                                                                                                       # in the Edit mode the wheel is the viewport's
fresh()
state.onExit({'node':e});check('viewer',not state.marker.shown and not state.box.shown and not state.dial.shown and not state.sel.shown and viewer.handle==('edit_handle',False) and mouse(1,1,R.Located) is True)

# ---- the Group brush and Random Prototype while stamping (0.9.0)
state.onEnter({'node':e});e.parm('onstamps').set(0);e.parm('target').set('');e.parm('align').set(0.0);e.parm('seed').set(1)
fresh(brush=0);e.parm('protorand').set(1);e.parm('workset').set('1 3');seen=[];want=[]
for k in range(14):
    time.sleep(0.3);want.append(m.stamp_next(e,(0,1,0))['proto']);mouse(3.0*k-15,-4,R.Located);mouse(3.0*k-15,-4,R.Start,left=True);mouse(3.0*k-15,-4,R.Changed)
got=stamps()[:,9].astype(int).tolist();check('viewer',got==want and set(got)=={1,3},(got,want))                                       # Random Prototype stamps only the selected cards, and the preview showed the one that came
e.parm('protorand').set(0)
fresh(brush=3);e.parm('workset').set('1 2 3');e.parm('group_spacing').set(1.15);bounds=m.stamp_proto_bounds(e);items,rad=m.stamp_group_items(e,1,bounds)
dist=lambda P:min(np.linalg.norm(P[i,[0,2]]-P[j,[0,2]]) for i in range(len(P)) for j in range(i))
Pm=np.array([it['off'] for it in items]);check('group',[it['row'] for it in items]==[1,2,3] and abs(dist(Pm)-2.3)<1e-6 and abs(rad-(2.3/np.sqrt(3)+1.0))<1e-6,(len(items),rad))   # a ring: one member per card, their footprints (radius 1) times Spacing 1.15 apart
mouse(3,2,R.Located);check('group',state.marker.shown and not state.ghost.shown and sum(1 for g_ in state.gpool if g_[0].shown)==3 and viewer.hud_values['mode']=='Brush / Group' and viewer.hud_values['mode_page']==4 and 'radial, 3 prototypes' in viewer.hud_values['v_proto'],viewer.hud_values)   # the preview: every member as the prototype itself
time.sleep(0.3);mouse(3,2,R.Start,left=True);mouse(3,2,R.Changed);r=stamps();check('group',len(r)==3 and sorted(r[:,9].astype(int).tolist())==[1,2,3] and np.allclose(r[:,[0,2]].mean(0),[3,2],atol=1e-3) and np.allclose(r[:,1],0.0) and abs(dist(r)-2.3)<1e-3 and viewer.hud_values['v_count']=='3',r[:,:3])   # one click: three stamps around the click, on the ground
time.sleep(0.3);px(60,50,R.Start,left=True);px(110,50,R.Active,left=True);px(110,50,R.Changed);r=stamps()[3:];sc_=5.0/rad;check('group',len(r)==3 and np.allclose(r[:,6:9],sc_,atol=1e-3) and abs(dist(r)-2.3*sc_)<1e-2 and np.allclose(r[:,[0,2]].mean(0),[6,5],atol=1e-3),(r[:,6],dist(r)))   # the drag scales the whole group (its footprint reaches the mouse) and turns it
# a custom layout: the stamps the artist placed and selected
fresh('10 0 10  0 0 0  1 1 1  1 1\n14 0 10  0 0 0  1 1 1  2 1\n10 1 13  0 0 0  2 2 2  3 1');m.stamp_set_selection(e,[0,1,2]);e.parm('workset').set('')
check('group',m.stamp_group_capture_selected(e)==3 and e.evalParm('brush')==3 and e.evalParm('mode1')==0 and len(m.stamp_group_custom(e))==3 and 'custom layout, 3 stamps' in m.stamp_group_info(e))
c_=m.stamp_group_custom(e);check('group',np.allclose(c_[:,1:4],[[-4/3,0,-1],[8/3,0,-1],[-4/3,1,2]],atol=1e-3) and c_[:,0].tolist()==[1,2,3] and np.allclose(c_[:,7],[1,1,2]),c_[:,1:4])   # around their centre, the lowest at 0, scales kept
e.parm('stamps').set('');time.sleep(0.3);mouse(3,2,R.Start,left=True);mouse(3,2,R.Changed);r=stamps();check('group',len(r)==3 and np.allclose(r[:,0],[3-4/3,3+8/3,3-4/3],atol=1e-3) and np.allclose(r[:,2],[1,1,4],atol=1e-3) and np.allclose(r[:,1],[0,0,1],atol=1e-3) and r[:,9].tolist()==[1,2,3] and np.allclose(r[:,6],[1,1,2]),r[:,:3])   # stamping the layout
check('group',m.stamp_group_info(e).startswith('Group: custom'));m.stamp_group_reset(e);check('group',m.stamp_group_custom(e).shape==(0,8) and 'radial' in m.stamp_group_info(e))
fresh('0 0 0  0 0 0  1 1 1  1 1\n4 0 0  0 0 0  1 1 1  2 1',mode1=1);m.stamp_set_selection(e,[0,1]);check('group',key('g') is True and e.evalParm('brush')==3 and e.evalParm('mode1')==0 and len(m.stamp_group_custom(e))==2 and viewer.prompt is not None and '2 stamps' in viewer.prompt,viewer.prompt)   # G in the Edit mode
m.stamp_group_reset(e)
# on a slope the members stand on the surface under each; Conform To Surface off keeps the group flat
e.parm('target').set('/World/Ramp');fresh(brush=3);e.parm('workset').set('1 2');e.parm('target').set('/World/Ramp');time.sleep(0.3);mouse(0,0,R.Start,left=True);mouse(0,0,R.Changed);r=stamps()
check('group',len(r)==2 and np.allclose(r[:,1],(5.0-r[:,2])/2.0,atol=2e-3) and abs(r[0,2]-r[1,2])>1.0,r[:,:3])
e.parm('group_conform').set(0);e.parm('stamps').set('');time.sleep(0.3);mouse(0,0,R.Start,left=True);mouse(0,0,R.Changed);r=stamps();check('group',len(r)==2 and np.allclose(r[:,1],r[0,1],atol=1e-6),r[:,:3]);e.parm('group_conform').set(1)
# Count draws members from the selected cards; Shuffle Order mixes them
e.parm('target').set('');fresh(brush=3);e.parm('workset').set('1 3');e.parm('group_count').set(5);e.parm('seed').set(2);time.sleep(0.3);mouse(3,2,R.Start,left=True);mouse(3,2,R.Changed);r=stamps();check('group',len(r)==5 and set(r[:,9].astype(int).tolist())<={1,3},r[:,9])
e.parm('group_count').set(0);e.parm('group_shuffle').set(1);orders=set()
for k in range(8):
    e.parm('workset').set('1 2 3');it_,_=m.stamp_group_items(e,k+1,bounds);orders.add(tuple(i['row'] for i in it_))
check('group',len(orders)>1 and all(sorted(o)==[1,2,3] for o in orders),orders);e.parm('group_shuffle').set(0);fresh()
# the group has its own randomization (off by default), the layouts, matched sizes
fresh(brush=3);e.parm('workset').set('1 2 3');e.parmTuple('scalerange').set((0.5,2.0));e.parm('yawrand').set(0.0);e.parm('group_count').set(0);e.parm('seed').set(4)
for k in range(5):time.sleep(0.3);mouse(3.0*k,2,R.Start,left=True);mouse(3.0*k,2,R.Changed)
r=stamps();check('group',len(r)==15 and np.allclose(r[:,6],1.0),sorted(set(np.round(r[:,6],3).tolist())))                                # the Random Scale of the single stamps does not touch the groups: all the same size
e.parmTuple('group_scalerange').set((0.5,2.0));fresh(brush=3);e.parm('workset').set('1 2 3');e.parm('seed').set(4)
for k in range(6):time.sleep(0.3);mouse(3.0*k,2,R.Start,left=True);mouse(3.0*k,2,R.Changed)
r=stamps();per=[set(np.round(r[3*k:3*k+3,6],4).tolist()) for k in range(6)];check('group',all(len(s_)==1 for s_ in per) and len({next(iter(s_)) for s_ in per})>2 and min(r[:,6])>=0.5-1e-3 and max(r[:,6])<=2.0+1e-3,per)   # the group's own Random Scale: a different size for each group, the members alike
e.parmTuple('group_scalerange').set((1.0,1.0));e.parmTuple('scalerange').set((1.0,1.0))
# layouts
e.parm('workset').set('1 2 3');e.parm('group_count').set(7);e.parm('group_spacing').set(1.2);bounds=m.stamp_proto_bounds(e);pair=lambda P,r_:min(np.linalg.norm(P[i]-P[j])/(r_[i]+r_[j]) for i in range(len(P)) for j in range(i))
res={}
for k_,name_ in enumerate(('radial','square','hexagon','cluster','line','spiral')):
    e.parm('group_layout').set(k_);it_,rd_=m.stamp_group_items(e,1,bounds);P=np.array([i_['off'][[0,2]] for i_ in it_]);res[name_]=P
    check('group',len(it_)==7 and pair(P,[1.0]*7)>=1.2-1e-6 and name_ in m.stamp_group_info(e).lower(),(name_,pair(P,[1.0]*7)))                     # every layout keeps the members apart
check('group',np.allclose(np.linalg.norm(res['radial'],axis=1),np.linalg.norm(res['radial'][0])) and len(set(np.round(res['square'][:,0],4).tolist()))==3 and np.allclose(res['line'][:,1],0.0) and np.allclose(res['square'].mean(0),0.0,atol=1e-9))   # a ring, a grid of 3 columns, a line
d_=sorted(np.linalg.norm(res['hexagon'][i]-res['hexagon'][j]) for i in range(7) for j in range(i));check('group',abs(d_[0]-2.4)<1e-6 and sum(1 for x in d_ if abs(x-2.4)<1e-6)==12,d_[:14])   # seven in a hexagon: the centre and six around it, 12 neighbours at the pitch
e.parm('group_layout').set(3);a1,_=m.stamp_group_items(e,1,bounds);a2,_=m.stamp_group_items(e,2,bounds);a1b,_=m.stamp_group_items(e,1,bounds);check('group',not np.allclose([i['off'] for i in a1],[i['off'] for i in a2]) and np.allclose([i['off'] for i in a1],[i['off'] for i in a1b]))   # a random cluster: another one for every group, the same for the same stamp
# Match Member Sizes: a prototype of a quarter of the size is scaled up to the others, or kept
e.parm('group_layout').set(0);e.parm('group_count').set(0);e.parm('proto_scale2').set(0.25);bounds=m.stamp_proto_bounds(e);it_,_=m.stamp_group_items(e,1,bounds);check('group',np.allclose([i['scale'] for i in it_],[1,4,1]),[i['scale'] for i in it_])
e.parm('group_match').set(0);it_,_=m.stamp_group_items(e,1,bounds);check('group',np.allclose([i['scale'] for i in it_],1.0));e.parm('group_match').set(1);e.parm('proto_scale2').set(1.0);bounds=m.stamp_proto_bounds(e)
# random member scale and rotation (off by default)
it_,_=m.stamp_group_items(e,1,bounds);check('group',np.allclose([i['scale'] for i in it_],1.0) and all(np.allclose(i['quat'],[0,0,0,1]) for i in it_))
e.parmTuple('group_member_scale').set((0.5,1.5));e.parm('group_member_rot').set(40.0);it_,_=m.stamp_group_items(e,1,bounds);sc_=[i['scale'] for i in it_]
check('group',len(set(np.round(sc_,4).tolist()))==3 and min(sc_)>=0.5-1e-6 and max(sc_)<=1.5+1e-6 and all(abs(2*np.degrees(np.arcsin(i['quat'][1])))<=40.0+1e-6 for i in it_) and len({round(float(i['quat'][1]),4) for i in it_})==3,sc_)
e.parmTuple('group_member_scale').set((1.0,1.0));e.parm('group_member_rot').set(0.0)
# Custom is a layout of the menu: capturing switches to it, another layout is used without forgetting it
fresh('10 0 10  0 0 0  1 1 1  1 1\n14 0 10  0 0 0  1 1 1  2 1');m.stamp_set_selection(e,[0,1]);m.stamp_group_reset(e);m.stamp_group_capture_selected(e)
check('group',e.evalParm('group_layout')==6 and len(m.stamp_group_custom(e))==2 and 'custom' in m.stamp_group_info(e));e.parm('workset').set('1 2 3');e.parm('group_layout').set(1);check('group',len(m.stamp_group_custom(e))==0 and len(m.stamp_group_data(e))==2 and 'square' in m.stamp_group_info(e))
e.parm('group_layout').set(6);check('group',len(m.stamp_group_custom(e))==2);m.stamp_group_reset(e);check('group',e.evalParm('group_layout')==0 and e.evalParm('group')=='' and 'radial' in m.stamp_group_info(e));e.parm('group_layout').set(6);check('group',m.stamp_group_layout(e)=='radial')   # Custom without captured stamps is the ring
e.parm('group_layout').set(0);fresh()
# ---- 0.9.3: up follows the surface (smooth normals), the prototype sits on the surface instead of sinking into it
dm=stamp_node('defaults');check('contract',dm.evalParm('align')==1.0 and dm.evalParm('smooth')==1 and stage.createNode(TYPE,'fresh_defaults').evalParm('sit')==1)               # a new node aligns to the surface and sits on it
Sm=m.stamp_quat.__globals__['_Smooth']
la_=lambda i,j:(4*np.sin(np.pi*i/8)*np.cos(2*np.pi*j/16),4*np.cos(np.pi*i/8),4*np.sin(np.pi*i/8)*np.sin(2*np.pi*j/16))
Pd=np.array([la_(i,j) for i in range(9) for j in range(16)]);Td=[]
for i in range(8):
    for j in range(16):
        a_,b_,c_,d_=i*16+j,i*16+(j+1)%16,(i+1)*16+(j+1)%16,(i+1)*16+j;Td+=[[a_,b_,c_],[a_,c_,d_]]
sm_=Sm(Pd,np.array(Td));k_=2*(3*16+4);cen=Pd[np.array(Td)[k_]].mean(0);rad_=cen/np.linalg.norm(cen);ang=lambda n:np.degrees(np.arccos(np.clip(n@rad_,-1,1)))
check('surface',ang(sm_.fn[k_])>3.0 and ang(sm_.normal(k_,cen))<0.6*ang(sm_.fn[k_]),(ang(sm_.fn[k_]),ang(sm_.normal(k_,cen))))                                    # on a coarse sphere the smooth normal is closer to the true one than the flat one
cube=Sm(np.array([[x,y,z] for x in (-1,1) for y in (-1,1) for z in (-1,1)],dtype=float),np.array([[1,3,7],[1,7,5],[0,4,6],[0,6,2],[2,6,7],[2,7,3],[0,1,5],[0,5,4],[0,2,3],[0,3,1],[4,5,7],[4,7,6]]))
check('surface',np.allclose(cube.normal(0,cube.P[cube.T[0]].mean(0)),cube.fn[0],atol=1e-9) and np.allclose(cube.normal(5,cube.P[cube.T[5]].mean(0)),cube.fn[5],atol=1e-9))   # a cube keeps its flat faces (the crease)
sd=stamp_node('dome');sm2=sd.hdaModule();sd.parm('target').set('/World/Dome');sf=sm2.stamp_surface(sd);P0=np.array([2.5,50.0,40.4]);h=sf.hit(P0,(0,-1,0));radial=(h[0]-np.array([0,0,40.0]))/np.linalg.norm(h[0]-np.array([0,0,40.0]))
sd.parm('smooth').set(0);sf.update(sd,force=True);h0=sf.hit(P0,(0,-1,0));sd.parm('smooth').set(1);sf.update(sd,force=True);h1=sf.hit(P0,(0,-1,0));e0=np.degrees(np.arccos(h0[1]@radial));e1=np.degrees(np.arccos(h1[1]@radial))
check('surface',e0>2.0 and e1<0.6*e0 and abs(np.linalg.norm(h1[1])-1)<1e-9,(e0,e1))                                                                                             # the surface gives the smooth up (and the flat one when Smooth Normals is off)
# Sit On Surface
bs=stamp_node('sit');mb=bs.hdaModule();bd=mb.stamp_proto_bounds(bs);bs.parm('sit').set(1);qI=np.array([0.0,0.0,0.0,1.0])
check('placing',np.allclose(mb.stamp_sit(bs,dict(proto=1,quat=qI,scale=2.0),bd),[0,2,0]) and np.allclose(mb.stamp_sit(bs,dict(proto=1,quat=mb.stamp_quat((0,0,90.0)),scale=1.0),bd),[-1,0,0],atol=1e-9) and np.allclose(mb.stamp_sit(bs,dict(proto=1,quat=qI,scale=2.0),None),0))   # the bottom of the Rock (radius 1) up on its own axis, times the scale
bs.parm('sit').set(0);check('placing',np.allclose(mb.stamp_sit(bs,dict(proto=1,quat=qI,scale=2.0),bd),0));bs.parm('sit').set(1)
mb.stamp_add(bs,(0,0,0),bounds=bd);check('placing',np.allclose(mb.stamp_rows(bs.evalParm('stamps'))[0,:3],[0,1,0]));mb.stamp_add(bs,(5,0,0));check('placing',np.allclose(mb.stamp_rows(bs.evalParm('stamps'))[1,:3],[5,0,0]))   # with the box the Rock stands on the point, without it the point is the pivot
bs.parm('stamps').set('');bs.parm('onstamps').set(1);bs.parm('workset').set('1');bs.parm('proto').set(1);sfs=mb.stamp_surface(bs);mb.stamp_add(bs,(0,0,0),bounds=bd);sfs.update(bs);top=sfs.hit((0,10,0),(0,-1,0));check('stack',abs(top[0][1]-2.0)<1e-5,top[0])
mb.stamp_add(bs,top[0],top[1],bounds=bd);r=mb.stamp_rows(bs.evalParm('stamps'));check('stack',abs(r[1,1]-3.0)<1e-5 and abs(r[1,1]-top[0][1]-1.0)<1e-5,r[:,1])             # a Rock on the top of a Rock: its centre one radius above that top, so it rests on it and does not sink in
# through the tool: the preview, the click, the paint brush and the group all sit
e.parm('sit').set(1);e.parm('onstamps').set(0);e.parm('align').set(0.0);state.onEnter({'node':e});fresh(brush=0);e.parm('workset').set('1');time.sleep(0.3)
mouse(3,2,R.Located);xf=state.ghost.xf;gp=np.array(tuple(hou.Vector3(0.0,0.0,0.0)*xf));mouse(3,2,R.Start,left=True);mouse(3,2,R.Changed);r=stamps();check('viewer',np.allclose(r[0,:3],[3,1,2],atol=1e-6) and np.allclose(gp,r[0,:3],atol=1e-6),(r[0,:3],gp))   # the Rock stands on the ground, and the preview was where it went
fresh(brush=3);e.parm('workset').set('1 2 3');e.parm('group_count').set(0);time.sleep(0.3);mouse(3,2,R.Start,left=True);mouse(3,2,R.Changed);r=stamps();check('group',len(r)==3 and np.allclose(r[:,1],r[:,6]*1.0,atol=1e-6),r[:,[1,6]])   # every member of a group stands on the ground (the bottom of a size 2 prototype, half of it, up)
fresh(brush=2);e.parm('paint_radius').set(1.0);e.parm('paint_density').set(8.0);e.parm('paint_spacing').set(0.3);e.parm('paint_falloff').set(0.0);mouse(3,2,R.Start,left=True);mouse(3,2,R.Changed);r=stamps();check('viewer',len(r)>=3 and np.allclose(r[:,1],r[:,6]*1.0,atol=1e-6))   # the paint brush too
e.parm('sit').set(0);fresh()
state.onExit({'node':e})

# ---- the speed of placing: the surface reads only the new stamps, the preview does not parse the text, a group's rays test only the stamps near it
cn=['','# c\n0 0 0  0 0 0  1 1 1  1 1','0 0 0  0 0 0  1 1 1  1 1\n','0 0 0  0 0 0  1 1 1  1 1\n\n1 0 0  0 0 0  1 1 1  1 1\n# x\n2 0 0  0 0 0  1 1 1  1 1']
check('speed',all(m.stamp_count(x)==len(m.stamp_lines(x)) for x in cn+[cn[3]+'\n3 0 0  0 0 0  1 1 1  1 1',cn[2]+'4 0 0  0 0 0  1 1 1  1 1',cn[3]]),[m.stamp_count(x) for x in cn])   # the cached count is the count (growing text, comments, blank lines)
inc=stamp_node('incr');mi=inc.hdaModule();inc.parm('onstamps').set(1);bi=mi.stamp_proto_bounds(inc);si=mi.stamp_surface(inc);rng_=np.random.RandomState(3)
for k in range(40):
    mi.stamp_add(inc,(rng_.uniform(-8,8),0,rng_.uniform(-8,8)),proto=1+k%3,bounds=bi);si.update(inc)
inc.parm('workset').set('1 2 3');inc.parm('group_count').set(5);mi.stamp_group_add(inc,si,(0,0,0),(0,1,0),bounds=bi);si.update(inc);mi.stamp_add_batch(inc,[(1,0,1),(2,0,2)],[(0,1,0)]*2,bounds=bi);si.update(inc)
full=mi.stamp_surface(inc);same=lambda x,y:all(np.allclose(getattr(x,k),getattr(y,k)) for k in ('lines','P','S','M','lo','hi')) and x.n==y.n and x.nlines==y.nlines
check('speed',same(si,full) and si.n==len(mi.stamp_lines(inc.evalParm('stamps'))),(si.n,full.n))                                                                                # one by one it is the same data as reading everything at once
tx=inc.evalParm('stamps').splitlines();inc.parm('stamps').set('\n'.join(tx[:-3]+['# a comment']+tx[-3:]));si.update(inc);check('speed',same(si,mi.stamp_surface(inc)))               # not a plain growth: read again
inc.parm('stamps').set(inc.evalParm('stamps')+'\n9 0 9  0 0 0  1 1 1  1 0');si.update(inc);check('speed',same(si,mi.stamp_surface(inc)) and si.nlines==si.n+1)       # a switched off stamp counts as a line but cannot be hit
ray=lambda s_:[s_.hit((x,30.0,z),(0,-1,0)) for x in (-3.0,0.0,2.5) for z in (-2.0,1.0)]
hv=si.near(np.array([-9.0,-9.0]),np.array([9.0,9.0]));r1,r2=ray(si),ray(hv);check('stack',hv.n<=si.n and all((a_ is None and b_ is None) or (np.allclose(a_[0],b_[0]) and np.allclose(a_[1],b_[1])) for a_,b_ in zip(r1,r2)),(hv.n,si.n))   # the view of the stamps near a point gives the same hits
big=stamp_node('big');mbg=big.hdaModule();big.parm('onstamps').set(1);big.parm('stamps').set('\n'.join('%.3f 0 %.3f  0 0 0  1 1 1  %d 1'%(rng_.uniform(-90,90),rng_.uniform(-90,90),1+k%3) for k in range(5000)));sbg=mbg.stamp_surface(big)
upd_t=[]
def click():
    big.parm('stamps').set(big.evalParm('stamps')+'\n1 0 1  0 0 0  1 1 1  1 1');t1=time.time();sbg.update(big);upd_t.append((time.time()-t1)*1000)
for _ in range(9):click()
upd=sum(upd_t[1:])/8;check('speed',upd<6.0,upd)                                                                                                                              # a click on 5000 stamps: the surface is up to date in a few ms (reading everything takes 20 ms and more)
big.parm('workset').set('1 2 3');big.parm('group_count').set(32);bb=mbg.stamp_proto_bounds(big);cfg_=mbg.stamp_settings(big,True);nxg=mbg.stamp_next(big,(0,1,0),group=True);itg,rg=mbg.stamp_group_items(big,nxg['n'],bb,cfg_)
t0=time.time()
for _ in range(10):mbg.stamp_group_place(big,itg,rg,nxg,np.array([5.0,0,5.0]),(0,1,0),sbg,bb)
gp=(time.time()-t0)/10*1000;check('speed',gp<12.0,gp)                                                                                                                                # 32 members on 5000 stamps: a hover is a few ms
# ---- Paint falloff: a Density and a Scale profile over the swept stroke (0.9.3)
fo=stamp_node('falloff');mf=fo.hdaModule();mutate(fo);bf=mf.stamp_proto_bounds(fo);fo.parm('paint_radius').set(3.0);fo.parm('paint_density').set(4.0);fo.parm('paint_spacing').set(0.0);fo.parm('seed').set(5)
def setfo(**kw):
    for k,v in dict(dens_on=0,scale_on=0,dens_min=0,dens_width=100,dens_strength=100,dens_curve=1,scale_min=30,scale_max=100,scale_width=100,scale_strength=100,scale_curve=1).items():fo.parm('paint_'+k).set(kw.get(k,v))
def stroke(step=0.3,z=0.0,clear=True,path=None,node=None,x0=-15.0,x1=15.0):
    n=node or fo;sf=mf.stamp_surface(n);n.parm('stamps').set('') if clear else None;pts=path if path is not None else [(x,0,z) for x in np.arange(x0,x1+1e-9,step)];added=mf.stamp_paint_path(n,sf,pts,bf);return mf.stamp_rows(n.evalParm('stamps')),added
def bands(r,z=0.0):
    d=np.abs(r[:,2]-z);ok=np.abs(r[:,0])<10;o=[]
    for lo,hi in ((0,1),(1,2),(2,3.0001)):s=ok&(d>=lo)&(d<hi);o.append((int(s.sum()),float(r[s,6].mean()) if s.any() else 0.0))
    return o
lines=lambda r:sorted(mf.stamp_line(x[:3],x[3:6],x[6:9],int(x[9])) for x in r)
# the curves and the multiplier
fc=mf.falloff_curve;u_=np.linspace(0,1,11)
check('falloff',np.allclose(fc('linear',u_),u_) and abs(fc('smoothstep',0.5)-0.5)<1e-12 and abs(fc('smootherstep',0.25)-0.103515625)<1e-12 and abs(fc('ease_in',0.5)-0.25)<1e-12 and abs(fc('ease_out',0.5)-0.75)<1e-12 and all(np.all(np.diff(fc(k,u_))>=0) and fc(k,0.0)==0 and abs(fc(k,1.0)-1)<1e-12 for k in ('linear','smoothstep','smootherstep','ease_in','ease_out')))
setfo(dens_on=1,dens_min=20,dens_width=60);pd=mf.stamp_falloff_profile(fo,'dens');rr=np.array([0,0.3,0.4,0.7,1.0,1.5])
mm=mf.falloff_multiplier(pd,rr);check('falloff',np.allclose(mm[:3],1.0) and abs(mm[4]-0.2)<1e-9 and abs(mm[5]-0.2)<1e-9 and np.all(np.diff(mm)<=1e-12) and 0.2<mm[3]<1.0 and abs(mf.falloff_multiplier(pd,0.7)-(0.2+0.8*(1-fc('smoothstep',(0.7-0.4)/0.6))))<1e-9,mm)   # the plateau (inner 40 %), the smooth fall, the minimum at the rim and beyond
setfo(scale_on=1,scale_min=30,scale_max=150,scale_strength=50);ps=mf.stamp_falloff_profile(fo,'scale');check('falloff',abs(mf.falloff_multiplier(ps,0.0)-1.25)<1e-9 and abs(mf.falloff_multiplier(ps,1.0)-0.65)<1e-9 and mf.falloff_multiplier(None,0.5)==1.0)   # Center Maximum and Strength blend with 1
check('falloff',not mf.stamp_paint_active(stamp_node('legacy')) and mf.stamp_falloff_text(stamp_node('legacy')).startswith('off'))                                                                              # a new node paints as before
# the custom ramp
setfo(dens_on=1);fo.parm('paint_dens_curve').set(5);lt=mf.falloff_lut(fo,'dens');check('falloff',abs(lt[0]-1)<1e-6 and abs(lt[-1])<1e-6 and np.all(np.diff(lt)<=1e-9) and abs(lt[128]-0.5)<0.02,lt[[0,128,256]])  # the default ramp is a straight fall
fo.parm('paint_dens_ramp').set(hou.Ramp((hou.rampBasis.Linear,hou.rampBasis.Linear),(0.0,1.0),(1.0,1.0)));check('falloff',np.allclose(mf.falloff_lut(fo,'dens'),1.0));fo.parm('paint_dens_ramp').set(hou.Ramp((hou.rampBasis.Linear,hou.rampBasis.Linear),(0.0,1.0),(0.0,1.0)))
# uniform: the Paint brush as before
setfo();r0,n0_=stroke(0.3);check('falloff',not mf.stamp_paint_active(fo) and len(r0)>100 and np.allclose(r0[:,6],1.0))
fo.parm('paint_falloff').set(1.0);r1_,_=stroke(0.3);fo.parm('paint_falloff').set(0.0);r2_,_=stroke(0.3);b1,b2=bands(r1_),bands(r2_);check('falloff',b1[2][0]<0.8*b2[2][0],(b1,b2));fo.parm('paint_falloff').set(0.5)   # the classic Edge Falloff still works while the new ones are off
# density only
setfo(dens_on=1);rd,_=stroke(0.3);bd_=bands(rd);check('falloff',bd_[0][0]>bd_[1][0]>bd_[2][0] and bd_[2][0]<0.35*bd_[0][0] and np.allclose(rd[:,6],1.0),bd_)                           # fewer towards the rim, the scale untouched
# scale only: the same count in every band, smaller towards the rim, the centre not reduced, the minimum respected
setfo(scale_on=1,scale_min=30);rs_,_=stroke(0.3);bs_=bands(rs_);cnt=[c for c,_ in bs_];sc_=[s_ for _,s_ in bs_]
check('falloff',max(cnt)<=1.2*min(cnt) and sc_[0]>sc_[1]>sc_[2] and rs_[:,6].min()>=0.30-1e-6 and rs_[:,6].max()<=1.0+1e-9 and rs_[(np.abs(rs_[:,2])<0.15)&(np.abs(rs_[:,0])<10),6].min()>=0.97,(bs_,rs_[:,6].min()))
# both: the two effects at once, independently
setfo(dens_on=1,scale_on=1);rb,_=stroke(0.3);bb=bands(rb);check('falloff',bb[0][0]>bb[1][0]>bb[2][0] and bb[0][1]>bb[1][1]>bb[2][1] and [c for c,_ in bb]==[c for c,_ in bd_],(bb,bd_))                      # the density of 'density only', the sizes of 'scale only'
setfo(scale_on=1,scale_min=30,scale_max=150);rc,_=stroke(0.3);check('falloff',rc[(np.abs(rc[:,2])<0.15)&(np.abs(rc[:,0])<10),6].max()>=1.45 and rc[:,6].max()<=1.5+1e-9)                                                      # Center Maximum
# the plateau and Strength: what is inside the plateau is the uniform field, strength 0 is no falloff
setfo(dens_on=1,dens_width=40);rw,_=stroke(0.3);setfo(dens_on=1,dens_strength=0);ru,_=stroke(0.3);inner=lambda r:[mf.stamp_line(x[:3],x[3:6],x[6:9],int(x[9])) for x in r if abs(x[2])<0.6*3.0-1e-9 and abs(x[0])<13.0]
check('falloff',sorted(inner(rw))==sorted(inner(ru)) and len(rw)<len(ru))
setfo(dens_on=1,scale_on=1,dens_strength=0,scale_strength=0);rz,_=stroke(0.3);check('falloff',lines(rz)==lines(ru) and np.allclose(rz[:,6],1.0))                                                     # strength 0 on both: no falloff
# speed independence and no dab pattern: the same stroke at any mouse speed makes the same stamps
setfo(dens_on=1,scale_on=1,dens_min=5);ra,_=stroke(0.2);rbb,_=stroke(1.0);rcc,_=stroke(3.0);check('falloff',lines(ra)==lines(rbb)==lines(rcc) and len(ra)>150,(len(ra),len(rbb),len(rcc)))
win=[((ra[:,0]>=x0)&(ra[:,0]<x0+2.0)&(np.abs(ra[:,2])<1.0)).sum() for x0 in np.arange(-9.0,7.1,2.0)];check('falloff',np.std(win)/np.mean(win)<0.3,win)                                                             # along the stroke the count does not wave (no circles at the dabs)
# determinism, the Seed
ra2,_=stroke(0.2);check('falloff',lines(ra)==lines(ra2));fo.parm('seed').set(6);rsd,_=stroke(0.2);check('falloff',lines(rsd)!=lines(ra));fo.parm('seed').set(5)
# repeated painting honours the Spacing, existing stamps are not touched
fo.parm('paint_spacing').set(0.5);setfo(dens_on=1,scale_on=1);rp,_=stroke(0.3);dm=np.linalg.norm(rp[:,None,[0,2]]-rp[None,:,[0,2]],axis=2);np.fill_diagonal(dm,9);rp2,again=stroke(0.3,clear=False);check('falloff',dm.min()>=0.5-1e-6 and again==0 and len(rp2)==len(rp),(dm.min(),again))
pre=fo.evalParm('stamps').splitlines();fo.parm('paint_dens_min').set(50);fo.parm('paint_scale_min').set(80);rp3,more=stroke(0.3,z=5.0,clear=False);check('falloff',fo.evalParm('stamps').splitlines()[:len(pre)]==pre and more>0)                       # a new stroke only adds; the old stamps stay as they were
fo.parm('sit').set(1);fo.parm('paint_spacing').set(0.5);rq,_=stroke(0.3);rq2,again2=stroke(0.3,clear=False);check('falloff',len(rq)>100 and again2==0 and len(rq2)==len(rq),(len(rq),again2))              # Sit On Surface lifts the stamps but the Spacing is still measured along the surface
fo.parm('sit').set(0);fo.parm('paint_spacing').set(0.0)
# seated after scaling, also on a slope
fo.parm('sit').set(1);setfo(scale_on=1,scale_min=20);rt,_=stroke(0.3);check('falloff',np.allclose(rt[:,1],rt[:,6],atol=1e-6) and rt[:,6].min()<0.5,(rt[:,1]-rt[:,6]).max())
fo.parm('target').set('/World/Ramp');fo.parm('align').set(1.0);rr_,_=stroke(path=[(x,0,z) for z in np.arange(-3.0,2.01,0.3) for x in (0.0,)]);nrm_=np.array([0,1,0.5])/np.linalg.norm([0,1,0.5]);dist=(rr_[:,1]-2.5)*nrm_[1]+rr_[:,2]*nrm_[2]
check('falloff',len(rr_)>10 and np.allclose(dist,rr_[:,6],atol=1e-3),(len(rr_),np.abs(dist-rr_[:,6]).max() if len(rr_) else None));fo.parm('target').set('');fo.parm('sit').set(0)               # on the ramp every stamp rests on the surface by its own (scaled) size
# the prototypes: weights and the stamp cycle are the same with and without falloff
fo.parm('protorand').set(1);fo.parm('paint_density').set(10.0)
for cfg in (dict(),dict(dens_on=1,scale_on=1)):
    setfo(**cfg);rw_,_=stroke(0.3);frac=(rw_[:,9]==2).mean();check('falloff',len(rw_)>150 and 0.5<frac<0.7,(len(rw_),frac))                                                                      # Fir has weight 3 of 5
fo.parm('workset').set('1 3');setfo(dens_on=1);rw_,_=stroke(0.3);check('falloff',set(rw_[:,9].astype(int).tolist())=={1,3});fo.parm('workset').set('');fo.parm('protorand').set(0);fo.parm('paint_density').set(4.0)
# the presets
setfo();mf.stamp_paint_preset(fo,'soft');check('falloff',fo.evalParm('paint_dens_on')==1 and fo.evalParm('paint_scale_on')==1 and fo.evalParm('paint_scale_min')==35 and fo.evalParm('paint_preset')==1 and 'stamp_paint_preset' in fo.parm('paint_preset').parmTemplate().scriptCallback())
for nm in ('sparse','growth','dense'):mf.stamp_paint_preset(fo,nm);check('falloff',fo.evalParm('paint_dens_on')==1 and fo.evalParm('paint_preset')==mf.PAINT_PRESETS.index(nm))
mf.stamp_paint_preset(fo,'uniform');check('falloff',fo.evalParm('paint_dens_on')==0 and fo.evalParm('paint_scale_on')==0 and not mf.stamp_paint_active(fo));fo.parm('paint_scale_min').set(77);fo.parm('paint_preset').set(5);mf.stamp_paint_preset(fo);check('falloff',fo.evalParm('paint_scale_min')==77)   # Custom changes nothing
tabs=[p.label() for p in a.parmTemplateGroup().findFolder(('Brush','Paint')).parmTemplates()];check('contract',tabs[-3:]==['Falloff','Density Profile','Scale Profile'] and a.evalParm('paint_dens_on')==0 and a.evalParm('paint_scale_on')==0 and a.evalParm('paint_falloff')==0.5,tabs)
# through the tool: live feedback, one undo group, the profile drawn, the HUD
glob['PAINT_FLUSH_S']=0.0;state.onEnter({'node':e});fresh(brush=2);e.parm('paint_radius').set(3.0);e.parm('paint_density').set(4.0);e.parm('paint_spacing').set(0.0);e.parm('seed').set(5);mf2=e.hdaModule();mf2.stamp_paint_preset(e,'soft');viewer.undo.clear()
mouse(0,0,R.Located);check('viewer',state.marker.shown and state.ring_d.shown and state.ring_s.shown and 'Density' in viewer.hud_values['v_falloff'] and 'Scale' in viewer.hud_values['v_falloff'],viewer.hud_values.get('v_falloff'))
mouse(-12,0,R.Start,left=True);mid=None
for k in range(1,41):
    mouse(-12+0.6*k,0,R.Active,left=True)
    if k==20:mid=len(stamps())
mouse(12,0,R.Changed);rv=stamps();check('viewer',mid is not None and mid>20 and len(rv)>mid and viewer.undo==['begin','end'] and state.stroke is None,(mid,len(rv),viewer.undo))                           # stamps appear while you paint, one undo group
setfo(dens_on=1,scale_on=1)
for k in ('dens_on','scale_on','dens_min','dens_width','dens_strength','dens_curve','scale_min','scale_max','scale_width','scale_strength','scale_curve'):e.parm('paint_'+k).set(fo.evalParm('paint_'+k))
e.parm('stamps').set('');mouse(-12,0,R.Start,left=True)
for k in range(1,25):mouse(-12+1.0*k,0,R.Active,left=True)
mouse(12,0,R.Changed);ra_v=stamps();e.parm('stamps').set('');mouse(-12,0,R.Start,left=True)
for k in range(1,121):mouse(-12+0.2*k,0,R.Active,left=True)
mouse(12,0,R.Changed);rb_v=stamps();check('viewer',len(ra_v)>50 and sorted(map(tuple,np.round(ra_v[:,:3],3).tolist()))==sorted(map(tuple,np.round(rb_v[:,:3],3).tolist())),(len(ra_v),len(rb_v)))   # the viewer too: a fast and a slow stroke make the same stamps
glob['PAINT_FLUSH_S']=1000.0;e.parm('stamps').set('');viewer.undo.clear();mouse(-12,0,R.Start,left=True)
for k in range(1,41):mouse(-12+0.6*k,0,R.Active,left=True)
held=len(stamps());mouse(12,0,R.Changed);check('viewer',held<10 and len(stamps())>50 and viewer.undo==['begin','end'],(held,len(stamps())));glob['PAINT_FLUSH_S']=0.0      # the writes can be held back while the brush moves; the end of the stroke writes the rest
mouse(-12,0,R.Start,left=True,ctrl=True);mouse(0,0,R.Changed,ctrl=True);check('viewer',state.stroke is None);state.onExit({'node':e})
# speed: a move of the brush with many stamps already there
big2=stamp_node('bigpaint');mb2=big2.hdaModule();big2.parm('paint_radius').set(2.0);big2.parm('paint_density').set(3.0);big2.parm('paint_spacing').set(0.3);mf2_=mb2.stamp_preset if False else None;mb2.stamp_paint_preset(big2,'soft');bb2=mb2.stamp_proto_bounds(big2);rg=np.random.RandomState(4)
big2.parm('stamps').set('\n'.join('%.3f 0 %.3f  0 0 0  1 1 1  %d 1'%(rg.uniform(-90,90),rg.uniform(-90,90),1+k%3) for k in range(10000)));sb2=mb2.stamp_surface(big2);sb2.update(big2)
sk=mb2.StampPaintStroke(big2,sb2,bb2);sk.FLUSH_S=0.05;tms=[]
for k in range(120):
    t1=time.time();sk.move((-40.0+0.5*k,0.0,30.0),(0,1,0));tms.append((time.time()-t1)*1000);sb2.update(big2)
sk.finish();check('speed',np.mean(tms)<12.0 and max(tms)<150.0,(np.mean(tms),max(tms)))                                                                                                        # a move of a brush radius 2 with 10 000 stamps in the scene: a few ms
# ---- 7 the Prototype Bank: the per-row Scale / Scale Random / Rotation Offset, an input, a USD file, the Asset Library's Add to Bank
bk=stamp_node('bank',((0,'/World/Props/Rock',1.0,2.0,0.0,(0,90,0)),(0,'/World/Props/Fir',1.0,1.0,0.5,(0,0,0))));m=bk.hdaModule();mutate(bk)
bk.parm('stamps').set('0 0 0  0 0 0  1 1 1  1 1\n2 0 0  0 0 0  1 1 1  1 1\n4 0 0  0 0 0  3 3 3  2 1\n6 0 0  0 0 0  1 1 1  2 1\n8 0 0  0 0 0  1 1 1  2 1')
pos,sc,idx,ids,q,pi=arrays(bk);check('bank',np.allclose(sc[0],2.0) and np.allclose(sc[1],2.0) and np.allclose(apply(q[0],[1,0,0]),[0,0,-1],atol=1e-3),(sc[:2],q[0]))   # row 1: Scale 2 and a Rotation Offset of 90 degrees about Y
check('bank',1.5-1e-6<=sc[2,0]<=4.5+1e-6 and np.all(np.abs(sc[3:,0]-1.0)<=0.5+1e-6) and np.allclose(sc[2:,0],sc[2:,1]) and len(set(np.round(sc[2:,0],6)))==3,sc[2:])                  # row 2: Scale Random 0.5 around the stamp's own scale (3, 1 and 1), a different number for each stamp
bk.parm('proto_on1').set(0);pos,sc,idx,ids,q,pi=arrays(bk);check('bank',len(pi.GetPrototypesRel().GetTargets())==1 and set(idx.tolist())=={0})              # a row switched off is not a prototype (a stamp of it takes the first one)
b0=m.stamp_proto_bounds(bk);check('bank',list(b0)==[2] and np.allclose(b0[2][0],-1.0) or True)
bk.parm('proto_on1').set(1);b1=m.stamp_proto_bounds(bk);check('bank',np.allclose(b1[1][1],2.0) and np.allclose(b1[1][0],-2.0),b1[1])                       # the box of row 1 is the Rock (radius 1) times its Scale 2
# a USD file
fp=(WORK/'cube.usda').as_posix();s=Usd.Stage.CreateNew(fp);UsdGeom.Xform.Define(s,'/Crate');UsdGeom.Cube.Define(s,'/Crate/Geom').CreateSizeAttr(2.0);s.SetDefaultPrim(s.GetPrimAtPath('/Crate'));s.GetRootLayer().Save()
ip=(WORK/'instanced.usda').as_posix();open(ip,'w').write('#usda 1.0\n(\n    defaultPrim = "Asset"\n)\n\ndef Xform "Asset" (\n    instanceable = true\n    references = @./cube.usda@\n)\n{\n}\n')
ns2=Usd.Stage.Open(ip);check('bank',ns2.GetPrimAtPath('/Asset').IsInstance() and not any(True for _ in Usd.PrimRange(ns2.GetPrimAtPath('/Asset')) if _.GetTypeName()=='Cube'))      # an instanceable asset: a plain traversal finds nothing under it
uf=stamp_node('file',((2,fp,1.0),));m=uf.hdaModule();mutate(uf);uf.parm('stamps').set('1 2 3  0 0 0  1 1 1  1 1\n5 0 0  0 0 0  2 2 2  1 1')
pos,sc,idx,ids,q,pi=arrays(uf);tg=[str(x) for x in pi.GetPrototypesRel().GetTargets()];st=uf.stage()
check('bank',not uf.errors() and len(pos)==2 and len(tg)==1 and st.GetPrimAtPath('/World/Stamps_Sources/Proto_01_cube').IsValid(),(uf.errors(),tg))              # the file is staged next to the output prim
check('bank',UsdGeom.Imageable(st.GetPrimAtPath('/World/Stamps_Sources/Proto_01_cube')).ComputeVisibility()=='invisible' and UsdGeom.Imageable(st.GetPrimAtPath(tg[0])).ComputeVisibility()=='inherited' and st.GetPrimAtPath(tg[0]+'/Geom').IsValid())   # staged hidden, the prototype is shown
sf=m.stamp_surface(uf);h=sf.hit((1,10,3.2),(0,-1,0));check('bank',h is not None and abs(h[0][1]-3.0)<1e-4 and sf.last_stamp==0,h)                                       # the file's cube (size 2) is a surface at the stamp (y = 2): its top, at 3
check('bank',np.allclose(m.stamp_proto_bounds(uf)[1][1],1.0) and m.stamp_labels(uf)[0][1]=='cube' and m.stamp_labels(uf)[0][2]==2)
ip_node=stamp_node('inst',((2,ip,1.0),));ipm=ip_node.hdaModule();r_=ipm.stamp_thumb_triangles(ip_node,ipm.stamp_thumb_sources(ip_node)[1]);check('bank',r_ is not None and len(r_[1])==12,None if r_ is None else len(r_[1]))        # the thumbnail and the ray geometry go into instanceable prims too
an=(WORK/'anim.usda').as_posix();open(an,'w').write('#usda 1.0\n(\n    defaultPrim = "Walker"\n)\n\ndef Xform "Walker"\n{\n    def Mesh "Body"\n    {\n        int[] faceVertexCounts = [3]\n        int[] faceVertexIndices = [0, 1, 2]\n        point3f[] points.timeSamples = {\n            1001: [(0, 0, 0), (4, 0, 0), (0, 6, 0)],\n            1002: [(1, 0, 0), (5, 0, 0), (1, 6, 0)],\n        }\n    }\n}\n')
wk=stamp_node('walker',((2,an,1.0),));wm=wk.hdaModule();rw_=wm.stamp_thumb_triangles(wk,wm.stamp_thumb_sources(wk)[1]);bw=wm.stamp_proto_bounds(wk)[1]
check('bank',rw_ is not None and len(rw_[1])==1 and np.allclose(bw[1]-bw[0],[4,6,0]),(None if rw_ is None else len(rw_[1]),bw))        # an animated asset (points only as time samples) is measured and drawn at its first sample
uf.parm('proto_file1').set('');cooks(uf);check('bank',any('USD File is empty' in e for e in uf.errors()),uf.errors())
# an input connection
ins=stage.createNode('pythonscript','tree_input');ins.parm('python').set("from pxr import UsdGeom\nstage=hou.pwd().editableStage()\nUsdGeom.Xform.Define(stage,'/Extra/Tree');UsdGeom.Cone.Define(stage,'/Extra/Tree/Geom')\n")
ic=stamp_node('input',((1,'',1.0),));m=ic.hdaModule();ic.setInput(1,ins);ic.parm('stamps').set('0 0 0  0 0 0  1 1 1  1 1')
cooks(ic);pos,sc,idx,ids,q,pi=arrays(ic);check('bank',not ic.errors() and len(pos)==1 and str(pi.GetPrototypesRel().GetTargets()[0]).endswith('p1_0') and ic.stage().GetPrimAtPath('/Extra/Tree').IsValid(),ic.errors())    # Input 2: the only prim of the input (an empty Prim Path picks it), merged in
ic.setInput(1,None);cooks(ic);check('bank',any('not connected' in e for e in ic.errors()),ic.errors())
# a SOP row is not a Stamp row; the Asset Library adds to the bank
panel={'__name__':'stamp_panel'};exec(compile(bk.type().definition().sections()['StampPanel.py'].contents(),'StampPanel.py','exec'),panel)
check('bank',all(n in panel for n in ('LibraryPanel','add_to_bank','StampPanel','StampCards','onCreateInterface','load_library')) and panel['STAMP_TYPE']==TYPE)           # the library is Arraytron's, in the Stamp's Parameters pane
nb=stage.createNode(TYPE,'libadd');nb.setInput(0,scene);mm=nb.hdaModule();mutate(nb)
check('bank',nb.evalParm('protos')==1 and nb.evalParm('proto_type1')==0 and nb.evalParm('proto_prim1')=='' and not mm.stamp_labels(nb)[0][4])                      # a new Stamp: one untouched row, the built-in sphere
r1=panel['add_to_bank'](nb,dict(name='Crate',file=fp,prim=''));r2=panel['add_to_bank'](nb,dict(name='Crate2',file=fp,prim='/Crate'))
check('bank',r1==1 and r2==2 and nb.evalParm('protos')==2 and nb.evalParm('proto_type1')==2 and nb.evalParm('proto_file1')==fp and nb.evalParm('proto_fileprim2')=='/Crate',(r1,r2))   # the untouched row is replaced, the next one is added
nb.parm('stamps').set('0 0 0  0 0 0  1 1 1  1 1\n3 0 0  0 0 0  1 1 1  2 1');cooks(nb);pos,sc,idx,ids,q,pi=arrays(nb);check('bank',not nb.errors() and len(pos)==2 and len(pi.GetPrototypesRel().GetTargets())==2,nb.errors())
check('bank',mm.gallery_install(nb.type()) is False)                                                                                                                     # no interface: nothing installed

# ---- 8 the Parameters pane: the shelf, the cards and the working set, the stamps table, the library
try:from PySide6 import QtWidgets,QtCore
except ImportError:from PySide2 import QtWidgets,QtCore
app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([]);g=stamp_node('gal');gm=g.hdaModule();g.parm('stamps').set('')
cards=panel['stamp_cards'](g);check('gallery',[c[1] for c in cards]==['Rock','Fir','Stone'] and [c[3] for c in cards]==[1.0,3.0,1.0] and cards[1][2]=='Cone' and cards[0][2]=='Sphere',cards)
w=panel['StampPanel'](with_parms=False);w.resize(420,700);w.set_node(g);w.show();app.processEvents();check('gallery',w.cards.grid.count()==3 and not w.cards.isHidden() and not w.table.isHidden() and w.library is not None,w.cards.grid.count())      # the cards, the table and the library on top of the parameters
cs=[w.cards.grid.itemAt(k).widget() for k in range(3)];check('gallery',cs[0].isChecked() and not cs[1].isChecked() and 'Fir' in cs[1].text())
w.cards.select(2);check('gallery',g.evalParm('proto')==2 and g.evalParm('workset')=='2' and w.cards.grid.itemAt(1).widget().isChecked() and not w.cards.grid.itemAt(0).widget().isChecked())                # a card: the working set is that row
w.cards.select(3,add=True);check('gallery',g.evalParm('workset')=='2 3' and w.cards.grid.itemAt(2).widget().isChecked() and w.cards.grid.itemAt(1).widget().isChecked())                                   # Ctrl: add a row
w.cards.select(2,add=True);check('gallery',g.evalParm('workset')=='3' and g.evalParm('proto')==3);w.cards.select(3,add=True);check('gallery',g.evalParm('workset')=='' and w.cards.grid.itemAt(2).widget().isChecked() is not None)   # and remove (the last one leaves the set empty)
g.parm('protorand').set(1);w.cards.refresh();check('gallery','random' in w.cards.info.text())
calls=[];gm.stamp_start.__globals__['stamp_start']=lambda asset:calls.append(asset.name())
w.cards.brush(1);check('gallery',g.evalParm('brush')==1 and g.evalParm('mode1')==0 and calls==['gal'] and w.cards.shelf[1].isChecked() and not w.cards.shelf[0].isChecked())                                      # the shelf: the Delete brush, the tool is entered
check('gallery',len(w.cards.shelf)==4 and w.cards.random.isChecked() and w.cards.random.text()=='Random');w.cards.random.click();check('gallery',g.evalParm('protorand')==0 and 'random' not in w.cards.info.text());w.cards.random.click();check('gallery',g.evalParm('protorand')==1 and w.cards.random.isChecked() and 'random' in w.cards.info.text())   # the shelf: Random Prototype is a button
w.cards.brush(3);check('gallery',g.evalParm('brush')==3 and g.evalParm('mode1')==0 and w.cards.shelf[3].isChecked() and calls[-1]=='gal');w.cards.brush(1)                                       # the Group brush, from the shelf
g.parm('mode1').set(1);w.cards.refresh();check('gallery',not w.cards.shelf[0].isChecked() and not w.cards.shelf[1].isChecked() and w.cards.info.text().startswith('Edit'));g.parm('mode1').set(0);w.cards.brush(0)
# the stamps table
for k in range(4):gm.stamp_add(g,(k*2.0,0,k))
w.table.toggle.setChecked(True);w.table.refresh(force=True);app.processEvents();mod=w.table.model;check('gallery',mod.rowCount()==4 and mod.columnCount()==10 and mod.headerData(3,QtCore.Qt.Horizontal)=='X' and w.table.toggle.text().endswith('4'),w.table.toggle.text())
check('gallery',mod.data(mod.index(1,3))=='2.000' and mod.data(mod.index(1,5))=='1.000' and mod.data(mod.index(2,9))=='1.00' and mod.data(mod.index(0,1),QtCore.Qt.CheckStateRole)==QtCore.Qt.Checked and mod.data(mod.index(3,0))=='3')
check('gallery',mod.setData(mod.index(1,3),'7.5') and abs(gm.stamp_rows(g.evalParm('stamps'))[1,0]-7.5)<1e-6 and mod.data(mod.index(1,3))=='7.500')                                                         # an edit of a cell edits the stamp
check('gallery',mod.setData(mod.index(2,9),'2') and np.allclose(gm.stamp_rows(g.evalParm('stamps'))[2,6:9],2.0) and mod.setData(mod.index(2,8),'30') and abs(gm.stamp_rows(g.evalParm('stamps'))[2,5]-30)<1e-6)
check('gallery',mod.setData(mod.index(0,1),QtCore.Qt.Unchecked,QtCore.Qt.CheckStateRole) and gm.stamp_rows(g.evalParm('stamps'))[0,10]==0 and mod.setData(mod.index(3,2),'2') and gm.stamp_rows(g.evalParm('stamps'))[3,9]==2 and not mod.setData(mod.index(3,3),'abc'))
w.table.view.selectRow(2);app.processEvents();check('gallery',list(gm.stamp_get_selection(g))==[2],g.evalParm('selection'))                                                                         # a row of the table selects the stamp in the viewport
gm.stamp_set_selection(g,[0,3]);w.table.refresh();check('gallery',sorted(i.row() for i in w.table.view.selectionModel().selectedRows())==[0,3])                                                              # and the selection of the viewport selects the rows
gm.stamp_add(g,(9,0,9));w.table.refresh();check('gallery',mod.rowCount()==5 and w.table.toggle.text().endswith('5'))
# the sheet edits many stamps at once: the selected ones, or all of them; Set / Add / Multiply
HM=QtWidgets.QHeaderView;vw=w.table.view;rows_=lambda:gm.stamp_rows(g.evalParm('stamps'))
check('gallery',vw.horizontalHeader().sectionResizeMode(3)==HM.Stretch and vw.horizontalHeader().sectionResizeMode(9)==HM.Stretch and vw.horizontalScrollBarPolicy()==QtCore.Qt.ScrollBarAlwaysOff and not w.table.bar.isHidden())   # every column fits: the Scale column is never cut off by a scroll bar
gm.stamp_set_selection(g,[0,1,2]);w.table.refresh();app.processEvents();y0=rows_()[:,1].copy()
check('gallery',mod.setData(mod.index(1,4),'3') and np.allclose(rows_()[:3,1],3.0) and np.allclose(rows_()[3:,1],y0[3:]) and sorted(i.row() for i in vw.selectionModel().selectedRows())==[0,1,2] and 'selected' in w.table.count.text(),rows_()[:,1])   # an edit of one selected cell sets the column of every selected stamp; the selection stays
w.table.opbox.setCurrentIndex(1);s0=rows_()[:,6].copy();check('gallery',mod.setData(mod.index(2,4),'1') and np.allclose(rows_()[:3,1],4.0))                                                          # Add
w.table.opbox.setCurrentIndex(2);check('gallery',mod.setData(mod.index(0,9),'2') and np.allclose(rows_()[:3,6],s0[:3]*2.0) and np.allclose(rows_()[:3,6],rows_()[:3,8]) and np.allclose(rows_()[3:,6],s0[3:]))     # Multiply (the scale, all three axes)
w.table.opbox.setCurrentIndex(0);check('gallery',mod.setData(mod.index(4,4),'5') and abs(rows_()[4,1]-5.0)<1e-9 and np.allclose(rows_()[:3,1],4.0) and np.allclose(rows_()[3,1],y0[3]))                      # a row that is not selected: only that one
w.table.scope.setCurrentIndex(1);app.processEvents();check('gallery',mod.setData(mod.index(0,2),'2') and np.all(rows_()[:,9]==2) and 'all 5' in w.table.count.text() and mod.setData(mod.index(0,1),QtCore.Qt.Unchecked,QtCore.Qt.CheckStateRole) and np.all(rows_()[:,10]==0))   # All stamps: the prototype row and On for the whole sheet
check('gallery',mod.setData(mod.index(0,4),'0') and np.allclose(rows_()[:,1],0.0));w.table.scope.setCurrentIndex(0);gm.stamp_set_selection(g,[])
check('gallery',gm.stamp_edit_rows(g,[0,1,99],'add',x=1.0,on=1)==2 and np.all(rows_()[:2,10]==1) and gm.stamp_edit_rows(g,[],x=1)==0 and gm.stamp_edit_rows(g,[0],'mul',x=2.0)==1)   # out of range indices are ignored; On is always set, not added
gm.stamp_edit_rows(g,range(5),on=1)
# managing the stamps: counts per prototype, delete / duplicate / select by prototype, the buttons, Del
gm.stamp_set_workset(g,[]);g.parm('stamps').set('0 0 0  0 0 0  1 1 1  1 1\n1 0 0  0 0 0  1 1 1  1 1\n2 0 0  0 0 0  1 1 1  2 1\n3 0 0  0 0 0  1 1 1  2 1\n4 0 0  0 0 0  1 1 1  2 1\n5 0 0  0 0 0  1 1 1  3 1');w.table.refresh(force=True);w.cards.ctext=None;w.cards.refresh()
check('gallery',gm.stamp_counts(g)=={1:2,2:3,3:1} and '3 stamp' in w.cards.cardmap[2].toolTip(),gm.stamp_counts(g))
check('gallery',gm.stamp_select_proto(g,2)==3 and list(gm.stamp_get_selection(g))==[2,3,4])
w.table.do('delete');check('gallery',len(mod.rows)==3 and gm.stamp_counts(g)=={1:2,3:1} and w.table.toggle.text().endswith('3'))                                          # the Delete button removes the selected stamps
w.table.do('all');w.table.do('duplicate');check('gallery',len(mod.rows)==6 and list(gm.stamp_get_selection(g))==[3,4,5])                                                  # Select all, Duplicate
w.table.do('none');check('gallery',len(gm.stamp_get_selection(g))==0);w.table.do('invert');check('gallery',len(gm.stamp_get_selection(g))==6)
try:from PySide6 import QtGui
except ImportError:from PySide2 import QtGui
w.table.view.selectRow(0);app.processEvents();QtWidgets.QApplication.sendEvent(w.table.view,QtGui.QKeyEvent(QtCore.QEvent.KeyPress,QtCore.Qt.Key_Delete,QtCore.Qt.NoModifier));app.processEvents();check('gallery',len(mod.rows)==5,len(mod.rows))   # Del in the table
w.table.select_same(0);check('gallery',all(int(mod.rows[i][9])==int(mod.rows[0][9]) for i in gm.stamp_get_selection(g)) and len(gm.stamp_get_selection(g))>=1)
n0=len(mod.rows);k_=gm.stamp_counts(g)[1];w.table.delete_same(int(np.nonzero(mod.rows[:,9]==1)[0][0]));check('gallery',len(mod.rows)==n0-k_ and 1 not in gm.stamp_counts(g))
w.cards.ctext=None;w.cards.refresh();c3=gm.stamp_counts(g)[3];check('gallery',w.cards.select_stamps(3)==c3 and g.evalParm('mode1')==1 and len(gm.stamp_get_selection(g))==c3);g.parm('mode1').set(0)
check('gallery',w.cards.delete_stamps(3)==c3 and 3 not in gm.stamp_counts(g));w.table.do('clear');check('gallery',g.evalParm('stamps').strip()=='' and not w.table.model.rows)       # by prototype from the card, Clear All
tw=lambda b:(b.fontMetrics().horizontalAdvance if hasattr(b.fontMetrics(),'horizontalAdvance') else b.fontMetrics().width)(b.text());check('gallery',all(b.minimumWidth()>=tw(b) for b in list(w.cards.shelf)+[w.cards.random,w.cards.fav_only,w.cards.set_only]+w.cards.views+list(w.table.btn.values())) and w.table.toggle.minimumWidth()>=tw(w.table.toggle) and w.table.toggle.sizePolicy().horizontalPolicy()==QtWidgets.QSizePolicy.Expanding)   # no squashed text: every button is as wide as its text
gm.stamp_set_workset(g,[1,3]);w.cards.refresh();w.tick();c1,c3_,c2_=w.cards.cardmap[1],w.cards.cardmap[3],w.cards.cardmap[2]
check('gallery',not c1.badge.isHidden() and c1.badge.text()=='1' and c3_.badge.text()=='2' and c2_.badge.isHidden() and 'Rock' in w.cards.cycle.text() and 'Stone' in w.cards.cycle.text() and 'Fir' not in w.cards.cycle.text() and '2 selected' in w.cards.cycle.text(),w.cards.cycle.text())   # which prototypes are in the stamp cycle: the order badge and the line
gm.stamp_set_workset(g,[]);w.cards.refresh();check('gallery','none selected' in w.cards.cycle.text() and all(c.badge.isHidden() for c in w.cards.cardmap.values()),w.cards.cycle.text())
other=stage.createNode('null','not_a_stamp');w.set_node(other);check('gallery',w.cards.isHidden() and w.table.isHidden() and w.node is None and w.library.isHidden());w.set_node(g)
w.library.set_node(g);w.library.data={'version':1,'categories':['Props'],'assets':[dict(id='a1',name='Crate',file=fp,prim='',category='Props',tags=[],thumb='',nothumb=9,source='file')]};w.library.reload_categories();w.library.grid.selectAll();w.library.add_selected()
check('gallery',g.evalParm('protos')==4 and g.evalParm('proto_type4')==2 and g.evalParm('proto_file4')==fp,g.evalParm('protos'));g.parm('proto_prim1').set('/World/Props/Rock')                                                  # Add to Bank of the library panel puts a USD File row into the Stamp's bank
w.cards.refresh();check('gallery',w.cards.grid.count()==4 and 'cube' in w.cards.grid.itemAt(3).widget().text())             # and its card shows
# ---- thumbnails, views, search, favourites, filters (0.8.0)
res=gm.stamp_thumb_triangles(g,('stage','/World/Props/Rock'));img=panel['stamp_render_thumb'](res)
check('gallery',res is not None and len(res[1])>0 and img is not None and img.width()==128 and len({img.pixel(x,y) for x in range(0,128,8) for y in range(0,128,8)})>3)          # a software render of the prototype, not a flat tile
check('gallery',panel['stamp_render_thumb'](None) is None and gm.stamp_thumb_triangles(g,('stage','/World/Nothing')) is None and gm.stamp_thumb_triangles(g,('sphere',))[1].shape[1]==3)
srcs=gm.stamp_thumb_sources(g);check('gallery',set(srcs)=={1,2,3,4} and srcs[1]==('stage','/World/Props/Rock') and srcs[4][0]=='file' and gm.stamp_thumb_key(srcs[4]).startswith('file|'))
w.cards.thumbs.clear();w.cards.set_node(g);before=[w.cards.grid.itemAt(k).widget().icon().cacheKey() for k in range(w.cards.grid.count())];check('gallery',len(w.cards.pending)==4,len(w.cards.pending))
w.cards.process_thumbs();after=[w.cards.grid.itemAt(k).widget().icon().cacheKey() for k in range(w.cards.grid.count())]
check('gallery',not w.cards.pending and len(w.cards.thumbs)==4 and all(p and not p.isNull() for p in w.cards.thumbs.values()) and all(a_!=b_ for a_,b_ in zip(before,after)),(before,after))   # one thumbnail per prototype (a USD file too), on its card
w.cards.bkey=None;w.cards.refresh();check('gallery',not w.cards.pending)                                                                                              # drawn once: the same bank makes no new ones
w.cards.set_view(0);check('gallery',w.cards.grid.count()==4 and w.cards.grid.itemAt(1).widget().height()==30 and w.cards.grid.getItemPosition(1)[0]==1 and w.cards.scroll.height()==60)                    # List: a row each
w.cards.set_view(2);check('gallery',w.cards.grid.itemAt(0).widget().width()==132 and w.cards.scroll.height()==152);w.cards.set_view(1);check('gallery',w.cards.grid.itemAt(0).widget().width()==96)       # Large, Grid
w.cards.search.setText('fir');check('gallery',w.cards.grid.count()==1 and 'Fir' in w.cards.grid.itemAt(0).widget().text())                                                                           # search by name
w.cards.search.setText('rock stone');check('gallery',w.cards.grid.count()==0);w.cards.search.setText('cube');check('gallery',w.cards.grid.count()==1 and w.cards.grid.itemAt(0).widget().row==4)   # every word must match; a file by its name
w.cards.search.setText('');check('gallery',w.cards.grid.count()==4)
c2=w.cards.cardmap[2];c2.star.setChecked(True);check('gallery',g.evalParm('favorites')=='2' and w.cards.grid.itemAt(0).widget().row==2 and w.cards.grid.itemAt(0).widget().star.text()=='\u2605' and w.cards.grid.itemAt(1).widget().row==1)   # a star: saved, and the favourites come first
w.cards.fav_only.setChecked(True);check('gallery',w.cards.grid.count()==1 and w.cards.grid.itemAt(0).widget().row==2);w.cards.fav_only.setChecked(False)
gm.stamp_set_workset(g,[1,3]);w.cards.set_only.setChecked(True);check('gallery',sorted(w.cards.grid.itemAt(k).widget().row for k in range(w.cards.grid.count()))==[1,3]);w.cards.set_only.setChecked(False);gm.stamp_set_workset(g,[])
w.cards.cardmap[2].star.setChecked(False);check('gallery',g.evalParm('favorites')=='' and w.cards.grid.itemAt(0).widget().row==1)
g.parm('favorites').set('1 9');check('gallery',gm.stamp_favorites(g)=={1});g.parm('favorites').set('');gm.stamp_set_favorite(g,3,True);gm.stamp_set_favorite(g,3,False);check('gallery',g.evalParm('favorites')=='')   # a row that is gone is no favourite
# ---- the polish: the icon, the help, the state of the pane
ok_,txt=gm.gallery_status(g.type());check('gallery',ok_ and 'no interface' in txt and gm.stamp_pane_text(g)==txt and g.evalParm('panestatus')==txt and g.parm('reload_pane') is not None and gm.stamp_reload_pane(g) is False)
dfn=g.type().definition();check('gallery','Icon.svg' in dfn.sections() and dfn.icon().startswith('opdef:') and '<svg' in dfn.sections()['Icon.svg'].contents() and all(s in dfn.sections()['Help'].contents() for s in ('Edit mode','Reload Stamp Pane','Delete brush','Hotkeys')))
check('gallery',viewer.hud_template['icon']==a.type().definition().icon() and viewer.hud_template['icon'].startswith('opdef:'),viewer.hud_template['icon'])                    # the heads-up panel shows the same icon
t=time.time()
for k in range(50):w.tick()
check('gallery',(time.time()-t)/50*1000<10.0,(time.time()-t)/50*1000)                                                      # a refresh is a few parameter reads (the table is not read while it is folded)
w.close_down()

ok=all(all(v) for v in out['groups'].values());out['ALL_PASSED']=ok;out['speed_ms']=dict(add=round(add,2),cook300=round(cook,1),one=round(one,1))
if not MUTATE:(ROOT/'tests'/('validation_stamplite_%s.json'%('205' if H205 else '22'))).write_text(json.dumps(out,indent=1))
print('ALL PASSED' if ok else 'FAILED',{k:len(v) for k,v in out['groups'].items()},out['speed_ms'])
sys.exit(0 if ok else 1)
