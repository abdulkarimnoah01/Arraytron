"""Build the Paint Engine 2.0 demo (v1.36.0 + Arraytron Stamp 0.11.0): hython tools/build_demo_paintengine_v1360.py
One terrain with hills, rows of painted strokes, each an Arraytron node of its own (the strokes are made with the tool's own functions, as the brush makes them):
  A  Soft density edge (Density Falloff only)            B  Soft scale edge (Scale Falloff only: even density, small at the rim)
  C  Combined (Sparse Organic, the default)              D  Relax (dense paint, the right half relaxed)
  E  Grow / Shrink (right half grown, left end shrunk)   F  Push / Attract (a hole pushed into a patch, a clump attracted)
  G  A continuous stroke over a hill (S curve)           S  Arraytron Stamp 0.11.0: a Sparse Organic stroke, soft-erased in the middle, combed at the end
Asserts each row did what it says. Writes dist/Arraytron_v1.36.0_paintengine_demo.hip or the Houdini 20.5 / 21 equivalent (otls_h205/..._H205_paintengine_demo.hip)."""
from pathlib import Path
import sys, json, os
import numpy as np
import hou
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
os.environ.pop('ARRAYTRON_STAMP',None)
VID=versions.BUILD;TYPE=versions.type_name(VID);HIP=versions.demo(VID,'paintengine');H205=versions.is_h205()
STAMP_HDA=ROOT/('otls_h205' if H205 else 'dist')/('Arraytron_Stamp_v0.11.0%s.hda'%('_H205' if H205 else ''));STAMP_TYPE='arraytron::stamp::0.11.0'
hou.hipFile.clear(suppress_save_prompt=True);versions.ensure_installed(VID)
if not H205:hou.hda.installFile(str(STAMP_HDA),force_use_assets=True)                     # the 20.5 / 21 build finds both HDAs through the scan path (tools/build_h205_demos.sh)
hou.hipFile.save(str(HIP))
SCENE='''from pxr import UsdGeom, Vt, Gf
import numpy as np
stage=hou.pwd().editableStage();UsdGeom.Xform.Define(stage,'/World')
n=160;sx=44.0;sz=72.0;x=np.linspace(-sx/2,sx/2,n+1);z=np.linspace(-sz/2,sz/2,n+1);X,Z=np.meshgrid(x,z)
Y=0.35*np.sin(X*0.3)*np.cos(Z*0.25)+2.2*np.exp(-((X-0.0)**2+(Z-27.0)**2)/18.0)
P=np.stack([X.ravel(),Y.ravel(),Z.ravel()],1);i=np.arange(n);I,J=np.meshgrid(i,i);a=(J*(n+1)+I).ravel();idx=np.stack([a,a+n+1,a+n+2,a+1],1).ravel()
m=UsdGeom.Mesh.Define(stage,'/World/Terrain');m.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(P.astype(np.float32)));m.CreateFaceVertexCountsAttr(Vt.IntArray([4]*(n*n)));m.CreateFaceVertexIndicesAttr(Vt.IntArray.FromNumpy(idx.astype(np.int32)))
m.CreateDisplayColorAttr([Gf.Vec3f(0.33,0.42,0.26)])
UsdGeom.Xform.Define(stage,'/World/Props/Shrub');s=UsdGeom.Sphere.Define(stage,'/World/Props/Shrub/G');s.CreateRadiusAttr(0.11);s.CreateDisplayColorAttr([Gf.Vec3f(0.2,0.55,0.25)])
UsdGeom.Xform.Define(stage,'/World/Props/Rock');c=UsdGeom.Cube.Define(stage,'/World/Props/Rock/G');c.CreateSizeAttr(0.18);c.CreateDisplayColorAttr([Gf.Vec3f(0.55,0.5,0.45)])
UsdGeom.Xform.Define(stage,'/World/Props/Fern');k=UsdGeom.Cone.Define(stage,'/World/Props/Fern/G');k.CreateRadiusAttr(0.07);k.CreateHeightAttr(0.3);k.CreateAxisAttr('Y');k.CreateDisplayColorAttr([Gf.Vec3f(0.85,0.75,0.25)])
'''
stage=hou.node('/stage');scene=stage.createNode('pythonscript','terrain_and_props');scene.parm('python').set(SCENE);scene.setPosition((0,6))
def height(x,z):x=np.asarray(x);z=np.asarray(z);return 0.35*np.sin(x*0.3)*np.cos(z*0.25)+2.2*np.exp(-((x-0.0)**2+(z-27.0)**2)/18.0)
def path(x0,x1,n,z):
    p=np.stack([np.linspace(x0,x1,n),np.zeros(n),np.full(n,float(z))],1);p[:,1]=height(p[:,0],p[:,2]);return p
