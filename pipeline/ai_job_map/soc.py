"""Title -> O*NET-SOC using the exact-match title map built in a-new-shape-for-work (data/title-map.tsv, from O*NET 31.0
title tables). The normaliser is copied from that repo's cluster/title_norm.py so both sides normalise identically.
Ambiguous, excluded or unknown titles are 'unassigned'; no candidate is ever picked for them."""
import csv
import re

LEVEL_EDGE = {"senior", "sr", "junior", "jr", "lead", "principal", "staff", "entry", "entry-level", "mid", "mid-level",
              "level", "i", "ii", "iii", "iv", "v", "1", "2", "3", "4", "5", "experienced", "new", "grad", "graduate"}
MODE = re.compile(r"\b(remote|hybrid|onsite|on-site|in-office|full[- ]time|part[- ]time|per diem|prn|contract|temporary|temp)\b")
CUT = re.compile(r"\s+[-–—|/]\s+|,|\s+at\s+|\s+@\s+")

MAJOR_GROUPS = {
    "11": "Management", "13": "Business and Financial Operations", "15": "Computer and Mathematical",
    "17": "Architecture and Engineering", "19": "Life, Physical, and Social Science", "21": "Community and Social Service",
    "23": "Legal", "25": "Educational Instruction and Library", "27": "Arts, Design, Entertainment, Sports, and Media",
    "29": "Healthcare Practitioners and Technical", "31": "Healthcare Support", "33": "Protective Service",
    "35": "Food Preparation and Serving Related", "37": "Building and Grounds Cleaning and Maintenance",
    "39": "Personal Care and Service", "41": "Sales and Related", "43": "Office and Administrative Support",
    "45": "Farming, Fishing, and Forestry", "47": "Construction and Extraction", "49": "Installation, Maintenance, and Repair",
    "51": "Production", "53": "Transportation and Material Moving", "55": "Military Specific",
}


def norm_title(t):
    t = (t or "").lower().replace("&", " and ")
    t = re.sub(r"\(.*?\)|\[.*?\]", " ", t)
    t = CUT.split(t, maxsplit=1)[0]
    t = MODE.sub(" ", t)
    t = re.sub(r"[^a-z0-9+#.' -]", " ", t)
    t = re.sub(r"\s+", " ", t).strip(" .-'")
    words = t.split()
    while words and words[0] in LEVEL_EDGE:
        words.pop(0)
    while words and words[-1] in LEVEL_EDGE:
        words.pop()
    return " ".join(words)


class TitleMap:
    def __init__(self, path):
        self.map = {}
        for r in csv.DictReader(open(path), delimiter="\t"):
            if r["status"] in ("unique", "rolled-up", "decided") and r["soc"] not in ("", "-"):
                self.map[r["title_norm"]] = r["soc"]

    def assign(self, title):
        """Returns O*NET-SOC 8-digit code or None."""
        return self.assign_with_method(title)[0]

    extra = {}

    def assign_with_method(self, title):
        """Exact normalised title first; else the longest trailing phrase of at least two words that the map knows
        ('payments software engineer' -> 'software engineer'), because English job titles put the head noun last;
        else the same two steps against the LCA title dictionary (employers' own filed title/SOC pairs)."""
        t = norm_title(title)
        words = t.split()
        for table, name in ((self.map, "title"), (self.extra, "title-lca-dictionary")):
            if t in table:
                return table[t], name + ("-exact" if name == "title" else "")
            for i in range(1, len(words) - 1):
                tail = " ".join(words[i:])
                if tail in table:
                    return table[tail], name + ("-suffix" if name == "title" else "")
        return None, None


def lca_title_dictionary(rows, min_filings=5, min_employers=3, min_agreement=0.7):
    """normalised JOB_TITLE -> O*NET-SOC (6-digit + '.00') when employers agree. rows: dicts with JOB_TITLE, SOC_CODE,
    EMPLOYER_NAME."""
    from collections import Counter, defaultdict
    socs, emps = defaultdict(Counter), defaultdict(set)
    for r in rows:
        t, s = norm_title(r.get("JOB_TITLE")), (r.get("SOC_CODE") or "")[:7]
        if t and re.match(r"^\d{2}-\d{4}$", s):
            socs[t][s] += 1
            emps[t].add(r.get("EMPLOYER_NAME"))
    out = {}
    for t, c in socs.items():
        n = sum(c.values())
        top, k = c.most_common(1)[0]
        if n >= min_filings and len(emps[t]) >= min_employers and k / n >= min_agreement:
            out[t] = top + ".00"
    return out


def soc6(onet_code):
    return onet_code[:7] if onet_code else None


def major(onet_code):
    return (onet_code[:2] + "-0000") if onet_code else "unassigned"


def major_title(code):
    return MAJOR_GROUPS.get(code[:2], "Unassigned") if code != "unassigned" else "Unassigned (title not matched to one occupation)"
