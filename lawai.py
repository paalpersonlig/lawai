"""Rank evidence for the Norwegian Lawai interview case."""

import argparse
import json
import re
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

REFERENCE_DATE = date(2026, 11, 11)
CASE_FILE = Path(__file__).with_name("case.json")
MONTHS = dict(zip(
    "januar februar mars april mai juni juli august september oktober november desember".split(),
    range(1, 13),
))
MONTH = "|".join(MONTHS)
FULL_DATE = rf"(\d{{1,2}})\.\s*({MONTH})\s+(\d{{4}})"
EFFECTIVE_DATE = re.compile(rf"\bmed virkning fra\s+{FULL_DATE}\b")
RATE_CHANGE = re.compile(r"økes fra kr ([\d]+,\d{2}) til kr ([\d]+,\d{2})")
HANDBOOK_REPLACEMENT = re.compile(rf"erstatter håndboka fra ({MONTH}) (\d{{4}})\b")

CURATED = {
    "D2": (date(2025, 4, 1), "D1"),
    "D3": (date(2026, 5, 1), "D2"),
    "D7": (None, "D6"),
}


@dataclass(frozen=True)
class Passage:
    document_id: str
    title: str
    kind: str
    document_date: Optional[date]
    rule: str
    section: Optional[str]
    value: str
    text: str
    verified_replaces: Optional[str] = None


@dataclass(frozen=True)
class Version:
    passage: Passage
    effective_from: Optional[date]
    date_basis: str
    replaces: Optional[str] = None
    issue: Optional[str] = None


def load_case(path=CASE_FILE):
    documents = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        Passage(
            document_id=document["id"], title=document["title"],
            kind=document["kind"],
            document_date=date.fromisoformat(document["document_date"])
            if document["document_date"] else None,
            **passage,
        )
        for document in documents
        for passage in document["passages"]
    ]


def norwegian_date(match):
    day, month, year = match.groups()
    return date(int(year), MONTHS[month], int(day))


def resolve_predecessor(passage, effective_from, candidates, effective_dates):
    if passage.verified_replaces:
        targets = [item for item in candidates if item.document_id == passage.verified_replaces]
        if len(targets) == 1:
            return passage.verified_replaces, None
        return None, "Fant ikke den registrerte kilden som erstattes."
    text = passage.text.casefold()
    rate = RATE_CHANGE.search(text)
    handbook = HANDBOOK_REPLACEMENT.search(text)
    if passage.kind == "amendment":
        if not rate or rate[2] != passage.value or not EFFECTIVE_DATE.search(text):
            return None, "Kunne ikke lese satsendringen og virkningsdatoen."
        candidates = [
            item for item in candidates
            if item.section == passage.section
            and item.kind in {"agreement", "amendment"}
            and effective_dates[item]
            and effective_dates[item] < effective_from
        ]
        if candidates:
            latest_start = max(effective_dates[item] for item in candidates)
            candidates = [
                item for item in candidates
                if effective_dates[item] == latest_start and item.value == rate[1]
            ]
    elif handbook:
        month, year = MONTHS[handbook[1]], int(handbook[2])
        candidates = [
            item for item in candidates
            if item.kind == "handbook" and item.title == passage.title
            and item.document_date
            and (item.document_date.year, item.document_date.month) == (year, month)
        ]
    elif "erstatter" in text:
        return None, "Kunne ikke lese hvilken kilde som erstattes."
    else:
        return None, None

    if len(candidates) != 1:
        return None, "Fant ikke én entydig kilde som erstattes."
    return candidates[0].document_id, None


