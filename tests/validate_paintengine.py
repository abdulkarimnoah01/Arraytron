"""Paint Engine 2.0 in both HDAs: Arraytron v1.36.0 (arraytron::instancer, the procedural paint) and Arraytron Stamp 0.11.0 (the stamps), on BrushCore (src/brushcore.py).
  hython tests/validate_paintengine.py [v1.36.0]        (hython 22 or 20.5; build both HDAs first)
Groups: shared (both PythonModules embed the same BrushCore) | storage (Arraytron's p3 paint data, old texts) | stroke (Tests A-D and I on the real nodes: soft density edge, soft scale edge,
combined, speed, determinism, spacing, revisit) | instances (the brushes reach the PointInstancer: Scale Falloff and Grow / Shrink in the scales, Orient / Comb in the headings despite a random yaw,
Swap in the prototypes, Erase keeps the other ids, Relax / Push stay on the surface) | clone | stamp (the Stamp's sculpt brushes on the Stamps text: Erase switches off, ids stable, Relax, Scale with
Sit On Surface, Push, Replace by the working set, Orient, Cancel, Clone, Restore / Remove Erased) | viewer (both tools through a stand-in viewport: one write and one undo step per stroke, Esc cancels,
H cycles the HUD level and keeps it, 1-9 / C, F presets, the cursor with the falloff rings).
Env PAINTENGINE_MUTATE=fall|comb|erase_ids|stamp_erase|cancel|swap breaks a part; the suite must FAIL. Writes tests/validation_paintengine_<22|205>.json."""
import os, sys, json, time, types, tempfile
from pathlib import Path
import numpy as np
import hou
from pxr import UsdGeom
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
os.environ['ARRAYTRON_BRUSH_PREFS']=os.path.join(tempfile.mkdtemp(),'arraytron_brush_prefs.json')
VID=versions.resolve(sys.argv[1]) if len(sys.argv)>1 else versions.CURRENT;H205=versions.is_h205();MUTATE=os.environ.get('PAINTENGINE_MUTATE')
TYPE=versions.type_name(VID);STAMP_HDA=ROOT/('otls_h205' if H205 else 'dist')/('Arraytron_Stamp_v0.12.0%s.hda'%('_H205' if H205 else ''));STAMP_TYPE='arraytron::stamp::0.12.0'
versions.ensure_installed(VID);hou.hda.installFile(str(STAMP_HDA),force_use_assets=True)
out={'groups':{}}
def check(group,cond,note=''):
    out['groups'].setdefault(group,[]).append(bool(cond))
    if not cond:
        import inspect;print('FAIL',group,'#%d'%len(out['groups'][group]),'line',inspect.currentframe().f_back.f_lineno,str(note)[:300])

SCENE='''from pxr import UsdGeom, Vt, Gf
import numpy as np
stage=hou.pwd().editableStage();UsdGeom.Xform.Define(stage,'/World')
n=60;s=40.0;x=np.linspace(-s/2,s/2,n+1);X,Z=np.meshgrid(x,x);Y=0.6*np.sin(X*0.25)*np.cos(Z*0.2)
P=np.stack([X.ravel(),Y.ravel(),Z.ravel()],1);i=np.arange(n);I,J=np.meshgrid(i,i);a=(J*(n+1)+I).ravel();idx=np.stack([a,a+n+1,a+n+2,a+1],1).ravel()
m=UsdGeom.Mesh.Define(stage,'/World/Terrain');m.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(P.astype(np.float32)));m.CreateFaceVertexCountsAttr(Vt.IntArray([4]*(n*n)));m.CreateFaceVertexIndicesAttr(Vt.IntArray.FromNumpy(idx.astype(np.int32)))
for name,shape in (('Ball',UsdGeom.Sphere),('Box',UsdGeom.Cube)):
    UsdGeom.Xform.Define(stage,'/World/Props/'+name);g=shape.Define(stage,'/World/Props/%s/G'%name)
    (g.CreateRadiusAttr(0.2) if name=='Ball' else g.CreateSizeAttr(0.3))
'''
stage=hou.node('/stage');scene=stage.createNode('pythonscript','scene');scene.parm('python').set(SCENE)
def height(x,z):return 0.6*np.sin(np.asarray(x)*0.25)*np.cos(np.asarray(z)*0.2)

def arraytron(name,**values):
    a=stage.createNode(TYPE,name);a.setInput(0,scene)
    if a.parm('copy_test_ground') is not None:a.parm('copy_test_ground').set(0)
    a.parm('protos').set(2);a.parm('proto_type1').set(0);a.parm('proto_prim1').set('/World/Props/Ball');a.parm('proto_type2').set(0);a.parm('proto_prim2').set('/World/Props/Box');a.parm('proto_weight2').set(0.0)
    a.parm('mode').set(6);a.parm('paint_prim').set('')
    for k,v in dict(paint_radius=1.0,paint_density=30.0,paint_spacing=0.0,paint_seed=1).items():a.parm(k).set(v)
    for k,v in values.items():a.parmTuple(k).set(v if isinstance(v,(tuple,list)) else (v,))
    a.node('SOURCE_RESOLVER').stage();return a
