"""Meaningful causality and fault containment checks for offline guard rules."""
import json
from pathlib import Path
import unittest
import numpy as np
from .guards import GuardConfig, SOURCE_NAMES, OnlineGuard, declared_candidates, replay
from .traj import DEFAULT_SELECTED, DEFAULT_RAW, load_episode, list_episodes


def synthetic(n=120):
    t=np.arange(n)*.05
    sources={}
    for i,s in enumerate(SOURCE_NAMES):
        T=np.broadcast_to(np.eye(4),(n,4,4)).copy()
        T[:,:3,3]=np.column_stack((.2*t,.03*np.sin(t),.01*t))*(1+.04*i)
        sources[s]={'T':T,'valid':np.ones(n,bool),'init_s':t[0]}
    return t,sources


class CausalityTests(unittest.TestCase):
    def test_future_poisoning_and_prefix_every_declared_arm(self):
        t,source=synthetic()
        for cfg in declared_candidates():
            for safe in ([False,True] if cfg.smooth_s else [False]):
                if safe:
                    cfg=GuardConfig(**dict(cfg.to_dict(),name=cfg.name+'-safe'))
                full=replay(t,source,cfg)
                for cut in (1,17,61):
                    prefix={s:dict(v,T=v['T'][:cut],valid=v['valid'][:cut]) for s,v in source.items()}
                    np.testing.assert_array_equal(full[:cut],replay(t[:cut],prefix,cfg),err_msg=cfg.name)
                    poison={s:dict(v,T=v['T'].copy(),valid=v['valid'].copy()) for s,v in source.items()}
                    for i,s in enumerate(SOURCE_NAMES):
                        poison[s]['T'][cut:,:3,3]=1e6*(i+1)
                        poison[s]['valid'][cut:]=False
                    np.testing.assert_array_equal(full[:cut],replay(t,poison,cfg)[:cut],err_msg=cfg.name)

    def test_online_matches_batch_absolute_and_increment(self):
        t,source=synthetic(45)
        for mode in ('absolute','increment'):
            cfg=GuardConfig(name='test-safe',mode=mode,smooth_s=.5)
            batch=replay(t,source,cfg)
            online=OnlineGuard(cfg)
            for k,tk in enumerate(t):
                observation={s:{'T':v['T'][k],'valid':v['valid'][k],'init_s':v['init_s']} for s,v in source.items()}
                _,pose=online.step(tk,observation)
                np.testing.assert_array_equal(batch[k],pose)

    def test_safe_smoothing_rejects_current_source_jump(self):
        t,source=synthetic()
        # Initially prefer VINS, then simulate a catastrophic VINS pose jump.
        source['openvins']['T'][:,:3,3]=source['vins']['T'][:,:3,3]
        source['vins']['T'][60:,:3,3]+=1e6
        cfg=GuardConfig(name='fault-safe',blend=0.,smooth_s=.5)
        out=replay(t,source,cfg)
        self.assertLess(np.max(np.linalg.norm(np.diff(out[:,:3,3],axis=0),axis=1)),.1)
        self.assertTrue(np.isfinite(out).all())

    def test_real_saved_stream_future_poisoning(self):
        episodes=list_episodes()
        # Static, moving-start, and known catastrophic VIO episode.
        names=[episodes[0],next(e for e in episodes if e.startswith('fastmid-')),
               'fast-ProcTHOR-Train-63-02']
        cfg=GuardConfig(**json.loads((Path(__file__).parent/'selected_config_safe.json').read_text())['arm'])
        for name in names:
            data=load_episode(DEFAULT_SELECTED,DEFAULT_RAW,name)
            t,src=data['t'],data['sources']
            full=replay(t,src,cfg)
            for cut in (600, min(1200,len(t))):
                truncated={s:dict(v,T=v['T'][:cut],valid=v['valid'][:cut]) for s,v in src.items()}
                np.testing.assert_array_equal(full[:cut],replay(t[:cut],truncated,cfg),err_msg=name)
                poisoned={s:dict(v,T=v['T'].copy(),valid=v['valid'].copy()) for s,v in src.items()}
                for i,s in enumerate(SOURCE_NAMES):
                    poisoned[s]['T'][cut:,:3,3]=1e8*(i+1)
                    poisoned[s]['valid'][cut:]=False
                np.testing.assert_array_equal(full[:cut],replay(t,poisoned,cfg)[:cut],err_msg=name)

if __name__=='__main__':
    unittest.main()