nodes=[]
def node(name,z,comment,**values):
    a=stage.createNode(TYPE,name);a.setInput(0,scene)
    if a.parm('copy_test_ground') is not None:a.parm('copy_test_ground').set(0)
    a.parm('protos').set(1);a.parm('proto_type1').set(0);a.parm('proto_prim1').set('/World/Props/Shrub');a.parm('outputpath').set('/World/Paint_%s'%name)
    a.parm('mode').set(6);a.parm('paint_prim').set('/World/Terrain')
    for k,v in dict(paint_radius=1.6,paint_density=9.0,paint_spacing=0.2,paint_seed=3).items():a.parm(k).set(v)
    for k,v in values.items():a.parmTuple(k).set(v if isinstance(v,(tuple,list)) else (v,))
    a.node('SOURCE_RESOLVER').stage();a.setComment(comment);a.setGenericFlag(hou.nodeFlag.DisplayComment,True);a.setPosition((len(nodes)*3.2-12,3));nodes.append(a);return a
def paint(a,p):
    m=a.hdaModule();s=m.PaintStroke(a,m.paint_data(a),m.paint_surface(a),(0,1,0))
    for q in p:s.move(q)
    s.finish();d=m.paint_stroke_add(s.result(),p,a.evalParm('paint_radius'));m.paint_apply(a,d,'demo stroke');return len(d['pts'])
def edit(a,kind,p,op=None):
    m=a.hdaModule();e=m.PaintEditStroke(a,m.paint_data(a),m.paint_surface(a),kind,(0,1,0),op=op)
    for q in p:e.move(q)
    e.finish();m.paint_apply(a,e.result(),'demo '+kind);return e.changed
