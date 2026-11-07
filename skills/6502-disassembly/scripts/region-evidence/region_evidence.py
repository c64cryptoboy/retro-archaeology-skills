#!/usr/bin/env python3
"""Check one bounded stream against a supplied consumer contract, without executing it."""
import argparse
from collections import deque
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

# Public helpers are read-only dependencies, including when imported from tests.
sys.dont_write_bytecode = True


def sha(data):
    return hashlib.sha256(data).hexdigest()


def integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{name} must be an integer in [{low}, {high}]')
    return value


def bounds(item, name):
    start = integer(item['start'], 0, 65535, name + '.start')
    end = integer(item['end'], start + 1, 65536, name + '.end')
    return start, end


def supplied(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError('evidence must be a nonempty supplied reference/description')
    return {'status': 'supplied-not-automatically-proved', 'reference': text}


def collection(value, name):
    if not isinstance(value, list):
        raise ValueError(f'{name} must be a list')
    return value


def verify_helper_cache(root):
    """Refuse conflicting imports rather than attribute other code to this root."""
    scripts = root / 'skills/pcode-disassembly/scripts'
    expected = {'formats': scripts / 'reconstruct/formats.py',
                'dis6502': root / 'shared/6502/dis6502.py'}
    for family in ('blitz', 'petspeed', 'basic64', 'dtl', 'speedcompiler'):
        filename = 'blitz_pcode.py' if family == 'blitz' else family + '.py'
        expected['_pcode_binary_' + family] = scripts / family / filename
    for name, path in expected.items():
        if name in sys.modules:
            origin = getattr(sys.modules[name], '__file__', None)
            if not origin or Path(origin).resolve() != path.resolve():
                raise ValueError(f'conflicting cached helper {name}; use a fresh process for this public root')


def load_helpers(root):
    """Load unchanged public helpers; one toolkit root per Python process."""
    root = Path(root).resolve()
    verify_helper_cache(root)
    paths = {
        'identifier': root / 'skills/pcode-disassembly/scripts/reconstruct/identify.py',
        'cfg': root / 'shared/6502/cfg6502.py',
    }
    modules = {'root': root}
    for name, path in paths.items():
        sys.path.insert(0, str(path.parent))
        try:
            spec = importlib.util.spec_from_file_location('_regional_' + name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            modules[name] = module
        finally:
            sys.path.pop(0)
    primary_files = list(paths.values()) + [
        paths['identifier'].with_name('identities.json'),
        paths['identifier'].with_name('formats.py'),
        paths['cfg'].with_name('dis6502.py'),
    ]
    return modules, {str(p.relative_to(root)): sha(p.read_bytes()) for p in primary_files}


def witness(item, raw, base):
    start, end = bounds(item, 'witness')
    evidence = supplied(item['evidence'])
    present = base <= start < end <= base + len(raw)
    actual = sha(raw[start - base:end - base]) if present else None
    return {'start': start, 'end': end, 'expectedSha256': item['sha256'],
            'actualSha256': actual, 'matched': present and actual == item['sha256'],
            'assertion': evidence}


def unknown_spans(start, end, owners):
    spans = []
    cursor = start
    while cursor < end:
        if cursor in owners:
            cursor += 1
            continue
        lo = cursor
        while cursor < end and cursor not in owners:
            cursor += 1
        spans.append({'start': lo, 'end': cursor})
    return spans


def check_stream(raw, base, region, contract):
    """Follow declared stream edges; refuse unknown, truncated, or overlapping records."""
    start, end = bounds(region, 'region')
    integer(base, 0, 65535, 'base')
    if not base <= start < end <= base + len(raw):
        raise ValueError('region is not wholly present in input')
    entries = collection(region['entries'], 'entries')
    declared_rules = collection(contract['rules'], 'rules')
    width = integer(contract['tokenBytes'], 1, 2, 'tokenBytes')
    if contract['byteOrder'] != 'little':
        raise ValueError('only little-endian tokens and absolute targets are supported')
    rules = {}
    for rule in declared_rules:
        token = integer(rule['token'], 0, (1 << (8 * width)) - 1, 'token')
        if token in rules:
            raise ValueError('duplicate token rule')
        operands = integer(rule['operandBytes'], 0, 16, 'operandBytes')
        if rule['flow'] not in ('next', 'stop', 'jump', 'branch'):
            raise ValueError('unsupported stream flow')
        supplied(rule['evidence'])
        if rule['flow'] in ('jump', 'branch'):
            integer(rule['targetOffset'], 0, operands - 2, 'targetOffset')
        elif 'targetOffset' in rule:
            raise ValueError('targetOffset requires jump or branch')
        rules[token] = rule
    if not entries:
        raise ValueError('at least one supplied stream entry is required')
    for entry in entries:
        integer(entry, start, end - 1, 'stream entry')
    queue, visited, owners, records, violations = deque(entries), set(), {}, [], []
    while queue:
        pc = queue.popleft()
        if pc in visited:
            continue
        visited.add(pc)
        if not start <= pc < end:
            violations.append({'at': pc, 'reason': 'edge-outside-region'})
            continue
        if pc in owners:
            violations.append({'at': pc, 'reason': 'edge-into-operand', 'owner': owners[pc]})
            continue
        if pc + width > end:
            violations.append({'at': pc, 'reason': 'truncated-token'})
            continue
        token = int.from_bytes(raw[pc - base:pc - base + width], 'little')
        rule = rules.get(token)
        if rule is None:
            violations.append({'at': pc, 'reason': 'unknown-token', 'token': token})
            continue
        finish = pc + width + rule['operandBytes']
        if finish > end:
            violations.append({'at': pc, 'reason': 'truncated-operands', 'requiredEnd': finish})
            continue
        conflicts = sorted({owners[a] for a in range(pc, finish) if a in owners})
        if conflicts:
            violations.append({'at': pc, 'reason': 'overlapping-record', 'owners': conflicts})
            continue
        blob = raw[pc - base:finish - base]
        successors = []
        if rule['flow'] in ('jump', 'branch'):
            offset = width + rule['targetOffset']
            successors.append(int.from_bytes(blob[offset:offset + 2], 'little'))
        if rule['flow'] in ('next', 'branch'):
            successors.append(finish)
        records.append({'start': pc, 'end': finish, 'bytes': blob.hex(), 'token': token,
                        'flow': rule['flow'], 'successors': successors,
                        'ruleEvidence': supplied(rule['evidence'])})
        for address in range(pc, finish):
            owners[address] = pc
        queue.extend(successors)
    gaps = unknown_spans(start, end, owners)
    status = 'refused' if violations else 'partial' if gaps else 'consistent'
    return {'status': status, 'scope': 'boundaries-only-under-supplied-contract',
            'records': sorted(records, key=lambda row: row['start']),
            'violations': violations, 'unknownRanges': gaps,
            'coveredBytes': len(owners), 'regionBytes': end - start}


def analyze(data, worksheet, helpers, helper_hashes):
    """Produce independent identity, mechanism, generation, and authorship fields."""
    verify_helper_cache(helpers['root'])
    collection(worksheet.get('componentPins', []), 'componentPins')
    collection(worksheet['region']['entries'], 'entries')
    consumer = worksheet.get('consumer')
    if consumer is not None:
        collection(consumer.get('nativeEntries', []), 'nativeEntries')
        if 'contract' in consumer:
            collection(consumer['contract']['rules'], 'rules')
    if worksheet['schema'] != 'regional-consumer-worksheet-v1':
        raise ValueError('unsupported worksheet schema')
    source = worksheet['input']
    if sha(data) != source['sha256']:
        raise ValueError('input SHA-256 does not match worksheet')
    if source['format'] == 'prg':
        if len(data) < 3:
            raise ValueError('PRG requires a header and payload')
        base, raw = int.from_bytes(data[:2], 'little'), data[2:]
    elif source['format'] == 'raw':
        base, raw = integer(source['base'], 0, 65535, 'base'), data
    else:
        raise ValueError('input format must be raw or prg')
    if not raw or base + len(raw) > 65536:
        raise ValueError('image is empty or exceeds the 16-bit address space')
    if source['cpu'] != '6502':
        raise ValueError('pilot supports the official 6502 instruction subset only')
    mapping = supplied(source['mappingEvidence'])
    region = worksheet['region']
    start, end = bounds(region, 'region')
    if not base <= start < end <= base + len(raw):
        raise ValueError('region is not wholly present in input')
    region_evidence = supplied(region['evidence'])
    baseline = helpers['identifier'].identify(data, raw_base=base if source['format'] == 'raw' else None)
    # The baseline is a component identifier, not an authorship confidence score.
    for match in baseline['matches']:
        match.pop('confidence', None)
    components = []
    for pin in worksheet.get('componentPins', []):
        match = witness(pin, raw, base)
        match['label'] = pin['label']
        match['labelStatus'] = 'supplied; exact bytes do not authenticate the label'
        components.append(match)
    result = {
        'schema': 'regional-implementation-evidence-v1',
        'input': {'sha256': sha(data), 'format': source['format'], 'base': base,
                  'end': base + len(raw), 'byteLength': len(data), 'cpu': '6502',
                  'mappingEvidence': mapping},
        'worksheetSha256': sha(json.dumps(worksheet, sort_keys=True, separators=(',', ':')).encode()),
        'publicHelperPrimaryFiles': helper_hashes,
        'region': {'start': start, 'end': end, 'sha256': sha(raw[start - base:end - base]),
                   'evidence': region_evidence, 'roleAssertion': supplied(region['roleEvidence'])},
        'componentIdentity': {'publicBaseline': baseline, 'suppliedPins': components},
        'mechanism': {'representationCandidate': 'unknown', 'actualReachability': 'unknown',
                      'candidateBasis': 'conditional-on-supplied-consumer; not a verified consumer mechanism',
                      'consumerAssertion': None, 'nativeStaticGraph': None,
                      'stream': {'status': 'unknown', 'reason': 'absent-consumer',
                                 'unknownRanges': [{'start': start, 'end': end}]}},
        'generationEvidence': {'status': 'none-established',
                               'reason': 'Identity and boundary compatibility do not establish generation.'},
        'historicalAuthorship': {'status': 'unresolved'},
        'limitations': [
            'Consumer semantics, entry points, mapping, rule meanings, and evidence references are supplied, not automatically proved.',
            'Static CFG paths are possible paths from supplied entries, not observed reachability; flags, banking, and self-modification are not modeled.',
            'Only fixed-width 1/2-byte tokens, 0..16 operand bytes, and absolute 16-bit stream targets are supported.',
            'No target execution, producer validation, source authentication, statistical inference, or handwritten default.',
            'Unvisited bytes stay unknown; bytes outside the selected region are outside this boundary question.',
            'Boundary consistency does not establish termination, actual execution, or semantic correctness.',
        ],
    }
    consumer = worksheet.get('consumer')
    if consumer is None:
        return result
    mechanism = result['mechanism']
    mechanism['consumerAssertion'] = {
        'operation': consumer['operation'], 'representation': consumer['representation'],
        'evidence': supplied(consumer['evidence']),
        'reachabilityEvidence': supplied(consumer['reachabilityEvidence']) if consumer.get('reachabilityEvidence') else None,
        'bytes': witness(consumer, raw, base),
    }
    if not mechanism['consumerAssertion']['bytes']['matched']:
        mechanism['stream']['reason'] = 'consumer-bytes-not-matched'
        return result
    if max(start, consumer['start']) < min(end, consumer['end']):
        mechanism['stream']['reason'] = 'consumer-overlaps-stream-unsupported'
        return result
    native_entries = consumer.get('nativeEntries', [])
    for entry in native_entries:
        integer(entry, base, base + len(raw) - 1, 'native entry')
    if native_entries:
        mechanism['nativeStaticGraph'] = helpers['cfg'].analyze(raw, base, native_entries, 512)
    if consumer['operation'] != 'dispatch':
        mechanism['stream']['reason'] = 'supplied-consumer-is-not-a-stream-dispatcher'
        return result
    if consumer['representation'] not in ('vm-opcodes', 'threaded-cells'):
        mechanism['stream']['reason'] = 'unsupported-representation'
        return result
    mechanism['stream'] = check_stream(raw, base, region, consumer['contract'])
    if mechanism['stream']['status'] == 'consistent':
        mechanism['representationCandidate'] = consumer['representation']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', type=Path)
    parser.add_argument('worksheet', type=Path)
    parser.add_argument('--public-root', type=Path, required=True,
                        help='trusted public toolkit root; never a private identity database')
    parser.add_argument('--output', type=Path, help='create a new report; never overwrite')
    args = parser.parse_args()
    try:
        helpers, hashes = load_helpers(args.public_root)
        data = args.binary.read_bytes()
        worksheet_bytes = args.worksheet.read_bytes()
        result = analyze(data, json.loads(worksheet_bytes), helpers, hashes)
        result['worksheetFileSha256'] = sha(worksheet_bytes)
        result['toolSha256'] = sha(Path(__file__).read_bytes())
        text = json.dumps(result, indent=2) + '\n'
        if args.output:
            with args.output.open('x') as stream:
                stream.write(text)
        else:
            print(text, end='')
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    sys.exit(main())
