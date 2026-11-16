import base64
import html
import json
import re
from pathlib import Path

import streamlit as st

import services

REQUIRE_LOGIN = True  # Round 3: real sign-in with the demo accounts printed on the login screen

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent

NAVY = "#1B2A4E"
TEAL = "#12917F"
TEAL_SOFT = "#E3F3F0"
BG = "#F4F6FA"
INK = "#1B2A4E"
MUTED = "#5A6480"
LINE = "#E2E7F0"

RED = "#D93025"
AMBER = "#B45309"
BLUE = "#1A73E8"
CATEGORY_COLORS = {
    "outdated_fact": RED,
    "visual": "#7C3AED",
    "messaging": AMBER,
    "claim": RED,
    "fact": RED,
    "expired_fact": RED,
    "expired": RED,
    "unverified_claim": RED,
    "tone": AMBER,
    "terminology": AMBER,
    "glossary": AMBER,
    "accessibility": BLUE,
    "readability": BLUE,
}

LOGO_CANDIDATES = [
    APP_DIR / "inkwise_logo.jpeg",
    ROOT / "assets" / "inkwise_logo.jpeg",
    ROOT / "inkwise_logo.jpeg",
]

ROLES = ["Creator", "Manager", "Reviewer", "Admin"]


STATIC_DIR = APP_DIR / "static"


def static_url(name: str):
    """URL of app/static/<name> (served by Streamlit, enableStaticServing = true), or None if missing.
    Images as files keep the page styles small, so the design appears at once (no unstyled flash)."""
    p = STATIC_DIR / name
    if not p.exists():
        return None
    return f"app/static/{name}?v={int(p.stat().st_mtime)}"


def logo_src() -> str:
    url = static_url("inkwise_logo.jpeg")
    if url:
        return url
    for p in LOGO_CANDIDATES:
        if p.exists():
            b64 = base64.b64encode(p.read_bytes()).decode()
            return f"data:image/jpeg;base64,{b64}"
    return ""


CSS = f"""
<style>
html, body, .stApp {{ color: {INK}; }}
.stApp {{ background: {BG}; color-scheme: light; }}
#MainMenu, footer {{ visibility: hidden; }}
header[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stDecoration"], .stDeployButton {{ display: none; }}
.block-container {{ padding-top: 1.2rem; max-width: 1180px; }}

h1, h2, h3, h4, h5 {{ color: {NAVY}; letter-spacing: -.01em; }}

textarea, input,
[data-baseweb="textarea"] textarea,
[data-baseweb="input"] input {{
  background: #fff !important;
  color: {INK} !important;
  -webkit-text-fill-color: {INK} !important;
  caret-color: {INK};
}}
[data-baseweb="textarea"], [data-baseweb="input"], [data-baseweb="select"] > div {{
  background: #fff !important;
  border-color: {LINE} !important;
}}
[data-baseweb="select"] div, [data-baseweb="select"] span {{ color: {INK} !important; }}
::placeholder {{ color: {MUTED} !important; opacity: 1 !important; -webkit-text-fill-color: {MUTED} !important; }}

[data-testid="stWidgetLabel"] p, label, label p {{ color: {INK} !important; font-weight: 600; }}
[data-testid="stCaptionContainer"], .stCaption {{ color: {MUTED} !important; }}

[data-testid="stSidebar"] {{ background: #fff; border-right: 1px solid {LINE}; }}
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span,
[data-testid="stSidebar"] label {{ color: {INK}; }}
[data-testid="stSidebarNav"] a {{ border-radius: 8px; padding: .35rem .6rem; }}
[data-testid="stSidebarNav"] a:hover {{ background: {BG}; }}
[data-testid="stSidebarNav"] a[aria-current="page"] {{ background: {TEAL}; }}
[data-testid="stSidebarNav"] a[aria-current="page"] * {{ color: #fff !important; font-weight: 600; }}
.sb-logo img {{ width: 100%; border-radius: 12px; margin-bottom: .6rem; }}

[data-testid="stSidebarCollapseButton"] button,
[data-testid="stExpandSidebarButton"],
[data-testid="stSidebarCollapsedControl"] button {{
  background: {TEAL} !important; color: #fff !important;
  border-radius: 8px; opacity: 1 !important;
}}
[data-testid="stSidebarCollapseButton"] svg,
[data-testid="stExpandSidebarButton"] svg,
[data-testid="stSidebarCollapsedControl"] svg {{ fill: #fff !important; color: #fff !important; }}

.iw-login {{ background: {NAVY}; border-radius: 16px; padding: 24px; text-align: center; margin-bottom: 18px; }}
.iw-login img {{ width: min(420px, 100%); border-radius: 12px; }}

.iw-kpi {{ background:#fff; border:1px solid {LINE}; border-radius:10px; padding:12px 14px; min-width:0; }}
.iw-kpi .n {{ font-size:1.8rem; font-weight:700; letter-spacing:-.02em; line-height:1.1; color:{NAVY}; }}
.iw-kpi .l {{ color:{MUTED}; font-size:.85rem; margin-top:2px; 
   white space:nowrap; overflow:hidden; text-overflow:ellipsis; word-break:normal; }}
.iw-kpi.warn .n {{ color:#B45309; }}
.iw-kpi.ok .n {{ color:{TEAL}; }}

.iw-card {{ background:#fff; border:1px solid {LINE}; border-radius:10px;
  padding:14px 16px; margin-bottom:6px; }}
.iw-card h4 {{ margin:0 0 4px; font-size:1rem; font-weight:700; color:{NAVY}; }}
.iw-card p {{ margin:0; color:{MUTED}; font-size:.88rem; line-height:1.45; }}
.iw-section {{ font-size:1.05rem; font-weight:700; margin: 22px 0 8px; color:{NAVY}; }}

.iw-empty {{ border:1px dashed #C5CCDA; border-radius:10px; padding:24px;
  text-align:center; color:{MUTED}; background:#fff; }}

.iw-banner {{ background:{TEAL_SOFT}; border:1px solid #BFE3DC; color:#0B5E52;
  border-radius:8px; padding:6px 12px; font-size:.8rem; margin-top:12px; }}

.iw-pill {{ display:inline-block; padding:2px 10px; border-radius:999px; font-size:.75rem; font-weight:600; }}
.iw-pill.open {{ background:#FFF1E0; color:#B45309; }}
.iw-pill.ok {{ background:{TEAL_SOFT}; color:#0B5E52; }}
.iw-pill.bad {{ background:#FDE8E8; color:#B42318; }}

.iw-tag {{ display:inline-block; padding:1px 6px; border-radius:4px; font-size:.7rem;
  font-weight:700; letter-spacing:.03em; border:1px solid {LINE}; color:{MUTED}; background:#fff; }}
.iw-tag.ai {{ color:{TEAL}; border-color:{TEAL}; }}

.iw-quote {{ background:{BG}; border-left:3px solid #C5CCDA; border-radius:4px;
  padding:10px 14px; color:{INK}; font-size:.9rem; line-height:1.5; }}
.iw-quote .src {{ color:{MUTED}; font-size:.78rem; margin-top:4px; }}

.iw-text {{ background:#fff; border:1px solid {LINE}; border-radius:10px;
  padding:16px 18px; line-height:1.9; color:{INK}; white-space:pre-wrap; }}
.iw-text mark {{ background:transparent; color:inherit; padding:0 1px;
  text-decoration-line:underline; text-decoration-style:wavy; text-decoration-thickness:2px;
  text-underline-offset:3px; }}
.iw-text sup {{ font-weight:700; font-size:.7rem; margin-left:1px; }}

.stButton>button, [data-testid="stPageLink"] a {{ border-radius:8px; font-weight:600; }}
.stButton>button[kind="primary"] {{ background:{TEAL}; border:none; color:#fff; }}
.stButton>button[kind="secondary"] {{ background:#fff; color:{INK}; border:1px solid {LINE}; }}

[data-testid="stAppDeployButton"] {{ display: none !important; }}
.iw-team {{ position:fixed; right:18px; bottom:14px; z-index:1000; font-size:.72rem; font-weight:700;
  letter-spacing:.06em; color:#fff; background:rgba(27,42,78,.9); padding:6px 12px; border-radius:999px;
  box-shadow:0 6px 18px rgba(5,12,28,.2); }}
.iw-team span {{ color:#5FD3C1; }}

[data-baseweb="select"] > div, [data-baseweb="select"] > div > div {{ background: #fff !important; }}
[data-baseweb="select"] svg {{ fill: {INK} !important; color: {INK} !important; }}
[data-baseweb="popover"] ul, [data-baseweb="popover"] li, [data-baseweb="menu"] {{
  background: #fff !important; color: {INK} !important; }}

[data-testid="stBaseButton-secondary"] {{ background: #fff !important; color: {INK} !important;
  border: 1px solid {LINE} !important; border-radius: 8px; font-weight: 600; }}
[data-testid="stBaseButton-secondary"] p {{ color: {INK} !important; }}
[data-testid="stBaseButton-primary"] {{ background: {TEAL} !important; color: #fff !important;
  border: none !important; border-radius: 8px; font-weight: 600; }}
[data-testid="stBaseButton-primary"] p {{ color: #fff !important; }}

[data-baseweb="tab"] p {{ color: {INK} !important; font-weight: 600; }}
[data-baseweb="tab-highlight"] {{ background: {TEAL} !important; }}
[data-testid="stMetricLabel"] p {{ color: {MUTED} !important; }}
[data-testid="stMetricValue"] {{ color: {NAVY} !important; }}

[data-baseweb="radio"] > div:first-child {{ border-color: {TEAL} !important; }}
[data-baseweb="radio"] label p, [data-testid="stRadio"] p {{ color: {INK} !important; }}

[data-testid="stExpander"] summary p {{ color: {INK} !important; font-weight: 600; }}
[data-testid="stExpander"] {{ background: #fff; border: 1px solid {LINE}; border-radius: 10px; }}
</style>
"""


def _style_text(block: str) -> str:
    return "\n".join(re.findall(r"<style>(.*?)</style>", block, re.S))


_PERSIST_JS = """<script>
(function () {
  const d = window.parent.document, parts = __PARTS__;
  for (const [id, css] of Object.entries(parts)) {
    let el = d.getElementById(id);
    if (css === null) { if (el) el.remove(); continue; }
    if (!el) { el = d.createElement("style"); el.id = id; d.head.appendChild(el); }
    if (el.textContent !== css) el.textContent = css;
  }
  if (!d.getElementById("iw-team-pill")) {
    const p = d.createElement("div");
    p.id = "iw-team-pill"; p.className = "iw-team"; p.innerHTML = "Team · <span>DECODIANS</span>";
    d.body.appendChild(p);
  }
  const box = window.frameElement && window.frameElement.closest('[data-testid="stElementContainer"]');
  if (box) box.style.cssText = "position:absolute;width:0;height:0;overflow:hidden;margin:0;padding:0";
})();
</script>"""


def persist_css(parts: dict) -> None:
    """Keep styles in the page <head>, outside Streamlit's element tree.

    Streamlit drops every element of the old page before drawing the new one, so styles sent with
    st.markdown vanish for ~150 ms on each page switch and the default look flashes through. Styles in
    <head> survive that. parts: {element id: css text, or None to remove}."""
    try:
        import streamlit.components.v1 as components
        components.html(_PERSIST_JS.replace("__PARTS__", json.dumps(parts)), height=0)
    except Exception:          # a future Streamlit without components.html: pages still work, just may flash
        pass


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)       # first paint and headless tests


def ai_banner() -> None:
    st.markdown(
        '<div class="iw-banner"><b>AI disclosure:</b> findings are generated with Gemini and '
        'checked against your brand kit. A human must approve every suggestion.</div>',
        unsafe_allow_html=True,
    )


def empty_state(msg: str) -> None:
    st.markdown(f'<div class="iw-empty">{html.escape(msg)}</div>', unsafe_allow_html=True)


def metric_row(items) -> None:
    cols = st.columns(len(items))
    for col, (n, label, kind) in zip(cols, items):
        col.markdown(
            f'<div class="iw-kpi {kind}"><div class="n">{n}</div><div class="l">{html.escape(label)}</div></div>',
            unsafe_allow_html=True,
        )


