"""Reading part of a long text: one window of it, and where a part of an outlined text ends.

A tool that serves a long text (a section of a regulation, a policy) returns it whole when it fits, as an outline
of its own headings when it does not, and a page at a time when it has no headings. The outline is a list of
(offset, heading, end, pin): a part runs from its heading to where the next heading of the same level, or a higher
one, begins, so a heading comes with what is under it; pin is the part's place in the text as a citation writes
it, the labels of the headings above it and its own ("(i)(5)", "E-1"), which a read of the part gives back so a
caller cites the paragraph without working it out.
"""

from __future__ import annotations

from typing import Any, Optional

# How much of a text one read returns. The server's alone: a caller cannot set it, since a model that asked for
# less turned a 3,777-character section into an outline and was then refused for asking for too little (#22). The
# same for every source; a regulation's sections and a policy's are read the same way.
#
# A text with an outline comes back whole up to WHOLE_CHARS and as its outline past that, since with headings to
# choose from a caller reads the one part it needs. A step's limit is on the characters it fetches, and five
# policies of 7,000 to 9,400 characters read whole for one clause each took 43,000 of a step's 60,000 (the first
# whole-document run), with rounds of calls to spare. A text with no outline has nothing to choose from, so it
# comes back whole up to PAGE_CHARS and a page of that size at a time past it; a part is never cut below that.
WHOLE_CHARS = 6_000
PAGE_CHARS = 12_000


def window(text: str, offset: int, max_chars: int, stop: Optional[int] = None) -> dict[str, Any]:
    """Part of a text: from offset to stop (the end of the text when none is given), and never more than
    max_chars, which ends on a paragraph break when one fits. truncated says the read was cut by max_chars
    before it reached its stop; a part read to its end is not truncated, though the text goes on."""
    total = len(text)
    offset = min(max(offset, 0), total)
    stop = total if stop is None else min(stop, total)
    end = stop
    if stop - offset > max_chars:
        end = offset + max_chars
        cut = text.rfind("\n\n", offset, end)
        if cut > offset:
            end = cut
    chunk = text[offset:end].rstrip()
    out: dict[str, Any] = {"text": chunk, "total_chars": total, "offset": offset,
                           "returned_chars": len(chunk), "truncated": end < stop}
    if out["truncated"]:
        out["next_offset"] = end + 2 if text.startswith("\n\n", end) else end
    return out


def with_ends(entries: list[tuple], total: int) -> list[tuple[int, str, int, str]]:
    """(offset, level, heading) or (offset, level, heading, label) in the order they come, as (offset, heading,
    end, pin): each part ends where the next heading of its level or a higher one (a lower number) begins, or with
    the text; its pin is the labels of the headings it sits under, outermost first, and its own."""
    out = []
    for k, entry in enumerate(entries):
        at, level, heading = entry[:3]
        end = next((other[0] for other in entries[k + 1:] if other[1] <= level), total)
        chain, below = [entry[3] if len(entry) > 3 else ""], level
        for other in reversed(entries[:k]):
            if other[1] < below:
                chain.insert(0, other[3] if len(other) > 3 else "")
                below = other[1]
        out.append((at, heading, end, "".join(chain)))
    return out


def read(text: str, outline: list[tuple[int, str, int, str]], offset: int) -> dict[str, Any]:
    """What a fetch of a long text returns. Whole when it is short; past WHOLE_CHARS and with an outline, the
    outline, each heading with its offset and the size of its part, and only the lines before the first heading
    (when the text opens with a heading, the lines up to the next one, since offset 0 asks for the outline); from a
    heading's offset, that part to its end, with its pin. An offset that is no heading's falls inside some part:
    it reads that part, from its heading when the part fits in one read (so the text is whole and the pin true),
    from the offset to the part's end when it does not (a long part being paged). With no outline, whole up to
    PAGE_CHARS and a page at a time past it. A text that comes whole has no part and no page to ask for, so an
    offset sent for one returns it whole again with a note that says so, never a piece that starts mid-sentence (a
    check asked for a 2,111-character section at 1300, 600 and 470, a round of calls each, #25)."""
    outlined = bool(outline) and len(text) > WHOLE_CHARS
    if offset and not outlined and len(text) <= PAGE_CHARS:
        out = window(text, 0, PAGE_CHARS)
        out["note"] = f"This text is {len(text):,} characters and comes whole in one read: an offset does not apply, and there is no more of it to read."
        return out
    if offset == 0 and outlined:
        out = window(text, 0, PAGE_CHARS, outline[0][0] or (outline[1][0] if len(outline) > 1 else outline[0][2]))
        out["truncated"] = True   # only the lines before the first heading: the rest is read by the outline
        out.pop("next_offset", None)
        out["outline"] = [f"{entry[0]}: {entry[1]} ({entry[2] - entry[0]:,} chars)" for entry in outline]
        return out
    part = None
    if offset and outlined:
        part = next((entry for entry in outline if entry[0] == offset), None)
        if part is None:   # not a heading's offset: the innermost part it falls in, the one that starts last
            holding = [entry for entry in outline if entry[0] < offset < entry[2]]
            part = max(holding, key=lambda entry: entry[0]) if holding else None
            if part and part[2] - part[0] <= PAGE_CHARS:
                offset = part[0]
    stop = part[2] if part else (outline[0][0] if outlined and 0 < offset < outline[0][0] else None)
    out = window(text, offset, PAGE_CHARS, stop)
    if part and part[3]:
        out["pin"] = part[3]
    return out
