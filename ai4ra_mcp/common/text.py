"""Reading part of a long text: one window of it, and where a part of an outlined text ends.

A tool that serves a long text (a section of a regulation, a policy) returns it whole when it fits, as an outline
of its own headings when it does not, and a page at a time when it has no headings. The outline is a list of
(offset, heading, end): a part runs from its heading to where the next heading of the same level, or a higher
one, begins, so a heading comes with what is under it.
"""

from __future__ import annotations

from typing import Any, Optional

# The most of a text one read returns: a text up to this comes back whole, a longer one as its outline (or a page of
# this size when it has no headings). The server's alone: a caller cannot set it, since a model that asked for less
# turned a 3,777-character section into an outline and was then refused for asking for too little (#22). One
# number for every source; a regulation's sections and a policy's are read the same way.
WHOLE_CHARS = 12_000


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


def with_ends(entries: list[tuple[int, int, str]], total: int) -> list[tuple[int, str, int]]:
    """(offset, level, heading) in the order they come, as (offset, heading, end): each part ends where the next
    heading of its level or a higher one (a lower number) begins, or with the text."""
    out = []
    for k, (at, level, heading) in enumerate(entries):
        end = next((other_at for other_at, other_level, _ in entries[k + 1:] if other_level <= level), total)
        out.append((at, heading, end))
    return out


def read(text: str, outline: list[tuple[int, str, int]], offset: int, max_chars: int = WHOLE_CHARS) -> dict[str, Any]:
    """What a fetch of a long text returns. Whole when it fits; when it does not and it has an outline, the
    outline with only the lines before the first heading (the first part itself when the text opens with a
    heading, since offset 0 asks for the outline); from a heading's offset, that part to its end; from any other
    offset, a page."""
    if offset == 0 and outline and len(text) > max_chars:
        out = window(text, 0, max_chars, outline[0][0] or outline[0][2])
        out["truncated"] = True   # only the lines before the first heading: the rest is read by the outline
        out.pop("next_offset", None)
        out["outline"] = [f"{at}: {heading}" for at, heading, _end in outline]
        return out
    return window(text, offset, max_chars, next((end for at, _heading, end in outline if offset and at == offset), None))
