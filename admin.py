"""Admin blueprint — dashboard, product CRUD, orders, users."""

from __future__ import annotations

import re

from flask import (Blueprint, abort, flash, redirect, render_template,
                   request, url_for)

from . import admin_required
from .db import execute, query

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@admin_required
def dashboard():
    stats = {
        "products": query("SELECT COUNT(*) n FROM products", one=True)["n"],
        "orders": query("SELECT COUNT(*) n FROM orders", one=True)["n"],
        "users": query("SELECT COUNT(*) n FROM users", one=True)["n"],
        "revenue_cents": query(
            "SELECT COALESCE(SUM(total_cents), 0) n FROM orders WHERE status != 'placed'",
            one=True)["n"],
        "low_stock": query(
            "SELECT name, stock FROM products WHERE stock <= 5 ORDER BY stock"),
        "recent_orders": query(
            """SELECT o.*, u.name AS user_name FROM orders o
               JOIN users u ON u.id = o.user_id
               ORDER BY o.created_at DESC LIMIT 5"""),
    }
    return render_template("admin/dashboard.html", s=stats)


# ---------------------------------------------------------------- products

@bp.route("/products")
@admin_required
def products():
    rows = query("SELECT * FROM products ORDER BY id")
    return render_template("admin/products.html", products=rows)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    base, i = slug, 2
    while query("SELECT 1 FROM products WHERE slug = ?", (slug,), one=True):
        slug = f"{base}-{i}"
        i += 1
    return slug


@bp.route("/products/new", methods=["GET", "POST"])
@bp.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def product_form(product_id: int | None = None):
    p = None
    if product_id:
        p = query("SELECT * FROM products WHERE id = ?", (product_id,), one=True)
        if not p:
            abort(404)

    if request.method == "POST":
        fields = {f: request.form.get(f, "").strip()
                  for f in ("name", "sku", "category", "brand", "description")}
        price = request.form.get("price", type=float)
        stock = request.form.get("stock", type=int)

        if not all(fields.values()) or price is None or price < 0 or stock is None or stock < 0:
            flash("Every field is required; price and stock must be non-negative.", "error")
            return render_template("admin/product_form.html", p={**(p or {}), **fields,
                                   "price_cents": int((price or 0) * 100), "stock": stock or 0})

        price_cents = round(price * 100)
        if p:
            execute(
                """UPDATE products SET name=?, sku=?, category=?, brand=?, description=?,
                   price_cents=?, stock=? WHERE id=?""",
                (*fields.values(), price_cents, stock, p["id"]),
            )
            flash("Product updated.", "success")
        else:
            execute(
                """INSERT INTO products (name, slug, sku, category, brand, description,
                   price_cents, stock, image) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (fields["name"], _slugify(fields["name"]), fields["sku"],
                 fields["category"], fields["brand"], fields["description"],
                 price_cents, stock, "placeholder.svg"),
            )
            flash("Product created.", "success")
        return redirect(url_for("admin.products"))

    return render_template("admin/product_form.html", p=p)


@bp.route("/products/<int:product_id>/delete", methods=["POST"])
@admin_required
def product_delete(product_id: int):
    execute("DELETE FROM products WHERE id = ?", (product_id,))
    flash("Product deleted.", "info")
    return redirect(url_for("admin.products"))


# ---------------------------------------------------------------- orders

@bp.route("/orders")
@admin_required
def orders():
    rows = query(
        """SELECT o.*, u.name AS user_name, u.email FROM orders o
           JOIN users u ON u.id = o.user_id ORDER BY o.created_at DESC""")
    return render_template("admin/orders.html", orders=rows)


@bp.route("/orders/<int:order_id>/deliver", methods=["POST"])
@admin_required
def deliver(order_id: int):
    execute(
        """UPDATE orders SET status = 'delivered', delivered_at = datetime('now')
           WHERE id = ? AND status = 'paid'""",
        (order_id,),
    )
    flash(f"Order #{order_id} marked delivered.", "success")
    return redirect(request.referrer or url_for("admin.orders"))


# ---------------------------------------------------------------- users

@bp.route("/users")
@admin_required
def users():
    rows = query(
        """SELECT u.id, u.name, u.email, u.is_admin, u.created_at,
                  COUNT(o.id) AS order_count
           FROM users u LEFT JOIN orders o ON o.user_id = u.id
           GROUP BY u.id ORDER BY u.id""")
    return render_template("admin/users.html", users=rows)
