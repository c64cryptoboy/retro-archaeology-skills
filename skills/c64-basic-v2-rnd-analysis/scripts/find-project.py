#!/usr/bin/env python3
"""Locate the bundled portable analysis, or an explicitly selected project."""
import os
from pathlib import Path

REQUIRED = ('REPRODUCE.md', 'FINAL_REPORT.md', 'rnd_query.py')


def main():
    default = Path(__file__).resolve().parents[1] / 'analysis'
    project = Path(os.environ.get('C64_RND_PROJECT', default)).expanduser().resolve()
    missing = [name for name in REQUIRED if not (project / name).is_file()]
    if missing:
        raise SystemExit(f'Invalid C64 RND project {project}: missing {missing}')
    print(project)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
