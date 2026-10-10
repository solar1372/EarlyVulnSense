import unittest
from unittest.mock import MagicMock

from amap_collector.collector import MerchantCollector
from amap_collector.normalize import normalize_poi, records_to_rows


class NormalizeTests(unittest.TestCase):
    def test_normalize_basic(self):
        poi = {
            "id": "B000A8UIN8",
            "name": "测试火锅",
            "type": "餐饮服务;中餐厅;火锅店",
            "typecode": "050117",
            "address": "测试路1号",
            "pname": "北京市",
            "cityname": "北京市",
            "adname": "东城区",
            "location": "116.1,39.9",
            "tel": "010-12345678",
            "biz_ext": {"rating": "4.5", "cost": "80"},
            "photos": [{"url": "https://example.com/a.jpg"}],
        }
        rec = normalize_poi(poi, source="text")
        self.assertEqual(rec["id"], "B000A8UIN8")
        self.assertEqual(rec["lng"], "116.1")
        self.assertEqual(rec["lat"], "39.9")
        self.assertEqual(rec["rating"], "4.5")
        self.assertIn("example.com", rec["photos"])
        rows = records_to_rows([rec])
        self.assertEqual(rows[0]["name"], "测试火锅")


class CollectorTests(unittest.TestCase):
    def test_paginate_and_dedupe(self):
        client = MagicMock()
        # page_size=1 才能触发翻页；第 2 页补全 A1 的 tel
        client.place_text.side_effect = [
            {
                "status": "1",
                "count": "2",
                "pois": [
                    {
                        "id": "A1",
                        "name": "店1",
                        "location": "1,2",
                        "address": "a",
                    },
                ],
            },
            {
                "status": "1",
                "count": "2",
                "pois": [
                    {
                        "id": "A2",
                        "name": "店2",
                        "location": "3,4",
                        "address": "b",
                        "tel": "028-85551234",
                    }
                ],
            },
            {
                "status": "1",
                "count": "2",
                "pois": [
                    {
                        "id": "A2",
                        "name": "店2",
                        "location": "3,4",
                        "address": "b",
                        "tel": "028-85551234",
                    }
                ],
            },
        ]
        collector = MerchantCollector(client=client, page_size=1, max_pages=5)
        collector.collect_by_keyword(keywords="火锅", city="北京")
        self.assertEqual(len(collector.records), 2)
        by_id = {r["id"]: r for r in collector.records}
        self.assertEqual(by_id["A2"]["tel"], "028-85551234")
        self.assertEqual(client.place_text.call_count, 3)


if __name__ == "__main__":
    unittest.main()
