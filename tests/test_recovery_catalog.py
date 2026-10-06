import unittest

from tools.recovery_catalog import CATALOG, REVIEWS, catalog_rows, catalog_text


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


if __name__ == "__main__":
    unittest.main()
