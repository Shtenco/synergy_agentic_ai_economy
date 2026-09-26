from __future__ import annotations
import argparse, json, math, random
from dataclasses import dataclass
from collections import deque
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

PAIR_NAMES = [
    ("SYNA","BTC"), ("SYNA","ETH"), ("SYNA","WETH"),
    ("SYNR","BTC"), ("SYNR","ETH"), ("SYNR","WETH"),
]
MARKET_STATE_DIM = 20
MARKET_ACTIONS = 32
CB_STATE_DIM = 12
CB_ACTIONS = 90

@dataclass
class Config:
    initial_hardnav: float = 10000.0
    initial_syna_price: float = 1.0
    initial_synr_price: float = 1.0
    initial_syna_supply: float = 10000.0
    initial_synr_supply: float = 10000.0
    bridge_fee_bps: float = 10.0
    swap_fee_bps: float = 30.0
    seed: int = 77

class MLP(nn.Module):
    def __init__(self, state_dim:int, actions:int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim,64), nn.ReLU(),
            nn.Linear(64,64), nn.ReLU(),
            nn.Linear(64,actions)
        )
    def forward(self,x): return self.net(x)

class DQNAgent:
    def __init__(self,state_dim,actions,seed,gamma=.99,lr=3e-4,buffer_size=20000,batch_size=48,target_sync=500,update_every=4):
        torch.manual_seed(seed)
        self.rng=random.Random(seed)
        self.actions=actions; self.gamma=gamma; self.batch_size=batch_size
        self.target_sync=target_sync; self.update_every=update_every
        self.q=MLP(state_dim,actions)
        self.target=MLP(state_dim,actions)
        self.target.load_state_dict(self.q.state_dict())
        self.opt=optim.Adam(self.q.parameters(),lr=lr)
        self.buf=deque(maxlen=buffer_size); self.steps=0
    def act(self,state,epsilon):
        if self.rng.random()<epsilon: return self.rng.randrange(self.actions)
        with torch.no_grad():
            return int(self.q(torch.tensor(state,dtype=torch.float32).unsqueeze(0)).argmax(1).item())
    def push(self,s,a,r,ns,d):
        self.buf.append((np.asarray(s,np.float32),int(a),float(r),np.asarray(ns,np.float32),float(d)))
        self.steps += 1
        if self.steps % self.update_every == 0: self.learn()
        if self.steps % self.target_sync == 0: self.target.load_state_dict(self.q.state_dict())
    def learn(self):
        if len(self.buf)<self.batch_size: return
        b=self.rng.sample(self.buf,self.batch_size)
        s=torch.tensor(np.stack([x[0] for x in b]))
        a=torch.tensor([x[1] for x in b],dtype=torch.long)
        r=torch.tensor([x[2] for x in b],dtype=torch.float32)
        ns=torch.tensor(np.stack([x[3] for x in b]))
        d=torch.tensor([x[4] for x in b],dtype=torch.float32)
        q=self.q(s).gather(1,a[:,None]).squeeze(1)
        with torch.no_grad():
            na=self.q(ns).argmax(1)
            nq=self.target(ns).gather(1,na[:,None]).squeeze(1)
            y=r+self.gamma*(1-d)*nq
        loss=nn.functional.smooth_l1_loss(q,y)
        self.opt.zero_grad(); loss.backward()
        nn.utils.clip_grad_norm_(self.q.parameters(),5.0); self.opt.step()

