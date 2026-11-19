"""v1.31.0 in real Houdini: hython tests/validate_surfproxy.py [version]
A surface of many triangles is read once and kept (the node cooked slowly and the Surface text read the whole mesh whenever the node was selected), Surface mode can scatter on a poly reduced copy
(Reduced Proxy: Target Triangles, Ghost Proxy), and the Place mode is retired (its menu slot stays so Biome keeps mode 10; the palette skips it).
Env ARRAYTRON_MUTATE=sp_reduce|sp_cache|sp_stale|sp_area|sp_info|sp_count|sp_limit breaks the module; the suite must FAIL."""
from pathlib import Path
import hou, json, os, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom, Vt
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v1.38.3':'v1.38.2','v1.38.2':'v1.38.1','v1.38.1':'v1.38.0','v1.38.0':'v1.37.0','v1.37.0':'v1.36.0','v1.36.0':'v1.35.0','v1.35.0':'v1.34.1','v1.34.1':'v1.34.0','v1.34.0':'v1.33.0','v1.33.0':'v1.32.0','v1.32.0':'v1.31.1','v1.31.1':'v1.31.0','v1.31.0':'v1.30.1'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_surfproxy_'));checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')
N=220                                                                            # 220 x 220 quads = 96 800 triangles
def hill(x,z):return 3.0*np.sin(x*0.2)*np.cos(z*0.17)
def write_scene():
    path=WORK/'surfproxy.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    xs=np.linspace(-50,50,N+1);X,Z=np.meshgrid(xs,xs);pts=np.stack([X.ravel(),hill(X,Z).ravel(),Z.ravel()],1);idx=np.arange((N+1)**2).reshape(N+1,N+1)
    quads=np.stack([idx[:-1,:-1].ravel(),idx[1:,:-1].ravel(),idx[1:,1:].ravel(),idx[:-1,1:].ravel()],1)
    g=UsdGeom.Mesh.Define(s,'/World/Mountain');g.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(pts.astype(np.float32)));g.CreateFaceVertexCountsAttr(Vt.IntArray.FromNumpy(np.full(N*N,4,dtype=np.int32)));g.CreateFaceVertexIndicesAttr(Vt.IntArray.FromNumpy(quads.ravel().astype(np.int32)))
    UsdGeom.Xform.Define(s,'/World/Props/Tree');UsdGeom.Cube.Define(s,'/World/Props/Tree/C').CreateSizeAttr(0.2)
    UsdGeom.Cube.Define(s,'/World/Block').CreateSizeAttr(10.0)
    s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
def install():
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True);install();hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
def scatter(stage,source,typ=None,name='Sp',surface='/World/Mountain',**values):
    a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Tree');a.parm('mode').set(5);a.parm('surface_prim').set(surface);a.parm('surface_seed').set(3)
    a.parm('surface_countmode').set(1);a.parm('surface_density').set(0.25)
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
    g=a.hdaModule().reduce_mesh.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='sp_reduce':
        g['reduce_mesh']=lambda P,T,target,total_area=None:(P,T)                                                                                                                    # nothing is reduced
    elif MUTATE=='sp_cache':
        g['SURFACE_CACHE']=type('NoCache',(dict,),{'get':lambda self,k,d=None:None})()                                                                                              # the surface is read every time
    elif MUTATE=='sp_stale':
        good=g['stage_surface'];first={}
        def stale(asset,parm='surface_prim',path=None):
            r=good(asset,parm,path);return first.setdefault(asset.path(),r)                                                                                                         # never refreshed
        g['stage_surface']=stale
    elif MUTATE=='sp_area':
        g['surface_proxy_mesh']=(lambda good:lambda asset:(good(asset)[0],1.0))(g['surface_proxy_mesh'])                                                                             # the amount follows the reduced area
    elif MUTATE=='sp_info':
        g['_estimate_triangles']=lambda root:0                                                                                                                                                         # the text always reads the surface
    elif MUTATE=='sp_limit':
        g['surface_limit']=lambda asset:10000                                                                                                                                      # the Point Limit is ignored
    elif MUTATE=='sp_count':
        g['scatter_info']=lambda asset:'0 instances'                                                                                                                                  # the counter is wrong
    elif MUTATE:raise SystemExit('unknown mutation '+MUTATE)
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()

