
# ---- Asset Library panel (src/arraytron_libpanel.py): the library of src/arraytron_library.py as a collapsible section of the Arraytron Parameters pane.
# A category selector with + / Rename / Delete, a search box, a grid of thumbnails with the asset names, and buttons to import (Asset Catalog, USD files, a folder) and to add the selected
# asset to the node's Prototype Bank. Double-click an asset to add it; drag USD files from the file browser onto the grid; right-click an asset for its menu.
THUMB = 64
THUMB_VERSION = 2                                              # the thumbnail renderer: an asset it could not draw is tried again after an upgrade of it

def _placeholder_icon(asset):
    """A drawn thumbnail for an asset without one: a tile coloured by the category with the first letter of the name."""
    pixmap = QtGui.QPixmap(THUMB, THUMB)
    pixmap.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    hue = (sum(ord(ch) for ch in asset.get('category', '')) * 37) % 360
    painter.setBrush(QtGui.QColor.fromHsv(hue, 90, 110))
    painter.setPen(QtGui.QColor.fromHsv(hue, 120, 170))
    painter.drawRoundedRect(2, 2, THUMB - 4, THUMB - 4, 9, 9)
    painter.setPen(QtGui.QColor(245, 245, 245))
    font = painter.font()
    font.setPixelSize(30)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(QtCore.QRect(0, 0, THUMB, THUMB), QtCore.Qt.AlignCenter, (asset['name'][:1] or '?').upper())
    painter.end()
    return QtGui.QIcon(pixmap)

