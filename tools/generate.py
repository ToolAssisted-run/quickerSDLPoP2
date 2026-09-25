#!/usr/bin/env python3
"""generate.py: writes source/quickerSDLPoP2/quickerSDLPoP2.hpp from SDLPoP2's game logic (extern/SDLPoP2/source).

The C sources are turned into one C++ class, so that every instance owns a whole game:
  - file-scope variables become members; the savestate's variables (state.c's tables, in their order) form the
    packed base struct QuickerSDLPoP2State, so a savestate is that struct's bytes, identical to SDLPoP2's pop2_save;
  - functions become member functions; static locals become members; statics with the same name in two files
    are renamed with their file's name;
  - drawing, sound output, scenes and the program shell are left out: the few of their routines the logic calls
    are given here as no-ops (STUBS) or rewritten (OVERRIDES).
Run it again after SDLPoP2 changes: python3 tools/generate.py
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
import csplit  # noqa: E402

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
SRC = os.path.join(ROOT, 'extern', 'SDLPoP2', 'source')
OUT = os.path.join(ROOT, 'source', 'quickerSDLPoP2', 'quickerSDLPoP2.hpp')

# the game logic (what pop2_init, pop2_new_game and pop2_frame reach), in SDLPoP2's order
LOGIC = ('anim beast blades bridge5 caverns char cheats collision control core dat fight final frame game glue guard '
         'heads hooks input items kid kidctl kind1 kind5 level lever5 mobs room roomhooks ruins seq shadow13 skeleton '
         'sound spirit state temple tick tiles trap walls').split()   # (text.c: only its state effects, overrides.py)
HEADERS = 'types globals glue state dat core text settings'.split()

# the savestate's layout: state.c's tables in order, then the checkpoint copy (level.c `cp`) and core.c's `scene`
STATE_EXTRA_TAIL = ['cp', 'scene']

from overrides import OVERRIDES, STUBS, DROP, MEMBER_EXTRA, API, PATCHES, TYPE_PATCHES, FILE_PATCHES  # noqa: E402

IDENT = re.compile(r'[A-Za-z_]\w*')


def read(name):
    return open(os.path.join(SRC, name)).read()


def replace_idents(text, mapping):
    """Replaces whole identifiers outside comments and strings."""
    if not mapping:
        return text
    out, i = [], 0
    while i < len(text):
        j = csplit._skip_comment_or_string(text, i)
        if j != i:
            out.append(text[i:j])
            i = j
            continue
        m = IDENT.match(text, i)
        if m and (i == 0 or not (text[i - 1].isalnum() or text[i - 1] == '_')):
            w = m.group(0)
            out.append(mapping.get(w, w))
            i = m.end()
            continue
        out.append(text[i])
        i += 1
    return ''.join(out)


def top_level_split(text, sep=','):
    parts, depth, cur, i = [], 0, [], 0
    while i < len(text):
        j = csplit._skip_comment_or_string(text, i)
        if j != i:
            cur.append(text[i:j])
            i = j
            continue
        c = text[i]
        if c in '([{':
            depth += 1
        elif c in ')]}':
            depth -= 1
        if c == sep and depth == 0:
            parts.append(''.join(cur))
            cur = []
        else:
            cur.append(c)
        i += 1
    parts.append(''.join(cur))
    return parts


def strip_attributes(s):
    """Removes __attribute__((...)) with balanced parentheses."""
    while True:
        i = s.find('__attribute__')
        if i < 0:
            return s
        j = s.find('(', i)
        depth, k = 0, j
        while k < len(s):
            if s[k] == '(':
                depth += 1
            elif s[k] == ')':
                depth -= 1
                if depth == 0:
                    break
            k += 1
        s = s[:i] + s[k + 1:]


def classify_decl(text):
    """'extern', 'type', 'proto' or 'var' for a file-scope declaration."""
    s = strip_attributes(csplit.strip_comments(text).strip())
    if re.match(r'extern\b', s):
        return 'extern'
    if re.match(r'typedef\b', s):
        return 'type'
    if re.match(r'(struct|enum|union)\b[^=({]*\{', s) and re.search(r'\}\s*;$', s):
        return 'type'
    if re.match(r'enum\b', s):
        return 'type'
    if re.match(r'_Static_assert\b', s):
        return 'assert'
    head = s.split('=')[0]
    # a prototype: an identifier followed by a parameter list at depth 0 (not "(*name)")
    if re.search(r'[A-Za-z_]\w*\s*\([^*]', head) and '(*' not in head and '=' not in s:
        return 'proto'
    return 'var'


def parse_var(text):
    """(base type, [(name, declarator text)]) of a variable definition; the declarator text has the initialiser."""
    s = strip_attributes(csplit.strip_comments(text).strip()).rstrip(';').strip()
    # an anonymous struct type: the base is the whole struct
    m = re.match(r'((?:static\s+)?(?:struct|union)\s*\w*\s*)\{', s)
    if m:
        depth, i = 0, m.end() - 1
        while True:
            if s[i] == '{':
                depth += 1
            elif s[i] == '}':
                depth -= 1
                if depth == 0:
                    break
            i += 1
        base = s[:i + 1]
        decls = top_level_split(s[i + 1:])
        return base, [(re.match(r'[\s*(]*([A-Za-z_]\w*)', d).group(1), d.strip()) for d in decls]
    parts = top_level_split(s)
    first = parts[0]
    # the base type: everything before the first declarator's name (or its '*' / '(*')
    m = re.match(r'((?:(?:static|const|volatile|unsigned|signed|struct|enum|union)\s+)*[A-Za-z_]\w*(?:\s+const)?)\s*(.*)$', first, re.S)
    base, rest = m.group(1), m.group(2)
    decls = [rest] + parts[1:]
    out = []
    for d in decls:
        d = d.strip()
        n = re.match(r'[\s*(]*([A-Za-z_]\w*)', d)
        out.append((n.group(1), d))
    return base, out


def strip_head_static(text):
    """Removes 'static' (and 'inline' duplicates) from a function definition's head only."""
    i = csplit_head_start(text)
    head, body = text[:i], text[i:]
    head = re.sub(r'\bstatic\s+', '', head)
    return head + body


