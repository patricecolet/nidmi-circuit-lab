"""Schémas de la bibliothèque de bending électromagnétique. Relancer : python3 -I circuits.py [nom…]

Coordonnées en unités de grille (2,54 mm). Chaque broche reçoit un net ; kischem.py trace les fils,
pose étiquettes et symboles d'alimentation, puis vérifie la netlist exportée par kicad-cli.
"""
import os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kischem import Sch

G = 2.54
def g(*v): return tuple(round(x * G, 2) for x in v)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'schemas')
CIRCUITS = {}
def circuit(f):
    CIRCUITS[f.__name__] = f
    return f

def P(s, ref, lib, val, x, y, r=0, unit=1, nets=None, rv=None):
    X, Y = g(x, y)
    if rv:
        rv = tuple(g(*p) for p in rv)
    s.part(ref, lib, val, X, Y, r, unit, nets, rv)

def W(s, *pts, net=None):
    s.wire(*[p if isinstance(p, str) else g(*p) for p in pts], net=net)

def PW(s, net, x, y, out=None):
    s.power(net, *g(x, y), out)

def Lb(s, net, x, y, a=0):
    s.label(net, *g(x, y), a)

def T(s, x, y, txt, size=1.27):
    s.text(*g(x, y), txt, size)


@circuit
def S0_ampli():
    s = Sch('S0_ampli', 'S0 — Ampli de sortie LM386 avec limiteur', notes=[
        'Toutes les boîtes son sortent sur J1 de ce module. D1/D2 écrêtent à ±0,6 V avant RV1 :',
        'le niveau maximal est plafonné quoi qu\'on branche en entrée (espace public).'])
    P(s, 'J1', 'Connector_Generic:Conn_01x02', 'entrée audio', 8, 25, 180, nets={'2': 'IN', '1': 'GND'})
    P(s, 'C1', 'Device:C', '1µF', 13.5, 24, 90, nets={'1': 'IN', '2': 'AC'})
    P(s, 'R1', 'Device:R', '10k', 18.5, 24, 90, nets={'1': 'AC', '2': 'LIM'})
    P(s, 'D1', 'Diode:1N4148', '1N4148', 22, 25.5, 90, nets={'2': 'LIM', '1': 'GND'})
    P(s, 'D2', 'Diode:1N4148', '1N4148', 27, 25.5, 270, nets={'1': 'LIM', '2': 'GND'})
    P(s, 'RV1', 'Device:R_Potentiometer', '10k niveau max', 33, 25.5, rv=((1.8, -1.6), (1.8, -0.6)), nets={'1': 'LIM', '3': 'GND', '2': 'VOL'})
    P(s, 'U1', 'Amplifier_Audio:LM386', 'LM386', 40, 26.5, nets={'3': 'VOL', '2': 'GND', '6': '+9V', '4': 'GND',
                                                              '7': 'NC', '1': 'NC', '8': 'NC', '5': 'OUT'})
    P(s, 'C3', 'Device:C_Polarized', '220µF', 46.5, 26.5, 90, nets={'1': 'OUT', '2': 'HP'})
    P(s, 'R2', 'Device:R', '10Ω', 44, 30, nets={'1': 'OUT', '2': 'ZOB'})
    P(s, 'C4', 'Device:C', '47nF', 44, 35, nets={'1': 'ZOB', '2': 'GND'})
    P(s, 'LS1', 'Device:Speaker', 'HP 8 Ω', 53, 26.5, nets={'1': 'HP', '2': 'GND'})
    P(s, 'J2', 'Connector_Generic:Conn_01x02', 'pile 9 V', 8, 34, 180, nets={'2': '+9V', '1': 'GND'})
    P(s, 'C5', 'Device:C_Polarized', '100µF', 14, 36.5, nets={'1': '+9V', '2': 'GND'})
    W(s, 'R1.2', 'RV1.1')
    W(s, 'U1.5', 'C3.1'); W(s, (44, 26.5), 'R2.1')
    Lb(s, 'LIM', 22, 24)
    return s


R, C, CP, L, LF, LI = 'Device:R', 'Device:C', 'Device:C_Polarized', 'Device:L', 'Device:L_Ferrite', 'Device:L_Iron'
POT, D4148, J2P = 'Device:R_Potentiometer', 'Diode:1N4148', 'Connector_Generic:Conn_01x02'


def supply(s, x, y, net, label='alim.'):
    """Connecteur d'alimentation (broche du haut = +) et découplage."""
    P(s, 'J9', J2P, label, x, y, 180, nets={'2': net, '1': 'GND'})
    P(s, 'C9', CP, '100µF', x + 6, y + 1.5, nets={'1': net, '2': 'GND'})


def out_jack(s, x, y, net, ref='J1', val='vers S0'):
    """Sortie audio vers l'ampli S0 (broche 1 = signal)."""
    P(s, ref, J2P, val, x, y, 0, nets={'1': net, '2': 'GND'})


@circuit
def S1_reed_apc():
    s = Sch('S1_reed_apc', 'S1 — Reed-bend sur Atari Punk Console (2 × NE555)', notes=[
        'U1 astable (hauteur, RV1) déclenche U2 monostable (largeur d\'impulsion, RV2) : le « stepped tone » de F. Mims.',
        'SW1 (ILS travail) : un aimant ajoute C3 en parallèle sur C1 → U1 descend d\'environ 3 octaves.',
        'SW2 (ILS travail) : met R4 en parallèle sur RV2 → impulsions courtes, timbre plus aigu.',
        'SW3 (ILS repos, s\'ouvre près d\'un aimant) : retire C2 → U2 ne tient plus que par les capacités parasites.',
        'ILS surmoulés (contacts d\'alarme de porte) : pas d\'ampoule de verre nue en extérieur.'])
    P(s, 'U1', 'Timer:NE555P', 'NE555', 22, 25, nets={'4': '+9V', '7': 'DIS1', '6': 'TH1', '2': 'TH1', '5': 'NC',
                                                      '8': '+9V', '1': 'GND', '3': 'CLK'})
    P(s, 'R1', R, '1k', 12, 21.5, nets={'1': '+9V', '2': 'DIS1'})
    P(s, 'RV1', POT, '500k', 12, 27, nets={'1': 'DIS1', '3': 'TH1', '2': 'TH1'})
    P(s, 'C1', C, '10nF', 15, 32.5, nets={'1': 'TH1', '2': 'GND'})
    P(s, 'SW1', 'Switch:SW_Reed', 'ILS', 18, 32, 90, nets={'2': 'TH1', '1': 'SW1C'})
    P(s, 'C3', C, '100nF', 18, 36.5, nets={'1': 'SW1C', '2': 'GND'})
    W(s, 'R1.2', 'RV1.1'); W(s, 'U1.7', (12, 24))
    W(s, 'U1.6', (15, 26), (15, 27), 'U1.2'); W(s, 'RV1.2', (15, 27))
    W(s, 'RV1.3', (12, 30), (15, 30), (15, 27)); W(s, (15, 30), 'C1.1'); W(s, (15, 30), 'SW1.2')
    P(s, 'U2', 'Timer:NE555P', 'NE555', 48, 25, nets={'4': '+9V', '7': 'TH2', '6': 'TH2', '2': 'CLK', '5': 'NC',
                                                      '8': '+9V', '1': 'GND', '3': 'OUT'})
    P(s, 'R2', R, '1k', 36, 19.5, nets={'1': '+9V', '2': 'RT2'})
    P(s, 'RV2', POT, '500k', 36, 24.5, nets={'1': 'RT2', '3': 'TH2', '2': 'TH2'})
    P(s, 'SW2', 'Switch:SW_Reed', 'ILS', 32, 24, 90, nets={'2': 'RT2', '1': 'SW2C'})
    P(s, 'R4', R, '10k', 32, 29.5, nets={'1': 'SW2C', '2': 'TH2'})
    P(s, 'SW3', 'Switch:SW_Reed_Opener', 'ILS repos', 38, 33, 90, nets={'2': 'TH2', '1': 'SW3C'})
    P(s, 'C2', C, '100nF', 38, 37, nets={'1': 'SW3C', '2': 'GND'})
    W(s, 'R2.2', 'RV2.1'); W(s, (36, 22), 'SW2.2')
    W(s, 'U2.7', (41, 24), (41, 26), 'U2.6'); W(s, (41, 26), (41, 31), 'R4.2')
    W(s, 'RV2.3', (36, 31)); W(s, 'RV2.2', (38.5, 24.5), (38.5, 26), (41, 26)); W(s, (38, 31), 'SW3.2')
    W(s, 'U1.3', (27, 25), (27, 42), (43, 42), (43, 27), 'U2.2')
    P(s, 'R3', R, '1k', 55, 25, 90, nets={'1': 'OUT', '2': 'AUD'})
    out_jack(s, 60, 25, 'AUD')
    supply(s, 4, 40, '+9V', 'pile 9 V')
    return s


