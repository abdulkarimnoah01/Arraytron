"""v1.28.0 Mask painted with Houdini's own Attribute Paint brush, in real Houdini: hython tests/validate_hpaint.py [version]
Paint Mask With Houdini Brush builds a paint helper (a geo object in /obj: the scattering surface as a dense mesh with a float point attribute mask, an Attribute Paint SOP, OUT) and enters the brush; Finish And
Scatter reads the painted attribute back into a grid (mask_hpaint_data) that the mask source Houdini Paint reads. The brush itself needs the interface (not tested: GUI); everything around it is: the dense surface,
the helper network, the painting simulated by a wrangle after the Attribute Paint SOP, the bake into the grid, the scatter that follows, the remap, saving, clearing. Env ARRAYTRON_MUTATE=hp_weld|hp_dense|hp_grid|
hp_base|hp_axis|hp_blur|hp_attr breaks the module; the suite must FAIL."""
from pathlib import Path
import hou, json, math, os, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v1.34.0':'v1.33.0','v1.33.0':'v1.32.0','v1.32.0':'v1.31.1','v1.31.1':'v1.31.0','v1.31.0':'v1.30.1','v1.30.1':'v1.30.0','v1.30.0':'v1.29.0','v1.28.0':'v1.27.0','v1.29.0':'v1.28.0'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_hpaint_'));checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')
def write_scene():
    path=WORK/'hpaint.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    UsdGeom.Xform.Define(s,'/World/Props/Tree');UsdGeom.Cube.Define(s,'/World/Props/Tree/C').CreateSizeAttr(0.2)
    m=UsdGeom.Mesh.Define(s,'/World/Terrain');m.CreatePointsAttr([(-20,0,-20),(20,0,-20),(20,0,20),(-20,0,20)]);m.CreateFaceVertexCountsAttr([4]);m.CreateFaceVertexIndicesAttr([0,3,2,1]);m.CreateSubdivisionSchemeAttr('none')
    s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
def install():
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True)
    for n in hou.node('/obj').children():n.destroy()
    install();hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
def scatter(stage,source,typ=None,name='Hp',**values):
    a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Tree');a.parm('mode').set(5);a.parm('surface_prim').set('/World/Terrain');a.parm('surface_count').set(900);a.parm('surface_seed').set(3)
    for k,v in values.items():
        if isinstance(v,(tuple,list)):a.parmTuple(k).set(v)
        else:a.parm(k).set(v)
    if typ is None:mutate(a)
    return a
def out(a):
    s=a.stage();assert not list(a.errors()),a.errors();pi=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    d=dict(pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3),ids=np.array(pi.GetIdsAttr().Get(t) or [],dtype=int))
    o=np.argsort(d['ids']);return {k:v[o] for k,v in d.items()}
def mutate(a):
    g=a.hdaModule().hpaint_grid.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='hp_weld':g['hpaint_weld']=lambda P,T:(np.asarray(P,dtype=float).reshape(-1,3),np.asarray(T,dtype=np.int64).reshape(-1,3))                                    # points are not merged: seams in the painted mesh
    elif MUTATE=='hp_dense':
        good=g['hpaint_dense'];g['hpaint_dense']=lambda P,T,target,max_tris=200000:good(P,T,1e9,max_tris)                                                                  # the surface is not subdivided
    elif MUTATE=='hp_grid':
        good=g['hpaint_grid'];g['hpaint_grid']=lambda P,mask,base,res:good(np.asarray(P).reshape(-1,3)[::2],np.asarray(mask).reshape(-1)[::2],base,res)                      # half of the points are ignored
    elif MUTATE=='hp_base':
        good=g['hpaint_values'];g['hpaint_values']=lambda text,xz,base=0.0,blur=0.0:good(text,xz,0.0,blur)                                                                  # the Unpainted Value is ignored
    elif MUTATE=='hp_axis':
        good=g['hpaint_values'];g['hpaint_values']=lambda text,xz,base=0.0,blur=0.0:good(text,np.asarray(xz).reshape(-1,2)[:,::-1],base,blur)                               # X and Z swapped
    elif MUTATE=='hp_blur':g['maskpaint_blur']=lambda grid,sigma:grid                                                                                                       # the Map Feather does nothing
    elif MUTATE=='hp_attr':
        good=g['hpaint_helper'];g['hpaint_helper']=lambda asset,create=True:(lambda geo:(geo.node('PAINT').parm('stroke_attrib').set('paintmask') if geo is not None else None,geo)[1])(good(asset,create))   # the brush paints another attribute
    elif MUTATE:raise SystemExit('unknown mutation '+MUTATE)
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()
def simulate(helper,snippet):
    """Stand in for the brush: a wrangle between the Attribute Paint SOP and OUT sets the mask the way strokes would."""
    wr=helper.createNode('attribwrangle','SIM');wr.parm('class').set(2);wr.parm('snippet').set(snippet);wr.setInput(0,helper.node('PAINT'));helper.node('OUT').setInput(0,wr);return wr

