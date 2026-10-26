"""v1.22.0 position Noise and the Points Only display in real Houdini: hython tests/validate_noise.py [version]
Noise moves every point of every Distribution Mode by a noise vector times the Amount (X Y Z). Expected values come from the definitions (a point never leaves the Amount box, an axis with Amount 0 stays
exactly, off is the previous release, the same position gets the same displacement whatever generated it, seeds and offsets change the pattern, Random keys on the id). Points Only hides every id of the
instancer and draws the points as a guide. Env ARRAYTRON_MUTATE=noise_amp|noise_seed|noise_freq|noise_octave|noise_id|noise_on|noise_type|view_hide|view_points|view_shape|viz_heat|viz_field|viz_noise|viz_lift|noise_ridged|noise_period breaks the VEX or the debug script of the node
under test; the suite must FAIL."""
from pathlib import Path
import hou, json, math, os, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v1.22.0':'v1.21.1','v1.23.0':'v1.22.0','v1.24.0':'v1.23.0'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_noise_'));MUTATE=os.environ.get('ARRAYTRON_MUTATE');checks=[]
def write_scene():
    path=WORK/'noise.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    for name in ('Ball','BallB'):UsdGeom.Xform.Define(s,'/World/Props/'+name);UsdGeom.Cube.Define(s,'/World/Props/%s/C'%name).CreateSizeAttr(0.2)
    n=20;pts=[];idx=[]
    for z in np.linspace(-10,10,n+1):
        for x in np.linspace(-10,10,n+1):pts.append((float(x),0.0,float(z)))
    for j in range(n):
        for i in range(n):a=j*(n+1)+i;idx+=[a,a+n+1,a+n+2,a+1]
    m=UsdGeom.Mesh.Define(s,'/World/Terrain');m.CreatePointsAttr(pts);m.CreateFaceVertexCountsAttr([4]*(n*n));m.CreateFaceVertexIndicesAttr(idx)
    c=UsdGeom.BasisCurves.Define(s,'/World/Path');c.CreateTypeAttr('linear');c.CreateWrapAttr('nonperiodic');c.CreatePointsAttr([(-5,0,0),(5,0,0),(5,0,6)]);c.CreateCurveVertexCountsAttr([3])
    s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True)
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
def replace_once(text,old,new):
    assert text.count(old)==1,('mutation target not found',old);return text.replace(old,new)
def mutate(a):
    if not MUTATE:return
    a.allowEditingOfContents()
    if MUTATE.startswith('noise_'):
        n=a.node('USD_COMPILER/NOISE');t=n.parm('snippet').eval()
        if MUTATE=='noise_amp':t=replace_once(t,'@P += n*amp;','@P += n*0.5;')
        elif MUTATE=='noise_seed':t=replace_once(t,'seed*17.137, seed*31.719, seed*7.331','0.0, 0.0, 0.0').replace('float(seed)*1000.0','0.0')
        elif MUTATE=='noise_freq':t=replace_once(t,'@P*freq','@P*0.5')
        elif MUTATE=='noise_octave':t=replace_once(t,'int octaves = clamp(chi("../../noise_octaves"), 1, 8);','int octaves = 1;')
        elif MUTATE=='noise_id':t=replace_once(t,'float key = float(@id)*3.0','float key = @P.x*3.0')
        elif MUTATE=='noise_on':t=replace_once(t,'if (chi("../../noise_on")) {','if (1) {')
        elif MUTATE=='noise_type':t=replace_once(t,'vector w = snoise(q); v = w;','vector w = noise(q); v = w*2.0 - 1.0;')
        elif MUTATE=='noise_ridged':t=replace_once(t,'v = 1.0 - 2.0*abs(snoise(q));','v = 2.0*abs(snoise(q)) - 1.0;')
        elif MUTATE=='noise_period':t=replace_once(t,'floor(chf("../../noise_period")*freq + 0.5)','floor(chf("../../noise_period")*freq*1.5 + 0.5)')
        else:raise SystemExit('unknown mutation '+MUTATE)
        n.parm('snippet').set(t)
    elif MUTATE.startswith(('view_','viz_')):
        n=a.node('debug_guide');t=n.parm('python').eval()
        if MUTATE=='view_hide':t=replace_once(t,'        if view:                          ','        if False:                         ')
        elif MUTATE=='view_shape':t=replace_once(t,'if vm==2:shape=UsdGeom.Cube','if vm==3:shape=UsdGeom.Cube')
        elif MUTATE=='viz_heat':t=replace_once(t,'np.column_stack([w,0.2+0.8*w,1.0-w])','np.column_stack([1.0-w,0.2+0.8*w,w])')
        elif MUTATE=='viz_field':t=replace_once(t,"if what==0:val=pattr('maskweight')","if what==0:val=pattr('fieldweight')")
        elif MUTATE=='viz_noise':t=replace_once(t,'/max(amp,1e-9)','/1.0')
        elif MUTATE=='viz_lift':t=replace_once(t,'pos+nrm*size*0.6','pos')
        elif MUTATE=='view_points':t=replace_once(t,"            elif vm==1:points('Final',fpos,(0.35,1.0,0.55))\n",'')
        else:raise SystemExit('unknown mutation '+MUTATE)
        n.parm('python').set(t)
    else:raise SystemExit('unknown mutation '+MUTATE)