def hall_front(s, out_net):
    """Capteur Hall DRV5055 → ampli non inverseur avec décalage réglable (sortie `out_net`)."""
    P(s, 'U1', 'Sensor_Magnetic:DRV5055A2xLPGxQ1', 'DRV5055A2', 10, 20, nets={'1': '+5V', '2': 'GND', '3': 'HALL'})
    P(s, 'C1', C, '100nF', 5, 20, nets={'1': '+5V', '2': 'GND'})
    P(s, 'U2', 'Amplifier_Operational:MCP6002-xP', 'MCP6002', 22, 21, nets={'3': 'HALL', '2': 'FB', '1': out_net})
    P(s, 'U2', 'Amplifier_Operational:MCP6002-xP', 'MCP6002', 28, 33, unit=3, nets={'8': '+5V', '4': 'GND'})
    P(s, 'R2', R, '47k', 22, 25, 90, nets={'1': 'FB', '2': out_net})
    P(s, 'R3', R, '10k', 18, 28.5, nets={'1': 'FB', '2': 'REF'})
    P(s, 'RV1', POT, '10k zéro', 14, 30, nets={'1': '+5V', '3': 'GND', '2': 'REF'})
    W(s, 'U2.2', (18, 22), 'R3.1'); W(s, (18, 25), 'R2.1'); W(s, 'RV1.2', 'R3.2')
    W(s, 'R2.2', (26, 25), (26, 21))


@circuit
def S2_magpot():
    s = Sch('S2_magpot', 'S2 — MagPot : potentiomètre magnétique isolé (Hall → vactrol)', notes=[
        'Gain U2A = 1 + R2/R3 ≈ 5,7 autour de la tension de RV1 : RV1 règle le point où la LED s\'allume.',
        'Pôle N du gant → la LED s\'éclaire → la LDR de U3 descend (≈ 1 MΩ dans le noir, quelques kΩ éclairée).',
        'J1 = les deux bornes de la LDR : à la place d\'un potentiomètre ou entre deux points de bend du circuit hôte.',
        'Isolation galvanique totale entre ce module et l\'hôte. U2B inutilisé : + à la masse, − relié à sa sortie.'])
    hall_front(s, 'AMP')
    P(s, 'Q1', 'Transistor_BJT:2N3904', '2N3904', 32, 21, nets={'2': 'AMP', '3': '+5V', '1': 'EM'})
    P(s, 'R4', R, '220Ω', 33, 25.5, nets={'1': 'EM', '2': 'LEDA'})
    P(s, 'U3', 'Isolator:NSL-32', 'NSL-32 (vactrol)', 40, 29, rv=((-3, -3.2), (-0.5, -3.2)), nets={'1': 'LEDA', '2': 'GND', '4': 'LDR1', '3': 'LDR2'})
    P(s, 'J1', J2P, 'vers circuit hôte', 50, 28, nets={'1': 'LDR1', '2': 'LDR2'})
    W(s, 'U2.1', 'Q1.2'); W(s, 'U3.3', (46, 30), (46, 29), 'J1.2')
    Lb(s, 'AMP', 28, 21, 90)
    supply(s, 4, 36, '+5V', '5 V')
    return s


@circuit
def S3_hall_vco():
    s = Sch('S3_hall_vco', 'S3 — Hall → VCO du CD4046', notes=[
        'Même étage d\'entrée que S2. CV = 0–5 V → VCO du 4046 : fmin fixée par R7, plage par R6 et C5.',
        'Avec R6 = 100k, R7 = 1M, C5 = 10 nF : de quelques dizaines de Hz à ≈ 1 kHz (à mesurer).',
        'Pôle N et pôle S font varier la hauteur dans des sens opposés ; RV1 place le repos au milieu de la plage.',
        'Comparateurs de phase inutilisés : entrées 3 et 14 à la masse, sorties en l\'air.'])
    hall_front(s, 'CV')
    Lb(s, 'CV', 28, 21, 90)
    W(s, 'U2.1', (28, 21))
    P(s, 'U3', '4xxx:4046', 'CD4046', 46, 25, rv=((-7, -7.4), (-4.4, -7.4)), nets={'3': 'GND', '14': 'GND', '6': 'CT1', '7': 'CT2', '11': 'R1', '12': 'R2',
                                                   '5': 'GND', '16': '+5V', '8': 'GND', '4': 'FOUT', '2': 'NC', '13': 'NC',
                                                   '9': 'CV', '1': 'NC', '10': 'NC', '15': 'NC'})
    W(s, 'U3.3', (40, 21), (40, 22), 'U3.14'); PW(s, 'GND', 40, 22)
    P(s, 'C5', C, '10nF', 33, 15, nets={'1': 'CT1', '2': 'CT2'})
    P(s, 'R6', R, '100k', 38, 31, nets={'1': 'R1', '2': 'GND'}, rv=((-3.6, -0.5), (-3.6, 0.5)))
    P(s, 'R7', R, '1M', 33, 32, nets={'1': 'R2', '2': 'GND'}, rv=((-2.6, -0.5), (-2.4, 0.5)))
    P(s, 'R8', R, '1k', 54, 21, 90, nets={'1': 'FOUT', '2': 'AUD'})
    out_jack(s, 59, 21, 'AUD')
    supply(s, 4, 36, '+5V', '5 V')
    return s


