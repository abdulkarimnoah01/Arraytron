"""Grow animation and the six-tab interface (v0.5.2) validation in real Houdini: hython tests/validate_grow.py
Results are read from the USD stage at chosen frames (hou.setFrame): instance scales, positions and the PointInstancer's invisibleIds. Expected values
are computed here with plain Python from the documented formulas. Env ARRAYTRON_MUTATE=<name> breaks the module; the suite must then FAIL."""
from pathlib import Path
import hou, json, math, os, re, shutil, sys, tempfile, time
import numpy as np
from pxr import Usd, UsdGeom, Gf, Vt
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT)
PHYSTAB='Physics' if VID[0]=='v' and tuple(int(x) for x in VID[1:].split('.'))>=(1,6,2) else 'Settle'
PREVIOUS={'v0.5.2':'v0.5.1','v0.6.0':'v0.5.2','v0.7.0':'v0.6.0','v0.8.0':'v0.7.0','v0.9.0':'v0.8.0','v1.0.0':'v0.9.0','v1.1.0':'v1.0.0','v1.5.0':'v1.1.0','v1.6.0':'v1.5.0','v1.6.1':'v1.6.0','v1.6.2':'v1.6.1'}[VID]
TYPE=versions.type_name(VID);OLD_TYPE=versions.type_name(PREVIOUS)
WORK=Path(tempfile.mkdtemp(prefix='arraytron_grow_'))
STONE=(ROOT/'dist/test_assets/stone.usda').as_posix()
checks=[];MUTATE=os.environ.get('ARRAYTRON_MUTATE')
def new_scene(name='scene'):
    hou.hipFile.clear(suppress_save_prompt=True)
    for v in (VID,PREVIOUS):hou.hda.installFile(str(versions.hda(v)),force_use_assets=True)
    hou.hipFile.save(str(WORK/(name+'.hip')));hou.setFrame(1);return hou.node('/stage')
def setv(a,**values):
    for key,value in values.items():
        t=a.parmTuple(key)
        for q in t:
            if q.keyframes():q.deleteAllKeyframes()                     # typing a number over an expression replaces it
        t.set(value if isinstance(value,(tuple,list)) else (value,))
    return a
def scene(**values):
    st=new_scene('grow');n=st.createNode('reference','stone');n.parm('primpath').set('/World/Props/Stone');n.parm('primpath1').set('/World/Props/Stone');n.parm('filepath1').set(STONE);n.parm('filerefprim1').set('defaultPrim')
    a=st.createNode(TYPE,'Arraytron');a.setInput(0,n);a.parm('protos').set(1);a.parm('proto_prim1').set('/World/Props/Stone')
    if MUTATE:mutate(a)
    return st,n,setv(a,**values)
def at(a,frame):
    hou.setFrame(frame);s=a.stage();assert not a.errors(),a.errors()
    pi=UsdGeom.PointInstancer(s.GetPrimAtPath(a.evalParm('outputpath')));t=hou.frame()
    inv=pi.GetInvisibleIdsAttr().Get(t) if pi.GetInvisibleIdsAttr() else None
    return dict(pos=np.array(pi.GetPositionsAttr().Get(t) or []).reshape(-1,3),scales=np.array(pi.GetScalesAttr().Get(t) or []).reshape(-1,3),ids=list(pi.GetIdsAttr().Get(t) or []),
                orient=np.array([[q.GetImaginary()[0],q.GetImaginary()[1],q.GetImaginary()[2],q.GetReal()] for q in (pi.GetOrientationsAttr().Get(t) or [])]).reshape(-1,4),
                proto=list(pi.GetProtoIndicesAttr().Get(t) or []),invisible=sorted(int(i) for i in inv) if inv is not None else None,stage=s)
def all_errors(node):
    out=list(node.errors())
    for c in node.children():out+=all_errors(c)
    return out
M64=(1<<64)-1
def ref_hash(i,seed,stream=0):
    z=(i*0x9E3779B97F4A7C15+seed*0xD1B54A32D192ED03+(stream+1)*0x8CB92BA72F3D8DD7)&M64
    z=((z^(z>>30))*0xBF58476D1CE4E5B9)&M64;z=((z^(z>>27))*0x94D049BB133111EB)&M64;z=z^(z>>31)
    return (z>>11)/float(1<<53)
