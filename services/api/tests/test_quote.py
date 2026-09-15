from buyeros_api.services.quote_service import eligible, quote_hash


def test_quote_hash_is_stable():
    payload = {"selection": ["b1", "b2"], "purpose": "contact_lookup"}
    assert quote_hash(payload) == quote_hash({"purpose": "contact_lookup", "selection": ["b1", "b2"]})


def test_eligibility_lists_block_reasons():
    ok, reasons = eligible({"accepted": True, "policy": "unknown", "suppressed": False})
    assert not ok and any("policy" in r for r in reasons)


def test_eligible_when_all_gates_pass():
    ok, reasons = eligible({"accepted": True, "policy": "permitted", "suppressed": False, "role_supported": True})
    assert ok and reasons == []


def test_suppressed_buyer_ineligible():
    ok, reasons = eligible({"accepted": True, "policy": "permitted", "suppressed": True})
    assert not ok and any("suppress" in r for r in reasons)
