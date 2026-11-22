import numpy as np, re, glob, sys
f=glob.glob(f'../../results/single_model/lv_{sys.argv[1]}/one/*/*/report/logs/*/stderr.txt')[0]
g=np.load(f'/data/backups/rganapa/Sebastian/tmp/lv_grav/{sys.argv[2]}.npz')['gb0']
fr=0; ev=[]
for l in open(f):
    m=re.match(r'E f=(\d+) .*Rz=([-\d.]+),([-\d.]+),([-\d.]+)',l)
    if m:
        fr=int(m.group(1)); Rz=np.array([float(m.group(i)) for i in (2,3,4)])
        if fr%5==0 and fr//5<len(g):
            a=np.degrees(np.arccos(np.clip(Rz@-g[fr//5],-1,1)))
            if float(sys.argv[3])<=fr*0.05<=float(sys.argv[4]): print('t %.2f tilt err %.1f'%(fr*.05,a), ' '.join(ev)); ev=[]
    elif l.startswith('LC apply'): ev.append('NET(r=%s)'%' '.join(l.split(' r ')[1].split()[:3]))
    elif l.startswith('D ') and ' fire=' in l and 'fire=0' not in l: ev.append('FIRE')