def csplit_head_start(text):
    """The index of a function's body '{' (depth 0), skipping comments."""
    i, depth = 0, 0
    while i < len(text):
        j = csplit._skip_comment_or_string(text, i)
        if j != i:
            i = j
            continue
        c = text[i]
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
        elif c == '{' and depth == 0:
            return i
        i += 1
    return len(text)


def hoist_static_locals(fname, text):
    """Moves a function's static locals out to members named <function>__<name>; returns (text, [(base, decl)])."""
    b = csplit_head_start(text)
    head, body = text[:b], text[b:]
    hoisted, renames = [], {}
    # statements inside the body starting with 'static' (at any depth > 0)
    out, i, depth, stmt_start = [], 0, 0, True
    while i < len(body):
        j = csplit._skip_comment_or_string(body, i)
        if j != i:
            out.append(body[i:j])
            i = j
            continue
        c = body[i]
        if depth > 0 and stmt_start and body.startswith('static', i) and not (body[i + 6].isalnum() or body[i + 6] == '_'):
            # the whole declaration up to ';' at this depth
            k, d2 = i, 0
            while k < len(body):
                m = csplit._skip_comment_or_string(body, k)
                if m != k:
                    k = m
                    continue
                if body[k] in '([{':
                    d2 += 1
                elif body[k] in ')]}':
                    d2 -= 1
                elif body[k] == ';' and d2 == 0:
                    break
                k += 1
            decl = body[i:k + 1]
            base, decls = parse_var(decl)
            base = re.sub(r'\bstatic\s+', '', base)
            for name, d in decls:
                new = '%s__%s' % (fname, name)
                decl_new = replace_idents(d, {name: new})
                if (base, decl_new) in hoisted:   # (the same static twice, in two branches: one member)
                    renames[name] = new
                    continue
                while any(re.match(r'[\s*(]*' + re.escape(new) + r'\b', h[1]) for h in hoisted):
                    new += '_'
                    decl_new = replace_idents(d, {name: new})
                renames[name] = new
                hoisted.append((base, decl_new))
            i = k + 1
            stmt_start = True
            continue
        if c in '{':
            depth += 1
        elif c == '}':
            depth -= 1
        if c in '{};':
            stmt_start = True
        elif not c.isspace():
            stmt_start = False
        out.append(c)
        i += 1
    body = replace_idents(''.join(out), renames)
    return head + body, hoisted


