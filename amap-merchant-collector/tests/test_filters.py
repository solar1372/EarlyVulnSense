import unittest

from amap_collector.filters import extract_landlines, filter_record, has_landline


class LandlineFilterTests(unittest.TestCase):
    def test_extract_chengdu_landline(self):
        self.assertEqual(extract_landlines("028-85551234"), ["028-85551234"])
        self.assertEqual(extract_landlines("02885551234"), ["028-85551234"])
        self.assertEqual(extract_landlines("(028)85551234"), ["028-85551234"])

    def test_reject_mobile(self):
        self.assertEqual(extract_landlines("13812345678"), [])
        self.assertFalse(has_landline("13900001111"))

    def test_mixed_keep_landline_only(self):
        raw = "13812345678;028-86661234"
        self.assertEqual(extract_landlines(raw), ["028-86661234"])
        rec = filter_record(
            {"name": "某五金店", "tel": raw},
            landline_only=True,
        )
        self.assertIsNotNone(rec)
        self.assertEqual(rec["tel"], "028-86661234")
        self.assertEqual(rec["tel_raw"], raw)

    def test_exclude_nippon(self):
        rec = filter_record(
            {"name": "立邦涂料专卖店", "tel": "028-85551234"},
            landline_only=True,
        )
        self.assertIsNone(rec)

    def test_drop_without_landline(self):
        rec = filter_record(
            {"name": "家居城", "tel": "13800138000"},
            landline_only=True,
        )
        self.assertIsNone(rec)

    def test_hotline_not_landline(self):
        self.assertEqual(extract_landlines("400-800-1234"), [])


if __name__ == "__main__":
    unittest.main()
