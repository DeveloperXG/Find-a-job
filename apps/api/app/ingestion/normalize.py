"""Pure parsing helpers that turn messy posting text into structured, filterable attributes.

No I/O. Every function is deterministic; none calls an LLM.
"""

import hashlib
import re
from typing import Final
from uuid import UUID

from bs4 import BeautifulSoup

from app.domain.enums import CompInterval, EmploymentType, RoleFamily, Seniority, WorkplaceType
from app.domain.jobs import Compensation

MAX_TEXT_CHARS: Final = 12_000
TRUNCATION_MARKER: Final = "…[truncated]"

_WS = re.compile(r"[ \t\r\f\v ]+")
_BLANKS = re.compile(r"\n{3,}")


def html_to_text(html: str | None) -> str:
    """HTML -> plain text. `<li>` becomes "- " lines; capped at 12,000 chars."""
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    for node in soup.find_all(string=True):
        node.replace_with(re.sub(r"\s+", " ", node))  # source newlines are not line breaks
    for li in soup.find_all("li"):
        li.insert_before("\n- ")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for block in soup.find_all(["p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "ul", "ol"]):
        block.insert_before("\n")
        block.append("\n")
    lines = [_WS.sub(" ", line).strip() for line in soup.get_text().splitlines()]
    text = _BLANKS.sub("\n\n", "\n".join(lines)).strip()
    if len(text) > MAX_TEXT_CHARS:
        keep = MAX_TEXT_CHARS - len(TRUNCATION_MARKER)
        text = text[:keep].rstrip() + TRUNCATION_MARKER
    return text


def _compile[T: str](rules: tuple[tuple[T, str], ...]) -> tuple[tuple[T, re.Pattern[str]], ...]:
    return tuple((label, re.compile(pat, re.IGNORECASE)) for label, pat in rules)


# --- titles ---------------------------------------------------------------------------------

_LOCATION_WORDS = (
    r"remote|hybrid|on-?site|anywhere|worldwide|emea|apac|latam|north america|"
    r"united states|usa|u\.s\.a?\.?|canada|united kingdom|uk|germany|india|ireland|france|"
    r"netherlands|singapore|australia|new york|nyc|san francisco|sf|bay area|seattle|austin|"
    r"boston|chicago|los angeles|london|toronto|berlin|dublin|paris|palo alto|mountain view|"
    r"menlo park|sunnyvale|redwood city|denver|atlanta|pittsburgh|remote-first"
)
_LOCATIONISH = (
    rf"(?:[^,()]*\b(?:{_LOCATION_WORDS})\b[^()]*|[A-Za-z .'-]+,\s*(?:[A-Z]{{2}}|[A-Z][a-z]+))"
)
_REQ_ID = re.compile(
    r"\s*(?:[\(\[]\s*(?:req(?:uisition)?|job|id)?\s*[-#:]?\s*[A-Za-z]{0,4}-?\d{3,}\s*[\)\]]"
    r"|[-–—|:,]\s*(?:req(?:uisition)?|job\s*id|id)\s*[-#:]?\s*[A-Za-z0-9-]*\d[A-Za-z0-9-]*"
    r"|[-–—|]\s*[A-Z]{1,4}-?\d{4,}"
    r"|\s#\d{3,})\s*$",
    re.IGNORECASE,
)
_PAREN_LOCATION = re.compile(rf"\s*[\(\[]\s*{_LOCATIONISH}\s*[\)\]]\s*$", re.IGNORECASE)
_SEP_LOCATION = re.compile(rf"\s*[-–—|@]\s*{_LOCATIONISH}\s*$", re.IGNORECASE)
_COMMA_LOCATION = re.compile(rf",\s*(?:{_LOCATION_WORDS})\b[^,]*$", re.IGNORECASE)
_ROMAN_LEVEL = re.compile(r"\b(III|II|I)\s*$")
_ROMAN_MAP = {"I": "1", "II": "2", "III": "3"}


def normalize_title(title: str) -> str:
    """Lowercase, drop req-IDs / location / "(Remote)" suffixes, map trailing I/II/III to 1/2/3."""
    t = _WS.sub(" ", title).strip()
    for _ in range(4):  # suffixes can stack: "Engineer - Remote (REQ-1234)"
        stripped = t
        for pat in (_REQ_ID, _PAREN_LOCATION, _SEP_LOCATION, _COMMA_LOCATION):
            stripped = pat.sub("", stripped).strip()
        if stripped == t:
            break
        t = stripped
    t = _ROMAN_LEVEL.sub(lambda m: _ROMAN_MAP[m.group(1)], t)
    return _WS.sub(" ", t).strip().lower()


# --- seniority ------------------------------------------------------------------------------

_SENIORITY_RULES: Final[tuple[tuple[Seniority, re.Pattern[str]], ...]] = _compile(
    (
        ("intern", r"\bintern(?:ship)?s?\b|\bco-?op\b"),
        (
            "new_grad",
            r"new[\s-]?grad|\bgraduate\b|\buniversity\b|early[\s-]career|entry[\s-]level"
            r"|\bcampus\b|recent graduate",
        ),
        (
            "staff_plus",
            r"\bstaff\b|\bprincipal\b|\bdistinguished\b|\bfellow\b(?<!ai research fellow)",
        ),
        ("senior", r"\bsenior\b|\bsr\b\.?"),
        ("manager", r"\bmanager\b|\bhead of\b|\bdirector\b|\bvp\b"),
        ("junior", r"\bjunior\b|\bjr\b\.?|\bassociate\b|\b(?:i|1)\b\s*$|\blevel\s*(?:i|1)\b"),
        ("mid", r"\bmid[\s-]?level\b|\bintermediate\b|\b(?:ii|2)\b\s*$|\blevel\s*(?:ii|2)\b"),
    )
)
# Text fallback only for the unambiguous entry-level phrases; "senior" etc. in a body is noise.
_TEXT_NEW_GRAD = re.compile(
    r"new[\s-]?grad|early[\s-]career|recent graduates?|university grad", re.IGNORECASE
)


def infer_seniority(title: str, text: str = "") -> Seniority:
    for level, pat in _SENIORITY_RULES:
        if level == "staff_plus" and re.search(r"\b(?:research|ai|ml)\s+fellow", title, re.I):
            continue  # a research fellowship is entry level, not "Fellow" seniority
        if pat.search(title):
            return level
    if _TEXT_NEW_GRAD.search(text):
        return "new_grad"
    return "unknown"


# --- role family ----------------------------------------------------------------------------

_ROLE_RULES: Final[tuple[tuple[RoleFamily, re.Pattern[str]], ...]] = _compile(
    (
        (
            "research",
            r"research\s+(?:scientist|engineer|intern|fellow|resident|associate)"
            r"|\bresident\b|\bresidency\b|\bfellow(?:ship)?\b",
        ),
        ("robotics", r"robotics?|autonomy|autonomous"),
        ("cv", r"computer vision|perception"),
        ("mle", r"machine learning|\bml\b|applied scientist"),
        (
            "aie",
            r"\bai\s+(?:engineer|developer|safety|evaluation)|applied ai|\bllm|gen\s?ai|"
            r"generative ai|agents\b|agentic|evaluation|\bevals?\b",
        ),
        ("data_science", r"data scien"),
        ("data_eng", r"data engineer|analytics engineer"),
        (
            "sde",
            r"software|back-?end|front-?end|full[\s-]?stack|\bswe\b|\bsde\b|"
            r"python developer|platform",
        ),
    )
)


def infer_role_family(title: str, dept: str | None = None) -> RoleFamily:
    """First matching rule wins; the title is tried before the department."""
    for source in (title, dept or ""):
        for family, pat in _ROLE_RULES:
            if pat.search(source):
                return family
    return "other"


# --- employment type ------------------------------------------------------------------------

_FELLOWSHIP = re.compile(r"\bfellow(?:ship)?\b|\bresident\b|\bresidency\b", re.IGNORECASE)
_INTERNSHIP = re.compile(r"\bintern(?:ship)?s?\b|\bco-?op\b", re.IGNORECASE)


def infer_employment_type(title: str, hint: EmploymentType = "unknown") -> EmploymentType:
    """Title keywords beat the ATS's own value (ATSes label interns "full time"); else `hint`."""
    if _FELLOWSHIP.search(title):
        return "fellowship"
    if _INTERNSHIP.search(title):
        return "internship"
    return hint


# --- years of experience --------------------------------------------------------------------

_NUM_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}  # fmt: skip
_NUM = r"(\d{1,2}|" + "|".join(_NUM_WORDS) + r")"
_YOE = re.compile(
    rf"\b{_NUM}\s*(?:\+|-|–|to)?\s*{_NUM}?\s*\+?\s*(?:years?|yrs?)\b"
    r"(?:\W+[A-Za-z-]+){0,4}?\W+(?:experience|exp)\b"
    rf"|(?:at least|minimum(?: of)?|min\.?)\s*{_NUM}\s*\+?\s*(?:years?|yrs?)\b",
    re.IGNORECASE,
)
_OPTIONAL = re.compile(r"preferred|nice to have|bonus|a plus|desired|ideally", re.IGNORECASE)
_MAX_PLAUSIBLE_YOE = 20


def _to_int(s: str) -> int:
    return int(s) if s.isdigit() else _NUM_WORDS[s.lower()]


def extract_min_yoe(text: str) -> int | None:
    """Highest minimum-years requirement found ("3-5 years" counts as 3), else None.

    Matches that sit next to "preferred / nice to have / bonus" are ignored.
    """
    best: int | None = None
    for m in _YOE.finditer(text):
        context = text[max(0, m.start() - 80) : m.end() + 20]
        if _OPTIONAL.search(context):
            continue
        groups = [g for g in m.groups() if g]
        value = _to_int(groups[0])
        if value > _MAX_PLAUSIBLE_YOE:
            continue
        best = value if best is None else max(best, value)
    return best


# --- locations ------------------------------------------------------------------------------

_LOC_SPLIT = re.compile(r"\s*(?:;|\||/|\bor\b)\s*", re.IGNORECASE)
_REMOTE = re.compile(r"\bremote(?:-first)?\b|\banywhere\b|\bwork from home\b|\bdistributed\b", re.I)
_HYBRID = re.compile(r"\bhybrid\b", re.IGNORECASE)
_ONSITE = re.compile(r"\bon-?site\b|\bin[\s-]office\b", re.IGNORECASE)
_REMOTE_NOISE = re.compile(
    r"\(?\s*\b(?:remote(?:-first)?|anywhere|hybrid|on-?site)\b\s*\)?|[-–—:,]\s*$|^\s*[-–—:,]", re.I
)
_US_STATES = frozenset(
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM "
    "NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split()
)
_CA_PROVINCES = frozenset("AB BC MB NB NL NS ON PE QC SK".split())
_COUNTRY_NAMES: Final[tuple[tuple[str, re.Pattern[str]], ...]] = tuple(
    (code, re.compile(pat, re.IGNORECASE))
    for code, pat in (
        ("US", r"\bunited states\b|\busa\b|\bu\.s\.a?\.?|\bus\b|\bamerica\b(?<!north america)"),
        ("CA", r"\bcanada\b"),
        ("GB", r"\bunited kingdom\b|\buk\b|\bengland\b|\bscotland\b|\blondon\b"),
        ("DE", r"\bgermany\b|\bberlin\b|\bmunich\b"),
        ("IE", r"\bireland\b|\bdublin\b"),
        ("FR", r"\bfrance\b|\bparis\b"),
        ("NL", r"\bnetherlands\b|\bamsterdam\b"),
        ("IN", r"\bindia\b|\bbangalore\b|\bbengaluru\b|\bhyderabad\b"),
        ("SG", r"\bsingapore\b"),
        ("AU", r"\baustralia\b|\bsydney\b"),
    )
)
_TRAILING_STATE = re.compile(r",\s*([A-Z]{2})\b(?:\s*,?\s*\d{5})?\s*$")


def _country_of(part: str) -> str | None:
    if (m := _TRAILING_STATE.search(part)) is not None:
        code = m.group(1)
        if code in _US_STATES:
            return "US"
        if code in _CA_PROVINCES:
            return "CA"
    for code, pat in _COUNTRY_NAMES:
        if pat.search(part):
            return code
    return None


def parse_locations(
    raw: str | None, workplace_hint: WorkplaceType = "unknown"
) -> tuple[list[str], WorkplaceType, list[str]]:
    """Return `(locations, workplace_type, countries)`; countries are ISO 3166-1 alpha-2.

    The text wins when it says remote/hybrid/on-site; otherwise `workplace_hint` is kept.
    """
    if not raw or not raw.strip():
        return [], workplace_hint, []
    workplace: WorkplaceType = workplace_hint
    if _HYBRID.search(raw):
        workplace = "hybrid"
    elif _REMOTE.search(raw):
        workplace = "remote"
    elif _ONSITE.search(raw):
        workplace = "onsite"

    locations: list[str] = []
    countries: list[str] = []
    for part in _LOC_SPLIT.split(raw):
        part = part.strip()
        if not part:
            continue
        country = _country_of(part)
        if country and country not in countries:
            countries.append(country)
        cleaned = _WS.sub(" ", _REMOTE_NOISE.sub(" ", part)).strip(" -–—:,()")
        if cleaned and cleaned not in locations:
            locations.append(cleaned)
    return locations, workplace, countries


# --- compensation ---------------------------------------------------------------------------

_CURRENCY = {"$": "USD", "€": "EUR", "£": "GBP", "C$": "CAD", "CA$": "CAD", "CAD$": "CAD"}
_MONEY = r"(?:CA\$|CAD\$|C\$|\$|€|£)"
_AMOUNT = r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*([kK])?"
_COMP_RANGE = re.compile(
    rf"({_MONEY})\s*{_AMOUNT}\s*(?:-|–|—|to)\s*(?:{_MONEY})?\s*{_AMOUNT}"
    r"(?:\s*(?:/|per)\s*(hr|hour|yr|year|annum))?",
    re.IGNORECASE,
)
_COMP_SINGLE = re.compile(
    rf"({_MONEY})\s*{_AMOUNT}\s*(?:/|per)\s*(hr|hour|yr|year|annum)", re.IGNORECASE
)
_CURRENCY_CODES = re.compile(r"\b(USD|EUR|GBP|CAD)\b")


def _amount(num: str, k: str | None) -> float:
    value = float(num.replace(",", ""))
    return value * 1000 if k else value


def _currency(symbol: str, window: str) -> str:
    sym = symbol.upper() if symbol[0].isalpha() else symbol
    if sym == "$" and (m := _CURRENCY_CODES.search(window)):
        return m.group(1)
    return _CURRENCY.get(sym, "USD")


def _interval(unit: str | None, low: float, high: float) -> CompInterval:
    if unit:
        return "hour" if unit.lower() in ("hr", "hour") else "year"
    return "year" if low >= 10_000 and high >= 10_000 else "unknown"


def parse_compensation_from_text(text: str) -> Compensation | None:
    """First pay range in `text`: `$120,000 - $160,000`, `$120k–$160k`, `$55/hr`, € / £ / C$."""
    candidates: list[tuple[int, float, float, str, str | None]] = []
    if m := _COMP_RANGE.search(text):
        lo, hi = _amount(m.group(2), m.group(3)), _amount(m.group(4), m.group(5))
        if m.group(5) and not m.group(3) and lo < 1000:  # "$120-160k": the k covers both ends
            lo *= 1000
        candidates.append((m.start(), lo, hi, m.group(1), m.group(6)))
    if m := _COMP_SINGLE.search(text):
        v = _amount(m.group(2), m.group(3))
        candidates.append((m.start(), v, v, m.group(1), m.group(4)))
    if not candidates:
        return None
    pos, lo, hi, symbol, unit = min(candidates)
    window = text[max(0, pos - 20) : pos + 80]
    return Compensation(
        min=min(lo, hi),
        max=max(lo, hi),
        currency=_currency(symbol, window),
        interval=_interval(unit, lo, hi),
    )


# --- work authorisation ---------------------------------------------------------------------

_WORK_AUTH_RULES: Final[tuple[tuple[str, re.Pattern[str]], ...]] = tuple(
    (flag, re.compile(pat, re.IGNORECASE))
    for flag, pat in (
        (
            "no_sponsorship",
            r"(?:not|unable to|cannot|can't|won't|will not|do not|does not|don't)\s+"
            r"(?:\w+\s+){0,3}?(?:offer|provide|support)?\s*(?:visa\s+)?sponsor"
            r"|no\s+(?:visa\s+)?sponsorship|without\s+(?:visa\s+)?sponsorship"
            r"|sponsorship\s+(?:is\s+)?(?:not\s+(?:available|offered|provided)|unavailable)"
            r"|must\s+be\s+(?:legally\s+)?(?:authorized|eligible)\s+to\s+work\b[^.]{0,60}"
            r"without\s+sponsorship",
        ),
        (
            "us_citizen_required",
            r"u\.?s\.?\s+citizen(?:ship)?\s+(?:is\s+)?required"
            r"|must\s+be\s+a\s+u\.?s\.?\s+citizen|requires?\s+u\.?s\.?\s+citizen"
            r"|(?:only\s+)?u\.?s\.?\s+citizens?\s+(?:and|or)\s+(?:permanent\s+residents|green)"
            r"|citizenship\s+is\s+required",
        ),
        (
            "security_clearance",
            r"security\s+clearance|\bclearance\s+required|\bts/sci\b|top\s+secret|"
            r"secret\s+clearance|ability\s+to\s+obtain\s+a?\s*clearance",
        ),
        (
            "sponsorship_available",
            r"(?<!no\s)(?<!not\s)\b(?:visa\s+)?sponsorship\s+(?:is\s+)?available|"
            r"we\s+(?:do\s+)?sponsor\s+(?:work\s+)?visas?|will\s+sponsor|"
            r"(?:offer|provide)s?\s+(?:visa\s+)?sponsorship|visa\s+sponsorship\s+provided",
        ),
    )
)


def detect_work_auth_flags(text: str) -> list[str]:
    """Flags in a stable order; `no_sponsorship` suppresses `sponsorship_available`."""
    flags = [flag for flag, pat in _WORK_AUTH_RULES if pat.search(text)]
    if "no_sponsorship" in flags and "sponsorship_available" in flags:
        flags.remove("sponsorship_available")
    return flags


# --- hashes ---------------------------------------------------------------------------------


def _norm_for_hash(s: str | None) -> str:
    return _WS.sub(" ", (s or "").lower()).strip()


def _sha256(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def content_hash(title: str, description_text: str, location_raw: str | None) -> str:
    """sha256 of normalized text + title + location. Changes when the posting is edited."""
    body = " ".join(_norm_for_hash(description_text).split())
    return _sha256(_norm_for_hash(title), body, _norm_for_hash(location_raw))


def fingerprint(company_id: UUID | str, title_normalized: str, primary_location: str | None) -> str:
    """sha256 of company_id + title_normalized + primary location (a role across ATSes)."""
    return _sha256(
        str(company_id).lower(), _norm_for_hash(title_normalized), _norm_for_hash(primary_location)
    )