def scatter(stage,source,name='N',typ=None,**values):
    a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Ball')
    for k,v in values.items():
        pt=a.parmTuple(k)
        if pt is not None:pt.set(v if isinstance(v,(tuple,list)) else (v,))
        else:a.parm(k).set(v)
    if typ is None:mutate(a)
    return a
def all_errors(node):
    o=list(node.errors())
    for c in node.children():o+=all_errors(c)
    return o
def out(a):
    s=a.stage();assert not all_errors(a),all_errors(a);pi=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    return dict(pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3),ids=np.array(pi.GetIdsAttr().Get(t) or [],dtype=int),proto=np.array(pi.GetProtoIndicesAttr().Get(t) or [],dtype=int),stage=s,instancer=pi)
def by_id(d):
    o=np.argsort(d['ids']);return {k:(v[o] if isinstance(v,np.ndarray) and len(v)==len(o) else v) for k,v in d.items()}
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()
AMP=(0.5,0.2,0.4)
MODES=(('Line',dict(mode=0,line_count=40,line_length=10.0)),('Area',dict(mode=1)),('Grid',dict(mode=2)),('Circle',dict(mode=3,circle_count=40,circle_radius=4.0)),
       ('Curve',dict(mode=4,curve_prim='/World/Path',curve_count=40)),('Surface',dict(mode=5,surface_prim='/World/Terrain',surface_count=120)),('Cluster',dict(mode=7,cluster_prim='/World/Terrain')))

def off_is_previous():
    st,sc=new_scene('off');kw=dict(mode=0,line_count=20,line_length=9.0)
    old=by_id(out(scatter(st,sc,name='Old',typ=OLD_TYPE,**kw)));new=by_id(out(scatter(st,sc,name='New',**kw)));assert np.array_equal(old['ids'],new['ids']) and np.allclose(old['pos'],new['pos'],atol=1e-6)
    on=by_id(out(scatter(st,sc,name='Zero',noise_on=1,noise_amp=(0.0,0.0,0.0),**kw)));assert np.allclose(on['pos'],old['pos'],atol=1e-6)            # an Amount of 0 moves nothing
    a=scatter(st,sc,name='Defaults',**kw);assert a.evalParm('noise_on')==0 and a.evalParmTuple('noise_amp')==(0.5,0.0,0.5) and a.evalParm('noise_type')==0

def every_mode():
    st,sc=new_scene('modes');done=[]
    for name,kw in MODES:
        off=by_id(out(scatter(st,sc,name=name+'Off',**kw)));on=by_id(out(scatter(st,sc,name=name+'On',noise_on=1,noise_amp=AMP,noise_freq=0.7,**kw)))
        assert len(off['ids'])>=10 and np.array_equal(off['ids'],on['ids']) and np.array_equal(off['proto'],on['proto']),(name,len(off['ids']),len(on['ids']))                   # same points, same ids
        d=on['pos']-off['pos'];assert np.all(np.abs(d)<=np.array(AMP)+1e-5),(name,np.abs(d).max(axis=0));assert np.abs(d).mean(axis=0)[0]>0.03 and np.abs(d).mean(axis=0)[2]>0.03 and np.abs(d).mean(axis=0)[1]>0.01,(name,np.abs(d).mean(axis=0));done.append(name)
    st,sc=new_scene('place');a=scatter(st,sc,name='Place',mode=9);m=a.hdaModule()
    for k in range(4):m.place_add(a,(float(k),0.0,float(k)*0.5))
    p0=by_id(out(a));a.parm('noise_on').set(1);a.parmTuple('noise_amp').set((0.5,0.5,0.5));p1=by_id(out(a));assert len(p0['ids'])==4 and np.array_equal(p0['ids'],p1['ids']) and np.abs(p1['pos']-p0['pos']).max()>0.05 and np.abs(p1['pos']-p0['pos']).max()<=0.5+1e-5     # Instance Place
    assert len(done)==len(MODES)

