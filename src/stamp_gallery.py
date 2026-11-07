# Arraytron Stamp: the Parameters pane of the node (the HDA section StampPanel.py, run as a Python Panel registered for this node type by gallery_install in stamp_core.py).
# The builder puts this text after the Qt imports, the Asset Library (src/arraytron_library.py, src/arraytron_libpanel.py: the same library as Arraytron's, shared) and before the entry points:
#   on top   the brush shelf (Place, Delete: a click enters the tool with that brush) and the cards of the Prototype Bank (a click selects the card: the working set, Ctrl adds or removes one):
#            real thumbnails (a software render of each prototype, one per timer tick), List / Grid / Large views, a search box, favourite stars, filters for the favourites and the working set
#   then     the STAMPS table (a collapsible section: every placed stamp, editable, selection shared with the Edit mode of the viewport) and the ASSET LIBRARY (categories, search, thumbnails, Add to Bank, ...)
#   below    the node's own parameters (hou.qt.ParmDialog): the Brush / Edit / Options tabs
# It only reads and writes parameters of the node, and looks at it every 0.8 s through a few parameter reads (no stage, no stamp table).
STAMP_TYPE = 'arraytron::stamp::0.9.3'

def stamp_icon(kind, size=52):
    pm = QtGui.QPixmap(size, size)
    pm.fill(QtCore.Qt.transparent)
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    p.setPen(QtGui.QPen(QtGui.QColor(70, 70, 70), 1.5))
    m = size * 0.14
    s = size - 2 * m
    if kind == 'Cone':
        p.setBrush(QtGui.QColor(70, 150, 90))
        p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(size / 2, m), QtCore.QPointF(m, size - m), QtCore.QPointF(size - m, size - m)]))
    elif kind == 'Cube':
        p.setBrush(QtGui.QColor(190, 170, 120))
        p.drawRect(QtCore.QRectF(m, m, s, s))
    elif kind in ('Cylinder', 'Capsule'):
        p.setBrush(QtGui.QColor(150, 150, 190))
        p.drawRoundedRect(QtCore.QRectF(size * 0.28, m, size * 0.44, s), 8, 8)
    elif kind in ('Mesh', 'PointInstancer', 'BasisCurves', 'File'):
        p.setBrush(QtGui.QColor(160, 160, 160))
        p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(size * 0.5, m), QtCore.QPointF(size - m, size * 0.4), QtCore.QPointF(size * 0.78, size - m), QtCore.QPointF(size * 0.22, size - m), QtCore.QPointF(m, size * 0.4)]))
    else:
        g = QtGui.QRadialGradient(size * 0.4, size * 0.38, size * 0.5)
        g.setColorAt(0, QtGui.QColor(235, 235, 235))
        g.setColorAt(1, QtGui.QColor(110, 110, 110))
        p.setBrush(g)
        p.drawEllipse(QtCore.QRectF(m, m, s, s))
    p.end()
    return pm

def fit_text(button, pad=20, expand=False):
    """A button wide enough for its text (the Houdini style makes text-only tool buttons as narrow as an icon, which squashes the text); expand: it takes the whole row."""
    metrics = button.fontMetrics()
    width = metrics.horizontalAdvance(button.text()) if hasattr(metrics, 'horizontalAdvance') else metrics.width(button.text())
    button.setMinimumWidth(width + pad)
    if expand:
        button.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

def confirm(text):
    """Ask before something that cannot be picked out again (Clear All, deleting every stamp of a prototype); no interface (hython, tests): yes."""
    try:
        if hou.isUIAvailable():
            return bool(hou.ui.displayConfirmation(text, severity=hou.severityType.Warning))
    except Exception:
        pass
    return True

VIEWS = (('List', 24, 0), ('Grid', 52, 96), ('Large', 84, 132))       # name, icon size, card size (0: a full-width row)
THUMB_SIZE = 128
_VIEW = [1]                                                           # the view of this session

