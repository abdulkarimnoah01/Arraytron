"""v1.14.0 Rows in real Houdini: hython tests/validate_rows.py [version]
The Line, Circle and Curve modes scatter along one path; Rows lays the path out in several parallel rows (next to each other, concentric rings, copies of the curve pushed to the side) and can randomise
between them. Expected values come from independent geometry (cross products, polyline distances, radii). Env ARRAYTRON_MUTATE=rows_side|rows_ids|rows_center|rows_random|rows_stagger|rows_tangent breaks the
module; the suite must FAIL."""
from pathlib import Path
import hou, json, math, os, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
SLIDER=tuple(int(x) for x in VID[1:].split('.'))>=(1,18,0)                                                          # v1.18.0: Stagger Rows is a slider (a fraction of the gap), the old tick meant 0.5
PREVIOUS={'v1.14.0':'v1.13.0','v1.15.0':'v1.14.0','v1.16.0':'v1.15.0','v1.17.0':'v1.16.0','v1.18.0':'v1.17.0','v1.19.0':'v1.18.0','v1.15.0':'v1.14.0'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_rows_'));checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')
STRIDE=20000000
def write_scene():
    path=WORK/'rows.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    UsdGeom.Xform.Define(s,'/World/Props/Ball');UsdGeom.Cube.Define(s,'/World/Props/Ball/C').CreateSizeAttr(0.2)
    c=UsdGeom.BasisCurves.Define(s,'/World/Path');c.CreateTypeAttr('linear');c.CreateWrapAttr('nonperiodic');c.CreatePointsAttr([(0,0,0),(6,0,0),(6,0,6)]);c.CreateCurveVertexCountsAttr([3])
    s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True)
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
def scatter(stage,source,name='Rows',typ=None,**values):
    a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Ball')
    for k,v in values.items():
        pt=a.parmTuple(k)
        if pt is not None:pt.set(v if isinstance(v,(tuple,list)) else (v,))
        else:a.parm(k).set(v)
    if typ is None:mutate(a)
    return a
def out(a):
    s=a.stage();assert not all_errors(a),all_errors(a);pi=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    q=pi.GetOrientationsAttr().Get(t) or []
    return dict(pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3),ids=np.array(pi.GetIdsAttr().Get(t) or [],dtype=int),quat=np.array([[x.GetImaginary()[0],x.GetImaginary()[1],x.GetImaginary()[2],x.GetReal()] for x in q]).reshape(-1,4))
def all_errors(node):
    o=list(node.errors())
    for c in node.children():o+=all_errors(c)
    return o
def by_id(d):
    o=np.argsort(d['ids']);return {k:(v[o] if isinstance(v,np.ndarray) and len(v)==len(o) else v) for k,v in d.items()}
def mutate(a=None):
    if a is None:return
    g=a.hdaModule().rows_expand.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='rows_side':
        good=g['rows_directions'];g['rows_directions']=lambda *a_,**k:(lambda r:(r[0],r[0]))(good(*a_,**k))                                        # sideways along the path
    elif MUTATE=='rows_ids':
        g['ROWS_ID_STRIDE']=0
    elif MUTATE=='rows_center':
        g['rows_offsets']=lambda count,spacing,centered:np.arange(int(count))*float(spacing)
    elif MUTATE=='rows_random':
        good=g['rows_expand'];g['rows_expand']=lambda P,ids,along,side,count,spacing,centered,random,shift,stagger,seed:good(P,ids,along,side,count,spacing,centered,0.0,shift,stagger,seed)
    elif MUTATE=='rows_stagger':
        good=g['rows_expand'];g['rows_expand']=lambda P,ids,along,side,count,spacing,centered,random,shift,stagger,seed:good(P,ids,along,side,count,spacing,centered,random,shift,False,seed)
    elif MUTATE=='rows_tangent':
        good=g['rows_directions'];g['rows_directions']=lambda mode,P,line_axis=0,line_direction=(1.0,0.0,0.0),circle_plane=0,pathdir=None:good(mode,P,line_axis,line_direction,circle_plane,None)
    elif MUTATE:raise SystemExit('unknown mutation '+MUTATE)
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()
def poly_distance(p,poly):
    best=1e9
    for a,b in zip(poly[:-1],poly[1:]):
        ab=b-a;u=min(max(float((p-a)@ab)/float(ab@ab),0.0),1.0);best=min(best,float(np.linalg.norm(p-(a+u*ab))))
    return best

