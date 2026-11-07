"""Qualified DTL runtime descriptions and literal/variable SYS navigation.

This is presentation/provenance, not runtime mode propagation or native analysis.
Unknown expressions are retained, not evaluated or resolved through assignments.
"""
from collections import defaultdict
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
import re

from dtl_xrefs import site, valid_offset

RUNTIME_SCOPE = ('Saved bytes and decoded directive names only. The associated RTL and normal entry path are assumed; '
                 'live flags, initialization, later STOP/POKE modes and native/header mutation are not proved.')
SYS_SCOPE = ('Static literal-address candidates, not a complete native call graph. No expression folding, alias '
             'resolution, reachability, effective runtime binding, callee semantics or return pairing is proved.')
INLINE_SCOPE = ('On the evidenced normal VARIABLE_FILE path, a nonzero saved header flag selects inline tables. '
                'Runtime skip/reuse flags may bypass setup; saved bytes do not prove live state or initialization.')


def raw_bytes(value):
    try:
        return bytes.fromhex(value) if isinstance(value, str) else None
    except ValueError:
        return None


def shape(row, opcode, grammar, control, length):
    raw = raw_bytes(row.get('bytes'))
    return (raw is not None and len(raw) == length and length > 0 and raw[0] == opcode and
            row.get('opcode', opcode) == opcode and row.get('length') == length and
            row.get('grammar') == grammar and row.get('control') == control and not row.get('targets'))


def variable_table_context(report, profile):
    """Read only an intact recognized saved header; never infer live loading."""
    result = {'status': 'unclassified', 'inlineFlag': None, 'flagAddress': None,
              'flagBytes': None, 'savedImageEnd': None, 'header': None, 'trailer': None,
              'runtimeStateProved': False, 'initializationProved': False,
              'scope': INLINE_SCOPE, 'reasons': []}
    regions = report.get('otherRegions', [])
    headers = [r for r in regions if r.get('name') == 'bootstrap/header']
    trailers = [r for r in regions if r.get('name') == 'trailer']
    layout = profile['layout']; base = layout['loadAddress']
    if len(headers) != 1 or len(trailers) != 1 or base != 0x0801:
        result['reasons'].append('Supported unique bootstrap/header and trailer context is absent.')
        return result
    header = headers[0]; raw = raw_bytes(header.get('bytes')); trailer = trailers[0]
    end = trailer.get('end'); end_offset = layout['imageEndOffset']
    trailer_raw = raw_bytes(trailer.get('bytes'))
    if (raw is None or header.get('start') != base or header.get('end') != base + len(raw) or
            len(raw) <= 0x85 or len(raw) < end_offset + 2 or
            hashlib.sha256(raw[:layout['bootstrapSize']]).hexdigest() != layout['bootstrapSha256'] or
            not isinstance(end, int) or isinstance(end, bool) or not base < end <= 65536 or
            trailer_raw is None or len(trailer_raw) != layout['trailerSize'] or
            trailer.get('start') != end-len(trailer_raw) or base+len(raw) > end-len(trailer_raw) or
            base + int.from_bytes(raw[layout['dataOffset']:layout['dataOffset']+2], 'little') != header['end'] or
            int.from_bytes(raw[end_offset:end_offset+2], 'little') != end):
        result['reasons'].append('Saved header/bootstrap, inline-flag extent or image-end evidence is inconsistent.')
        return result
    flag = raw[0x85]
    result.update(status='saved-inline' if flag else 'external-load-eligible', inlineFlag=flag,
                  flagAddress=base+0x85, flagBytes=raw[0x85:0x86].hex(), savedImageEnd=end,
                  header=deepcopy(header), trailer=deepcopy(trailer))
    if not flag:
        result['reasons'].append('Zero saved flag permits the external-load branch only if runtime skip/reuse checks do not bypass it; external VL decoding is unsupported.')
    return result


def describe_directive(row, profile):
    operands = row.get('operands', {}); selector = operands.get('selector')
    raw = raw_bytes(row.get('bytes')); spec = profile['opcodes']['5E']
    operation = spec['selectors'].get(f'{selector:02X}') if valid_offset(selector) and selector <= 255 else None
    valid = (shape(row, 0x5e, 'selector', 'fallthrough', 2) and operation is not None and
             raw[1] == selector and operands.get('operation') == operation)
    return {**site(row), 'status': 'described' if valid else 'refused',
            'operation': operation if valid else None,
            'heading': ('REM VM DIRECTIVE '+operation+f' (selector ${selector:02X})') if valid else 'REM VM DIRECTIVE',
            'reasons': [] if valid else ['Directive selector/operation/encoding contract is inconsistent; no description inferred.']}


