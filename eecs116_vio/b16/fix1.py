s = open('b16s.c').read()
BS = chr(92)
bad = "} } " + BS + "nstatic void NAME(const float *in"
good = "} } " + BS + "\nstatic void NAME(const float *in"
assert s.count(bad) == 1, s.count(bad)
s = s.replace(bad, good)
a = "#ifndef LC_DVCORR\n#define LC_DVCORR 1\n#endif\n"
assert s.count(a) == 1
s = s.replace(a, "")
s = s.replace("#define LC_PREP_PARTS 8\n", "#define LC_PREP_PARTS 8\n" + a, 1)
open('b16s.c', 'w').write(s)
print("fixed")
