"""Replay one wholly contained appearance of the same slot in each of two bands."""
from static_composite import static_composite


def replay(background, upper, lower, *, first_lower_row, offset_x, offset_y):
    """Join registered static previews at an independently supplied active-area row."""
    if type(first_lower_row) is not int or not 0 < first_lower_row < 200:
        raise ValueError("need two nonempty bands in the 200-row active area")
    if upper["slot"] != lower["slot"]:
        raise ValueError("expected the same hardware slot twice")
    parts = []
    for layer, start, stop in ((upper, 0, first_lower_row), (lower, first_lower_row, 200)):
        y = layer["metadata"]["y"] + offset_y
        if not layer["metadata"]["enabled"] or not start <= y <= stop - layer["height"]:
            raise ValueError(f"enabled sprite must fit wholly in rows [{start}, {stop})")
        plane = static_composite(background, [layer], offset_x=offset_x, offset_y=offset_y)
        parts.append(plane[320 * start:320 * stop])
    return b"".join(parts)