def pts(a):return a.hdaModule().paint_wide(a.hdaModule().paint_data(a)['pts'])
facts={}
A=node('A_DensityEdge',-30,'A: Density Falloff only (smoothstep over 80 % of the radius): dense along the stroke, thinning smoothly to nothing at its edge. No circles where the mouse paused.',paint_dens_on=1,paint_scale_on=0)
facts['A']=paint(A,path(-15,15,240,-30))
B=node('B_ScaleEdge',-22,'B: Scale Falloff only (Edge Minimum 25 %, smootherstep): the density is even, the instances shrink towards the edge of the stroke.',paint_dens_on=0,paint_scale_on=1,paint_preset=7)
facts['B']=paint(B,path(-15,15,240,-22));pb=pts(B);assert pb[:,7].min()<0.4 and pb[:,7].max()>0.99
C=node('C_Combined',-14,'C: both (Sparse Organic, the default of a new node): a broad sparse rim, a tighter size taper, a full dense core.')
facts['C']=paint(C,path(-15,15,240,-14))
D=node('D_Relax',-6,'D: dense paint (Min Spacing 0), the right half relaxed with the Relax brush to an even spacing of 0.26.',paint_spacing=0.0,paint_density=12.0,paint_dens_on=0,paint_scale_on=0)
facts['D']=paint(D,path(-15,15,240,-6));D.parm('paint_spacing').set(0.26);D.parm('paint_radius').set(1.8);facts['D_moved']=edit(D,'relax',path(0,15,120,-6));D.parm('paint_radius').set(1.6)
E=node('E_GrowShrink',2,'E: the right half grown with Grow / Shrink, the left end shrunk (Ctrl): an artist scale edit on top of the falloff, undoable, never compounding.',paint_dens_on=0,paint_scale_on=0)
facts['E']=paint(E,path(-15,15,240,2));E.parm('brush_amount').set(0.8);edit(E,'scale',path(2,15,80,2),'grow');edit(E,'scale',path(-15,-8,50,2),'shrink');pe=pts(E);assert pe[:,8].max()>1.3 and pe[:,8].min()<0.8
F=node('F_PushAttract',10,'F: a patch with a hole pushed into its middle (Push) and a clump gathered at its right end (Ctrl: Attract).',paint_dens_on=0,paint_scale_on=0,paint_radius=2.5)
facts['F']=paint(F,np.concatenate([path(-15,15,200,9),path(15,-15,200,11)]));F.parm('paint_radius').set(1.6);F.parm('brush_amount').set(0.6)
c=np.array([0.0,height(0,10),10.0]);edit(F,'push',[c]*1+[c+[0.01,0,0]]*3,'push');c2=np.array([11.0,height(11,10),10.0]);edit(F,'push',[c2,c2+[0.01,0,0],c2+[0.02,0,0]],'attract')
G=node('G_OverTheHill',27,'G: one continuous stroke in an S over a hill: the falloff follows the stroke on the slope, the instances stand on the terrain.')
t=np.linspace(0,1,300);sp=np.stack([-14+28*t,np.zeros_like(t),27+4.5*np.sin(t*2*np.pi)],1);sp[:,1]=height(sp[:,0],sp[:,2]);facts['G']=paint(G,sp);pg=pts(G);assert np.allclose(pg[:,1],height(pg[:,0],pg[:,2]),atol=0.1)
S=stage.createNode(STAMP_TYPE,'S_Stamp');S.setInput(0,scene);S.parm('target').set('/World/Terrain');S.parm('outputpath').set('/World/Stamps_S');S.parm('sit').set(1)
S.parm('protos').set(3)
for i,prim in enumerate(('/World/Props/Shrub','/World/Props/Rock','/World/Props/Fern'),1):S.parm('proto_type%d'%i).set(0);S.parm('proto_prim%d'%i).set(prim)
S.parm('protorand').set(1);S.parm('paint_radius').set(1.6);S.parm('paint_density').set(10.0);S.parm('paint_spacing').set(0.3);S.parm('yawrand').set(180.0);S.parmTuple('scalerange').set((0.8,1.2))
S.setComment('S: Arraytron Stamp 0.11.0 on the same engine: a Sparse Organic stroke of three prototypes, soft-erased in the middle (Erase, Shift), combed at the right end (Orient / Comb).');S.setGenericFlag(hou.nodeFlag.DisplayComment,True);S.setPosition((len(nodes)*3.2-12,3))
ms=S.hdaModule();surf=ms.stamp_surface(S);sp2=path(-15,15,240,34);stroke=ms.StampPaintStroke(S,surf,ms.stamp_proto_bounds(S),normal=(0,1,0));stroke.FLUSH_S=1e9
for q in sp2:stroke.move(q)
stroke.finish();n0=ms.stamp_count(S.evalParm('stamps'))
S.parm('brush_amount').set(0.8);e=ms.StampEditStroke(S,ms.stamp_surface(S),'erase',(0,1,0),op='soft')
for q in path(-3,3,60,34):e.move(q)
e.finish();S.parm('brush_amount').set(1.0);e=ms.StampEditStroke(S,ms.stamp_surface(S),'orient',(0,1,0),op='comb')
for q in path(7,15,80,34):e.move(q)
e.finish();rows=ms.stamp_rows(S.evalParm('stamps'));facts['S']=dict(stamps=n0,erased=int((rows[:,10]<0.5).sum()));assert n0>50 and 0<facts['S']['erased']<n0,facts['S']
merge=stage.createNode('merge','all_rows')
for k,a in enumerate(nodes+[S]):merge.setInput(k,a)
merge.setDisplayFlag(True);merge.setPosition((0,0))
cam=stage.createNode('camera','camera1');cam.setInput(0,merge);cam.setPosition((0,-1))
for p_,v in (('tx',0.0),('ty',115.0),('tz',2.0),('rx',-90.0)):cam.parm(p_).set(v)
st=merge.stage();errs=[(a.name(),a.errors()) for a in nodes+[S] if a.errors()];assert not errs,errs
hou.hipFile.save(str(HIP))
print(json.dumps({'saved':hou.hipFile.path(),'facts':facts}))