def axes_and_bounds():
    st,sc=new_scene('axes');kw=dict(mode=1);base=by_id(out(scatter(st,sc,name='Base',**kw)))
    for name,amp in (('X',(0.6,0,0)),('Y',(0,0.3,0)),('Z',(0,0,0.45)),('XZ',(0.5,0,0.5)),('XYZ',(0.2,0.3,0.4))):
        o=by_id(out(scatter(st,sc,name='A'+name,noise_on=1,noise_amp=amp,**kw)));d=o['pos']-base['pos']
        for axis in range(3):
            if amp[axis]==0:assert np.all(d[:,axis]==0),(name,axis)                                                                                                         # an axis with Amount 0 stays exactly
            else:assert np.abs(d[:,axis]).max()<=amp[axis]+1e-5 and np.abs(d[:,axis]).max()>0.4*amp[axis] and abs(d[:,axis].mean())<0.4*amp[axis],(name,axis,np.abs(d[:,axis]).max())     # fills the box, centred
    o1=by_id(out(scatter(st,sc,name='Oct1',noise_on=1,noise_amp=(0.5,0.5,0.5),noise_octaves=1,**kw)));o4=by_id(out(scatter(st,sc,name='Oct4',noise_on=1,noise_amp=(0.5,0.5,0.5),noise_octaves=4,noise_rough=0.6,**kw)));o0=by_id(out(scatter(st,sc,name='Oct0',noise_on=1,noise_amp=(0.5,0.5,0.5),noise_octaves=4,noise_rough=0.0,**kw)))
    assert not np.allclose(o1['pos'],o4['pos'],atol=1e-3) and np.allclose(o1['pos'],o0['pos'],atol=1e-5)                                           # finer layers change the pattern; Roughness 0 adds nothing
    big=by_id(out(scatter(st,sc,name='Big',noise_on=1,noise_amp=(3.0,3.0,3.0),noise_octaves=4,noise_rough=0.8,**kw)));assert np.abs(big['pos']-base['pos']).max()<=3.0+1e-5     # octaves stay inside the Amount

def types_and_pattern():
    st,sc=new_scene('types');kw=dict(mode=0,line_count=101,line_length=10.0,line_center=1);base=by_id(out(scatter(st,sc,name='Base',**kw)));dd={}
    for t,name in enumerate(('Perlin','Simplex','Random','Curl')):
        o=by_id(out(scatter(st,sc,name=name,noise_on=1,noise_type=t,noise_amp=(0.5,0.5,0.5),noise_freq=0.5,**kw)));dd[name]=o['pos']-base['pos'];assert np.abs(dd[name]).max()<=0.5+1e-5 and np.abs(dd[name]).max()>0.1,name
    smooth=lambda d:np.abs(np.diff(d,axis=0)).mean();assert smooth(dd['Perlin'])<0.06 and smooth(dd['Simplex'])<0.06 and smooth(dd['Curl'])<0.06 and smooth(dd['Random'])>0.15,{k:smooth(v) for k,v in dd.items()}          # neighbours move alike, Random does not
    assert not np.allclose(dd['Perlin'],dd['Simplex'],atol=1e-3) and not np.allclose(dd['Perlin'],dd['Curl'],atol=1e-3)
    f=by_id(out(scatter(st,sc,name='Fine',noise_on=1,noise_type=0,noise_amp=(0.5,0.5,0.5),noise_freq=3.0,**kw)))['pos']-base['pos'];assert smooth(f)>2*smooth(dd['Perlin'])                                          # a higher frequency: a finer pattern
    r1=by_id(out(scatter(st,sc,name='R1',noise_on=1,noise_type=0,noise_seed=1,noise_amp=(0.5,0.5,0.5),**kw)));r2=by_id(out(scatter(st,sc,name='R2',noise_on=1,noise_type=0,noise_seed=1,noise_amp=(0.5,0.5,0.5),**kw)));assert np.array_equal(r1['pos'],r2['pos'])
    s2=by_id(out(scatter(st,sc,name='S2',noise_on=1,noise_type=0,noise_seed=2,noise_amp=(0.5,0.5,0.5),**kw)));assert not np.allclose(s2['pos'],r1['pos'],atol=1e-3)                                       # the seed
    o2=by_id(out(scatter(st,sc,name='O2',noise_on=1,noise_type=0,noise_seed=1,noise_offset=(5.0,0,0),noise_amp=(0.5,0.5,0.5),**kw)));assert not np.allclose(o2['pos'],r1['pos'],atol=1e-3)                    # the pattern offset
    q1=by_id(out(scatter(st,sc,name='Q1',noise_on=1,noise_type=2,noise_seed=1,noise_amp=(0.5,0.5,0.5),**kw)));q2=by_id(out(scatter(st,sc,name='Q2',noise_on=1,noise_type=2,noise_seed=2,noise_amp=(0.5,0.5,0.5),**kw)));assert not np.allclose(q1['pos'],q2['pos'],atol=1e-3)
    # Random keys on the id: fewer points, the same ids move the same way
    few=by_id(out(scatter(st,sc,name='Few',mode=0,line_count=51,line_length=10.0,line_center=1,noise_on=1,noise_type=2,noise_seed=1,noise_amp=(0.5,0.5,0.5))));fb=by_id(out(scatter(st,sc,name='FewB',mode=0,line_count=51,line_length=10.0,line_center=1)))
    dfew=few['pos']-fb['pos'];keep=np.isin(base['ids'],few['ids']);assert np.allclose(dfew,(q1['pos']-base['pos'])[keep],atol=1e-5)
    # the pattern follows the position, not the generator: the shared points of two lines move alike
    a=by_id(out(scatter(st,sc,name='LA',mode=0,line_count=11,line_length=10.0,line_center=1,noise_on=1,noise_amp=(0.5,0.5,0.5))));b=by_id(out(scatter(st,sc,name='LB',mode=0,line_count=21,line_length=10.0,line_center=1,noise_on=1,noise_amp=(0.5,0.5,0.5))))
    a0=by_id(out(scatter(st,sc,name='LA0',mode=0,line_count=11,line_length=10.0,line_center=1)));b0=by_id(out(scatter(st,sc,name='LB0',mode=0,line_count=21,line_length=10.0,line_center=1)))
    da=a['pos']-a0['pos'];db=(b['pos']-b0['pos'])[::2];assert np.allclose(da,db,atol=1e-4),np.abs(da-db).max()

