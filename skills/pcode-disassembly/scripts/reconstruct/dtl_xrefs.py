"""DTL static navigation from decoded operands; no dataflow or reachability proof.

Only explicit typed operand references get variable roles. Interpreter/native
sites and runtime-selected loop/formal effects remain separately visible. Calls
are encoded GOSUB targets, not inferred routine extents or matched returns.
"""
from collections import defaultdict
from copy import deepcopy
import re


SCOPE = ('Static decoded-operand navigation, not a complete access/call graph. '
         'Embedded BASIC, native memory effects, runtime-selected variables and '
         'descriptor bindings are not resolved; reachability, routine extents '
         'and return pairing are not proved.')
TYPED_ACCESS = re.compile(r'(LOAD|STORE)_(REAL|INTEGER|STRING)_(SCALAR|ARRAY)(?:_LONG)?')
LOOPS = {'FOR_REAL': 'real', 'FOR_REAL_STEP': 'real',
         'FOR_INTEGER': 'integer', 'FOR_INTEGER_STEP': 'integer'}


def valid_offset(value):
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 65535


def site(row):
    """Copy exact operand/address provenance, never borrow mutable report fields."""
    return {key: deepcopy(row[key]) for key in
            ('address', 'region', 'mnemonic', 'grammar', 'control', 'length', 'bytes', 'operands', 'targets')
            if key in row}


