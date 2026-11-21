"""estcmp.py DIR_A DIR_B : compare estimate.tum + twist.txt byte-for-byte per episode between two run_guest_fast eval folders"""
import sys, glob, os, hashlib
def m(d):
    out = {}
    for f in glob.glob(os.path.join(d, '*/report/logs/*/estimate.tum')):
        ep = f.split('/report/')[0].split('/')[-1]; tw = f.replace('estimate.tum', 'twist.txt')
        out[ep] = hashlib.sha1(open(f, 'rb').read() + (open(tw, 'rb').read() if os.path.exists(tw) else b'')).hexdigest()
    return out
A, B = m(sys.argv[1]), m(sys.argv[2]); com = sorted(set(A) & set(B))
diff = [e for e in com if A[e] != B[e]]
print('episodes A %d B %d common %d identical %d differ %d %s' % (len(A), len(B), len(com), len(com) - len(diff), len(diff), diff[:5]))
