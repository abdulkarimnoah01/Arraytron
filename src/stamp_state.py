# Arraytron Stamp: the Python Viewer State of arraytron::stamp (the ViewerStateModule section), built like Houdini's Layout / Paint Instances tool. Entering the node's tool is placing.
# Paint Engine 2.0 (0.11.0): the brush maths is BrushCore's (src/brushcore.py, in the PythonModule, shared with Arraytron); the sculpt brushes Erase, Relax, Grow / Shrink, Push / Attract, Replace,
# Orient / Comb and Clone; C opens a radial brush menu, H cycles the HUD (minimal, standard, expanded, hidden; kept in the user's arraytron_brush_prefs.json), Esc during a stroke cancels it.
#   Modes   Brush and Edit (Shift+B, or the tabs of the Parameters pane); brushes Place, Delete, Paint and Group (C opens the brush menu, B the options menu)
#   Place   LMB click places | LMB drag sets rotation and scale (the stamp stays where you pressed, turns to face the mouse and grows until its footprint reaches it)
#           Shift+LMB drag: scale only | Ctrl+LMB drag: orient only, to increments | Ctrl+Shift+LMB drag: orient freely | mousewheel: cycle the working set (the selected cards)
#           Shift / Ctrl + mousewheel: scale / rotation of the next stamp | [ ] scale | , . rotation | 1 - 9 prototype row
#   Delete  LMB click or drag over the stamps to delete them (they show red while you drag, one undo step when you release)
#   Paint   LMB drag paints stamps inside a disc (Radius, Density, Spacing, Edge Falloff of Brush > Paint); Ctrl + LMB drag erases the stamps inside it; Shift / Ctrl + mousewheel (and [ ]) change the radius / density; one undo step per stroke
#   Group   like Place, but one click stamps several prototypes: a ring of the selected cards, or the layout of stamps the artist placed (Edit mode: select them, G = Set Layout From Selection)
# Place shows the prototype itself under the mouse (a ghost: the real geometry, lit, translucent), not a box.
#   Edit    LMB click selects a stamp (Shift: add or remove), LMB drag on nothing: box select; the edit handle moves, turns and scales the selection;
#           Z + drag duplicates | Del deletes the selection | M steps the material of the selection | Enter leaves the stroke
# The hotkeys are Houdini hotkeys (Edit > Preferences > Hotkeys, "arraytron_stamp Operation"), the hints and values are the viewer's HUD panel (Shift + F1 hides it).
# Object aware: the ray hits the stamps already placed too (Place On Stamps), so stamps stack. Light on purpose: the ray goes against a hou.Geometry (its own BVH), the prototype boxes are read once,
# the HUD is only updated when a value changes, a placement writes ONE parameter and an edit drag rewrites only the selected lines.
import hou
import numpy as np
import time
import traceback

STATE_NAME='arraytron_stamp'
STRICT=False                                                                   # the tests set it: errors are raised instead of being shown in the viewer
PAINT_FLUSH_S=0.05                                                             # Paint with falloff writes its new stamps at most this often (a write costs as long as the text)
RING=48;TICKS=36;DRAG_PIXELS=5;MAX_BOXES=2000;MAX_GHOSTS=12
KEYS={'duplicate':'z','finish':'Enter','delete':'Del','brushselector':'c','brushradial':'b','togglemode':'Shift+b','scaleup':']','scaledown':'[','rotleft':',','rotright':'.','group':'g','material':'m','hud':'h'}
HK_NAMES={'duplicate':('Duplicate','Duplicate the selection (hold while dragging the edit handle)'),'finish':('Finish Stroke','Finish the stroke'),'delete':('Delete Selection','Delete the selected stamps'),
          'brushselector':('Brush Menu','Choose the brush'),'brushradial':('Brush Options Menu','The options of the brush'),'togglemode':('Toggle Mode','Switch between Brush and Edit'),
          'scaleup':('Scale Up','Scale the next stamp up'),'scaledown':('Scale Down','Scale the next stamp down'),'rotleft':('Rotate Left','Turn the next stamp'),'rotright':('Rotate Right','Turn the next stamp'),'group':('Group From Selection','Edit mode: the selected stamps become the layout of the Group brush'),
          'material':('Next Material','Edit mode: the selected stamps take the next material of their bank row (own, 1, 2, ... own)'),'hud':('Cycle Hints','The HUD hints: minimal, standard, expanded, hidden')}
BOX_EDGES=np.array(((0,1),(2,3),(4,5),(6,7),(0,2),(1,3),(4,6),(5,7),(0,4),(1,5),(2,6),(3,7)),dtype=np.int64)
BRUSHES=('Place','Delete','Paint','Group','Erase','Relax','Grow / Shrink','Push / Attract','Replace','Orient / Comb','Clone');MODES=('Brush','Edit')
BRUSH_KEYS=('place','delete','paint','group','erase','relax','scale','push','replace','orient','clone')                       # the value of the parameter brush (0.9 had the first four)
SCULPT=(4,5,6,7,8,9);CLONE=10
VALUES={'place':(('v_proto',),('v_proto','v_scale','v_rot','v_mat','v_count','v_sel'),()),'group':(('v_proto',),('v_proto','v_scale','v_rot','v_mat','v_count','v_sel'),()),
        'paint':(('v_paint',),('v_paint','v_falloff','v_proto','v_count'),('v_scale','v_rot','v_mat')),'delete':(('v_count',),('v_count',),('v_sel',)),'edit':(('v_sel',),('v_count','v_sel'),('v_mat',)),
        'clone':(('v_clone',),('v_clone','v_brush','v_count'),('v_sel',))}
VALUE_LABELS={'v_proto':'Prototype','v_scale':'Scale','v_rot':'Rotation','v_mat':'Material','v_count':'Stamps','v_sel':'Selected','v_paint':'Radius / density / strength','v_falloff':'Paint falloff','v_brush':'Radius / strength / amount','v_clone':'Clone source'}
HANDLE_ZERO=('rpivotx','rpivoty','rpivotz','rprex','rprey','rprez','rpostx','rposty','rpostz','roffsetx','roffsety','roffsetz','spivotx','spivoty','spivotz','soffsetx','soffsety','soffsetz',
             'pivot_comp_tx','pivot_comp_ty','pivot_comp_tz','pivot_comp_rx','pivot_comp_ry','pivot_comp_rz','tx','ty','tz','rx','ry','rz','shear_xy','shear_xz','shear_yz','pivot_rx','pivot_ry','pivot_rz')
GREEN=(0.2,1.0,0.4,1.0);WHITE=(1.0,1.0,1.0,1.0);GREY=(0.75,0.75,0.75,0.8);YELLOW=(1.0,0.85,0.2,1.0);RED=(1.0,0.25,0.2,1.0);BLUE=(0.35,0.7,1.0,1.0);ORANGE=(1.0,0.63,0.19,1.0)

def hk_symbol(token):
    """The Houdini hotkey symbol of a token of this state (needs the interface)."""
    import viewerstate.utils as su
    return su.hotkeyContextForState(STATE_NAME,hou.lopNodeTypeCategory())+'.'+token

def hk_ref(token):
    """How the HUD names a hotkey: the symbol with a $ (the HUD expands it into whatever key is bound), else the default key."""
    try:
        import viewerstate.utils as su
        return su.hudHotkeyRef(hk_symbol(token))
    except Exception:return KEYS[token]

def hk_is(key,token):
    """True when a key event (a hotkey symbol or a key string) is the hotkey token."""
    try:match=bool(hou.hotkeys.isKeyMatch(key,hk_symbol(token)))                      # Houdini hands the state the hotkey symbol of the binding the key matched (rebinding works)
    except Exception:match=False
    return match or key==KEYS[token]                                                  # the default key string also works (no interface, or a hotkey that was not registered)

