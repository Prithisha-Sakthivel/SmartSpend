import csv
import io
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app import create_app
from app.db import get_db
from app.services.money import safe_to_spend, runway, rupees


class SmartSpendTests(unittest.TestCase):
    def test_rupees_uses_integer_paise_and_indian_grouping(self):
        self.assertEqual(rupees(123456789),"₹12,34,567.89")
        self.assertEqual(rupees(-50),"-₹0.50")

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.app=create_app({"TESTING":True,"DEBUG":True,"SECRET_KEY":"test-secret","DATABASE":str(Path(self.tmp.name)/"db.sqlite3"),"UPLOAD_DIR":str(Path(self.tmp.name)/"avatars"),"C_LIBRARY":str(Path(self.tmp.name)/"missing.dll")})
        self.client=self.app.test_client()
        self._register("one@example.test")

    def tearDown(self):self.tmp.cleanup()

    def token(self):
        response=self.client.get("/transactions") if self.client.get_cookie("session") else self.client.get("/login")
        html=response.get_data(as_text=True)
        import re
        match=re.search(r'name="csrf_token" value="([^"]+)',html)
        self.assertIsNotNone(match)
        return match.group(1)

    def post(self,path,data):
        data=dict(data);data["csrf_token"]=self.token()
        return self.client.post(path,data=data,follow_redirects=True)

    def _register(self,email):
        self.client.get("/register")
        import re
        html=self.client.get("/register").get_data(as_text=True)
        token=re.search(r'name="csrf_token" value="([^"]+)',html).group(1)
        response=self.client.post("/register",data={"csrf_token":token,"display_name":"Test User","email":email,"password":"test-password-123"},follow_redirects=True)
        self.assertEqual(response.status_code,200)

    def test_all_authenticated_pages_render(self):
        for path in ["/dashboard","/transactions","/commitments","/budgets","/purchases","/cooling-off","/goals","/challenges","/insights","/reports","/settings","/runway"]:
            with self.subTest(path=path):self.assertEqual(self.client.get(path).status_code,200)

    def test_insights_uses_global_paise_currency_formatter(self):
        for day in range(5):
            self.post("/transactions",{"type":"expense","description":f"Snack {day}","amount":"50.00","occurred_on":date.today().isoformat()})
        response=self.client.get("/insights")
        self.assertEqual(response.status_code,200)
        self.assertIn("₹250.00".encode(),response.data)

    def test_chart_pages_render_user_scoped_database_series(self):
        today_s=date.today().isoformat()
        with self.app.app_context():
            db=get_db();uid=db.execute("SELECT id FROM users WHERE email='one@example.test'").fetchone()[0]
            food=db.execute("SELECT id FROM categories WHERE user_id=? AND name='Food'",(uid,)).fetchone()[0]
            db.execute("INSERT INTO transactions(user_id,type,amount_paise,description,category_id,occurred_on) VALUES(?,?,?,?,?,?)",(uid,'income',100000,'Pay',None,today_s))
            db.execute("INSERT INTO transactions(user_id,type,amount_paise,description,category_id,occurred_on) VALUES(?,?,?,?,?,?)",(uid,'expense',25000,'Groceries',food,today_s))
            goal=db.execute("INSERT INTO savings_goals(user_id,name,target_paise) VALUES(?,?,?)",(uid,'Emergency fund',100000)).lastrowid
            db.execute("INSERT INTO goal_contributions(user_id,goal_id,amount_paise,contributed_on) VALUES(?,?,?,?)",(uid,goal,50000,today_s));db.commit()
        dashboard=self.client.get('/dashboard').get_data(as_text=True)
        insights=self.client.get('/insights').get_data(as_text=True)
        reports=self.client.get('/reports').get_data(as_text=True)
        self.assertIn('dashboardCashflow',dashboard);self.assertIn('100000',dashboard);self.assertIn('25000',dashboard)
        self.assertIn('insightsCategories',insights);self.assertIn('25000',insights)
        self.assertIn('reportCashflow',reports);self.assertIn('reportSavings',reports);self.assertIn('50000',reports)

    def test_transaction_crud_and_persisted_undo(self):
        response=self.post("/transactions",{"type":"expense","description":"Coffee","amount":"4.50","occurred_on":date.today().isoformat()})
        self.assertIn(b"Transaction added",response.data)
        with self.app.app_context():
            db=get_db();row=db.execute("SELECT * FROM transactions WHERE description='Coffee'").fetchone();self.assertEqual(row["amount_paise"],450)
        response=self.post("/transactions/undo",{})
        with self.app.app_context():self.assertEqual(get_db().execute("SELECT COUNT(*) FROM transactions WHERE description='Coffee'").fetchone()[0],0)

    def test_csrf_rejects_mutation(self):
        self.assertEqual(self.client.post("/transactions",data={"description":"x"}).status_code,400)

    def test_safe_to_spend_edges(self):
        with self.app.app_context():
            db=get_db();uid=db.execute("SELECT id FROM users WHERE email='one@example.test'").fetchone()[0]
            pref=db.execute("SELECT * FROM user_settings WHERE user_id=?",(uid,)).fetchone();self.assertEqual(pref["default_buffer_paise"],0)
            db.execute("UPDATE user_settings SET available_balance_paise=100000,balance_as_of_date=? WHERE user_id=?",(date.today().isoformat(),uid))
            db.execute("INSERT INTO scheduled_commitments(user_id,kind,description,amount_paise,due_on) VALUES(?,?,?,?,?)",(uid,"bill","Rent",25000,date.today().isoformat()))
            db.execute("INSERT INTO scheduled_commitments(user_id,kind,description,amount_paise,due_on) VALUES(?,?,?,?,?)",(uid,"income","Pay",50000,(date.today()+timedelta(days=1)).isoformat()))
            pref=db.execute("SELECT * FROM user_settings WHERE user_id=?",(uid,)).fetchone();result=safe_to_spend(db,uid,pref,date.today())
            self.assertEqual(result["amount"],125000)
            db.execute("UPDATE user_settings SET available_balance_paise=NULL,balance_as_of_date=NULL WHERE user_id=?",(uid,))
            pref=db.execute("SELECT * FROM user_settings WHERE user_id=?",(uid,)).fetchone();self.assertFalse(safe_to_spend(db,uid,pref,date.today())["available"])

    def test_safe_to_spend_deducts_scoped_commitments_buffer_and_post_snapshot_activity(self):
        today=date.today();end=today+timedelta(days=29);next_day=today+timedelta(days=1)
        with self.app.app_context():
            db=get_db();uid=db.execute("SELECT id FROM users WHERE email='one@example.test'").fetchone()[0]
            db.execute("UPDATE user_settings SET available_balance_paise=12000000,balance_as_of_date=?,default_buffer_paise=300000,planning_horizon_days=30 WHERE user_id=?",(today.isoformat(),uid))
            # The snapshot already reflects transactions on its as-of date. Only later-dated ledger activity adjusts it.
            db.execute("INSERT INTO transactions(user_id,type,amount_paise,description,occurred_on) VALUES(?,?,?,?,?)",(uid,"expense",80000,"Included in opening snapshot",today.isoformat()))
            db.execute("INSERT INTO transactions(user_id,type,amount_paise,description,occurred_on) VALUES(?,?,?,?,?)",(uid,"expense",100000,"After opening snapshot",next_day.isoformat()))
            def add_commitment(owner,kind,amount,due,status="scheduled",description="Test commitment"):
                db.execute("INSERT INTO scheduled_commitments(user_id,kind,description,amount_paise,due_on,status) VALUES(?,?,?,?,?,?)",(owner,kind,description,amount,due.isoformat(),status))
            add_commitment(uid,"bill",250000,today)
            add_commitment(uid,"savings",100000,end)
            add_commitment(uid,"income",500000,end)
            add_commitment(uid,"bill",9900000,end+timedelta(days=1),description="Beyond horizon")
            add_commitment(uid,"bill",9900000,today-timedelta(days=1),description="Past due")
            add_commitment(uid,"bill",9900000,today,status="cancelled",description="Cancelled")
            add_commitment(uid,"savings",9900000,today,status="completed",description="Already completed")
            other_id=db.execute("INSERT INTO users(email,password_hash,display_name) VALUES(?,?,?)",("other@example.test","unused-test-hash","Other User")).lastrowid
            add_commitment(other_id,"bill",9900000,today,description="Another user's bill")
            db.commit()
            pref=db.execute("SELECT * FROM user_settings WHERE user_id=?",(uid,)).fetchone()
            result=safe_to_spend(db,uid,pref,today)
            self.assertEqual(result["funds"],11900000)
            self.assertEqual(result["income"],500000)
            self.assertEqual(result["bills"],250000)
            self.assertEqual(result["savings"],100000)
            self.assertEqual(result["buffer"],300000)
            self.assertEqual(result["amount"],11750000)
            self.assertEqual(result["start"],today.isoformat())
            self.assertEqual(result["end"],end.isoformat())

    def test_dashboard_shows_equal_balance_when_no_safe_to_spend_deductions_exist(self):
        with self.app.app_context():
            db=get_db();uid=db.execute("SELECT id FROM users WHERE email='one@example.test'").fetchone()[0]
            db.execute("UPDATE user_settings SET available_balance_paise=12000000,balance_as_of_date=?,default_buffer_paise=0,planning_horizon_days=30 WHERE user_id=?",(date.today().isoformat(),uid));db.commit()
            pref=db.execute("SELECT * FROM user_settings WHERE user_id=?",(uid,)).fetchone()
            result=safe_to_spend(db,uid,pref,date.today())
            self.assertEqual(result["amount"],12000000)
        page=self.client.get("/dashboard")
        self.assertEqual(page.status_code,200)
        self.assertRegex(page.get_data(as_text=True),r'<div class="balance-number">₹1,20,000\.00</div>')
        self.assertRegex(page.get_data(as_text=True),r'<div class="safe-number">₹1,20,000\.00</div>')

    def test_csv_formula_injection_is_neutralized(self):
        self.post("/transactions",{"type":"expense","description":"=1+1","amount":"12.00","occurred_on":date.today().isoformat()})
        response=self.client.get("/reports.csv")
        self.assertEqual(response.status_code,200)
        self.assertIn(b"'=1+1",response.data)

    def test_user_isolation(self):
        self.post("/transactions",{"type":"expense","description":"Private purchase","amount":"19.00","occurred_on":date.today().isoformat()})
        self.client.post("/logout",data={"csrf_token":self.token()})
        self._register("two@example.test")
        self.assertNotIn(b"Private purchase",self.client.get("/transactions").data)

    def test_password_reset_link_is_single_use(self):
        page=self.client.get("/forgot-password");import re
        token=re.search(r'name="csrf_token" value="([^"]+)',page.get_data(as_text=True)).group(1)
        page=self.client.post("/forgot-password",data={"csrf_token":token,"email":"one@example.test"},follow_redirects=True)
        link=re.search(rb'href="(/reset-password/[^" ]+)',page.data)
        self.assertIsNotNone(link)
        path=link.group(1).decode()
        response=self.post(path,{"password":"different-password-456"})
        self.assertIn(b"Password updated",response.data)
        self.assertEqual(self.client.get(path).status_code,302)

    def test_edit_can_be_undone(self):
        self.post("/transactions",{"type":"expense","description":"Old name","amount":"10.00","occurred_on":date.today().isoformat()})
        with self.app.app_context():tid=get_db().execute("SELECT id FROM transactions WHERE description='Old name'").fetchone()[0]
        self.post(f"/transactions/{tid}/edit",{"type":"expense","description":"New name","amount":"18.00","occurred_on":date.today().isoformat()})
        self.post("/transactions/undo",{})
        with self.app.app_context():
            row=get_db().execute("SELECT description,amount_paise FROM transactions WHERE id=?",(tid,)).fetchone()
            self.assertEqual((row["description"],row["amount_paise"]),("Old name",1000))

    def test_balance_snapshot_and_runway_override(self):
        with self.app.app_context():
            db=get_db();uid=db.execute("SELECT id FROM users LIMIT 1").fetchone()[0]
            db.execute("UPDATE user_settings SET available_balance_paise=100000,balance_as_of_date=? WHERE user_id=?",(date.today().isoformat(),uid))
            pref=db.execute("SELECT * FROM user_settings WHERE user_id=?",(uid,)).fetchone()
            self.assertFalse(runway(db,uid,pref,date.today())["available"])
            result=runway(db,uid,pref,date.today(),5000)
            self.assertEqual(result["days"],20)

    def test_recurring_commitments_materialize_occurrences(self):
        response=self.post("/commitments",{"kind":"bill","description":"Rent","amount":"1000.00","due_on":date.today().isoformat(),"recurrence":"monthly"})
        self.assertIn(b"Commitment scheduled",response.data)
        with self.app.app_context():
            rows=get_db().execute("SELECT due_on FROM scheduled_commitments WHERE description='Rent' ORDER BY due_on").fetchall()
            self.assertGreaterEqual(len(rows),12)
            self.assertEqual(len({r["due_on"] for r in rows}),len(rows))

    def test_no_spend_progress_uses_explicit_checkins(self):
        today_s=date.today().isoformat();end=(date.today()+timedelta(days=2)).isoformat()
        with self.app.app_context():category=get_db().execute("SELECT id FROM categories WHERE name='Food' AND user_id=(SELECT id FROM users WHERE email='one@example.test')").fetchone()[0]
        response=self.post("/challenges",{"name":"Skip takeout","challenge_type":"no_spend","start_on":today_s,"end_on":end,"cadence":"daily","category_id":str(category)})
        self.assertIn(b"Challenge created",response.data)
        with self.app.app_context():cid=get_db().execute("SELECT id FROM savings_challenges WHERE name='Skip takeout'").fetchone()[0]
        response=self.post(f"/challenges/{cid}/checkin",{"check_on":today_s,"result":"met"})
        self.assertIn(b"No-spend check-in saved",response.data)
        with self.app.app_context():
            row=get_db().execute("SELECT COUNT(*) FROM challenge_checkins WHERE challenge_id=? AND result='met'",(cid,)).fetchone()
            self.assertEqual(row[0],1)

    def test_budget_and_goal_contribution_flows(self):
        with self.app.app_context():category=get_db().execute("SELECT id FROM categories WHERE name='Food' AND user_id=(SELECT id FROM users WHERE email='one@example.test')").fetchone()[0]
        response=self.post("/budgets",{"category_id":str(category),"limit":"250.00"})
        self.assertIn(b"Monthly budget saved",response.data)
        response=self.post("/goals",{"name":"Emergency fund","target":"5000.00","target_date":""})
        self.assertIn(b"Savings goal created",response.data)
        with self.app.app_context():gid=get_db().execute("SELECT id FROM savings_goals WHERE name='Emergency fund'").fetchone()[0]
        response=self.post(f"/goals/{gid}/contribute",{"amount":"125.50","contributed_on":date.today().isoformat()})
        self.assertIn(b"Contribution added",response.data)
        with self.app.app_context():self.assertEqual(get_db().execute("SELECT SUM(amount_paise) FROM goal_contributions WHERE goal_id=?",(gid,)).fetchone()[0],12550)
        report=self.client.get("/reports")
        self.assertIn(b"Emergency fund",report.data)
        self.assertIn(b"Category limits in this period",report.data)

    def test_purchase_cooling_queue_and_proceed(self):
        self.post("/settings",{"action":"finance","balance":"5000.00","balance_as_of":date.today().isoformat(),"buffer":"100.00","horizon":"30"})
        response=self.post("/purchases",{"description":"Desk lamp","amount":"34.00","action":"later"})
        self.assertIn(b"Added to your cooling-off list",response.data)
        with self.app.app_context():pid=get_db().execute("SELECT id FROM cooling_off_purchases WHERE description='Desk lamp'").fetchone()[0]
        response=self.post(f"/cooling-off/{pid}/proceed",{})
        self.assertIn(b"Cooling-off item updated",response.data)
        with self.app.app_context():
            row=get_db().execute("SELECT status,linked_transaction_id FROM cooling_off_purchases WHERE id=?",(pid,)).fetchone()
            self.assertEqual(row["status"],"proceeded");self.assertIsNotNone(row["linked_transaction_id"])
        self.post("/transactions/undo",{})
        with self.app.app_context():self.assertEqual(get_db().execute("SELECT status FROM cooling_off_purchases WHERE id=?",(pid,)).fetchone()[0],"pending")

    def test_undo_reopens_completed_scheduled_commitment(self):
        self.post("/commitments",{"kind":"bill","description":"Water bill","amount":"25.00","due_on":date.today().isoformat()})
        with self.app.app_context():cid=get_db().execute("SELECT id FROM scheduled_commitments WHERE description='Water bill'").fetchone()[0]
        self.post(f"/commitments/{cid}/complete",{})
        with self.app.app_context():self.assertEqual(get_db().execute("SELECT status FROM scheduled_commitments WHERE id=?",(cid,)).fetchone()[0],"completed")
        self.post("/transactions/undo",{})
        with self.app.app_context():
            row=get_db().execute("SELECT status,linked_transaction_id FROM scheduled_commitments WHERE id=?",(cid,)).fetchone()
            self.assertEqual(row["status"],"scheduled");self.assertIsNone(row["linked_transaction_id"])

    def test_avatar_upload_reencodes_and_is_user_scoped(self):
        from PIL import Image
        image=Image.new("RGB",(12,12),(112,65,166));buf=io.BytesIO();image.save(buf,format="PNG");buf.seek(0)
        token=self.token()
        response=self.client.post("/settings/avatar",data={"csrf_token":token,"avatar":(buf,"portrait.png")},content_type="multipart/form-data",follow_redirects=True)
        self.assertIn(b"Profile photo updated",response.data)
        with self.app.app_context():key=get_db().execute("SELECT avatar_storage_key FROM users WHERE email='one@example.test'").fetchone()[0]
        self.assertTrue(key.endswith(".jpg"));avatar_response=self.client.get(f"/avatar/{key}");self.assertEqual(avatar_response.status_code,200);avatar_response.close()

    def test_demo_reset_is_user_scoped_and_preserves_real_entries(self):
        self.post("/transactions",{"type":"expense","description":"Keep me","amount":"2.00","occurred_on":date.today().isoformat()})
        with self.app.app_context():
            db=get_db();uid=db.execute("SELECT id FROM users WHERE email='one@example.test'").fetchone()[0]
            db.execute("INSERT INTO transactions(user_id,type,amount_paise,description,occurred_on,source) VALUES(?,?,?,?,?,'demo')",(uid,"expense",350,"Demo record",date.today().isoformat()))
            db.execute("UPDATE user_settings SET available_balance_paise=125000,balance_as_of_date=?,balance_is_demo=1 WHERE user_id=?",(date.today().isoformat(),uid));db.commit()
        response=self.post("/settings/demo/reset",{})
        self.assertIn(b"Demo records were removed",response.data)
        with self.app.app_context():
            db=get_db();self.assertEqual(db.execute("SELECT COUNT(*) FROM transactions WHERE description='Keep me'").fetchone()[0],1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM transactions WHERE source='demo'").fetchone()[0],0)
            self.assertIsNone(db.execute("SELECT available_balance_paise FROM user_settings WHERE user_id=(SELECT id FROM users WHERE email='one@example.test')").fetchone()[0])


if __name__=="__main__":unittest.main()
