"""Write the Distribution Mode cell icons: python tools/make_mode_icons.py
Per mode two 64 x 64 SVGs in icon/modes/: Mode_<key>_off.svg (dark tile, dim glyph) and Mode_<key>_on.svg (lit tile with a halo, bright glyph). The HDA shows one of the two for every mode
(the one that is selected is lit), so the mode cells look switched off or on; the builder embeds the files as HDA sections (opdef:)."""
from pathlib import Path
import math
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'icon' / 'modes'

OFF = dict(line='#94a0b4', dot='#c0c8d4', acc='#94a0b4', tile='<rect x="3" y="3" width="58" height="58" rx="9" fill="#23272d" stroke="#363c46" stroke-width="2"/>')
ON = dict(line='#fff1c8', dot='#ffffff', acc='#ffd23c',
          tile=('<rect x="0.5" y="0.5" width="63" height="63" rx="12" fill="#ffc400" fill-opacity="0.14"/><rect x="1.5" y="1.5" width="61" height="61" rx="11" fill="#ffc400" fill-opacity="0.20"/>'
                '<rect x="3" y="3" width="58" height="58" rx="9" fill="#4a3a12" stroke="#ffd23c" stroke-width="2.4"/>'))

def dots(points, c, r=3.4, fill=None):
    return ''.join('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s"/>' % (x, y, r, fill or c['dot']) for x, y in points)

def bezier(p0, p1, p2, p3, t):
    u = 1 - t
    return (u**3*p0[0]+3*u*u*t*p1[0]+3*u*t*t*p2[0]+t**3*p3[0], u**3*p0[1]+3*u*u*t*p1[1]+3*u*t*t*p2[1]+t**3*p3[1])

def glyph(key, c):
    """The picture of a mode on a 64 x 64 canvas (drawn in the middle 44 x 44 of the tile)."""
    if key == 'line':
        return '<path d="M8 50 L56 14"/>' + dots([(8+i*12, 50-i*9) for i in range(5)], c)
    if key == 'area':
        return '<rect x="8" y="12" width="48" height="40" rx="5"/>' + dots([(18, 22), (32, 19), (46, 25), (24, 34), (39, 36), (49, 44), (17, 45), (31, 47)], c)
    if key == 'grid':
        return '<rect x="8" y="8" width="48" height="48" rx="4" stroke-dasharray="2 5"/>' + dots([(16+i*16, 16+j*16) for i in range(3) for j in range(3)], c)
    if key == 'circle':
        return '<circle cx="32" cy="32" r="22" stroke-dasharray="2 5"/>' + dots([(32+22*math.cos(a*math.pi/4), 32+22*math.sin(a*math.pi/4)) for a in range(8)], c)
    if key == 'curve':
        return '<path d="M8 48 C20 4 44 60 56 16"/>' + dots([bezier((8, 48), (20, 4), (44, 60), (56, 16), i/6) for i in range(7)], c)
    if key == 'surface':
        return ('<path d="M6 44 C18 34 24 22 32 24 C42 26 48 40 58 36"/><path d="M6 44 L6 54 L58 54 L58 36" stroke-dasharray="2 4"/>'
                + dots([(14, 39), (24, 29), (33, 25), (41, 31), (49, 38), (56, 36)], c, fill=c['acc']) + dots([(18, 48), (32, 49), (46, 48)], c, r=2.6))
    if key == 'paint':                                        # a simple brush: handle, ferrule, teardrop of bristles
        return ('<path d="M25.6 28.8 L56.5 5 Q60.5 2.5 63 6.5 Q64.5 10 61.5 13 L34.4 38.8 Z"/><path d="M25.6 28.8 Q35 31 34.4 38.8"/><path d="M25.6 28.8 L16.3 41.3 M34.4 38.8 L20.6 46.3"/>'
                '<path d="M16.3 41.3 C9 38.5 3 46 1.8 58.5 C13 57.5 21.5 54 20.6 46.3 Z" fill="%s" fill-opacity="0.35" stroke="%s"/>' % (c['acc'], c['acc']))
    if key == 'cluster':
        return (''.join('<circle cx="%d" cy="%d" r="%d" stroke-dasharray="2 4"/>' % q for q in ((20, 22, 13), (44, 30, 11), (26, 46, 10)))
                + dots([(15, 18), (24, 25), (20, 14), (41, 27), (48, 34), (44, 22), (22, 44), (30, 49), (27, 40)], c, r=3))
    if key == 'imported':
        return '<path d="M32 4 L32 24 M24 17 L32 25 L40 17" stroke="%s"/><rect x="6" y="30" width="52" height="26" rx="4"/>' % c['acc'] + dots([(15, 40), (28, 46), (40, 38), (50, 48), (21, 51)], c)
    if key == 'place':
        return ('<path d="M14 8 L14 40 L22 33 L28 46 L34 43 L28 31 L38 30 Z" fill="%s" fill-opacity="0.25"/><circle cx="46" cy="46" r="9" stroke="%s"/><path d="M46 40 V52 M40 46 H52" stroke="%s"/>'
                % (c['line'], c['acc'], c['acc']))
    if key == 'biome':
        return '<path d="M4 54 L22 22 L32 38 L42 16 L60 54 Z"/><path d="M34 26 L42 16 L50 30" stroke="%s"/>' % c['acc'] + dots([(14, 49), (26, 50), (38, 49), (50, 49), (20, 40), (44, 38)], c, r=2.8)
    raise KeyError(key)

KEYS = ('line', 'area', 'grid', 'circle', 'curve', 'surface', 'paint', 'cluster', 'imported', 'place', 'biome')

def svg(key, c):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">%s'
            '<g transform="translate(10 10) scale(0.6875)" fill="none" stroke="%s" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">%s</g></svg>\n') % (c['tile'], c['line'], glyph(key, c))

if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob('Mode_*.svg'):
        old.unlink()
    for key in KEYS:
        (OUT / ('Mode_%s_off.svg' % key)).write_text(svg(key, OFF), encoding='utf8')
        (OUT / ('Mode_%s_on.svg' % key)).write_text(svg(key, ON), encoding='utf8')
    print('wrote', 2 * len(KEYS), 'icons to', OUT)
