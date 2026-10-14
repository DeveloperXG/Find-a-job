from uuid import UUID

import pytest

from app.domain.enums import ALL_ROLE_FAMILIES, ALL_SENIORITIES
from app.ingestion import normalize as n

# The 20 titles from ARCHITECTURE.md "Target roles": (title, role_family, seniority, employment).
TARGET_TITLES = [
    ("Junior Software Engineer (SDE I)", "sde", "junior", None),
    ("New Grad Software Engineer", "sde", "new_grad", None),
    ("Software Engineering Intern", "sde", "intern", "internship"),
    ("Backend Software Engineer (Junior)", "sde", "junior", None),
    ("Python Developer (Junior)", "sde", "junior", None),
    ("Full-Stack Developer (Junior)", "sde", "junior", None),
    ("Machine Learning Engineer (Junior)", "mle", "junior", None),
    ("Machine Learning Intern", "mle", "intern", "internship"),
    ("Applied Scientist Intern", "mle", "intern", "internship"),
    ("AI Engineer", "aie", "unknown", None),
    ("Applied AI Engineer", "aie", "unknown", None),
    ("AI Evaluation Engineer (Junior)", "aie", "junior", None),
    ("AI Safety Engineer (Junior)", "aie", "junior", None),
    ("AI Research Engineer (Entry-Level)", "research", "new_grad", None),
    ("AI/ML Research Intern", "research", "intern", "internship"),
    ("AI Research Fellow", "research", "unknown", "fellowship"),
    ("AI/ML Resident", "research", "unknown", "fellowship"),
    ("Data Scientist (Junior)", "data_science", "junior", None),
    ("Robotics Software Engineer (Junior)", "robotics", "junior", None),
    ("Computer Vision Engineer (Junior)", "cv", "junior", None),
]


def test_target_titles_cover_all_20() -> None:
    assert len(TARGET_TITLES) == 20


@pytest.mark.parametrize(("title", "family", "_s", "_e"), TARGET_TITLES)
def test_role_family_target_titles(title: str, family: str, _s: str, _e: str | None) -> None:
    assert n.infer_role_family(title) == family


@pytest.mark.parametrize(("title", "_f", "seniority", "_e"), TARGET_TITLES)
def test_seniority_target_titles(title: str, _f: str, seniority: str, _e: str | None) -> None:
    assert n.infer_seniority(title) == seniority


@pytest.mark.parametrize(("title", "_f", "_s", "employment"), TARGET_TITLES)
def test_employment_target_titles(title: str, _f: str, _s: str, employment: str | None) -> None:
    assert n.infer_employment_type(title, "full_time") == (employment or "full_time")


# --- html_to_text ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ("", ""),
        (None, ""),
        ("<p>Hello</p>", "Hello"),
        ("<p>Hello   \n   world</p>", "Hello world"),
        ("<script>alert(1)</script><p>Hi</p>", "Hi"),
        ("<style>p{color:red}</style><p>Hi</p>", "Hi"),
        ("<ul><li>One</li><li>Two</li></ul>", "- One\n- Two"),
        ("<p>A</p><p>B</p>", "A\n\nB"),
        ("A<br>B", "A\nB"),
        ("<h2>Title</h2><ul><li>x</li></ul>", "Title\n\n- x"),
        ("&amp; &lt;b&gt; caf&eacute;", "& <b> café"),
        ("<div>  spaced   out  </div>", "spaced out"),
        ("<p>a</p><p></p><p></p><p></p><p>b</p>", "a\n\nb"),
    ],
)
def test_html_to_text(html: str | None, expected: str) -> None:
    assert n.html_to_text(html) == expected


def test_html_to_text_truncates() -> None:
    out = n.html_to_text("<p>" + "x" * 20_000 + "</p>")
    assert len(out) == n.MAX_TEXT_CHARS
    assert out.endswith(n.TRUNCATION_MARKER)


def test_html_to_text_short_not_truncated() -> None:
    assert not n.html_to_text("<p>short</p>").endswith(n.TRUNCATION_MARKER)