def describe_variable_file(row, context):
    operands = row.get('operands', {}); count = operands.get('count')
    raw = raw_bytes(row.get('bytes')); payload = raw_bytes(operands.get('bytes'))
    valid = (valid_offset(count) and count <= 255 and
             shape(row, 0x5b, 'counted_bytes', 'fallthrough', count+2) and
             raw[1] == count and payload == raw[2:])
    heading = 'REM VM VARIABLE_FILE'; display = None
    if valid:
        # JSON display escapes are explicitly not original/runnable BASIC syntax.
        display = json.dumps(payload.decode('latin-1'), ensure_ascii=True)
        mode = {'saved-inline': 'saved flag selects normal inline-table path',
                'external-load-eligible': 'saved flag permits external-load path; live skip/reuse unresolved',
                'unclassified': 'saved variable-table mode not established'}[context['status']]
        heading += ' '+display+'; '+mode
    return {**site(row), 'status': 'described' if valid else 'refused', 'filenameHex': payload.hex() if valid else None,
            'filenameDisplay': display, 'savedMode': context['status'], 'heading': heading,
            'reasons': [] if valid else ['Counted filename/encoding contract is inconsistent; filename interpretation withheld.']}


def annotate_runtime(report, groups, profile):
    """Post-replay descriptions only; do not feed facts back into symbolic state."""
    context = variable_table_context(report, profile)
    directives = []; variables = []
    for group in groups:
        if not group['instructions']:
            continue
        row = group['instructions'][-1]; name = row['mnemonic']
        if name == 'DIRECTIVE':
            entry = describe_directive(row, profile); directives.append(entry)
            caveats = [RUNTIME_SCOPE] + entry['reasons']
        elif name == 'VARIABLE_FILE':
            entry = describe_variable_file(row, context); variables.append(entry)
            caveats = [INLINE_SCOPE] + entry['reasons'] + context['reasons']
        else:
            continue
        group['text'] = entry['heading']
        group['warnings'].extend(w for w in caveats if w not in group['warnings'])
    return {'schema': 'dtl-runtime-navigation-v1', 'scope': RUNTIME_SCOPE,
            'variableTableContext': context, 'directives': directives, 'variableFiles': variables,
            'modePropagationPerformed': False, 'runtimeIdentityProved': False}


def literal_value(row):
    """Exact supported literal bytes, including signed words and packed real values."""
    raw = raw_bytes(row.get('bytes')); operands = row.get('operands', {})
    if not raw:
        return None
    opcode = raw[0]; name = row.get('mnemonic')
    if 0x80 <= opcode <= 0x87 and name == 'INTEGER_SMALL':
        if shape(row, opcode, 'none', 'fallthrough', 1) and operands.get('constant') == opcode-0x80:
            return Fraction(opcode-0x80)
    elif opcode == 0x89 and name == 'INTEGER_BYTE':
        if shape(row, opcode, 'u8', 'fallthrough', 2) and operands.get('value') == raw[1] and operands.get('raw', raw[1:].hex()) == raw[1:].hex():
            return Fraction(raw[1])
    elif opcode == 0x8d and name == 'INTEGER_WORD':
        if (shape(row, opcode, 'u16be', 'fallthrough', 3) and
                operands.get('value') == int.from_bytes(raw[1:], 'big') and
                operands.get('signedValue') == int.from_bytes(raw[1:], 'big', signed=True) and
                operands.get('raw', raw[1:].hex()) == raw[1:].hex()):
            return Fraction(operands['signedValue'])
    elif opcode == 0x88 and name == 'REAL_LITERAL':
        if (shape(row, opcode, 'float5', 'fallthrough', 6) and
                operands.get('packedFloat') == raw[1:].hex() and
                operands.get('raw', raw[1:].hex()) == raw[1:].hex()):
            exp = raw[1]; mantissa = int.from_bytes(raw[2:], 'big')
            return Fraction(0) if exp == 0 else Fraction((1 << 31)+(mantissa & 0x7fffffff),1 << 31)*Fraction(2)**(exp-129)*(-1 if mantissa >> 31 else 1)
    return None


def sys_shape(row):
    from formats import module, profile
    raw = raw_bytes(row.get('bytes')); operands = row.get('operands', {})
    tail = raw_bytes(operands.get('rawTail'))
    return (raw is not None and len(raw) >= 2 and shape(row, 0x51, 'sys_basic_tail', 'native-call-dynamic-return', len(raw)) and
            raw[-1] == 0x3a and tail == raw[1:-1] and (not tail or tail[0] == 0x2c) and
            0 not in tail and 0x3a not in tail and tail.count(0x22) % 2 == 0 and
            operands.get('terminator') == 0x3a and operands.get('terminatorOwned') is True and
            operands.get('tail') == module('dtl').basic_text(tail, profile('dtl')['basicTokens']))


