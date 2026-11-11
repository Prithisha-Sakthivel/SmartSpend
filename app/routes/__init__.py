import csv
import calendar
import hashlib
import io
import json
from decimal import Decimal
import secrets
import smtplib
import ssl
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from functools import wraps
from pathlib import Path
from datetime import timezone

from flask import Blueprint, current_app, flash, g, redirect, render_template, request, send_file, session, url_for, abort
from PIL import Image, UnidentifiedImageError
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from app.db import get_db
from app.services.money import parse_paise, rupees, safe_to_spend, runway, current_funds, commitments
from app.services import c_bridge

bp = Blueprint("main", __name__)


def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please sign in to continue.", "info")
            return redirect(url_for("main.login"))
        g.user_id = int(session["user_id"])
        return fn(*args, **kwargs)
    return wrapped


def today():
    return datetime.now(timezone(timedelta(hours=5, minutes=30))).date()


def settings_row():
    return get_db().execute("SELECT * FROM user_settings WHERE user_id=?", (g.user_id,)).fetchone()


def parse_date(value, label="date"):
    try:
        return date.fromisoformat(value).isoformat()
    except (ValueError, TypeError):
        raise ValueError(f"Choose a valid {label}.")


def record_transaction(db, user_id, form, existing=None):
    kind = form.get("type", "expense")
    if kind not in {"income", "expense"}:
        raise ValueError("Choose income or expense.")
    desc = (form.get("description") or "").strip()[:100]
    if not desc:
        raise ValueError("Add a description.")
    amount = parse_paise(form.get("amount"))
    category = form.get("category_id") or None
    if category:
        ok = db.execute("SELECT 1 FROM categories WHERE id=? AND (user_id=? OR user_id IS NULL) AND kind=? AND is_active=1", (category, user_id, kind)).fetchone()
        if not ok:
            raise ValueError("Choose a valid category.")
    row = {"type": kind, "amount_paise": amount, "description": desc, "category_id": int(category) if category else None, "occurred_on": parse_date(form.get("occurred_on") or today().isoformat()), "notes": (form.get("notes") or "").strip()[:500] or None}
    if existing:
        db.execute("UPDATE transactions SET type=?,amount_paise=?,description=?,category_id=?,occurred_on=?,notes=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?", (*row.values(), existing, user_id))
        return int(existing)
    cur = db.execute("INSERT INTO transactions(user_id,type,amount_paise,description,category_id,occurred_on,notes) VALUES(?,?,?,?,?,?,?)", (user_id, *row.values()))
    return int(cur.lastrowid)


def transaction_image(row):
    return {k: row[k] for k in ("type", "amount_paise", "description", "category_id", "occurred_on", "notes", "source")}


def add_undo_event(db, user_id, entity_id, operation, before, after, related=None):
    seq = db.execute("SELECT COALESCE(MAX(sequence_no),0)+1 n FROM undo_events WHERE user_id=?", (user_id,)).fetchone()["n"]
    relation_type,relation_id=related if related else (None,None)
    db.execute("INSERT INTO undo_events(user_id,sequence_no,entity_id,operation,before_image,after_image,related_entity_type,related_entity_id) VALUES(?,?,?,?,?,?,?,?)", (user_id, seq, entity_id, operation, json.dumps(before, separators=(",", ":")) if before else None, json.dumps(after, separators=(",", ":")) if after else None,relation_type,relation_id))
    # Keep up to 50 unconsumed operations; older operations beyond the limit cannot be undone.
    db.execute("DELETE FROM undo_events WHERE user_id=? AND undone_at IS NULL AND id NOT IN (SELECT id FROM undo_events WHERE user_id=? AND undone_at IS NULL ORDER BY sequence_no DESC LIMIT 50)", (user_id, user_id))


def challenge_progress(db, challenge):
    if challenge["challenge_type"] == "no_spend":
        checkins=db.execute("SELECT COUNT(*) total,SUM(CASE result WHEN 'met' THEN 1 ELSE 0 END) successful FROM challenge_checkins WHERE user_id=? AND challenge_id=?",(challenge["user_id"],challenge["id"])).fetchone()
        return {"saved":0,"target":0,"count":int(checkins["successful"] or 0),"total_days":int(checkins["total"] or 0),"met":False}
    total = db.execute("SELECT COALESCE(SUM(amount_paise),0) n FROM goal_contributions WHERE user_id=? AND challenge_id=? AND reversed_at IS NULL AND contributed_on BETWEEN ? AND ?", (challenge["user_id"], challenge["id"], challenge["start_on"], min(challenge["end_on"], today().isoformat()))).fetchone()["n"]
    return {"saved": int(total), "target": int(challenge["target_paise"]), "count": 0, "met": total >= challenge["target_paise"]}


@bp.route("/")
def home():
    return redirect(url_for("main.dashboard" if session.get("user_id") else "main.login"))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = (request.form.get("display_name") or "").strip()[:60]
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        if not name or "@" not in email or len(email) > 254 or len(password) < 10:
            flash("Enter your name, a valid email, and a password of at least 10 characters.", "error")
        else:
            db = get_db()
            try:
                cur = db.execute("INSERT INTO users(email,password_hash,display_name) VALUES(?,?,?)", (email, generate_password_hash(password), name))
                db.execute("INSERT INTO user_settings(user_id) VALUES(?)", (cur.lastrowid,))
                for cat in [("Housing", "expense"), ("Food", "expense"), ("Transport", "expense"), ("Utilities", "expense"), ("Health", "expense"), ("Shopping", "expense"), ("Entertainment", "expense"), ("Other", "expense"), ("Salary", "income"), ("Other income", "income")]:
                    db.execute("INSERT OR IGNORE INTO categories(user_id,name,kind) VALUES(?,?,?)", (cur.lastrowid, *cat))
                db.commit()
                session.clear(); session["user_id"] = cur.lastrowid
                flash("Your account is ready. Add a balance snapshot to start your estimates.", "success")
                return redirect(url_for("main.dashboard"))
            except Exception:
                db.rollback()
                flash("An account with that email may already exist.", "error")
    return render_template("auth.html", mode="register")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        row = get_db().execute("SELECT id,password_hash FROM users WHERE email=? AND is_active=1", (email,)).fetchone()
        if row and check_password_hash(row["password_hash"], request.form.get("password") or ""):
            session.clear(); session["user_id"] = row["id"]
            flash("Welcome back.", "success")
            return redirect(url_for("main.dashboard"))
        flash("Email or password was not recognized.", "error")
    return render_template("auth.html", mode="login")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You are signed out.", "info")
    return redirect(url_for("main.login"))


