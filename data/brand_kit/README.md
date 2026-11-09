# Lumora brand kit (synthetic demo data): Step 2, Pritha

Lumora is a **fictional** fintech brand. Create three files in this folder. `engine/schemas.py` validates them, so keep the field names exact.

## guidelines.json (about 15 items, G01–G15)
`category` is one of: tone, terminology, claim, outdated_fact, messaging, accessibility
```json
[
  {
    "id": "G01",
    "title": "Friendly, plain tone",
    "rule": "Write like a helpful friend. Avoid jargon and hype words such as 'revolutionary' or 'game-changing'.",
    "category": "tone",
    "examples_good": ["Send money in a few taps."],
    "examples_bad": ["Our revolutionary, game-changing payments paradigm."]
  }
]
```

## facts.json (about 20 items, F01–F20; at least 5 already expired)
`expires_on` is YYYY-MM-DD, or `null` if it never expires.
```json
[
  {
    "id": "F01",
    "statement": "Lumora Pay has 2 million registered users.",
    "source": "Lumora Q2 2026 investor update",
    "owner": "Comms team",
    "expires_on": "2026-09-30"
  }
]
```

## glossary.json (about 15 items, T01–T15)
```json
[
  {
    "id": "T01",
    "approved": "Lumora Pay",
    "banned_variants": ["LumoraPay", "Lumora pay", "LPay"],
    "note": "Always two words, both capitalised."
  }
]
```
