"""Call the exact upstream replay. Never reproduce its accounting implementation."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def verified_source(path):
    root = Path(path).resolve()
    lock = json.loads((ROOT / 'research.lock.json').read_text())
    actual = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in (root / 'src').rglob('*.py')}
    if actual != lock['files']:
        raise ValueError('Research dependency does not match the pinned source manifest')
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(root / 'src'))
    return lock['source_commit']


def run_fixture(source):
    commit = verified_source(source)
    import pandas as pd
    from hedging_harness.replay import OptionPosition, replay
    # Complete path is available only because this is a declared synthetic replay.
    dates = pd.to_datetime(['2026-11-05', '2026-11-06', '2026-11-09', '2026-11-10'])
    prices = pd.DataFrame({f'SYN{i:02}': [100+i, 101+i, 96+i, 98+i]
                           for i in range(10)}, index=dates)
    targets = {name: (10 if i < 7 else -5) for i, name in enumerate(prices.columns)}
    capital = 10000.0
    # Independent pre-trade limits, using fixture inception marks and fixed targets.
    notionals = {k: v * float(prices.iloc[0][k]) for k, v in targets.items()}
    if sum(abs(x) for x in notionals.values()) / capital > 1.0:
        raise ValueError('Gross exposure limit')
    if max(abs(x) for x in notionals.values()) / capital > .15:
        raise ValueError('Concentration limit')
    accounts = []
    for policy in ['unhedged-control-v1', 'synthetic-put-example-v1']:
        positions = [] if policy.startswith('unhedged') else [OptionPosition(
            instrument_id='SYN00-PUT', underlying='SYN00', kind='put', strike=100,
            expiry=dates[-1], quantity=10, volatility=.25)]
        result = replay(prices, positions, equity_holdings=targets,
                        initial_capital=capital, rate=0, cost_bps=2,
                        liquidate_at_end=False, hedge_options=False,
                        session_calendar=dates, data_label='Synthetic fixture v1; not observed prices')
        # Assertions are independent checks, not a second state-transition engine.
        import numpy as np
        ledger = result.ledger
        np.testing.assert_allclose(ledger.nav, ledger.cash + ledger.core_equity_value
                                   + ledger.hedge_stock_value + ledger.option_value)
        def records(frame):
            return json.loads(frame.reset_index().to_json(orient='records', date_format='iso'))
        accounts.append({'account': policy, 'policy_status': 'demonstration-only; not promoted',
                         'initial_capital': capital, 'ledger': records(ledger),
                         'holdings': records(result.holdings), 'trades': records(result.trades),
                         'option_events': records(result.option_ledger),
                         'research_provenance': result.provenance})
    return {'schema': 1, 'mode': 'synthetic-replay', 'fixture': 'ten-name-v1',
            'research_commit': commit, 'decision_date': '2026-11-04',
            'session_dates': [str(d.date()) for d in dates], 'targets': targets,
            'limits': {'gross_max': 1, 'name_max': .15, 'passed': True},
            'accounts': accounts, 'reconciled': True,
            'limitations': ['No deployment or live scheduler', 'No LLM or broker calls',
                'Upstream session-based financing; rate zero in this fixture',
                'No calendar accrual, corporate-action or incremental-ledger claim',
                'Options use European model marks and simulated cashflows',
                'Policy is a demonstration fixture, not a research-selected recommendation']}