class Economy:
    def __init__(self,cfg:Config):
        self.cfg=cfg; self.rng=np.random.default_rng(cfg.seed); self.reset()
    def reset(self):
        c=self.cfg; self.block=0
        self.ext_price={"BTC":65000.0,"ETH":3200.0,"WETH":3200.0}
        self.prev_ext=self.ext_price.copy()
        self.token_price={"SYNA":c.initial_syna_price,"SYNR":c.initial_synr_price}
        self.supply={"SYNA":c.initial_syna_supply,"SYNR":c.initial_synr_supply}
        nav=c.initial_hardnav
        self.real={"BTC":.25*nav,"ETH":.20*nav,"WETH":.05*nav,"USDC":.50*nav}
        self.synthetic={"BTC":0.0,"ETH":0.0,"WETH":0.0}
        self.lp={p:500.0 for p in PAIR_NAMES}
        self.bridge_fee_bps=c.bridge_fee_bps; self.reserve_target=.55
        self.emission_bias=0.0; self.risk_mult=1.0
        self.external_flow=0.0; self.fees=0.0; self.exec_cost=0.0; self.volume=0.0
        self.max_nav=self.hardnav(); self.last_vol=0.0; self.last_flow=0.0
        self.pending={p:0.0 for p in PAIR_NAMES}
        self.last_market={p:-999 for p in PAIR_NAMES}; self.last_cb=-999
        return self.states()
    def hardnav(self): return float(sum(self.real.values()))
    def capital_adjusted(self): return self.hardnav()-self.external_flow
    def reserve_coverage(self):
        liabilities=sum(self.supply[t]*self.token_price[t] for t in ("SYNA","SYNR"))
        return self.hardnav()/max(liabilities,1e-9)
    def market_move(self):
        z=self.rng.multivariate_normal([0,0],[[1,.72],[.72,1]])
        rb=0.00008+0.010*z[0]; re=0.00010+0.013*z[1]
        self.prev_ext=self.ext_price.copy()
        self.ext_price["BTC"]*=math.exp(rb); self.ext_price["ETH"]*=math.exp(re)
        self.ext_price["WETH"]*=math.exp(re+self.rng.normal(0,.00015))
        for a in ("BTC","ETH","WETH"):
            self.real[a]*=self.ext_price[a]/self.prev_ext[a]
        self.last_vol=float(np.std([rb,re]))
    def user_flow(self):
        total=0.0
        for a in ("BTC","ETH","WETH"):
            usd=float(max(0,self.rng.lognormal(2.1,.45)-7))
            if self.rng.random()<.52:
                self.real[a]+=usd; self.synthetic[a]+=usd; self.external_flow+=usd; total+=usd
                fee=usd*self.bridge_fee_bps/10000
                self.real["USDC"]+=fee; self.fees+=fee; self.volume+=usd
            else:
                gross=min(usd,self.synthetic[a],self.real[a]*.01)
                fee=gross*self.bridge_fee_bps/10000
                delivered=max(0,gross-fee)
                self.synthetic[a]-=gross; self.real[a]-=delivered; self.external_flow-=delivered; total-=delivered
                self.real["USDC"]+=fee; self.fees+=fee; self.volume+=gross
        for p in PAIR_NAMES:
            q=float(max(0,self.rng.lognormal(1.9,.55)-5.5))
            self.pending[p]=q if self.rng.random()<.5 else -q
        self.last_flow=total
    def route(self,src,dst,usd):
        if usd<=0:return 0.0
        b=self.bridge_fee_bps/10000; s=self.cfg.swap_fee_bps/10000
        if src in ("BTC","ETH","WETH") and dst in ("SYNA","SYNR"):
            self.real[src]+=usd; self.synthetic[src]+=usd; self.external_flow+=usd
            delivered=usd*(1-b)*(1-s); fee=usd-delivered
            self.real["USDC"]+=fee; self.fees+=fee; self.volume+=usd
            return delivered
        if src in ("SYNA","SYNR") and dst in ("BTC","ETH","WETH"):
            gross=min(usd*(1-s),self.synthetic[dst],self.real[dst]*.03)
            delivered=gross*(1-b)
            if delivered<=0:return 0.0
            self.synthetic[dst]-=gross; self.real[dst]-=delivered; self.external_flow-=delivered
            self.real["USDC"]+=gross-delivered; self.fees+=gross-delivered; self.volume+=gross
            return delivered
        return 0.0
    def market_state(self,p):
        t,a=p; nav=self.hardnav(); dd=max(0,1-nav/max(self.max_nav,1e-9))
        er=self.ext_price[a]/self.prev_ext[a]-1
        return np.array([
            self.token_price[t], math.log1p(self.supply[t])/10, er*100, self.last_vol*100,
            nav/self.cfg.initial_hardnav, dd, self.reserve_coverage(), self.real[a]/nav,
            self.synthetic[a]/nav, self.lp[p]/nav, self.bridge_fee_bps/100,
            self.cfg.swap_fee_bps/100, self.last_flow/nav, self.volume/nav, self.fees/nav,
            self.exec_cost/nav, self.emission_bias, self.risk_mult, self.reserve_target,
            self.pending[p]/nav
        ],dtype=np.float32)
    def cb_state(self):
        nav=self.hardnav(); dd=max(0,1-nav/max(self.max_nav,1e-9))
        risky=sum(self.real[a] for a in ("BTC","ETH","WETH"))/nav
        return np.array([
            nav/self.cfg.initial_hardnav,dd,self.reserve_coverage(),
            self.token_price["SYNA"],self.token_price["SYNR"],self.last_vol*100,
            self.volume/nav,self.fees/nav,(self.supply["SYNA"]+self.supply["SYNR"])/20000,
            self.last_flow/nav,risky,self.risk_mult
        ],dtype=np.float32)
    def states(self): return [self.market_state(p) for p in PAIR_NAMES], self.cb_state()
    def apply_cb(self,a):
        if self.block-self.last_cb<8:return 0.0
        risk_idx=a%2; x=a//2; emis_idx=x%3; x//=3; reserve_idx=x%5; fee_idx=x//5
        nf=[5,10,20][fee_idx]; nr=[.35,.45,.55,.65,.75][reserve_idx]
        ne=[-.001,0,.001][emis_idx]; nm=[.7,1.0][risk_idx]
        dd=max(0,1-self.hardnav()/max(self.max_nav,1e-9))
        if dd>.10:
            nr=max(nr,.65); ne=min(ne,0.0); nm=min(nm,.6); nf=max(nf,10)
        penalty=abs(nf-self.bridge_fee_bps)*.002+abs(nr-self.reserve_target)*.2+abs(ne-self.emission_bias)*10+abs(nm-self.risk_mult)*.05
        self.bridge_fee_bps=nf; self.reserve_target=nr; self.emission_bias=ne; self.risk_mult=nm
        for t in ("SYNA","SYNR"):
            self.supply[t]=max(1000,self.supply[t]*(1+ne))
            self.token_price[t]*=max(.997,min(1.003,1-ne*.35))
        self.last_cb=self.block
        return penalty
    def apply_market(self,p,a):
        if a==0:return 0.0
        t,asset=p; sizes=[.001,.0025,.005,.01,.02]
        group=(a-1)//5; idx=(a-1)%5; nav=self.hardnav()
        if group>=2 and self.block-self.last_market[p]<4:return 0.0
        dd=max(0,1-nav/max(self.max_nav,1e-9))
        if dd>.12 and group>=2:return 0.0
        usd=min(nav*sizes[idx]*self.risk_mult,self.lp[p]*.25)
        before=self.capital_adjusted()
        if group==0:
            fill=min(usd,max(0,self.pending[p]))
            if fill>0:self.route(asset,t,fill); self.pending[p]-=fill
        elif group==1:
            fill=min(usd,max(0,-self.pending[p]))
            if fill>0:
                got=self.route(t,asset,fill); self.pending[p]+=got
        elif group==2:
            move=min(usd,self.real[asset]*.03)
            self.synthetic[asset]+=move
            fee=move*self.bridge_fee_bps/10000; self.real["USDC"]-=min(self.real["USDC"],fee); self.exec_cost+=fee
        elif group==3:
            move=min(usd,self.synthetic[asset],self.real[asset]*.03)
            self.synthetic[asset]-=move
            fee=move*self.bridge_fee_bps/10000; self.real["USDC"]-=min(self.real["USDC"],fee); self.exec_cost+=fee
        elif group==4:
            add=min(usd,self.real["USDC"]*.02); self.lp[p]+=add
            cost=add*.001; self.real["USDC"]-=min(self.real["USDC"],cost); self.exec_cost+=cost
        elif group==5:
            rem=min(usd,self.lp[p]*.10); self.lp[p]=max(100,self.lp[p]-rem)
        else:
            target=self.reserve_target/3; cur=self.real[asset]/nav; delta=(target-cur)*nav*.05
            if delta>0:
                move=min(delta,self.real["USDC"]*.05); self.real["USDC"]-=move; self.real[asset]+=move
            else:
                move=min(-delta,self.real[asset]*.05); self.real[asset]-=move; self.real["USDC"]+=move
        if group>=2:self.last_market[p]=self.block
        return self.capital_adjusted()-before
    def step(self,ma,ca):
        pre_ca=self.capital_adjusted(); pre_prices=self.token_price.copy()
        self.market_move(); self.user_flow(); cb_pen=self.apply_cb(ca)
        pnls=[self.apply_market(p,a) for p,a in zip(PAIR_NAMES,ma)]
        nav=self.hardnav(); self.max_nav=max(self.max_nav,nav)
        dd=max(0,1-nav/max(self.max_nav,1e-9)); ca_nav=self.capital_adjusted()
        mrs=[]
        for i,p in enumerate(PAIR_NAMES):
            asset=p[1]; backed=min(self.synthetic[asset],self.real[asset])/max(nav,1)
            over=max(0,self.synthetic[asset]-self.real[asset])/max(nav,1)
            action_pen=.001 if ma[i]!=0 else 0
            r=pnls[i]*.025 + backed*.02 - over*20 - dd*8 - action_pen
            mrs.append(float(np.clip(r,-5,5)))
        rc=self.reserve_coverage()
        cb_r=(ca_nav-pre_ca)*.015-dd*30-abs(rc-self.reserve_target)*.7-cb_pen
        cb_r-=sum(abs(self.token_price[t]-pre_prices[t]) for t in ("SYNA","SYNR"))*.05
        self.block+=1
        info={"hardnav":nav,"capital_adjusted_hardnav":ca_nav,"drawdown":dd,"reserve_coverage":rc,"fees":self.fees,"bridge_volume":self.volume}
        return self.states(),mrs,float(np.clip(cb_r,-10,10)),info

