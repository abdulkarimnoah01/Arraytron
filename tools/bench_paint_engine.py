"""Paint Engine benchmark (Paint Engine 2.0): the paint tools of Arraytron and Arraytron Stamp driven through a stand-in viewport (the real viewer-state code of the HDA,
a viewport that looks straight down), on a terrain of 80 000 triangles with 1 000 / 10 000 / 50 000 / 100 000 instances already there.
  hython tools/bench_paint_engine.py arraytron <hda> <type> [sizes] [out.json]
  hython tools/bench_paint_engine.py stamp <hda> <type> [sizes] [out.json]
Times are taken without tracemalloc (the memory is a separate stroke). Measures per size: entering the tool, cursor hover, a Paint stroke (per mouse event, the release = the commit), Erase, the editing brushes the version has (Relax, Grow / Shrink, Push),
the LOP cook after the stroke, Undo / Redo of the stroke, Save / Reopen, and the Python peak memory of a stroke (tracemalloc). Milliseconds. Not measured: the GPU drawing of a real viewer."""
import sys, os, time, json, types, tempfile, tracemalloc, traceback
import numpy as np
import hou
TOOL=sys.argv[1];HDA=sys.argv[2];TYPE=sys.argv[3]
SIZES=[int(x) for x in sys.argv[4].split(',')] if len(sys.argv)>4 else [1000,10000,50000,100000]
OUT=sys.argv[5] if len(sys.argv)>5 else None
os.environ.pop('ARRAYTRON_STAMP',None)
hou.hda.installFile(HDA,force_use_assets=True)
TERRAIN='''from pxr import UsdGeom, Vt, Gf
import numpy as np
stage=hou.pwd().editableStage();UsdGeom.Xform.Define(stage,'/World');n=200;s=100.0
x=np.linspace(-s/2,s/2,n+1);X,Z=np.meshgrid(x,x);Y=1.5*np.sin(X*0.15)*np.cos(Z*0.12)
P=np.stack([X.ravel(),Y.ravel(),Z.ravel()],1);i=np.arange(n);I,J=np.meshgrid(i,i);a=(J*(n+1)+I).ravel()
idx=np.stack([a,a+n+1,a+n+2,a+1],1).ravel()
c=UsdGeom.Cube.Define(stage,'/World/Props/Crate');c.CreateSizeAttr(0.5)                     # the prototype of Arraytron's default bank row
m=UsdGeom.Mesh.Define(stage,'/World/Terrain');m.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(P.astype(np.float32)));m.CreateFaceVertexCountsAttr(Vt.IntArray([4]*(n*n)));m.CreateFaceVertexIndicesAttr(Vt.IntArray.FromNumpy(idx.astype(np.int32)))
'''
def height(x,z):return 1.5*np.sin(x*0.15)*np.cos(z*0.12)

class StubDrawable(object):
    def __init__(self,*a,**k):self.geo=None;self.shown=False
    def setParams(self,p):pass
    def setGeometry(self,g):self.geo=g
    def setTransform(self,x):pass
    def show(self,v):self.shown=v
    def draw(self,h,p=None):pass
class Fwd(object):
    """hou with the drawables replaced (the stand-in viewer draws nothing)."""
    GeometryDrawable=StubDrawable;TextDrawable=StubDrawable
    def __getattr__(self,k):return getattr(hou,k)
class VP(object):
    def mapToScreen(self,p):return (p[0]*10.0,p[2]*10.0)
    def mapToWorld(self,x,y):return hou.Vector3((0,-1,0)),hou.Vector3((x/10.0,50.0,y/10.0))
    def draw(self):pass
class Viewer(object):
    def __init__(self):self.groups=[];self.prompt=None
    def setPromptMessage(self,m,t=None):self.prompt=m
    def clearPromptMessage(self):self.prompt=None
    def curViewport(self):return VP()
    def hudInfo(self,*a,**k):pass
    def showHandle(self,*a):pass
    def displayRadialMenu(self,*a):pass
    def beginStateUndo(self,label):g=hou.undos.group(label);g.__enter__();self.groups.append(g)
    def endStateUndo(self):
        if self.groups:self.groups.pop().__exit__(None,None,None)
