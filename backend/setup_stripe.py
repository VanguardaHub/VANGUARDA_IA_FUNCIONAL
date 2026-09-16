import os
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

import stripe

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY") or "sk_test_emergent"

CATALOG = [
    {
        "emergent_product_id": "vanguarda_starter",
        "name": "Vanguarda.IA — Starter Agência",
        "tax_code": "txcd_10103001",
        "prices": [
            {"lookup_key": "starter_monthly", "amount": 9700, "currency": "brl", "interval": "month"},
            {"lookup_key": "starter_yearly", "amount": 93000, "currency": "brl", "interval": "year"},
        ],
    },
    {
        "emergent_product_id": "vanguarda_pro",
        "name": "Vanguarda.IA — Pro Scale",
        "tax_code": "txcd_10103001",
        "prices": [
            {"lookup_key": "pro_monthly", "amount": 19700, "currency": "brl", "interval": "month"},
            {"lookup_key": "pro_yearly", "amount": 189000, "currency": "brl", "interval": "year"},
        ],
    },
    {
        "emergent_product_id": "vanguarda_agency",
        "name": "Vanguarda.IA — Enterprise White-label",
        "tax_code": "txcd_10103001",
        "prices": [
            {"lookup_key": "agency_monthly", "amount": 39700, "currency": "brl", "interval": "month"},
            {"lookup_key": "agency_yearly", "amount": 381000, "currency": "brl", "interval": "year"},
        ],
    },
]


def ensure_tax_settings():
    try:
        s = stripe.tax.Settings.retrieve()
        if s.head_office and getattr(s.head_office, "address", None):
            return
        stripe.tax.Settings.modify(
            head_office={"address": {"country": "BR", "line1": "Av. Paulista, 1000",
                                     "city": "São Paulo", "state": "SP", "postal_code": "01310-100"}},
            defaults={"tax_behavior": "exclusive"},
        )
    except Exception as e:
        print(f"tax settings skipped: {e}")


def get_or_create_product(entry):
    for p in stripe.Product.list(active=True).auto_paging_iter():
        if p.to_dict().get("metadata", {}).get("emergent_product_id") == entry["emergent_product_id"]:
            return p
    return stripe.Product.create(name=entry["name"], tax_code=entry.get("tax_code"),
                                 metadata={"managed_by": "emergent", "emergent_product_id": entry["emergent_product_id"]})


def main():
    account = stripe.Account.retrieve()
    print(f"Stripe account: {account.id} country={account['country']}")
    ensure_tax_settings()
    for entry in CATALOG:
        product = get_or_create_product(entry)
        for price in entry["prices"]:
            existing = stripe.Price.list(lookup_keys=[price["lookup_key"]], active=True, limit=1).data
            if existing and (existing[0].unit_amount != price["amount"] or existing[0].currency != price["currency"]):
                stripe.Price.modify(existing[0].id, active=False)
                existing = []
            if not existing:
                kwargs = dict(product=product.id, unit_amount=price["amount"], currency=price["currency"],
                              lookup_key=price["lookup_key"], transfer_lookup_key=True)
                if price.get("interval"):
                    kwargs["recurring"] = {"interval": price["interval"]}
                stripe.Price.create(**kwargs)
                print(f"created price {price['lookup_key']}")
            else:
                print(f"price exists {price['lookup_key']}")
    print("Catalog ready")


if __name__ == "__main__":
    main()
