"""PRODUCT-INTENT-V1 — is this chat message a request to FIND products to sell (or suppliers for one)? Deterministic, on the raw
message (+ the last user turn for a follow-up such as "find suppliers for that"); no model.

PRODUCT-SEARCH-E2E (the owner, 2026-11-01): "it shouldnt really expect a niche it uses a corpus to find products"; "it returns
things like this corpus doesnt recommend products rather than using copus to hypothesize". A product request therefore switches the
chat turn into product mode (`product_search.service.ProductTurn`): the corpus is read for product hypotheses and CJ Dropshipping
is searched for each. This module only DECIDES and EXTRACTS; it never retrieves.

It fires on requests, never on knowledge questions ABOUT products:
  fires        "Find me products I could dropship for pet owners in the US", "what should I sell to new moms?",
               "find suppliers for yoga mats", "give me product ideas from this corpus", "show me CJ finds for dog owners"
  never fires  "what does Christensen say about the products customers hire", "how should I price a product",
               "what is dropshipping", "how do I find product-market fit"
Rules (each named in the receipt as `rule`):
  * STRONG, first-person selling or sourcing forms, which no knowledge veto overrides: `sell_object` ("products I could sell",
    "what should I sell"), `dropship_object` ("products to dropship", "what can I dropship"), `supplier_request` ("find a
    supplier for X", "source X from Alibaba", "CJ finds for X");
  * VETOABLE, product-idea and product-list requests: `product_ideas` ("product ideas", "winning products", "find me a winning
    product"), `dropship_noun` ("dropshipping products"), `request_products` ("find products for gamers"), `terse_products`
    ("products for busy parents?"). An attribution question ("what does the book say ...", "according to"), a method or
    definition question ("how do I ...", "what are the risks of ...", "explain ...") or a reference to what a text mentions
    ("products mentioned in chapter 2") vetoes them;
  * `follow_up`: a short deictic request ("find suppliers for that", "any CJ listings for those?") fires when the last user turn
    was itself a product request; its seed, audience and geography come from that turn.
Extracted (each optional): `seed` (a product or niche: "yoga mats", "pet store"), `audience` ("pet owners"), `geography`
(ISO-3166 alpha-2, or "EU": "US"), and `search_terms` — the fallback CJ search terms used when no hypothesis supplies its own.
Pure: no I/O."""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

CONTRACT = "product-intent-v1"
KINDS = ("sell", "dropship", "suppliers", "product_ideas", "find_products", "follow_up", "forced")
MAX_TERMS = 3
MAX_PHRASE_TOKENS = 5
FOLLOW_UP_MAX_WORDS = 14

_REQ = (r"(?:find|suggest|recommend|give|list|show|brainstorm|generate|propose|identify|discover|spot|pick|choose|hypothesi[sz]e|"
        r"come\s+up\s+with|think\s+of|surface|uncover|search(?:\s+for)?|look(?:ing)?\s+for|get|scout|name|share|tell\s+me|"
        r"help\s+me\s+(?:find|pick|choose|come\s+up\s+with)|i\s+(?:need|want)|i'm\s+looking\s+for)")
_MODAL = r"(?:could|can|should|might|would|to|ought\s+to|'d|'ll)"
_OBJ_STRICT = r"(?:what|which(?:\s+[\w'-]+)?|something|anything|stuff|things?)"
_OBJ_PRODUCT = r"(?:(?:a|an|the|some|any|good|great|new|cheap|unique)\s+)?(?:products?|items?|goods|merch(?:andise)?|gadgets?|skus?)"
_DROPSHIP = r"drop[- ]?ship"

#: STRONG (never vetoed): explicit first-person selling, dropshipping or sourcing
_SELL_OBJECT = re.compile(
    rf"\b(?:{_OBJ_STRICT}\s+(?:(?:i|we|you)\s+)?{_MODAL}\s+(?:[\w'-]+\s+)?(?:sell|resell|stock|{_DROPSHIP})"
    rf"|{_OBJ_PRODUCT}\s+(?:(?:i|we|you)\s+)?{_MODAL}\s+(?:[\w'-]+\s+)?(?:sell|resell|stock|carry|launch|offer|list|source|import|retail|market))\b")
