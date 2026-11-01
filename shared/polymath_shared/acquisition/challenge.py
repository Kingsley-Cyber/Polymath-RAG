"""CHALLENGE-PAGE DETECTOR (SUPPLIER-APIS, the owner's decision of 2026-09-27): is a text a verification wall (a CAPTCHA, a slider, a
"verify you are human" or "unusual traffic" interstitial, a bot block) instead of content? A DETECTOR, never a solver: it reads the
text it is given and names the wall; nothing here answers, clicks, waits out, retries or otherwise gets past any check.

It is used where a wall must never become evidence:
  * the research-acquisition read paths (`opencli.blocked` once a reader got nothing, `service.shape` on listing and search rows,
    the search-engine listing reader): a wall is HUMAN_ACTION_REQUIRED or is left out, never a record;
  * the receipt check (`adapter.transitions.validate_receipt`): an observation whose quote is a wall is refused
    (CHALLENGE_PAGE_AS_EVIDENCE).

Content that only MENTIONS a check is content (the lesson of B-17 in `opencli.blocked`): a thread titled "Endless captcha loop", a
comment that says the "verify you are human" pop-ups are annoying, a listing called "Security Check Mirror" among its details. So a
text is a wall only when
  * a wall's OWN line (its heading, its prompt, its button) stands as a WHOLE segment: a line, or one sentence of a line; and
  * the wall's lines, not content, make up the text: what is neither a wall line nor wall furniture (a host name, a "Ray ID", "this
    may take a few seconds") stays within a small budget.
One line that content also uses ("Captcha", "Security check", "I'm not a robot") is not enough on its own; "Access denied" counts
only beside a bot notice.

PRODUCT-SEARCH-E2E (2026-11-01, measured on the owner's Agent Reach probes): a page READER's output carries its own framing
(Exa: `Title:` / `URL:` / `Published:` / `Author:` / `Highlights:`; Jina Reader: `Title:` / `URL Source:` / `Final URL:` /
`Markdown Content:`) and markdown (image lines, links, bold). That framing made CJ's "Human verification" page read as content
(8 content segments), so a check page could pass as evidence. Now:
  * the reader framing is furniture, and a framing line that names the page's OWN URL (`URL:`, `URL Source:`, `Final URL:`) whose
    path is a wall route (`WALL_ROUTE`: CJ's `/egg/cj/validation.html`, a `/captcha` page) names the wall by itself;
  * the page's own title (`Title:`) that IS a check page's title ("Human verification", "Captcha Interception") is a strong line;
  * a markdown image is no text (its alt text stays, Jina's "Image N" label does not), a link is its text, bold is plain;
  * a captcha form's own furniture ("Submit", "Note: Not case sensitive") is not content.
A URL merely MENTIONED in content (a link, an image) never names a wall: only the framing's own URL does. Pure: no I/O."""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit

#: what may stand beside a wall's own lines and still be the wall (a title, a line of chrome): at most this many segments and characters
CONTENT_SEGMENTS_MAX, CONTENT_CHARS_MAX = 3, 200
#: a CJK wall line is a short prompt ("请按住滑块，拖动到最右边"); a longer CJK sentence that holds the words is content
CJK_SEGMENT_MAX = 40

_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'", "＇": "'"})
#: a segment ends at a line break, at a sentence end followed by a space, after a CJK sentence mark or comma, and at a " | " title separator
_SPLIT = re.compile(r"[\r\n]+|(?<=[.!?])\s+|(?<=[。！？，；：、])|\s[|•·]\s")
_TRIM = " \t.,;:!?…\"'()[]{}<>*-–—。！？，；：、"
_CJK = re.compile(r"[㐀-鿿]")
_YOU_ARE = r"you(?:'re|\s+are)"


def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


