import sys
d = {}
for a in sys.argv[1:]:
    k = a.split('=')[0]; d.pop(k, None); d[k] = a
print(' '.join(d.values()))
