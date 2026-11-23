"""Pure functions of the AI job map pipeline. Standard library only; no I/O here, so every step is unit-testable.

Method references: Babina, Fedyk, He & Hodson (2024), JFE 151:103745 (AI-relatedness w(s), omega(j));
Acemoglu, Autor, Hazell & Restrepo (2022), JOLE 40(S1) (role-weighted occupation exposure roll-up).
"""
import hashlib
import math
import random
import re
from collections import Counter, defaultdict

# ---------------------------------------------------------------- titles, locations, role keys

US_STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA", "colorado": "CO", "connecticut": "CT",
    "delaware": "DE", "district of columbia": "DC", "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID", "illinois": "IL",
    "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI",
    "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA",
    "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY", "puerto rico": "PR",
}
US_ABBR = set(US_STATES.values())


# Defaults are today's values; build.py passes the config's (decision points DP-01 to DP-04).
TRAILING_EMPLOYMENT_SUFFIX = r"-(?:ft|pt)\s*$"
TITLE_KEEP_CHARS = "a-z0-9+#"
REMOTE_PATTERN = "remote"
ROLE_KEY_FIELDS = ("firm", "title", "locations")


def norm_role_title(title, req_pattern=None, suffix_pattern=TRAILING_EMPLOYMENT_SUFFIX, keep_chars=TITLE_KEEP_CHARS):
    """Light normalisation for distinct-role counting: keeps level words (Senior vs junior are different roles)."""
    t = (title or "").lower()
    if req_pattern:
        t = re.sub(req_pattern, " ", t)
    if suffix_pattern:
        t = re.sub(suffix_pattern, " ", t)
    t = re.sub(f"[^{keep_chars}]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def norm_location_set(locations, remote_pattern=REMOTE_PATTERN):
    out = set()
    for loc in locations or []:
        s = re.sub(r"\s+", " ", (loc or "").lower()).strip()
        if not s:
            continue
        if re.search(remote_pattern, s):
            s = "remote:" + ("us" if re.search(r"\b(us|usa|united states)\b", s) else re.sub(r"[^a-z]+", "", re.sub(remote_pattern, "", s)) or "any")
        out.add(s)
    return tuple(sorted(out))


def role_key(firm_id, title, locations, req_sha=None, req_pattern=None, fields=ROLE_KEY_FIELDS, title_opts=None, loc_opts=None):
    """(firm, normalised title, normalised location set, requirement-text hash). A field left out of `fields` is
    blanked, so roles that differ only in it count once. The firm is always part of the key."""
    if "firm" not in fields:
        raise ValueError("the role key must include the firm")
    t = norm_role_title(title, req_pattern, **(title_opts or {})) if "title" in fields else ""
    locs = norm_location_set(locations, **(loc_opts or {})) if "locations" in fields else ()
    return (firm_id, t, locs, req_sha or "")


def parse_city_state(loc):
    """'Boston, MA' / 'Cambridge, Massachusetts, United States' -> ('Boston', 'MA'); anything else -> None."""
    parts = [p.strip() for p in re.split(r",|\|", loc or "") if p.strip()]
    if len(parts) < 2:
        return None
    city, st = parts[0], parts[1]
    code = st.upper() if st.upper() in US_ABBR else US_STATES.get(st.lower())
    if not code or re.search(r"remote|hybrid|\d", city, re.I):
        return None
    return (re.sub(r"\s+", " ", city).title(), code)


# ---------------------------------------------------------------- requirement text

QUOTES = str.maketrans({"\u2019": "'", "\u2018": "'", "\u02bc": "'", "\u201c": '"', "\u201d": '"'})


def _matches(patterns, text):
    """Patterns are anchored at the start of the heading text."""
    return any(re.match(p, text) for p in patterns)


def block_hash(block):
    return hashlib.sha256(re.sub(r"\s+", " ", block.strip().lower()).encode()).hexdigest()[:16]


def requirement_blocks(blocks, cfg, repeated=frozenset()):
    """Keep requirement blocks, drop boilerplate. Returns (kept_blocks, sectioned: bool).

    Headings are short blocks. A drop heading turns dropping on until the next heading; a keep heading turns keeping on.
    If the posting has any keep heading, only blocks under keep headings survive; otherwise everything not under a drop
    heading survives. Blocks whose hash repeats across the firm's postings (`repeated`) are always dropped.
    """
    maxc = cfg["heading_max_chars"]
    drop_p, keep_p = cfg["drop_heading_patterns"], cfg["keep_heading_patterns"]
    labelled, state, has_keep = [], "intro", False
    for b in blocks:
        s = b.strip()
        low = re.sub(r"^[^a-z0-9]+", "", s.lower().translate(QUOTES)).rstrip(": ")
        if s and len(s) <= maxc and not s.endswith(".") and len(low.split()) <= 8:
            if _matches(keep_p, low):
                # A short bullet such as "Experience with Python" can look like a heading: keep its text either way.
                state, has_keep = "keep", True
                labelled.append(("keep", s))
                continue
            if _matches(drop_p, low):
                state = "drop"
                continue
        labelled.append((state, s))
    kept = []
    for state, s in labelled:
        if not s or block_hash(s) in repeated:
            continue
        if has_keep and state == "keep":
            kept.append(s)
        elif not has_keep and state != "drop":
            kept.append(s)
    return kept, has_keep


def repeated_blocks(postings_blocks, share, min_postings):
    """Block hashes that appear in >= share of a firm's postings (firm has >= min_postings)."""
    n = len(postings_blocks)
    if n < min_postings:
        return frozenset()
    c = Counter()
    for blocks in postings_blocks:
        c.update({block_hash(b) for b in blocks if b.strip()})
    return frozenset(h for h, k in c.items() if k / n >= share)


# ---------------------------------------------------------------- tokens, n-grams, skills

STOP = set("""a an and are as at be been but by can for from has have i if in into is it its may of on or our so such than that the
their them then there these they this to us was we were what when where which while who will with within without you your yours
etc e g eg ie i.e via per plus all any each other more most must should would could able also well across both including include
includes using use used work working new strong excellent good great preferred required requirements requirement equivalent
related relevant years year experience experiences knowledge understanding ability skills skill familiarity proficiency
proficient demonstrated proven solid hands minimum least degree bachelor bachelors master masters phd field fields similar
role roles team teams help helping environment environments level levels make making one two three five plus""".split())

TOKEN = re.compile(r"[a-z0-9][a-z0-9+#.]*[a-z0-9+#]|[a-z0-9]")
SEGMENT = re.compile(r"[;:,!?()\[\]{}•·|/]|\.\s|\.$|\s[-–—]\s|\n")


def tokens(segment, token_alias, token_re=TOKEN):
    out = []
    for t in token_re.findall(segment.lower()):
        out.extend(token_alias[t].split() if t in token_alias else [t])
    return out


SEED_MARK = "\x00seed"


def ngrams_of_text(text, max_n, token_alias, ngram_alias, seeds=(), stop=STOP, token_re=TOKEN, segment_re=SEGMENT, mask_seeds=True):
    """Set of candidate skill n-grams: 1..max_n tokens, never crossing punctuation, never starting or ending with a
    stopword, never pure digits. Seed phrases are found first and, with mask_seeds (the default), masked, so no
    candidate contains or splits a seed (a fragment such as 'large language' would co-occur with its seed by
    construction). Seeds found are returned as themselves."""
    found = set()
    seed_toks = sorted((s.split() for s in seeds), key=len, reverse=True)
    alias_multi = {tuple(k.split()): v.split() for k, v in ngram_alias.items()}
    for seg in segment_re.split(text):
        toks = tokens(seg, token_alias, token_re)
        # apply multi-word aliases (e.g. 'large language model' -> 'large language models') before seed matching
        i, out = 0, []
        while i < len(toks):
            for k, v in alias_multi.items():
                if tuple(toks[i:i + len(k)]) == k:
                    out.extend(v); i += len(k); break
            else:
                out.append(toks[i]); i += 1
        toks, i, masked = out, 0, []
        while i < len(toks):
            for st in seed_toks:
                if toks[i:i + len(st)] == st:
                    found.add(" ".join(st)); masked.extend([SEED_MARK] if mask_seeds else st); i += len(st); break
            else:
                masked.append(toks[i]); i += 1
        for n in range(1, max_n + 1):
            for j in range(len(masked) - n + 1):
                g = masked[j:j + n]
                if SEED_MARK in g or g[0] in stop or g[-1] in stop or all(x.isdigit() for x in g):
                    continue
                s = " ".join(g)
                found.add(ngram_alias.get(s, s))
    return found


def build_vocabulary(role_ngrams, role_firm, min_roles, min_firms, max_doc_share):
    """role_ngrams: {role_id: set(ngrams)}. Returns {skill: (roles, firms)} passing support rules."""
    df, firms = Counter(), defaultdict(set)
    for rid, gs in role_ngrams.items():
        df.update(gs)
        f = role_firm[rid]
        for g in gs:
            firms[g].add(f)
    n = max(1, len(role_ngrams))
    return {g: (k, len(firms[g])) for g, k in df.items()
            if k >= min_roles and len(firms[g]) >= min_firms and k / n <= max_doc_share}


# ---------------------------------------------------------------- AI-relatedness

def compute_w(role_skills, seeds):
    """w(s) = (# roles requiring s AND a seed skill) / (# roles requiring s)."""
    seeds = set(seeds)
    with_s, with_s_and_seed = Counter(), Counter()
    for skills in role_skills.values():
        has_seed = bool(skills & seeds)
        for s in skills:
            with_s[s] += 1
            if has_seed:
                with_s_and_seed[s] += 1
    return {s: with_s_and_seed[s] / with_s[s] for s in with_s}


def omega(skills, w, min_skills=1):
    """omega(j) = mean of w(s) over the role's skills; None when fewer than min_skills skills have a w."""
    vals = [w[s] for s in skills if s in w]
    if len(vals) < min_skills:
        return None
    return sum(vals) / len(vals)


def term_regex(terms):
    parts = sorted({re.escape(t.lower()) for t in terms}, key=len, reverse=True)
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(parts) + r")(?![a-z0-9])") if parts else None


