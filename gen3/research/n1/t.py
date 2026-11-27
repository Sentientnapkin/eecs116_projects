import sim,time,glob
f=sorted(glob.glob('cache/*.npz'))[0]
for opts in [{'noupd':1},{}]:
  t=time.time();print(sim.run((f,0.3,10,'white',10,opts)),time.time()-t)