# --- normalize_title ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Software Engineer", "software engineer"),
        ("Software Engineer (Remote)", "software engineer"),
        ("Software Engineer - Remote", "software engineer"),
        ("Software Engineer - San Francisco, CA", "software engineer"),
        ("Software Engineer | London", "software engineer"),
        ("Software Engineer (New York)", "software engineer"),
        ("Software Engineer (REQ-12345)", "software engineer"),
        ("Software Engineer - R12345", "software engineer"),
        ("Software Engineer #98765", "software engineer"),
        ("Software Engineer - Remote (REQ-1234)", "software engineer"),
        ("Software Engineer I", "software engineer 1"),
        ("Software Engineer II", "software engineer 2"),
        ("Software Engineer III", "software engineer 3"),
        ("Machine Learning Engineer (Junior)", "machine learning engineer (junior)"),
        ("  Data   Scientist  ", "data scientist"),
        ("Intern, Software Engineering - Toronto, ON", "intern, software engineering"),
    ],
)
def test_normalize_title(raw: str, expected: str) -> None:
    assert n.normalize_title(raw) == expected


# --- infer_seniority ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "text", "expected"),
    [
        ("Software Engineering Intern", "", "intern"),
        ("Summer 2027 Internship - ML", "", "intern"),
        ("Co-op Software Developer", "", "intern"),
        ("New Grad Software Engineer", "", "new_grad"),
        ("Software Engineer, University Graduate", "", "new_grad"),
        ("Software Engineer - Early Career", "", "new_grad"),
        ("Staff Software Engineer", "", "staff_plus"),
        ("Principal Engineer", "", "staff_plus"),
        ("Distinguished Engineer", "", "staff_plus"),
        ("Senior Staff Engineer", "", "staff_plus"),
        ("Senior Software Engineer", "", "senior"),
        ("Sr. Data Scientist", "", "senior"),
        ("Engineering Manager", "", "manager"),
        ("Head of Machine Learning", "", "manager"),
        ("Director of Engineering", "", "manager"),
        ("Junior Developer", "", "junior"),
        ("Associate Software Engineer", "", "junior"),
        ("Software Engineer I", "", "junior"),
        ("Software Engineer 1", "", "junior"),
        ("Software Engineer II", "", "mid"),
        ("Mid-Level Backend Engineer", "", "mid"),
        ("Software Engineer", "", "unknown"),
        ("AI Engineer", "We value strong senior engineers on the team.", "unknown"),
        ("Software Engineer", "This is an early career role for new grads.", "new_grad"),
        ("Internal Tools Engineer", "", "unknown"),
    ],
)
def test_infer_seniority(title: str, text: str, expected: str) -> None:
    assert n.infer_seniority(title, text) == expected


def test_seniority_values_are_in_vocabulary() -> None:
    for title in ("Intern", "Senior Engineer", "Engineer"):
        assert n.infer_seniority(title) in ALL_SENIORITIES


# --- infer_role_family ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "dept", "expected"),
    [
        ("Research Scientist", None, "research"),
        ("Research Engineer", None, "research"),
        ("Software Engineer, Research Resident", None, "research"),
        ("Robotics Engineer", None, "robotics"),
        ("Autonomy Software Engineer", None, "robotics"),
        ("Computer Vision Engineer", None, "cv"),
        ("Perception Engineer", None, "cv"),
        ("ML Engineer", None, "mle"),
        ("Applied Scientist", None, "mle"),
        ("Software Engineer, Machine Learning", None, "mle"),
        ("LLM Engineer", None, "aie"),
        ("GenAI Developer", None, "aie"),
        ("Agents Engineer", None, "aie"),
        ("Data Scientist", None, "data_science"),
        ("Data Engineer", None, "data_eng"),
        ("Analytics Engineer", None, "data_eng"),
        ("Backend Engineer", None, "sde"),
        ("Frontend Engineer", None, "sde"),
        ("SWE Intern", None, "sde"),
        ("Platform Engineer", None, "sde"),
        ("Account Executive", None, "other"),
        ("Engineer", "Machine Learning", "mle"),
        ("Engineer", "Engineering", "other"),
    ],
)
def test_infer_role_family(title: str, dept: str | None, expected: str) -> None:
    assert n.infer_role_family(title, dept) == expected
    assert expected in ALL_ROLE_FAMILIES