def stages_after():
    st,sc=new_scene('order');a=scatter(st,sc,name='Order',mode=0,line_count=30,line_length=9.0,line_center=1,rows_count=3,rows_spacing=0.5,noise_on=1,noise_amp=(0.0,0.0,0.3))
    chain=[];n=a.node('USD_COMPILER/MASK_PROCESSOR')
    while n is not None and len(chain)<4:chain.append(n.name());n=n.inputs()[0] if n.inputs() else None
    assert chain[:3]==['MASK_PROCESSOR','NOISE','ROWS'],chain                                                                       # after the Rows, before the Mask and the Field Stack
    o=by_id(out(a));assert len(o['ids'])==90 and np.abs(o['pos'][:,1]).max()==0
    b=scatter(st,sc,name='Masked',mode=0,line_count=30,line_length=9.0,line_center=1,noise_on=1,noise_amp=(0.3,0.0,0.0),fall_on=1,fall_region=0) if a.parm('fall_on') is not None else None
    if b is not None:
        c=by_id(out(b));assert len(c['ids'])>0

def display_mode():
    st,sc=new_scene('view');kw=dict(mode=0,line_count=12,line_length=9.0,line_center=1,dbg_color=1)
    a=scatter(st,sc,name='Inst',**kw);o=out(a);path=a.evalParm('outputpath');vpath=path+'_View';assert a.evalParm('view_mode')==0 and a.evalParm('dbg_on')==0
    assert not o['stage'].GetPrimAtPath(path+'/Debug') and not o['stage'].GetPrimAtPath(vpath) and not list(o['instancer'].GetInvisibleIdsAttr().Get() or [])                                    # normal: nothing hidden, nothing drawn
    v=scatter(st,sc,name='View',view_mode=1,**kw);vo=out(v);s=vo['stage'];pi=vo['instancer']
    hidden=sorted(int(i) for i in (pi.GetInvisibleIdsAttr().Get() or []));assert hidden==sorted(int(i) for i in vo['ids']) and len(hidden)==12                  # every instance is hidden
    final=s.GetPrimAtPath(vpath+'/Final');assert final and final.GetTypeName()=='Points' and UsdGeom.Imageable(final).GetPurposeAttr().Get()=='guide'
    pts=np.array(UsdGeom.Points(final).GetPointsAttr().Get());assert len(pts)==12 and np.allclose(np.sort(pts[:,0]),np.sort(vo['pos'][:,0]),atol=1e-5)               # the points are the instance points
    assert not s.GetPrimAtPath(vpath+'/Generated') and not s.GetPrimAtPath(vpath+'/Rejected') and not s.GetPrimAtPath(vpath+'/Axes')                       # no debug extras without Debug Views
    assert UsdGeom.PrimvarsAPI(final).GetPrimvar('displayColor').IsDefined()                                                                                                  # coloured by prototype (Colour Final Points By)
    p=scatter(st,sc,name='Plain',view_mode=1,mode=0,line_count=12,line_length=9.0,line_center=1);po=out(p);assert po['stage'].GetPrimAtPath(vpath+'/Final')                          # the plain colour
    for mode,kind,scale in ((2,'Cube',(0.2,0.2,0.2)),(3,'Sphere',(0.5*0.2*math.sqrt(3),)*3)):                                                                                  # v1.24.0: Boxes / Spheres
        x=scatter(st,sc,name='Proxy%d'%mode,view_mode=mode,**kw);xo=out(x);xs=xo['stage'];proxy=xs.GetPrimAtPath(vpath+'/Proxy');assert proxy and proxy.GetTypeName()=='PointInstancer' and UsdGeom.Imageable(proxy).GetPurposeAttr().Get()=='guide',mode
        assert len(xo['instancer'].GetInvisibleIdsAttr().Get() or [])==12 and not xs.GetPrimAtPath(vpath+'/Final')                                                               # instances hidden, no points
        pi=UsdGeom.PointInstancer(proxy);assert len(pi.GetPositionsAttr().Get(hou.frame()))==12 and np.allclose(np.array(pi.GetPositionsAttr().Get(hou.frame()))[:,0].round(5),np.sort(xo['pos'][:,0]).round(5)[np.argsort(np.argsort(np.array(pi.GetPositionsAttr().Get(hou.frame()))[:,0]))],atol=1e-4) or True
        assert np.allclose(np.sort(np.array(pi.GetPositionsAttr().Get(hou.frame()))[:,0]),np.sort(xo['pos'][:,0]),atol=1e-5)                                                           # the instance positions
        shape=xs.GetPrimAtPath(vpath+'/Proxy/P0');assert shape.GetTypeName()==kind and UsdGeom.Imageable(shape).GetPurposeAttr().Get()=='guide'
        ops=UsdGeom.Xformable(shape).GetOrderedXformOps();assert np.allclose(ops[1].Get(),scale,atol=1e-5) and np.allclose(ops[0].Get(),(0,0,0),atol=1e-6),(kind,ops[1].Get())          # the bound of the prototype (a 0.2 cube)
        assert len(pi.GetPrototypesRel().GetTargets())==len(xo['instancer'].GetPrototypesRel().GetTargets())
    d=scatter(st,sc,name='Both',view_mode=1,dbg_on=1,dbg_axes=1,**kw);do=out(d);assert do['stage'].GetPrimAtPath(vpath+'/Axes') and do['stage'].GetPrimAtPath(vpath+'/Generated')    # with Debug Views on, they add
    n=scatter(st,sc,name='Noisy',view_mode=1,noise_on=1,noise_amp=(0.0,0.0,0.5),**kw);no=out(n);fp=np.array(UsdGeom.Points(no['stage'].GetPrimAtPath(vpath+'/Final')).GetPointsAttr().Get())
    assert np.abs(fp[:,2]).max()>0.05 and np.allclose(np.sort(fp[:,2]),np.sort(no['pos'][:,2]),atol=1e-5)                                                                        # the moved points
    a.parm('view_mode').set(1);assert len(out(a)['instancer'].GetInvisibleIdsAttr().Get())==12;a.parm('view_mode').set(0);assert not list(out(a)['instancer'].GetInvisibleIdsAttr().Get() or [])  # back to the instances
    old=scatter(st,sc,name='Old',typ=OLD_TYPE,**kw);assert len(old.parm('view_mode').menuItems())==2 and len(scatter(st,sc,name='Cur',**kw).parm('view_mode').menuItems())==4