def render_usd_thumbnail(file_path, prim_path='', size=128):
    """A small software render of a USD asset (its meshes and cubes, flat shaded, from a fixed three-quarter view) as a QImage: no renderer needed. Returns None when there is nothing to draw."""
    import math
    from pxr import Usd, UsdGeom, Gf
    stage = Usd.Stage.Open(file_path, Usd.Stage.LoadAll)
    root = stage.GetPrimAtPath(prim_path) if prim_path else stage.GetDefaultPrim()
    if root is None or not root.IsValid():
        root = stage.GetPseudoRoot()
    cache = UsdGeom.XformCache()
    triangles = []                                                  # (three world points, base colour)
    for prim in Usd.PrimRange(root):
        if not prim.IsA(UsdGeom.Gprim):
            continue
        matrix = cache.GetLocalToWorldTransform(prim)
        color = (0.62, 0.70, 0.56)
        try:
            shown = UsdGeom.Gprim(prim).GetDisplayColorAttr().Get()
            if shown:
                color = (float(shown[0][0]), float(shown[0][1]), float(shown[0][2]))
        except Exception:
            pass
        if prim.IsA(UsdGeom.Mesh):
            mesh = UsdGeom.Mesh(prim)
            points = mesh.GetPointsAttr().Get() or []
            world = [matrix.Transform(Gf.Vec3d(p)) for p in points]
            counts = mesh.GetFaceVertexCountsAttr().Get() or []
            indices = mesh.GetFaceVertexIndicesAttr().Get() or []
            at = 0
            for count in counts:
                face = indices[at:at + count]
                at += count
                for k in range(1, len(face) - 1):
                    triangles.append(((world[face[0]], world[face[k]], world[face[k + 1]]), color))
        elif prim.IsA(UsdGeom.Sphere) or prim.IsA(UsdGeom.Cylinder) or prim.IsA(UsdGeom.Cone) or prim.IsA(UsdGeom.Capsule):
            rings = []                                              # (height along the axis, radius) from one end to the other, 16 segments round
            axis = 'Z'
            if prim.IsA(UsdGeom.Sphere):
                r = float(UsdGeom.Sphere(prim).GetRadiusAttr().Get() or 1.0)
                rings = [(-r * math.cos(math.pi * k / 8.0), r * math.sin(math.pi * k / 8.0)) for k in range(9)]
                axis = 'Y'
            else:
                shape = UsdGeom.Cylinder(prim) if prim.IsA(UsdGeom.Cylinder) else UsdGeom.Cone(prim) if prim.IsA(UsdGeom.Cone) else UsdGeom.Capsule(prim)
                r = float(shape.GetRadiusAttr().Get() or 1.0)
                h = float(shape.GetHeightAttr().Get() or 2.0) * 0.5
                axis = str(shape.GetAxisAttr().Get() or 'Z')
                rings = [(-h, r), (h, 0.0 if prim.IsA(UsdGeom.Cone) else r)] if not prim.IsA(UsdGeom.Capsule) else [(-h - r, 0.0), (-h, r), (h, r), (h + r, 0.0)]
                if prim.IsA(UsdGeom.Cone):
                    rings = [(-h, r), (h, 0.0)]
            def place(height, radius, angle):
                u, v = radius * math.cos(angle), radius * math.sin(angle)
                local = (height, u, v) if axis == 'X' else (u, height, v) if axis == 'Y' else (u, v, height)
                return matrix.Transform(Gf.Vec3d(*local))
            for k in range(len(rings) - 1):
                for j in range(16):
                    a0, a1 = 2.0 * math.pi * j / 16.0, 2.0 * math.pi * (j + 1) / 16.0
                    p00, p01 = place(rings[k][0], rings[k][1], a0), place(rings[k][0], rings[k][1], a1)
                    p10, p11 = place(rings[k + 1][0], rings[k + 1][1], a0), place(rings[k + 1][0], rings[k + 1][1], a1)
                    triangles.append(((p00, p01, p11), color))
                    triangles.append(((p00, p11, p10), color))
        elif prim.IsA(UsdGeom.Cube):
            h = float(UsdGeom.Cube(prim).GetSizeAttr().Get() or 1.0) * 0.5
            corners = [matrix.Transform(Gf.Vec3d(x * h, y * h, z * h)) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
            for a_, b_, c_, d_ in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
                triangles.append(((corners[a_], corners[b_], corners[c_]), color))
                triangles.append(((corners[a_], corners[c_], corners[d_]), color))
    if not triangles:
        return None
    if len(triangles) > 30000:
        triangles = triangles[::len(triangles) // 30000 + 1]
    yaw, pitch = math.radians(35.0), math.radians(24.0)
    cy, sy, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
    def view(p):
        x, y, z = p[0] * cy - p[2] * sy, p[1], p[0] * sy + p[2] * cy
        return x, y * cp - z * sp, y * sp + z * cp                  # screen x, screen y (up), depth
    projected = [([view(p) for p in tri], color) for tri, color in triangles]
    xs = [q[0] for tri, _ in projected for q in tri]
    ys = [q[1] for tri, _ in projected for q in tri]
    span = max(max(xs) - min(xs), max(ys) - min(ys), 1e-9)
    scale = (size - 14) / span
    ox, oy = (size - (max(xs) - min(xs)) * scale) / 2.0 - min(xs) * scale, (size + (max(ys) - min(ys)) * scale) / 2.0 + min(ys) * scale
    image = QtGui.QImage(size, size, QtGui.QImage.Format_ARGB32)
    image.fill(QtGui.QColor(44, 48, 56))
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.Antialiasing)
    painter.setPen(QtCore.Qt.NoPen)
    light = (0.45, 0.75, 0.5)
    for tri, color in sorted(projected, key=lambda t: sum(q[2] for q in t[0])):
        a_, b_, c_ = tri
        ux, uy, uz = b_[0] - a_[0], b_[1] - a_[1], b_[2] - a_[2]
        vx, vy, vz = c_[0] - a_[0], c_[1] - a_[1], c_[2] - a_[2]
        nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
        length = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
        shade = 0.35 + 0.65 * abs((nx * light[0] + ny * light[1] + nz * light[2]) / length)
        painter.setBrush(QtGui.QColor(min(255, int(color[0] * 255 * shade)), min(255, int(color[1] * 255 * shade)), min(255, int(color[2] * 255 * shade))))
        painter.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(q[0] * scale + ox, oy - q[1] * scale) for q in tri]))
    painter.end()
    return image

