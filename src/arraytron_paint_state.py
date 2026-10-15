# Arraytron Paint: the Python Viewer State of arraytron::instancer (v0.6.0, shortcuts v1.6.0). Stored in the HDA as the ViewerStateModule section.
# It only does the interaction: mouse ray -> hit on the Paint Target -> brush_add / brush_remove / brush_replace / brush_relax (src/arraytron_paint.py, tested
# without a viewport) -> the hidden parm paint_data. Shortcuts (the prompt line shows the live values):
#   mouse   LMB paint | Ctrl+LMB erase | Shift+LMB relax | Ctrl+Shift+LMB drag left / right: brush radius
#           wheel: Shift = radius, Ctrl = strength, Ctrl+Shift = density          (Alt and the middle mouse button always navigate the camera)
#   keys    [ ] radius | - = strength | , . density | 1 2 3 4 Add Remove Replace Relax | F falloff | H help line | Esc / Enter leave
import hou
import numpy as np

STATE_NAME='arraytron_paint'
CIRCLE_POINTS=48
STRICT=False                                                                   # the tests set it: errors are raised instead of being shown in the viewer
KINDS=('add','remove','replace','relax');KIND_NAMES=('Add','Remove','Replace','Relax');FALLOFFS=('Linear','Smooth','Gaussian','Hard')
KIND_COLORS={'add':(1.0,0.65,0.1,1.0),'remove':(1.0,0.2,0.2,1.0),'replace':(0.3,0.6,1.0,1.0),'relax':(0.3,0.9,0.4,1.0)}
HELP=('LMB paint  |  Ctrl+LMB erase  |  Shift+LMB relax  |  Ctrl+Shift+LMB drag: radius  |  wheel + Shift: radius, + Ctrl: strength, + Ctrl+Shift: density  |  '
      '[ ] radius  |  - = strength  |  , . density  |  1 2 3 4: Add Remove Replace Relax  |  F falloff  |  H hide this help  |  Esc / Enter: finish')
import traceback
def guarded(func):
    """A callback that never breaks the viewer: an error is printed to the Houdini console and shown in the viewport prompt (tests re-raise it)."""
    def run(self,kwargs):
        try:return func(self,kwargs)
        except Exception as exc:
            if STRICT:raise
            traceback.print_exc()
            try:self.scene_viewer.setPromptMessage('Arraytron Paint error: %s'%exc,hou.promptMessageType.Error)
            except Exception:pass
            return False
    run.__name__=func.__name__;return run

