"""v1.30.0 Surface mode, Keep By Direction in real Houdini: hython tests/validate_surfdir.py [version]
Like Group Create > Keep By Normals: only the triangles whose normal lies within Spread Angle of a Direction (a vector, or the way towards a light) receive points; the Count stays exact, By Density counts the kept
area, a Soft Edge fades the density out, Include Opposite Direction keeps the other side too. Expected values come from a cube (every face a known axis normal) and a sphere (a known normal at every
point). Env ARRAYTRON_MUTATE=sd_spread|sd_opp|sd_soft|sd_light|sd_area breaks the module; the suite must FAIL."""
from pathlib import Path
import hou, json, math, os, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom, UsdLux, Gf
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v1.33.0':'v1.32.0','v1.32.0':'v1.31.1','v1.31.1':'v1.31.0','v1.31.0':'v1.30.1','v1.30.1':'v1.30.0','v1.30.0':'v1.29.0'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_surfdir_'));checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')
def write_scene():
    path=WORK/'surfdir.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    UsdGeom.Xform.Define(s,'/World/Props/Tree');UsdGeom.Cube.Define(s,'/World/Props/Tree/C').CreateSizeAttr(0.2)
    UsdGeom.Cube.Define(s,'/World/Block').CreateSizeAttr(10.0)
    UsdGeom.Sphere.Define(s,'/World/Ball').CreateRadiusAttr(5.0)
    sun=UsdLux.DistantLight.Define(s,'/World/SunDown');x=UsdGeom.Xformable(sun);x.AddRotateXYZOp().Set(Gf.Vec3f(-90,0,0))                      # shines along -Y: the way towards it is +Y
    east=UsdLux.DistantLight.Define(s,'/World/SunEast');UsdGeom.Xformable(east).AddRotateXYZOp().Set(Gf.Vec3f(0,90,0))                      # its +Z axis is +X
    lamp=UsdLux.SphereLight.Define(s,'/World/Lamp');UsdGeom.Xformable(lamp).AddTranslateOp().Set(Gf.Vec3d(0,20,0))                           # a place above the block
    UsdLux.DomeLight.Define(s,'/World/Sky')
    s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
def install():
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True);install();hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
def scatter(stage,source,typ=None,name='Sd',surface='/World/Block',count=600,**values):
    a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Tree');a.parm('mode').set(5);a.parm('surface_prim').set(surface);a.parm('surface_count').set(count);a.parm('surface_seed').set(3);a.parm('surface_slope_max').set(180.0)                  # downward faces allowed (the default 90 leaves them out)
    for k,v in values.items():
        if isinstance(v,(tuple,list)):a.parmTuple(k).set(v)
        else:a.parm(k).set(v)
    if typ is None:mutate(a)
    return a
def out(a):
    s=a.stage();assert not list(a.errors()),a.errors();pi=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    d=dict(pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3),ids=np.array(pi.GetIdsAttr().Get(t) or [],dtype=int))
    o=np.argsort(d['ids']);return {k:v[o] for k,v in d.items()}
def errs(n):
    n.stage();return ' '.join(list(n.errors())+[e for c in n.allSubChildren() for e in c.errors()])
def face_of(P):
    """The face of the cube (size 10) each point lies on: 0 +X, 1 -X, 2 +Y, 3 -Y, 4 +Z, 5 -Z."""
    big=np.argmax(np.abs(P),axis=1);assert np.allclose(np.abs(P[np.arange(len(P)),big]),5.0,atol=1e-6),'a point is not on a face';return big*2+(P[np.arange(len(P)),big]<0)
def mutate(a):
    g=a.hdaModule().direction_weights.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='sd_spread':
        good=g['direction_weights'];g['direction_weights']=lambda n,d,spread,soft=0.0,opp=False:good(n,d,180.0,soft,opp)                                                             # the Spread Angle is ignored
    elif MUTATE=='sd_opp':
        good=g['direction_weights'];g['direction_weights']=lambda n,d,spread,soft=0.0,opp=False:good(n,d,spread,soft,False)                                                         # Include Opposite does nothing
    elif MUTATE=='sd_soft':
        good=g['direction_weights'];g['direction_weights']=lambda n,d,spread,soft=0.0,opp=False:good(n,d,spread,0.0,opp)                                                            # Soft Edge does nothing
    elif MUTATE=='sd_light':
        good=g['surface_light_directions'];g['surface_light_directions']=lambda asset,centers:-good(asset,centers)                                                                  # the way away from the light
    elif MUTATE=='sd_area':
        g['selected_area']=lambda area,w:float(area.sum())                                                                                                                           # By Density counts the whole surface
    elif MUTATE:raise SystemExit('unknown mutation '+MUTATE)
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()

