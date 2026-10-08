import re


_DESCRIPTION_SIZE_MARKERS = re.compile(r"\[\[size=(?:1[3-9]|20)\]\]|\[\[/size\]\]")


def description_character_count(description):
    """Counts readable description characters without editor-only size markers."""
    return len(strip_description_size_markers(description))


def strip_description_size_markers(description):
    """Removes editor-only font-size tokens from plain-text surfaces."""
    return _DESCRIPTION_SIZE_MARKERS.sub("", description or "")
