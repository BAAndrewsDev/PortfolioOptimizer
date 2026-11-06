"""Regression checks for policy semantics, using hand-checkable portfolios."""
import unittest
from types import SimpleNamespace
import numpy as np
import pandas as pd
from gurobipy import GRB
import model
from data.fetch_data import dividend_yield_pct

class PolicyTests(unittest.TestCase):
    def portfolio(self, n=3, defensive=None):
        tickers = list('ABC')[:n]
        return SimpleNamespace(tickers=tickers, mu=np.array([.3,.2,.1][:n]),
            cov=np.eye(n), meta=pd.DataFrame({'defensive': defensive or [0]*n,
            'asset_class':['US Equity']*n,'div_yield_pct':[0]*n},index=tickers))

    def params(self, **changes):
        raw=dict(tickers=['SPY','QQQ','BND'], mode='lp', lambda_=0,
            long_only=True,max_single=0,min_lowrisk=0,max_equity=0,
            min_dividend=0,max_holdings=None,min_position=None)
        raw.update(changes)
        return model.clean_params(raw)[0]

    def optimize(self, p, data=None):
        m,w,*_=model._build_model(data or self.portfolio(),p)
        m.optimize()
        return m,w

    def test_shorting_and_signed_output(self):
        m,w=self.optimize(self.params(long_only=False))
        self.assertEqual(m.Status,GRB.OPTIMAL)
        self.assertAlmostEqual(w['C'].X,-1)
        result=model.solve(dict(tickers=['SPY','QQQ','TLT'],mode='lp',long_only=False,
            max_single=0,min_lowrisk=0,max_equity=0,min_dividend=0))
        self.assertTrue(any(v<0 for v in result['weights'].values()))
        self.assertAlmostEqual(sum(result['weights'].values()),1,places=5)

    def test_minimum_alone_is_enforced(self):
        p=self.params(min_position=40)
        self.assertEqual(p['min_position'],.4)
        m,w=self.optimize(p)
        m.addConstr(w['A']<=.7); m.optimize()
        self.assertAlmostEqual(w['A'].X,.6)
        self.assertAlmostEqual(w['B'].X,.4)

    def test_maximum_holdings_does_not_require_all(self):
        p=self.params(max_holdings=2,min_position=60)
        self.assertEqual(p['min_position'],.6)
        m,w=self.optimize(p)
        self.assertEqual(m.Status,GRB.OPTIMAL)
        self.assertAlmostEqual(w['A'].X,1)
        m.addConstrs((v<=.7 for v in w.values())); m.optimize()
        self.assertEqual(m.Status,GRB.INFEASIBLE)

    def test_signed_minimum_and_cardinality(self):
        m,w=self.optimize(self.params(long_only=False,max_holdings=2,min_position=40))
        m.addConstr(w['C']<=-.1); m.optimize()
        self.assertEqual(m.Status,GRB.INFEASIBLE)
        m,w=self.optimize(self.params(long_only=False,min_position=40))
        m.addConstr(w['C']<=-.1); m.optimize()
        self.assertLessEqual(w['C'].X,-.4+1e-6)
        self.assertTrue(all(abs(v.X)<1e-6 or abs(v.X)>=.4-1e-6 for v in w.values()))

    def test_or_relaxation_allows_negative_defensive_exposure(self):
        p=self.params(long_only=False,max_single=100,min_lowrisk=100,logic='or')
        m,w=self.optimize(p,self.portfolio(defensive=[0,0,1]))
        self.assertAlmostEqual(w['C'].X,-1)

    def test_joint_or_cost(self):
        p=dict(tickers=['SPY','QQQ','BND'],mode='lp',max_single=40,
            min_lowrisk=60,max_equity=0,min_dividend=0,logic='or')
        result=model.solve(p)
        labels=[r['rule'] for r in result['rule_costs']]
        self.assertIn('Rule A OR B: joint policy',labels)
        self.assertNotIn('Rule B: defensive floor',labels)

    def test_frontier_respects_holding_limit_and_or(self):
        p=dict(tickers=['SPY','QQQ','BND'],mode='qp',lambda_=3,long_only=True,
            max_single=40,min_lowrisk=60,max_equity=0,min_dividend=0,
            logic='or',max_holdings=1,min_position=50)
        f=model.frontier(p,n_points=3)
        curve=f['df'].query("series == 'With your guidelines'")
        self.assertFalse(curve.empty) # A impossible, B satisfied by BND alone.
        expected=model.load_data().subset(['BND']).mu[0]*100
        self.assertTrue(np.allclose(curve.ret_pct,expected,atol=1e-4))

    def test_dividend_percentage_units(self):
        self.assertAlmostEqual(dividend_yield_pct(4,100,9),4)
        self.assertAlmostEqual(dividend_yield_pct(.42,100,9),.42)
        self.assertEqual(dividend_yield_pct(0,100,9),0)
        for annual,price in [(None,100),(4,0),(float('nan'),100)]:
            self.assertEqual(dividend_yield_pct(annual,price,9),9)

if __name__=='__main__':
    unittest.main()