def stamp_render_thumb(result, size=THUMB_SIZE):
    """A QImage of a prototype from stamp_thumb_triangles (points, triangles, colour): flat shaded, a fixed three-quarter view, a software painter's algorithm (no renderer needed). None when there is nothing."""
    if result is None:
        return None
    P, T, color = result
    yaw, pitch = np.radians(35.0), np.radians(24.0)
    cy, sy, cp, sp = np.cos(yaw), np.sin(yaw), np.cos(pitch), np.sin(pitch)
    x = P[:, 0] * cy - P[:, 2] * sy
    z = P[:, 0] * sy + P[:, 2] * cy
    view = np.stack([x, P[:, 1] * cp - z * sp, P[:, 1] * sp + z * cp], axis=1)               # screen x, screen y (up), depth
    lo, hi = view[:, :2].min(0), view[:, :2].max(0)
    span = max(float((hi - lo).max()), 1e-9)
    scale = (size - 14) / span
    off = (size - (hi - lo) * scale) / 2.0
    xy = (view[:, :2] - lo) * scale + off
    xy[:, 1] = size - xy[:, 1]
    tri = view[T]
    normal = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    length = np.linalg.norm(normal, axis=1)
    length[length == 0] = 1.0
    shade = 0.35 + 0.65 * np.abs(normal @ np.array([0.45, 0.75, 0.5]) / length)
    order = np.argsort(tri[:, :, 2].sum(axis=1))
    image = QtGui.QImage(size, size, QtGui.QImage.Format_ARGB32)
    image.fill(QtGui.QColor(44, 48, 56))
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setPen(QtCore.Qt.NoPen)
    base = np.array(color) * 255.0
    for k in order:
        c = np.minimum(base * shade[k], 255.0)
        painter.setBrush(QtGui.QColor(int(c[0]), int(c[1]), int(c[2])))
        a, b, d = T[k]
        painter.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(xy[a, 0], xy[a, 1]), QtCore.QPointF(xy[b, 0], xy[b, 1]), QtCore.QPointF(xy[d, 0], xy[d, 1])]))
    painter.end()
    return image

