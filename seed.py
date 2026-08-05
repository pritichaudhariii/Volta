"""Seed the database with demo users, products (with generated SVG art),
and a few reviews. Idempotent: wipes and refills product/user tables.

Run:  python -m app.seed
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from werkzeug.security import generate_password_hash

from .db import DB_PATH, SCHEMA

IMG_DIR = Path(__file__).resolve().parent / "static" / "img"

# ---------------------------------------------------------------------------
# SVG product art — duotone geometric illustrations, generated locally so the
# store works fully offline with zero external image dependencies.
# ---------------------------------------------------------------------------

PALETTES = {
    "audio":    ("#1B2240", "#4257E0"),
    "keys":     ("#26221B", "#E08A1F"),
    "video":    ("#1D2B26", "#2FA57A"),
    "power":    ("#2B1D2A", "#C24FA0"),
    "display":  ("#20242B", "#5C8DEB"),
    "storage":  ("#2B241D", "#C9A24B"),
}


def _svg(kind: str, palette: str, label: str) -> str:
    bg, fg = PALETTES[palette]
    shapes = {
        "headphones": f"""
    <path d="M130 260 a130 130 0 0 1 260 0" fill="none" stroke="{fg}" stroke-width="26" stroke-linecap="round"/>
    <rect x="108" y="252" width="58" height="112" rx="24" fill="{fg}"/>
    <rect x="354" y="252" width="58" height="112" rx="24" fill="{fg}"/>
    <rect x="122" y="268" width="30" height="80" rx="14" fill="{bg}" opacity="0.55"/>
    <rect x="368" y="268" width="30" height="80" rx="14" fill="{bg}" opacity="0.55"/>""",
        "keyboard": f"""
    <rect x="80" y="180" width="360" height="150" rx="18" fill="{fg}"/>
    {''.join(f'<rect x="{100 + c * 44}" y="{200 + r * 44}" width="34" height="34" rx="7" fill="{bg}" opacity="0.75"/>' for r in range(2) for c in range(8))}
    <rect x="144" y="288" width="232" height="26" rx="8" fill="{bg}" opacity="0.75"/>""",
        "camera": f"""
    <rect x="96" y="170" width="328" height="190" rx="26" fill="{fg}"/>
    <circle cx="260" cy="265" r="70" fill="{bg}"/>
    <circle cx="260" cy="265" r="46" fill="{fg}" opacity="0.6"/>
    <circle cx="238" cy="243" r="12" fill="#FFFFFF" opacity="0.7"/>
    <rect x="130" y="140" width="90" height="46" rx="12" fill="{fg}"/>
    <circle cx="392" cy="200" r="10" fill="#FFFFFF" opacity="0.85"/>""",
        "charger": f"""
    <rect x="150" y="120" width="220" height="290" rx="34" fill="{fg}"/>
    <path d="M275 165 L225 275 h42 l-22 90 78 -128 h-46 l30 -72 z" fill="{bg}"/>
    <rect x="150" y="120" width="220" height="290" rx="34" fill="none" stroke="{bg}" stroke-opacity="0.3" stroke-width="6"/>""",
        "monitor": f"""
    <rect x="76" y="132" width="368" height="216" rx="16" fill="{fg}"/>
    <rect x="96" y="152" width="328" height="176" rx="8" fill="{bg}"/>
    <path d="M96 328 L250 210 L330 268 L424 190 V328 Z" fill="{fg}" opacity="0.5"/>
    <rect x="228" y="352" width="64" height="34" fill="{fg}"/>
    <rect x="180" y="386" width="160" height="16" rx="8" fill="{fg}"/>""",
        "drive": f"""
    <rect x="140" y="120" width="240" height="300" rx="26" fill="{fg}"/>
    <rect x="164" y="150" width="192" height="90" rx="12" fill="{bg}" opacity="0.7"/>
    <circle cx="260" cy="330" r="34" fill="{bg}"/>
    <circle cx="260" cy="330" r="14" fill="{fg}"/>
    <rect x="164" y="150" width="192" height="20" rx="10" fill="#FFFFFF" opacity="0.25"/>""",
        "speaker": f"""
    <rect x="150" y="100" width="220" height="320" rx="30" fill="{fg}"/>
    <circle cx="260" cy="200" r="52" fill="{bg}"/>
    <circle cx="260" cy="200" r="26" fill="{fg}" opacity="0.55"/>
    <circle cx="260" cy="330" r="66" fill="{bg}"/>
    <circle cx="260" cy="330" r="36" fill="{fg}" opacity="0.55"/>
    <circle cx="260" cy="330" r="12" fill="{bg}"/>""",
        "mouse": f"""
    <path d="M175 200 a85 85 0 0 1 170 0 v90 a85 85 0 0 1 -170 0 z" fill="{fg}"/>
    <rect x="252" y="150" width="16" height="60" rx="8" fill="{bg}"/>
    <path d="M260 118 v-0" stroke="{fg}"/>
    <path d="M175 240 h170" stroke="{bg}" stroke-width="6" opacity="0.5"/>""",
    }
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 520 480">
  <rect width="520" height="480" fill="{bg}"/>
  <circle cx="452" cy="60" r="120" fill="{fg}" opacity="0.12"/>
  <circle cx="60" cy="430" r="90" fill="{fg}" opacity="0.10"/>
  {shapes[kind]}
  <text x="34" y="446" font-family="ui-monospace, monospace" font-size="20"
        letter-spacing="4" fill="#FFFFFF" opacity="0.55">{label}</text>
</svg>
"""


