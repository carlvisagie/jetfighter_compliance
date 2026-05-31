"""First-sale workflow — shop pricing, payment link, kickoff."""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from services.intake.payment_email import build_payment_link_email_html
from services.intake.payment_products import get_payment_product, list_payment_products


def test_payment_products_catalog():
    products = list_payment_products()
    assert len(products) == 3
    ids = {p["id"] for p in products}
    assert ids == {"cmmc_l1", "cmmc_l2", "eu_dpp"}
    for p in products:
        assert p["paypal_url"].startswith("https://www.paypal.com/ncp/payment/")


def test_payment_email_template_uses_paypal_only():
    product = get_payment_product("cmmc_l1")
    html = build_payment_link_email_html(
        customer_name="Acme",
        company="Acme Defense",
        product=product,
    )
    assert "PayPal" in html
    assert "paypal.com" in html
    assert "buy." not in html  # banned legacy card rail domain pattern


def test_shop_shows_three_services_and_prices(anon_client: TestClient):
    r = anon_client.get("/ui/shop.html")
    assert r.status_code == 200
    text = r.text
    assert "CMMC Level 1 Fast-Track Assessment" in text
    assert "CMMC Level 2 Readiness Assessment" in text
    assert "EU Digital Product Passport Pilot" in text
    assert "$3,500" in text
    assert "$8,000" in text
    assert "$6,000" in text
    assert "Upload paperwork for free review" in text
    assert "paypal.com" not in text.lower()


def test_send_payment_link_operator_action(fb_env, anon_client: TestClient, client: TestClient):
    up = anon_client.post(
        "/api/founding-beta/upload",
        files=[("files", ("policy.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf"))],
        data={"email": "pay@example.com", "company": "PayCo"},
    )
    assert up.status_code == 200
    iid = up.json()["intake_id"]

    r = client.post(
        "/api/operator/founding-beta/action",
        json={"intake_id": iid, "action": "send_payment_link", "product_id": "cmmc_l2"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert body.get("product_id") == "cmmc_l2"
    assert "paypal.com" in (body.get("paypal_url") or "")

    q = client.get("/api/operator/founding-beta/queue")
    row = next(x for x in q.json()["queue"] if x["intake_id"] == iid)
    assert row["payment"]["product_id"] == "cmmc_l2"
    assert row["payment"]["payment_link_sent_at_utc"]


def test_kickoff_project_after_payment_link(fb_env, anon_client: TestClient, client: TestClient):
    up = anon_client.post(
        "/api/founding-beta/upload",
        files=[("files", ("doc.pdf", io.BytesIO(b"%PDF"), "application/pdf"))],
        data={"email": "kick@example.com", "company": "KickCo"},
    )
    iid = up.json()["intake_id"]
    client.post(
        "/api/operator/founding-beta/action",
        json={"intake_id": iid, "action": "send_payment_link", "product_id": "eu_dpp"},
    )
    ko = client.post(
        "/api/operator/founding-beta/action",
        json={"intake_id": iid, "action": "kickoff_project"},
    )
    assert ko.status_code == 200
    assert ko.json().get("project_id")
    assert ko.json().get("files_linked")


def test_send_payment_link_requires_product(fb_env, anon_client: TestClient, client: TestClient):
    iid = anon_client.post(
        "/api/founding-beta/upload",
        files=[("files", ("a.pdf", io.BytesIO(b"%PDF"), "application/pdf"))],
        data={"email": "x@y.com"},
    ).json()["intake_id"]
    r = client.post(
        "/api/operator/founding-beta/action",
        json={"intake_id": iid, "action": "send_payment_link"},
    )
    assert r.status_code == 400