def ease_ref(kind,x):
    x=min(1.0,max(0.0,x))
    if kind==0:return x
    if kind==1:return x*x*(3-2*x)
    if kind==2:c1=1.70158;c3=c1+1;return 1+c3*(x-1)**3+c1*(x-1)**2
    n1,d1=7.5625,2.75
    if x<1/d1:return n1*x*x
    if x<2/d1:x-=1.5/d1;return n1*x*x+0.75
    if x<2.5/d1:x-=2.25/d1;return n1*x*x+0.9375
    x-=2.625/d1;return n1*x*x+0.984375
def check(name,func):
    t=time.time();func();checks.append(name);print('PASS %s (%.1fs)'%(name,time.time()-t));sys.stdout.flush()
def mutate(a):
    g=a.hdaModule().sop_grow.__globals__
    if g.get('_mutation')==MUTATE:return
    g['_mutation']=MUTATE
    if MUTATE=='grow_order':
        good=g['sweep_position'];g['sweep_position']=lambda P,ids,mode,vector,reverse:good(P,ids,mode,vector,1-int(reverse))
    elif MUTATE=='grow_ease':
        good=g['ease'];g['ease']=lambda kind,x:good(1 if kind==2 else kind,x)
    elif MUTATE=='grow_time':
        good=g['growth'];g['growth']=lambda u,ids,frame,start,sweep,duration,delay,seed:good(u,ids,frame,start,sweep,duration*2,delay,seed)
    elif MUTATE=='grow_final':
        good=g['apply_style'];g['apply_style']=lambda style,kind,f,scale,P,rise:good(style,kind,np.minimum(np.asarray(f),0.999),scale,P,rise)
    elif MUTATE=='grow_style':
        good=g['apply_style'];g['apply_style']=lambda style,kind,f,scale,P,rise:good(0 if style==1 else style,kind,f,scale,P,rise)
    else:raise SystemExit('unknown mutation '+MUTATE)

LINE=dict(mode=0,line_count=5,line_length=4,line_axis=0,line_center=1)      # five points at x = -2, -1, 0, 1, 2
def flat(entries):
    out=[]
    for t in entries:
        if t.type()==hou.parmTemplateType.Folder and t.folderType()!=hou.folderType.MultiparmBlock:out+=flat(t.parmTemplates())
        elif not t.name().startswith('ui_'):out.append(t.name())
    return out

def ui_tabs():
    st,n,a=scene();g=a.parmTemplateGroup();tabs=g.entries()
    assert [t.label() for t in tabs]==['Source','Layout','Look','Spacing',PHYSTAB,'Animate']+(['Optimize'] if any(x.name()=='cam_on' for t in tabs for x in t.parmTemplates()) else [])+(['Finish'] if any(x.name()=='dbg_on' for t in tabs for x in t.parmTemplates()) else []) and all(t.folderType()==hou.folderType.Tabs for t in tabs)
    assert sum(len(flat([t])) for t in tabs)>=140,'every parameter is still there'
    contents={t.label():flat([t]) for t in tabs}
    exp=['protos','proto_mode']+(['proto_percent'] if 'proto_percent' in contents['Source'] else [])+['proto_summary'];assert contents['Source'][:len(exp)]==exp and contents['Source'][-1]=='outputpath'
    assert contents['Layout'][0]=='mode' and 'bound_t' in contents['Layout'] and 'line_axis' in contents['Layout'] and 'surface_prim' in contents['Layout']
    assert contents['Look'][:2]==['base_rotation','base_scale'] and 'mask_source' in contents['Look'] and 'scale_nonuniform' in contents['Look']
    assert contents['Spacing'][0]=='overlap_mode' and contents[PHYSTAB][0]=='phys_on' and contents['Animate'][0]=='grow_on' and 'phys_bake' in contents[PHYSTAB]
    # no parameter appears twice and the old flat names are all present
    names=flat(tabs);assert len(names)==len(set(names)),[n for n in names if names.count(n)>1]
    old=hou.nodeType(hou.lopNodeTypeCategory(),OLD_TYPE).parmTemplateGroup();oldnames=flat(old.entries());assert set(oldnames)<=set(names),sorted(set(oldnames)-set(names))
    # every parameter of an old release keeps its default value and its menu
    for name in oldnames:
        o=old.find(name);nw=g.find(name)
        if o.type()==hou.parmTemplateType.Folder:continue
        assert o.type()==nw.type() and o.dataType()==nw.dataType(),name
        if hasattr(o,'defaultValue') and o.type()!=hou.parmTemplateType.Label:assert o.defaultValue()==nw.defaultValue(),(name,o.defaultValue(),nw.defaultValue())
        if o.type()==hou.parmTemplateType.Menu:assert nw.menuItems()[:len(o.menuItems())]==o.menuItems() and nw.menuLabels()[:len(o.menuLabels())]==o.menuLabels(),name
    # mode panels sit under headings and carry the mode condition; essential details are in collapsible sections
    for name,mode in (('line_axis',0),('area_sizex',1),('grid_count',2),('circle_radius',3),('curve_prim',4),('surface_prim',5)):assert g.find(name).conditionals()[hou.parmCondType.HideWhen].endswith('{ mode != %d }'%mode),name
    assert {t.label() for t in tabs[0].parmTemplates() if t.type()==hou.parmTemplateType.Folder}=={'Prototype Bank','Selection Details'}
    sections=[f.label() for t in tabs for f in t.parmTemplates() if f.type()==hou.parmTemplateType.Folder and f.folderType()==hou.folderType.Collapsible];assert sections==['Selection Details','Pivot & Guide','Variation Details','Mask Details','Solver Settings','Material & Forces','Collision Settings','Cache Settings'],sections
    assert g.find('ui_pivot') and 'bound_p' in flat([g.find('ui_pivot')]) and 'show_bounds' in flat([g.find('ui_pivot')])
    # the viewport handle still binds the same 12 parameters
    text=hou.hda.definitionsInFile(str(versions.hda(VID)))[0].sections()['DialogScript'].contents();bound=re.findall(r'^\s*bindhandle (\w+) lopxform "Transformer" (\w+) ""',text,re.M);assert sorted(p for p,_ in bound)==sorted('bound_%s%s'%(t,x) for t in 'trsp' for x in 'xyz')

