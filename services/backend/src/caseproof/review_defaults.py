"""Current default document criteria and the exact legacy copy they replace."""

LEGACY_INVOICE_CRITERIA = "The active invoice states one SGD line with no tax or charges, and quantity × unit price equals the stated total (decimal arithmetic, 2 dp)."
INVOICE_CRITERIA = "Assess invoice accuracy across all line items, quantities, prices, taxes, discounts, credits and other charges. Reconcile the stated totals using the document’s currencies and rounding conventions. Identify missing information and inconsistencies."
LEGACY_DELIVERY_CRITERIA = "Distinct delivery events from a permitted receipt source, referencing the invoice with matching goods and units, add up to the invoiced quantity. Copies count once; dispatch is not receipt."
DELIVERY_CRITERIA = "Assess whether evidence of receipt accounts for the invoiced items and quantities. Match parties, references, items and units in context. Account for partial and cumulative deliveries without double-counting, and identify shortfalls, conflicts or unsupported conversions. Dispatch alone does not confirm receipt."


def current_requirements(definition: dict) -> list[dict]:
    rules = [dict(r) for r in definition["requirements"]]
    for rule in rules:
        old, new = {
            "invoice_total": (LEGACY_INVOICE_CRITERIA, INVOICE_CRITERIA),
            "delivery_receipts": (LEGACY_DELIVERY_CRITERIA, DELIVERY_CRITERIA),
        }.get(rule["key"], ("", ""))
        if old and rule["description"].startswith(old):
            rule["description"] = rule["description"].replace(old, new, 1)
        if rule["label"] == "Invoice total agrees with quantity × unit price":
            rule["label"] = "Invoice amounts are consistent"
    return rules
