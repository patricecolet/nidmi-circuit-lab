"""Génère hp-capteur.kicad_sch : haut-parleur utilisé comme capteur → enveloppe → ADC d'une XIAO ESP32-C3.

Chaque broche reçoit un court fil et une étiquette de net (ou un symbole d'alimentation) :
la connectivité est entièrement portée par les noms de nets, vérifiée par `kicad-cli sch erc`.
Relancer : python3 -I gen_schema.py
"""
import math, os, sys, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kisexpr import S, flatten, pins, dump

LIB = '/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols/'
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hp-capteur.kicad_sch')
PROJ = 'hp-capteur'
NS = uuid.UUID('6f1d3c2e-8b1a-4c55-9a0e-5e2c1d7a9b31')
def uid(*k): return S(str(uuid.uuid5(NS, '/'.join(map(str, k)))))
ROOT = uid('root')
STUB = 2.54

# ── Composants : (réf, bibliothèque, symbole, valeur, x, y, rotation, unité, {broche: connexion}) ──
# Connexion : 'GND' / '+3V3' (symbole d'alimentation au bout d'un fil), 'L:NOM' (étiquette de net),
# '-' (reliée par un fil explicite de WIRES). Un suffixe '@longueur' allonge le fil.
P, G = '+3V3', 'GND'
PARTS = [
    # Entrée : haut-parleur, liaison, résistance série, clamp
    ('LS1', 'Device', 'Speaker',      'HP 8 Ω (capteur)', 25.4, 58.42, 180, 1, {'2': '-', '1': '-'}),
    ('C1',  'Device', 'C_Polarized',  '10µF',   40.64, 55.88, 270, 1, {'1': '-', '2': '-'}),
    ('R9',  'Device', 'R',            '10k',    55.88, 55.88, 270, 1, {'1': '-', '2': '-'}),
    ('R1',  'Device', 'R',            '100k',   66.04, 45.72, 0,   1, {'1': 'L:VBIAS', '2': '-'}),
    ('D2',  'Diode',  '1N4148',       '1N4148', 73.66, 68.58, 270, 1, {'1': P, '2': '-'}),
    ('D3',  'Diode',  '1N4148',       '1N4148', 73.66, 78.74, 270, 1, {'1': '-', '2': G}),
    # Préampli non inverseur, gain alternatif 1 + R4/R5 ≈ 22
    ('U1',  'Amplifier_Operational', 'MCP6002-xP', 'MCP6002', 101.6, 58.42, 0, 1, {'3': '-', '2': '-', '1': '-'}),
    ('R4',  'Device', 'R',            '100k',   101.6, 68.58, 90, 1, {'1': '-', '2': '-'}),
    ('R5',  'Device', 'R',            '4.7k',   91.44, 76.2, 0,   1, {'1': '-', '2': '-'}),
    ('C3',  'Device', 'C',            '10µF',   91.44, 88.9, 0,   1, {'1': '-', '2': 'L:VBIAS'}),
    # Détecteur d'enveloppe
    ('C4',  'Device', 'C',            '1µF',    119.38, 58.42, 90, 1, {'1': '-', '2': '-'}),
    ('R6',  'Device', 'R',            '100k',   127.0, 66.04, 0,   1, {'1': '-', '2': G}),
    ('D1',  'Diode',  '1N4148',       '1N4148', 137.16, 58.42, 180, 1, {'2': '-', '1': '-'}),
    ('C5',  'Device', 'C',            '100nF',  147.32, 66.04, 0,   1, {'1': '-', '2': G}),
    ('R7',  'Device', 'R',            '220k',   157.48, 66.04, 0,   1, {'1': '-', '2': G}),
    ('J1',  'Connector_Generic', 'Conn_01x03', 'vers XIAO ESP32-C3', 175.26, 58.42, 0, 1,
            {'1': '-', '2': '-', '3': '-'}),
    # Point milieu 1,65 V tamponné par la 2e moitié du MCP6002
    ('R2',  'Device', 'R',            '100k',   40.64, 116.84, 0, 1, {'1': P, '2': '-'}),
    ('R3',  'Device', 'R',            '100k',   40.64, 129.54, 0, 1, {'1': '-', '2': G}),
    ('C2',  'Device', 'C',            '10µF',   50.8, 129.54, 0,  1, {'1': '-', '2': G}),
    ('U1',  'Amplifier_Operational', 'MCP6002-xP', 'MCP6002', 71.12, 125.73, 0, 2, {'5': '-', '6': '-', '7': '-'}),
    ('U1',  'Amplifier_Operational', 'MCP6002-xP', 'MCP6002', 106.68, 125.73, 0, 3, {'8': P, '4': G}),
    ('C7',  'Device', 'C',            '100nF',  114.3, 125.73, 0, 1, {'1': P, '2': G}),
]
# Fils : suites de points ; un point est (réf, unité, broche) ou (x, y)
WIRES = [
    [('LS1', 1, '2'), ('C1', 1, '2')],
    [('LS1', 1, '1'), (33.02, 58.42), (33.02, 63.5)],
    [('C1', 1, '1'), ('R9', 1, '2')],
    [('R9', 1, '1'), ('U1', 1, '3')],                        # ligne INP
    [('R1', 1, '2'), (66.04, 55.88)],
    [('D2', 1, '2'), ('D3', 1, '1')],                         # clamp
    [(73.66, 73.66), (78.74, 73.66), (78.74, 55.88)],
    [('U1', 1, '2'), (91.44, 60.96), ('R5', 1, '1')],         # FB
    [(91.44, 68.58), ('R4', 1, '1')],
    [('R4', 1, '2'), (111.76, 68.58), (111.76, 58.42)],
    [('U1', 1, '1'), ('C4', 1, '1')],                         # AMP
    [('R5', 1, '2'), ('C3', 1, '1')],                         # RG
    [('C4', 1, '2'), ('D1', 1, '2')],                         # AC
    [('R6', 1, '1'), (127.0, 58.42)],
    [('D1', 1, '1'), ('J1', 1, '2')],                         # ENV
    [('J1', 1, '1'), (167.64, 55.88), (167.64, 50.8)],
    [('J1', 1, '3'), (167.64, 60.96), (167.64, 66.04)],
    [('C5', 1, '1'), (147.32, 58.42)],
    [('R7', 1, '1'), (157.48, 58.42)],
    [('R2', 1, '2'), ('R3', 1, '1')],                         # VDIV
    [(40.64, 123.19), ('U1', 2, '5')],
    [('C2', 1, '1'), (50.8, 123.19)],
    [('U1', 2, '6'), (60.96, 128.27), (60.96, 133.35), (81.28, 133.35), (81.28, 125.73)],
    [('U1', 2, '7'), (86.36, 125.73)],
]
JUNCTIONS = [(66.04, 55.88), (78.74, 55.88), (73.66, 73.66), (91.44, 68.58), (111.76, 58.42), (127.0, 58.42),
             (147.32, 58.42), (157.48, 58.42), (40.64, 123.19), (50.8, 123.19), (81.28, 125.73)]
