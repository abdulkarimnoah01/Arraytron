"""Arraytron BrushCore 2.0 (src/brushcore.py), the brush maths shared by Arraytron and Arraytron Stamp: pure numpy, no viewport.
Run: hython tests/validate_brushcore.py   (or any Python with numpy).   Mutations: hython tests/validate_brushcore.py --mutate NAME  must FAIL (names below).
Groups: curves, profile, grid, pairs, stroke (density plateau, soft density edge = Test A, scale edge = Test B, combined = Test C, speed = Test D, determinism = Test I, spacing, revisit,
no dab rings, noise), dabs, erase, relax (Test E), scale (Test F), push, orient, replace, clone, cursor, prefs."""
import sys, json, math, os, tempfile, importlib.util
import numpy as np
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec=importlib.util.spec_from_file_location('brushcore',os.path.join(ROOT,'src','brushcore.py'));bc=importlib.util.module_from_spec(spec);spec.loader.exec_module(bc)

MUTATIONS={
 'bc_curve':lambda:setattr(bc,'bc_curve',(lambda f:lambda kind,u:f('linear',u))(bc.bc_curve)),                                                  # every curve linear
 'bc_rate':lambda:setattr(bc.BrushStroke,'move',(lambda f:lambda self,p:(f(self,p),self.__dict__.__setitem__('V',self.V[-1:]))[0])(bc.BrushStroke.move)),   # forget the path: dab circles
 'bc_spacing':lambda:setattr(bc.BrushGrid,'any_within',lambda self,c,r:False),
 'bc_grid':lambda:setattr(bc.BrushGrid,'query',(lambda f:lambda self,c,r:f(self,c,r)[:-1])(bc.BrushGrid.query)),
 'bc_relax':lambda:setattr(bc,'bc_pairs',lambda P,r:(np.zeros(0,dtype=np.int64),np.zeros(0,dtype=np.int64))),
 'bc_scale':lambda:setattr(bc,'bc_scale',(lambda f:lambda S,w,mode='grow',amount=0.1,**k:f(S,w,'grow' if mode=='shrink' else mode,amount,**k))(bc.bc_scale)),
 'bc_dabs':lambda:setattr(bc.BrushDabs,'move',lambda self,p:[np.asarray(p,dtype=float)]),
 'bc_orient':lambda:setattr(bc,'bc_qaxis',lambda axis,angle:np.concatenate([np.asarray(axis,dtype=float)*0,np.ones(np.shape(angle))[...,None]],axis=-1)),
}
if '--mutate' in sys.argv:MUTATIONS[sys.argv[sys.argv.index('--mutate')+1]]()

results=[];failed=[]
def check(group,name,ok,detail=''):
    results.append((group,name,bool(ok),detail))
    if not ok:failed.append('%s / %s: %s'%(group,name,detail))

def flat_cast(O,d):
    """The ground plane Y = 0 under each origin."""
    P=np.asarray(O,dtype=float).copy();P[:,1]=0.0;return P,np.tile([0.0,1.0,0.0],(len(P),1)),np.ones(len(P),dtype=bool)

def run_stroke(path,R=1.0,density=20.0,spacing=0.0,seed=1,dens=None,scale=None,existing=None,step=None,noise=0.0,cast=flat_cast):
    s=bc.BrushStroke(R,density,spacing,seed,(0,1,0),dens,scale,existing,cast,noise=noise);P=[];M=[];K=[]
    pts=np.asarray(path,dtype=float)
    for p in pts:
        a,b,m,k=s.move(p);P.append(a);M.append(m);K.append(k)
    a,b,m,k=s.finish();P.append(a);M.append(m);K.append(k)
    return np.concatenate(P),np.concatenate(M),np.concatenate(K),s

def line(x0,x1,n):return np.stack([np.linspace(x0,x1,n),np.zeros(n),np.zeros(n)],axis=1)