@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        user = get_db().execute("SELECT id,email FROM users WHERE email=? AND is_active=1", (email,)).fetchone()
        dev_url = None
        if user:
            token = secrets.token_urlsafe(32)
            digest = hashlib.sha256(token.encode()).hexdigest()
            db = get_db()
            db.execute("UPDATE password_reset_tokens SET used_at=? WHERE user_id=? AND used_at IS NULL", (datetime.utcnow().isoformat(), user["id"]))
            db.execute("INSERT INTO password_reset_tokens(user_id,token_hash,created_at,expires_at) VALUES(?,?,?,?)", (user["id"], digest, datetime.utcnow().isoformat(), (datetime.utcnow()+timedelta(minutes=30)).isoformat()))
            db.commit()
            host = current_app.config.get("MAIL_HOST")
            if host:
                msg = EmailMessage(); msg["Subject"] = "Reset your SmartSpend password"; msg["From"] = current_app.config.get("MAIL_FROM", "SmartSpend <noreply@localhost>"); msg["To"] = user["email"]
                msg.set_content(f"Use this link within 30 minutes to reset your password: {url_for('main.reset_password', token=token, _external=True)}")
                try:
                    with smtplib.SMTP(host, int(current_app.config.get("MAIL_PORT", 587)), timeout=10) as smtp:
                        smtp.starttls(context=ssl.create_default_context()); smtp.login(current_app.config["MAIL_USER"], current_app.config["MAIL_PASSWORD"]); smtp.send_message(msg)
                except Exception:
                    current_app.logger.exception("Password reset email delivery failed")
            elif current_app.config.get("DEBUG"):
                dev_url = url_for("main.reset_password", token=token)
        flash("If an active account uses that email, a reset link will be sent.", "success")
        return render_template("forgot.html", dev_url=dev_url)
    return render_template("forgot.html", dev_url=None)


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    digest = hashlib.sha256(token.encode()).hexdigest()
    row = get_db().execute("SELECT id,user_id FROM password_reset_tokens WHERE token_hash=? AND used_at IS NULL AND expires_at>?", (digest, datetime.utcnow().isoformat())).fetchone()
    if not row:
        flash("That reset link is invalid or has expired.", "error")
        return redirect(url_for("main.forgot_password"))
    if request.method == "POST":
        password = request.form.get("password") or ""
        if len(password) < 10:
            flash("Use at least 10 characters for your new password.", "error")
        else:
            db = get_db(); db.execute("BEGIN IMMEDIATE")
            valid = db.execute("SELECT id FROM password_reset_tokens WHERE id=? AND used_at IS NULL AND expires_at>?", (row["id"], datetime.utcnow().isoformat())).fetchone()
            if valid:
                db.execute("UPDATE users SET password_hash=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (generate_password_hash(password), row["user_id"]))
                db.execute("UPDATE password_reset_tokens SET used_at=? WHERE id=?", (datetime.utcnow().isoformat(), row["id"]))
                db.commit(); flash("Password updated. Sign in with your new password.", "success"); return redirect(url_for("main.login"))
            db.rollback(); flash("That reset link has already been used.", "error")
    return render_template("reset.html")


@bp.route("/dashboard")
@login_required
def dashboard():
    db = get_db(); settings = settings_row(); today_s = today().isoformat(); month_start = today().replace(day=1).isoformat()
    funds = current_funds(db, g.user_id, settings)
    month = db.execute("SELECT COALESCE(SUM(CASE WHEN type='income' THEN amount_paise ELSE 0 END),0) income,COALESCE(SUM(CASE WHEN type='expense' THEN amount_paise ELSE 0 END),0) expenses FROM transactions WHERE user_id=? AND occurred_on BETWEEN ? AND ?", (g.user_id, month_start, today_s)).fetchone()
    cashflow_chart = db.execute("SELECT occurred_on,SUM(CASE WHEN type='income' THEN amount_paise ELSE 0 END) income,SUM(CASE WHEN type='expense' THEN amount_paise ELSE 0 END) expenses FROM transactions WHERE user_id=? AND occurred_on BETWEEN ? AND ? GROUP BY occurred_on ORDER BY occurred_on", (g.user_id,month_start,today_s)).fetchall()
    tx = db.execute("SELECT t.*,c.name category FROM transactions t LEFT JOIN categories c ON c.id=t.category_id WHERE t.user_id=? ORDER BY t.occurred_on DESC,t.id DESC LIMIT 8", (g.user_id,)).fetchall()
    commitments_due = db.execute("SELECT * FROM scheduled_commitments WHERE user_id=? AND status='scheduled' AND due_on>=? ORDER BY due_on LIMIT 6", (g.user_id,today_s)).fetchall()
    goals = db.execute("SELECT g.*,COALESCE(SUM(CASE WHEN c.reversed_at IS NULL THEN c.amount_paise ELSE 0 END),0) saved FROM savings_goals g LEFT JOIN goal_contributions c ON c.goal_id=g.id AND c.user_id=g.user_id WHERE g.user_id=? AND g.status='active' GROUP BY g.id ORDER BY g.target_date LIMIT 4", (g.user_id,)).fetchall()
    budget_rows = db.execute("SELECT b.*,c.name category,COALESCE((SELECT SUM(t.amount_paise) FROM transactions t WHERE t.user_id=b.user_id AND t.category_id=b.category_id AND t.type='expense' AND t.occurred_on BETWEEN b.period_start AND b.period_end),0) spent FROM budgets b JOIN categories c ON c.id=b.category_id WHERE b.user_id=? AND b.period_start<=? AND b.period_end>=?", (g.user_id,today_s,today_s)).fetchall()
    c_ready = c_bridge.available(current_app.config["C_LIBRARY"])
    return render_template("dashboard.html", title="Overview", funds=funds, settings=settings, month=month, transactions=tx, commitments=commitments_due, goals=goals, budgets=budget_rows, safe=safe_to_spend(db,g.user_id,settings,today()), runway=runway(db,g.user_id,settings), c_ready=c_ready, cashflow_chart=cashflow_chart, rupees=rupees)


@bp.route("/runway",methods=["GET","POST"])
@login_required
def runway_page():
    db=get_db();settings=settings_row();override=None
    if request.method=="POST":
        try:override=parse_paise(request.form.get("daily_burn"),allow_zero=True)
        except ValueError as exc:flash(str(exc),"error")
    result=runway(db,g.user_id,settings,today(),override)
    return render_template("runway.html",title="Zero-Day Runway",result=result,override=override,rupees=rupees)


@bp.route("/transactions", methods=["GET", "POST"])
@login_required
def transactions():
    db=get_db()
    if request.method=="POST":
        try:
            db.execute("BEGIN IMMEDIATE")
            tid=record_transaction(db,g.user_id,request.form)
            row=db.execute("SELECT * FROM transactions WHERE id=? AND user_id=?",(tid,g.user_id)).fetchone()
            add_undo_event(db,g.user_id,tid,"create",None,transaction_image(row)); db.commit()
            flash("Transaction added. You can undo it from this page.","success")
            return redirect(url_for("main.transactions"))
        except ValueError as exc:
            db.rollback(); flash(str(exc),"error")
        except Exception:
            db.rollback(); current_app.logger.exception("Transaction create failed"); flash("Could not save this transaction.","error")
    query=(request.args.get("q") or "").strip()[:80]; kind=request.args.get("type",""); category=request.args.get("category",""); start=request.args.get("from",""); end=request.args.get("to","")
    sql="SELECT t.*,c.name category FROM transactions t LEFT JOIN categories c ON c.id=t.category_id WHERE t.user_id=?"; params=[g.user_id]
    if query: sql+=" AND (t.description LIKE ? OR CAST(t.id AS TEXT)=?)";params.extend([f"%{query}%",query])
    if kind in ("income","expense"):sql+=" AND t.type=?";params.append(kind)
    if category.isdigit():sql+=" AND t.category_id=?";params.append(int(category))
    if start:
        try:sql+=" AND t.occurred_on>=?";params.append(parse_date(start))
        except ValueError:flash("Invalid start date filter.","error")
    if end:
        try:sql+=" AND t.occurred_on<=?";params.append(parse_date(end))
        except ValueError:flash("Invalid end date filter.","error")
    rows=db.execute(sql+" ORDER BY t.occurred_on DESC,t.id DESC LIMIT 300",params).fetchall()
    all_sorted=db.execute("SELECT id,amount_paise,type,category_id FROM transactions WHERE user_id=? ORDER BY id",(g.user_id,)).fetchall()
    if query.isdigit():
        found=c_bridge.binary_search(current_app.config["C_LIBRARY"],all_sorted,int(query))
        rows=[row for row in rows if found and row["id"]==found["id"]]
    count=c_bridge.transaction_list_count(current_app.config["C_LIBRARY"],all_sorted)
    categories=db.execute("SELECT * FROM categories WHERE is_active=1 AND (user_id=? OR user_id IS NULL) ORDER BY name",(g.user_id,)).fetchall()
    undo_events=db.execute("SELECT id FROM undo_events WHERE user_id=? AND undone_at IS NULL ORDER BY sequence_no",(g.user_id,)).fetchall()
    c_ready=c_bridge.available(current_app.config["C_LIBRARY"])
    return render_template("transactions.html",title="Transactions",rows=rows,categories=categories,query=query,kind=kind,category=category,start=start,end=end,undo_count=len(undo_events),c_count=count,c_ready=c_ready,rupees=rupees)


@bp.route("/transactions/<int:tid>/edit",methods=["GET","POST"])
@login_required
def edit_transaction(tid):
    db=get_db(); row=db.execute("SELECT * FROM transactions WHERE id=? AND user_id=?",(tid,g.user_id)).fetchone()
    if not row:abort(404)
    if request.method=="POST":
        try:
            before=transaction_image(row);db.execute("BEGIN IMMEDIATE");record_transaction(db,g.user_id,request.form,tid)
            after=transaction_image(db.execute("SELECT * FROM transactions WHERE id=? AND user_id=?",(tid,g.user_id)).fetchone())
            add_undo_event(db,g.user_id,tid,"edit",before,after);db.commit();flash("Transaction updated.","success");return redirect(url_for("main.transactions"))
        except ValueError as exc:db.rollback();flash(str(exc),"error")
    categories=db.execute("SELECT * FROM categories WHERE is_active=1 AND (user_id=? OR user_id IS NULL) ORDER BY name",(g.user_id,)).fetchall()
    return render_template("transaction_edit.html",title="Edit transaction",row=row,categories=categories)


@bp.route("/transactions/<int:tid>/delete",methods=["POST"])
@login_required
def delete_transaction(tid):
    db=get_db();db.execute("BEGIN IMMEDIATE");row=db.execute("SELECT * FROM transactions WHERE id=? AND user_id=?",(tid,g.user_id)).fetchone()
    if not row:db.rollback();abort(404)
    before=transaction_image(row)
    parent=db.execute("SELECT id,'scheduled_commitment' entity_type FROM scheduled_commitments WHERE linked_transaction_id=? AND user_id=? UNION ALL SELECT id,'cooling_off_purchase' entity_type FROM cooling_off_purchases WHERE linked_transaction_id=? AND user_id=? LIMIT 1",(tid,g.user_id,tid,g.user_id)).fetchone()
    relation=(parent["entity_type"],parent["id"]) if parent else None
    db.execute("DELETE FROM transactions WHERE id=? AND user_id=?",(tid,g.user_id))
    if relation and relation[0]=="scheduled_commitment":db.execute("UPDATE scheduled_commitments SET status='scheduled',linked_transaction_id=NULL WHERE id=? AND user_id=?",(relation[1],g.user_id))
    if relation and relation[0]=="cooling_off_purchase":db.execute("UPDATE cooling_off_purchases SET status='pending',linked_transaction_id=NULL WHERE id=? AND user_id=?",(relation[1],g.user_id))
    add_undo_event(db,g.user_id,tid,"delete",before,None,relation);db.commit();flash("Transaction deleted. You can undo it from this page.","success");return redirect(url_for("main.transactions"))


@bp.route("/transactions/undo",methods=["POST"])
@login_required
def undo_transaction():
    db=get_db();db.execute("BEGIN IMMEDIATE")
    events=db.execute("SELECT * FROM undo_events WHERE user_id=? AND undone_at IS NULL ORDER BY sequence_no",(g.user_id,)).fetchall()
    event_id=c_bridge.newest_undo_id(current_app.config["C_LIBRARY"],[e["id"] for e in events])
    event=next((e for e in events if e["id"]==event_id),None)
    if not event:db.rollback();flash("There is nothing to undo.","info");return redirect(url_for("main.transactions"))
    before=json.loads(event["before_image"]) if event["before_image"] else None;after=json.loads(event["after_image"]) if event["after_image"] else None
    current=db.execute("SELECT * FROM transactions WHERE id=? AND user_id=?",(event["entity_id"],g.user_id)).fetchone()
    mismatch=(event["operation"]=="create" and (not current or transaction_image(current)!=after)) or (event["operation"]=="edit" and (not current or transaction_image(current)!=after)) or (event["operation"]=="delete" and current is not None)
    if mismatch:db.rollback();flash("This transaction changed after the saved action, so that undo is no longer safe.","error");return redirect(url_for("main.transactions"))
    if event["operation"]=="create":db.execute("DELETE FROM transactions WHERE id=? AND user_id=?",(event["entity_id"],g.user_id))
    elif event["operation"]=="edit":db.execute("UPDATE transactions SET type=?,amount_paise=?,description=?,category_id=?,occurred_on=?,notes=?,source=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",(before["type"],before["amount_paise"],before["description"],before["category_id"],before["occurred_on"],before["notes"],before["source"],event["entity_id"],g.user_id))
    else:
        db.execute("INSERT INTO transactions(id,user_id,type,amount_paise,description,category_id,occurred_on,notes,source) VALUES(?,?,?,?,?,?,?,?,?)",(event["entity_id"],g.user_id,before["type"],before["amount_paise"],before["description"],before["category_id"],before["occurred_on"],before["notes"],before["source"]))
    if event["related_entity_type"]=="scheduled_commitment":
        if event["operation"]=="delete":db.execute("UPDATE scheduled_commitments SET status='completed',linked_transaction_id=? WHERE id=? AND user_id=?",(event["entity_id"],event["related_entity_id"],g.user_id))
        elif event["operation"]=="create":db.execute("UPDATE scheduled_commitments SET status='scheduled',linked_transaction_id=NULL WHERE id=? AND user_id=?",(event["related_entity_id"],g.user_id))
    elif event["related_entity_type"]=="cooling_off_purchase":
        if event["operation"]=="delete":db.execute("UPDATE cooling_off_purchases SET status='proceeded',linked_transaction_id=? WHERE id=? AND user_id=?",(event["entity_id"],event["related_entity_id"],g.user_id))
        elif event["operation"]=="create":db.execute("UPDATE cooling_off_purchases SET status='pending',linked_transaction_id=NULL WHERE id=? AND user_id=?",(event["related_entity_id"],g.user_id))
    db.execute("UPDATE undo_events SET undone_at=? WHERE id=? AND user_id=?",(datetime.utcnow().isoformat(),event["id"],g.user_id));db.commit();flash("Last transaction change undone.","success");return redirect(url_for("main.transactions"))


@bp.route("/commitments",methods=["GET","POST"])
@login_required
def commitments_page():
    db=get_db()
    if request.method=="POST":
        try:
            kind=request.form.get("kind");desc=(request.form.get("description") or "").strip()[:100]
            if kind not in {"bill","income","savings"} or not desc:raise ValueError("Enter a description and choose a commitment type.")
            due=parse_date(request.form.get("due_on"),"due date");amount=parse_paise(request.form.get("amount"));category=request.form.get("category_id") or None
            expected_kind="income" if kind=="income" else "expense"
            if category and not db.execute("SELECT 1 FROM categories WHERE id=? AND (user_id=? OR user_id IS NULL) AND kind=?",(category,g.user_id,expected_kind)).fetchone():raise ValueError("Choose a valid category.")
            recurrence=request.form.get("recurrence") or None;series=secrets.token_hex(8) if recurrence else None
            if recurrence not in {None,"weekly","monthly"}:raise ValueError("Choose no repeat, weekly, or monthly.")
            db.execute("INSERT INTO scheduled_commitments(user_id,kind,description,amount_paise,due_on,category_id,recurrence_rule,series_id) VALUES(?,?,?,?,?,?,?,?)",(g.user_id,kind,desc,amount,due,category,recurrence,series))
            if recurrence in {"weekly","monthly"}:fill_recurring_series(db,g.user_id,series)
            db.commit();flash("Commitment scheduled, including dated occurrences for the next year.","success");return redirect(url_for("main.commitments_page"))
        except ValueError as exc:db.rollback();flash(str(exc),"error")
    rows=db.execute("SELECT s.*,c.name category FROM scheduled_commitments s LEFT JOIN categories c ON c.id=s.category_id WHERE s.user_id=? ORDER BY CASE status WHEN 'scheduled' THEN 0 ELSE 1 END,due_on",(g.user_id,)).fetchall()
    return render_template("commitments.html",title="Commitments",rows=rows,categories=db.execute("SELECT * FROM categories WHERE user_id=? OR user_id IS NULL ORDER BY name",(g.user_id,)).fetchall(),rupees=rupees)


@bp.route("/commitments/<int:cid>/complete",methods=["POST"])
@login_required
def complete_commitment(cid):
    db=get_db();db.execute("BEGIN IMMEDIATE");row=db.execute("SELECT * FROM scheduled_commitments WHERE id=? AND user_id=? AND status='scheduled'",(cid,g.user_id)).fetchone()
    if not row:db.rollback();abort(404)
    if row["kind"]=="savings":
        db.execute("UPDATE scheduled_commitments SET status='completed',updated_at=CURRENT_TIMESTAMP WHERE id=?",(cid,))
        if row["series_id"]:fill_recurring_series(db,g.user_id,row["series_id"])
        db.commit();flash("Savings commitment marked complete. Add a goal contribution if you want it in goal progress.","success");return redirect(url_for("main.commitments_page"))
    kind="expense" if row["kind"]=="bill" else "income";cur=db.execute("INSERT INTO transactions(user_id,type,amount_paise,description,category_id,occurred_on,source) VALUES(?,?,?,?,?,?,?)",(g.user_id,kind,row["amount_paise"],row["description"],row["category_id"],today().isoformat(),"scheduled"));db.execute("UPDATE scheduled_commitments SET status='completed',linked_transaction_id=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(cur.lastrowid,cid));add_undo_event(db,g.user_id,cur.lastrowid,"create",None,transaction_image(db.execute("SELECT * FROM transactions WHERE id=?",(cur.lastrowid,)).fetchone()),("scheduled_commitment",cid))
    if row["series_id"]:fill_recurring_series(db,g.user_id,row["series_id"])
    db.commit();flash("Commitment completed and recorded in transactions.","success");return redirect(url_for("main.commitments_page"))


def next_occurrence(due_on, rule):
    current=date.fromisoformat(due_on)
    return advance_occurrence(current,rule).isoformat()


def advance_occurrence(current, rule, anchor_day=None):
    if rule=="weekly":return current+timedelta(days=7)
    year=current.year+(current.month//12);month=(current.month%12)+1
    return current.replace(year=year,month=month,day=min(anchor_day or current.day,calendar.monthrange(year,month)[1]))


def fill_recurring_series(db,user_id,series_id):
    rows=db.execute("SELECT due_on,recurrence_rule FROM scheduled_commitments WHERE user_id=? AND series_id=? ORDER BY due_on",(user_id,series_id)).fetchall()
    if not rows:return
    rule=rows[0]["recurrence_rule"]
    if rule not in {"weekly","monthly"}:return
    anchor=date.fromisoformat(rows[0]["due_on"]);latest=date.fromisoformat(rows[-1]["due_on"]);horizon=today()+timedelta(days=365)
    for _ in range(60):
        if latest>=horizon:break
        latest=advance_occurrence(latest,rule,anchor.day)
        if latest>horizon:break
        db.execute("INSERT OR IGNORE INTO scheduled_commitments(user_id,kind,description,amount_paise,due_on,category_id,recurrence_rule,series_id) SELECT user_id,kind,description,amount_paise,?,category_id,recurrence_rule,series_id FROM scheduled_commitments WHERE user_id=? AND series_id=? ORDER BY due_on LIMIT 1",(latest.isoformat(),user_id,series_id))


@bp.route("/commitments/<int:cid>/cancel",methods=["POST"])
@login_required
def cancel_commitment(cid):
    db=get_db();db.execute("UPDATE scheduled_commitments SET status='cancelled',updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=? AND status='scheduled'",(cid,g.user_id));db.commit();flash("Commitment cancelled.","success");return redirect(url_for("main.commitments_page"))


@bp.route("/budgets",methods=["GET","POST"])
@login_required
def budgets():
    db=get_db();start=today().replace(day=1);next_month=(start.replace(day=28)+timedelta(days=4)).replace(day=1);end=next_month-timedelta(days=1)
    if request.method=="POST":
        try:
            category=int(request.form.get("category_id"));limit=parse_paise(request.form.get("limit"))
            if not db.execute("SELECT 1 FROM categories WHERE id=? AND user_id=? AND kind='expense'",(category,g.user_id)).fetchone():raise ValueError("Select one of your expense categories.")
            db.execute("INSERT INTO budgets(user_id,category_id,period_start,period_end,limit_paise) VALUES(?,?,?,?,?) ON CONFLICT(user_id,category_id,period_start) DO UPDATE SET limit_paise=excluded.limit_paise,period_end=excluded.period_end",(g.user_id,category,start.isoformat(),end.isoformat(),limit));db.commit();flash("Monthly budget saved.","success");return redirect(url_for("main.budgets"))
        except (ValueError,TypeError) as exc:db.rollback();flash(str(exc),"error")
    rows=db.execute("SELECT b.*,c.name category,COALESCE((SELECT SUM(t.amount_paise) FROM transactions t WHERE t.user_id=b.user_id AND t.category_id=b.category_id AND t.type='expense' AND t.occurred_on BETWEEN b.period_start AND b.period_end),0) spent FROM budgets b JOIN categories c ON c.id=b.category_id WHERE b.user_id=? AND b.period_start=? ORDER BY c.name",(g.user_id,start.isoformat())).fetchall()
    cats=db.execute("SELECT * FROM categories WHERE user_id=? AND kind='expense' AND is_active=1 ORDER BY name",(g.user_id,)).fetchall()
    return render_template("budgets.html",title="Budgets",rows=rows,categories=cats,period=start.strftime("%B %Y"),rupees=rupees)


@bp.route("/purchases",methods=["GET","POST"])
@login_required
def purchases():
    db=get_db();settings=settings_row();result=None
    categories=db.execute("SELECT * FROM categories WHERE user_id=? AND kind='expense' ORDER BY name",(g.user_id,)).fetchall()
    if request.method=="POST":
        action=request.form.get("action","preview");description=(request.form.get("description") or "").strip()[:100]
        try:
            if not description:raise ValueError("Enter the product or purchase name.")
            amount=parse_paise(request.form.get("amount"));category=request.form.get("category_id") or None
            if category and not db.execute("SELECT 1 FROM categories WHERE id=? AND user_id=? AND kind='expense'",(category,g.user_id)).fetchone():raise ValueError("Choose one of your expense categories.")
            safe=safe_to_spend(db,g.user_id,settings,today());run=runway(db,g.user_id,settings)
            budget=None
            if category:
                budget=db.execute("SELECT b.limit_paise,COALESCE(SUM(t.amount_paise),0) spent FROM budgets b LEFT JOIN transactions t ON t.user_id=b.user_id AND t.category_id=b.category_id AND t.type='expense' AND t.occurred_on BETWEEN b.period_start AND b.period_end WHERE b.user_id=? AND b.category_id=? AND b.period_start<=? AND b.period_end>=? GROUP BY b.id LIMIT 1",(g.user_id,category,today().isoformat(),today().isoformat())).fetchone()
            result={"description":description,"amount":amount,"funds":current_funds(db,g.user_id,settings),"safe":safe,"runway":run,"budget":budget}
            if action=="later":
                review=(today()+timedelta(days=2)).isoformat();db.execute("INSERT INTO cooling_off_purchases(user_id,description,amount_paise,category_id,review_on) VALUES(?,?,?,?,?)",(g.user_id,description,amount,category,review));db.commit();flash("Added to your cooling-off list for review in two days.","success");return redirect(url_for("main.cooling_off"))
            if action=="buy":
                if not result["funds"]:raise ValueError("Set up a balance snapshot before recording a simulated purchase.")
                cur=db.execute("INSERT INTO transactions(user_id,type,amount_paise,description,category_id,occurred_on,source) VALUES(?,?,?,?,?,?,?)",(g.user_id,"expense",amount,description,category,today().isoformat(),"purchase_preview"));add_undo_event(db,g.user_id,cur.lastrowid,"create",None,transaction_image(db.execute("SELECT * FROM transactions WHERE id=?",(cur.lastrowid,)).fetchone()));db.commit();flash("Purchase recorded as an expense.","success");return redirect(url_for("main.transactions"))
        except ValueError as exc:flash(str(exc),"error")
    return render_template("purchase.html",title="Before you buy",categories=categories,result=result,rupees=rupees)


@bp.route("/cooling-off")
@login_required
def cooling_off():
    rows=get_db().execute("SELECT p.*,c.name category FROM cooling_off_purchases p LEFT JOIN categories c ON c.id=p.category_id WHERE p.user_id=? ORDER BY p.review_on,p.created_at",(g.user_id,)).fetchall()
    rows=c_bridge.cooling_order(current_app.config["C_LIBRARY"],rows)
    return render_template("cooling.html",title="Cooling-off list",rows=rows,rupees=rupees,c_ready=c_bridge.available(current_app.config["C_LIBRARY"]))


@bp.route("/cooling-off/<int:pid>/<action>",methods=["POST"])
@login_required
def cooling_action(pid,action):
    if action not in {"proceed","cancel","reschedule"}:abort(404)
    db=get_db();row=db.execute("SELECT * FROM cooling_off_purchases WHERE id=? AND user_id=? AND status='pending'",(pid,g.user_id)).fetchone()
    if not row:abort(404)
    if action=="cancel":db.execute("UPDATE cooling_off_purchases SET status='cancelled' WHERE id=?",(pid,))
    elif action=="reschedule":
        review=parse_date(request.form.get("review_on"),"review date");db.execute("UPDATE cooling_off_purchases SET review_on=? WHERE id=?",(review,pid))
    else:
        cur=db.execute("INSERT INTO transactions(user_id,type,amount_paise,description,category_id,occurred_on,source) VALUES(?,?,?,?,?,?,?)",(g.user_id,"expense",row["amount_paise"],row["description"],row["category_id"],today().isoformat(),"cooling_off"));db.execute("UPDATE cooling_off_purchases SET status='proceeded',linked_transaction_id=? WHERE id=?",(cur.lastrowid,pid));add_undo_event(db,g.user_id,cur.lastrowid,"create",None,transaction_image(db.execute("SELECT * FROM transactions WHERE id=?",(cur.lastrowid,)).fetchone()),("cooling_off_purchase",pid))
    db.commit();flash("Cooling-off item updated.","success");return redirect(url_for("main.cooling_off"))


@bp.route("/goals",methods=["GET","POST"])
@login_required
def goals():
    db=get_db()
    if request.method=="POST":
        try:
            name=(request.form.get("name") or "").strip()[:100];target=parse_paise(request.form.get("target"));due=parse_date(request.form.get("target_date"),"target date") if request.form.get("target_date") else None
            if not name:raise ValueError("Enter a goal name.")
            db.execute("INSERT INTO savings_goals(user_id,name,target_paise,target_date) VALUES(?,?,?,?)",(g.user_id,name,target,due));db.commit();flash("Savings goal created.","success");return redirect(url_for("main.goals"))
        except ValueError as exc:db.rollback();flash(str(exc),"error")
    rows=db.execute("SELECT g.*,COALESCE(SUM(CASE WHEN c.reversed_at IS NULL THEN c.amount_paise ELSE 0 END),0) saved FROM savings_goals g LEFT JOIN goal_contributions c ON c.goal_id=g.id AND c.user_id=g.user_id WHERE g.user_id=? GROUP BY g.id ORDER BY g.status,g.target_date",(g.user_id,)).fetchall()
    history=db.execute("SELECT c.*,g.name goal_name FROM goal_contributions c LEFT JOIN savings_goals g ON g.id=c.goal_id WHERE c.user_id=? AND c.reversed_at IS NULL ORDER BY c.contributed_on DESC,c.id DESC LIMIT 30",(g.user_id,)).fetchall()
    return render_template("goals.html",title="Savings goals",goals=rows,contributions=history,rupees=rupees)


@bp.route("/goals/<int:gid>/contribute",methods=["POST"])
@login_required
def contribute(gid):
    db=get_db();goal=db.execute("SELECT id FROM savings_goals WHERE id=? AND user_id=?",(gid,g.user_id)).fetchone()
    if not goal:abort(404)
    try:
        amount=parse_paise(request.form.get("amount"));when=parse_date(request.form.get("contributed_on") or today().isoformat(),"contribution date");note=(request.form.get("note") or "").strip()[:200] or None
        db.execute("INSERT INTO goal_contributions(user_id,goal_id,amount_paise,contributed_on,note) VALUES(?,?,?,?,?)",(g.user_id,gid,amount,when,note));db.commit();flash("Contribution added to your goal history.","success")
    except ValueError as exc:db.rollback();flash(str(exc),"error")
    return redirect(url_for("main.goals"))


@bp.route("/challenges",methods=["GET","POST"])
@login_required
def challenges():
    db=get_db()
    if request.method=="POST":
        try:
            name=(request.form.get("name") or "").strip()[:100];kind=request.form.get("challenge_type");start=parse_date(request.form.get("start_on"),"start date");end=parse_date(request.form.get("end_on"),"end date");cadence=request.form.get("cadence","once")
            if not name or kind not in {"target_by_end","fixed_cadence","no_spend"} or end<start:raise ValueError("Check the challenge name, type, and date range.")
            if cadence not in {"once","daily","weekly","monthly"}:raise ValueError("Choose a valid challenge cadence.")
            target=parse_paise(request.form.get("target")) if kind!="no_spend" else 0
            installment=parse_paise(request.form.get("installment")) if kind=="fixed_cadence" else None
            goal=request.form.get("goal_id") or None
            if goal and not db.execute("SELECT 1 FROM savings_goals WHERE id=? AND user_id=?",(goal,g.user_id)).fetchone():raise ValueError("Choose a valid savings goal.")
            category=request.form.get("category_id") or None
            if kind=="no_spend" and (not category or not db.execute("SELECT 1 FROM categories WHERE id=? AND user_id=? AND kind='expense'",(category,g.user_id)).fetchone()):raise ValueError("Choose the expense category to avoid during a no-spend challenge.")
            db.execute("INSERT INTO savings_challenges(user_id,name,challenge_type,target_paise,installment_paise,start_on,end_on,cadence,goal_id,category_id,status) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(g.user_id,name,kind,target,installment,start,end,cadence,goal,category,"scheduled" if start>today().isoformat() else "active"));db.commit();flash("Challenge created.","success");return redirect(url_for("main.challenges"))
        except ValueError as exc:db.rollback();flash(str(exc),"error")
    rows=db.execute("SELECT s.*,c.name category_name FROM savings_challenges s LEFT JOIN categories c ON c.id=s.category_id WHERE s.user_id=? ORDER BY s.start_on DESC",(g.user_id,)).fetchall()
    decorated=[(row,challenge_progress(db,row)) for row in rows]
    return render_template("challenges.html",title="Savings challenges",challenges=decorated,goals=db.execute("SELECT id,name FROM savings_goals WHERE user_id=? AND status='active'",(g.user_id,)).fetchall(),categories=db.execute("SELECT id,name FROM categories WHERE user_id=? AND kind='expense'",(g.user_id,)).fetchall(),rupees=rupees)


@bp.route("/challenges/<int:cid>/contribute",methods=["POST"])
@login_required
def challenge_contribute(cid):
    db=get_db();challenge=db.execute("SELECT * FROM savings_challenges WHERE id=? AND user_id=?",(cid,g.user_id)).fetchone()
    if not challenge:abort(404)
    try:
        amount=parse_paise(request.form.get("amount"));when=parse_date(request.form.get("contributed_on") or today().isoformat(),"contribution date")
        if challenge["challenge_type"]=="no_spend":raise ValueError("No-spend challenges do not take money contributions.")
        if not challenge["start_on"]<=when<=challenge["end_on"] or when>today().isoformat():raise ValueError("Contribution date must be from today or earlier and inside the challenge dates.")
        db.execute("INSERT INTO goal_contributions(user_id,goal_id,challenge_id,amount_paise,contributed_on,note,source) VALUES(?,?,?,?,?,?,?)",(g.user_id,challenge["goal_id"],cid,amount,when,(request.form.get("note") or "").strip()[:200] or None,"challenge"));db.commit();flash("Challenge contribution saved.","success")
    except ValueError as exc:db.rollback();flash(str(exc),"error")
    return redirect(url_for("main.challenges"))


@bp.route("/challenges/<int:cid>/checkin",methods=["POST"])
@login_required
def challenge_checkin(cid):
    db=get_db();challenge=db.execute("SELECT * FROM savings_challenges WHERE id=? AND user_id=? AND challenge_type='no_spend'",(cid,g.user_id)).fetchone()
    if not challenge:abort(404)
    try:
        when=parse_date(request.form.get("check_on") or today().isoformat(),"check-in date");result=request.form.get("result")
        if result not in {"met","missed"} or when>today().isoformat() or not challenge["start_on"]<=when<=challenge["end_on"]:raise ValueError("Choose a valid current or past date inside this challenge.")
        if result=="met" and db.execute("SELECT 1 FROM transactions WHERE user_id=? AND type='expense' AND category_id=? AND occurred_on=? LIMIT 1",(g.user_id,challenge["category_id"],when)).fetchone():raise ValueError("Your ledger contains spending in that category on this date. Mark the day missed instead.")
        db.execute("INSERT INTO challenge_checkins(user_id,challenge_id,check_on,result) VALUES(?,?,?,?) ON CONFLICT(user_id,challenge_id,check_on) DO UPDATE SET result=excluded.result",(g.user_id,cid,when,result));db.commit();flash("No-spend check-in saved.","success")
    except ValueError as exc:db.rollback();flash(str(exc),"error")
    return redirect(url_for("main.challenges"))


@bp.route("/insights")
@login_required
def insights():
    db=get_db();start=(today()-timedelta(days=29)).isoformat();end=today().isoformat();messages=[]
    small=db.execute("SELECT COUNT(*) n,COALESCE(SUM(amount_paise),0) total FROM transactions WHERE user_id=? AND type='expense' AND occurred_on BETWEEN ? AND ? AND amount_paise<=100000",(g.user_id,start,end)).fetchone()
    if small["n"]>=5:messages.append(("Small expenses add up",f"{small['n']} expenses of ₹1,000 or less totalled {rupees(small['total'])} in the last 30 days."))
    top=db.execute("SELECT c.name,SUM(t.amount_paise) total FROM transactions t JOIN categories c ON c.id=t.category_id WHERE t.user_id=? AND t.type='expense' AND t.occurred_on BETWEEN ? AND ? GROUP BY c.id ORDER BY total DESC LIMIT 1",(g.user_id,start,end)).fetchone()
    if top:messages.append(("Highest-spend category",f"{top['name']} was your largest category at {rupees(top['total'])} over the last 30 days."))
    repeated=db.execute("SELECT description,COUNT(*) n,SUM(amount_paise) total FROM transactions WHERE user_id=? AND type='expense' AND occurred_on BETWEEN ? AND ? GROUP BY lower(description) HAVING COUNT(*)>=3 ORDER BY total DESC LIMIT 5",(g.user_id,start,end)).fetchall()
    overs=db.execute("SELECT c.name,b.limit_paise,COALESCE(SUM(t.amount_paise),0) spent FROM budgets b JOIN categories c ON c.id=b.category_id LEFT JOIN transactions t ON t.user_id=b.user_id AND t.category_id=b.category_id AND t.type='expense' AND t.occurred_on BETWEEN b.period_start AND b.period_end WHERE b.user_id=? AND b.period_start<=? AND b.period_end>=? GROUP BY b.id HAVING spent>b.limit_paise",(g.user_id,end,end)).fetchall()
    for r in overs:messages.append(("Budget exceeded",f"{r['name']} is {rupees(r['spent']-r['limit_paise'])} over its monthly limit."))
    expenses=db.execute("SELECT amount_paise FROM transactions WHERE user_id=? AND type='expense' AND occurred_on BETWEEN ? AND ? ORDER BY amount_paise DESC",(g.user_id,start,end)).fetchall()
    if len(expenses)>=3:
        avg=sum(r["amount_paise"] for r in expenses)//len(expenses)
        if avg and expenses[0]["amount_paise"]>=avg*2:messages.append(("One unusually large entry",f"Your largest expense, {rupees(expenses[0]['amount_paise'])}, was at least twice the average expense in this period."))
    for r in repeated:
        messages.append(("Possible recurring expense",f"“{r['description']}” appeared {r['n']} times for {rupees(r['total'])}. Check whether it is a subscription or habit you still want."))
    insight_categories=db.execute("SELECT COALESCE(c.name,'Uncategorized') name,SUM(t.amount_paise) total FROM transactions t LEFT JOIN categories c ON c.id=t.category_id AND (c.user_id=t.user_id OR c.user_id IS NULL) WHERE t.user_id=? AND t.type='expense' AND t.occurred_on BETWEEN ? AND ? GROUP BY COALESCE(c.name,'Uncategorized') ORDER BY total DESC",(g.user_id,start,end)).fetchall()
    pref=settings_row();month_start=today().replace(day=1).isoformat()
    cash=db.execute("SELECT COALESCE(SUM(CASE WHEN type='income' THEN amount_paise ELSE -amount_paise END),0) n FROM transactions WHERE user_id=? AND occurred_on BETWEEN ? AND ?",(g.user_id,month_start,end)).fetchone()["n"]
    next_items=commitments(db,g.user_id,today().isoformat(),(today()+timedelta(days=29)).isoformat())
    surplus=max(0,int(cash)-next_items.get("bill",0)-next_items.get("savings",0));suggestion=surplus//5
    safe=safe_to_spend(db,g.user_id,pref,today());suggestion=min(suggestion,safe["amount"]) if safe["available"] else suggestion
    return render_template("insights.html",title="Spending insights",messages=messages,suggestion=suggestion,suggestion_basis="20% of this month's recorded net cash flow after the next 30 days of scheduled bills and savings commitments. This is a starting point, not a required target." if suggestion else "There is no clear monthly surplus in the records yet. Add income, expenses, and commitments before setting a suggested target.",insight_categories=insight_categories,rupees=rupees)


@bp.route("/reports")
@login_required
def reports():
    db=get_db();start=request.args.get("from") or today().replace(day=1).isoformat();end=request.args.get("to") or today().isoformat()
    try:start=parse_date(start);end=parse_date(end)
    except ValueError:start=today().replace(day=1).isoformat();end=today().isoformat();flash("Report dates were invalid; showing this month.","error")
    rows=db.execute("SELECT type,COALESCE(SUM(amount_paise),0) total FROM transactions WHERE user_id=? AND occurred_on BETWEEN ? AND ? GROUP BY type",(g.user_id,start,end)).fetchall();totals={r["type"]:int(r["total"]) for r in rows}
    cats=db.execute("SELECT c.name,SUM(t.amount_paise) total FROM transactions t JOIN categories c ON c.id=t.category_id WHERE t.user_id=? AND t.type='expense' AND t.occurred_on BETWEEN ? AND ? GROUP BY c.id ORDER BY total DESC",(g.user_id,start,end)).fetchall()
    expense_rows=db.execute("SELECT id,amount_paise,category_id,description,occurred_on FROM transactions WHERE user_id=? AND type='expense' AND occurred_on BETWEEN ? AND ?",(g.user_id,start,end)).fetchall()
    ranked=c_bridge.rank_expenses(current_app.config["C_LIBRARY"],expense_rows)
    cat_ids=[r["id"] for r in db.execute("SELECT id FROM categories WHERE (user_id=? OR user_id IS NULL) AND kind='expense' ORDER BY id",(g.user_id,)).fetchall()]
    c_totals=c_bridge.category_totals(current_app.config["C_LIBRARY"],expense_rows,cat_ids)
    names={r["id"]:r["name"] for r in db.execute("SELECT id,name FROM categories WHERE (user_id=? OR user_id IS NULL) AND kind='expense'",(g.user_id,)).fetchall()}
    cats=sorted([{"name":names[cid],"total":total} for cid,total in c_totals.items() if total],key=lambda r:-r["total"])
    cashflow_trend=db.execute("SELECT strftime('%Y-%W',occurred_on) period,SUM(CASE WHEN type='income' THEN amount_paise ELSE 0 END) income,SUM(CASE WHEN type='expense' THEN amount_paise ELSE 0 END) expenses FROM transactions WHERE user_id=? AND occurred_on BETWEEN ? AND ? GROUP BY period ORDER BY period",(g.user_id,start,end)).fetchall()
    savings_trend=db.execute("SELECT strftime('%Y-%W',contributed_on) period,SUM(amount_paise) saved FROM goal_contributions WHERE user_id=? AND reversed_at IS NULL AND contributed_on BETWEEN ? AND ? GROUP BY period ORDER BY period",(g.user_id,start,end)).fetchall()
    streak=0;day=today()
    while True:
        has=db.execute("SELECT 1 FROM goal_contributions WHERE user_id=? AND reversed_at IS NULL AND contributed_on=? LIMIT 1",(g.user_id,day.isoformat())).fetchone()
        if not has:break
        streak+=1;day-=timedelta(days=1)
    week_start=(today()-timedelta(days=today().weekday())).isoformat()
    week=db.execute("SELECT type,COALESCE(SUM(amount_paise),0) total FROM transactions WHERE user_id=? AND occurred_on BETWEEN ? AND ? GROUP BY type",(g.user_id,week_start,today().isoformat())).fetchall()
    week_totals={r["type"]:r["total"] for r in week}
    weekly_top=db.execute("SELECT c.name,SUM(t.amount_paise) total FROM transactions t JOIN categories c ON c.id=t.category_id WHERE t.user_id=? AND t.type='expense' AND t.occurred_on BETWEEN ? AND ? GROUP BY c.id ORDER BY total DESC LIMIT 1",(g.user_id,week_start,today().isoformat())).fetchone()
    week_saved=db.execute("SELECT COALESCE(SUM(amount_paise),0) n FROM goal_contributions WHERE user_id=? AND reversed_at IS NULL AND contributed_on BETWEEN ? AND ?",(g.user_id,week_start,today().isoformat())).fetchone()["n"]
    budget_reports=[]
    for budget in db.execute("SELECT b.*,c.name category FROM budgets b JOIN categories c ON c.id=b.category_id WHERE b.user_id=? AND b.period_start<=? AND b.period_end>=? ORDER BY c.name",(g.user_id,end,start)).fetchall():
        range_start=max(start,budget["period_start"]);range_end=min(end,budget["period_end"])
        spent=db.execute("SELECT COALESCE(SUM(amount_paise),0) n FROM transactions WHERE user_id=? AND category_id=? AND type='expense' AND occurred_on BETWEEN ? AND ?",(g.user_id,budget["category_id"],range_start,range_end)).fetchone()["n"]
        budget_reports.append({"category":budget["category"],"limit":budget["limit_paise"],"spent":int(spent)})
    savings_reports=db.execute("SELECT g.id,g.name,g.target_paise,COALESCE(SUM(CASE WHEN c.reversed_at IS NULL THEN c.amount_paise ELSE 0 END),0) total_saved,COALESCE(SUM(CASE WHEN c.reversed_at IS NULL AND c.contributed_on BETWEEN ? AND ? THEN c.amount_paise ELSE 0 END),0) period_saved FROM savings_goals g LEFT JOIN goal_contributions c ON c.goal_id=g.id AND c.user_id=g.user_id WHERE g.user_id=? GROUP BY g.id ORDER BY g.status,g.name",(start,end,g.user_id)).fetchall()
    return render_template("reports.html",title="Reports",start=start,end=end,totals=totals,categories=cats,ranked=ranked,streak=streak,week_totals=week_totals,weekly_saved=int(week_saved),weekly_top=weekly_top,budget_reports=budget_reports,savings_reports=savings_reports,cashflow_trend=cashflow_trend,savings_trend=savings_trend,c_ready=c_bridge.available(current_app.config["C_LIBRARY"]),rupees=rupees)


@bp.route("/reports.csv")
@login_required
def export_csv():
    start=request.args.get("from") or "0001-01-01";end=request.args.get("to") or "9999-12-31"
    try:start=parse_date(start);end=parse_date(end)
    except ValueError:abort(400)
    rows=get_db().execute("SELECT t.id,t.occurred_on,t.type,t.description,t.amount_paise,c.name category,t.notes FROM transactions t LEFT JOIN categories c ON c.id=t.category_id WHERE t.user_id=? AND t.occurred_on BETWEEN ? AND ? ORDER BY t.occurred_on,t.id",(g.user_id,start,end)).fetchall()
    output=io.StringIO();writer=csv.writer(output);writer.writerow(["ID","Date","Type","Description","Amount (INR)","Category","Notes"])
    for r in rows:
        def safe_cell(value):
            text=str(value or "")
            if text.lstrip(" \t\r\n")[:1] in {"=","+","-","@"}:return "'"+text
            return text
        writer.writerow([r["id"],r["occurred_on"],r["type"],safe_cell(r["description"]),f"{Decimal(r['amount_paise'])/100:.2f}",safe_cell(r["category"] or "Uncategorized"),safe_cell(r["notes"])])
    data=io.BytesIO(output.getvalue().encode("utf-8-sig"));return send_file(data,mimetype="text/csv; charset=utf-8",as_attachment=True,download_name=f"smartspend-{start}-to-{end}.csv")


@bp.route("/settings",methods=["GET","POST"])
@login_required
def settings():
    db=get_db();user=db.execute("SELECT * FROM users WHERE id=?",(g.user_id,)).fetchone();pref=settings_row()
    if request.method=="POST":
        action=request.form.get("action")
        try:
            if action=="profile":
                name=(request.form.get("display_name") or "").strip()[:60];email=(request.form.get("email") or "").strip().lower()
                if not name or "@" not in email:raise ValueError("Enter a valid name and email.")
                db.execute("UPDATE users SET display_name=?,email=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(name,email,g.user_id))
            elif action=="password":
                old=request.form.get("current_password") or "";new=request.form.get("new_password") or ""
                if not check_password_hash(user["password_hash"],old) or len(new)<10:raise ValueError("Current password did not match, or the new password is shorter than 10 characters.")
                db.execute("UPDATE users SET password_hash=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(generate_password_hash(new),g.user_id))
            elif action=="finance":
                buffer=parse_paise(request.form.get("buffer"),allow_zero=True) if request.form.get("buffer") else 0;horizon=int(request.form.get("horizon") or 30)
                if not 1<=horizon<=365:raise ValueError("Planning horizon must be between 1 and 365 days.")
                balance=parse_paise(request.form.get("balance"),allow_zero=True,allow_negative=True) if request.form.get("balance") else None
                asof=parse_date(request.form.get("balance_as_of"),"balance date") if balance is not None else None
                db.execute("UPDATE user_settings SET default_buffer_paise=?,planning_horizon_days=?,available_balance_paise=?,balance_as_of_date=?,balance_is_demo=0 WHERE user_id=?",(buffer,horizon,balance,asof,g.user_id))
            else:raise ValueError("Unknown settings action.")
            db.commit();flash("Settings saved.","success");return redirect(url_for("main.settings"))
        except Exception as exc:db.rollback();flash(str(exc) if isinstance(exc,ValueError) else "That change could not be saved. Check that the email is not already in use.","error")
    return render_template("settings.html",title="Settings",user=user,pref=pref,rupees=rupees)


@bp.route("/settings/avatar",methods=["POST"])
@login_required
def avatar_upload():
    from PIL import ImageOps
    db=get_db();upload=request.files.get("avatar")
    if not upload or not upload.filename:flash("Choose an image first.","error");return redirect(url_for("main.settings"))
    if len(upload.read())>2*1024*1024:flash("Avatar must be 2 MB or smaller.","error");return redirect(url_for("main.settings"))
    upload.stream.seek(0)
    try:
        image=Image.open(upload.stream);image.verify();upload.stream.seek(0);image=Image.open(upload.stream)
        if image.format not in {"PNG","JPEG","WEBP"}:raise ValueError("Use a PNG, JPEG, or WebP image.")
        if image.width>5000 or image.height>5000:raise ValueError("Image dimensions are too large.")
        image=ImageOps.exif_transpose(image).convert("RGB");image.thumbnail((512,512))
        key=secrets.token_hex(24)+".jpg";folder=Path(current_app.config["UPLOAD_DIR"]);folder.mkdir(parents=True,exist_ok=True);image.save(folder/key,"JPEG",quality=88,optimize=True)
        old=db.execute("SELECT avatar_storage_key FROM users WHERE id=?",(g.user_id,)).fetchone()[0]
        db.execute("UPDATE users SET avatar_storage_key=? WHERE id=?",(key,g.user_id));db.commit()
        if old:
            try:(folder/secure_filename(old)).unlink(missing_ok=True)
            except OSError:current_app.logger.warning("Could not remove replaced avatar")
        flash("Profile photo updated.","success")
    except (UnidentifiedImageError, OSError, ValueError) as exc:flash(str(exc) if isinstance(exc,ValueError) else "That image could not be read.","error")
    return redirect(url_for("main.settings"))


@bp.route("/avatar/<key>")
@login_required
def avatar(key):
    stored=get_db().execute("SELECT avatar_storage_key FROM users WHERE id=?",(g.user_id,)).fetchone()
    if not stored or not stored[0] or stored[0]!=key:abort(404)
    path=Path(current_app.config["UPLOAD_DIR"])/secure_filename(key)
    if not path.is_file():abort(404)
    return send_file(path,mimetype="image/jpeg",max_age=0)


@bp.route("/settings/avatar/remove",methods=["POST"])
@login_required
def avatar_remove():
    db=get_db();row=db.execute("SELECT avatar_storage_key FROM users WHERE id=?",(g.user_id,)).fetchone();db.execute("UPDATE users SET avatar_storage_key=NULL WHERE id=?",(g.user_id,));db.commit()
    if row and row[0]:
        try:(Path(current_app.config["UPLOAD_DIR"])/secure_filename(row[0])).unlink(missing_ok=True)
        except OSError:current_app.logger.warning("Could not remove avatar file")
    flash("Profile photo removed.","success");return redirect(url_for("main.settings"))


@bp.route("/settings/demo/reset",methods=["POST"])
@login_required
def reset_demo():
    db=get_db();db.execute("BEGIN IMMEDIATE")
    db.execute("DELETE FROM undo_events WHERE user_id=? AND entity_id IN (SELECT id FROM transactions WHERE user_id=? AND source='demo')",(g.user_id,g.user_id))
    db.execute("DELETE FROM transactions WHERE user_id=? AND source='demo'",(g.user_id,))
    db.execute("DELETE FROM goal_contributions WHERE user_id=? AND is_demo=1",(g.user_id,))
    db.execute("DELETE FROM savings_challenges WHERE user_id=? AND is_demo=1",(g.user_id,))
    db.execute("DELETE FROM savings_goals WHERE user_id=? AND is_demo=1",(g.user_id,))
    db.execute("DELETE FROM scheduled_commitments WHERE user_id=? AND is_demo=1",(g.user_id,))
    db.execute("DELETE FROM cooling_off_purchases WHERE user_id=? AND is_demo=1",(g.user_id,))
    db.execute("DELETE FROM budgets WHERE user_id=? AND is_demo=1",(g.user_id,))
    db.execute("DELETE FROM challenge_checkins WHERE user_id=? AND challenge_id IN (SELECT id FROM savings_challenges WHERE user_id=? AND is_demo=1)",(g.user_id,g.user_id))
    db.execute("UPDATE user_settings SET available_balance_paise=NULL,balance_as_of_date=NULL,default_buffer_paise=0,balance_is_demo=0 WHERE user_id=? AND balance_is_demo=1",(g.user_id,))
    db.commit();flash("Demo records were removed.","success");return redirect(url_for("main.settings"))