_DROPSHIP_OBJECT = re.compile(
    rf"\b(?:{_OBJ_STRICT}|{_OBJ_PRODUCT})\s+(?:(?:i|we|you)\s+)?{_MODAL}\s+(?:[\w'-]+\s+)?{_DROPSHIP}\b")
_SUPPLIER = re.compile(
    r"\b(?:find|source|get|show|list|look\s+up|search(?:\s+for)?|recommend|suggest|give|need|want|locate|scout)\s+(?:me\s+|us\s+)?"
    r"(?:a\s+|an\s+|some\s+|the\s+|good\s+|reliable\s+|cheap\s+|best\s+|top\s+|cj\s+|alibaba\s+)?(?:[\w'-]+\s+)?"
    r"(?:suppliers?|vendors?|manufacturers?|wholesalers?|factor(?:y|ies)|dropshippers?)\b"
    r"|^\s*(?:any\s+)?(?:suppliers?|vendors?|manufacturers?|wholesalers?)\s+(?:for|of)\s+\w"
    r"|\bwhere\s+(?:can|could|do|should)\s+(?:i|we)\s+(?:source|buy\s+wholesale|find\s+(?:a\s+)?suppliers?)\b"
    r"|\bsourc(?:e|ing)\s+(?:[\w'-]+\s+){1,5}?(?:from|on|via|through)\s+(?:cj|cjdropshipping|alibaba|aliexpress|china|suppliers?|a\s+supplier)\b"
    r"|\b(?:cj|cjdropshipping|cj\s+dropshipping|alibaba|aliexpress)\s+(?:finds?|products?|listings?|suppliers?|items?|results?)\b"
    r"|\bsearch\s+(?:on\s+)?(?:cj|cjdropshipping|alibaba|aliexpress)\b"
    r"|\b(?:find|search|look\s+up|show)\s+(?:me\s+)?(?:[\w'-]+\s+){0,4}?on\s+(?:cj|cjdropshipping|cj\s+dropshipping|alibaba|aliexpress)\b")
#: VETOABLE: product-idea and product-list requests
_IDEAS = re.compile(
    r"\bproduct\s+(?:ideas?|opportunit(?:y|ies)|concepts?|hypothes[ie]s|suggestions?|recommendations?|candidates?|finds?|picks?|niches?|angles?)\b"
    r"|\b(?:winning|trending|viral|hot|best[- ]?selling|top[- ]selling|profitable|in[- ]demand|untapped|evergreen)\s+"
    r"(?:products|items|niches|product\s+ideas|gadgets)\b"
    rf"|\b{_REQ}\s+(?:me\s+|us\s+)?(?:a|an|one)\s+(?:(?:winning|trending|viral|hot|profitable|good|great|new|unique)\s+)?(?:product|niche)\b"
    r"(?!-|\s+(?:market|manager|management|description|photography|design|development|roadmap|strategy|page|life\s*cycle|lifecycle|"
    r"team|owner|launch|positioning|pricing|line|review|spec|name|category)\b)")
_DROPSHIP_NOUN = re.compile(
    rf"\b{_DROPSHIP}(?:ping|pable)?\s+(?:products?|items?|ideas?|niches?|finds?|candidates?|opportunit(?:y|ies)|picks?|goods)\b")
_REQUEST_PRODUCTS = re.compile(
    rf"\b{_REQ}\s+(?:me\s+|us\s+)?(?:some\s+|a\s+few\s+|a\s+list\s+of\s+|the\s+best\s+|\d+\s+|three\s+|five\s+|ten\s+)?"
    r"(?:[\w'-]+\s+){0,2}?(?:products|items|gadgets|goods|gifts|merch(?:andise)?|product\s+ideas)\b")
_TERSE = re.compile(r"^\s*(?:any\s+|some\s+|good\s+|best\s+|top\s+)?(?:products?|product\s+ideas|items|gadgets|gifts)\s+"
                    r"(?:for|to\s+sell|i\s+could|we\s+could|that\s+(?:i|we)\s+could)\b")

