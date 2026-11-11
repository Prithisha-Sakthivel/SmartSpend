import argparse
import getpass
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from datetime import timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.db import get_db
from werkzeug.security import generate_password_hash


def seed(email, password):
    app = create_app({"DEBUG": True})
    with app.app_context():
        db = get_db()
        user = db.execute("SELECT id FROM users WHERE email=?", (email.lower(),)).fetchone()
        if user:
            uid = user["id"]
        else:
            cur = db.execute("INSERT INTO users(email,password_hash,display_name) VALUES(?,?,?)", (email.lower(), generate_password_hash(password), "Aarav Mehta"))
            uid = cur.lastrowid
            db.execute("INSERT INTO user_settings(user_id) VALUES(?)", (uid,))
        db.execute("UPDATE users SET password_hash=?,display_name='Aarav Mehta' WHERE id=?", (generate_password_hash(password), uid))
        db.execute("DELETE FROM transactions WHERE user_id=? AND source='demo'", (uid,))
        db.execute("DELETE FROM goal_contributions WHERE user_id=? AND is_demo=1", (uid,))
        db.execute("DELETE FROM savings_challenges WHERE user_id=? AND is_demo=1", (uid,))
        db.execute("DELETE FROM savings_goals WHERE user_id=? AND is_demo=1", (uid,))
        db.execute("DELETE FROM scheduled_commitments WHERE user_id=? AND is_demo=1", (uid,))
        db.execute("DELETE FROM cooling_off_purchases WHERE user_id=? AND is_demo=1", (uid,))
        db.execute("DELETE FROM budgets WHERE user_id=? AND is_demo=1", (uid,))
        if email.lower()=="demo@smartspend.local":
            # Clean the clearly named records from the pre-provenance v1 demo seed.
            db.execute("DELETE FROM savings_challenges WHERE user_id=? AND name='Friday savings habit'",(uid,))
            db.execute("DELETE FROM savings_goals WHERE user_id=? AND name='A camera for the next trip'",(uid,))
            db.execute("DELETE FROM scheduled_commitments WHERE user_id=? AND description IN ('Mobile plan','Freelance payment','Monthly savings transfer','Water bill')",(uid,))
            db.execute("DELETE FROM cooling_off_purchases WHERE user_id=? AND description='Desk lamp for the study corner'",(uid,))
        cats = {r["name"]: r["id"] for r in db.execute("SELECT id,name FROM categories WHERE user_id=?", (uid,)).fetchall()}
        for name, kind in [("Housing","expense"),("Food","expense"),("Transport","expense"),("Utilities","expense"),("Health","expense"),("Shopping","expense"),("Entertainment","expense"),("Other","expense"),("Salary","income"),("Other income","income")]:
            db.execute("INSERT OR IGNORE INTO categories(user_id,name,kind) VALUES(?,?,?)", (uid,name,kind))
        cats = {r["name"]: r["id"] for r in db.execute("SELECT id,name FROM categories WHERE user_id=?", (uid,)).fetchall()}
        today = datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
        db.execute("UPDATE user_settings SET available_balance_paise=?,balance_as_of_date=?,default_buffer_paise=?,planning_horizon_days=30,balance_is_demo=1 WHERE user_id=?", (6250000,today.isoformat(),500000,uid))
        tx = [(-37,"expense",125000,"Monthly rent","Housing"),(-31,"income",8500000,"Monthly salary","Salary"),(-29,"expense",23800,"Weekly groceries","Food"),(-27,"expense",8500,"Metro card top-up","Transport"),(-24,"expense",17500,"Electricity bill","Utilities"),(-21,"expense",12900,"Dinner with friends","Food"),(-18,"expense",69900,"Running shoes","Shopping"),(-15,"expense",16500,"Pharmacy","Health"),(-13,"expense",5600,"Coffee and pastry","Food"),(-10,"expense",29000,"Internet bill","Utilities"),(-8,"expense",14900,"Groceries","Food"),(-5,"expense",42000,"Streaming subscription","Entertainment"),(-3,"expense",8400,"Auto fare","Transport"),(-1,"expense",11500,"Lunch","Food")]
        for offset, kind, amount, desc, cat in tx:
            db.execute("INSERT INTO transactions(user_id,type,amount_paise,description,category_id,occurred_on,source) VALUES(?,?,?,?,?,?,?)", (uid,kind,amount,desc,cats[cat],(today+timedelta(days=offset)).isoformat(),"demo"))
        month_start=today.replace(day=1);next_month=(month_start.replace(day=28)+timedelta(days=4)).replace(day=1);month_end=next_month-timedelta(days=1)
        for cat,limit in [("Food",180000),("Transport",80000),("Shopping",250000),("Utilities",220000)]:
            db.execute("INSERT OR REPLACE INTO budgets(user_id,category_id,period_start,period_end,limit_paise,is_demo) VALUES(?,?,?,?,?,1)",(uid,cats[cat],month_start.isoformat(),month_end.isoformat(),limit))
        goal=db.execute("INSERT INTO savings_goals(user_id,name,target_paise,target_date,is_demo) VALUES(?,?,?,?,1)",(uid,"A camera for the next trip",1200000,(today+timedelta(days=150)).isoformat())).lastrowid
        for ago,amount in [(21,75000),(12,50000),(5,85000)]:
            db.execute("INSERT INTO goal_contributions(user_id,goal_id,amount_paise,contributed_on,note,source,is_demo) VALUES(?,?,?,?,?,'manual',1)",(uid,goal,amount,(today-timedelta(days=ago)).isoformat(),"Demo contribution"))
        db.execute("INSERT INTO savings_challenges(user_id,name,challenge_type,target_paise,installment_paise,start_on,end_on,cadence,goal_id,is_demo) VALUES(?,?,?,?,?,?,?,?,?,1)",(uid,"Friday savings habit","fixed_cadence",400000,100000,(today-timedelta(days=7)).isoformat(),(today+timedelta(days=21)).isoformat(),"weekly",goal))
        for offset,kind,amount,desc,cat in [(3,"bill",72000,"Mobile plan","Utilities"),(8,"income",1200000,"Freelance payment","Other income"),(12,"savings",50000,"Monthly savings transfer",None),(18,"bill",31000,"Water bill","Utilities")]:
            db.execute("INSERT INTO scheduled_commitments(user_id,kind,description,amount_paise,due_on,category_id,is_demo) VALUES(?,?,?,?,?,?,1)",(uid,kind,desc,amount,(today+timedelta(days=offset)).isoformat(),cats.get(cat) if cat else None))
        db.execute("INSERT INTO cooling_off_purchases(user_id,description,amount_paise,category_id,review_on,is_demo) VALUES(?,?,?,?,?,1)",(uid,"Desk lamp for the study corner",34900,cats["Shopping"],(today+timedelta(days=2)).isoformat()))
        db.commit()
        return uid


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description="Create or refresh a clearly marked local SmartSpend demo account.")
    parser.add_argument("--email",default="demo@smartspend.local")
    parser.add_argument("--password",help="Avoid on shared systems; otherwise you will be prompted.")
    args=parser.parse_args()
    password=args.password or getpass.getpass("Demo account password (10+ characters): ")
    if len(password)<10:raise SystemExit("Use a password of at least 10 characters.")
    uid=seed(args.email,password)
    print(f"Demo account ready for {args.email} (user ID {uid}). The password was not saved in the application source.")