class Dev(object):
    def __init__(self,x,y,left=False,ctrl=False,shift=False,key='',wheel=0):self.x,self.y,self.left,self.ctrl,self.shift,self.key,self.wheel=x,y,left,ctrl,shift,key,wheel
    def mouseX(self):return self.x
    def mouseY(self):return self.y
    def isLeftButton(self):return self.left
    def isCtrlKey(self):return self.ctrl
    def isShiftKey(self):return self.shift
    def isMiddleButton(self):return False
    def isAltKey(self):return False
    def isKeyDown(self):return False
    def keyString(self):return self.key
    def mouseWheel(self):return self.wheel
class Ev(object):
    def __init__(self,d,r):self.d,self.r=d,r
    def device(self):return self.d
    def reason(self):return self.r
    def curViewport(self):return VP()
    def ray(self):return hou.Vector3((self.d.x/10.0,50.0,self.d.y/10.0)),hou.Vector3((0,-1,0))

def stats(ts):
    a=np.array(ts)*1000.0;return {'mean':round(float(a.mean()),3),'p95':round(float(np.percentile(a,95)),3),'max':round(float(a.max()),3),'n':len(a)} if len(a) else None

stage=hou.node('/stage');terrain=stage.createNode('pythonscript','terrain');terrain.parm('python').set(TERRAIN)
code=None;report={'tool':TOOL,'type':TYPE,'houdini':hou.applicationVersionString(),'sizes':{}}
rng=np.random.RandomState(1)

def populate(node,n):
    """n instances spread over 80 x 80 of the terrain."""
    x=rng.rand(n)*80-40;z=rng.rand(n)*80-40;y=height(x,z)
    if TOOL=='arraytron':
        m=node.hdaModule();pts=np.column_stack([x,y,z,np.zeros(n),np.ones(n),np.zeros(n),np.arange(n)])
        node.parm('paint_data').set(m.paint_encode({'pts':pts,'dab':0,'next':n,'strokes':[]}))
    else:
        lines=['%.4f %.4f %.4f  0 %.2f 0  1 1 1  1 1 0'%(a,b,c,r) for a,b,c,r in zip(x,y,z,rng.rand(n)*360)];node.parm('stamps').set('\n'.join(lines))

def count(node):
    if TOOL=='arraytron':return len(node.hdaModule().paint_decode(node.evalParm('paint_data'))['pts'])
    return node.hdaModule().stamp_count(node.evalParm('stamps'))

def make(n):
    if TOOL=='arraytron':
        a=stage.createNode(TYPE,'bench%d'%n);a.setInput(0,terrain);a.parm('mode').set(6);a.parm('paint_prim').set('/World/Terrain')
        for k,v in (('paint_radius',2.0),('paint_density',3.0),('paint_spacing',0.3),('paint_strength',1.0)):a.parm(k).set(v)
        for k,v in (('paint_preset',1),):
            if a.parm(k) is not None:a.parm(k).set(v);a.hdaModule().paint_preset(a) if hasattr(a.hdaModule(),'paint_preset') else None
        if a.parm('copy_test_ground') is not None:a.parm('copy_test_ground').set(0)
    else:
        a=stage.createNode(TYPE,'bench%d'%n);a.setInput(0,terrain);a.parm('target').set('/World/Terrain');a.parm('brush').set(2);a.parm('onstamps').set(0)
        for k,v in (('paint_radius',2.0),('paint_density',3.0),('paint_spacing',0.3)):a.parm(k).set(v)
        a.hdaModule().stamp_paint_preset(a,'soft')
    populate(a,n)
    if a.node('SOURCE_RESOLVER') is not None:a.node('SOURCE_RESOLVER').stage()                      # Arraytron reads the Paint Target from the Source Resolver's stage
    return a

def state_for(node):
    src=node.type().definition().sections()['ViewerStateModule'].contents().replace('import hou'+chr(10),'',1);glob={'hou':Fwd(),'np':np,'__name__':'bench_state'};exec(compile(src,'state','exec'),glob)
    glob['STRICT']=True;cls=glob['PaintState'] if TOOL=='arraytron' else glob['StampState'];v=Viewer();return cls('bench',v),v,glob

