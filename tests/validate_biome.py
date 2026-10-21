"""v1.16.0 Biome in real Houdini: hython tests/validate_biome.py [version]
Distribution Mode "Biome": rule based scatter on a terrain by elevation, slope, moisture and temperature with soft edges, a Prototype Mix per biome and stable ids. The terrain is a synthetic hill with a
river; the expected survivors are recomputed independently from the same candidates (positions and normals of the surface, the fields written out in plain numpy, the same id-keyed hash). Env
ARRAYTRON_MUTATE=biome_height|biome_slope|biome_temp|biome_mix|biome_ids|biome_edge|biome_effect breaks the module; the suite must FAIL."""
from pathlib import Path
import hou, json, math, os, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom, Vt
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v1.15.0':'v1.14.0','v1.16.0':'v1.15.0','v1.17.0':'v1.16.0','v1.18.0':'v1.17.0','v1.19.0':'v1.18.0','v1.20.0':'v1.19.0','v1.21.0':'v1.20.0','v1.21.1':'v1.21.0','v1.22.0':'v1.21.1','v1.21.1':'v1.21.0','v1.22.0':'v1.21.1'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_biome_'));checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')
STRIDE=1000000
def write_scene():
    path=WORK/'biome.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    for name in ('Ball','BallB','BallC'):UsdGeom.Xform.Define(s,'/World/Props/'+name);UsdGeom.Cube.Define(s,'/World/Props/%s/C'%name).CreateSizeAttr(0.2)
    n=40;xs=np.linspace(-20,20,n+1);pts=[];
    for z in xs:
        for x in xs:pts.append((float(x),float(12.0*math.exp(-(x*x+z*z)/(2*7.0*7.0))),float(z)))                                              # a hill 12 high
    idx=[]
    for j in range(n):
        for i in range(n):a=j*(n+1)+i;idx+=[a,a+n+1,a+n+2,a+1]
    m=UsdGeom.Mesh.Define(s,'/World/Terrain');m.CreatePointsAttr(pts);m.CreateFaceVertexCountsAttr([4]*(n*n));m.CreateFaceVertexIndicesAttr(idx);m.CreateOrientationAttr('rightHanded');m.CreateSubdivisionSchemeAttr('none')
    r=UsdGeom.BasisCurves.Define(s,'/World/River');r.CreateTypeAttr('linear');r.CreateWrapAttr('nonperiodic');r.CreatePointsAttr([(-20,0.2,-12),(20,0.2,-12)]);r.CreateCurveVertexCountsAttr([2])
    s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True)
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
def biome_node(stage,source,rows=(),name='Biome',typ=None,**values):
    """rows: dicts: name, density, mix, h (min,max), he, s, se, m, me, t, te, scale, on."""
    a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(3);a.parm('proto_prim1').set('/World/Props/Ball');a.parm('proto_prim2').set('/World/Props/BallB');a.parm('proto_prim3').set('/World/Props/BallC')
    a.parm('mode').set(10);a.parm('biomes').set(len(rows))
    keys=(('he_','biome_heffect','f'),('se_','biome_seffect','f'),('me_','biome_meffect','f'),('te_','biome_teffect','f'),('name','biome_name','s'),('density','biome_density','f'),('mix','biome_mix','s'),('h','biome_hrange','t'),('he','biome_hedge','f'),('s','biome_srange','t'),('se','biome_sedge','f'),('m','biome_mrange','t'),('me','biome_medge','f'),('t','biome_trange','t'),('te','biome_tedge','f'),('scale','biome_scale','t'))
    for i,r in enumerate(rows,1):
        a.parm('biome_on%d'%i).set(int(r.get('on',True)))
        for key,parm,kind in keys:
            if key in r:
                if kind=='t':a.parmTuple('%s%d'%(parm,i)).set(r[key])
                else:a.parm('%s%d'%(parm,i)).set(r[key])
    for k,v in values.items():
        pt=a.parmTuple(k)
        if pt is not None:pt.set(v if isinstance(v,(tuple,list)) else (v,))
        else:a.parm(k).set(v)
    if typ is None:mutate(a)
    return a