#: knowledge vetoes (they veto only the VETOABLE rules)
_ATTRIBUTION = re.compile(
    r"\bwhat\s+(?:does|did|do)\s+(?:[\w.'-]+\s+){1,5}?(?:say|says|said|think|thinks|argue|argues|write|writes|wrote|claim|claims|"
    r"mean|means|recommend|recommends|suggest|suggests|teach|teaches|tell\s+us|explain|explains)\b"
    r"|\bhow\s+(?:does|did|do)\s+(?:[\w.'-]+\s+){1,5}?(?:define|describe|explain|frame|view|see|characteri[sz]e)\b"
    r"|\b(?:according\s+to|in\s+the\s+view\s+of|the\s+author'?s?)\b")
_MENTIONED = re.compile(r"\b(?:mentioned|discussed|described|covered|cited|named|featured|reviewed)\s+(?:in|by)\b"
                        r"|\b(?:in|from)\s+(?:chapter|section|page|part)\s+\d+")
_METHOD = re.compile(
    r"^\s*how\s+(?:do|does|did|should|can|could|would|to|is|are|much|many)\b"
    r"|^\s*(?:what|which)\s+(?:is|are|was|were)\s+(?:the\s+)?(?:risks?|benefits?|pros|cons|steps?|principles?|types?|stages?|costs?|"
    r"rules?|laws?|differences?|advantages?|disadvantages?|challenges?|ways?|best\s+practices|basics|fundamentals|definition|meaning|"
    r"history|role|purpose|process|key\s+[\w'-]+)\b"
    r"|^\s*(?:explain|define|describe|summari[sz]e|compare|contrast|tell\s+me\s+about|why)\b"
    r"|^\s*what\s+(?:makes|made|causes|caused|drives|determines)\b"
    r"|^\s*(?:is|are|was|were|does|do|did|can|could|should)\s+(?:it|dropshipping|drop\s+shipping|this|that|there)\b")

_DEICTIC = re.compile(
    r"\b(?:for|on|of|about|with)\s+(?:that|this|those|these|it|them|each(?:\s+one)?|all\s+of\s+them|the\s+(?:first|second|third|"
    r"fourth|fifth|last|top)\s+(?:one|idea|hypothesis|product)|(?:idea|hypothesis|product|number|#)\s*\d)\b"
    r"|\b(?:find|search|look\s+up)\s+(?:that|this|those|these|it|them)\s+on\b")
_FOLLOW_UP_WORDS = re.compile(r"\b(?:suppliers?|vendors?|manufacturers?|listings?|finds?|products?|cj|alibaba|aliexpress|sources?|"
                              rf"{_DROPSHIP}|sell)\b")

_TOKEN = re.compile(r"[a-z0-9][a-z0-9'&-]*|[,.?!;:()]")
_PREPOSITIONS = ("for", "to", "targeting", "serving", "catering")
_STOP = frozenset("in on at who that which with from under below over across within around near during using via so but or and "
                  "for to if when while because like whose where , . ? ! ; : ( )".split())
_DETERMINERS = frozenset("the a an my our their your some any".split())
_DEICTIC_WORDS = frozenset("that this those these it them each one ones all first second third fourth fifth last top next previous "
                           "above latter former idea ideas hypothesis hypotheses option options number".split())
_GENERIC = frozenset("me us you him her store shop business website brand online sale sales profit money cheap free now today "
                     "tomorrow example instance sure real reference context ideas products items stuff things something anything "
                     "everything everyone anyone myself ourselves yourself dropshipping dropship selling sell sourcing market "
                     "markets".split())
#: place words: never a seed, a niche or an audience's product root ("for the UK market", "American homeowners")
_GEO_WORDS = frozenset("us usa u.s. u.s.a. uk u.k. eu america american americans states united kingdom britain british england "
                       "english scotland wales canada canadian canadians australia australian australians aussie aussies germany "
                       "german france french spain spanish italy italian netherlands dutch ireland irish india indian nigeria "
                       "nigerian japan japanese mexico mexican brazil brazilian singapore philippines filipino europe european uae "
                       "dubai local global international domestic world worldwide".split())
_VERBS = frozenset("sell resell dropship drop-ship stock carry launch offer source import retail market buy find get make use start run "
                   "help target reach serve ship list pick choose".split())
