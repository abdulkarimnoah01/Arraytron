"""Arraytron Stamp Gallery: a Python Panel that looks like the Layout tool's panel - a brush row, Transform / Asset / Advanced tabs and a grid of the prototypes to click.
The panel only reads and writes the parameters of the Stamp node, so the placing tool, the table and everything downstream are the same as without it."""
GALLERY_NAME='arraytron_stamp_gallery';GALLERY_TYPE='arraytron::stamp::0.1.0'
GALLERY_TABS=(('Transform',(('place_align','Align To Surface'),('place_offset','Offset'),('place_def_scale','Scale'),('place_def_scalerange','Random Scale'),('place_def_yaw','Rotation'),('place_def_yawrand','Random Rotation'),('place_def_tilt','Random Tilt'),('place_seed','Seed'))),
              ('Asset',(('place_def_protorand','Random Prototype'),)),
              ('Advanced',(('place_target','Place On'),('place_snap','Snap Position'),('place_snap_rot','Snap Rotation'),('place_dragset','Drag Sets Rotation And Scale'),('place_def_copies','Copies'))))

def gallery_signature(asset):
    """What the cards depend on (cheap to read, so the panel can poll it): the enabled rows with their prim path and weight."""
    return tuple((r,asset.evalParm('proto_prim%d'%r),asset.evalParm('proto_weight%d'%r)) for r in range(1,asset.evalParm('protos')+1) if asset.evalParm('proto_on%d'%r))

def gallery_cards(asset,cache=None):
    """[(row, label, prim path, prim type name, weight)] of the enabled rows of the Prototype Bank, with the type of the prim read from the first input (a guess for the icon only).
    cache (a dict path -> type) keeps the stage from being read again for a path already known: reading the input stage can cook it."""
    stage=None;cache={} if cache is None else cache
    cards=[]
    for r in range(1,asset.evalParm('protos')+1):
        if not asset.evalParm('proto_on%d'%r):continue
        path=asset.evalParm('proto_prim%d'%r).strip();kind='Sphere' if not path else ''
        if path and path in cache:kind=cache[path]
        elif path:
            try:
                if stage is None and asset.inputs() and asset.inputs()[0] is not None:stage=asset.inputs()[0].stage()
            except Exception:stage=None
            if stage is not None:
                try:
                    prim=stage.GetPrimAtPath(path.rstrip('*').rstrip('/'))
                    if prim and prim.IsValid():
                        kind=prim.GetTypeName()
                        if kind in ('Xform','Scope',''):
                            for child in prim.GetChildren():
                                if child.GetTypeName() not in ('Xform','Scope',''):kind=child.GetTypeName();break
                        cache[path]=kind
                except Exception:pass
        cards.append((r,path.rstrip('/').split('/')[-1] if path else 'Built-in sphere',path,kind,asset.evalParm('proto_weight%d'%r)))
    return cards