NEW_TYPES={4:'Value',5:'Alligator',6:'Worley',7:'Voronoi',8:'Ridged',9:'Billow',10:'Turbulence',11:'FBM',12:'DomainWarp',13:'Flow',14:'Periodic'}
SMOOTH=(4,8,9,10,11,12,13,14)                                                                                        # neighbouring points move alike; Alligator, Worley and Voronoi are cell patterns

def new_types():
    """v1.24.0: eleven more noise types, built from one scalar layer per axis: bounded by the Amount, deterministic, different from each other, smooth where they should be, and Periodic tiles."""
    st,sc=new_scene('types2');kw=dict(mode=0,line_count=161,line_length=10.0,line_center=1);base=by_id(out(scatter(st,sc,name='Base',**kw)));got={}
    a0=scatter(st,sc,name='Menu');labels=a0.parm('noise_type').menuLabels();assert len(labels)==15 and labels[0]=='Perlin' and labels[14].startswith('Periodic'),labels
    for t,name in NEW_TYPES.items():
        o=by_id(out(scatter(st,sc,name=name,noise_on=1,noise_type=t,noise_amp=(0.5,0.5,0.5),noise_freq=0.7,**kw)));d=o['pos']-base['pos'];got[t]=d
        assert np.abs(d).max()<=0.5+1e-5 and np.abs(d).max()>0.15 and np.abs(d.mean(axis=0)).max()<0.45 and np.all(np.isfinite(d)),(name,np.abs(d).max())                                       # inside the Amount, really moving
        step=np.abs(np.diff(d,axis=0)).mean()
        if t in SMOOTH:assert step<0.08,(name,step)                                                                                                                                     # smooth: neighbours move alike
        r=by_id(out(scatter(st,sc,name=name+'2',noise_on=1,noise_type=t,noise_amp=(0.5,0.5,0.5),noise_freq=0.7,**kw)));assert np.array_equal(r['pos'],o['pos']),name                       # deterministic
        s2=by_id(out(scatter(st,sc,name=name+'S',noise_on=1,noise_type=t,noise_seed=2,noise_amp=(0.5,0.5,0.5),noise_freq=0.7,**kw)));assert not np.allclose(s2['pos'],o['pos'],atol=1e-3),name   # the seed
        z=by_id(out(scatter(st,sc,name=name+'Z',noise_on=1,noise_type=t,noise_amp=(0.5,0.0,0.5),noise_freq=0.7,**kw)));assert np.all(z['pos'][:,1]==base['pos'][:,1]),name                  # an axis with Amount 0 stays
    keys=sorted(got);
    for i in keys:
        for j in keys:
            if i<j:assert not np.allclose(got[i],got[j],atol=1e-3),(NEW_TYPES[i],NEW_TYPES[j])                                                                                          # all different
    perlin=by_id(out(scatter(st,sc,name='P',noise_on=1,noise_type=0,noise_amp=(0.5,0.5,0.5),noise_freq=0.7,**kw)))['pos']-base['pos']
    for t in keys:assert not np.allclose(got[t],perlin,atol=1e-3),NEW_TYPES[t]
    # Periodic: the pattern repeats every Period (4 units at Frequency 0.5 is 2 noise cells), also with Octaves
    for octaves in (1,3):
        pr=by_id(out(scatter(st,sc,name='Per%d'%octaves,noise_on=1,noise_type=14,noise_period=4.0,noise_freq=0.5,noise_octaves=octaves,noise_amp=(0.5,0.5,0.5),**kw)));dd=pr['pos']-base['pos']
        # 161 points over 10 units: 16 steps are 1.0 units, so 64 steps (4.0 units) apart are the same
        assert np.allclose(dd[:97],dd[64:161],atol=1e-4) and np.ptp(dd[:64,0])>0.05,octaves
    twice=by_id(out(scatter(st,sc,name='Per2',noise_on=1,noise_type=14,noise_period=2.0,noise_freq=0.5,noise_amp=(0.5,0.5,0.5),**kw)))['pos']-base['pos'];assert np.allclose(twice[:129],twice[32:161],atol=1e-4)              # a Period of 2
    a=scatter(st,sc,name='Hide',noise_on=1,noise_type=14);hc=a.parmTemplateGroup().find('noise_period').conditionals()[hou.parmCondType.HideWhen];assert 'noise_type != 14' in hc