PRODUCTS = [
    dict(kind="headphones", palette="audio", name="Aria ANC Headphones", brand="Fieldwave",
         category="Audio", price_cents=24900, stock=12, sku="VLT-AUD-001",
         description="Over-ear active noise cancelling headphones with 42-hour battery life, "
         "multipoint Bluetooth 5.3, and a fold-flat travel hinge. Includes USB-C fast charge: "
         "ten minutes on the cable buys five hours of playback."),
    dict(kind="keyboard", palette="keys", name="Tactile 75 Keyboard", brand="Keyforge",
         category="Peripherals", price_cents=15900, stock=25, sku="VLT-PER-002",
         description="Hot-swappable 75% mechanical keyboard with gasket mount, pre-lubed linear "
         "switches, and south-facing RGB. Aluminum case, tri-mode connectivity (USB-C, 2.4G, BT)."),
    dict(kind="camera", palette="video", name="Meridian 4K Webcam", brand="Optiq",
         category="Video", price_cents=12900, stock=18, sku="VLT-VID-003",
         description="4K30 / 1080p60 webcam with a Sony sensor, dual noise-cancelling mics, "
         "auto-framing, and a physical privacy shutter. Works without drivers on every OS."),
    dict(kind="charger", palette="power", name="Surge 100W GaN Charger", brand="Voltcore",
         category="Power", price_cents=6900, stock=40, sku="VLT-PWR-004",
         description="Palm-sized 100W GaN charger with two USB-C and one USB-A port. Charges a "
         "laptop, phone, and earbuds simultaneously with intelligent power distribution."),
    dict(kind="monitor", palette="display", name="Vista 27 QHD Monitor", brand="Clearline",
         category="Displays", price_cents=32900, stock=7, sku="VLT-DSP-005",
         description="27-inch QHD IPS panel at 165Hz with 98% DCI-P3 coverage, height-adjustable "
         "stand, and USB-C with 65W power delivery — a one-cable docking setup."),
    dict(kind="drive", palette="storage", name="Vault 2TB NVMe SSD", brand="Datakeep",
         category="Storage", price_cents=18900, stock=15, sku="VLT-STO-006",
         description="Portable USB4 NVMe drive hitting 3,800 MB/s reads. Anodized aluminum shell, "
         "IP54 dust and splash resistance, and hardware AES-256 encryption."),
    dict(kind="speaker", palette="audio", name="Pillar Bookshelf Speaker", brand="Fieldwave",
         category="Audio", price_cents=21900, stock=9, sku="VLT-AUD-007",
         description="Powered bookshelf speaker pair with 5-inch woven-fiber woofers, silk dome "
         "tweeters, and built-in phono, optical, and Bluetooth aptX-HD inputs."),
    dict(kind="mouse", palette="keys", name="Glide Pro Wireless Mouse", brand="Keyforge",
         category="Peripherals", price_cents=8900, stock=0, sku="VLT-PER-008",
         description="59-gram wireless mouse with a 26K sensor, optical switches rated for 90M "
         "clicks, and 110-hour battery. Currently out of stock — restock lands next week."),
]

USERS = [
    ("Riley Okafor", "admin@volta.dev", "admin123", 1),
    ("Jordan Micah", "jordan@example.com", "password123", 0),
    ("Priya Sharma", "priya@example.com", "password123", 0),
]

REVIEWS = [  # (product_index, user_index, rating, comment)
    (0, 1, 5, "The ANC is genuinely startling — my office went silent. Battery claim holds up."),
    (0, 2, 4, "Comfortable for long sessions. Wish the case were slimmer, but the sound is superb."),
    (1, 1, 5, "Thocky out of the box. Hot-swap sockets made switch experiments painless."),
    (2, 2, 4, "Sharp image and the auto-framing actually tracks well. Mic is fine, not amazing."),
    (4, 1, 5, "One USB-C cable to my laptop and everything just works. Panel is gorgeous."),
    (5, 2, 5, "Moved a 400GB project in under two minutes. It barely got warm."),
]


def seed() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    IMG_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    cur = conn.cursor()

    cur.execute("DELETE FROM order_items")
    cur.execute("DELETE FROM orders")
    cur.execute("DELETE FROM reviews")
    cur.execute("DELETE FROM products")
    cur.execute("DELETE FROM users")

    user_ids = []
    for name, email, password, is_admin in USERS:
        cur.execute(
            "INSERT INTO users (name, email, password, is_admin) VALUES (?, ?, ?, ?)",
            (name, email, generate_password_hash(password), is_admin),
        )
        user_ids.append(cur.lastrowid)

    product_ids = []
    for p in PRODUCTS:
        slug = p["name"].lower().replace(" ", "-")
        image = f"{slug}.svg"
        (IMG_DIR / image).write_text(_svg(p["kind"], p["palette"], p["sku"]))
        cur.execute(
            """INSERT INTO products
               (name, slug, sku, category, brand, description, price_cents, stock, image)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (p["name"], slug, p["sku"], p["category"], p["brand"],
             p["description"], p["price_cents"], p["stock"], image),
        )
        product_ids.append(cur.lastrowid)

    for p_idx, u_idx, rating, comment in REVIEWS:
        cur.execute(
            "INSERT INTO reviews (product_id, user_id, rating, comment) VALUES (?, ?, ?, ?)",
            (product_ids[p_idx], user_ids[u_idx], rating, comment),
        )

    conn.commit()
    conn.close()
    print(f"Seeded {len(PRODUCTS)} products, {len(USERS)} users, {len(REVIEWS)} reviews.")
    print("Admin login:  admin@volta.dev / admin123")
    print("Demo login:   jordan@example.com / password123")


if __name__ == "__main__":
    seed()
