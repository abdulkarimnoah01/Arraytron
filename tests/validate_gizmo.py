"""v1.30.1 Show Gizmo: hython tests/validate_gizmo.py [version]
The Bounds Transform gizmo is not bound on the node any more (it was drawn whenever the node was selected, also while painting); the viewer state owns it: Show Gizmo (off by default) decides,
and it is hidden while a brush tool (Paint, Place, Mask Paint, Biome Paint, Pick) is active. showHandle is only called when the answer changes.
Env ARRAYTRON_MUTATE=gizmo_alwaysbreaks the state; the suite must FAIL."""
from pathlib import Path
import hou, os, sys, types
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import versions
VID=versions.resolve(sys.argv[1] if len(sys.argv)>1 else versions.CURRENT);TYPE=versions.type_name(VID);MUTATE=os.environ.get('ARRAYTRON_MUTATE')
hou.hda.installFile(str(versions.hda(VID)),force_use_assets=True)
stage=hou.node('/stage');a=stage.createNode(TYPE,'gizmo');checks=[]
def check(ok,note=''):
    checks.append(bool(ok))
    if not ok:print('FAIL #%d'%len(checks),note)
d=a.type().definition();dialog=d.sections()['DialogScript'].contents();code=d.sections()['ViewerStateModule'].contents()
check('bindhandle' not in dialog,'the node binding is gone')
check(a.parm('bound_gizmo') is not None and a.evalParm('bound_gizmo')==0 and a.parm('bound_gizmo').parmTemplate().type()==hou.parmTemplateType.Toggle)
check('GIZMO_HANDLE=True' in code and "bindHandleStatic('lopxform','Transformer'" in code)
check(all(a.parmTuple(n) is not None for n in ('bound_t','bound_r','bound_s','bound_p')))                       # the parameters themselves are unchanged
class StubDrawable(object):
    def __init__(self,*x,**k):self.shown=False
    def setParams(self,p):pass
    def setGeometry(self,g):pass
    def show(self,v):self.shown=v
class Viewer(object):
    def __init__(self):self.prompt=None;self.handle=[]
    def setPromptMessage(self,m,t=None):self.prompt=m
    def clearPromptMessage(self):self.prompt=None
    def showHandle(self,name,value):self.handle.append((name,value))
class Device(object):
    def __init__(self,x=0,y=0):self.x,self.y=x,y
    def isShiftKey(self):return False
    def mouseWheel(self):return 0
    def mouseX(self):return self.x
    def mouseY(self):return self.y
    def isLeftButton(self):return False
    def isCtrlKey(self):return False
    def isMiddleButton(self):return False
    def isAltKey(self):return False
    def keyString(self):return ''
class Event(object):
    def __init__(self,x=0,y=0):self.d=Device(x,y)
    def device(self):return self.d
    def reason(self):return hou.uiEventReason.Located
    def ray(self):return hou.Vector3((self.d.x/10.0,10.0,self.d.y/10.0)),hou.Vector3((0,-1,0))
ns=types.SimpleNamespace(**{k:getattr(hou,k) for k in ('Vector4','Vector3','Geometry','drawableGeometryType','uiEventReason','promptMessageType','Error','lopNodeTypeCategory','ViewerStateTemplate','undos')});ns.GeometryDrawable=StubDrawable
glob={'hou':ns,'np':np};exec(compile(code.replace('import hou'+chr(10),'',1),'arraytron_paint_state.py','exec'),glob);glob['STRICT']=True
if MUTATE=='gizmo_always':glob['PaintState']._active=lambda self:False                       # never hidden by a tool
viewer=Viewer();state=glob['PaintState']('arraytron_gizmo_test',viewer)
state.onEnter({'node':a});check(viewer.handle==[('Transformer',False)],viewer.handle)                            # Show Gizmo off: hidden
state.onMouseEvent({'ui_event':Event(1,1)});state.onMouseEvent({'ui_event':Event(2,2)});check(viewer.handle==[('Transformer',False)],'showHandle only when the answer changes')
a.parm('bound_gizmo').set(1);state.onMouseEvent({'ui_event':Event(3,3)});check(viewer.handle[-1]==('Transformer',True) and len(viewer.handle)==2,viewer.handle)             # on: shown (the mode is not a brush mode)
state.onMouseEvent({'ui_event':Event(4,4)});check(len(viewer.handle)==2)
a.setUserData('arraytron_place','1');state.onMouseEvent({'ui_event':Event(5,5)});check(state.placing and viewer.handle[-1]==('Transformer',False) and len(viewer.handle)==3,viewer.handle)   # a brush tool is active: hidden
state.onExit({'node':a});state.onEnter({'node':a});check(viewer.handle[-1][1] is True or viewer.handle[-1][1] is False)                                                              # re-entering decides again
a.parm('mode').set(6);state.onEnter({'node':a});check(viewer.handle[-1]==('Transformer',False),viewer.handle[-1])                                                                       # Paint mode: hidden
a.parm('mode').set(0);state.onResume({'node':a});check(viewer.handle[-1]==('Transformer',True),viewer.handle[-1])
class Bare(object):
    def __init__(self):self.prompt=None
    def setPromptMessage(self,m,t=None):self.prompt=m
    def clearPromptMessage(self):self.prompt=None
bare=glob['PaintState']('arraytron_gizmo_bare',Bare());bare.onEnter({'node':a});check(True)                      # a viewer without showHandle (the other suites' stand-in) is tolerated
ok=all(checks);print('ALL PASSED %d'%len(checks) if ok else 'FAILED',len(checks));sys.exit(0 if ok else 1)
