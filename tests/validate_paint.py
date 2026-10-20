"""Viewport brush (v0.6.0) validation in real Houdini: hython tests/validate_paint.py
The brush maths (stroke storage, falloff, Add with spacing and projection, Remove) is checked against independent re-implementations and brute
force; the Paint mode is checked end to end through the real HDA (PointInstancer positions, ids, orientations, edits that keep ids stable, the
other stages on top). The Python Viewer State is exercised headlessly with a stand-in for the viewport (stub drawables, scripted mouse events).
What this does NOT show: the look and feel of the tool in a real Scene Viewer (see STATUS.md). Env ARRAYTRON_MUTATE=<name> breaks the module; the suite must FAIL."""
from pathlib import Path
import ast, hou, json, math, os, sys, tempfile, time, types
import numpy as np
from pxr import Usd, UsdGeom, Gf
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v0.6.0':'v0.5.2','v0.7.0':'v0.6.0','v0.8.0':'v0.7.0','v0.9.0':'v0.8.0','v1.0.0':'v0.9.0','v1.1.0':'v1.0.0','v1.5.0':'v1.1.0','v1.6.0':'v1.5.0','v1.6.1':'v1.6.0','v1.6.2':'v1.6.1','v1.7.0':'v1.6.2','v1.8.0':'v1.7.0','v1.9.0':'v1.8.0','v1.10.0':'v1.9.0','v1.11.0':'v1.10.0','v1.12.0':'v1.11.0','v1.9.0':'v1.8.0','v1.10.0':'v1.9.0','v1.11.0':'v1.10.0','v1.12.0':'v1.11.0'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_paint_'))
checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')
TILT=(0.0,-0.8,0.6)                       # normal of the tilted test plane (unit: 0.64+0.36 = 1)
def write_scene():
    path=WORK/'paint.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    ball=UsdGeom.Sphere.Define(s,'/World/Props/Ball/S');ball.CreateRadiusAttr(0.1)
    UsdGeom.Xform.Define(s,'/World/Props/Ball')
    big=UsdGeom.Sphere.Define(s,'/World/Terrain/Dome');big.CreateRadiusAttr(2.0)                    # smooth surface
    # a tilted plane: through the origin with normal n = (0, 0.8, 0.6); spanned by u = (1,0,0) and v = n x u
    n=np.array([0.0,0.8,0.6]);u=np.array([1.0,0.0,0.0]);v=np.cross(n,u)
    quad=[tuple((a*u+b*v+np.array([10.0,0.0,0.0])).tolist()) for a,b in ((-3,-3),(3,-3),(3,3),(-3,3))]       # 6 x 6 at x offset 10
    m=UsdGeom.Mesh.Define(s,'/World/Slope/Quad');m.CreatePointsAttr(quad);m.CreateFaceVertexCountsAttr([4]);m.CreateFaceVertexIndicesAttr([0,1,2,3]);m.CreateOrientationAttr('rightHanded')
    s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
def new_scene(name='scene',old=False):
    hou.hipFile.clear(suppress_save_prompt=True)
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
def arraytron(stage,source,typ=None,name='Arraytron',**values):
    a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Ball')
    for key,value in values.items():a.parmTuple(key).set(value if isinstance(value,(tuple,list)) else (value,))
    if typ is None and MUTATE:mutate(a)
    return a
def out(a):
    s=a.stage();assert not a.errors(),a.errors()
    pi=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    return dict(pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3),ids=list(pi.GetIdsAttr().Get(t) or []),
                quat=np.array([[q.GetImaginary()[0],q.GetImaginary()[1],q.GetImaginary()[2],q.GetReal()] for q in (pi.GetOrientationsAttr().Get(t) or [])]).reshape(-1,4),scales=np.array(pi.GetScalesAttr().Get(t) or []).reshape(-1,3))
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()
def rotate_y(q):
    x,y,z,w=q;return np.array([2*(x*y-z*w),1-2*(x*x+z*z),2*(y*z+x*w)])
def mutate(a):
    g=a.hdaModule().paint_decode.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='paint_falloff':g['falloff_weight']=lambda t,kind:np.where(np.asarray(t)<=1.0,1.0,0.0)
    elif MUTATE=='paint_spacing':
        good=g['brush_add'];g['brush_add']=lambda data,c,n,r,d,sp,f,s,seed,p:good(data,c,n,r,d,0.0,f,s,seed,p)
    elif MUTATE=='paint_project':
        g['make_projector']=lambda surface,center,radius,smooth=True:(lambda pts,normal:(np.asarray(pts),np.tile(np.asarray(normal,dtype=float),(len(pts),1)),np.ones(len(pts),dtype=bool)))
    elif MUTATE=='paint_remove':g['brush_remove']=lambda data,center,radius,falloff,strength,seed:({'pts':data['pts'],'dab':data['dab']+1,'next':data['next']},0)
    elif MUTATE=='paint_seed':
        good=g['dab_candidates'];g['dab_candidates']=lambda c,n,r,d,seed,dab:good(c,n,r,d,1,dab)
    elif MUTATE=='paint_ids':
        good=g['brush_add'];g['brush_add']=lambda *a,**k:(lambda new,c:(dict(new,pts=np.column_stack([new['pts'][:,:6],np.arange(len(new['pts']))*2.0]) if len(new['pts']) else new['pts'],next=new['next']),c))(*good(*a,**k))
    elif MUTATE in ('paint_resize','paint_wheel','paint_shift'):pass                                                    # applied to the viewer state source in brush_shortcuts()
    else:raise SystemExit('unknown mutation '+MUTATE)