#: people nouns: the last word of an audience phrase ("pet OWNERS", "new MOMS")
_PEOPLE = frozenset("""owners owner lovers lover parents parent moms mom mums mum mothers mother dads dad fathers father families family
kids kid children child babies baby toddlers toddler teens teen teenagers students student gamers gamer athletes athlete runners
runner cyclists cyclist bikers biker hikers hiker campers camper travelers traveler travellers traveller workers worker professionals
professional nurses nurse doctors teachers teacher seniors senior retirees elderly women woman men man ladies girls boys people couples
homeowners homeowner renters renter gardeners gardener cooks cook chefs chef bakers baker drivers driver truckers trucker fishermen
anglers angler hunters hunter golfers golfer yogis enthusiasts enthusiast fans fan beginners beginner freelancers freelancer
entrepreneurs entrepreneur creators creator musicians musician artists artist crafters crafter knitters developers developer
programmers programmer engineers engineer commuters commuter millennials shoppers shopper customers customer consumers consumer buyers
buyer users user riders rider swimmers swimmer skaters skater surfers surfer climbers climber dancers dancer readers reader writers
writer photographers photographer streamers streamer patients patient caregivers caregiver veterans veteran brides bride newlyweds
adults adult singles minimalists collectors collector hobbyists hobbyist makers maker builders mechanics plumbers electricians
landlords tenants employees employee managers founders marketers lifters bodybuilders vegans vegetarians pilots sailors boaters
gym-goers dieters sleepers insomniacs sufferers survivors learners coders nomads expats tourists guests hosts nannies cleaners
stylists barbers groomers fishers boomers zoomers retiree mums-to-be""".split())
#: an audience without its own product root ("new moms") borrows one for the fallback CJ terms
_AUDIENCE_ROOT = {"moms": "baby", "mom": "baby", "mums": "baby", "mothers": "baby", "parents": "baby", "dads": "baby", "fathers": "baby",
                  "babies": "baby", "toddlers": "toddler", "kids": "kids", "children": "kids", "teens": "teen", "teenagers": "teen",
                  "gamers": "gaming", "runners": "running", "hikers": "hiking", "campers": "camping", "cyclists": "cycling",
                  "bikers": "cycling", "travelers": "travel", "travellers": "travel", "gardeners": "garden", "cooks": "kitchen",
                  "chefs": "kitchen", "bakers": "baking", "golfers": "golf", "yogis": "yoga", "anglers": "fishing",
                  "fishermen": "fishing", "students": "student", "seniors": "senior", "elderly": "senior", "retirees": "senior",
                  "nurses": "nurse", "doctors": "medical", "drivers": "car", "truckers": "car", "photographers": "photography",
                  "musicians": "music", "artists": "art", "crafters": "craft", "knitters": "knitting", "swimmers": "swimming",
                  "skaters": "skateboard", "surfers": "surf", "climbers": "climbing", "developers": "desk", "programmers": "desk",
                  "coders": "desk", "homeowners": "home", "renters": "home", "athletes": "sports", "brides": "wedding",
                  "newlyweds": "wedding", "women": "women", "men": "men", "lifters": "gym", "bodybuilders": "gym",
                  "gym-goers": "gym", "dancers": "dance", "readers": "book", "writers": "writing", "streamers": "streaming",
                  "patients": "health", "caregivers": "caregiver", "commuters": "commuter", "nomads": "travel", "tourists": "travel",
                  "workers": "home office", "freelancers": "home office", "professionals": "office", "employees": "office"}
_AUDIENCE_SOFT = frozenset("busy new young old first-time avid serious casual modern local working stay-at-home single expecting "
                           "active aspiring passionate dedicated everyday regular remote anxious stressed tired lazy picky messy "
                           "frugal budget eco-conscious health-conscious sleepy nervous worried overwhelmed frustrated happy "
                           "proud".split())

#: ISO-3166 alpha-2 (or EU): (code, case-insensitive pattern); "US" / "UK" in capitals are matched on the original text
_GEO_CASED = (("US", re.compile(r"\bU\.?S\.?A?\.?(?![\w])")), ("GB", re.compile(r"\bU\.?K\.?(?![\w])")))
_NOT_GEO_AFTER = (r"(?!\s+(?:shepherds?|bulldogs?|pointers?|mastiffs?|spaniels?|setters?|eskimos?|staffordshire|akitas?|wolfhounds?|"
                  r"terriers?|curl|bobtails?|fries|toast|press|horn|roulette|football)\b)")