def analyze_xrefs(report, array_index):
    rows = report['instructions']; at = {r['address']: r for r in rows}
    scalar_records = defaultdict(list)
    for record in report.get('scalars', []):
        scalar_records[record['offset']].append(record)
    arrays = {d['descriptorOffset']: d for d in array_index['descriptors']}
    variables = {}; rejected = []; dynamic = []; opaque = []; cursor = []; system = []
    calls = []; targets = {}; returns = []

    def variable(namespace, offset):
        key = (namespace, offset)
        if key in variables:
            return variables[key]
        name = kind = rank = None; reasons = []
        provenance = 'unresolved'; records = []; declarations = []; registrations = []
        if namespace == 'scalar':
            records = scalar_records.get(offset, [])
            if len(records) == 1:
                record = records[0]; kind = record.get('type'); candidate = record.get('name', '')
                pattern = {'real': r'[A-Z][A-Z0-9]?', 'integer': r'[A-Z][A-Z0-9]?%',
                           'string': r'[A-Z][A-Z0-9]?\$', 'function': r'FN [A-Z][A-Z0-9]?'}.get(kind)
                if pattern and re.fullmatch(pattern, candidate):
                    name = candidate; provenance = 'binary-scalar-record'
                else:
                    reasons.append('Scalar name/type is not a supported typed binary name.')
            else:
                reasons.append('Scalar record is missing or ambiguous.')
        else:
            descriptor = arrays.get(offset)
            if descriptor:
                declarations = descriptor['declarations']; registrations = descriptor['registrations']
                reasons.extend(descriptor['reasons'])
                if descriptor['status'] == 'associated':
                    name, kind, rank = descriptor['name'], descriptor['type'], descriptor['rank']
                    provenance = 'static-binary-DIM-association'
            else:
                reasons.append('Array descriptor has no static DIM association.')
        value = {'namespace': namespace, 'offset': offset, 'name': name, 'type': kind,
                 'rank': rank, 'nameProvenance': provenance, 'reasons': reasons,
                 'scalarRecords': deepcopy(records), 'declarations': list(declarations),
                 'registrations': list(registrations), 'sites': []}
        variables[key] = value
        return value

    def reference(row, namespace, offset, field, role, kind=None):
        record = {**site(row), 'operandField': field, 'offset': offset,
                  'role': role, 'accessType': kind, 'status': 'decoded-reference', 'reasons': []}
        if not valid_offset(offset):
            record.update(status='refused', reasons=['Missing or invalid variable/descriptor offset.'])
            rejected.append(record); return
        var = variable(namespace, offset)
        if var['name'] is None:
            record.update(status='unnamed-reference', reasons=list(var['reasons']))
        elif kind and var['type'] != kind:
            record.update(status='type-mismatch', reasons=['Typed operand disagrees with retained variable type.'])
        var['sites'].append(record)

    # Include retained declarations with no explicit uses, without calling them dead.
    for offset in scalar_records:
        if valid_offset(offset):
            variable('scalar', offset)
    for offset in arrays:
        if valid_offset(offset):
            variable('array', offset)

    for row in rows:
        n = row['mnemonic']; operands = row.get('operands', {}); value = operands.get('value')
        match = TYPED_ACCESS.fullmatch(n)
        if match:
            action, kind, namespace = match.groups()
            reference(row, namespace.lower(), value, 'value', 'read' if action == 'LOAD' else 'write', kind.lower())
        elif n == 'ARRAY_REGISTER':
            reference(row, 'array', value, 'value', 'descriptor-write')
        elif n in LOOPS:
            reference(row, 'scalar', value, 'value', 'loop-setup-reference', LOOPS[n])
        elif n == 'NEXT_NAMED':
            # Actual type/loop-stack selection is not inferred from source order.
            reference(row, 'scalar', value, 'value', 'implicit-read-write')
        elif n == 'DEF_FN':
            encoded = operands.get('descriptorOffset')
            offset = encoded + 3 if valid_offset(encoded) else None
            reference(row, 'scalar', offset, 'descriptorOffset + 3', 'descriptor-write', 'function')
            reference(row, 'scalar', operands.get('parameterOffset'), 'parameterOffset', 'formal-reference', 'real')
        elif n == 'FN_CALL':
            reference(row, 'scalar', value, 'value', 'descriptor-read', 'function')
        elif row.get('grammar') in ('var8', 'var16', 'array8', 'array16'):
            rejected.append({**site(row), 'status': 'unclassified',
                             'reasons': ['Operand-bearing instruction has no supported access role.']})

        if n in ('NEXT', 'FN_RETURN'):
            dynamic.append({**site(row), 'role': 'implicit-read-write' if n == 'NEXT' else 'formal-restore',
                            'reason': 'Runtime-selected loop variable/formal; no static storage target assigned.'})
        elif n in ('CLEAR_OR_RUN', 'RUN_BOOTSTRAP', 'INIT_DECODE', 'INIT_ENTER', 'VARIABLE_FILE'):
            dynamic.append({**site(row), 'role': 'runtime-state',
                            'reason': 'Runtime setup/reset/transfer, not expanded into individual variable accesses.'})

        if row.get('grammar') == 'basic_island':
            opaque.append({**site(row), 'reason': 'Embedded BASIC accesses/control are not parsed into this index.'})
            if operands.get('text', '').startswith('READ'):
                cursor.append({**site(row), 'role': 'embedded-READ',
                               'reason': 'Destinations and DATA cursor sequence not resolved.'})
        elif n in ('SYS', 'POKE', 'DIRECTIVE') or (
                n in ('FUNCTION', 'FUNCTION_F8') and operands.get('operation') in ('USR', 'PEEK')):
            opaque.append({**site(row), 'reason': 'Native/memory/runtime effects are not assigned to named variables or call targets.'})
        if n == 'RESTORE':
            cursor.append({**site(row), 'role': 'reset-DATA-cursor'})
        if n in ('FUNCTION', 'FUNCTION_F8') and operands.get('operation') in ('TI', 'TI$', 'ST', 'SET_TI$'):
            operation = operands['operation']
            system.append({**site(row), 'name': 'TI$' if operation == 'SET_TI$' else operation,
                           'role': 'write' if operation == 'SET_TI$' else 'read'})

        if n == 'RETURN':
            returns.append(site(row))
        if n not in ('GOSUB', 'ON_GOSUB'):
            continue
        encoded_targets = row.get('targets', [])
        reasons = []; length = row.get('length', row.get('size'))
        if n == 'GOSUB':
            if row.get('grammar') != 'xor_target' or row.get('control') != 'call' or length != 3 or len(encoded_targets) != 1:
                reasons.append('Inconsistent direct GOSUB target contract.')
        else:
            count = operands.get('count')
            if (row.get('grammar') != 'target_table' or row.get('control') != 'multi-branch' or
                    not valid_offset(count) or count > 252 or count != 2 * len(encoded_targets) or length != count + 2):
                reasons.append('Inconsistent ON GOSUB byte-count/table contract.')
        entries = []
        for ordinal, target in enumerate(encoded_targets, 1):
            target_row = at.get(target) if valid_offset(target) else None
            entries.append({'target': target, 'tableEntry': ordinal if n == 'ON_GOSUB' else None,
                            'targetRegion': target_row.get('region') if target_row else None,
                            'status': 'instruction-boundary' if target_row else 'unresolved-target'})
            if target_row is None:
                reasons.append('Encoded target is not a decoded instruction boundary.')
        call = {**site(row), 'entries': entries, 'status': 'refused' if reasons else 'decoded-targets',
                'reasons': list(dict.fromkeys(reasons))}
        calls.append(call)
        if not reasons:
            for entry in entries:
                target = entry['target']
                aggregate = targets.setdefault(target, {'target': target, 'region': entry['targetRegion'], 'callers': []})
                aggregate['callers'].append({'address': row['address'], 'region': row.get('region'),
                                            'mnemonic': n, 'tableEntry': entry['tableEntry']})

    ordered_variables = sorted(variables.values(), key=lambda v: (v['namespace'], v['offset']))
    return {'schema': 'dtl-static-xrefs-v1', 'scope': SCOPE, 'completeAccessGraph': False,
            'reachabilityProved': False, 'variables': ordered_variables, 'unclassifiedReferences': rejected,
            'dynamicSites': dynamic, 'opaqueSites': opaque, 'dataCursorSites': cursor,
            'systemVariableSites': system, 'callSites': calls, 'subroutineTargets': [targets[t] for t in sorted(targets)],
            'returnSites': returns, 'returnPairingProved': False,
            'notes': ['Read/write roles describe explicit typed operands only; subscript identity and aliasing are not resolved.',
                      'Loop setup is a reference, not an inferred initializer write; named NEXT is implicit read/write.',
                      'DEF formal-reference does not write the formal at definition time; FN_CALL save/bind/restore effects are not expanded.',
                      'Descriptor FN calls and definitions remain in functionIndex; they are not direct GOSUB edges.',
                      'Scalar records without explicit indexed sites are not proven unused or dead.',
                      'DATA cursor sites do not map READ fields to retained DATA or prove cursor order.']}


