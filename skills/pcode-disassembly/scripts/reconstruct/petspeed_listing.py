"""Bridge the exact-runtime PETSpeed evidence report to a numbered reading copy."""
from collections import Counter
from importlib import import_module

from formats import module

RUNTIME = '3b13c8c451db362fdd3fafa91832f3484dd9fd3eac0fcff792b82e9484a9131a'
SCHEMA = 'petspeed-numbered-reading-v1'


def backend(name):
    return import_module(module('petspeed').__name__ + '.decompy_compat.' + name)


def display(text):
    # Never emit terminal control bytes; the PRG is made from tokens, not display text.
    return ''.join(c if 32 <= ord(c) <= 126 else f'{{0x{ord(c):02X}}}' for c in text)


def check_effect_counts(instructions, lines):
    """A necessary check, not a proof of call identity, order, or reachability."""
    # Opcode -> BASIC V2 token. Count instructions, not bytes inside operands.
    pairs = {0xBB: (0xBB, 'RND'), 0xC2: (0xC2, 'PEEK'), 0xB8: (0xB8, 'FRE')}
    expected = Counter(item['opcode'] for item in instructions)
    actual = Counter()
    for line in lines:
        quoted = data = False
        for b in line.body:
            if b == 0x22:
                quoted = not quoted
            elif not quoted:
                if b == 0x3A:
                    data = False
                elif not data:
                    if b == 0x8F:  # REM to end of line
                        break
                    if b == 0x83:  # DATA to next unquoted colon
                        data = True
                    else:
                        actual[b] += 1
    for op, (token, name) in pairs.items():
        if expected[op] != actual[token]:
            raise ValueError(f'numbered reading changes {name} call count: {expected[op]} p-code sites, {actual[token]} emitted')


def check_target_entries(instructions, targets):
    """A direct entry at a scalar assignment has no proved incoming FAC value."""
    by_pc = {item['address']: item['opcode'] for item in instructions}
    for target in targets:
        op = by_pc.get(target.address)
        if op is None:
            raise ValueError('numbered reading branch disagrees with canonical instruction boundaries')
        if 0x60 <= op <= 0x7F or op == 0xFF:
            raise ValueError(f'numbered reading cannot prove incoming value at branch-target store ${target.address:04X}')


def retained_data(image):
    """Keep compiled field bytes separate from regenerated BASIC line grouping."""
    start, end = image.sections[:2]
    pos = start
    records = []
    for item in image.data_items():
        field = item.text.encode('latin-1')
        encoded = bytes([item.tag]) + field + item.numeric
        if pos + len(encoded) >= end or image.payload(pos, len(encoded)) != encoded:
            raise ValueError('numbered reading DATA record disagrees with retained bytes')
        records.append({'address': pos, 'tag': item.tag, 'textHex': field.hex(),
                        'numericHex': item.numeric.hex()})
        pos += len(encoded)
    if pos != end - 1:
        raise ValueError('numbered reading DATA records do not reach the footer')
    return {'records': records, 'footer': {'address': pos, 'byte': image.byte(pos)}}


def build(prg, decoded):
    if decoded.get('runtimeSha256') != RUNTIME or not decoded.get('completeCodeDecode'):
        raise ValueError('numbered PETSpeed reading requires the exact supported runtime and a complete instruction decode')
    core, basic = backend('petspeed_core'), backend('basic_v2')
    # This VM stores the explicit leading accumulator bit.  The compact
    # formatter assumes normalized numbers; do not silently supply that bit.
    for row in decoded['instructions']:
        if row['opcode'] in (0x43, 0x4C):
            raw = bytes.fromhex(row['bytes'])
            if raw[1] and not raw[2] & 0x80:
                raise ValueError(f"unnormalized floating literal at ${row['address']:04X}")
    image = core.read_image(prg)
    parsed = backend('speedcode').instructions(image)
    # The compact parser omits only the second of the two terminal ENDs.
    # A difference elsewhere (including a contextual INPUT modifier) is not
    # a license to present two incompatible partitions of the same bytes.
    rows = decoded['instructions']
    if (not rows or rows[-1]['bytes'] != 'd3' or
            [(p.address, p.opcode, p.after) for p in parsed] !=
            [(r['address'], r['opcode'], r['address'] + r['size']) for r in rows[:-1]]):
        raise ValueError('numbered reading parser disagrees with canonical instruction widths')
    translated = core.decompile_with_evidence(prg)
    lines = translated.lines
    check_effect_counts(decoded['instructions'], lines)
    check_target_entries(decoded['instructions'], translated.targets)
    if not lines or any(a.number >= b.number for a, b in zip(lines, lines[1:])):
        raise ValueError('numbered reading has missing or unordered generated lines')
    return {'schema': SCHEMA,
            'scope': 'Generated BASIC V2 reading copy. Names, line numbers, dimensions, and statement grouping are reconstructed, not original. Execution equivalence is not established.',
            'data': retained_data(image),
            'targetPolicy': 'First statement emitted at or after the encoded target; an emission site is not proof that entering mid-expression is equivalent.',
            'targets': [{'address': t.address, 'number': t.line_number, 'emissionAddress': t.emission_address,
                         'policy': t.policy} for t in translated.targets],
            'lines': [{'number': s.line.number, 'text': display(basic.detokenize(s.line.body)),
                       'tokenHex': s.line.body.hex(), 'emissionAddress': s.emission_address,
                       'targetAddresses': list(s.branch_targets), 'generated': s.generated}
                      for s in translated.statements]}


def serialize(report):
    view = report.get('readingView', {})
    if view.get('schema') != SCHEMA:
        raise ValueError(report.get('readingRefusal') or 'No tokenized BASIC export for this runtime')
    basic = backend('basic_v2')
    return basic.write_program([basic.BasicLine(row['number'], bytes.fromhex(row['tokenHex'])) for row in view['lines']])
