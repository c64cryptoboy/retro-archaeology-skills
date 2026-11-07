"""Pure presentation selection.  Adapters supply storage identities and target proofs.

No compiler, ROM, emulator, private file, or host-float conversion is implicit.
Strict shortening requires the supplied parser to reproduce exact encoded bytes.
An explicitly separate nominal interval display never claims a parser round trip.
Generated aliases are display identities, never source recovery.
"""
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
from fractions import Fraction
from itertools import product
import re

DECIMAL = re.compile(r'-?[0-9]+(?:\.[0-9]+)?\Z')


def short_names(identities, *, excluded=(), occupied=()):
    """Allocate unique one/two-letter bases in the caller's stable identity order.

    Suffixes/types belong to adapters.  Occupied names reserve their first two
    significant letters across types, rather than merely their full spelling.
    Refuse duplicate identities or exhaustion instead of reusing a name.
    """
    identities = list(identities)
    if len(set(identities)) != len(identities):
        raise ValueError('Duplicate storage identity')
    blocked = {str(n).upper().rstrip('$%')[:2] for n in (*excluded, *occupied)}
    alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    candidates = (''.join(p) for width in (1, 2) for p in product(alphabet, repeat=width))
    available = [n for n in candidates if n not in blocked]
    if len(identities) > len(available):
        raise ValueError('One/two-letter alias space exhausted')
    return dict(zip(identities, available))


def decimal_candidates(exact, *, significant_digits=11):
    """Bounded readable candidates; Decimal proximity is not an acceptance proof."""
    if not DECIMAL.fullmatch(exact):
        raise ValueError('Expected a finite fixed-point decimal')
    if not 1 <= significant_digits <= 20:
        raise ValueError('Candidate search budget outside 1..20')
    if '.' not in exact or Fraction(exact) == 0:
        return []
    with localcontext() as context:
        context.prec = max(200, len(exact) + significant_digits + 5)
        value = Decimal(exact)
        candidates = set()
        for digits in range(1, significant_digits + 1):
            quantum = Decimal(1).scaleb(value.copy_abs().adjusted() - digits + 1)
            center = value.quantize(quantum, rounding=ROUND_HALF_EVEN)
            for number in (center, center - quantum, center + quantum):
                text = format(number, 'f')
                if '.' in text:
                    text = text.rstrip('0').rstrip('.')
                if text == '-0':
                    text = '0'
                if len(text) < len(exact):
                    candidates.add(text)
        return sorted(candidates, key=lambda text: (len(text), text))


def select_decimal(exact, encoded, parser):
    """Return a proof-carrying choice using parser(text) -> exact bytes.

    Parser failures propagate: a broken oracle must not silently masquerade as
    an unshortenable literal.  An unchanged value records the attempted search.
    """
    encoded = bytes(encoded)
    attempts = []
    for text in decimal_candidates(exact):
        observed = bytes(parser(text))
        accepted = observed == encoded
        attempts.append({'text': text, 'observedHex': observed.hex(), 'accepted': accepted})
        if accepted:
            return {'exactText': exact, 'displayText': text, 'encodedHex': encoded.hex(),
                    'decision': 'proved-shorter', 'attempts': attempts,
                    'proof': {'text': text, 'observedHex': observed.hex(), 'exactBytesEqual': True}}
    return {'exactText': exact, 'displayText': exact, 'encodedHex': encoded.hex(),
            'decision': 'unchanged-after-search' if attempts else 'already-short',
            'attempts': attempts, 'proof': None}


def select_nominal_decimal(exact, lower, upper):
    """Choose a readable value strictly inside a caller-proved storage cell.

    This is an explicitly approximate reader view, not source-parser equality.
    The target adapter owns exact neighbor/midpoint derivation.  No epsilon,
    host float, or guessed number of display digits determines acceptance.
    """
    lower, upper = Fraction(lower), Fraction(upper)
    if not lower < Fraction(exact) < upper:
        raise ValueError('Exact value is not inside the supplied storage cell')
    for text in decimal_candidates(exact):
        candidate = Fraction(text)
        if lower < candidate < upper:
            return {'exactText': exact, 'displayText': text,
                    'decision': 'nominal-cell-display',
                    'nominalProof': {'lowerExclusive': str(lower),
                                     'upperExclusive': str(upper),
                                     'candidateValue': str(candidate),
                                     'parserRoundTrip': False}}
    return {'exactText': exact, 'displayText': exact,
            'decision': 'exact-unshortened', 'nominalProof': None}