def all_errors(node):
    out=list(node.errors())
    for c in node.children():out+=all_errors(c)
    return out
def module():
    st,sc=new_scene('mod');a=arraytron(st,sc);return a,a.hdaModule()
def flat_project(points,normal):
    pts=np.asarray(points,dtype=float).copy();pts[:,1]=0.0;return pts,np.tile([0.0,1.0,0.0],(len(pts),1)),np.ones(len(pts),dtype=bool)

# ------------------------------------------------------------------ groups
def a_icon(d):return d.icon()=='opdef:/arraytron::Lop/instancer::%s?Icon.svg'%VID[1:]
def ui_contract():
    st,sc=new_scene('ui');a=arraytron(st,sc);g=a.parmTemplateGroup()
    mode=g.find('mode');assert mode.menuLabels()[6]=='Paint' and len(mode.menuItems())>=7 and mode.defaultValue()==0
    for name in ('paint_start','paint_prim','paint_op','paint_radius','paint_strength','paint_density','paint_spacing','paint_falloff','paint_seed','paint_align','paint_offset','paint_info','paint_clear','paint_data'):
        t=g.find(name);assert t is not None,name
        if name!='paint_data':assert '{ mode != 6 }' in t.conditionals()[hou.parmCondType.HideWhen],name
    assert g.find('paint_data').isHidden() and g.find('paint_start').type()==hou.parmTemplateType.Button
    assert g.find('paint_falloff').menuLabels()==('Linear','Smooth','Gaussian','Hard') and g.find('paint_op').menuLabels()[:2]==('Add','Remove')
    assert g.find('paint_start').scriptCallback().endswith("paint_start(kwargs['node'])") and g.find('paint_clear').scriptCallback().endswith("paint_clear(kwargs['node'])")
    # the Paint settings sit in the Layout tab under their own heading, after the Surface ones
    tabs=g.entries();layout=[t for t in tabs if t.label()=='Layout'][0];names=[t.name() for t in layout.parmTemplates()]
    assert names.index('paint_prim')>names.index('surface_prim') and names.index('paint_start')<names.index('paint_prim')
    heads=[t.columnLabels()[0] for t in layout.parmTemplates() if t.name().startswith('ui_head')];assert 'PAINT SETTINGS' in heads,heads
    # every v0.5.2 parameter is still there with the same type, default and menu
    old=hou.hda.definitionsInFile(str(versions.hda(PREVIOUS)))[0].parmTemplateGroup()
    def flat(group):
        res={}
        def walk(ts):
            for t in ts:
                if t.type()==hou.parmTemplateType.Folder and t.folderType()!=hou.folderType.MultiparmBlock:walk(t.parmTemplates())
                else:res[t.name()]=t
        walk(group.entries());return res
    fo,fn=flat(old),flat(g)
    for name,t in fo.items():
        if name.startswith(('ui_','tab_')):continue
        n=fn[name];assert n.type()==t.type() and n.numComponents()==t.numComponents(),name
        if hasattr(t,'defaultValue'):assert n.defaultValue()==t.defaultValue(),name
        if t.type()==hou.parmTemplateType.Menu:assert n.menuItems()[:len(t.menuItems())]==t.menuItems() and n.menuLabels()[:len(t.menuLabels())]==t.menuLabels(),name
    d=a.type().definition();sections=d.sections()
    assert sections['DefaultState'].contents().strip()=='arraytron_paint_'+VID.replace('.','') and 'createViewerStateTemplate' in sections['ViewerStateModule'].contents()
    assert 'register_pystate_embedded' in sections['ViewerStateInstall'].contents()
    assert sections['Icon.svg'].contents()==(ROOT/'icon'/'Arraytron-Clean.svg').read_text(encoding='utf8') and a_icon(d)
    labels=[a.type().inputLabel(i) if hasattr(a.type(),'inputLabel') else '' for i in range(4)]
    text=sections['DialogScript'].contents()
    for line in ('Scene Stream: terrain, curve, models','Input 2: extra prototype (optional)','Input 3: extra prototype (optional)','Input 4: extra prototype (optional)'):assert '"%s"'%line in text,line
def defaults_unchanged():
    st,sc=new_scene('defaults')
    cases=[dict(mode=0,line_count=7),dict(mode=1,area_count=40,area_seed=3),dict(mode=2),dict(mode=3),dict(mode=5,surface_prim='/World/Terrain',surface_count=50,surface_seed=2)]
    for values in cases:
        new=arraytron(st,sc,**values);old=arraytron(st,sc,typ=OLD_TYPE,**values);a,b=out(new),out(old)
        assert len(a['pos'])==len(b['pos'])>0 and np.array_equal(a['ids'],b['ids']) and np.allclose(a['pos'],b['pos'],atol=1e-6) and np.allclose(a['quat'],b['quat'],atol=2e-3) and np.allclose(a['scales'],b['scales']),values
def storage():
    a,m=module();rng=np.random.default_rng(5);pts=np.column_stack([rng.normal(size=(300,3))*5,np.tile([0,1.0,0],(300,1)),np.arange(300)*3+7.0])
    d={'pts':pts,'dab':41,'next':1000};text=m.paint_encode(d);back=m.paint_decode(text)
    assert back['dab']==41 and back['next']==1000 and np.array_equal(back['pts'][:,6],pts[:,6]) and np.allclose(back['pts'][:,:6],pts[:,:6],atol=1e-5*np.abs(pts[:,:6]).max())
    assert m.paint_encode(back)==text                                                                    # round trip is stable (no drift on repeated saves)
    empty=m.paint_decode('');assert len(empty['pts'])==0 and empty['next']==0 and m.paint_decode(m.paint_encode(empty))['pts'].shape==(0,7)
    for bad in ('garbage','p2:0:0:0:','p1:5:0:0:'+text.split(':',4)[4]):
        try:m.paint_decode(bad);raise AssertionError('accepted '+bad[:20])
        except ValueError:pass
    assert len(text)<300*40