def maths():
    st,sc=new_scene('mod');a=scatter(st,sc);m=a.hdaModule();N=np.array([[0,1,0],[1,0,0],[0,-1,0],[0,0.7071067811865476,0.7071067811865476],[0,0.9238795325112867,0.3826834323650898]])
    assert np.array_equal(m.direction_weights(N,[0,1,0],45.0),[1,0,0,1,1])                                                                                                           # a hard cone: 45 degrees includes the normal at exactly 45
    assert np.array_equal(m.direction_weights(N,[0,1,0],44.9),[1,0,0,0,1]) and np.array_equal(m.direction_weights(N,[0,3,0],45.0),[1,0,0,1,1])                                       # ... not 44.9; the vector need not be a unit vector
    assert np.array_equal(m.direction_weights(N,[0,1,0],90.0),[1,1,0,1,1]) and np.array_equal(m.direction_weights(N,[0,1,0],180.0),np.ones(5)) and np.array_equal(m.direction_weights(N,[0,1,0],0.0),[1,0,0,0,0])
    assert np.array_equal(m.direction_weights(N,[0,1,0],45.0,0.0,True),[1,0,1,1,1])                                                                                                   # Include Opposite: the down normal counts
    w=m.direction_weights(N[[0,3,1]],[0,1,0],90.0,1.0);assert w[0]==1.0 and abs(w[1]-0.5)<1e-9 and w[2]==0.0                                                                           # Soft Edge 1: 1 at the middle, half at half the spread (smooth step), 0 at the spread
    w=m.direction_weights(np.array([[0,np.cos(np.radians(a_)),np.sin(np.radians(a_))] for a_ in (0,20,30,40,45,50)]),[0,1,0],45.0,0.5);assert np.allclose(w[:2],1.0) and w[2]<1.0 and np.all(np.diff(w[1:])<=1e-12) and abs(w[4])<1e-9 and w[5]==0.0   # full to 22.5, fading to 0 at 45
    per=m.direction_weights(np.array([[0,1,0],[0,1,0]]),np.array([[0,1,0],[1,0,0]]),10.0);assert np.array_equal(per,[1,0])                                                         # one direction per triangle
    pts=m.surface_points;P=np.array([[0,0,0],[1,0,0],[0,0,1],[1,0,1.]]);T=np.array([[0,2,1],[1,2,3]]);ar=np.array([0.5,0.5]);nm=np.array([[0,1,0],[0,1,0.]])
    p0,_,_=pts(P,T,ar,nm,nm,50,1,False,0,90,0,1.0);p1,_,_=pts(P,T,ar,nm,nm,50,1,False,0,90,0,1.0,np.array([1.0,1.0]));assert np.array_equal(p0,p1)                                      # a weight of 1: the same points as before
    p2,_,_=pts(P,T,ar,nm,nm,200,1,False,0,90,0,1.0,np.array([1.0,0.0]));assert (p2[:,0]+p2[:,2]<=1.0+1e-9).all() and len(p2)==200                                                       # a weight of 0 removes a triangle, the count stays