def source_quote(source_text: str, source_id: str, owner: str = "") -> None:
    owner_part = f" · {html.escape(owner)}" if owner else ""
    st.markdown(
        f'<div class="iw-quote">{html.escape(source_text)}'
        f'<div class="src">{html.escape(source_id)}{owner_part}</div></div>',
        unsafe_allow_html=True,
    )
    if source_id == "UNVERIFIED":
        st.warning("No approved source supports this claim.")


def checker_tag(checked_by: str) -> str:
    if checked_by == "ai":
        return '<span class="iw-tag ai">AI</span>'
    return '<span class="iw-tag">Rule</span>'


def highlight_html(text: str, findings) -> str:
    out, pos = [], 0
    for i, f in enumerate(sorted(findings, key=lambda x: x["start"]), 1):
        if f["start"] < pos:
            continue
        color = CATEGORY_COLORS.get(str(f.get("category", "")).lower(), MUTED)
        out.append(html.escape(text[pos:f["start"]]))
        out.append(
            f'<mark style="text-decoration-color:{color};">'
            f'{html.escape(text[f["start"]:f["end"]])}</mark>'
            f'<sup style="color:{color}">[{i}]</sup>'
        )
        pos = f["end"]
    out.append(html.escape(text[pos:]))
    return f'<div class="iw-text">{"".join(out)}</div>'


def not_connected(err) -> None:
    st.markdown(
        f'<div class="iw-card" style="border-color:#B45309">'
        f'<h4>Backend not connected: {err.part}</h4>'
        f'<p>This screen needs <code>{err.needs}</code>. Owner: {err.owner}. '
        f'It will start working as soon as that is merged into main and you run <code>git pull</code>.</p></div>',
        unsafe_allow_html=True,
    )


ROLE_INFO = {
    # username: (initials, role title, one line on what they do, badge background, badge text colour)
    "asha": ("CR", "Creator", "Write and check campaign copy, then send it for approval", "#E3F3F0", "#0B5E52"),
    "meera": ("MG", "Manager", "Approve or return drafts and see unclear guidelines", "#E8EEFB", "#1A4FB0"),
    "ravi": ("AD", "Admin", "Keep facts current and manage the brand kit", "#F3E9FB", "#6B2FA3"),
}


def icon_src() -> str:
    url = static_url("logo_icon.png")
    if url:
        return url
    p = APP_DIR / "assets" / "logo_icon.png"
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode() if p.exists() else logo_src()


def wordmark(dark_bg: bool = True, size: int = 30) -> str:
    """Logo icon + 'inkwise.ai' as live text, so it sits cleanly on any background."""
    col = "#fff" if dark_bg else NAVY
    return (f'<div class="iw-wordmark"><img src="{icon_src()}" style="width:{size}px;height:{size}px"/>'
            f'<span style="color:{col}">inkwise<em>.ai</em></span></div>')


def _contours_svg(stroke: str = "#9FB4D6", scale: float = 1.0) -> str:
    """Topographic contour lines (deterministic). Served as a static image when it was built
    (scripts/build_static_assets.py), otherwise as an inline SVG data URI."""
    known = {("#9FB4D6", 1.0): "contours_login.webp", ("#1B2A4E", .55): "contours_inner.webp"}
    url = static_url(known.get((stroke, scale), ""))
    if url:
        return url
    import math, urllib.parse
    w, h = 1400, 1000
    centres = [(260, 260, 1.0), (1080, 760, 1.25), (900, 160, .8)]
    paths = []
    for cx, cy, sc in centres:
        for k in range(1, 15):
            r = k * 34 * sc
            pts = []
            for i in range(0, 361, 6):
                a = math.radians(i)
                wob = 1 + .12 * math.sin(3 * a + k * .45) + .07 * math.cos(5 * a - k * .3)
                pts.append(f"{cx + r * wob * math.cos(a):.1f},{cy + r * .78 * wob * math.sin(a):.1f}")
            op = (.16 if k % 5 == 0 else .07) * scale
            paths.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{stroke}" stroke-opacity="{op:.3f}" stroke-width="1"/>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid slice">'
           + "".join(paths) + "</svg>")
    return "data:image/svg+xml;utf8," + urllib.parse.quote(svg)


def _photo(name: str):
    """Static URL of a background photo, or an inline data URI if app/static was not built."""
    url = static_url(name)
    if url:
        return url
    p = APP_DIR / "assets" / name
    return f"data:image/jpeg;base64,{base64.b64encode(p.read_bytes()).decode()}" if p.exists() else None


LOGIN_BG_DEFAULT = "desklines"   # login background: desklines | desksoft | desk | linesfull | lines | ink


def _login_bg(choice: str = "") -> str:
    """Full-screen photo (app/assets/login_bg_<choice>.jpg) under a navy tint that is darkest behind the text,
    or the code-drawn contour panel when choice is 'lines' or the photo is missing."""
    choice = (choice or LOGIN_BG_DEFAULT).lower()
    if choice == "linesfull":     # navy everywhere, contour lines across the whole screen, darker behind the text
        return ("radial-gradient(ellipse 60% 70% at 25% 45%, rgba(9,14,28,.55), transparent 70%), "
                "radial-gradient(ellipse 120% 100% at 50% 50%, transparent 55%, rgba(5,9,20,.6) 100%), "
                f'url("{_contours_svg()}") center / cover no-repeat, '
                "linear-gradient(135deg, #0F1A31 0%, #16264A 55%, #10203A 100%)")
    if choice == "desklines":     # desk photo, soft tint, contour lines drawn over it
        photo = _photo("login_bg_desk.jpg")
        if photo:
            return (f'url("{_contours_svg()}") center / cover no-repeat, '
                    "linear-gradient(90deg, rgba(10,16,32,.80) 0%, rgba(10,16,32,.45) 46%, rgba(10,16,32,.10) 100%), "
                    f'url("{photo}") center / cover no-repeat, #0E1730')
    if choice == "desksoft":      # same desk photo, lighter tint so more of the photo shows
        photo = _photo("login_bg_desk.jpg")
        if photo:
            return ("linear-gradient(90deg, rgba(10,16,32,.80) 0%, rgba(10,16,32,.45) 46%, rgba(10,16,32,.10) 100%), "
                    f'url("{photo}") center / cover no-repeat, #0E1730')
    photo = _photo(f"login_bg_{choice}.jpg") if choice != "lines" else None
    if photo:
        tint = (".90, .78, .42" if choice == "ink" else ".86, .66, .30")
        a1, a2, a3 = [x.strip() for x in tint.split(",")]
        return (f"linear-gradient(90deg, rgba(10,16,32,{a1}) 0%, rgba(10,16,32,{a2}) 46%, rgba(10,16,32,{a3}) 100%), "
                f'url("{photo}") center / cover no-repeat, #0E1730')
    return ("radial-gradient(ellipse 70% 60% at 20% 30%, rgba(255,255,255,.05), transparent 70%) 0 0 / 52% 100% no-repeat, "
            "radial-gradient(ellipse 90% 90% at 30% 50%, transparent 55%, rgba(5,9,20,.55) 100%) 0 0 / 52% 100% no-repeat, "
            f'url("{_contours_svg()}") 0 0 / 52% 100% no-repeat, '
            "linear-gradient(90deg, #121C33 52%, #F5F2EB 52%)")



