"""Générateur de schémas KiCad à partir d'une description par nets.

On place les composants à la main (coordonnées en mm, grille 2,54) et on donne, broche par broche,
le net auquel elle appartient. Le générateur :
  - trace les fils explicitement demandés (`wire`) ;
  - relie automatiquement les nets à deux broches alignées (fil droit) ou presque (un coude),
    si le tracé ne traverse aucun corps de composant ni aucun autre net ;
  - pose un court fil + une étiquette de net sur les broches restantes, un symbole
    d'alimentation sur les nets d'alimentation, un drapeau « non connecté » sur 'NC' ;
  - ajuste la page au contenu, puis vérifie avec kicad-cli : ERC + comparaison de la netlist
    exportée avec les nets voulus. Toute fusion accidentelle de deux nets fait échouer la génération.

Réutilise kisexpr.py (lecteur S-expression + aplatissement des symboles) de scratchpad/hp-capteur.
"""
import json, math, os, re, subprocess, sys, uuid
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'hp-capteur'))
from kisexpr import S, flatten, pins, dump, parse, find, first

LIB = '/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols/'
CLI = '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
POWER = {'GND', '+5V', '+3V3', '+9V', '+BATT'}
STUB = 2.54
EPS = 1e-6


def r2(v): return round(v + 0.0, 2)


def rot(x, y, r):
    a = math.radians(r)
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)


def unit_vec(ang):
    return {0: (1, 0), 90: (0, -1), 180: (-1, 0), 270: (0, 1)}[int(ang) % 360]   # repère schéma (Y bas)


def body_bbox(flat, unit):
    """Boîte des graphismes (hors pattes) d'une unité, repère bibliothèque."""
    xs, ys = [], []
    for sub in find(flat, 'symbol'):
        m = re.search(r'_(\d+)_(\d+)$', sub[1])
        u, style = int(m.group(1)), int(m.group(2))
        if style > 1 or u not in (0, unit):
            continue
        for g in sub:
            if not isinstance(g, list) or not g:
                continue
            if g[0] == 'rectangle':
                for k in ('start', 'end'):
                    p = first(g, k); xs.append(float(p[1])); ys.append(float(p[2]))
            elif g[0] in ('polyline', 'bezier'):
                for p in find(first(g, 'pts'), 'xy'):
                    xs.append(float(p[1])); ys.append(float(p[2]))
            elif g[0] == 'circle':
                c = first(g, 'center'); rr = float(first(g, 'radius')[1])
                xs += [float(c[1]) - rr, float(c[1]) + rr]; ys += [float(c[2]) - rr, float(c[2]) + rr]
            elif g[0] == 'arc':
                for k in ('start', 'mid', 'end'):
                    p = first(g, k); xs.append(float(p[1])); ys.append(float(p[2]))
            elif g[0] == 'pin':
                at = first(g, 'at'); ln = float(first(g, 'length')[1])
                a = math.radians(float(at[3]))
                xs.append(float(at[1]) + ln * math.cos(a)); ys.append(float(at[2]) + ln * math.sin(a))
    if not xs:
        return (0, 0, 0, 0)
    return min(xs), min(ys), max(xs), max(ys)


class Part:
    def __init__(self, ref, lib_id, value, x, y, r, unit, nets, rv):
        self.ref, self.lib_id, self.value, self.x, self.y, self.r, self.unit = ref, lib_id, value, x, y, r, unit
        self.nets, self.rv = nets, rv


