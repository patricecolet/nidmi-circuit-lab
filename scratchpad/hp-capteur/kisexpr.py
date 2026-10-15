"""Mini lecteur/écrivain S-expression KiCad + aplatissement des symboles de bibliothèque."""
import math, re

class S(str):
    """Chaîne entre guillemets (distincte d'un atome)."""

def parse(text):
    tok = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')
    stack, cur = [], []
    for m in tok.finditer(text):
        t = m.group(0)
        if t == '(':
            stack.append(cur); cur = []
        elif t == ')':
            done = cur; cur = stack.pop(); cur.append(done)
        elif t[0] == '"':
            cur.append(S(re.sub(r'\\(.)', lambda m: '\n' if m.group(1) == 'n' else m.group(1), t[1:-1])))
        else:
            cur.append(t)
    return cur[0]

def q(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'

def dump(x, ind=0):
    if isinstance(x, S):
        return q(x)
    if not isinstance(x, list):
        return str(x)
    simple = all(not isinstance(e, list) for e in x)
    if simple:
        return '(' + ' '.join(dump(e) for e in x) + ')'
    out = '(' + ' '.join(dump(e) for e in x if not isinstance(e, list))
    for e in x:
        if isinstance(e, list):
            out += '\n' + '\t' * (ind + 1) + dump(e, ind + 1)
    return out + '\n' + '\t' * ind + ')'

def find(x, key):
    return [e for e in x if isinstance(e, list) and e and e[0] == key]

def first(x, key):
    r = find(x, key)
    return r[0] if r else None

_libcache = {}
def lib(path):
    if path not in _libcache:
        root = parse(open(path, encoding='utf-8').read())
        _libcache[path] = {e[1]: e for e in find(root, 'symbol')}
    return _libcache[path]

def flatten(path, name, libname):
    """Renvoie la définition autonome 'libname:name' (extends résolu)."""
    syms = lib(path)
    sym = syms[name]
    ext = first(sym, 'extends')
    if ext:
        parent = flatten(path, ext[1], libname)
        out = [e for e in parent]
        out[1] = S(f'{libname}:{name}')
        props = {p[1]: p for p in find(sym, 'property')}
        new = []
        for e in out:
            if isinstance(e, list) and e and e[0] == 'property' and e[1] in props:
                new.append(props.pop(e[1]))
            elif isinstance(e, list) and e and e[0] == 'symbol':
                sub = list(e); pname = ext[1]
                sub[1] = S(name + sub[1][len(pname):])
                new.append(sub)
            else:
                new.append(e)
        # propriétés propres à l'enfant, insérées avant les sous-symboles
        idx = next(i for i, e in enumerate(new) if isinstance(e, list) and e[0] == 'symbol')
        for p in props.values():
            new.insert(idx, p); idx += 1
        return new
    out = list(sym)
    out[1] = S(f'{libname}:{name}')
    return out

def pins(flat):
    """[(numéro, nom, unité, x, y, angle)] en coordonnées bibliothèque (Y vers le haut)."""
    res = []
    for sub in find(flat, 'symbol'):
        m = re.search(r'_(\d+)_(\d+)$', sub[1])
        unit, style = int(m.group(1)), int(m.group(2))
        if style > 1:
            continue
        for p in find(sub, 'pin'):
            at = first(p, 'at')
            res.append((first(p, 'number')[1], first(p, 'name')[1], unit,
                        float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0))
    return res
