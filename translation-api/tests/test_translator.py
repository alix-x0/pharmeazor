"""
Tests for the Darija translator module.
Run with: python tests/test_translator.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.translator import translate_to_darija, translate_interaction_result

# ── Realistic DDinter-style descriptions ─────────────────────────────────────
SAMPLES = [
    {
        "drug1": "Aspirin",
        "drug2": "Warfarin",
        "risk_level": "major",
        "description": (
            "Concurrent use of aspirin and warfarin significantly increases "
            "the risk of bleeding. Aspirin inhibits platelet aggregation and "
            "can also increase the anticoagulant effect of warfarin by displacing "
            "it from plasma protein binding sites. Avoid this combination unless "
            "under strict medical supervision."
        ),
    },
    {
        "drug1": "Metformin",
        "drug2": "Ibuprofen",
        "risk_level": "moderate",
        "description": (
            "NSAIDs like ibuprofen may reduce the effectiveness of metformin "
            "and increase the risk of kidney problems in diabetic patients. "
            "Monitor kidney function and blood glucose levels closely if "
            "this combination is necessary."
        ),
    },
    {
        "drug1": "Paracetamol",
        "drug2": "Codeine",
        "risk_level": "minor",
        "description": (
            "This combination is commonly used and generally safe. "
            "However, exceeding the recommended dose of paracetamol can cause "
            "serious liver damage. Do not take more than 4 grams of paracetamol "
            "per day from all sources."
        ),
    },
    {
        "drug1": "Amoxicillin",
        "drug2": "Oral Contraceptives",
        "risk_level": "moderate",
        "description": (
            "Antibiotics like amoxicillin may reduce the effectiveness of oral "
            "contraceptives by altering gut bacteria that metabolize estrogens. "
            "Use additional contraceptive methods during antibiotic treatment "
            "and for 7 days after."
        ),
    },
]


def run_tests():
    print("=" * 60)
    print("DARIJA TRANSLATOR — TEST RUN")
    print("=" * 60)

    passed = 0
    failed = 0

    for i, sample in enumerate(SAMPLES, 1):
        print(f"\n[Test {i}] {sample['drug1']} + {sample['drug2']}")
        print(f"  Risk level : {sample['risk_level']}")
        print(f"  English    : {sample['description'][:80]}...")

        enriched = translate_interaction_result(sample)

        success = enriched.get("translation_success", False)
        darija  = enriched.get("darija_description", "")
        label   = enriched.get("darija_risk_label", "")
        error   = enriched.get("translation_error")

        if success and darija:
            print(f"  ✅ Darija    : {darija[:120]}...")
            print(f"  Label       : {label}")
            passed += 1
        else:
            print(f"  ❌ FAILED — {error}")
            print(f"  Fallback    : {darija[:80]}...")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {len(SAMPLES)} tests")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
