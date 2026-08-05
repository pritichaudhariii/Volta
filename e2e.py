"""End-to-end test — boots VOLTA on port 5001 and walks the full journey:

browse → search → product → sign in → cart → checkout → pay →
review → stock check → admin dashboard → fulfil order → access control.

Run:
    pip install playwright && playwright install chromium
    python tests/e2e.py

Re-seed first for a clean run:  python -m app.seed
"""

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from werkzeug.serving import make_server

from app import create_app

PORT = 5001
BASE = f"http://localhost:{PORT}"


def login(page, email, password):
    page.goto(f"{BASE}/login")
    page.fill("input[name=email]", email)
    page.fill("input[name=password]", password)
    page.click(".auth-card button[type=submit]")


def main() -> None:
    server = make_server("127.0.0.1", PORT, create_app(), threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    time.sleep(1)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        page.goto(BASE)
        assert page.locator(".card").count() == 8
        print("✓ home renders 8 product cards")

        page.fill("input[name=q]", "headphones")
        page.click(".search button")
        assert page.locator(".card").count() == 1
        print("✓ search filters the catalog")

        page.goto(f"{BASE}/product/aria-anc-headphones")
        assert page.locator(".review").count() == 2
        print("✓ product page shows seeded reviews")

        login(page, "jordan@example.com", "password123")
        assert page.locator(".nav-links", has_text="Jordan").count()
        print("✓ customer sign-in")

        page.goto(f"{BASE}/product/aria-anc-headphones")
        page.click(".buy-box button[type=submit]")
        page.goto(f"{BASE}/product/tactile-75-keyboard")
        page.click(".buy-box button[type=submit]")
        page.goto(f"{BASE}/cart")
        assert page.locator(".cart-row").count() == 2
        print("✓ cart holds 2 items")

        page.click("aside.summary a.btn")
        page.fill("input[name=ship_address]", "42 Battery Lane")
        page.fill("input[name=ship_city]", "Seattle")
        page.fill("input[name=ship_postal]", "98101")
        page.fill("input[name=ship_country]", "USA")
        page.click(".checkout-form button[type=submit]")
        assert "/orders/" in page.url
        print("✓ checkout creates an order")

        page.click("aside.summary form button[type=submit]")
        assert page.locator(".status-paid").count()
        print("✓ demo payment marks order paid")

        page.goto(f"{BASE}/product/surge-100w-gan-charger")
        page.select_option(".review-form select[name=rating]", "5")
        page.fill(".review-form textarea", "Tiny brick, huge output.")
        page.click(".review-form button")
        assert page.locator(".flash-success").count()
        print("✓ review posting")

        page.goto(f"{BASE}/product/aria-anc-headphones")
        assert "11" in page.locator(".stock-ok").inner_text()
        print("✓ stock decrements after purchase")

        page.goto(f"{BASE}/logout")
        login(page, "admin@volta.dev", "admin123")
        page.goto(f"{BASE}/admin/")
        assert page.locator(".stat").count() == 4
        print("✓ admin dashboard")

        page.goto(f"{BASE}/admin/orders")
        page.click("text=mark delivered")
        assert page.locator(".status-delivered").count()
        print("✓ admin can fulfil orders")

        page.goto(f"{BASE}/logout")
        page.goto(f"{BASE}/admin/")
        assert "/admin" not in page.url
        print("✓ admin routes protected")

        browser.close()

    server.shutdown()
    print("\nALL E2E CHECKS PASSED ✅")


if __name__ == "__main__":
    main()
