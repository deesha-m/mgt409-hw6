"""Code-layer defense: keep only the text a person would actually see in the document.

Every reader returns (visible_text, notes). `notes` lists what was dropped and why; it goes to the
audit trail, never to the model.
"""
import re
from email import policy
from email.parser import BytesParser
from pathlib import Path

from bs4 import BeautifulSoup, Comment
from pypdf import PdfReader

# Zero-width and text-direction characters: invisible to people, used to hide words from keyword filters.
INVISIBLE_CHARS = re.compile(r"[­​-‏‪-‮⁠-⁤﻿]")
MIN_VISIBLE_PX = 4          # HTML text smaller than this is treated as hidden
MIN_VISIBLE_PT = 4.0        # PDF text smaller than this is treated as hidden
NAMED_COLORS = {"white": (255, 255, 255), "black": (0, 0, 0), "transparent": None}


def _short(text: str, limit: int = 160) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + "..."


def strip_invisible_chars(text: str, notes: list[str]) -> str:
    count = len(INVISIBLE_CHARS.findall(text))
    if count:
        notes.append(f"removed {count} zero-width/invisible characters")
    return INVISIBLE_CHARS.sub("", text)


# ---------------------------------------------------------------- HTML

def _parse_css_rules(soup: BeautifulSoup) -> list[tuple[str, str]]:
    """Simple selectors (tag, .class, #id, comma lists) from <style> blocks, as (selector, declarations)."""
    rules = []
    for style in soup.find_all("style"):
        css = re.sub(r"/\*.*?\*/", "", style.get_text(), flags=re.S)
        for selectors, decls in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
            for selector in selectors.split(","):
                rules.append((selector.strip(), decls))
    return rules


def _matches(el, selector: str) -> bool:
    if selector.startswith("."):
        return selector[1:] in (el.get("class") or [])
    if selector.startswith("#"):
        return el.get("id") == selector[1:]
    return re.fullmatch(r"[a-zA-Z][a-zA-Z0-9]*", selector) is not None and el.name == selector.lower()


def _style(el, rules) -> dict[str, str]:
    decls = ";".join(d for s, d in rules if _matches(el, s)) + ";" + (el.get("style") or "")
    out = {}
    for decl in decls.split(";"):
        if ":" in decl:
            key, value = decl.split(":", 1)
            out[key.strip().lower()] = value.strip().lower().replace("!important", "").strip()
    return out


def _color(value: str | None):
    if not value:
        return None
    value = value.strip()
    if value in NAMED_COLORS:
        return NAMED_COLORS[value]
    if m := re.fullmatch(r"#([0-9a-f]{3})", value):
        return tuple(int(c * 2, 16) for c in m.group(1))
    if m := re.fullmatch(r"#([0-9a-f]{6})", value):
        return tuple(int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4))
    if m := re.fullmatch(r"rgba?\(([^)]*)\)", value):
        parts = [p.strip() for p in m.group(1).split(",")]
        if len(parts) == 4 and float(parts[3]) == 0:
            return None
        return tuple(int(float(p.rstrip("%"))) for p in parts[:3])
    return None


def _px(value: str) -> float | None:
    m = re.fullmatch(r"(-?[\d.]+)\s*(px|pt|em|rem|%)?", value.strip())
    if not m:
        return None
    number, unit = float(m.group(1)), m.group(2) or "px"
    return number * {"px": 1, "pt": 4 / 3, "em": 16, "rem": 16, "%": 0.16}[unit]


def _background(el, rules):
    for node in [el, *el.parents]:
        if getattr(node, "name", None) is None:
            continue
        style = _style(node, rules)
        bg = _color(style.get("background-color") or style.get("background", "").split(" ")[0])
        if bg:
            return bg
    return (255, 255, 255)


def _hidden_reason(el, rules) -> str | None:
    if el.has_attr("hidden") or el.get("aria-hidden") == "true":
        return "hidden attribute"
    style = _style(el, rules)
    if style.get("display") == "none":
        return "display:none"
    if style.get("visibility") in ("hidden", "collapse"):
        return "visibility:hidden"
    if (opacity := style.get("opacity")) and _px(opacity) is not None and _px(opacity) <= 0.05:
        return "opacity:0"
    if (size := style.get("font-size")) and (px := _px(size)) is not None and px < MIN_VISIBLE_PX:
        return f"font-size:{size}"
    for prop in ("left", "top", "text-indent", "margin-left"):
        if (v := style.get(prop)) and (px := _px(v)) is not None and px <= -500:
            return f"{prop}:{v} (off-screen)"
    if style.get("clip", "").startswith("rect(0") or style.get("clip-path", "").startswith("inset(50%"):
        return "clipped to nothing"
    if (style.get("height") in ("0", "0px") or style.get("max-height") in ("0", "0px")) and style.get("overflow") == "hidden":
        return "zero height"
    if "color" in style:
        fg = _color(style["color"])
        if style["color"].startswith("rgba") and fg is None:
            return "transparent text"
        if fg and sum(abs(a - b) for a, b in zip(fg, _background(el, rules))) < 40:
            return f"text color {style['color']} matches background"
    return None