class PaintState(object):
    def __init__(self,state_name,scene_viewer):
        self.state_name=state_name;self.scene_viewer=scene_viewer
        self.node=None;self.data=None;self.surface=None;self.hit=None;self.painting=False;self.removing=False;self.kind='add';self.dirty=False
        self.resizing=None;self.hover_kind='add';self.show_help=True
        self.brush=hou.GeometryDrawable(scene_viewer,hou.drawableGeometryType.Line,'arraytron_brush')
        self.core=hou.GeometryDrawable(scene_viewer,hou.drawableGeometryType.Line,'arraytron_brush_core')
        self.preview=hou.GeometryDrawable(scene_viewer,hou.drawableGeometryType.Point,'arraytron_paint_points')
        self.brush.setParams({'color1':hou.Vector4(KIND_COLORS['add']),'line_width':2.0})
        self.core.setParams({'color1':hou.Vector4((1.0,1.0,1.0,0.6)),'line_width':1.0})
        self.preview.setParams({'color1':hou.Vector4((0.2,0.9,0.4,1.0)),'radius':4.0})

    # ----- helpers
    def _m(self):return self.node.hdaModule()
    def _radius(self):return max(self.node.evalParm('paint_radius'),1e-4)
    def _set(self,name,value,lo,hi):
        """Set a node parameter, kept inside its range."""
        self.node.parm(name).set(min(max(value,lo),hi))
    def _kind_for(self,dev):
        """The operation of a stroke: the Operation menu, Ctrl inverts it (erase, or paint when the menu says Remove), Shift relaxes (or paints when the menu says Relax)."""
        op=min(self.node.evalParm('paint_op'),3)
        if dev.isCtrlKey() and not dev.isShiftKey():return 'add' if op==1 else 'remove'
        if dev.isShiftKey() and not dev.isCtrlKey():return 'add' if op==3 else 'relax'
        return KINDS[op]
    def _load(self):
        m=self._m();self.data=m.paint_decode(self.node.evalParm('paint_data'))
        try:self.surface=m.paint_surface(self.node)
        except hou.Error as exc:
            self.surface=None;self.scene_viewer.setPromptMessage('Arraytron Paint: %s'%exc,hou.promptMessageType.Error)
        self._draw_points()
    def _draw_points(self):
        geo=hou.Geometry()
        if self.data is not None and len(self.data['pts']):
            geo.createPoints([tuple(p) for p in self.data['pts'][:,:3].tolist()])
        self.preview.setGeometry(geo);self.preview.show(True)
    def _ring(self,pos,nrm,radius):
        geo=hou.Geometry();u,v=self._m().tangent_frame(nrm)
        pts=geo.createPoints([tuple((np.asarray(pos)+nrm*0.01+radius*(np.cos(a)*u+np.sin(a)*v)).tolist()) for a in np.linspace(0,2*np.pi,CIRCLE_POINTS,endpoint=False)])
        poly=geo.createPolygon(is_closed=False)
        for p in pts:poly.addVertex(p)
        poly.addVertex(pts[0]);return geo
    def _draw_brush(self):
        """The outer ring is the radius (its colour is the operation: orange Add, red Remove, blue Replace, green Relax); the white inner ring is the strength."""
        if self.hit is None:self.brush.show(False);self.core.show(False);return
        pos,nrm=self.hit;r=self._radius();kind=self.kind if self.painting else self.hover_kind
        self.brush.setParams({'color1':hou.Vector4(KIND_COLORS[kind]),'line_width':2.0});self.brush.setGeometry(self._ring(pos,nrm,r));self.brush.show(True)
        strength=min(max(self.node.evalParm('paint_strength'),0.0),1.0)
        if 0.02<strength<0.99:self.core.setGeometry(self._ring(pos,nrm,r*strength));self.core.show(True)
        else:self.core.show(False)
    def _pick(self,ui_event):
        try:origin,direction=ui_event.ray()                                                      # the mouse ray, as Houdini's own states take it
        except Exception:
            dev=ui_event.device();origin,direction=ui_event.curViewport().mapToWorld(dev.mouseX(),dev.mouseY())
        if self.surface is None:self.hit=None;return
        m=self._m();P,T,area,normals,vn=self.surface
        t,j=m.ray_triangles(np.array(origin),np.array(direction),P,T)
        if j[0]<0:self.hit=None;return
        point=np.array(origin)+np.array(direction)*t[0];n=normals[j[0]]
        if np.dot(n,np.array(direction))>0:n=-n
        self.hit=(point,n)
    def _dab(self,kind):
        """kind: 'add', 'remove', 'replace' or 'relax'."""
        m=self._m();node=self.node;pos,nrm=self.hit;r=self._radius();seed=node.evalParm('paint_seed');fall=node.evalParm('paint_falloff');strength=node.evalParm('paint_strength');spacing=node.evalParm('paint_spacing');density=node.evalParm('paint_density')
        if kind=='remove':self.data,count=m.brush_remove(self.data,pos,r,fall,strength,seed)
        elif kind=='relax':self.data,count=m.brush_relax(self.data,pos,r,fall,strength,spacing,m.make_projector(self.surface,pos,r*1.5,True))
        elif kind=='replace':
            self.data,added,removed=m.brush_replace(self.data,pos,nrm,r,density,spacing,fall,strength,seed,m.make_projector(self.surface,pos,r,True));count=added+removed
        else:self.data,count=m.brush_add(self.data,pos,nrm,r,density,spacing,fall,strength,seed,m.make_projector(self.surface,pos,r,True))
        if count:self.dirty=True;self._draw_points()
    def _commit(self):
        if self.dirty:
            self._m().paint_apply(self.node,self.data);self.dirty=False
    def status(self):
        """The prompt line: the live brush values (and the shortcuts until H hides them)."""
        n=self.node;line='Arraytron Paint [%s]  radius %.3g  strength %.2f  density %.3g  falloff %s  |  %d points'%(KIND_NAMES[min(n.evalParm('paint_op'),3)],n.evalParm('paint_radius'),n.evalParm('paint_strength'),n.evalParm('paint_density'),FALLOFFS[min(n.evalParm('paint_falloff'),3)],0 if self.data is None else len(self.data['pts']))
        return line+('\n'+HELP if self.show_help else '')
    def _prompt(self):
        self.scene_viewer.setPromptMessage(self.status())

    # ----- state callbacks
    @guarded
    def onEnter(self,kwargs):
        self.node=kwargs['node']
        if self.node.evalParm('mode')!=6:self.node.parm('mode').set(6)
        self._load();self._prompt()
    @guarded
    def onResume(self,kwargs):
        self._load();self._prompt()
    @guarded
    def onInterrupt(self,kwargs):
        self._commit();self.brush.show(False);self.core.show(False);self.preview.show(False)
    @guarded
    def onExit(self,kwargs):
        self._commit();self.brush.show(False);self.core.show(False);self.preview.show(False);self.scene_viewer.clearPromptMessage()
    @guarded
    def onMouseEvent(self,kwargs):
        ev=kwargs['ui_event'];dev=ev.device();reason=ev.reason()
        if dev.isMiddleButton() or dev.isAltKey():return False                        # let the camera handle navigation
        self._pick(ev)
        if self.resizing is not None:                                                  # Ctrl+Shift+LMB drag: the radius follows the mouse sideways (about 150 pixels per doubling)
            if reason==hou.uiEventReason.Changed:self.resizing=None
            else:
                x0,r0=self.resizing;self._set('paint_radius',r0*2.0**((dev.mouseX()-x0)/150.0),0.01,100.0)
            self._prompt();self._draw_brush();return True
        if reason==hou.uiEventReason.Start and dev.isLeftButton() and dev.isCtrlKey() and dev.isShiftKey():
            self.resizing=(dev.mouseX(),self.node.evalParm('paint_radius'));self._draw_brush();return True
        self.hover_kind=self._kind_for(dev)
        if reason==hou.uiEventReason.Picked and dev.isLeftButton() and self.hit is not None:                          # a plain click: one dab
            self.kind=self.hover_kind;self.removing=self.kind=='remove'
            if self.data is None:self._load()
            self._dab(self.kind);self._commit();self._prompt()
        elif reason==hou.uiEventReason.Start and dev.isLeftButton() and self.hit is not None:
            self.painting=True;self.kind=self.hover_kind;self.removing=self.kind=='remove'
            if self.data is None:self._load()
            self._dab(self.kind)
        elif reason==hou.uiEventReason.Active and self.painting and self.hit is not None:
            self._dab(self.kind)
        elif reason==hou.uiEventReason.Changed and self.painting:
            self.painting=False;self._commit();self._prompt()
        self._draw_brush();return True
    @guarded
    def onMouseWheelEvent(self,kwargs):
        """Shift + wheel: radius; Ctrl + wheel: strength; Ctrl + Shift + wheel: density (anything else scrolls / zooms the camera as usual)."""
        dev=kwargs['ui_event'].device();step=dev.mouseWheel();sign=1 if step>0 else -1 if step<0 else 0
        if sign==0 or dev.isAltKey():return False
        if dev.isShiftKey() and dev.isCtrlKey():self._set('paint_density',self.node.evalParm('paint_density')*1.15**sign,0.0,1000.0)
        elif dev.isShiftKey():self._set('paint_radius',self.node.evalParm('paint_radius')*1.1**sign,0.01,100.0)
        elif dev.isCtrlKey():self._set('paint_strength',self.node.evalParm('paint_strength')+0.05*sign,0.0,1.0)
        else:return False
        self._prompt();self._draw_brush();return True
    @guarded
    def onKeyEvent(self,kwargs):
        key=kwargs['ui_event'].device().keyString();n=self.node
        if key in ('[',']'):self._set('paint_radius',n.evalParm('paint_radius')*(1.1 if key==']' else 1/1.1),0.01,100.0)
        elif key in ('-','_'):self._set('paint_strength',n.evalParm('paint_strength')-0.05,0.0,1.0)
        elif key in ('=','+'):self._set('paint_strength',n.evalParm('paint_strength')+0.05,0.0,1.0)
        elif key==',':self._set('paint_density',n.evalParm('paint_density')/1.15,0.0,1000.0)
        elif key=='.':self._set('paint_density',n.evalParm('paint_density')*1.15,0.0,1000.0)
        elif key in ('1','2','3','4'):n.parm('paint_op').set(int(key)-1)
        elif key in ('f','F'):n.parm('paint_falloff').set((n.evalParm('paint_falloff')+1)%4)
        elif key in ('h','H'):self.show_help=not self.show_help
        else:return False
        self._prompt();self._draw_brush();return True
    @guarded
    def onDraw(self,kwargs):
        handle=kwargs['draw_handle'];self.preview.draw(handle);self.brush.draw(handle);self.core.draw(handle)

def createViewerStateTemplate():
    """Mandatory entry point: the state template for Solaris (LOP) nodes."""
    template=hou.ViewerStateTemplate(kwargs['type'].definition().sections()['DefaultState'].contents().strip(),'Arraytron Paint',hou.lopNodeTypeCategory())
    template.bindFactory(PaintState)
    template.bindIcon('MISC_paint')
    return template