def line(x0,x1,n,z=0.0):return np.stack([np.linspace(x0,x1,n),np.zeros(n),np.full(n,z)],axis=1)
def tline(x0,x1,n,z=0.0):
    L=line(x0,x1,n,z);L[:,1]=height(L[:,0],L[:,2]);return L                     # a path on the terrain (where the tool's hits are)
def paint(a,path,surface=None):
    """A Paint stroke through path with the node's settings, written as the tool does (one paint_apply)."""
    m=a.hdaModule();data=m.paint_data(a);surface=surface or m.paint_surface(a);s=m.PaintStroke(a,data,surface,(0,1,0))
    for p in path:s.move(p)
    s.finish();m.paint_apply(a,s.result());return s
def edit(a,kind,path,op=None):
    m=a.hdaModule();e=m.PaintEditStroke(a,m.paint_data(a),m.paint_surface(a),kind,(0,1,0),op=op)
    for p in path:e.move(p)
    e.finish();m.paint_apply(a,e.result());return e
def pts(a):return a.hdaModule().paint_wide(a.hdaModule().paint_data(a)['pts'])
def inst(a):
    st=a.stage();assert not a.errors(),a.errors();pi=UsdGeom.PointInstancer(st.GetPrimAtPath(a.evalParm('outputpath')))
    q=np.array([[v.GetImaginary()[0],v.GetImaginary()[1],v.GetImaginary()[2],v.GetReal()] for v in (pi.GetOrientationsAttr().Get() or [])]).reshape(-1,4)
    return dict(ids=np.array(pi.GetIdsAttr().Get() or [],dtype=np.int64),pos=np.array(pi.GetPositionsAttr().Get() or []).reshape(-1,3),scale=np.array(pi.GetScalesAttr().Get() or []).reshape(-1,3),q=q,proto=np.array(pi.GetProtoIndicesAttr().Get() or []))
def mut(m):
    """The mutations: each breaks one part inside the HDA module (its globals, where its own functions look names up)."""
    g=m.paint_data.__globals__
    if MUTATE=='fall':g['bc_multiplier']=lambda profile,r:np.ones_like(np.asarray(r,dtype=float))
    if MUTATE=='comb':g['paint_align_quats']=lambda pts,amount:g['normal_alignment'](pts[:,3:6],amount)
    if MUTATE=='erase_ids' and not getattr(g['PaintEditStroke'],'_mutated',False):
        orig=g['PaintEditStroke'].result
        def result(self):
            d=orig(self);p=d['pts'].copy();p[:,6]=np.arange(len(p));d['pts']=p;return d
        g['PaintEditStroke'].result=result;g['PaintEditStroke']._mutated=True
    if MUTATE=='swap':g['bc_replace']=lambda ids,w,rows,weights,strength=1.0,seed=0,dab=0:(np.zeros(len(ids),dtype=bool),np.zeros(len(ids),dtype=np.int64))

# ---------------------------------------------------------------- shared
a0=arraytron('shared');ma=a0.hdaModule();mut(ma)
s0=stage.createNode(STAMP_TYPE,'stamp_shared');ms=s0.hdaModule()
for name in ('bc_curve','bc_multiplier','BrushStroke','BrushDabs','BrushGrid','bc_relax','bc_scale','bc_push','bc_orient','bc_replace','bc_cursor','bc_radial_layout'):
    check('shared',hasattr(ma,name) and hasattr(ms,name),name)
check('shared',ma.BC_VERSION==ms.BC_VERSION=='2.0.0' and ma.BC_PRESETS==ms.BC_PRESETS and ma.BC_CURVES==ms.BC_CURVES)
check('shared',all(ma.paint_profile(a0,p) is not None for p in ('dens','scale')) and ma.BC_PRESETS[a0.evalParm('paint_preset')]=='organic' and a0.evalParm('paint_engine')==0,'defaults: Sparse Organic, both falloffs on')
check('shared',ms.BC_PRESETS[s0.evalParm('paint_preset')]=='organic' and s0.evalParm('paint_dens_on')==1 and s0.evalParm('paint_scale_on')==1 and s0.evalParm('paint_engine')==0)
pa=ma.paint_profile(a0,'scale');ps=ms.stamp_falloff_profile(s0,'scale');r=np.linspace(0,1,50)
check('shared',np.allclose(ma.bc_multiplier(pa,r),ms.bc_multiplier(ps,r)) and abs(ma.bc_multiplier(pa,np.array([1.0]))[0]-0.25)<1e-9,'the same parameters give the same falloff in both tools')
vfl=(ROOT/'src'/'vex_v1360'/'transforms.vfl').read_text();check('shared','paint_combed' in vfl)

