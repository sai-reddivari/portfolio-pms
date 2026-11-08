"""Explicit public projection and buildless read-only dashboard."""
import html
from .store import canonical


def project(snapshot_id, payload):
    # Never serialize arbitrary upstream provenance, prompts or internal columns.
    return {'snapshot_id': snapshot_id, 'mode': payload['mode'],
            'data_date': payload['session_dates'][-1], 'research_commit': payload['research_commit'],
            'status': 'RECONCILED FIXTURE — NOT LIVE', 'limitations': payload['limitations'],
            'accounts': [{'name': a['account'], 'policy_status': a['policy_status'],
                'series': [{k: row[k] for k in ['date', 'nav', 'cash', 'daily_pnl',
                    'cumulative_pnl', 'option_value', 'transaction_cost']} for row in a['ledger']]
                } for a in payload['accounts']]}


def render(public):
    e = lambda x: html.escape(str(x))
    sections = []
    for a in public['accounts']:
        rows = ''.join('<tr>' + ''.join(f'<td>{e(row[k][:10]) if k == "date" else e(format(row[k], ",.2f"))}</td>'
                        for k in ['date','nav','cash','daily_pnl','option_value']) + '</tr>' for row in a['series'])
        sections.append(f'<section><h2>{e(a["name"])}</h2><p>{e(a["policy_status"])}</p><div class="scroll"><table><thead><tr><th>Date</th><th>NAV</th><th>Cash</th><th>Daily PnL</th><th>Model option value</th></tr></thead><tbody>{rows}</tbody></table></div></section>')
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Paper portfolio | synthetic integration</title><style>
body{{margin:0;background:#f3f5f2;color:#172e30;font:16px/1.55 system-ui,sans-serif}}main{{max-width:1040px;margin:56px auto;padding:0 24px}}header{{border-top:5px solid #207363;padding-top:20px}}h1{{font-size:42px;line-height:1.1;max-width:650px}}.eyebrow{{font-size:12px;letter-spacing:.12em;font-weight:700}}.notice{{background:#fff2d1;padding:18px;border-left:4px solid #bb7919}}section{{background:white;padding:24px;margin:24px 0;border:1px solid #d9e2dc}}h2{{font-size:21px}}table{{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}}th,td{{text-align:right;padding:12px;border-bottom:1px solid #e0e7e1}}th:first-child,td:first-child{{text-align:left}}.scroll{{overflow-x:auto}}code{{overflow-wrap:anywhere}}footer{{font-size:13px;color:#516561}}a{{color:#126955}}@media(max-width:600px){{h1{{font-size:32px}}section{{padding:14px}}}}
</style><main><header><p class="eyebrow">PAPER PORTFOLIO / DEVELOPMENT FIXTURE</p><h1>From a hedge policy to an auditable portfolio.</h1><p>One core book. Two demonstration accounts. Shared upstream accounting.</p></header>
<p class="notice"><strong>{e(public['status'])}</strong><br>Fixture valuation date: {e(public['data_date'])}. This is a synthetic replay, including future-dated fixture observations. It is not today's market record, a running fund or a deployed pilot.</p>
<section><h2>What the portfolio is doing</h2><p>A fixed rules-based fixture holds seven long and three short synthetic names. Independent gross and concentration checks run before the shared research replay. A control keeps the equity book alone; the second account adds a small model put on one name. This demonstrates integration, not superior performance or the final grouped/ML/variance research policy.</p><p>Targets dated November 4 precede the first simulated fill on November 5. All prices are synthetic. All option values are European model marks; all fills are simulated.</p></section>
{''.join(sections)}<section><h2>Operating status and limits</h2><ul>{''.join('<li>'+e(x)+'</li>' for x in public['limitations'])}</ul><p>No next scheduled run: scheduler is not deployed. Operational freshness monitoring remains disabled; an HTTP health check must not label this historical fixture current.</p></section>
<footer><p>Source commit: <code>{e(public['research_commit'])}</code><br>Snapshot SHA-256: <code>{e(public['snapshot_id'])}</code></p><p><a href="snapshot.json">Download the allowlisted synthetic snapshot</a></p></footer></main></html>'''