def hud_template(mode,brush,icon='MISC_paint',level='standard',rows=None):
    """The HUD panel for one mode and brush at one level (minimal: the brush, one hint and its main value; standard: its hints and values; expanded: everything). rows: the hint rows of a sculpt brush
    (BrushCore's bc_hud_rows). The panel is built again when the brush or the level changes; values are written only when they change."""
    pages={'place':[{'label':'Click and drag to place','key':'LMB'},{'label':'Cycle through the working set','key':'mousewheel'},{'label':'Scale','key':'Shift LMB'},
                    {'label':'Orient to increments','key':'Ctrl LMB'},{'label':'Orient freely','key':'Ctrl Shift LMB'}],
           'delete':[{'label':'Delete the stamps under the mouse','key':'LMB'}],
           'paint':[{'label':'Paint stamps','key':'LMB drag'},{'label':'Erase stamps','key':'Ctrl LMB drag'},{'label':'Brush radius','key':'Shift mousewheel'},{'label':'Density','key':'Ctrl mousewheel'},{'label':'Cycle through the working set','key':'mousewheel'},{'label':'Strength','key':'-  ='}],
           'group':[{'label':'Click and drag to place the group','key':'LMB'},{'label':'Scale','key':'Shift LMB'},{'label':'Orient to increments','key':'Ctrl LMB'},{'label':'Layout from the selected stamps (Edit mode)','key':hk_ref('group')}],
           'edit':[{'label':'Select (add or remove)','key':'LMB (Shift LMB)'},{'label':'Box select','key':'LMB drag'},{'label':'Hold when dragging to duplicate','key':hk_ref('duplicate')},{'label':'Delete selection','key':hk_ref('delete')},
                   {'label':'Next material of the selection','key':hk_ref('material')}]}
    key='edit' if mode==1 else BRUSH_KEYS[min(max(int(brush),0),len(BRUSH_KEYS)-1)]
    hints=[{'label':a,'key':b} for a,b in rows] if (rows is not None and key not in pages) else pages.get(key,[])
    if level=='minimal':hints=hints[:1]
    vals=VALUES.get(key,(('v_brush',),('v_brush','v_count'),('v_proto','v_sel')));ids=list(vals[0]) if level=='minimal' else list(vals[1])+(list(vals[2]) if level=='expanded' else [])
    out=[{'id':'mode','label':'Mode','key':hk_ref('togglemode')}]
    if level!='minimal':out.append({'id':'mode_g','type':'choicegraph','count':2})
    out+=[{'type':'divider','label':'Edit' if mode==1 else BRUSHES[BRUSH_KEYS.index(key)]+' Brush'}]+hints+[{'type':'divider','label':'Values'}]+[{'id':i,'label':VALUE_LABELS[i]} for i in ids]
    if level!='minimal':out+=[{'type':'divider','label':'Common'},{'label':'Brush Menu','key':hk_ref('brushselector')},{'label':'Hints (minimal, standard, expanded, hidden)','key':hk_ref('hud')}]
    if level=='expanded':out+=[{'label':'Brush Options Menu','key':hk_ref('brushradial')},{'label':'Cancel the stroke','key':'Esc'}]
    return {'title':'Arraytron Stamp','desc':'tool','icon':icon,'rows':out}

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
            try:self.scene_viewer.setPromptMessage('Arraytron Stamp error: %s'%exc,hou.promptMessageType.Error)
            except Exception:pass
            return False
    run.__name__=func.__name__;return run

def _rot(q,v):
    """The vector v turned by the quaternion q (x, y, z, w)."""
    q=np.asarray(q,dtype=np.float64);u=q[:3];v=np.asarray(v,dtype=np.float64);return v+2*q[3]*np.cross(u,v)+2*np.cross(u,np.cross(u,v))

def _ray(vp,x,y):
    """(origin, direction) of the ray through a viewport pixel. hou.GeometryViewport.mapToWorld returns (direction, origin): read the other way round, the box select was drawn around the world origin."""
    d,o=vp.mapToWorld(x,y);return np.array(tuple(o),dtype=np.float64),np.array(tuple(d),dtype=np.float64)

def _lines(geo,segments):
    """Add open polylines (lists of points) to a hou.Geometry in one go."""
    pts=[p for s in segments for p in s];made=geo.createPoints([tuple(float(c) for c in p) for p in pts]);k=0
    for s in segments:
        poly=geo.createPolygon(is_closed=False)
        for _ in s:poly.addVertex(made[k]);k+=1
    return geo

def _box(lo,hi,center,q,scale):
    """The 12 edges of the prototype box placed like the stamp (scale: a number or three)."""
    c=[np.array([x,y,z]) for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])];w=[center+_rot(q,p*scale) for p in c]
    return [[w[a],w[b]] for a,b in ((0,1),(2,3),(4,5),(6,7),(0,2),(1,3),(4,6),(5,7),(0,4),(1,5),(2,6),(3,7))]

