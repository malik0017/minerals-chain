"""
app/core/simple_markup.py
"""
import html
import re

from markupsafe import Markup

_LINK = re.compile(r"\[([^\]]+)\]\(((?:https?://|/)[^)\s]+)\)")
_BOLD = re.compile(r"\*\*(.+?)\*\*")


def _inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    return _LINK.sub(lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>', text)


def render(text: str | None) -> Markup:
    if not text:
        return Markup("")
    out, bullets, para = [], [], []

    def flush():
        if para:
            out.append("<p>" + "<br>".join(_inline(p) for p in para) + "</p>")
            para.clear()
        if bullets:
            out.append("<ul>" + "".join(f"<li>{_inline(b)}</li>" for b in bullets) + "</ul>")
            bullets.clear()

    for raw in text.replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        if not line.strip():
            flush()
        elif line.startswith("## "):
            flush(); out.append(f"<h5 class='mt-4'>{_inline(line[3:])}</h5>")
        elif line.startswith("# "):
            flush(); out.append(f"<h4 class='mt-4'>{_inline(line[2:])}</h4>")
        elif line.lstrip().startswith("- "):
            if para:
                out.append("<p>" + "<br>".join(_inline(p) for p in para) + "</p>"); para.clear()
            bullets.append(line.lstrip()[2:])
        else:
            if bullets:
                flush()
            para.append(line)
    flush()
    return Markup("\n".join(out))