# ---------------------------------------------------------------- storage
g='storage'
d=ma.paint_empty();d['pts']=ma.paint_rows(np.array([[1.0,0,2]]),np.array([[0,1.0,0]]),np.array([5]));d['next']=6
t1=ma.paint_encode(d);check(g,t1.startswith('p1:'),'no edits: the v0.6.0 text')
d['pts'][0,7]=0.4;d['pts'][0,8]=1.7;d['pts'][0,9]=0.5;d['pts'][0,10]=1;d['pts'][0,11]=2;t3=ma.paint_encode(d);back=ma.paint_decode(t3)
check(g,t3.startswith('p3:') and np.allclose(back['pts'][0,7:],[0.4,1.7,0.5,1,2],atol=1e-6) and back['next']==6,back['pts'])
d2=ma.paint_stroke_add(d,np.array([[0,0,0],[1,0,0.0]]),1.0);b2=ma.paint_decode(ma.paint_encode(d2));check(g,len(b2['strokes'])==1 and np.allclose(b2['pts'][0,7:],[0.4,1.7,0.5,1,2],atol=1e-6),'p3 with the stroke paths of the Falloff tab')
old=ma.paint_decode(t1);check(g,old['pts'].shape==(1,ma.PAINT_WIDE) and np.allclose(old['pts'][0,7:],ma.PAINT_EXTRA_DEFAULT),'an old p1 text reads with the defaults')
try:ma.paint_decode(t3[:40]);ok=False
except ValueError:ok=True
except Exception:ok=True
check(g,ok,'a damaged p3 text is an error')
check(g,ma.PAINT_MAX==200000)

# ---------------------------------------------------------------- stroke: Tests A-D, I on the node (the ground plane)
g='stroke'
aa=arraytron('strokes',paint_dens_on=1,paint_dens_min=0.0,paint_dens_width=80.0,paint_dens_curve=1,paint_scale_on=0);mut(aa.hdaModule())
paint(aa,line(-6,6,600));P=pts(aa);mid=np.abs(P[:,0])<4.0;dz=np.abs(P[mid,2])
bands=[((dz>=lo)&(dz<lo+0.2)).sum()/(0.2*2*8.0)/30.0 for lo in (0,0.2,0.4,0.6,0.8)]
check(g,bands[0]>0.85 and bands[-1]<0.3 and all(bands[k]>=bands[k+1]-0.06 for k in range(4)),'Test A soft density edge %s'%np.round(bands,2))
check(g,np.allclose(P[:,7],1.0),'density only: no scale falloff written')
ab=arraytron('scaleedge',paint_dens_on=0,paint_scale_on=1,paint_scale_min=25.0,paint_scale_width=55.0,paint_scale_curve=2);mut(ab.hdaModule());paint(ab,line(-6,6,600));Pb=pts(ab);mb=np.abs(Pb[:,0])<4.0
check(g,abs(mb.sum()/(8*2.0)/30.0-1)<0.08 and np.allclose(Pb[mb][np.abs(Pb[mb,2])<0.4,7],1.0) and Pb[mb][np.abs(Pb[mb,2])>0.95,7].max()<0.35,'Test B soft scale edge')
check(g,np.allclose(Pb[mb,7],ab.hdaModule().bc_multiplier(ab.hdaModule().paint_profile(ab,'scale'),np.abs(Pb[mb,2])),atol=1e-5),'the scale column is the profile of the distance to the stroke')
ac=arraytron('combined',paint_dens_on=1,paint_dens_width=80.0,paint_dens_curve=1,paint_scale_on=1,paint_scale_min=25.0,paint_scale_width=55.0,paint_scale_curve=2);mut(ac.hdaModule());paint(ac,line(-6,6,600));Pc=pts(ac)
check(g,len(Pc)==len(P) and np.allclose(np.sort(Pc[:,0]),np.sort(P[:,0])),'Test C: combined = the density layout of A with the scales of B')
ad=arraytron('speed',paint_dens_on=1,paint_dens_width=80.0,paint_scale_on=1);paint(ad,line(-6,6,9));Pd=pts(ad)
check(g,np.allclose(np.sort(Pd[:,0]),np.sort(Pc[:,0])) and np.allclose(np.sort(Pd[:,7]),np.sort(Pc[:,7])),'Test D: 9 events make what 600 make (%d vs %d)'%(len(Pd),len(Pc)))
ae=arraytron('determinism',paint_dens_on=1,paint_dens_width=80.0,paint_scale_on=1);paint(ae,line(-6,6,600));check(g,ae.evalParm('paint_data')==ac.evalParm('paint_data'),'Test I: the same stroke gives the same text')
af=arraytron('spacing',paint_spacing=0.25);paint(af,line(-6,6,600));Pf=pts(af);i,j=ma.bc_pairs(Pf[:,[0,2]],0.25*(1-1e-6));check(g,len(i)==0,'spacing')
n1=len(Pf);paint(af,line(-6,6,600));check(g,len(pts(af))==n1,'revisit: painting over the same stroke adds nothing')
check(g,np.array_equal(pts(af)[:,6],np.arange(n1)),'consecutive ids')
at=arraytron('terrain',paint_prim='/World/Terrain');paint(at,tline(-6,6,200));Pt=pts(at);check(g,len(Pt)>100 and np.allclose(Pt[:,1],height(Pt[:,0],Pt[:,2]),atol=0.08),'on the terrain (Test G)')
check(g,np.all(Pt[:,4]>0.8) and np.allclose(np.linalg.norm(Pt[:,3:6],axis=1),1.0,atol=1e-6),'normals of the terrain')
an=arraytron('noise',paint_noise=0.8);paint(an,line(-6,6,600));check(g,len(pts(an))!=len(Pc) and len(pts(an))>0,'spatter changes the layout')