def make_agents(seed):
    return [DQNAgent(20,32,seed+i) for i in range(6)], DQNAgent(12,90,seed+100)

def eps(step,total): return .03+.97*max(0,1-step/max(total,1))

def run_passive(seed,blocks):
    e=Economy(Config(seed=seed)); ms,cs=e.states(); arr=[]
    neutral_cb=44
    for _ in range(blocks):
        (ms,cs),_,_,info=e.step([0]*6,neutral_cb); arr.append(info)
    end=arr[-1]["capital_adjusted_hardnav"]
    return {"return_pct":(end/10000-1)*100,"end":end,"max_drawdown_pct":max(x["drawdown"] for x in arr)*100}

def train_multiseed(train_seeds=(1,2,3),blocks_per_seed=400,holdout_seeds=(77,101,2026,42,31415),oos_blocks=300,base_seed=9001):
    random.seed(base_seed); np.random.seed(base_seed); torch.manual_seed(base_seed)
    markets,cb=make_agents(base_seed); total=len(train_seeds)*blocks_per_seed; gs=0; train=[]
    for sd in train_seeds:
        e=Economy(Config(seed=int(sd))); ms,cs=e.states(); maxdd=0.0
        for i in range(blocks_per_seed):
            epsilon=eps(gs,total)
            ma=[ag.act(st,epsilon) for ag,st in zip(markets,ms)]; ca=cb.act(cs,epsilon)
            (nms,ncs),mrs,cr,info=e.step(ma,ca); done=i==blocks_per_seed-1
            for ag,st,a,r,nst in zip(markets,ms,ma,mrs,nms): ag.push(st,a,r,nst,done)
            cb.push(cs,ca,cr,ncs,done); ms,cs=nms,ncs; gs+=1; maxdd=max(maxdd,info["drawdown"])
        train.append({"seed":int(sd),"end_ca_nav":info["capital_adjusted_hardnav"],"max_dd_pct":maxdd*100})
    hold=[]
    for sd in holdout_seeds:
        e=Economy(Config(seed=int(sd))); ms,cs=e.states(); arr=[]
        for _ in range(oos_blocks):
            ma=[ag.act(st,0.0) for ag,st in zip(markets,ms)]; ca=cb.act(cs,0.0)
            (ms,cs),_,_,info=e.step(ma,ca); arr.append(info)
        pas=run_passive(int(sd),oos_blocks); end=arr[-1]["capital_adjusted_hardnav"]
        hold.append({"seed":int(sd),"return_pct":(end/10000-1)*100,"passive_return_pct":pas["return_pct"],
                     "alpha_vs_passive_pct":(end/pas["end"]-1)*100,
                     "max_drawdown_pct":max(x["drawdown"] for x in arr)*100,
                     "passive_max_drawdown_pct":pas["max_drawdown_pct"],
                     "fees":arr[-1]["fees"],"bridge_volume":arr[-1]["bridge_volume"]})
    al=[x["alpha_vs_passive_pct"] for x in hold]
    ddi=[x["passive_max_drawdown_pct"]-x["max_drawdown_pct"] for x in hold]
    return {"mode":"DQN_MARKET_CB","train_seeds":list(train_seeds),"blocks_per_seed":blocks_per_seed,
            "holdout_seeds":list(holdout_seeds),"oos_blocks":oos_blocks,
            "architecture":{"market_agents":6,"market_state":20,"market_actions":32,"cb_state":12,"cb_actions":90,
                            "network":"64-64","gamma":.99,"replay":20000,"batch":48,"target_sync":500,"update_every":4},
            "train":train,"holdouts":hold,
            "aggregate":{"positive_alpha_count":sum(x>0 for x in al),"holdout_count":len(hold),
                         "mean_alpha_pct":float(np.mean(al)),"median_alpha_pct":float(np.median(al)),
                         "worst_alpha_pct":float(np.min(al)),"drawdown_better_count":sum(x>0 for x in ddi),
                         "mean_drawdown_improvement_pct_points":float(np.mean(ddi)),
                         "worst_dqn_drawdown_pct":float(max(x["max_drawdown_pct"] for x in hold))},
            "models":(markets,cb)}

