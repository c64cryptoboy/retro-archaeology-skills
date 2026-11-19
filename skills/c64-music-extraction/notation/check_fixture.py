"""Render the authored example, then prove the gate check rejects a bad duration."""
from pathlib import Path
from tempfile import TemporaryDirectory
import argparse
import shutil
import subprocess

from midi_score import engrave
from check_render import verify

HERE = Path(__file__).resolve().parent
FIX = HERE/'fixture'


def engraver():
    found = shutil.which('lilypond')
    if found:
        return found
    import lilypond  # optional PyPI binary wheel
    return str(lilypond.executable())


def render(ly):
    subprocess.run([engraver(), '-dno-point-and-click', '-o', ly.stem, ly.name],
                   cwd=ly.parent, check=True)


def run(out, chirp):
    engrave(FIX/'performance.mid', FIX/'plan.json', out, chirp)
    ly = out/'score.ly'
    render(ly)
    verify(out/'score.midi', FIX/'expected.csv', 64)
    text = ly.read_text()
    assert text.count('^\\markup \\tiny "*"') == 1
    # Same attacks, keys, track lengths, bar checks, and tempo.  Change just
    # one release and put the missing eighth into a rest so only a gate test fails.
    target = "c'4 c'4 r4"
    assert text.count(target) == 1
    with TemporaryDirectory() as temp:
        wrong = Path(temp)/'wrong-duration.ly'
        wrong.write_text(text.replace(target, "c'8 r8 c'4 r4"))
        render(wrong)
        try:
            verify(wrong.with_suffix('.midi'), FIX/'expected.csv', 64)
        except ValueError as err:
            if str(err) != 'gate mismatch (staff, start, end, key): expected (1, 0, 8, 60), rendered (1, 0, 4, 60)':
                raise
            print('PASS: wrong-duration engraving rejected: ' + str(err))
        else:
            raise AssertionError('wrong duration was accepted')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path)
    p.add_argument('--check-chirp', action='store_true')
    args=p.parse_args()
    if args.out:
        run(args.out.resolve(), args.check_chirp)
    else:
        with TemporaryDirectory() as temp:
            run(Path(temp), args.check_chirp)