def pierce(s, y, inv, buf, L_, Lsym, Lval, Rf, Rs, C1, C2, xnet, extra=None):
    """Oscillateur LC CMOS (Pierce, inductance à la place du quartz) + tampon."""
    i, o = str(inv[1]), str(inv[2])
    bi, bo = str(buf[1]), str(buf[2])
    U = 'U1'
    P(s, U, '4xxx:4069', 'CD4069UB', 14, y, unit=inv[0], nets={i: 'IN' + xnet, o: 'OUT' + xnet})
    P(s, Rf, R, '1M', 14, y - 4, 90, nets={'1': 'IN' + xnet, '2': 'OUT' + xnet})
    P(s, Rs, R, '1k', 21, y, 90, nets={'1': 'OUT' + xnet, '2': 'X' + xnet})
    P(s, L_, Lsym, Lval, 17, y + 4, 90, nets={'1': 'IN' + xnet, '2': 'X' + xnet})
    P(s, C1, C, '2.2nF C0G', 10, y + 6.5, nets={'1': 'IN' + xnet, '2': 'GND'})
    P(s, C2, C, '2.2nF C0G', 24, y + 6.5, nets={'1': 'X' + xnet, '2': 'GND'})
    P(s, U, '4xxx:4069', 'CD4069UB', 33, y, unit=buf[0], nets={bi: 'X' + xnet, bo: 'OSC' + xnet})
    W(s, Rf + '.1', (10, y - 4), C1 + '.1'); W(s, U + '.' + i, (10, y)); W(s, L_ + '.1', (10, y + 4))
    W(s, U + '.' + o, Rs + '.1'); W(s, Rf + '.2', (18, y - 4), (18, y))
    W(s, Rs + '.2', U + '.' + bi); W(s, (24, y), C2 + '.1'); W(s, L_ + '.2', (24, y + 4), (24, y))
    if extra:
        P(s, extra, 'Device:C_Trim', '5–60pF accord', 29, y + 6.5, nets={'1': 'X' + xnet, '2': 'GND'})
        W(s, (29, y), extra + '.1')


@circuit
def S4_bfo():
    s = Sch('S4_bfo', 'S4 — Battement de deux oscillateurs LC (BFO)', notes=[
        'f ≈ 1 / (2π √(L · C/2)) : L = 330 µH et C = 2,2 nF donnent ≈ 260 kHz. CV1 accorde U1C/L2 à quelques Hz de U1A/L1.',
        'U2A (XOR) sort la somme et la différence ; R5/C5 ne gardent que la différence, audible.',
        'Ferrite ou acier près de L1 → f baisse ; cuivre ou alu → f monte ; aimant fort (saturation) → f monte.',
        'Condensateurs C0G (stables en température) et bouton d\'accord accessible : le soleil fait dériver l\'accord.'])
    pierce(s, 20, (1, 1, 2), (2, 3, 4), 'L1', LF, 'antenne ferrite AM ≈ 330µH', 'R1', 'R2', 'C1', 'C2', '1')
    pierce(s, 34, (3, 5, 6), (4, 9, 8), 'L2', L, '330µH (fixe, loin de L1)', 'R3', 'R4', 'C3', 'C4', '2', extra='CV1')
    P(s, 'U1', '4xxx:4069', 'CD4069UB', 46, 42, unit=7, nets={'14': '+5V', '7': 'GND'})
    P(s, 'U2', '4xxx:4070', 'CD4070', 44, 27, unit=1, nets={'1': 'OSC1', '2': 'OSC2', '3': 'MIX'})
    P(s, 'U2', '4xxx:4070', 'CD4070', 52, 42, unit=5, nets={'14': '+5V', '7': 'GND'})
    W(s, 'U1.4', (38.5, 20), (38.5, 26), 'U2.1'); W(s, 'U1.8', (38.5, 34), (38.5, 28), 'U2.2')
    P(s, 'R5', R, '4.7k', 50.5, 27, 90, nets={'1': 'MIX', '2': 'LP'})
    P(s, 'C5', C, '10nF', 54, 28.5, nets={'1': 'LP', '2': 'GND'})
    out_jack(s, 62, 27, 'LP')
    W(s, 'R5.2', 'J1.1')
    supply(s, 30, 47, '+5V', '5 V')
    return s


@circuit
def S5_captrice_fm():
    s = Sch('S5_captrice_fm', 'S5 — Bobine captrice + transfo élévateur → FM d\'un oscillateur 40106', notes=[
        'L1 : bobine téléphonique à ventouse ou bobine à air basse impédance. T1 (8 Ω : 1 kΩ, transfo de sortie de',
        'radio à transistors, monté à l\'envers) élève la tension d\'environ ×11 sans bruit avant le préampli.',
        'Gain U1A = 1 + R2/R3 ≈ 100. Le signal capté module la charge de C4 via R4 : FM, et verrouillage quand',
        'le gant émetteur (G4) est proche de la fréquence de U2A. RV1 : hauteur de repos.'])
    P(s, 'L1', LI, 'bobine captrice', 6, 22, nets={'1': 'P1', '2': 'P2'})
    P(s, 'T1', 'Device:Transformer_1P_1S', '8Ω : 1kΩ', 14, 22, nets={'1': 'P1', '2': 'P2', '4': 'SEC', '3': 'GND'})
    P(s, 'C1', C, '1µF', 21.5, 20, 90, nets={'1': 'SEC', '2': 'INP'})
    P(s, 'R1', R, '100k', 24, 16.5, nets={'1': 'VB', '2': 'INP'})
    P(s, 'U1', 'Amplifier_Operational:MCP6002-xP', 'MCP6002', 29, 21, nets={'3': 'INP', '2': 'FB', '1': 'PRE'})
    P(s, 'U1', 'Amplifier_Operational:MCP6002-xP', 'MCP6002', 34, 35, unit=3, nets={'8': '+5V', '4': 'GND'})
    P(s, 'R2', R, '100k', 29, 25, 90, nets={'1': 'FB', '2': 'PRE'})
    P(s, 'R3', R, '1k', 25, 28.5, nets={'1': 'FB', '2': 'RG'})
    P(s, 'C3', CP, '10µF', 25, 33, nets={'1': 'RG', '2': 'GND'})
    W(s, 'C1.2', 'U1.3'); W(s, 'R1.2', (24, 20))
    W(s, 'U1.2', (25, 22), 'R3.1'); W(s, (25, 25), 'R2.1')
    W(s, 'U1.1', 'C2.1'); W(s, 'R2.2', (33, 25), (33, 21))
    P(s, 'C2', C, '100nF', 36, 21, 90, nets={'1': 'PRE', '2': 'MOD'})
    P(s, 'R4', R, '100k', 41, 21, 90, nets={'1': 'MOD', '2': 'TIM'})
    P(s, 'U2', '4xxx:40106', 'CD40106', 50, 24, unit=1, nets={'1': 'TIM', '2': 'OSC'})
    P(s, 'U2', '4xxx:40106', 'CD40106', 52, 36, unit=7, nets={'14': '+5V', '7': 'GND'})
    P(s, 'C4', C, '10nF', 45, 27.5, nets={'1': 'TIM', '2': 'GND'})
    P(s, 'R5', R, '10k', 47, 18, 90, nets={'1': 'TIM', '2': 'RF'})
    P(s, 'RV1', POT, '100k', 52, 18, 90, nets={'1': 'RF', '3': 'OSC', '2': 'OSC'})
    W(s, 'R4.2', (45, 21), (45, 24), 'U2.1'); W(s, (45, 24), 'C4.1'); W(s, 'R5.1', (45, 18), (45, 21))
    W(s, 'U2.2', 'R6.1'); W(s, (55, 24), (55, 18), 'RV1.3'); W(s, 'RV1.2', (52, 15.5), (53.5, 15.5), 'RV1.3')
    P(s, 'R6', R, '1k', 58, 24, 90, nets={'1': 'OSC', '2': 'AUD'})
    out_jack(s, 63, 24, 'AUD')
    P(s, 'R7', R, '100k', 8, 32, nets={'1': '+5V', '2': 'VB'})
    P(s, 'R8', R, '100k', 8, 37, nets={'1': 'VB', '2': 'GND'})
    P(s, 'C5', CP, '10µF', 12, 37, nets={'1': 'VB', '2': 'GND'})
    W(s, 'R7.2', 'R8.1'); W(s, (8, 34.5), (12, 34.5), 'C5.1'); Lb(s, 'VB', 12, 34.5)
    supply(s, 18, 44, '+5V', '5 V')
    return s


