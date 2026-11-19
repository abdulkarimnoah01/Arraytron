"""Saved masks (Arraytron v1.38.0): Save Mask For Other Arraytron Nodes, the Upstream Mask source and the offer when nodes are wired.
  hython tests/validate_maskstage.py [v1.38.0]        (hython 22 or 20.5; build the HDA first)
Groups: saving (the grid and its customData, the name: typed, default, cleaned, reserved; the primvar of that name on every instance, equal to the weight the node used; off removes both), the cache (the same
grid while nothing changed, a new one when the mask changed), using it (Upstream Mask reads the saved weight at every point, several masks multiply / maximum / minimum, outside the area black or edge, a missing
name says which masks exist, the points of the node below follow the mask above), the offer (once per mask, Use / Not Now / Don't Ask, several masks, Find Upstream Masks, nothing without the switch), chains
(a node below two saving nodes sees both) and the menu and the info texts."""
import sys, os, json
from pathlib import Path
import numpy as np
import hou
from pxr import UsdGeom
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
os.environ.pop('ARRAYTRON_STAMP',None)
VID=versions.resolve(sys.argv[1]) if len(sys.argv)>1 else versions.CURRENT;TYPE=versions.type_name(VID)
hou.hda.installFile(str(versions.hda(VID,versions.is_h205())),force_use_assets=True)
fails=[];passed=[0]
def check(name,ok,detail=''):
    if ok:print('PASS',name);passed[0]+=1
    else:print('FAIL',name,'->',detail);fails.append(name)
stage=hou.node('/stage')
SRC=("from pxr import UsdGeom, Vt, Gf\nstage=hou.pwd().editableStage()\nm=UsdGeom.Mesh.Define(stage,'/World/Ground')\n"
     "m.CreatePointsAttr(Vt.Vec3fArray([Gf.Vec3f(-20,0,-20),Gf.Vec3f(20,0,-20),Gf.Vec3f(20,0,20),Gf.Vec3f(-20,0,20)]));m.CreateFaceVertexCountsAttr(Vt.IntArray([4]));m.CreateFaceVertexIndicesAttr(Vt.IntArray([0,3,2,1]))\n"
     "UsdGeom.Sphere.Define(stage,'/World/Props/Crate').CreateRadiusAttr(0.3)\n")
src=stage.createNode('pythonscript','scene');src.parm('python').set(SRC)
def scatter(name,inp,out,count=900):
    n=stage.createNode(TYPE,name);n.setInput(0,inp)
    if n.parm('copy_test_ground') is not None:n.parm('copy_test_ground').set(0)
    n.parm('outputpath').set(out);n.parm('mode').set(5);n.parm('surface_prim').set('/World/Ground');n.parm('surface_count').set(count)
    return n
def instancer(n,path):
    return UsdGeom.PointInstancer(n.stage().GetPrimAtPath(path))
def points(n,node='USD_COMPILER/OUT_POINTS'):
    g=n.node(node).geometry();return np.array(g.pointFloatAttribValues('P')).reshape(-1,3),g
