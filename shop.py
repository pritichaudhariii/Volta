"""Shop blueprint — catalog, product detail, cart, checkout, orders."""

from __future__ import annotations

import math

from flask import (Blueprint, abort, flash, g, redirect, render_template,
                   request, session, url_for)

from . import login_required
from .db import execute, get_db, query

bp = Blueprint("shop", __name__)

PER_PAGE = 8
FREE_SHIPPING_CENTS = 10000   # free shipping over $100
SHIPPING_CENTS = 900
TAX_RATE = 0.10


# ---------------------------------------------------------------- catalog

PRODUCT_LIST_SQL = """
    SELECT p.*,
           COALESCE(AVG(r.rating), 0) AS rating,
           COUNT(r.id)                AS review_count
    FROM products p LEFT JOIN reviews r ON r.product_id = p.id
    {where}
    GROUP BY p.id
    {order}
    LIMIT ? OFFSET ?
"""


@bp.route("/")
def home():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    page = max(1, request.args.get("page", 1, type=int))

    where, args = [], []
    if q:
        where.append("(p.name LIKE ? OR p.brand LIKE ? OR p.description LIKE ?)")
        args += [f"%{q}%"] * 3
    if category:
        where.append("p.category = ?")
        args.append(category)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    total = query(
        f"SELECT COUNT(*) AS n FROM products p {where_sql}", tuple(args), one=True
    )["n"]
    pages = max(1, math.ceil(total / PER_PAGE))
    page = min(page, pages)

    products = query(
        PRODUCT_LIST_SQL.format(where=where_sql, order="ORDER BY p.id"),
        tuple(args) + (PER_PAGE, (page - 1) * PER_PAGE),
    )
    categories = [r["category"] for r in query(
        "SELECT DISTINCT category FROM products ORDER BY category")]

    return render_template(
        "home.html", products=products, categories=categories,
        q=q, category=category, page=page, pages=pages, total=total,
    )


@bp.route("/product/<slug>")
def product(slug: str):
    item = query(
        PRODUCT_LIST_SQL.format(where="WHERE p.slug = ?", order=""),
        (slug, 1, 0), one=True,
    )
    if not item or not item.get("id"):
        abort(404)
    reviews = query(
        """SELECT r.*, u.name AS user_name FROM reviews r
           JOIN users u ON u.id = r.user_id
           WHERE r.product_id = ? ORDER BY r.created_at DESC""",
        (item["id"],),
    )
    my_review = None
    if g.user:
        my_review = query(
            "SELECT id FROM reviews WHERE product_id = ? AND user_id = ?",
            (item["id"], g.user["id"]), one=True,
        )
    return render_template("product.html", p=item, reviews=reviews, my_review=my_review)


@bp.route("/product/<slug>/review", methods=["POST"])
@login_required
def add_review(slug: str):
    item = query("SELECT id FROM products WHERE slug = ?", (slug,), one=True)
    if not item:
        abort(404)
    rating = request.form.get("rating", type=int)
    comment = request.form.get("comment", "").strip()
    if not rating or not 1 <= rating <= 5:
        flash("Pick a rating from 1 to 5.", "error")
    else:
        try:
            execute(
                "INSERT INTO reviews (product_id, user_id, rating, comment) VALUES (?, ?, ?, ?)",
                (item["id"], g.user["id"], rating, comment),
            )
            flash("Review posted — thanks.", "success")
        except Exception:
            flash("You've already reviewed this product.", "error")
    return redirect(url_for("shop.product", slug=slug))


# ---------------------------------------------------------------- cart

def _cart() -> dict[str, int]:
    return session.setdefault("cart", {})


def _cart_rows():
    cart = _cart()
    if not cart:
        return [], 0
    placeholders = ",".join("?" * len(cart))
    products = query(
        f"SELECT * FROM products WHERE id IN ({placeholders})",
        tuple(int(k) for k in cart),
    )
    rows, subtotal = [], 0
    for p in products:
        qty = min(cart[str(p["id"])], max(p["stock"], 1))
        line = p["price_cents"] * qty
        subtotal += line
        rows.append({**p, "qty": qty, "line_cents": line})
    return rows, subtotal


@bp.route("/cart")
def cart():
    rows, subtotal = _cart_rows()
    return render_template("cart.html", rows=rows, subtotal=subtotal)