def gallery_widget(PySideFlavor=None):
    """The panel's root QWidget (PySide2 or PySide6, whichever this Houdini has). It follows the current Stamp node and refreshes by timer."""
    try:from PySide6 import QtWidgets,QtCore,QtGui
    except ImportError:from PySide2 import QtWidgets,QtCore,QtGui
    STAMP_TYPE='arraytron::stamp::'

    def icon_for(kind,size=58,on=False):
        pm=QtGui.QPixmap(size,size);pm.fill(QtCore.Qt.transparent);p=QtGui.QPainter(pm);p.setRenderHint(QtGui.QPainter.Antialiasing)
        c=QtGui.QColor(190,190,190);p.setPen(QtGui.QPen(QtGui.QColor(70,70,70),1.5));m=size*0.14;s=size-2*m
        if kind=='Cone':
            p.setBrush(QtGui.QColor(70,150,90));p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(size/2,m),QtCore.QPointF(m,size-m),QtCore.QPointF(size-m,size-m)]))
        elif kind=='Cube':
            p.setBrush(QtGui.QColor(190,170,120));p.drawRect(QtCore.QRectF(m,m,s,s))
        elif kind=='Cylinder' or kind=='Capsule':
            p.setBrush(QtGui.QColor(150,150,190));p.drawRoundedRect(QtCore.QRectF(size*0.28,m,size*0.44,s),8,8)
        elif kind in ('Mesh','PointInstancer','BasisCurves'):
            p.setBrush(QtGui.QColor(160,160,160));p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(size*0.5,m),QtCore.QPointF(size-m,size*0.4),QtCore.QPointF(size*0.78,size-m),QtCore.QPointF(size*0.22,size-m),QtCore.QPointF(m,size*0.4)]))
        else:
            g=QtGui.QRadialGradient(size*0.4,size*0.38,size*0.5);g.setColorAt(0,QtGui.QColor(235,235,235));g.setColorAt(1,QtGui.QColor(110,110,110));p.setBrush(g);p.drawEllipse(QtCore.QRectF(m,m,s,s))
        p.end();return pm

    class Gallery(QtWidgets.QWidget):
        def __init__(self):
            super().__init__();self.node=None;self.rows=[];self.widgets={};self.cardkey=None;self.infokey=None;self.kinds={};self.busy=False
            root=QtWidgets.QVBoxLayout(self);root.setContentsMargins(6,6,6,6);root.setSpacing(6)
            top=QtWidgets.QHBoxLayout();top.addWidget(QtWidgets.QLabel('Stamp'));self.pick=QtWidgets.QComboBox();self.pick.currentIndexChanged.connect(self._choose);top.addWidget(self.pick,1);root.addLayout(top)
            brush=QtWidgets.QHBoxLayout()
            for text,tip,fn in (('Place','Start placing in the viewport (Esc leaves). Press, drag to rotate and scale, release.',self._place),('Delete Last','Remove the last placed instance.',self._delete_last),('Clear All','Remove every placed instance.',self._clear),('Fix Ids','Give every row its own id.',self._fix)):
                b=QtWidgets.QPushButton(text);b.setToolTip(tip);b.clicked.connect(fn);brush.addWidget(b)
            root.addLayout(brush);self.info=QtWidgets.QLabel('');self.info.setWordWrap(True);root.addWidget(self.info)
            tabs=QtWidgets.QTabWidget();root.addWidget(tabs)
            for title,items in GALLERY_TABS:
                page=QtWidgets.QWidget();form=QtWidgets.QFormLayout(page);form.setContentsMargins(6,6,6,6)
                for name,label in items:form.addRow(label,self._control(name))
                tabs.addTab(page,title)
            self.grid_host=QtWidgets.QWidget();self.grid=QtWidgets.QGridLayout(self.grid_host);self.grid.setAlignment(QtCore.Qt.AlignTop|QtCore.Qt.AlignLeft)
            scroll=QtWidgets.QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(self.grid_host);root.addWidget(scroll,1)
            self.timer=QtCore.QTimer(self);self.timer.timeout.connect(self.refresh);self.timer.start(700);self.refresh()

        # ---- controls bound to a parameter of the node
        def _control(self,name):
            holder=QtWidgets.QWidget();lay=QtWidgets.QHBoxLayout(holder);lay.setContentsMargins(0,0,0,0);parts=[]
            self.widgets[name]=holder;holder._name=name;holder._parts=parts;holder._lay=lay;return holder

        def _fill(self,holder,tup):
            """Build the editors of one parameter the first time its tuple is known."""
            name=holder._name;tpl=tup.parmTemplate();n=len(tup);t=tpl.type()
            for k in range(n):
                if t==hou.parmTemplateType.Toggle:w=QtWidgets.QCheckBox();w.stateChanged.connect(lambda v,k=k,nm=name:self._set(nm,k,bool(v)))
                elif t==hou.parmTemplateType.String:w=QtWidgets.QLineEdit();w.editingFinished.connect(lambda k=k,nm=name,w=w:self._set(nm,k,w.text()))
                elif t==hou.parmTemplateType.Int:
                    w=QtWidgets.QSpinBox();w.setRange(-10000000,10000000);w.valueChanged.connect(lambda v,k=k,nm=name:self._set(nm,k,v))
                else:
                    w=QtWidgets.QDoubleSpinBox();w.setDecimals(3);w.setRange(-100000.0,100000.0);w.setSingleStep(0.1);w.valueChanged.connect(lambda v,k=k,nm=name:self._set(nm,k,v))
                w.setToolTip(tpl.help());holder._lay.addWidget(w);holder._parts.append(w)
            holder._built=True

        def _set(self,name,k,value):
            if self.busy or self.node is None:return
            tup=self.node.parmTuple(name)
            if tup is not None:tup[k].set(value)

        # ---- buttons
        def _place(self):
            if self.node is not None:
                try:self.node.hdaModule().place_start(self.node)
                except Exception as e:hou.ui.displayMessage(str(e),severity=hou.severityType.Warning)
        def _delete_last(self):
            if self.node is not None and self.node.evalParm('places')>0:self.node.hdaModule().place_remove(self.node,self.node.evalParm('places'))
        def _clear(self):
            if self.node is not None:self.node.hdaModule().place_clear(self.node)
        def _fix(self):
            if self.node is not None:self.node.hdaModule().place_normalize(self.node)
        def _choose(self,index):
            if self.busy:return
            path=self.pick.itemData(index)
            self.node=hou.node(path) if path else None;self.cardkey=None;self.refresh()

        def _card(self,row,label,kind,weight,on):
            b=QtWidgets.QToolButton();b.setIcon(QtGui.QIcon(icon_for(kind)));b.setIconSize(QtCore.QSize(58,58));b.setText('%s\n%d  (w %g)'%(label,row,weight) if row else label)
            b.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon);b.setCheckable(True);b.setChecked(on);b.setFixedWidth(104);b.setToolTip('Place prototype row %d'%row if row else 'The Selection Mode / Random Prototype chooses')
            b.clicked.connect(lambda _=False,r=row:self._select(r));return b
        def _select(self,row):
            if self.node is not None:self.node.parm('place_def_proto').set(row);self.refresh()

        def _stamps(self):
            try:return sorted([n for n in hou.nodeType(hou.lopNodeTypeCategory(),GALLERY_TYPE).instances()],key=lambda n:n.path())
            except Exception:return []

        def refresh(self):
            self.busy=True
            try:
                stamps=self._stamps();paths=[n.path() for n in stamps]
                if [self.pick.itemData(i) for i in range(self.pick.count())]!=paths:
                    self.pick.clear()
                    for n in stamps:self.pick.addItem(n.path(),n.path())
                cur=[n for n in hou.selectedNodes() if n in stamps]
                if cur and self.node!=cur[0]:self.node=cur[0]
                if (self.node is None or not self.node.path() in paths) and stamps:self.node=stamps[0]
                if self.node is not None and self.node.path() in paths and self.pick.currentData()!=self.node.path():self.pick.setCurrentIndex(paths.index(self.node.path()))
                if self.node is None:self.info.setText('No Arraytron Stamp node in this scene. Create one in /stage.');self._cards([]);return
                for name,holder in self.widgets.items():
                    tup=self.node.parmTuple(name);holder.setVisible(tup is not None)
                    if tup is None:continue
                    if not getattr(holder,'_built',False):self._fill(holder,tup)
                    for k,w in enumerate(holder._parts):
                        if w.hasFocus():continue
                        v=tup[k].eval()
                        if isinstance(w,QtWidgets.QCheckBox):w.setChecked(bool(v))
                        elif isinstance(w,QtWidgets.QLineEdit):
                            if w.text()!=v:w.setText(v)
                        elif w.value()!=v:w.setValue(v)
                places=self.node.evalParm('places')
                if (self.node.path(),places)!=self.infokey:self.infokey=(self.node.path(),places);self.info.setText(self.node.hdaModule().place_info(self.node))      # the table is read only when a stamp was added or removed
                cur_proto=self.node.evalParm('place_def_proto');key=(self.node.path(),gallery_signature(self.node),cur_proto)
                if key!=self.cardkey:
                    self.cardkey=key;self._cards(gallery_cards(self.node,self.kinds.setdefault(self.node.path(),{})),cur_proto)             # the stage is read once per prototype path
            finally:self.busy=False

        def _cards(self,cards,current=0):
            while self.grid.count():
                w=self.grid.takeAt(0).widget()
                if w is not None:w.deleteLater()
            if not cards:return
            allcards=[(0,'Auto','','',1.0)]+list(cards);cols=max(1,(self.grid_host.width()-8)//112)
            for i,(row,label,path,kind,weight) in enumerate(allcards):self.grid.addWidget(self._card(row,label,kind or 'Sphere',weight,row==current),i//cols,i%cols)

    return Gallery()

def gallery_ensure():
    """Open the Stamp Gallery unless a pane showing it already exists (called when the Stamp's tool is entered)."""
    try:
        for tab in hou.ui.paneTabs():
            if tab.type()==hou.paneTabType.PythonPanel and tab.activeInterface() is not None and tab.activeInterface().name()==GALLERY_NAME:return None
    except Exception:pass
    return gallery_open()

def gallery_open(asset=None):
    """Open the Stamp Gallery as a floating Python Panel (it can be docked next to the viewport like any pane)."""
    import tempfile,os
    if not hou.isUIAvailable():raise hou.NodeError('The Stamp Gallery needs the Houdini interface.')
    xml=('<?xml version="1.0" encoding="UTF-8"?>\n<pythonPanelDocument>\n<interface name="%s" label="Stamp Gallery" icon="MISC_python" showNetworkNavigationBar="false" help_url="">\n<script><![CDATA[\n'
         'import hou\n\ndef onCreateInterface():\n    stamp=[n for n in hou.nodeType(hou.lopNodeTypeCategory(),"%s").instances()]\n    if not stamp:\n        try:import PySide6.QtWidgets as W\n        except ImportError:import PySide2.QtWidgets as W\n        return W.QLabel("Create an Arraytron Stamp node in /stage, then reopen this panel.")\n    return stamp[0].hdaModule().gallery_widget()\n'
         ']]></script>\n<includeInToolbarMenu menu_position="1000" create_separator="false"/>\n<help><![CDATA[]]></help>\n</interface>\n</pythonPanelDocument>\n')%(GALLERY_NAME,GALLERY_TYPE)
    path=os.path.join(tempfile.gettempdir(),'arraytron_stamp_gallery.pypanel')
    with open(path,'w',encoding='utf-8') as f:f.write(xml)
    hou.pypanel.installFile(path)
    panel=hou.ui.curDesktop().createFloatingPanel(hou.paneTabType.PythonPanel);panel.setName('Stamp Gallery');tab=panel.paneTabs()[0]
    tab.setActiveInterface(hou.pypanel.interfaceByName(GALLERY_NAME));panel.setSize((420,640))
    return panel