# ---------------------------------------------------------------- instances: the brushes reach the PointInstancer
g='instances'
ai=arraytron('inst',paint_dens_on=0,paint_scale_on=1,paint_scale_min=25.0,paint_scale_width=55.0,paint_scale_curve=2,paint_spacing=0.2);mi=ai.hdaModule();mut(mi)
for k,v in (('scale_random',0.0),('base_scale',1.0)):
    if ai.parm(k) is not None:ai.parm(k).set(v)
paint(ai,line(-4,4,300));Pi=pts(ai);I=inst(ai);order=np.argsort(I['ids']);byid={int(k):i for i,k in enumerate(I['ids'])}
sc=np.array([I['scale'][byid[int(k)],0] for k in Pi[:,6]]);check(g,len(I['ids'])==len(Pi) and np.allclose(sc,Pi[:,7],rtol=1e-3),'Scale Falloff reaches the instance scale')
base=sc.copy();edit(ai,'scale',line(-1,1,40),op='grow');Pg=pts(ai);I=inst(ai);byid={int(k):i for i,k in enumerate(I['ids'])};sg=np.array([I['scale'][byid[int(k)],0] for k in Pg[:,6]])
check(g,np.any(Pg[:,8]>1.01) and np.allclose(sg,Pg[:,7]*Pg[:,8],rtol=1e-3),'Grow: the edit multiplies the falloff scale (fall x edit)')
edit(ai,'scale',line(-1,1,40),op='shrink');check(g,np.allclose(pts(ai)[:,8],1.0,atol=1e-9),'Test F: shrink undoes grow exactly (no compounding)')
P0=pts(ai);ids0=set(P0[:,6].astype(int).tolist());edit(ai,'remove',line(-0.5,0.5,10),op='hard');P1=pts(ai);ids1=set(P1[:,6].astype(int).tolist())
pos0={int(k):P0[i,0:3] for i,k in enumerate(P0[:,6])};check(g,all(np.allclose(pos0.get(int(k),[1e9,0,0]),P1[i,0:3]) for i,k in enumerate(P1[:,6])),'every survivor keeps its own id')
check(g,ids1<ids0 and len(ids0-ids1)>0,'Erase removes points and keeps the other ids (%d -> %d)'%(len(ids0),len(ids1)))
check(g,set(inst(ai)['ids'].tolist())==ids1,'the instancer has exactly the surviving ids')
soft=arraytron('soft');paint(soft,line(-4,4,300));n0=len(pts(soft));edit(soft,'remove',line(-4,4,100),op='soft');n1=len(pts(soft));check(g,0.3*n0<n1<0.98*n0,'soft erase thins (%d -> %d)'%(n0,n1))
ar=arraytron('comb',paint_dens_on=0,paint_scale_on=0,paint_spacing=0.3)
if ar.parm('rotation_random_mode') is not None:ar.parm('rotation_random_mode').set(1);ar.parm('yaw_random').set(180.0)
paint(ar,line(-3,3,200));I0=inst(ar);F0=ma.bc_qrot(I0['q'],np.array([0,0,1.0]));check(g,np.std(np.arctan2(F0[:,0],F0[:,2]))>0.5,'random yaw before combing')
ar.parm('brush_amount').set(1.0);edit(ar,'orient',line(-3,3,200),op='comb');I1=inst(ar);F1=ma.bc_qrot(I1['q'],np.array([0,0,1.0]));Pr=pts(ar);byid={int(k):i for i,k in enumerate(I1['ids'])}
combed=np.array([byid[int(k)] for k in Pr[(Pr[:,10]>0.5)&(np.abs(Pr[:,2])<0.5),6]]);check(g,len(combed)>0.5*len(Pr) and np.mean(F1[combed,0])>0.6,'Orient / Comb: the headings turn along the stroke despite the random yaw (mean x %.2f)'%(np.mean(F1[combed,0]) if len(combed) else 0))
edit(ar,'orient',line(-3,3,200),op='restore');check(g,np.all(pts(ar)[:,10]==0) and np.allclose(pts(ar)[:,9],0),'Restore gives the random rotation back')
asw=arraytron('swap');paint(asw,line(-3,3,200));asw.parm('paint_swap_row').set(2);mut(asw.hdaModule());edit(asw,'swap',line(-1,1,40));Ps=pts(asw);I=inst(asw);byid={int(k):i for i,k in enumerate(I['ids'])}
sw=Ps[Ps[:,11]==2,6];check(g,len(sw)>0 and len(set(I['proto'][[byid[int(k)] for k in sw]].tolist()))==1 and len(set(I['proto'][[byid[int(k)] for k in Ps[Ps[:,11]==0,6]]].tolist()))==1 and I['proto'][byid[int(sw[0])]]!=I['proto'][byid[int(Ps[Ps[:,11]==0,6][0])]],'Swap: the swapped points take bank row 2 (weight 0 otherwise)')
arl=arraytron('relax',paint_prim='/World/Terrain',paint_spacing=0.0,paint_density=60.0);paint(arl,tline(-2,2,100));Pq=pts(arl);before=len(ma.bc_pairs(Pq[:,[0,2]],0.096)[0])
arl.parm('paint_spacing').set(0.12);edit(arl,'relax',tline(-2,2,100));Pq2=pts(arl);after=len(ma.bc_pairs(Pq2[:,[0,2]],0.096)[0])
check(g,after<0.6*before and np.allclose(Pq2[:,1],height(Pq2[:,0],Pq2[:,2]),atol=0.08) and set(Pq2[:,6].tolist())==set(Pq[:,6].tolist()),'Relax (Test E): fewer crowded pairs (< 0.8 x spacing) %d -> %d, on the terrain, the same ids'%(before,after))
c=np.array([0.0,float(height(0,0)),0]);d0=np.linalg.norm(Pq2[:,[0,2]],axis=1);edit(arl,'push',[c],op='push');Pp=pts(arl);d1=np.linalg.norm(Pp[:,[0,2]],axis=1)
near=d0<0.9;check(g,np.all(d1[near]>=d0[near]-1e-9) and np.any(d1[near]>d0[near]+1e-3) and np.allclose(Pp[:,1],height(Pp[:,0],Pp[:,2]),atol=0.08),'Push moves away and stays on the terrain')