def ui_animate():
    st,n,a=scene();g=a.parmTemplateGroup()
    d=dict(grow_on=0,grow_direction=0,grow_reverse=0,grow_start=1.0,grow_sweep=48.0,grow_time=12.0,grow_delay=0.0,grow_seed=1,grow_style=0,grow_ease=1,grow_rise=0.5)
    for k,v in d.items():assert a.evalParm(k)==v,(k,a.evalParm(k));assert g.find(k).help().strip(),k
    assert tuple(a.evalParmTuple('grow_vector'))==(1,0,0) and g.find('grow_start').defaultExpression()==('$FSTART',) and g.find('grow_frame').isHidden() and g.find('grow_frame').defaultExpression()==('$FF',)
    assert g.find('grow_direction').menuLabels()==('Along X','Along Y (upward)','Along Z','Custom Vector','Outward From Centre','By Point Order') and g.find('grow_ease').menuLabels()==('Linear','Smooth','Overshoot (pop)','Bounce')
    assert g.find('grow_style').menuLabels()==('Grow (scale up)','Plant (taller first, wider later)','Rise (climb out of the ground)')
    hide=lambda n:g.find(n).conditionals()[hou.parmCondType.HideWhen];dis=lambda n:g.find(n).conditionals()[hou.parmCondType.DisableWhen]
    assert hide('grow_vector')=='{ grow_direction != 3 }' and hide('grow_seed')=='{ grow_delay == 0 }' and hide('grow_rise')=='{ grow_style != 2 }'
    assert all(dis(n)=='{ grow_on == 0 }' for n in ('grow_direction','grow_start','grow_sweep','grow_time','grow_style','grow_ease','grow_delay'))
    assert a.evalParm('grow_info')=='Grow is off.'
    setv(a,grow_on=1,grow_start=10,grow_sweep=20,grow_time=10);assert a.evalParm('grow_info')=='The first instance starts at frame 10, the last one is full size at frame 40 (now: frame 1).',a.evalParm('grow_info')
    setv(a,grow_delay=0.5);assert 'frame 55' in a.evalParm('grow_info'),a.evalParm('grow_info')
    order=[];n=a.node('USD_COMPILER/OUT_POINTS')
    while n is not None:order.append(n.name());n=n.inputs()[0] if n.inputs() else None
    order=[x for x in order if x!='PROTO_PATH']                # the Houdini 20.5 / 21 build adds PROTO_PATH last
    pv=['PRIMVARS'] if a.node('USD_COMPILER/PRIMVARS') else []
    ov=['OVERRIDES'] if a.node('USD_COMPILER/OVERRIDES') else []
    assert order[:3+len(pv)+len(ov)]==['OUT_POINTS']+pv+['GROW']+ov+['PHYSICS_SWITCH'],order
    assert 'Grow' in a.type().definition().sections()['ArraytronVersion'].contents()

