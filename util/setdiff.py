#!/usr/bin/env python3

import sys

def file_to_set(f):
    with open(f) as fd:
        return set((t for t in fd))

a = file_to_set(sys.argv[1])
b = file_to_set(sys.argv[2])

for l in sorted(a - b):
    sys.stdout.write("- " + l)
for l in sorted(b - a):
    sys.stdout.write("+ " + l)

