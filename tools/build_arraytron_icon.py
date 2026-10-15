"""Draw Arraytron's vector seal and render its preview with Qt SVG."""
from pathlib import Path
import math
import os
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'icon'
OUT.mkdir(exist_ok=True)

parts = ['''<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024" role="img" aria-labelledby="title description">
  <title id="title">Arraytron — distribution seal</title>
  <desc id="description">A monochrome double-ring seal. An inverted triangle floats above an isometric matrix of scattered cubes and spheres, joined by fine construction lines.</desc>
  <g id="seal" stroke="#000" fill="none">
    <circle id="white-field" cx="512" cy="512" r="446" fill="#fff" stroke="none"/>
    <circle cx="512" cy="512" r="446" stroke-width="9"/>
    <circle cx="512" cy="512" r="426" stroke-width="3.5"/>
  </g>
  <g id="construction" fill="none" stroke="#000" stroke-width="2" stroke-linecap="butt">
''']

def project(row, col):
    return (512 + (col-row)*93, 382 + (col+row)*57)

def line(a, b, extra=''):
    parts.append(f'<path d="M {a[0]:.2f},{a[1]:.2f} L {b[0]:.2f},{b[1]:.2f}" {extra}/>')

# The diamond lattice describes distribution; displaced objects imply variation.
for i in range(4):
    line(project(i,-.5), project(i,3.5))
    line(project(-.5,i), project(3.5,i))
corners=[project(-.5,-.5),project(-.5,3.5),project(3.5,3.5),project(3.5,-.5)]
parts.append('<polygon points="'+' '.join(f'{x},{y}' for x,y in corners)+'" stroke-width="3"/>')
line((512,314),(512,875),'stroke-dasharray="9 11"')
line((168,512),(856,512),'stroke-dasharray="8 11"')
for angle in (0,90,180,270):
    rad=math.radians(angle)
    line((512+409*math.cos(rad),512+409*math.sin(rad)),
         (512+426*math.cos(rad),512+426*math.sin(rad)), 'stroke-width="4"')
parts.append('</g>')

# A single solid triangle anchors the upper field, echoing the supplied reference.
parts.append('''<g id="inverted-triangle" fill="#000">
  <path d="M 387,176 H 637 L 512,326 Z"/>
</g>
<g id="scattered-matrix" stroke="#000" stroke-linejoin="miter">''')

def cube(x,y,s,index):
    parts.append(f'''<g id="cube-{index}" transform="translate({x} {y}) scale({s})" stroke-width="3.8">
      <path d="M 0,-32 28,-16 28,16 0,32 -28,16 -28,-16 Z" fill="#fff"/>
      <path d="M 0,0 28,-16 28,16 0,32 Z" fill="#000"/>
      <path d="M -28,-16 0,0 28,-16 M 0,0 V 32" fill="none"/>
    </g>''')

def sphere(x,y,s,index):
    parts.append(f'''<g id="sphere-{index}" transform="translate({x} {y}) scale({s})">
      <circle r="26" fill="#fff" stroke-width="3.8"/>
      <path d="M 0,-26 A 26,26 0 0 1 0,26 C 18,20 18,-20 0,-26 Z" fill="#000" stroke="none"/>
      <ellipse rx="26" ry="8" fill="none" stroke-width="2"/>
      <path d="M 0,-26 C -15,-16 -15,16 0,26" fill="none" stroke-width="2"/>
    </g>''')

offsets=[(0,-1),(-7,3),(7,-4),(3,2),(-4,-6),(4,4),(-5,-2),(8,2),
         (7,0),(-8,4),(3,-5),(-4,7),(-5,-2),(6,3),(-4,-1),(0,5)]
spheres={1,3,4,6,9,12,14}
scales=[1.04,.94,1.03,.86,.94,1.12,.85,1.0,1.04,.98,1.08,.92,.86,1.0,.91,1.1]
# Back-to-front drawing order makes the SVG editor's layer order intuitive.
for row,col in sorted(((r,c) for r in range(4) for c in range(4)),key=lambda p:sum(p)):
    index=row*4+col
    x,y=project(row,col);dx,dy=offsets[index]
    (sphere if index in spheres else cube)(x+dx,y+dy,scales[index],index+1)
parts.append('''</g>
  <g id="lower-register" fill="none" stroke="#000">
    <circle cx="512" cy="861" r="13" stroke-width="3" fill="#fff"/>
    <circle cx="512" cy="861" r="4" stroke-width="2" fill="#000"/>
    <path d="M 472,861 H 489 M 535,861 H 552" stroke-width="2"/>
  </g>
</svg>''')

svg=OUT/'Arraytron-Clean.svg'
svg.write_text('\n'.join(parts)+'\n',encoding='utf-8')
ET.parse(svg)

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication,QImage,QPainter
from PySide6.QtSvg import QSvgRenderer
app=QGuiApplication.instance() or QGuiApplication([])
renderer=QSvgRenderer(str(svg))
assert renderer.isValid()
for name,size,background in [('Arraytron-Clean.png',2048,Qt.GlobalColor.transparent),
                             ('Arraytron-Preview.png',1024,Qt.GlobalColor.white)]:
    image=QImage(size,size,QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(background)
    painter=QPainter(image);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter);painter.end()
    assert image.save(str(OUT/name))
print(f'Saved editable SVG and PNG previews to {OUT}')
