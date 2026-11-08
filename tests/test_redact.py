from engine.redact import redact, redact_with_map, restore


def test_masks_email_phone_and_names_and_restores():
    t = "Mail ria@lumora.com or call +91 98765 43210. Ask Dr. Rao. Regards, Priya Nair"
    safe, mapping = redact_with_map(t)
    for secret in ("ria@lumora.com", "98765", "Rao", "Priya"):
        assert secret not in safe
    assert restore(safe, mapping) == t
    assert redact(t)[1] == len(mapping) == 4


def test_numbers_prices_and_brand_not_masked():
    t = "Save 20% before 2026. Dear Lumora customer, 2 million users."
    assert redact(t) == (t, 0)


def test_same_value_gets_same_placeholder():
    safe, mapping = redact_with_map("a@b.com and again a@b.com")
    assert safe == "[EMAIL_1] and again [EMAIL_1]" and len(mapping) == 1
