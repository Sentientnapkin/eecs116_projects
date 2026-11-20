import sys,glob,numpy as np,os
a,b=sys.argv[1:3]; n=0; bad=0; mx=0
for f in sorted(glob.glob(a+'/*.npz')):
    za=np.load(f); zb=np.load(os.path.join(b,os.path.basename(f))); n+=1
    if not np.array_equal(za['pose'],zb['pose']): bad+=1; mx=max(mx,np.abs(za['pose'][:,:3]-zb['pose'][:,:3]).max())
print('flights',n,'not bit-identical',bad,'max pos diff',mx)
