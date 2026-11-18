"""Synthetic calibration corpus with shared prefixes but distinct full routines."""

import json
import random
from pathlib import Path

from calibrate_reuse6502 import calibrate
from exact_anchor_controls6502 import run_controls
from make_region_manifest6502 import create_manifest
from reuse_align6502 import analyze_manifests


def routine(seed):
    rng = random.Random(seed)
    prefix = bytes.fromhex("a510 290f 8511 a612 e8 8612 c908 18")
    body = b"".join(bytes((rng.choice((0xA9, 0x49, 0x69, 0x29, 0xC9)), rng.randrange(256)))
                    for _ in range(50))
    return prefix + body + b"\x60"


def manifest(root, name, data):
    raw = root / (name + ".bin")
    raw.write_bytes(data)
    create_manifest(raw, root / name, name)
    return root / name / "regions.json"


def save(path, value):
    path.write_text(json.dumps(value))
    return path


def complete_calibration(root: Path):
    data = b"\x02".join(routine(i) for i in range(3))
    left = manifest(root, "known-left", data)
    right = manifest(root, "known-right", data)
    other = manifest(root, "control", bytes([0x02]) * 128)
    controls = run_controls(left, right, instruction_count=8, shuffle_trials=1,
                            random_trials=1, token_shuffle_trials=1, min_unique_mnemonics=4,
                            max_occurrences=64, max_pairs=4096)
    def alignment(path, right_path, k=8, paired=16):
        return save(root / path, analyze_manifests(left, right_path, seed_instruction_count=k,
                    probable_min_paired=paired, max_seed_clusters=50))
    primary = alignment("primary.json", right)
    variants = [alignment(f"{k}-{paired}.json", right, k, paired)
                for k, paired in ((6, 16), (10, 16), (8, 12), (8, 20))]
    args = (primary, save(root / "controls.json", controls),
            [alignment("unrelated.json", other)], variants)
    return calibrate(*args), args
