import unittest

from tools.recovery_catalog import CATALOG, REVIEWS, catalog_rows, catalog_summary, catalog_text


class RecoveryCatalogTests(unittest.TestCase):
    def test_reviews_are_attached_to_real_original_symbols(self):
        rows = catalog_rows()
        keys = {(int(row["segment"]), row["name"]) for row in rows}
        self.assertLessEqual(set(REVIEWS), keys)
        self.assertEqual(len(rows), 1198)

    def test_unreviewed_symbols_are_not_marked_as_implemented(self):
        for row in catalog_rows():
            if (int(row["segment"]), row["name"]) not in REVIEWS:
                self.assertEqual(row["review_status"], "indexed-only")
                self.assertEqual(row["prototype_owner"], "")
            self.assertNotIn(row["review_status"], ("complete", "verified", "100%"))

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