def signal_types(text_lower, om, threshold, rx):
    """Flags per the config: builds needs omega > threshold; integrates excludes builds; uses_tools only for roles
    that are otherwise not AI-related. Returns dict of booleans plus ai_related."""
    ai = om is not None and om > threshold
    builds = ai and bool(rx["builds"] and rx["builds"].search(text_lower))
    integrates = (not builds) and bool(rx["integrates"] and rx["integrates"].search(text_lower))
    uses = (om is not None and not ai and not builds and not integrates
            and bool(rx["uses_tools"] and rx["uses_tools"].search(text_lower)))
    return {"ai_related": ai, "builds": builds, "integrates": integrates, "uses_tools": uses}


# ---------------------------------------------------------------- shapes and tiers

def distribution(labels):
    c = Counter(labels)
    n = sum(c.values())
    return {k: v / n for k, v in c.items()} if n else {}


def js_similarity(p, q):
    """1 - Jensen-Shannon distance (base 2), in [0, 1]."""
    keys = set(p) | set(q)
    m = {k: 0.5 * (p.get(k, 0) + q.get(k, 0)) for k in keys}

    def kl(a):
        return sum(a[k] * math.log2(a[k] / m[k]) for k in keys if a.get(k, 0) > 0)
    jsd = 0.5 * kl(p) + 0.5 * kl(q)
    return 1 - math.sqrt(max(0.0, min(1.0, jsd)))