#: a wall's own lines that no content line is: one of them makes a short text a wall
_STRONG: tuple[tuple[str, re.Pattern[str]], ...] = tuple((label, _rx(p)) for label, p in (
    # "slide to the right" alone is a dance lyric and "slide to unlock" a phone: the slider's own prompt names the slider or the check
    ("slider check", (r"(?:please\s+)?(?:slide|drag)\s+(?:the\s+)?(?:slider|puzzle(?:\s+piece)?|bar)\s+(?:all\s+the\s+way\s+)?to\s+the\s+(?:right|end|far\s+right)"
                      r"(?:\s+to\s+(?:verify|complete(?:\s+(?:the\s+)?verification)?))?")),
    ("slider check", r"(?:please\s+)?(?:slide|drag)\s+(?:the\s+(?:slider|puzzle(?:\s+piece)?|bar)\s+)?to\s+(?:verify|complete\s+(?:the\s+)?(?:verification|puzzle|security\s+check))"),
    ("unusual-traffic notice", r"(?:sorry,?\s+)?(?:we\s+have|we've|our\s+systems\s+have)\s+detected\s+unusual\s+traffic\s+from\s+your\s+(?:computer\s+)?network"),
    ("unusual-traffic notice", r"this\s+page\s+checks\s+to\s+see\s+if\s+it's\s+really\s+you\s+sending\s+the\s+requests,?\s+and\s+not\s+a\s+robot"),
    ("human check", (rf"(?:please\s+)?(?:verify|confirm|prove)\s+(?:that\s+)?{_YOU_ARE}\s+(?:a\s+)?human(?:\s+(?:and\s+)?not\s+a\s+(?:ro)?bot)?"
                     r"(?:\s+by\s+completing\s+the\s+action\s+below)?")),
    ("human check", rf"verifying\s+(?:that\s+)?{_YOU_ARE}\s+(?:a\s+)?human"),
    ("human check", rf"press\s+(?:&|and)\s+hold\s+to\s+confirm\s+{_YOU_ARE}\s+(?:a\s+)?human(?:\s+\(?and\s+not\s+a\s+bot\)?)?"),
    ("robot check", rf"(?:please\s+)?(?:confirm|verify|prove|show)\s+(?:that\s+)?{_YOU_ARE}\s+not\s+a\s+(?:ro)?bot"),
    ("robot check", rf"(?:sorry,?\s+)?we\s+(?:would\s+like|want|just\s+need|need)\s+to\s+make\s+sure\s+(?:that\s+)?{_YOU_ARE}\s+not\s+a\s+(?:ro)?bot"),
    ("robot check", r"(?:please\s+)?(?:enter|type)\s+the\s+characters\s+(?:you\s+see\s+)?(?:below|in\s+(?:this|the)\s+(?:image|picture))"),
    ("browser check", r"checking\s+(?:if\s+the\s+site\s+connection\s+is\s+secure|your\s+browser(?:\s+before\s+accessing(?:\s+\S+)?)?)"),
    ("browser check", r"\S+\s+needs\s+to\s+review\s+the\s+security\s+of\s+your\s+connection\s+before\s+proceeding"),
    ("browser check", r"please\s+enable\s+js\s+and\s+disable\s+any\s+ad\s+blocker"),
    ("block page", r"sorry,?\s+you\s+have\s+been\s+blocked"),
    ("block page", r"this\s+website\s+is\s+using\s+a\s+security\s+service\s+to\s+protect\s+itself\s+from\s+online\s+attacks"),
    ("block page", r"pardon\s+our\s+interruption"),
    ("block page", r"as\s+you\s+were\s+browsing,?\s+something\s+about\s+your\s+browser\s+made\s+us\s+think\s+you\s+were\s+a\s+bot"),
    ("security check", r"(?:please\s+)?complete\s+the\s+(?:security\s+check|captcha|verification|challenge)(?:\s+below)?\s+to\s+(?:access|continue|proceed)(?:\s+\S+){0,3}"),
))
#: a heading or a button that a comment or a title can carry too: a wall only beside another wall line
_WEAK: tuple[tuple[str, re.Pattern[str]], ...] = tuple((label, _rx(p)) for label, p in (
    ("captcha", r"(?:re)?captcha(?:\s+(?:interception|verification|required|check|challenge|page))?"),
    ("security check", r"(?:one\s+more\s+step\s*)?(?:security|bot|robot)\s+(?:check|verification|challenge)(?:\s+required)?"),
    ("human check", r"(?:human|identity)\s+verification(?:\s+required)?|verification\s+required|are\s+you\s+(?:a\s+)?(?:robot|human)"),
    ("robot check", r"i\s*(?:'m|\s+am)\s+not\s+a\s+(?:ro)?bot"),
    ("browser check", r"just\s+a\s+moment|one\s+more\s+step|attention\s+required|enable\s+javascript\s+and\s+cookies\s+to\s+continue"),
    ("block page", rf"{_YOU_ARE}\s+unable\s+to\s+access\s+\S+"),
))
#: a wall's footer, ids and waiting notes: neither wall evidence nor content
_FURNITURE: tuple[re.Pattern[str], ...] = tuple(_rx(p) for p in (
    r"(?:https?://)?(?:[a-z0-9-]+\.)+[a-z]{2,}/?", r"ray\s+id:?\s*[0-9a-f]{6,}", r"(?:performance\s+(?:&|and)\s+security|ddos\s+protection)\s+by\s+[\w .-]{2,40}",
    r"this\s+(?:process\s+is\s+automatic|may\s+take\s+a\s+few\s+seconds)", r"your\s+browser\s+will\s+redirect\s+to\s+your\s+requested\s+content\s+shortly",
    r"please\s+(?:allow\s+up\s+to\s+\d+\s+seconds|wait|stand\s+by|enable\s+cookies)", r"verification\s+(?:successful|failed|complete)",
    r"waiting\s+for\s+\S+\s+to\s+respond", r"why\s+have\s+i\s+been\s+blocked", r"what\s+can\s+i\s+do\s+to\s+resolve\s+this",
    r"reference\s*#?\s*[0-9a-f.]{6,}", r"privacy\s*-\s*terms", r"hcaptcha", r"(?:request|event|incident)\s+id:?\s*[\w.-]+", r"(?:error|code):?\s*[\w.-]{3,}",
    r"feedback", r"loading", r"retry", r"try\s+again", r"refresh",
    # a captcha form's button and its input hint (CJ's check page: "Note: Not case sensitive" / "Submit")
    r"submit", r"(?:note\s*:?\s*)?not\s+case[\s-]+sensitive",
))
#: wall ROUTES, matched on the PATH of a page's own URL (anchored at its start, as `opencli.blocked` matches it): a captcha page,
#: CJ's human-verification page. A slug or a search word that merely contains the word ("/r/x/comments/abc/captcha/") is content.
WALL_ROUTE = re.compile(r"/captcha(?:[/.]|$)|/egg/cj/validation\.html$")
#: a check page's own TITLE (CJ: "Human verification"; Alibaba: "Captcha Interception"): strong when it is the page's `Title:` line
_WALL_TITLE = _rx(r"human\s+verification|captcha\s+interception")
#: a page reader's framing lines (Exa, Jina Reader): (the label, its value)
_FRAMING = re.compile(r"^\s*(title|url\s+source|final\s+url|url|published(?:\s+time)?|author|highlights|markdown\s+content|warning)\s*:\s*(.*?)\s*$",
                      re.IGNORECASE)