def off_unchanged():
    st,n,new=scene();old=st.createNode(OLD_TYPE,'old');old.setInput(0,n);old.parm('protos').set(1);old.parm('proto_prim1').set('/World/Props/Stone')
    def snap(node):
        pi=UsdGeom.PointInstancer(node.stage().GetPrimAtPath('/World/Arraytron'));t=hou.frame();assert not node.errors(),node.errors()
        return {k:list(getattr(pi,'Get'+k+'Attr')().Get(t)) for k in ('Positions','Orientations','Scales','Ids','ProtoIndices')}
    cases=[dict(mode=0,line_count=40,position_random=(.1,.1,.1)),dict(mode=1,area_count=120,bound_t=(1,2,3),mask_source=1,overlap_mode=1),dict(mode=2,grid_count=(3,3,3),scale_random_mode=1),dict(mode=3,circle_facing=1,circle_count=20),dict(mode=1,area_count=30,phys_on=1)]
    for k,values in enumerate(cases):
        for node in (new,old):
            for p in node.parms():
                if p.parmTemplate().type() not in (hou.parmTemplateType.Folder,hou.parmTemplateType.FolderSet) and not p.isMultiParmInstance() and p.name()!='protos' and not p.name().startswith('grow_') and not p.name().startswith('ui_'):p.revertToDefaults()
            node.parm('protos').set(1);setv(node,proto_prim1='/World/Props/Stone',**values)
        for frame in (1,37):
            hou.setFrame(frame);assert snap(new)==snap(old),('case',k,values,frame)
    hou.setFrame(1);new.node('USD_COMPILER/GROW').geometry();assert not new.node('USD_COMPILER/GROW').isTimeDependent(),'Grow off: the node does not depend on time'

def timing_exact():
    st,n,a=scene(**LINE,base_scale=2.0,scale_random=0.2,random_seed=3);plain=at(a,1)['scales'];setv(a,grow_on=1,grow_start=10,grow_sweep=20,grow_time=10,grow_ease=0)
    u=[0,0.25,0.5,0.75,1.0]
    for frame in (1,9,10,12,15,20,22.5,25,30,35,40,60):
        d=at(a,frame);f=[min(1.0,max(0.0,(frame-(10+ui*20))/10)) for ui in u];want=np.array([plain[i]*max(f[i],1e-5) if f[i]<1 else plain[i] for i in range(5)])
        assert np.allclose(d['scales'],want,rtol=1e-4,atol=1e-9),(frame,d['scales'][:,0],want[:,0])
        assert d['invisible']==[i for i in range(5) if f[i]<=0],(frame,d['invisible'],f)
        assert d['ids']==list(range(5)) and d['proto']==[0]*5
    full=at(a,60);setv(a,grow_on=0);off=at(a,60);assert np.array_equal(full['scales'],off['scales']) and np.array_equal(full['pos'],off['pos']) and np.array_equal(full['orient'],off['orient']),'after the sweep the result is exactly the normal one'
    assert off['invisible'] in (None,[]),'Grow off authors no invisible ids'
    setv(a,grow_on=1,grow_reverse=1);d=at(a,20);f=[min(1.0,max(0.0,(20-(10+(1-ui)*20))/10)) for ui in u];assert np.allclose(d['scales'][:,0],[plain[i,0]*max(f[i],1e-5) if f[i]<1 else plain[i,0] for i in range(5)],rtol=1e-4),'Reverse starts at the other end'
    setv(a,grow_reverse=0,grow_sweep=0);d=at(a,10.5);assert np.allclose(d['scales'][:,0],plain[:,0]*0.05,rtol=1e-4),'Sweep 0: everything starts together'
    setv(a,grow_sweep=20,grow_start=-5);assert np.allclose(at(a,-5)['scales'][:,0],plain[:,0]*1e-5,rtol=1e-3),'a negative Start Frame works'
    # scrubbing: any order of frames gives the same result
    setv(a,grow_start=10);a1=at(a,22)['scales'];at(a,5);at(a,45);a2=at(a,22)['scales'];assert np.array_equal(a1,a2),'the result depends only on the current frame'