def osc40106(s, y, unit, i, o, node, out, rf, rv, c, cval='10nF', inject=None):
    """Oscillateur à trigger de Schmitt : nœud de timing `node` à x = 12."""
    P(s, 'U1', '4xxx:40106', 'CD40106', 17, y, unit=unit, nets={i: node, o: out})
    P(s, rf, R, '10k', 15, y - 4, 90, nets={'1': node, '2': rf + 'X'})
    P(s, rv, POT, '500k', 20, y - 4, 90, nets={'1': rf + 'X', '3': out, '2': out})
    P(s, c, C, cval, 12, y + 4.5, nets={'1': node, '2': 'GND'})
    W(s, rf + '.1', (12, y - 4), c + '.1'); W(s, 'U1.' + i, (12, y))
    W(s, 'U1.' + o, (23, y), (23, y - 4), rv + '.3'); W(s, rv + '.2', (20, y - 6), (21.5, y - 6), rv + '.3')
    if inject:
        cl, cr, cc = inject
        P(s, cc, C, '47nF', 9, y, 90, nets={'1': cc + 'X', '2': node})
        P(s, cr, R, '4.7k', 5, y, 90, nets={'1': cl + 'X', '2': cc + 'X'})
        P(s, cl, L, '10mH (bobine)', 2, y + 2.5, nets={'1': cl + 'X', '2': 'GND'})
        W(s, cc + '.2', (12, y))


@circuit
def S6_bobines_noeuds():
    s = Sch('S6_bobines_noeuds', 'S6 — Points de bend magnétiques : bobines sur les nœuds de timing', notes=[
        'Hôte : deux oscillateurs 40106 mélangés par un XOR (U2A). Chaque cellule L–R–C est un',
        '« point de bend magnétique » : le gant émetteur (G4/B2) injecte son signal dans le nœud de timing.',
        'L1/L2 : selfs 10 mH axiales, ou 50 à 200 spires à air. R2/R4 limitent le courant, C2/C4 bloquent le continu.',
        'Même cellule soudable sur n\'importe quel jouet : condensateurs de timing, entrées CMOS, horloge.'])
    osc40106(s, 20, 1, '1', '2', 'TA', 'OSCA', 'R1', 'RV1', 'C1', inject=('L1', 'R2', 'C2'))
    osc40106(s, 36, 2, '3', '4', 'TB', 'OSCB', 'R3', 'RV2', 'C3', inject=('L2', 'R4', 'C4'))
    Lb(s, 'OSCA', 23, 20, 0)
    P(s, 'U2', '4xxx:4070', 'CD4070', 34, 28, unit=1, nets={'1': 'OSCA', '2': 'OSCB', '3': 'MIX'})
    W(s, (23, 36), (29, 36), (29, 29), 'U2.2'); Lb(s, 'OSCB', 23, 36, 0)
    P(s, 'U1', '4xxx:40106', 'CD40106', 44, 40, unit=7, nets={'14': '+5V', '7': 'GND'})
    P(s, 'U2', '4xxx:4070', 'CD4070', 50, 40, unit=5, nets={'14': '+5V', '7': 'GND'})
    P(s, 'R7', R, '1k', 40.5, 28, 90, nets={'1': 'MIX', '2': 'AUD'})
    out_jack(s, 46, 28, 'AUD')
    supply(s, 4, 46, '+5V', '5 V')
    return s


@circuit
def S7_absorption():
    s = Sch('S7_absorption', 'S7 — Absorption (grid-dip) : oscillateur de Clapp + détecteur → CV', notes=[
        'L1 = 50 µH (bobine de détection, ≈ 25 spires sur Ø 3 cm). C1 = C2 = 47 nF, C3 = 470 nF → f ≈ 150 kHz.',
        'RV1 : régler juste au-dessus du seuil d\'oscillation (sensibilité maximale à l\'absorption).',
        'Un résonateur G3 accordé sur f approché de L1 prend de l\'énergie : l\'amplitude chute, DET et CV baissent.',
        'D1/D2 : doubleur-détecteur. CV (0–5 V) va au VCO de S3 (à la place du Hall) ou à un VCA.',
        'Plusieurs canaux : un oscillateur par fréquence (≥ ±20 % d\'écart) et un résonateur accordé par doigt.'])
    P(s, 'Q1', 'Transistor_BJT:BC547', 'BC547', 20, 22, nets={'2': 'B', '1': '+5V', '3': 'E'})
    P(s, 'R1', R, '47k', 15, 17, nets={'1': '+5V', '2': 'B'})
    P(s, 'R2', R, '47k', 15, 32, nets={'1': 'B', '2': 'GND'})
    P(s, 'C3', C, '470nF', 11.5, 20, 90, nets={'1': 'TK', '2': 'B'})
    P(s, 'L1', L, '50µH détection', 8, 23, nets={'1': 'TK', '2': 'GND'})
    P(s, 'C1', C, '47nF', 18, 27, 90, nets={'1': 'B', '2': 'E'})
    P(s, 'C2', C, '47nF', 21, 31, nets={'1': 'E', '2': 'GND'})
    P(s, 'R3', R, '1k', 25, 28.5, nets={'1': 'E', '2': 'RE'})
    P(s, 'RV1', POT, '2k seuil', 25, 32.5, nets={'1': 'RE', '3': 'GND', '2': 'GND'}, rv=((2.6, -0.6), (2.6, 0.6)))
    W(s, 'RV1.2', (27, 32.5), (27, 34), 'RV1.3'); W(s, 'RV1.3', (25, 35)); PW(s, 'GND', 25, 35)
    W(s, 'R1.2', 'R2.1'); W(s, 'Q1.2', (15, 22)); W(s, 'C3.2', (15, 20)); W(s, 'C1.1', (15, 27))
    W(s, 'Q1.3', 'C2.1'); W(s, 'C1.2', (21, 27)); W(s, (21, 26), (25, 26), 'R3.1'); W(s, (25, 26), 'C4.1')
    P(s, 'C4', C, '100nF', 28.5, 26, 90, nets={'1': 'E', '2': 'A'})
    P(s, 'D1', D4148, '1N4148', 33, 26, 180, nets={'2': 'A', '1': 'DET'})
    P(s, 'D2', D4148, '1N4148', 31, 30.5, 270, nets={'1': 'A', '2': 'GND'})
    P(s, 'C5', C, '100nF', 36, 28.5, nets={'1': 'DET', '2': 'GND'})
    P(s, 'R5', R, '100k', 39, 28.5, nets={'1': 'DET', '2': 'GND'})
    W(s, 'C4.2', 'D1.2'); W(s, (31, 26), 'D2.1')
    P(s, 'U1', 'Amplifier_Operational:MCP6002-xP', 'MCP6002', 46, 27, nets={'3': 'DET', '2': 'FB', '1': 'CV'})
    P(s, 'U1', 'Amplifier_Operational:MCP6002-xP', 'MCP6002', 52, 38, unit=3, nets={'8': '+5V', '4': 'GND'})
    P(s, 'R6', R, '22k', 46, 31, 90, nets={'1': 'FB', '2': 'CV'})
    P(s, 'R7', R, '10k', 42, 34.5, nets={'1': 'FB', '2': 'GND'})
    W(s, 'D1.1', 'U1.3'); W(s, (36, 26), 'C5.1'); W(s, (39, 26), 'R5.1')
    W(s, 'U1.2', (42, 28), 'R7.1'); W(s, (42, 31), 'R6.1'); W(s, 'R6.2', (50, 31), (50, 27))
    P(s, 'J1', J2P, 'CV vers S3 / VCA', 56, 27, nets={'1': 'CV', '2': 'GND'})
    W(s, 'U1.1', 'J1.1')
    supply(s, 4, 36, '+5V', '5 V')
    return s