LOGIN_CSS = f"""
<style>
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
[data-testid="stExpandSidebarButton"], header[data-testid="stHeader"] {{ display:none !important; }}
@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif&display=swap');
.stApp {{ background: __LOGIN_BG__ !important; background-attachment: fixed !important; }}
.block-container {{ padding-top:0 !important; max-width:1120px !important; }}
.iw-hero {{ color:#E8EEF8; margin-top:4vh; padding-right:12px; }}
.iw-hero .eyebrow {{ font-size:.68rem; letter-spacing:.2em; font-weight:600; color:#C9D3E3; margin-bottom:18px; }}
.iw-hero h1 {{ font-family:'Instrument Serif', Georgia, serif; font-size:3rem; line-height:1.02; font-weight:400;
  letter-spacing:-.01em; color:#fff !important; margin:0 0 18px; }}
.iw-hero h1 span {{ font-style:italic; color:#fff; }}
.iw-hero p.lead {{ font-size:1rem; color:#B9C4D9; max-width:440px; line-height:1.55; margin:0 0 26px; }}
.iw-proof {{ display:flex; flex-direction:column; gap:10px; max-width:440px; }}
.iw-proof div {{ display:flex; gap:14px; align-items:flex-start; padding:10px 0;
  border-top:1px solid rgba(255,255,255,.16); }}
.iw-proof b {{ color:#fff; font-size:.9rem; }}
.iw-proof small {{ color:#9FB0CC; font-size:.78rem; display:block; }}
.iw-proof .n {{ min-width:58px; font-weight:600; color:#fff; font-size:.95rem; }}
.iw-preview {{ background:#fff; border-radius:12px; padding:14px 18px 12px; max-width:460px; margin:2px 0 18px;
  box-shadow:0 18px 40px rgba(5,10,24,.35); color:#1B2A4E; }}
.iw-preview .bar {{ display:flex; gap:6px; margin-bottom:12px; }}
.iw-preview .bar i {{ width:8px; height:8px; border-radius:50%; background:#E5E7EB; display:block; }}
.iw-preview .bar b {{ margin-left:auto; font-size:.62rem; letter-spacing:.12em; color:#9AA3B2; font-weight:600; }}
.iw-preview .copy {{ font-size:.86rem; line-height:1.6; color:#33415C; }}
.iw-preview mark {{ background:#FDECEC; color:#9F1D1D; padding:1px 3px; border-radius:3px;
  border-bottom:2px solid #D93025; }}
.iw-preview mark.t {{ background:#FFF4E0; color:#8A4B06; border-bottom-color:#B45309; }}
.iw-preview .finding {{ margin-top:12px; border:1px solid #EEF0F4; border-left:3px solid #D93025; border-radius:8px;
  padding:10px 12px; background:#FCFCFD; }}
.iw-preview .finding .top {{ display:flex; gap:8px; align-items:center; font-size:.72rem; color:#5A6480; }}
.iw-preview .tag {{ font-weight:700; font-size:.62rem; letter-spacing:.06em; padding:2px 7px; border-radius:999px;
  background:#FDECEC; color:#B42318; }}
.iw-preview .src {{ font-family: ui-monospace, Menlo, monospace; font-size:.7rem; background:#F3F4F6; padding:1px 6px;
  border-radius:4px; color:#1B2A4E; }}
.iw-preview .why {{ font-size:.8rem; color:#1B2A4E; margin:6px 0 4px; }}
.iw-preview .fix {{ font-size:.78rem; color:#0B5E52; }}
.iw-preview .fix b {{ color:#0B5E52; }}
.iw-preview .btns {{ display:flex; gap:6px; margin-top:8px; }}
.iw-preview .btns label {{ font-size:.66rem; font-weight:600; padding:4px 10px; border-radius:6px; border:1px solid #E5E7EB;
  color:#33415C; cursor:pointer; background:#fff; transition:all .12s; user-select:none; }}
.iw-preview .btns label:hover {{ border-color:#12917F; color:#0B5E52; }}
.iw-preview .btns label.ok {{ background:#12917F; border-color:#12917F; color:#fff; }}
.iw-preview .btns label.ok:hover {{ background:#0E7A6B; color:#fff; }}
.iw-preview input.iwd {{ position:absolute; opacity:0; pointer-events:none; width:0; height:0; }}
.iw-preview .sp .v1, .iw-preview .sp .v2, .iw-preview .sp .v3 {{ display:none; }}
.iw-preview mark.fixed {{ background:#E8F6F2; color:#0B5E52; border-bottom-color:#12917F; }}
.iw-preview .res {{ display:none; font-size:.72rem; margin-top:8px; padding:6px 10px; border-radius:6px; }}
.iw-preview .ra {{ background:#E8F6F2; color:#0B5E52; }} .iw-preview .re {{ background:#FFF4E0; color:#8A4B06; }}
.iw-preview .rr {{ background:#F3F5F9; color:#33415C; }}
#iwd-a:checked ~ .copy .v0, #iwd-e:checked ~ .copy .v0, #iwd-r:checked ~ .copy .v0 {{ display:none; }}
#iwd-a:checked ~ .copy .v1, #iwd-e:checked ~ .copy .v2, #iwd-r:checked ~ .copy .v3 {{ display:inline; }}
#iwd-a:checked ~ .finding .ra, #iwd-e:checked ~ .finding .re, #iwd-r:checked ~ .finding .rr {{ display:block; }}
#iwd-a:checked ~ .finding .btns label[for=iwd-a], #iwd-e:checked ~ .finding .btns label[for=iwd-e],
#iwd-r:checked ~ .finding .btns label[for=iwd-r] {{ box-shadow:0 0 0 2px #1B2A4E inset; }}
#iwd-a:checked ~ .finding, #iwd-e:checked ~ .finding, #iwd-r:checked ~ .finding {{ border-left-color:#12917F; }}
.iw-human {{ text-align:center; margin-top:12px; padding-top:10px; border-top:1px dashed #E5E7EB; }}
.iw-human b {{ display:block; font-family:'Instrument Serif', Georgia, serif; font-weight:400; font-size:1.15rem;
  color:#1B2A4E; letter-spacing:.01em; }}
.iw-human small {{ display:block; font-size:.7rem; color:#8A93A6; margin-top:1px; }}
.iw-trust {{ display:flex; flex-wrap:wrap; gap:8px 18px; max-width:470px; }}
.iw-trust span {{ font-size:.74rem; color:#C9D3E3; display:flex; align-items:center; gap:6px; }}
.iw-trust span::before {{ content:""; width:6px; height:6px; border-radius:50%; background:#5FD3C1; display:inline-block; }}
.iw-wordmark {{ display:flex; align-items:center; gap:10px; }}
.iw-wordmark img {{ border-radius:8px; box-shadow:0 2px 8px rgba(0,0,0,.25); }}
.iw-wordmark span {{ font-weight:700; font-size:1.25rem; letter-spacing:-.02em; }}
.iw-hero .iw-wordmark span {{ font-size:2rem; }}
.iw-hero .iw-wordmark {{ gap:14px; }}
.iw-hero .iw-wordmark img {{ border-radius:12px; }}
.iw-wordmark em {{ font-style:normal; color:#2BB39D; }}
.iw-hero .iw-wordmark {{ margin-bottom:30px; }}
.iw-card-title {{ font-family:'Instrument Serif', Georgia, serif; font-size:2rem; color:{NAVY}; margin:0 0 4px; line-height:1.1; }}
.iw-card-sub {{ color:{MUTED}; font-size:.86rem; margin:0 0 18px; }}
.iw-trust {{ display:grid !important; grid-template-columns:1fr 1fr; gap:8px 22px !important; max-width:470px; }}
.iw-trust span {{ align-items:flex-start !important; line-height:1.35; }}
.iw-trust span::before {{ margin-top:5px; flex:none; }}
.st-key-iw_login {{ max-width:420px; margin:calc(4vh + 72px) auto 2rem; background:#fff;
  border:1px solid #E7E2D8; border-radius:14px; padding:30px 30px 18px;
  box-shadow:0 1px 2px rgba(20,24,33,.04), 0 12px 32px rgba(20,24,33,.08); }}
@media (max-width: 900px) {{ .stApp {{ background:#16223D !important; }} .iw-hero {{ margin-top:4vh; }}
  .iw-hero h1 {{ font-size:2.4rem; }} }}
.iw-brand {{ display:flex; align-items:center; gap:12px; margin-bottom:22px; }}
.iw-brand img {{ height:44px; border-radius:10px; }}
.iw-brand .eyebrow {{ font-size:.66rem; letter-spacing:.14em; font-weight:700; color:{TEAL}; }}
.iw-login-h1 {{ font-size:1.65rem; font-weight:700; color:{NAVY}; margin:0 0 4px; letter-spacing:-.02em; }}
.iw-login-sub {{ color:{MUTED}; font-size:.9rem; margin:0 0 22px; }}
.iw-login-h2 {{ font-size:.95rem; font-weight:700; color:{NAVY}; margin:0 0 2px; }}
.iw-login-note {{ color:{MUTED}; font-size:.8rem; margin:0 0 10px; }}
.st-key-iw_roles [data-testid="stVerticalBlock"] {{ gap:.5rem; }}
.st-key-iw_roles button {{ width:100%; position:relative; justify-content:flex-start !important;
  min-height:60px; padding:10px 40px 10px 62px !important; border-radius:12px !important;
  background:#fff !important; border:1px solid {LINE} !important; transition:border-color .15s, box-shadow .15s; }}
.st-key-iw_roles button:hover {{ border-color:{TEAL} !important; box-shadow:0 2px 10px rgba(18,145,127,.12); }}
.st-key-iw_roles button p {{ text-align:left; white-space:normal; font-weight:400 !important;
  font-size:.82rem; color:{MUTED} !important; line-height:1.35; }}
.st-key-iw_roles button p strong {{ display:block; font-size:.92rem; color:{NAVY}; font-weight:700; }}
.st-key-iw_roles button::after {{ content:"→"; position:absolute; right:16px; top:50%;
  transform:translateY(-50%); color:{MUTED}; font-size:1rem; }}
.st-key-iw_roles button:hover::after {{ color:{TEAL}; }}
.st-key-iw_login [data-testid="stExpander"] {{ border:none !important; background:transparent !important; }}
.st-key-iw_login [data-testid="stExpander"] summary p {{ font-size:.82rem; color:{MUTED} !important; font-weight:600; }}
.iw-team {{ position:fixed; right:22px; bottom:16px; z-index:1000; font-size:.7rem; font-weight:600;
  letter-spacing:.12em; color:#C3CCDB !important; text-transform:uppercase; background:rgba(10,16,32,.72) !important;
  backdrop-filter:blur(6px); box-shadow:none !important; padding:6px 12px !important; border-radius:999px;
  border:1px solid rgba(255,255,255,.12); }}
.iw-team span {{ color:#fff; font-weight:700; }}
.iw-or {{ display:flex; align-items:center; gap:10px; margin:14px 0 10px; color:#9AA3B2; font-size:.72rem;
  text-transform:uppercase; letter-spacing:.14em; }}
.iw-or::before, .iw-or::after {{ content:""; flex:1; height:1px; background:#E7E2D8; }}
.st-key-acct_open button {{ min-height:46px; border-radius:12px !important; background:{NAVY} !important;
  border:1px solid {NAVY} !important; transition:background .15s, transform .05s; }}
.st-key-acct_open button p {{ color:#fff !important; font-weight:600 !important; font-size:.9rem; }}
.st-key-acct_open button:hover {{ background:#24376A !important; }}
.st-key-acct_open button:active {{ transform:translateY(1px); }}
.st-key-iw_acct [data-testid="stForm"] {{ padding:0; border:none; }}
.st-key-iw_acct input {{ border-radius:10px !important; }}
.st-key-acct_close button {{ background:transparent !important; border:none !important; padding:4px 0 !important;
  min-height:0 !important; }}
.st-key-acct_close button p {{ color:{MUTED} !important; font-size:.8rem; text-decoration:underline; font-weight:500 !important; }}
.iw-soon {{ background:#F1F7F6; border:1px solid #CDE8E2; border-radius:10px; padding:10px 12px; margin:6px 0 4px; }}
.iw-soon b {{ display:block; color:#0B5E52; font-size:.84rem; }}
.iw-soon span {{ display:block; color:#33415C; font-size:.78rem; margin-top:2px; line-height:1.4; }}
.iw-login-foot {{ text-align:center; color:{MUTED}; font-size:.72rem; margin-top:14px; }}
""" + "".join(
    f".st-key-login_{u} button::before {{ content:'{i}'; position:absolute; left:14px; top:50%; transform:translateY(-50%);"
    f" width:34px; height:34px; border-radius:9px; background:{bg}; color:{fg}; font-weight:700; font-size:.72rem;"
    f" display:flex; align-items:center; justify-content:center; letter-spacing:.04em; }}"
    for u, (i, _r, _d, bg, fg) in ROLE_INFO.items()) + "</style>"


TEAM_BADGE = '<div class="iw-team">Team · <span>DECODIANS</span></div>'


def restore_session() -> None:
    """Keep a demo person signed in across a browser refresh.

    Streamlit forgets everything on refresh, so the signed-in demo account is kept in the address
    (?as=asha). Only the three demo accounts can be restored this way; they have no password anyway."""
    ss = st.session_state
    if ss.get("auth") or ss.get("signed_out"):
        return
    who = str(st.query_params.get("as", "")).strip().lower()
    if who and who in ROLE_INFO and switch_user(who):
        ss.landed_for = who            # a refresh keeps you on the page you were on
        ss.splash_done = True


def _sign_in(result: dict) -> None:
    st.session_state.pop("signed_out", None)
    st.session_state.auth = True
    st.session_state.user = result.get("user", "")
    st.session_state.role = result.get("role", "Creator")
    st.session_state.team = result.get("team", "")


def _login_click(username: str) -> None:
    """Sign-in row callback: one run per click; a failure is shown on the next run."""
    if not switch_user(username):
        st.session_state["login_failed"] = True


def switch_user(username: str) -> bool:
    """Sign in as a demo account (used by the login rows and the guided tour)."""
    try:
        result = services.demo_sign_in(username)
    except Exception:
        result = None
    if result:
        _sign_in(result)
        return True
    return False


BOOT_CSS = ".stApp { background: #0E1730 !important; }"   # navy under the splash and sign-in, kept in <head>


def login_screen() -> None:
    # keep a navy background in <head> so nothing light shows between the splash and this page
    persist_css({"iw-global": _style_text(CSS), "iw-shell": None, "iw-boot": BOOT_CSS})
    bg_choice = st.query_params.get("bg", "")
    st.markdown(LOGIN_CSS.replace("__LOGIN_BG__", _login_bg(bg_choice)), unsafe_allow_html=True)
    if st.query_params.get("card", "") == "glass":
        st.markdown("""<style>
        .st-key-iw_login { background:rgba(255,255,255,.80) !important; backdrop-filter:blur(18px) saturate(140%);
          -webkit-backdrop-filter:blur(18px) saturate(140%); border:1px solid rgba(255,255,255,.55) !important; }
        .st-key-iw_roles button { background:rgba(255,255,255,.78) !important; }
        </style>""", unsafe_allow_html=True)
    accounts = services.demo_accounts()
    hero, card = st.columns([1.15, 1], gap="large")
    with hero:
        ev = services.eval_summary() if hasattr(services, "eval_summary") else {}
        recall = ev.get("recall", "")
        st.markdown(
            '<div class="iw-hero">' + wordmark(True, 52) + '<div class="eyebrow">CONTENT GOVERNANCE BEFORE YOU PUBLISH</div>'
            '<h1>Every claim,<br/><span>traced to its source.</span></h1>'
            '<p class="lead">Inkwise checks campaign copy against your guidelines, approved facts and glossary, '
            'shows the source behind every finding, and keeps a person in charge of every change.</p>'
            '<div class="iw-preview"><div class="bar"><i></i><i></i><i></i><b>REVIEW · DIWALI LAUNCH POST</b></div>'
            '<input type="radio" name="iwd" id="iwd-a" class="iwd"/><input type="radio" name="iwd" id="iwd-e" class="iwd"/>'
            '<input type="radio" name="iwd" id="iwd-r" class="iwd"/>'
            '<div class="copy">Join <span class="sp"><mark class="v0">2 million happy users</mark>'
            '<mark class="v1 fixed">happy users</mark><mark class="v2 fixed">our growing community</mark>'
            '<mark class="v3">2 million happy users</mark></span> of <mark class="t">LumoraPay</mark> and '
            'send money to family this festive season.</div>'
            '<div class="finding"><div class="top"><span class="tag">EXPIRED FACT</span>'
            '<span class="src">F01</span><span>owner: Comms team · expired 30 Sep 2026</span></div>'
            '<div class="why">This figure comes from an approved fact that has expired. Check it before reuse.</div>'
            '<div class="fix"><b>Suggested:</b> ask Comms team for the current figure, or remove it.</div>'
            '<div class="btns"><label for="iwd-a" class="ok">Accept</label><label for="iwd-e">Edit</label>'
            '<label for="iwd-r">Reject</label></div>'
            '<div class="res ra">✓ Accepted: the expired figure was removed. Logged in the audit trail.</div>'
            '<div class="res re">✎ Edited: your own wording replaced the claim. Logged as an override.</div>'
            '<div class="res rr">✕ Rejected: copy kept as written, with your reason logged for the approver.</div>'
            '</div><div class="iw-human"><b>AI suggests. You decide.</b>'
            '<small>Nothing changes until a person accepts, edits or rejects it.</small></div></div>'
            '<div class="iw-trust">'
            + (f'<span>{html.escape(recall)} recall on 100 labelled samples</span>' if recall else '')
            + '<span>Personal data masked before any AI call</span>'
              '<span>Human approval on every change</span><span>Full audit trail</span></div></div>',
            unsafe_allow_html=True)
    with card, st.container(key="iw_login"):
        st.markdown(
            '<div class="iw-card-title">Sign in</div>'
            '<p class="iw-card-sub">Pick a demo role to explore Inkwise. No password needed.</p>',
            unsafe_allow_html=True)
        with st.container(key="iw_roles"):
            for a in accounts:
                u = a["username"]
                _i, title, desc, _bg, _fg = ROLE_INFO.get(u, ("", a["role"], a["can"], "", ""))
                st.button(f"**{title}** {full_name(u)} · {desc}", key=f"login_{u}", width="stretch",
                          on_click=_login_click, args=(u,))
            if st.session_state.pop("login_failed", False):
                st.error("Sign in failed. Try again in a moment.")
        st.markdown('<div class="iw-or"><span>or</span></div>', unsafe_allow_html=True)
        with st.container(key="iw_acct"):
            if not st.session_state.get("show_acct"):
                st.button("Sign in with your work account", key="acct_open", width="stretch",
                          on_click=st.session_state.__setitem__, args=("show_acct", True))
            else:
                with st.form("login_form", border=False):
                    email = st.text_input("Work email", placeholder="you@company.com")
                    password = st.text_input("Password", type="password")
                    submitted = st.form_submit_button("Continue", type="primary", width="stretch")
                if submitted:
                    name = (email or "").strip().split("@")[0].lower()
                    if not email.strip() or not password:
                        st.warning("Enter your work email and password.")
                    else:
                        result = None
                        for r in ROLES:  # demo accounts still work here (asha, meera, ravi)
                            try:
                                result = services.authenticate(name, password, r)
                            except Exception:
                                result = None
                            if result:
                                break
                        if result:
                            _sign_in(result)
                            st.session_state.show_acct = False
                            st.rerun()
                        else:
                            st.markdown(
                                '<div class="iw-soon"><b>Company accounts are coming with the live release.</b>'
                                '<span>Work email and single sign-on will be available when Inkwise goes live. '
                                'For now, pick a demo role above to explore everything.</span></div>',
                                unsafe_allow_html=True)
                st.button("Back to demo roles", key="acct_close",
                          on_click=st.session_state.__setitem__, args=("show_acct", False))
        st.markdown('<div class="iw-login-foot">Demo workspace · Lumora is a fictional brand · no real data</div>',
                    unsafe_allow_html=True)
    st.stop()


