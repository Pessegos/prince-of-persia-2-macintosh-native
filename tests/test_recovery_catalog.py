import unittest

from tools.recovery_catalog import (CATALOG, REVIEWS, catalog_rows, catalog_summary, catalog_text,
                                    ledger_citations, ledger_reviews)


class RecoveryCatalogTests(unittest.TestCase):
    def test_reviews_are_attached_to_real_original_symbols(self):
        rows = catalog_rows()
        keys = {(int(row["segment"]), row["name"]) for row in rows}
        self.assertLessEqual(set(REVIEWS), keys)
        self.assertEqual(len(rows), 1198)

    def test_unreviewed_symbols_are_not_marked_as_implemented(self):
        rows = catalog_rows()
        cited = ledger_reviews(rows)
        for row in rows:
            key = (int(row["segment"]), row["name"])
            if key in cited and key not in REVIEWS:
                self.assertEqual(row["review_status"], "partial")
                self.assertTrue(row["review_scope"].startswith("Branch ledger rows"))
            elif key not in REVIEWS:
                self.assertEqual(row["review_status"], "indexed-only")
                self.assertEqual(row["prototype_owner"], "")
            self.assertNotIn(row["review_status"], ("complete", "verified", "100%"))

    def test_ledger_citations_follow_a_segment_across_its_offsets(self):
        self.assertEqual(ledger_citations("9:16fe, 09ca, 0a42-0a9c; 6:424c"),
                         [(9, 0x16fe, 0x16fe), (9, 0x09ca, 0x09ca), (9, 0x0a42, 0x0a9c),
                          (6, 0x424c, 0x424c)])
        # Prose of hex letters is not an offset; CODE before a name still counts.
        self.assertEqual(ledger_citations("4:2bae and face; CheckBarr4:4e34/4f7c-4fb4"),
                         [(4, 0x2bae, 0x2bae), (4, 0x4e34, 0x4e34), (4, 0x4f7c, 0x4fb4)])

    def test_a_citation_counts_only_inside_a_marker_region(self):
        rows = [{"segment": "9", "name": name, "body_offset": body, "marker_offset": marker}
                for name, body, marker in (("JaffarGoToPos3", "0x136e", "0x14b6"),
                                           ("JaffarUpdateOppInfo", "0x185a", "0x193c"))]
        # 9:16fe lies between the two regions (an unnamed controller): neither
        # routine takes it, as the earlier next-routine ranges would have.
        self.assertEqual(ledger_reviews(rows, [("path", [(9, 0x16fe, 0x16fe)], [])]), {})
        found = ledger_reviews(rows, [("path", [(9, 0x16fe, 0x16fe), (9, 0x185a, 0x185a)],
                                       ["pop2/final_path.py"])])
        self.assertEqual(found, {(9, "JaffarUpdateOppInfo"): (["path"], ["pop2/final_path.py"])})

    def test_generated_catalog_is_current(self):
        self.assertEqual(CATALOG.read_text(encoding="utf-8"), catalog_text(catalog_rows()))

    def test_summary_counts_reviews_without_claiming_a_rule_total(self):
        summary = catalog_summary(catalog_rows())
        self.assertEqual(summary['routine_markers'], 1198)
        self.assertEqual(sum(summary[key] for key in ('partial', 'reference-only', 'indexed-only')), 1198)
        self.assertGreater(summary['partial'], 0)
        self.assertNotIn('complete', summary)
        self.assertEqual(catalog_summary([]), {'routine_markers': 0, 'partial': 0,
                                             'reference-only': 0, 'indexed-only': 0})


if __name__ == "__main__":
    unittest.main()
