"""
Quick demo — run this to see the translator in action.
Usage: python demo.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.translator import translate_to_darija

def main():
    print("\n🇩🇿  Darija Drug Interaction Translator — Demo\n")

    description = input("Paste an English drug interaction description:\n> ").strip()
    if not description:
        description = (
            "Taking ibuprofen together with aspirin increases the risk of "
            "stomach bleeding and ulcers. Avoid this combination without "
            "consulting your doctor."
        )
        print(f"\nUsing default example:\n  {description}\n")

    risk = input("Risk level (major / moderate / minor) [press Enter to skip]: ").strip() or None

    print("\n⏳ Translating...")
    result = translate_to_darija(description, risk)

    print("\n" + "=" * 55)
    if result["success"]:
        print("✅ Translation successful!\n")
    else:
        print("⚠️  Translation failed — showing original text\n")
        if result["error"]:
            print(f"Error: {result['error']}\n")

    print(f"Risk label : {result['risk_label']}")
    print(f"\nDarija:\n{result['darija_text']}")
    print("=" * 55)


if __name__ == "__main__":
    main()
