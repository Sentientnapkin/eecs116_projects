import sys,ctypes,subprocess,numpy as np,json
NAT='/dev/shm/sebastian-vio/viobench/viobench/solution/runtime/native'
src=sys.argv[1];defs=sys.argv[2] if len(sys.argv)>2 else '';f=sys.argv[3]
so='/dev/shm/n2_dbg.so';subprocess.check_call(['gcc','-O2','-shared','-fPIC','-msse4.1','-I'+NAT,*['-D'+d for d in defs.split()],'-o',so,src,'-lm'])
