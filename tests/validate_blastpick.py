"""v1.33.0 in real Houdini: hython tests/validate_blastpick.py [version]
Blast, part two: the Region shapes (Triangle, Hexagon, Polygon with your own number of sides, Star, Metaballs) and Select By Custom, the selection made by hand with Houdini's own point selection: the helper geometry holds one
point per instance (in world space, as the viewport shows them), Houdini's selection (here a stand-in for hou.SceneViewer.selectGeometry) returns point numbers, and they come back as instance ids. Env
ARRAYTRON_MUTATE=bp_map|bp_world|bp_op|bp_star breaks the module; the suite must FAIL."""
from pathlib import Path
import hou, json, math, os, sys, tempfile, time, types
import numpy as np
from pxr import Usd, UsdGeom
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
TYPE=versions.type_name(VID)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_blastpick_'));checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')
def write_scene():
    path=WORK/'blastpick.usda';s=Usd.Stage.CreateNew(str(path));root=UsdGeom.Xform.Define(s,'/World');s.SetDefaultPrim(root.GetPrim());UsdGeom.SetStageUpAxis(s,UsdGeom.Tokens.y)
    UsdGeom.Xform.Define(s,'/World/Props/Ball');UsdGeom.Cube.Define(s,'/World/Props/Ball/C').CreateSizeAttr(0.2)
    s.GetRootLayer().Save();return path.as_posix()
SCENE=write_scene()
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True);hou.hda.installFile(str(versions.hda(VID)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));st=hou.node('/stage')
    n=st.createNode('reference','scene');n.parm('primpath').set('/World');n.parm('primpath1').set('/World');n.parm('filepath1').set(SCENE);n.parm('filerefprim1').set('defaultPrim');return st,n
def node(stage,source,name='Bp',count=2500,**values):
    a=stage.createNode(TYPE,name);a.setInput(0,source);a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Ball');a.parm('mode').set(1);a.parm('area_count').set(count);a.parm('area_sizex').set(20.0);a.parm('area_sizez').set(20.0)
    for k,v in values.items():
        pt=a.parmTuple(k)
        if pt is not None:pt.set(v if isinstance(v,(tuple,list)) else (v,))
        else:a.parm(k).set(v)
    mutate(a);return a
def all_errors(n):
    o=list(n.errors())
    for c in n.children():o+=all_errors(c)
    return o
def out(a):
    a.stage();errs=all_errors(a);assert not errs,errs;pi=UsdGeom.PointInstancer(a.stage().GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    ids=np.array(pi.GetIdsAttr().Get(t) or [],dtype=int);pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3);o=np.argsort(ids);return ids[o],pos[o]
def mutate(a):
    g=a.hdaModule().select_ids.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='bp_map':
        good=g['blast_points_from_text'];g['blast_points_from_text']=lambda text:good(text)+1                                                                                                     # every picked point is the next one
    elif MUTATE=='bp_world':
        good=g['blast_snapshot'];g['blast_snapshot']=lambda asset:(lambda r:dict(ids=r['ids'],P=r['P']-np.array(asset.evalParmTuple('bound_t'))))(good(asset))                              # the layout transform is ignored: the points are not where the instances are
    elif MUTATE=='bp_op':
        good=g['combine_picks'];g['combine_picks']=lambda cur,hits,op:good(cur,hits,{2:1,3:1}.get(op,op))                                                                                   # Remove and Toggle add
    elif MUTATE=='bp_star':
        good=g['star_vertices'];g['star_vertices']=lambda outer,inner,points:good(outer,1.0,points)                                                                                         # no inner radius
    elif MUTATE:raise SystemExit('unknown mutation '+MUTATE)
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()

# ---------------------------------------------------------------- independent expectations
def polar(centre,radius,angles_deg):
    return [(centre[0]+radius*math.cos(math.radians(a)),centre[2]+radius*math.sin(math.radians(a))) for a in angles_deg]
def inside_convex(P,verts):
    """Inside a convex polygon given counter-clockwise or clockwise by the sign of every cross product."""
    signs=[]
    for k in range(len(verts)):
        a=np.array(verts[k]);b=np.array(verts[(k+1)%len(verts)]);signs.append((b[0]-a[0])*(P[:,2]-a[1])-(b[1]-a[1])*(P[:,0]-a[0]))
    s=np.array(signs);return (s>=0).all(axis=0)|(s<=0).all(axis=0)