def falloff():
    a,m=module();t=np.linspace(0,1.2,25);w=m.falloff_weight(t,0)
    ref=[np.clip(1-x,0,1) if x<=1 else 0 for x in t];assert np.allclose(w,ref)
    ref=[(1-(3*x*x-2*x**3)) if x<=1 else 0 for x in t];assert np.allclose(m.falloff_weight(t,1),ref)
    ref=[math.exp(-4.5*x*x) if x<=1 else 0 for x in t];assert np.allclose(m.falloff_weight(t,2),ref)
    ref=[1.0 if x<=1 else 0 for x in t];assert np.allclose(m.falloff_weight(t,3),ref)
    assert m.falloff_weight(0.0,0)==1 and m.falloff_weight(1.0,0)==0 and m.falloff_weight(1.0,1)==0 and m.falloff_weight(1.0,3)==1
def add_basics():
    a,m=module();c=np.array([0.3,0.0,-0.2]);n=np.array([0.0,1.0,0.0]);d0=m.paint_empty()
    d1,k1=m.brush_add(d0,c,n,1.0,100.0,0.0,3,1.0,1,flat_project)
    expected=100*math.pi;assert abs(k1-expected)<5*math.sqrt(expected) and k1==len(d1['pts']),(k1,expected)          # density x area, Poisson-like spread
    p=d1['pts'];assert np.all(np.linalg.norm(p[:,[0,2]]-c[[0,2]],axis=1)<=1.0+1e-9) and np.allclose(p[:,1],0) and np.allclose(p[:,3:6],[0,1,0])
    assert list(p[:,6])==list(range(k1)) and d1['next']==k1 and d1['dab']==1
    d1b,k1b=m.brush_add(d0,c,n,1.0,100.0,0.0,3,1.0,1,flat_project);assert np.array_equal(d1b['pts'],d1['pts'])           # deterministic
    d1c,_=m.brush_add(d0,c,n,1.0,100.0,0.0,3,1.0,2,flat_project);assert not np.array_equal(d1c['pts'],d1['pts'])           # the seed matters
    z,kz=m.brush_add(d0,c,n,1.0,100.0,0.0,3,0.0,1,flat_project);assert kz==0 and len(z['pts'])==0                          # strength 0 paints nothing
    half,kh=m.brush_add(d0,c,n,1.0,100.0,0.0,3,0.5,1,flat_project);assert abs(kh-0.5*expected)<5*math.sqrt(expected)     # strength is a keep chance
    d2,k2=m.brush_add(d1,c+np.array([0.5,0,0]),n,1.0,100.0,0.0,3,1.0,1,flat_project)
    assert np.array_equal(d2['pts'][:k1],d1['pts']) and list(d2['pts'][k1:,6])==list(range(k1,k1+k2))                    # earlier points keep their place and id
    low,kl=m.brush_add(d0,c,n,1.0,0.05,0.0,3,1.0,1,flat_project);assert kl<=2                                              # a low density still paints a little
def add_falloff():
    a,m=module();c=np.zeros(3);n=np.array([0.0,1.0,0.0]);d0=m.paint_empty()
    for kind,(lo,hi) in {0:(2.0,100),1:(1.5,100),2:(1.5,100),3:(0.7,1.4)}.items():
        d,_=m.brush_add(d0,c,n,1.0,2000.0,0.0,kind,1.0,4,flat_project);r=np.linalg.norm(d['pts'][:,[0,2]],axis=1);inner=np.sum(r<0.5);outer=np.sum(r>=0.5)
        # a disc is 1/4 inner area, 3/4 outer area: Hard gives a ratio inner/outer of 1/3; soft falloffs push points to the centre
        ratio=inner/max(outer,1);assert lo*0.15<=ratio<=hi,(kind,ratio)
        if kind==3:assert 0.28<ratio<0.40,ratio
        else:assert ratio>0.5,(kind,ratio)
def add_spacing():
    a,m=module();c=np.zeros(3);n=np.array([0.0,1.0,0.0]);d=m.paint_empty()
    for k in range(6):d,_=m.brush_add(d,c+np.array([0.15*k,0,0.1*k]),n,1.0,400.0,0.12,3,1.0,5,flat_project)
    p=d['pts'][:,:3];assert len(p)>20;dist=np.linalg.norm(p[:,None]-p[None],axis=2);np.fill_diagonal(dist,9);assert dist.min()>=0.12-1e-9,dist.min()     # no two closer than the spacing
    loose=m.paint_empty()
    for k in range(6):loose,_=m.brush_add(loose,c+np.array([0.15*k,0,0.1*k]),n,1.0,400.0,0.0,3,1.0,5,flat_project)
    assert len(loose['pts'])>len(p)
    # packed: the 1.0-radius disc cannot hold more than (area / (pi (s/2)^2)) points of spacing s -> saturation, repeated painting adds nothing
    sat=d;before=len(sat['pts'])
    for k in range(10):sat,_=m.brush_add(sat,c,n,1.0,400.0,0.12,3,1.0,5,flat_project)
    assert len(sat['pts'])<=before*2.2