@circuit
def S8_larsen():
    s = Sch('S8_larsen', 'S8 — Larsen magnétique : le gant referme la boucle', notes=[
        'L1 (captrice) et L2 (émettrice, alimentée par la sortie de l\'ampli) sont montées à angle droit ou éloignées :',
        'aucun couplage au repos. Une barre de ferrite ou une plaque d\'acier (G2) referme le flux → larsen.',
        'Gain U1A ≈ 100. D1/D2 + RV1 plafonnent le niveau entrant dans U2 : limiteur obligatoire en public.',
        'R5 limite le courant dans L2 ; L1 est polarisée à VB à travers sa propre bobine.'])
    P(s, 'L1', LI, 'captrice', 6, 22, nets={'1': 'INP', '2': 'VB'})
    P(s, 'U1', 'Amplifier_Operational:LM358', 'LM358', 14, 21, nets={'3': 'INP', '2': 'FB', '1': 'PRE'})
    P(s, 'U1', 'Amplifier_Operational:LM358', 'LM358', 22, 36, unit=3, nets={'8': '+9V', '4': 'GND'})
    P(s, 'R1', R, '100k', 14, 25, 90, nets={'1': 'FB', '2': 'PRE'})
    P(s, 'R2', R, '1k', 10, 28.5, nets={'1': 'FB', '2': 'RG'})
    P(s, 'C1', CP, '10µF', 10, 33, nets={'1': 'RG', '2': 'GND'})
    W(s, 'U1.2', (10, 22), 'R2.1'); W(s, (10, 25), 'R1.1'); W(s, 'R1.2', (18, 25), (18, 21))
    W(s, 'U1.1', 'C2.1')
    P(s, 'C2', C, '1µF', 21, 21, 90, nets={'1': 'PRE', '2': 'VOLA'})
    P(s, 'RV1', POT, '10k', 25, 22.5, nets={'1': 'VOLA', '3': 'GND', '2': 'VOLW'})
    W(s, 'C2.2', 'RV1.1')
    P(s, 'R3', R, '10k', 29, 22.5, 90, nets={'1': 'VOLW', '2': 'CLIP'})
    P(s, 'D1', D4148, '1N4148', 32, 24, 90, nets={'2': 'CLIP', '1': 'GND'})
    P(s, 'D2', D4148, '1N4148', 34.5, 24, 270, nets={'1': 'CLIP', '2': 'GND'})
    P(s, 'U2', 'Amplifier_Audio:LM386', 'LM386', 44, 23.5, nets={'3': 'CLIP', '2': 'GND', '6': '+9V', '4': 'GND',
                                                              '7': 'NC', '1': 'NC', '8': 'NC', '5': 'OUT'})
    W(s, 'R3.2', 'U2.3')
    P(s, 'C3', CP, '220µF', 50.5, 23.5, 90, nets={'1': 'OUT', '2': 'HP'})
    P(s, 'R4', R, '10Ω', 48, 27.5, nets={'1': 'OUT', '2': 'ZOB'})
    P(s, 'C4', C, '47nF', 48, 32, nets={'1': 'ZOB', '2': 'GND'})
    W(s, 'U2.5', 'C3.1'); W(s, (48, 23.5), 'R4.1')
    P(s, 'LS1', 'Device:Speaker', 'HP 8 Ω', 60, 23.5, nets={'1': 'HP', '2': 'GND'})
    P(s, 'R5', R, '10Ω 1W', 54, 27, nets={'1': 'HP', '2': 'L2A'})
    P(s, 'L2', LF, 'émettrice', 54, 32, nets={'1': 'L2A', '2': 'GND'})
    W(s, 'C3.2', 'LS1.1'); W(s, (54, 23.5), 'R5.1')
    P(s, 'R6', R, '10k', 30, 34, nets={'1': '+9V', '2': 'VB'})
    P(s, 'R7', R, '10k', 30, 39, nets={'1': 'VB', '2': 'GND'})
    P(s, 'C5', CP, '47µF', 34, 39, nets={'1': 'VB', '2': 'GND'})
    W(s, 'R6.2', 'R7.1'); W(s, (30, 36.5), (34, 36.5), 'C5.1'); Lb(s, 'VB', 34, 36.5)
    supply(s, 4, 44, '+9V', 'pile 9 V')
    return s


