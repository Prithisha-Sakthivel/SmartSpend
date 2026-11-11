from flask import Flask, g, session, render_template
from datetime import date, datetime, timezone, timedelta
import os
import hmac
from config import Config
from app.db import get_db, init_app as init_db
from app.routes import bp
from app.services.money import rupees


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    # All templates share the canonical formatter; its input unit is integer paise.
    app.jinja_env.globals["rupees"] = rupees
    for key in ("MAIL_HOST", "MAIL_PORT", "MAIL_USER", "MAIL_PASSWORD", "MAIL_FROM"):
        if os.environ.get("SMARTSPEND_" + key):
            app.config[key] = os.environ["SMARTSPEND_" + key]
    if test_config:
        app.config.update(test_config)
    secret = str(app.config["SECRET_KEY"] or "")
    if not app.config["DEBUG"] and (len(secret) < 32 or secret == "local-development-key-change-me" or secret.startswith("replace-")):
        raise RuntimeError("Set SMARTSPEND_SECRET to a unique random value of at least 32 characters before running with debug disabled.")
    init_db(app)
    app.register_blueprint(bp)

    @app.before_request
    def csrf_guard():
        from flask import request, abort
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            supplied = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
            expected = session.get("csrf_token")
            if not expected or not supplied or not hmac.compare_digest(str(supplied), str(expected)):
                abort(400, "Invalid request token. Reload the page and try again.")

    @app.context_processor
    def globals_for_templates():
        import secrets
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)
        user = None
        if session.get("user_id"):
            user = get_db().execute("SELECT id,display_name,email,avatar_storage_key FROM users WHERE id=? AND is_active=1", (session["user_id"],)).fetchone()
        now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
        local_today=now.date()
        return {"current_user": user, "csrf_token": session["csrf_token"], "today_value": local_today.isoformat(), "month_start": local_today.replace(day=1).isoformat(), "now_hour": now.hour, "now_label": now.strftime("%A, %d %B %Y")}

    @app.errorhandler(404)
    def not_found(_):
        return render_template("error.html", title="Page not found", message="That page is not here."), 404

    @app.errorhandler(500)
    def server_error(_):
        return render_template("error.html", title="Something went wrong", message="Please try again. Your data has not been changed unless you saw a success message."), 500

    return app
