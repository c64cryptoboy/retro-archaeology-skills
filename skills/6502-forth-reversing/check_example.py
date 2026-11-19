"""Check the five-byte teaching word in example.md, not arbitrary binaries."""

BODY = bytes.fromhex("C8 02 53 01 01")
STARTS = {0, 2, 4}  # From the authored layout, not inferred from token values.


def follow(body, top):
    ip = 0
    path = []
    while len(path) < len(STARTS):  # This leaf has no loop.
        if ip not in STARTS:
            raise ValueError("not an operation start")
        if ip >= len(body):
            raise ValueError("missing token")
        path.append(ip)
        token = body[ip]
        ip += 1
        if token == 0x01:
            return path, top
        if token not in (0xC8, 0x53):
            raise ValueError("unknown token")
        if ip >= len(body):
            raise ValueError("missing operand")
        operand = body[ip]
        ip += 1
        if token == 0x53:
            top = (top + operand) % 256
        elif top % 2 == 0:
            ip = (ip + operand) % 256
    raise ValueError("did not return within the leaf")


def expect(actual, wanted):
    if actual != wanted:
        raise AssertionError(f"expected {wanted!r}, got {actual!r}")


def check_rounding(body):
    for top in range(256):
        odd = top % 2
        expect(follow(body, top), ([0, 2, 4] if odd else [0, 4], (top + odd) % 256))


def main():
    check_rounding(BODY)
    changed_addend = bytes.fromhex("C8 02 53 03 01")
    expect(follow(changed_addend, 7), ([0, 2, 4], 10))
    expect(follow(changed_addend, 6), ([0, 4], 6))

    for bad, top, reason in [
        (bytes.fromhex("C8 01 53 01 01"), 6, "not an operation start"),
        (bytes.fromhex("C8 02 FF 01 01"), 7, "unknown token"),
        (BODY[:3], 7, "missing operand"),
    ]:
        try:
            follow(bad, top)
        except ValueError as err:
            expect(str(err), reason)
        else:
            raise AssertionError(f"accepted: {reason}")

    # A zero displacement lands on a real token.  Only checking ownership
    # would accept it; require the original path and input/output contract.
    wrong_edge = bytes.fromhex("C8 00 53 01 01")
    expect(follow(wrong_edge, 6), ([0, 2, 4], 7))
    try:
        check_rounding(wrong_edge)
    except AssertionError:
        pass
    else:
        raise AssertionError("accepted wrong even edge")
    print("PASS: 256 inputs, changed addend, and four wrong controls")


if __name__ == "__main__":
    main()