def remove():
    a,m=module();c=np.array([0.0,0.0,0.0]);n=np.array([0.0,1.0,0.0]);d,_=m.brush_add(m.paint_empty(),c,n,2.0,50.0,0.0,3,1.0,1,flat_project);base=d['pts'].copy()
    far=np.array([1.5,0.0,0.0]);gone=np.linalg.norm(base[:,:3]-far,axis=1)<=0.5
    d2,k=m.brush_remove(d,far,0.5,3,1.0,1);assert k==gone.sum()>0 and np.array_equal(d2['pts'],base[~gone])                 # exactly the points inside, the others untouched, ids kept
    d3,k3=m.brush_remove(d,far,0.5,3,0.0,1);assert k3==0 and np.array_equal(d3['pts'],base)
    d4,k4=m.brush_remove(d,far,0.5,0,1.0,1);rem=np.linalg.norm(base[:,:3]-far,axis=1);assert 0<k4<gone.sum() and np.all(rem[~np.isin(base[:,6],d4['pts'][:,6])]<=0.5)   # Linear falloff keeps some of the rim
    assert d2['next']==d['next'] and d2['dab']==d['dab']+1
    d5,_=m.brush_add(d2,far,n,0.5,50.0,0.0,3,1.0,1,flat_project);assert d5['pts'][-1,6]==d['next']+len(d5['pts'])-len(d2['pts'])-1       # new ids never reuse removed ones
    assert not set(d5['pts'][len(d2['pts']):,6])&set(base[:,6])
def projection():
    st,sc=new_scene('proj');a=arraytron(st,sc);m=a.hdaModule()
    a.parm('paint_prim').set('/World/Slope');a.parm('mode').set(6)
    surface=m.paint_surface(a);P,T,area,normals,vn=surface;assert len(T)==2
    n=np.array([0.0,0.8,0.6]);centre=np.array([10.0,0.0,0.0]);project=m.make_projector(surface,centre,1.0,True)
    d,k=m.brush_add(m.paint_empty(),centre,n,1.0,60.0,0.0,3,1.0,1,project);p=d['pts'];assert k>100
    assert np.allclose((p[:,:3]-centre)@n,0,atol=1e-5) and np.allclose(p[:,3:6],n,atol=1e-5)                              # exactly on the plane, normal = the plane's
    # the brush looks from the side: a dab whose normal is tilted off the surface still lands on it
    d2,k2=m.brush_add(m.paint_empty(),centre,np.array([0.0,1.0,0.0]),1.0,60.0,0.0,3,1.0,1,m.make_projector(surface,centre,1.0,True));assert k2>50 and np.allclose((d2["pts"][:,:3]-centre)@n,0,atol=1e-5)
    # a dab off the quad (all candidates miss) adds nothing, without an error
    away=np.array([40.0,0.0,0.0]);d3,k3=m.brush_add(m.paint_empty(),away,n,1.0,60.0,0.0,3,1.0,1,m.make_projector(surface,away,1.0,True));assert k3==0
    # a smooth dome: the points lie on the sphere and the normals point outwards
    a.parm('paint_prim').set('/World/Terrain');s2=m.paint_surface(a);top=np.array([0.0,2.0,0.0]);pr=m.make_projector(s2,top,0.6,True)
    d4,k4=m.brush_add(m.paint_empty(),top,np.array([0.0,1.0,0.0]),0.6,80.0,0.0,3,1.0,1,pr);q=d4['pts'];assert k4>30
    rad=np.linalg.norm(q[:,:3],axis=1);assert np.all(rad>1.96)and np.all(rad<=2.0+1e-6),(rad.min(),rad.max())              # the mesh of the sphere is inscribed
    assert np.all(np.einsum('ij,ij->i',q[:,3:6],q[:,:3]/rad[:,None])>0.97)
    # an empty Paint Target paints on the ground plane at Y = 0
    a.parm('paint_prim').set('');g=m.paint_surface(a);t,j=m.ray_triangles(np.array([[3.0,5.0,-2.0]]),np.array([0.0,-1.0,0.0]),g[0],g[1]);assert abs(t[0]-5.0)<1e-9
    a.parm('paint_prim').set('/World/Nothing')
    try:m.paint_surface(a);raise AssertionError('missing prim accepted')
    except hou.Error:pass
def ray_test():
    a,m=module();P=np.array([[0,0,0],[1,0,0],[0,1,0.0]]);T=np.array([[0,1,2]])
    t,j=m.ray_triangles(np.array([[0.2,0.2,2.0],[0.9,0.9,2.0],[0.2,0.2,-3.0]]),np.array([0.0,0.0,-1.0]),P,T)
    assert abs(t[0]-2.0)<1e-9 and j[0]==0 and np.isinf(t[2]) and j[2]==-1
    assert np.isinf(t[1]) and j[1]==-1
    t,j=m.ray_triangles(np.array([[0.2,0.2,-3.0]]),np.array([0.0,0.0,1.0]),P,T);assert abs(t[0]-3.0)<1e-9                       # both faces count
    t,j=m.ray_triangles(np.array([[0.2,0.2,2.0]]),np.array([0.0,0.0,1.0]),P,T);assert np.isinf(t[0])                         # a hit behind the origin is no hit