_URL_LABELS = frozenset({"url", "url source", "final url"})
_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_JINA_IMAGE_LABEL = re.compile(r"^\s*image\s+\d+\s*(?::\s*)?", re.IGNORECASE)


def wall_route(url: str | None) -> bool:
    """True when `url` (a page's own URL) is a verification page by its route: CJ's `/egg/cj/validation.html`, a `/captcha` page."""
    try:
        path = urlsplit(str(url or "").strip()).path.lower()
    except ValueError:
        return False
    return bool(path) and WALL_ROUTE.match(path) is not None


def _unframe(text: str) -> tuple[str, list[str], list[str]]:
    """(the text without a reader's framing and markdown, the page titles it named, the page URLs it named)."""
    lines, titles, urls = [], [], []
    for raw in str(text or "").splitlines():
        m = _FRAMING.match(raw)
        if m:
            label = " ".join(m.group(1).lower().split())
            if label == "title" and m.group(2):
                titles.append(m.group(2))
            elif label in _URL_LABELS and m.group(2):
                urls.append(m.group(2))
            continue                                             # framing is furniture, never content
        line = _MD_IMAGE.sub(lambda i: _JINA_IMAGE_LABEL.sub("", i.group(1)), raw)
        line = _MD_LINK.sub(lambda k: k.group(1), line).replace("**", "").replace("__", "")
        lines.append(line)
    return "\n".join(lines), titles, urls
