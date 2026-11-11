from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def parse_paise(value, allow_zero=False, allow_negative=False):
    text = str(value or "").replace(",", "").replace("₹", "").strip()
    if not text or len(text) > 18:
        raise ValueError("Enter a valid amount in rupees.")
    try:
        amount = Decimal(text).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        rupees = int(amount * 100)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Enter a valid amount in rupees.") from exc
    if (rupees < 0 and not allow_negative) or (rupees == 0 and not allow_zero) or abs(rupees) > 9_000_000_000_000_000:
        raise ValueError("Amount must be positive and within the supported limit.")
    return int(rupees)


def rupees(paise):
    value=int(paise or 0)
    sign="-" if value<0 else ""
    rupee_part,paise_part=divmod(abs(value),100)
    digits=str(rupee_part)
    if len(digits)>3:
        tail=digits[-3:];head=digits[:-3];groups=[]
        while head:
            groups.insert(0,head[-2:]);head=head[:-2]
        digits=",".join(groups+[tail])
    return f"{sign}₹{digits}.{paise_part:02d}"


def current_funds(db, user_id, settings):
    if settings["available_balance_paise"] is None:
        return None
    delta = db.execute("SELECT COALESCE(SUM(CASE type WHEN 'income' THEN amount_paise ELSE -amount_paise END),0) n FROM transactions WHERE user_id=? AND occurred_on>?", (user_id, settings["balance_as_of_date"])).fetchone()["n"]
    return int(settings["available_balance_paise"] + delta)


def commitments(db, user_id, start, end):
    rows = db.execute("SELECT kind,COALESCE(SUM(amount_paise),0) total FROM scheduled_commitments WHERE user_id=? AND status='scheduled' AND due_on BETWEEN ? AND ? GROUP BY kind", (user_id, start, end)).fetchall()
    return {r["kind"]: int(r["total"]) for r in rows}


def safe_to_spend(db, user_id, settings, today=None):
    today = today or date.today()
    end = today + timedelta(days=int(settings["planning_horizon_days"]) - 1)
    funds = current_funds(db, user_id, settings)
    if funds is None:
        return {"available": False, "reason": "Add your available balance and the date you checked it to estimate spending capacity."}
    c = commitments(db, user_id, today.isoformat(), end.isoformat())
    raw = funds + c.get("income", 0) - c.get("bill", 0) - c.get("savings", 0) - int(settings["default_buffer_paise"])
    return {"available": True, "amount": max(0, raw), "raw": raw, "funds": funds, "income": c.get("income", 0), "bills": c.get("bill", 0), "savings": c.get("savings", 0), "buffer": int(settings["default_buffer_paise"]), "start": today.isoformat(), "end": end.isoformat()}


def runway(db, user_id, settings, today=None, override=None):
    today = today or date.today()
    funds = current_funds(db, user_id, settings)
    if funds is None:
        return {"available": False, "reason": "Add your available balance snapshot first."}
    if funds <= 0:
        return {"available": True, "days": 0, "zero_date": today.isoformat(), "funds": funds, "burn": 0, "reason": "Your current balance is at or below zero."}
    since = (today - timedelta(days=29)).isoformat()
    expenses = db.execute("SELECT COALESCE(SUM(amount_paise),0) n,COUNT(*) c FROM transactions WHERE user_id=? AND type='expense' AND source!='scheduled' AND occurred_on BETWEEN ? AND ?", (user_id, since, today.isoformat())).fetchone()
    if override is None:
        if expenses["c"] == 0:
            return {"available": False, "reason": "There are no expenses in the last 30 days. Add a daily burn estimate to continue."}
        burn = int(expenses["n"]) // 30
        if burn == 0:
            return {"available": False, "reason": "Recent spending averages to less than one paise per day; enter a daily estimate to project runway."}
    else:
        burn = max(0, int(override))
    crows = db.execute("SELECT kind,due_on,amount_paise FROM scheduled_commitments WHERE user_id=? AND status='scheduled' AND kind IN ('bill','income') AND due_on>=? ORDER BY due_on", (user_id, today.isoformat())).fetchall()
    by_day = {}
    for row in crows:
        by_day.setdefault(row["due_on"], {"bill": 0, "income": 0})[row["kind"]] += int(row["amount_paise"])
    cash = funds
    for offset in range(3650):
        day = today + timedelta(days=offset)
        due = by_day.get(day.isoformat(), {"bill": 0, "income": 0})
        cash += -burn + due["income"] - due["bill"]
        if cash <= 0:
            return {"available": True, "days": offset + 1, "zero_date": day.isoformat(), "funds": funds, "burn": burn, "reason": None}
    return {"available": True, "days": None, "zero_date": None, "funds": funds, "burn": burn, "reason": "Balance stays above zero beyond the 10-year estimate window."}