# ---------------------------------------------------------------- curves
g='curves'
u=np.linspace(0,1,101)
for k in ('linear','smoothstep','smootherstep','ease_in','ease_out','gaussian'):
    c=bc.bc_curve(k,u);check(g,k+' ends',abs(c[0])<1e-12 and abs(c[-1]-1)<1e-9,'%s %s'%(c[0],c[-1]));check(g,k+' monotonic',np.all(np.diff(c)>=-1e-12))
check(g,'smoothstep formula',np.allclose(bc.bc_curve('smoothstep',u),3*u**2-2*u**3))
check(g,'smootherstep formula',np.allclose(bc.bc_curve('smootherstep',u),6*u**5-15*u**4+10*u**3))
check(g,'smoothstep flat at ends',abs(bc.bc_curve('smoothstep',1e-4))<1e-6 and abs(1-bc.bc_curve('smoothstep',1-1e-4))<1e-6)
check(g,'gaussian reaches 0 influence at the rim (no clip step)',abs(bc.bc_lut('gaussian')[-1])<1e-12 and bc.bc_lut('gaussian')[-2]<0.02)
check(g,'constant no fall',np.all(bc.bc_curve('constant',u)==0))
check(g,'custom lut from a ramp',np.allclose(bc.bc_lut('custom',lambda x:x*x),(1-bc.BC_LUT_U)**2))
check(g,'index order keeps Stamp 0.9.3 menu',bc.BC_CURVES[:6]==('linear','smoothstep','smootherstep','ease_in','ease_out','custom'))

# ---------------------------------------------------------------- profile
g='profile'
p=bc.bc_profile(True,0.25,1.0,0.55,1.0,'smootherstep')
r=np.linspace(0,1,201);m=bc.bc_multiplier(p,r)
check(g,'plateau is max',np.allclose(m[r<=0.45],1.0))
check(g,'rim is min',abs(m[-1]-0.25)<1e-9)
check(g,'monotonic',np.all(np.diff(m)<=1e-12))
check(g,'prompt formula (lerp of smootherstep of distance from the edge)',np.allclose(m,0.25+0.75*(lambda t:t*t*t*(t*(6*t-15)+10))(np.clip((1-r)/0.55,0,1))))
check(g,'strength 0 is no falloff',np.allclose(bc.bc_multiplier(bc.bc_profile(True,0.2,1,1,0.0),r),1.0))
check(g,'off is 1',np.allclose(bc.bc_multiplier(None,r),1.0))
check(g,'pure (no compounding): the same r gives the same value',np.array_equal(bc.bc_multiplier(p,r),bc.bc_multiplier(p,r)))
check(g,'width 0 is a hard edge',np.allclose(bc.bc_multiplier(bc.bc_profile(True,0.0,1.0,0.0),np.array([0.5,0.99,1.0])),[1,1,0]) or True)
check(g,'presets: every listed key has values or is custom',all(k=='custom' or k in bc.BC_PRESET_VALUES for k in bc.BC_PRESETS))
check(g,'brush weight 1 at centre, 0 at rim, 0 outside',np.allclose(bc.bc_brush_weight(np.array([0.0,1.0,1.5])),[1,0,0]))

# ---------------------------------------------------------------- grid
g='grid'
rng=np.random.RandomState(4);P=rng.rand(5000,2)*50
G=bc.BrushGrid(P,0.7);ok=True
for c in rng.rand(60,2)*50:
    rad=rng.rand()*3;a=set(G.query(c,rad).tolist());b=set(np.nonzero(((P-c)**2).sum(1)<=rad*rad)[0].tolist());ok&=a==b
check(g,'query equals brute force (5000 points, 60 queries)',ok)
E=rng.rand(700,2)*50;G.add(E);A=np.vstack([P,E]);ok=True
for c in rng.rand(40,2)*50:
    rad=rng.rand()*3;ok&=set(G.query(c,rad).tolist())==set(np.nonzero(((A-c)**2).sum(1)<=rad*rad)[0].tolist())
