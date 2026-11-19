"""An outline may omit byte columns, never qualifications or opaque groups."""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch
from group_outline import render_outline
import reconstruct

REPORT = dict(family='example', groups=[
    dict(text='PRINT 1', kind='inferred', warnings=['Device unproved.'], instructions=[dict(address=0)]),
    dict(text='REM not modeled', kind='unresolved', warnings=[], instructions=[dict(address=141)]),
    dict(text='REM synthetic', kind='partial', warnings=[], instructions=[])],
    retainedData=[dict(address=250, kind='opaque', text=None, caveat='Original grouping unknown.')],
    limitations=['Not runnable.'])


class OutlineTests(unittest.TestCase):
    def test_preserves_group_order_qualifications_and_real_address_zero(self):
        lines = render_outline(REPORT).splitlines()[2:]
        self.assertEqual(lines, ['$0000 [inferred] PRINT 1', '    ; Device unproved.',
                                 '$008D [unresolved] REM not modeled', '(no owned instruction) [partial] REM synthetic',
                                 '$00FA [opaque data] opaque; see detailed bytes', '    ; Original grouping unknown.', '; Not runnable.'])

    def test_cli_writes_only_requested_new_file_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, dest = Path(tmp)/'object', Path(tmp)/'outline'; src.write_bytes(b'example')
            with patch.object(sys, 'argv', ['reconstruct', str(src), '--outline-output', str(dest)]), patch.object(reconstruct, 'reconstruct', return_value=REPORT), redirect_stdout(io.StringIO()) as out:
                reconstruct.main()
                self.assertEqual(dest.read_text(), render_outline(REPORT)); self.assertEqual(out.getvalue(), '')
                dest.write_text('preserved')
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                    reconstruct.main()
                self.assertEqual(raised.exception.code, 2); self.assertEqual(dest.read_text(), 'preserved')
