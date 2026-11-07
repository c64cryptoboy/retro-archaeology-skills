"""Portable defaults; large result data may live outside this source package."""
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent


def configured(name, default):
    return Path(os.environ.get(name, default)).expanduser().resolve()


ROM_DIR = configured('C64_ROM_DIR', HERE.parents[1] / 'c64-rom-reference' / 'assets' / 'roms')
RUN_DIR = configured('C64_RND_RUN_DIR', HERE / 'scratch/full-production')
SHELL_DIR = configured('C64_RND_SHELL_DIR', HERE / 'scratch/negative-shell-production')