@circuit
def S10_numerique():
    s = Sch('S10_numerique', 'S10 — Magnétomètre 3 axes → XIAO ESP32-C3 → synthèse', notes=[
        'Module magnétomètre I²C (LIS3MDL ou MLX90393 sur carte) : position 3D d\'un aimant (G1, ou baguette B2).',
        'Calibrer le champ terrestre (≈ 50 µT) au démarrage. Synthèse logicielle (Mozzi) en PWM sur D2,',
        'filtrée par deux cellules RC (≈ 16 kHz) avant l\'ampli S0. Les cartes ont déjà leurs résistances de tirage I²C.',
        'Sert aussi d\'instrument de mesure : enregistrer le champ vu par chaque circuit pour comparer les portées.'])
    P(s, 'J1', 'Connector_Generic:Conn_01x07', 'XIAO gauche D0…D6', 14, 24,
      nets={'1': 'NC', '2': 'NC', '3': 'PWM', '4': 'NC', '5': 'SDA', '6': 'SCL', '7': 'NC'})
    P(s, 'J2', 'Connector_Generic:Conn_01x07', 'XIAO droite 5V GND 3V3 D10…D7', 34, 24, 180,
      nets={'7': 'NC', '6': 'GND', '5': '+3V3', '4': 'NC', '3': 'NC', '2': 'NC', '1': 'NC'})
    W(s, 'J2.5', (37, 23), (37, 19)); PW(s, '+3V3', 37, 19)
    W(s, 'J2.6', (39, 22), (39, 25)); PW(s, 'GND', 39, 25)
    P(s, 'J3', 'Connector_Generic:Conn_01x04', 'module magnétomètre', 52, 25, 0,
      nets={'1': '+3V3', '2': 'SCL', '3': 'SDA', '4': 'GND'})
    P(s, 'R1', R, '1k', 12, 32, 90, nets={'1': 'PWM', '2': 'F1'})
    P(s, 'C1', C, '10nF', 14.5, 34, nets={'1': 'F1', '2': 'GND'})
    P(s, 'R2', R, '1k', 18, 32, 90, nets={'1': 'F1', '2': 'F2'})
    P(s, 'C2', C, '10nF', 20.5, 34, nets={'1': 'F2', '2': 'GND'})
    P(s, 'C3', C, '1µF', 24, 32, 90, nets={'1': 'F2', '2': 'AUD'})
    W(s, 'R1.2', 'R2.1'); W(s, 'R2.2', 'C3.1')
    W(s, (14.5, 32), 'C1.1'); W(s, (20.5, 32), 'C2.1')
    Lb(s, 'F1', 15.5, 32, 90); Lb(s, 'F2', 21.5, 32, 90)
    out_jack(s, 30, 32, 'AUD', ref='J4')
    return s


@circuit
def S11_hartley_transfo():
    s = Sch('S11_hartley_transfo', 'S11 — Oscillateur Hartley sur petit transfo de sortie audio', notes=[
        'T1 : transfo de sortie de radio à transistors, primaire 1 kΩ à point milieu, secondaire 8 Ω → HP direct.',
        'Le primaire entier et C1 forment le circuit accordé ; C2 renvoie l\'extrémité opposée au collecteur sur la base.',
        'f ≈ 1 / (2π √(Lp · C1)) : avec Lp ≈ 1–3 H et C1 = 100 nF, quelques centaines de Hz (à mesurer).',
        'Un aimant contre le noyau feuilleté le sature : Lp baisse, la hauteur monte. Le noyau capte aussi le gant G4.',
        'Point de départ du montage, à valider sur plaque d\'essai (R1, C2 selon le transfo).'])
    P(s, 'T1', 'Device:Transformer_SP_1S', '1kΩ PM : 8Ω', 25, 22, nets={'1': 'COL', '2': '+9V', '3': 'FB', '5': 'S2', '4': 'S1'})
    P(s, 'Q1', 'Transistor_BJT:2N3904', '2N3904', 14, 27, nets={'2': 'B', '3': 'COL', '1': 'EM'})
    P(s, 'C1', C, '100nF', 18, 22, nets={'1': 'COL', '2': 'FB'})
    P(s, 'R1', R, '100k', 10, 22, nets={'1': '+9V', '2': 'B'})
    P(s, 'C2', C, '100nF', 10, 31, nets={'1': 'B', '2': 'FB'})
    P(s, 'R2', R, '470Ω', 15, 32.5, nets={'1': 'EM', '2': 'GND'})
    P(s, 'LS1', 'Device:Speaker', 'HP 8 Ω', 34, 21, nets={'1': 'S2', '2': 'S1'})
    W(s, 'Q1.3', (15, 20), 'T1.1'); W(s, 'C1.1', (18, 20))
    W(s, 'T1.3', (18, 24), 'C1.2')
    W(s, 'T1.2', (20, 22), (20, 17)); PW(s, '+9V', 20, 17)
    W(s, 'R1.2', (10, 27), 'Q1.2'); W(s, (10, 27), 'C2.1')
    W(s, 'T1.5', (31, 20), (31, 21), 'LS1.1'); W(s, 'T1.4', (31, 24), (31, 22), 'LS1.2')
    Lb(s, 'FB', 18, 24, 270)
    supply(s, 20, 38, '+9V', 'pile 9 V')
    return s


@circuit
def S12_wah_magnetique():
    s = Sch('S12_wah_magnetique', 'S12 — Wah magnétique : circuit LC parallèle à inductance de wah', notes=[
        'U1A (40106) produit un signal carré riche en harmoniques. R1 l\'injecte dans le circuit accordé L1 ∥ C2 :',
        'seules les harmoniques proches de f = 1 / (2π √(L1 · C2)) ≈ 710 Hz (500 mH, 100 nF) ressortent.',
        'Un aimant près du noyau de L1 fait baisser L1 → la résonance monte : balayage de wah sans pédale.',
        'Le pied du circuit accordé est à VB (et non à la masse) : aucun courant continu dans L1, sortie centrée.',
        'L1 : inductance de wah 500 mH (pot ferrite) ; une self à tambour ouverte (100 mH) réagit plus fort.'])
    osc40106(s, 20, 1, '1', '2', 'T', 'SQ', 'R2', 'RV1', 'C1', cval='47nF')
    P(s, 'R1', R, '10k', 27, 20, 90, nets={'1': 'SQ', '2': 'TANK'})
    P(s, 'L1', LF, '500mH wah', 31, 23.5, nets={'1': 'TANK', '2': 'VB'}, rv=((-2.8, -0.5), (-5.2, 0.5)))
    P(s, 'C2', C, '100nF', 34, 23.5, nets={'1': 'TANK', '2': 'VB'})
    W(s, 'U1.2', 'R1.1'); W(s, 'R1.2', 'U2.3'); W(s, (31, 20), 'L1.1'); W(s, (34, 20), 'C2.1')
    W(s, 'L1.2', (31, 26), (34, 26), 'C2.2'); Lb(s, 'VB', 31, 26, 180)
    Lb(s, 'SQ', 23, 20, 90)
    P(s, 'U2', 'Amplifier_Operational:MCP6002-xP', 'MCP6002', 40, 21, nets={'3': 'TANK', '2': 'BUF', '1': 'BUF'})
    P(s, 'U2', 'Amplifier_Operational:MCP6002-xP', 'MCP6002', 42, 34, unit=3, nets={'8': '+5V', '4': 'GND'})
    P(s, 'U1', '4xxx:40106', 'CD40106', 48, 34, unit=7, nets={'14': '+5V', '7': 'GND'})
    W(s, 'U2.2', (36, 22), (36, 24), (44, 24), (44, 21)); W(s, 'U2.1', 'C3.1')
    P(s, 'C3', C, '1µF', 47, 21, 90, nets={'1': 'BUF', '2': 'AUD'})
    out_jack(s, 52, 21, 'AUD')
    P(s, 'R3', R, '10k', 8, 34, nets={'1': '+5V', '2': 'VB'})
    P(s, 'R4', R, '10k', 8, 39, nets={'1': 'VB', '2': 'GND'})
    P(s, 'C4', CP, '47µF', 12, 39, nets={'1': 'VB', '2': 'GND'})
    W(s, 'R3.2', 'R4.1'); W(s, (8, 36.5), (12, 36.5), 'C4.1'); Lb(s, 'VB', 12, 36.5)
    supply(s, 18, 40, '+5V', '5 V')
    return s


