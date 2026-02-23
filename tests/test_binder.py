import unittest

from app.binder import parse_hotkey, normalize_hotkey


class BinderHotkeyTests(unittest.TestCase):
    def test_parse_single_key_end(self):
        modifiers, key_vk, normalized = parse_hotkey("End")

        self.assertEqual(modifiers, 0)
        self.assertEqual(key_vk, 0x23)
        self.assertEqual(normalized, "End")

    def test_normalize_mixed_case_single_key(self):
        self.assertEqual(normalize_hotkey("eNd"), "End")

    def test_parse_numpad_digit(self):
        modifiers, key_vk, normalized = parse_hotkey("Num1")

        self.assertEqual(modifiers, 0)
        self.assertEqual(key_vk, 0x61)
        self.assertEqual(normalized, "Num1")

    def test_parse_ctrl_numpad_plus(self):
        modifiers, key_vk, normalized = parse_hotkey("Ctrl+NumPlus")

        self.assertEqual(modifiers, 0x0002)
        self.assertEqual(key_vk, 0x6B)
        self.assertEqual(normalized, "Ctrl+NumPlus")


if __name__ == "__main__":
    unittest.main()
