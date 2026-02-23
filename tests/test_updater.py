import unittest

from app.updater import _is_newer


class UpdaterVersionTests(unittest.TestCase):
    def test_newer_patch(self):
        self.assertTrue(_is_newer("1.2.4", "1.2.3"))

    def test_newer_with_v_prefix(self):
        self.assertTrue(_is_newer("v1.3.0", "1.2.9"))

    def test_not_newer_same(self):
        self.assertFalse(_is_newer("1.2.3", "1.2.3"))

    def test_not_newer_lower(self):
        self.assertFalse(_is_newer("1.2.2", "1.2.3"))

    def test_invalid_remote(self):
        self.assertFalse(_is_newer("stable", "1.2.3"))


if __name__ == "__main__":
    unittest.main()
