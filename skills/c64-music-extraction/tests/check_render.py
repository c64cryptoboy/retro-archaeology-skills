"""Audio smoke check for Glass Steps only, not a transcriber or hardware oracle."""
import cmath
import math
import struct
import sys
import wave


def check_render(path):
    with wave.open(str(path), 'rb') as wav:
        if (wav.getnchannels(), wav.getsampwidth()) != (1, 2):
            raise ValueError('render as mono signed 16-bit PCM')
        fs = wav.getframerate()
        pcm = [x[0] for x in struct.iter_unpack('<h', wav.readframes(2 * fs))]
    if len(pcm) != 2 * fs:
        raise ValueError('need at least two seconds of audio')
    pitches = (391.995, 466.164, 349.228, 587.330)
    # Four 15-frame slots at ~60 Hz.  Sample the sustained middle, away from
    # gate transitions/startup. Compare four candidate fundamentals, not RMS alone.
    ratios = []
    for i in range(8):
        start = round((0.08 + i * .25) * fs)
        block = pcm[start:start + round(.08 * fs)]
        mean = sum(block) / len(block)
        power = [abs(sum((x - mean) * cmath.exp(-2j * math.pi * f * n / fs)
                         for n, x in enumerate(block))) / len(block) for f in pitches]
        target = power[i % 4]
        runner_up = max(power[:i % 4] + power[i % 4 + 1:])
        ratio = target / max(1, runner_up)
        if target < 10 or ratio < 2:
            raise ValueError(f'unexpected pitch or near-silence in slot {i}: {power}')
        ratios.append(ratio)
    return min(ratios)


if __name__ == '__main__':
    print(f'8/8 windows follow G4, Bb4, F4, D5 twice; min amplitude ratio {check_render(sys.argv[1]):.2f}')