mod=None
A=scatter('A',src,'/World/ForestA')
A.parm('mask_source').set(1);A.parm('mask_noise_freq').set(0.12);A.parm('mstage_on').set(1);A.parm('mstage_res').set(512);mod=A.hdaModule()
# ---- 1 saving
prim=A.stage().GetPrimAtPath('/World/ForestA');data=prim.GetCustomDataByKey('arraytron:mask')
check('saving: the output prim carries the grid (name, area, size, data)',bool(data) and data['name']=='A_mask' and data['w']>=8 and data['h']>=8 and data['sx']>0 and data['sz']>0 and len(data['data'])>100,data and {k:v for k,v in data.items() if k!='data'})
grid=mod.mstage_decode(data)
check('saving: the grid is a 0 to 1 mask that varies (it is not flat)',grid.shape==(data['h'],data['w']) and float(grid.min())>=0 and float(grid.max())<=1 and float(grid.std())>0.05,(grid.shape,grid.min(),grid.max(),grid.std()))
P,g=points(A);u=(P[:,0]-data['cx'])/data['sx']+0.5;v=(P[:,2]-data['cz'])/data['sz']+0.5
w_now=np.array(g.pointFloatAttribValues('A_mask'))
check('saving: the grid agrees with the weight the node used at its own instances (within a few hundredths)',len(P)>50 and np.abs(mod.sample_image(grid,u,v,2)-w_now).max()<0.05,np.abs(mod.sample_image(grid,u,v,2)-w_now).max() if len(P) else 'no points')
pv=UsdGeom.PrimvarsAPI(prim).GetPrimvar('A_mask');vals=np.array(pv.Get()) if pv else None
check('saving: primvars:A_mask is on every instance and equals the weight the node used',vals is not None and len(vals)==len(instancer(A,'/World/ForestA').GetPositionsAttr().Get()) and np.allclose(vals,w_now,atol=1e-6),(None if vals is None else (len(vals),len(w_now))))
A.parm('mstage_name').set('my forest mask!')
check('saving: a typed name is cleaned to a proper primvar name',mod.mstage_name(A)=='my_forest_mask' and UsdGeom.PrimvarsAPI(A.stage().GetPrimAtPath('/World/ForestA')).GetPrimvar('my_forest_mask').IsDefined(),mod.mstage_name(A))
A.parm('mstage_name').set('mask');check('saving: a name the instancer already uses gets _mask added',mod.mstage_name(A)=='mask_mask',mod.mstage_name(A))
A.parm('mstage_name').set('');check('saving: no name means <node name>_mask',mod.mstage_name(A)=='A_mask',mod.mstage_name(A))
A.parm('mstage_on').set(0)
prim=A.stage().GetPrimAtPath('/World/ForestA')
check('saving: Save Mask off removes the grid and the primvar',not prim.GetCustomDataByKey('arraytron:mask') and not UsdGeom.PrimvarsAPI(prim).GetPrimvar('A_mask').IsDefined(),prim.GetCustomDataByKey('arraytron:mask'))
A.parm('mstage_on').set(1)
# ---- 2 the cache
p1=mod.mstage_payload(A);p2=mod.mstage_payload(A)
check('cache: the same grid object while nothing changed',p1 is p2)
A.parm('mask_noise_freq').set(0.3);p3=mod.mstage_payload(A)
check('cache: a changed mask is saved again',p3 is not p1 and p3['data']!=p1['data'])
A.parm('mask_noise_freq').set(0.12);A.parm('mstage_res').set(128);p4=mod.mstage_payload(A)
check('cache: the Cache Resolution sets the grid size',max(p4['w'],p4['h'])==128,(p4['w'],p4['h']))
A.parm('mstage_res').set(512)
# ---- 3 using it
B=scatter('B',A,'/World/ForestB',1500);B.parm('mask_source').set(6);B.parm('mup_name').set('A_mask');pB,gB=points(B,'USD_COMPILER/MASK_PROCESSOR')
d=A.stage().GetPrimAtPath('/World/ForestA').GetCustomDataByKey('arraytron:mask');gridA=mod.mstage_decode(d)
want=mod.sample_image(gridA,(pB[:,0]-d['cx'])/d['sx']+0.5,(pB[:,2]-d['cz'])/d['sz']+0.5,0)
got=np.array(gB.pointFloatAttribValues('maskweight'))
check('using: Upstream Mask reads the saved weight at every point of the node below',len(pB)>50 and np.allclose(got,want,atol=1e-6),(len(pB),np.abs(got-want).max() if len(pB) else None))
nB=len(instancer(B,'/World/ForestB').GetPositionsAttr().Get());check('using: the node below has no errors and made instances',not B.errors() and nB>50,(B.errors(),nB))
PB=np.array(instancer(B,'/World/ForestB').GetPositionsAttr().Get());uu=(PB[:,0]-d['cx'])/d['sx']+0.5;vv=(PB[:,2]-d['cz'])/d['sz']+0.5
check('using: the instances of the node below sit where the mask above is high',mod.sample_image(gridA,uu,vv,0).mean()>float(gridA.mean())+0.03,(mod.sample_image(gridA,uu,vv,0).mean(),float(gridA.mean())))
B.parm('mup_name').set('nothing_here');msg=''
try:B.node('USD_COMPILER/MASK_PROCESSOR').cook(force=True)
except hou.OperationFailed:pass
errs=' '.join(str(e) for e in B.errors())+' '.join(str(e) for e in B.node('USD_COMPILER/MASK_PROCESSOR').errors())
check('using: a missing name says which masks exist',('nothing_here' in errs) and ('A_mask' in errs),errs[:300])
B.parm('mup_name').set('')
try:B.node('USD_COMPILER/MASK_PROCESSOR').cook(force=True)
except hou.OperationFailed:pass
errs=' '.join(str(e) for e in B.node('USD_COMPILER/MASK_PROCESSOR').errors())+' '.join(str(e) for e in B.errors())
check('using: no name chosen explains how to choose one',('Upstream Mask' in errs) or ('choose' in errs),errs[:300])
B.parm('mup_name').set('A_mask')
B.parm('mup_outside').set(1);PP=np.array([[1e4,0,1e4],[-1e4,0,-1e4]]);edge=mod.mup_values(B,PP);B.parm('mup_outside').set(0);black=mod.mup_values(B,PP)
check('using: beyond the saved area the value is black, or the edge value',float(black.max())==0.0 and float(edge.max())>=0.0 and edge.shape==(2,),(black,edge))
# ---- 4 chains, several masks, combine
C=scatter('C',B,'/World/ForestC',900);C.parm('mask_source').set(1);C.parm('mstage_on').set(1);C.parm('mstage_name').set('noise_c');C.parm('mstage_res').set(128)
D=scatter('D',C,'/World/ForestD',900);md=D.hdaModule()
items=md.mup_menu(D)
names=[items[i] for i in range(0,len(items),2)]
check('chains: the menu lists the masks of every node above (A_mask is not saved by B: B saves nothing; C saves noise_c)','noise_c' in names and 'A_mask' in names,names)
D.parm('mask_source').set(6);D.parm('mup_name').set('A_mask noise_c');PD=np.array([[0.0,0,0],[3.0,0,3.0],[-8.0,0,6.0]])
D.parm('mup_combine').set(0);mul=md.mup_values(D,PD);D.parm('mup_combine').set(1);mx=md.mup_values(D,PD);D.parm('mup_combine').set(2);mn=md.mup_values(D,PD)
check('chains: Multiply, Maximum and Minimum of two upstream masks are ordered and in 0 to 1',np.all(mul<=mn+1e-9) and np.all(mn<=mx+1e-9) and mx.max()<=1.0,(mul,mn,mx))
check('chains: the info text lists both masks and stars the ones in use',md.mup_info(D).count('*')==2 and 'noise_c' in md.mup_info(D) and 'A_mask' in md.mup_info(D),md.mup_info(D))
# ---- 5 the offer (the OnInputChanged hook of the HDA runs it while the input is wired: the stand-ins below take the place of the windows)
md.mup_set_ui(force=True);asked=[];chosen=[];ANSWER=[0]
def ask(text,buttons):
    asked.append((text,buttons));return ANSWER[0]
