#!/usr/bin/env python3
"""score_play.py <shared-tag> [<microG-tag>]  -- score a shared Play services round against a microG one.

Reads $WL_CORPUS/round-<tag>.log (the lifecycle rung of each app: 5 = drawing) and, for the shared
tag, each app's stderr in $WL_SC/inputs/logs/<tag>/ for the WL-PLAY trace (WESTLAKE_PLAY_TRACE):
connection replies by status, error replies by interface, and services an app asked for that the
shared process did not have. play-tokens.log gives FCM token counts per app. LIST=<file> limits it
to those packages (default every package in apps.csv)."""
import re,os,collections as C,sys
os.chdir(os.environ.get('WL_CORPUS') or os.path.join(os.environ['WL_SC'],'inputs/corpus-hk'))
IN=os.path.join(os.environ['WL_SC'],'inputs')
A=sys.argv[1]; B=sys.argv[2] if len(sys.argv)>2 else None
def rd(t):
    o={}
    if t is None or not os.path.exists(f'round-{t}.log'): return o
    for l in open(f'round-{t}.log',errors='ignore'):
        p=l.split()
        if len(p)>2 and p[0].startswith('hk-') and re.fullmatch(r'\d',p[1]): o[p[0][3:]]=(int(p[1]),' '.join(p[2:]))
    return o
a=rd(A);b=rd(B); L=[x.strip() for x in open(os.environ.get("LIST","apps.csv")) if x.strip()]
print('unscored shared',len([x for x in L if x not in a]),'microG',len([x for x in L if x not in b]))
for n,o in((A,a),(B,b)): print(n,len(o),sorted(C.Counter(v[0] for v in o.values()).items()))
print('\nDIFF (rung shared vs microG)')
for k in L:
    x=a.get(k,(None,''));y=b.get(k,(None,''))
    if x[0]!=y[0]: print(f' {k[:40]:40} sh={x[0]} mg={y[0]} | {(x[1] if (x[0] or 0)<(y[0] or 0) else y[1])[:80]}')
print('\nSHARED NOT DRAWING')
for k in L:
    x=a.get(k)
    if x and x[0]<5: print(f' {k[:38]:38} {x[0]} mg={b.get(k,(None,))[0]} {x[1][:95]}')
stat=C.Counter();apps=C.Counter();iface=C.Counter();nos=C.Counter();conn=0;bad=C.Counter();perapp={}
exc=C.Counter()
for k in L:
    f=os.path.join(IN,'logs',A,f'hk-{k}.stderr')
    if not os.path.exists(f): continue
    t=open(f,errors='ignore').read()
    conn+='WL-PLAY] connected' in t
    best={}
    for m in re.finditer(r'WL-PLAY-TRACE\] (.*) x(\d+)\n',t):
        key,n=m[1],int(m[2]); best[key]=max(best.get(key,0),n)
    ok=fail=0
    for key,n in best.items():
        m=re.search(r'IGmsCallbacks code=\d+ status=(\S+) afterService=(\S+)',key)
        if m:
            stat[(m[1])]+=n
            if m[1]=='0': ok+=n
            else: fail+=n; bad[(m[1],m[2])]+=n
        m=re.match(r'out (\S+) code=(\d+)(?: service=\d+)? (\S+)',key)
        if m:
            if m[1]!='null': iface[m[1].split('.')[-1]]+=n
            if re.fullmatch(r'-\d+',m[3]) or not re.fullmatch(r'-?\d+|oneway',m[3]): exc[(m[1].split('.')[-1],m[2],m[3])]+=n
    perapp[k]=(ok,fail)
    for m in set(re.findall(r'WL-PLAY\] no service for Intent \{ act=(\S+)',t)): nos[m]+=1
print('\nconnected apps',conn,'status',stat.most_common())
print('nonzero status by (status,afterService)',bad.most_common(20))
print('apps with any connection',sum(1 for v in perapp.values() if sum(v)),'with a nonzero',sum(1 for v in perapp.values() if v[1]))
print('error replies (iface,code,reply)',exc.most_common(15))
print('top interfaces',iface.most_common(18))
print('no-service apps',nos.most_common(12))
tk={}
tf=os.path.join(os.environ.get('PLAY_DIR') or os.path.join(IN,'play-runs'),'play-tokens.log')
for l in (open(tf,errors='ignore') if os.path.exists(tf) else []):
    p=l.split()
    if len(p)==4: 
        v=tk.get(p[1],(0,0)); tk[p[1]]=(max(v[0],int(p[2])),max(v[1],int(p[3])))
s=[k for k in L if k in tk]
print('token file seen',len(s),'with token',sum(tk[k][0]>0 for k in s),'placeholder',sum(tk[k][1]>0 for k in s))
print('no token file',[k[:28] for k in L if k not in tk][:40])
print('in file no token',[k[:28] for k in s if tk[k][0]==0])