def state_names():
    """The savestate's variables, in order, with their sizes (state.c's snap_fields then extra_fields)."""
    src = csplit.strip_comments(read('state.c'))
    names = []
    for table in ('snap_fields', 'extra_fields'):
        m = re.search(table + r'\[\]\s*=\s*\{(.*?)\n\};', src, re.S)
        for e in re.finditer(r'\{\s*"(\w+)"\s*,\s*(\w+)\s*,\s*([^,]+?)\s*,\s*&?([A-Za-z_]\w*)\s*\}', m.group(1)):
            names.append((e.group(4), e.group(3).strip()))
    return names


def split_protos(s):
    """[(name, prototype)] of a declaration statement of one or more prototypes."""
    out = []
    for stmt in s.split(';'):
        stmt = stmt.strip()
        if not stmt:
            continue
        m = re.search(r'([A-Za-z_]\w*)\s*\(', stmt)
        if m and '(*' not in stmt.split('(')[0]:
            # several declarators sharing a type: "void f(void), g(int)"
            parts = top_level_split(stmt)
            base = parts[0][:parts[0].find(m.group(1))]
            for i, p in enumerate(parts):
                p = p.strip()
                n = m if i == 0 else re.match(r'[\s*]*([A-Za-z_]\w*)\s*\(', p)
                if n:
                    out.append((n.group(1), (p if i == 0 else base + p) + ';'))
    return out


def drop_local_externs(text):
    """Removes 'extern ...;' declarations inside a function body (the variables are members now)."""
    b = csplit_head_start(text)
    body = text[b:]
    out, i = [], 0
    while i < len(body):
        j = csplit._skip_comment_or_string(body, i)
        if j != i:
            out.append(body[i:j])
            i = j
            continue
        if body.startswith('extern', i) and (i == 0 or not (body[i - 1].isalnum() or body[i - 1] == '_')) and not (body[i + 6].isalnum() or body[i + 6] == '_'):
            k = body.find(';', i)
            i = k + 1
            continue
        out.append(body[i])
        i += 1
    return text[:b] + ''.join(out)


def zero_init(d):
    """C zero-initialises file-scope and static variables; a member without an initialiser gets '{}'."""
    return d if '=' in d else d + '{}'


def size_open_array(d):
    """'name[] = {a, b, c}' -> 'name[3] = {a, b, c}' (a member array needs its bound)."""
    m = re.match(r'([^=\[]*)\[\s*\](.*?)=\s*(\{.*\}|"(?:[^"\\]|\\.)*")\s*$', d, re.S)
    if not m:
        return d
    init = m.group(3)
    if init.startswith('"'):
        n = len(bytes(init[1:-1], 'utf-8').decode('unicode_escape')) + 1
    else:
        n = len([p for p in top_level_split(init[1:-1]) if p.strip()])
    return '%s[%d]%s= %s' % (m.group(1), n, m.group(2), init)


