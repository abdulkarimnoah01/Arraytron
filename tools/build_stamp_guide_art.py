"""Draw the diagrams and infographics of the Arraytron Stamp guide into docs/img/: hython tools/build_stamp_guide_art.py   (hython 22 or 20.5, offscreen Qt; no Houdini interface needed).
The layout diagram is drawn from the Stamp's own layout function (stamp_group_offsets), so it shows what the tool does. The screenshots of the Parameters pane (panel_*.png) are captured from a running Houdini, not drawn here."""
import os, sys, math, importlib.util
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import numpy as np
try:
    from PySide6 import QtGui, QtCore, QtWidgets
except ImportError:
    from PySide2 import QtGui, QtCore, QtWidgets
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs'/'img';OUT.mkdir(parents=True,exist_ok=True)
app=QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
spec=importlib.util.spec_from_file_location('stamp_core_art',ROOT/'src'/'stamp_core.py');core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)

BG=QtGui.QColor('#262a30');PANEL=QtGui.QColor('#323841');LINE=QtGui.QColor('#4a525e');TEXT=QtGui.QColor('#e8eaed');DIM=QtGui.QColor('#9aa0a6')
ORANGE=QtGui.QColor('#ffa030');GREEN=QtGui.QColor('#3fa660');BLUE=QtGui.QColor('#5aa0ff');RED=QtGui.QColor('#e5534b');SAND=QtGui.QColor('#d9c58a');GREY=QtGui.QColor('#a0a0a0')
COL={1:GREY,2:GREEN,3:SAND,4:RED}
FONT='SideFX Source Sans Pro' if 'SideFX Source Sans Pro' in QtGui.QFontDatabase.families() else 'DejaVu Sans'                  # the offscreen Qt only sees the fonts of Houdini
Qt=QtCore.Qt

class Canvas(object):
    def __init__(self,w,h,name,title=None,sub=None):
        self.w,self.h,self.name=w,h,name;self.img=QtGui.QImage(w,h,QtGui.QImage.Format_ARGB32);self.img.fill(BG);self.p=QtGui.QPainter(self.img);self.p.setRenderHint(QtGui.QPainter.Antialiasing);self.p.setRenderHint(QtGui.QPainter.TextAntialiasing)
        if title:self.text(36,22,title,22,TEXT,True)
        if sub:self.text(36,56,sub,12.5,DIM)
    def font(self,size,bold=False):
        f=QtGui.QFont(FONT);f.setPointSizeF(size*1.12);f.setBold(bold);self.p.setFont(f)
    def text(self,x,y,s,size=12,color=TEXT,bold=False,w=None,h=None,align=Qt.AlignLeft|Qt.AlignTop,wrap=False):
        self.font(size,bold);self.p.setPen(color);r=QtCore.QRectF(x,y,w if w else self.w-x,h if h else 400)
        self.p.drawText(r,int(align)|(int(Qt.TextWordWrap) if wrap else 0),s)
    def center(self,x,y,w,s,size=12,color=TEXT,bold=False,wrap=True,h=200):
        self.text(x,y,s,size,color,bold,w,h,Qt.AlignHCenter|Qt.AlignTop,wrap)
    def box(self,x,y,w,h,fill=PANEL,line=LINE,r=10,lw=1.5):
        self.p.setBrush(fill);self.p.setPen(QtGui.QPen(line,lw) if line else Qt.NoPen);self.p.drawRoundedRect(QtCore.QRectF(x,y,w,h),r,r)
    def arrow(self,x1,y1,x2,y2,color=DIM,lw=2.2,head=10):
        self.p.setPen(QtGui.QPen(color,lw));self.p.drawLine(QtCore.QPointF(x1,y1),QtCore.QPointF(x2,y2));a=math.atan2(y2-y1,x2-x1)
        self.p.setBrush(color);self.p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(x2,y2),QtCore.QPointF(x2-head*math.cos(a-0.4),y2-head*math.sin(a-0.4)),QtCore.QPointF(x2-head*math.cos(a+0.4),y2-head*math.sin(a+0.4))]))
    def circle(self,x,y,r,fill,line=QtGui.QColor(20,20,20),lw=1.2):
        self.p.setBrush(fill);self.p.setPen(QtGui.QPen(line,lw) if line else Qt.NoPen);self.p.drawEllipse(QtCore.QPointF(x,y),r,r)
    def pill(self,x,y,s,color=ORANGE,fg=QtGui.QColor('#202020'),size=11):
        self.font(size,True);m=self.p.fontMetrics();w=m.horizontalAdvance(s)+18;self.box(x,y,w,26,color,None,13);self.text(x+9,y+3,s,size,fg,True);return w
    def save(self):
        self.p.end();self.img.save(str(OUT/self.name));print('wrote',self.name)