def reduction():
    st,sc=new_scene('red');a=scatter(st,sc);m=a.hdaModule();P,T,area,normals,vn=m.stage_surface(a);assert len(T)==2*N*N
    for target in (2000,10000,30000):
        Q,t=m.reduce_mesh(P,T,target,float(area.sum()));assert 0.6*target<=len(t)<=1.4*target,(target,len(t))
        _,t2,ar2,nm2,_=m.mesh_attributes(np.asarray(Q),np.asarray(t))
        assert abs(ar2.sum()/area.sum()-1)<0.05 and (nm2[:,1]>0.2).all(),(target,ar2.sum()/area.sum(),nm2[:,1].min())      # the area stays (within 5 percent), every triangle faces up like the hill does: the winding is kept
        err=np.abs(Q[:,1]-hill(Q[:,0],Q[:,2]));assert err.max()<0.35 and err.mean()<0.08,(target,err.max(),err.mean())       # the vertices stay near the real surface
    Q,t=m.reduce_mesh(P,T,10**7,float(area.sum()));assert len(t)==len(T)                                                       # a mesh below the target comes back as it is
    cube=m.stage_surface(a,path='/World/Block');Q,t=m.reduce_mesh(cube[0],cube[1],50);assert len(t)==len(cube[1])             # (12 triangles: not reduced)
    raised=m.reduce_mesh(P,T,5000);assert 3000<=len(raised[1])<=7000                                                            # works without a given area

def cache():
    st,sc=new_scene('cache');a=scatter(st,sc,name='C');m=a.hdaModule();g=m.reduce_mesh.__globals__;reads=[]
    good=g['_read_surface'];g['_read_surface']=lambda *args,**kw:(reads.append(1),good(*args,**kw))[1]
    try:
        out(a);assert len(reads)==1,len(reads);first=m.stage_surface(a);assert m.stage_surface(a) is first and len(reads)==1                                  # read once, then the very same arrays
        assert not first[0].flags.writeable and not first[1].flags.writeable                                                                                  # read-only, so nobody can change the cached surface
        a.parm('surface_seed').set(9);out(a);a.parm('surface_density').set(0.3);out(a);a.parm('surface_slope_max').set(80.0);out(a);assert len(reads)==1,len(reads) # Seed, Density and Slope do not read the mesh again
        a.parm('surface_proxy').set(1);out(a);a.parm('surface_proxy_tris').set(20000);out(a);assert len(reads)==1,len(reads)                                  # nor does the proxy
        a.parm('surface_proxy').set(0);b=scatter(st,sc,name='C2');out(b);assert len(reads)==2,len(reads)                                                  # another node has its own entry
        before=len(reads);up=st.createNode('xform','nudge');up.setInput(0,sc);up.parm('primpattern').set('/World/Mountain');up.parm('tx').set(5.0);a.setInput(0,up);moved=out(a);assert len(reads)==before+1,len(reads)   # the incoming stage changed: read again
        a.parm('surface_prim').set('/World/Block');out(a);assert len(reads)==before+2 and len(m.stage_surface(a)[1])==12                                          # another Surface Prim: read again
        m.surface_cache_clear();m.stage_surface(a);assert len(reads)==before+3                                                                                # clearing it works
    finally:g['_read_surface']=good
    assert moved['pos'][:,0].min()>-45.0-1e-3 and moved['pos'][:,0].max()>49.0,(moved['pos'][:,0].min(),moved['pos'][:,0].max())                                                                                          # the points followed the moved surface (it starts at x = -50 + 5)

def info():
    st,sc=new_scene('info');a=scatter(st,sc,name='I');m=a.hdaModule();g=m.reduce_mesh.__globals__;reads=[];good=g['_read_surface'];g['_read_surface']=lambda *args,**kw:(reads.append(1),good(*args,**kw))[1]
    old=g['INFO_LIMIT']
    try:
        g['INFO_LIMIT']=1000;m.surface_cache_clear();text=m.surface_info(a);assert len(reads)==0 and text.startswith('About 96800 triangles'),(len(reads),text)  # a big surface that is not read yet: only its size, nothing is read
        out(a);assert len(reads)==1;text=m.surface_info(a);assert len(reads)==1 and text.startswith('96800 triangles, area '),text                              # after the cook: the numbers, from the cache
        g['INFO_LIMIT']=old;m.surface_cache_clear();text=m.surface_info(a);assert text.startswith('96800 triangles') and len(reads)==2                            # a surface under the limit is read for the text (as before)
    finally:g['_read_surface']=good;g['INFO_LIMIT']=old
    assert m._estimate_triangles(m._local_root(a,'surface_prim')[1])==2*N*N