def maths():
    st,sc=new_scene('mod');a=scatter(st,sc);m=a.hdaModule()
    P=np.array([[0,0,0],[1,0,0],[1,0,1],[0,0,1],[0,0,0],[1,0,1]],dtype=float);T=np.array([[0,1,2],[3,4,5]]);Pw,Tw=m.hpaint_weld(P,T);assert len(Pw)==4 and Tw.shape==(2,3) and len(set(Tw.ravel().tolist()))==4        # a quad made of two loose triangles: four points
    Pw2,Tw2=m.hpaint_weld(np.array([[0,0,0],[1,0,0],[0,0,1],[1,0,0.0000001]]),np.array([[0,1,2],[1,3,2]]));assert len(Tw2)==1 or len(Pw2)==3                                       # a degenerate triangle is dropped
    quad=np.array([[0,0,0],[4,0,0],[4,0,4],[0,0,4.]]);tq=np.array([[0,1,2],[0,2,3]]);D,DT,longest=m.hpaint_dense(quad,tq,1.0)
    assert longest<=1.0+1e-9 and len(DT)==2*4**3 and len(D)==(8+1)**2 and np.allclose(D[:,1],0) and D[:,0].min()==0 and D[:,0].max()==4 and D[:,2].max()==4                                   # shared edge midpoints: an 9 x 9 grid of points
    assert abs(sum(np.linalg.norm(np.cross(D[t[1]]-D[t[0]],D[t[2]]-D[t[0]]))*0.5 for t in DT)-16.0)<1e-6                                                                            # the area is kept
    edges={};[edges.__setitem__(tuple(sorted(e)),edges.get(tuple(sorted(e)),0)+1) for t in DT for e in ((t[0],t[1]),(t[1],t[2]),(t[2],t[0]))];assert max(edges.values())==2         # watertight: every edge has at most two triangles
    capped,CT,_=m.hpaint_dense(quad,tq,0.001,max_tris=100);assert len(CT)<=100 and len(CT)>=2                                                                                           # the triangle cap
    _,same,_=m.hpaint_dense(quad,tq,100.0);assert len(same)==2                                                                                                                       # a coarse target leaves the mesh as it is
    xs=np.linspace(0,10,101);X,Z=np.meshgrid(xs,xs);Pt=np.stack([X.ravel(),np.zeros(X.size),Z.ravel()],axis=1);mask=(Pt[:,0]/10.0)                                                  # a ramp in X
    grid,spec=m.hpaint_grid(Pt,mask,0.0,64);x0,z0,cell,nx,nz=spec;gx=x0+np.arange(nx)*cell
    assert x0==0 and z0==0 and nx>=9 and np.allclose(grid[nz//2],np.clip(gx/10.0,0,1),atol=cell/10.0+0.02) and np.allclose(grid[0],grid[-1],atol=0.05)                                     # the ramp comes back, the same along Z
    keep=np.hypot(Pt[:,0]-5,Pt[:,2]-5)>2.0;g2,s2=m.hpaint_grid(Pt[keep],np.ones(int(keep.sum())),0.25,64);c2=s2[2];ci=int(round(5/c2));assert g2[ci,ci]==0.25 and g2.max()==1.0 and g2[int(round(7.2/c2)),ci]==1.0 and g2[int(round(2.3/c2)),ci]==1.0   # a hole in the points: filled from its neighbours at the border, the base in the middle
    txt=m.hpaint_encode(grid,spec);back,bspec=m.hpaint_decode(txt);assert bspec[3:]==spec[3:] and np.allclose(bspec[:3],spec[:3],atol=1e-6) and np.abs(back-grid).max()<1/65535.0+1e-12 and json.loads(txt)['v']==1   # the text round trip
    assert m.hpaint_decode('') is None and m.hpaint_decode('   ') is None
    for bad in ('nope','{"nx":2}','{"nx":2,"nz":2,"x0":0,"z0":0,"cell":1,"data":"@@"}'):
        try:m.hpaint_decode(bad);assert False,bad
        except ValueError as e:assert 'cannot be read' in str(e)
    v=m.hpaint_values(txt,np.array([[5.0,5.0],[2.5,7.0],[-50.0,0.0],[99.0,99.0]]),0.4);assert abs(v[0]-0.5)<0.03 and abs(v[1]-0.25)<0.03 and v[2]==0.4 and v[3]==0.4                          # read at points, `base` beyond the map
    assert np.allclose(m.hpaint_values('',np.zeros((3,2)),0.7),0.7)                                                                                                                  # nothing baked: the base everywhere
    step=np.zeros((60,60));step[:,30:]=1.0;sp=(0.0,0.0,1.0,60,60);st_=m.hpaint_encode(step,sp);hard=m.hpaint_values(st_,np.array([[29.0,30.0],[31.0,30.0]]),0.0);soft=m.hpaint_values(st_,np.array([[29.0,30.0],[31.0,30.0]]),0.0,3.0)
    assert hard[0]<0.01 and hard[1]>0.99 and 0.01<soft[0]<0.45 and 0.55<soft[1]<0.99                                                                                                  # the Map Feather softens the border

def helper_network():
    st,sc=new_scene('helper');a=scatter(st,sc,mask_brush_value=0.8,mask_brush_bg=0.1,mask_brush_radius=3.0,mask_brush_feather=0.4,mask_brush_strength=0.7,mask_paint_base=0.2);m=a.hdaModule()
    assert m.hpaint_helper(a,create=False) is None;geo=m.hpaint_helper(a);assert geo.path()=='/obj/Hp'+m.HPAINT_HELPER_SUFFIX and geo.userData('arraytron_node')==a.path() and a.userData('arraytron_hpaint')==geo.path()
    assert [c.name() for c in geo.children() if c.name() in ('SURFACE','PAINT','OUT')]==['SURFACE','PAINT','OUT'] or sorted(c.name() for c in geo.children())==['OUT','PAINT','SURFACE']
    paint=geo.node('PAINT');assert paint.type().name()=='attribpaint' and paint.evalParm('stroke_attrib')=='mask' and abs(paint.evalParm('fgfloat')-0.8)<1e-9 and abs(paint.evalParm('bgfloat')-0.1)<1e-9
    assert abs(paint.evalParm('stroke_radius')-3.0)<1e-9 and abs(paint.evalParm('stroke_softedge')-0.4)<1e-9 and abs(paint.evalParm('stroke_opacity')-0.7)<1e-9 and paint.isDisplayFlagSet() and paint.type().defaultState()                # the brush starts with the settings of the node
    assert m.hpaint_helper(a).path()==geo.path() and len([n for n in hou.node('/obj').children() if n.name().startswith('Hp')])==1                                                   # reused, not duplicated
    g=geo.node('OUT').geometry();Pt=np.array(g.pointFloatAttribValues('P')).reshape(-1,3);mk=np.array(g.pointFloatAttribValues('mask'))
    assert len(Pt)>20000 and np.allclose(Pt[:,1],0) and Pt[:,0].min()==-20 and Pt[:,0].max()==20 and Pt[:,2].min()==-20 and np.allclose(mk,0.2) and len(g.prims())>=2*len(Pt)//2.2        # the dense surface, the mask at the Unpainted Value
    coarse=scatter(st,sc,name='Coarse',mask_hpaint_detail=40);gc=m.hpaint_helper(coarse).node('OUT').geometry();assert 1000<len(gc.points())<len(Pt)/5                                       # Paint Detail
    area=scatter(st,sc,name='Area',mask_hpaint_plane=6.0);area.parm('mode').set(1);ga=area.hdaModule().hpaint_helper(area).node('OUT').geometry();Pa=np.array(ga.pointFloatAttribValues('P')).reshape(-1,3)
    assert abs(np.abs(Pa[:,0]).max()-3.0)<1e-9 and abs(np.abs(Pa[:,2]).max()-3.0)<1e-9 and np.allclose(Pa[:,1],0)                                                                    # no surface: a flat Plane Size square
    started=m.hpaint_start(a);assert started.path()==geo.path() and a.evalParm('mask_source')==5                                                                                     # without the interface the button builds the helper and switches the source
    assert not paint.errors() and not geo.node('SURFACE').errors()

def paint_and_scatter():
    st,sc=new_scene('scatter');base=out(scatter(st,sc,name='None',mask_source=0));P=base['pos'];inside=(P[:,0]>0)&(P[:,0]<8)&(np.abs(P[:,2])<8)
    a=scatter(st,sc,name='Hp',mask_source=5);m=a.hdaModule();assert len(out(a)['ids'])==0                                                                                            # Houdini Paint, nothing baked, Unpainted 0: no scatter
    geo=m.hpaint_helper(a);simulate(geo,'f@mask = (@P.x>0 && @P.x<8 && abs(@P.z)<8) ? 1.0 : 0.0;');cell=40.0/511*1.0
    assert m.hpaint_finish(a)>20000 and a.evalParm('mask_hpaint_data')!='' and a.evalParm('mask_source')==5                                                                         # Finish And Scatter bakes the painted attribute
    o=out(a);margin=0.8;assert len(o['ids'])>20 and set(o['ids'].tolist())<=set(base['ids'][(P[:,0]>-margin)&(P[:,0]<8+margin)&(np.abs(P[:,2])<8+margin)].tolist())                       # only in the painted rectangle
    assert set(base['ids'][(P[:,0]>margin)&(P[:,0]<8-margin)&(np.abs(P[:,2])<8-margin)].tolist())<=set(o['ids'].tolist())                                                            # every point well inside grows
    assert np.array_equal(o['pos'],P[np.isin(base['ids'],o['ids'])])                                                                                                                 # the mask never moves a point
    geo.node('SIM').parm('snippet').set('f@mask = (@P.x>0 && @P.x<8 && abs(@P.z)<8) ? 0.5 : 0.0;');m.hpaint_bake(a);half=out(a);ii=set(base['ids'][(P[:,0]>margin)&(P[:,0]<8-margin)&(np.abs(P[:,2])<8-margin)].tolist());assert 0.3<len(set(half['ids'].tolist())&ii)/len(ii)<0.7   # a painted value of 0.5: about half
    geo.node('SIM').parm('snippet').set('f@mask = @P.x/40.0+0.5;');m.hpaint_bake(a);ramp=out(a);xr=ramp['pos'][:,0];assert len(xr)>100 and xr.mean()>5.0 and np.corrcoef(xr,np.arange(len(xr)))[0,1]!=2          # a ramp: more points to the right
    ids_r=ramp['ids'];pr=P[np.isin(base['ids'],ids_r)];left=(P[:,0]<0).sum();right=(P[:,0]>0).sum();assert (pr[:,0]<-10).sum()/max(left,1)<(pr[:,0]>10).sum()/max(right,1)*0.6
    a.parm('mask_paint_base').set(1.0);geo.node('SIM').parm('snippet').set('f@mask = (abs(@P.x)<6 && abs(@P.z)<6) ? 0.0 : 1.0;');m.hpaint_bake(a);hole=out(a);inner=base['ids'][(np.abs(P[:,0])<6-margin)&(np.abs(P[:,2])<6-margin)]
    assert not set(inner.tolist())&set(hole['ids'].tolist()) and set(base['ids'][(np.abs(P[:,0])>6+margin)|(np.abs(P[:,2])>6+margin)].tolist())<=set(hole['ids'].tolist())                  # a hole painted in a full scatter
    a.parm('mask_paint_base').set(0.0);geo.node('SIM').parm('snippet').set('f@mask = (@P.x>0 && @P.x<8 && abs(@P.z)<8) ? 1.0 : 0.0;');m.hpaint_bake(a);hard=out(a);a.parm('mask_paint_blur').set(2.0);soft=out(a)
    assert set(soft['ids'].tolist())!=set(hard['ids'].tolist()) and len(set(soft['ids'].tolist())-set(hard['ids'].tolist()))>0                                                          # Map Feather works on the Houdini paint
    a.parm('mask_paint_blur').set(0.0);a.parmTuple('mask_outrange').set((1.0,0.0));flip=out(a);assert not set(flip['ids'].tolist())&set(base['ids'][(P[:,0]>margin)&(P[:,0]<8-margin)&(np.abs(P[:,2])<8-margin)].tolist()) and len(flip['ids'])>200   # the Output Range flips it
    a.parmTuple('mask_outrange').set((0.0,1.0));a.parm('mask_gamma').set(2.0);assert not a.errors() and len(out(a)['ids'])>=len(hard['ids'])                                           # Gamma: at least as many
    a.parm('mask_gamma').set(1.0);full=scatter(st,sc,name='Full',mask_source=5,mask_paint_base=1.0);fg=full.hdaModule().hpaint_helper(full);full.hdaModule().hpaint_bake(full);assert np.array_equal(out(full)['ids'],base['ids'])   # painted nothing, base 1: the full scatter
    try:scatter(st,sc,name='NoHelper',mask_source=5).hdaModule().hpaint_bake(hou.node('/stage/NoHelper'));assert False
    except hou.NodeError as e:assert 'no paint to finish' in str(e)

def persistence_and_info():
    st,sc=new_scene('persist');a=scatter(st,sc,name='Info',mask_source=5);m=a.hdaModule();assert 'Nothing baked' in m.hpaint_info(a) and 'Nothing baked' in m.mask_info(a)
    geo=m.hpaint_helper(a);assert 'A paint helper exists' in m.hpaint_info(a);simulate(geo,'f@mask = @P.x>0 ? 1.0 : 0.25;');m.hpaint_bake(a);info=m.hpaint_info(a);assert 'baked' in info and 'min 0.25' in info and 'max 1' in info and 'Kept' in m.mask_info(a)
    text=a.evalParm('mask_hpaint_data');gp=geo.path();path=str(WORK/'persist.hip');hou.hipFile.save(path);hou.hipFile.load(path,suppress_save_prompt=True);b=hou.node('/stage/Info');assert b.evalParm('mask_hpaint_data')==text and b.userData('arraytron_hpaint')==gp and hou.node(gp) is not None   # saved with the scene, the helper too
    assert b.hdaModule().hpaint_clear(b)==True and b.evalParm('mask_hpaint_data')=='' and hou.node(gp) is None and not b.userData('arraytron_hpaint') and b.hdaModule().hpaint_clear(b)==False
    b.parm('mask_hpaint_data').set('garbage');assert 'cannot be read' in b.hdaModule().hpaint_info(b)
    try:b.hdaModule().hpaint_field(b,np.zeros((2,3)));assert False
    except hou.NodeError as e:assert 'cannot be read' in str(e)
    b.parm('mask_source').set(0);assert 'No mask' in b.hdaModule().mask_info(b)

def contract():
    st,sc=new_scene('contract');a=scatter(st,sc,name='C');g=a.parmTemplateGroup()
    for n in ('mask_hpaint_start','mask_hpaint_finish','mask_hpaint_clear','mask_hpaint_detail','mask_hpaint_plane','mask_hpaint_data'):assert g.find(n) is not None,n
    assert g.find('mask_source').menuLabels()==('None','Noise','Image','Mesh Primvar','Painted','Houdini Paint') and a.evalParm('mask_source')==0
    assert g.find('mask_hpaint_detail').defaultValue()==(150,) and g.find('mask_hpaint_plane').defaultValue()==(20.0,) and a.evalParm('mask_hpaint_data')=='' and g.find('mask_hpaint_data').isHidden()
    for n,call in (('mask_hpaint_start','hpaint_start'),('mask_hpaint_finish','hpaint_finish'),('mask_hpaint_clear','hpaint_clear')):assert g.find(n).scriptCallback().endswith("%s(kwargs['node'])"%call),n
    assert g.find('mask_hpaint_start').conditionals()[hou.parmCondType.HideWhen]=='{ mask_source != 5 }' and g.find('mask_paint_base').conditionals()[hou.parmCondType.HideWhen]=='{ mask_source != 4 mask_source != 5 }' and g.find('mask_paint_start').conditionals()[hou.parmCondType.HideWhen]=='{ mask_source != 4 }'
    assert '{ mask_source == 5 }' in g.find('mask_prim').conditionals()[hou.parmCondType.HideWhen]
    text_=a.type().definition().sections()['PythonModule'].contents();assert '$' not in text_.split('# ---- Houdini Paint mask')[1]
    for n in ('hpaint_weld','hpaint_dense','hpaint_grid','hpaint_encode','hpaint_decode','hpaint_values','sop_hpaint_surface','hpaint_helper','hpaint_start','hpaint_bake','hpaint_finish','hpaint_clear','hpaint_field','hpaint_info','hpaint_surface','hpaint_has_surface'):assert hasattr(a.hdaModule(),n),n
    helper=a.hdaModule().hpaint_helper(a);assert helper.node('SURFACE').parm('python').eval()==a.hdaModule().HPAINT_SOP;a.hdaModule().hpaint_clear(a)

def unchanged():
    st,sc=new_scene('same');values=dict(mask_source=1,mask_noise_freq=0.6,mask_noise_contrast=2.5,mask_low=0.2,mask_high=0.9,mask_effect=2,mask_minscale=0.3,mask_invert=1)
    pa=out(scatter(st,sc,name='N',**values));ob=st.createNode(OLD_TYPE,'O');ob.setInput(0,sc);ob.parm('protos').set(1);ob.parm('proto_prim1').set('/World/Props/Tree');ob.parm('mode').set(5);ob.parm('surface_prim').set('/World/Terrain');ob.parm('surface_count').set(900);ob.parm('surface_seed').set(3)
    for k,v in values.items():ob.parm(k).set(v)
    pb=out(ob);assert len(pa['ids'])>50 and np.array_equal(pa['ids'],pb['ids']) and np.array_equal(pa['pos'],pb['pos'])                                                 # the previous release exactly (noise mask)
    txt=json.dumps({'v':1,'stamps':[[0,0,0,0,6,1.0,0.5,1.0,1]]});pc=out(scatter(st,sc,name='P',mask_source=4,mask_paint_data=txt));od=st.createNode(OLD_TYPE,'P0');od.setInput(0,sc);od.parm('protos').set(1);od.parm('proto_prim1').set('/World/Props/Tree');od.parm('mode').set(5);od.parm('surface_prim').set('/World/Terrain');od.parm('surface_count').set(900);od.parm('surface_seed').set(3)
    od.parm('mask_source').set(4);od.parm('mask_paint_data').set(txt);pd=out(od);assert len(pc['ids'])>10 and np.array_equal(pc['ids'],pd['ids'])                                         # ... and the painted mask of v1.27.0

def main():
    for name,func in (('Maths: weld, the uniform subdivision (shared points, area, watertight, cap), the points as a map, the text, reading it, Map Feather',maths),
                      ('The paint helper: network, brush settings from the node, reuse, Paint Detail, Plane Size, the button without an interface',helper_network),
                      ('Painting simulated after the Attribute Paint SOP, Finish And Scatter: region, value, ramp, hole, Map Feather, remap, nothing painted',paint_and_scatter),
                      ('The map saved with the scene (and the helper), the read-out, clearing, a broken text',persistence_and_info),
                      ('Contract: parameters, defaults, menu, conditionals, callbacks, module functions, no dollar signs',contract),
                      ('The previous release unchanged',unchanged)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_hpaint_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