LABELS = [('VBIAS', 86.36, 125.73, 0), ('INP', 83.82, 55.88, 0), ('ENV', 160.02, 58.42, 0)]
POWERS = [(G, 33.02, 63.5, 270), (P, 167.64, 50.8, 90), (G, 167.64, 66.04, 270)]
FLAGS = [(P, 132.08, 116.84), (G, 142.24, 116.84)]   # PWR_FLAG : l'alimentation vient de J1

TEXTS = [
    (25.4, 17.78, 2.0, 'Haut-parleur capteur → enveloppe → ADC (XIAO ESP32-C3)'),
    (25.4, 21.59, 1.27, 'Frappe / frottement de la membrane → Note On/Off + aftertouch via le composant Velostat de NiDMI.'),
    (25.4, 25.4, 1.27, 'Gain alternatif = 1 + R4/R5 ≈ 22 (ajuster R5 : 2.2k → ×46, 10k → ×11).  Enveloppe : τ = R7·C5 ≈ 22 ms.'),
    (25.4, 29.21, 1.27, 'D2/D3 (1N4148) limitent l\'entrée de l\'ampli à −0,6 V / +3,9 V quand on frappe fort ; R9 limite le courant.'),
    (25.4, 105.41, 1.27, 'VBIAS = 1,65 V (milieu de l\'alimentation), tamponné par U1B'),
    (124.46, 86.36, 1.27, 'D1 = 1N4148 : seuil ≈ 0,5 V (porte de bruit).\nRégler velocityMax ≈ 1500–1800 dans le Velostat.'),
    (180.34, 53.34, 1.27, 'J1 vers XIAO :\n1 = 3V3\n2 = D0 (GPIO2, ADC1)\n3 = GND'),
]

def rot(x, y, r):
    a = math.radians(r)
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)

def r2(v): return round(v, 2)

