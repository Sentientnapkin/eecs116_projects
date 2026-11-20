import sys
def leb(d,i):
    r=s=0
    while True:
        b=d[i];i+=1;r|=(b&127)<<s;s+=7
        if b<128:return r,i
def parse(p):
    d=open(p,'rb').read();assert d[:4]==b'\0asm';i=8;imp=[];exp=[];secs=[]
    while i<len(d):
        sid=d[i];n,j=leb(d,i+1);secs.append((sid,n));body=j
        if sid in(2,7):
            c,k=leb(d,j)
            for _ in range(c):
                if sid==2:
                    l,k=leb(d,k);m=d[k:k+l].decode();k+=l;l,k=leb(d,k);f=d[k:k+l].decode();k+=l;kind=d[k];k+=1
                    if kind==0:_,k=leb(d,k)
                    elif kind==1:k+=1;fl=d[k];k+=1;_,k=leb(d,k);(_,k)=leb(d,k) if fl&1 else (0,k)
                    elif kind==2:fl=d[k];k+=1;_,k=leb(d,k);(_,k)=leb(d,k) if fl&1 else (0,k)
                    elif kind==3:k+=2
                    imp.append((m,f))
                else:
                    l,k=leb(d,k);nm=d[k:k+l].decode();k+=l;kind=d[k];k+=1;_,k=leb(d,k);exp.append((nm,kind))
        i=j+n
    return imp,exp
for p in sys.argv[1:]:
    imp,exp=parse(p);print(p);print(' imports:',imp);print(' exports:',[e for e in exp])
