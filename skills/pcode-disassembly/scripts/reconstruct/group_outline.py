"""A shorter display of existing statement groups; not another source lifter."""


def render_outline(report):
    lines = [f'; {report["family"]}: statement outline in decoder order, not execution order.',
             '; Addresses are mapped p-code, not BASIC line numbers.  Use --at or the detailed report for instruction bytes.']
    for group in report['groups']:
        rows = group['instructions']
        start = f'${rows[0]["address"]:04X}' if rows else '(no owned instruction)'
        lines.append(f'{start} [{group["kind"]}] {group["text"]}')
        lines.extend('    ; ' + warning for warning in group['warnings'])
    for item in report.get('retainedData', ()):
        lines.append(f'${item["address"]:04X} [{item["kind"]} data] ' + (item.get('text') or 'opaque; see detailed bytes'))
        if item.get('caveat'):
            lines.append('    ; ' + item['caveat'])
    lines.extend('; ' + warning for warning in report.get('limitations', ()))
    return '\n'.join(lines) + '\n'