def record_sys(row, expression, rows_by_address):
    """Capture the consumed expression, without changing it or resolving aliases."""
    dependencies = sorted(expression.deps)
    result = {**site(row), 'expression': expression.text, 'expressionWarnings': list(expression.warnings),
              'expressionDependencies': dependencies, 'producerAddress': expression.producer,
              'producerSite': None, 'status': 'unresolved-expression', 'target': None, 'reasons': [],
              'returnCaveat': row.get('operands', {}).get('returnCaveat')}
    if not sys_shape(row):
        result.update(status='refused', reasons=['SYS tail/encoding contract is inconsistent; no target candidate assigned.'])
        return result
    producer = rows_by_address.get(expression.producer)
    if producer is not None:
        result['producerSite'] = site(producer)
    if (producer is None or dependencies != [expression.producer] or expression.warnings or
            expression.reference or not expression.stable or producer.get('region') != row.get('region') or
            producer['address'] >= row['address']):
        result['reasons'].append('Target is not one complete local literal-origin expression; aliases, joins, effects and arithmetic are not resolved.')
        return result
    value = literal_value(producer)
    if value is None:
        result['reasons'].append('Producer is not a consistent supported literal encoding.')
    elif value.denominator != 1 or not 0 <= value <= 65535:
        result.update(status='unsupported-literal', reasons=['Literal is not an unsigned 16-bit integral address; native conversion/wrapping is not assumed.'])
    elif expression.text != str(value.numerator):
        result.update(status='refused', reasons=['Literal value disagrees with the consumed expression.'])
    else:
        result.update(status='literal-address-candidate', target=value.numerator)
    return result


def build_sys_index(sites):
    targets = defaultdict(list)
    for record in sites:
        if record['status'] == 'literal-address-candidate':
            targets[record['target']].append({'address': record['address'], 'region': record.get('region')})
    return {'schema': 'dtl-native-call-navigation-v1', 'scope': SYS_SCOPE, 'sites': deepcopy(sites),
            'targets': [{'target': t, 'callers': targets[t]} for t in sorted(targets)],
            'completeCallGraph': False, 'runtimeBindingProved': False, 'returnPairingProved': False}


VARIABLE_SYS_SCOPE = ('Object-local input-variable references, not native target addresses. A mutable variable may '
                      'hold different values at different calls. No assignment/alias propagation, numeric conversion, '
                      'cross-object identity, initialization, reachability, effective callee or return pairing is proved.')
NUMERIC_LOADS = {'LOAD_REAL_SCALAR': (0x90, 'real', 1),
                 'LOAD_INTEGER_SCALAR': (0x91, 'integer', 1),
                 'LOAD_REAL_SCALAR_LONG': (0x94, 'real', 2),
                 'LOAD_INTEGER_SCALAR_LONG': (0x95, 'integer', 2)}


def scalar_sys_identity(report, producer):
    """Validate encoded numeric load and unique retained scalar name/type evidence."""
    form = NUMERIC_LOADS.get(producer.get('mnemonic'))
    if form is None:
        return None, 'Producer is not a supported numeric scalar load.'
    opcode, kind, width = form
    operands = producer.get('operands', {}); offset = operands.get('value')
    raw = raw_bytes(producer.get('bytes'))
    if (not valid_offset(offset) or offset >= 1 << (8*width) or
            not shape(producer, opcode, 'var8' if width == 1 else 'var16', 'fallthrough', width+1) or
            int.from_bytes(raw[1:], 'big') != offset or
            operands.get('raw', raw[1:].hex()) != raw[1:].hex()):
        return None, 'Numeric scalar load encoding and decoded offset disagree.'
    records = [r for r in report.get('scalars', []) if r.get('offset') == offset]
    if len(records) != 1:
        return None, 'Scalar record is missing or ambiguous.'
    record = records[0]; encoded = raw_bytes(record.get('raw')); name = record.get('name')
    if (encoded is None or len(encoded) != 7 or type(record.get('offset')) is not int or
            not valid_offset(record.get('address')) or record['address'] + 7 > 65536 or
            record.get('type') != kind or not isinstance(name, str) or
            not re.fullmatch(r'[A-Z][A-Z0-9]?' + ('%' if kind == 'integer' else ''), name)):
        return None, 'Unique scalar record lacks consistent supported numeric type/name/bytes.'
    a, b = encoded[:2]
    encoded_kind = ('integer' if a & 128 else 'string') if b & 128 else ('function' if a & 128 else 'real')
    encoded_name = chr(a & 127) + (chr(b & 127) if b & 127 else '') + ('%' if encoded_kind == 'integer' else '')
    if encoded_kind != kind or encoded_name != name or operands.get('name') != name:
        return None, 'Scalar raw name/type, load operand and retained name disagree.'
    return {'namespace': 'scalar', 'offset': offset, 'type': kind, 'name': name,
            'scalarRecord': deepcopy(record)}, None