class GalleryDialog(QtWidgets.QDialog):
    """Pick assets of the Solaris Asset Catalog (Asset Gallery) and import them into the library under a category."""
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Import from the Asset Catalog')
        self.resize(560, 420)
        self.assets = []
        layout = QtWidgets.QVBoxLayout(self)
        self.info = QtWidgets.QLabel('')
        layout.addWidget(self.info)
        self.grid = QtWidgets.QListWidget()
        self.grid.setViewMode(QtWidgets.QListView.IconMode)
        self.grid.setIconSize(QtCore.QSize(THUMB, THUMB))
        self.grid.setResizeMode(QtWidgets.QListView.Adjust)
        self.grid.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.grid.setGridSize(QtCore.QSize(THUMB + 30, THUMB + 34))
        self.grid.setWordWrap(True)
        layout.addWidget(self.grid, 1)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel('Category'))
        self.category = QtWidgets.QComboBox()
        self.category.setEditable(True)
        self.category.addItems(list(data['categories']))
        row.addWidget(self.category, 1)
        self.import_button = QtWidgets.QPushButton('Import selected')
        self.import_button.clicked.connect(self.accept)
        cancel = QtWidgets.QPushButton('Cancel')
        cancel.clicked.connect(self.reject)
        row.addWidget(self.import_button)
        row.addWidget(cancel)
        layout.addLayout(row)
        self.fill()

    def fill(self):
        try:
            source = hou.ui.sharedAssetGalleryDataSource(None)
            self.assets = gallery_assets(source) if source is not None else []
        except Exception as error:
            self.assets = []
            self.info.setText('The Asset Catalog could not be read (%s).' % error)
            return
        self.info.setText('%d USD assets in the Asset Catalog. Select the ones to import (Ctrl / Shift for several).' % len(self.assets) if self.assets else
                          'The Asset Catalog has no USD assets yet. Add some in the Asset Catalog pane (Windows > Asset Catalog), or use Add USD Files.')
        for asset in self.assets:
            icon = QtGui.QIcon()
            if asset['thumb']:
                pixmap = QtGui.QPixmap()
                if pixmap.loadFromData(bytes(asset['thumb'])):
                    icon = QtGui.QIcon(pixmap)
            if icon.isNull():
                icon = _placeholder_icon({'name': asset['name'], 'category': ''})
            item = QtWidgets.QListWidgetItem(icon, asset['name'])
            item.setData(QtCore.Qt.UserRole, asset['id'])
            self.grid.addItem(item)

    def chosen(self):
        return {item.data(QtCore.Qt.UserRole) for item in self.grid.selectedItems()}