# ---------------------------------------------------------------- clone
g='clone'
acl=arraytron('clone',paint_spacing=0.2);paint(acl,line(-0.5,0.5,30));mc=acl.hdaModule();k=mc.paint_clone_capture(acl,mc.paint_data(acl),(0,0,0),(0,1,0),1.2)
src=mc.paint_clone_source(acl);check(g,k>3 and src is not None and len(src['off'])==k)
data=mc.paint_data(acl);rows=mc.paint_clone_rows(acl,mc.paint_surface(acl),src,np.array([10.0,0,0]),np.array([0,1.0,0]),data['next'],copy=0)
check(g,len(rows)==k and np.all(rows[:,6]>=data['next']) and np.allclose(rows[:,1],0.0,atol=1e-6) and np.all(np.abs(rows[:,0]-10)<1.6),'a copy lands at the new place with new ids')
D=lambda X:np.linalg.norm(X[:,None,[0,2]]-X[None,:,[0,2]],axis=2);orig=pts(acl)[np.linalg.norm(pts(acl)[:,0:3],axis=1)<=1.2]
check(g,np.allclose(np.sort(D(rows).ravel()),np.sort(D(orig).ravel()),atol=1e-4),'the arrangement is kept (distances)')

# ---------------------------------------------------------------- stamp: the sculpt brushes on the Stamps text
g='stamp'
def stampnode(name):
    s=stage.createNode(STAMP_TYPE,name);s.setInput(0,scene);s.parm('target').set('');s.parm('sit').set(0)
    s.parm('protos').set(2);s.parm('proto_type1').set(0);s.parm('proto_prim1').set('/World/Props/Ball');s.parm('proto_type2').set(0);s.parm('proto_prim2').set('/World/Props/Box');return s
st=stampnode('sculpt');m=st.hdaModule()
if MUTATE=='stamp_erase':m.StampEditStroke.FLUSH_S=0.05;orig_dab=m.StampEditStroke._dab;m.StampEditStroke._dab=lambda self,c:(orig_dab(self,c),setattr(self,'lines',[l for l in self.lines]))[0] if self.kind!='erase' else None
surf=m.stamp_surface(st);rs=np.random.RandomState(3);P=np.column_stack([rs.rand(400)*8-4,np.zeros(400),rs.rand(400)*8-4])
st.parm('stamps').set('\n'.join(m.stamp_line(p,(0,rs.rand()*360,0),(1,1,1),1) for p in P))
def sculpt(kind,path,op=None,node=st):
    e=node.hdaModule().StampEditStroke(node,node.hdaModule().stamp_surface(node),kind,(0,1,0),op=op,bounds=node.hdaModule().stamp_proto_bounds(node))
    for p in path:e.move(p)
    e.finish();return e