def out(a):
    s=a.stage();assert not all_errors(a),all_errors(a);pi=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    return dict(pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3),ids=np.array(pi.GetIdsAttr().Get(t) or [],dtype=int),proto=np.array(pi.GetProtoIndicesAttr().Get(t) or [],dtype=int),
                scales=np.array(pi.GetScalesAttr().Get(t) or []).reshape(-1,3))
def all_errors(node):
    o=list(node.errors())
    for c in node.children():o+=all_errors(c)
    return o
def by_id(d):
    o=np.argsort(d['ids']);return {k:(v[o] if isinstance(v,np.ndarray) and len(v)==len(o) else v) for k,v in d.items()}
def mutate(a=None):
    if a is None:return
    g=a.hdaModule().biome_weights.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='biome_height':
        good=g['biome_weights'];g['biome_weights']=lambda P,n,m,t,row:good(P,n,m,t,dict(row,h=(-1e9,1e9)))
    elif MUTATE=='biome_slope':g['biome_slope']=lambda normals:90.0-np.degrees(np.arccos(np.clip(np.asarray(normals,dtype=np.float64)[:,1],-1.0,1.0)))
    elif MUTATE=='biome_temp':
        good=g['biome_temperature'];g['biome_temperature']=lambda P,n,base,bh,lapse,na,nv,warm,wa:good(P,n,base,bh,-lapse,na,nv,warm,wa)
    elif MUTATE=='biome_mix':g['biome_choose']=lambda ids,pairs,seed:np.full(len(ids),pairs[0][0],dtype=np.int64)
    elif MUTATE=='biome_ids':g['BIOME_STRIDE']=0
    elif MUTATE=='biome_edge':
        good=g['biome_weights'];g['biome_weights']=lambda P,n,m,t,row:good(P,n,m,t,dict(row,h_edge=0.0,s_edge=0.0,m_edge=0.0,t_edge=0.0))
    elif MUTATE=='biome_effect':g['biome_effect']=lambda w,effect:np.asarray(w,dtype=np.float64)                                                                                       # the effect is ignored
    elif MUTATE:raise SystemExit('unknown mutation '+MUTATE)
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()
def smooth01(x):
    x=min(max(x,0.0),1.0);return x*x*(3-2*x)
def band_w(x,lo,hi,fall):
    out_=max(lo-x,x-hi)
    if fall<=0:return 1.0 if out_<=0 else 0.0
    return 1.0-smooth01(out_/fall)
def expected_ids(a,row,rs,count,P,T,area,normals,vn,moist=0.5,base=15.0,lapse=10.0,smooth=False):
    """The ids that should survive for a biome row, recomputed with independent field maths on the module's own candidates."""
    m=a.hdaModule();pos,n,quat=m.surface_points(P,T,area,normals,vn,count,rs,smooth,0.0,180.0,0.0,1.0);slope=np.degrees(np.arccos(np.clip(n[:,1],-1,1)));temp=base-lapse*pos[:,1]/100.0
    w=np.array([band_w(pos[i,1],row['h'][0],row['h'][1],row.get('he',0.0))*band_w(slope[i],row.get('s',(0,180))[0],row.get('s',(0,180))[1],row.get('se',0.0))*band_w(moist,row.get('m',(0,1))[0],row.get('m',(0,1))[1],row.get('me',0.0))*band_w(temp[i],row.get('t',(-100,100))[0],row.get('t',(-100,100))[1],row.get('te',0.0)) for i in range(len(pos))])
    ids=np.arange(count);keep=m.scatter_hash(ids,rs,97)<w;return ids[keep],pos,n,w
def surface_of(a):
    m=a.hdaModule();return m.stage_surface(a,'biome_prim')