@circuit
def S13_ring_transfos():
    s = Sch('S13_ring_transfos', 'S13 — Modulateur en anneau à deux transformateurs', notes=[
        'T1, T2 : transfos audio 600 Ω : 600 Ω à point milieu (ou 1 kΩ PM : 8 Ω). D1–D4 : Schottky BAT43 (seuil bas).',
        'Porteuse : oscillateur U1A injecté entre les points milieux. Signal modulant sur J1 : préampli de la bobine',
        'captrice (S5, sortie PRE) → on entend le signal du gant émetteur (G4/B2) multiplié par la porteuse.',
        'Anneau : A1 → B1 → A2 → B2 → A1 (anode → cathode). D2 et D4 se croisent dans l\'anneau, d\'où les étiquettes.'])
    P(s, 'J1', J2P, 'signal modulant', 5, 21, 180, nets={'2': 'MOD', '1': 'GND'})
    P(s, 'T1', 'Device:Transformer_1P_SS', 'T1 PM', 15, 22, nets={'1': 'MOD', '2': 'GND', '5': 'A1', '4': 'CAR', '3': 'A2'})
    P(s, 'T2', 'Device:Transformer_1P_SS', 'T2 PM', 37, 22, 180, nets={'3': 'B1', '4': 'GND', '5': 'B2', '2': 'OUTM', '1': 'GND'})
    P(s, 'D1', 'Diode:BAT43', 'BAT43', 26, 20, 180, nets={'2': 'A1', '1': 'B1'})
    P(s, 'D3', 'Diode:BAT43', 'BAT43', 26, 24, 180, nets={'2': 'A2', '1': 'B2'})
    P(s, 'D2', 'Diode:BAT43', 'BAT43', 24, 30, 180, nets={'2': 'B1', '1': 'A2'})
    P(s, 'D4', 'Diode:BAT43', 'BAT43', 24, 34, 180, nets={'2': 'B2', '1': 'A1'})
    W(s, 'J1.2', 'T1.1'); W(s, 'T1.5', 'D1.2'); W(s, 'D1.1', 'T2.3'); W(s, 'T1.3', 'D3.2'); W(s, 'D3.1', 'T2.5')
    Lb(s, 'A1', 21, 20, 90); Lb(s, 'B1', 31, 20, 90); Lb(s, 'A2', 21, 24, 270); Lb(s, 'B2', 31, 24, 270)
    W(s, 'T2.4', (31.5, 22)); PW(s, 'GND', 31.5, 22)
    P(s, 'J2', J2P, 'vers S0', 46, 20, 0, nets={'1': 'OUTM', '2': 'GND'})
    W(s, 'T2.2', 'J2.1')
    P(s, 'U1', '4xxx:40106', 'CD40106', 11, 40, unit=1, nets={'1': 'TC', '2': 'SQC'})
    P(s, 'U1', '4xxx:40106', 'CD40106', 40, 40, unit=7, nets={'14': '+5V', '7': 'GND'})
    P(s, 'R1', R, '47k', 11, 35, 90, nets={'1': 'TC', '2': 'SQC'})
    P(s, 'C1', C, '10nF', 6, 44.5, nets={'1': 'TC', '2': 'GND'})
    W(s, 'R1.1', (6, 35), 'C1.1'); W(s, 'U1.1', (6, 40)); W(s, 'U1.2', (15, 40), (15, 35), 'R1.2')
    P(s, 'C2', CP, '10µF', 19, 40, 90, nets={'1': 'SQC', '2': 'CR'})
    P(s, 'R2', R, '220Ω', 24, 40, 90, nets={'1': 'CR', '2': 'CAR'})
    W(s, 'U1.2', 'C2.1')
    supply(s, 18, 48, '+5V', '5 V')
    return s


@circuit
def G3_resonateur():
    s = Sch('G3_resonateur', 'G3 — Résonateur passif de doigt (avec pression Velostat)', notes=[
        'f = 1 / (2π √(L1 · C1)) : 50 µH (≈ 25 spires sur Ø 2–3 cm) et 22 nF C0G → ≈ 152 kHz, accordé sur S7.',
        'Un doigt = une fréquence : changer C1 (10 nF → 225 kHz, 47 nF → 104 kHz).',
        'R1 (Velostat entre deux électrodes) amortit le circuit quand on appuie : la pression dose l\'absorption.',
        'Aucune pile ; tout se coud dans le gant et se lave une fois les pièces enrobées.'])
    P(s, 'L1', L, '50µH', 10, 20, nets={'1': 'T', '2': 'B'})
    P(s, 'C1', C, '22nF C0G', 15, 20, nets={'1': 'T', '2': 'B'})
    P(s, 'R1', 'Device:R_Variable', 'Velostat', 21, 20, nets={'1': 'T', '2': 'B'})
    W(s, 'L1.1', (10, 17.5), (21, 17.5), 'R1.1'); W(s, 'C1.1', (15, 17.5))
    W(s, 'L1.2', (10, 22.5), (21, 22.5), 'R1.2'); W(s, 'C1.2', (15, 22.5))
    return s


@circuit
def G4_gant_emetteur():
    s = Sch('G4_gant_emetteur', 'G4 — Gant émetteur : NE555 + MOSFET → bobine de paume', notes=[
        'f ≈ 1,44 / ((R1 + 2·RF) · C1) : RF = capteur de flexion (≈ 25–100 kΩ) → ≈ 1,2 kHz à 300 Hz selon le doigt plié.',
        'L1 : ≈ 200 spires de fil émaillé 0,2 mm sur Ø 5 cm, cousue dans la paume. D1 : roue libre (Schottky).',
        'R4 limite le courant à ≈ 9 V / (22 Ω + R bobine). Le champ émis porte le son : à capter par S5, S6, S13.',
        'Interrupteur SW1 obligatoire (pile 9 V dans un boîtier de poignet).'])
    P(s, 'J1', J2P, 'pile 9 V', 6, 20, 180, nets={'2': 'VB9', '1': 'GND'})
    P(s, 'SW1', 'Switch:SW_SPST', 'marche', 12, 19, nets={'1': 'VB9', '2': '+9V'})
    P(s, 'U1', 'Timer:NE555P', 'NE555', 26, 25, nets={'4': '+9V', '7': 'DIS', '6': 'TH', '2': 'TH', '5': 'NC',
                                                      '8': '+9V', '1': 'GND', '3': 'OUT'})
    P(s, 'R1', R, '1k', 18, 21.5, nets={'1': '+9V', '2': 'DIS'})
    P(s, 'RF', 'Device:R_Variable', 'flexion', 18, 27, nets={'1': 'DIS', '2': 'TH'})
    P(s, 'C1', C, '22nF', 21, 32.5, nets={'1': 'TH', '2': 'GND'})
    W(s, 'R1.2', 'RF.1'); W(s, 'U1.7', (18, 24))
    W(s, 'U1.6', (21, 26), (21, 27), 'U1.2'); W(s, 'RF.2', (18, 30), (21, 30), (21, 27)); W(s, (21, 30), 'C1.1')
    P(s, 'R2', R, '100Ω', 33, 25, 90, nets={'1': 'OUT', '2': 'G'})
    P(s, 'Q1', 'Transistor_FET:2N7000', '2N7000', 39, 25, nets={'2': 'G', '3': 'DRN', '1': 'GND'})
    P(s, 'R3', R, '100k', 36, 28, nets={'1': 'G', '2': 'GND'})
    W(s, 'R2.2', 'Q1.2'); W(s, (36, 25), 'R3.1')
    P(s, 'L1', LI, 'bobine de paume', 40, 19.5, nets={'1': 'TOP', '2': 'DRN'}, rv=((-3, -0.5), (-7, 0.5)))
    P(s, 'D1', 'Diode:1N5817', '1N5817', 43, 19.5, 270, nets={'1': 'TOP', '2': 'DRN'})
    P(s, 'R4', R, '22Ω', 40, 14.5, nets={'1': '+9V', '2': 'TOP'})
    W(s, 'Q1.3', 'L1.2'); W(s, (40, 22), (43, 22), 'D1.2')
    W(s, 'R4.2', 'L1.1'); W(s, (40, 17), (43, 17), 'D1.1')
    P(s, 'C2', CP, '100µF', 8, 29, nets={'1': '+9V', '2': 'GND'})
    return s