def proxy():
    st,sc=new_scene('proxy');off=scatter(st,sc,name='Off');po=out(off);assert len(po['ids'])>0
    on=scatter(st,sc,name='On',surface_proxy=1,surface_proxy_tris=8000);pn=out(on);assert len(pn['ids'])==len(po['ids']),(len(pn['ids']),len(po['ids']))                        # the same amount: the Density counts the area of the ORIGINAL surface
    err=np.abs(pn['pos'][:,1]-hill(pn['pos'][:,0],pn['pos'][:,2]));assert err.max()<0.6 and err.mean()<0.15,(err.max(),err.mean())                                                # the points lie near the real surface
    assert np.abs(po['pos'][:,1]-hill(po['pos'][:,0],po['pos'][:,2])).max()<0.02                                                                                                      # (the original surface: on it)
    assert not np.array_equal(po['pos'],pn['pos']) and (np.abs(pn['pos'][:,0])<=50.0+1e-6).all()
    again=out(on);assert np.array_equal(again['pos'],pn['pos'])                                                                                                                      # stable
    on.parm('surface_proxy_tris').set(4000);coarse=out(on);ec=np.abs(coarse['pos'][:,1]-hill(coarse['pos'][:,0],coarse['pos'][:,2])).mean();assert ec>err.mean()*0.8                       # a coarser proxy follows the surface less closely
    n=on.hdaModule().surface_proxy_mesh(on)[0];assert 0.6*4000<=len(n[1])<=1.4*4000,len(n[1])
    text=on.hdaModule().surface_info(on);assert 'Reduced Proxy:' in text and 'from 96800' in text,text
    cnt=scatter(st,sc,name='Cnt',surface_proxy=1,surface_proxy_tris=8000,surface_countmode=0,surface_count=137);assert len(out(cnt)['ids'])==137                                                      # By Count stays exact
    sl=scatter(st,sc,name='Dir',surface_proxy=1,surface_proxy_tris=8000,surface_dirsel=1,surface_dir=(0,1,0),surface_spread=20.0,surface_countmode=0,surface_count=200);ds=out(sl);assert len(ds['ids'])==200   # Keep By Direction works on the proxy

def ghost():
    st,sc=new_scene('ghost');a=scatter(st,sc,name='G',surface_proxy=1,surface_proxy_tris=6000);out(a);s=a.stage();path=a.evalParm('outputpath')+'_View/GhostProxy';prim=s.GetPrimAtPath(path)
    assert prim and prim.IsValid() and prim.GetTypeName()=='Mesh',path                                                                                                          # the proxy shown as a mesh next to the instancer
    assert UsdGeom.Imageable(prim).GetPurposeAttr().Get()=='guide'                                                                                                                  # a guide: never rendered
    mesh=UsdGeom.Mesh(prim);assert 0.6*6000<=len(mesh.GetFaceVertexCountsAttr().Get())<=1.4*6000 and set(mesh.GetFaceVertexCountsAttr().Get())=={3}
    op=UsdGeom.PrimvarsAPI(prim).GetPrimvar('displayOpacity').Get();assert op is not None and 0.0<op[0]<1.0                                                                       # translucent
    a.parm('surface_ghost').set(2);out(a);pr=a.stage().GetPrimAtPath(path);assert UsdGeom.Imageable(pr).GetPurposeAttr().Get()=='default'                                                  # Viewport And Render: the mesh is renderable
    a.parm('surface_ghost').set(0);out(a);p2=a.stage().GetPrimAtPath(path);assert not (p2 and p2.IsValid())                                                                          # Show Ghost Proxy off: no mesh
    a.parm('surface_ghost').set(1);a.parm('surface_proxy').set(0);out(a);p3=a.stage().GetPrimAtPath(path);assert not (p3 and p3.IsValid())                                           # proxy off: no mesh
    b=scatter(st,sc,name='G2');out(b);assert not b.stage().GetPrimAtPath(b.evalParm('outputpath')+'_View/GhostProxy').IsValid()                                                       # a plain node draws nothing extra
    c=scatter(st,sc,name='G3',surface_proxy=1,surface_proxy_tris=6000,surface_ghost=1);c.parm('dbg_on').set(0);out(c);assert c.stage().GetPrimAtPath(c.evalParm('outputpath')+'_View/GhostProxy').IsValid()