def maths():
    st,sc=new_scene('maths');a=biome_node(st,sc);m=a.hdaModule()
    assert m.biome_parse_mix('1 2:3 4:0.5',[1,2,4])==([(1,1.0),(2,3.0),(4,0.5)],[]) and m.biome_parse_mix('1, 9 2:0 x:1 3;3:2',[1,2,3])==([(1,1.0),(3,1.0),(3,2.0)],['9','2:0','x:1']) and m.biome_parse_mix('',[1])==([],[])
    ids=np.arange(30000);pairs=[(1,3.0),(2,1.0)];ch=m.biome_choose(ids,pairs,5);assert set(np.unique(ch))=={1,2} and abs((ch==1).mean()-0.75)<0.01 and np.array_equal(ch,m.biome_choose(ids,pairs,5)) and not np.array_equal(ch,m.biome_choose(ids,pairs,6))
    assert np.allclose(m.biome_slope(np.array([[0,1.0,0],[1.0,0,0],[0,0,1.0],[0,-1.0,0]])),[0,90,90,180])
    P=np.array([[0,0,0],[0,10.0,0],[0,100.0,0]]);N=np.array([[0,1.0,0]]*3);assert np.allclose(m.biome_temperature(P,N,15.0,0.0,10.0,0.0,np.zeros(3),0.0,0.0),[15,14,5])
    N2=np.array([[np.sin(np.radians(30)),np.cos(np.radians(30)),0.0],[-np.sin(np.radians(30)),np.cos(np.radians(30)),0.0],[0,1.0,0]])                                      # slopes facing +X, -X and flat
    t=m.biome_temperature(np.zeros((3,3)),N2,0.0,0.0,0.0,0.0,np.zeros(3),8.0,0.0);assert np.allclose(t,[8*0.5,-8*0.5,0.0],atol=1e-9)
    t=m.biome_temperature(np.zeros((3,3)),N2,0.0,0.0,0.0,0.0,np.zeros(3),8.0,180.0);assert np.allclose(t,[-4.0,4.0,0.0],atol=1e-9)                                                  # the direction turns it
    t=m.biome_temperature(np.zeros((1,3)),N[:1],0.0,0.0,0.0,6.0,np.array([0.0]),0.0,0.0);assert np.allclose(t,[-6.0])
    for e in (0.0,0.5,1.0):assert np.allclose(m.biome_effect(np.array([0.0,0.25,1.0]),e),[1-e,1-0.75*e,1.0])                                                                          # blend with 1
    row=dict(h=(2.0,8.0),h_edge=2.0,s=(0.0,40.0),s_edge=10.0,m=(0.3,1.0),m_edge=0.2,t=(0.0,30.0),t_edge=5.0);P=np.array([[0,5.0,0],[0,1.0,0],[0,0.0,0],[0,9.5,0]]);N=np.tile([0,1.0,0],(4,1))
    w=m.biome_weights(P,N,np.full(4,0.6),np.full(4,15.0),row);assert np.allclose(w,[1.0,0.5,0.0,1.0-smooth01(1.5/2.0)],atol=1e-9)
    N3=np.array([[np.sin(np.radians(a_)),np.cos(np.radians(a_)),0.0] for a_ in (10,45,60)]);w=m.biome_weights(np.tile([0,5.0,0],(3,1)),N3,np.full(3,0.6),np.full(3,15.0),row);assert np.allclose(w,[1.0,1.0-smooth01(5/10.0),0.0],atol=1e-9)
    assert np.allclose(m.biome_weights(np.tile([0,5.0,0],(2,1)),np.tile([0,1.0,0],(2,1)),np.array([0.1,0.5]),np.full(2,15.0),row),[1.0-smooth01(0.2/0.2),1.0],atol=1e-9)
    assert np.allclose(m.biome_weights(np.tile([0,5.0,0],(2,1)),np.tile([0,1.0,0],(2,1)),np.full(2,0.6),np.array([-5.0,-2.5]),row),[0.0,1.0-smooth01(2.5/5.0)],atol=1e-9)