def node_end_to_end():
    st,sc=new_scene('e2e');a=arraytron(st,sc,mode=6,paint_prim='/World/Terrain');m=a.hdaModule()
    d0=out(a);assert len(d0['pos'])==0 and 'Nothing painted' in a.parm('paint_info').eval()                              # nothing painted: empty, no error
    surface=m.paint_surface(a);centre=np.array([0.0,2.0,0.0]);d=m.paint_empty()
    for k in range(4):
        c=centre+np.array([0.25*k,0,0]);c=c*(2.0/np.linalg.norm(c));d,_=m.brush_add(d,c,c/np.linalg.norm(c),0.5,200.0,0.05,1,1.0,3,m.make_projector(surface,c,0.5,True))
    m.paint_apply(a,d);o=out(a);pts=d['pts'];assert len(o['pos'])==len(pts)>40 and sorted(o['ids'])==sorted(pts[:,6].astype(int).tolist())
    order=np.argsort(o['ids']);ref=pts[np.argsort(pts[:,6])];assert np.allclose(o['pos'][order],ref[:,:3],atol=1e-5)
    for q,nrm in zip(o['quat'][order],ref[:,3:6]):assert np.allclose(rotate_y(q),nrm,atol=3e-3)                       # Align to Normal 1: +Y onto the painted normal
    a.parm('paint_align').set(0.0);o2=out(a);assert np.allclose(o2['quat'],[0,0,0,1],atol=2e-3)
    a.parm('paint_align').set(1.0);a.parm('paint_offset').set(0.5);o3=out(a);o3=o3['pos'][np.argsort(o3['ids'])];assert np.allclose(o3,ref[:,:3]+ref[:,3:6]*0.5,atol=1e-5)
    a.parm('paint_offset').set(0.0)
    # Remove a part: the survivors keep their ids and positions, so everything keyed on id (variation, mask, overlap) stays put
    d2,k=m.brush_remove(d,centre,0.35,3,1.0,1);assert 0<k<len(pts);m.paint_apply(a,d2);o4=out(a)
    keep={int(i):p for i,p in zip(o['ids'],o['pos'])};assert len(o4['pos'])==len(pts)-k and all(np.allclose(keep[int(i)],p,atol=1e-6) for i,p in zip(o4['ids'],o4['pos']))
    m.paint_clear(a);assert a.evalParm('paint_data')=='' and len(out(a)['pos'])==0
    # the other stages work on painted points: variation scale, mask, No Overlap
    m.paint_apply(a,d);a.parm('scale_random_mode').set(1);a.parm('scale_min').set(0.5);a.parm('scale_max').set(2.0);o5=out(a);assert o5['scales'].max()>1.2 and o5['scales'].min()<0.8
    a.parm('scale_random_mode').set(0)
    a.parm('overlap_mode').set(1);a.parm('overlap_tolerance').set(1.0);o6=out(a);assert 0<len(o6['pos'])<len(pts);a.parm('overlap_mode').set(0)
def stable_text():
    st,sc=new_scene('text');texts=[]
    for run in range(2):
        a=arraytron(st,sc,name='P%d'%run,mode=6,paint_prim='/World/Terrain');m=a.hdaModule();surface=m.paint_surface(a);d=m.paint_empty();seed=a.evalParm('paint_seed')
        for k in range(5):
            c=np.array([0.2*k,2.0,0.0]);c=c*(2.0/np.linalg.norm(c));d,_=m.brush_add(d,c,c/2.0,0.6,40.0,0.05,2,0.8,seed,m.make_projector(surface,c,0.6,True))
        texts.append(m.paint_encode(d))
    assert texts[0]==texts[1] and len(texts[0])>100
def state_static():
    code=(ROOT/'src/arraytron_paint_state.py').read_text();tree=ast.parse(code);classes={n.name:n for n in tree.body if isinstance(n,ast.ClassDef)}
    methods={f.name for f in classes['PaintState'].body if isinstance(f,ast.FunctionDef)}
    assert {'onEnter','onExit','onInterrupt','onResume','onMouseEvent','onKeyEvent','onDraw'}<=methods and any(isinstance(n,ast.FunctionDef) and n.name=='createViewerStateTemplate' for n in tree.body)
    a,m=module();used=set()
    for name in ('paint_decode','paint_apply','paint_surface','tangent_frame','ray_triangles','make_projector','brush_add','brush_remove'):assert hasattr(m,name),name
    assert hasattr(m,'paint_start') and hasattr(m,'paint_clear') and hasattr(m,'paint_state_name')
class StubDrawable(object):
    def __init__(self,*a,**k):self.geo=None;self.shown=False;self.params={}
    def setParams(self,p):self.params.update(p)
    def setGeometry(self,g):self.geo=g
    def show(self,v):self.shown=v
    def draw(self,handle,params=None):self.drawn=True
class StubViewer(object):
    def __init__(self):self.prompt=None
    def setPromptMessage(self,m,t=None):self.prompt=m
    def clearPromptMessage(self):self.prompt=None
class Device(object):
    def __init__(self,x,y,left=False,ctrl=False,key='',shift=False,wheel=0):self.x,self.y,self.left,self.ctrl,self.key,self.shift,self.wheel=x,y,left,ctrl,key,shift,wheel
    def isShiftKey(self):return self.shift
    def mouseWheel(self):return self.wheel
    def mouseX(self):return self.x
    def mouseY(self):return self.y
    def isLeftButton(self):return self.left
    def isCtrlKey(self):return self.ctrl
    def isMiddleButton(self):return False
    def isAltKey(self):return False
    def keyString(self):return self.key