def maths():
    st,sc=new_scene('maths');a=st.createNode(TYPE,'M');m=a.hdaModule();mutate(a)
    assert np.allclose(m.rows_offsets(3,0.5,True),[-0.5,0,0.5]) and np.allclose(m.rows_offsets(4,1.0,True),[-1.5,-0.5,0.5,1.5]) and np.allclose(m.rows_offsets(3,0.5,False),[0,0.5,1.0]) and np.allclose(m.rows_offsets(1,2.0,True),[0.0])
    P=np.array([[1.0,0,0],[2.0,0,0]]);al,sd=m.rows_directions(0,P,0);assert np.allclose(al,[[1,0,0]]*2) and np.allclose(sd,[[0,0,-1]]*2)                    # up x along
    al,sd=m.rows_directions(0,P,2);assert np.allclose(al,[[0,0,1]]*2) and np.allclose(sd,[[1,0,0]]*2)
    al,sd=m.rows_directions(0,P,1);assert np.allclose(al,[[0,1,0]]*2) and np.allclose(sd,[[1,0,0]]*2)                                                      # a vertical line: sideways falls back to X
    d=np.array([1.0,0,1.0]);al,sd=m.rows_directions(0,P,3,d);assert np.allclose(al,[d/np.linalg.norm(d)]*2) and np.allclose(np.linalg.norm(sd,axis=1),1) and np.allclose((sd*al).sum(axis=1),0) and np.allclose(sd[:,1],0)
    C=np.array([[3.0,0,0],[0,0,4.0],[-2.0,0,0]]);al,sd=m.rows_directions(3,C,circle_plane=0);assert np.allclose(sd,[[1,0,0],[0,0,1],[-1,0,0]]) and np.allclose((al*sd).sum(axis=1),0) and np.allclose(np.cross(sd,al),[[0,1,0]]*3)      # XZ ring: radial and counter-clockwise tangent
    W=np.array([[0.0,3.0,0.0]]);al,sd=m.rows_directions(3,W,circle_plane=1);assert np.allclose(sd,[[0,1,0]])                                                                                             # XY ring
    al,sd=m.rows_directions(3,np.zeros((1,3)),circle_plane=0);assert np.allclose(np.linalg.norm(sd,axis=1),1)                                                                                             # the centre point
    T=np.array([[1.0,0,0],[0,0,1.0],[0,1.0,0]]);al,sd=m.rows_directions(4,np.zeros((3,3)),pathdir=T);assert np.allclose(al,T) and np.allclose(sd[0],[0,0,-1]) and np.allclose(sd[1],[1,0,0]) and np.allclose(np.linalg.norm(sd,axis=1),1)
    ids=np.arange(5);P=np.array([[x,0,0] for x in (0.0,1.0,2.0,4.0,5.0)]);assert abs(m.rows_gap(P,ids)-1.0)<1e-12 and m.rows_gap(P[:1],ids[:1])==0.0 and abs(m.rows_gap(P[::-1],ids[::-1])-1.0)<1e-12   # the median gap in id order
    al=np.tile([1.0,0,0],(5,1));sd=np.tile([0,0,-1.0],(5,1));src,pos,nid,row=m.rows_expand(P,ids,al,sd,3,0.5,True,0.0,0.0,False,1)
    assert len(src)==15 and row.tolist()==[0]*5+[1]*5+[2]*5 and np.array_equal(nid,np.concatenate([ids,ids+STRIDE,ids+2*STRIDE])) and np.allclose(pos[:5],P+np.array([0,0,0.5])) and np.allclose(pos[5:10],P) and np.allclose(pos[10:],P-np.array([0,0,0.5]))
    one=m.rows_expand(P,ids,al,sd,1,0.5,True,0.0,0.0,False,1);assert np.allclose(one[1],P) and np.array_equal(one[2],ids)                                                                                  # one row is the path
    _,r1,i1,w1=m.rows_expand(P,ids,al,sd,2,0.8,False,1.0,0.0,False,7);_,r2,i2,w2=m.rows_expand(P,ids,al,sd,4,0.8,False,1.0,0.0,False,7)
    assert np.allclose(r1,r2[:len(r1)]) and np.array_equal(i1,i2[:len(i1)])                                                                                                                                  # a point keeps its offset when rows are added
    lat=r1[:,2]+(w1*0.8)[:]*0;jit=r1[:,2]-(-(w1*0.8));assert np.all(np.abs(jit)<=0.5*1.0*0.8+1e-12) and np.ptp(jit)>0.2                                                                                       # sideways jitter within +/- random * spacing / 2
    _,rs,_,_=m.rows_expand(P,ids,al,sd,1,0.5,True,0.0,1.0,False,3);assert np.all(np.abs(rs[:,0]-P[:,0])<=0.5*1.0*1.0+1e-12) and np.ptp(rs[:,0]-P[:,0])>0.2 and np.allclose(rs[:,2],0)                              # along jitter within +/- shift * gap / 2
    _,st_,_,rw=m.rows_expand(P,ids,al,sd,3,0.5,False,0.0,0.0,0.5 if SLIDER else True,1);assert np.allclose(st_[rw==1][:,0],P[:,0]+0.5) and np.allclose(st_[rw==0][:,0],P[:,0]) and np.allclose(st_[rw==2][:,0],P[:,0])               # odd rows shifted by half a gap