class StampState(object):
    def __init__(self,state_name,scene_viewer):
        self.state_name=state_name;self.scene_viewer=scene_viewer;self.node=None;self.surf=None;self.surf_key=None;self.hit=None;self.drag=None;self.last=0.0;self.under=None
        self.bounds=None;self.bounds_key=None;self.hud=None;self.hudkey=None;self.labels=[];self.press=None;self.rect=None;self.sweep=None;self.duplicate=False
        self.snap_rows=None;self.snap_lines=None;self.snap_sel=None;self.snap_pivot=None;self.handle_on=None;self.editing=False
        self.stroke=None;self.gpool=[];self.entries=None;self.entries_key=None;self.ghosts={};self.ghost_key=None;self.ghost_alpha=None;self.ring_color=None;self.edit_key=None;self.watching=None
        def lines(name,color,width):
            d=hou.GeometryDrawable(scene_viewer,hou.drawableGeometryType.Line,name);d.setParams({'color1':hou.Vector4(color),'line_width':width});return d
        self.marker=lines('arraytron_stamp_marker',GREEN,2.0);self.box=lines('arraytron_stamp_box',GREY,1.5);self.dial=lines('arraytron_stamp_dial',WHITE,1.5)
        self.sel=lines('arraytron_stamp_selected',YELLOW,2.0);self.ring_d=lines('arraytron_stamp_profile_density',BLUE,1.6);self.ring_s=lines('arraytron_stamp_profile_scale',ORANGE,1.6);self.gone=lines('arraytron_stamp_delete',RED,2.0);self.frame=lines('arraytron_stamp_rect',BLUE,1.5)
        self.cursor=lines('arraytron_stamp_cursor',GREEN,2.0);self.cursor_color=None
        self.ghost=hou.GeometryDrawable(scene_viewer,hou.drawableGeometryType.Face,'arraytron_stamp_ghost');self.ghost.setParams({'color1':hou.Vector4((1.0,1.0,1.0,0.7)),'use_cd':True,'fade_factor':0.35})
        self.text=hou.TextDrawable(scene_viewer,'arraytron_stamp_text')

    # ----- helpers
    def _m(self):return self.node.hdaModule()
    def _set(self,name,value,lo,hi):self.node.parm(name).set(min(max(value,lo),hi))
    def _mode(self):return 1 if self.node.evalParm('mode1')==1 else 0
    def _brush(self):return min(max(int(self.node.evalParm('brush')),0),len(BRUSHES)-1)
    def _surface(self):
        """The surface, built again when Place On changed (a mesh is turned into a ray-cast geometry once)."""
        key=self.node.evalParm('target').strip()
        if self.surf is None or key!=self.surf_key:
            self.surf=None;self.surf_key=key
            try:self.surf=self._m().stamp_surface(self.node);self.scene_viewer.clearPromptMessage()
            except hou.Error as exc:self.scene_viewer.setPromptMessage('Arraytron Stamp: %s'%exc,hou.promptMessageType.Error)
        return self.surf
    def _bounds(self,row):
        """The box of a prototype line, read once per Prototype Bank."""
        key=self._m().bank_key(self.node)
        if self.bounds is None or key!=self.bounds_key:
            self.bounds_key=key
            try:self.bounds=self._m().stamp_proto_bounds(self.node)
            except Exception:self.bounds={}                                                  # an unresolved bank: a unit box
        return self.bounds.get(row) or (next(iter(self.bounds.values())) if self.bounds else (np.full(3,-0.5),np.full(3,0.5)))
    def _entries(self):
        """The resolved bank (read again only when it changed); None when it cannot be resolved (the box is shown instead of the ghost)."""
        key=self._m().bank_key(self.node)
        if self.entries_key!=key:
            self.entries_key=key;self.ghosts={};self.ghost_key=None
            try:self.entries=self._m().stamp_entries(self.node)
            except Exception:self.entries=None
        return self.entries
    def _tint(self,row):
        """(colour, amount) of the slot colour of a bank row over its ghost; (None, 0) when Slot Colors is off."""
        m=self._m();a=m.stamp_slot_amount(self.node)
        if a<=0:return None,0.0
        seed=int(self.node.evalParm('slotcolor_seed')) if self.node.parm('slotcolor_seed') is not None else 0
        return m.stamp_slot_color(row,seed),a
    def _slot_box_color(self,row,alpha=0.8):
        """The colour of the box drawn for the next stamp when it has no ghost: its slot colour, else grey."""
        col,a=self._tint(row)
        return GREY if col is None else (col[0],col[1],col[2],alpha)
    def _ghost_geo(self,entries,row,child):
        """The geometry of a prototype for the ghost (the prototype itself, decimated and lit, its slot colour over it), built once per bank row, child and slot colour."""
        tint=self._tint(row);key=(self.entries_key,row,child,tint)
        if key not in self.ghosts:
            geo=False
            try:
                e=[e for e in entries if e['row']==row][0];arrays=self._m().stamp_ghost_arrays(self.node,e['srcs'][child])
                if arrays is not None:geo=self._m().stamp_ghost_geo(arrays,tint[0],tint[1])
            except Exception:geo=False
            if len(self.ghosts)>64:self.ghosts={}
            self.ghosts[key]=geo
        return self.ghosts[key] or None
    def _show_ghost(self,nx,pos,nrm,alpha):
        """The next stamp as the prototype itself at its place (rotation, scale, the bank row's own Scale and Rotation Offset). False when there is no geometry for it (the box is drawn instead)."""
        entries=self._entries()
        if not entries:return False
        try:row,child,xf=self._m().stamp_next_xform(self.node,nx,pos,nrm,entries)
        except Exception:return False
        geo=self._ghost_geo(entries,row,child)
        if geo is None:return False
        if self.ghost_key is None or self.ghost_key[0] is not geo:self.ghost.setGeometry(geo);self.ghost_key=(geo,(row,child))          # a new row, child or slot colour: another geometry
        if alpha!=self.ghost_alpha:self.ghost.setParams({'color1':hou.Vector4((1.0,1.0,1.0,alpha)),'use_cd':True,'fade_factor':0.35});self.ghost_alpha=alpha
        self.ghost.setTransform(xf);self.ghost.show(True);return True
    def _hide_pool(self):
        for d in self.gpool:d[0].show(False)
    def _pool(self,i):
        """The i-th drawable of the group preview (made once, reused)."""
        while len(self.gpool)<=i:
            d=hou.GeometryDrawable(self.scene_viewer,hou.drawableGeometryType.Face,'arraytron_stamp_group_%d'%len(self.gpool));d.setParams({'color1':hou.Vector4((1.0,1.0,1.0,0.7)),'use_cd':True,'fade_factor':0.35});self.gpool.append([d,None,0.7])
        return self.gpool[i]
    def _bound_map(self):
        self._bounds(0);return self.bounds or {}
    def _group_radius(self,nrm):
        """The footprint of the whole group (what the drag scales against)."""
        m=self._m();return m.stamp_group_items(self.node,m.stamp_next(self.node,nrm)['n'],self._bound_map())[1]
    def _show_group(self,nx,pos,nrm,alpha,color):
        """The Group brush preview: every member as the prototype itself (at most MAX_GHOSTS; the rest and the ones without geometry as boxes), placed by the same function that makes the stamps."""
        node=self.node;m=self._m();items,radius=m.stamp_group_items(node,nx['n'],self._bound_map());placed=m.stamp_group_place(node,items,radius,nx,pos,nrm,self.surf,self._bound_map());entries=self._entries();used=0;segs=[]
        for j,p in enumerate(placed):
            ok=False
            if entries and used<MAX_GHOSTS:
                try:
                    row,child,xf=m.stamp_next_xform(node,dict(n=nx['n']+j,proto=p['proto'],scale=p['scale'],quat=p['quat']),p['pos'],(0.0,0.0,0.0),entries);geo=self._ghost_geo(entries,row,child)
                    if geo is not None:
                        d=self._pool(used)
                        if d[1] is not geo:d[0].setGeometry(geo);d[1]=geo
                        if d[2]!=alpha:d[0].setParams({'color1':hou.Vector4((1.0,1.0,1.0,alpha)),'use_cd':True,'fade_factor':0.35});d[2]=alpha
                        d[0].setTransform(xf);d[0].show(True);used+=1;ok=True
                except Exception:ok=False
            if not ok:lo,hi=self._bounds(p['proto']);segs+=_box(lo,hi,p['pos'],p['quat'],p['scale']);boxrow=p['proto']
        for d in self.gpool[used:]:d[0].show(False)
        self.ghost.show(False)
        if segs:
            if color==GREY:color=self._slot_box_color(boxrow)                                                       # boxes of the members without a ghost: the slot colour (of the last one)
            self.box.setParams({'color1':hou.Vector4(color)});self.box.setGeometry(_lines(hou.Geometry(),segs));self.box.show(True)
        else:self.box.show(False)
    def _frame(self,nrm):
        """up, forward (yaw 0) and right of a stamp on this normal (Align To Surface)."""
        a=self._m().stamp_align(nrm,self.node.evalParm('align'));return _rot(a,(0.0,1.0,0.0)),_rot(a,(0.0,0.0,1.0)),_rot(a,(1.0,0.0,0.0))
    def _rows(self):return self._m().stamp_rows(self.node.evalParm('stamps'))
    def _selection(self,count=None):return self._m().stamp_get_selection(self.node,count)
    def _prefs(self):
        """The brush preferences shared with Arraytron (HUD level ...): BrushCore's small JSON file in the Houdini user folder."""
        if getattr(self,'prefs',None) is None:
            try:
                import os
                self.prefs_path=os.environ.get('ARRAYTRON_BRUSH_PREFS') or self._m().bc_prefs_path(hou.homeHoudiniDirectory());self.prefs=self._m().bc_prefs_load(self.prefs_path)
            except Exception:self.prefs_path=None;self.prefs={'hud':'standard'}
        return self.prefs
    def _cycle_hud(self):
        p=self._prefs();p['hud']=self._m().bc_next_hud(p.get('hud','standard'))
        if getattr(self,'prefs_path',None):self._m().bc_prefs_save(self.prefs_path,p)
        self.hud=None;self._hud()
        try:self.scene_viewer.setPromptMessage('Arraytron Stamp: hints %s'%p['hud'])
        except Exception:pass
    def _hud(self,nx=None):
        """The HUD panel: the hints of the mode and the brush at the HUD level (H), the values when they change."""
        n=self.node;mode=self._mode();brush=self._brush();level=self._prefs().get('hud','standard');m=self._m()
        if getattr(self,'hud_for',None)!=(mode,brush,level):self.hud=None;self.hud_for=(mode,brush,level)                  # the brush changed elsewhere (the shelf, a script): the panel of that brush
        if self.hud is None:
            try:
                if level=='hidden':self.scene_viewer.hudInfo(show=False)
                else:
                    key=BRUSH_KEYS[brush];rows=m.bc_hud_rows(key,level) if (mode==0 and key in m.BC_BRUSHES) else None;self.hud_tmpl=hud_template(mode,brush,self._icon(),level,rows)
                    self.scene_viewer.hudInfo(template=self.hud_tmpl);self.scene_viewer.hudInfo(show=True)
            except Exception:
                if STRICT:raise
            self.hud={};self.hudkey=None
        if level=='hidden':return
        labels={l[0]:l for l in m.stamp_labels(n)}
        if nx is None:nx=dict(proto=n.evalParm('proto') or next(iter(labels),1),scale=n.evalParm('scale'),yaw=n.evalParm('yaw'))
        label=labels[nx['proto']][1] if nx['proto'] in labels else '-';ws=m.stamp_workset(n);ids={r.get('id') for r in getattr(self,'hud_tmpl',{'rows':[]})['rows']}
        values={'mode':MODES[mode]+(' / '+BRUSHES[brush] if mode==0 else ''),'mode_g':mode,'v_proto':'%d  %s'%(nx['proto'],label)+('  (random)' if n.evalParm('protorand') and self.drag is None else '')+('  [set of %d]'%len(ws) if len(ws)>1 else ''),
                'v_scale':'%.3g'%nx['scale'],'v_rot':'%.1f deg'%nx['yaw'],'v_count':str(m.stamp_count(n.evalParm('stamps'))),'v_sel':str(len(self._selection())),
                'v_paint':'%.3g / %.3g / %.2g'%(n.evalParm('paint_radius'),n.evalParm('paint_density'),n.evalParm('paint_strength') if n.parm('paint_strength') is not None else 1.0)}
        if 'v_mat' in ids:values['v_mat']=m.stamp_material_info(n,nx if 'mat' in nx else None)
        if 'v_falloff' in ids:values['v_falloff']=m.stamp_falloff_text(n)
        if 'v_brush' in ids:values['v_brush']='%.3g / %.2g / %.2g'%(n.evalParm('paint_radius'),n.evalParm('paint_strength') if n.parm('paint_strength') is not None else 1.0,n.evalParm('brush_amount') if n.parm('brush_amount') is not None else 0.0)
        if 'v_clone' in ids:values['v_clone']=m.stamp_clone_info(n) if n.parm('clone_src') is not None else '-'
        if brush==3 and mode==0:values['v_proto']=m.stamp_group_info(n)[7:]
        values={k:v for k,v in values.items() if k in ids}
        if values!=self.hudkey:
            self.hudkey=values
            try:self.scene_viewer.hudInfo(values=values)
            except Exception:pass
    def _icon(self):
        """The icon of the node type (the seal with a stamp, an opdef: path), for the HUD."""
        try:return self.node.type().definition().icon() or 'MISC_paint'
        except Exception:return 'MISC_paint'
    def _hide(self):
        for d in (self.marker,self.box,self.dial,self.sel,self.gone,self.frame,self.text,self.ghost,self.ring_d,self.ring_s,self.cursor):d.show(False)
        self._hide_pool();self.labels=[];self.edit_key=None
    def _clear_hover(self):
        for d in (self.marker,self.box,self.dial,self.text,self.ghost,self.ring_d,self.ring_s,self.cursor):d.show(False)
        self._hide_pool();self.labels=[]
    def _boxes(self,drawable,rows,indices):
        """Draw the boxes of some stamps (their prototype's box, their own rotation and scale; at most MAX_BOXES), all at once: the corners of every box in numpy, one geometry of open lines."""
        idx=np.asarray(indices,dtype=np.int64).ravel()[:MAX_BOXES] if len(indices) else np.zeros(0,dtype=np.int64);idx=idx[(idx>=0)&(idx<len(rows))]
        if not len(idx):drawable.show(False);return
        m=self._m();bmap=self._bound_map();first=next(iter(bmap.values())) if bmap else (np.full(3,-0.5),np.full(3,0.5));r=rows[idx]
        box={int(p):bmap.get(int(p),first) for p in np.unique(r[:,9])};lo=np.array([box[int(p)][0] for p in r[:,9]],dtype=np.float64);hi=np.array([box[int(p)][1] for p in r[:,9]],dtype=np.float64)
        c=np.stack([np.stack([np.where(k&4,hi[:,0],lo[:,0]),np.where(k&2,hi[:,1],lo[:,1]),np.where(k&1,hi[:,2],lo[:,2])],-1) for k in range(8)],1)        # (n, 8, 3), the order of _box
        world=np.einsum('nij,nkj->nki',m._quat_matrices(m.stamp_quat(r[:,3:6])),c*r[:,None,6:9])+r[:,None,0:3]
        geo=hou.Geometry();geo.createPoints([tuple(p) for p in world.reshape(-1,3).tolist()]);geo.createPolygons((BOX_EDGES[None]+8*np.arange(len(idx))[:,None,None]).reshape(-1,2).tolist(),False)
        drawable.setGeometry(geo);drawable.show(True)
    def _show_hover(self,pos,nrm,t):
        """Place brush: under the mouse a small ring and the box of the next stamp (its prototype, rotation and scale, with the random draws of the click)."""
        m=self._m();node=self.node;nx=m.stamp_next(node,nrm,snap_rot=node.evalParm('snaprot') or None,group=self._brush()==3);u,f,r=self._frame(nrm);lift=u*0.005;p0=pos+lift
        rr=max(t*0.012,1e-3);ring=[p0+rr*(np.cos(a)*f+np.sin(a)*r) for a in np.linspace(0,2*np.pi,25)]
        self.marker.setGeometry(_lines(hou.Geometry(),[ring,[p0,p0+_rot(nx['quat'],(0.0,0.0,1.0))*rr*3.0]]));self.marker.show(True)
        sit=m.stamp_sit(node,nx,self._bound_map());lp=pos+sit
        if self._brush()==3:self._show_group(nx,pos,nrm,0.7,GREY)
        elif self._show_ghost(nx,lp,nrm,0.7):self.box.show(False)
        else:
            self.ghost.show(False)
            lo,hi=self._bounds(nx['proto']);center=lp+nrm*node.evalParm('offset')
            self.box.setParams({'color1':hou.Vector4(self._slot_box_color(nx['proto']))});self.box.setGeometry(_lines(hou.Geometry(),_box(lo,hi,center,nx['quat'],nx['scale'])));self.box.show(True)
        self.dial.show(False);self.text.show(False);self.labels=[];self._hud(nx)
    def _show_drag(self):
        """While dragging: the dial (a ring through the mouse, ticks every 10 degrees, the spoke to the mouse), the box of the stamp as it will be, the scale and angle by the mouse."""
        node=self.node;m=self._m();d=self.drag;pos,nrm,t=d['hit'];u,f,r=d['frame'];p0=pos+u*0.005;R=max(d['dist'],1e-4)
        ring=[p0+R*(np.cos(a)*f+np.sin(a)*r) for a in np.linspace(0,2*np.pi,RING+1)];segs=[ring]
        for k in range(TICKS):
            a=2*np.pi*k/TICKS;e=np.cos(a)*f+np.sin(a)*r;L=R*(0.16 if k%3==0 else 0.08);segs.append([p0+e*R,p0+e*(R+L)])
        yaw=np.radians(d['yaw']);e=np.cos(yaw)*f+np.sin(yaw)*r;segs.append([p0,p0+e*R]);segs.append([p0,p0+f*R*0.25])
        self.dial.setGeometry(_lines(hou.Geometry(),segs));self.dial.show(True)
        nx=m.stamp_next(node,nrm,yaw=d['yaw'] if d['set_yaw'] else None,scale=d['scale'] if d['set_scale'] else None,proto=d['proto'],snap_rot=node.evalParm('snaprot') or None,group=self._brush()==3)
        lp=pos+m.stamp_sit(node,nx,self._bound_map())
        if self._brush()==3:self._show_group(nx,pos,nrm,0.9,YELLOW)
        elif self._show_ghost(nx,lp,nrm,0.9):self.box.show(False)
        else:
            self.ghost.show(False)
            lo,hi=self._bounds(nx['proto']);self.box.setParams({'color1':hou.Vector4(YELLOW)});self.box.setGeometry(_lines(hou.Geometry(),_box(lo,hi,lp+nrm*node.evalParm('offset'),nx['quat'],nx['scale'])));self.box.show(True)
        self.marker.show(False);self.labels=[(p0+e*R,'%.2f    %.1f°'%(d['scale'] if d['set_scale'] else nx['scale'],d['yaw']%360.0 if d['set_yaw'] else nx['yaw']%360.0))];self.text.show(True);self._hud(nx)
    def _commit(self,**kw):
        if time.time()-self.last<0.25:return                                              # a click can arrive as Start, Changed and Picked: place once
        self.last=time.time();pos,nrm,t=self.hit
        if self._brush()==3:
            kw.pop('proto',None);self._m().stamp_group_add(self.node,self.surf,pos,nrm,snap_rot=self.node.evalParm('snaprot') or None,bounds=self._bound_map(),**kw);return
        self._m().stamp_add(self.node,pos,nrm,snap_rot=self.node.evalParm('snaprot') or None,bounds=self._bound_map(),**kw)

    # ----- the handle of the Edit mode
    def _show_handle(self,show):
        if show!=self.handle_on:
            try:self.scene_viewer.showHandle('edit_handle',bool(show));self.handle_on=show
            except Exception:pass
    def _refresh_edit(self,rows=None):
        """Edit mode: the boxes of the selection, the handle at its centre. Built again only when the stamps, the selection or the bank changed, not on every mouse move (it was the lag of the Edit mode
        with many stamps selected)."""
        n=self.node;mode=self._mode();key=(mode,n.evalParm('stamps'),n.evalParm('selection'),self._m().bank_key(n)) if mode==1 else (mode,)
        if key==self.edit_key:return
        self.edit_key=key
        if mode==1:
            rows=self._rows() if rows is None else rows;sel=self._selection(len(rows));self._boxes(self.sel,rows,sel);self._show_handle(len(sel)>0)
        else:self.sel.show(False);self._show_handle(False)
    def _watch(self,on):
        """While the tool is on: a selection or stamps changed elsewhere (the table, the Edit tab buttons) is drawn at once, not at the next mouse move."""
        if self.watching is not None:
            try:self.watching[0].removeEventCallback((hou.nodeEventType.ParmTupleChanged,),self.watching[1])
            except Exception:pass
            self.watching=None
        if not on or self.node is None:return
        def changed(**kw):
            pt=kw.get('parm_tuple')
            if self.editing or (pt is not None and pt.name() not in ('selection','stamps')):return
            try:self._refresh_edit();self._hud();self.scene_viewer.curViewport().draw()
            except Exception:pass
        try:self.node.addEventCallback((hou.nodeEventType.ParmTupleChanged,),changed);self.watching=(self.node,changed)
        except Exception:self.watching=None
    @guarded
    def onStateToHandle(self,kwargs):
        if kwargs.get('handle')!='edit_handle' or self.node is None:return
        p=kwargs['parms'];rows=self._rows();sel=self._selection(len(rows))
        for k in HANDLE_ZERO:p[k]=0
        for k in ('sx','sy','sz'):p[k]=1
        c=self._m().stamp_selection_pivot(rows,sel);p['px'],p['py'],p['pz']=float(c[0]),float(c[1]),float(c[2]);p['onoff']=len(sel)>0
    @guarded
    def onBeginHandleToState(self,kwargs):
        if kwargs.get('handle','edit_handle')!='edit_handle' or self.node is None:return
        m=self._m();rows=self._rows();sel=self._selection(len(rows))
        if self.duplicate and len(sel):sel=m.stamp_duplicate(self.node,sel);rows=self._rows()                   # Z held: the copies are the ones that move
        self.snap_rows=rows;self.snap_lines=m.stamp_lines(self.node.evalParm('stamps'));self.snap_sel=np.array(sel,dtype=np.int64);self.editing=True
        try:self.scene_viewer.beginStateUndo('Arraytron Stamp: edit')
        except Exception:pass
    @guarded
    def onHandleToState(self,kwargs):
        if kwargs.get('handle')!='edit_handle' or self.node is None or not self.editing or not len(self.snap_sel):return
        m=self._m();d=m.stamp_handle_delta(kwargs['parms']);new=m.stamp_delta_rows(self.snap_rows[self.snap_sel],d);lines=list(self.snap_lines);rows=self.snap_rows.copy();rows[self.snap_sel]=new
        for i in self.snap_sel:m.stamp_write_row(lines,rows,int(i))
        self.node.parm('stamps').set('\n'.join(lines));self._boxes(self.sel,rows,self.snap_sel)
    @guarded
    def onEndHandleToState(self,kwargs):
        self.editing=False
        try:self.scene_viewer.endStateUndo()
        except Exception:pass
        self.snap_rows=None;self._refresh_edit();self._hud()

    # ----- the popup menus (C and B)
    def _popup(self,items):
        """A menu at the cursor: [(label, callback, checked or None)]; a None label is a separator. Nothing happens without Qt (the tests)."""
        try:
            try:from PySide6 import QtWidgets,QtGui
            except ImportError:from PySide2 import QtWidgets,QtGui
            if QtWidgets.QApplication.instance() is None:return                                     # no interface (hython): a Qt widget without an application would abort the process
            menu=QtWidgets.QMenu()
            for label,fn,checked in items:
                if label is None:menu.addSeparator();continue
                act=menu.addAction(label)
                if checked is not None:act.setCheckable(True);act.setChecked(bool(checked))
                act.triggered.connect(lambda _=False,fn=fn:fn())
            menu.exec(QtGui.QCursor.pos()) if hasattr(menu,'exec') else menu.exec_(QtGui.QCursor.pos())
        except Exception:pass
    def radial_menu(self):
        """C: Houdini's radial menu (like the Layout tool's brush selector): Paint north, the sculpt brushes around it, More (Orient, Place, Delete, Group, Edit mode) south. Without a radial menu (an older
        build, the tests) the popup menu at the cursor."""
        m=self._m();main,more=m.bc_radial_layout(set(BRUSH_KEYS),('place','delete','group'))
        try:
            import radialmenu
            def entry(key):
                i=BRUSH_KEYS.index(key);return {'type':'script_action','label':BRUSHES[i],'script':lambda i=i,**kw:self._set_brush(i),'check':lambda i=i,**kw:self._brush()==i and self._mode()==0}
            sub={d:entry(k) for d,k in zip(('n','ne','e','se','sw','w','nw'),[k for k in more if k in BRUSH_KEYS][:7])}
            sub['s']={'type':'script_action','label':'Edit Mode','script':lambda **kw:self._set_mode(1)}
            top={d:entry(k) for d,k in main.items()}
            top['s']={'type':'script_submenu','label':'More','script':lambda **kw:radialmenu.setRadialMenu(sub)}
            item=hou.ui.createRadialItem(True,True);item.setLabel('Arraytron Stamp Brushes');item.setActionCallback(lambda **kw:radialmenu.setRadialMenu(top))
            self.scene_viewer.displayRadialMenu(item);return True
        except Exception:
            self._popup(self.brush_menu());return False
    def brush_menu(self):
        n=self.node;items=[]
        for i,name in enumerate(BRUSHES):items.append((name+' brush',lambda i=i:self._set_brush(i),self._brush()==i and self._mode()==0))
        items.append((None,None,None));items.append(('Edit mode',lambda:self._set_mode(1),self._mode()==1));return items
    def _group_capture(self):
        self._m().stamp_group_capture_selected(self.node);self.hud=None;self._clear_hover();self._refresh_edit();self._hud()
    def options_menu(self):
        n=self.node;m=self._m();items=[('Align To Surface',lambda:n.parm('align').set(0.0 if n.evalParm('align')>0 else 1.0),n.evalParm('align')>0),('Random Prototype',lambda:n.parm('protorand').set(0 if n.evalParm('protorand') else 1),n.evalParm('protorand')),
                           ('Drag Sets Rotation And Scale',lambda:n.parm('dragset').set(0 if n.evalParm('dragset') else 1),n.evalParm('dragset')),('Place On Stamps',lambda:n.parm('onstamps').set(0 if n.evalParm('onstamps') else 1),n.evalParm('onstamps')),
                           (None,None,None),('Group: Set Layout From Selected Stamps',lambda:self._group_capture(),None),('Group: Reset To Radial Layout',lambda:m.stamp_group_reset(n),None),
                           (None,None,None),('Material: Next For Selected Stamps',lambda:m.stamp_material_next_selected(n),None),('Material: Random For Selected Stamps',lambda:m.stamp_material_random_selected(n),None),
                           ("Material: Prototype's Own For Selected Stamps",lambda:m.stamp_material_own_selected(n),None),
                           (None,None,None),('Snap Rotation 15 degrees',lambda:n.parm('snaprot').set(0.0 if n.evalParm('snaprot') else 15.0),n.evalParm('snaprot')>0)]
        return items
    def _set_brush(self,i):
        with hou.undos.disabler():
            self.node.parm('brush').set(i);self.node.parm('mode1').set(0)
        self.hud=None;self._refresh_edit();self._hud()
    def _set_mode(self,i):
        with hou.undos.disabler():self.node.parm('mode1').set(i)
        self.hud=None;self._clear_hover();self._refresh_edit();self._hud()

    # ----- state callbacks
    @guarded
    def onEnter(self,kwargs):
        self.node=kwargs['node'];self.surf=None;self.surf_key=None;self.hit=None;self.drag=None;self.bounds=None;self.hud=None;self.handle_on=None;self.press=None;self.sweep=None;self.edit_key=None
        self._surface();self._hud();self._refresh_edit();self._watch(True)
    @guarded
    def onResume(self,kwargs):
        self.surf=None;self.bounds=None;self.hud=None;self.handle_on=None;self.edit_key=None
        if self.node is not None:self._surface();self._hud();self._refresh_edit()
    @guarded
    def onInterrupt(self,kwargs):
        if self.stroke is not None:self._end_stroke()
        self._hide();self._show_handle(False)
    @guarded
    def onExit(self,kwargs):
        if self.stroke is not None:self._end_stroke()
        self._watch(False);self._hide();self._show_handle(False);self.hit=None;self.drag=None;self.press=None;self.sweep=None;self.surf=None;self.scene_viewer.clearPromptMessage()
    @guarded
    def onDraw(self,kwargs):
        handle=kwargs['draw_handle']
        for d in [self.ghost]+[g[0] for g in self.gpool]+[self.box,self.dial,self.marker,self.cursor,self.ring_d,self.ring_s,self.sel,self.gone,self.frame]:d.draw(handle)
        if self.labels:
            vp=self.scene_viewer.curViewport()
            for world,text in self.labels:
                s=vp.mapToScreen(hou.Vector3(tuple(float(c) for c in world)))
                self.text.draw(handle,{'text':text,'translate':hou.Vector3(s[0]+14.0,s[1]+6.0,0.0),'color1':hou.Color(1.0,1.0,1.0),'origin':hou.drawableTextOrigin.BottomLeft})

    # ----- the mouse
    @guarded
    def onMouseEvent(self,kwargs):
        if self.node is None:return False
        ev=kwargs['ui_event'];dev=ev.device();reason=ev.reason()
        if dev.isMiddleButton() or dev.isAltKey():return False                        # let the camera handle navigation
        surf=self._surface()
        if surf is None:return True
        mode=self._mode();brush=self._brush()
        if mode==1 and self.press is not None and reason==hou.uiEventReason.Active:return self._edit_mouse(ev,dev,reason,surf,None,None)   # a box select growing: only its rectangle, nothing else is read
        if mode==1 or brush in (0,1,3):surf.update(self.node,force=(mode==1 or brush==1))      # the stamps are surfaces too (a string compare when nothing changed); Delete and Edit always see them. Paint, the sculpt brushes and Clone cast onto Place On only: their live writes never rebuild the stamps' ray-cast data
        try:origin,direction=ev.ray()
        except Exception:origin,direction=_ray(ev.curViewport(),dev.mouseX(),dev.mouseY())
        o=np.array(origin,dtype=float);d=np.array(direction,dtype=float);d=d/np.linalg.norm(d)
        if mode==1:return self._edit_mouse(ev,dev,reason,surf,o,d)
        if brush==1:return self._delete_mouse(ev,dev,reason,surf,o,d)
        if brush==2:return self._paint_mouse(ev,dev,reason,surf,o,d)
        if brush in SCULPT:return self._sculpt_mouse(ev,dev,reason,surf,o,d)
        if brush==CLONE:return self._clone_mouse(ev,dev,reason,surf,o,d)
        return self._place_mouse(ev,dev,reason,surf,o,d)
    def _place_mouse(self,ev,dev,reason,surf,o,d):
        node=self.node;m=self._m();left=dev.isLeftButton();R=hou.uiEventReason;self.sweep=None;self.press=None;self.sel.show(False);self.gone.show(False);self.frame.show(False);self._show_handle(False)
        if self.drag is None:
            h=surf.hit(o,d);self.hit=None
            if h is not None:
                point,nrm=surf.snapped(h[0],h[1],node.evalParm('snap'));self.hit=(point,nrm,h[2])
        if left and reason==R.Start and self.hit is not None:
            if node.evalParm('dragset'):
                pos,nrm,t=self.hit;self.drag=dict(x=dev.mouseX(),y=dev.mouseY(),hit=self.hit,frame=self._frame(nrm),yaw=0.0,scale=1.0,dist=0.0,moved=False,set_yaw=True,set_scale=True,proto=m.stamp_next(node,nrm)['proto'])
            else:self._commit()
        elif self.drag is not None and reason==R.Active:
            dr=self.drag;pos,nrm,t=dr['hit'];u,f,r=dr['frame'];den=d@u
            if abs(dev.mouseX()-dr['x'])+abs(dev.mouseY()-dr['y'])>=DRAG_PIXELS:dr['moved']=True
            shift=dev.isShiftKey();ctrl=dev.isCtrlKey()
            dr['set_yaw']=(not shift) or ctrl;dr['set_scale']=not ctrl                           # Shift: scale only | Ctrl: orient only | Ctrl+Shift: orient only, freely | none: both
            if dr['moved'] and abs(den)>1e-9:
                point=o+d*(((pos-o)@u)/den)                                                   # the mouse on the plane of the stamp
                snap=0.0 if (ctrl and shift) else (node.evalParm('snaprot') or (15.0 if ctrl else 0.0))   # Ctrl: orient to increments (the Snap Rotation, else 15 degrees); Ctrl+Shift: freely
                dr['yaw'],dr['scale'],dr['dist']=m.stamp_drag(pos,u,f,r,point,self._group_radius(nrm) if self._brush()==3 else m.stamp_footprint(self._bounds(dr['proto'])),snap)
        elif self.drag is not None and reason in (R.Changed,R.Picked):
            dr=self.drag;self.drag=None;self.hit=dr['hit']
            if dr['moved']:self._commit(yaw=dr['yaw'] if dr['set_yaw'] else None,scale=dr['scale'] if dr['set_scale'] else None,proto=dr['proto'])
            else:self._commit()
        elif left and reason==R.Picked and self.hit is not None:self._commit()
        if self.drag is not None and self.drag['moved']:self._show_drag()
        elif (self.drag['hit'] if self.drag is not None else self.hit) is not None:self._show_hover(*(self.drag['hit'] if self.drag is not None else self.hit))
        else:self._clear_hover();self._hud()
        return True
    def _paint_mouse(self,ev,dev,reason,surf,o,d):
        """Paint brush: a ring of the radius on the surface under the mouse; LMB drag paints stamps (one dab every 35% of the radius), Ctrl + LMB drag erases; one undo step per stroke."""
        node=self.node;m=self._m();left=dev.isLeftButton();R=hou.uiEventReason;ctrl=dev.isCtrlKey()
        self.drag=None;self.press=None;self.sweep=None;self._clear_hover();self.sel.show(False);self.gone.show(False);self.frame.show(False);self._show_handle(False)
        h=surf.hit(o,d,stamps=False);self.hit=(h[0],h[1],h[2]) if h is not None else None;radius=max(node.evalParm('paint_radius'),1e-4)
        if left and reason==R.Start and self.hit is not None and self.stroke is None:
            self.stroke=dict(last=None,n0=len(self._rows()),dab=0,erase=ctrl,added=0,cfg=m.stamp_settings(node),field=None,text0=node.evalParm('stamps'))
            if not ctrl and m.stamp_paint_active(node):self.stroke['field']=m.StampPaintStroke(node,self.surf,self._bound_map(),normal=self.hit[1]);self.stroke['field'].FLUSH_S=PAINT_FLUSH_S          # Density / Scale Falloff: the swept field engine, one move per mouse position
            try:self.scene_viewer.beginStateUndo('Arraytron Stamp: paint')
            except Exception:pass
        if self.stroke is not None and left and reason in (R.Start,R.Active) and self.hit is not None:
            st=self.stroke;pos=self.hit[0]
            if st.get('field') is not None:st['field'].move(pos,self.hit[1])
            elif st['last'] is None or np.linalg.norm(pos-st['last'])>=0.35*radius:st['last']=pos;self._dab(st,pos,self.hit[1],radius)
        if self.stroke is not None and reason in (R.Changed,R.Picked):self._end_stroke()
        if self.hit is None:self.marker.show(False);self.cursor.show(False);self.ring_d.show(False);self.ring_s.show(False)
        else:
            erasing=ctrl or (self.stroke or {}).get('erase')
            self._show_ring(surf,self.hit,radius,m.BC_COLORS['erase'] if erasing else m.BC_COLORS['paint'],() if erasing else self._inners())
            if ctrl or (self.stroke or {}).get('erase'):self.ring_d.show(False);self.ring_s.show(False)
            else:self._show_profiles(self.hit[0],self.hit[1],radius)
        self._hud();return True
    def _dab(self,st,pos,nrm,radius):
        node=self.node;m=self._m()
        if st['erase']:st['added']-=m.stamp_erase_dab(node,pos,radius);st['dab']+=1;return
        rng=np.random.RandomState(int((node.evalParm('seed')*7919+st['n0']*104729+st['dab']*31+1)%(2**31)))
        new_pos,new_nrm=m.stamp_paint_dab(self.surf,pos,nrm,radius,node.evalParm('paint_density'),node.evalParm('paint_spacing'),node.evalParm('paint_falloff'),rng,self._rows()[:,0:3])
        if len(new_pos):st['added']+=m.stamp_add_batch(node,new_pos,new_nrm,snap_rot=node.evalParm('snaprot') or None,cfg=st['cfg'],bounds=self._bound_map())
        st['dab']+=1
    def _end_stroke(self):
        st=self.stroke
        if st is not None:
            try:
                if st.get('field') is not None:st['field'].finish()                       # what still waits for the brush to pass is decided now
                if st.get('edit') is not None:st['edit'].finish()
                if st.get('clone') is not None and st.get('buf'):self._m().stamp_append_lines(self.node,st['buf'])
            except Exception:
                if STRICT:raise
        self.stroke=None
        try:self.scene_viewer.endStateUndo()
        except Exception:pass
    def _cancel_stroke(self):
        """Esc during a stroke: the stamps go back to what they were when it began (nothing half done stays)."""
        st=self.stroke;self.stroke=None
        if st is None:return
        try:
            if st.get('edit') is not None:st['edit'].cancel()
            else:
                if st.get('field') is not None:st['field'].cancel()
                if st.get('text0') is not None:
                    with hou.undos.disabler():self.node.parm('stamps').set(st['text0'])
        except Exception:
            if STRICT:raise
        try:self.scene_viewer.endStateUndo();self.scene_viewer.setPromptMessage('Arraytron Stamp: stroke cancelled.')
        except Exception:pass
    def _show_profiles(self,pos,nrm,radius):
        """The falloff of the Paint brush where you are going to paint, standing on the surface along a spoke (density to one side, scale to the other: the height is the multiplier at that distance)."""
        m=self._m()
        for drawable,prefix,sign in ((self.ring_d,'dens',1.0),(self.ring_s,'scale',-1.0)):
            prof=m.stamp_falloff_profile(self.node,prefix)
            if prof is None or self._prefs().get('compact',False):drawable.show(False);continue
            drawable.setGeometry(_lines(hou.Geometry(),m.bc_profile_lines(pos,nrm,radius,prof,sign)));drawable.show(True)
    def _show_ring(self,surf,hit,radius,color,inners=()):
        """The cursor (BrushCore's bc_cursor): the radius ring cast onto the surface (it follows the ground), a ring where each falloff starts, a centre cross and a normal tick."""
        pos,nrm,t=hit;m=self._m();lift=radius*1.5+0.05;prefs=self._prefs()
        if prefs.get('compact',False):inners=()                                                       # the compact cursor (arraytron_brush_prefs.json): the ring and the cross only
        a_=min(max(float(prefs.get('cursor_opacity',1.0)),0.1),1.0);color=(color[0],color[1],color[2],color[3]*a_)
        sig=(tuple(np.round(np.asarray(pos)/max(radius*0.01,1e-6))),tuple(np.round(nrm,3)),round(radius,6),tuple(color),tuple(round(x,4) for x in inners))
        if sig==getattr(self,'cursor_sig',None) and _drawable_on(self.cursor):self.marker.show(False);return      # nothing moved: no casts, no geometry
        self.cursor_sig=sig
        def project(P):
            if hasattr(surf,'project'):return surf.project(P,nrm,lift)                             # positions only (no smooth normals): the cursor costs a few casts
            out=np.array(P,dtype=np.float64)
            for k in range(len(out)):
                h=surf.hit(out[k]+nrm*lift,-nrm,stamps=False)
                if h is not None:out[k]=h[0]
            return out
        if color!=self.cursor_color:self.cursor.setParams({'color1':hou.Vector4(color),'line_width':2.0});self.cursor_color=color
        self.cursor.setGeometry(_lines(hou.Geometry(),m.bc_cursor(pos,nrm,radius,inners,48,project)));self.cursor.show(True);self.marker.show(False)
    def _inners(self):
        """The rings inside the paint cursor: where the density and the scale start to fall."""
        m=self._m();out=[]
        for prefix in ('dens','scale'):
            p=m.stamp_falloff_profile(self.node,prefix)
            if p is not None:out.append(p['inner'])
        return out
    def _variant(self,key,dev):
        """The variant of a sculpt brush for the modifier keys: Ctrl / Shift pick the opposite or the companion operation (None: the brush's own setting)."""
        ctrl=dev.isCtrlKey();shift=dev.isShiftKey()
        if key=='erase':
            soft=bool(self.node.evalParm('erase_soft')) if self.node.parm('erase_soft') is not None else False;return 'soft' if (soft!=shift) else 'hard'
        if key=='scale':return 'shrink' if ctrl else 'smooth' if shift else None
        if key=='push':return 'attract' if ctrl else 'drag' if shift else None
        if key=='orient':return 'random' if ctrl else 'smooth' if shift else None
        return None
    def _sculpt_mouse(self,ev,dev,reason,surf,o,d):
        """Erase, Relax, Grow / Shrink, Push / Attract, Replace, Orient / Comb: LMB drag works under the brush (BrushCore dabs along the path, one undo step per stroke, Esc cancels)."""
        node=self.node;m=self._m();left=dev.isLeftButton();R=hou.uiEventReason;key=BRUSH_KEYS[self._brush()]
        self.drag=None;self.press=None;self.sweep=None;self._clear_hover();self.sel.show(False);self.gone.show(False);self.frame.show(False);self._show_handle(False)
        h=surf.hit(o,d,stamps=False);self.hit=(h[0],h[1],h[2]) if h is not None else None;radius=max(node.evalParm('paint_radius'),1e-4)
        if left and reason==R.Start and self.hit is not None and self.stroke is None:
            self.stroke=dict(edit=m.StampEditStroke(node,surf,key,self.hit[1],op=self._variant(key,dev),bounds=self._bound_map()),kind=key)
            try:self.scene_viewer.beginStateUndo('Arraytron Stamp: %s'%BRUSHES[self._brush()])
            except Exception:pass
        if self.stroke is not None and self.stroke.get('edit') is not None and left and reason in (R.Start,R.Active) and self.hit is not None:self.stroke['edit'].move(self.hit[0])
        if self.stroke is not None and reason in (R.Changed,R.Picked):self._end_stroke()
        if self.hit is None:self.cursor.show(False)
        else:
            hard=float(node.evalParm('brush_hardness')) if node.parm('brush_hardness') is not None else 0.0
            color=m.BC_COLORS['delete' if (key=='erase' and dev.isShiftKey()) else key] if key in m.BC_COLORS else GREEN
            self._show_ring(surf,self.hit,radius,color,(hard,) if hard>0.03 else ())
        self._hud();return True
    def _clone_mouse(self,ev,dev,reason,surf,o,d):
        """Clone: Ctrl + click picks the stamps under the brush as the source; click stamps a copy, drag stamps copies along the stroke (Clone > Spacing apart); the copies show as boxes under the mouse."""
        node=self.node;m=self._m();left=dev.isLeftButton();R=hou.uiEventReason
        self.drag=None;self.press=None;self.sweep=None;self._clear_hover();self.sel.show(False);self.gone.show(False);self.frame.show(False);self._show_handle(False)
        h=surf.hit(o,d,stamps=False);self.hit=(h[0],h[1],h[2]) if h is not None else None;radius=max(node.evalParm('paint_radius'),1e-4)
        if left and reason==R.Start and self.hit is not None and dev.isCtrlKey():
            k=m.stamp_clone_capture(node,self.hit[0],self.hit[1],radius)
            try:self.scene_viewer.setPromptMessage('Arraytron Stamp: clone source of %d stamp%s.'%(k,'' if k==1 else 's') if k else 'Arraytron Stamp: no stamps under the brush to clone.')
            except Exception:pass
            self.hud=None;self._hud();return True
        src=m.stamp_clone_source(node) if node.parm('clone_src') is not None else None
        if left and reason==R.Start and self.hit is not None and src is not None and self.stroke is None:
            step=max(2.0*src['radius']*float(node.evalParm('clone_scale'))*float(node.evalParm('clone_spacing')),radius*0.25)
            self.stroke=dict(clone=src,dabs=m.BrushDabs(step),n0=m.stamp_count(node.evalParm('stamps')),copies=0,buf=[],timer=m.BrushTimer(0.05))
            try:self.scene_viewer.beginStateUndo('Arraytron Stamp: clone')
            except Exception:pass
        st=self.stroke
        if st is not None and st.get('clone') is not None and left and reason in (R.Start,R.Active) and self.hit is not None:
            for c in st['dabs'].move(self.hit[0]):st['buf']+=m.stamp_clone_lines(node,surf,c,self.hit[1],copy=st['n0']+st['copies'],clone=st['clone']);st['copies']+=1
            if st['buf'] and st['timer'].due():t0=time.time();m.stamp_append_lines(node,st['buf']);st['buf']=[];st['timer'].wrote(t0)
        if st is not None and reason in (R.Changed,R.Picked):self._end_stroke()
        if self.hit is None:self.cursor.show(False);self.box.show(False)
        else:
            self._show_ring(surf,self.hit,radius,m.BC_COLORS['clone'])
            if src is not None:
                rows=m.stamp_rows('\n'.join(m.stamp_clone_lines(node,surf,self.hit[0],self.hit[1],copy=(st or {}).get('n0',m.stamp_count(node.evalParm('stamps')))+(st or {}).get('copies',0),clone=src)))
                self.box.setParams({'color1':hou.Vector4(m.BC_COLORS['clone'])});self._boxes(self.box,rows,np.arange(len(rows)))
            else:self.box.show(False)
        self._hud();return True
    def _delete_mouse(self,ev,dev,reason,surf,o,d):
        """Delete brush: the stamp under the mouse shows red; press and drag over several, release deletes them all (one undo step)."""
        m=self._m();left=dev.isLeftButton();R=hou.uiEventReason;self.drag=None;self.press=None;self._clear_hover();self.sel.show(False);self.frame.show(False);self._show_handle(False)
        h=surf.hit(o,d);under=surf.last_stamp if h is not None else None;rows=self._rows()
        if left and reason==R.Start:self.sweep=set()
        if self.sweep is not None and under is not None:self.sweep.add(int(under))
        if self.sweep is not None and reason in (R.Changed,R.Picked):
            if time.time()-self.last>=0.25 or len(self.sweep)>1:
                self.last=time.time();m.stamp_delete_many(self.node,self.sweep)
            self.sweep=None;rows=self._rows()
        show=set(self.sweep or ())|({int(under)} if under is not None else set());self._boxes(self.gone,rows,sorted(show));self._hud();return True
    def _edit_mouse(self,ev,dev,reason,surf,o,d):
        """Edit mode: click selects the stamp under the mouse (Shift adds or removes), a drag on nothing is a box select, the handle edits the selection."""
        m=self._m();left=dev.isLeftButton();R=hou.uiEventReason;self.drag=None
        if self.press is not None and reason==R.Active:                                      # the box grows: the rectangle only (no ray cast, no parsing, no HUD)
            p=self.press
            if abs(dev.mouseX()-p['x'])+abs(dev.mouseY()-p['y'])>=DRAG_PIXELS:p['moved']=True
            if p['moved']:self.box.show(False);self._show_rect(ev,dev,p)
            return True
        self._clear_hover();self.gone.show(False);rows=self._rows();sel=list(self._selection(len(rows)))
        h=surf.hit(o,d);under=int(surf.last_stamp) if h is not None and surf.last_stamp is not None else None
        if left and reason==R.Start:self.press=dict(x=dev.mouseX(),y=dev.mouseY(),under=under,moved=False,shift=dev.isShiftKey())
        elif self.press is not None and reason in (R.Changed,R.Picked):
            p=self.press;self.press=None;self.frame.show(False)
            if p['moved']:
                vp=ev.curViewport()
                try:hit=m.stamp_select_in_rays(rows[:,0:3],[_ray(vp,x,y) for x,y in ((p['x'],p['y']),(dev.mouseX(),p['y']),(dev.mouseX(),dev.mouseY()),(p['x'],dev.mouseY()))])   # four rays, numpy over every stamp
                except Exception:hit=m.stamp_select_in_box(self.node,lambda pos:self._project(vp,pos),p['x'],p['y'],dev.mouseX(),dev.mouseY())
                new=sorted(set(sel)|set(hit)) if p['shift'] else hit
            elif p['under'] is not None:
                new=[i for i in sel if i!=p['under']] if (p['shift'] and p['under'] in sel) else sorted(set(sel)|{p['under']}) if p['shift'] else [p['under']]
            else:new=sel if p['shift'] else []
            m.stamp_set_selection(self.node,new)
        else:
            if self.press is None and under is not None and reason!=R.Active:
                self.box.setParams({'color1':hou.Vector4(GREY)});self._boxes(self.box,rows,[under])                 # the stamp under the mouse
            else:self.box.show(False)
        self._refresh_edit(rows);self._hud();return True
    def _project(self,vp,pos):
        try:
            s=vp.mapToScreen(hou.Vector3((float(pos[0]),float(pos[1]),float(pos[2]))));return (float(s[0]),float(s[1]))
        except Exception:return None
    def _show_rect(self,ev,dev,p):
        """The box of a box select: a rectangle of lines on the rays through its four corners, just past the near clipping plane (in front of everything, so nothing hides it)."""
        vp=ev.curViewport()
        try:t=max(float(vp.defaultCamera().clipNear())*4.0,0.01)
        except Exception:t=0.1
        try:
            pts=[];
            for x,y in ((p['x'],p['y']),(dev.mouseX(),p['y']),(dev.mouseX(),dev.mouseY()),(p['x'],dev.mouseY()),(p['x'],p['y'])):
                o,dr=_ray(vp,x,y);pts.append(o+dr/np.linalg.norm(dr)*t)
            self.frame.setGeometry(_lines(hou.Geometry(),[pts]));self.frame.show(True)
        except Exception:self.frame.show(False)

    # ----- the wheel and the keys
    @guarded
    def onMouseWheelEvent(self,kwargs):
        if self.node is None or self._mode()==1:return False
        dev=kwargs['ui_event'].device();step=dev.mouseWheel();sign=1 if step>0 else -1 if step<0 else 0
        if sign==0 or dev.isAltKey():return False
        brush=self._brush();paint=brush==2;n=self.node
        if brush==CLONE and dev.isShiftKey():self._set('clone_yaw',n.evalParm('clone_yaw')+15.0*sign,-180.0,180.0)
        elif brush==CLONE and dev.isCtrlKey():self._set('clone_scale',n.evalParm('clone_scale')*1.1**sign,0.05,10.0)
        elif brush in SCULPT and dev.isShiftKey():self._set('paint_radius',n.evalParm('paint_radius')*1.1**sign,0.001,10000.0)
        elif brush in SCULPT and dev.isCtrlKey():
            if brush in (4,5,8):self._set('paint_strength',n.evalParm('paint_strength')+0.05*sign,0.0,1.0)                           # Erase, Relax, Replace: the strength
            else:self._set('brush_amount',n.evalParm('brush_amount')*1.15**sign,0.001,2.0)                                         # Grow / Shrink, Push, Orient: the amount
        elif paint and dev.isShiftKey():self._set('paint_radius',self.node.evalParm('paint_radius')*1.1**sign,0.001,10000.0)       # the Paint brush: the radius
        elif paint and dev.isCtrlKey():self._set('paint_density',self.node.evalParm('paint_density')*1.15**sign,0.0,1000.0)       # and the density
        elif dev.isShiftKey():self._set('scale',self.node.evalParm('scale')*1.1**sign,0.0001,1000.0)
        elif dev.isCtrlKey():self._set('yaw',self.node.evalParm('yaw')+15.0*sign,-360.0,360.0)
        elif self._brush() in (0,2,8):self._m().stamp_cycle(self.node,sign)               # the Place, Paint and Replace brushes: the wheel cycles the working set
        else:return False
        self._refresh();return True
    @guarded
    def onKeyEvent(self,kwargs):
        if self.node is None:return False
        try:import viewerstate.utils as su;key=su.hotkeySymbolOrKeyString(kwargs)
        except Exception:key=kwargs['ui_event'].device().keyString()
        n=self.node;m=self._m()
        if not key:return False
        if hk_is(key,'togglemode'):self._set_mode(0 if self._mode()==1 else 1);return True
        if hk_is(key,'brushselector'):self.radial_menu();return True
        if hk_is(key,'hud'):self._cycle_hud();return True
        if key in ('Esc','Escape') and self.stroke is not None:self._cancel_stroke();return True
        if hk_is(key,'brushradial'):self._popup(self.options_menu());self._refresh();return True
        if hk_is(key,'delete') and self._mode()==1:
            sel=self._selection(len(self._rows()))
            if len(sel):m.stamp_delete_many(n,sel);self._refresh_edit();self._hud()
            return True
        if hk_is(key,'finish'):
            if self.press is None and self.sweep is None and self.drag is None:return False                    # nothing to finish: Enter leaves the tool as it always does
            self.press=None;self.sweep=None;self.drag=None;self.frame.show(False);self.gone.show(False);return True
        if hk_is(key,'group') and self._mode()==1:
            k=m.stamp_group_capture_selected(n);self.hud=None;self._clear_hover();self._refresh_edit();self._hud()
            try:self.scene_viewer.setPromptMessage('Arraytron Stamp: group layout from %d stamp%s, the Group brush is on.'%(k,'' if k==1 else 's') if k else 'Arraytron Stamp: select stamps first.')
            except Exception:pass
            return True
        if hk_is(key,'material') and self._mode()==1:
            k=m.stamp_material_next_selected(n);self._refresh_edit();self._hud()
            try:self.scene_viewer.setPromptMessage('Arraytron Stamp: the next material for %d stamp%s.'%(k,'' if k==1 else 's') if k else 'Arraytron Stamp: select stamps first.')
            except Exception:pass
            return True
        if self._mode()==1:return False
        if key in ('-','_','=','+') and (self._brush()==2 or self._brush() in SCULPT) and n.parm('paint_strength') is not None:self._set('paint_strength',n.evalParm('paint_strength')+(0.05 if key in ('=','+') else -0.05),0.0,1.0)
        elif hk_is(key,'scaleup'):self._size(1.1)
        elif hk_is(key,'scaledown'):self._size(1/1.1)
        elif hk_is(key,'rotright'):self._set('yaw',n.evalParm('yaw')+15.0,-360.0,360.0)
        elif hk_is(key,'rotleft'):self._set('yaw',n.evalParm('yaw')-15.0,-360.0,360.0)
        elif len(key)==1 and key.isdigit():
            row=int(key) or None
            if row is not None and row in [l[0] for l in m.stamp_labels(n)]:m.stamp_set_workset(n,[row],proto=row)
            elif row is None:m.stamp_set_workset(n,[])
        else:return False
        self._refresh();return True
    @guarded
    def onKeyTransitEvent(self,kwargs):
        """Z held while dragging the handle duplicates the selection (a volatile client: the release is reported back)."""
        if self.node is None:return False
        try:import viewerstate.utils as su;key=su.hotkeySymbolOrKeyString(kwargs)
        except Exception:key=kwargs['ui_event'].device().keyString()
        if key and kwargs['ui_event'].device().isKeyDown() and hk_is(key,'duplicate'):
            self.duplicate=True;kwargs['add_volatile_client']={'name':'arraytron_stamp_duplicate'};return True
        return False
    @guarded
    def onVolatileClientEvent(self,kwargs):
        if kwargs.get('client_name')=='arraytron_stamp_duplicate' and kwargs.get('event_type')=='release':self.duplicate=False;return True
        return False
    def _size(self,k):
        """[ and ]: the radius of the Paint brush, the scale of the next stamp otherwise."""
        n=self.node
        if self._brush()==2 or self._brush() in SCULPT:self._set('paint_radius',n.evalParm('paint_radius')*k,0.001,10000.0)
        elif self._brush()==CLONE:self._set('clone_scale',n.evalParm('clone_scale')*k,0.05,10.0)
        else:self._set('scale',n.evalParm('scale')*k,0.0001,1000.0)
    def _refresh(self):
        """After a setting changed by key or wheel: the box under the mouse and the HUD show it at once."""
        if self.drag is None and self.hit is not None and self._mode()==0 and self._brush() in (0,3):self._show_hover(*self.hit)
        else:self._hud()

def createViewerStateTemplate():
    import viewerstate.utils as su
    cat=hou.lopNodeTypeCategory();template=hou.ViewerStateTemplate(kwargs['type'].definition().sections()['DefaultState'].contents().strip(),'Arraytron Stamp',cat)
    template.bindFactory(StampState);template.bindHandle('xform','edit_handle')
    try:template.bindIcon(kwargs['type'].definition().icon() or 'MISC_paint')
    except Exception:template.bindIcon('MISC_paint')
    defs=hou.PluginHotkeyDefinitions()
    for token,(label,descr) in HK_NAMES.items():su.defineHotkey(defs,STATE_NAME,token,KEYS[token],label,descr,cat)
    template.bindHotkeyDefinitions(defs)
    return template