class Event(object):
    """A viewport that looks straight down: pixel (x, y) is the ray from (x/10, 10, y/10) along -Y."""
    def __init__(self,device,reason):self.d,self.r=device,reason
    def device(self):return self.d
    def reason(self):return self.r
    def ray(self):x,y=self.d.mouseX(),self.d.mouseY();return hou.Vector3((x/10.0,10.0,y/10.0)),hou.Vector3((0,-1,0))
    def curViewport(self):
        class VP(object):
            def mapToWorld(s,x,y):return hou.Vector3((x/10.0,10.0,y/10.0)),hou.Vector3((0,-1,0))
        return VP()
def viewer_state():
    st,sc=new_scene('state');a=arraytron(st,sc,mode=0,paint_prim='',paint_radius=0.5,paint_density=200.0,paint_spacing=0.0,paint_falloff=3);m=a.hdaModule()
    ns=types.SimpleNamespace(**{k:getattr(hou,k) for k in ('Vector4','Vector3','Geometry','drawableGeometryType','uiEventReason','promptMessageType','Error','lopNodeTypeCategory','ViewerStateTemplate')});ns.GeometryDrawable=StubDrawable
    glob={'hou':ns,'np':np,'__name__':'arraytron_paint_state_test'};exec(compile((ROOT/'src/arraytron_paint_state.py').read_text().replace('import hou'+chr(10),'',1),'arraytron_paint_state.py','exec'),glob);glob['STRICT']=True;glob['STRICT']=True
    viewer=StubViewer();state=glob['PaintState']('arraytron_paint_test',viewer);R=hou.uiEventReason
    # selecting the node enters the tool by itself: with another Distribution Mode it must change nothing and leave every event to Houdini
    state.onEnter({'node':a});assert a.evalParm('mode')==0 and 'Arraytron Paint [' not in (viewer.prompt or '')
    assert state.onMouseEvent({'ui_event':Event(Device(30,20,left=True),R.Start)}) is False and state.onMouseWheelEvent({'ui_event':Event(Device(0,0,wheel=1,shift=True),R.Changed)}) is False and state.onKeyEvent({'ui_event':Event(Device(0,0,key=']'),R.Changed)}) is False
    assert a.evalParm('mode')==0 and a.evalParm('paint_radius')==0.5 and a.evalParm('paint_data')=='' and not state.painting
    a.parm('mode').set(6);state.onMouseEvent({'ui_event':Event(Device(30,20),R.Located)});assert 'Arraytron Paint [' in viewer.prompt        # Paint mode (the Start Painting button sets it) wakes the tool
    # stroke: press at (30, 20) -> world (3, 0, 2), drag to (34, 20), release
    assert state.onMouseEvent({'ui_event':Event(Device(30,20,left=True),R.Start)}) is True
    hit=state.hit;assert hit is not None and np.allclose(hit[0],[3.0,0.0,2.0],atol=1e-9) and np.allclose(hit[1],[0,1,0]) and state.painting
    n1=len(state.data['pts']);assert n1>50
    state.onMouseEvent({'ui_event':Event(Device(34,20,left=True),R.Active)});n2=len(state.data['pts']);assert n2>n1
    assert a.evalParm('paint_data')=='' and state.dirty                                                                     # nothing is written while dragging
    state.onMouseEvent({'ui_event':Event(Device(34,20,left=False),R.Changed)});assert not state.painting and not state.dirty
    saved=m.paint_decode(a.evalParm('paint_data'));assert len(saved['pts'])==n2 and np.all(np.abs(saved['pts'][:,1])<1e-9)  # committed once, on the ground plane
    assert np.all(np.linalg.norm(saved['pts'][:,[0,2]]-[3.2,2.0],axis=1)<0.5+0.2+1e-6)
    pre=a.evalParm('paint_data');state.onMouseEvent({'ui_event':Event(Device(300,300,left=False),R.Located)});assert a.evalParm('paint_data')==pre   # hovering paints nothing
    assert state.brush.shown and state.brush.geo is not None
    # ctrl-drag removes
    state.onMouseEvent({'ui_event':Event(Device(32,20,left=True,ctrl=True),R.Start)});state.onMouseEvent({'ui_event':Event(Device(32,20,left=True,ctrl=True),R.Changed)})
    after=m.paint_decode(a.evalParm('paint_data'));assert len(after['pts'])<n2 and np.all(np.linalg.norm(after['pts'][:,[0,2]]-[3.2,2.0],axis=1)>=0.0)
    removed=set(saved['pts'][:,6])-set(after['pts'][:,6]);assert len(removed)>0 and all(np.linalg.norm(saved['pts'][saved['pts'][:,6]==i][0,[0,2]]-[3.2,2.0])<=0.5+1e-6 for i in removed)
    # [ and ] change the radius
    r0=a.evalParm('paint_radius');assert state.onKeyEvent({'ui_event':Event(Device(0,0,key=']'),R.Changed)}) and a.evalParm('paint_radius')>r0
    assert state.onKeyEvent({'ui_event':Event(Device(0,0,key='x'),R.Changed)}) is False
    # a click that misses the surface (no ground hit: a viewport looking up) paints nothing
    count=len(m.paint_decode(a.evalParm('paint_data'))['pts']);state.surface=None;state.onMouseEvent({'ui_event':Event(Device(30,20,left=True),R.Start)});assert not state.painting
    state.onExit({});assert viewer.prompt is None and not state.brush.shown