def line_rows():
    st,sc=new_scene('line');kw=dict(mode=0,line_count=10,line_length=9.0,line_center=1)
    b=by_id(out(scatter(st,sc,name='Base',**kw)));a=scatter(st,sc,name='Three',rows_count=3,rows_spacing=0.5,**kw);o=by_id(out(a));assert len(o['ids'])==30
    assert set(o['ids'].tolist())=={int(i)+k*STRIDE for i in b['ids'] for k in (0,1,2)}
    for k,z in ((0,0.5),(1,0.0),(2,-0.5)):
        sel=(o['ids']//STRIDE)==k;assert np.allclose(o['pos'][sel][:,2],z,atol=1e-6) and np.allclose(o['pos'][sel][:,0],b['pos'][:,0],atol=1e-6) and np.allclose(o['pos'][sel][:,1],0,atol=1e-6),k        # centred rows next to each other
    u=by_id(out(scatter(st,sc,name='Side',rows_count=3,rows_spacing=0.5,rows_center=0,**kw)));assert sorted(set(np.round(u['pos'][:,2],6)))==[-1.0,-0.5,0.0] and set(u['ids']//STRIDE)=={0,1,2}       # the path is the first row
    four=by_id(out(scatter(st,sc,name='Four',rows_count=4,rows_spacing=0.5,rows_center=0,**kw)));assert set(u['ids'].tolist())<=set(four['ids'].tolist()) and len(four['ids'])==40
    for i in u['ids'][:5]:assert np.allclose(u['pos'][u['ids']==i],four['pos'][four['ids']==i],atol=1e-6)                                                                                                   # more rows never move the others
    r=by_id(out(scatter(st,sc,name='Rand',rows_count=3,rows_spacing=1.0,rows_random=1.0,rows_seed=4,rows_center=0,**kw)))
    exp=np.array([-(i//STRIDE)*1.0 for i in r['ids']]);jit=r['pos'][:,2]-exp;assert np.all(np.abs(jit)<=0.5+1e-6) and np.ptp(jit)>0.5 and np.allclose(r['pos'][:,0],np.tile(b['pos'][:,0],3),atol=1e-6)         # random across each row, not along
    r2=by_id(out(scatter(st,sc,name='Rand2',rows_count=3,rows_spacing=1.0,rows_random=1.0,rows_seed=4,rows_center=0,**kw)));assert np.allclose(r['pos'],r2['pos'])                                           # deterministic
    r3=by_id(out(scatter(st,sc,name='Rand3',rows_count=3,rows_spacing=1.0,rows_random=1.0,rows_seed=5,rows_center=0,**kw)));assert not np.allclose(r['pos'],r3['pos'],atol=1e-3)                              # the seed
    sh=by_id(out(scatter(st,sc,name='Shift',rows_count=2,rows_spacing=1.0,rows_shift=1.0,rows_center=0,**kw)));d=sh['pos'][:,0]-np.tile(b['pos'][:,0],2);assert np.all(np.abs(d)<=0.5*1.0+1e-6) and np.ptp(d)>0.3     # along: within half a gap (1.0)
    sg=by_id(out(scatter(st,sc,name='Stagger',rows_count=3,rows_spacing=1.0,rows_stagger=0.5 if SLIDER else 1,rows_center=0,**kw)));rows=sg['ids']//STRIDE;assert np.allclose(sg['pos'][rows==1][:,0],b['pos'][:,0]+0.5,atol=1e-6) and np.allclose(sg['pos'][rows==2][:,0],b['pos'][:,0],atol=1e-6)
    if SLIDER:
        for amount in (0.25,0.75,1.0):                                                                                                                  # the slider is the fraction of the gap
            q=by_id(out(scatter(st,sc,name='Stag%d'%int(amount*100),rows_count=3,rows_spacing=1.0,rows_stagger=amount,rows_center=0,**kw)));rq=q['ids']//STRIDE
            assert np.allclose(q['pos'][rq==1][:,0],b['pos'][:,0]+amount,atol=1e-6) and np.allclose(q['pos'][rq==0][:,0],b['pos'][:,0],atol=1e-6) and np.allclose(q['pos'][rq==2][:,0],b['pos'][:,0],atol=1e-6)
        z=by_id(out(scatter(st,sc,name='Stag0',rows_count=3,rows_spacing=1.0,rows_stagger=0.0,rows_center=0,**kw)));assert np.allclose(z['pos'][:,0],np.tile(b['pos'][:,0],3),atol=1e-6)      # 0 is off
    band=by_id(out(scatter(st,sc,name='Band',rows_count=1,rows_spacing=2.0,rows_random=1.0,**kw)));assert len(band['ids'])==10 and np.all(np.abs(band['pos'][:,2])<=1.0+1e-6) and np.ptp(band['pos'][:,2])>0.3 and np.array_equal(band['ids'],b['ids'])      # one row with a random offset: a band
    z=by_id(out(scatter(st,sc,name='Z',mode=0,line_axis=2,line_count=6,line_length=5.0,rows_count=2,rows_spacing=1.0,rows_center=0)));assert sorted(set(np.round(z['pos'][:,0],6)))==[0.0,1.0]                         # a line along Z: rows along X
    c=scatter(st,sc,name='Info',rows_count=3,**kw);out(c);assert '3 rows of 10 points = 30 points' in c.hdaModule().rows_info(c)

def circle_rows():
    st,sc=new_scene('circle');kw=dict(mode=3,circle_count=24,circle_radius=4.0,circle_facing=1)
    b=by_id(out(scatter(st,sc,name='Base',**kw)));a=scatter(st,sc,name='Rings',rows_count=3,rows_spacing=0.6,**kw);o=by_id(out(a));assert len(o['ids'])==72
    r=np.linalg.norm(o['pos'][:,[0,2]],axis=1);rows=o['ids']//STRIDE
    for k,rad in ((0,3.4),(1,4.0),(2,4.6)):assert np.allclose(r[rows==k],rad,atol=1e-5),k                                                                                                                  # concentric rings
    ang=np.arctan2(o['pos'][:,2],o['pos'][:,0]);base_ang=np.arctan2(b['pos'][:,2],b['pos'][:,0]);base_id={int(i):k for k,i in enumerate(b['ids'])}
    for i in range(72):assert abs(math.remainder(ang[i]-base_ang[base_id[int(o['ids'][i])%STRIDE]],2*math.pi))<1e-5                                                                                          # the same angles
    for i in range(72):assert abs(abs(float(np.dot(o['quat'][i],b['quat'][base_id[int(o['ids'][i])%STRIDE]])))-1.0)<2e-3                                                                                    # the facing is copied
    out_rows=by_id(out(scatter(st,sc,name='Out',rows_count=3,rows_spacing=0.6,rows_center=0,**kw)));assert np.allclose(sorted(set(np.round(np.linalg.norm(out_rows['pos'][:,[0,2]],axis=1),5))),[4.0,4.6,5.2])         # outwards
    wall=scatter(st,sc,name='Wall',mode=3,circle_count=12,circle_radius=3.0,circle_plane=1,rows_count=2,rows_spacing=1.0,rows_center=0);w=by_id(out(wall));rw=np.linalg.norm(w['pos'][:,[0,1]],axis=1);assert np.allclose(w['pos'][:,2],0,atol=1e-6) and np.allclose(sorted(set(np.round(rw,5))),[3.0,4.0])   # a ring in the XY plane

def curve_rows():
    st,sc=new_scene('curve');kw=dict(mode=4,curve_prim='/World/Path',curve_count=13)
    b=by_id(out(scatter(st,sc,name='Base',**kw)));assert len(b['ids'])==13
    a=scatter(st,sc,name='Rows',rows_count=3,rows_spacing=0.5,**kw);o=by_id(out(a));assert len(o['ids'])==39 and set(o['ids']//STRIDE)=={0,1,2}
    poly=[np.array(v,dtype=float) for v in ((0,0,0),(6,0,0),(6,0,6))];rows=o['ids']//STRIDE
    for i in range(len(o['ids'])):
        src=int(o['ids'][i])%STRIDE;p0=b['pos'][list(b['ids']).index(src)];want=0.5*abs(rows[i]-1)
        d=poly_distance(o['pos'][i],poly)
        if min(np.linalg.norm(p0-np.array(v)) for v in poly)>0.8:assert abs(d-want)<1e-6,(i,d,want)                                                                                                         # sideways from the path, on both legs
    leg2=[i for i in range(len(o['ids'])) if b['pos'][list(b['ids']).index(int(o['ids'][i])%STRIDE)][2]>2.0 and rows[i]!=1];leg1=[i for i in range(len(o['ids'])) if b['pos'][list(b['ids']).index(int(o['ids'][i])%STRIDE)][0]<4.0 and rows[i]!=1 and b['pos'][list(b['ids']).index(int(o['ids'][i])%STRIDE)][2]<1e-6]
    assert leg1 and leg2 and all(abs(abs(o['pos'][i][2])-0.5)<1e-6 for i in leg1) and all(abs(abs(o['pos'][i][0]-6.0)-0.5)<1e-6 for i in leg2)                                                    # offset along Z on the first leg, along X on the second
    old=by_id(out(scatter(st,sc,name='Old',typ=OLD_TYPE,**kw)));one=by_id(out(scatter(st,sc,name='One',**kw)));assert np.array_equal(old['ids'],one['ids']) and np.allclose(old['pos'],one['pos'])        # rows 1 = the previous release

def other_modes_and_stages():
    st,sc=new_scene('stages');area=dict(mode=1,area_count=300,area_sizex=6.0,area_sizez=6.0,area_seed=2)
    x=by_id(out(scatter(st,sc,name='Area1',**area)));y=by_id(out(scatter(st,sc,name='Area4',rows_count=4,rows_spacing=1.0,rows_random=1.0,**area)));assert np.array_equal(x['ids'],y['ids']) and np.allclose(x['pos'],y['pos'])                       # Rows only touch the linear modes
    kw=dict(mode=0,line_count=40,line_length=10.0,rows_count=5,rows_spacing=0.4,rows_random=0.6)
    b=by_id(out(scatter(st,sc,name='Plain',**kw)));f=by_id(out(scatter(st,sc,name='Fall',fall_on=1,fall_shape=1,fall_curve=0,fall_density=100.0,fall_scale=0.2,**kw)));assert len(f['ids'])==200
    d=scatter(st,sc,name='Dens',fall_on=1,fall_shape=1,fall_curve=0,fall_density=0.0,fall_scale=1.0,**kw);od=by_id(out(d));assert set(od['ids'].tolist())<=set(b['ids'].tolist()) and 60<len(od['ids'])<200                              # the Falloff works on all the rows
    mk=by_id(out(scatter(st,sc,name='Mask',mask_source=1,mask_effect=0,mask_noise_freq=0.4,**kw)));assert set(mk['ids'].tolist())<=set(b['ids'].tolist()) and 20<len(mk['ids'])<200                                         # and the Mask
    assert len(set(b['ids'].tolist()))==200

def contract():
    st,sc=new_scene('contract');a=st.createNode(TYPE,'C');g=a.parmTemplateGroup()
    for n in ('rows_count','rows_spacing','rows_center','rows_random','rows_shift','rows_stagger','rows_seed','rows_info'):assert g.find(n) is not None,n
    assert g.find('rows_count').defaultValue()==(1,) and g.find('rows_random').defaultValue()==(0.0,) and g.find('rows_shift').defaultValue()==(0.0,) and ((g.find('rows_stagger').defaultValue()==(0.0,) and g.find('rows_stagger').minValue()==0.0 and g.find('rows_stagger').maxValue()==1.0) if SLIDER else g.find('rows_stagger').defaultValue() is False)
    layout=[t for t in g.entries() if t.label()=='Layout'][0];names=[t.name() for t in layout.parmTemplates()];assert names.index('rows_count')>names.index('circle_count') and names.index('rows_count')<names.index('bound_t')
    assert 'mode != 0' in g.find('rows_count').conditionals()[hou.parmCondType.HideWhen] and 'mode != 4' in g.find('rows_count').conditionals()[hou.parmCondType.HideWhen]
    chain=[];n=a.node('USD_COMPILER/MASK_PROCESSOR')
    while n is not None and len(chain)<4:chain.append(n.name());n=n.inputs()[0] if n.inputs() else None
    assert chain[:3]==['MASK_PROCESSOR','ROWS','DISTRIBUTION_GENERATOR'],chain
    assert '$' not in a.type().definition().sections()['PythonModule'].contents().split('# ---- Rows')[1].split('# ----')[0] and 'Row 0 keeps its ids' in g.find('rows_count').help()

def main():
    for name,func in (('Maths: offsets, directions (line, circle planes, curve), gap, expansion, ids, random and stagger bounds, stability',maths),
                      ('Line: rows next to each other (centred or on one side), ids, more rows never move the others, random across, shift along, stagger, a band, other axis',line_rows),
                      ('Circle: concentric rings, same angles, facing copied, outwards, a ring in another plane',circle_rows),
                      ('Curve: rows pushed sideways from the path on every leg; one row is the previous release',curve_rows),
                      ('Other modes untouched; Falloff and Mask work on all rows',other_modes_and_stages),
                      ('Contract: parameters, Layout tab, stage order, no dollar signs',contract)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_rows_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