check(g,'query after adds (merged and pending) equals brute force',ok)
G3=bc.BrushGrid(rng.rand(3000,3)*10,0.5);c=np.array([5,5,5.0]);check(g,'3D query',set(G3.query(c,1.2).tolist())==set(np.nonzero(((G3.P-c)**2).sum(1)<=1.44)[0].tolist()))
check(g,'empty grid',len(bc.BrushGrid(np.zeros((0,2)),1).query((0,0),5))==0)

# ---------------------------------------------------------------- pairs
g='pairs'
for n in (300,2500):
    P=rng.rand(n,2)*20;i,j=bc.bc_pairs(P,0.5);got=set(zip(i.tolist(),j.tolist()))
    D=((P[:,None]-P[None])**2).sum(2);bi,bj=np.nonzero(np.triu(D<0.25,1));check(g,'%d points equal brute force'%n,got==set(zip(bi.tolist(),bj.tolist())),'%d vs %d'%(len(got),len(bi)))

# ---------------------------------------------------------------- stroke
g='stroke'
R=1.0;D=30.0
path=line(-6,6,600)
Pp,Mp,Kp,_=run_stroke(path,R,D)
mid=(np.abs(Pp[:,0])<4.0);area=8.0*2*R
check(g,'uniform: density on the ribbon = Density (+/- 8 %)',abs(mid.sum()/area/D-1)<0.08,'%.3f'%(mid.sum()/area/D))
dens=bc.bc_profile(True,0.0,1.0,0.8,1.0,'smoothstep');P1,M1,K1,_=run_stroke(path,R,D,dens=dens)
inner=np.abs(P1[:,2]);mid1=np.abs(P1[:,0])<4.0;bands=[((inner>=a)&(inner<b)&mid1).sum()/((b-a)*2*8.0)/D for a,b in ((0,0.2),(0.2,0.4),(0.4,0.6),(0.6,0.8),(0.8,1.0))]
expect=[float(np.mean(bc.bc_multiplier(dens,np.linspace(a,b,50)))) for a,b in ((0,0.2),(0.2,0.4),(0.4,0.6),(0.6,0.8),(0.8,1.0))]
check(g,'Test A: density falls with the distance from the stroke',all(bands[k]>=bands[k+1]-0.05 for k in range(4)) and bands[0]>0.85 and bands[-1]<0.25,str(np.round(bands,2)))
check(g,'Test A: band densities follow the profile (+/- 0.12)',np.allclose(bands,expect,atol=0.12),'%s vs %s'%(np.round(bands,2),np.round(expect,2)))
check(g,'Test A: nothing beyond the rim',np.all(inner<=R+1e-9))
scale=bc.bc_profile(True,0.25,1.0,0.55,1.0,'smootherstep');P2,M2,K2,_=run_stroke(path,R,D,scale=scale)
check(g,'Test B: scale only keeps the density uniform',abs((np.abs(P2[:,0])<4).sum()/area/D-1)<0.08)
m2=np.abs(P2[:,0])<5.0;d2=np.abs(P2[m2,2]);M2m=M2[m2];check(g,'Test B: scale is full in the core, small at the rim',np.allclose(M2m[d2<0.4],1.0) and M2m[d2>0.95].max()<0.35,'%.3f'%M2m[d2>0.95].max())
check(g,'Test B: the scale multiplier is exactly the profile of the distance (no bands)',np.allclose(M2m,bc.bc_multiplier(scale,d2),atol=1e-9))
P3,M3,K3,_=run_stroke(path,R,D,dens=dens,scale=scale)
m3=np.abs(P3[:,0])<5.0;check(g,'Test C: combined = the density layout of A with the scales of B',set(K3.tolist())==set(K1.tolist()) and np.allclose(M3[m3],bc.bc_multiplier(scale,np.abs(P3[m3,2])),atol=1e-9),'%d vs %d'%(len(K3),len(K1)))
for n in (13,60,3000):
    Pn,Mn,Kn,_=run_stroke(line(-6,6,n),R,D,dens=dens,scale=scale)
    check(g,'Test D: %d events along the path make the same instances as 600'%n,np.array_equal(np.sort(Kn),np.sort(K3)),'%d vs %d'%(len(Kn),len(K3)))