@circuit
def B2_baguette():
    s = Sch('B2_baguette', 'B2 — Baguette multi-mode : électroaimant piloté, sélecteur rotatif 2 × 6', notes=[
        'SW1 pôle A choisit ce qui est branché sur l\'électroaimant L1 ; pôle B indique la position à la XIAO (MODE, ADC).',
        'Pos. 1 AIMANT : courant continu, sens et force par PWM (N/S) → S1 S2 S3 S10.   Pos. 2 ÉMETTEUR : audio → S5 S6 S8 S13.',
        'Pos. 3 IMPULSIONS : rafales → S9 (dynamo).   Pos. 4 / 5 RÉSONATEUR f1 / f2 : L1 + C3 ou C4, pont en veille → S7.',
        'Pos. 6 FERRITE : bobine en l\'air, le noyau seul agit → S4 S8.  En positions 4–6, nSLEEP bas : sorties du pont en haute impédance.',
        'L1 : ≈ 300 spires 0,3 mm sur barreau ferrite Ø 10 mm, R ≥ 8 Ω (avec R1) pour limiter le courant sur LiPo.',
        'IMU : inclinaison et vitesse du geste → intensité, hauteur ; BTN : déclencher. Résistances de MODE : 0 / 2,2k / 4,7k / 10k / 22k / 47k.'])
    P(s, 'J1', 'Connector_Generic:Conn_01x07', 'XIAO D0…D6', 18, 25,
      nets={'1': 'MODE', '2': 'BTN', '3': 'NC', '4': 'NC', '5': 'SDA', '6': 'SCL', '7': 'NC'})
    P(s, 'J2', 'Connector_Generic:Conn_01x07', 'XIAO 5V…D7', 38, 25, 180,
      nets={'7': 'NC', '6': 'GND', '5': '+3V3', '4': 'SLEEP', '3': 'IN1', '2': 'IN2', '1': 'NC'})
    W(s, 'J2.5', (41, 24), (41, 20)); PW(s, '+3V3', 41, 20)
    W(s, 'J2.6', (43, 23), (43, 20.5), (45, 20.5)); PW(s, 'GND', 45, 20.5)
    P(s, 'R11', R, '10k', 12, 20, nets={'1': '+3V3', '2': 'MODE'}, rv=((-3.4, -0.5), (-2.8, 0.5)))
    W(s, 'R11.2', (12, 22), 'J1.1'); Lb(s, 'MODE', 14, 22, 90)
    P(s, 'SW2', 'Switch:SW_Push', 'BTN', 9, 24, nets={'2': 'BTN', '1': 'GND'})
    W(s, 'SW2.2', (14, 24), (14, 23), 'J1.2')
    P(s, 'J3', J2P, 'LiPo → BAT+/BAT− XIAO', 6, 34, 180, nets={'2': '+BATT', '1': 'GND'})
    P(s, 'J4', 'Connector_Generic:Conn_01x04', 'module IMU (LSM6DS3)', 24, 38, 0,
      nets={'1': '+3V3', '2': 'SCL', '3': 'SDA', '4': 'GND'})
    P(s, 'U1', 'Driver_Motor:DRV8837C', 'DRV8837', 56, 28, rv=((-9, -5.2), (-6.4, -5.2)), nets={'6': 'IN1', '5': 'IN2', '7': 'SLEEP', '8': '+3V3',
                                                               '1': '+BATT', '4': 'GND', '9': 'GND', '2': 'O1', '3': 'COILB'})
    P(s, 'C1', CP, '10µF', 62, 19, nets={'1': '+BATT', '2': 'GND'})
    W(s, 'U1.1', (56, 17.5), 'C1.1'); PW(s, '+BATT', 59, 17.5)
    P(s, 'R1', R, '4.7Ω 1W', 64, 26, 90, nets={'1': 'O1', '2': 'DRV'}, rv=((-3.2, -1.4), (-1.6, -1.4)))
    P(s, 'L1', LF, 'électroaimant', 72, 22, 90, nets={'1': 'COILB', '2': 'COILA'})
    W(s, 'L1.2', (75, 22), (75, 25), 'SW1.13')
    P(s, 'SW1', 'Switch:SW_Rotary_2x6', 'sélecteur de mode', 82, 28, rv=((-6, -5.6), (-3.4, -5.6)),
      nets={'13': 'COILA', '14': 'MODE', '1': 'DRV', '2': 'DRV', '3': 'DRV', '4': 'F1', '5': 'F2', '6': 'NC',
            '7': 'GND', '8': 'K8', '9': 'K9', '10': 'K10', '11': 'K11', '12': 'K12'})
    W(s, 'SW1.1', (89, 22), (89, 24), 'SW1.3'); W(s, 'SW1.2', (89, 23)); Lb(s, 'DRV', 89, 22, 0)
    for k, (ref, val) in enumerate([('R5', '2.2k'), ('R6', '4.7k'), ('R7', '10k'), ('R8', '22k'), ('R9', '47k')]):
        y = 30 + k
        P(s, ref, R, val, 91, y, 90, nets={'1': f'K{8 + k}', '2': 'GND'}, rv=((4.2, 0.4), (6.2, 0.4)))
        W(s, ref + '.2', (94, y))
    W(s, 'SW1.7', (94, 29), (94, 35), net='GND'); PW(s, 'GND', 94, 35)
    P(s, 'C3', C, 'f1', 76, 39, nets={'1': 'F1', '2': 'COILB'})
    P(s, 'C4', C, 'f2', 80, 39, nets={'1': 'F2', '2': 'COILB'})
    return s


def main(names):
    bad = 0
    for n, f in CIRCUITS.items():
        if names and n not in names:
            continue
        errs = f().build(OUT)
        print(('OK  ' if not errs else 'ERR ') + n)
        for e in errs:
            print('    ' + e); bad += 1
        subprocess.run(['rsvg-convert', '-b', 'white', '-z', '3', '-o', os.path.join(OUT, '.check', n + '.png'),
                        os.path.join(OUT, n + '.svg')])
    sys.exit(1 if bad else 0)

if __name__ == '__main__':
    main(sys.argv[1:])