def retired():
    st,sc=new_scene('place');a=scatter(st,sc,name='P');labels=list(a.parm('mode').menuLabels());assert 'Instance Place' not in labels and labels[9]=='Place (retired)' and labels[10]=='Biome' and len(labels)==11,labels  # Biome keeps mode 10
    old=scatter(st,sc,typ=OLD_TYPE,name='OldP');assert old.parm('mode').menuLabels()[9] in ('Instance Place','Place (retired)')
    import re;secs=a.type().definition().sections();pal=[s for s in secs if 'odePalette' in s];assert pal,list(secs)
    titles=re.search(r"TITLES = \{(.*?)\}",secs[pal[0]].contents(),re.S).group(1);assert 'Place (retired)' not in titles and "'Biome': 'biome'" in titles                  # the palette shows only the labels it knows: the retired one is not among them
    b=scatter(st,sc,name='B',mode=9);assert b.evalParm('mode')==9 and b.parm('mode').evalAsString()=='9'                                                                              # an old scene with mode 9 still loads

def counter():
    st,sc=new_scene('counter');a=scatter(st,sc,name='K',surface_countmode=0,surface_count=300);m=a.hdaModule();assert m.scatter_info(a).startswith('Not cooked yet') or m.scatter_info(a).endswith('instances')   # nothing is cooked by the text itself
    o=out(a);text=m.scatter_info(a);assert text.split('\n')[0]=='300 instances' and len(o['ids'])==300,text                                                      # the count is the number of instances
    assert a.parm('scatter_info').parmTemplate().label()=='Scattered' and a.parm('scatter_info').eval()==text
    b=scatter(st,sc,name='K2',surface_countmode=0,surface_count=2000,overlap_mode=1,overlap_axes=0,overlap_size=1,overlap_radius=2.0);ob=out(b);t2=b.hdaModule().scatter_info(b);first=t2.split('\n')[0]
    assert 0<len(ob['ids'])<2000 and first.startswith('%s instances (2,000 generated, '%format(len(ob['ids']),',')) and '%s removed'%format(2000-len(ob['ids']),',') in first,(first,len(ob['ids']))   # points removed by Separation are counted
    st2=st.createNode('arraytron::instancer::1.31.0','C3') if False else None
    c=scatter(st,sc,name='K3',surface_countmode=0,surface_count=100,protos=2);c.parm('proto_prim2').set('/World/Block');c.parm('proto_mode').set(0);oc=out(c);t3=c.hdaModule().scatter_info(c)
    assert t3.split('\n')[0]=='100 instances' and 'Tree' in t3.split('\n')[1] and 'Block' in t3.split('\n')[1],t3                                                    # how many use each prototype
    a.parm('surface_count').set(450);t4=a.hdaModule().scatter_info(a);assert 'old' in t4 and t4.startswith('300 instances'),t4                                     # changed, not cooked: the last count, marked old
    out(a);assert a.hdaModule().scatter_info(a)=='450 instances'                                                                                                   # after the cook: the new count
    big=scatter(st,sc,name='K4',surface_density=1000.0);ob_=out(big);tb=big.hdaModule().scatter_info(big)
    assert len(ob_['ids'])==10000 and tb.split('\n')[0].startswith('10,000 instances - LIMITED: the settings ask for ') and 'the Point Limit is 10,000' in tb,tb                              # the default limit cuts a huge Density, and the counter says what was asked
    big.parm('surface_limit').set(60000);o2=out(big);t2_=big.hdaModule().scatter_info(big);assert len(o2['ids'])==60000 and 'LIMITED' in t2_ and '60,000' in t2_,t2_                           # the Point Limit raises it (still limited by the Density asked)
    big.parm('surface_density').set(0.4);big.parm('surface_limit').set(5000000);o3=out(big);assert 'LIMITED' not in big.hdaModule().scatter_info(big) and len(o3['ids'])==int(round(big.hdaModule().surface_total_area(big)*0.4))   # asked less than the limit: no note
    if hasattr(c.hdaModule(),'sop_protopath'):                                                                                                                    # Houdini 20.5 / 21: every point's protopath is the flat path of its protoindex (fast numpy path)
        pg=c.node('USD_COMPILER/PROTO_PATH').geometry();pp=pg.pointStringAttribValues('protopath');ix=pg.pointIntAttribValues('protoindex');fp=c.hdaModule().flat_paths(c)
        assert len(pp)==100 and all(pp[k]==fp[ix[k]] for k in range(100)) and len(set(ix))==2,(set(ix),pp[:3])
    cnt=scatter(st,sc,name='K5',surface_countmode=0,surface_count=700,surface_limit=500);assert len(out(cnt)['ids'])==500 and 'asks for 700' not in cnt.hdaModule().scatter_info(cnt) and 'ask for 700' in cnt.hdaModule().scatter_info(cnt)   # By Count too
                                                                                                   # after the cook: the new count