class StampCard(QtWidgets.QToolButton):
    """A card of the Prototype Bank: the thumbnail, the name, the row and the weight, and a star (a favourite)."""
    def __init__(self, row, parent=None):
        super().__init__(parent)
        self.row = row
        self.star = QtWidgets.QToolButton(self)
        self.star.setCheckable(True)
        self.star.setAutoRaise(True)
        self.star.setFixedSize(20, 20)
        self.star.setToolTip('Favourite: favourites come first, and the star filter shows only them.')
        self.set_favorite(False)
        self.setStyleSheet('QToolButton:checked { border: 2px solid #ffa030; }')               # a card of the stamp cycle has an orange frame
        self.badge = QtWidgets.QLabel('', self)
        self.badge.setStyleSheet('background: #ffa030; color: #202020; font-weight: bold; padding: 0px 4px; border-radius: 3px;')
        self.badge.setToolTip('The place of this prototype in the stamp cycle (the mousewheel goes 1, 2, 3 ...).')
        self.badge.move(3, 3)
        self.badge.hide()
        self.on_menu = None

    def set_order(self, n):
        """The number of the card in the stamp cycle (None: not in it)."""
        if n:
            self.badge.setText(str(n))
            self.badge.adjustSize()
            self.badge.show()
            self.badge.raise_()
        else:
            self.badge.hide()

    def contextMenuEvent(self, event):
        if self.on_menu is not None:
            self.on_menu(self.row, event.globalPos())

    def set_favorite(self, on):
        self.star.blockSignals(True)
        self.star.setChecked(bool(on))
        self.star.setText('\u2605' if on else '\u2606')
        self.star.blockSignals(False)

    def place_star(self):
        if self.toolButtonStyle() == QtCore.Qt.ToolButtonTextBesideIcon:
            self.star.move(self.width() - 24, (self.height() - 20) // 2)
        else:
            self.star.move(self.width() - 22, 2)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.place_star()

def stamp_cards(node, kinds=None):
    """[(row, label, kind, weight)] of the enabled Prototype Bank rows. The icon kind comes from the prim type in the stage for a prim, a group or an input (read once per path: kinds is the cache),
    'File' for a USD file and 'Sphere' for the built-in sphere."""
    m = node.hdaModule()
    kinds = {} if kinds is None else kinds
    stage = None
    cards = []
    for row, label, typ, weight, src in m.stamp_labels(node):
        kind = 'File' if typ == m.TYPE_FILE else 'Sphere' if not src else kinds.get(src, '')
        if typ != m.TYPE_FILE and src and src not in kinds:
            try:
                if stage is None:
                    stage = m.merged_stage(node)
                prim = stage.GetPrimAtPath(src.rstrip('*').rstrip('/')) if stage is not None else None
                if prim is not None and prim.IsValid():
                    kind = prim.GetTypeName()
                    if kind in ('Xform', 'Scope', ''):
                        for child in prim.GetChildren():
                            if child.GetTypeName() not in ('Xform', 'Scope', ''):
                                kind = child.GetTypeName()
                                break
                    kinds[src] = kind
            except Exception:
                pass
        cards.append((row, label, kind, weight))
    return cards

class StampCards(QtWidgets.QFrame):
    """The brush shelf and the cards of the Prototype Bank (thumbnails, views, search, favourites, filters)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.node = None
        self.key = None
        self.kinds = {}
        self.thumbs = {}                                    # thumbnail key -> QPixmap (False: it could not be drawn)
        self.pending = []                                   # [(row, key, source)] still to be drawn: one per timer tick
        self.sources = {}
        self.bkey = None
        self.cardmap = {}
        self.ctext = None                                   # the stamps text the counts were made from
        self.counts = {}
        top = QtWidgets.QVBoxLayout(self)
        top.setContentsMargins(8, 6, 8, 6)
        top.setSpacing(6)
        brush = QtWidgets.QHBoxLayout()
        brush.setSpacing(4)
        self.shelf = []
        for index, (text, tip) in enumerate((('Place', 'The Place brush: enter the viewport tool (Esc leaves). Click to place, drag to turn and scale; Shift drag scales, Ctrl drag orients; the mousewheel cycles the selected cards.'),
                                              ('Delete', 'The Delete brush: enter the viewport tool; click or drag over stamps to delete them.'),
                                              ('Paint', 'The Paint brush: enter the viewport tool; drag to paint stamps inside a disc (Radius, Density, Spacing in Brush > Paint), Ctrl + drag erases.'),
                                              ('Group', 'The Group brush: one click stamps several prototypes at once. By default a ring of the selected cards (Ctrl + click adds cards); or the layout of stamps you placed (Edit mode, select them, press G or Brush > Group > Set Layout From Selected Stamps).'))):
            b = QtWidgets.QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.setCheckable(True)
            b.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
            fit_text(b, 28)
            b.clicked.connect(lambda _=False, i=index: self.brush(i))
            brush.addWidget(b)
            self.shelf.append(b)
        self.random = QtWidgets.QToolButton()
        self.random.setText('Random')
        self.random.setToolTip('Random Prototype: every stamp takes a random one of the selected cards (every card when none is selected), by its Weight. The preview shows the one that comes next.')
        self.random.setCheckable(True)
        fit_text(self.random, 28)
        self.random.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        self.random.clicked.connect(self.set_random)
        brush.addWidget(self.random)
        brush.addStretch(1)
        self.info = QtWidgets.QLabel('')
        brush.addWidget(self.info)
        top.addLayout(brush)
        self.cycle = QtWidgets.QLabel('')
        self.cycle.setWordWrap(True)
        top.addWidget(self.cycle)
        bar = QtWidgets.QHBoxLayout()
        bar.setSpacing(3)
        self.views = []
        for index, (name, icon, card) in enumerate(VIEWS):
            b = QtWidgets.QToolButton()
            b.setText(name)
            b.setToolTip('%s view of the prototype cards' % name)
            b.setCheckable(True)
            b.setAutoRaise(True)
            fit_text(b, 16)
            b.clicked.connect(lambda _=False, i=index: self.set_view(i))
            bar.addWidget(b)
            self.views.append(b)
        self.fav_only = QtWidgets.QToolButton()
        self.fav_only.setText('\u2605')
        self.fav_only.setToolTip('Show only the favourites')
        self.fav_only.setCheckable(True)
        self.fav_only.setAutoRaise(True)
        fit_text(self.fav_only, 14)
        self.fav_only.toggled.connect(lambda _: self.refresh())
        self.set_only = QtWidgets.QToolButton()
        self.set_only.setText('Set')
        self.set_only.setToolTip('Show only the working set (the selected cards)')
        self.set_only.setCheckable(True)
        self.set_only.setAutoRaise(True)
        fit_text(self.set_only, 16)
        self.set_only.toggled.connect(lambda _: self.refresh())
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText('Search prototypes')
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _: self.refresh())
        bar.addWidget(self.fav_only)
        bar.addWidget(self.set_only)
        bar.addWidget(self.search, 1)
        top.addLayout(bar)
        self.grid_host = QtWidgets.QWidget()
        self.grid = QtWidgets.QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(4)
        self.grid.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.grid_host)
        self.scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        top.addWidget(self.scroll)
        self.set_view(_VIEW[0], refresh=False)

    def set_node(self, node):
        self.node = node
        self.key = None
        self.bkey = None
        self.pending = []
        self.refresh()

    def set_view(self, index, refresh=True):
        """List / Grid / Large (kept for the session)."""
        _VIEW[0] = index
        for i, b in enumerate(self.views):
            b.setChecked(i == index)
        self.scroll.setFixedHeight((60, 112, 152)[index])
        if refresh:
            self.key = None
            self.refresh()

    def brush(self, index):
        """A shelf button: choose the brush, leave the Edit mode and enter the viewport tool."""
        if self.node is None:
            return
        with hou.undos.disabler():
            self.node.parm('brush').set(index)
            self.node.parm('mode1').set(0)
        try:
            self.node.hdaModule().stamp_start(self.node)
        except Exception as error:
            hou.ui.displayMessage(str(error), severity=hou.severityType.Warning)
        self.refresh()

    def show_cycle(self, labels, ws, rand):
        """Which prototypes the mousewheel cycles through (and Random draws from): the selected cards by name, or all of them."""
        names = {l[0]: l[1] for l in labels}
        if ws:
            shown = ', '.join('%d %s' % (i + 1, names.get(r, '?')) for i, r in enumerate(ws[:5])) + (' ...' if len(ws) > 5 else '')
            text = 'Stamp cycle, %d selected: %s' % (len(ws), shown)
        else:
            text = 'Stamp cycle: none selected, all %d prototypes are in play (click a card to choose, Ctrl + click adds)' % len(names)
        self.cycle.setText(text + ('   |   Random draws from these' if rand else ''))

    def card_menu(self, row, pos):
        """Right click on a card: select or delete the stamps of this prototype, or put it in the stamp cycle."""
        if self.node is None:
            return
        n = self.counts.get(row, 0)
        menu = QtWidgets.QMenu(self)
        menu.addAction('Select its %d stamp(s) (Edit mode)' % n, lambda: self.select_stamps(row)).setEnabled(n > 0)
        menu.addAction('Delete its %d stamp(s)' % n, lambda: self.delete_stamps(row)).setEnabled(n > 0)
        menu.addSeparator()
        menu.addAction('Only this prototype in the stamp cycle', lambda: self.select(row))
        menu.addAction('Add / remove in the stamp cycle', lambda: self.select(row, True))
        (menu.exec if hasattr(menu, 'exec') else menu.exec_)(pos)

    def select_stamps(self, row):
        """The stamps of a prototype become the selection and the Edit mode shows them."""
        n = self.node.hdaModule().stamp_select_proto(self.node, row)
        if n:
            with hou.undos.disabler():
                self.node.parm('mode1').set(1)
        self.refresh()
        return n

    def delete_stamps(self, row):
        n = self.counts.get(row, 0)
        if n and confirm('Delete the %d stamp(s) of this prototype?' % n):
            n = self.node.hdaModule().stamp_delete_proto(self.node, row)
        else:
            n = 0
        self.ctext = None
        self.refresh()
        return n

    def set_random(self, on):
        if self.node is not None:
            self.node.parm('protorand').set(1 if on else 0)
            self.refresh()

    def select(self, row, add=False):
        """A card: the working set becomes this row (Ctrl: the row is added or removed). The mousewheel cycles the working set and Random Prototype draws from it."""
        if self.node is not None:
            m = self.node.hdaModule()
            ws = m.stamp_workset(self.node)
            if add:
                rows = [r for r in ws if r != row] if row in ws else ws + [row]
            else:
                rows = [row]
            m.stamp_set_workset(self.node, rows, proto=row if row in rows else (rows[0] if rows else None))
            self.refresh()

    def favorite(self, row, on):
        if self.node is not None:
            self.node.hdaModule().stamp_set_favorite(self.node, row, on)
            self.refresh()

    def card(self, row, label, kind, weight, on, rand, fav, view, count=0, order=None):
        name, icon, size = VIEWS[view]
        b = StampCard(row)
        pixmap = self.thumbs.get(self.thumb_key(row))
        b.setIcon(QtGui.QIcon(pixmap if pixmap else stamp_icon(kind or 'Sphere')))
        b.setIconSize(QtCore.QSize(icon, icon))
        if view == 0:
            b.setText('%s     row %d   w %g   \u00d7%d' % (label, row, weight, count))
            b.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
            b.setFixedHeight(30)
            b.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        else:
            b.setText('%s\n%d  w %g' % (label, row, weight) + ('  \u00d7%d' % count if view == 2 else ''))
            b.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
            b.setFixedSize(size, size)
        b.setCheckable(True)
        b.setChecked(on)
        b.set_favorite(fav)
        b.place_star()
        b.set_order(order)
        b.on_menu = self.card_menu
        b.setToolTip('Prototype row %d (%s), %d stamp(s) use it\nClick: the stamp cycle is this one. Ctrl + click: add it to or remove it from the stamp cycle. Right click: select or delete its stamps.' % (row, label, count) + ('\nRandom Prototype is on: stamps draw a row of the working set by its weight.' if rand else ''))
        b.clicked.connect(lambda _=False, r=row: self.select(r, bool(QtWidgets.QApplication.keyboardModifiers() & QtCore.Qt.ControlModifier)))
        b.star.toggled.connect(lambda on, r=row: self.favorite(r, on))
        self.cardmap[row] = b
        return b

    def thumb_key(self, row):
        src = self.sources.get(row)
        return self.node.hdaModule().stamp_thumb_key(src) if src is not None else None

    # ---- the thumbnails: one per timer tick, so a big bank never freezes the pane
    def queue_thumbs(self):
        m = self.node.hdaModule()
        self.sources = m.stamp_thumb_sources(self.node)
        self.pending = []
        for row, src in self.sources.items():
            key = m.stamp_thumb_key(src)
            if key not in self.thumbs:
                self.pending.append((row, key, src))
        if self.pending:
            QtCore.QTimer.singleShot(20, self.thumb_step)

    def thumb_step(self):
        """Draw the next thumbnail and put it on its card."""
        if self.node is None or not self.pending:
            return
        row, key, src = self.pending.pop(0)
        pixmap = False
        try:
            image = stamp_render_thumb(self.node.hdaModule().stamp_thumb_triangles(self.node, src))
            pixmap = QtGui.QPixmap.fromImage(image) if image is not None else False
        except Exception:
            pixmap = False
        self.thumbs[key] = pixmap
        card = self.cardmap.get(row)
        if pixmap and card is not None and self.thumb_key(row) == key:
            card.setIcon(QtGui.QIcon(pixmap))
        if self.pending:
            QtCore.QTimer.singleShot(20, self.thumb_step)

    def process_thumbs(self):
        """Draw every pending thumbnail now (the tests; a script)."""
        while self.pending:
            self.thumb_step()

    def refresh(self):
        node = self.node
        if node is None:
            return
        try:
            node.path()
        except hou.ObjectWasDeleted:
            self.node = None
            return
        m = node.hdaModule()
        cur = node.evalParm('proto')
        rand = node.evalParm('protorand')
        ws = m.stamp_workset(node)
        favs = m.stamp_favorites(node)
        view = _VIEW[0]
        card = VIEWS[view][2]
        cols = 1 if view == 0 else max(1, (self.grid_host.width() - 4) // (card + 4))
        bank = m.bank_key(node)
        if bank != self.bkey:
            self.bkey = bank
            self.queue_thumbs()
            self.key = None
        query = self.search.text().strip().lower().split()
        text = node.evalParm('stamps')
        if text != self.ctext:
            self.ctext = text
            self.counts = m.stamp_counts(node, text)
        counts = self.counts
        key = (node.path(), bank, cur, rand, tuple(ws), tuple(sorted(favs)), view, tuple(query), self.fav_only.isChecked(), self.set_only.isChecked(), cols, tuple(sorted(counts.items())))
        if key != self.key:
            self.key = key
            while self.grid.count():
                w = self.grid.takeAt(0).widget()
                if w is not None:
                    w.deleteLater()
            self.cardmap = {}
            kinds = self.kinds.setdefault(node.path(), {})
            texts = {l[0]: (l[1] + ' ' + l[4]).lower() for l in m.stamp_labels(node)}
            cards = [c for c in stamp_cards(node, kinds)
                     if all(q in texts.get(c[0], '') for q in query) and (not self.fav_only.isChecked() or c[0] in favs) and (not self.set_only.isChecked() or c[0] in ws or not ws)]
            cards.sort(key=lambda c: c[0] not in favs)                  # the favourites first, the bank order inside
            first = cards[0][0] if cards else 1
            for i, (row, label, kind, weight) in enumerate(cards):
                self.grid.addWidget(self.card(row, label, kind, weight, (row in ws) if ws else (row == (cur or first)), rand, row in favs, view, counts.get(row, 0), ws.index(row) + 1 if row in ws else None), i // cols, i % cols)
            self.show_cycle(m.stamp_labels(node), ws, rand)
        brush = node.evalParm('brush')
        edit = node.evalParm('mode1') == 1
        for i, b in enumerate(self.shelf):
            b.setChecked(brush == i and not edit)
        self.random.setChecked(bool(rand))
        self.info.setText('%s%d stamp(s)%s' % ('Edit  |  ' if edit else '', len(m.stamp_lines(node.evalParm('stamps'))), '  |  random prototype' if rand else ''))

class StampModel(QtCore.QAbstractTableModel):
    """The placed stamps as a table (a virtual model over the stamp rows: thousands of rows cost nothing). Editing a cell edits the stamp (one undo step)."""
    COLUMNS = ('#', 'On', 'Row', 'X', 'Y', 'Z', 'Rx', 'Ry', 'Rz', 'Scale')

    def __init__(self, parent=None):
        super().__init__(parent)
        self.node = None
        self.rows = []
        self.text = None
        self.scope = 0                                                    # 0 the selected stamps (the edited one when it is not selected), 1 all of them
        self.op = 'set'                                                   # set, add, mul

    def targets(self, r):
        """The stamps an edit of row r reaches: all, the selection when r is in it, else r alone."""
        if self.scope == 1:
            return range(len(self.rows))
        m = self.node.hdaModule()
        sel = [int(i) for i in m.stamp_get_selection(self.node, len(self.rows))]
        return sel if r in sel else [r]

    def reload(self, force=False):
        """Read the stamps again when the text changed (a string compare otherwise)."""
        node = self.node
        text = node.evalParm('stamps') if node is not None else ''
        if text == self.text and not force:
            return False
        rows = node.hdaModule().stamp_rows(text) if node is not None and text.strip() else []
        self.text = text
        if len(rows) == len(self.rows) and len(rows):                      # same stamps, other values (an edit): the table keeps its selection
            self.rows = rows
            self.dataChanged.emit(self.index(0, 0), self.index(len(rows) - 1, len(self.COLUMNS) - 1))
            return True
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()
        return True

    def rowCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QtCore.QModelIndex()):
        return 0 if parent.isValid() else len(self.COLUMNS)

    def headerData(self, section, orientation, role=QtCore.Qt.DisplayRole):
        if role == QtCore.Qt.DisplayRole and orientation == QtCore.Qt.Horizontal:
            return self.COLUMNS[section]
        return None

    def data(self, index, role=QtCore.Qt.DisplayRole):
        r, c = index.row(), index.column()
        row = self.rows[r]
        if c == 0:
            return str(r) if role == QtCore.Qt.DisplayRole else None
        if c == 1:
            return (QtCore.Qt.Checked if row[10] > 0.5 else QtCore.Qt.Unchecked) if role == QtCore.Qt.CheckStateRole else None
        if role not in (QtCore.Qt.DisplayRole, QtCore.Qt.EditRole):
            return None
        if c == 2:
            return str(int(row[9]))
        value = row[{3: 0, 4: 1, 5: 2, 6: 3, 7: 4, 8: 5, 9: 6}[c]]
        return '%.4g' % value if role == QtCore.Qt.EditRole else ('%.2f' % value if c == 9 else '%.3f' % value if c < 6 else '%.1f' % value)

    def flags(self, index):
        base = QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable
        if index.column() == 1:
            return base | QtCore.Qt.ItemIsUserCheckable
        return base if index.column() == 0 else base | QtCore.Qt.ItemIsEditable

    def setData(self, index, value, role=QtCore.Qt.EditRole):
        r, c = index.row(), index.column()
        m = self.node.hdaModule()
        try:
            if c == 1 and role == QtCore.Qt.CheckStateRole:
                m.stamp_edit_rows(self.node, self.targets(r), on=1 if value in (QtCore.Qt.Checked, 2) else 0)
            elif c >= 2 and role == QtCore.Qt.EditRole:
                x = float(value)
                if c == 2:
                    m.stamp_edit_rows(self.node, self.targets(r), proto=int(x))
                elif c == 9:
                    m.stamp_edit_rows(self.node, self.targets(r), self.op, sx=x, sy=x, sz=x)
                else:
                    m.stamp_edit_rows(self.node, self.targets(r), self.op, **{m.STAMP_NAMES[{3: 0, 4: 1, 5: 2, 6: 3, 7: 4, 8: 5}[c]]: x})
            else:
                return False
        except (ValueError, hou.Error):
            return False
        self.reload()
        return True

class StampView(QtWidgets.QTableView):
    """The table: Del deletes the selected stamps, a right click opens the stamp menu."""
    def __init__(self, owner):
        super().__init__()
        self.owner = owner

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Delete and self.state() != QtWidgets.QAbstractItemView.EditingState:
            self.owner.do('delete')
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        self.owner.context_menu(self.indexAt(event.pos()).row(), event.globalPos())

class StampTable(QtWidgets.QWidget):
    """The STAMPS section: a collapsible table of every placed stamp. Its selection is the selection of the Edit mode (the hidden parameter `selection`), both ways."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.node = None
        self.selkey = None
        self.busy = False
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(4, 2, 4, 2)
        outer.setSpacing(3)
        self.toggle = QtWidgets.QToolButton()
        self.toggle.setCheckable(True)
        self.toggle.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(QtCore.Qt.RightArrow)
        self.toggle.setAutoRaise(True)
        self.toggle.setText('STAMPS')
        fit_text(self.toggle, 44, True)
        self.toggle.toggled.connect(self.on_toggle)
        outer.addWidget(self.toggle)
        self.bar = QtWidgets.QWidget()
        bar = QtWidgets.QHBoxLayout(self.bar)
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(4)
        bar.addWidget(QtWidgets.QLabel('Edit'))
        self.scope = QtWidgets.QComboBox()
        self.scope.addItems(('Selected', 'All'))
        self.scope.setMinimumWidth(96)
        self.scope.setToolTip('A cell you edit changes the selected stamps (select rows of the table, or stamps in the viewport; Ctrl + A selects all) or every stamp. When the edited row is not selected only that row changes.')
        self.scope.currentIndexChanged.connect(self.on_scope)
        bar.addWidget(self.scope)
        self.opbox = QtWidgets.QComboBox()
        self.opbox.addItems(('Set', 'Add', 'Multiply'))
        self.opbox.setToolTip('Set puts the typed value into every target; Add adds it to each one\'s own value (Rx / Ry / Rz, X / Y / Z); Multiply multiplies (Scale). Row and On are always set.')
        self.opbox.currentIndexChanged.connect(self.on_scope)
        bar.addWidget(self.opbox)
        self.count = QtWidgets.QLabel('')
        bar.addWidget(self.count, 1)
        self.bar.setVisible(False)
        outer.addWidget(self.bar)
        self.tools = QtWidgets.QWidget()
        tools = QtWidgets.QHBoxLayout(self.tools)
        tools.setContentsMargins(0, 0, 0, 0)
        tools.setSpacing(3)
        self.btn = {}
        for name, text, tip in (('delete', 'Delete', 'Delete the selected stamps (Del in the table, undoable).'), ('duplicate', 'Duplicate', 'Copy the selected stamps; the copies become the selection.'),
                                ('all', 'All', 'Select every stamp.'), ('none', 'None', 'Clear the selection.'), ('invert', 'Invert', 'Select the stamps that are not selected.'),
                                ('clear', 'Clear All', 'Remove every stamp (asks first, undoable).')):
            b = QtWidgets.QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            fit_text(b, 20)
            b.clicked.connect(lambda _=False, n=name: self.do(n))
            tools.addWidget(b)
            self.btn[name] = b
        tools.addStretch(1)
        self.tools.setVisible(False)
        outer.addWidget(self.tools)
        self.model = StampModel(self)
        self.view = StampView(self)
        self.view.setModel(self.model)
        self.view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.view.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.view.verticalHeader().setVisible(False)
        self.view.verticalHeader().setDefaultSectionSize(20)
        header = self.view.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        for column in (0, 1, 2):
            header.setSectionResizeMode(column, QtWidgets.QHeaderView.ResizeToContents)
        self.view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.view.setMinimumHeight(120)
        self.view.setMaximumHeight(260)
        self.view.setVisible(False)
        self.view.selectionModel().selectionChanged.connect(self.on_selection)
        outer.addWidget(self.view)

    def set_node(self, node):
        self.node = node
        self.model.node = node
        self.model.text = None
        self.selkey = None
        self.refresh(force=True)

    def do(self, name):
        """The buttons under the table (and Del): manage the stamps."""
        if self.node is None:
            return
        m = self.node.hdaModule()
        n = len(self.model.rows)
        if name == 'delete':
            m.stamp_delete_selected(self.node)
        elif name == 'duplicate':
            m.stamp_duplicate_selected(self.node)
        elif name == 'all':
            m.stamp_select_all(self.node)
        elif name == 'none':
            m.stamp_select_none(self.node)
        elif name == 'invert':
            m.stamp_select_invert(self.node)
        elif name == 'clear' and n and confirm('Remove all %d stamps?' % n):
            m.stamp_clear(self.node)
        self.refresh(force=True)

    def select_same(self, row):
        if self.node is not None and 0 <= row < len(self.model.rows):
            self.node.hdaModule().stamp_select_proto(self.node, int(self.model.rows[row][9]))
            self.refresh(force=True)

    def delete_same(self, row):
        if self.node is not None and 0 <= row < len(self.model.rows):
            proto = int(self.model.rows[row][9])
            n = self.model.rows[:, 9].tolist().count(proto) if len(self.model.rows) else 0
            if confirm('Delete the %d stamp(s) of prototype row %d?' % (n, proto)):
                self.node.hdaModule().stamp_delete_proto(self.node, proto)
            self.refresh(force=True)

    def context_menu(self, row, pos):
        menu = QtWidgets.QMenu(self)
        menu.addAction('Delete selected', lambda: self.do('delete'))
        menu.addAction('Duplicate selected', lambda: self.do('duplicate'))
        menu.addSeparator()
        menu.addAction('Select all', lambda: self.do('all'))
        menu.addAction('Select none', lambda: self.do('none'))
        menu.addAction('Invert selection', lambda: self.do('invert'))
        if row >= 0:
            menu.addSeparator()
            menu.addAction('Select the stamps of the same prototype', lambda: self.select_same(row))
            menu.addAction('Delete the stamps of the same prototype', lambda: self.delete_same(row))
        (menu.exec if hasattr(menu, 'exec') else menu.exec_)(pos)

    def on_scope(self, *args):
        self.model.scope = self.scope.currentIndex()
        self.model.op = ('set', 'add', 'mul')[self.opbox.currentIndex()]
        self.update_count()

    def update_count(self):
        n = len(self.model.rows)
        k = 0 if self.node is None else len(self.node.hdaModule().stamp_get_selection(self.node, n))
        self.count.setText('%s' % ('all %d stamps' % n if self.model.scope == 1 else '%d selected' % k if k else 'edited row only'))

    def on_toggle(self, checked):
        self.view.setVisible(checked)
        self.bar.setVisible(checked)
        self.tools.setVisible(checked)
        self.toggle.setArrowType(QtCore.Qt.DownArrow if checked else QtCore.Qt.RightArrow)
        self.refresh(force=True)

    def on_selection(self, *args):
        """The user selected rows of the table: that is the selection of the Edit mode."""
        if self.busy or self.node is None:
            return
        rows = sorted({i.row() for i in self.view.selectionModel().selectedRows()})
        self.node.hdaModule().stamp_set_selection(self.node, rows)
        self.selkey = self.node.evalParm('selection')
        self.update_count()

    def refresh(self, force=False):
        node = self.node
        if node is None:
            return
        n = len(node.hdaModule().stamp_lines(node.evalParm('stamps'))) if not self.view.isVisible() else None
        if self.view.isVisible() or force:
            self.busy = True
            try:
                self.model.reload()
                n = len(self.model.rows)
                sel = node.evalParm('selection')
                if sel != self.selkey or force:
                    self.selkey = sel
                    picked = node.hdaModule().stamp_get_selection(node, n)
                    model = self.view.selectionModel()
                    model.clearSelection()
                    for r in picked:
                        model.select(self.model.index(int(r), 0), QtCore.QItemSelectionModel.Select | QtCore.QItemSelectionModel.Rows)
            finally:
                self.busy = False
        self.toggle.setText('STAMPS   %d' % n)
        fit_text(self.toggle, 44, True)
        if self.view.isVisible():
            self.update_count()

class StampPanel(QtWidgets.QWidget):
    """The Parameters pane of a Stamp node: the cards, the Asset Library, the node's own parameters."""
    def __init__(self, parent=None, with_parms=True):
        super().__init__(parent)
        self.node = None
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.cards = StampCards(self)
        layout.addWidget(self.cards, 0)
        self.table = StampTable(self)
        layout.addWidget(self.table, 0)
        self.library = LibraryPanel(self) if 'LibraryPanel' in globals() else None
        if self.library is not None:
            layout.addWidget(self.library, 0)
        self.dialog = None
        if with_parms:
            self.dialog = hou.qt.ParmDialog(None, False)
            layout.addWidget(self.dialog, 1)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(800)

    def tick(self):
        self.cards.refresh()
        self.table.refresh()
        if self.library is not None:
            fit_text(self.library.toggle, 44, True)

    def set_node(self, node):
        ok = False
        try:
            ok = node is not None and node.type().name() == STAMP_TYPE
        except hou.ObjectWasDeleted:
            pass
        self.node = node if ok else None
        self.cards.setVisible(ok)
        self.cards.set_node(self.node)
        self.table.set_node(self.node)
        self.table.setVisible(ok)
        if self.library is not None:
            self.library.set_node(self.node)
            self.library.setVisible(ok)
        if self.dialog is not None:
            try:
                self.dialog.setNode(node)
            except Exception:
                self.dialog.setNode(None)

    def close_down(self):
        self.timer.stop()
        if self.dialog is not None:
            try:
                self.dialog.setNode(None)
            except Exception:
                pass

_panel = None

def onCreateInterface():
    global _panel
    _panel = StampPanel()
    return _panel

def onNodePathChanged(node):
    if _panel is not None:
        _panel.set_node(node)

def onActivateInterface():
    if _panel is not None:
        try:
            _panel.set_node(kwargs['paneTab'].currentNode())
        except Exception:
            pass

def onDestroyInterface():
    global _panel
    if _panel is not None:
        try:
            _panel.close_down()
        except Exception:
            pass
    _panel = None
