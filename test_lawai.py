import unittest
from dataclasses import replace
from datetime import date

from lawai import (
    REFERENCE_DATE, build_versions, conflict_case, load_case, rank_period, rank_sources,
)


QUESTIONS = [
    ("Hva er minstelønnen for en fagarbeider på sykkelverksted?",
     REFERENCE_DATE, REFERENCE_DATE, ["D3"]),
    ("Hva var minstelønnen for en fagarbeider på sykkelverksted i februar 2026?",
     date(2026, 2, 1), date(2026, 2, 28), ["D2"]),
    ("Hvor mange dager velferdspermisjon har jeg?",
     REFERENCE_DATE, REFERENCE_DATE, ["D7"]),
    ("Hva er minstelønnen for en fagarbeider i båtpleie?",
     REFERENCE_DATE, REFERENCE_DATE, ["D5"]),
    ("Hvordan har minstelønnen for fagarbeidere på sykkelverksted endret seg siden 2024?",
     date(2024, 1, 1), REFERENCE_DATE, ["D1", "D2", "D3"]),
]


class RankingTests(unittest.TestCase):
    def setUp(self):
        self.corpus = load_case()

    def assert_sources(self, response, expected):
        self.assertEqual(response["status"], "ok", response)
        self.assertEqual([entry["document_id"] for entry in response["sources"]], expected)

    def test_curated_case_with_explicit_dates(self):
        versions = build_versions(self.corpus, curated=True)
        for question, start, end, expected in QUESTIONS:
            with self.subTest(question=question):
                self.assert_sources(rank_period(question, start, end, versions), expected)

    def test_five_original_questions(self):
        for question, _, _, expected in QUESTIONS:
            with self.subTest(question=question):
                self.assert_sources(rank_sources(question, REFERENCE_DATE, self.corpus), expected)

    def test_extraction_matches_curated_dates_and_links(self):
        extracted = build_versions(self.corpus)
        curated = build_versions(self.corpus, curated=True)
        self.assertTrue(all(version.issue is None for version in extracted))
        self.assertEqual(
            [(version.effective_from, version.replaces) for version in extracted],
            [(version.effective_from, version.replaces) for version in curated],
        )

    def test_retroactive_amendment_boundary(self):
        question = QUESTIONS[0][0]
        for requested_date, expected in [("30. april 2026", "D2"), ("1. mai 2026", "D3")]:
            with self.subTest(requested_date=requested_date):
                response = rank_sources(f"{question.rstrip('?')} den {requested_date}?",
                                        REFERENCE_DATE, self.corpus)
                self.assert_sources(response, [expected])
        response = rank_sources(question, REFERENCE_DATE, self.corpus)
        self.assertEqual(response["sources"][0]["document_date"], "2026-06-12")
        self.assertEqual(response["sources"][0]["effective_from"], "2026-05-01")

    def test_mid_month_amendment_returns_both_intervals(self):
        corpus = [
            replace(passage, text=passage.text.replace("1. mai 2026", "15. mai 2026"))
            if passage.document_id == "D3" else passage for passage in self.corpus
        ]
        response = rank_sources("Minstelønn på sykkelverksted i mai 2026?", REFERENCE_DATE, corpus)
        self.assert_sources(response, ["D2", "D3"])
        self.assertEqual(response["sources"][0]["effective_through"], "2026-05-14")
        self.assertEqual(response["sources"][1]["effective_from"], "2026-05-15")

    def test_other_provisions_survive_partial_amendment(self):
        for question, section in [
            ("Hva er tillegget for overtid på sykkelverksted?", "4"),
            ("Hva er minstelønnen uten fagbrev på sykkelverksted?", "3"),
        ]:
            with self.subTest(question=question):
                response = rank_sources(question, REFERENCE_DATE, self.corpus)
                self.assert_sources(response, ["D1"])
                self.assertEqual(response["sources"][0]["section"], section)

    def test_ambiguous_industry(self):
        response = rank_sources("Hva er minstelønnen for en fagarbeider?",
                                REFERENCE_DATE, self.corpus)
        self.assertEqual(response["status"], "ambiguous_scope")
        self.assertEqual(response["candidates"], ["bicycle.skilled", "boat.skilled"])

    def test_ambiguous_handbook_replacement(self):
        original = next(passage for passage in self.corpus if passage.document_id == "D6")
        corpus = self.corpus + [replace(original, document_id="D6b", document_date=date(2023, 1, 20))]
        response = rank_sources(QUESTIONS[2][0], REFERENCE_DATE, corpus)
        self.assertEqual(response["status"], "uncertain_timeline")
        self.assertEqual(response["sources"][0]["document_id"], "D7")

    def test_unresolved_undated_conflict_in_stable_order(self):
        response = rank_sources(QUESTIONS[2][0], REFERENCE_DATE, reversed(conflict_case()))
        self.assertEqual(response["status"], "conflict")
        self.assertEqual([entry["document_id"] for entry in response["sources"]], ["U1", "U2"])

    def test_verified_dated_successor_resolves_conflict(self):
        earlier, later = conflict_case()
        later = replace(later, document_date=date(2025, 8, 1), verified_replaces="U1")
        self.assert_sources(rank_sources(QUESTIONS[2][0], REFERENCE_DATE, [earlier, later]), ["U2"])

    def test_undated_successor_does_not_establish_an_effective_date(self):
        earlier, later = conflict_case()
        later = replace(later, verified_replaces="U1")
        response = rank_sources(QUESTIONS[2][0], REFERENCE_DATE, [earlier, later])
        self.assertEqual(response["status"], "unknown_effective_date")
        self.assertEqual([entry["document_id"] for entry in response["sources"]], ["U2"])

    def test_unsupported_or_invalid_time(self):
        for suffix in ("i fjor", "i februar", "før i februar 2026", "den 30. februar 2026", "siden 2027"):
            with self.subTest(suffix=suffix):
                response = rank_sources(f"Minstelønn på sykkelverksted {suffix}?",
                                        REFERENCE_DATE, self.corpus)
                self.assertEqual(response["status"], "unsupported_time")


if __name__ == "__main__":
    unittest.main()
