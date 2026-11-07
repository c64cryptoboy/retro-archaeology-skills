"""Regression controls for independent review findings; synthetic inputs only."""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import region_evidence as pilot
from synthetic_fixture import BASE, example


class ReviewGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(os.environ['PUBLIC_TOOLKIT_ROOT'])
        cls.helpers, cls.hashes = pilot.load_helpers(cls.root)

    def test_direct_checker_requires_present_bytes(self):
        _, worksheet = example()
        contract = copy.deepcopy(worksheet['consumer']['contract'])
        for raw, base, start, end in ((b'', 4096, 4096, 4097),
                                      (b'\0', 4096, 4095, 4096),
                                      (b'\0', 4096, 4096, 4098),
                                      (b'\0', 4096, 4097, 4098)):
            with self.subTest(raw=raw, start=start, end=end):
                with self.assertRaisesRegex(ValueError, 'region is not wholly present'):
                    pilot.check_stream(raw, base, dict(start=start, end=end, entries=[start]), contract)

    def test_conflicting_cached_dependencies_refuse(self):
        for name in ('formats', 'dis6502', '_pcode_binary_blitz', '_pcode_binary_petspeed',
                     '_pcode_binary_basic64', '_pcode_binary_dtl', '_pcode_binary_speedcompiler'):
            fake = types.ModuleType(name)
            fake.__file__ = '/unrelated/' + name + '.py'
            with self.subTest(name=name), patch.dict(sys.modules, {name: fake}):
                with self.assertRaisesRegex(ValueError, 'conflicting cached helper'):
                    pilot.load_helpers(self.root)
                with self.assertRaisesRegex(ValueError, 'conflicting cached helper'):
                    pilot.analyze(*example(), self.helpers, self.hashes)

    def test_second_root_refuses_instead_of_claiming_wrong_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            other = Path(directory) / 'public'
            shutil.copytree(self.root / 'skills/pcode-disassembly/scripts',
                            other / 'skills/pcode-disassembly/scripts',
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            shutil.copytree(self.root / 'shared/6502', other / 'shared/6502',
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            with self.assertRaisesRegex(ValueError, 'conflicting cached helper'):
                pilot.load_helpers(other)
            # Refusal must not corrupt the existing selected-root analysis.
            result = pilot.analyze(*example(), self.helpers, self.hashes)
            self.assertEqual(result['mechanism']['stream']['status'], 'consistent')

    def test_wrong_collection_types_reject_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data, original = example()
            binary, manifest = root / 'input.bin', root / 'input.json'
            binary.write_bytes(data)
            for key in ('componentPins', 'entries', 'nativeEntries', 'rules'):
                for value in ({}, '', None):
                    worksheet = copy.deepcopy(original)
                    owner = (worksheet if key == 'componentPins' else worksheet['region'] if key == 'entries'
                             else worksheet['consumer'] if key == 'nativeEntries' else worksheet['consumer']['contract'])
                    owner[key] = value
                    manifest.write_text(json.dumps(worksheet))
                    completed = subprocess.run([sys.executable, '-B', str(HERE / 'region_evidence.py'),
                        str(binary), str(manifest), '--public-root', str(self.root)], capture_output=True, text=True)
                    with self.subTest(key=key, value=value):
                        self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)
                        self.assertIn('must be a list', completed.stderr)

    def test_permitted_empty_collections_keep_meaning(self):
        data, worksheet = example()
        worksheet['componentPins'] = []
        worksheet['consumer']['nativeEntries'] = []
        result = pilot.analyze(data, worksheet, self.helpers, self.hashes)
        self.assertEqual(result['mechanism']['stream']['status'], 'consistent')
        self.assertIsNone(result['mechanism']['nativeStaticGraph'])
        worksheet['consumer']['contract']['rules'] = []
        result = pilot.analyze(data, worksheet, self.helpers, self.hashes)
        self.assertEqual(result['mechanism']['stream']['status'], 'refused')


if __name__ == '__main__':
    unittest.main()