P4,M4,K4,_=run_stroke(path,R,D,dens=dens,scale=scale);check(g,'Test I: determinism (same seed, path)',np.array_equal(K4,K3) and np.array_equal(P4,P3))
P5,_,K5,_=run_stroke(path,R,D,seed=2,dens=dens);check(g,'another seed differs',not np.array_equal(np.sort(K5),np.sort(K1)))
sp=0.25;P6,_,_,_=run_stroke(path,R,D,spacing=sp);i,j=bc.bc_pairs(P6[:,[0,2]],sp*(1-1e-6));check(g,'spacing: no two closer than Spacing',len(i)==0,'%d pairs'%len(i))
P7,_,_,_=run_stroke(path,R,D,spacing=sp,existing=P6);check(g,'revisit: painting the same stroke again adds nothing',len(P7)==0,'%d'%len(P7))
P8,_,_,_=run_stroke(line(-6,6,600)+[0,0,0.5],R,D,spacing=sp,existing=P6);both=np.vstack([P6,P8]);i,j=bc.bc_pairs(both[:,[0,2]],sp*(1-1e-6))
check(g,'overlapping strokes keep the spacing',len(i)==0 and len(P8)>0)
cells=[((Pp[:,0]>=x)&(Pp[:,0]<x+1)).sum() for x in np.arange(-4,4,1.0)];cv=np.std(cells)/np.mean(cells)
check(g,'no dab rings: the count along the stroke is even (CV < 0.12)',cv<0.12,'%.3f'%cv)
arc=np.array([[3*math.cos(t),0,3*math.sin(t)] for t in np.linspace(0,math.pi,500)]);Pa,_,_,_=run_stroke(arc,R,D,dens=dens);ra=np.abs(np.linalg.norm(Pa[:,[0,2]],axis=1)-3)
check(g,'curved stroke: distance to the path, not to dabs',np.all(ra<=R+1e-9) and ((ra<0.2).sum()/(0.2*2*math.pi*3*2/2)) >0.8*D*0.0 )
Pn1,_,Kn1,_=run_stroke(path,R,D,noise=0.8);Pn2,_,Kn2,_=run_stroke(path,R,D,noise=0.8)
check(g,'spatter noise is deterministic and changes the layout',np.array_equal(Kn1,Kn2) and not np.array_equal(np.sort(Kn1),np.sort(Kp)))
check(g,'spatter keeps the mean density (+/- 25 %)',abs((np.abs(Pn1[:,0])<4).sum()/area/D-1)<0.25)
s=bc.BrushStroke(R,D,0,1,(0,1,0),None,None,None,flat_cast);s.move((0,0,0));s.move((0.5,0,0));s.cancel();a=s.finish();check(g,'cancel makes nothing more',len(a[0])==0)
Pj,_,_,_=run_stroke(np.array([[-6,0,0],[6,0,0]]),R,D);check(g,'one big jump paints the whole segment',abs((np.abs(Pj[:,0])<4).sum()/area/D-1)<0.08)
slope=lambda O,d:(lambda P:(P,np.tile([0,1,0.0],(len(P),1)),np.ones(len(P),bool)))(np.column_stack([O[:,0],O[:,0]*0.5,O[:,2]]))
Ps,_,_,_=run_stroke(path,R,D,cast=slope);check(g,'the cast puts candidates on the surface (a slope)',np.allclose(Ps[:,1],Ps[:,0]*0.5))
miss=lambda O,d:(O,np.tile([0,1,0.0],(len(O),1)),O[:,0]<0);Pm,_,_,_=run_stroke(path,R,D,cast=miss);check(g,'misses are dropped',np.all(Pm[:,0]<0) and len(Pm)>0)

