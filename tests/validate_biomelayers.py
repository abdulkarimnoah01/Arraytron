"""v1.19.0 Biome layers, exclusion and presets in real Houdini: hython tests/validate_biomelayers.py [version]
Layers and Clearance: a biome on a lower layer (a bigger number) keeps clear of the points of the biomes above it by the Clearance of the biome above (times the point's own scale); Excludes Rows does
the same between any two biomes; only the biomes above can remove points, so adding a lower layer never moves the ones above. Presets: ready-made and saved tables of biomes whose elevations are fractions
of the terrain height. The expected survivors are recomputed with brute-force distances from the same stable candidates. Env ARRAYTRON_MUTATE=bx_layer|bx_scale|bx_exclude|bx_preset breaks the module;
the suite must FAIL."""
from pathlib import Path
import hou, json, math, os, shutil, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PREVIOUS={'v1.19.0':'v1.18.0','v1.20.0':'v1.19.0','v1.21.0':'v1.20.0','v1.21.1':'v1.21.0','v1.21.1':'v1.21.0'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_biomelayers_'));checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')
LIB=WORK/'lib';os.environ['ARRAYTRON_LIBRARY']=str(LIB)
STRIDE=1000000
def write_scene():
    path=WORK/'biome.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    for name in ('Tree','Bush','Grass','Rock'):UsdGeom.Xform.Define(s,'/World/Props/'+name);UsdGeom.Cube.Define(s,'/World/Props/%s/C'%name).CreateSizeAttr(0.2)
    n=40;xs=np.linspace(-20,20,n+1);pts=[]
    for z in xs:
        for x in xs:pts.append((float(x),float(12.0*math.exp(-(x*x+z*z)/(2*7.0*7.0))),float(z)))
    idx=[]
    for j in range(n):
        for i in range(n):a=j*(n+1)+i;idx+=[a,a+n+1,a+n+2,a+1]
    m=UsdGeom.Mesh.Define(s,'/World/Terrain');m.CreatePointsAttr(pts);m.CreateFaceVertexCountsAttr([4]*(n*n));m.CreateFaceVertexIndicesAttr(idx);m.CreateOrientationAttr('rightHanded');m.CreateSubdivisionSchemeAttr('none')
    s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True)
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
KEYS=(('layer','biome_layer','i'),('clear','biome_clear','f'),('excl','biome_excl','s'),('name','biome_name','s'),('density','biome_density','f'),('mix','biome_mix','s'),('scale','biome_scale','t'),('s','biome_srange','t'),('on','biome_on','i'))
def biome_node(stage,source,rows,typ=None,name='Layers',**values):
    a=stage.createNode(typ or TYPE,name);a.setInput(0,source);a.parm('protos').set(4)
    for k,pr in enumerate(('Tree','Bush','Grass','Rock'),1):a.parm('proto_prim%d'%k).set('/World/Props/'+pr)
    a.parm('mode').set(10);a.parm('biomes').set(len(rows));a.parm('biome_seed').set(3);a.parm('biome_normal').set(0);a.parm('biome_moist_mode').set(0);a.parm('biome_moist_const').set(0.5)
    for i,r in enumerate(rows,1):
        for key,parm,kind in KEYS:
            if key in r:
                if kind=='t':a.parmTuple('%s%d'%(parm,i)).set(r[key])
                else:a.parm('%s%d'%(parm,i)).set(r[key])
    for k,v in values.items():a.parm(k).set(v)
    if typ is None:mutate(a)
    return a
def out(a):
    s=a.stage();assert not list(a.errors()),a.errors();from pxr import UsdGeom as G;pi=G.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    d=dict(pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3),ids=np.array(pi.GetIdsAttr().Get(t) or [],dtype=int),scales=np.array(pi.GetScalesAttr().Get(t) or []).reshape(-1,3))
    o=np.argsort(d['ids']);return {k:v[o] for k,v in d.items()}