def analyze_variable_sys(report, native_index):
    """Add navigation only after replay; do not alter the old numeric SYS index."""
    rows = report['instructions']; at = {r['address']: r for r in rows}
    entries = []; variables = {}
    for original in native_index['sites']:
        if original['target'] is not None:
            continue
        row = at.get(original['address']); producer = at.get(original['producerAddress'])
        entry = {'address': original['address'], 'region': original.get('region'),
                 'expression': original['expression'], 'status': 'unassociated',
                 'sysSite': site(original), 'producerSite': deepcopy(original['producerSite']),
                 'variable': None, 'reasons': []}
        reason = None; identity = None
        if (len(at) != len(rows) or row is None or site(row) != site(original) or not sys_shape(row)):
            reason = 'SYS provenance does not match a unique supported decoded site.'
        elif (original['status'] != 'unresolved-expression' or original['expressionWarnings'] or
              producer is None or original['expressionDependencies'] != [producer['address']] or
              original['producerSite'] != site(producer)):
            reason = 'Argument is not a complete single-producer variable expression.'
        elif (producer.get('region') != row.get('region') or row.get('region') is None or
              producer['address'] + producer.get('length', 0) != row['address']):
            reason = 'Scalar producer is not immediately adjacent in the same region.'
        else:
            identity, reason = scalar_sys_identity(report, producer)
            if identity is not None and original['expression'] != identity['name']:
                identity = None
                reason = 'Consumed expression is not the retained scalar name.'
        if reason:
            entry['reasons'].append(reason)
        else:
            entry.update(status='associated', variable=deepcopy(identity))
            key = (identity['namespace'], identity['type'], identity['offset'])
            if key not in variables:
                variables[key] = {**deepcopy(identity), 'callers': []}
            variables[key]['callers'].append({'address': row['address'], 'region': row['region'],
                                             'producerAddress': producer['address']})
        entries.append(entry)
    return {'schema': 'dtl-native-variable-navigation-v1', 'scope': VARIABLE_SYS_SCOPE,
            'sites': entries, 'variables': [variables[k] for k in sorted(variables)],
            'numericTargetsResolved': False, 'runtimeBindingProved': False, 'returnPairingProved': False}


def render_variable_sys(index):
    if not index['variables']:
        return []
    out = ['\n; DTL SYS INPUT VARIABLES / CALLERS — '+index['scope']]
    for variable in index['variables']:
        out.append(f'; Variable {variable["name"]} ({variable["type"]} scalar offset {variable["offset"]}); numeric target unresolved:')
        for caller in variable['callers']:
            out.append(f';   L_{caller["address"]:04X}[{caller["region"]}] from load L_{caller["producerAddress"]:04X}')
    out.append('; Original expressions, unresolved numeric targets, SYS tails and return caveats remain unchanged in nativeCallIndex.')
    return out


def render_runtime(index):
    context = index['variableTableContext']
    out = ['\n; DTL RUNTIME DIRECTIVES / SAVED VARIABLE TABLE — '+index['scope'],
           '; Saved variable-table mode: '+context['status']]
    if context['flagAddress'] is not None:
        out.append(f'; Header ${context["flagAddress"]:04X} = ${context["inlineFlag"]:02X}; saved image end ${context["savedImageEnd"]:04X}.')
    out.extend('; '+reason for reason in context['reasons'])
    out.append('; '+context['scope'])
    for record in index['directives'] + index['variableFiles']:
        out.append(f'; L_{record["address"]:04X}[{record.get("region", "unknown")}] '+record['heading'])
        out.extend('; '+reason for reason in record['reasons'])
    return out


def render_sys(index):
    out = ['\n; DTL SYS LITERAL TARGETS / CALLERS — '+index['scope']]
    for target in index['targets']:
        out.append(f'; Candidate ${target["target"]:04X} ({target["target"]}) callers:')
        for caller in target['callers']:
            out.append(f';   L_{caller["address"]:04X}[{caller.get("region", "unknown")}]')
    out.append('; UNGROUPED SYS SITES (expressions retained; not guessed targets)')
    for record in index['sites']:
        if record['target'] is None:
            out.append(f'; L_{record["address"]:04X}[{record.get("region", "unknown")}] {record["expression"]}: '+
                       record['status']+'; '+'; '.join(record['reasons']))
    out.append('; All exact SYS tails and callee-controlled cursor/return caveats remain in site records and owned p-code.')
    return out