def inside_winding(P,verts):
    """Winding number test (angles), any polygon."""
    v=np.array(verts);tot=np.zeros(len(P))
    for k in range(len(v)):
        a=v[k]-P[:,[0,2]];b=v[(k+1)%len(v)]-P[:,[0,2]];tot+=np.arctan2(a[:,0]*b[:,1]-a[:,1]*b[:,0],a[:,0]*b[:,0]+a[:,1]*b[:,1])
    return np.abs(tot)>np.pi

def shapes():
    st,sc=new_scene('shapes');ref=node(st,sc,name='Ref');ids0,pos0=out(ref);assert len(ids0)==2500;c=(1.0,0.0,-1.0)
    def kept(**v):
        v.setdefault('blast_center',c);a=node(st,sc,name='S',blast_on=1,blast_select=2,blast_action=0,**v);return out(a)
    # triangle and hexagon and a seven sided polygon, turned 30 degrees
    for shape,sides,name in ((2,3,'Triangle'),(3,6,'Hexagon'),(4,7,'Polygon')):
        ids,pos=kept(blast_shape=shape,blast_radius=5.0,blast_rotate=30.0,blast_sides=sides);verts=polar(c,5.0,[30.0+360.0*k/sides for k in range(sides)]);inside=inside_convex(pos0,verts)
        assert set(ids)==set(ids0[~inside]) and 20<inside.sum()<2000,(name,len(ids),int(inside.sum()))
    assert 3<=int(inside_convex(pos0,polar(c,5.0,[30,150,270])).sum()) and not np.array_equal(kept(blast_shape=2,blast_radius=5.0,blast_rotate=30.0)[0],kept(blast_shape=2,blast_radius=5.0,blast_rotate=90.0)[0])        # the Rotate parameter turns it
    # a star
    ids,pos=kept(blast_shape=5,blast_radius=6.0,blast_points=5,blast_inner=0.4,blast_rotate=10.0);verts=[]
    for k in range(10):r=6.0 if k%2==0 else 6.0*0.4;a=math.radians(10.0+36.0*k);verts.append((c[0]+r*math.cos(a),c[2]+r*math.sin(a)))
    inside=inside_winding(pos0,verts);assert set(ids)==set(ids0[~inside]) and 20<inside.sum()<1500
    # metaballs: the field of the balls, summed with a loop
    ids,pos=kept(blast_shape=6,blast_radius=3.0,blast_blobs=4,blast_spread=3.0,blast_threshold=0.3,blast_blobseed=2);m=ref.hdaModule();centres,radii=m.blob_layout(c,3.0,4,3.0,2)
    f=np.zeros(len(pos0))
    for k in range(4):
        t2=((pos0-centres[k])**2).sum(axis=1)/radii[k]**2;f+=np.where(t2<1,(1-t2)**3,0.0)
    assert set(ids)==set(ids0[~(f>=0.3)]) and (f>=0.3).sum()>30
    fat=kept(blast_shape=6,blast_radius=3.0,blast_blobs=4,blast_spread=3.0,blast_threshold=0.05,blast_blobseed=2)[0];thin=kept(blast_shape=6,blast_radius=3.0,blast_blobs=4,blast_spread=3.0,blast_threshold=0.8,blast_blobseed=2)[0]
    assert len(fat)<len(ids)<len(thin)                                                                                       # a lower threshold fattens the blob
    # the height of the flat shapes: a column 2 tall at height 5 holds nothing
    assert len(kept(blast_shape=3,blast_radius=5.0,blast_center=(1.0,5.0,-1.0),blast_height=2.0)[0])==2500
    # Box turned
    ids,pos=kept(blast_shape=1,blast_size=(8.0,4.0,3.0),blast_rotate=45.0);a=math.radians(45.0);d=pos0-np.array(c);u=d[:,0]*math.cos(a)+d[:,2]*math.sin(a);v=-d[:,0]*math.sin(a)+d[:,2]*math.cos(a);inside=(abs(u)<=4)&(abs(v)<=1.5)
    assert set(ids)==set(ids0[~inside])

# ---------------------------------------------------------------- the native selection (a stand-in for the viewer)
class FakeSelection(object):
    """What Houdini returns: the selection belongs to the node it was made on, so it cannot be read once the helper is gone."""
    def __init__(self,text,helper=None):self.text=text;self.path=helper.path() if helper is not None else None
    def mergedSelectionString(self,empty_string_selects_all=True,force_numeric=False):
        if self.path is not None and hou.node(self.path) is None:raise hou.ObjectWasDeleted()
        return self.text
def helper_points(helper):
    g=helper.node('SNAPSHOT').geometry();return np.array(g.pointFloatAttribValues('P')).reshape(-1,3),np.array(g.pointIntAttribValues('id'))
