"""Contract-valid immutable ICP payloads for real database tests."""

FACT_ID = "e1000000-0000-4000-8000-000000000001"
REQUIREMENT_ID = "e1000000-0000-4000-8000-000000000002"


def valid_icp_payload() -> dict:
    return {
        "basis_offer_revision": 1,
        "offer_facts": [
            {
                "id": FACT_ID,
                "field": "product",
                "value": "Industrial sensors",
                "provenance": "user_entered",
                "approved": False,
            }
        ],
        "requirements": [
            {
                "id": REQUIREMENT_ID,
                "text": "Distributes industrial sensors",
                "category": "must",
                "hard_exclusion": False,
            }
        ],
        "markets": ["DE"],
        "buyer_types": ["distributor"],
        "languages": ["en"],
    }