def tree(c,x,y,ang,size,color=GREEN):
    """A small tree (a cone on a trunk) standing at x, y, its up turned by ang degrees from the screen's up."""
    c.p.save();c.p.translate(x,y);c.p.rotate(ang);c.p.setPen(QtGui.QPen(QtGui.QColor(20,20,20),1));c.p.setBrush(QtGui.QColor('#7a5a3a'));c.p.drawRect(QtCore.QRectF(-size*0.08,-size*0.25,size*0.16,size*0.25))
    c.p.setBrush(color);c.p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(0,-size),QtCore.QPointF(-size*0.38,-size*0.22),QtCore.QPointF(size*0.38,-size*0.22)]));c.p.restore()

# ------------------------------------------------------------------ 1 overview
def overview():
    c=Canvas(1600,720,'d_overview.png','How Arraytron Stamp works','One Solaris node. You place by hand in the viewport; the node writes one point instancer.')
    c.box(40,140,300,300,PANEL);c.center(40,150,300,'The scene (input 1)',15,TEXT,True)
    for k,(label,col) in enumerate((('Ground or a mesh to Place On',GREEN),('Props and prototypes (prims)',SAND),('Other stamps (stack on them)',GREY))):
        c.box(65,200+k*70,250,50,BG,col,8);c.center(65,212+k*70,250,label,11.5,TEXT)
    c.arrow(340,290,430,290,ORANGE,3);c.text(345,255,'Place On',11,ORANGE,True)
    c.box(430,110,520,400,PANEL,ORANGE,14,2.5);c.center(430,122,520,'Arraytron Stamp',20,ORANGE,True);c.center(430,155,520,'one Python LOP',12.5,DIM)
    c.box(460,200,460,110,BG,LINE,8);c.center(460,208,460,'The Stamps text  (one parameter)',13.5,TEXT,True);c.center(460,238,460,'one line per stamp:',11.5,DIM);c.center(460,262,460,'x y z    rx ry rz    sx sy sz    prototype row    on',12.5,SAND,True)
    c.box(460,330,460,150,BG,LINE,8);c.center(460,338,460,'The Prototype Bank',13.5,TEXT,True);c.center(460,368,460,'prims of the scene, USD files, inputs 2 to 4, group rows;\nweight, scale, scale random, rotation offset for each row',11.5,DIM,False,True)
    c.arrow(950,310,1060,310,ORANGE,3);c.box(1060,200,280,220,PANEL,LINE,12);c.center(1060,212,280,'UsdGeomPointInstancer',14,TEXT,True);c.center(1060,245,280,'/World/Stamps',12,SAND,True);c.center(1070,285,260,'prototypes as internal references, one id per line of the text',11.5,DIM,False,True)
    c.arrow(1340,310,1440,310,ORANGE,3);c.box(1440,230,120,160,BG,LINE,10);c.center(1440,250,120,'Karma\nHydra\nyour render',12.5,TEXT,False,True)
    c.box(430,560,230,110,PANEL,BLUE,10);c.center(430,570,230,'Viewer state',14,BLUE,True);c.center(436,598,218,'Place  Delete  Paint  Group  Edit\nhotkeys, HUD, ghost preview',11,DIM,False,True)
    c.arrow(545,560,545,512,BLUE,2.5);c.text(556,528,'a click adds a line',10.5,BLUE)
    c.box(720,560,230,110,PANEL,GREEN,10);c.center(720,570,230,'Parameters pane',14,GREEN,True);c.center(726,598,218,'shelf, prototype cards,\nSTAMPS sheet, Asset Library',11,DIM,False,True)
    c.arrow(835,560,835,512,GREEN,2.5);c.text(846,528,'edits the same text',10.5,GREEN)
    c.text(1000,560,'Light on purpose',14,TEXT,True);c.text(1000,590,'a placement is one parameter write (about 1 ms);\n300 stamps cook in about 5 ms; the mouse ray goes against\na hou.Geometry; the surface reads only the new stamps.',11.5,DIM)
    c.save()

