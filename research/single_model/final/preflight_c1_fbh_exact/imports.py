import sys,wasmtime
m=wasmtime.Module(wasmtime.Engine(),open(sys.argv[1],'rb').read())
print(' imports:',[(i.module,i.name) for i in m.imports]); print(' exports:',[(e.name) for e in m.exports])