@bp.route("/cart/add/<int:product_id>", methods=["POST"])
def cart_add(product_id: int):
    p = query("SELECT id, name, stock FROM products WHERE id = ?", (product_id,), one=True)
    if not p:
        abort(404)
    if p["stock"] < 1:
        flash(f"{p['name']} is out of stock.", "error")
        return redirect(request.referrer or url_for("shop.home"))
    qty = max(1, request.form.get("qty", 1, type=int))
    cart = _cart()
    cart[str(product_id)] = min(p["stock"], cart.get(str(product_id), 0) + qty)
    session.modified = True
    flash(f"Added {p['name']} to your cart.", "success")
    return redirect(request.referrer or url_for("shop.cart"))


@bp.route("/cart/update/<int:product_id>", methods=["POST"])
def cart_update(product_id: int):
    qty = request.form.get("qty", 0, type=int)
    cart = _cart()
    key = str(product_id)
    if qty <= 0:
        cart.pop(key, None)
    else:
        p = query("SELECT stock FROM products WHERE id = ?", (product_id,), one=True)
        cart[key] = min(qty, p["stock"] if p else qty)
    session.modified = True
    return redirect(url_for("shop.cart"))


# ---------------------------------------------------------------- checkout

def _totals(subtotal: int) -> dict:
    shipping = 0 if subtotal >= FREE_SHIPPING_CENTS or subtotal == 0 else SHIPPING_CENTS
    tax = round(subtotal * TAX_RATE)
    return {
        "items_cents": subtotal,
        "shipping_cents": shipping,
        "tax_cents": tax,
        "total_cents": subtotal + shipping + tax,
    }


@bp.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    rows, subtotal = _cart_rows()
    if not rows:
        flash("Your cart is empty.", "info")
        return redirect(url_for("shop.home"))
    totals = _totals(subtotal)

    if request.method == "POST":
        fields = {f: request.form.get(f, "").strip()
                  for f in ("ship_name", "ship_address", "ship_city",
                            "ship_postal", "ship_country")}
        if not all(fields.values()):
            flash("Fill in every shipping field.", "error")
            return render_template("checkout.html", rows=rows, totals=totals, **fields)

        db = get_db()
        cur = db.cursor()
        cur.execute(
            """INSERT INTO orders (user_id, ship_name, ship_address, ship_city,
                                   ship_postal, ship_country, payment_method,
                                   items_cents, shipping_cents, tax_cents, total_cents)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (g.user["id"], *fields.values(),
             request.form.get("payment_method", "demo"),
             totals["items_cents"], totals["shipping_cents"],
             totals["tax_cents"], totals["total_cents"]),
        )
        order_id = cur.lastrowid
        for r in rows:
            cur.execute(
                """INSERT INTO order_items (order_id, product_id, name, price_cents, qty)
                   VALUES (?, ?, ?, ?, ?)""",
                (order_id, r["id"], r["name"], r["price_cents"], r["qty"]),
            )
            cur.execute("UPDATE products SET stock = stock - ? WHERE id = ?",
                        (r["qty"], r["id"]))
        db.commit()
        session["cart"] = {}
        flash("Order placed.", "success")
        return redirect(url_for("shop.order", order_id=order_id))

    return render_template("checkout.html", rows=rows, totals=totals,
                           ship_name=g.user["name"], ship_address="",
                           ship_city="", ship_postal="", ship_country="")


@bp.route("/orders/<int:order_id>")
@login_required
def order(order_id: int):
    o = query("SELECT * FROM orders WHERE id = ?", (order_id,), one=True)
    if not o or (o["user_id"] != g.user["id"] and not g.user["is_admin"]):
        abort(404)
    items = query("SELECT * FROM order_items WHERE order_id = ?", (order_id,))
    return render_template("order.html", o=o, items=items)


@bp.route("/orders/<int:order_id>/pay", methods=["POST"])
@login_required
def pay(order_id: int):
    """Demo payment — in production, swap for Stripe / PayPal webhooks."""
    o = query("SELECT * FROM orders WHERE id = ?", (order_id,), one=True)
    if not o or o["user_id"] != g.user["id"]:
        abort(404)
    if o["status"] == "placed":
        execute("UPDATE orders SET status = 'paid', paid_at = datetime('now') WHERE id = ?",
                (order_id,))
        flash("Payment confirmed (demo gateway).", "success")
    return redirect(url_for("shop.order", order_id=order_id))
