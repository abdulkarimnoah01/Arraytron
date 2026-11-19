# Arraytron Paint: the Python Viewer State of arraytron::instancer (v0.6.0, shortcuts v1.6.0, mask brush v1.26.0). Stored in the HDA as the ViewerStateModule section.
# It only does the interaction: mouse ray -> hit on the Paint Target -> brush_add / brush_remove / brush_replace / brush_relax (src/arraytron_paint.py, tested
# without a viewport) -> the hidden parm paint_data. Shortcuts (the prompt line shows the live values):
#   mouse   LMB paint | Ctrl+LMB erase | Shift+LMB relax | Ctrl+Shift+LMB drag left / right: brush radius
#           wheel: Shift = radius, Ctrl = strength, Ctrl+Shift = density          (Alt and the middle mouse button always navigate the camera)
#   Edit    (v1.35.0, the Select And Edit Instances button) click selects an instance (Shift adds or removes), a drag on nothing is a box select, the edit handle moves / rotates / scales the selection (override rows),
#           Del deletes it, A all, I invert, N none | Esc / Enter finish
#   keys    [ ] radius | - = strength | , . density | 1 2 3 4 Add Remove Replace Relax | F falloff | H help line | Esc / Enter leave
# Paint Engine 2.0 (v1.36.0, Brush Engine Continuous Stroke): BrushCore strokes (src/brushcore.py, shared with Arraytron Stamp): Paint is one ribbon with a density and a scale falloff, the same
#   at any mouse speed; 5-9 Grow / Shrink, Push / Attract, Swap Prototype, Orient / Comb, Clone; C the radial brush menu; H cycles the HUD panel (minimal, standard, expanded, hidden);
#   F the falloff preset; Esc during a stroke drops it; the stroke is written once, on release (one undo step). Classic Dabs keeps the v0.6.0 brush exactly.
import hou
import numpy as np

STATE_NAME='arraytron_paint'
CIRCLE_POINTS=48
STRICT=False                                                                   # the tests set it: errors are raised instead of being shown in the viewer
GIZMO_HANDLE=False                                                             # v1.30.1: the builder sets it; the state owns the Bounds Transform gizmo (Show Gizmo) instead of the node binding
GIZMO_BINDINGS=tuple((p+a,h+a) for p,h in (('bound_t','t'),('bound_r','r'),('bound_s','s'),('bound_p','p')) for a in 'xyz')
KINDS=('add','remove','replace','relax','scale','push','swap','orient','clone');KIND_NAMES=('Add','Remove','Replace','Relax','Grow / Shrink','Push / Attract','Swap Prototype','Orient / Comb','Clone');FALLOFFS=('Linear','Smooth','Gaussian','Hard')
PREVIEW_S=0.06                                                                 # Paint Engine 2.0: the points of a stroke are drawn again at most this often (a stroke over 100 000 points stays light)
KIND_COLORS={'add':(1.0,0.65,0.1,1.0),'remove':(1.0,0.2,0.2,1.0),'replace':(0.3,0.6,1.0,1.0),'relax':(0.3,0.9,0.4,1.0)}
MASK_OPS=('Paint','Erase','Add','Subtract','Smooth','Multiply','Maximum','Minimum','Paint Background','Sample Foreground','Sample Background');MASK_CURVES=('Linear','Smooth','Gaussian')
MASK_HEAVY=(4,5,6,7)                                                                        # the menu entries that are not applied live (they are full mask operations)
MASK_OPPOSITE={0:1,1:0,2:3,3:2,8:0}                                                         # what Ctrl does with the Opposite entry of its menu (anything else erases)
MASK_OP_COLORS=((0.3,1.0,0.4,1.0),(1.0,0.25,0.2,1.0),(1.0,0.65,0.1,1.0),(0.75,0.4,1.0,1.0),(0.2,0.9,0.9,1.0),(1.0,0.9,0.2,1.0),(1.0,1.0,1.0,1.0),(0.6,0.6,0.6,1.0),(0.1,0.5,0.2,1.0),(0.3,0.5,1.0,1.0),(0.3,0.5,1.0,1.0))
HELP=('LMB paint  |  Ctrl+LMB erase  |  Shift+LMB relax  |  Ctrl+Shift+LMB drag: radius  |  wheel + Shift: radius, + Ctrl: strength, + Ctrl+Shift: density  |  '
      '[ ] radius  |  - = strength  |  , . density  |  1 2 3 4: Add Remove Replace Relax  |  F falloff  |  H hide this help  |  Esc / Enter: finish')
import time
import traceback
EDIT_HANDLE_ZERO=('rpivotx','rpivoty','rpivotz','rprex','rprey','rprez','rpostx','rposty','rpostz','roffsetx','roffsety','roffsetz','spivotx','spivoty','spivotz','soffsetx','soffsety','soffsetz',
                  'pivot_comp_tx','pivot_comp_ty','pivot_comp_tz','pivot_comp_rx','pivot_comp_ry','pivot_comp_rz','tx','ty','tz','rx','ry','rz','shear_xy','shear_xz','shear_yz','pivot_rx','pivot_ry','pivot_rz')
EDIT_BOXES=2000;EDIT_LIVE_S=1.0/30.0;EDIT_EDGES=np.array(((0,1),(2,3),(4,5),(6,7),(0,2),(1,3),(4,6),(5,7),(0,4),(1,5),(2,6),(3,7)),dtype=np.int64);EDIT_TOKEN='edit_delete';EDIT_KEY='Del';EDIT_YELLOW=(1.0,0.85,0.2,1.0);EDIT_BLUE=(0.35,0.7,1.0,1.0);EDIT_GREY=(0.85,0.85,0.85,0.9)
def edit_hud_template(icon='MISC_paint'):
    """The HUD panel of the Edit tool: the hints once, the numbers when they change (the look of Arraytron Stamp's panel)."""
    return {'title':'Arraytron','desc':'Edit instances','icon':icon,'rows':[{'type':'divider','label':'Edit'},
        {'label':'Select (add or remove)','key':'LMB (Shift LMB)'},{'label':'Box select','key':'LMB drag'},{'label':'Move, rotate, scale the selection','key':'handle'},{'label':'Delete selection','key':EDIT_KEY},
        {'label':'Select all / invert / none','key':'A  I  N'},{'label':'Finish','key':'Esc'},
        {'type':'divider','label':'Instances'},{'id':'v_total','label':'Instances'},{'id':'v_sel','label':'Selected'},{'id':'v_rows','label':'Edited'}]}
def _vray(vp,x,y):
    """(origin, direction) of the ray through a viewport pixel (hou.GeometryViewport.mapToWorld returns direction first, then origin)."""
    d,o=vp.mapToWorld(x,y);return np.array(tuple(o),dtype=np.float64),np.array(tuple(d),dtype=np.float64)
def _hk_is(key,token):
    """True when a key event (a hotkey symbol or a key string) is the hotkey of Delete Selected (rebinding in the hotkey editor works)."""
    try:
        import viewerstate.utils as su
        match=bool(hou.hotkeys.isKeyMatch(key,su.hotkeyContextForState(STATE_NAME,hou.lopNodeTypeCategory())+'.'+token))
    except Exception:match=False
    return match or key in (EDIT_KEY,'Delete','BackSpace')
PAINT_HOTKEYS={'paint_brushmenu':('c','Brush Menu','Paint Engine 2.0: the radial menu of the paint brushes'),'paint_hints':('h','Cycle Hints','The HUD hints: minimal, standard, expanded, hidden')}
def _key_is(kwargs,key,token):
    """True when a key event is the state hotkey token (as bound in the Hotkey Editor) or its default key (no interface, or not registered)."""
    try:
        import viewerstate.utils as su
        sym=su.hotkeySymbolOrKeyString(kwargs)
        if sym and hou.hotkeys.isKeyMatch(sym,su.hotkeyContextForState(STATE_NAME,hou.lopNodeTypeCategory())+'.'+token):return True
    except Exception:pass
    return (key or '').lower()==PAINT_HOTKEYS[token][0]
