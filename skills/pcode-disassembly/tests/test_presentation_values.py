"""Pure presentation-mechanism tests; no target/parser claims or private inputs."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/reconstruct'))
from presentation_values import decimal_candidates,select_decimal,select_nominal_decimal,short_names
from fractions import Fraction

class Names(unittest.TestCase):
    def test_stable_short_unique(self):
        a=short_names(range(100),excluded={'IF','ON','OR','TO','FN','GO','TI','ST'})
        self.assertEqual(a[0],'A');self.assertEqual(a[26],'AA')
        self.assertEqual(len(set(a.values())),100)
        self.assertTrue(all(n.isalpha() and n.isupper() and 1<=len(n)<=2 for n in a.values()))
    def test_existing_significant_names_reserved(self):
        a=short_names(range(690),occupied=['A$','APPLE'])
        self.assertNotIn('A',a.values());self.assertNotIn('AP',a.values())
    def test_duplicate_or_exhausted_reject(self):
        with self.assertRaises(ValueError):short_names(['a','a'])
        with self.assertRaises(ValueError):short_names(range(703))

class DecimalPolicy(unittest.TestCase):
    exact='0.80000000004656612873077392578125'
    def test_proposal_is_not_a_value_proof(self):
        self.assertIn('0.8',decimal_candidates(self.exact))
        result=select_decimal(self.exact,b'one',lambda _:b'two')
        self.assertEqual(result['displayText'],self.exact);self.assertIsNone(result['proof'])
    def test_only_exact_callback_equality_accepts(self):
        result=select_decimal(self.exact,b'one',lambda t:b'one' if t=='0.8' else b'two')
        self.assertEqual(result['displayText'],'0.8');self.assertTrue(result['proof']['exactBytesEqual'])
    def test_rejected_neighbor_and_parser_failure(self):
        result=select_decimal(self.exact,b'neighbor',lambda _:b'one')
        self.assertEqual(result['displayText'],self.exact)
        def broken(_):raise RuntimeError('parser unavailable')
        with self.assertRaises(RuntimeError):select_decimal(self.exact,b'one',broken)
    def test_short_and_invalid_tokens(self):
        self.assertEqual(select_decimal('7',b'x',lambda _:self.fail())['decision'],'already-short')
        with self.assertRaises(ValueError):decimal_candidates('1e-3')

class NominalPolicy(unittest.TestCase):
    exact=DecimalPolicy.exact
    def test_explicitly_separate_non_round_trip_contract(self):
        center=Fraction(4,5);half=Fraction(1,2**32)
        value=select_nominal_decimal(self.exact,center-half,center+half)
        self.assertEqual(value['displayText'],'0.8')
        self.assertIs(value['nominalProof']['parserRoundTrip'],False)
        self.assertNotIn('proof',value)
    def test_tight_cell_retains_exact_value(self):
        center=Fraction(self.exact);half=Fraction(1,10**45)
        value=select_nominal_decimal(self.exact,center-half,center+half)
        self.assertEqual(value['displayText'],self.exact)
        self.assertIsNone(value['nominalProof'])
    def test_midpoint_is_not_admitted(self):
        value=select_nominal_decimal(self.exact,Fraction(4,5),Fraction(81,100))
        self.assertNotEqual(value['displayText'],'0.8')
    def test_wrong_cell_or_missing_contract_rejected(self):
        with self.assertRaises(ValueError):select_nominal_decimal(self.exact,1,2)
        with self.assertRaises(ValueError):select_nominal_decimal(self.exact,1,0)

if __name__=='__main__':unittest.main()