rows0=m.stamp_rows(st.evalParm('stamps'));sculpt('erase',line(-1,1,30),'hard');rows1=m.stamp_rows(st.evalParm('stamps'))
gone=np.nonzero(rows1[:,10]<0.5)[0];check(g,len(rows1)==len(rows0) and len(gone)>0 and np.all(np.abs(rows0[gone,2])<=1.0+1e-6),'Erase switches stamps off; the line count (the ids) stays')
I=inst(st) if False else None
ids=np.array(UsdGeom.PointInstancer(st.stage().GetPrimAtPath('/World/Stamps')).GetIdsAttr().Get());check(g,set(ids.tolist())==set(np.nonzero(rows1[:,10]>0.5)[0].tolist()),'the instancer keeps the ids of the others')
check(g,m.stamp_restore_erased(st)==len(gone) and np.all(m.stamp_rows(st.evalParm('stamps'))[:,10]>0.5),'Restore Erased Stamps')
sculpt('erase',line(-1,1,30),'hard');k=m.stamp_remove_erased(st);check(g,k==len(gone) and len(m.stamp_rows(st.evalParm('stamps')))==len(rows0)-k,'Remove Erased Stamps')
r0=m.stamp_rows(st.evalParm('stamps'));sculpt('scale',[np.array([2.5,0,2.5])],'grow');r1=m.stamp_rows(st.evalParm('stamps'));chg=np.nonzero(np.abs(r1[:,6]-r0[:,6])>1e-6)[0]
check(g,len(chg)>0 and np.all(r1[chg,6]>r0[chg,6]) and np.all(np.linalg.norm(r0[chg][:,[0,2]]-[2.5,2.5],axis=1)<=1.0+1e-6),'Grow scales the stamps under the brush %d %s'%(len(chg),r0[chg][:3,[0,2,6]] if len(chg) else ''))
sculpt('scale',[np.array([2.5,0,2.5])],'shrink');r2=m.stamp_rows(st.evalParm('stamps'));check(g,np.allclose(r2[:,6],r0[:,6],atol=2e-4),'shrink undoes grow (to the 4 decimals of the text)')
before=len(m.bc_pairs(r2[r2[:,10]>0.5][:,[0,2]],0.35)[0]);st.parm('paint_spacing').set(0.35);st.parm('paint_radius').set(2.0);sculpt('relax',line(-2,2,40));r3=m.stamp_rows(st.evalParm('stamps'))
after=len(m.bc_pairs(r3[r3[:,10]>0.5][:,[0,2]],0.35)[0]);check(g,after<before and np.allclose(r3[:,1],0.0,atol=1e-4),'Relax: fewer close pairs %d -> %d, on the ground'%(before,after))
st.parm('paint_radius').set(1.0);r3=m.stamp_rows(st.evalParm('stamps'));sculpt('push',[np.array([2.5,0,2.5])],'push');r4=m.stamp_rows(st.evalParm('stamps'));d3=np.linalg.norm(r3[:,[0,2]]-[2.5,2.5],axis=1);d4=np.linalg.norm(r4[:,[0,2]]-[2.5,2.5],axis=1)
check(g,np.all(d4[d3<0.9]>=d3[d3<0.9]-1e-4) and np.any(d4>d3+1e-3),'Push moves the stamps away')
m.stamp_set_workset(st,[2]);sculpt('replace',[np.array([2.5,0,2.5])]);r5=m.stamp_rows(st.evalParm('stamps'));sw=np.nonzero(r5[:,9]!=r4[:,9])[0]
check(g,len(sw)>0 and np.all(r5[sw,9]==2) and np.allclose(r5[sw,0:9],r4[sw,0:9],atol=2e-3),'Replace takes the working set and keeps the placement %d %s'%(len(sw),np.abs(r5[sw,0:9]-r4[sw,0:9]).max() if len(sw) else ''))
st.parm('brush_amount').set(1.0);sculpt('orient',line(1.5,3.5,40,2.5),'comb');r6=m.stamp_rows(st.evalParm('stamps'));F=m.bc_qrot(m.stamp_quat(r6[:,3:6]),np.array([0,0,1.0]));turned=np.nonzero(np.abs(r6[:,4]-r5[:,4])>1e-3)[0]
check(g,len(turned)>0 and np.mean(F[turned,0])>0.5,'Orient / Comb turns the headings along the stroke %d %.2f'%(len(turned),np.mean(F[turned,0]) if len(turned) else 0))
text=st.evalParm('stamps');e=m.StampEditStroke(st,surf,'push',(0,1,0),op='push');e.FLUSH_S=0.0;e.timer.interval=0.0;e.move(np.array([2.5,0,2.5]));e.move(np.array([3.0,0,2.5]))
check(g,st.evalParm('stamps')!=text,'live writes while dragging');e.cancel();check(g,st.evalParm('stamps')==text,'Cancel puts the stamps back')
k=m.stamp_clone_capture(st,(2.5,0,2.5),(0,1,0),1.0);lines=m.stamp_clone_lines(st,m.stamp_surface(st),np.array([20.0,0,0]),np.array([0,1.0,0]),0);rc=m.stamp_rows('\n'.join(lines))
check(g,k>0 and len(lines)==k and np.all(np.abs(rc[:,0]-20)<1.5) and np.allclose(rc[:,1],0.0,atol=1e-3),'Clone: a copy of the stamps under the brush')