def _drawable_on(d):
    """Whether a drawable is shown: hou.GeometryDrawable.visible() (it has no `shown`; the tests' stand-ins do)."""
    try:return bool(d.visible())
    except AttributeError:return bool(getattr(d,'shown',False))
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
        self.resizing=None;self.hover_kind='add';self.show_help=True;self.loaded=False;self.picking=False;self.inst=None;self.pick_hit=None;self.placing=False;self.place_surf=None;self.place_hit=None;self.place_last=(0.0,None);self.place_drag=None;self.stroke=[];self.stroke_radius=0.0
        self.engine=None;self.engine_next0=0;self.hover_ctrl=False;self.preview_t=0.0;self.prefs=None;self.phud_for=None
        self.editing=False;self.es=None;self.esnap=None;self.epress=None;self.edrag=None;self.ehandle=None;self.ewatch=None;self.etext=None;self.ehud=None;self.ehudkey=None;self.esel_n=0
        self.biomepaint=False;self.bsurf=None;self.bdata=None;self.bhit=None;self.bpainting=False;self.bdirty=False;self.bsign=1;self._biome_erase_hover=False
        self.maskpaint=False;self.msurf=None;self.mdata=None;self.mhit=None;self.mpainting=False;self.mdirty=False;self.mop=0;self.morig='';self.mlast=0.0;self.mlive=False;self.mwarn='';self.mresize=None;self.mhover=None;self.msampled=None;self.mlastdab=None     # v1.26.0: the mask brush
        self.erased=hou.GeometryDrawable(scene_viewer,hou.drawableGeometryType.Point,'arraytron_biome_erase');self.erased.setParams({'color1':hou.Vector4((1.0,0.25,0.2,1.0)),'radius':4.0})
        self.esel=hou.GeometryDrawable(scene_viewer,hou.drawableGeometryType.Line,'arraytron_edit_selected');self.esel.setParams({'color1':hou.Vector4(EDIT_YELLOW),'line_width':2.0})
        self.ehover=hou.GeometryDrawable(scene_viewer,hou.drawableGeometryType.Line,'arraytron_edit_hover');self.ehover.setParams({'color1':hou.Vector4(EDIT_GREY),'line_width':1.5})
        self.eframe=hou.GeometryDrawable(scene_viewer,hou.drawableGeometryType.Line,'arraytron_edit_rect');self.eframe.setParams({'color1':hou.Vector4(EDIT_BLUE),'line_width':1.5})
        self.brush=hou.GeometryDrawable(scene_viewer,hou.drawableGeometryType.Line,'arraytron_brush')
        self.core=hou.GeometryDrawable(scene_viewer,hou.drawableGeometryType.Line,'arraytron_brush_core')
        self.preview=hou.GeometryDrawable(scene_viewer,hou.drawableGeometryType.Point,'arraytron_paint_points')
        self.marker=hou.GeometryDrawable(scene_viewer,hou.drawableGeometryType.Line,'arraytron_pick_marker')
        self.marker.setParams({'color1':hou.Vector4((1.0,0.9,0.1,1.0)),'line_width':3.0})
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
        op=min(self.node.evalParm('paint_op'),len(KINDS)-1)
        if op>3:return KINDS[op]                                                       # the sculpt brushes of Paint Engine 2.0: Ctrl / Shift pick their variant (_variant)
        if dev.isCtrlKey() and not dev.isShiftKey():return 'add' if op==1 else 'remove'
        if dev.isShiftKey() and not dev.isCtrlKey():return 'add' if op==3 else 'relax'
        return KINDS[op]
    def _engine(self):return self.node is not None and hasattr(self._m(),'paint_engine_on') and self._m().paint_engine_on(self.node)
    def _variant(self,kind,dev):
        """The variant of an editing brush for the modifier keys (None: the brush's own parameter)."""
        ctrl=dev.isCtrlKey();shift=dev.isShiftKey()
        if kind=='remove':
            soft=bool(self.node.evalParm('erase_soft')) if self.node.parm('erase_soft') is not None else False;return 'soft' if (soft!=(shift and self.node.evalParm('paint_op')==1)) else 'hard'
        if kind=='scale':return 'shrink' if ctrl else 'smooth' if shift else None
        if kind=='push':return 'attract' if ctrl else 'drag' if shift else None
        if kind=='orient':return 'random' if ctrl else 'restore' if shift else None
        return None
    def _active(self):return self.node is not None and (self.editing or self.picking or self.placing or self.biomepaint or self.maskpaint or self.node.evalParm('mode')==6)
    def _ensure(self):
        """True while the node is in Paint mode. Selecting the node enters this tool by itself, so it never changes the Distribution Mode: with another mode it stays idle
        (nothing drawn, no prompt, every mouse / key event is left to Houdini) and wakes up when the mode becomes Paint (the Start Painting button sets it)."""
        if self.node is not None and not self.editing and self.node.userData('arraytron_edit'):                          # the Select And Edit Instances button asked for the Edit tool
            self.node.destroyUserData('arraytron_edit');self.editing=True;self.picking=False;self.placing=False;self.biomepaint=False;self.maskpaint=False;self.loaded=False;self.painting=False;self.resizing=None
        if self.editing and self.node is not None and any(self.node.userData(k) for k in ('arraytron_pick','arraytron_place','arraytron_biomepaint','arraytron_maskpaint')):self._edit_leave()
        if self.node is not None and not self.picking and self.node.userData('arraytron_pick'):             # the Pick Instance button asked for picking
            self.node.destroyUserData('arraytron_pick');self.picking=True;self.placing=False;self.biomepaint=False;self.maskpaint=False;self.loaded=False;self.painting=False;self.resizing=None
        if self.node is not None and not self.placing and self.node.userData('arraytron_place'):                          # the Place Instances button asked for placing
            self.node.destroyUserData('arraytron_place');self.placing=True;self.picking=False;self.biomepaint=False;self.maskpaint=False;self.loaded=False;self.painting=False;self.resizing=None
        if self.node is not None and not self.biomepaint and self.node.userData('arraytron_biomepaint'):                  # the Paint Biome Map button asked for biome painting
            self.node.destroyUserData('arraytron_biomepaint');self.biomepaint=True;self.picking=False;self.placing=False;self.maskpaint=False;self.loaded=False;self.painting=False;self.bpainting=False;self.resizing=None
        if self.node is not None and not self.maskpaint and self.node.userData('arraytron_maskpaint'):                    # the Paint Mask button asked for mask painting
            self.node.destroyUserData('arraytron_maskpaint');self.maskpaint=True;self.picking=False;self.placing=False;self.biomepaint=False;self.loaded=False;self.painting=False;self.mpainting=False;self.resizing=None
        if not self._active():
            if self.loaded:
                self._commit();self._mask_viz_restore();self.loaded=False;self.painting=False;self.bpainting=False;self.mpainting=False;self.resizing=None
                self.brush.show(False);self.core.show(False);self.preview.show(False);self.marker.show(False);self.erased.show(False);self._edit_hide();self.scene_viewer.clearPromptMessage()
            return False
        if not self.loaded:
            if self.maskpaint:self._mask_load()
            elif self.editing:self._edit_load()
            elif self.placing:
                self.place_hit=None;self.brush.show(False);self.core.show(False);self.preview.show(False)
                try:self.place_surf=self._m().place_surface(self.node)
                except hou.Error as exc:
                    self.place_surf=None;self.scene_viewer.setPromptMessage('Arraytron Place: %s'%exc,hou.promptMessageType.Error)
            elif self.biomepaint:self._biome_load()
            elif self.picking:
                self.inst=self._m().pick_instances(self.node);self.pick_hit=None;self.brush.show(False);self.core.show(False);self.preview.show(False)
            else:self._load()
            self.loaded=True;self._prompt()
        return True
    # ----- Edit mode (v1.35.0): select instances like Arraytron Stamp's Edit mode (boxes round the selection, a HUD panel), change them with Houdini's edit handle; every change is an override row
    def _edit_hide(self):
        for d in (self.esel,self.eframe,self.ehover):d.show(False)
        self._edit_handle(False);self._edit_watch(False);self.ehud=None
    def _edit_leave(self):
        self.editing=False;self.es=None;self.esnap=None;self.epress=None;self.edrag=None;self.loaded=False;self._edit_hide()
    def _edit_handle(self,show):
        if show!=self.ehandle:
            try:self.scene_viewer.showHandle('edit_handle',bool(show));self.ehandle=show
            except Exception:pass
    def _edit_watch(self,on):
        """While the Edit tool is on: a selection or override rows changed elsewhere (the buttons of the Finish tab, undo) are drawn at once."""
        if self.ewatch is not None:
            try:self.ewatch[0].removeEventCallback((hou.nodeEventType.ParmTupleChanged,),self.ewatch[1])
            except Exception:pass
            self.ewatch=None
        if not on or self.node is None:return
        def changed(**kw):
            pt=kw.get('parm_tuple')
            if self.edrag is not None or not self.editing or pt is None:return
            name=pt.name()
            try:
                if name=='edit_ids':self._edit_refresh();self.scene_viewer.curViewport().draw()
                elif name in ('edit_data','edit_on'):self._edit_load();self.scene_viewer.curViewport().draw()
            except Exception:pass
        try:self.node.addEventCallback((hou.nodeEventType.ParmTupleChanged,),changed);self.ewatch=(self.node,changed)
        except Exception:self.ewatch=None
    def _edit_load(self):
        """The instances as they are rendered (read from the node's stage once; again after an edit)."""
        self.es=None;self.esnap=None;self.epress=None;self.edrag=None;self.brush.show(False);self.core.show(False);self.preview.show(False);self.marker.show(False);self.erased.show(False)
        try:self.es=self._m().edit_display(self.node)
        except Exception as exc:self.scene_viewer.setPromptMessage('Arraytron Edit: %s'%exc,hou.promptMessageType.Error)
        self._edit_watch(True);self.ehud=None;self._edit_refresh()
    def _edit_selected(self):
        """Indices (into the display) of the selected instances."""
        if self.es is None:return np.zeros(0,dtype=np.int64)
        return np.nonzero(np.isin(self.es['ids'],self._m().edit_get_selection(self.node)))[0]
    def _edit_boxes(self,drawable,corners):
        """Draw boxes (corners (n, 8, 3) in the order of edit_corners) as lines, all at once."""
        if corners is None or not len(corners):drawable.show(False);return
        corners=corners[:EDIT_BOXES];geo=hou.Geometry();geo.createPoints([tuple(q) for q in corners.reshape(-1,3).tolist()]);geo.createPolygons((EDIT_EDGES[None]+8*np.arange(len(corners))[:,None,None]).reshape(-1,2).tolist(),False);drawable.setGeometry(geo);drawable.show(True)
    def _edit_refresh(self,corners=None):
        """The boxes of the selected instances (yellow) and the handle at their centre; corners: the boxes while the handle drags."""
        sel=self._edit_selected();self.etext=self.node.evalParm('edit_ids');self.esel_n=len(sel)
        if self.es is None or not len(sel):self.esel.show(False);self._edit_handle(False);self._edit_hud();return
        self._edit_boxes(self.esel,self._m().edit_corners(self.es,sel) if corners is None else corners);self._edit_handle(True)
        if corners is None:                                                                         # the handle is moved to the centre of the selection (a dynamic handle asks the state only when it is told to update)
            try:hou.Handle(self.scene_viewer,'edit_handle').update()
            except Exception:pass
        self._edit_hud()
    def _edit_hud(self):
        """The HUD panel (hints once, the numbers when they change), like the Edit mode of Arraytron Stamp."""
        if self.ehud is None:
            try:self.scene_viewer.hudInfo(template=edit_hud_template(self._icon()))
            except Exception:pass
            self.ehud={};self.ehudkey=None
        values={'v_total':'0' if self.es is None else str(len(self.es['ids'])),'v_sel':str(getattr(self,'esel_n',0)),'v_rows':str(len(self._m().edit_store(self.node)[0]))}
        if values!=self.ehudkey:
            self.ehudkey=values
            try:self.scene_viewer.hudInfo(values=values)
            except Exception:pass
    def _icon(self):
        try:return self.node.type().definition().icon() or 'MISC_paint'
        except Exception:return 'MISC_paint'
    def _edit_rect(self,ev,dev,p):
        """The box of a box select: a rectangle on the rays through its four corners, just past the near clipping plane."""
        vp=ev.curViewport()
        try:t=max(float(vp.defaultCamera().clipNear())*4.0,0.01)
        except Exception:t=0.1
        try:
            pts=[]
            for x,y in ((p['x'],p['y']),(dev.mouseX(),p['y']),(dev.mouseX(),dev.mouseY()),(p['x'],dev.mouseY()),(p['x'],p['y'])):
                o,d=_vray(vp,x,y);pts.append(o+d/np.linalg.norm(d)*t)
            geo=hou.Geometry();made=geo.createPoints([tuple(float(c) for c in q) for q in pts]);poly=geo.createPolygon(is_closed=False)
            for q in made:poly.addVertex(q)
            self.eframe.setGeometry(geo);self.eframe.show(True)
        except Exception:self.eframe.show(False)
    def _edit_mouse(self,ev,dev,reason):
        """Edit mode: click selects the instance under the mouse (Shift adds or removes), a drag on nothing is a box select; the edit handle changes the selection. While a box grows only its rectangle is drawn."""
        m=self._m();R=hou.uiEventReason;left=dev.isLeftButton()
        if self.es is None:return True
        if self.epress is not None and reason==R.Active:
            p=self.epress
            if abs(dev.mouseX()-p['x'])+abs(dev.mouseY()-p['y'])>=5:p['moved']=True
            if p['moved']:self.ehover.show(False);self._edit_rect(ev,dev,p)
            return True
        if self.node.evalParm('edit_ids')!=self.etext:self._edit_refresh()
        try:origin,direction=ev.ray()
        except Exception:origin,direction=_vray(ev.curViewport(),dev.mouseX(),dev.mouseY())
        under=m.edit_under(self.es,origin,direction) if reason!=R.Active else None
        if left and reason==R.Start:self.epress=dict(x=dev.mouseX(),y=dev.mouseY(),under=under,moved=False,shift=dev.isShiftKey())
        elif self.epress is not None and reason in (R.Changed,R.Picked):
            p=self.epress;self.epress=None;self.eframe.show(False);sel=[int(i) for i in m.edit_get_selection(self.node)]
            if p['moved']:
                vp=ev.curViewport();hit=self.es['ids'][m.edit_select_in_rays(self.es['pos'],[_vray(vp,x,y) for x,y in ((p['x'],p['y']),(dev.mouseX(),p['y']),(dev.mouseX(),dev.mouseY()),(p['x'],dev.mouseY()))])]
                new=sorted(set(sel)|{int(i) for i in hit}) if p['shift'] else sorted(int(i) for i in hit)
            elif p['under'] is not None:
                u=int(self.es['ids'][p['under']]);new=[i for i in sel if i!=u] if (p['shift'] and u in sel) else sorted(set(sel)|{u}) if p['shift'] else [u]
            else:new=sel if p['shift'] else []
            m.edit_set_selection(self.node,new);self._edit_refresh()
        if under is None or self.epress is not None:self.ehover.show(False)
        else:self._edit_boxes(self.ehover,m.edit_corners(self.es,[under]))
        return True
    def _edit_key(self,kwargs):
        try:import viewerstate.utils as su;key=su.hotkeySymbolOrKeyString(kwargs)
        except Exception:key=kwargs['ui_event'].device().keyString()
        n=self.node;m=self._m()
        if not key:return False
        if _hk_is(key,EDIT_TOKEN):
            ids=m.edit_get_selection(n)
            if len(ids):m.edit_delete_ids(n,ids)
            return True
        k=key.lower() if len(key)==1 else key
        if k=='a':m.edit_select_all(n)
        elif k=='i':m.edit_select_invert(n)
        elif k=='n':m.edit_select_none(n)
        else:return False
        return True
    @guarded
    def onStateToHandle(self,kwargs):
        if kwargs.get('handle')!='edit_handle' or not self.editing or self.es is None or self.edrag is not None:return
        p=kwargs['parms'];sel=self._edit_selected()
        for k in EDIT_HANDLE_ZERO:p[k]=0
        for k in ('sx','sy','sz'):p[k]=1
        c=self.es['pos'][sel].mean(axis=0) if len(sel) else np.zeros(3);p['px'],p['py'],p['pz']=float(c[0]),float(c[1]),float(c[2]);p['onoff']=len(sel)>0
    @guarded
    def onBeginHandleToState(self,kwargs):
        if kwargs.get('handle','edit_handle')!='edit_handle' or not self.editing or self.es is None:return
        m=self._m();sel=self._edit_selected();self.esnap=m.edit_snapshot(self.node);self.edrag=dict(sel=sel,delta=None,corners=m.edit_corners(self.es,sel),base=m.edit_store(self.node),ids=self.es['ids'][sel],last=0.0,live=bool(self.node.evalParm('edit_live')),written=False)
        try:self.scene_viewer.beginStateUndo('Arraytron: edit instances')
        except Exception:pass
    @guarded
    def onHandleToState(self,kwargs):
        if kwargs.get('handle')!='edit_handle' or self.edrag is None or not len(self.edrag['sel']):return
        m=self._m();dr=self.edrag;d=m.edit_handle_delta(kwargs['parms']);dr['delta']=d;self._edit_refresh(m.edit_move_corners(dr['corners'],d))
        if dr['live'] and self.esnap is not None and time.time()-dr['last']>=EDIT_LIVE_S:                   # the instances follow the handle: one parameter written, at most this often
            m.edit_set_data(self.node,m.edit_drag_text(dr['base'],self.esnap,dr['ids'],d));dr['last']=time.time();dr['written']=True
    @guarded
    def onEndHandleToState(self,kwargs):
        drag=self.edrag
        try:
            if drag is not None and drag['delta'] is not None and len(drag['sel']) and self.esnap is not None:self._m().edit_set_data(self.node,self._m().edit_drag_text(drag['base'],self.esnap,drag['ids'],drag['delta']))
        finally:
            self.edrag=None
            try:self.scene_viewer.endStateUndo()
            except Exception:pass
        if self.editing:self._edit_load()
    def _biome_row(self):
        n=self.node;return min(max(n.evalParm('biome_brush_row'),1),max(n.evalParm('biomes'),1))
    def _biome_load(self):
        m=self._m();self.brush.show(False);self.core.show(False);self.preview.show(False);self.marker.show(False);self.erased.show(False)
        try:self.bsurf=m.biomemap_surface(self.node)
        except hou.Error as exc:
            self.bsurf=None;self.scene_viewer.setPromptMessage('Arraytron Biome Map: %s'%exc,hou.promptMessageType.Error)
        self.bdata=m.biomemap_decode(self.node.evalParm('biome_map_data'));self.bdirty=False;self.bhit=None;self._biome_draw_points()
    def _biome_draw_points(self):
        """The stamps of the active biome row as points on the terrain: green where painted, red where erased."""
        row=self._biome_row();paint=hou.Geometry();erase=hou.Geometry()
        if self.bdata is not None and len(self.bdata):
            sel=self.bdata[self.bdata[:,0]==row][-4000:]
            paint.createPoints([(float(s[2]),float(s[3])+0.02,float(s[4])) for s in sel if s[1]>0]);erase.createPoints([(float(s[2]),float(s[3])+0.02,float(s[4])) for s in sel if s[1]<=0])
        self.preview.setGeometry(paint);self.preview.show(True);self.erased.setGeometry(erase);self.erased.show(True)
    def _biome_dab(self):
        n=self.node;pos,nrm=self.bhit;r=max(n.evalParm('biome_brush_radius'),1e-4)
        self.bdata,added=self._m().biomemap_add(self.bdata,self._biome_row(),self.bsign,pos,r,n.evalParm('biome_brush_strength'),n.evalParm('biome_brush_falloff'))
        if added:self.bdirty=True;self._biome_draw_points()
    def _biome_ring(self):
        if self.bhit is None:self.brush.show(False);self.core.show(False);return
        pos,nrm=self.bhit;r=max(self.node.evalParm('biome_brush_radius'),1e-4);erase=self.bsign<0 if self.bpainting else self._biome_erase_hover
        self.brush.setParams({'color1':hou.Vector4((1.0,0.25,0.2,1.0) if erase else (0.3,1.0,0.4,1.0)),'line_width':2.0});self.brush.setGeometry(self._ring(pos,nrm,r));self.brush.show(True)
        strength=min(max(self.node.evalParm('biome_brush_strength'),0.0),1.0)
        if 0.02<strength<0.99:self.core.setGeometry(self._ring(pos,nrm,r*strength));self.core.show(True)
        else:self.core.show(False)
    def _biome_mouse(self,ev,dev,reason):
        """Biome map painting: LMB paints the active biome row (keys 1 to 9 pick the row) where the mouse hits the terrain, Ctrl+LMB keeps it out; one undo step per stroke."""
        try:origin,direction=ev.ray()
        except Exception:
            origin,direction=ev.curViewport().mapToWorld(dev.mouseX(),dev.mouseY())
        m=self._m();R=hou.uiEventReason;o=np.array(origin,dtype=float);d=np.array(direction,dtype=float);d=d/np.linalg.norm(d);self.bhit=None
        if self.bsurf is not None:
            P,T,area,normals,vn=self.bsurf;t,j=m.ray_triangles(o,d,P,T)
            if j[0]>=0:
                nrm=normals[j[0]]
                if np.dot(nrm,d)>0:nrm=-nrm
                self.bhit=(o+d*t[0],nrm)
        left=dev.isLeftButton();self._biome_erase_hover=dev.isCtrlKey()
        if left and reason==R.Start and self.bhit is not None:
            self.bpainting=True;self.bsign=-1 if dev.isCtrlKey() else 1;self._biome_dab()
        elif reason==R.Active and self.bpainting and self.bhit is not None:self._biome_dab()
        elif reason==R.Changed and self.bpainting:
            self.bpainting=False;self._commit()
        elif reason==R.Picked and left and self.bhit is not None and not self.bpainting:
            self.bsign=-1 if dev.isCtrlKey() else 1;self._biome_dab();self._commit()
        self._biome_ring();self._prompt();return True
    # ----- the mask brush (v1.26.0): the Paint Mask button; LMB paints the Mask Source Painted, Ctrl+LMB does the opposite, the cook follows the brush while the stroke goes on
    def _mask_op(self,dev=None):
        """The operation of a stroke, an entry of the Brush Operation menu: the menu itself, or (v1.27.0) the Ctrl menu with Ctrl and the Shift menu with Shift. The Opposite entry of the Ctrl menu (the default)
        flips Paint and Erase, Add and Subtract, as in v1.26.0."""
        n=self.node;op=min(n.evalParm('mask_brush_op'),10)
        if dev is None or dev.isCtrlKey()==dev.isShiftKey():return op
        name='mask_brush_op_ctrl' if dev.isCtrlKey() else 'mask_brush_op_shift'
        pick=n.evalParm(name) if n.parm(name) is not None else (11 if dev.isCtrlKey() else op)                            # a build without the Shift menu: Shift does nothing
        if pick>=11:return MASK_OPPOSITE.get(op,1)
        return pick
    def _mask_load(self):
        m=self._m();self.brush.show(False);self.core.show(False);self.preview.show(False);self.marker.show(False);self.erased.show(False);self.mwarn=''
        try:self.msurf=m.maskpaint_surface(self.node)
        except hou.Error as exc:
            self.msurf=m.plane_surface(1000.0,0.0);self.mwarn='no surface (%s): painting on the ground plane'%str(exc).strip().splitlines()[0][:70]
        self.mdata=m.maskpaint_decode(self.node.evalParm('mask_paint_data'));self.mdirty=False;self.mlive=False;self.mhit=None;self._mask_viz_on();self._mask_draw_points()
    def _mask_viz_on(self):
        """Show the mask on the scattering surface while painting (Mask > Visualize), and remember to switch it off again."""
        viz=self.node.parm('mask_viz')
        if viz is not None and self.node.evalParm('mask_paint_show') and viz.eval()==0 and not self.node.userData('arraytron_maskviz'):
            self.node.setUserData('arraytron_maskviz','1');viz.set(1)
    def _mask_viz_restore(self):
        if self.node is not None and self.node.userData('arraytron_maskviz'):
            self.node.destroyUserData('arraytron_maskviz');viz=self.node.parm('mask_viz')
            if viz is not None:viz.set(0)
    def _mask_draw_points(self):
        """The stamps as points on the surface: green where the mask was raised, red where it was lowered."""
        raised=hou.Geometry();lowered=hou.Geometry()
        if self.mdata is not None and len(self.mdata):
            sel=self.mdata[-4000:]
            raised.createPoints([(float(s[1]),float(s[2])+0.02,float(s[3])) for s in sel if int(s[0]) not in (1,3,7)]);lowered.createPoints([(float(s[1]),float(s[2])+0.02,float(s[3])) for s in sel if int(s[0]) in (1,3,7)])
        self.preview.setGeometry(raised);self.preview.show(True);self.erased.setGeometry(lowered);self.erased.show(True)
    def _mask_live(self,force=False):
        """The realtime part: while the stroke goes on the paint is written to the node (without undo steps, about ten times a second), so the scatter follows the brush."""
        if not self.mdirty or not self.node.evalParm('mask_paint_live') or (self.mop in MASK_HEAVY and self.node.parm('mask_brush_bg') is not None):return   # v1.27.0: the full operations (Smooth, Multiply, Maximum, Minimum) are applied when the stroke ends, not live
        now=time.time()
        if not force and now-self.mlast<0.1:return
        with hou.undos.disabler():self.node.parm('mask_paint_data').set(self._m().maskpaint_encode(self.mdata))
        self.mlast=now;self.mlive=True
    def _mask_dab(self):
        """One dab: the operation of the menu entry on the Foreground (or Background) value, repeated across the symmetry planes. The Sample entries read the mask under the brush into Foreground / Background instead."""
        n=self.node;m=self._m();pos,nrm=self.mhit;r=max(n.evalParm('mask_brush_radius'),1e-4);fg=n.evalParm('mask_brush_value');bg=n.evalParm('mask_brush_bg') if n.parm('mask_brush_bg') is not None else 0.0
        what=m.maskpaint_stamp_for(self.mop,fg,bg) if hasattr(m,'maskpaint_stamp_for') else (self.mop,fg)
        if what is None:
            v=m.maskpaint_value_at(n,self.mdata,float(pos[0]),float(pos[2]));self.msampled=v;n.parm('mask_brush_value' if self.mop==9 else 'mask_brush_bg').set(round(v,4));return
        op,value=what
        if self.mlastdab is not None and self.mlastdab[0]==self.mop and np.hypot(self.mlastdab[1]-pos[0],self.mlastdab[2]-pos[2])<0.2*r:return          # not closer than a fifth of the radius to the last dab of the stroke
        self.mlastdab=(self.mop,float(pos[0]),float(pos[2]))
        sym=n.parm('mask_sym_x') is not None;places=m.maskpaint_mirrors(pos,n.evalParm('mask_sym_x'),n.evalParm('mask_sym_z'),n.evalParmTuple('mask_sym_center')) if sym else [tuple(pos)];any_added=False
        for p in places:
            self.mdata,added=m.maskpaint_add(self.mdata,op,p,r,n.evalParm('mask_brush_strength'),n.evalParm('mask_brush_feather'),value,n.evalParm('mask_brush_curve'));any_added=any_added or added
        if any_added:self.mdirty=True;self._mask_draw_points();self._mask_live()
    def _mask_ring(self):
        """The outer ring is the radius (green Paint, orange Add, red Erase, purple Subtract); the white inner ring is the hard core, where the brush is at full strength (radius x (1 - feather))."""
        if self.mhit is None:self.brush.show(False);self.core.show(False);return
        pos,nrm=self.mhit;r=max(self.node.evalParm('mask_brush_radius'),1e-4);op=self.mop if self.mpainting else self._mask_hover_op
        self.brush.setParams({'color1':hou.Vector4(MASK_OP_COLORS[min(op,10)]),'line_width':2.0});self.brush.setGeometry(self._ring(pos,nrm,r));self.brush.show(True)
        feather=min(max(self.node.evalParm('mask_brush_feather'),0.0),1.0)
        if feather>0.02:self.core.setGeometry(self._ring(pos,nrm,r*(1.0-feather)));self.core.show(True)
        else:self.core.show(False)
    _mask_hover_op=0
    def _mask_mouse(self,ev,dev,reason):
        """Mask painting: LMB paints where the mouse hits the surface, Ctrl+LMB does the opposite operation; the paint is written live while the stroke goes on and committed as one undo step at its end."""
        try:origin,direction=ev.ray()
        except Exception:
            origin,direction=ev.curViewport().mapToWorld(dev.mouseX(),dev.mouseY())
        m=self._m();R=hou.uiEventReason;o=np.array(origin,dtype=float);d=np.array(direction,dtype=float);d=d/np.linalg.norm(d);self.mhit=None
        if self.msurf is not None:
            P,T,area,normals,vn=self.msurf;t,j=m.ray_triangles(o,d,P,T)
            if j[0]>=0:
                nrm=normals[j[0]]
                if np.dot(nrm,d)>0:nrm=-nrm
                self.mhit=(o+d*t[0],nrm)
        left=dev.isLeftButton();self._mask_hover_op=self._mask_op(dev)
        if self.mresize is not None:                                                               # Ctrl+Shift+LMB drag: the radius follows the mouse sideways (about 150 pixels per doubling)
            if reason==R.Changed:self.mresize=None
            else:x0,r0=self.mresize;self._set('mask_brush_radius',r0*2.0**((dev.mouseX()-x0)/150.0),0.01,100000.0)
            self._mask_ring();self._prompt();return True
        if reason==R.Start and left and dev.isCtrlKey() and dev.isShiftKey():
            self.mresize=(dev.mouseX(),self.node.evalParm('mask_brush_radius'));self._mask_ring();self._prompt();return True
        if left and reason==R.Start and self.mhit is not None:
            self.mpainting=True;self.mop=self._mask_hover_op;self.morig=self.node.evalParm('mask_paint_data');self.mlive=False;self.mlastdab=None;self._mask_dab()
        elif reason==R.Active and self.mpainting and self.mhit is not None:self._mask_dab()
        elif reason==R.Changed and self.mpainting:
            self.mpainting=False;self.mlastdab=None;self._commit()
        elif reason==R.Picked and left and self.mhit is not None and not self.mpainting:
            self.mop=self._mask_hover_op;self.morig=self.node.evalParm('mask_paint_data');self.mlive=False;self.mlastdab=None;self._mask_dab();self._commit()
        self.mhover=None
        if self.mhit is not None and not self.mpainting and self.mdata is not None:                 # the mask value under the brush, shown in the prompt line
            try:self.mhover=m.maskpaint_value_at(self.node,self.mdata,float(self.mhit[0][0]),float(self.mhit[0][2]))
            except Exception:self.mhover=None
        self._mask_ring();self._prompt();return True
    def _load(self):
        m=self._m();self.data=m.paint_decode(self.node.evalParm('paint_data'))
        try:self.surface=m.paint_surface(self.node)
        except hou.Error as exc:
            self.surface=None;self.scene_viewer.setPromptMessage('Arraytron Paint: %s'%exc,hou.promptMessageType.Error)
        self._draw_points()
    def _draw_points(self,pts=None):
        """The painted points as dots. Paint Engine 2.0: at most the preview budget of them (a fixed subset by id, so it does not flicker) plus every point of the stroke, written to the geometry in one call."""
        geo=hou.Geometry();P=(self.data['pts'] if pts is None else pts) if (self.data is not None or pts is not None) else None
        if P is not None and len(P):
            P=np.asarray(P);budget=int(self._prefs().get('preview_budget',20000)) if self._engine() else 0
            if budget and len(P)>budget:
                keep=(P[:,6].astype(np.int64)*2654435761%1000003)<(budget/len(P))*1000003
                if self.engine is not None and getattr(self.engine,'next',None) is not None:keep|=P[:,6]>=self.engine_next0
                P=P[keep]
            geo.createPoints([tuple(p) for p in P[:,:3].tolist()])
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
        if self._engine():return self._draw_cursor()
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
        m=self._m()
        if self._engine():                                                                       # v1.36.0: a hou.Geometry ray cast (Houdini's own acceleration structure), not every triangle in numpy
            self.hit=m.paint_hit(self.surface,np.array(origin),np.array(direction));return
        P,T,area,normals,vn=self.surface
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
        if kind in ('add','replace'):self.stroke.append(np.array(pos,dtype=float));self.stroke_radius=float(r)                  # the path of the stroke, kept for the Falloff
        if count:self.dirty=True;self._draw_points()
    def _draw_cursor(self):
        """Paint Engine 2.0: BrushCore's cursor (the radius ring laid on the surface, a ring where each falloff starts or at the hardness of an editing brush, a centre cross, a normal tick) in the
        brush's colour; the falloff profiles stand on the surface beside it (density one side, scale the other)."""
        m=self._m();pos,nrm=self.hit;r=self._radius();kind=self.kind if self.painting else self.hover_kind;key=m.PAINT_OP_BRUSH.get(kind,'paint')
        if kind=='remove' or (kind=='add' and self.hover_ctrl):key='erase'
        inners=[]
        if kind=='add':inners=[p['inner'] for p in (m.paint_profile(self.node,'dens'),m.paint_profile(self.node,'scale')) if p is not None]
        elif self.node.parm('brush_hardness') is not None and self.node.evalParm('brush_hardness')>0.03:inners=[self.node.evalParm('brush_hardness')]
        prefs=self._prefs();compact=bool(prefs.get('compact',False));alpha=min(max(float(prefs.get('cursor_opacity',1.0)),0.1),1.0)
        if compact:inners=[]                                                                     # the compact cursor: the radius ring and the cross only
        lift=r*1.5+0.05;surf=self.surface;color=m.BC_COLORS.get(key,(1.0,0.65,0.1,1.0));color=(color[0],color[1],color[2],color[3]*alpha)
        sig=(tuple(np.round(np.asarray(pos)/max(r*0.01,1e-6))),tuple(np.round(nrm,3)),round(r,6),key,tuple(round(x,4) for x in inners))
        if sig==getattr(self,'cursor_sig',None) and _drawable_on(self.brush):return                  # nothing moved: the drawable already shows it (no casts, no geometry)
        self.cursor_sig=sig;proj=m.paint_project(surf) if surf is not None else None
        def project(P):return P if proj is None else proj(P,nrm,lift)
        geo=hou.Geometry()
        for line in m.bc_cursor(pos,nrm,r,inners,48,project):
            pts=geo.createPoints([tuple(float(c) for c in q) for q in line]);poly=geo.createPolygon(is_closed=False)
            for q in pts:poly.addVertex(q)
        self.brush.setParams({'color1':hou.Vector4(color),'line_width':2.0});self.brush.setGeometry(geo);self.brush.show(True)
        if kind=='add' and not compact:
            lines=[];k=1.0
            for prefix,side in (('dens',1.0),('scale',-1.0)):lines+=m.bc_profile_lines(pos,nrm,r,m.paint_profile(self.node,prefix),side)
            if lines:
                g2=hou.Geometry()
                for line in lines:
                    pts=g2.createPoints([tuple(float(c) for c in q) for q in line]);poly=g2.createPolygon(is_closed=False)
                    for q in pts:poly.addVertex(q)
                self.core.setParams({'color1':hou.Vector4(m.BC_COLORS['inner']),'line_width':1.0});self.core.setGeometry(g2);self.core.show(True);return
        self.core.show(False)
    def _prefs(self):
        if getattr(self,'prefs',None) is None:
            try:
                import os
                m=self._m();self.prefs_path=os.environ.get('ARRAYTRON_BRUSH_PREFS') or m.bc_prefs_path(hou.homeHoudiniDirectory());self.prefs=m.bc_prefs_load(self.prefs_path)
            except Exception:self.prefs_path=None;self.prefs={'hud':'standard','preview_budget':20000}
        return self.prefs
    def _paint_hud(self):
        """Paint Engine 2.0: the HUD panel of the brush (its hints at the HUD level, the live values when they change); the prompt line keeps one line."""
        if not self._engine() or not hasattr(self.scene_viewer,'hudInfo'):return                   # a viewer without a HUD panel (the tests' stand-ins): the prompt line only
        m=self._m();n=self.node;op=KINDS[min(n.evalParm('paint_op'),len(KINDS)-1)];level=self._prefs().get('hud','standard');key=m.PAINT_OP_BRUSH.get(op,'paint')
        want=(op,level)
        if getattr(self,'phud_for',None)!=want:
            self.phud_for=want;self.phud_vals=None
            try:
                if level=='hidden':self.scene_viewer.hudInfo(show=False);return
                rows=[{'label':a,'key':b} for a,b in m.bc_hud_rows(key if key in m.BC_BRUSHES else 'paint',level)]
                vals=[('v_brush','Brush'),('v_radius','Radius / strength')]+([('v_density','Density'),('v_falloff','Falloff')] if op=='add' else [('v_amount','Amount')])+([('v_count','Points')] if level!='minimal' else [])
                if level=='minimal':vals=vals[:2]
                common=[] if level=='minimal' else [{'type':'divider','label':'Common'},{'label':'Brush Menu','key':'C'},{'label':'Hints (minimal, standard, expanded, hidden)','key':'H'},{'label':'Brush 1 - 9','key':'1 - 9'}]
                if level=='expanded':common+=[{'label':'Falloff preset','key':'F'},{'label':'Cancel the stroke','key':'Esc'},{'label':'Radius by dragging','key':'Ctrl Shift LMB drag'}]
                self.phud_ids=[i for i,_ in vals]
                self.scene_viewer.hudInfo(template={'title':'Arraytron Paint','desc':'Paint Engine 2.0','icon':'MISC_paint','rows':[{'type':'divider','label':KIND_NAMES[KINDS.index(op)]}]+rows+[{'type':'divider','label':'Values'}]+[{'id':i,'label':l} for i,l in vals]+common})
                self.scene_viewer.hudInfo(show=True)
            except Exception:
                if STRICT:raise
        if level=='hidden':return
        values={'v_brush':KIND_NAMES[KINDS.index(op)]+(' (Classic Dabs)' if not self._engine() else ''),'v_radius':'%.3g / %.2f'%(n.evalParm('paint_radius'),n.evalParm('paint_strength')),'v_density':'%.3g per unit area'%n.evalParm('paint_density'),
                'v_falloff':m.paint_falloff_text(n),'v_amount':'%.3g'%n.evalParm('brush_amount') if n.parm('brush_amount') is not None else '-','v_count':str(0 if self.data is None else len(self.data['pts']))}
        values={k:v for k,v in values.items() if k in getattr(self,'phud_ids',())}
        if values!=getattr(self,'phud_vals',None):
            self.phud_vals=values
            try:self.scene_viewer.hudInfo(values=values)
            except Exception:pass
    def _cycle_hud(self):
        p=self._prefs();p['hud']=self._m().bc_next_hud(p.get('hud','standard'))
        if getattr(self,'prefs_path',None):self._m().bc_prefs_save(self.prefs_path,p)
        self.phud_for=None;self._paint_hud()
    def radial_menu(self):
        """C: Houdini's radial menu of the paint brushes (Paint north, the sculpt brushes around it, More: Orient / Comb, Repaint); the popup menu at the cursor without one."""
        m=self._m();keys=[m.PAINT_OP_BRUSH[k] for k in KINDS];main,more=m.bc_radial_layout(set(keys),())
        def choose(kind):
            with hou.undos.disabler():self.node.parm('paint_op').set(KINDS.index(kind))
            self.phud_for=None;self._paint_hud();self._prompt()
        inv={v:k for k,v in m.PAINT_OP_BRUSH.items()}
        try:
            import radialmenu
            def entry(key):
                kind=inv[key];return {'type':'script_action','label':KIND_NAMES[KINDS.index(kind)],'script':lambda kind=kind,**kw:choose(kind),'check':lambda kind=kind,**kw:KINDS[min(self.node.evalParm('paint_op'),len(KINDS)-1)]==kind}
            sub={d:entry(k) for d,k in zip(('n','ne','e','se','sw','w','nw'),more[:7])}
            top={d:entry(k) for d,k in main.items()};top['s']={'type':'script_submenu','label':'More','script':lambda **kw:radialmenu.setRadialMenu(sub)}
            item=hou.ui.createRadialItem(True,True);item.setLabel('Arraytron Paint Brushes');item.setActionCallback(lambda **kw:radialmenu.setRadialMenu(top));self.scene_viewer.displayRadialMenu(item);return True
        except Exception:
            try:
                try:from PySide6 import QtWidgets,QtGui
                except ImportError:from PySide2 import QtWidgets,QtGui
                if QtWidgets.QApplication.instance() is None:return False                      # no interface (hython): a Qt widget without an application would abort the process
                menu=QtWidgets.QMenu()
                for kind,label in zip(KINDS,KIND_NAMES):
                    act=menu.addAction(label);act.setCheckable(True);act.setChecked(KINDS[min(self.node.evalParm('paint_op'),len(KINDS)-1)]==kind);act.triggered.connect(lambda _=False,kind=kind:choose(kind))
                menu.exec(QtGui.QCursor.pos()) if hasattr(menu,'exec') else menu.exec_(QtGui.QCursor.pos())
            except Exception:pass
            return False
    def _start_stroke(self,kind,dev):
        """Paint Engine 2.0: the stroke object of a brush (it works in memory; nothing is written until release)."""
        m=self._m();node=self.node;pos,nrm=self.hit;self.engine=None;self.engine_next0=int(self.data['next']) if self.data is not None else 0;self.preview_t=0.0
        if kind=='add':self.engine=m.PaintStroke(node,self.data,self.surface,nrm)
        elif kind in ('remove','relax','scale','push','swap','orient'):self.engine=m.PaintEditStroke(node,self.data,self.surface,kind,nrm,op=self._variant(kind,dev))
        elif kind=='replace':self.engine=None;self.repaint=m.BrushDabs(self._radius()*0.35)
        elif kind=='clone':
            if dev.isCtrlKey():
                k=m.paint_clone_capture(node,self.data,pos,nrm,self._radius())
                try:self.scene_viewer.setPromptMessage('Arraytron Paint: clone source of %d point%s.'%(k,'' if k==1 else 's') if k else 'Arraytron Paint: no painted points under the brush to clone.')
                except Exception:pass
                return False
            src=m.paint_clone_source(node)
            if src is None:
                try:self.scene_viewer.setPromptMessage('Arraytron Paint: Ctrl + click painted points first: they become the clone source.')
                except Exception:pass
                return False
            self.engine=dict(clone=src,dabs=m.BrushDabs(max(2.0*src['radius']*float(node.evalParm('clone_scale'))*float(node.evalParm('clone_spacing')),self._radius()*0.25)),rows=[],next=int(self.data['next']),copies=0)
        return True
    def _move_stroke(self,kind):
        m=self._m();pos,nrm=self.hit
        if kind=='replace':
            for c in self.repaint.move(pos):
                self.hit=(c,nrm);self._dab('replace')
            self.hit=(pos,nrm);return
        if isinstance(self.engine,dict):
            e=self.engine
            for c in e['dabs'].move(pos):
                rows=m.paint_clone_rows(self.node,self.surface,e['clone'],c,nrm,e['next'],copy=e['next']+e['copies']);e['copies']+=1
                if len(rows):e['rows'].append(rows);e['next']+=len(rows)
            if e['rows']:self.data=dict(self.data,pts=np.vstack([self.data['pts']]+e['rows']),next=e['next']);e['rows']=[];self.dirty=True
        elif self.engine is not None:
            self.engine.move(pos)
            if kind=='add':self.stroke.append(np.array(pos,dtype=float));self.stroke_radius=float(self._radius())
        if time.time()-getattr(self,'preview_t',0.0)>=PREVIEW_S:
            self.preview_t=time.time();self._draw_points(self.engine.points() if (self.engine is not None and not isinstance(self.engine,dict)) else None)
    def _end_stroke(self):
        """The release: the stroke is finished, the paint data written once (one undo step)."""
        e=self.engine;self.engine=None
        if e is not None and not isinstance(e,dict):
            e.finish();self.data=e.result();self.dirty=True
        self._commit();self._draw_points()
    def _cancel_stroke(self):
        """Esc during a stroke: nothing of it is kept (the paint data were never written)."""
        self.engine=None;self.painting=False;self.stroke=[];self.dirty=False;self._load()
        try:self.scene_viewer.setPromptMessage('Arraytron Paint: stroke cancelled.')
        except Exception:pass
    def _commit(self):
        if self.biomepaint and self.bdirty and self.bdata is not None:
            self._m().biomemap_apply(self.node,self.bdata);self.bdirty=False
        if self.maskpaint and self.mdirty and self.mdata is not None:
            if self.mlive:
                with hou.undos.disabler():self.node.parm('mask_paint_data').set(self.morig)                  # back to the text before the stroke, so the one undo step covers the whole stroke
            self._m().maskpaint_apply(self.node,self.mdata);self.mdirty=False;self.mlive=False
        if self.stroke and self.data is not None:
            self.data=self._m().paint_stroke_add(self.data,self.stroke,self.stroke_radius);self.dirty=True
        self.stroke=[]
        if self.dirty:
            self._m().paint_apply(self.node,self.data);self.dirty=False
    def status(self):
        """The prompt line: the live brush values (and the shortcuts until H hides them)."""
        n=self.node
        if self.editing:
            sel=0 if self.es is None else len(self._edit_selected());total=0 if self.es is None else len(self.es['ids'])
            return 'Arraytron Edit  |  %d instances  |  %d selected'%(total,sel)+('\nClick: select  |  Shift+click: add or remove  |  drag on nothing: box select  |  the handle moves, turns and scales the selection  |  Del: delete  |  A all  |  I invert  |  N none  |  H hide this help  |  Esc / Enter: finish' if self.show_help else '')
        if self.maskpaint:
            head='Arraytron Mask Paint [%s]  |  radius %.3g  strength %.2f  feather %.2f (%s)  value %.2f%s  |  %d stamps%s'%(MASK_OPS[min(self.mop if self.mpainting else self._mask_hover_op,10)],n.evalParm('mask_brush_radius'),n.evalParm('mask_brush_strength'),n.evalParm('mask_brush_feather'),MASK_CURVES[min(n.evalParm('mask_brush_curve'),2)],n.evalParm('mask_brush_value'),'  bg %.2f'%n.evalParm('mask_brush_bg') if n.parm('mask_brush_bg') is not None else '',0 if self.mdata is None else len(self.mdata),'  |  live' if n.evalParm('mask_paint_live') else '')
            if n.parm('mask_sym_x') is not None and (n.evalParm('mask_sym_x') or n.evalParm('mask_sym_z')):head+='  |  symmetry '+('X ' if n.evalParm('mask_sym_x') else '')+('Z' if n.evalParm('mask_sym_z') else '')
            if self.mwarn:head+='  |  '+self.mwarn
            elif self.mhit is None:head+='  |  no surface under the mouse'
            elif self.mhover is not None:head+='  |  mask here %.2f'%self.mhover
            return head+('\nLMB: the Brush Operation  |  Ctrl+LMB: the Ctrl operation (the opposite)  |  Shift+LMB: the Shift operation (smooth)  |  Ctrl+Shift+LMB drag: radius  |  1-8 operation (Paint Erase Add Subtract Smooth, Paint Background, Sample FG, Sample BG)  |  X swap FG and BG  |  wheel + Shift: radius, + Ctrl: strength, + Ctrl+Shift: feather  |  [ ] radius  |  - = strength  |  , . feather  |  9 0 value  |  F curve  |  H hide this help  |  Esc / Enter: finish' if self.show_help else '')
        if self.biomepaint:
            row=self._biome_row();name=n.evalParm('biome_name%d'%row) if n.evalParm('biomes')>0 else '-';mode=('Off','Add And Erase','Only Where Painted')[min(n.evalParm('biome_map%d'%row),2)] if n.evalParm('biomes')>0 else '-'
            head='Arraytron Biome Map  |  row %d %s  (Map: %s)  radius %.3g  strength %.2f  falloff %s  |  %d stamps'%(row,name,mode,n.evalParm('biome_brush_radius'),n.evalParm('biome_brush_strength'),FALLOFFS[min(n.evalParm('biome_brush_falloff'),3)],0 if self.bdata is None else len(self.bdata))
            if self.bsurf is None:head+='  |  no terrain'
            elif self.bhit is None:head+='  |  no terrain under the mouse'
            return head+('\nLMB paint this biome  |  Ctrl+LMB keep it out  |  1-9 biome row  |  wheel + Shift: radius, + Ctrl: strength  |  [ ] radius  |  - = strength  |  F falloff  |  H hide this help  |  Esc / Enter: finish' if self.show_help else '')
        if self.placing:
            proto=n.evalParm('place_def_proto')
            head='Arraytron Place  |  scale %.3g  rotation %g  prototype %s  |  %d placed'%(n.evalParm('place_def_scale'),n.evalParm('place_def_yaw'),'auto' if proto==0 else 'row %d'%proto,n.evalParm('places'))
            if n.evalParm('place_snap')>0 or n.evalParm('place_snap_rot')>0:head+='  |  snap %g / %g deg'%(n.evalParm('place_snap'),n.evalParm('place_snap_rot'))
            if self.place_drag is not None:head='Arraytron Place  |  drag: rotation %+.0f deg  scale x%.2f  |  release to place'%(self.place_drag['yaw'],self.place_drag['scale'])
            elif self.place_hit is None:head+='  |  no surface under the mouse'
            return head+('\nClick: place an instance (press, drag to turn and scale, release)  |  Ctrl+click: delete the one under the mouse  |  wheel + Shift: scale, + Ctrl: rotation  |  [ ] scale  |  , . rotation  |  0-9 prototype row (0 auto)  |  H hide this help  |  Esc / Enter: finish' if self.show_help else '')
        if self.picking:
            head='Arraytron Pick  |  no instance under the mouse'
            if self.pick_hit is not None:
                row=self._m().pick_row(n,self.pick_hit[0]);head='Arraytron Pick  |  instance id %d%s'%(self.pick_hit[0],'  (override row %d)'%row if row else '')
            return head+('\nClick: add / select its override row  |  Ctrl+click: also tick Delete  |  Esc / Enter: finish' if self.show_help else '')
        if self._engine():                                                               # Paint Engine 2.0: one line; the hints are the HUD panel (H)
            op=min(n.evalParm('paint_op'),len(KINDS)-1)
            return 'Arraytron Paint [%s]  radius %.3g  strength %.2f  %s  |  %d points  |  C brushes  H hints'%(KIND_NAMES[op],n.evalParm('paint_radius'),n.evalParm('paint_strength'),('density %.3g  %s'%(n.evalParm('paint_density'),self._m().paint_falloff_text(n))) if op==0 else 'amount %.3g'%(n.evalParm('brush_amount') if n.parm('brush_amount') is not None else 0.0),0 if self.data is None else len(self.data['pts']))
        line='Arraytron Paint [%s]  radius %.3g  strength %.2f  density %.3g  falloff %s  |  %d points'%(KIND_NAMES[min(n.evalParm('paint_op'),3)],n.evalParm('paint_radius'),n.evalParm('paint_strength'),n.evalParm('paint_density'),FALLOFFS[min(n.evalParm('paint_falloff'),3)],0 if self.data is None else len(self.data['pts']))
        return line+('\n'+HELP if self.show_help else '')
    def _prompt(self):
        if self.editing:return
        self.scene_viewer.setPromptMessage(self.status())
        if not (self.maskpaint or self.biomepaint or self.placing or self.picking):self._paint_hud()

    def _gizmo(self):
        """Show the Bounds Transform gizmo only when Show Gizmo is on and no brush tool is active (it is called on entering, on every mouse event and on leaving; showHandle is only called when the answer changes)."""
        if not GIZMO_HANDLE or self.node is None:return
        try:
            parm=self.node.parm('bound_gizmo');want=bool(parm.eval()) and not self._active() if parm is not None else False
            if want!=getattr(self,'_gizmo_on',None):self.scene_viewer.showHandle('Transformer',want);self._gizmo_on=want
        except Exception:pass                                                            # a viewer without handles (the tests' stand-in): nothing to show or hide

    # ----- state callbacks
    @guarded
    def onEnter(self,kwargs):
        self.node=kwargs['node'];self.loaded=False;self._gizmo_on=None;self._gizmo()
        if 'stamp' in self.node.type().name() and not self.placing:self.node.setUserData('arraytron_place','1')
        if 'stamp' in self.node.type().name():
            try:self.node.hdaModule().gallery_ensure()                                                                                               # the Layout-like panel opens with the tool
            except Exception:pass
        # Arraytron Stamp: entering the node's tool is placing, like the Layout tool (Esc leaves)
        self._ensure()
    @guarded
    def onResume(self,kwargs):
        self.loaded=False;self._ensure();self._gizmo_on=None;self._gizmo()
    @guarded
    def onInterrupt(self,kwargs):
        if self.painting and self.engine is not None:self.painting=False;self._end_stroke()                       # the mouse left the viewer mid-stroke: what was painted is kept (one undo step)
        self._commit();self.mpainting=False;self.brush.show(False);self.core.show(False);self.preview.show(False);self.marker.show(False);self.erased.show(False);self.esel.show(False);self.ehover.show(False);self.eframe.show(False);self._edit_handle(False)
    @guarded
    def onExit(self,kwargs):
        if self.painting and self.engine is not None:self.painting=False;self._end_stroke()
        self._commit();self._mask_viz_restore();self._edit_leave();self.maskpaint=False;self.mpainting=False;self.mresize=None;self.mhover=None;self.mhit=None;self.picking=False;self.placing=False;self.biomepaint=False;self.bpainting=False;self.bhit=None;self.place_hit=None;self.place_drag=None;self.inst=None;self.pick_hit=None;self.loaded=False
        self.brush.show(False);self.core.show(False);self.preview.show(False);self.marker.show(False);self.erased.show(False);self.scene_viewer.clearPromptMessage()
    @guarded
    def onMouseEvent(self,kwargs):
        active=self._ensure();self._gizmo()
        if not active:return False
        ev=kwargs['ui_event'];dev=ev.device();reason=ev.reason()
        if dev.isMiddleButton() or dev.isAltKey():return False                        # let the camera handle navigation
        if self.editing:return self._edit_mouse(ev,dev,reason)
        if self.maskpaint:return self._mask_mouse(ev,dev,reason)
        if self.biomepaint:return self._biome_mouse(ev,dev,reason)
        if self.placing:return self._place_mouse(ev,dev,reason)
        if self.picking:return self._pick_mouse(ev,dev,reason)
        self._pick(ev)
        if self.resizing is not None:                                                  # Ctrl+Shift+LMB drag: the radius follows the mouse sideways (about 150 pixels per doubling)
            if reason==hou.uiEventReason.Changed:self.resizing=None
            else:
                x0,r0=self.resizing;self._set('paint_radius',r0*2.0**((dev.mouseX()-x0)/150.0),0.01,100.0)
            self._prompt();self._draw_brush();return True
        if reason==hou.uiEventReason.Start and dev.isLeftButton() and dev.isCtrlKey() and dev.isShiftKey():
            self.resizing=(dev.mouseX(),self.node.evalParm('paint_radius'));self._draw_brush();return True
        self.hover_kind=self._kind_for(dev);self.hover_ctrl=dev.isCtrlKey()
        if self._engine():return self._engine_mouse(dev,reason)
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
    def _engine_mouse(self,dev,reason):
        """Paint Engine 2.0: press starts the brush's stroke object, drag feeds it the path (distance based: the same result at any mouse speed), release writes it once (one undo step)."""
        R=hou.uiEventReason
        if reason in (R.Start,R.Picked) and dev.isLeftButton() and self.hit is not None and not self.painting:
            if self.data is None:self._load()
            self.kind=self.hover_kind;self.removing=self.kind=='remove';self.stroke=[]
            if self._start_stroke(self.kind,dev):
                self.painting=True;self._move_stroke(self.kind)
                if reason==R.Picked:self.painting=False;self._end_stroke()
        elif reason==R.Active and self.painting and self.hit is not None:self._move_stroke(self.kind)
        elif reason in (R.Changed,R.Picked) and self.painting:
            self.painting=False;self._end_stroke()
        self._draw_brush();self._prompt();return True
    def _place_mouse(self,ev,dev,reason):
        """Instance Place: the marker follows the surface under the mouse (snapped to the grid when Snap Position is on). Press and drag turn and scale the new instance, release places it (a plain click
        that arrives as Picked places at once; with Drag Sets Rotation And Scale off the press places). Ctrl-click deletes the placed instance under the mouse."""
        try:origin,direction=ev.ray()
        except Exception:
            origin,direction=ev.curViewport().mapToWorld(dev.mouseX(),dev.mouseY())
        m=self._m();node=self.node;o=np.array(origin,dtype=float);d=np.array(direction,dtype=float);d=d/np.linalg.norm(d);left=dev.isLeftButton();R=hou.uiEventReason
        if self.place_drag is None:
            self.place_hit=None
            if self.place_surf is not None:
                P,T,area,normals,vn=self.place_surf;t,j=m.ray_triangles(o,d,P,T)
                if j[0]>=0:
                    nrm=normals[j[0]]
                    if np.dot(nrm,d)>0:nrm=-nrm
                    point,nrm=m.place_snap_point(node,self.place_surf,o+d*t[0],nrm);self.place_hit=(point,nrm,float(t[0]))
        def commit(yaw_add=0.0,scale_mult=1.0):
            if time.time()-self.place_last[0]<0.25:return                                   # a click can arrive as Start, Changed and Picked: place once
            self.place_last=(time.time(),None);pos,nrm,t=self.place_hit
            m.place_add(node,pos,nrm,yaw_add=yaw_add,scale_mult=scale_mult,snap_rot=node.evalParm('place_snap_rot') or None)
        if left and reason==R.Start and dev.isCtrlKey():
            if time.time()-self.place_last[0]>=0.25:
                self.place_last=(time.time(),None);found=m.place_nearest(node,o,d)
                if found is not None:m.place_remove(node,found[0])
        elif left and reason==R.Start and self.place_hit is not None:
            if node.evalParm('place_dragset'):self.place_drag=dict(x=dev.mouseX(),y=dev.mouseY(),hit=self.place_hit,yaw=0.0,scale=1.0)
            else:commit()
        elif self.place_drag is not None and reason==R.Active:
            self.place_drag['yaw'],self.place_drag['scale']=m.place_drag_values(dev.mouseX()-self.place_drag['x'],self.place_drag['y']-dev.mouseY())
        elif self.place_drag is not None and reason in (R.Changed,R.Picked):
            drag=self.place_drag;self.place_drag=None;self.place_hit=drag['hit'];commit(drag['yaw'],drag['scale'])
        elif left and reason==R.Picked and self.place_hit is not None and not dev.isCtrlKey():commit()
        shown=self.place_drag['hit'] if self.place_drag is not None else self.place_hit
        if shown is None:self.marker.show(False);self.erased.show(False)
        else:
            pos,nrm,t=shown;r=max(t*0.02,1e-3);yaw=node.evalParm('place_def_yaw')+(self.place_drag['yaw'] if self.place_drag is not None else 0.0);k=self.place_drag['scale'] if self.place_drag is not None else 1.0
            snap=node.evalParm('place_snap_rot')
            if snap>0:yaw=float(np.round(yaw/snap)*snap)
            geo=self._ring(pos,nrm,r);a=geo.createPoint();a.setPosition(hou.Vector3(tuple((pos+nrm*0.01).tolist())));b=geo.createPoint();b.setPosition(hou.Vector3(tuple((pos+nrm*r*3.0).tolist())));line=geo.createPolygon(is_closed=False);line.addVertex(a);line.addVertex(b)
            forward=m.place_rotate(m.place_aim(nrm,node.evalParm('place_align'),yaw),(0.0,0.0,1.0));c=geo.createPoint();c.setPosition(hou.Vector3(tuple((pos+nrm*0.01).tolist())));e=geo.createPoint();e.setPosition(hou.Vector3(tuple((pos+nrm*0.01+forward*r*3.0*k).tolist())))
            head=geo.createPolygon(is_closed=False);head.addVertex(c);head.addVertex(e)                                      # the heading of the new instance (+Z)
            self.marker.setParams({'color1':hou.Vector4((0.2,1.0,0.4,1.0)),'line_width':3.0});self.marker.setGeometry(geo);self.marker.show(True)
        self._prompt();return True
    def _pick_mouse(self,ev,dev,reason):
        """Pick Instance: the marker follows the instance under the mouse; a click creates (or finds) its override row, Ctrl-click ticks Delete."""
        try:origin,direction=ev.ray()
        except Exception:
            origin,direction=ev.curViewport().mapToWorld(dev.mouseX(),dev.mouseY())
        m=self._m()
        if self.inst is None:self.inst=m.pick_instances(self.node)
        self.pick_hit=m.pick_nearest(origin,direction,self.inst['P'],self.inst['ids'])
        if self.pick_hit is None:self.marker.show(False);self.erased.show(False)
        else:
            iid,pos,t=self.pick_hit;view=-np.asarray(direction,dtype=float);view=view/np.linalg.norm(view)
            self.marker.setParams({'color1':hou.Vector4((1.0,0.9,0.1,1.0)),'line_width':3.0});self.marker.setGeometry(self._ring(pos,view,max(t*0.03,1e-3)));self.marker.show(True)
            if dev.isLeftButton() and reason in (hou.uiEventReason.Start,hou.uiEventReason.Picked):
                m.pick_add(self.node,iid,delete=dev.isCtrlKey());self.inst=None                       # the list is read again (a deleted instance is gone)
        self._prompt();return True
    @guarded
    def onMouseWheelEvent(self,kwargs):
        """Shift + wheel: radius; Ctrl + wheel: strength; Ctrl + Shift + wheel: density (anything else scrolls / zooms the camera as usual)."""
        if not self._ensure() or self.picking or self.editing:return False
        if self.maskpaint:
            dev=kwargs['ui_event'].device();step=dev.mouseWheel();sign=1 if step>0 else -1 if step<0 else 0
            if sign==0 or dev.isAltKey():return False
            if dev.isShiftKey() and dev.isCtrlKey():self._set('mask_brush_feather',self.node.evalParm('mask_brush_feather')+0.05*sign,0.0,1.0)
            elif dev.isShiftKey():self._set('mask_brush_radius',self.node.evalParm('mask_brush_radius')*1.1**sign,0.01,100000.0)
            elif dev.isCtrlKey():self._set('mask_brush_strength',self.node.evalParm('mask_brush_strength')+0.05*sign,0.0,1.0)
            else:return False
            self._prompt();self._mask_ring();return True
        if self.biomepaint:
            dev=kwargs['ui_event'].device();step=dev.mouseWheel();sign=1 if step>0 else -1 if step<0 else 0
            if sign==0 or dev.isAltKey():return False
            if dev.isShiftKey():self._set('biome_brush_radius',self.node.evalParm('biome_brush_radius')*1.1**sign,0.01,100000.0)
            elif dev.isCtrlKey():self._set('biome_brush_strength',self.node.evalParm('biome_brush_strength')+0.05*sign,0.0,1.0)
            else:return False
            self._prompt();self._biome_ring();return True
        if self.placing:
            dev=kwargs['ui_event'].device();step=dev.mouseWheel();sign=1 if step>0 else -1 if step<0 else 0
            if sign==0 or dev.isAltKey():return False
            if dev.isShiftKey():self._set('place_def_scale',self.node.evalParm('place_def_scale')*1.1**sign,0.0001,1000.0)
            elif dev.isCtrlKey():self._set('place_def_yaw',self.node.evalParm('place_def_yaw')+15.0*sign,-360.0,360.0)
            else:return False
            self._prompt();return True
        dev=kwargs['ui_event'].device();step=dev.mouseWheel();sign=1 if step>0 else -1 if step<0 else 0
        if sign==0 or dev.isAltKey():return False
        if dev.isShiftKey() and dev.isCtrlKey() and self._engine() and self.node.evalParm('paint_op')>=4 and self.node.parm('brush_amount') is not None:self._set('brush_amount',self.node.evalParm('brush_amount')*1.15**sign,0.001,2.0)     # the sculpt brushes: the amount
        elif dev.isShiftKey() and dev.isCtrlKey():self._set('paint_density',self.node.evalParm('paint_density')*1.15**sign,0.0,1000.0)
        elif dev.isShiftKey():self._set('paint_radius',self.node.evalParm('paint_radius')*1.1**sign,0.01,100.0)
        elif dev.isCtrlKey():self._set('paint_strength',self.node.evalParm('paint_strength')+0.05*sign,0.0,1.0)
        else:return False
        self._prompt();self._draw_brush();return True
    @guarded
    def onKeyEvent(self,kwargs):
        if not self._ensure() or self.picking:return False
        if self.editing:return self._edit_key(kwargs)
        key=kwargs['ui_event'].device().keyString();n=self.node
        if self.maskpaint:
            if key in ('[',']'):self._set('mask_brush_radius',n.evalParm('mask_brush_radius')*(1.1 if key==']' else 1/1.1),0.01,100000.0)
            elif key in ('-','_'):self._set('mask_brush_strength',n.evalParm('mask_brush_strength')-0.05,0.0,1.0)
            elif key in ('=','+'):self._set('mask_brush_strength',n.evalParm('mask_brush_strength')+0.05,0.0,1.0)
            elif key==',':self._set('mask_brush_feather',n.evalParm('mask_brush_feather')-0.05,0.0,1.0)
            elif key=='.':self._set('mask_brush_feather',n.evalParm('mask_brush_feather')+0.05,0.0,1.0)
            elif key=='9':self._set('mask_brush_value',n.evalParm('mask_brush_value')-0.1,0.0,1.0)
            elif key=='0':self._set('mask_brush_value',n.evalParm('mask_brush_value')+0.1,0.0,1.0)
            elif key in ('1','2','3','4'):n.parm('mask_brush_op').set(int(key)-1)
            elif key in ('5','6','7','8') and n.parm('mask_brush_bg') is not None:n.parm('mask_brush_op').set({'5':4,'6':8,'7':9,'8':10}[key])                          # Smooth, Paint Background, Sample Foreground, Sample Background
            elif key in ('x','X') and n.parm('mask_brush_bg') is not None:
                fg=n.evalParm('mask_brush_value');n.parm('mask_brush_value').set(n.evalParm('mask_brush_bg'));n.parm('mask_brush_bg').set(fg)                       # swap Foreground and Background
            elif key in ('f','F'):n.parm('mask_brush_curve').set((n.evalParm('mask_brush_curve')+1)%3)
            elif key in ('h','H'):self.show_help=not self.show_help
            else:return False
            self._mask_hover_op=self._mask_op();self._prompt();self._mask_ring();return True
        if self.biomepaint:
            if key in ('[',']'):self._set('biome_brush_radius',n.evalParm('biome_brush_radius')*(1.1 if key==']' else 1/1.1),0.01,100000.0)
            elif key in ('-','_'):self._set('biome_brush_strength',n.evalParm('biome_brush_strength')-0.05,0.0,1.0)
            elif key in ('=','+'):self._set('biome_brush_strength',n.evalParm('biome_brush_strength')+0.05,0.0,1.0)
            elif key in ('f','F'):n.parm('biome_brush_falloff').set((n.evalParm('biome_brush_falloff')+1)%4)
            elif len(key)==1 and key.isdigit() and key!='0':
                n.parm('biome_brush_row').set(min(int(key),max(n.evalParm('biomes'),1)));self._biome_draw_points()
            elif key in ('h','H'):self.show_help=not self.show_help
            else:return False
            self._prompt();self._biome_ring();return True
        if self.placing:
            if key in ('[',']'):self._set('place_def_scale',n.evalParm('place_def_scale')*(1.1 if key==']' else 1/1.1),0.0001,1000.0)
            elif key in (',','.'):self._set('place_def_yaw',n.evalParm('place_def_yaw')+(15.0 if key=='.' else -15.0),-360.0,360.0)
            elif len(key)==1 and key.isdigit():n.parm('place_def_proto').set(int(key))
            elif key in ('h','H'):self.show_help=not self.show_help
            else:return False
            self._prompt();return True
        if self._engine():
            if key in ('Esc','Escape') and self.painting:self._cancel_stroke();self._draw_brush();return True
            if _key_is(kwargs,key,'paint_brushmenu'):self.radial_menu();return True
            if _key_is(kwargs,key,'paint_hints'):self._cycle_hud();self._prompt();return True
            if len(key)==1 and key.isdigit() and key!='0' and int(key)<=len(KINDS):n.parm('paint_op').set(int(key)-1);self.phud_for=None;self._prompt();self._draw_brush();return True
            if key in ('f','F'):
                m=self._m();i=(min(max(int(n.evalParm('paint_preset')),0),len(m.BC_PRESETS)-1)+1)%len(m.BC_PRESETS)
                if m.BC_PRESETS[i]=='custom':i=(i+1)%len(m.BC_PRESETS)
                m.paint_preset(n,m.BC_PRESETS[i]);self._prompt();self._draw_brush();return True
        if key in ('[',']'):self._set('paint_radius',n.evalParm('paint_radius')*(1.1 if key==']' else 1/1.1),0.01,100.0)
        elif key in ('-','_'):self._set('paint_strength',n.evalParm('paint_strength')-0.05,0.0,1.0)
        elif key in ('=','+'):self._set('paint_strength',n.evalParm('paint_strength')+0.05,0.0,1.0)
        elif key==',':self._set('paint_density',n.evalParm('paint_density')/1.15,0.0,1000.0)
        elif key=='.':self._set('paint_density',n.evalParm('paint_density')*1.15,0.0,1000.0)
        elif key in ('1','2','3','4'):n.parm('paint_op').set(int(key)-1)
        elif key in ('f','F'):n.parm('paint_falloff').set((n.evalParm('paint_falloff')+1)%4)
        elif key in ('h','H') or _key_is(kwargs,key,'paint_hints'):self.show_help=not self.show_help
        else:return False
        self._prompt();self._draw_brush();return True
    @guarded
    def onDraw(self,kwargs):
        handle=kwargs['draw_handle'];self.esel.draw(handle);self.ehover.draw(handle);self.eframe.draw(handle);self.preview.draw(handle);self.erased.draw(handle);self.brush.draw(handle);self.core.draw(handle);self.marker.draw(handle)