_GEO = (
    ("US", r"\b(?:usa|united\s+states(?:\s+of\s+america)?|stateside)\b|\b(?:in|across|to|for|within|throughout)\s+the\s+us\b"
           r"|\bus[- ](?:market|based|customers|shoppers|buyers|consumers|audience|only)\b|\bamerica\b|\bamericans\b"
           rf"|\bamerican\b{_NOT_GEO_AFTER}"),
    ("GB", r"\b(?:united\s+kingdom|great\s+britain|britain|england|scotland|wales)\b|\b(?:in|across|to|for|within)\s+the\s+uk\b"
           rf"|\buk[- ](?:market|based|customers|shoppers|buyers|consumers)\b|\b(?:british|english)\b{_NOT_GEO_AFTER}"
           r"(?=\s+(?:[\w'-]+\s+){0,2}?(?:customers|shoppers|buyers|consumers|market|audience|people|users|parents|owners|families))"),
    ("CA", r"\bcanada\b|\bcanadians?\b"), ("AU", r"\baustralia\b|\baustralians?\b|\baussies?\b"), ("NZ", r"\bnew\s+zealand\b|\bkiwis\b"),
    ("DE", rf"\bgermany\b|\bgerman\b{_NOT_GEO_AFTER}(?=\s+(?:[\w'-]+\s+){{0,2}}?(?:customers|shoppers|buyers|consumers|market|people))"),
    ("FR", rf"\bfrance\b|\bfrench\b{_NOT_GEO_AFTER}(?=\s+(?:[\w'-]+\s+){{0,2}}?(?:customers|shoppers|buyers|consumers|market|people))"),
    ("ES", r"\bspain\b"), ("IT", r"\bitaly\b"), ("NL", r"\bnetherlands\b|\bholland\b"), ("IE", r"\bireland\b"),
    ("IN", r"\bindia\b"), ("NG", r"\bnigeria\b|\bnigerians?\b"), ("ZA", r"\bsouth\s+africa\b"), ("BR", r"\bbrazil\b"),
    ("MX", r"\bmexico\b"), ("JP", r"\bjapan\b"), ("AE", r"\b(?:uae|united\s+arab\s+emirates|dubai)\b"), ("SG", r"\bsingapore\b"),
    ("PH", r"\bphilippines\b"), ("EU", r"\b(?:europe|european\s+union|the\s+eu|eu[- ]market)\b"),
)
_GEO_RE = tuple((code, re.compile(pattern)) for code, pattern in _GEO)


@dataclass(frozen=True)
class ProductIntent:
    """The product request a chat message makes, as PRODUCT-INTENT-V1 read it."""
    kind: str
    rule: str
    seed: str | None = None
    seed_kind: str | None = None             # "product" (a thing to search) | "niche" (a market or setting) | None
    audience: str | None = None
    geography: str | None = None
    search_terms: tuple[str, ...] = ()
    source: str = "message"                  # "message" | "history" (a follow-up) | "forced"
    vetoed: tuple[str, ...] = field(default_factory=tuple)   # VETOABLE rules a knowledge veto stopped (receipt only)

    def as_dict(self) -> dict[str, Any]:
        return {"contract": CONTRACT, "kind": self.kind, "rule": self.rule, "seed": self.seed, "seed_kind": self.seed_kind,
                "audience": self.audience, "geography": self.geography, "search_terms": list(self.search_terms),
                "source": self.source}


def _norm(text: str) -> str:
    return " ".join(str(text or "").replace("’", "'").replace("‘", "'").lower().split())


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(_norm(text))


def _vetoes(t: str) -> list[str]:
    return [name for name, rx in (("attribution", _ATTRIBUTION), ("mentioned", _MENTIONED), ("method", _METHOD)) if rx.search(t)]