def main():
    commit = subprocess.run(['git', '-C', os.path.join(ROOT, 'extern', 'SDLPoP2'), 'rev-parse', '--short', 'HEAD'],
                            capture_output=True, text=True).stdout.strip()
    macros, types, members, functions, asserts = [], [], [], [], []
    var_types = {}           # name -> (base, declarator) of every file-scope variable
    file_items = {}

    protos = {}   # name -> prototype text (headers and sources), for the stubs
    # headers: macros and types only
    for h in HEADERS:
        for it in csplit.split(read(h + '.h')):
            t = csplit.strip_comments(it.text).strip()
            if it.kind == 'decl' and classify_decl(it.text) == 'proto':
                for p in split_protos(t):
                    protos.setdefault(p[0], p[1])
            if it.kind == 'decl' and classify_decl(it.text) == 'var':
                base, decls = parse_var(it.text)
                base = re.sub(r'\bstatic\s+', '', base)
                members.append((h + '.h', '', base, [d for _, d in decls]))
            if it.kind == 'pp':
                if re.match(r'#\s*define\b', t):
                    macros.append(it.lead.strip('\n') + '\n' + it.text if it.lead.strip() else it.text)
                elif re.match(r'#\s*pragma\s+pack\b', t):
                    types.append(it.text)
            elif it.kind == 'decl' and classify_decl(it.text) == 'type':
                types.append(it.text)

    # sources: split, find the statics that clash between files
    statics = {}
    for f in LOGIC:
        src = read(f + '.c')
        for a, b in FILE_PATCHES.get(f, []):
            if a not in src:
                raise SystemExit('file patch for %s.c does not apply (SDLPoP2 changed?): %r' % (f, a))
            src = src.replace(a, b)
        its = csplit.split(src)
        file_items[f] = its
        for it in its:
            s = csplit.strip_comments(it.text).strip()
            if not s.startswith('static'):
                continue
            if it.kind == 'func':
                n = re.search(r'([A-Za-z_]\w*)\s*\([^()]*(\([^()]*\)[^()]*)*\)\s*$', s.split('{')[0].strip())
                if n:
                    statics.setdefault(n.group(1), set()).add(f)
            elif it.kind == 'decl' and classify_decl(it.text) in ('var', 'proto'):
                if classify_decl(it.text) == 'var':
                    for name, _ in parse_var(it.text)[1]:
                        statics.setdefault(name, set()).add(f)
    clash = {n for n, fs in statics.items() if len(fs) > 1}

    state = state_names()
    state_set = {n for n, _ in state} | set(STATE_EXTRA_TAIL)

    for f in LOGIC:
        rename = {n: '%s__%s' % (n, f) for n in clash if f in statics.get(n, ())}
        for it in file_items[f]:
            text = replace_idents(it.text, rename)
            lead = it.lead
            s = csplit.strip_comments(text).strip()
            if it.kind == 'pp':
                if re.match(r'#\s*define\b', s):
                    macros.append(text)
                elif re.match(r'#\s*undef\b', s):
                    macros.append(text)
                continue
            if it.kind == 'comment':
                continue
            if it.kind == 'func':
                head = s.split('{')[0]
                n = re.search(r'([A-Za-z_]\w*)\s*\(', head.split('(')[0] + '(')
                name = re.search(r'([A-Za-z_]\w*)\s*$', head.split('(')[0]).group(1)
                if name in DROP:
                    continue
                if name in OVERRIDES:
                    functions.append((f, name, OVERRIDES[name]))
                    continue
                for old_text, new_text in PATCHES.get(name, []):
                    if old_text not in text:
                        raise SystemExit('patch for %s does not apply (SDLPoP2 changed?): %r' % (name, old_text))
                    text = text.replace(old_text, new_text)
                text, hoisted = hoist_static_locals(name, text)
                text = drop_local_externs(text)
                for base, d in hoisted:
                    members.append((f, '', base, [d]))
                functions.append((f, name, lead + text))
                continue
            kind = classify_decl(text)
            if kind == 'proto':
                for p in split_protos(s):
                    protos.setdefault(p[0], p[1])
                continue
            if kind == 'extern':
                for p in split_protos(re.sub(r'^extern\s+', '', s)):
                    protos.setdefault(p[0], p[1])
                continue
            if kind == 'type':
                types.append(lead + text)
                continue
            if kind == 'assert':
                asserts.append(text.replace('_Static_assert', 'static_assert'))
                continue
            base, decls = parse_var(text)
            base = re.sub(r'\bstatic\s+', '', base)
            keep = []
            for name, d in decls:
                var_types[name] = (base, d)
                if name in state_set or name in DROP:
                    continue
                keep.append(d)
            if keep:
                members.append((f, lead, base, keep))

    # hand-written stubs and extra functions
    for name, body in STUBS.items():
        functions.append(('stub', name, body))
    # routines outside the logic that the logic calls: no-ops (listed, to be reviewed: see overrides.py)
    defined = {n for _, n, _ in functions}
    used = set()
    for _, _, t in functions:
        used |= set(IDENT.findall(csplit.strip_comments(t)))
    auto = sorted(n for n in used if n in protos and n not in defined and n not in DROP)
    for n in auto:
        ret = protos[n].split(n)[0].strip()
        body = '{ }' if re.match(r'^(static\s+)?void$', ret) else '{ return {}; }'
        functions.append(('auto', n, re.sub(r'\bstatic\s+', '', protos[n]).rstrip(';').strip() + ' ' + body))
    open(os.path.join(ROOT, 'tools', 'autostubs.txt'), 'w').write('\n'.join(protos[n] for n in auto) + '\n')
    # types: each struct / typedef once
    seen, uniq = set(), []
    for t in types:
        c = csplit.strip_comments(t).strip()
        k = re.search(r'(\w+)\s*;\s*$', c)
        tag = re.match(r'(?:typedef\s+)?(?:struct|union|enum)\s+(?:__attribute__\s*\(\(.*?\)\)\s*)?(\w+)\s*\{', c)
        keys = {x for x in [k.group(1) if k else None, tag.group(1) if tag else None] if x}
        if keys and keys & seen:
            continue
        seen |= keys
        uniq.append(t)
    types = uniq

    # write
    o = []
    o.append('// quickerSDLPoP2: SDLPoP2\'s game logic as one C++ class (thread-safe: no globals).\n')
    o.append('// GENERATED by tools/generate.py from SDLPoP2 %s: edit the generator or its overrides, not this file.\n' % commit)
    o.append('// SDLPoP2 is (C) 2026 Sergio Martin and the SDLPoP2 contributors, GPL-3.0-or-later.\n\n')
    o.append('#pragma once\n\n#include <cstdint>\n#include <cstdio>\n#include <cstdlib>\n#include <cstring>\n#include <cctype>\n#include <map>\n#include <memory>\n#include <mutex>\n#include <string>\n#include <vector>\n')
    o.append('#include <jaffarCommon/serializers/base.hpp>\n#include <jaffarCommon/deserializers/base.hpp>\n\n')
    o.append('#pragma GCC diagnostic push\n')
    for w in ('-Wpedantic', '-Wnarrowing', '-Waddress-of-packed-member', '-Wmisleading-indentation', '-Wunused-variable',
              '-Wunused-but-set-variable', '-Wunused-function', '-Wunused-parameter', '-Wsign-compare', '-Wparentheses',
              '-Wchar-subscripts', '-Wtype-limits', '-Wimplicit-fallthrough', '-Wmissing-field-initializers', '-Wstringop-truncation', '-Wformat-truncation', '-Wmaybe-uninitialized', '-Wclass-memaccess'):
        o.append('#pragma GCC diagnostic ignored "%s"\n' % w)
    o.append('\nnamespace quicker\n{\n\n')
    o.append('// ---- macros\n')
    defined_macros = set()
    for m in macros:
        dm = re.match(r'\s*#\s*define\s+(\w+)', csplit.strip_comments(m).strip())
        if dm and dm.group(1) in defined_macros:
            o.append('#undef %s\n' % dm.group(1))   # (defined again by another file)
        if dm:
            defined_macros.add(dm.group(1))
        o.append(m.strip('\n') + '\n')
    o.append('// ---- types\n')
    for t in types:
        for a, b in TYPE_PATCHES:
            t = t.replace(a, b)
        o.append(t.strip('\n') + '\n')
    o.append('\n// ---- the savestate (the order and sizes of SDLPoP2\'s pop2_save)\n')
    o.append('struct __attribute__((packed)) QuickerSDLPoP2State\n{\n')
    for name, size in state + [(n, None) for n in STATE_EXTRA_TAIL]:
        if name not in var_types:
            raise SystemExit('state variable without a definition: ' + name)
        base, d = var_types[name]
        d = d.split('=')[0].strip()
        o.append('  %s %s{};\n' % (base, d))
    o.append('};\n\n')
    o.append('// every field as large as SDLPoP2 saves it\n')
    for name, size in state:
        if 'sizeof' in size and name in size:
            continue
        o.append('static_assert(sizeof(((QuickerSDLPoP2State *)0)->%s) == (%s), "%s");\n' % (name, size, name))
    o.append('\nclass QuickerSDLPoP2 : public QuickerSDLPoP2State\n{\npublic:\n')
    o.append(API)
    o.append('\n// ---- members (the variables outside the savestate)\n')
    for f, lead, base, keep in members:
        keep = [zero_init(size_open_array(d)) for d in keep]
        o.append('%s %s;   // %s\n' % (base, ', '.join(keep), f if f.endswith('.h') else f + '.c'))
    o.append(MEMBER_EXTRA)
    o.append('\n// ---- the game logic\n')
    cur = None
    for f, name, text in functions:
        if f != cur:
            o.append('\n// ==== %s\n' % ({'stub': 'hand-written (overrides.py)', 'auto': 'outside the game logic: no-ops (tools/autostubs.txt)'}.get(f, f + '.c')))
            cur = f
        t = strip_head_static(text.strip('\n'))
        t = re.sub(r'__attribute__\s*\(\(\s*weak\s*\)\)\s*', '', t)
        o.append(t + '\n')
    o.append('\n};   // class QuickerSDLPoP2\n\n')
    for a in asserts:
        o.append(a + '\n')
    o.append('\n} // namespace quicker\n\n#pragma GCC diagnostic pop\n')
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, 'w').write(''.join(o))
    print('wrote', OUT, '(%d functions, %d member declarations, %d state fields, %d renamed statics)' %
          (len(functions), len(members), len(state) + len(STATE_EXTRA_TAIL), len(clash)))


if __name__ == '__main__':
    main()