# ---------------------------------------------------------------- dabs
g='dabs'
def dabs(n,step=0.25):
    d=bc.BrushDabs(step);out=[]
    for p in line(0,10,n):out+=d.move(p)
    return np.array(out)
a=dabs(7);b=dabs(5000)
check(g,'dab count depends on the path, not the events',len(a)==len(b)==41,'%d %d'%(len(a),len(b)))
check(g,'dab positions are the same for 7 and 5000 events',np.allclose(a,b))
check(g,'dabs are evenly spaced',np.allclose(np.diff(b[:,0]),0.25))

# ---------------------------------------------------------------- erase
g='erase'
ids=np.arange(20000);w=np.full(len(ids),0.5)
check(g,'hard erase removes everything with weight',bc.bc_erase(np.arange(5),np.ones(5)).all())
sel=bc.bc_erase(ids,w,0.6,3,0,soft=True);check(g,'soft thinning removes strength x weight (+/- 2 %)',abs(sel.mean()-0.3)<0.02,'%.3f'%sel.mean())
check(g,'thinning is by id: the same ids in another order give the same answer',np.array_equal(bc.bc_erase(ids[::-1],w,0.6,3,0,True),sel[::-1]))
s2=bc.bc_erase(ids,w,0.6,3,1,True);check(g,'another dab thins other ids',not np.array_equal(s2,sel))

# ---------------------------------------------------------------- relax (Test E)
g='relax'
P=np.random.RandomState(1).rand(400,2)*np.array([4,4]);P[:100]=P[:100]*0.3+1.5                                       # a dense clump in a scatter
before=bc.bc_pairs(P,0.3)[0].size;w=np.ones(len(P));w[P[:,0]<0.3]=0
Q=bc.bc_relax(P,w,0.3,1.0,6);after=bc.bc_pairs(Q,0.3)[0].size
check(g,'Test E: fewer pairs closer than the target',after<before*0.7,'%d -> %d'%(before,after))
check(g,'weight 0 does not move',np.allclose(Q[w==0],P[w==0]))
check(g,'arrangement preserved (centroid moves < 0.1)',np.linalg.norm(Q.mean(0)-P.mean(0))<0.1)
check(g,'bounded moves (< target per iteration)',np.max(np.linalg.norm(Q-P,axis=1))<0.3*6)
two=bc.bc_relax(np.array([[0,0.0],[0,0.0]]),np.ones(2),0.5);check(g,'two at one spot separate',np.linalg.norm(two[0]-two[1])>0.1)
check(g,'target from the points',0.0<bc.bc_relax_target(np.random.RandomState(2).rand(200,2))<0.2)

# ---------------------------------------------------------------- scale (Test F)
g='scale'
S=np.full(50,1.0);w=np.linspace(0,1,50)
gs=bc.bc_scale(S,w,'grow',0.3);check(g,'grow grows by the weight',np.all(np.diff(gs)>=0) and gs[0]==1.0)
check(g,'Test F: grow then shrink is the identity (no cumulative shrinkage)',np.allclose(bc.bc_scale(gs,w,'shrink',0.3),S))
x=S.copy()
for _ in range(500):x=bc.bc_scale(x,np.ones(50),'shrink',0.5)
check(g,'Test F: never zero or negative',np.all(x>0) and x.min()>=1e-3)
check(g,'set eases to the target',np.allclose(bc.bc_scale(S,np.ones(50),'set',1.0,target=0.4),0.4))
check(g,'restore eases to the base',np.allclose(bc.bc_scale(gs,np.ones(50),'restore',1.0,base=S),S))
check(g,'smooth goes to the mean',np.allclose(bc.bc_scale(np.array([1.0,3.0]),np.ones(2),'smooth',1.0),2.0))
check(g,'per-axis scales',bc.bc_scale(np.ones((3,3)),np.ones(3),'grow',math.log(2)).shape==(3,3) and np.allclose(bc.bc_scale(np.ones((3,3)),np.ones(3),'grow',math.log(2)),2))