def createViewerStateTemplate():
    """Mandatory entry point: the state template for Solaris (LOP) nodes."""
    template=hou.ViewerStateTemplate(kwargs['type'].definition().sections()['DefaultState'].contents().strip(),'Arraytron Paint',hou.lopNodeTypeCategory())
    template.bindFactory(PaintState)
    if GIZMO_HANDLE:template.bindHandleStatic('lopxform','Transformer',list(GIZMO_BINDINGS))               # the gizmo of the Move The Layout parameters (before 1.30.1: bound on the node, always shown)
    template.bindHandle('xform','edit_handle')                                                            # v1.35.0: the edit handle of the Edit tool (Select And Edit Instances)
    template.bindIcon('MISC_paint')
    try:
        import viewerstate.utils as su
        defs=hou.PluginHotkeyDefinitions();su.defineHotkey(defs,STATE_NAME,EDIT_TOKEN,EDIT_KEY,'Delete Selected Instances','Edit tool: delete the selected instances',hou.lopNodeTypeCategory())
        for token,(k,label,descr) in PAINT_HOTKEYS.items():su.defineHotkey(defs,STATE_NAME,token,k,label,descr,hou.lopNodeTypeCategory())             # v1.36.0: C and H belong to the paint tool (Houdini's own C radial menu stays outside it)
        template.bindHotkeyDefinitions(defs)
    except Exception:pass
    return template