def cube():
    st,sc=new_scene('cube');off=out(scatter(st,sc,name='Off'));f0=np.bincount(face_of(off['pos']),minlength=6);assert len(off['ids'])==600 and (f0>60).all()                            # all six faces
    on=lambda **kw:out(scatter(st,sc,name='K%d'%len(checks_made.setdefault('n',[])+[0]),surface_dirsel=1,**kw))
    checks_made={}
    def run(**kw):
        checks_made.setdefault('n',[]).append(0);return out(scatter(st,sc,name='K%d'%len(checks_made['n']),surface_dirsel=1,**kw))
    up=run(surface_dir=(0,1,0),surface_spread=45.0);assert len(up['ids'])==600 and (face_of(up['pos'])==2).all()                                                                     # Direction up, 45: the top only, 600 points
    assert np.array_equal(up['ids'],off['ids'])                                                                                                                                    # point ids are the same
    big=run(surface_dir=(0,1,0),surface_spread=90.0);fb=np.bincount(face_of(big['pos']),minlength=6);assert len(big['ids'])==600 and fb[3]==0 and (fb[[0,1,2,4,5]]>60).all()               # 90: the top and the four sides (the bottom is 180 away)
    allp=run(surface_dir=(0,1,0),surface_spread=180.0);assert np.array_equal(allp['pos'],off['pos'])                                                                                 # 180: every triangle, the very same points as with the option off
    east=run(surface_dir=(3,0,0),surface_spread=30.0);assert (face_of(east['pos'])==0).all() and len(east['ids'])==600                                                                # +X only
    opp=run(surface_dir=(0,1,0),surface_spread=30.0,surface_opp=1);fo=np.bincount(face_of(opp['pos']),minlength=6);assert fo[2]>150 and fo[3]>150 and fo[[0,1,4,5]].sum()==0 and len(opp['ids'])==600   # Include Opposite: top and bottom
    diag=run(surface_dir=(1,1,0),surface_spread=50.0);fd=np.bincount(face_of(diag['pos']),minlength=6);assert fd[0]>100 and fd[2]>100 and fd[[1,3,4,5]].sum()==0                                  # a diagonal direction: +X and +Y
    dens=out(scatter(st,sc,name='Dens',surface_countmode=1,surface_density=2.0,surface_dirsel=1,surface_dir=(0,1,0),surface_spread=45.0));assert len(dens['ids'])==200                       # By Density counts the kept area: 100 x 2
    both=out(scatter(st,sc,name='Slope',surface_dirsel=1,surface_dir=(0,1,0),surface_spread=180.0,surface_slope_max=45.0));assert (face_of(both['pos'])==2).all()                       # together with the slope limits
    seed=run(surface_dir=(0,1,0),surface_spread=45.0,surface_seed=7);assert not np.array_equal(seed['pos'],up['pos'])
    more=out(scatter(st,sc,name='More',count=900,surface_dirsel=1,surface_dir=(0,1,0),surface_spread=45.0));assert np.array_equal(more['pos'][:600],up['pos'])                           # raising the Count adds points and moves none
    z=scatter(st,sc,name='Zero',surface_dirsel=1,surface_dir=(0,0,0))
    assert 'zero vector' in errs(z),errs(z)                                                                                                                                       # a zero Direction is refused
    info=scatter(st,sc,name='Info',surface_dirsel=1,surface_dir=(0,1,0),surface_spread=45.0).hdaModule().surface_info(hou.node('/stage/Info'));assert 'Keep By Direction: 2 of 12 triangles kept, area 100' in info,info
    none=scatter(st,sc,name='None',surface_dirsel=1,surface_dir=(0,1,0),surface_spread=45.0,surface_slope_min=80.0);assert len(out(none)['ids'])==0 and 'Keep By Direction: 0 of 12' in none.hdaModule().surface_info(none)   # nothing kept: no points

def sphere():
    st,sc=new_scene('sphere');hard=out(scatter(st,sc,name='Hard',surface='/World/Ball',count=2000,surface_dirsel=1,surface_dir=(0,1,0),surface_spread=40.0));P=hard['pos']
    ang=np.degrees(np.arccos(np.clip(P[:,1]/np.linalg.norm(P,axis=1),-1,1)));assert len(P)==2000 and ang.max()<40.0+12.0 and (ang<20).sum()>200                                          # a cap around the top (the triangles of the sphere are some degrees wide)
    soft=out(scatter(st,sc,name='Soft',surface='/World/Ball',count=2000,surface_dirsel=1,surface_dir=(0,1,0),surface_spread=60.0,surface_soft=1.0));Q=soft['pos']
    aq=np.degrees(np.arccos(np.clip(Q[:,1]/np.linalg.norm(Q,axis=1),-1,1)));density=lambda lo,hi:((aq>=lo)&(aq<hi)).sum()/(math.cos(math.radians(lo))-math.cos(math.radians(hi)))
    d1,d2,d3=density(5,20),density(20,35),density(35,50);assert d1>d2>d3>0 and d3<0.5*d1,(d1,d2,d3)                                                                                  # a soft edge: the density per area falls towards the border
    h2=out(scatter(st,sc,name='Hard2',surface='/World/Ball',count=2000,surface_dirsel=1,surface_dir=(0,1,0),surface_spread=60.0));ah=np.degrees(np.arccos(np.clip(h2['pos'][:,1]/np.linalg.norm(h2['pos'],axis=1),-1,1)))
    dh=lambda lo,hi:((ah>=lo)&(ah<hi)).sum()/(math.cos(math.radians(lo))-math.cos(math.radians(hi)));assert abs(dh(5,20)/dh(35,50)-1.0)<0.35                                                    # hard: the same density across the cap