def build_versions(corpus, *, curated=False):
    corpus = tuple(corpus)
    versions = []
    dates = {}
    bases = {}
    date_issues = {}
    for passage in corpus:
        override, _ = CURATED.get(passage.document_id, (None, None))
        match = EFFECTIVE_DATE.search(passage.text.casefold())
        try:
            explicit = override if curated else norwegian_date(match) if match else None
        except ValueError:
            explicit = None
            date_issues[passage] = "Virkningsdatoen i teksten er ugyldig."
        dates[passage] = explicit or passage.document_date
        if explicit:
            bases[passage] = "curated" if curated else "explicit"
        else:
            bases[passage] = "document_date" if passage.document_date else "unknown"

    for passage in corpus:
        candidates = [
            item for item in corpus
            if item.rule == passage.rule and item.document_id != passage.document_id
        ]
        if curated:
            _, replaces = CURATED.get(passage.document_id, (None, None))
            if passage.verified_replaces:
                replaces, issue = resolve_predecessor(passage, dates[passage], candidates, dates)
            else:
                issue = None
        else:
            replaces, issue = resolve_predecessor(passage, dates[passage], candidates, dates)
        versions.append(Version(
            passage, dates[passage], bases[passage], replaces,
            date_issues.get(passage, issue),
        ))
    return versions


def question_period(question, reference_date):
    text = question.casefold()
    exact_day = re.search(rf"\b(?:den|på)\s+{FULL_DATE}\b", text)
    month = re.search(rf"\bi\s+({MONTH})\s+(\d{{4}})\b", text)
    since = re.search(r"\bsiden\s+(\d{4})\b", text)
    unsupported = (
        rf"\b(?:{MONTH}|siden|før|etter|mellom|tidligere|fjor|måneden|året|"
        r"forrige|neste|var|hadde|gjaldt|\d{4})\b"
    )
    patterns = [(exact_day, "day"), (month, "month"), (since, "since")]
    matches = [(match, kind) for match, kind in patterns if match]
    if len(matches) > 1:
        raise ValueError
    if not matches:
        if re.search(unsupported, text):
            raise ValueError
        return reference_date, reference_date

    match, kind = matches[0]
    remaining_text = text[:match.start()] + text[match.end():]
    if re.search(r"\b(?:siden|før|etter|mellom|\d{4})\b", remaining_text):
        raise ValueError
    if kind == "day":
        day = norwegian_date(match)
        return day, day
    if kind == "month":
        month_number, year = MONTHS[match[1]], int(match[2])
        return date(year, month_number, 1), date(year, month_number, monthrange(year, month_number)[1])
    return date(int(match[1]), 1, 1), reference_date


def candidate_rules(question, versions):
    text = question.casefold()
    subjects = {
        "leave": r"\bvelferdspermisjon\w*",
        "overtime": r"\bovertid\w*",
        "unskilled": r"\buten fagbrev\b|\bufaglært\w*",
        "skilled": r"\bfagarbeider\w*|\bminstelønn\w*|\btimesats\w*",
    }
    matched = {subject for subject, pattern in subjects.items() if re.search(pattern, text)}
    if "unskilled" in matched and not re.search(r"\bfagarbeider\w*", text):
        matched.discard("skilled")
    industries = {
        industry for industry, keyword in (("bicycle", "sykkelverksted"), ("boat", "båtpleie"))
        if re.search(rf"\b{keyword}", text)
    }
    return sorted({
        version.passage.rule for version in versions
        if version.passage.rule.split(".")[1] in matched
        and (not industries or version.passage.rule.split(".")[0] in industries
             or version.passage.rule == "handbook.leave")
    })


def result(status, sources=(), **details):
    return {"status": status, "sources": list(sources), **details}


def source(version, end=None, reason="Kilden gjelder i den forespurte perioden."):
    passage = version.passage
    return {
        "document_id": passage.document_id,
        "title": passage.title,
        "source_type": passage.kind,
        "rule": passage.rule,
        "section": passage.section,
        "excerpt": passage.text,
        "document_date": passage.document_date.isoformat() if passage.document_date else None,
        "effective_from": version.effective_from.isoformat() if version.effective_from else None,
        "effective_through": end.isoformat() if end else None,
        "date_basis": version.date_basis,
        "replaces": version.replaces,
        "reason": reason,
    }