# ---------------------------------------------------------------- viewer: both states through a stand-in viewport
g='viewer'
class StubDrawable(object):
    """Like hou.GeometryDrawable: visible(), and no `shown` attribute (a state that reads .shown fails here as it did in the viewer)."""
    def __init__(self,*a,**k):self.geo=None;self._vis=False;self.params={}
    def setParams(self,p):self.params.update(p)
    def setGeometry(self,geo):self.geo=geo
    def setTransform(self,x):pass
    def show(self,v):self._vis=bool(v)
    def visible(self):return self._vis
    def draw(self,h,p=None):pass
class VP(object):
    def mapToScreen(self,p):return (p[0]*10.0,p[2]*10.0)
    def mapToWorld(self,x,y):return hou.Vector3((0,-1,0)),hou.Vector3((x/10.0,10.0,y/10.0))
    def draw(self):pass
class Viewer(object):
    def __init__(self):self.prompt=None;self.tmpl=None;self.vals={};self.undo=[];self.groups=[];self.shown=None
    def setPromptMessage(self,m,t=None):self.prompt=m
    def clearPromptMessage(self):self.prompt=None
    def curViewport(self):return VP()
    def hudInfo(self,show=-1,template=None,values=None,**k):
        if template is not None:self.tmpl=template
        if values is not None:self.vals.update(values)
        if show!=-1:self.shown=show
    def showHandle(self,*a):pass
    def beginStateUndo(self,label):self.undo.append('begin');g_=hou.undos.group(label);g_.__enter__();self.groups.append(g_)
    def endStateUndo(self):
        self.undo.append('end')
        if self.groups:self.groups.pop().__exit__(None,None,None)
class Dev(object):
    def __init__(self,x,y,left=False,ctrl=False,shift=False,key='',wheel=0):self.x,self.y,self.left,self.ctrl,self.shift,self.key,self.wheel=x,y,left,ctrl,shift,key,wheel
    def mouseX(self):return self.x
    def mouseY(self):return self.y
    def isLeftButton(self):return self.left
    def isCtrlKey(self):return self.ctrl
    def isShiftKey(self):return self.shift
    def isMiddleButton(self):return False
    def isAltKey(self):return False
    def isKeyDown(self):return False
    def keyString(self):return self.key
    def mouseWheel(self):return self.wheel
class Ev(object):
    def __init__(self,d,r):self.d,self.r=d,r
    def device(self):return self.d
    def reason(self):return self.r
    def curViewport(self):return VP()
    def ray(self):return hou.Vector3((self.d.x/10.0,10.0,self.d.y/10.0)),hou.Vector3((0,-1,0))
class Fwd(object):
    GeometryDrawable=StubDrawable;TextDrawable=StubDrawable
    def __getattr__(self,k):return getattr(hou,k)
def state_of(node,cls):
    src=node.type().definition().sections()['ViewerStateModule'].contents().replace('import hou'+chr(10),'',1)
    if MUTATE=='cancel':src=src.replace("self.engine=None;self.painting=False;self.stroke=[];self.dirty=False;self._load()","self.painting=False;self._end_stroke()")
    glob={'hou':Fwd(),'np':np,'__name__':'pe_state'};exec(compile(src,'state','exec'),glob);glob['STRICT']=True;v=Viewer();return glob[cls]('pe',v),v