def render_xrefs(index):
    out = ['\n; DTL VARIABLE / SUBROUTINE INDEX — ' + index['scope']]

    def label(record):
        suffix = ('!' + record['status']) if record.get('status') in ('type-mismatch', 'unnamed-reference') else ''
        return f'L_{record["address"]:04X}[{record.get("region", "unknown")}]' + suffix

    def sites(title, records):
        for start in range(0, len(records), 8):
            out.append(';   ' + (title if start == 0 else ' ' * len(title)) + ': ' +
                       ', '.join(label(r) for r in records[start:start + 8]))

    for var in index['variables']:
        name = var['name'] or '(unnamed)'
        out.append(f'; {name} — {var["namespace"]} offset {var["offset"]}; {var["type"] or "unknown type"}; {var["nameProvenance"]}')
        roles = defaultdict(list)
        for record in var['sites']:
            roles[record['role']].append(record)
        if not roles:
            out.append(';   No explicit indexed sites; not proof of unused storage.')
        for role in sorted(roles):
            sites(role, roles[role])
        out.extend(';   ' + reason for reason in var['reasons'])
    out.append('; EXPLICIT GOSUB TARGETS / CALLERS (ON table entries are one-based positions)')
    for target in index['subroutineTargets']:
        out.append(f'; L_{target["target"]:04X}[{target["region"]}] callers:')
        for caller in target['callers']:
            ordinal = f' entry {caller["tableEntry"]}' if caller['tableEntry'] is not None else ''
            out.append(';   ' + label(caller) + ' ' + caller['mnemonic'] + ordinal)
    for call in index['callSites']:
        if call['status'] == 'refused':
            out.append('; REFUSED call at ' + label(call) + ': ' + '; '.join(call['reasons']))
    for title, key in [('Unpaired RETURN sites', 'returnSites'), ('Opaque interpreter/native sites', 'opaqueSites'),
                       ('Runtime-selected/setup sites', 'dynamicSites'), ('DATA cursor sites', 'dataCursorSites'),
                       ('System variable sites', 'systemVariableSites'), ('Unclassified/refused operand sites', 'unclassifiedReferences')]:
        sites(title, index[key])
    out.extend('; ' + note for note in index['notes'])
    return out
