"""Arraytron Stamp Gallery (the Layout-like Python Panel): hython tests/validate_gallery.py   (hython 22 or 20.5; build the Stamp first)
The panel needs the interface for hou.ui, so this tests what runs headless: the card list, and the widget itself in an offscreen Qt application
(the controls are read from and written to the node, the cards select the prototype, the brush buttons act). Writes tests/validation_gallery_<22|205>.json."""
import os, sys, json
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import hou
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import versions
ROOT=Path(__file__).resolve().parents[1];H205=versions.is_h205()
HDA=ROOT/('otls_h205' if H205 else 'dist')/('Arraytron_Stamp_v0.1.0%s.hda'%('_H205' if H205 else ''))
out={'groups':{}}
def check(group,cond,note=''):
    out['groups'].setdefault(group,[]).append(bool(cond))
    if not cond:print('FAIL',group,note)

hou.hda.installFile(str(HDA),force_use_assets=True);stage=hou.node('/stage')
a=stage.createNode('arraytron::stamp::0.1.0','stamp_a');m=a.hdaModule()
a.parm('protos').set(3)
for i,(p,w) in enumerate((('/World/Props/Fir',3.0),('/World/Props/Rock',2.0),('/World/Props/Stone',1.0)),1):a.parm('proto_prim%d'%i).set(p);a.parm('proto_weight%d'%i).set(w)
a.parm('proto_on3').set(0)

cards=m.gallery_cards(a)                                                       # 1: the cards
check('cards',len(cards)==2 and [c[0] for c in cards]==[1,2] and cards[0][1]=='Fir' and cards[0][4]==3.0 and cards[1][1]=='Rock',cards)
a.parm('proto_prim1').set('');check('cards',m.gallery_cards(a)[0][1]=='Built-in sphere' and m.gallery_cards(a)[0][3]=='Sphere')
a.parm('proto_prim1').set('/World/Props/Fir')

try:from PySide6 import QtWidgets
except ImportError:from PySide2 import QtWidgets
app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
w=m.gallery_widget();w.node=a;w.refresh()                                      # 2: the widget reads the node
check('widget',w.node==a and w.pick.count()>=1 and abs(w.widgets['place_def_scale']._parts[0].value()-a.evalParm('place_def_scale'))<1e-6)
check('widget',len(w.widgets['place_def_scalerange']._parts)==2 and 'placed' in w.info.text() or 'No instances' in w.info.text(),w.info.text())
buttons=[b for b in w.grid_host.findChildren(QtWidgets.QToolButton)];check('widget',len(buttons)==3,len(buttons))      # Auto + 2 enabled rows

w.widgets['place_def_scale']._parts[0].setValue(2.5);check('controls',abs(a.evalParm('place_def_scale')-2.5)<1e-6)        # 3: writing back
w.widgets['place_def_scalerange']._parts[1].setValue(1.8);check('controls',abs(a.evalParmTuple('place_def_scalerange')[1]-1.8)<1e-6)
w.widgets['place_def_protorand']._parts[0].setChecked(True);check('controls',a.evalParm('place_def_protorand')==1)
w.widgets['place_snap']._parts[0].setValue(0.5);check('controls',abs(a.evalParm('place_snap')-0.5)<1e-6)
w._select(2);check('controls',a.evalParm('place_def_proto')==2)                                                           # the card of row 2
w._select(0);check('controls',a.evalParm('place_def_proto')==0)
a.parm('place_def_scale').set(4.0);w.refresh();check('controls',abs(w.widgets['place_def_scale']._parts[0].value()-4.0)<1e-6)    # the node's change shows in the panel

for k in range(3):m.place_add(a,(float(k),0.0,0.0))                              # 4: the brush buttons
check('buttons',a.evalParm('places')==3)
w._delete_last();check('buttons',a.evalParm('places')==2)
w._clear();check('buttons',a.evalParm('places')==0)

ok=all(all(v) for v in out['groups'].values());out['ALL_PASSED']=ok
(ROOT/'tests'/('validation_gallery_%s.json'%('205' if H205 else '22'))).write_text(json.dumps(out,indent=1))
print('ALL PASSED' if ok else 'FAILED',{k:len(v) for k,v in out['groups'].items()})
sys.exit(0 if ok else 1)
