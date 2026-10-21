"""Arraytron Mode Palette: big icon cells with the mode title under each one, shown on top of the node's own parameters (a Python Panel in the Parameters pane, like Paint Instances).
The cell of the selected Distribution Mode is lit, the others are dim; a click sets the mode of the selected Arraytron node. It follows the selection in the network editor (the newest selected
Arraytron node, else the last one it showed) and re-reads the node a few times per second, so a change of the mode anywhere (the old menu, a script, an undo) shows at once.
The widget code is plain PySide (PySide6 in Houdini 21 and 22 builds, PySide2 in Houdini 20.5); the icons are the SVGs of tools/make_mode_icons.py (ICONS, filled in by the builder)."""
import hou
try:
    from PySide6 import QtCore, QtGui, QtWidgets, QtSvg
except ImportError:                                           # Houdini 20.5
    from PySide2 import QtCore, QtGui, QtWidgets, QtSvg

ICONS = {}                                                    # 'line_on' / 'line_off' ... -> SVG text (the builder writes them here)
TITLES = {'Line': 'line', 'Area': 'area', 'Grid / Matrix': 'grid', 'Circle / Radial': 'circle', 'Curve': 'curve', 'Surface': 'surface', 'Paint': 'paint', 'Cluster': 'cluster',
          'Imported Points': 'imported', 'Instance Place': 'place', 'Biome': 'biome'}
SHORT = {'Grid / Matrix': 'Grid', 'Circle / Radial': 'Circle', 'Imported Points': 'Imported', 'Instance Place': 'Place'}
TILE = 72                                                     # largest icon size in pixels
MIN_CELL = 48                                                 # narrowest cell: a single row of all the modes when the pane is wide enough, else rows of COLUMNS
COLUMNS = 6

def is_arraytron(node):
    try:
        return node is not None and node.type().name().startswith('arraytron::instancer') and node.parm('mode') is not None
    except hou.ObjectWasDeleted:
        return False

def newest_arraytron():
    for node in hou.selectedNodes():
        if is_arraytron(node):
            return node
    return None