#: "Access denied" is a wall only beside a bot notice on the same page (a plain 403 is not a human check)
_ACCESS_DENIED = _rx(r"access\s+(?:denied|blocked)(?:\s+\S+){0,3}|访问被拒绝|訪問被拒絕")
_BOT_NOTICE = _rx(r"\b(?:bots?|robots?|automated|crawlers?|scrapers?)\b|unusual\s+(?:traffic|activity)|suspicious\s+(?:traffic|activity)"
                  r"|reference\s*#|don't\s+have\s+permission\s+to\s+access|do\s+not\s+have\s+permission\s+to\s+access")
#: CJK wall prompts (a short segment that holds one): security / human-machine verification, the slider, "drag to the far right"
_CJK_WALL = re.compile("安全验证|安全驗證|人机验证|人機驗證|滑块|滑塊"
                       "|拖动到最右|拖動到最右|完成验证|完成驗證"
                       "|通过验证|通過驗證|验证失败|驗證失敗")


def segments(text: str | None) -> list[str]:
    """The text as whole segments (lines, and the sentences of a line), normalised: NFKC, straight apostrophes, single spaces,
    surrounding punctuation trimmed. Empty segments are dropped."""
    norm = unicodedata.normalize("NFKC", str(text or "")).translate(_APOSTROPHES)
    out = []
    for part in _SPLIT.split(norm):
        seg = " ".join(part.split()).strip(_TRIM).strip()
        if seg:
            out.append(seg)
    return out


def _wall_line(seg: str) -> tuple[str, str] | None:
    """(strength, label) when `seg` is one of a wall's own lines, else None."""
    if _CJK.search(seg):
        return ("strong", "安全验证 (security verification)") if len(seg) <= CJK_SEGMENT_MAX and _CJK_WALL.search(seg) else None
    for label, pattern in _STRONG:
        if pattern.fullmatch(seg):
            return "strong", label
    for label, pattern in _WEAK:
        if pattern.fullmatch(seg):
            return "weak", label
    return None


def looks_like_challenge(text: str | None) -> str | None:
    """What kind of verification wall `text` is ("slider check", "unusual-traffic notice", "human check", "robot check", "browser
    check", "block page", "security check", "captcha", "access denied beside a bot notice", the CJK "security verification", or
    "verification page route" when a reader's framing names a wall route as the page's own URL), or None when it is content (or
    empty). See the module docstring for the rule."""
    body, titles, urls = _unframe(str(text or ""))
    if any(wall_route(u) for u in urls):
        return "verification page route"
    segs = segments(body)
    strong: list[str] = []
    weak: list[str] = []
    content: list[str] = []
    denied = False
    for title in titles:                                         # the page's own title: a check page's title is a strong line
        seg = " ".join(unicodedata.normalize("NFKC", title).split()).strip(_TRIM).strip()
        if _WALL_TITLE.fullmatch(seg):
            strong.append("human check")
        elif seg:
            segs.insert(0, seg)
    for seg in segs:
        hit = _wall_line(seg)
        if hit is not None:
            (strong if hit[0] == "strong" else weak).append(hit[1])
        elif _ACCESS_DENIED.fullmatch(seg):
            denied = True
        elif not any(f.fullmatch(seg) for f in _FURNITURE):
            content.append(seg)
    if len(content) > CONTENT_SEGMENTS_MAX or sum(len(c) for c in content) > CONTENT_CHARS_MAX:
        return None                                              # content with a wall's words in it is content
    if strong:
        return strong[0]
    if denied and any(_BOT_NOTICE.search(s) for s in segs):
        return "access denied beside a bot notice"
    if len(weak) >= 2:
        return weak[0]
    return None