def chooser(rule):
    """A selection stand-in: picks the helper points for which rule(P) is true, the way the user would with the box or lasso."""
    def pick(helper):
        P,ids=helper_points(helper);numbers=np.nonzero(rule(P))[0]
        return FakeSelection(' '.join(str(int(i)) for i in numbers),helper)
    return pick
def picked(a):return set(a.hdaModule().blast_picked_ids(a).tolist())

def native_selection():
    st,sc=new_scene('native');a=node(st,sc,name='Nat',count=1500,blast_on=1,blast_select=4,blast_action=0);a.parmTuple('bound_t').set((5.0,0.0,2.0));m=a.hdaModule();full=len(out(a)[0]);assert full==1500
    inst=m.pick_instances(a);assert len(inst['ids'])==1500;world={int(i):p for i,p in zip(inst['ids'],inst['P'])}                                                           # where the instances are, from the USD
    left=lambda P:P[:,0]<5.0                                                                                                                           # the left half of the scatter (the layout sits at x = 5)
    seen={}
    def first(helper):
        P,ids=helper_points(helper);seen['n']=len(P);seen['err']=max(float(np.abs(P[k]-world[int(i)]).max()) for k,i in enumerate(ids[:400]));return chooser(left)(helper)
    n=m.blast_hselect(a,first);want={i for i,p in world.items() if p[0]<5.0}
    assert seen['n']==1500 and seen['err']<1e-3,seen                                                                                                   # one point per instance, exactly where the instance is (the layout transform included)
    assert a.evalParm('blast_select')==4 and picked(a)==want and n==len(want) and 300<len(want)<1200 and hou.node('/obj/'+a.name()+'_blast_select') is None                # the helper is gone again
    assert set(out(a)[0].tolist())==set(range(1500))-want                                                                                                 # Blast deletes exactly the picked ones
    top=lambda P:P[:,2]<2.0;topids={i for i,p in world.items() if p[2]<2.0}
    a.parm('blast_pick_op').set(1);m.blast_hselect(a,chooser(top));assert picked(a)==want|topids
    a.parm('blast_pick_op').set(2);m.blast_hselect(a,chooser(top));assert picked(a)==want-topids
    a.parm('blast_pick_op').set(3);m.blast_hselect(a,chooser(top));assert picked(a)==(want-topids)^topids
    a.parm('blast_pick_op').set(0);m.blast_hselect(a,chooser(top));assert picked(a)==topids
    before=picked(a);assert m.blast_hselect(a,lambda helper:None)==len(before) and picked(a)==before                                                    # Esc: nothing changes
    m.blast_hselect(a,chooser(lambda P:np.zeros(len(P),dtype=bool)));assert picked(a)==set()                                                            # Replace with nothing selected clears the list
    m.blast_hselect(a,chooser(left));cnt={}
    def check_all(helper):
        P,ids=helper_points(helper);cnt['n']=len(P);g=helper.node('SNAPSHOT').geometry();cd=np.array(g.pointFloatAttribValues('Cd')).reshape(-1,3);cnt['red']=int((cd[:,0]>0.9).sum());return FakeSelection('',helper)
    a.parm('blast_pick_op').set(1);m.blast_hselect(a,check_all);assert cnt['n']==1500 and cnt['red']==len(want),cnt                                       # all 1500 are there although the picked ones are deleted, the picked ones are red
    a.parm('blast_invert').set(1);assert set(out(a)[0].tolist())==want;a.parm('blast_invert').set(0)
    a.parm('blast_action').set(1);a.parmTuple('blast_move').set((0.0,3.0,0.0));ids2,pos2=out(a);ref=node(st,sc,name='Ref',count=1500);ref.parmTuple('bound_t').set((5.0,0.0,2.0));ids0,pos0=out(ref);sel=np.isin(ids0,list(want))
    assert np.allclose(pos2[sel],pos0[sel]+[0,3,0],atol=1e-3) and np.allclose(pos2[~sel],pos0[~sel],atol=1e-3)                                           # a transform of the picked instances together
    m.blast_pick_clear(a);assert picked(a)==set();m.blast_pick_all(a);assert picked(a)==set(range(1500));a.parm('blast_picked').set('3 7-10');assert picked(a)=={3,7,8,9,10}