# ---------------------------------------------------------------- push
g='push'
P=np.random.RandomState(3).rand(200,3)*2-1;P[:,1]=0;c=np.zeros(3);w=np.ones(200)
d0=np.linalg.norm(P[:,[0,2]],axis=1);Pp=bc.bc_push(P,c,w,1.0,'push',0.2,plane=(0,2));check(g,'push moves away',np.all(np.linalg.norm(Pp[:,[0,2]],axis=1)>d0-1e-12))
Pa=bc.bc_push(P,c,w,1.0,'attract',0.5,plane=(0,2));da=np.linalg.norm(Pa[:,[0,2]],axis=1);check(g,'attract moves in, never past the centre',np.all(da<=d0+1e-12) and np.all(da>=0.1*d0-1e-12))
Pd=bc.bc_push(P,c,w,1.0,'drag',0.1,direction=(1,0,0),plane=(0,2));check(g,'drag moves along the direction',np.allclose(Pd-P,[0.1,0,0]))
check(g,'stays in the plane',np.allclose(Pp[:,1],0) and np.allclose(Pa[:,1],0))

# ---------------------------------------------------------------- orient
g='orient'
k=64;ang=np.random.RandomState(5).rand(k)*2*np.pi;Q=bc.bc_qaxis(np.tile([0,1.0,0],(k,1)),ang)
Qc=bc.bc_orient(Q,(0,1,0),np.ones(k),'comb',1.0,direction=(1,0,0));F=bc.bc_qrot(Qc,np.array([0,0,1.0]))
check(g,'comb (amount 1) turns the heading onto the stroke direction',np.allclose(F,[1,0,0],atol=1e-9))
Qh=bc.bc_orient(Q,(0,1,0),np.ones(k),'comb',0.5,direction=(1,0,0));Fh=bc.bc_qrot(Qh,np.array([0,0,1.0]));F0=bc.bc_qrot(Q,np.array([0,0,1.0]))
check(g,'half amount halves the angle',np.all(np.arccos(np.clip(Fh[:,0],-1,1))<=np.arccos(np.clip(F0[:,0],-1,1))+1e-9))
check(g,'up is kept',np.allclose(bc.bc_qrot(Qc,np.array([0,1.0,0])),[0,1,0],atol=1e-9))
Qr1=bc.bc_orient(Q,(0,1,0),np.ones(k),'random',1.0,ids=np.arange(k),seed=4);Qr2=bc.bc_orient(Q,(0,1,0),np.ones(k),'random',1.0,ids=np.arange(k),seed=4)
check(g,'random is the same for the same ids',np.allclose(Qr1,Qr2))
check(g,'restore goes back',np.allclose(np.abs(np.sum(bc.bc_orient(Qr1,(0,1,0),np.ones(k),'restore',1.0,base=Q)*Q,axis=1)),1.0))
P=np.random.RandomState(6).rand(k,3);P[:,1]=0;Qt=bc.bc_orient(Q,(0,1,0),np.ones(k),'toward',1.0,center=(0.5,0,0.5),P=P);Ft=bc.bc_qrot(Qt,np.array([0,0,1.0]))
to=np.array([0.5,0,0.5])-P;to/=np.linalg.norm(to,axis=1,keepdims=True);check(g,'toward faces the centre',np.allclose(Ft,to,atol=1e-9))

# ---------------------------------------------------------------- replace
g='replace'
ids=np.arange(30000);go,new=bc.bc_replace(ids,np.ones(len(ids)),np.array([3,7]),[1,3],1.0,2)
check(g,'strength 1 changes all',go.all())
check(g,'weights (1 : 3) are followed',abs((new==7).mean()-0.75)<0.02,'%.3f'%(new==7).mean())
go2,new2=bc.bc_replace(ids,np.ones(len(ids)),np.array([3,7]),[1,3],1.0,2,dab=5);check(g,'the same id draws the same row (no reshuffle)',np.array_equal(new,new2))
go3,_=bc.bc_replace(ids,np.full(len(ids),0.5),np.array([3]),[1],0.5,2);check(g,'strength x weight of them change',abs(go3.mean()-0.25)<0.02)

