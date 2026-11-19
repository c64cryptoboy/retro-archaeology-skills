"""The shared symbolic listing describes PETSCII bytes, not host glyphs."""
import re
import unittest

from symbolic import quoted


class LiteralBytesTests(unittest.TestCase):
    def test_graphics_and_controls_separated_from_real_punctuation(self):
        self.assertEqual(quoted(b'A[\\]^_`az~!'),
                         '"A["+CHR$(92)+"]"+CHR$(94)+CHR$(95)+CHR$(96)+'
                         'CHR$(97)+CHR$(122)+CHR$(126)+"!"')
        self.assertEqual(quoted(b'"+'), 'CHR$(34)+"+"')
        self.assertEqual(quoted(b''), '""')

    def test_full_alphabet_round_trips_without_host_glyph_aliases(self):
        source = bytes(range(256))
        spelling = quoted(source)
        # Independent inverse of the two allowed terms; "+" in a string
        # is data, not a separator.  Require all characters to be consumed.
        term = re.compile(r'"([^"]*)"|CHR\$\(([0-9]+)\)')
        result = bytearray()
        pos = 0
        while pos < len(spelling):
            m = term.match(spelling, pos)
            self.assertIsNotNone(m)
            if m[1] is not None:
                self.assertRegex(m[1], r'^[ -!#-\[\]]*$')
                result.extend(m[1].encode('ascii'))
            else:
                result.append(int(m[2]))
            pos = m.end()
            if pos < len(spelling):
                self.assertEqual(spelling[pos], '+')
                pos += 1
        self.assertEqual(bytes(result), source)
