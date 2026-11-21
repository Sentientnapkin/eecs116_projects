import numpy as np, glob, sys
F=[np.load(f) for f in sorted(glob.glob('../../results/single_model/t1m_prof_%s/*.npz'%sys.argv[1]))]
L={0:'oth',1:'prop',3:'lc',4:'visO',5:'pyr',7:'clone',8:'map',9:'det',11:'QR',12:'solve',13:'upd',14:'fr',15:'tri',20:'prep',25:'head',27:'gray',30:'klt',31:'jac',32:'null',33:'gH0P',34:'gS',35:'chol'}
rows=[]
for fi,z in enumerate(F):
    for f in range(len(z['tot'])): rows.append((z['tot'][f],fi,f))
rows.sort(reverse=True)
for t,fi,f in rows[:int(sys.argv[2]) if len(sys.argv)>2 else 15]:
    z=F[fi]; S=z['seg'][f]; V=z['vals'][f]
    top=sorted(((S[i],L.get(i,str(i))) for i in range(48) if S[i]>2e4),reverse=True)[:7]
    print('%.2fM f%4d pred %4dk vis %d klt %d rows %d nb %d cells %d units %d map %d prior %d | '%(t/1e6,f,V[43],V[38],V[44],V[45],V[39],V[16],V[17],V[18],V[19])+' '.join('%s %.0f'%(n,v/1e3) for v,n in top))