defs, out_syms, items, pwr_n = {}, [], [], [0]

def eff(size=1.27, justify=None, hide=False):
    e = ['effects', ['font', ['size', size, size]]]
    if justify: e.append(['justify'] + justify.split())
    if hide: e.append(['hide', 'yes'])
    return e

def prop(name, val, x, y, ang=0, justify=None, hide=False):
    return ['property', S(name), S(val), ['at', r2(x), r2(y), ang], eff(justify=justify, hide=hide)]

def symdef(libname, name):
    key = f'{libname}:{name}'
    if key not in defs:
        defs[key] = flatten(LIB + libname + '.kicad_sym', name, libname)
    return defs[key]

def lib_is_part(l): return l != 'power'

def place(ref, libname, name, value, x, y, r, unit, extra_props=(), refpos=None, valpos=None, hide_ref=False):
    d = symdef(libname, name)
    k = (ref, unit)
    fa = 90 if r in (90, 270) and lib_is_part(libname) else 0
    rp = refpos or (x, y - 6.35)
    vp = valpos or (x, y + 6.35)
    s = ['symbol', ['lib_id', S(f'{libname}:{name}')], ['at', r2(x), r2(y), r], ['unit', unit],
         ['exclude_from_sim', 'no'], ['in_bom', 'yes'], ['on_board', 'yes'], ['dnp', 'no'],
         ['uuid', uid('sym', *k)],
         prop('Reference', ref, *rp, ang=fa, hide=hide_ref), prop('Value', value, *vp, ang=fa),
         prop('Footprint', '', x, y, hide=True), prop('Datasheet', '', x, y, hide=True),
         *extra_props]
    for num, *_ in pins(d):
        if _[1] in (0, unit):
            s.append(['pin', S(num), ['uuid', uid('pin', *k, num)]])
    s.append(['instances', ['project', S(PROJ), ['path', S('/' + ROOT), ['reference', S(ref)], ['unit', unit]]]])
    out_syms.append(s)
    return d

def wire(x1, y1, x2, y2, *k):
    items.append(['wire', ['pts', ['xy', r2(x1), r2(y1)], ['xy', r2(x2), r2(y2)]],
                  ['stroke', ['width', 0], ['type', 'default']], ['uuid', uid('w', *k)]])

def power(net, x, y, outward):
    """Symbole d'alimentation au bout du fil, orienté vers l'extérieur."""
    pwr_n[0] += 1
    ref = f'#PWR0{pwr_n[0]:02d}'
    # GND pointe vers le bas à 0°, +3V3 vers le haut ; rotation pour suivre la direction sortante
    base = 270 if net == G else 90
    r = int((outward - base) % 360)
    tx, ty = rot(0, -3.81 if net == G else 3.81, r)
    place(ref, 'power', net, net, x, y, r, 1, refpos=(x, y), valpos=(x + tx, y - ty), hide_ref=True)

def label(net, x, y, outward, *k):
    ang = {0: 0, 90: 90, 180: 180, 270: 270}[int(outward) % 360]
    just = 'left bottom' if ang in (0, 90) else 'right bottom'
    items.append(['label', S(net), ['at', r2(x), r2(y), ang], ['fields_autoplaced', 'yes'],
                  eff(justify=just), ['uuid', uid('lbl', *k)]])

# Positions des étiquettes Référence/Valeur selon la forme du composant
def ref_val_pos(name, x, y, r):
    if name in ('R', 'C', 'C_Polarized'):
        if r in (0, 180):
            return (x + 2.54, y - 1.27), (x + 2.54, y + 1.27)
        return (x, y - 3.81), (x, y + 3.81)
    if name == 'MCP6002-xP':
        return (x + 2.54, y - 7.62), (x + 2.54, y - 5.08)
    if name == 'BAT54S':
        return (x - 10.16, y - 1.27), (x - 10.16, y + 1.27)
    if name == '1N4148':
        if r in (90, 270):
            return (x - 6.35, y - 1.27), (x - 6.35, y + 1.27)
        return (x, y - 3.81), (x, y + 3.81)
    if name == 'Speaker':
        return (x - 2.54, y - 7.62), (x - 2.54, y + 6.35)
    if name == 'Conn_01x03':
        return (x, y - 6.35), (x + 12.7, y + 6.35)
    return (x, y - 6.35), (x, y + 6.35)