def visible_html_text(html: str) -> tuple[str, list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    notes: list[str] = []
    rules = _parse_css_rules(soup)
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        if comment.strip():
            notes.append(f"removed HTML comment: {_short(comment)}")
        comment.extract()
    for tag in soup(["script", "style", "template", "noscript", "head", "meta", "iframe", "object"]):
        tag.decompose()
    for el in soup.find_all(True):
        if el.decomposed:
            continue
        if reason := _hidden_reason(el, rules):
            text = el.get_text(" ", strip=True)
            if text:
                notes.append(f"removed hidden HTML ({reason}): {_short(text)}")
            el.decompose()
    text = strip_invisible_chars(soup.get_text("\n", strip=True), notes)
    return text, notes


# ---------------------------------------------------------------- PDF

def _is_white(op: bytes, args: list[float]) -> bool:
    if op in (b"rg", b"sc", b"scn") and len(args) == 3:
        return min(args) >= 0.95
    if op in (b"g", b"sc", b"scn") and len(args) == 1:
        return args[0] >= 0.95
    if op == b"k" and len(args) == 4:
        return max(args) <= 0.05
    return False


def visible_pdf_text(path: Path) -> tuple[str, list[str]]:
    notes: list[str] = []
    lines: list[tuple[int, float, float, str]] = []
    for page_no, page in enumerate(PdfReader(path).pages):
        box = page.mediabox
        state = {"white": False, "invisible": False}
        stack: list[dict] = []

        def before(op, args, cm, tm):
            if op == b"q":
                stack.append(dict(state))
            elif op == b"Q" and stack:
                state.update(stack.pop())
            elif op in (b"rg", b"g", b"k", b"sc", b"scn"):
                numbers = [float(a) for a in args if isinstance(a, (int, float))]
                state["white"] = _is_white(op, numbers)
            elif op == b"Tr" and args:
                state["invisible"] = int(args[0]) == 3

        def visit(text, cm, tm, font, size):
            if not text.strip():
                return
            scale = abs(float(tm[3]) * float(cm[3])) or 1.0
            x = float(tm[4]) * float(cm[0]) + float(cm[4])
            y = float(tm[5]) * float(cm[3]) + float(cm[5])
            reason = None
            if state["invisible"]:
                reason = "invisible render mode"
            elif state["white"]:
                reason = "white text on white page"
            elif size * scale < MIN_VISIBLE_PT:
                reason = f"{size * scale:g}pt font"
            elif not (float(box.left) - 5 <= x <= float(box.right) and float(box.bottom) - 5 <= y <= float(box.top) + 5):
                reason = f"placed off the page at ({x:g}, {y:g})"
            if reason:
                notes.append(f"removed hidden PDF text ({reason}): {_short(text)}")
            else:
                lines.append((page_no, -y, x, text.strip()))

        page.extract_text(visitor_operand_before=before, visitor_text=visit)
    # Reading order a person would use: page by page, top to bottom, left to right.
    text = "\n".join(t for *_, t in sorted(lines))
    return strip_invisible_chars(text, notes), notes


# ---------------------------------------------------------------- Email

def visible_eml_text(path: Path) -> tuple[str, list[str]]:
    """What an email app shows: the HTML part if there is one (minus hidden text), otherwise plain text."""
    msg = BytesParser(policy=policy.default).parse(path.open("rb"))
    header = f"From: {msg['from']}\nTo: {msg['to']}\nSubject: {msg['subject']}\nDate: {msg['date']}\n\n"
    notes: list[str] = []
    html = msg.get_body(preferencelist=("html",))
    plain = msg.get_body(preferencelist=("plain",))
    if html is not None:
        body, notes = visible_html_text(html.get_content())
        if plain is not None:
            plain_words = set(re.findall(r"[\w$.]+", plain.get_content().lower()))
            extra = set(re.findall(r"[\w$.]+", body.lower())) - plain_words
            if extra:
                notes.append(f"HTML and plain-text versions differ; HTML has extra words: {_short(' '.join(sorted(extra)))}")
    elif plain is not None:
        body = strip_invisible_chars(plain.get_content(), notes)
    else:
        body = ""
    return header + body, notes


def visible_text(path: Path) -> tuple[str, list[str]]:
    suffix = path.suffix.lower()
    if suffix in (".html", ".htm"):
        return visible_html_text(path.read_text(encoding="utf-8"))
    if suffix == ".pdf":
        return visible_pdf_text(path)
    if suffix == ".eml":
        return visible_eml_text(path)
    raise ValueError(f"unsupported file type {suffix}")