class Sch:
    def __init__(self, name, title, notes=()):
        self.name, self.title, self.notes = name, title, list(notes)
        self.parts, self.wires, self.labels, self.texts, self.manual_pwr = [], [], [], [], []
        self.NS = uuid.uuid5(uuid.NAMESPACE_URL, 'nidmi/em-bending/' + name)

    def uid(self, *k): return S(str(uuid.uuid5(self.NS, '/'.join(map(str, k)))))

    # ── description ──
    def part(self, ref, lib_id, value, x, y, r=0, unit=1, nets=None, rv=None):
        self.parts.append(Part(ref, lib_id, value, x, y, r, unit, dict(nets or {}), rv))
        self.parts[-1].rv_center = False

    def wire(self, *pts, net=None):
        """Polyligne ; un point est 'REF.broche' ou (x, y). Sans broche, donner `net`."""
        self.wires.append((list(pts), net))

    def label(self, net, x, y, ang=0):
        self.labels.append((net, x, y, ang))

    def text(self, x, y, txt, size=1.27):
        self.texts.append((x, y, txt, size))

    def power(self, net, x, y, out=None):
        """Symbole d'alimentation posé à la main au bout d'un fil explicite."""
        self.manual_pwr.append((net, x, y, out if out is not None else (270 if net == 'GND' else 90)))

    # ── génération ──
    def _defs(self):
        self.defs = {}
        for p in self.parts:
            libname, sym = p.lib_id.split(':')
            if p.lib_id not in self.defs:
                self.defs[p.lib_id] = flatten(LIB + libname + '.kicad_sym', sym, libname)

    def _pins(self):
        """Position, direction sortante et net de chaque broche utilisée."""
        self.pin = {}          # (ref, num) -> dict
        for p in self.parts:
            d = self.defs[p.lib_id]
            nums = []
            for num, name, u, px, py, pa in pins(d):
                if u not in (0, p.unit):
                    continue
                nums.append(num)
                dx, dy = rot(px, py, p.r)
                out = int((pa + 180 + p.r) % 360)
                if num not in p.nets:
                    raise SystemExit(f'{self.name}: {p.ref} broche {num} ({name}) sans net')
                raw = p.nets[num]
                self.pin[(p.ref, num)] = dict(x=r2(p.x + dx), y=r2(p.y - dy), out=out, net=raw.rstrip('!'),
                                              straight=raw.endswith('!'), part=p)
            extra = set(p.nets) - set(nums)
            if extra:
                raise SystemExit(f'{self.name}: {p.ref} broches inconnues {extra}')
            bx0, by0, bx1, by1 = body_bbox(d, p.unit)
            cs = [rot(cx, cy, p.r) for cx, cy in ((bx0, by0), (bx0, by1), (bx1, by0), (bx1, by1))]
            p.bbox = (p.x + min(c[0] for c in cs), p.y - max(c[1] for c in cs),
                      p.x + max(c[0] for c in cs), p.y - min(c[1] for c in cs))

    def _pt(self, spec):
        if isinstance(spec, str):
            ref, num = spec.rsplit('.', 1)
            q = self.pin[(ref, num)]
            return (q['x'], q['y'])
        return (r2(spec[0]), r2(spec[1]))

    # Segments déjà tracés : (x1, y1, x2, y2, net)
    def _on_seg(self, x, y, s, interior=True):
        x1, y1, x2, y2 = s[:4]
        if abs(x1 - x2) < EPS and abs(x - x1) < EPS:
            lo, hi = sorted((y1, y2))
            return lo + EPS < y < hi - EPS if interior else lo - EPS <= y <= hi + EPS
        if abs(y1 - y2) < EPS and abs(y - y1) < EPS:
            lo, hi = sorted((x1, x2))
            return lo + EPS < x < hi - EPS if interior else lo - EPS <= x <= hi + EPS
        return False

    def _seg_ok(self, a, b, net, own_parts=()):
        """Le segment a–b peut-il être tracé pour `net` sans contact parasite ?"""
        (x1, y1), (x2, y2) = a, b
        seg = (x1, y1, x2, y2)
        # traverse un corps de composant ?
        for p in self.parts:
            bx0, by0, bx1, by1 = p.bbox
            m = 0.3
            if abs(x1 - x2) < EPS:
                lo, hi = sorted((y1, y2))
                if bx0 + m < x1 < bx1 - m and lo < by1 - m and hi > by0 + m:
                    return False
            else:
                lo, hi = sorted((x1, x2))
                if by0 + m < y1 < by1 - m and lo < bx1 - m and hi > bx0 + m:
                    return False
        # touche une broche d'un autre net ?
        for q in self.pin.values():
            if q['net'] != net and self._on_seg(q['x'], q['y'], seg, interior=False):
                return False
        for s in self.segs:
            if s[4] == net:
                continue
            # extrémité posée sur l'autre, ou recouvrement colinéaire
            if self._on_seg(x1, y1, s, False) or self._on_seg(x2, y2, s, False):
                return False
            if self._on_seg(s[0], s[1], seg, False) or self._on_seg(s[2], s[3], seg, False):
                return False
        for (lx, ly, ln) in self.lab_pts:
            if ln != net and self._on_seg(lx, ly, seg, False):
                return False
        return True

    def _add_seg(self, a, b, net):
        if a != b:
            self.segs.append((a[0], a[1], b[0], b[1], net))

    def _route(self):
        self.segs, self.lab_pts, self.power_syms, self.ncs, self.auto_labels = [], [], [], [], []
        nets = {}
        for k, q in self.pin.items():
            nets.setdefault(q['net'], []).append(k)
        covered = set()
        # 1. fils explicites
        for poly, wnet in self.wires:
            pts = [self._pt(s) for s in poly]
            pin_specs = [s for s in poly if isinstance(s, str)]
            if not pin_specs and not wnet:
                raise SystemExit(f'{self.name}: fil sans broche {poly}')
            netset = {self.pin[tuple(s.rsplit('.', 1))]['net'].split('@')[0] for s in pin_specs} | ({wnet} if wnet else set())
            if len(netset) != 1:
                raise SystemExit(f'{self.name}: fil reliant plusieurs nets {netset} {poly}')
            net = netset.pop()
            for s in pin_specs:
                covered.add(tuple(s.rsplit('.', 1)))
            for a, b in zip(pts, pts[1:]):
                if not (abs(a[0] - b[0]) < EPS or abs(a[1] - b[1]) < EPS):
                    raise SystemExit(f'{self.name}: fil oblique {a}->{b}')
                self._add_seg(a, b, net)
        # broches touchées par un fil explicite sans y être nommées
        for k, q in self.pin.items():
            if k not in covered and any(self._on_seg(q['x'], q['y'], s, False) and s[4] == q['net'] for s in self.segs):
                covered.add(k)
        for net, x, y, a in self.labels:
            self.lab_pts.append((x, y, net))
        for net, x, y, a in self.manual_pwr:
            self.lab_pts.append((x, y, net))
            self.power_syms.append((net, x, y, a))
        # 2. alimentation / NC
        for k, q in sorted(self.pin.items()):
            net = q['net'].split('@')[0]
            if k in covered:
                continue
            if net == 'NC':
                self.ncs.append((q['x'], q['y'])); covered.add(k)
            elif net in POWER:
                lens = [float(q['net'].split('@')[1])] if '@' in q['net'] else [STUB, 5.08, 7.62, 10.16]
                ux, uy = unit_vec(q['out'])
                for ln in lens:
                    path = [(q['x'], q['y']), (r2(q['x'] + ux * ln), r2(q['y'] + uy * ln))]
                    out = q['out']
                    if out in (0, 180) and not q['straight']:
                        up = -1 if net != 'GND' else 1
                        path.append((path[1][0], r2(path[1][1] + up * STUB)))
                        out = 270 if net == 'GND' else 90
                    if all(self._seg_ok(a, b, net) for a, b in zip(path, path[1:])):
                        break
                else:
                    raise SystemExit(f'{self.name}: pas de place pour {net} sur {k}')
                for a, b in zip(path, path[1:]):
                    self._add_seg(a, b, net)
                self.power_syms.append((net, path[-1][0], path[-1][1], out))
                self.lab_pts.append((path[-1][0], path[-1][1], net))
                covered.add(k)
        # 3. nets à deux broches : fil droit ou un coude
        for net, ks in sorted(nets.items()):
            base = net.split('@')[0]
            if base in POWER or base == 'NC':
                continue
            if any(k in covered for k in ks) or len(ks) != 2:
                continue
            a, b = (self.pin[k] for k in ks)
            pa, pb = (a['x'], a['y']), (b['x'], b['y'])
            ua, ub = unit_vec(a['out']), unit_vec(b['out'])
            cands = []
            if abs(pa[0] - pb[0]) < EPS or abs(pa[1] - pb[1]) < EPS:
                d = (pb[0] - pa[0], pb[1] - pa[1])
                if (d[0] * ua[0] + d[1] * ua[1]) > 0 and (-d[0] * ub[0] - d[1] * ub[1]) > 0:
                    cands.append([pa, pb])
            else:
                for c in ((pb[0], pa[1]), (pa[0], pb[1])):
                    da = (c[0] - pa[0], c[1] - pa[1]); db = (c[0] - pb[0], c[1] - pb[1])
                    if da[0] * ua[0] + da[1] * ua[1] > 0 and db[0] * ub[0] + db[1] * ub[1] > 0:
                        cands.append([pa, c, pb])
            for path in cands:
                if all(self._seg_ok(s, t, net) for s, t in zip(path, path[1:])):
                    for s, t in zip(path, path[1:]):
                        self._add_seg(s, t, net)
                    covered.update(ks)
                    break
        # 4. étiquettes sur les broches restantes
        for net, ks in sorted(nets.items()):
            base = net.split('@')[0]
            rest = [k for k in ks if k not in covered]
            if not rest:
                continue
            wired = [k for k in ks if k in covered]
            if wired and base not in POWER and not any(l[0] == base for l in self.labels):
                raise SystemExit(f'{self.name}: net {base} en partie câblé, ajouter une étiquette sur la partie câblée')
            for k in rest:
                q = self.pin[k]
                ux, uy = unit_vec(q['out'])
                for ln in ([float(net.split('@')[1])] if '@' in net else [STUB, 5.08, 1.27, 7.62]):
                    e = (r2(q['x'] + ux * ln), r2(q['y'] + uy * ln))
                    if self._seg_ok((q['x'], q['y']), e, base):
                        break
                else:
                    raise SystemExit(f'{self.name}: pas de place pour l\'étiquette {base} sur {k}')
                self._add_seg((q['x'], q['y']), e, base)
                self.auto_labels.append((base, e[0], e[1], q['out']))
                self.lab_pts.append((e[0], e[1], base))

    def _junctions(self):
        pts = {}
        def bump(p, n): pts[p] = pts.get(p, 0) + n
        for s in self.segs:
            bump((r2(s[0]), r2(s[1])), 1); bump((r2(s[2]), r2(s[3])), 1)
        for q in self.pin.values():
            k = (q['x'], q['y'])
            if k in pts or any(self._on_seg(k[0], k[1], sg, True) for sg in self.segs):
                bump(k, 1)
        for (lx, ly, _n) in self.lab_pts:
            if any(self._on_seg(lx, ly, sg, True) for sg in self.segs):
                pts.setdefault((r2(lx), r2(ly)), 0)
        # T : extrémité posée au milieu d'un segment → couper le segment
        changed = True
        while changed:
            changed = False
            for i, s in enumerate(self.segs):
                for p in list(pts):
                    if self._on_seg(p[0], p[1], s, interior=True):
                        self.segs[i:i + 1] = [(s[0], s[1], p[0], p[1], s[4]), (p[0], p[1], s[2], s[3], s[4])]
                        bump(p, 2); changed = True
                        break
                if changed:
                    break
        self.junc = [p for p, n in pts.items() if n >= 3]

    def _fit(self):
        """Décale tout pour que le contenu commence à la marge, et taille la page."""
        xs, ys = [], []
        for p in self.parts:
            xs += [p.bbox[0], p.bbox[2]]; ys += [p.bbox[1], p.bbox[3]]
        for s in self.segs:
            xs += [s[0], s[2]]; ys += [s[1], s[3]]
        for (net, x, y, a) in self.labels + self.auto_labels:
            w = 1.0 * len(net) + 2
            ux, uy = unit_vec(a)
            xs += [x, x + ux * w]; ys += [y - 1.5, y + uy * w]
        for (_, x, y, a) in self.power_syms:
            xs += [x - 3, x + 3]; ys += [y - 5, y + 5]
        for p in self.parts:                                  # textes Référence/Valeur
            (rx, ry), (vx, vy) = self._rv(p)
            for tx, ty, t in ((rx, ry, p.ref), (vx, vy, p.value)):
                xs += [tx - 0.45 * len(t) - 0.5, tx + 0.45 * len(t) + 0.5]; ys += [ty - 1.5, ty + 1]
        self.title_y = min(ys) - 10
        for (x, y, txt, size) in self.texts:
            lines = txt.split('\n')
            xs += [x, x + 0.75 * size * max(len(l) for l in lines)]; ys += [y - size, y + 1.7 * size * len(lines)]
        for n in self.notes:
            xs.append(min(xs) + 2 + 0.82 * len(n))
        tw = 0.75 * 2.0 * len(self.title)
        xs += [min(xs) + tw]; ys += [self.title_y - 2]
        nl = len(self.notes)
        g = 2.54
        x0 = math.floor((min(xs) - 6) / g) * g
        y0 = math.floor((min(ys) - 6) / g) * g
        self.dx, self.dy = -x0, -y0
        self.W = math.ceil((max(xs) - x0 + 6) / g) * g
        self.H = math.ceil((max(ys) - y0 + 6 + nl * 2.3) / g) * g
        self.notes_y = max(ys) + 4

    def _rv(self, p):
        """Centres des champs Référence / Valeur (texte centré : insensible aux rotations)."""
        cw = 0.41                                             # demi-largeur d'un caractère (police 1,27)
        if p.rv:
            (a, b), (c, d) = p.rv
            return (p.x + a + cw * len(p.ref), p.y + b), (p.x + c + cw * len(p.value), p.y + d)
        bx0, by0, bx1, by1 = p.bbox
        w, h = bx1 - bx0, by1 - by0
        lib = p.lib_id.split(':')[0]
        npins = sum(1 for k in self.pin if k[0] == p.ref and self.pin[k]['part'] is p)
        cy = (by0 + by1) / 2
        if lib == 'Connector_Generic':                        # du côté opposé aux broches
            if any(q['out'] == 180 for q in self.pin.values() if q['part'] is p):
                return (bx1 + 1.5 + cw * len(p.ref), cy - 1.27), (bx1 + 1.5 + cw * len(p.value), cy + 1.27)
            return (bx0 - 1.5 - cw * len(p.ref), cy - 1.27), (bx0 - 1.5 - cw * len(p.value), cy + 1.27)
        pp = [q for q in self.pin.values() if q['part'] is p]
        if npins == 2 and abs(pp[0]['y'] - pp[1]['y']) < EPS:  # dipôle horizontal : dessus / dessous
            return (p.x, by0 - 1.6), (p.x, by1 + 2.4)
        if npins <= 3 and w <= 8:                             # dipôle vertical, transistor : à droite
            return (bx1 + 1 + cw * len(p.ref), cy - 1.27), (bx1 + 1 + cw * len(p.value), cy + 1.27)
        return (bx1 + 0.6 + cw * len(p.ref), by0 + 0.4), (bx1 + 0.6 + cw * len(p.value), by0 + 2.5)

    def build(self, outdir):
        self._defs(); self._pins(); self._route(); self._junctions(); self._fit()
        dx, dy = self.dx, self.dy
        X = lambda v: r2(v + dx)
        Y = lambda v: r2(v + dy)
        items, syms, pwr = [], [], [0]
        ROOT = self.uid('root')

        def eff(size=1.27, justify=None, hide=False):
            e = ['effects', ['font', ['size', size, size]]]
            if justify: e.append(['justify'] + justify.split())
            if hide: e.append(['hide', 'yes'])
            return e

        def prop(n, v, x, y, ang=0, justify=None, hide=False):
            return ['property', S(n), S(v), ['at', X(x), Y(y), ang], eff(justify=justify, hide=hide)]

        def place(ref, lib_id, value, x, y, r, unit, rp, vp, hide_ref=False, k=None, rjust='left', ang=0):
            d = self.defs.setdefault(lib_id, flatten(LIB + lib_id.split(':')[0] + '.kicad_sym',
                                                     lib_id.split(':')[1], lib_id.split(':')[0]))
            k = k or (ref, unit)
            s = ['symbol', ['lib_id', S(lib_id)], ['at', X(x), Y(y), r], ['unit', unit],
                 ['exclude_from_sim', 'no'], ['in_bom', 'yes'], ['on_board', 'yes'], ['dnp', 'no'],
                 ['uuid', self.uid('sym', *k)],
                 prop('Reference', ref, *rp, ang=ang, justify=rjust, hide=hide_ref),
                 prop('Value', value, *vp, ang=ang, justify=rjust),
                 prop('Footprint', '', x, y, hide=True), prop('Datasheet', '', x, y, hide=True)]
            for num, _, u, *_r in pins(d):
                if u in (0, unit):
                    s.append(['pin', S(num), ['uuid', self.uid('pin', *k, num)]])
            s.append(['instances', ['project', S(self.name), ['path', S('/' + ROOT), ['reference', S(ref)], ['unit', unit]]]])
            syms.append(s)

        for p in self.parts:
            rp, vp = self._rv(p)
            turned = p.r in (90, 270)
            place(p.ref, p.lib_id, p.value, p.x, p.y, p.r, p.unit, rp, vp,
                  rjust='', ang=90 if turned else 0)
        for net, x, y, out in self.power_syms:
            pwr[0] += 1
            base = 270 if net == 'GND' else 90
            r = int((out - base) % 360)
            tx, ty = rot(0, -3.81 if net == 'GND' else 3.81, r)
            place(f'#PWR{pwr[0]:03d}', 'power:' + net, net, x, y, r, 1, (x, y), (x + tx, y - ty),
                  hide_ref=True, rjust='', k=('pwr', pwr[0]))
        for i, s in enumerate(self.segs):
            items.append(['wire', ['pts', ['xy', X(s[0]), Y(s[1])], ['xy', X(s[2]), Y(s[3])]],
                          ['stroke', ['width', 0], ['type', 'default']], ['uuid', self.uid('w', i)]])
        for i, (x, y) in enumerate(self.junc):
            items.append(['junction', ['at', X(x), Y(y)], ['diameter', 0], ['color', 0, 0, 0, 0], ['uuid', self.uid('j', i)]])
        for i, (x, y) in enumerate(self.ncs):
            items.append(['no_connect', ['at', X(x), Y(y)], ['uuid', self.uid('nc', i)]])
        for i, (net, x, y, a) in enumerate(self.labels + self.auto_labels):
            a = int(a) % 360
            just = 'left bottom' if a in (0, 90) else 'right bottom'
            items.append(['label', S(net), ['at', X(x), Y(y), a], ['fields_autoplaced', 'yes'],
                          eff(justify=just), ['uuid', self.uid('l', i)]])
        texts = [(min(p.bbox[0] for p in self.parts), self.title_y, self.title, 2.0)] + self.texts
        for i, n in enumerate(self.notes):
            texts.append((-dx + 7.62, self.notes_y + 2.3 * i, n, 1.27))
        for i, (x, y, txt, size) in enumerate(texts):
            items.append(['text', S(txt), ['exclude_from_sim', 'no'], ['at', X(x), Y(y), 0],
                          ['effects', ['font', ['size', size, size]], ['justify', 'left', 'bottom']],
                          ['uuid', self.uid('t', i)]])
        doc = ['kicad_sch', ['version', 20250114], ['generator', S('eeschema')], ['generator_version', S('9.0')],
               ['uuid', ROOT], ['paper', S('User'), r2(self.W), r2(self.H)],
               ['title_block', ['title', S(self.title)], ['company', S('NiDMI')]],
               ['lib_symbols', *self.defs.values()], *items, *syms,
               ['sheet_instances', ['path', S('/'), ['page', S('1')]]], ['embedded_fonts', 'no']]
        os.makedirs(outdir, exist_ok=True)
        path = os.path.join(outdir, self.name + '.kicad_sch')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(dump(doc) + '\n')
        return self._check(path, outdir)

    # ── vérifications kicad-cli ──
    def _check(self, path, outdir):
        tmp = os.path.join(outdir, '.check'); os.makedirs(tmp, exist_ok=True)
        nl = os.path.join(tmp, self.name + '.net')
        subprocess.run([CLI, 'sch', 'export', 'netlist', '-o', nl, path], check=True, capture_output=True)
        got = {}
        for net in find(first(parse(open(nl, encoding='utf-8').read()), 'nets'), 'net'):
            nodes = frozenset((n[1][1], n[2][1]) for n in find(net, 'node')
                              for n in [[None, first(n, 'ref'), first(n, 'pin')]] if not n[1][1].startswith('#'))
            if nodes:
                got[first(net, 'name')[1]] = nodes
        want = {}
        for (ref, num), q in self.pin.items():
            base = q['net'].split('@')[0]
            if base != 'NC':
                want.setdefault(base, set()).add((ref, num))
        want_sets = {frozenset(v) for v in want.values() if len(v) > 0}
        got_sets = set(got.values())
        errs = []
        for w in want_sets - got_sets:
            name = next(k for k, v in want.items() if frozenset(v) == w)
            errs.append(f'net voulu {name} absent tel quel : {sorted(w)}')
        for g in got_sets - want_sets:
            name = next(k for k, v in got.items() if v == g)
            if name.startswith('unconnected-') and len(g) == 1:
                continue
            if len(g) > 1 or not any(g <= w for w in want_sets):
                errs.append(f'net obtenu {name} inattendu : {sorted(g)}')
        erc = os.path.join(tmp, self.name + '.erc.json')
        subprocess.run([CLI, 'sch', 'erc', '--format', 'json', '--severity-all', '-o', erc, path], capture_output=True)
        ignore = {'power_pin_not_driven', 'missing_unit', 'missing_power_pin', 'lib_symbol_issues',
                  'lib_symbol_mismatch', 'missing_input_pin', 'footprint_link_issues', 'pin_to_pin', 'unit_value_mismatch'}
        viol = []
        for sh in json.load(open(erc)).get('sheets', []):
            for v in sh.get('violations', []):
                if v['type'] not in ignore:
                    viol.append(f"ERC {v['type']}: {v['description']} " +
                                ' / '.join(i['description'] for i in v.get('items', [])))
        subprocess.run([CLI, 'sch', 'export', 'svg', '-e', '-o', outdir, path], check=True, capture_output=True)
        return errs + viol