def _match(t: str) -> tuple[str | None, str | None, list[str]]:
    """(rule, kind, vetoed rules) for a normalised message."""
    for rule, kind, rx in (("sell_object", "sell", _SELL_OBJECT), ("dropship_object", "dropship", _DROPSHIP_OBJECT),
                           ("supplier_request", "suppliers", _SUPPLIER)):
        if rx.search(t):
            if rule == "sell_object" and _DROPSHIP_OBJECT.search(t):
                return "dropship_object", "dropship", []
            return rule, kind, []
    vetoes = _vetoes(t)
    vetoed: list[str] = []
    for rule, kind, rx in (("product_ideas", "product_ideas", _IDEAS), ("dropship_noun", "dropship", _DROPSHIP_NOUN),
                           ("request_products", "find_products", _REQUEST_PRODUCTS), ("terse_products", "find_products", _TERSE)):
        if rx.search(t):
            if vetoes:
                vetoed.append(rule)
                continue
            return rule, kind, []
    return None, None, vetoed


def _phrase(tokens: list[str], start: int) -> list[str]:
    """The words after position `start` up to a stop word, punctuation or another preposition (at most MAX_PHRASE_TOKENS)."""
    out: list[str] = []
    for tok in tokens[start:]:
        if tok in _STOP or len(out) >= MAX_PHRASE_TOKENS:
            break
        out.append(tok)
    while out and out[0] in _DETERMINERS:
        out.pop(0)
    return out


def _audience_and_niche(tokens: list[str]) -> tuple[str | None, str | None]:
    """The first "for / to / targeting <people>" phrase is the audience; the first "for <thing>" phrase is a niche."""
    audience = niche = None
    for i, tok in enumerate(tokens):
        if tok not in _PREPOSITIONS:
            continue
        start = i + 1 + (1 if tok == "catering" and i + 1 < len(tokens) and tokens[i + 1] == "to" else 0)
        words = _phrase(tokens, start)
        if not words or words[0] in _VERBS or words[0] in _DEICTIC_WORDS:
            continue
        if words[-1] in _PEOPLE:
            if audience is None:
                audience = " ".join(words)
        elif tok == "for" and niche is None and not any(w.isdigit() for w in words):
            niche = " ".join(w for w in words if w not in _GENERIC and w not in _GEO_WORDS) or None
        if audience is not None and niche is not None:
            break
    return audience, niche


_SEED_AFTER = re.compile(
    r"\b(?:suppliers?|vendors?|manufacturers?|wholesalers?|factor(?:y|ies)|listings?|finds?)\s+(?:for|of)\s+(?P<a>[^,.?!;:]+)"
    r"|\bsourc(?:e|ing)\s+(?P<b>[^,.?!;:]+?)\s+(?:from|on|via|through)\b"
    r"|\b(?:search\s+(?:on\s+)?(?:cj|cjdropshipping|alibaba|aliexpress)\s+for)\s+(?P<c>[^,.?!;:]+)"
    r"|\b(?:find|search|look\s+up|show)\s+(?:me\s+)?(?P<d>(?:[\w'-]+\s+){1,4}?)on\s+(?:cj|cjdropshipping|alibaba|aliexpress)\b"
    r"|\b(?:products?|something|items?)\s+like\s+(?P<e>[^,.?!;:]+)"
    r"|\b(?:in|for)\s+the\s+(?P<f>(?:[\w'-]+\s+){0,2}?[\w'-]+)\s+(?:niche|space|category|market)\b"
    r"|\bniche:?\s+(?P<g>[^,.?!;:]+)"
    r"|\bwhere\s+(?:can|could|do|should)\s+(?:i|we)\s+(?:source|buy|get|find)\s+(?P<h>[^,.?!;:]+)")


def _clean_seed(raw: str) -> str | None:
    words = _phrase(_tokens(raw), 0)
    words = [w for w in words if w not in ("me", "us") and w not in _GEO_WORDS]
    if not words or all(w in _DEICTIC_WORDS or w in _GENERIC for w in words):
        return None
    return " ".join(words)