def brush_shortcuts():
    """Mouse and keyboard shortcuts of the Paint tool through the stand-in viewport: Ctrl+Shift drag and Shift / Ctrl / Ctrl+Shift wheel, keys, the live prompt,
    Shift = Relax, Ctrl = erase, the brush colour per operation and the strength ring."""
    st,sc=new_scene('keys');a=arraytron(st,sc,mode=6,paint_prim='',paint_radius=0.5,paint_density=200.0,paint_spacing=0.0,paint_falloff=3,paint_strength=1.0);m=a.hdaModule()
    ns=types.SimpleNamespace(**{k:getattr(hou,k) for k in ('Vector4','Vector3','Geometry','drawableGeometryType','uiEventReason','promptMessageType','Error','lopNodeTypeCategory','ViewerStateTemplate')});ns.GeometryDrawable=StubDrawable
    text=(ROOT/'src/arraytron_paint_state.py').read_text().replace('import hou'+chr(10),'',1)
    if MUTATE=='paint_resize':text=text.replace("2.0**((dev.mouseX()-x0)/150.0)","2.0**((x0-dev.mouseX())/150.0)")
    if MUTATE=='paint_wheel':text=text.replace("*1.1**sign,0.01,100.0)","*1.1**-sign,0.01,100.0)")
    if MUTATE=='paint_shift':text=text.replace("'add' if op==3 else 'relax'","KINDS[op]")
    glob={'hou':ns,'np':np};exec(compile(text,'arraytron_paint_state.py','exec'),glob);glob['STRICT']=True;viewer=StubViewer();state=glob['PaintState']('keys',viewer);R=hou.uiEventReason
    state.onEnter({'node':a});assert 'radius 0.5' in viewer.prompt and 'strength 1.00' in viewer.prompt and 'density 200' in viewer.prompt and 'falloff Hard' in viewer.prompt and '[Add]' in viewer.prompt and 'Esc' in viewer.prompt
    def mouse(dev,reason):return state.onMouseEvent({'ui_event':Event(dev,reason)})
    def key(k):return state.onKeyEvent({'ui_event':Event(Device(0,0,key=k),R.Changed)})
    def wheel(step,**mods):return state.onMouseWheelEvent({'ui_event':Event(Device(0,0,wheel=step,**mods),R.Changed)})
    # Ctrl+Shift + LMB drag sideways resizes: 150 pixels to the right doubles the radius, to the left halves it, and nothing is painted
    r0=a.evalParm('paint_radius');assert mouse(Device(30,20,left=True,ctrl=True,shift=True),R.Start) is True and state.resizing is not None
    mouse(Device(180,20,left=True,ctrl=True,shift=True),R.Active);assert abs(a.evalParm('paint_radius')-2*r0)<1e-6
    mouse(Device(-120,20,left=True,ctrl=True,shift=True),R.Active);assert abs(a.evalParm('paint_radius')-r0/2)<1e-6
    mouse(Device(30,20,left=True,ctrl=True,shift=True),R.Changed);assert state.resizing is None and a.evalParm('paint_data')=='' and not state.dirty
    a.parm('paint_radius').set(0.5)
    # the wheel: Shift = radius, Ctrl = strength, Ctrl+Shift = density; a plain wheel is left to the camera
    assert wheel(1,shift=True) is True and abs(a.evalParm('paint_radius')-0.55)<1e-9 and wheel(-1,shift=True) and abs(a.evalParm('paint_radius')-0.5)<1e-9
    assert wheel(-1,ctrl=True) and abs(a.evalParm('paint_strength')-0.95)<1e-9 and wheel(1,ctrl=True) and wheel(1,ctrl=True) and a.evalParm('paint_strength')==1.0              # clamped at 1
    assert wheel(1,ctrl=True,shift=True) and abs(a.evalParm('paint_density')-230.0)<1e-6 and wheel(0,shift=True) is False and wheel(1) is False
    a.parm('paint_density').set(200.0)
    # keys
    assert key(']') and abs(a.evalParm('paint_radius')-0.55)<1e-9 and key('[') and abs(a.evalParm('paint_radius')-0.5)<1e-9
    assert key('-') and abs(a.evalParm('paint_strength')-0.95)<1e-9 and key('=') and a.evalParm('paint_strength')==1.0 and key('+') and a.evalParm('paint_strength')==1.0
    assert key(',') and abs(a.evalParm('paint_density')-200/1.15)<1e-6 and key('.') and abs(a.evalParm('paint_density')-200.0)<1e-6
    for k,op,name in (('2',1,'Remove'),('3',2,'Replace'),('4',3,'Relax'),('1',0,'Add')):assert key(k) and a.evalParm('paint_op')==op and '[%s]'%name in viewer.prompt
    assert key('f') and a.evalParm('paint_falloff')==0 and key('F') and a.evalParm('paint_falloff')==1 and 'falloff Smooth' in viewer.prompt and key('f') and key('f') and key('f') and a.evalParm('paint_falloff')==0
    assert 'Esc' in viewer.prompt and key('h') and 'Esc' not in viewer.prompt and 'radius' in viewer.prompt and key('H') and 'Esc' in viewer.prompt                                     # H hides and shows the shortcut help, the values stay
    assert key('x') is False and key('3') and a.parm('paint_op').eval()==2 and key('1')
    # Shift = Relax, Ctrl = erase, the menu decides the plain drag; the brush ring changes colour with the operation
    a.parm('paint_density').set(300.0);a.parm('paint_radius').set(0.6);mouse(Device(30,20,left=True),R.Start);mouse(Device(30,20,left=True),R.Changed);painted=len(m.paint_decode(a.evalParm('paint_data'))['pts']);assert painted>100
    colors=[]
    for kw,kind in (({},'add'),({'ctrl':True},'remove'),({'shift':True},'relax')):
        mouse(Device(30,20,**kw),R.Located);assert state.hover_kind==kind,(kw,state.hover_kind);colors.append(tuple(state.brush.params['color1']))
    assert len(set(colors))==3
    before=m.paint_decode(a.evalParm('paint_data'))['pts'].copy()
    mouse(Device(30,20,left=True,shift=True),R.Start);assert state.kind=='relax';mouse(Device(30,20,left=True,shift=True),R.Changed);after=m.paint_decode(a.evalParm('paint_data'))['pts']
    assert len(after)==len(before) and np.array_equal(after[:,6],before[:,6]) and not np.allclose(after[:,:3],before[:,:3])                                     # Relax moved points, kept every id
    a.parm('paint_op').set(3);mouse(Device(30,20),R.Located);assert state.hover_kind=='relax';mouse(Device(30,20,shift=True),R.Located);assert state.hover_kind=='add'                  # menu Relax: Shift paints instead
    a.parm('paint_op').set(1);mouse(Device(30,20,ctrl=True),R.Located);assert state.hover_kind=='add'
    a.parm('paint_op').set(0)
    # the white inner ring shows a strength below 1
    a.parm('paint_strength').set(0.5);mouse(Device(30,20),R.Located);assert state.core.shown;a.parm('paint_strength').set(1.0);mouse(Device(30,20),R.Located);assert not state.core.shown
    # a plain click (Picked) paints one dab
    n0=len(m.paint_decode(a.evalParm('paint_data'))['pts']);mouse(Device(120,60,left=True),R.Picked);assert len(m.paint_decode(a.evalParm('paint_data'))['pts'])>n0
    # Alt and the middle mouse button are never taken from the camera
    class Alt(Device):
        def isAltKey(self):return True
    assert mouse(Alt(30,20,left=True),R.Start) is False