class ModePalette(QtWidgets.QWidget):
    def __init__(self, parent=None, embedded=False):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.embedded = embedded                              # embedded: shows the node the Parameters pane shows, one fixed-height row
        self.node = None
        self.hover = -1
        self.tile = TILE
        self.cells = []                                       # (rect, mode index, title, key)
        self._renderers = {}
        self._last = None
        self.setMinimumHeight(40)
        self.setAutoFillBackground(True)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(250)
        self.refresh()

    # ---- state
    def renderer(self, name):
        if name not in self._renderers and name in ICONS:
            self._renderers[name] = QtSvg.QSvgRenderer(QtCore.QByteArray(ICONS[name].encode('utf8')))
        return self._renderers.get(name)

    def refresh(self):
        picked = None if self.embedded else newest_arraytron()
        if picked is not None and (self.node is None or picked.path() != self._path()):
            self.node = picked
        if self.node is not None and not is_arraytron(self.node):
            self.node = None
        state = None
        if self.node is not None:
            state = (self.node.path(), self.node.evalParm('mode'), tuple(self.node.parm('mode').menuLabels()))
        if state != self._last:
            self._last = state
            self.layout_cells()
            self.update()

    def _path(self):
        try:
            return self.node.path()
        except hou.ObjectWasDeleted:
            return None

    def mode(self):
        return self.node.evalParm('mode') if self.node is not None else -1

    def layout_cells(self):
        self.cells = []
        self.tile = TILE
        if self.node is None:
            return
        labels = [label for label in self.node.parm('mode').menuLabels() if label in TITLES]
        count = max(1, len(labels))
        width = max(self.width(), 200) - 12
        columns = count if width // count >= MIN_CELL else max(1, min(COLUMNS, width // MIN_CELL))
        cell_w = width // columns
        self.tile = max(30, min(TILE, cell_w - 12))
        cell_h = self.tile + 26
        for position, label in enumerate(labels):
            row, column = divmod(position, columns)
            index = list(self.node.parm('mode').menuLabels()).index(label)
            self.cells.append((QtCore.QRect(6 + column * cell_w, 30 + row * cell_h, cell_w, cell_h - 2), index, SHORT.get(label, label), TITLES[label]))
        rows = (count + columns - 1) // columns
        self.setMinimumHeight(30 + rows * cell_h + 4)
        if self.embedded:
            self.setFixedHeight(30 + rows * cell_h + 4)

    # ---- painting and mouse
    def sizeHint(self):
        return QtCore.QSize(11 * (MIN_CELL + 8) + 12, 30 + (MIN_CELL + 26) + 6)

    def resizeEvent(self, event):
        self.layout_cells()
        super().resizeEvent(event)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        p.fillRect(self.rect(), QtGui.QColor(36, 36, 36))
        font = p.font()
        font.setPointSizeF(8.5)
        p.setFont(font)
        if self.node is None:
            p.setPen(QtGui.QColor(150, 150, 150))
            p.drawText(self.rect().adjusted(8, 4, -8, -4), QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter | QtCore.Qt.TextWordWrap, 'Select an Arraytron node to choose its Distribution Mode.')
            return
        p.setPen(QtGui.QColor(170, 176, 186))
        p.drawText(QtCore.QRect(8, 4, self.width() - 16, 22), QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, 'DISTRIBUTION MODE   %s' % self.node.name())
        current = self.mode()
        for rect, index, title, key in self.cells:
            on = index == current
            icon = self.renderer('%s_%s' % (key, 'on' if on else 'off'))
            if self.hover == index and not on:
                p.setPen(QtCore.Qt.NoPen)
                p.setBrush(QtGui.QColor(255, 255, 255, 18))
                p.drawRoundedRect(rect, 8, 8)
            if icon is not None:
                icon.render(p, QtCore.QRectF(rect.left() + (rect.width() - self.tile) / 2.0, rect.top() + 2, self.tile, self.tile))
            font.setBold(on)
            p.setFont(font)
            p.setPen(QtGui.QColor(255, 226, 120) if on else QtGui.QColor(168, 176, 190))
            p.drawText(QtCore.QRect(rect.left() - 4, rect.top() + self.tile + 4, rect.width() + 8, 20), QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop, title)

    def cell_at(self, pos):
        for rect, index, title, key in self.cells:
            if rect.contains(pos):
                return index
        return -1

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint() if hasattr(event, 'position') else event.pos()
        index = self.cell_at(pos)
        if index != self.hover:
            self.hover = index
            self.setToolTip(self.node.parm('mode').menuLabels()[index] if index >= 0 and self.node is not None else '')
            self.update()

    def leaveEvent(self, event):
        self.hover = -1
        self.update()

    def mousePressEvent(self, event):
        if event.button() != QtCore.Qt.LeftButton or self.node is None:
            return
        pos = event.position().toPoint() if hasattr(event, 'position') else event.pos()
        index = self.cell_at(pos)
        if index >= 0:
            with hou.undos.group('Arraytron: Distribution Mode'):
                self.node.parm('mode').set(index)
            self.refresh()

    def set_node(self, node):
        self.node = node if is_arraytron(node) else None
        self._last = None
        self.refresh()

class ParmPanel(QtWidgets.QWidget):
    """The Parameters pane of an Arraytron node: the mode palette on top, the node's own parameters (hou.qt.ParmDialog) below."""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.palette = ModePalette(self, embedded=True)
        self.dialog = hou.qt.ParmDialog(None, False)
        layout.addWidget(self.palette, 0)
        self.library = LibraryPanel(self) if 'LibraryPanel' in globals() else None             # the Asset Library section (src/arraytron_libpanel.py), when this build has it
        if self.library is not None:
            layout.addWidget(self.library, 0)
        layout.addWidget(self.dialog, 1)

    def set_node(self, node):
        self.palette.set_node(node)
        self.palette.setVisible(self.palette.node is not None)
        if self.library is not None:
            self.library.set_node(node if self.palette.node is not None else None)
            self.library.setVisible(self.palette.node is not None)
        try:
            self.dialog.setNode(node)
        except Exception:
            self.dialog.setNode(None)

_panel = None

def onCreateInterface():
    """Python Panel entry point (the interface is registered with showInParametersPane for this node type)."""
    global _panel
    _panel = ParmPanel()
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
            _panel.dialog.setNode(None)
        except Exception:
            pass
    _panel = None
