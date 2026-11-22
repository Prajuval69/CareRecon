"""CSV field contracts. Type errors retain partial typed values and raw evidence."""

from .util import integer, iso_date


def parse_fields(values, contract):
    typed, issues = {}, []
    for field in contract["required"]:
        value = (values.get(field) or "").strip()
        spec = contract["fields"][field]
        if not value:
            typed[field] = None
            if not spec.get("nullable"):
                issues.append(f"{field}: required value is blank")
            continue
        try:
            kind = spec["type"]
            parsed = value
            if kind == "integer":
                parsed = integer(value)
                if "min" in spec and parsed < spec["min"]:
                    raise ValueError(f"expected at least {spec['min']}")
            elif kind == "date":
                parsed = iso_date(value)
            elif kind == "enum" and value not in spec["choices"]:
                raise ValueError("expected " + " or ".join(spec["choices"]))
            typed[field] = parsed
        except ValueError as exc:
            typed[field] = None
            issues.append(f"{field}: {exc}")

    for start, end in contract.get("intervals", []):
        if typed[start] and typed[end] and typed[start] > typed[end]:
            issues.append(f"{end}: precedes {start}")
    if typed.get("transaction_type") == "DISPENSE" and (
        typed.get("paid_cents") is not None and typed["paid_cents"] < 0
    ):
        issues.append("paid_cents: DISPENSE cannot be negative; use a linked REVERSAL")
    return typed, issues


def business_key(values, contract):
    parts = [(values.get(field) or "").strip() for field in contract["business_key"]]
    return parts[0] if all(parts) else None
