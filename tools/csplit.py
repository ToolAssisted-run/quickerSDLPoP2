"""Splits C source into top-level items for tools/generate.py.

An item is one of:
  ('pp', text)          a preprocessor line (with its continuations)
  ('func', text)        a function definition (declaration and body)
  ('decl', text)        anything ending in ';' at file scope: variables, prototypes, typedefs, struct/enum definitions
  ('comment', text)     a comment standing alone between items
Comments and blank lines directly before an item are kept with it (in 'lead'), so the output stays readable.
"""
import re


class Item:
    def __init__(self, kind, text, lead=''):
        self.kind, self.text, self.lead = kind, text, lead

    def __repr__(self):
        return '%s: %s' % (self.kind, self.text[:60].replace('\n', ' '))


def _skip_comment_or_string(src, i):
    """If src[i:] starts a comment, string or char literal, returns the index after it, else i."""
    if src.startswith('//', i):
        j = src.find('\n', i)
        return len(src) if j < 0 else j
    if src.startswith('/*', i):
        j = src.find('*/', i + 2)
        return len(src) if j < 0 else j + 2
    if src[i] in '"\'':
        q = src[i]
        j = i + 1
        while j < len(src) and src[j] != q:
            j += 2 if src[j] == '\\' else 1
        return j + 1
    return i


def strip_comments(text):
    """The text without comments (strings kept), for classifying items."""
    out, i = [], 0
    while i < len(text):
        j = _skip_comment_or_string(text, i)
        if j != i:
            if text[i] in '"\'':
                out.append(text[i:j])
            else:
                out.append(' ')
            i = j
        else:
            out.append(text[i])
            i += 1
    return ''.join(out)


def split(src):
    items, i, n = [], 0, len(src)
    lead_start = 0
    while True:
        # the lead: blank lines and comments before the next item
        j = i
        while j < n:
            if src[j].isspace():
                j += 1
                continue
            k = _skip_comment_or_string(src, j) if src[j] == '/' else j
            if k != j:
                j = k
                continue
            break
        if j >= n:
            if src[i:].strip():
                items.append(Item('comment', src[i:]))
            break
        lead = src[i:j]
        start = j
        if src[j] == '#':
            # a preprocessor line and its continuations
            k = j
            while True:
                e = src.find('\n', k)
                if e < 0:
                    e = n
                    break
                if src[e - 1] == '\\':
                    k = e + 1
                    continue
                break
            items.append(Item('pp', src[start:e], lead))
            i = e
            continue
        # a declaration or a function: up to ';' at depth 0, or a function body's closing brace
        depth, k, saw_body = 0, j, False
        head_end = None
        while k < n:
            c = src[k]
            m = _skip_comment_or_string(src, k)
            if m != k:
                k = m
                continue
            if c in '([':
                depth += 1
            elif c in ')]':
                depth -= 1
            elif c == '{':
                if depth == 0 and head_end is None:
                    head_end = k
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0 and head_end is not None:
                    head = strip_comments(src[start:head_end])
                    # a function: a parameter list before the body, no '=' (an initialiser) and not a struct/enum/union
                    if '(' in head and '=' not in head and not re.search(r'\b(struct|enum|union)\s*\w*\s*$', head.strip()) \
                            and not re.match(r'\s*(typedef|(static\s+)?(const\s+)?(struct|enum|union))\b', head):
                        k += 1
                        saw_body = True
                        break
            elif c == ';' and depth == 0:
                k += 1
                break
            k += 1
        text = src[start:k]
        items.append(Item('func' if saw_body else 'decl', text, lead))
        i = k
    return items


if __name__ == '__main__':
    import sys
    for path in sys.argv[1:]:
        its = split(open(path).read())
        print(path, len(its), {k: sum(1 for x in its if x.kind == k) for k in ('pp', 'func', 'decl', 'comment')})