R=hou.uiEventReason
av=arraytron('viewer');sv,vv=state_of(av,'PaintState');sv.onEnter({'node':av})
def amouse(x,z,r,**k):return sv.onMouseEvent({'ui_event':Ev(Dev(x*10.0,z*10.0,**k),r)})
def akey(k):return sv.onKeyEvent({'ui_event':Ev(Dev(0,0,key=k),R.Changed)})
amouse(0,0,R.Located);amouse(0,0,R.Located);amouse(0.0001,0,R.Located);check(g,sv.brush.visible() and sv.brush.geo is not None and len(sv.brush.geo.prims())>=4,'the cursor: the radius ring, the falloff rings, the cross and the tick')
check(g,vv.tmpl is not None and vv.tmpl['title']=='Arraytron Paint' and any(r.get('key')=='LMB drag' for r in vv.tmpl['rows']) and 'v_falloff' in vv.vals and '\n' not in (vv.prompt or ''),'the HUD panel and a one-line prompt')
text0=av.evalParm('paint_data');amouse(-2,0,R.Start,left=True)
for x in np.linspace(-2,2,30):amouse(x,0,R.Active,left=True)
check(g,av.evalParm('paint_data')==text0 and len(sv.engine.points())>len(ma.paint_data(av)['pts']),'nothing is written while dragging')
amouse(2,0,R.Changed);n=len(pts(av));check(g,n>50 and av.evalParm('paint_data')!=text0,'one write on release (%d points)'%n)
hou.undos.performUndo();check(g,len(pts(av))==0,'one undo step takes the whole stroke');hou.undos.performRedo();check(g,len(pts(av))==n)
t1=av.evalParm('paint_data');amouse(-2,1,R.Start,left=True);amouse(0,1,R.Active,left=True);akey('Escape');amouse(0,1,R.Changed)
check(g,av.evalParm('paint_data')==t1 and sv.engine is None and not sv.painting,'Esc cancels the stroke: nothing is written')
lvl=sv._prefs()['hud'];akey('h');check(g,sv._prefs()['hud']!=lvl and json.load(open(os.environ['ARRAYTRON_BRUSH_PREFS']))['hud']==sv._prefs()['hud'],'H cycles the HUD level and keeps it')
while sv._prefs()['hud']!='standard':akey('h')
check(g,akey('5') and av.evalParm('paint_op')==4 and vv.tmpl['rows'][0]['label']=='Grow / Shrink','5: Grow / Shrink and its hints')
check(g,akey('c') is True,'C opens the brush menu (the popup without Houdini radial menus)');akey('1')
p0=av.evalParm('paint_preset');akey('f');check(g,av.evalParm('paint_preset')!=p0,'F: the next falloff preset')
av.parm('paint_op').set(1);n0=len(pts(av));amouse(-1,0,R.Start,left=True);amouse(1,0,R.Active,left=True);amouse(1,0,R.Changed);check(g,len(pts(av))<n0,'Erase through the tool')
sst=stampnode('stamp_viewer');ss,sv2=state_of(sst,'StampState');sst.parm('brush').set(2);sst.parm('paint_density').set(20.0);sst.parm('paint_spacing').set(0.1);ss.onEnter({'node':sst})
def smouse(x,z,r,**k):return ss.onMouseEvent({'ui_event':Ev(Dev(x*10.0,z*10.0,**k),r)})
smouse(0,0,R.Located);smouse(0,0,R.Located);smouse(0.0001,0,R.Located);check(g,ss.cursor.visible() and sv2.vals.get('mode')=='Brush / Paint','the Stamp cursor')
smouse(-2,0,R.Start,left=True)
for x in np.linspace(-2,2,30):smouse(x,0,R.Active,left=True)
smouse(2,0,R.Changed);n=ms.stamp_count(sst.evalParm('stamps'));check(g,n>20 and sv2.undo[-2:]==['begin','end'],'Stamp Paint: one undo group (%d stamps)'%n)
sst.parm('brush').set(4);sv2.undo.clear();smouse(-1,0,R.Start,left=True);smouse(1,0,R.Active,left=True);smouse(1,0,R.Changed);rows=ms.stamp_rows(sst.evalParm('stamps'))
check(g,(rows[:,10]<0.5).sum()>0 and len(rows)==n and sv2.undo==['begin','end'],'Stamp Erase through the tool')
sst.parm('brush').set(7);t2=sst.evalParm('stamps');smouse(0,0,R.Start,left=True);smouse(0.5,0,R.Active,left=True);ss.onKeyEvent({'ui_event':Ev(Dev(0,0,key='Escape'),R.Changed)})
check(g,sst.evalParm('stamps')==t2 and ss.stroke is None,'Stamp: Esc cancels a Push stroke')
check(g,ss.onKeyEvent({'ui_event':Ev(Dev(0,0,key='c'),R.Changed)}) is True,'Stamp C')

res={'version':VID,'houdini':hou.applicationVersionString(),'groups':{k:'%d/%d'%(sum(v),len(v)) for k,v in out['groups'].items()},'mutate':MUTATE}
bad=[k for k,v in out['groups'].items() if not all(v)]
print(('FAILED ' if bad else 'ALL PASSED ')+json.dumps(res['groups']))
if not MUTATE:
    with open(ROOT/'tests'/('validation_paintengine_%s.json'%('205' if H205 else '22')),'w') as f:json.dump(res,f,indent=1)
sys.exit(1 if bad else 0)