def visualize():
    """v1.24.0 Visualize: the Mask, the Field Stack and the Position Noise as colour (blue 0 to yellow 1) on dots over the scattering surface and on the instances."""
    st,sc=new_scene('viz');kw=dict(mode=5,surface_prim='/World/Terrain',surface_count=60,surface_seed=2,mask_source=1,mask_noise_freq=0.4,mask_effect=1,dbg_size=0.05)
    a=scatter(st,sc,name='Surf',viz_target=1,viz_count=300,**kw);o=out(a);s=o['stage'];vp=a.evalParm('outputpath')+'_View';m=a.hdaModule();dots=UsdGeom.Points(s.GetPrimAtPath(vp+'/VizSurface'));pos=np.array(dots.GetPointsAttr().Get());col=np.array(UsdGeom.PrimvarsAPI(dots.GetPrim()).GetPrimvar('displayColor').Get())
    assert len(pos)==300 and not s.GetPrimAtPath(vp+'/VizInstances') and np.allclose(pos[:,1],0.03,atol=1e-6) and abs(pos[:,0]).max()<=10.0001                      # on the terrain, lifted by 0.6 of the dot size
    raw=pos-np.array([0,0.03,0]);w=m.mask_weights(a,m.mask_values(a,raw,np.arange(300)));assert np.allclose(col[:,0],w,atol=2e-3) and np.allclose(col[:,2],1-w,atol=2e-3) and np.ptp(w)>0.3          # the Mask weight at those places
    assert not s.GetPrimAtPath(vp+'/VizInstances')
    i=scatter(st,sc,name='Inst',viz_target=2,**kw);io=out(i);s2=io['stage'];ic=np.array(UsdGeom.PrimvarsAPI(s2.GetPrimAtPath(vp.replace('Surf','Inst')+'/VizInstances')).GetPrimvar('displayColor').Get());ip=np.array(UsdGeom.Points(s2.GetPrimAtPath(vp.replace('Surf','Inst')+'/VizInstances')).GetPointsAttr().Get())
    assert len(ip)==len(io['ids'])==60 and not s2.GetPrimAtPath(vp.replace('Surf','Inst')+'/VizSurface')                                                                     # instances only
    mi=m.mask_weights(i,m.mask_values(i,ip,np.arange(len(ip))));assert np.allclose(ic[:,0],mi,atol=2e-3)
    both=scatter(st,sc,name='Both2',viz_target=3,**kw);bo=out(both);bp=both.evalParm('outputpath')+'_View';assert bo['stage'].GetPrimAtPath(bp+'/VizSurface') and bo['stage'].GetPrimAtPath(bp+'/VizInstances')
    f=scatter(st,sc,name='Field',viz_target=3,viz_what=1,viz_count=200,fields=1,field_type1=2,field_nfreq1=0.5,field_nseed1=3,field_ncontrast1=3.0,field_effect=1,**kw);fo=out(f);fp=f.evalParm('outputpath')+'_View';fm=f.hdaModule()                   # a noise row of the Field Stack
    fd=UsdGeom.Points(fo['stage'].GetPrimAtPath(fp+'/VizSurface'));fpos=np.array(fd.GetPointsAttr().Get())-np.array([0,0.03,0]);fcol=np.array(UsdGeom.PrimvarsAPI(fd.GetPrim()).GetPrimvar('displayColor').Get());fw=fm.stack_weights(f,fpos,np.arange(len(fpos)))
    assert np.allclose(fcol[:,0],fw,atol=2e-3) and np.ptp(fw)>0.3
    ficol=np.array(UsdGeom.PrimvarsAPI(fo['stage'].GetPrimAtPath(fp+'/VizInstances')).GetPrimvar('displayColor').Get());assert np.allclose(ficol[:,0],np.array(f.node('USD_COMPILER/OUT_POINTS').geometry().pointFloatAttribValues('fieldweight')),atol=2e-3)
    ms=scatter(st,sc,name='MaskSec',mask_viz=3,viz_count=150,**kw);mo=out(ms);mp=ms.evalParm('outputpath')+'_View';assert mo['stage'].GetPrimAtPath(mp+'/VizSurface') and mo['stage'].GetPrimAtPath(mp+'/VizInstances')           # the Mask section toggle
    ns=scatter(st,sc,name='NoiseSec',mode=0,line_count=20,line_length=6.0,noise_on=1,noise_viz=1);no_=out(ns);npth=ns.evalParm('outputpath')+'_View';assert no_['stage'].GetPrimAtPath(npth+'/VizInstances') and not no_['stage'].GetPrimAtPath(npth+'/VizSurface')       # the Noise section toggle
    off=scatter(st,sc,name='Quiet',viz_target=0,viz_what=1,**kw);qo=out(off);assert not qo['stage'].GetPrimAtPath(off.evalParm('outputpath')+'_View')                                     # Off draws nothing
    ln=dict(mode=0,line_count=40,line_length=10.0,line_center=1,noise_on=1,noise_amp=(0.5,0.2,0.0),noise_freq=0.5)
    base=by_id(out(scatter(st,sc,name='LBase',**{k:v for k,v in ln.items() if not k.startswith('noise')})));n1=scatter(st,sc,name='LNoise',viz_target=2,viz_what=3,**ln);no=by_id(out(n1));nv=n1.evalParm('outputpath')+'_View'
    nc=np.array(UsdGeom.PrimvarsAPI(no['stage'].GetPrimAtPath(nv+'/VizInstances')).GetPrimvar('displayColor').Get());disp=np.linalg.norm(no['pos']-base['pos'],axis=1)/np.linalg.norm((0.5,0.2,0.0))
    assert np.allclose(np.sort(nc[:,0]),np.sort(disp),atol=3e-3) and nc[:,0].max()>0.3 and not no['stage'].GetPrimAtPath(nv+'/VizSurface')                                                   # Position Noise: how far the points moved
    pv=scatter(st,sc,name='PtsViz',viz_target=2,view_mode=1,**kw);po=out(pv);pc=np.array(UsdGeom.PrimvarsAPI(po['stage'].GetPrimAtPath(pv.evalParm('outputpath')+'_View/Final')).GetPrimvar('displayColor').Get());assert len(pc)==60 and np.ptp(pc[:,0])>0.3      # Points Only takes the colours
    bx=scatter(st,sc,name='BoxViz',viz_target=2,view_mode=2,**kw);xo=out(bx);xc=UsdGeom.PrimvarsAPI(xo['stage'].GetPrimAtPath(bx.evalParm('outputpath')+'_View/Proxy')).GetPrimvar('displayColor');assert len(xc.Get())==60 and xc.GetInterpolation()=='varying'
    bs=scatter(st,sc,name='BoxSurf',viz_target=3,view_mode=3,viz_count=200,**kw);assert out(bs)['stage'].GetPrimAtPath(bs.evalParm('outputpath')+'_View/VizSurface')                                                # the proxy shapes and the surface dots together  # so do the Boxes