def light():
    st,sc=new_scene('light');L=lambda path,**kw:out(scatter(st,sc,name='L%d'%(abs(hash(path+str(kw)))%10**6),surface_dirsel=1,surface_dirsrc=1,surface_light=path,**kw))
    sun=L('/World/SunDown',surface_spread=45.0);assert len(sun['ids'])==600 and (face_of(sun['pos'])==2).all()                                                                         # a distant light shining down: the faces looking up
    east=L('/World/SunEast',surface_spread=45.0);assert (face_of(east['pos'])==0).all()                                                                                              # a distant light on the east: the +X face
    lamp=L('/World/Lamp',surface_spread=60.0);assert (face_of(lamp['pos'])==2).all()                                                                                                  # a lamp above: the top
    wide=L('/World/Lamp',surface_spread=110.0);fw=np.bincount(face_of(wide['pos']),minlength=6);assert fw[2]>50 and fw[[0,1,4,5]].min()>10 and fw[3]==0                                       # a lamp is a place: with a wide cone the sides lean towards it too, the bottom never
    for path,err in (('/World/Sky','dome light'),('/World/Missing','does not exist'),('','empty')):
        n=scatter(st,sc,name='E%d'%len(path),surface_dirsel=1,surface_dirsrc=1,surface_light=path)
        assert err in errs(n),(path,errs(n))
    v=scatter(st,sc,name='Vec',surface_dirsel=1,surface_dirsrc=0,surface_light='/World/SunEast',surface_dir=(0,1,0),surface_spread=45.0);assert (face_of(out(v)['pos'])==2).all()                  # Direction From Vector ignores the light

def contract():
    st,sc=new_scene('contract');a=scatter(st,sc,name='C');g=a.parmTemplateGroup();d=lambda n:g.find(n).defaultValue()
    for n in ('surface_dirsel','surface_dirsrc','surface_dir','surface_light','surface_spread','surface_soft','surface_opp'):assert g.find(n) is not None,n
    assert d('surface_dirsel')==False and d('surface_dirsrc')==0 and d('surface_dir')==(0.0,1.0,0.0) and d('surface_light')==('',) and d('surface_spread')==(45.0,) and d('surface_soft')==(0.0,) and d('surface_opp')==False
    assert g.find('surface_dirsrc').menuLabels()==('Vector','Light Prim') and g.find('surface_dirsel').label()=='Keep By Direction'
    hide=lambda n:g.find(n).conditionals().get(hou.parmCondType.HideWhen);assert '{ surface_dirsel == 0 }' in hide('surface_spread') and '{ surface_dirsel == 0 } { surface_dirsrc != 0 }' in hide('surface_dir') and '{ surface_dirsel == 0 } { surface_dirsrc != 1 }' in hide('surface_light') and '{ mode != 5 }' in hide('surface_spread')      # the mode condition of the Surface section is added by the layout
    for n in ('direction_weights','surface_light_directions','surface_selection','surface_total_area'):assert hasattr(a.hdaModule(),n),n
    assert '$' not in a.type().definition().sections()['PythonModule'].contents().split('def direction_weights')[1].split('def surface_total_area')[0]

def unchanged():
    st,sc=new_scene('same');a=scatter(st,sc,name='N',surface='/World/Ball',count=500,surface_slope_max=70.0,surface_normal=1);b=scatter(st,sc,typ=OLD_TYPE,name='O',surface='/World/Ball',count=500,surface_slope_max=70.0,surface_normal=1)
    oa=out(a);ob=out(b);assert len(oa['ids'])==500 and np.array_equal(oa['pos'],ob['pos']) and np.array_equal(oa['ids'],ob['ids'])                                                         # Keep By Direction off: the previous release exactly
    assert a.hdaModule().surface_info(a)==b.hdaModule().surface_info(b)

def main():
    for name,func in (('Maths: the cone (hard, soft, opposite, per-triangle directions) and the weighted triangle sampling',maths),
                      ('On a cube: top, sides, +X, opposite, diagonal, 180 = the same points as off, By Density counts the kept area, slope limits, Count stays exact and stable, errors, nothing kept',cube),
                      ('On a sphere: a cap of the right size, a soft edge thins the density towards the border',sphere),
                      ('Light Prim: a distant light down / east, a lamp above, a wide cone, dome and missing light refused, Vector ignores the light',light),
                      ('Contract: parameters, defaults, menu, conditionals, module functions, no dollar signs',contract),
                      ('The previous release unchanged with Keep By Direction off',unchanged)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_surfdir_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