def self_test():
    e=Economy(Config(seed=123))
    assert len(e.market_state(PAIR_NAMES[0]))==20 and len(e.cb_state())==12
    for ext in ("BTC","ETH","WETH"):
        for tok in ("SYNA","SYNR"):
            x=Economy(Config(seed=1)); assert x.route(ext,tok,100)>0
            y=Economy(Config(seed=1)); assert y.route(tok,ext,50)==0
            y.synthetic[ext]=100; assert y.route(tok,ext,50)>0
    x=Economy(Config(seed=1)); f=x.external_flow; x.apply_cb(44); assert x.external_flow==f
    x=Economy(Config(seed=1)); x.synthetic["BTC"]=10; assert x.route("SYNA","BTC",1000)<=10
    return {"status":"PASS","checks":5}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--self-test",action="store_true"); ap.add_argument("--output",default="p9_dqn_report.json")
    ap.add_argument("--train-seeds",default="1,2,3"); ap.add_argument("--holdout-seeds",default="77,101,2026,42,31415")
    ap.add_argument("--train-blocks",type=int,default=400); ap.add_argument("--oos-blocks",type=int,default=300)
    args=ap.parse_args()
    if args.self_test:
        print(json.dumps(self_test(),indent=2)); return
    r=train_multiseed(tuple(map(int,args.train_seeds.split(","))),args.train_blocks,tuple(map(int,args.holdout_seeds.split(","))),args.oos_blocks)
    models=r.pop("models")
    with open(args.output,"w") as f: json.dump(r,f,indent=2)
    torch.save({"market":[a.q.state_dict() for a in models[0]],"cb":models[1].q.state_dict()},args.output.replace(".json",".pt"))
    print(json.dumps(r["aggregate"],indent=2))
if __name__=="__main__": main()