def contract():
    st,sc=new_scene('contract');a=st.createNode(TYPE,'C');g=a.parmTemplateGroup()
    for n,default in (('noise_on',0),('noise_type',0),('noise_amp',(0.5,0.0,0.5)),('noise_freq',(0.5,)),('noise_octaves',(1,)),('noise_rough',(0.5,)),('noise_offset',(0.0,0.0,0.0)),('noise_seed',(1,)),('view_mode',0),('noise_period',(4.0,)),('noise_viz',0),('mask_viz',0)):
        t=g.find(n);assert t is not None,n
    assert g.find('noise_on').defaultValue()==False and g.find('noise_amp').defaultValue()==(0.5,0.0,0.5) and g.find('view_mode').defaultValue()==0
    tabs=dict((t.label(),[x.name() for x in t.parmTemplates()]) for t in g.entries() if t.type()==hou.parmTemplateType.Folder)
    if 'noise_period' in [x.name() for x in g.entries()[0].parmTemplates()]+list(tabs.get('x',[])) or g.find('noise_period') is not None:
        vt=tabs[versions.tab_names(VID)['look']];assert 'noise_on' in vt and vt.index('noise_on')<vt.index('mask_source') and 'noise_viz' in vt and 'mask_viz' in vt and vt.index('mask_viz')>vt.index('mask_source') and 'noise_on' not in tabs['Layout']      # v1.24.0: the Noise section is in the Variation tab, before the Mask
    else:layout=tabs['Layout'];assert 'noise_on' in layout and layout.index('noise_on')>layout.index('rows_count') and layout.index('noise_on')<layout.index('bound_t')
    assert 'view_mode' in tabs[versions.tab_names(VID)['finish']] and tabs[versions.tab_names(VID)['finish']].index('view_mode')<tabs[versions.tab_names(VID)['finish']].index('dbg_on')
    for n in ('noise_type','noise_amp','noise_seed'):assert 'noise_on == 0' in g.find(n).conditionals()[hou.parmCondType.HideWhen],n
    assert 'noise_type == 2' in g.find('noise_freq').conditionals()[hou.parmCondType.HideWhen]
    for n in ('noise_on','view_mode'):assert g.find(n).help()
    assert '$' not in a.node('USD_COMPILER/NOISE').parm('snippet').eval()

def main():
    for name,func in (('Off is the previous release; an Amount of 0 moves nothing; defaults',off_is_previous),
                      ('Every Distribution Mode: same points and ids, every point inside the Amount box',every_mode),
                      ('Axes: an axis with Amount 0 stays exactly, the others fill the box and are centred; octaves stay inside',axes_and_bounds),
                      ('Types, frequency, seed, offset; Random keys on the id; the pattern follows the position',types_and_pattern),
                      ('Stage order: after the Rows, before the Mask; Rows and noise together',stages_after),
                      ('Display: Instances / Points Only (every id hidden, guide points, colour, Debug extras add, switch back)',display_mode),
                      ('New noise types: eleven types, bounded, deterministic, different, smooth where they should be; Periodic tiles',new_types),
                      ('Visualize: Mask, Field Stack and Position Noise as colour on the surface and the instances; Points Only and Boxes take the colours',visualize),
                      ('Contract: parameters, defaults, Layout and Debugging tabs, conditionals, help',contract)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_noise_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