def mutate(a):
    g=a.hdaModule().biome_clear_keep.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='bx_layer':
        good=g['biome_order'];g['biome_order']=lambda rows:list(reversed(good(rows)))                          # the lower layer is placed first
    elif MUTATE=='bx_scale':
        good=g['biome_clear_keep'];g['biome_clear_keep']=lambda data,rows:good(dict(data,scale=np.ones_like(data['scale'])),rows)    # the clearance ignores the scale of the points
    elif MUTATE=='bx_exclude':
        good=g['biome_clear_keep'];g['biome_clear_keep']=lambda data,rows:good(data,[dict(r,exclude=()) for r in rows])               # Excludes Rows is ignored
    elif MUTATE=='bx_preset':
        g['biome_terrain_height']=lambda asset:(0.0,1.0)                                                       # the preset ignores the height of the terrain
    elif MUTATE:raise SystemExit('unknown mutation '+MUTATE)
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()
def module(a=None):
    if a is None:
        st,sc=new_scene('mod');a=biome_node(st,sc,[dict(density=10.0)])
    return a.hdaModule()
def near(A,B,radius):
    """For every point of B whether some point of A is closer than that point's radius entry (radius per A point)."""
    d=np.linalg.norm(B[:,None,:]-A[None,:,:],axis=2);return (d<radius[None,:]).any(axis=1)

