"""Auth blueprint — register, login, logout, profile."""

from __future__ import annotations

from flask import (Blueprint, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from . import login_required
from .db import execute, query

bp = Blueprint("auth", __name__)


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        error = None
        if not name or not email or "@" not in email:
            error = "A name and a valid email are required."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif query("SELECT id FROM users WHERE email = ?", (email,), one=True):
            error = "An account with that email already exists."

        if error:
            flash(error, "error")
        else:
            user_id = execute(
                "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password)),
            )
            session["user_id"] = user_id
            flash(f"Welcome to VOLTA, {name}.", "success")
            return redirect(url_for("shop.home"))

    return render_template("register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = query("SELECT * FROM users WHERE email = ?", (email,), one=True)

        if user is None or not check_password_hash(user["password"], password):
            flash("Email or password is incorrect.", "error")
        else:
            session["user_id"] = user["id"]
            flash(f"Signed in as {user['name']}.", "success")
            next_url = request.args.get("next")
            return redirect(next_url or url_for("shop.home"))

    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("Signed out.", "info")
    return redirect(url_for("shop.home"))


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        password = request.form.get("password", "")
        if name:
            execute("UPDATE users SET name = ? WHERE id = ?", (name, g.user["id"]))
        if password:
            if len(password) < 8:
                flash("New password must be at least 8 characters.", "error")
                return redirect(url_for("auth.profile"))
            execute(
                "UPDATE users SET password = ? WHERE id = ?",
                (generate_password_hash(password), g.user["id"]),
            )
        flash("Profile updated.", "success")
        return redirect(url_for("auth.profile"))

    orders = query(
        """SELECT o.*, COUNT(i.id) AS item_count
           FROM orders o LEFT JOIN order_items i ON i.order_id = o.id
           WHERE o.user_id = ?
           GROUP BY o.id ORDER BY o.created_at DESC""",
        (g.user["id"],),
    )
    return render_template("profile.html", orders=orders)