def contract():
    st,sc=new_scene('contract');a=scatter(st,sc,name='C');g=a.parmTemplateGroup();d=lambda n:g.find(n).defaultValue()
    for n in ('surface_proxy','surface_proxy_tris','surface_ghost','scatter_info'):assert g.find(n) is not None,n
    assert d('surface_proxy')==False and d('surface_proxy_tris')==(100000,) and d('surface_ghost')==1 and g.find('surface_ghost').menuLabels()==('Hidden','Viewport Only','Viewport And Render')
    hide=lambda n:g.find(n).conditionals().get(hou.parmCondType.HideWhen);assert '{ surface_proxy == 0 }' in hide('surface_proxy_tris') and '{ surface_proxy == 0 }' in hide('surface_ghost') and '{ mode != 5 }' in hide('surface_proxy_tris')
    for n in ('reduce_mesh','mesh_attributes','surface_proxy_mesh','surface_scatter_mesh','surface_cache_clear','surface_proxy_on'):assert hasattr(a.hdaModule(),n),n
    assert '$' not in a.type().definition().sections()['PythonModule'].contents().split('def _cluster_mesh')[1].split('def surface_points')[0]
    assert 'surface_ghost' in a.type().definition().sections()['debug_guide'].contents() if 'debug_guide' in a.type().definition().sections() else True

def unchanged():
    st,sc=new_scene('same');a=scatter(st,sc,name='N',surface_normal=1,surface_slope_max=70.0);b=scatter(st,sc,typ=OLD_TYPE,name='O',surface_normal=1,surface_slope_max=70.0)
    oa=out(a);ob=out(b);assert len(oa['ids'])>0 and np.array_equal(oa['ids'],ob['ids']) and np.abs(oa['pos']-ob['pos']).max()<1e-4,np.abs(oa['pos']-ob['pos']).max()                  # the proxy off: the previous release (the vertex normals use bincount now: equal to float precision)

def main():
    for name,func in (('Poly reduce: the target, the area, the winding, the distance to the surface; small meshes unchanged',reduction),
                      ('Cache: one read, the same read-only arrays, Seed / Density / Slope / proxy do not read again, a changed stage or prim does, clearing works',cache),
                      ('Surface text: a big surface that is not read yet shows its size only (no read), after the cook the numbers from the cache',info),
                      ('Reduced Proxy: the same amount of points (area of the original), near the surface, stable, Target Triangles, By Count exact, Keep By Direction, the text',proxy),
                      ('Ghost proxy: a translucent guide mesh next to the instancer, Hidden / Viewport Only / Viewport And Render or the proxy off',ghost),
                      ('Place retired: not in the menu or the palette, Biome keeps mode 10, mode 9 still loads',retired),
                      ('Scattered counter: the number of instances, points removed by Separation, instances per prototype, the old count while the node has changed',counter),
                      ('Contract: parameters, defaults, conditionals, module functions, no dollar signs',contract),
                      ('The previous release unchanged with the proxy off',unchanged)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_surfproxy_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
