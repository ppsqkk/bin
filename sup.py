#!/usr/bin/env python3
# Shortest unique prefix

import argparse
import collections
import functools
import pathlib

Trie = lambda: collections.defaultdict(Trie)

def sup(w, l):
    t = Trie()
    for s in l:
        prev = t
        for c in s:
            prev = prev[c]

    res = ''
    for c in w:
        res += c

        # If there is a branch corresponding to the character c, walk the tree.
        # Otherwise, we know that the current res is a unique prefix.
        if c in t:
            t = t[c]
        else:
            break
    return res

def f(l):
    res = []
    for p in l:
        d = [x.name for x in filter(lambda x: x.is_dir() and x.name != p.name,
                                    p.parent.iterdir())]
        res.append(sup(p.name, d))
    return res

parser = argparse.ArgumentParser()
parser.add_argument('path', nargs='?', default='.')
parser.add_argument('-n', default=1, type=int)
args = parser.parse_args()

path = pathlib.Path(args.path).resolve()
home = pathlib.Path.home()
if path.is_relative_to(home):
    path = '~' / path.relative_to(home)

abs = functools.reduce(lambda x, y: x + [x[-1] / y],
                       path.parts[1:],
                       [pathlib.Path(path.parts[0]).expanduser()])
x = len(abs) - args.n
x = x if x > 0 else 1
print(pathlib.Path(path.parts[0], *f(abs[1:x]), *path.parts[x:]))