# ------------------------------------------------------------------ 2 gestures
def gestures():
    c=Canvas(1700,600,'d_gestures.png','The Place brush, by hand','Press where the stamp goes. What you do with the mouse after the press decides the rotation and the scale.')
    items=(('Click','no drag','The stamp takes the settings of the Randomization tab (random rotation, scale, prototype).'),
           ('Drag','turn and grow','The stamp turns to face the mouse and grows until its footprint reaches it. The ring is the scale, the number and the angle are shown.'),
           ('Shift + drag','scale only','The rotation stays the setting; only the scale follows the mouse.'),
           ('Ctrl + drag','orient to steps','The angle jumps in steps (Snap Rotation, else 15 degrees); the scale stays the setting.'),
           ('Ctrl + Shift + drag','orient freely','The angle follows the mouse exactly; the scale stays the setting.'))
    for k,(name,sub,txt) in enumerate(items):
        x=36+k*330;c.box(x,100,310,470,PANEL,LINE,12);c.pill(x+14,114,name);c.text(x+16,148,sub,11.5,DIM)
        cx,cy=x+155,300;c.p.setPen(QtGui.QPen(LINE,1))
        for g in range(-120,121,40):c.p.drawLine(QtCore.QPointF(cx+g,cy-120),QtCore.QPointF(cx+g,cy+120));c.p.drawLine(QtCore.QPointF(cx-120,cy+g),QtCore.QPointF(cx+120,cy+g))
        c.circle(cx,cy,5,ORANGE,None)
        if k==0:
            c.circle(cx,cy,18,GREY);c.p.setPen(QtGui.QPen(GREEN,2.4));c.p.drawLine(QtCore.QPointF(cx,cy),QtCore.QPointF(cx,cy-34))
        else:
            ang=[0,-40,-40,-45,-33][k];R=[0,80,80,80,80][k];fa=math.radians(ang);ex,ey=cx+R*math.sin(-fa)*-1 if False else cx+R*math.sin(math.radians(60)),cy-R*math.cos(math.radians(60))
            ring=(k in (1,2));dial=(k in (1,3,4))
            if ring:c.p.setBrush(Qt.NoBrush);c.p.setPen(QtGui.QPen(QtGui.QColor('white'),1.8));c.p.drawEllipse(QtCore.QPointF(cx,cy),R,R)
            if k in (3,):
                for t in range(24):
                    a=2*math.pi*t/24;c.p.setPen(QtGui.QPen(ORANGE if t==10 else DIM,1.6 if t==10 else 1));L=14 if t%3==0 else 8;c.p.drawLine(QtCore.QPointF(cx+(R+4)*math.sin(a),cy-(R+4)*math.cos(a)),QtCore.QPointF(cx+(R+4+L)*math.sin(a),cy-(R+4+L)*math.cos(a)))
                a=2*math.pi*10/24;ex,ey=cx+R*math.sin(a),cy-R*math.cos(a)
            elif k==4:
                a=math.radians(51.3);ex,ey=cx+R*math.sin(a),cy-R*math.cos(a)
            else:ex,ey=cx+R*math.sin(math.radians(60)),cy-R*math.cos(math.radians(60))
            if k==2:ex,ey=cx+R*math.sin(math.radians(60)),cy-R*math.cos(math.radians(60))
            if k!=2:c.p.setPen(QtGui.QPen(QtGui.QColor('white'),2));c.p.drawLine(QtCore.QPointF(cx,cy),QtCore.QPointF(ex,ey))
            else:c.p.setPen(QtGui.QPen(DIM,1.4,Qt.DashLine));c.p.drawLine(QtCore.QPointF(cx,cy),QtCore.QPointF(ex,ey))
            c.circle(ex,ey,5.5,QtGui.QColor('white'),None)
            size=R*0.5 if k!=0 else 18;yaw=[0,60,0,60,51][k]
            c.p.save();c.p.translate(cx,cy);c.p.rotate(yaw);c.p.setBrush(QtGui.QColor(160,160,160,170));c.p.setPen(QtGui.QPen(QtGui.QColor(20,20,20),1));c.p.drawEllipse(QtCore.QPointF(0,0),size,size);c.p.setPen(QtGui.QPen(GREEN,2.6));c.p.drawLine(QtCore.QPointF(0,0),QtCore.QPointF(0,-size*1.1));c.p.restore()
        c.text(x+16,440,txt,11.5,TEXT,False,278,120,Qt.AlignLeft|Qt.AlignTop,True)
    c.save()