ORG = "Lumora"
FULL_NAMES = {"asha": "Asha Menon", "meera": "Meera Kapoor", "ravi": "Ravi Sharma",
              "dev": "Dev Malhotra", "priya": "Priya Nair"}


def full_name(u: str) -> str:
    return FULL_NAMES.get((u or "").lower(), (u or "").title())
NAV = [  # (page file, tab label, roles that see it; None = everyone). Each person sees only their own workspace.
    ("Home.py", "Home", None),
    ("pages/1_Review.py", "Review", ("Creator",)),
    ("pages/Approvals.py", "Approvals", ("Manager", "Reviewer")),
    ("pages/Fact_Register.py", "Fact Register", ("Admin",)),
    ("pages/Insights.py", "Insights", ("Manager", "Reviewer", "Admin")),
    ("pages/History.py", "History", None),
    ("pages/Knowledge_Base.py", "Brand Kit", None),
    ("pages/Help.py", "Help", None),
]

# Every person gets a workspace with only the pages they need: Creators write and check, Managers sign off,
# Admins keep facts and the brand kit current.
WORKSPACE = {
    "Creator": ("Creator studio", "Write, check and send drafts for approval"),
    "Manager": ("Approval desk", "Sign off drafts and spot guidelines people find unclear"),
    "Reviewer": ("Approval desk", "Sign off drafts and spot guidelines people find unclear"),
    "Admin": ("Admin console", "Keep facts and the brand kit current"),
}
# Pages that belong to one workspace, and the demo person who works there. Fact Register is not here: anyone whose
# team owns a fact may renew it, so it stays open (it is in the Admin's tabs and linked from everyone's Home).
WORKSPACE_PAGES = {
    "pages/1_Review.py": ("asha", "the Creator studio", "writing and checking drafts"),
    "pages/Approvals.py": ("meera", "the Approval desk", "signing off drafts"),
    "pages/Insights.py": ("meera", "the Approval desk and the Admin console", "guideline insights"),
}


DEMO_VIDEO = APP_DIR / "assets" / "demo.mp4"


def demo_video(caption: bool = True) -> bool:
    """The 2-minute walkthrough recorded from the real app. False when the file is missing."""
    if not DEMO_VIDEO.exists():
        return False
    st.video(str(DEMO_VIDEO))
    if caption:
        st.caption("One draft from first check to sign-off: Asha checks and sends it, Meera approves it, "
                   "Ravi renews an expired fact. No sound; captions on screen.")
    return True


WELCOME = {   # what a first-time person needs to know, in plain words, and the one place to start
    "Creator": ("You are Asha, a content creator.",
                "Before anything is published, check it here. Inkwise marks every problem in your copy and shows the "
                "brand rule or fact behind it. You decide what to change, then send the draft to your manager.",
                "Check a sample draft", "pages/1_Review.py"),
    "Manager": ("You are Meera, the manager.",
                "Drafts from your team arrive in the Approval queue. You see what Inkwise found and what the creator "
                "decided, then approve the draft or send it back with a comment.",
                "Open the approval queue", "pages/Approvals.py"),
    "Reviewer": ("You review drafts.",
                 "Drafts arrive in the Approval queue. Read what Inkwise found and what the creator decided, then "
                 "approve or send back.", "Open the approval queue", "pages/Approvals.py"),
    "Admin": ("You are Ravi, the brand admin.",
              "You keep the brand kit current. Facts have owners and expiry dates; renew an expired one and every "
              "open draft that uses it is checked again.", "Open the Fact Register", "pages/Fact_Register.py"),
}


def welcome() -> None:
    """First visit per person: who you are, what you do here, one button to start, and the demo video."""
    ss = st.session_state
    user, role = ss.get("user", ""), ss.get("role", "Creator")
    hidden = ss.setdefault("welcome_hidden", set())
    if user in hidden or role not in WELCOME:
        return
    who, what, go_label, page = WELCOME[role]
    with st.container(key="iw_welcome"):
        c1, c2 = st.columns([3.2, 1.3], gap="large")
        with c1:
            st.markdown(f'<div class="iw-wel"><small>NEW HERE? START WITH THIS</small><h3>{html.escape(who)}</h3>'
                        f'<p>{html.escape(what)}</p></div>', unsafe_allow_html=True)
            b1, b2, b3 = st.columns([1.3, 1.3, 1])
            with b1:
                if st.button(go_label, key="wel_go", type="primary", width="stretch"):
                    hidden.add(user)
                    if role == "Creator":
                        smp = next((x for x in services.demo_samples() if x["id"] == "launch"), None)
                        if smp:
                            ss.rv_text, ss.rv_title = smp["text"], smp["title"].split(" (")[0]
                    try:
                        st.switch_page(page)
                    except Exception:
                        st.rerun()
            b2.button("Show me the whole story", key="wel_story", width="stretch",
                      on_click=lambda: (hidden.add(user), ss.__setitem__("journey_hidden", False)),
                      help="A five-step walkthrough on Check a draft; each step signs you in as the right person")
            b3.button("Hide", key="wel_hide", on_click=hidden.add, args=(user,))
        with c2:
            if not demo_video(caption=False):
                st.markdown('<div class="iw-wel-side">Every page has <b>Help</b> in the tabs, and the bell shows '
                            'what needs you.</div>', unsafe_allow_html=True)
            else:
                st.caption("2-minute demo · no sound")


def can_open(page: str, role: str) -> bool:
    if page not in WORKSPACE_PAGES:
        return True
    roles = next((r for p, _l, r in NAV if p == page), None)
    return roles is None or role in roles


# Tabs are named after the job each person does there (as in a real tool), not after the code page.
TAB_LABELS = {
    "Creator": {"pages/1_Review.py": "Check a draft", "pages/History.py": "My drafts"},
    "Manager": {"pages/Approvals.py": "Approval queue", "pages/History.py": "All drafts"},
    "Reviewer": {"pages/Approvals.py": "Approval queue", "pages/History.py": "All drafts"},
    "Admin": {"pages/History.py": "All drafts"},
}


def visible_tabs(role: str) -> list:
    names = TAB_LABELS.get(role, {})
    return [(p, names.get(p, label), r) for p, label, r in NAV if r is None or role in r]


def attention(kind: str, text: str, page: str = "", label: str = "") -> None:
    """One-line call to action at the top of a page: what needs this person now, and the link that does it."""
    with st.container(key=f"iw_attn_{kind}"):
        c1, c2 = st.columns([5, 1.3], vertical_alignment="center")
        c1.markdown(f'<div class="iw-attn"><span class="dot"></span><div>{text}</div></div>', unsafe_allow_html=True)
        if page:
            with c2:
                try:
                    st.page_link(page, label=label, width="stretch")
                except Exception:
                    pass


def _workspace_guard() -> None:
    """A page from another person's workspace (opened by link or address): say whose it is and offer both ways out."""
    ss = st.session_state
    page, role = _current_page(), ss.get("role", "Creator")
    if can_open(page, role):
        return
    owner, where, what = WORKSPACE_PAGES[page]
    mine = WORKSPACE.get(role, ("your workspace", ""))[0]
    st.markdown(
        f'<div class="iw-guard"><span class="ic">⇄</span><div><small>NOT IN YOUR WORKSPACE</small>'
        f'<h3>This page is part of {html.escape(where)}</h3>'
        f'<p>{html.escape(full_name(ss.get("user", "")))} works in the <b>{html.escape(mine)}</b>, so '
        f'{html.escape(what)} is not one of your tabs. {html.escape(full_name(owner))} '
        f'({html.escape(ROLE_INFO.get(owner, ("", "", ""))[1])}) does this in the demo.</p></div></div>',
        unsafe_allow_html=True)
    c1, c2, _ = st.columns([1.2, 1.6, 3])
    with c1:
        try:
            st.page_link("Home.py", label="← Back to my workspace", width="stretch")
        except Exception:
            pass
    if c2.button(f"Continue as {full_name(owner)}", key="guard_switch", type="primary", width="stretch"):
        if switch_user(owner):
            st.rerun()
    footer()
    st.stop()


