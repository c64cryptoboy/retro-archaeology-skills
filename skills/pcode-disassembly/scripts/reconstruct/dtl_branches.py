"""Narrow DTL false-test edge normalization for the reading view only.

IF_SKIP_FALSE preserves a false typed value on its direct false edge under the
supported runtime's ordinary no-STOP path. That edge may bypass another such
test. This is not arbitrary stack propagation, runnable-code optimization or a
claim about hidden native entries, asynchronous mutation or STOP polling.
"""
from collections import defaultdict


SCOPE = ('Reading-view false-edge forwarding under the evidenced DTL normal no-STOP '
         'path and decoded explicit CFG. Original instructions/targets are unchanged. '
         'No arbitrary join-state, hidden native-entry, timing or asynchronous-state proof.')


def explicit_targets(row):
    values = row.get('operands', {})
    targets = set(row.get('targets', [])) | set(values.get('targets', []))
    for key in ('target', 'bodyTarget', 'skipTarget'):
        if key in row:
            targets.add(row[key])
    for key in ('target', 'body', 'skip', 'bodyEntry'):
        if key in values:
            targets.add(values[key])
    return targets


def analyze_false_tests(report):
    rows = report['instructions']
    at = {r['address']: r for r in rows}
    incoming = defaultdict(list)
    for r in rows:
        for target in explicit_targets(r):
            incoming[target].append(r)

    def valid_test(r):
        targets = r.get('targets', [])
        if (r['mnemonic'] != 'IF_SKIP_FALSE' or r.get('control') != 'conditional' or
                r.get('grammar') != 'relative8' or r.get('length') != 2 or len(targets) != 1):
            return False
        address, target = r['address'], targets[0]
        region = r.get('region')
        if (region is None or target not in at or address + 2 not in at or
                at[target].get('region') != region or at[address + 2].get('region') != region or
                not 2 <= target - address <= 255 or explicit_targets(r) != {target}):
            return False
        return r.get('bytes', '').lower() == bytes([0x4f, target - address]).hex()

    joins = []
    for i, r in enumerate(rows):
        address = r['address']
        if r['mnemonic'] != 'IF_SKIP_FALSE' or not incoming[address]:
            continue
        reasons = []
        if not valid_test(r):
            reasons.append('Join false-test encoding/forward-target/region contract is inconsistent.')
        if any(not valid_test(p) or p['address'] >= address or
               p.get('region') != r.get('region') for p in incoming[address]):
            reasons.append('Incoming edge is not a same-region forward IF false edge.')
        previous = rows[i - 1] if i else None
        if (previous is None or previous['address'] + previous.get('length', 0) != address or
                previous.get('region') != r.get('region') or
                previous.get('control') not in ('fallthrough', 'descriptor-indirect-call')):
            reasons.append('No contiguous ordinary fallthrough value producer before this test.')
        joins.append({'address': address, 'falseTarget': next(iter(r.get('targets', [])), None),
                      'incoming': [p['address'] for p in incoming[address]],
                      'predecessor': previous['address'] if previous else None,
                      'status': 'candidate' if not reasons else 'unresolved', 'reasons': reasons})
    return {'schema': 'dtl-false-test-joins-v1', 'scope': SCOPE, 'joins': joins, 'forwardedEdges': []}


def forwarded_edges(index, enabled):
    """Only enabled, strictly forward joins can be elided from a reading edge."""
    joins = {j['address']: j for j in index['joins'] if j['address'] in enabled}
    edges = {}
    for address, join in joins.items():
        through = []
        target = address
        while target in joins:
            through.append(target)
            following = joins[target]['falseTarget']
            if following <= target:
                raise ValueError('non-forward DTL false-test chain')
            target = following
        for source in join['incoming']:
            edges[source] = {'source': source, 'encodedTarget': address,
                             'readingTarget': target, 'through': through}
    return edges


def render_false_tests(index):
    if not index['joins']:
        return []
    lines = ['\n; DTL FALSE-TEST JOINS', '; ' + index['scope']]
    for j in index['joins']:
        lines.append(f'; L_{j["address"]:04X} [{j["status"]}]; incoming: ' +
                     ', '.join(f'L_{a:04X}' for a in j['incoming']))
        lines.extend(';   ' + reason for reason in j['reasons'])
    for edge in index['forwardedEdges']:
        lines.append(f'; false edge L_{edge["source"]:04X}: encoded L_{edge["encodedTarget"]:04X}; '
                     f'reading target L_{edge["readingTarget"]:04X}; through ' +
                     ', '.join(f'L_{a:04X}' for a in edge['through']))
    return lines
