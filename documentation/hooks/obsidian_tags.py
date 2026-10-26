"""
Convert Obsidian inline tags (#tag) to HTML badges for MkDocs.
Source .md files are never modified — transformation happens at build time only.

To strip tags instead of rendering them, set STRIP_TAGS = True.
"""
import re

STRIP_TAGS = False

# Map specific tags to badge colors (Material color names or hex)
TAG_COLORS = {
    "todo":          ("#e53935", "#fff"),
    "towrite":       ("#fb8c00", "#fff"),
    "designchoice":  ("#1e88e5", "#fff"),
    "impl":          ("#43a047", "#fff"),
}
DEFAULT_COLOR = ("#78909c", "#fff")

# Matches #tag (word chars only, not preceded by [ to avoid [[wikilinks]])
TAG_RE = re.compile(r'(?<!\[)(?<!\w)#([a-zA-Z][a-zA-Z0-9_]*)')


def _replace_tag(match):
    tag = match.group(1)
    if STRIP_TAGS:
        return ""
    bg, fg = TAG_COLORS.get(tag, DEFAULT_COLOR)
    return (
        f'<span style="display:inline-block;padding:1px 6px;border-radius:4px;'
        f'font-size:0.72em;font-weight:600;background:{bg};color:{fg};'
        f'vertical-align:middle;margin:0 1px">#{tag}</span>'
    )


def on_page_markdown(markdown, **kwargs):
    # Skip fenced code blocks to avoid mangling code
    parts = re.split(r'(```.*?```)', markdown, flags=re.DOTALL)
    result = []
    for i, part in enumerate(parts):
        if i % 2 == 1:  # inside a code block
            result.append(part)
        else:
            result.append(TAG_RE.sub(_replace_tag, part))
    return "".join(result)