SHELL_CSS = f"""
<style>
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stExpandSidebarButton"],
[data-testid="stSidebarNav"], header[data-testid="stHeader"] {{ display:none !important; }}
.stApp {{ background: __INNER_BG__ !important; background-attachment: fixed !important; }}
.block-container {{ padding:0 2.6rem 4rem !important; max-width:100% !important; }}
/* hidden <style> blocks before the header still take a flex gap each: take them out of the flow */
[data-testid="stVerticalBlock"] > div:has(~ div > .st-key-iw_header) {{ position:absolute !important; width:0 !important;
  height:0 !important; overflow:hidden !important; }}
/* the header and footer colour bands extend past the content; never let that create a sideways scroll */
[data-testid="stMain"] {{ overflow-x:hidden !important; }}
/* pin the header: its own wrapper is exactly its height, so make the wrapper the sticky element */
[data-testid="stVerticalBlock"] > div:has(> .st-key-iw_header) {{ position:sticky !important; top:0; z-index:999; }}
[data-testid="stAppViewContainer"]::before {{ content:""; position:absolute; top:0; left:0; right:0; height:93px;
  z-index:0; pointer-events:none; background:linear-gradient(90deg, #0D1A31 0%, #13284A 55%, #0F2A3F 100%); }}
[data-testid="stElementContainer"]:has(> iframe[height="0"]), .stIFrame:has(iframe[height="0"]) {{ position:absolute !important; }}
[data-stale="true"] {{ opacity:1 !important; transition:none !important; }}
/* pop-ups appear just below the header bar, so they never cover the person's name or the bell */
[data-testid="stToastContainer"] {{ top:104px !important; }}
/* Streamlit 1.50: an image outside st.columns shrinks to 1rem; make it fill its card */
[data-testid="stElementContainer"]:has([data-testid="stImage"]) {{ width:100% !important; }}
[data-testid="stImage"] img {{ border-radius:10px; }}
.st-key-iw_header {{ position:sticky; top:0; z-index:999; padding:8px 0 6px; margin-bottom:22px;
  background:linear-gradient(90deg, #0D1A31 0%, #13284A 55%, #0F2A3F 100%);
  box-shadow:0 0 0 100vmax #0F213C; clip-path:inset(0 -100vmax 0 -100vmax); }}
.st-key-iw_header::after {{ content:""; position:absolute; left:-100vmax; right:-100vmax; bottom:0; height:1px;
  background:linear-gradient(90deg, transparent, rgba(63,208,182,.55), transparent); }}
.st-key-iw_header .iw-wordmark span {{ color:#fff !important; }}
.st-key-iw_header .iw-wordmark em {{ color:#3FD0B6 !important; }}
.st-key-iw_header .st-key-iw_tabs [data-testid="stPageLink"] a p, .st-key-iw_header .iw-tab-fallback {{ color:rgba(255,255,255,.68) !important; }}
.st-key-iw_header .st-key-iw_tabs [data-testid="stPageLink"] a:hover {{ background-color:rgba(255,255,255,.07) !important; }}
.st-key-iw_header .st-key-iw_tabs [data-testid="stPageLink"] a:hover p {{ color:#fff !important; }}
.st-key-iw_header [class*="st-key-iw_tab_on_"] [data-testid="stPageLink"] a,
.st-key-iw_header [class*="st-key-iw_tab_on_"] .iw-tab-fallback {{ background-color:rgba(63,208,182,.15) !important;
  border-color:rgba(63,208,182,.45) !important; box-shadow:0 0 0 3px rgba(63,208,182,.06); }}
.st-key-iw_header [class*="st-key-iw_tab_on_"] [data-testid="stPageLink"] a p,
.st-key-iw_header [class*="st-key-iw_tab_on_"] .iw-tab-fallback {{ color:#fff !important; }}
.st-key-iw_header .iw-status {{ border:1px solid rgba(255,255,255,.14); }}
.st-key-iw_header .iw-status.ok {{ background:rgba(63,208,182,.14); color:#7FE6D2; }}
.st-key-iw_header .iw-status.ok i {{ background:#3FD0B6; box-shadow:0 0 0 3px rgba(63,208,182,.25); }}
.st-key-iw_header .iw-status.bad {{ background:rgba(239,90,80,.16); color:#FFB4AE; }}
.st-key-iw_header .iw-status.bad i {{ background:#FF6B60; }}
.st-key-iw_header .iw-status:not(.ok):not(.bad) {{ background:rgba(255,255,255,.08) !important; color:rgba(255,255,255,.7) !important; }}
.st-key-iw_header .st-key-iw_user [data-testid="stPopover"] button p {{ color:rgba(255,255,255,.62) !important; }}
.st-key-iw_header .st-key-iw_user [data-testid="stPopover"] button p strong {{ color:#fff !important; }}
.st-key-iw_header .st-key-iw_user [data-testid="stPopover"] button::before {{ background:#3FD0B6 !important; color:#0D1A31 !important; }}
.st-key-iw_header .st-key-iw_user [data-testid="stPopover"] button:hover {{ background:rgba(255,255,255,.06) !important; }}
.st-key-iw_header .st-key-iw_user [data-testid="stPopover"] button svg {{ color:rgba(255,255,255,.7) !important; fill:currentColor; }}
.st-key-iw_header [data-testid="stHorizontalBlock"] {{ align-items:center; }}
.iw-strip {{ display:flex; align-items:center; gap:12px; font-size:.68rem; color:rgba(255,255,255,.62);
  padding:2px 0 7px; margin-bottom:2px; border-bottom:1px solid rgba(255,255,255,.08); white-space:nowrap; overflow:hidden; }}
.iw-strip b {{ color:#fff; font-weight:600; }}
.iw-strip .sp {{ flex:1; }}
.iw-strip .pill.ws {{ background:rgba(63,208,182,.18); color:#7FE6D2; border-color:rgba(63,208,182,.35); font-weight:700; }}
[class*="st-key-iw_attn_"] {{ border-radius:12px; padding:8px 12px 8px 16px; border:1px solid; margin:2px 0 6px; }}
.st-key-iw_attn_bad {{ background:#FDF1F0; border-color:#F5C9C4; }}
.st-key-iw_attn_warn {{ background:#FFF8EC; border-color:#F6DDB0; }}
.st-key-iw_attn_ok {{ background:#EEF8F5; border-color:#C6E7DE; }}
.iw-attn {{ display:flex; gap:12px; align-items:center; font-size:.9rem; color:{NAVY}; }}
.iw-attn .dot {{ width:9px; height:9px; border-radius:50%; flex:none; background:#12917F; }}
.st-key-iw_attn_bad .iw-attn .dot {{ background:#D93025; }} .st-key-iw_attn_warn .iw-attn .dot {{ background:#B45309; }}
[class*="st-key-iw_attn_"] [data-testid="stPageLink"] a {{ background:{NAVY} !important; border-radius:10px !important;
  justify-content:center; padding:8px 12px !important; }}
[class*="st-key-iw_attn_"] [data-testid="stPageLink"] a p {{ color:#fff !important; font-weight:650 !important; }}
.st-key-iw_welcome {{ background:linear-gradient(135deg,#13213F 0%,#1B2A4E 100%); border-radius:16px;
  padding:18px 22px 14px; margin:2px 0 12px; }}
.iw-wel small {{ font-size:.66rem; letter-spacing:.14em; color:#7FE6D2; font-weight:700; }}
.iw-wel h3 {{ font-family:'Instrument Serif', Georgia, serif !important; font-weight:400 !important; color:#fff !important;
  font-size:1.6rem !important; margin:4px 0 6px !important; padding:0 !important; }}
.iw-wel p {{ color:rgba(255,255,255,.82); font-size:.92rem; line-height:1.5; margin:0 0 10px; max-width:640px; }}
.iw-wel-side {{ color:rgba(255,255,255,.8); font-size:.85rem; padding-top:18px; }}
.st-key-iw_welcome [data-testid="stCaptionContainer"] p {{ color:rgba(255,255,255,.65) !important; }}
.st-key-iw_welcome .stButton button[kind="secondary"] {{ background:transparent !important; color:#fff !important;
  border:1px solid rgba(255,255,255,.35) !important; }}
.st-key-iw_welcome .stButton button[kind="secondary"] p {{ color:#fff !important; }}
.iw-guard {{ display:flex; gap:16px; align-items:flex-start; background:#fff; border:1px solid #E2E7F0; border-radius:16px;
  padding:22px 24px; margin:26px 0 14px; box-shadow:0 8px 24px rgba(20,24,33,.05); max-width:760px; }}
.iw-guard .ic {{ width:44px; height:44px; border-radius:12px; background:#E8F6F2; color:#0B5E52; display:flex;
  align-items:center; justify-content:center; font-size:1.3rem; flex:none; }}
.iw-guard small {{ font-size:.66rem; letter-spacing:.12em; color:#8A93A6; font-weight:700; }}
.iw-guard h3 {{ font-family:'Instrument Serif', Georgia, serif !important; font-weight:400 !important; color:{NAVY} !important;
  font-size:1.6rem !important; margin:2px 0 6px !important; padding:0 !important; }}
.iw-guard p {{ color:#5A6480; font-size:.9rem; margin:0; line-height:1.5; }}
.iw-strip .pill {{ font-style:normal; font-weight:600; padding:2px 9px; border-radius:999px;
  background:rgba(255,255,255,.08); color:rgba(255,255,255,.82); }}
.iw-strip .pill.mint {{ background:rgba(63,208,182,.16); color:#7FE6D2; }}
.st-key-iw_footer {{ margin-top:56px; padding:34px 0 0; position:relative; color:rgba(255,255,255,.72);
  background:linear-gradient(90deg, #0D1A31 0%, #13284A 60%, #0F2A3F 100%);
  box-shadow:0 0 0 100vmax #0F213C; clip-path:inset(0 -100vmax -100vmax -100vmax); }}
.st-key-iw_footer::before {{ content:""; position:absolute; left:-100vmax; right:-100vmax; top:0; height:1px;
  background:linear-gradient(90deg, transparent, rgba(63,208,182,.55), transparent); }}
.iw-ft-blurb {{ font-size:.8rem; line-height:1.55; margin:10px 0 12px; max-width:360px; }}
.iw-ft-tags {{ font-size:.7rem; color:#7FE6D2; letter-spacing:.02em; }}
.iw-ft-h {{ font-size:.66rem; letter-spacing:.16em; font-weight:700; color:#fff; margin:4px 0 10px; }}
.iw-ft-li {{ font-size:.8rem; margin:0 0 7px; color:rgba(255,255,255,.72); }}
.st-key-iw_footer [data-testid="stPageLink"] a {{ padding:0 !important; min-height:0 !important; background:transparent !important; }}
.st-key-iw_footer [data-testid="stPageLink"] a p {{ font-size:.8rem !important; color:rgba(255,255,255,.72) !important; font-weight:400 !important; }}
.st-key-iw_footer [data-testid="stPageLink"] a:hover p {{ color:#fff !important; }}
.st-key-iw_footer [data-testid="stPageLink"] {{ margin-bottom:-6px; }}
.iw-team-row {{ margin:24px 0 0; padding-top:18px; border-top:1px solid rgba(255,255,255,.08); text-align:center; }}
.iw-team-h {{ font-size:.62rem; letter-spacing:.18em; font-weight:700; color:rgba(255,255,255,.45); margin-bottom:10px; }}
.iw-team-h b {{ color:#7FE6D2; font-weight:700; }}
.iw-team-grid {{ display:flex; flex-wrap:wrap; justify-content:center; gap:10px; }}
.iw-tm {{ display:inline-flex; align-items:center; gap:9px; padding:6px 8px 6px 6px; border-radius:999px; cursor:default;
  background:rgba(255,255,255,.04); border:1px solid rgba(255,255,255,.08); transition:border-color .15s ease, background-color .15s ease; }}
.iw-tm:hover {{ border-color:rgba(63,208,182,.4); background:rgba(255,255,255,.07); }}
.iw-tm > i {{ font-style:normal; width:28px; height:28px; border-radius:50%; flex:none; display:flex; align-items:center;
  justify-content:center; background:linear-gradient(135deg, #3FD0B6, #12917F); color:#0D1A31; font-weight:700; font-size:.66rem; }}
.iw-tm b {{ display:block; color:#fff; font-size:.78rem; font-weight:600; line-height:1.15; text-align:left; }}
.iw-tm small {{ display:block; color:rgba(255,255,255,.5); font-size:.66rem; line-height:1.2; text-align:left; }}
.iw-tm-l {{ display:inline-flex; gap:4px; margin-left:4px; }}
.iw-tm-l a {{ width:24px; height:24px; border-radius:50%; display:inline-flex; align-items:center; justify-content:center;
  color:rgba(255,255,255,.7) !important; background:rgba(255,255,255,.06); text-decoration:none !important;
  transition:background-color .15s ease, color .15s ease; }}
.iw-tm-l a:hover {{ background:#3FD0B6; color:#0D1A31 !important; }}
.iw-ft-legal {{ display:flex; flex-wrap:wrap; justify-content:center; text-align:center; gap:6px 18px; font-size:.7rem; color:rgba(255,255,255,.5);
  border-top:1px solid rgba(255,255,255,.08); margin-top:22px; padding:14px 0 18px; }}
.iw-ft-legal b {{ color:rgba(255,255,255,.8); font-weight:600; }}
.iw-ph {{ margin:6px 0 20px; }}
.iw-ph .eyebrow {{ font-size:.68rem; letter-spacing:.18em; font-weight:700; color:{TEAL}; margin-bottom:6px; }}
.iw-ph h1 {{ font-family:'Instrument Serif', Georgia, serif !important; font-weight:400 !important; font-size:2.5rem !important;
  color:{NAVY} !important; margin:0 !important; padding:0 !important; line-height:1.1 !important; letter-spacing:-.01em; }}
.iw-ph p {{ color:{MUTED}; font-size:.95rem; margin:6px 0 0; max-width:760px; }}
.iw-stat {{ background:#fff; border:1px solid {LINE}; border-radius:14px; padding:14px 16px; display:flex; gap:12px;
  align-items:center; box-shadow:0 1px 2px rgba(20,24,33,.03); }}
.iw-stat .ic {{ width:40px; height:40px; border-radius:10px; display:flex; align-items:center; justify-content:center;
  font-size:1.1rem; flex:none; }}
.iw-stat .n {{ font-size:1.6rem; font-weight:700; color:{NAVY}; line-height:1; }}
.iw-stat .l {{ font-size:.78rem; color:{MUTED}; margin-top:3px; }}
.iw-panel {{ background:#fff; border:1px solid {LINE}; border-radius:14px; padding:16px 18px; margin-bottom:16px;
  box-shadow:0 1px 2px rgba(20,24,33,.03); }}
.iw-panel h3 {{ font-size:1rem !important; font-weight:700 !important; color:{NAVY} !important; margin:0 0 2px !important; padding:0 !important; }}
.iw-panel .sub {{ font-size:.78rem; color:{MUTED}; margin:0 0 10px; }}
.iw-row {{ display:flex; align-items:center; gap:12px; padding:10px 0; border-top:1px solid #F0F2F6; }}
.iw-row:first-of-type {{ border-top:none; }}
.iw-row .t {{ flex:1; min-width:0; }} .iw-row .t b {{ color:{NAVY}; font-size:.9rem; display:block;
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.iw-row .t small {{ color:{MUTED}; font-size:.76rem; }}
.iw-dot {{ width:8px; height:8px; border-radius:50%; flex:none; }}
.iw-bar {{ display:flex; align-items:center; gap:10px; font-size:.78rem; color:{NAVY}; margin:6px 0; }}
.iw-bar span.k {{ width:96px; color:{MUTED}; text-transform:capitalize; }}
.iw-bar .track {{ flex:1; height:8px; background:#EEF1F5; border-radius:999px; overflow:hidden; }}
.iw-bar .fill {{ height:100%; background:{TEAL}; border-radius:999px; }}
.iw-bar span.v {{ width:44px; text-align:right; font-weight:600; }}
.iw-big {{ display:flex; gap:18px; margin:4px 0 10px; }}
.iw-big div b {{ display:block; font-size:1.5rem; color:{NAVY}; line-height:1.1; }}
.iw-big div small {{ font-size:.72rem; color:{MUTED}; }}
.iw-step {{ display:flex; gap:12px; padding:10px 0; border-top:1px solid #F0F2F6; }}
.iw-step:first-of-type {{ border-top:none; }}
.iw-step .num {{ width:26px; height:26px; border-radius:50%; background:{TEAL_SOFT}; color:#0B5E52; font-weight:700;
  font-size:.8rem; display:flex; align-items:center; justify-content:center; flex:none; }}
.iw-step b {{ color:{NAVY}; font-size:.88rem; }} .iw-step small {{ display:block; color:{MUTED}; font-size:.76rem; line-height:1.4; }}
.iw-wordmark {{ display:flex; align-items:center; gap:10px; }}
.iw-wordmark img {{ border-radius:8px; }}
.iw-wordmark span {{ font-weight:700; letter-spacing:-.02em; }}
.iw-wordmark em {{ font-style:normal; color:#12917F; }}
.st-key-iw_header .iw-wordmark {{ gap:12px; }}
.st-key-iw_header .iw-wordmark span {{ font-size:1.6rem; letter-spacing:-.025em; }}
.st-key-iw_header .iw-wordmark img {{ border-radius:11px; box-shadow:0 4px 14px rgba(0,0,0,.25); }}
.iw-status {{ display:inline-flex; align-items:center; gap:6px; font-size:.72rem; font-weight:600; padding:4px 10px;
  border-radius:999px; white-space:nowrap; }}
.iw-status i {{ width:7px; height:7px; border-radius:50%; display:inline-block; }}
.iw-status.ok {{ background:#E8F6F2; color:#0B5E52; }} .iw-status.ok i {{ background:#12917F; }}
.iw-status.warn {{ background:#FFF4E0; color:#8A4B06; }} .iw-status.warn i {{ background:#B45309; }}
.iw-status.bad {{ background:#FDECEC; color:#B42318; cursor:help; }} .iw-status.bad i {{ background:#D93025; }}
.st-key-iw_tabs [data-testid="stHorizontalBlock"] {{ gap:0 !important; flex-wrap:nowrap; }}
.st-key-iw_tabs [data-testid="stColumn"] {{ min-width:0 !important; }}
/* tabs: every tab is the same element with the same box, so switching pages never moves anything */
.st-key-iw_tabs [data-testid="stPageLink"] {{ margin:0 clamp(0px, .2vw, 3px); }}
.st-key-iw_header .iw-status {{ font-size:clamp(.58rem, .76vw, .72rem); padding:4px clamp(5px, .6vw, 10px); gap:clamp(3px, .4vw, 6px); }}
@media (max-width: 1250px) {{ .st-key-iw_header .st-key-iw_user [data-testid="stPopover"] button p {{ font-size:.7rem !important; }}
  .st-key-iw_header .st-key-iw_user [data-testid="stPopover"] button p strong {{ font-size:.8rem !important; }} }}
.st-key-iw_header .iw-wordmark span {{ font-size:clamp(1.2rem, 1.75vw, 1.6rem) !important; }}
@media (max-width: 1150px) {{ .iw-strip span:nth-of-type(2), .iw-strip .pill:not(.mint) {{ display:none; }} }}
.st-key-iw_tabs [data-testid="stPageLink"] a {{ border-radius:999px !important; padding:7px clamp(2px, .45vw, 8px) !important; min-height:36px;
  border:1px solid transparent !important; background:transparent !important; justify-content:center;
  transition:background-color .15s ease, border-color .15s ease; }}
.st-key-iw_tabs [data-testid="stPageLink"] a p {{ font-size:clamp(.66rem, .96vw, .84rem) !important; font-weight:600 !important;
  white-space:nowrap; letter-spacing:.01em; overflow:visible !important; text-overflow:clip !important; }}
.st-key-iw_tabs [data-testid="stPageLink"] a > * {{ overflow:visible !important; }}
.iw-tab-fallback {{ display:block; text-align:center; padding:7px 12px; min-height:36px; border-radius:999px;
  font-size:.84rem; font-weight:600; white-space:nowrap; border:1px solid transparent; }}
.st-key-iw_user [data-testid="stPopover"] button {{ background:transparent !important; border:none !important;
  padding:4px 6px 4px 50px !important; min-height:46px; position:relative; justify-content:flex-start; }}
.st-key-iw_user [data-testid="stPopover"] button p {{ text-align:left; line-height:1.25; font-size:.78rem; white-space:nowrap;
  color:{MUTED} !important; font-weight:400 !important; }}
.st-key-iw_user [data-testid="stPopover"] button p strong {{ display:block; color:{NAVY}; font-size:.9rem; font-weight:600; }}
.st-key-iw_user [data-testid="stPopover"] button::before {{ content:var(--iw-initials); position:absolute; left:4px; top:50%;
  transform:translateY(-50%); width:38px; height:38px; border-radius:50%; background:{NAVY}; color:#fff;
  font-weight:700; font-size:.8rem; display:flex; align-items:center; justify-content:center; letter-spacing:.03em; }}
[data-testid="stPopoverBody"] {{ min-width:300px; padding:8px !important; border-radius:12px !important; }}
.iw-menu-h {{ font-size:.68rem; letter-spacing:.14em; font-weight:700; color:#8A93A6; padding:6px 10px 6px; }}
[data-testid="stPopoverBody"] .stButton button {{ width:100%; justify-content:flex-start; text-align:left;
  background:transparent !important; border:none !important; border-radius:10px !important; padding:8px 12px !important;
  min-height:52px; }}
[data-testid="stPopoverBody"] .stButton button:hover {{ background:{BG} !important; }}
[data-testid="stPopoverBody"] .stButton button p {{ text-align:left; color:{MUTED} !important; font-size:.8rem;
  font-weight:400 !important; line-height:1.3; }}
[data-testid="stPopoverBody"] .stButton button p strong {{ display:block; color:{NAVY}; font-size:.92rem; font-weight:600; }}
[data-testid="stPopoverBody"] .stButton button:disabled {{ background:#EEF4FF !important; opacity:1 !important; }}
[data-testid="stPopoverBody"] .stButton button {{ position:relative; padding-right:70px !important; }}
[data-testid="stPopoverBody"] .stButton button:disabled p em {{ color:#3C5BD8 !important; font-style:normal;
  position:absolute; right:14px; top:50%; transform:translateY(-50%); font-size:.78rem; }}
.st-key-iw_bell [data-testid="stPopover"] > div > button, .st-key-iw_bell [data-testid="stPopover"] button {{
  background:rgba(255,255,255,.06) !important; border:1px solid rgba(255,255,255,.14) !important; border-radius:999px !important;
  min-height:38px; width:42px; padding:0 !important; position:relative; justify-content:center; }}
.st-key-iw_bell [data-testid="stPopover"] button:hover {{ background:rgba(255,255,255,.12) !important; }}
.st-key-iw_bell [data-testid="stPopover"] button p {{ font-size:1rem; }}
.st-key-iw_bell [data-testid="stPopover"] button svg {{ display:none; }}
.st-key-iw_bell [data-testid="stPopover"] button::after {{ content:var(--iw-unread); position:absolute; top:-5px; right:-6px;
  min-width:18px; height:18px; padding:0 5px; border-radius:999px; background:#FF6B60; color:#fff; font-size:.66rem;
  font-weight:700; display:flex; align-items:center; justify-content:center; box-shadow:0 0 0 2px #13284A; }}
.st-key-iw_bell [data-testid="stPopover"] button[aria-expanded]::after {{ }}
[data-testid="stPopoverBody"]:has(.st-key-nt_read), [data-testid="stPopoverBody"]:has([class*="st-key-nt_"]) {{ min-width:390px; max-width:420px; }}
[data-testid="stPopoverBody"] [class*="st-key-nt_new_"] button {{ background:#F0F8F6 !important; }}
[data-testid="stPopoverBody"] [class*="st-key-nt_new_"] button::before {{ content:""; position:absolute; left:6px; top:50%;
  transform:translateY(-50%); width:7px; height:7px; border-radius:50%; background:#12917F; }}
.iw-nt-empty {{ font-size:.86rem; color:{MUTED}; padding:10px 12px 14px; }}
.st-key-nt_read button {{ min-height:38px !important; border-top:1px solid {LINE} !important; border-radius:0 !important; }}
.st-key-nt_read button p {{ color:#12917F !important; font-weight:600 !important; font-size:.84rem !important; }}
.st-key-iw_signout button {{ min-height:40px !important; border-top:1px solid {LINE} !important; border-radius:0 !important; }}
.st-key-iw_signout button p {{ color:{NAVY} !important; font-size:.88rem !important; }}
.rv-live .rm {{ color:#B42318; background:#FDECEC; text-decoration:line-through; text-decoration-thickness:1.5px;
  border-radius:4px; padding:0 2px; }}
.rv-live .ad {{ color:#0B5E52; background:#DDF3EC; border-radius:4px; padding:0 3px; font-weight:500; }}
.rv-live .kp {{ text-decoration:underline dotted #9AA3B5; text-decoration-thickness:2px; text-underline-offset:4px; }}
.rv-live .mn {{ background:#FFF4E0; border-bottom:2px dashed #B45309; border-radius:3px; padding:0 2px; }}
.rv-live sup.k {{ color:#9AA3B5; }} .rv-live sup.d {{ color:#0B5E52; }} .rv-live sup.m {{ color:#B45309; }}
.rv-legend {{ display:flex; flex-wrap:wrap; gap:14px; font-size:.72rem; color:#5A6480; margin:6px 0 10px; }}
.rv-legend span {{ display:inline-flex; align-items:center; gap:5px; }}
.rv-legend i {{ display:inline-block; width:22px; height:12px; border-radius:3px; }}
</style>
"""


