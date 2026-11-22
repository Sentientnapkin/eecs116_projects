import sys
sys.path.insert(0, "/mnt/c/Users/alexa/Projects/eecs116_vio/proto/night/hf")
from hf_sum import man, load
names = sys.argv[1:]
R = {n: load(n) for n in names}
fl = sorted(f for f in R[names[0]] if man[f]["start_offset_s"] == 0)
worst = sorted(fl, key=lambda f: -max(R[n][f][0] for n in names))[:8]
print("rest flight".ljust(36) + "".join(f"{n:>10s}" for n in names) + "   nothing")
for f in worst: print(f[:36].ljust(36) + "".join(f"{R[n][f][0]:10.2f}" for n in names) + f"   {R[names[0]][f][1]:.2f}")