def _seed(t: str, niche: str | None, audience: str | None) -> tuple[str | None, str | None]:
    for m in _SEED_AFTER.finditer(t):
        group = next((g for g in m.groupdict().values() if g), None)
        seed = _clean_seed(group or "")
        if seed and (audience is None or seed != audience) and _tokens(seed)[-1:] != [] and _tokens(seed)[-1] not in _PEOPLE:
            kind = "niche" if m.group("f") or m.group("g") else "product"
            return seed, kind
    if niche:
        return niche, "niche"
    return None, None


def _geography(original: str, t: str) -> str | None:
    hits: list[tuple[int, str]] = []
    for code, rx in _GEO_CASED:
        m = rx.search(original or "")
        if m:
            hits.append((m.start(), code))
    for code, rx in _GEO_RE:
        m = rx.search(t)
        if m:
            hits.append((m.start(), code))
    return min(hits)[1] if hits else None


def _clip_term(text: str) -> str:
    words = [w for w in _tokens(text) if w not in _STOP][:6]
    return " ".join(words)[:60].strip()


def search_terms_for(seed: str | None, seed_kind: str | None, audience: str | None) -> tuple[str, ...]:
    """The fallback CJ search terms: the seed itself (a niche gets "<niche> products"), else the audience's product root
    ("pet owners" → "pet products", "pet accessories"; "new moms" → "baby products"), else none."""
    terms: list[str] = []
    if seed:
        terms.append(_clip_term(seed if seed_kind == "product" else f"{seed} products"))
    elif audience:
        words = _tokens(audience)
        root_words = [w for w in words[:-1] if w not in _AUDIENCE_SOFT and w not in _GENERIC and w not in _GEO_WORDS]
        root = " ".join(root_words) or _AUDIENCE_ROOT.get(words[-1] if words else "", "")
        if root:
            terms += [_clip_term(f"{root} products"), _clip_term(f"{root} accessories")]
    return tuple(dict.fromkeys(t for t in terms if len(t) >= 2))[:MAX_TERMS]


def _last_user_turn(history: Iterable[Any] | None) -> str | None:
    for turn in reversed(list(history or [])):
        role = getattr(turn, "role", None) or (turn.get("role") if isinstance(turn, dict) else None)
        content = getattr(turn, "content", None) if not isinstance(turn, dict) else turn.get("content")
        if role == "user" and str(content or "").strip():
            return str(content)
    return None


def _extract(message: str, t: str) -> dict[str, Any]:
    tokens = _tokens(message)
    audience, niche = _audience_and_niche(tokens)
    seed, seed_kind = _seed(t, niche, audience)
    return {"seed": seed, "seed_kind": seed_kind, "audience": audience, "geography": _geography(message, t)}


def _is_follow_up(t: str) -> bool:
    return len(t.split()) <= FOLLOW_UP_MAX_WORDS and bool(_DEICTIC.search(t)) and bool(_FOLLOW_UP_WORDS.search(t))


def detect(message: str, history: Iterable[Any] | None = None, *, force: bool = False) -> ProductIntent | None:
    """The message's product intent, or None when it is not a product request (and `force` is off). `force` (POST /product/search)
    always returns an intent: the rule that matched, else `forced`."""
    t = _norm(message)
    rule, kind, vetoed = _match(t)
    fields = _extract(message, t)
    source = "message"
    if _is_follow_up(t):
        prior = _last_user_turn(history)
        prior_t = _norm(prior or "")
        prior_rule = _match(prior_t)[0] if prior else None
        if prior_rule is not None or (rule is not None and prior):
            earlier = _extract(prior or "", prior_t)
            fields = {"seed": fields["seed"] or earlier["seed"],
                      "seed_kind": fields["seed_kind"] if fields["seed"] else earlier["seed_kind"],
                      "audience": fields["audience"] or earlier["audience"],
                      "geography": fields["geography"] or earlier["geography"]}
            if rule is None:
                rule, kind = "follow_up", "follow_up"
            source = "history"
    if rule is None:
        if not force:
            return None
        rule, kind, source = "forced", "forced", "forced"
    terms = search_terms_for(fields["seed"], fields["seed_kind"], fields["audience"])
    return ProductIntent(kind=kind or "find_products", rule=rule, seed=fields["seed"], seed_kind=fields["seed_kind"],
                         audience=fields["audience"], geography=fields["geography"], search_terms=terms, source=source,
                         vetoed=tuple(vetoed))