R=hou.uiEventReason
def stroke(state,pts,**mods):
    ts=[];x,y=pts[0];t0=time.perf_counter();state.onMouseEvent({'ui_event':Ev(Dev(x,y,left=True,**mods),R.Start)});ts.append(time.perf_counter()-t0)
    for x,y in pts[1:]:
        t0=time.perf_counter();state.onMouseEvent({'ui_event':Ev(Dev(x,y,left=True,**mods),R.Active)});ts.append(time.perf_counter()-t0)
    t0=time.perf_counter();state.onMouseEvent({'ui_event':Ev(Dev(x,y,left=False,**mods),R.Changed)});commit=time.perf_counter()-t0
    return ts,commit

def set_brush(node,name):
    """The brush of a version that has it (2.0: paint_op / brush menus), else None."""
    m=node.hdaModule()
    if hasattr(m,'brush_select'):return m.brush_select(node,name)
    if name=='paint':return True
    if TOOL=='arraytron' and name=='erase':node.parm('paint_op').set(1);return True
    if TOOL=='arraytron' and name=='relax':node.parm('paint_op').set(3);return True
    return None

for n in SIZES:
    res={};node=make(n);t0=time.perf_counter();node.stage();res['cook_initial_ms']=round((time.perf_counter()-t0)*1000,2)
    try:
        state,viewer,glob=state_for(node);t0=time.perf_counter();state.onEnter({'node':node})
        if TOOL=='arraytron':state.onMouseEvent({'ui_event':Ev(Dev(0,0),R.Located)})
        res['enter_ms']=round((time.perf_counter()-t0)*1000,2)
        hov=[]
        for k in range(120):
            x=-200+k*3.3;y=-50+k*0.8;t0=time.perf_counter();state.onMouseEvent({'ui_event':Ev(Dev(x,y),R.Located)});hov.append(time.perf_counter()-t0)
        res['hover']=stats(hov)
        path=[(-200+k*2.0,-50+k*0.5) for k in range(201)]
        for brush,mods in (('paint',{}),('erase',{}),('relax',{}),('scale',{}),('push',{}),('paint_ctrl',{'ctrl':True})):
            if brush=='paint_ctrl':
                if set_brush(node,'paint') is None:continue
            elif set_brush(node,brush) is None:continue
            before=count(node);ts,commit=stroke(state,path,**mods);peak=0                    # timed without tracemalloc (it slows Python allocations several times); the memory is measured on a second stroke below
            after=count(node);t0=time.perf_counter();node.stage();cook=time.perf_counter()-t0
            entry={'event':stats(ts),'commit_ms':round(commit*1000,2),'cook_ms':round(cook*1000,2),'count_before':before,'count_after':after,'peak_mb':round(peak/1e6,2)}
            t0=time.perf_counter();hou.undos.performUndo();entry['undo_ms']=round((time.perf_counter()-t0)*1000,2);entry['undo_restores']=count(node)==before
            t0=time.perf_counter();hou.undos.performRedo();entry['redo_ms']=round((time.perf_counter()-t0)*1000,2);entry['redo_reapplies']=count(node)==after
            if brush=='paint':                                                                  # the Python peak memory of the same stroke, measured apart and taken back
                tracemalloc.start();stroke(state,path,**mods);cur,peak=tracemalloc.get_traced_memory();tracemalloc.stop();entry['peak_mb']=round(peak/1e6,2);hou.undos.performUndo()
            res[brush]=entry
        set_brush(node,'paint')
    except Exception as exc:
        res['error']=traceback.format_exc()[-1500:]
    tmp=os.path.join(tempfile.mkdtemp(),'bench.hip');t0=time.perf_counter();hou.hipFile.save(tmp);res['save_ms']=round((time.perf_counter()-t0)*1000,2);keep=count(node)
    t0=time.perf_counter();hou.hipFile.load(tmp,suppress_save_prompt=True);node=hou.node('/stage/bench%d'%n);node.stage();res['reopen_cook_ms']=round((time.perf_counter()-t0)*1000,2);res['reopen_same_count']=count(node)==keep
    stage=hou.node('/stage');terrain=hou.node('/stage/terrain')
    report['sizes'][str(n)]=res;print(json.dumps({str(n):res}),flush=True)
    node.destroy()
if OUT:
    with open(OUT,'w') as f:json.dump(report,f,indent=1)