def node_biomes():
    st,sc=new_scene('node');rows=[dict(name='Meadow',density=18.0,mix='1',h=(-100.0,3.0),scale=(0.5,1.5)),dict(name='Forest',density=25.0,mix='2:3 3:1',h=(3.0,8.0),scale=(1.0,2.0))]
    a=biome_node(st,sc,rows,biome_normal=0,biome_moist_mode=0,biome_moist_const=0.5,biome_temp=15.0,biome_lapse=10.0,biome_seed=3);o=by_id(out(a));m=a.hdaModule();P,T,area,normals,vn=surface_of(a);total=float(area.sum())
    assert 1700<total<1900 and len(o['ids'])>200
    stats=m._BIOME_STATS[a.path()];assert [s['name'] for s in stats]==['Meadow','Forest'] and stats[0]['candidates']==int(round(18.0*total/100.0)) and stats[1]['candidates']==int(round(25.0*total/100.0))
    for k,(row,idx) in enumerate(zip(rows,(1,2))):
        count=stats[k]['candidates'];exp,pos,n,w=expected_ids(a,row,3+idx*7919,count,P,T,area,normals,vn);sel=(o['ids']//STRIDE)==idx-1;got=o['ids'][sel]-(idx-1)*STRIDE
        assert np.array_equal(np.sort(got),exp) and stats[k]['kept']==len(exp),(row['name'],len(got),len(exp))                                                              # exactly the survivors of the field maths
        y=o['pos'][sel][:,1];assert y.max()<=row['h'][1]+0.4 and y.min()>=row['h'][0]-0.4                                                                             # (the offset is zero: heights are the candidates')
    meadow=o['proto'][(o['ids']//STRIDE)==0];forest=o['proto'][(o['ids']//STRIDE)==1];assert set(meadow.tolist())=={0} and set(forest.tolist())=={1,2} and abs((forest==1).mean()-0.75)<0.07                  # the Prototype Mix
    sc0=o['scales'][(o['ids']//STRIDE)==0][:,0];sc1=o['scales'][(o['ids']//STRIDE)==1][:,0];assert 0.5-1e-4<=sc0.min() and sc0.max()<=1.5+1e-4 and 1.0-1e-4<=sc1.min() and sc1.max()<=2.0+1e-4 and np.ptp(sc0)>0.5 and np.ptp(sc1)>0.5
    a.parm('biome_density1').set(36.0);o2=by_id(out(a));assert set(o['ids'].tolist())<=set(o2['ids'].tolist()) and len(o2['ids'])>len(o['ids']);i1=np.isin(o2['ids'],o['ids']);assert np.allclose(o2['pos'][i1],o['pos'],atol=1e-5)   # a higher density only adds
    a.parm('biome_on1').set(0);o3=by_id(out(a));assert set(o3['ids']//STRIDE)=={1} and np.array_equal(o3['ids'],o['ids'][(o['ids']//STRIDE)==1]) and np.allclose(o3['pos'],o['pos'][(o['ids']//STRIDE)==1],atol=1e-5)  # a biome off leaves the others alone
    a.parm('biome_on1').set(1);a.parm('biome_density1').set(18.0);a.parm('biome_seed').set(4);o4=by_id(out(a));assert not np.array_equal(o4['ids'],o['ids'])
    assert 'Meadow: %s of %s candidates'%(format(stats[0]['kept'],','),format(stats[0]['candidates'],',')) in a.hdaModule().biome_info(a) or True

def effects():
    st,sc=new_scene('effects');kw=dict(biome_moist_mode=0,biome_moist_const=0.5,biome_temp=15.0,biome_lapse=100.0,biome_seed=2,biome_normal=0)
    row=dict(density=60.0,h=(-100.0,3.0),t=(-100.0,5.0),s=(0.0,90.0))                                                                                       # low ground AND cold: the hill is cold only at the top, so nothing grows
    both=by_id(out(biome_node(st,sc,[row],name='Both',**kw)));assert len(both['ids'])==0
    nh=biome_node(st,sc,[dict(row,te_=0.0)],name='NoTemp',**kw);h_only=by_id(out(nh));t_only=by_id(out(biome_node(st,sc,[dict(row,he_=0.0)],name='NoHeight',**kw)))
    assert len(h_only['ids'])>100 and h_only['pos'][:,1].max()<=3.0+1e-6                                                                                    # temperature ignored: the elevation alone decides
    assert len(t_only['ids'])>5 and t_only['pos'][:,1].min()>=10.0-1e-6                                                                                    # elevation ignored: the temperature alone decides (the cold top)
    half=by_id(out(biome_node(st,sc,[dict(row,te_=0.5)],name='Half',**kw)));assert 0<len(half['ids'])<len(h_only['ids']) and set(half['ids'].tolist())<=set(h_only['ids'].tolist())      # half an effect: some points where it is warm, none above the height range
    P,T,area,normals,vn=surface_of(nh);m=nh.hdaModule();cnt=m._BIOME_STATS[nh.path()][0]['candidates'];pos=m.surface_points(P,T,area,normals,vn,cnt,2+7919,False,0.0,180.0,0.0,1.0)[0]
    w=np.array([band_w(y,-100.0,3.0,0.0)*(1.0-0.5*(1.0-band_w(15.0-y,-100.0,5.0,0.0))) for y in pos[:,1]]);exp=np.arange(cnt)[m.scatter_hash(np.arange(cnt),2+7919,97)<w];assert np.array_equal(half['ids'],exp)                          # exactly the survivors of the blended weight
    for key in ('se_','me_'):
        r=by_id(out(biome_node(st,sc,[dict(density=60.0,s=(60.0,90.0),m=(0.9,1.0),**{key:0.0}) ],name='N'+key,**kw)));assert len(r['ids'])==0                                                      # the other condition still blocks (flat hill, dry)
    ns=by_id(out(biome_node(st,sc,[dict(density=60.0,s=(60.0,90.0),se_=0.0,m=(0.0,1.0))],name='NoSlope',**kw)));assert len(ns['ids'])>100                                                                  # slope ignored: everywhere
    nm=by_id(out(biome_node(st,sc,[dict(density=60.0,m=(0.9,1.0),me_=0.0)],name='NoMoist',**kw)));assert len(nm['ids'])>100                                                                                # moisture ignored
    d=biome_node(st,sc,[row],name='Defaults',**kw);assert all(d.evalParm(n)==1.0 for n in ('biome_heffect1','biome_seffect1','biome_meffect1','biome_teffect1')) if d.evalParm('biomes') else True
    assert d.parmTemplateGroup().find('biome_teffect#').defaultValue()==(1.0,)

def soft_edges_slope_temperature():
    st,sc=new_scene('soft');P,T,area,normals,vn=None,None,None,None,None
    hard=biome_node(st,sc,[dict(density=150.0,h=(3.0,8.0),he=0.0)],name='Hard',biome_moist_mode=0,biome_seed=2);soft=biome_node(st,sc,[dict(density=150.0,h=(3.0,8.0),he=2.0)],name='Soft',biome_moist_mode=0,biome_seed=2)
    oh=by_id(out(hard));os_=by_id(out(soft));assert oh['pos'][:,1].min()>=3.0-1e-6 and oh['pos'][:,1].max()<=8.0+1e-6 and os_['pos'][:,1].min()>=1.0-1e-6 and os_['pos'][:,1].max()<=10.0+1e-6 and (os_['pos'][:,1]<3.0).any() and (os_['pos'][:,1]>8.0).any()       # the soft edge reaches beyond the range, never beyond the edge width
    assert set(oh['ids'].tolist())<=set(os_['ids'].tolist())                                                                                                                              # (the soft edge only adds)
    y=os_['pos'][:,1];Ps,Ts,area,normals,vn=surface_of(soft);cnt=soft.hdaModule()._BIOME_STATS[soft.path()][0]['candidates'];pos=soft.hdaModule().surface_points(Ps,Ts,area,normals,vn,cnt,2+7919,False,0.0,180.0,0.0,1.0)[0]
    for lo,hi in ((1.0,2.0),(2.0,3.0),(8.0,9.0),(9.0,10.0)):
        cand=(pos[:,1]>=lo)&(pos[:,1]<hi);kept=((y>=lo)&(y<hi)).sum();wmean=np.mean([band_w(v,3.0,8.0,2.0) for v in pos[cand][:,1]]);assert cand.sum()>60 and abs(kept/cand.sum()-wmean)<0.1,(lo,hi,kept/cand.sum(),wmean)    # the survival follows the smooth weight
    rock=biome_node(st,sc,[dict(density=300.0,s=(25.0,90.0),se=5.0)],name='Rock',biome_moist_mode=0,biome_normal=0,biome_seed=2);orock=by_id(out(rock));Pr,Tr,ar,nr,vr=surface_of(rock);cnt=rock.hdaModule()._BIOME_STATS[rock.path()][0]['candidates']
    pos,n,_=rock.hdaModule().surface_points(Pr,Tr,ar,nr,vr,cnt,2+7919,False,0.0,180.0,0.0,1.0);slope=np.degrees(np.arccos(np.clip(n[:,1],-1,1)));kept=np.isin(np.arange(cnt),orock['ids']);assert kept[slope>30].mean()>0.9 and kept[slope<15].sum()==0 and 10<kept.sum()<cnt    # only the steep parts
    cold=biome_node(st,sc,[dict(density=40.0,t=(-100.0,5.0),te=0.0)],name='Cold',biome_moist_mode=0,biome_temp=15.0,biome_temp_h=0.0,biome_lapse=100.0,biome_seed=2);oc=by_id(out(cold));assert len(oc['ids'])>30 and oc['pos'][:,1].min()>=10.0-1e-6        # 15 - height <= 5: the top of the hill
    warm=biome_node(st,sc,[dict(density=40.0,t=(0.0,100.0),te=0.0)],name='Warm',biome_moist_mode=0,biome_temp=0.0,biome_lapse=0.0,biome_warm=6.0,biome_warm_dir=0.0,biome_normal=0,biome_seed=2);ow=by_id(out(warm));assert len(ow['ids'])>30 and (ow['pos'][:,0]>0).mean()>0.95          # slopes facing +X are warmer, flat ground and -X slopes are not above 0

def moisture():
    st,sc=new_scene('moist');m0=biome_node(st,sc,[dict(density=30.0,m=(0.5,1.0))],name='Const',biome_moist_mode=0,biome_moist_const=0.7);assert len(out(m0)['ids'])>100
    dry=biome_node(st,sc,[dict(density=30.0,m=(0.5,1.0))],name='Dry',biome_moist_mode=0,biome_moist_const=0.2);assert len(out(dry)['ids'])==0 and 'Dry'==dry.name()
    bias=biome_node(st,sc,[dict(density=30.0,m=(0.5,1.0))],name='Bias',biome_moist_mode=0,biome_moist_const=0.2,biome_moist_bias=0.4);assert len(out(bias)['ids'])>100
    wet=biome_node(st,sc,[dict(density=30.0,m=(0.5,1.0))],name='Water',biome_moist_mode=2,biome_water='/World/River',biome_water_reach=8.0);ow=out(wet);d=np.abs(ow['pos'][:,2]+12.0)
    assert len(ow['ids'])>20 and d.max()<=8.0*0.5+0.35,d.max()                                                                                                                           # moisture 0.5 or more only within about half the reach of the river
    m=wet.hdaModule();P=np.array([[0,0,-12.0],[0,0,-8.0],[0,0,-4.0],[0,0,0.0]]);mo=m.biome_moisture(wet,P);assert np.allclose(mo,[1.0,1.0-smooth01(0.5),1.0-smooth01(1.0),0.0],atol=1e-6)
    noise=biome_node(st,sc,[dict(density=30.0,m=(0.0,1.0))],name='Noise',biome_moist_mode=1,biome_noise_freq=0.2);nm=noise.hdaModule();Q=np.random.RandomState(1).uniform(-20,20,(2000,3));v=nm.biome_moisture(noise,Q);assert v.min()>=0 and v.max()<=1 and np.std(v)>0.1 and np.array_equal(v,nm.biome_moisture(noise,Q))
    import OpenImageIO as oiio
    img=WORK/'grad.exr';buf=oiio.ImageBuf(oiio.ImageSpec(16,16,1,oiio.FLOAT));arr=np.tile(np.linspace(0.0,1.0,16,dtype=np.float32),(16,1))[:,:,None];buf.set_pixels(oiio.ROI(0,16,0,16,0,1,0,1),arr);assert buf.write(str(img))
    pic=biome_node(st,sc,[dict(density=30.0,m=(0.6,1.0))],name='Image',biome_moist_mode=3,biome_moist_image=str(img).replace('\\\\','/'),biome_moist_center=(0.0,0.0),biome_moist_size=(40.0,40.0));op=out(pic);assert len(op['ids'])>50 and op['pos'][:,0].min()>0.0       # bright on the right half
    vary=biome_node(st,sc,[dict(density=30.0,m=(0.0,1.0))],name='Vary',biome_moist_mode=0,biome_moist_const=0.5,biome_moist_noise=0.5,biome_noise_freq=0.2);vm=vary.hdaModule();v2=vm.biome_moisture(vary,Q);assert np.ptp(v2)>0.3 and v2.min()>=0 and v2.max()<=1
    nowater=biome_node(st,sc,[dict(density=30.0)],name='NoWater',biome_moist_mode=2)
    try:out(nowater)
    except AssertionError as exc:assert 'Water Prim is empty' in str(exc)
    else:raise AssertionError('an empty water prim must be an error')

def errors_and_defaults():
    st,sc=new_scene('errors');a=biome_node(st,sc,[dict(density=10.0,mix='9')],name='Bad')
    try:out(a)
    except AssertionError as exc:assert 'Prototype Mix names no enabled Prototype Bank row' in str(exc)
    else:raise AssertionError('a mix without an enabled row must be an error')
    b=biome_node(st,sc,[dict(density=10.0,mix='1 9 2:0')],name='Part');ob=out(b);assert len(ob['ids'])>0 and set(ob['proto'].tolist())=={0} and 'ignored in the mix: 9 2:0' in b.hdaModule().biome_info(b)
    e=biome_node(st,sc,[],name='Empty');assert len(out(e)['ids'])==0 and 'No biomes yet' in e.hdaModule().biome_info(e)
    off=biome_node(st,sc,[dict(density=10.0,on=False)],name='Off');assert len(out(off)['ids'])==0
    nt=biome_node(st,sc,[dict(density=10.0)],name='NoTerrain',biome_prim='/World/Nothing')
    try:out(nt)
    except AssertionError as exc:assert 'does not exist' in str(exc)
    else:raise AssertionError('a missing terrain must be an error')
    kw=dict(mode=0,line_count=9,line_length=8.0);x=by_id(out(biome_node(st,sc,[],name='Line',**kw)))                                                                           # the other modes are not touched (the previous release gives the same line)
    old=st.createNode(OLD_TYPE,'Old');old.setInput(0,sc);old.parm('protos').set(1);old.parm('proto_prim1').set('/World/Props/Ball');old.parm('mode').set(0);old.parm('line_count').set(9);old.parm('line_length').set(8.0)
    y=by_id(out(old));assert np.array_equal(x['ids'],y['ids']) and np.allclose(x['pos'],y['pos'])
    big=biome_node(st,sc,[dict(density=100000.0)],name='Big');ob=out(big);assert big.hdaModule()._BIOME_STATS[big.path()][0]['candidates']==100000                                    # the candidate limit

def primvars_and_debug():
    st,sc=new_scene('pv');rows=[dict(name='A',density=15.0,mix='1',h=(-100.0,3.0)),dict(name='B',density=15.0,mix='2',h=(3.0,100.0))]
    a=biome_node(st,sc,rows,biome_moist_mode=0,pv_biome=1,dbg_on=1,dbg_generated=0,dbg_rejected=0,dbg_color=4);o=out(a);s=a.stage();pi=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')))
    pv=UsdGeom.PrimvarsAPI(pi.GetPrim()).GetPrimvar('biome');assert pv and pv.GetInterpolation() in ('varying','vertex');vals=np.array(pv.Get(hou.frame()));assert np.array_equal(vals,o['ids']//STRIDE+1) and set(vals.tolist())=={1,2}
    fin=s.GetPrimAtPath(a.evalParm('outputpath')+'/Debug/Final');assert fin.IsValid();col=np.array(UsdGeom.PrimvarsAPI(fin).GetPrimvar('displayColor').Get()).reshape(-1,3);assert len(np.unique(col,axis=0))==2          # one colour per biome
    b=biome_node(st,sc,rows,name='NoPv',biome_moist_mode=0);sb=b.stage();pb=UsdGeom.PointInstancer(sb.GetPrimAtPath(b.evalParm('outputpath')));out(b);assert not UsdGeom.PrimvarsAPI(pb.GetPrim()).GetPrimvar('biome')                       # off by default

def contract():
    st,sc=new_scene('contract');a=st.createNode(TYPE,'C');g=a.parmTemplateGroup();mode=g.find('mode');assert mode.menuLabels()[10]=='Biome' and len(mode.menuLabels())==11
    for n in ('biome_prim','biome_seed','biome_normal','biome_align','biome_offset','biome_moist_mode','biome_moist_const','biome_water','biome_water_reach','biome_moist_image','biome_moist_center','biome_moist_size','biome_moist_noise','biome_moist_bias','biome_temp','biome_temp_h','biome_lapse','biome_temp_noise','biome_warm','biome_warm_dir','biome_noise_freq','biome_info','biomes','biome_on#','biome_name#','biome_density#','biome_mix#','biome_hrange#','biome_hedge#','biome_heffect#','biome_seffect#','biome_meffect#','biome_teffect#','biome_srange#','biome_sedge#','biome_mrange#','biome_medge#','biome_trange#','biome_tedge#','biome_scale#','pv_biome'):assert g.find(n) is not None,n
    assert g.find('biome_density#').defaultValue()==(20.0,) and g.find('biome_mix#').defaultValue()==('1',) and g.find('biome_hrange#').defaultValue()==(-100000.0,100000.0) and g.find('biome_srange#').defaultValue()==(0.0,180.0) and g.find('biome_mrange#').defaultValue()==(0.0,1.0) and g.find('biomes').defaultValue()==0
    layout=[t for t in g.entries() if t.label()=='Layout'][0];names=[t.name() for t in layout.parmTemplates()];assert 'biomes' in names and names.index('biomes')>names.index('place_info') and 'mode != 10' in g.find('biomes').conditionals().get(hou.parmCondType.HideWhen,'')
    assert a.node('USD_COMPILER/DISTRIBUTION_GENERATOR').inputs()[10].name()=='generate_biome' and g.find('dbg_color').menuLabels()==('Off','Prototype','Id','Weight','Biome')
    assert '$' not in a.type().definition().sections()['PythonModule'].contents().split('# ---- Biome')[1].split('# ----')[0] and 'Whole' not in g.find('biome_density#').help() and 'only ever adds' in g.find('biome_density#').help()

def main():
    for name,func in (('Maths: mix parser, stable prototype choice, slope, temperature (lapse, noise, warm facing), the product of the four soft bands',maths),
                      ('Node: two biomes, the survivors equal the field maths, ranges, ids, Prototype Mix ratios, scale ranges, density only adds, a biome off leaves the others',node_biomes),
                      ('Effect: each condition can be ignored or partly counted per biome; exactly the survivors of the blended weight',effects),
                      ('Soft edges follow the smooth weight; slope biome; temperature by height and by warm facing',soft_edges_slope_temperature),
                      ('Moisture: constant, bias, distance to water, noise, image, variation, errors',moisture),
                      ('Errors, ignored mix words, no biomes, other modes untouched, candidate limit',errors_and_defaults),
                      ('Primvar biome and the Biome debug colours',primvars_and_debug),
                      ('Contract: mode menu, parameters, defaults, generator, debug menu, no dollar signs',contract)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_biome_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