def directions():
    # a 3 x 3 x 3 grid: ids x fastest; positions -2..2 on every axis (grid_size 4), unit spacing 2
    st,n,a=scene(mode=2,grid_count=(3,3,3),grid_size=(4,4,4),grid_center=1,grow_on=1,grow_start=0,grow_sweep=40,grow_time=1,grow_ease=0)
    plain=at(a,1000);P=plain['pos'];full=plain['scales'][:,0]
    def started_at(direction,**extra):
        setv(a,grow_direction=direction,**extra);out=[]
        for frame in range(0,42):
            d=at(a,frame);vis=set(range(27))-set(d['invisible'])
            out.append(vis)
        first={i:min(f for f,v in enumerate(out) if i in v) for i in range(27)};return first
    for direction,vec in ((0,(1,0,0)),(1,(0,1,0)),(2,(0,0,1)),(3,(1,1,0))):
        first=started_at(direction,grow_vector=vec);d=np.array(vec,float);d/=np.linalg.norm(d);proj=P@d;u=(proj-proj.min())/(proj.max()-proj.min())
        for i in range(27):assert abs(first[i]-(u[i]*40+1))<=1.0,(direction,i,first[i],u[i]*40)          # visible from the first frame after its start frame start = u x 40
        order=sorted(range(27),key=lambda i:(first[i]));assert all(proj[order[k]]<=proj[order[k+1]]+1e-6 for k in range(26)),'start order follows the projection along %s'%(vec,)
    first=started_at(4);r=np.linalg.norm(P[:,[0,2]]-0.5*(P[:,[0,2]].min(axis=0)+P[:,[0,2]].max(axis=0)),axis=1);assert first[13]<=first[0] and all(first[i]>=first[13] for i in range(27)),'Outward: the centre starts first'
    first=started_at(5);assert [first[i] for i in range(27)]==sorted(first[i] for i in range(27)),'By Point Order follows the ids'

def easing_and_styles():
    st,n,a=scene(**LINE,base_scale=1.0,grow_on=1,grow_start=10,grow_sweep=0,grow_time=20)
    plain=at(a,1000)['scales']
    for kind in range(4):
        setv(a,grow_ease=kind)
        for frame in (10.0,12.0,15.0,17.5,20.0,25.0,29.0,30.0):
            x=(frame-10)/20;d=at(a,frame)['scales'];want=max(ease_ref(kind,x),1e-5) if x<1 else 1.0;assert np.allclose(d[:,0],plain[:,0]*want,rtol=2e-4,atol=1e-9),(kind,frame,d[0,0],want)
    assert max(ease_ref(2,x/100) for x in range(101))>1.05,'overshoot really overshoots'
    setv(a,grow_ease=1,grow_style=1)
    for frame in (10,14,20,25,30):
        f=(frame-10)/20;d=at(a,frame)['scales'];h=ease_ref(1,min(f/0.7,1)) if f<0.7 else 1.0;w=ease_ref(1,min(max((f-0.2)/0.8,0),1)) if f<1 else 1.0
        base=plain[0];assert np.allclose(d[0],[base[0]*max(w,1e-5),base[1]*max(h,1e-5),base[2]*max(w,1e-5)],rtol=2e-4,atol=1e-9),(frame,d[0],h,w)
    done=at(a,30);assert np.array_equal(done['scales'],plain),'Plant ends exactly at the normal scales'
    setv(a,grow_style=2,grow_rise=1.5,grow_ease=0);p0=at(a,1000)['pos']
    for frame in (10,13,16,20,26,30):
        f=(frame-10)/20;d=at(a,frame);e=f if f<1 else 1.0;assert np.allclose(d['pos'][:,1],p0[:,1]-(1-e)*1.5,atol=2e-5),(frame,d['pos'][0,1],p0[0,1]-(1-e)*1.5)
        assert np.allclose(d['pos'][:,[0,2]],p0[:,[0,2]],atol=1e-5);sf=ease_ref(1,min(f/0.3,1)) if f<0.3 else 1.0;assert np.allclose(d['scales'][:,0],plain[:,0]*max(sf,1e-5),rtol=2e-4,atol=1e-9),(frame,d['scales'][0,0],sf)
    assert np.array_equal(at(a,30)['pos'],p0),'Rise ends exactly at the normal positions'

def random_delay_and_stability():
    st,n,a=scene(mode=1,area_count=200,area_sizex=8,area_sizez=8,grow_on=1,grow_start=0,grow_sweep=30,grow_time=10,grow_ease=0,grow_delay=0.5,grow_seed=5)
    plain=at(a,1000)['scales'][:,0]
    pos=at(a,1000)['pos'];proj=pos[:,0];u=(proj-proj.min())/(proj.max()-proj.min());ids=list(range(200))
    for frame in (5,20,35,50,59):
        d=at(a,frame);f=np.array([min(1.0,max(0.0,(frame-(u[i]*30+ref_hash(i,5,31)*0.5*40))/10)) for i in ids]);want=np.where(f>=1,plain,plain*np.maximum(f,1e-5))
        assert np.allclose(d['scales'][:,0],want,rtol=2e-4,atol=1e-9),frame
        assert d['invisible']==[i for i in ids if f[i]<=0]
    setv(a,grow_seed=6);d6=at(a,35);setv(a,grow_seed=5);d5=at(a,35);assert not np.allclose(d6['scales'],d5['scales']),'the delay seed changes the pattern'

