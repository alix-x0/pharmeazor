"""
Darija Translator Module
Translates drug interaction descriptions from English to Algerian Darija
using the Gemini API.
"""

import os
import time
import logging
from typing import Optional
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── OpenAI setup ──────────────────────────────────────────────────────────────
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    raise EnvironmentError("OPENAI_API_KEY is not set. Check your .env file.")

client = OpenAI(api_key=API_KEY)

# ── Prompt template ───────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
أنت خبير في الترجمة الطبية للدارجة الجزائرية. ترجم النص الطبي التالي بصرامة.

**قواعد صارمة:**
- استعمل فقط الحروف العربية. ممنوع تماما أي حرف لاتيني (A-Z).
- ممنوع الأرقام الفرانكو-عربية (3، 7، 9، إلخ).
- الأسماء العلمية للأدوية (مثل Paracetamol) خلّيها باللاتيني فقط إذا ما لقيتش بديل.
- لا تكتب مقدمات: ممنوع "إليك الترجمة"، "الترجمة هي"، أو أي كلام قبل النص المترجم.

**التعليمات:**
1. ترجم بلهجة جزائرية أصيلة (ماشي فصحى ولا دارجة بلد أخرى).
2. لغة بسيطة كأنك تشرح لواحد من دارك مافهمش في الطب.
3. شرح المفاهيم الطبية الصعبة بالدارجة.
4. ركّز على المعلومات المهمة فقط:
   - شنو الدواء وكيفاش يخدم
   - الأعراض الجانبية الخطيرة (اللي تستدعي الطبيب)
   - التفاعلات مع الأدوية الأخرى
   - مين ميستعملوش (الحوامل، مرضى القلب، إلخ)
5. **حذف تام** لـ: تاريخ اكتشاف الدواء، قصص الشركات المصنعة، إحصائيات طويلة، أو أي "كلام فاضي".
6. **الملخص فقط** — ما تطوّلش.
"""

# ── Risk level labels in Darija ───────────────────────────────────────────────
RISK_LABELS = {
    "major":    "⛔ خطر كبير",
    "moderate": "⚠️  خطر متوسط",
    "minor":    "ℹ️  خطر خفيف",
    "unknown":  "❓ ما عرفناش",
}


def translate_to_darija(
    english_text: str,
    risk_level: Optional[str] = None,
    max_retries: int = 3,
    retry_delay: float = 2.0,
) -> dict:
    """
    Translate an English drug interaction description to Algerian Darija.

    Args:
        english_text: The English description from DDinter / your backend.
        risk_level:   Optional risk level string ('major', 'moderate', 'minor').
        max_retries:  Number of retries on transient API failures.
        retry_delay:  Seconds to wait between retries.

    Returns:
        {
            "darija_text":  str,   # translated text
            "risk_label":  str,   # human-readable Darija risk label
            "risk_level":  str,   # original risk level
            "success":     bool,
            "error":       str | None,
        }
    """
    prompt = f"{SYSTEM_PROMPT}\n\nText to translate:\n{english_text.strip()}"

    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Translation attempt %d/%d", attempt, max_retries)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
                temperature=0.3,
            )
            darija = response.choices[0].message.content.strip()

            risk_key   = (risk_level or "unknown").lower()
            risk_label = RISK_LABELS.get(risk_key, RISK_LABELS["unknown"])

            return {
                "darija_text": darija,
                "risk_label":  risk_label,
                "risk_level":  risk_key,
                "success":     True,
                "error":       None,
            }

        except Exception as exc:
            logger.warning("Attempt %d failed: %s", attempt, exc)
            if attempt < max_retries:
                time.sleep(retry_delay)

    # All retries exhausted → return the original English as fallback
    logger.error("All translation attempts failed, returning original text.")
    return {
        "darija_text": english_text,
        "risk_label":  RISK_LABELS.get((risk_level or "unknown").lower(), RISK_LABELS["unknown"]),
        "risk_level":  (risk_level or "unknown").lower(),
        "success":     False,
        "error":       "Translation failed after all retries. Showing English original.",
    }


def translate_interaction_result(interaction: dict) -> dict:
    """
    Convenience wrapper: takes the dict your team's backend returns and
    adds Darija fields to it.

    Expected input keys (at minimum):
        - description  (str)  English interaction description
        - risk_level   (str)  'major' | 'moderate' | 'minor'
        - drug1        (str)
        - drug2        (str)

    Returns the same dict with added keys:
        - darija_description
        - darija_risk_label
        - translation_success
        - translation_error
    """
    result = translate_to_darija(
        english_text=interaction.get("description", ""),
        risk_level=interaction.get("risk_level"),
    )

    return {
        **interaction,
        "darija_description":  result["darija_text"],
        "darija_risk_label":   result["risk_label"],
        "translation_success": result["success"],
        "translation_error":   result["error"],
    }