def select(text,labels):
    chosen.append(labels);return (0,1)
md.mup_set_ui(ask=ask,select=select)
E=scatter('E',A,'/World/ForestE',300)                                  # wiring E below A runs the offer by itself
check('offer: wiring a node below one that saved a mask offers it, and Use This Mask makes it the Mask Source',len(asked)==1 and 'A_mask' in asked[0][0] and E.evalParm('mask_source')==6 and E.parm('mup_name').eval()=='A_mask',(asked,E.evalParm('mask_source')))
asked.clear();E.parm('mask_source').set(0);E.parm('mup_name').set('');again=md.mup_input_changed(E)
check('offer: the same mask is not offered twice',again==[] and not asked,(again,asked))
ANSWER[0]=1;asked.clear();F=scatter('F',A,'/World/ForestF',300)
check('offer: Not Now changes nothing',len(asked)==1 and F.evalParm('mask_source')==0 and F.evalParm('mup_ask')==1,(len(asked),F.evalParm('mask_source')))
asked.clear();manual=md.mup_find_button(F)
check('offer: Find Upstream Masks offers it again (also what was declined)',len(asked)==1 and manual==[],(asked,manual))
ANSWER[0]=2;asked.clear();G=scatter('G',A,'/World/ForestG',300)
check("offer: Don't Ask Again switches the offer off for that node",G.evalParm('mup_ask')==0 and G.evalParm('mask_source')==0 and len(asked)==1,(G.evalParm('mup_ask'),G.evalParm('mask_source')))
asked.clear();G.setInput(0,C)
check('offer: with the offer off nothing is asked',not asked,asked)
ANSWER[0]=0;asked.clear();H=scatter('H',C,'/World/ForestH',300)
check('offer: several masks above give a list to choose from, the chosen ones are used together',len(chosen)==1 and H.evalParm('mask_source')==6 and set(H.parm('mup_name').eval().split())=={'A_mask','noise_c'} and not asked,(H.parm('mup_name').eval(),len(chosen),asked))
asked.clear();chosen.clear();I=scatter('I',src,'/World/ForestI',300)
check('offer: no mask above, no window',not asked and not chosen and I.evalParm('mask_source')==0,(asked,chosen))
md.mup_set_ui(force=False);asked.clear();J=scatter('J',A,'/World/ForestJ',300)
check('offer: without the user interface the node never asks by itself',not asked and J.evalParm('mask_source')==0,asked)
md.mup_set_ui(force=False)
# ---- 6 info texts
check('info: Save Mask says what it saved',('A_mask' in mod.mstage_info(A)) and ('primvars' in mod.mstage_info(A)),mod.mstage_info(A))
print('ALL PASSED' if not fails else 'FAILED',passed[0],fails)
sys.exit(1 if fails else 0)