PINPOS = {}
for ref, libname, name, value, x, y, r, unit, nets in PARTS:
    rp, vp = ref_val_pos(name, x, y, r)
    d = place(ref, libname, name, value, x, y, r, unit, refpos=rp, valpos=vp)
    for num, pname, pu, px, py, pa in pins(d):
        if pu not in (0, unit) or num not in nets:
            continue
        dx, dy = rot(px, py, r)
        cx, cy = x + dx, y - dy                       # point de connexion (Y schéma vers le bas)
        PINPOS[(ref, unit, num)] = (r2(cx), r2(cy))
        conn = nets[num]
        if conn == '-':
            continue
        conn, _, ln = conn.partition('@')
        outward = (pa + 180 + r) % 360                # direction sortante en coordonnées bibliothèque
        ox, oy = rot(float(ln or STUB), 0, outward)
        ex, ey = cx + ox, cy - oy
        wire(cx, cy, ex, ey, ref, unit, num)
        if conn in (P, G):
            power(conn, ex, ey, outward)
        else:
            label(conn[2:], ex, ey, outward, ref, unit, num)
    missing = set(nets) - {p[0] for p in pins(d)}
    assert not missing, (ref, missing)

for i, poly in enumerate(WIRES):
    pts = [PINPOS[p] if isinstance(p[0], str) else p for p in poly]
    for j in range(len(pts) - 1):
        (x1, y1), (x2, y2) = pts[j], pts[j + 1]
        assert x1 == x2 or y1 == y2, ('fil oblique', poly, pts)
        wire(x1, y1, x2, y2, 'poly', i, j)
# Couper chaque fil aux jonctions et aux extrémités d'autres fils qui tombent en son milieu
def split_wires():
    ws = [it for it in items if it[0] == 'wire']
    pts = {(e[1], e[2]) for w in ws for e in w[1][1:]} | set(JUNCTIONS) | {(x, y) for _, x, y, _ in LABELS}
    out = []
    for w in ws:
        (_, x1, y1), (_, x2, y2) = w[1][1], w[1][2]
        inner = [(x, y) for (x, y) in pts
                 if (x1 == x2 == x and min(y1, y2) < y < max(y1, y2))
                 or (y1 == y2 == y and min(x1, x2) < x < max(x1, x2))]
        inner.sort(key=lambda p: abs(p[0] - x1) + abs(p[1] - y1))
        chain = [(x1, y1), *inner, (x2, y2)]
        for k in range(len(chain) - 1):
            out.append(['wire', ['pts', ['xy', *chain[k]], ['xy', *chain[k + 1]]],
                        ['stroke', ['width', 0], ['type', 'default']], ['uuid', uid(w[-1][1], k)]])
    items[:] = [it for it in items if it[0] != 'wire'] + out
split_wires()

for i, (x, y) in enumerate(JUNCTIONS):
    items.append(['junction', ['at', x, y], ['diameter', 0], ['color', 0, 0, 0, 0], ['uuid', uid('jct', i)]])
for i, (net, x, y, a) in enumerate(LABELS):
    label(net, x, y, a, 'extra', i)
for net, x, y, a in POWERS:
    power(net, x, y, a)

for i, (net, x, y) in enumerate(FLAGS):
    place(f'#FLG0{i + 1}', 'power', 'PWR_FLAG', 'PWR_FLAG', x, y, 0, 1,
          refpos=(x, y), valpos=(x, y - 3.81), hide_ref=True)
    wire(x, y, x, y + STUB, 'flag', i)
    power(net, x, y + STUB, 270)

for i, (x, y, size, txt) in enumerate(TEXTS):
    items.append(['text', S(txt), ['exclude_from_sim', 'no'], ['at', x, y, 0],
                  ['effects', ['font', ['size', size, size]], ['justify', 'left', 'bottom']],
                  ['uuid', uid('txt', i)]])

doc = ['kicad_sch', ['version', 20250114], ['generator', S('eeschema')], ['generator_version', S('9.0')],
       ['uuid', ROOT], ['paper', S('A4')],
       ['title_block', ['title', S('Haut-parleur capteur → XIAO ESP32-C3')], ['date', S('2026-10-15')],
        ['rev', S('0.1')], ['company', S('NiDMI')],
        ['comment', 1, S('Enveloppe pour le composant Velostat (Note On/Off + aftertouch)')]],
       ['lib_symbols', *defs.values()],
       *items, *out_syms,
       ['sheet_instances', ['path', S('/'), ['page', S('1')]]],
       ['embedded_fonts', 'no']]
with open(OUT, 'w', encoding='utf-8') as f:
    f.write(dump(doc) + '\n')
print('écrit', OUT)