def split_half_similarity(labels, splits, rng):
    """Median similarity between random halves of one firm's role labels."""
    labels = list(labels)
    n = len(labels)
    if n < 2:
        return None
    sims = []
    for _ in range(splits):
        idx = list(range(n))
        rng.shuffle(idx)
        h = n // 2
        a = distribution(labels[i] for i in idx[:h])
        b = distribution(labels[i] for i in idx[h:2 * h])
        sims.append(js_similarity(a, b))
    sims.sort()
    return sims[len(sims) // 2]


def stability_curve(firm_labels, bins, splits, seed):
    """firm_labels: {firm: [label per distinct role]}. Returns rows per role-count bin with median, p25, p75 of the
    firms' median split-half similarity."""
    rng = random.Random(seed)
    per = []
    for firm in sorted(firm_labels):
        labels = firm_labels[firm]
        s = split_half_similarity(labels, splits, rng)
        if s is not None:
            per.append((len(labels), s))
    rows = []
    for lo, hi in bins:
        vals = sorted(s for n, s in per if lo <= n <= hi)
        if not vals:
            rows.append({"roles_from": lo, "roles_to": hi, "firms": 0, "median_similarity": None, "p25": None, "p75": None})
            continue
        q = lambda f: vals[min(len(vals) - 1, int(f * (len(vals) - 1) + 0.5))]
        rows.append({"roles_from": lo, "roles_to": hi, "firms": len(vals), "median_similarity": round(q(0.5), 4),
                     "p25": round(q(0.25), 4), "p75": round(q(0.75), 4)})
    return rows


def choose_cutoff(curve, plateau_min_roles, within, max_next_gain, fallback):
    """Smallest bin start whose median is within `within` of the plateau (median over bins starting at or above
    plateau_min_roles) and whose gain to the next bin is below max_next_gain. Returns (cutoff, plateau, reason)."""
    usable = [r for r in curve if r["median_similarity"] is not None and r["firms"] >= 3]
    plat = [r["median_similarity"] for r in usable if r["roles_from"] >= plateau_min_roles]
    if not plat:
        return fallback, None, "no plateau bins with at least 3 firms; fallback used"
    plat.sort()
    plateau = plat[len(plat) // 2]
    for i, r in enumerate(usable):
        nxt = usable[i + 1]["median_similarity"] if i + 1 < len(usable) else r["median_similarity"]
        if plateau - r["median_similarity"] <= within and nxt - r["median_similarity"] < max_next_gain:
            return r["roles_from"], plateau, "rule met"
    return fallback, plateau, "rule never met; fallback used"


def assign_tier(distinct_roles, cutoff):
    return "A" if distinct_roles >= cutoff else "B"


# ---------------------------------------------------------------- posting dynamics

def days_between(a, b):
    from datetime import date
    y1, m1, d1 = map(int, a[:10].split("-"))
    y2, m2, d2 = map(int, b[:10].split("-"))
    return (date(y2, m2, d2) - date(y1, m1, d1)).days + 1


def km_median(durations):
    """Kaplan-Meier median. durations: list of (days, closed: bool). Returns None if survival never drops to 0.5."""
    if not durations:
        return None
    times = sorted({d for d, _ in durations})
    at_risk, s = len(durations), 1.0
    for t in times:
        deaths = sum(1 for d, c in durations if d == t and c)
        n_t = sum(1 for d, _ in durations if d == t)
        if at_risk > 0 and deaths:
            s *= 1 - deaths / at_risk
        if s <= 0.5:
            return t
        at_risk -= n_t
    return None


RELIST_FIELDS = ("firm", "title", "locations", "hash")
_RELIST_KEY = {"firm": "firm", "title": "title", "locations": "locs", "hash": "hash"}


def relisted_roles(postings, fields=RELIST_FIELDS, min_gap_days=1):
    """postings: list of dicts with key (firm,title,locs,hash), source_id, first_seen, last_seen. A role is relisted
    when a later posting id with the same key (the `fields`) is first seen at least min_gap_days after an earlier
    one's last_seen. Only postings with an ad hash are considered."""
    groups = defaultdict(list)
    for p in postings:
        if p["hash"]:
            groups[tuple(p[_RELIST_KEY[f]] for f in fields)].append(p)
    n = 0
    for ps in groups.values():
        ps.sort(key=lambda p: p["first_seen"])
        if any(days_between(max(q["last_seen"] for q in ps[:i]), ps[i]["first_seen"]) - 1 >= min_gap_days
               and ps[i]["source_id"] not in {q["source_id"] for q in ps[:i]}
               for i in range(1, len(ps))):
            n += 1
    return n


# ---------------------------------------------------------------- exposure roll-up (deferred on the site; tested)

def exposure_rollup(role_occupations, exposure):
    """After Acemoglu et al. (2022): role-weighted mean of occupation exposure. Roles without an occupation or
    without an exposure value are left out and reported. Returns (score or None, roles_used, roles_left_out)."""
    used = [exposure[o] for o in role_occupations if o and o in exposure]
    left = len(role_occupations) - len(used)
    return (sum(used) / len(used) if used else None), len(used), left


# ---------------------------------------------------------------- sector

def load_buckets(rows):
    return {r["naics_prefix"]: (r["bucket_id"], r["bucket"]) for r in rows}


def naics_bucket(code, buckets):
    """Longest-prefix match. Returns (bucket_id, bucket, prefix) or (None, None, None)."""
    code = re.sub(r"\D", "", str(code or ""))
    for k in range(len(code), 1, -1):
        if code[:k] in buckets:
            b = buckets[code[:k]]
            return b[0], b[1], code[:k]
    return None, None, None


SUFFIX = re.compile(r"\b(incorporated|inc|llc|l\s?l\s?c|corp|corporation|co|company|ltd|limited|plc|lp|l\s?p|llp|pllc|pc|na|n\s?a|usa|us|the)\b")


def norm_employer(name):
    s = (name or "").lower().replace("&", " and ")
    s = re.sub(r"[.,'’`]", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = SUFFIX.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()