# ------------------------------------------------------------------ 3 align and sit
def align_sit():
    c=Canvas(1700,790,'d_align_sit.png','Up follows the surface, and the prototype sits on it','Two settings of the Placement tab, both on by default in 0.9.2.')
    def hill(x0,w,y0,amp):
        pts=[QtCore.QPointF(x0+w*t/60,y0-amp*math.sin(t/60*math.pi*1.6)) for t in range(61)];path=QtGui.QPainterPath(pts[0])
        for q in pts[1:]:path.lineTo(q)
        return path,lambda t:(x0+w*t,y0-amp*math.sin(t*math.pi*1.6),math.degrees(math.atan2(amp*math.pi*1.6*math.cos(t*math.pi*1.6),w)))
    for k,(title,note,on) in enumerate((('Align To Surface = 0','every stamp stands upright in the world',False),('Align To Surface = 1  (default)','the up of every stamp is the smooth normal of the surface under it',True))):
        x=36+k*830;c.box(x,100,790,300,PANEL,LINE,12);c.text(x+18,112,title,15,ORANGE if on else TEXT,True);c.text(x+18,140,note,11.5,DIM)
        path,fn=hill(x+30,730,320,60);c.p.setBrush(Qt.NoBrush);c.p.setPen(QtGui.QPen(QtGui.QColor('#5c7a5c'),4));c.p.drawPath(path)
        for t in (0.1,0.25,0.4,0.55,0.7,0.85):
            px,py,sl=fn(t);ang=-sl*0.0+math.degrees(math.atan2(-(fn(min(t+0.005,1))[1]-fn(max(t-0.005,0))[1]),(fn(min(t+0.005,1))[0]-fn(max(t-0.005,0))[0])))*-1
            tree(c,px,py,(-ang) if on else 0,70)
    c.text(36,428,'Smooth Normals',15,TEXT,True);c.text(36,456,'Between the vertices of the mesh the up changes smoothly, so stamps on a body or a hill lean gradually. Creases over 60 degrees stay sharp: the top of a cube stays flat.',11.5,DIM,False,1630,60,Qt.AlignLeft|Qt.AlignTop,True)
    for k,(title,note,sit) in enumerate((('Sit On Surface = off','the pivot of the prototype is on the surface: a prototype with its origin in the middle sinks in',False),('Sit On Surface = on  (default)','the bottom of the prototype touches the surface or the stamp below',True))):
        x=36+k*830;c.box(x,500,790,265,PANEL,LINE,12);c.text(x+18,512,title,15,ORANGE if sit else TEXT,True);c.text(x+18,540,note,11.5,DIM,False,750,50,Qt.AlignLeft|Qt.AlignTop,True)
        gy=730;c.p.setPen(QtGui.QPen(QtGui.QColor('#5c7a5c'),4));c.p.drawLine(QtCore.QPointF(x+30,gy),QtCore.QPointF(x+760,gy))
        for j,(bx,r) in enumerate(((x+170,48),(x+470,34),(x+620,34))):
            cy=gy-r if sit else gy
            if j==2:cy=(gy-2*34-34) if sit else gy-34;bx=x+470 if j==2 else bx
            if j==1 and False:pass
            c.circle(bx,cy,r,QtGui.QColor(160,160,160,210));c.p.setPen(QtGui.QPen(RED if not sit else DIM,2));c.p.drawLine(QtCore.QPointF(bx-8,cy),QtCore.QPointF(bx+8,cy));c.p.drawLine(QtCore.QPointF(bx,cy-8),QtCore.QPointF(bx,cy+8))
        c.text(x+30,615,'pivot (+)' ,11,RED if not sit else DIM)
    c.save()