def rank_period(question, start, end, versions):
    rules = candidate_rules(question, versions)
    if not rules:
        return result("no_match", message="Fant ingen bestemmelse som passer spørsmålet.")
    if len(rules) > 1:
        return result("ambiguous_scope", candidates=rules,
                      message="Oppgi hvilken bransje eller bestemmelse du mener.")

    relevant = [version for version in versions if version.passage.rule == rules[0]]
    primary = [version for version in relevant if version.passage.kind != "secondary"]
    evidence = primary or relevant
    dated = sorted(
        (version for version in evidence if version.effective_from),
        key=lambda version: (version.effective_from, version.passage.document_id),
    )
    issues = [
        version for version in evidence if version.issue
        and (version.effective_from is None or version.effective_from <= end)
    ]
    if issues:
        return result("uncertain_timeline", [
            source(version, reason=version.issue) for version in issues
        ])
    undated = sorted(
        (version for version in evidence if version.effective_from is None),
        key=lambda version: version.passage.document_id,
    )
    if len(dated) == 1 and dated[0].effective_from <= start and dated[0].replaces:
        undated = [
            version for version in undated
            if version.passage.document_id != dated[0].replaces
        ]
    if not dated:
        replaced = {version.replaces for version in undated if version.replaces}
        remaining = [version for version in undated if version.passage.document_id not in replaced]
        if len(undated) == 2 and len(remaining) == 1:
            undated = remaining
    if len({version.passage.value for version in undated}) > 1:
        return result("conflict", [
            source(version, reason="Udatert kilde med avvikende opplysning.")
            for version in undated
        ])
    if undated:
        return result("unknown_effective_date", [
            source(version, reason="Kan ikke fastslå når kilden gjelder.")
            for version in undated
        ])

    selected = []
    for index, version in enumerate(dated):
        successor = dated[index + 1] if index + 1 < len(dated) else None
        if version.effective_from > end:
            break
        if successor and successor.replaces != version.passage.document_id:
            if successor.effective_from <= end:
                return result("uncertain_timeline", [
                    source(item, reason="Kildene mangler en bekreftet erstatningslenke.")
                    for item in (version, successor)
                ])
            successor = None
        through = successor.effective_from - timedelta(days=1) if successor else None
        if through is None or (through >= start and through >= version.effective_from):
            selected.append(source(version, through))
    if not selected:
        return result("no_applicable_source", message="Fant ingen kilde for perioden.")
    return result("ok", selected, requested_from=start.isoformat(), requested_through=end.isoformat())


def rank_sources(question, reference_date, corpus, *, curated=False):
    try:
        start, end = question_period(question, reference_date)
        if start > end:
            raise ValueError
    except ValueError:
        return result("unsupported_time", message="Kunne ikke tolke tidsperioden i spørsmålet.")
    return rank_period(question, start, end, build_versions(corpus, curated=curated))


def conflict_case():
    return [
        Passage("U1", "Personalhåndbok A", "handbook", None, "handbook.leave",
                "7.2", "3 dager", "Ansatte har rett til inntil 3 dager velferdspermisjon."),
        Passage("U2", "Personalhåndbok B", "handbook", None, "handbook.leave",
                "7.2", "5 dager", "Ansatte har rett til inntil 5 dager velferdspermisjon."),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", nargs="?", help="Spørsmål på norsk")
    parser.add_argument("--reference-date", type=date.fromisoformat, default=REFERENCE_DATE)
    parser.add_argument("--curated", action="store_true", help="Bruk håndregistrerte lenker og datoer")
    parser.add_argument("--conflict-demo", action="store_true", help="Vis to motstridende, udaterte kilder")
    args = parser.parse_args()
    if not args.question and not args.conflict_demo:
        parser.error("oppgi et spørsmål eller bruk --conflict-demo")
    corpus = conflict_case() if args.conflict_demo else load_case()
    question = args.question or "Hvor mange dager velferdspermisjon har jeg?"
    response = rank_sources(question, args.reference_date, corpus, curated=args.curated)
    print(json.dumps(response, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
