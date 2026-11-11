import unittest
from app.services import c_bridge


class CBridgeTests(unittest.TestCase):
    def test_python_fallback_ordering_is_explicitly_available(self):
        rows=[{"id":1,"amount_paise":100,"category_id":2,"type":"expense"},{"id":2,"amount_paise":300,"category_id":1,"type":"expense"}]
        path="missing-smartspend.dll"
        self.assertEqual([r["id"] for r in c_bridge.rank_expenses(path,rows)],[2,1])
        self.assertEqual([r["id"] for r in c_bridge.cooling_order(path,rows)],[1,2])
        self.assertEqual(c_bridge.transaction_list_count(path,rows),2)
        self.assertEqual(c_bridge.category_totals(path,rows,[1,2]),{1:300,2:100})
        self.assertEqual(c_bridge.binary_search(path,sorted(rows,key=lambda r:r["id"]),2)["id"],2)

    def test_binary_search_rejects_unsorted_data(self):
        with self.assertRaises(ValueError):c_bridge.binary_search("missing-smartspend.dll",[{"id":2},{"id":1}],1)


if __name__=="__main__":unittest.main()