def all_features():
    # Add and Remove through the node's own Operation menu: op=Remove inverts a plain drag
    st,sc=new_scene('op');a=arraytron(st,sc,mode=6,paint_prim='',paint_op=1);m=a.hdaModule()
    ns=types.SimpleNamespace(**{k:getattr(hou,k) for k in ('Vector4','Vector3','Geometry','drawableGeometryType','uiEventReason','promptMessageType','Error','lopNodeTypeCategory','ViewerStateTemplate')});ns.GeometryDrawable=StubDrawable
    glob={'hou':ns,'np':np};exec(compile((ROOT/'src/arraytron_paint_state.py').read_text().replace('import hou'+chr(10),'',1),'s','exec'),glob);glob['STRICT']=True;state=glob['PaintState']('x',StubViewer());R=hou.uiEventReason
    d,_=m.brush_add(m.paint_empty(),np.zeros(3),np.array([0.0,1.0,0.0]),1.0,50.0,0.0,3,1.0,1,flat_project);m.paint_apply(a,d);state.onEnter({'node':a})
    state.onMouseEvent({'ui_event':Event(Device(0,0,left=True),R.Start)});state.onMouseEvent({'ui_event':Event(Device(0,0,left=True),R.Changed)})
    assert len(m.paint_decode(a.evalParm('paint_data'))['pts'])<len(d['pts'])                                                # Operation = Remove: a plain drag erased points
def corrupt():
    st,sc=new_scene('bad');a=arraytron(st,sc,mode=6);a.parm('paint_data').set('not paint data')
    try:a.cook(force=True)
    except hou.OperationFailed:pass          # Houdini 20.5 / 21 raise on a cook error, Houdini 22 does not
    a.stage();errs=all_errors(a);assert errs and any('Paint' in e or 'paint' in e or 'p1' in e for e in errs),errs
    assert 'Cannot read' in a.parm('paint_info').eval()
def main():
    for name,func in (('UI contract: Paint mode, folder, buttons, hidden data, embedded viewer state, socket labels, every v0.5.2 parameter unchanged',ui_contract),
                      ('Defaults reproduce v0.5.2 exactly (Line, Area, Grid, Circle, Surface)',defaults_unchanged),
                      ('Stroke storage: compact round trip, no drift, damaged data rejected',storage),
                      ('Falloff curves against independent formulas',falloff),
                      ('Add dab: density, strength, determinism, seed, stable ids, earlier points untouched',add_basics),
                      ('Add dab: falloff shapes the point distribution (hard disc vs soft)',add_falloff),
                      ('Minimum spacing holds (brute force) and saturates when painting over the same place',add_spacing),
                      ('Remove dab: exactly the points inside, ids kept, never reused',remove),
                      ('Ray test and surface projection: tilted plane, dome, ground plane, missing prim',ray_test),
                      ('Points land on the Paint Target (plane exact, dome inscribed, normals right)',projection),
                      ('Node end to end: positions, ids, alignment, offset, Remove keeps ids, Clear, variation / overlap on top',node_end_to_end),
                      ('Same strokes give identical stored text',stable_text),
                      ('Viewer state: stroke, drag, commit once on release, hover, Ctrl erase, bracket keys, miss, exit (stub viewport)',viewer_state),
                      ('Viewer state source and module entry points (static)',state_static),
                      ('Brush shortcuts: Ctrl+Shift drag, wheel, keys, live prompt, Shift relax, Ctrl erase, colours and the strength ring',brush_shortcuts),
                      ('Operation = Remove inverts a plain drag',all_features),
                      ('Damaged paint data gives a readable error',corrupt)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_paint_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