def annotated_image(image_bytes: bytes, findings, max_w: int = 900) -> bytes:
    """The creative with a numbered box for every image finding (colour = type; green = decided)."""
    import io
    from PIL import Image, ImageDraw, ImageFont
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img.thumbnail((max_w, max_w))
    W, H = img.size
    d = ImageDraw.Draw(img, "RGBA")
    size = max(14, W // 45)
    font = None
    for name in ("DejaVuSans-Bold.ttf", "Arial Bold.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                 "/Library/Fonts/Arial Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"):
        try:
            font = ImageFont.truetype(name, size)
            break
        except OSError:
            continue
    if font is None:
        try:
            font = ImageFont.load_default(size=size)
        except TypeError:                     # Pillow < 10.1
            font = ImageFont.load_default()
    for f in findings:
        b = f.get("box")
        if f.get("where") != "image" or not b:
            continue
        decided = f.get("status", "open") != "open"
        col = "#12917F" if decided else CATEGORY_COLORS.get(str(f.get("category", "")).lower(), MUTED)
        x0, y0, x1, y1 = b[0] * W, b[1] * H, b[2] * W, b[3] * H
        pad = 4
        d.rectangle((x0 - pad, y0 - pad, x1 + pad, y1 + pad), outline=col, width=max(3, W // 300))
        label = ("✓" if decided else "") + str(f.get("n", ""))
        tw = d.textlength(label, font=font) + 12
        th = getattr(font, "size", 12) + 10
        lx, ly = max(x0 - pad, 0), max(y0 - pad - th, 0)
        d.rectangle((lx, ly, lx + tw, ly + th), fill=col)
        d.text((lx + 6, ly + 3), label, fill="#FFFFFF", font=font)
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


def live_html(segs) -> str:
    """A draft with every decision applied, shown as tracked changes (segments from review_helpers.revision)."""
    out = []
    for g in segs:
        t, n, k = html.escape(g["text"]), g.get("n"), g["kind"]
        if k == "plain":
            out.append(t)
        elif k == "open":
            c = CATEGORY_COLORS.get(g["category"], MUTED)
            out.append(f'<mark style="text-decoration-color:{c}">{t}</mark><sup style="color:{c}">[{n}]</sup>')
        elif k == "removed":
            out.append(f'<span class="rm" title="Removed by finding {n}">{t}</span>')
        elif k == "added":
            out.append(f'<span class="ad" title="Fix from finding {n}">{t}</span><sup class="d">[{n}✓]</sup>')
        elif k == "kept":
            out.append(f'<span class="kp" title="Finding {n} rejected: kept as written">{t}</span><sup class="k">[{n}✕]</sup>')
        else:
            out.append(f'<span class="mn" title="Accepted: needs your own rewrite">{t}</span><sup class="m">[{n}✎]</sup>')
    return f'<div class="iw-text rv-live">{"".join(out)}</div>'


LIVE_LEGEND = ('<div class="rv-legend">'
               '<span><i style="background:#FDECEC;border:1px solid #F3B4B0"></i>removed</span>'
               '<span><i style="background:#DDF3EC"></i>fix applied ✓</span>'
               '<span><i style="border-bottom:2px dotted #9AA3B5"></i>rejected, kept as written ✕</span>'
               '<span><i style="background:#FFF4E0;border-bottom:2px dashed #B45309"></i>needs a rewrite ✎</span>'
               '<span><i style="border-bottom:2px wavy #D93025"></i>still open</span></div>')


FOOTER_PRODUCT = [("pages/1_Review.py", "Pre-publication check"), ("pages/Approvals.py", "Approvals and sign-off"),
                  ("pages/Fact_Register.py", "Fact Register"), ("pages/Insights.py", "Guideline insights"),
                  ("pages/History.py", "History and audit reports"), ("pages/Knowledge_Base.py", "Brand kit")]
FOOTER_TRUST = ["Every finding cites its source", "Facts with owners and expiry dates", "A person approves every change",
                "Personal data masked before AI", "Full audit trail"]


def _team() -> dict:
    try:
        return json.loads((APP_DIR.parent / "data" / "team.json").read_text(encoding="utf-8"))
    except Exception:
        return {"team": "DECODIANS", "members": []}


def _safe_url(u: str) -> str:
    u = (u or "").strip()
    return html.escape(u, quote=True) if u.startswith(("https://", "http://")) else ""


_ICON_IN = ('<svg viewBox="0 0 24 24" width="12" height="12" aria-hidden="true"><path fill="currentColor" d="M4.98 3.5a2.5 '
            '2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5zM3 9h4v12H3zM9 9h3.8v1.7h.05c.53-1 1.83-2.05 3.77-2.05 4.03 0 4.78 2.65 4.78 '
            '6.1V21h-4v-5.4c0-1.29-.02-2.95-1.8-2.95-1.8 0-2.08 1.4-2.08 2.86V21H9z"/></svg>')
_ICON_GH = ('<svg viewBox="0 0 24 24" width="12" height="12" aria-hidden="true"><path fill="currentColor" d="M12 .5a11.5 11.5 0 '
            '0 0-3.64 22.41c.58.1.79-.25.79-.56v-2c-3.2.7-3.88-1.37-3.88-1.37-.52-1.33-1.28-1.69-1.28-1.69-1.05-.71.08-.7.08-.7 '
            '1.16.08 1.77 1.19 1.77 1.19 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.28 '
            '1.19-3.09-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.17 1.18a11 11 0 0 1 5.77 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 '
            '2.76.11 3.05.74.81 1.19 1.83 1.19 3.09 0 4.42-2.7 5.39-5.26 5.68.41.36.78 1.06.78 2.14v3.17c0 .31.21.67.8.56A11.5 '
            '11.5 0 0 0 12 .5z"/></svg>')


def team_html() -> str:
    """Slim, centred 'Built by DECODIANS' row: avatar, name, role and small LinkedIn / GitHub icons.
    What each person built is in the tooltip, so the footer stays light."""
    t = _team()
    pills = []
    for m in t.get("members", []):
        links = "".join(
            f'<a href="{url}" target="_blank" rel="noopener noreferrer" title="{label} · {html.escape(m.get("name", ""))}"'
            f' aria-label="{label}">{icon}</a>'
            for label, url, icon in (("LinkedIn", _safe_url(m.get("linkedin")), _ICON_IN),
                                     ("GitHub", _safe_url(m.get("github")), _ICON_GH)) if url)
        pills.append(
            f'<div class="iw-tm" title="{html.escape(m.get("built", ""), quote=True)}">'
            f'<i>{html.escape(_initials(m.get("name", "")))}</i>'
            f'<div><b>{html.escape(m.get("name", ""))}</b><small>{html.escape(m.get("role", ""))}</small></div>'
            + (f'<span class="iw-tm-l">{links}</span>' if links else "") + "</div>")
    if not pills:
        return ""
    return (f'<div class="iw-team-row"><div class="iw-team-h">BUILT BY <b>{html.escape(t.get("team", ""))}</b></div>'
            f'<div class="iw-team-grid">{"".join(pills)}</div></div>')


def footer() -> None:
    """Navy footer at the bottom of every signed-in page."""
    def link(page, label):
        try:
            st.page_link(page, label=label)
        except Exception:                       # headless tests: no multipage context
            st.markdown(f'<div class="iw-ft-li">{html.escape(label)}</div>', unsafe_allow_html=True)

    with st.container(key="iw_footer"):
        c1, c2, c3, c4 = st.columns([1.6, 1, 1.1, 1], gap="large")
        with c1:
            st.markdown(wordmark(True, 34)
                        + '<div class="iw-ft-blurb">Checks campaign copy and creatives against your guidelines, '
                          'approved facts and glossary, shows the source behind every finding, and keeps a person '
                          'in charge of every change.</div>'
                          '<div class="iw-ft-tags">Built for CodeTitans India 2026 · Round 3 · DECODIANS</div>',
                        unsafe_allow_html=True)
        with c2:
            st.markdown('<div class="iw-ft-h">PRODUCT</div>', unsafe_allow_html=True)
            mine = {p for p, _l, _r in visible_tabs(st.session_state.get("role", "Creator"))}
            for page, label in FOOTER_PRODUCT:
                if page in mine:
                    link(page, label)
        with c3:
            st.markdown('<div class="iw-ft-h">TRUST AND GOVERNANCE</div>'
                        + "".join(f'<div class="iw-ft-li">{html.escape(x)}</div>' for x in FOOTER_TRUST),
                        unsafe_allow_html=True)
        with c4:
            st.markdown('<div class="iw-ft-h">RESOURCES</div>', unsafe_allow_html=True)
            link("pages/Help.py", "Help Centre")
            link("pages/Help.py", "Methodology and AI disclosure")
            link("pages/Help.py", "Known limitations")
        st.markdown(team_html(), unsafe_allow_html=True)
        st.markdown('<div class="iw-ft-legal"><span>© 2026 <b>Inkwise.ai</b></span>'
                    '<span>Lumora is a fictional brand; all data is synthetic</span>'
                    '<span>AI findings are suggestions, never automatic edits</span>'
                    '<span>Gemini is used for AI checks; personal data is masked first</span></div>',
                    unsafe_allow_html=True)


def page_header(eyebrow: str, title: str, subtitle: str = "") -> None:
    """Same header on every page: small category label, serif title, one-line purpose."""
    st.markdown(f'<div class="iw-ph"><div class="eyebrow">{html.escape(eyebrow.upper())}</div><h1>{html.escape(title)}</h1>'
                + (f"<p>{html.escape(subtitle)}</p>" if subtitle else "") + "</div>", unsafe_allow_html=True)


def stat_cards(items) -> None:
    """items: (number, label, icon, tint bg, tint fg)."""
    cols = st.columns(len(items))
    for col, (n, label, icon, bg, fg) in zip(cols, items):
        col.markdown(f'<div class="iw-stat"><div class="ic" style="background:{bg};color:{fg}">{icon}</div>'
                     f'<div><div class="n">{html.escape(str(n))}</div><div class="l">{html.escape(label)}</div></div></div>',
                     unsafe_allow_html=True)


JOURNEY = [
    # (step, person, title, what to do, page, sample to preload)
    ("1", "asha", "Check a draft", "Load the “Launch post” sample and run the check. The expired 2-million figure is "
     "contradicted by fact F01; the “fastest app” claim has no source, so it is UNVERIFIED.", "pages/1_Review.py", "launch"),
    ("2", "asha", "Fix it", "Accept, edit or reject each finding. Every decision is logged, then send the draft "
     "for approval.", "pages/1_Review.py", None),
    ("3", "meera", "Sign off", "Open Approvals, read the findings and the creator's decisions, then approve with a "
     "comment or send it back.", "pages/Approvals.py", None),
    ("4", "ravi", "Renew a fact", "In the Fact Register, renew F01 with a new date. Open drafts that cite it are "
     "re-checked straight away, and the renewal is logged.", "pages/Fact_Register.py", None),
    ("5", "meera", "Fix an unclear rule", "Insights shows which guidelines reviewers keep overriding. Ask for a "
     "clearer wording; an admin can accept it.", "pages/Insights.py", None),
]

JOURNEY_CSS = """<style>
.st-key-iw_journey { background:linear-gradient(135deg,#16223D 0%,#1F3360 100%); border-radius:16px; padding:18px 20px 14px;
  margin-bottom:18px; box-shadow:0 10px 30px rgba(15,24,48,.18); }
.st-key-iw_journey .jh { display:flex; align-items:baseline; gap:10px; color:#fff; margin-bottom:2px; }
.st-key-iw_journey .jh b { font-family:'Instrument Serif',Georgia,serif; font-weight:400; font-size:1.45rem; }
.st-key-iw_journey .jh small { color:#AFC0DA; font-size:.8rem; }
.st-key-iw_journey .js { color:#AFC0DA; font-size:.8rem; margin:0 0 12px; }
.st-key-iw_journey [data-testid="stHorizontalBlock"] { gap:10px !important; }
.iw-jcard { background:rgba(255,255,255,.07); border:1px solid rgba(255,255,255,.12); border-radius:12px;
  padding:12px 12px 10px; min-height:150px; }
.iw-jcard .n { display:inline-flex; width:22px; height:22px; border-radius:50%; background:#2BB39D; color:#0B1A2E;
  font-weight:800; font-size:.72rem; align-items:center; justify-content:center; margin-right:6px; }
.iw-jcard b { color:#fff; font-size:.9rem; } .iw-jcard .who { color:#7FD8C7; font-size:.7rem; font-weight:600;
  letter-spacing:.06em; display:block; margin:6px 0 4px; text-transform:uppercase; }
.iw-jcard p { color:#C9D3E3; font-size:.76rem; line-height:1.45; margin:0; }
.st-key-iw_journey .stButton button { background:rgba(255,255,255,.95) !important; border:none !important;
  border-radius:9px !important; min-height:34px !important; }
.st-key-iw_journey .stButton button p { color:#16223D !important; font-size:.76rem !important; font-weight:700 !important; }
.st-key-iw_journey .st-key-j_hide button { background:transparent !important; }
.st-key-iw_journey .st-key-j_hide button p { color:#AFC0DA !important; text-decoration:underline; font-weight:500 !important; }
</style>"""


def journey() -> None:
    """End-to-end story for judges: five steps, each switches to the right person and opens the right page."""
    ss = st.session_state
    if ss.get("journey_hidden", True):                 # hidden until someone asks for it
        st.markdown("""<style>
.st-key-iw_journey_closed { background:linear-gradient(90deg, #13284A, #1B2A4E); border-radius:14px; padding:10px 12px 10px 18px;
  box-shadow:0 6px 18px rgba(13,26,49,.12); margin-bottom:6px; }
.st-key-iw_journey_closed [data-testid="stHorizontalBlock"] { align-items:center; }
.iw-jc { display:flex; align-items:center; gap:12px; color:#C9D6EA; font-size:.86rem; }
.iw-jc i { font-style:normal; width:30px; height:30px; border-radius:50%; background:rgba(63,208,182,.16); color:#7FE6D2;
  display:flex; align-items:center; justify-content:center; font-size:.9rem; flex:none; }
.iw-jc b { color:#fff; font-weight:650; }
.st-key-j_show button { background:#3FD0B6 !important; border:none !important; border-radius:999px !important; min-height:36px; }
.st-key-j_show button p { color:#0D1A31 !important; font-weight:700 !important; font-size:.84rem !important; }
.st-key-j_show button:hover { background:#7FE6D2 !important; }
</style>""", unsafe_allow_html=True)
        with st.container(key="iw_journey_closed"):
            c1, c2 = st.columns([5, 1.3])
            c1.markdown('<div class="iw-jc"><i>▶</i><span><b>First time here?</b> Walk one draft from first check '
                        'to sign-off in five short steps.</span></div>', unsafe_allow_html=True)
            c2.button("Show the walkthrough", key="j_show", width="stretch",
                      on_click=ss.__setitem__, args=("journey_hidden", False))
        return
    st.markdown(JOURNEY_CSS, unsafe_allow_html=True)
    with st.container(key="iw_journey"):
        h1, h2 = st.columns([8, 1])
        h1.markdown('<div class="jh"><b>One draft, start to finish</b><small>five short steps</small></div>'
                    '<div class="js">Every button signs you in as the person who does that step and opens their page; '
                    'each person only sees the pages of their own workspace.</div>', unsafe_allow_html=True)
        h2.button("Hide", key="j_hide", on_click=ss.__setitem__, args=("journey_hidden", True))
        for col, (n, who, title, text, page, sample) in zip(st.columns(len(JOURNEY)), JOURNEY):
            with col:
                st.markdown(f'<div class="iw-jcard"><span class="n">{n}</span><b>{html.escape(title)}</b>'
                            f'<span class="who">as {html.escape(full_name(who))}</span>'
                            f'<p>{html.escape(text)}</p></div>', unsafe_allow_html=True)
                if st.button(f"Go as {full_name(who).split()[0]}", key=f"j_{n}", width="stretch"):
                    if switch_user(who):
                        ss.landed_for = who
                        if sample:
                            smp = next((x for x in services.demo_samples() if x["id"] == sample), None)
                            if smp:
                                ss.rv_text, ss.rv_title = smp["text"], smp["title"].split(" (")[0]
                        try:
                            st.switch_page(page)
                        except Exception:
                            st.rerun()


def _current_page() -> str:
    import inspect
    for fr in inspect.stack():
        f = Path(fr.filename)
        if f.parent.name == "pages":
            return f"pages/{f.name}"
        if f.name == "Home.py":
            return "Home.py"
    return "Home.py"


def _initials(name: str) -> str:
    parts = [p for p in name.replace(".", " ").split() if p]
    return (parts[0][:2] if len(parts) == 1 else parts[0][0] + parts[-1][0]).upper() if parts else "?"


def _sign_out() -> None:
    for key in ("auth", "user", "role", "team", "show_acct"):
        st.session_state.pop(key, None)
    st.session_state["signed_out"] = True          # do not restore from the address after an explicit sign-out
    try:
        if "as" in st.query_params:
            del st.query_params["as"]
    except Exception:
        pass


def _ago(stamp: str) -> str:
    from datetime import datetime, timezone
    try:
        t = datetime.strptime((stamp or "")[:16].replace("T", " "), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            t = datetime.strptime((stamp or "")[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return ""
    m = int((datetime.now(timezone.utc) - t).total_seconds() // 60)
    if m < 0:
        return "soon"
    return (f"{max(m, 1)} min ago" if m < 60 else f"{m // 60} h ago" if m < 1440 else
            "yesterday" if m < 2880 else f"{m // 1440} days ago")


def _mark_read(user: str, ids: list) -> None:
    st.session_state.setdefault("notif_seen", {}).setdefault(user, set()).update(ids)


TOAST_SECONDS = 3            # pop-ups stay a little shorter than Streamlit's 4 s default


def notification_bell(user: str, role: str) -> None:
    """Bell with the unread count; pop-ups for anything new when a person signs in or switches."""
    ss = st.session_state
    try:
        notifs = services.notifications(user, role, {u: full_name(u) for u in FULL_NAMES})
    except Exception:
        notifs = []
    seen = ss.setdefault("notif_seen", {}).setdefault(user, set())
    toasted = ss.setdefault("notif_toasted", {}).setdefault(user, set())
    unread = [n for n in notifs if n["id"] not in seen]
    fresh = [n for n in unread if n["id"] not in toasted]
    # at most two pop-ups, so they never cover the page: the newest one, then a pointer to the bell
    for n in fresh[:1]:
        st.toast(f"**{n['title']}**  \n{n['detail']}", icon=n["icon"], duration=TOAST_SECONDS)
    if len(fresh) > 1:
        st.toast(f"{len(fresh) - 1} more in your notifications (🔔, top right)", icon="🔔", duration=TOAST_SECONDS)
    toasted.update(n["id"] for n in fresh)
    st.markdown(f"<style>.st-key-iw_bell {{ --iw-unread:'{len(unread) if unread else ''}'; }}</style>",
                unsafe_allow_html=True)
    with st.popover("🔔", help="Notifications"):
        st.markdown(f'<div class="iw-menu-h">NOTIFICATIONS · {len(unread)} NEW</div>', unsafe_allow_html=True)
        if not notifs:
            st.markdown('<div class="iw-nt-empty">You are all caught up.</div>', unsafe_allow_html=True)
        for i, n in enumerate(notifs[:12]):
            new = n["id"] not in seen
            when = _ago(n["at"])
            if st.button(f"**{n['icon']}  {n['title']}** {n['detail']}" + (f" · {when}" if when else ""),
                         key=f"nt_{'new' if new else 'old'}_{i}", width="stretch"):
                _mark_read(user, [n["id"]])
                try:
                    st.switch_page(n["page"])
                except Exception:
                    st.rerun()
        if unread:
            st.button("Mark all as read", key="nt_read", width="stretch",
                      on_click=_mark_read, args=(user, [n["id"] for n in notifs]))


def header() -> None:
    """Top bar on every signed-in page: wordmark, page tabs, AI status, user menu (switch demo user / sign out)."""
    ss = st.session_state
    role, user = ss.get("role", "Creator"), ss.get("user", "")
    current = _current_page()
    try:
        ai = services.ai_status()
    except Exception:
        ai = {"ok": False, "reason": "Status unavailable"}
    initials = _initials(full_name(user))
    inner_bg = ("radial-gradient(ellipse 80% 50% at 50% 0%, rgba(18,145,127,.06), transparent 70%), "
                f'url("{_contours_svg("#1B2A4E", .55)}") center top / 1600px auto repeat, '
                "linear-gradient(180deg, #F7F5F0 0%, #F3F1EA 100%)")
    shell = (SHELL_CSS.replace("__INNER_BG__", inner_bg)
             + f"<style>.st-key-iw_user {{ --iw-initials:'{initials}'; }}</style>")
    st.markdown(shell, unsafe_allow_html=True)
    persist_css({"iw-global": _style_text(CSS), "iw-shell": _style_text(shell), "iw-boot": None})
    with st.container(key="iw_header"):
        st.markdown(
            '<div class="iw-strip"><span>Content governance before you publish</span>'
            '<i class="pill mint">CodeTitans India 2026</i><span>Round 3 · The Finish</span>'
            f'<i class="pill ws">{html.escape(WORKSPACE.get(role, ("Workspace", ""))[0])}</i>'
            '<i class="pill">Demo workspace · Lumora is a fictional brand</i>'
            '<span class="sp"></span><span>Built by <b>DECODIANS</b></span></div>', unsafe_allow_html=True)
        c_logo, c_tabs, c_status, c_bell, c_user = st.columns([1.75, 6.2, 1.15, 0.55, 1.95], vertical_alignment="center",
                                                              gap="small")
        with c_logo:
            st.markdown(wordmark(True, 44), unsafe_allow_html=True)
        with c_tabs, st.container(key="iw_tabs"):
            tabs = visible_tabs(role)
            widths = [max(len(label), 6) + 5 for _p, label, _r in tabs]       # longer labels get wider pills, nothing truncates
            for i, (col, (page, label, _r)) in enumerate(zip(st.columns(widths), tabs)):
                on = "on" if page == current else "off"
                with col, st.container(key=f"iw_tab_{on}_{i}"):
                    try:
                        st.page_link(page, label=label, width="stretch")
                    except Exception:   # headless test runner without multipage context
                        st.markdown(f'<span class="iw-tab-fallback">{html.escape(label)}</span>', unsafe_allow_html=True)
        with c_status:
            if ai["ok"] is None:
                st.markdown('<span class="iw-status" style="background:#F3F5F9;color:#5A6480">'
                            '<i style="background:#8A93A6"></i>Checking AI…</span>', unsafe_allow_html=True)
            elif ai["ok"]:
                st.markdown(f'<span class="iw-status ok" title="Gemini reachable ({html.escape(ai["reason"])})">'
                            '<i></i>AI connected</span>', unsafe_allow_html=True)
            else:
                st.markdown(f'<span class="iw-status bad" title="{html.escape(ai["reason"])}. Rule checks still run.">'
                            '<i></i>AI not connected</span>', unsafe_allow_html=True)
        with c_bell, st.container(key="iw_bell"):
            notification_bell(user, role)
        with c_user, st.container(key="iw_user"):
            with st.popover(f"**{full_name(user)}** {role} · {ORG}"):
                st.markdown('<div class="iw-menu-h">SWITCH DEMO USER</div>', unsafe_allow_html=True)
                for a in services.demo_accounts():
                    is_me = a["username"] == user
                    lbl = ("*current* " if is_me else "") + f"**{full_name(a['username'])}** {a['role']} · {ORG}"
                    if st.button(lbl, key=f"sw_{a['username']}", disabled=is_me, width="stretch"):
                        if switch_user(a["username"]):
                            if not can_open(current, st.session_state.get("role", "")):
                                try:
                                    st.switch_page("Home.py")     # the new person does not work on this page
                                except Exception:
                                    pass
                            st.rerun()
                with st.container(key="iw_signout"):
                    if st.button("Sign out", key="sign_out", width="stretch"):
                        _sign_out()
                        st.rerun()


def render_shell() -> None:
    inject_css()
    st.session_state.setdefault("role", "Creator")
    st.session_state.setdefault("user", "Demo user")

    restore_session()
    if REQUIRE_LOGIN and not st.session_state.get("auth"):
        login_screen()
    if st.session_state.get("auth") and st.session_state.get("user") in ROLE_INFO:
        try:
            st.query_params["as"] = st.session_state["user"]     # survives a refresh; see restore_session()
        except Exception:
            pass

    header()
    _workspace_guard()