# --- infer_employment_type ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "hint", "expected"),
    [
        ("Research Fellow", "unknown", "fellowship"),
        ("AI Fellowship", "full_time", "fellowship"),
        ("ML Resident", "unknown", "fellowship"),
        ("AI Residency Program", "unknown", "fellowship"),
        ("Software Engineering Intern", "full_time", "internship"),
        ("Co-op Engineer", "unknown", "internship"),
        ("ML Internship", "contract", "internship"),
        ("Software Engineer", "full_time", "full_time"),
        ("Software Engineer", "contract", "contract"),
        ("Software Engineer", "unknown", "unknown"),
        ("Internal Tools Engineer", "full_time", "full_time"),
        ("Residential Services Lead", "unknown", "unknown"),
    ],
)
def test_infer_employment_type(title: str, hint: str, expected: str) -> None:
    assert n.infer_employment_type(title, hint) == expected  # type: ignore[arg-type]


# --- extract_min_yoe ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", None),
        ("No experience needed.", None),
        ("5+ years of experience in Python", 5),
        ("3-5 years experience required", 3),
        ("3 to 5 years of relevant experience", 3),
        ("At least 4 years in software", 4),
        ("Minimum of 2 years", 2),
        ("Five years of professional experience", 5),
        ("7+ yrs of industry experience", 7),
        ("0-2 years of experience", 0),
        ("1 year of experience with SQL and 5+ years of experience overall", 5),
        ("Nice to have: 8 years of experience", None),
        ("Founded 20 years ago; 3+ years of experience", 3),
        ("We have 40 years of experience in the industry", None),
    ],
)
def test_extract_min_yoe(text: str, expected: int | None) -> None:
    assert n.extract_min_yoe(text) == expected


# --- parse_locations ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "hint", "locs", "workplace", "countries"),
    [
        (None, "unknown", [], "unknown", []),
        ("", "onsite", [], "onsite", []),
        ("San Francisco, CA", "unknown", ["San Francisco, CA"], "unknown", ["US"]),
        ("Remote", "unknown", [], "remote", []),
        ("Remote - US", "unknown", ["US"], "remote", ["US"]),
        ("Anywhere", "unknown", [], "remote", []),
        ("New York, NY; Austin, TX", "unknown", ["New York, NY", "Austin, TX"], "unknown", ["US"]),
        ("Seattle, WA | Remote", "unknown", ["Seattle, WA"], "remote", ["US"]),
        ("London or Dublin", "unknown", ["London", "Dublin"], "unknown", ["GB", "IE"]),
        ("Toronto, ON", "unknown", ["Toronto, ON"], "unknown", ["CA"]),
        ("Berlin, Germany", "unknown", ["Berlin, Germany"], "unknown", ["DE"]),
        ("Hybrid - Boston, MA", "unknown", ["Boston, MA"], "hybrid", ["US"]),
        ("Austin, TX", "hybrid", ["Austin, TX"], "hybrid", ["US"]),
        ("United States", "unknown", ["United States"], "unknown", ["US"]),
        ("Remote (Canada)", "unknown", ["Canada"], "remote", ["CA"]),
        ("Bangalore", "onsite", ["Bangalore"], "onsite", ["IN"]),
    ],
)
def test_parse_locations(
    raw: str | None, hint: str, locs: list[str], workplace: str, countries: list[str]
) -> None:
    assert n.parse_locations(raw, hint) == (locs, workplace, countries)  # type: ignore[arg-type]