def combinations_and_guide():
    st,n,a=scene(mode=1,area_count=60,area_sizex=6,area_sizez=6,phys_on=1,phys_duration=6)
    res=a.hdaModule().bake(a);settled=at(a,1);setv(a,grow_on=1,grow_start=5,grow_sweep=30,grow_time=10,grow_style=2,grow_rise=1.0,grow_ease=0)
    done=at(a,100);assert np.array_equal(done['pos'],settled['pos']) and np.array_equal(done['scales'],settled['scales']),'a finished Grow equals the cached settled result'
    mid=at(a,20);assert not np.allclose(mid['pos'][:,1],settled['pos'][:,1]) and a.stage().GetPrimAtPath('/World/Arraytron').GetCustomDataByKey('arraytron:physics')['state']=='settled','the cache is used, not simulated again'
    early=at(a,5);assert len(early['invisible'])==60,'before the first start everything is hidden'
    # the order comes from the final positions: it does not change from frame to frame even though Rise moves the points
    seen=[];[seen.append(set(at(a,f)['invisible'])) for f in range(5,45,3)];assert all(seen[k+1]<=seen[k] for k in range(len(seen)-1)),'instances only ever appear, never disappear again'
    setv(a,phys_on=0,mask_source=1,mask_noise_freq=0.4,overlap_mode=1);d=at(a,12);assert len(d['ids'])<60 and set(d['invisible'])<=set(d['ids']),'with a mask and No Overlap the ids are the survivors'
    # guide: an arrow along the sweep; none for Outward / By Point Order
    setv(a,mask_source=0,overlap_mode=0,grow_style=0,grow_direction=0);s=at(a,12)['stage'];g='/World/Arraytron/Bounds_Guide/Grow'
    prim=s.GetPrimAtPath(g);assert prim,'sweep arrow';pts=np.array(UsdGeom.BasisCurves(prim).GetPointsAttr().Get(),float)
    xs=at(a,12)['pos'][:,0];assert abs(pts[0][0]-xs.min())<1e-3 and abs(pts[1][0]-xs.max())<1e-3 and pts[1][0]>pts[0][0],'the arrow runs from the first to the last instance'
    setv(a,grow_reverse=1);pts=np.array(UsdGeom.BasisCurves(at(a,12)['stage'].GetPrimAtPath(g)).GetPointsAttr().Get(),float);assert pts[0][0]>pts[1][0],'Reverse flips the arrow'
    setv(a,grow_reverse=0,grow_direction=4);assert not at(a,12)['stage'].GetPrimAtPath(g)
    setv(a,grow_direction=0,grow_on=0);assert not at(a,12)['stage'].GetPrimAtPath(g) and at(a,12)['invisible'] in (None,[]),'off: no arrow, no hidden instances'

check('Six tabs: order, contents, no parameter lost or renamed, defaults and menus identical to the previous release, collapsible details, handle binding',ui_tabs)
check('Animate tab: defaults, menus, conditionals, hidden frame expression, timing read-out, network order',ui_animate)
check('Grow off: every output array equals the previous release at any frame',off_unchanged)
check('Grow timing is exact: per-frame scales and invisibleIds, Reverse, Sweep 0, negative start, scrub order, exact end state',timing_exact)
check('Sweep directions: X, Y, Z, custom vector, outward from centre and point order follow the projection',directions)
check('Easing curves and the Plant and Rise styles against independent formulas, exact end states',easing_and_styles)
check('Random delay: deterministic by id, seed, exact against an independent hash',random_delay_and_stability)
check('Grow with Physics Settle, mask and No Overlap; instances only ever appear; the sweep guide arrow',combinations_and_guide)
out=ROOT/'tests'/('validation_grow_%s.json'%versions.tag(VID))
out.write_text(json.dumps({'houdini':hou.applicationVersionString(),'hda':TYPE,'checks':checks,'passed':True},indent=2))
shutil.rmtree(WORK,ignore_errors=True)
print('ALL PASSED',len(checks))