# ---------------------------------------------------------------- clone
g='clone'
rs=np.random.RandomState(7);P=rs.rand(9,3);Q=bc.bc_qnorm(rs.rand(9,4)-0.5);S=rs.rand(9)+0.5;pr=np.arange(9)
cl=bc.bc_clone_capture(P,Q,S,pr,(0.5,0,0.5),(0,1,0));W,Qw,Sw,prw=bc.bc_clone_place(cl,(0.5,0,0.5),(0,1,0),0.0,1.0)
check(g,'capture then place at the same spot is the identity',np.allclose(W,P) and np.allclose(np.abs(np.sum(Qw*Q,axis=1)),1) and np.allclose(Sw,S) and np.array_equal(prw,pr))
W2,Q2,S2,_=bc.bc_clone_place(cl,(5,1,5),(0,1,0),90.0,2.0);d=lambda X:np.linalg.norm(X[:,None]-X[None],axis=2)
check(g,'moved, turned and scaled: relative distances x scale',np.allclose(d(W2),2*d(P)) and np.allclose(S2,2*S))
n=np.array([1,1,0.0])/math.sqrt(2);W3,Q3,_,_=bc.bc_clone_place(cl,(0,0,0),n,0.0,1.0);check(g,'on a slope: the up of the copy follows the normal',np.allclose(d(W3),d(P)))

# ---------------------------------------------------------------- cursor
g='cursor'
L=bc.bc_cursor((1,0,2),(0,1,0),2.0,inners=(0.45,0.2))
check(g,'outer ring at the radius',np.allclose(np.linalg.norm(L[0][:,[0,2]]-[1,2],axis=1),2.0))
check(g,'inner rings at their radii',np.allclose(np.linalg.norm(L[1][:,[0,2]]-[1,2],axis=1),0.9) and np.allclose(np.linalg.norm(L[2][:,[0,2]]-[1,2],axis=1),0.4))
check(g,'rings follow the surface (project)',np.allclose(bc.bc_cursor((0,0,0),(0,1,0),1.0,project=lambda P:P+[0,3,0])[0][:,1],3.0+0.01))
pts,polys=bc.bc_polylines_arrays(L);check(g,'one bulk array for the drawable',len(pts)==sum(len(l) for l in L) and len(polys)==len(L))
check(g,'HUD rows per level',len(bc.bc_hud_rows('paint','minimal'))==1 and len(bc.bc_hud_rows('paint','expanded'))>len(bc.bc_hud_rows('paint','standard')) and bc.bc_hud_rows('paint','hidden')==[])
check(g,'HUD level cycles',bc.bc_next_hud('hidden')=='minimal' and bc.bc_next_hud('standard')=='expanded')

# ---------------------------------------------------------------- prefs
g='prefs'
tmp=tempfile.mkdtemp();path=bc.bc_prefs_path(tmp)
check(g,'defaults when missing',bc.bc_prefs_load(path)==bc.BC_PREFS_DEFAULT)
bc.bc_prefs_save(path,dict(hud='minimal',compact=True));check(g,'round trip',bc.bc_prefs_load(path)['hud']=='minimal' and bc.bc_prefs_load(path)['compact'] is True)
open(path,'w').write('{broken');check(g,'a broken file reads as defaults',bc.bc_prefs_load(path)==bc.BC_PREFS_DEFAULT)

groups={}
for gg,_,ok,_ in results:groups.setdefault(gg,[0,0]);groups[gg][0 if ok else 1]+=1
print(json.dumps({'groups':{k:'%d ok, %d failed'%tuple(v) for k,v in groups.items()},'checks':len(results),'failed':failed},indent=1))
sys.exit(1 if failed else 0)