def viewer_calls():
    """The real call: Houdini's selectGeometry on the helper, with the points type, then the viewer is put back."""
    st,sc=new_scene('viewer');a=node(st,sc,name='Vw',count=400,blast_on=1,blast_select=4);m=a.hdaModule();log={}
    class FakeViewer(object):
        def __init__(self):self.cwd=st
        def pwd(self):return self.cwd
        def setPwd(self,n):self.cwd=n
        def selectGeometry(self,prompt='',**kw):
            log['pwd']=self.cwd.path();log['kw']=kw;log['prompt']=prompt;P,ids=helper_points(self.cwd);log['n']=len(P);return FakeSelection('0-9 20',self.cwd)
    import types as _t;viewer=FakeViewer();old=(hou.isUIAvailable,getattr(hou,'ui',None));queued=[]
    try:
        try:m.blast_pick_start(a);raise AssertionError('no interface here')
        except hou.NodeError as exc:assert 'interface' in str(exc)
        hou.isUIAvailable=lambda:True;hou.ui=_t.SimpleNamespace(paneTabOfType=lambda t:viewer,setStatusMessage=lambda *x,**k:None);sys.modules['hdefereval']=_t.SimpleNamespace(executeDeferred=lambda f:queued.append(f))
        m.blast_pick_start(a);assert len(queued)==1 and picked(a)==set()                                                                  # the button only schedules: the selection runs after the callback has returned
        m.blast_pick_start(a);assert len(queued)==1                                                                                         # Enter on the focused button while it is pending or running does nothing
        queued[0]();assert len(queued)==1                                                                                                   # the scheduled selection
        m.blast_pick_start(a);assert len(queued)==1                                                                                         # nor does it a moment after the selection ended
    finally:
        sys.modules.pop('hdefereval',None);hou.isUIAvailable=old[0]
        if old[1] is None:del hou.ui
        else:hou.ui=old[1]
    assert log['pwd']=='/obj/'+a.name()+'_blast_select' and log['kw'].get('geometry_types')==(hou.geometryType.Points,) and log['kw'].get('use_existing_selection') is False and log['n']==400 and 'select' in log['prompt'].lower()
    assert viewer.cwd==st and set(m.blast_picked_ids(a).tolist())==set(range(10))|{20} and hou.node('/obj/'+a.name()+'_blast_select') is None                                      # the viewer is put back, the points 0-9 and 20 are the ids, read while the helper existed

def buttons():
    st,sc=new_scene('buttons');a=node(st,sc,name='Btn',count=400);m=a.hdaModule();g=a.parmTemplateGroup()
    for k in ('blast_pick_go','blast_pick_all','blast_pick_clear'):
        t=g.find(k);assert t is not None and t.type()==hou.parmTemplateType.Button and t.scriptCallbackLanguage()==hou.scriptLanguage.Python and {'blast_pick_go':'blast_pick_start'}.get(k,k) in t.scriptCallback(),k
    assert g.find('blast_pick_go').label()=='Select In Houdini' and tuple(g.find('blast_select').menuLabels())==('Id Pattern','Random','Region','Prototype','Custom (Houdini selection)') and tuple(g.find('blast_shape').menuLabels())==('Sphere','Box','Triangle','Hexagon','Polygon','Star','Metaballs')
    assert tuple(g.find('blast_pick_op').menuLabels())==('Replace','Add','Remove','Toggle')
    a.parm('blast_on').set(1);a.parm('blast_select').set(4);m.blast_pick_all(a);assert len(picked(a))==400
    a.parm('blast_action').set(0);assert len(out(a)[0])==0;m.blast_pick_clear(a);assert picked(a)==set() and len(out(a)[0])==400
    a.parm('blast_picked').set('3 7-10 15');assert set(out(a)[0].tolist())==set(range(400))-{3,7,8,9,10,15}                                                          # the list can be typed too
    names=[x.name() for t in g.entries() if t.label()=='Scatter' for x in t.parmTemplates()]
    for k in ('blast_rotate','blast_height','blast_sides','blast_points','blast_inner','blast_blobs','blast_spread','blast_threshold','blast_blobseed','blast_pick_go','blast_pick_op','blast_picked','blast_pick_all','blast_pick_clear'):assert k in names,k
    for k in ('blast_tool','blast_brush','blast_through','blast_picking'):assert g.find(k) is None,k                                                              # no tool of our own any more: Houdini's own

for n,f in (('Region shapes: Triangle, Hexagon, Polygon, Star, Metaballs, Box turned, Height',shapes),("Select By Custom with Houdini's own selection: the helper points, the ids, the Operation menu, Esc, the picked ones in red, Blast acts on them",native_selection),
            ('the real call: selectGeometry on the helper with the points type, the viewer put back',viewer_calls),('the buttons, the menus and the parameters in the Scatter tab',buttons)):check(n,f)
result={'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'mutation':MUTATE}
if not MUTATE:(ROOT/'tests'/('validation_blastpick_%s.json'%versions.tag(VID))).write_text(json.dumps(result,indent=1))
print('ALL PASSED %d'%len(checks));print(json.dumps(checks))