class LibraryPanel(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.node = None
        self.data = load_library()
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(4, 2, 4, 2)
        outer.setSpacing(3)
        self.toggle = QtWidgets.QToolButton()
        self.toggle.setCheckable(True)
        self.toggle.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(QtCore.Qt.RightArrow)
        self.toggle.setAutoRaise(True)
        self.toggle.setText('ASSET LIBRARY')
        self.toggle.toggled.connect(self.on_toggle)
        outer.addWidget(self.toggle)
        self.body = QtWidgets.QWidget()
        outer.addWidget(self.body)
        body = QtWidgets.QVBoxLayout(self.body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(3)
        top = QtWidgets.QHBoxLayout()
        self.category = QtWidgets.QComboBox()
        self.category.currentIndexChanged.connect(self.refresh_list)
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText('Search name or tag')
        self.search.textChanged.connect(self.refresh_list)
        top.addWidget(self.category, 1)
        for text, tip, slot in (('+', 'New category', self.new_category), ('Rename', 'Rename the category', self.rename_category), ('Delete', 'Delete the category (its assets move to Uncategorized)', self.delete_category)):
            button = QtWidgets.QToolButton()
            button.setText(text)
            button.setToolTip(tip)
            button.clicked.connect(slot)
            top.addWidget(button)
        body.addLayout(top)
        body.addWidget(self.search)
        self.grid = QtWidgets.QListWidget()
        self.grid.setViewMode(QtWidgets.QListView.IconMode)
        self.grid.setIconSize(QtCore.QSize(THUMB, THUMB))
        self.grid.setResizeMode(QtWidgets.QListView.Adjust)
        self.grid.setMovement(QtWidgets.QListView.Static)
        self.grid.setGridSize(QtCore.QSize(THUMB + 26, THUMB + 32))
        self.grid.setWordWrap(True)
        self.grid.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.grid.setMinimumHeight(THUMB + 40)
        self.grid.setMaximumHeight(2 * (THUMB + 40))
        self.grid.setAcceptDrops(True)
        self.grid.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.grid.customContextMenuRequested.connect(self.context_menu)
        self.grid.itemDoubleClicked.connect(lambda item: self.add_selected())
        self.grid.dragEnterEvent = self._drag_enter
        self.grid.dragMoveEvent = self._drag_enter
        self.grid.dropEvent = self._drop
        body.addWidget(self.grid)
        buttons = QtWidgets.QHBoxLayout()
        for text, tip, slot in (('Add to Bank', 'Add the selected assets to the Prototype Bank of this node (double-click does the same)', self.add_selected),
                                ('Asset Catalog...', 'Import assets from the Solaris Asset Catalog (Asset Gallery)', self.import_gallery_dialog),
                                ('USD Files...', 'Add USD files to the library', self.import_files_dialog),
                                ('Folder...', 'Add every USD file under a folder to the library', self.import_folder_dialog)):
            button = QtWidgets.QPushButton(text)
            button.setToolTip(tip)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        body.addLayout(buttons)
        self.status = QtWidgets.QLabel('')
        self.status.setStyleSheet('color: #9aa4b2;')
        body.addWidget(self.status)
        self.body.setVisible(False)
        self.reload_categories()

    # ---- data
    def save(self):
        try:
            save_library(self.data)
        except OSError as error:
            self.say('Could not save the library: %s' % error)

    def say(self, text):
        self.status.setText(text)

    def current_category(self):
        index = self.category.currentIndex()
        return None if index <= 0 else self.category.itemData(index)

    def reload_categories(self, select=None):
        self.category.blockSignals(True)
        self.category.clear()
        self.category.addItem('All (%d)' % len(self.data['assets']), None)
        names = list(self.data['categories'])
        if any(a.get('category') == UNCATEGORIZED for a in self.data['assets']):
            names.append(UNCATEGORIZED)
        for name in names:
            count = sum(1 for a in self.data['assets'] if a.get('category') == name)
            self.category.addItem('%s (%d)' % (name, count), name)
        index = max(0, next((i for i in range(self.category.count()) if self.category.itemData(i) == select), 0)) if select else 0
        self.category.setCurrentIndex(index)
        self.category.blockSignals(False)
        self.refresh_list()

    def refresh_list(self, *args):
        self.grid.clear()
        for asset in query_assets(self.data, self.current_category(), self.search.text()):
            icon = None
            if not asset.get('thumb') and asset.get('file') and os.path.isfile(asset['file']) and int(asset.get('nothumb') or 0) < THUMB_VERSION:
                self.make_thumbnail(asset)
            if asset.get('thumb'):
                path = os.path.join(library_dir(), asset['thumb'])
                if os.path.exists(path):
                    icon = QtGui.QIcon(path)
            item = QtWidgets.QListWidgetItem(icon or _placeholder_icon(asset), asset['name'])
            item.setData(QtCore.Qt.UserRole, asset['id'])
            item.setToolTip('%s\n%s%s\nCategory: %s' % (asset['name'], asset['file'], ('  ' + asset['prim']) if asset.get('prim') else '', asset.get('category', '')))
            self.grid.addItem(item)
        if getattr(self, '_dirty', False):
            self._dirty = False
            self.save()
        self.toggle.setText('ASSET LIBRARY   %d' % len(self.data['assets']))

    def make_thumbnail(self, asset):
        """Render a thumbnail for an asset that has none and keep it in the library folder (one try per asset and renderer version: a file that cannot be drawn is marked nothumb)."""
        try:
            image = render_usd_thumbnail(asset['file'], asset.get('prim', ''))
            if image is not None:
                folder = os.path.join(library_dir(), 'thumbs')
                os.makedirs(folder, exist_ok=True)
                relative = 'thumbs/%s.png' % asset['id']
                if image.save(os.path.join(library_dir(), relative)):
                    asset['thumb'] = relative
            if not asset.get('thumb'):
                asset['nothumb'] = THUMB_VERSION
        except Exception:
            asset['nothumb'] = THUMB_VERSION
        self._dirty = True

    def selected_assets(self):
        return [a for a in (find_asset(self.data, item.data(QtCore.Qt.UserRole)) for item in self.grid.selectedItems()) if a is not None]

    def set_node(self, node):
        self.node = node

    def on_toggle(self, checked):
        self.body.setVisible(checked)
        self.toggle.setArrowType(QtCore.Qt.DownArrow if checked else QtCore.Qt.RightArrow)
        if checked:
            self.data = load_library()
            self.reload_categories(self.current_category())

    # ---- categories
    def new_category(self):
        name, ok = QtWidgets.QInputDialog.getText(self, 'New category', 'Category name')
        if ok and add_category(self.data, name):
            self.save()
            self.reload_categories(clean_name(name))

    def rename_category(self):
        old = self.current_category()
        if old is None or old == UNCATEGORIZED:
            return
        name, ok = QtWidgets.QInputDialog.getText(self, 'Rename category', 'New name', text=old)
        if ok and rename_category(self.data, old, name):
            self.save()
            self.reload_categories(clean_name(name))

    def delete_category(self):
        name = self.current_category()
        if name is None or name == UNCATEGORIZED:
            return
        if QtWidgets.QMessageBox.question(self, 'Delete category', 'Delete "%s"? Its assets stay in the library as Uncategorized.' % name) == QtWidgets.QMessageBox.Yes:
            delete_category(self.data, name)
            self.save()
            self.reload_categories()

    # ---- importing
    def finish_import(self, assets, what):
        self.save()
        self.reload_categories(self.current_category())
        self.say('Imported %d %s into %s.' % (len(assets), what, self.current_category() or 'the library'))

    def import_category(self):
        return self.current_category() if self.current_category() not in (None, UNCATEGORIZED) else None

    def import_gallery_dialog(self):
        dialog = GalleryDialog(self.data, self)
        if dialog.exec_() if hasattr(dialog, 'exec_') else dialog.exec():
            added = import_gallery(self.data, hou.ui.sharedAssetGalleryDataSource(None), dialog.chosen(), category=dialog.category.currentText() or None)
            self.finish_import(added, 'assets')

    def import_files_dialog(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(self, 'Add USD files to the library', '', 'USD files (*.usd *.usda *.usdc *.usdz)')
        if paths:
            self.finish_import(import_files(self.data, paths, category=self.import_category()), 'files')

    def import_folder_dialog(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, 'Add every USD file under a folder')
        if folder:
            self.finish_import(import_files(self.data, [folder], category=self.import_category()), 'files')

    def _drag_enter(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def _drop(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if paths:
            self.finish_import(import_files(self.data, paths, category=self.import_category()), 'files')
            event.acceptProposedAction()

    # ---- using and editing
    def add_selected(self):
        assets = self.selected_assets()
        if not assets:
            self.say('Select an asset first.')
            return
        if self.node is None:
            self.say('Select an Arraytron node first.')
            return
        rows = [add_to_bank(self.node, asset) for asset in assets]
        self.say('Added %d to the Prototype Bank (row %s).' % (len(rows), ', '.join(str(r) for r in rows)))

    def context_menu(self, pos):
        assets = self.selected_assets()
        if not assets:
            return
        menu = QtWidgets.QMenu(self)
        menu.addAction('Add to Bank', self.add_selected)
        move = menu.addMenu('Move to category')
        for name in list(self.data['categories']) + [UNCATEGORIZED]:
            move.addAction(name, lambda name=name: self.move_selected(name))
        move.addAction('New category...', lambda: self.move_selected(None))
        menu.addAction('Rename...', self.rename_selected)
        menu.addAction('Tags...', self.tag_selected)
        menu.addAction('Show in file browser', lambda: self.reveal(assets[0]))
        menu.addSeparator()
        menu.addAction('Remove from the library', self.remove_selected)
        menu.exec_(self.grid.mapToGlobal(pos)) if hasattr(menu, 'exec_') else menu.exec(self.grid.mapToGlobal(pos))

    def move_selected(self, name):
        if name is None:
            name, ok = QtWidgets.QInputDialog.getText(self, 'New category', 'Category name')
            if not ok or not clean_name(name):
                return
        for asset in self.selected_assets():
            set_asset(self.data, asset['id'], category=name)
        self.save()
        self.reload_categories(self.current_category())

    def rename_selected(self):
        assets = self.selected_assets()
        if assets:
            name, ok = QtWidgets.QInputDialog.getText(self, 'Rename asset', 'Name', text=assets[0]['name'])
            if ok and set_asset(self.data, assets[0]['id'], name=name):
                self.save()
                self.refresh_list()

    def tag_selected(self):
        assets = self.selected_assets()
        if assets:
            text, ok = QtWidgets.QInputDialog.getText(self, 'Tags', 'Tags (comma separated)', text=', '.join(assets[0].get('tags', [])))
            if ok:
                for asset in assets:
                    set_asset(self.data, asset['id'], tags=[t for t in text.split(',')])
                self.save()
                self.refresh_list()

    def remove_selected(self):
        assets = self.selected_assets()
        if assets and QtWidgets.QMessageBox.question(self, 'Remove', 'Remove %d asset(s) from the library? The USD files are not deleted.' % len(assets)) == QtWidgets.QMessageBox.Yes:
            for asset in assets:
                remove_asset(self.data, asset['id'])
            self.save()
            self.reload_categories(self.current_category())

    def reveal(self, asset):
        import subprocess
        folder = os.path.dirname(asset['file'])
        if os.path.isdir(folder):
            if os.name == 'nt':
                os.startfile(folder)
            else:
                subprocess.Popen(['xdg-open', folder])