# ------------------------------------------------------------------ 4 layouts
def layouts():
    c=Canvas(1700,820,'d_layouts.png','Group brush layouts','Drawn with the Stamp\'s own layout function: seven members, three different prototypes, Spacing 1.2. Top view.')
    kinds=(('radial','Radial','a ring; the first member is at the top'),('square','Square','a grid, as square as it gets'),('hexagon','Hexagon','a hexagonal lattice from the middle out'),('cluster','Random Cluster','another one for every group'),('line','Line','along X, spaced by their sizes'),('spiral','Spiral','a sunflower spiral'))
    radii=[0.5,0.8,0.45,0.65,0.5,0.8,0.55];protos=[1,2,3,1,2,3,1]
    for k,(kind,name,note) in enumerate(kinds):
        x=36+(k%3)*550;y=96+(k//3)*350;c.box(x,y,520,330,PANEL,LINE,12);c.text(x+16,y+10,name,15,ORANGE,True);c.text(x+16,y+38,note,11,DIM)
        P=core.stamp_group_offsets(kind,radii,1.2,np.random.RandomState(5));ext=max(float(np.abs(P).max())+max(radii),1.0);ex_=float(np.abs(P[:,0]).max())+max(radii);ey_=float(np.abs(P[:,1]).max())+max(radii);sc=min(125.0/ey_,225.0/ex_);cx,cy=x+260,y+195
        c.p.setPen(QtGui.QPen(LINE,1));c.p.drawLine(QtCore.QPointF(cx-230,cy),QtCore.QPointF(cx+230,cy));c.p.drawLine(QtCore.QPointF(cx,cy-120),QtCore.QPointF(cx,cy+120))
        for i,(pt,r,pr) in enumerate(zip(P,radii,protos)):
            c.circle(cx+pt[0]*sc,cy+pt[1]*sc,r*sc,QtGui.QColor(COL[pr].red(),COL[pr].green(),COL[pr].blue(),215))
            c.text(cx+pt[0]*sc-4,cy+pt[1]*sc-9,str(i+1),9.5,QtGui.QColor('#202020'),True)
    c.save()

# ------------------------------------------------------------------ 5 randomization
def randomization():
    c=Canvas(1700,640,'d_random.png','Brush > Randomization','What changes between one stamp and the next. The same Seed gives the same stamps; more stamps never change the earlier ones.')
    rng=np.random.RandomState(7)
    cols=(('Prototype','Random Prototype  (also the Random button)','Every stamp takes one of the selected cards by its Weight.'),('Scale','Uniform Scale  x  Random Scale Min / Max','Every stamp is the base scale times a random number in the range.'),('Rotation','Rotate  +  Random Rotate (+/- deg)  +  Random Tilt','A random turn about the up axis, and a random lean off it.'))
    for k,(title,params,note) in enumerate(cols):
        x=36+k*550;c.box(x,100,520,500,PANEL,LINE,12);c.text(x+18,112,title,18,ORANGE,True);c.text(x+18,146,params,11.5,TEXT,True,484,40,Qt.AlignLeft|Qt.AlignTop,True);c.text(x+18,196,note,11,DIM,False,484,60,Qt.AlignLeft|Qt.AlignTop,True)
        if k==0:
            for j,(nm,w,col) in enumerate((('Rock  w 1',1,GREY),('Fir  w 3',3,GREEN),('Stone  w 1',1,SAND))):
                c.text(x+18,270+j*40,nm,11.5,TEXT);c.box(x+130,272+j*40,40*w,20,col,None,4)
            picks=rng.choice(3,14,p=[0.2,0.6,0.2]);c.text(x+18,410,'fourteen stamps in a row:',11,DIM)
            for j,pk in enumerate(picks):
                col=(GREY,GREEN,SAND)[pk];cx=x+40+j*34
                (c.circle(cx,490,12,col) if pk==0 else tree(c,cx,502,0,34,col) if pk==1 else c.box(cx-11,478,22,22,col,QtGui.QColor(20,20,20),2))
        elif k==1:
            c.box(x+30,280,460,16,BG,LINE,8);c.box(x+30+460*0.25,280,460*0.5,16,ORANGE,None,8);c.text(x+30,300,'0.5',10,DIM);c.text(x+450,300,'1.5',10,DIM);c.center(x+30,318,460,'Random Scale 0.8 / 1.3 around Uniform Scale 1.0',10.5,DIM)
            for j in range(10):
                s=0.8+0.5*rng.rand();c.circle(x+50+j*46,470,22*s,GREY);
            c.text(x+30,520,'each circle is one stamp: 80 % to 130 % of the base size',10.5,DIM)
        else:
            for j in range(10):
                ang=rng.uniform(-180,180);tilt=rng.uniform(-14,14);tree(c,x+50+j*46,490,ang*0.0+tilt,50,GREEN)
            c.text(x+30,520,'Random Tilt: every tree leans a little',10.5,DIM)
            for j in range(10):
                cx=x+50+j*46;a=math.radians(rng.uniform(-180,180));c.circle(cx,330,18,GREY);c.p.setPen(QtGui.QPen(GREEN,2.6));c.p.drawLine(QtCore.QPointF(cx,330),QtCore.QPointF(cx+18*math.sin(a),330-18*math.cos(a)))
            c.text(x+30,360,'Random Rotate 180: any direction (top view)',10.5,DIM)
    c.save()

# ------------------------------------------------------------------ 6 modes
def modes():
    c=Canvas(1700,560,'d_modes.png','Modes and brushes','Entering the node\'s tool in the viewport is placing. The shelf, the C menu and the tabs of the pane switch the brush.')
    c.box(36,100,1000,420,PANEL,LINE,12);c.text(54,110,'Brush mode',16,ORANGE,True)
    for k,(name,desc,col) in enumerate((('Place','click, drag to turn and scale; the wheel cycles the stamp cycle',GREEN),('Delete','click or drag over stamps; they turn red; one undo step on release',RED),('Paint','drag to paint inside a disc; Ctrl + drag erases',BLUE),('Group','one click stamps several prototypes in a layout',ORANGE))):
        x=54+k*242;c.box(x,160,226,200,BG,col,10,2.5);c.center(x,172,226,name,18,col,True);c.center(x+10,214,206,desc,11,TEXT,False,True)
    c.text(54,380,'Every brush uses the ghost preview (the prototype itself, translucent), the stamp cycle and the settings of the Brush tab.',11.5,DIM,False,960,60,Qt.AlignLeft|Qt.AlignTop,True)
    c.text(54,440,'Shelf buttons  Place  Delete  Paint  Group  Random   |   C = brush menu   |   B = options menu',12,TEXT,True)
    c.box(1070,100,594,420,PANEL,LINE,12);c.text(1088,110,'Edit mode',16,ORANGE,True);c.text(1088,148,'Shift + B toggles Brush and Edit.',11.5,DIM)
    for k,t in enumerate(('click selects a stamp (Shift adds or removes)','drag on nothing: box select','the edit handle moves, turns and scales the selection','hold Z while dragging: duplicate','Del deletes the selection','G: the selection becomes the Group layout')):
        c.text(1100,190+k*38,'•  '+t,12,TEXT)
    c.save()

# ------------------------------------------------------------------ 7 stamp cycle
def cycle():
    c=Canvas(1700,520,'d_cycle.png','The stamp cycle','The cards you chose (orange frame, a number) are the stamps the wheel goes through and Random draws from.')
    names=('Rock','Fir','Stone','Mushroom');weights=(1,3,1,1);chosen=(1,2,3)
    for k,(nm,w) in enumerate(zip(names,weights)):
        x=60+k*200;on=(k+1) in chosen;c.box(x,130,170,190,PANEL,ORANGE if on else LINE,10,4 if on else 1.5)
        {0:lambda:c.circle(x+85,200,38,GREY),1:lambda:tree(c,x+85,235,0,90,GREEN),2:lambda:c.box(x+48,164,74,74,SAND,QtGui.QColor(20,20,20),4),3:lambda:c.box(x+68,160,34,84,RED,QtGui.QColor(20,20,20),16)}[k]()
        c.center(x,262,170,nm,13,TEXT,True);c.center(x,288,170,'row %d   weight %d'%(k+1,w),10.5,DIM)
        if on:c.box(x+8,138,26,24,ORANGE,None,5);c.center(x+8,140,26,str(chosen.index(k+1)+1),12,QtGui.QColor('#202020'),True)
    c.text(60,350,'Stamp cycle, 3 selected: 1 Rock, 2 Fir, 3 Stone   |   Random draws from these',12.5,TEXT,True)
    c.text(60,384,'Click a card: it alone is the cycle.   Ctrl + click: add or remove.   Right click: select or delete its stamps.   Key 1 to 9: that row alone, 0: all.',11,DIM,False,800,60,Qt.AlignLeft|Qt.AlignTop,True)
    c.box(940,110,720,380,PANEL,LINE,12);c.text(960,120,'Mouse wheel (Place, Paint)',15,ORANGE,True)
    import math as m
    cx,cy=1170,300
    for j in range(3):
        a=2*m.pi*j/3-m.pi/2;px,py=cx+90*m.cos(a),cy+90*m.sin(a);c.circle(px,py,32,ORANGE,None);c.center(px-30,py-14,60,str(j+1),17,QtGui.QColor('#202020'),True)
    for j in range(3):
        a1=2*m.pi*j/3-m.pi/2+0.55;a2=2*m.pi*(j+1)/3-m.pi/2-0.55;c.arrow(cx+90*m.cos(a1),cy+90*m.sin(a1),cx+90*m.cos(a2),cy+90*m.sin(a2),DIM,2.4)
    c.text(1330,200,'Random button',15,ORANGE,True);c.text(1330,232,'every stamp draws one by weight:',11.5,DIM,False,300,40,Qt.AlignLeft|Qt.AlignTop,True)
    for j,(nm,w,col) in enumerate((('Rock',1,GREY),('Fir',3,GREEN),('Stone',1,SAND))):
        c.text(1330,290+j*38,nm,11.5,TEXT);c.box(1410,292+j*38,40*w,20,col,None,4)
    c.save()

# ------------------------------------------------------------------ 8 sheet
def sheet():
    c=Canvas(1700,500,'d_sheet.png','The STAMPS sheet edits many at once','A cell you edit changes the selected stamps, or all of them; Set, Add or Multiply.')
    def table(x,y,rows,sel,hi=None,title=''):
        c.text(x,y-34,title,13,TEXT,True);cols=('#','Row','X','Y','Z','Scale');w=70
        for j,h in enumerate(cols):c.box(x+j*w,y,w,28,QtGui.QColor('#3c434d'),LINE,2);c.center(x+j*w,y+4,w,h,10.5,DIM,True)
        for i,r in enumerate(rows):
            for j,v in enumerate(r):
                col=QtGui.QColor('#7a5a1e') if i in sel else PANEL;c.box(x+j*w,y+28+i*28,w,28,col,LINE,2)
                c.center(x+j*w,y+32+i*28,w,v,10.5,ORANGE if (hi and (i,j) in hi) else TEXT,bool(hi and (i,j) in hi))
    base=[('0','2','1.0','0.0','1.0','1.00'),('1','1','2.5','0.0','3.0','1.00'),('2','3','4.0','0.0','1.5','1.50'),('3','2','5.0','0.0','0.5','1.00')]
    table(36,120,base,{0,1,2},None,'Before: rows 0, 1, 2 are selected')
    after=[('0','2','1.0','1.0','1.0','1.00'),('1','1','2.5','1.0','3.0','1.00'),('2','3','4.0','1.0','1.5','1.50'),('3','2','5.0','0.0','0.5','1.00')]
    table(500,120,after,{0,1,2},{(0,3),(1,3),(2,3)},'Selected + Add: type 1 in the Y cell of any selected row')
    after2=[('0','2','1.0','0.0','1.0','2.00'),('1','1','2.5','0.0','3.0','2.00'),('2','3','4.0','0.0','1.5','3.00'),('3','2','5.0','0.0','0.5','1.00')]
    table(964,120,after2,{0,1,2},{(0,5),(1,5),(2,5)},'Selected + Multiply: type 2 in a Scale cell')
    c.box(36,330,1628,130,PANEL,LINE,12)
    for k,(h,t) in enumerate((('Edit: Selected | All','Selected changes the selection when the edited row is in it, else only that row. All changes every stamp.'),('Set | Add | Multiply','Set puts the value in. Add adds it to each stamp\'s own value (X, Y, Z, Rx, Ry, Rz). Multiply multiplies (Scale). Row and On are always set.'),('Buttons and keys','Delete, Duplicate, All, None, Invert, Clear All (asks first). Del in the table. Right click: select or delete the stamps of the same prototype.'))):
        x=60+k*540;c.text(x,350,h,14,ORANGE,True);c.text(x,384,t,11.5,TEXT,False,490,180,Qt.AlignLeft|Qt.AlignTop,True)
    c.save()

# ------------------------------------------------------------------ 9 performance
def performance():
    c=Canvas(1700,640,'d_perf.png','Placing is light','Milliseconds, before and after the 0.9.2 work; heavy prototypes, a 160 000 triangle ground, 3000 stamps unless said.')
    rows=(('Surface read after a click (3000 stamps)',10.7,4.0),('Surface read after a click (20 000 stamps)',71.0,29.0),('Preview text count (20 000 stamps)',2.9,1.3),('Group of 7: place the members',2.4,1.3),('Group of 64: place the members',21.0,12.0),('Group of 64: commit',27.0,17.5))
    scale=1300/75.0
    for k,(label,a,b) in enumerate(rows):
        y=110+k*78;c.text(36,y,label,13,TEXT,True);c.box(36,y+30,a*scale,18,GREY,None,4);c.text(44+a*scale,y+27,'%.1f ms  before'%a,11,DIM);c.box(36,y+52,b*scale,18,GREEN,None,4);c.text(44+b*scale,y+49,'%.1f ms  now'%b,11,GREEN,True)
    c.save()

# ------------------------------------------------------------------ 10 workflow
def workflow():
    c=Canvas(1700,420,'d_workflow.png','Five steps','From an empty node to a placed set.')
    steps=(('1','Make the node','Tab > Arraytron Stamp in /stage. Connect the scene to input 1.'),('2','Fill the bank','Click the cards, add prims or USD files in Brush > Asset, or the Asset Library.'),('3','Choose the cycle','Click a card (Ctrl + click adds). Press Random for a mix.'),('4','Place','Press Place (or Enter the tool). Click, drag, paint, or stamp groups.'),('5','Tidy up','Edit mode, the STAMPS sheet, Delete. One undo step each.'))
    for k,(n,h,t) in enumerate(steps):
        x=36+k*330;c.box(x,110,300,260,PANEL,LINE,12);c.circle(x+40,160,26,ORANGE,None);c.center(x+14,146,52,n,20,QtGui.QColor('#202020'),True);c.text(x+80,146,h,15,TEXT,True,210,40,Qt.AlignLeft|Qt.AlignTop,True);c.text(x+22,214,t,12,DIM,False,260,140,Qt.AlignLeft|Qt.AlignTop,True)
        if k<4:c.arrow(x+304,240,x+326,240,ORANGE,3,9)
    c.save()


# ------------------------------------------------------------------ 11 paint falloff
def falloff():
    c=Canvas(1700,1340,'d_falloff.png','Paint falloff: density and scale','One swept field, two channels. The strokes below are the stamps of the Paint Falloff demo, painted with the tool\'s own engine; the dot size is the real size of each rock.')
    import hou
    # the curves
    c.box(36,100,800,360,PANEL,LINE,12);c.text(54,110,'Curve of the fall (influence: 1 = full, 0 = the minimum)',14,ORANGE,True)
    x0,y0,w,h=90,170,470,250;c.p.setPen(QtGui.QPen(LINE,1));c.p.drawRect(QtCore.QRectF(x0,y0,w,h));c.text(x0-30,y0+h-8,'0',10,DIM);c.text(x0-30,y0-6,'1',10,DIM);c.text(x0,y0+h+6,'inner edge of the fall',10,DIM);c.text(x0+w-60,y0+h+6,'brush rim',10,DIM)
    cols=(('linear',DIM),('smoothstep',GREEN),('smootherstep',BLUE),('ease_in',SAND),('ease_out',RED))
    for kind,col in cols:
        u=np.linspace(0,1,80);infl=1.0-core.falloff_curve(kind,u);pts=[QtCore.QPointF(x0+w*a,y0+h*(1-b)) for a,b in zip(u,infl)];path=QtGui.QPainterPath(pts[0])
        for q in pts[1:]:path.lineTo(q)
        c.p.setBrush(Qt.NoBrush);c.p.setPen(QtGui.QPen(col,3 if kind in ('smoothstep','smootherstep') else 2));c.p.drawPath(path)
    for k,(kind,col) in enumerate(cols):c.box(620,y0+16+k*28,18,12,col,None,3);c.text(646,y0+11+k*28,{'linear':'Linear','smoothstep':'Smoothstep (recommended)','smootherstep':'Smootherstep (recommended)','ease_in':'Ease In','ease_out':'Ease Out'}[kind],10.5,TEXT)
    c.text(620,y0+16+5*28-4,'+ Custom Ramp',10.5,DIM)
    # the multiplier along the radius
    c.box(864,100,800,360,PANEL,LINE,12);c.text(882,110,'Soft Natural: the multiplier from the centre to the rim',14,ORANGE,True)
    lut=1.0-core.falloff_curve('smootherstep',core.np.linspace(0,1,257));pd=dict(min=0.05,max=1.0,inner=0.25,strength=1.0,lut=lut);lut2=1.0-core.falloff_curve('smoothstep',core.np.linspace(0,1,257));ps=dict(min=0.35,max=1.0,inner=0.15,strength=1.0,lut=lut2)
    x0,y0,w,h=920,170,700,250;c.p.setPen(QtGui.QPen(LINE,1));c.p.drawRect(QtCore.QRectF(x0,y0,w,h));c.text(x0-36,y0+h-8,'0 %',10,DIM);c.text(x0-42,y0-6,'100 %',10,DIM);c.text(x0,y0+h+6,'centre',10,DIM);c.text(x0+w-70,y0+h+6,'rim (r = 1)',10,DIM)
    for prof,col,name in ((pd,BLUE,'Density: edge minimum 5 %, falls from 25 % of the radius'),(ps,ORANGE,'Scale: edge minimum 35 %, falls from 15 % of the radius')):
        r=np.linspace(0,1,100);m=core.falloff_multiplier(prof,r);pts=[QtCore.QPointF(x0+w*a,y0+h*(1-b)) for a,b in zip(r,m)];path=QtGui.QPainterPath(pts[0])
        for q in pts[1:]:path.lineTo(q)
        c.p.setBrush(Qt.NoBrush);c.p.setPen(QtGui.QPen(col,3));c.p.drawPath(path)
    c.text(940,y0+176,'Density: edge minimum 5 %, the fall starts at 25 % of the radius',11,BLUE,True);c.text(940,y0+202,'Scale: edge minimum 35 %, the fall starts at 15 % of the radius',11,ORANGE,True)
    # the strokes of the demo
    hip=ROOT/'dist'/'Arraytron_Stamp_v0.9.3_paint_falloff_demo.hip'
    try:
        hou.hipFile.load(str(hip),suppress_save_prompt=True,ignore_load_warnings=True);ok=True
    except Exception as exc:
        ok=False;c.text(36,500,'(demo hip not found: %s)'%exc,12,RED)
    if ok:
        def strip(x,y,w,node,title,xr,zr):
            n=hou.node('/stage/'+node);r=core.stamp_rows(n.evalParm('stamps'));ppu=w/(xr[1]-xr[0]);hgt=(zr[1]-zr[0])*ppu
            c.box(x,y,w+20,hgt+54,PANEL,LINE,10);c.text(x+12,y+8,title,12.5,TEXT,True)
            c.p.save();c.p.setClipRect(QtCore.QRectF(x+10,y+36,w,hgt));c.p.setBrush(QtGui.QColor('#2a3a2c'));c.p.setPen(Qt.NoPen);c.p.drawRect(QtCore.QRectF(x+10,y+36,w,hgt))
            for row in r:
                px=x+10+(row[0]-xr[0])*ppu;py=y+36+(row[2]-zr[0])*ppu;rad=max(1.0,0.22*row[6]*ppu);c.circle(px,py,rad,QtGui.QColor(190,186,176),QtGui.QColor(30,30,30),0.6)
            c.p.restore()
        strip(36,490,780,'Paint1_Uniform','Uniform: no falloff',(-17,17),(-17.5,-12.5));strip(864,490,780,'Paint2_DensityOnly','Density Falloff only: fewer towards the rim, the same size',(-17,17),(-13,-8))
        strip(36,670,780,'Paint3_ScaleOnly','Scale Falloff only: the same number, smaller towards the rim',(-17,17),(-8.5,-3.5));strip(864,670,780,'Paint4_SoftNatural','Both: the Soft Natural preset',(-17,17),(-4,1))
        strip(36,850,1608,'Paint5_LongStroke','One long continuous stroke, Soft Natural: a ribbon with a soft edge, no circles at the dabs',(-17,17),(-0.5,7.5))
    c.save()
if __name__=='__main__':
    for f in (overview,gestures,align_sit,layouts,randomization,modes,cycle,sheet,performance,workflow,falloff):f()