# --- parse_compensation_from_text -----------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "lo", "hi", "cur", "interval"),
    [
        ("Pay range $120,000 - $160,000", 120_000, 160_000, "USD", "year"),
        ("Pay range $120,000–$160,000 per year", 120_000, 160_000, "USD", "year"),
        ("$120k–$160k base", 120_000, 160_000, "USD", "year"),
        ("$120-160k", 120_000, 160_000, "USD", "year"),
        ("$55/hr", 55, 55, "USD", "hour"),
        ("$40 - $55 per hour", 40, 55, "USD", "hour"),
        ("€50,000 - €70,000", 50_000, 70_000, "EUR", "year"),
        ("£45,000 to £60,000", 45_000, 60_000, "GBP", "year"),
        ("C$90,000 - C$110,000", 90_000, 110_000, "CAD", "year"),
        ("CA$100k-CA$130k", 100_000, 130_000, "CAD", "year"),
        ("$1,200.50/hr", 1200.5, 1200.5, "USD", "hour"),
        ("Salary: $100,000 - $130,000 CAD", 100_000, 130_000, "CAD", "year"),
    ],
)
def test_parse_compensation(text: str, lo: float, hi: float, cur: str, interval: str) -> None:
    comp = n.parse_compensation_from_text(text)
    assert comp is not None
    assert (comp.min, comp.max, comp.currency, comp.interval) == (lo, hi, cur, interval)


@pytest.mark.parametrize("text", ["", "Competitive salary", "We have 100 employees", "5 years"])
def test_parse_compensation_none(text: str) -> None:
    assert n.parse_compensation_from_text(text) is None


# --- detect_work_auth_flags -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", []),
        ("We offer great benefits.", []),
        ("We are unable to provide visa sponsorship.", ["no_sponsorship"]),
        ("Candidates must not require sponsorship now or in the future.", ["no_sponsorship"]),
        ("No visa sponsorship is available.", ["no_sponsorship"]),
        ("We do not sponsor work visas.", ["no_sponsorship"]),
        ("Must be a U.S. citizen.", ["us_citizen_required"]),
        ("US citizenship is required.", ["us_citizen_required"]),
        ("Active security clearance required", ["security_clearance"]),
        ("TS/SCI clearance preferred", ["security_clearance"]),
        ("Visa sponsorship is available for this role.", ["sponsorship_available"]),
        ("We will sponsor qualified candidates.", ["sponsorship_available"]),
        (
            "U.S. citizenship required; Top Secret clearance. No sponsorship.",
            ["no_sponsorship", "us_citizen_required", "security_clearance"],
        ),
    ],
)
def test_detect_work_auth_flags(text: str, expected: list[str]) -> None:
    assert n.detect_work_auth_flags(text) == expected


# --- hashes ---------------------------------------------------------------------------------

CID = UUID("00000000-0000-0000-0000-000000000001")


def test_content_hash_is_stable_and_whitespace_case_insensitive() -> None:
    a = n.content_hash("Software Engineer", "Build  things.\n", "Remote")
    assert a == n.content_hash("software engineer", "build things.", " remote ")
    assert len(a) == 64


@pytest.mark.parametrize(
    "args",
    [
        ("Other Title", "Build things.", "Remote"),
        ("Software Engineer", "Build other things.", "Remote"),
        ("Software Engineer", "Build things.", "Austin, TX"),
    ],
)
def test_content_hash_changes_with_content(args: tuple[str, str, str]) -> None:
    assert n.content_hash(*args) != n.content_hash("Software Engineer", "Build things.", "Remote")


def test_content_hash_field_boundaries_do_not_collide() -> None:
    assert n.content_hash("ab", "c", None) != n.content_hash("a", "bc", None)


def test_fingerprint_stable_across_case_and_id_type() -> None:
    a = n.fingerprint(CID, "software engineer 1", "Austin, TX")
    assert a == n.fingerprint(str(CID).upper(), "Software Engineer 1", " austin, tx")
    assert len(a) == 64


@pytest.mark.parametrize(
    ("company", "title", "loc"),
    [
        (UUID(int=2), "software engineer 1", "Austin, TX"),
        (CID, "software engineer 2", "Austin, TX"),
        (CID, "software engineer 1", "Denver, CO"),
    ],
)
def test_fingerprint_changes(company: UUID, title: str, loc: str) -> None:
    assert n.fingerprint(company, title, loc) != n.fingerprint(
        CID, "software engineer 1", "Austin, TX"
    )
