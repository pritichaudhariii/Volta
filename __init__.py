"""VOLTA — application factory."""

from __future__ import annotations

import functools
import os

from flask import Flask, flash, g, redirect, session, url_for

from . import db as database


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
    app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024

    database.init_db()
    app.teardown_appcontext(database.close_db)

    # ---- template filters -------------------------------------------------
    @app.template_filter("money")
    def money(cents: int | None) -> str:
        return f"${(cents or 0) / 100:,.2f}"

    @app.template_filter("stars")
    def stars(rating: float | None) -> str:
        r = round(rating or 0)
        return "★" * r + "☆" * (5 - r)

    # ---- current user + cart badge ---------------------------------------
    @app.before_request
    def load_user():
        user_id = session.get("user_id")
        g.user = (
            database.query(
                "SELECT id, name, email, is_admin FROM users WHERE id = ?",
                (user_id,), one=True,
            )
            if user_id else None
        )
        cart = session.get("cart", {})
        g.cart_count = sum(cart.values())

    @app.context_processor
    def inject_globals():
        return {"current_user": g.user, "cart_count": g.cart_count}

    # ---- blueprints -------------------------------------------------------
    from . import admin, auth, shop
    app.register_blueprint(shop.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(admin.bp)

    return app


# ---------------------------------------------------------------- decorators

def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Sign in to continue.", "info")
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None or not g.user["is_admin"]:
            flash("That page needs an admin account.", "error")
            return redirect(url_for("shop.home"))
        return view(*args, **kwargs)
    return wrapped