def maths():
    m=module();rows=lambda **kw:dict(dict(index=1,layer=1,clear=0.0,exclude=()),**kw)
    R=[rows(index=1,layer=2),rows(index=2,layer=1,clear=1.0),rows(index=3,layer=3,clear=0.5),rows(index=4,layer=1)]
    assert [r['index'] for r in m.biome_order(R)]==[2,4,1,3]                                                                                              # a layer above comes first (ties by layer, then row)
    X=[rows(index=1,layer=1,exclude=(2,),clear=1.0),rows(index=2,layer=1)];assert [r['index'] for r in m.biome_order(X)]==[1,2]
    X=[rows(index=1,layer=1),rows(index=2,layer=1,exclude=(1,),clear=1.0)];assert [r['index'] for r in m.biome_order(X)]==[2,1]                                   # an excluder is placed before the rows it excludes
    cyc=[rows(index=1,exclude=(2,),clear=1.0),rows(index=2,exclude=(1,),clear=1.0)];assert [r['index'] for r in m.biome_order(cyc)]==[1,2]                         # a cycle is broken by row number
    assert m.biome_parse_rows('2 3, 3;x 05')==(2,3,5) and m.biome_parse_rows('')==() and m.biome_parse_rows(None)==()
    rng=np.random.RandomState(4);n=200
    data=dict(pos=rng.uniform(-3,3,(n,3)),ids=np.arange(n),biome=np.repeat([1,2],n//2),scale=rng.uniform(0.5,1.5,n),normal=np.zeros((n,3)),align=np.zeros((n,4)),proto=np.zeros(n,dtype=int),weight=np.ones(n))
    top=dict(index=1,layer=1,clear=0.8,exclude=());low=dict(index=2,layer=2,clear=0.0,exclude=())
    keep=m.biome_clear_keep(data,[top,low]);A=data['pos'][:100];B=data['pos'][100:];hit=near(A,B,0.8*data['scale'][:100])
    assert keep[:100].all() and np.array_equal(keep[100:],~hit) and 0<hit.sum()<100                                                                           # exactly the brute force
    assert m.biome_clear_keep(data,[dict(top,clear=0.0),low]).all()                                                                                         # clearance 0: nothing changes
    assert m.biome_clear_keep(data,[dict(top,layer=2),low]).all()                                                                                           # the same layer: no interaction
    ex=m.biome_clear_keep(data,[dict(top,layer=2,exclude=(2,)),low]);assert np.array_equal(ex[100:],~hit) and ex[:100].all()                                      # exclusion works on the same layer
    rev=m.biome_clear_keep(data,[dict(top,layer=2),dict(low,layer=1,clear=0.8)]);hit2=near(B,A,0.8*data['scale'][100:]);assert np.array_equal(rev[:100],~hit2) and rev[100:].all()   # the top layer decides, whatever the row number
    big=m.biome_clear_keep(data,[dict(top,clear=3.0),low]);assert big[100:].sum()<keep[100:].sum()                                                          # a larger clearance removes more
    s2=dict(data,scale=data['scale']*2);k2=m.biome_clear_keep(s2,[top,low]);assert k2[100:].sum()<keep[100:].sum()                                                    # the clearance grows with the scale of the point

def layers_on_node():
    st,sc=new_scene('layers');canopy=dict(name='Canopy',density=12.0,mix='1',layer=1,clear=1.6,scale=(0.8,1.4));ground=dict(name='Ground',density=60.0,mix='3',layer=2,clear=0.0,scale=(0.5,1.0))
    base=out(biome_node(st,sc,[dict(canopy,clear=0.0),ground],name='Base'));lay=biome_node(st,sc,[canopy,ground],name='Lay');o=out(lay)
    can=(base['ids']//STRIDE==0);gr=(base['ids']//STRIDE==1);assert can.sum()>20 and gr.sum()>200
    oc=o['ids']//STRIDE==0;og=o['ids']//STRIDE==1
    assert np.array_equal(o['ids'][oc],base['ids'][can]) and np.array_equal(o['pos'][oc],base['pos'][can])                                                      # the canopy (above) is never touched
    hit=near(o['pos'][oc],base['pos'][gr],1.6*o['scales'][oc][:,0]);expected=base['ids'][gr][~hit];assert 0<hit.sum()<gr.sum() and np.array_equal(o['ids'][og],expected)       # the ground keeps exactly the points outside the clearance
    dist=np.linalg.norm(o['pos'][og][:,None,:]-o['pos'][oc][None,:,:],axis=2);assert (dist>=1.6*o['scales'][oc][:,0][None,:]-1e-9).all()
    assert 'cleared by the layers above' in lay.hdaModule().biome_info(lay)
    only=out(biome_node(st,sc,[canopy],name='Only'));assert np.array_equal(only['ids'],o['ids'][oc])                                                           # a lower layer never moves the ones above
    same=out(biome_node(st,sc,[canopy,dict(ground,layer=1)],name='Same'));assert np.array_equal(same['ids'],base['ids'])                                         # the same layer: no clearing
    third=dict(name='Moss',density=90.0,mix='3',layer=3,clear=0.0,scale=(0.4,0.8));deep=out(biome_node(st,sc,[canopy,ground,third],name='Deep'));dg=deep['ids']//STRIDE==2
    assert dg.sum()>0 and np.array_equal(deep['ids'][deep['ids']//STRIDE<2],o['ids'])                                                                                  # a third layer leaves the two above alone
    g_clear=dict(ground,clear=0.6);d3=out(biome_node(st,sc,[canopy,g_clear,third],name='Chain'));m3=d3['ids']//STRIDE==2
    far=near(d3['pos'][d3['ids']//STRIDE==1],d3['pos'][m3],0.6*d3['scales'][d3['ids']//STRIDE==1][:,0]);assert not far.any()                                       # the third layer keeps clear of the second too

def exclusion_rows():
    st,sc=new_scene('excl');a=dict(name='A',density=40.0,mix='1',layer=1,clear=1.2,excl='2',scale=(0.8,1.2));b=dict(name='B',density=80.0,mix='2',layer=1,clear=0.0,scale=(0.8,1.2))
    base=out(biome_node(st,sc,[dict(a,excl='',clear=0.0),b],name='B0'));o=out(biome_node(st,sc,[a,b],name='E1'));oa=o['ids']//STRIDE==0;ob=o['ids']//STRIDE==1
    ba=base['ids']//STRIDE==0;bb=base['ids']//STRIDE==1;assert np.array_equal(o['ids'][oa],base['ids'][ba]) and 0<ob.sum()<bb.sum()
    assert not near(o['pos'][oa],o['pos'][ob],1.2*o['scales'][oa][:,0]).any()                                                                                  # B keeps clear of A
    back=out(biome_node(st,sc,[dict(a,excl=''),dict(b,excl='1',clear=1.2)],name='E2'));assert np.array_equal(back['ids'][back['ids']//STRIDE==1],base['ids'][bb])      # B excludes A: B is placed first, so B is untouched
    assert (back['ids']//STRIDE==0).sum()<ba.sum()
    none=out(biome_node(st,sc,[dict(a,excl='9 x'),b],name='E3'));assert np.array_equal(none['ids'],base['ids'])                                                    # unknown rows in the list are ignored: nothing is cleared
    off=out(biome_node(st,sc,[dict(a,on=0),b],name='E4'));assert np.array_equal(off['ids'],base['ids'][bb])                                                        # a biome that is off does not clear anything

def presets():
    clean=lambda:shutil.rmtree(LIB,ignore_errors=True);clean();st,sc=new_scene('presets');a=biome_node(st,sc,[],name='P');m=a.hdaModule()
    ymin,ymax=m.biome_terrain_height(a);assert abs(ymin-0.0)<0.2 and abs(ymax-12.0)<0.2,(ymin,ymax)
    names=[p['name'] for p in m.BUILTIN_BIOME_PRESETS];assert names==['Temperate Forest','Alpine','Coastal Wetland','Desert']
    for p in m.BUILTIN_BIOME_PRESETS:
        assert 3<=len(p['rows'])<=4 and p['description']
        n=m.biome_apply_preset(a,p);assert n==len(p['rows'])==a.evalParm('biomes')
        for i,r in enumerate(p['rows'],1):
            assert a.evalParm('biome_name%d'%i)==r['name'] and abs(a.evalParm('biome_density%d'%i)-r['density'])<1e-9 and a.evalParm('biome_layer%d'%i)==r['layer'] and abs(a.evalParm('biome_clear%d'%i)-r['clear'])<1e-9
            h=a.evalParmTuple('biome_hrange%d'%i)
            if r['h']:assert abs(h[0]-(ymin+r['h'][0]*(ymax-ymin)))<1e-6 and abs(h[1]-(ymin+r['h'][1]*(ymax-ymin)))<1e-6 and abs(a.evalParm('biome_hedge%d'%i)-r['he']*(ymax-ymin))<1e-6        # fractions of the terrain height
            else:assert h[0]<-99999 and h[1]>99999
            assert a.evalParm('biome_mix%d'%i)==r['mix']
        o=out(a);assert len(o['ids'])>20 and set((o['ids']//STRIDE).tolist())<=set(range(len(p['rows'])))                                                 # every preset cooks and plants
    p=m.BUILTIN_BIOME_PRESETS[0];m.biome_apply_preset(a,dict(p,rows=[dict(p['rows'][0],mix=None)]*2));assert a.evalParm('biomes')==2 and a.evalParm('biome_mix2')=='2'      # no mix named: bank row k
    a.parm('protos').set(1);m.biome_apply_preset(a,dict(p,rows=[dict(p['rows'][0],mix=None)]*3));assert a.evalParm('biome_mix3')=='1'                                    # ... or the last bank row
    a.parm('protos').set(4);m.biome_apply_preset(a,m.BUILTIN_BIOME_PRESETS[1])
    with hou.undos.group('t'):pass
    assert m.biome_load_user_presets()==[]
    path=m.biome_save_preset(a,'  My   Alpine ');assert os.path.isfile(path) and [x['name'] for x in m.biome_load_user_presets()]==['My Alpine']
    mine=m.biome_load_user_presets()[0];assert len(mine['rows'])==4 and mine['rows'][0]['layer']==1 and abs(mine['rows'][0]['h'][0]-0.05)<1e-6 and abs(mine['rows'][0]['clear']-1.2)<1e-9      # elevations saved as fractions
    assert [l for l,_ in m.biome_all_presets()][-1]=='My Alpine  (mine)'
    m.biome_save_preset(a,'My Alpine');assert len(m.biome_load_user_presets())==1                                                                              # the same name is replaced
    b=biome_node(st,sc,[],name='P2',biome_prim='/World/Terrain');m2=b.hdaModule();m2.biome_apply_preset(b,mine);assert b.evalParm('biomes')==4 and abs(b.evalParmTuple('biome_hrange1')[0]-(0.05*(ymax-ymin)+ymin))<1e-6
    open(m.biome_preset_path(),'w').write('not json');assert m.biome_load_user_presets()==[]                                                                         # a broken file is no presets

def contract():
    st,sc=new_scene('contract');a=biome_node(st,sc,[dict(density=5.0)],name='C');g=a.parmTemplateGroup()
    for n in ('biome_layer#','biome_clear#','biome_excl#','biome_preset_load','biome_preset_save'):assert g.find(n) is not None,n
    assert g.find('biome_layer#').defaultValue()==(1,) and g.find('biome_clear#').defaultValue()==(0.0,) and g.find('biome_excl#').defaultValue()==('',) and g.find('biome_layer#').minValue()==1 and g.find('biome_layer#').maxValue()==4
    assert 'biome_layer1' in [p.name() for p in a.parms()] and a.evalParm('biome_layer1')==1 and a.evalParm('biome_clear1')==0.0 and a.evalParm('biome_excl1')==''
    assert g.find('biome_preset_load').scriptCallback().endswith('biome_preset_load(kwargs[\'node\'])')
    text=a.type().definition().sections()['PythonModule'].contents();assert '$' not in text.split('# ---- Biome presets')[1].split('# ----')[0]
    for n in ('biome_order','biome_clear_keep','biome_parse_rows','biome_apply_preset','biome_save_preset'):assert hasattr(a.hdaModule(),n),n

def unchanged():
    st,sc=new_scene('same');rows=[dict(name='F',density=50.0,mix='1',s=(0,60)),dict(name='G',density=90.0,mix='3',scale=(0.5,0.9))]
    pa=out(biome_node(st,sc,rows,name='N'));old=hou.nodeType(hou.lopNodeTypeCategory(),OLD_TYPE);ob=st.createNode(OLD_TYPE,'O');ob.setInput(0,sc);ob.parm('protos').set(4)
    for k,pr in enumerate(('Tree','Bush','Grass','Rock'),1):ob.parm('proto_prim%d'%k).set('/World/Props/'+pr)
    ob.parm('mode').set(10);ob.parm('biomes').set(2);ob.parm('biome_seed').set(3);ob.parm('biome_normal').set(0);ob.parm('biome_moist_mode').set(0);ob.parm('biome_moist_const').set(0.5)
    for i,r in enumerate(rows,1):
        ob.parm('biome_name%d'%i).set(r['name']);ob.parm('biome_density%d'%i).set(r['density']);ob.parm('biome_mix%d'%i).set(r['mix'])
        if 's' in r:ob.parmTuple('biome_srange%d'%i).set(r['s'])
        if 'scale' in r:ob.parmTuple('biome_scale%d'%i).set(r['scale'])
    pb=out(ob);assert len(pa['ids'])>50 and np.array_equal(pa['ids'],pb['ids']) and np.array_equal(pa['pos'],pb['pos']) and np.array_equal(pa['scales'],pb['scales'])    # defaults: the previous release exactly

def main():
    for name,func in (('Maths: the order of the layers and exclusions, the clearance against brute force, scale, same layer, direction, cycles',maths),
                      ('Layers on a node: the upper layer untouched, the lower keeps exactly the points outside the clearance, a third layer, the read-out',layers_on_node),
                      ('Excludes Rows: a biome keeps clear of another on the same layer, the excluder wins, a biome that is off clears nothing',exclusion_rows),
                      ('Presets: the four ready-made tables (elevation as terrain fractions, every one cooks), mixes by row, saving and loading your own, a broken file',presets),
                      ('Contract: parameters, defaults, buttons, module functions, no dollar signs',contract),
                      ('The previous release unchanged with the default layers',unchanged)):check(name,func)
    result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
    if not MUTATE:(ROOT/'tests'/('validation_biomelayers_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
    print('ALL PASSED',len(checks))
main()
