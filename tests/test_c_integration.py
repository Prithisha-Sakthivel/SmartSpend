import unittest
from pathlib import Path
from app.services import c_bridge


class CompiledCIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dll=str(Path(__file__).resolve().parents[1]/"c_core"/"build"/"smartspend.dll")
        if not c_bridge.available(cls.dll):raise unittest.SkipTest("Build the DLL with build_c.bat to run ctypes integration tests.")

    def test_required_operations_through_ctypes(self):
        rows=[{"id":3,"amount_paise":500,"category_id":2,"type":"expense"},{"id":1,"amount_paise":500,"category_id":1,"type":"income"},{"id":2,"amount_paise":1200,"category_id":2,"type":"expense"}]
        self.assertEqual(c_bridge.transaction_list_count(self.dll,rows),3)
        self.assertEqual([r["id"] for r in c_bridge.rank_expenses(self.dll,rows)],[2,1,3])
        self.assertEqual(c_bridge.category_totals(self.dll,[rows[0],rows[2]],[1,2]),{1:0,2:1700})
        self.assertEqual(c_bridge.binary_search(self.dll,sorted(rows,key=lambda r:r["id"]),3)["id"],3)
        self.assertEqual(c_bridge.newest_undo_id(self.dll,[10,11,12]),12)
        self.assertEqual([r["id"] for r in c_bridge.cooling_order(self.dll,rows)],[3,1,2])


if __name__=="__main__":unittest.main()
