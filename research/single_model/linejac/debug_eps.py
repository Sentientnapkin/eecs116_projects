from pathlib import Path
w=Path(__file__).resolve().parent
s=(w/'lj.c').read_text()
# Change only the numeric comparison step; production source remains untouched.
s=s.replace('const double eps = 1e-6','const double eps = 1e-7')
(w/'check_eps.c').write_text(s)
