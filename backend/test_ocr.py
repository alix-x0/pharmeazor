import os
import django
import sys

sys.path.append(r"c:\Users\sasas\Desktop\Projects\Biovatech Hackathon\hackathon\backend")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apis.views import preprocess_image, slice_after_ordonnance
from apis.models import Drug
import cv2
import pytesseract
import numpy as np
import re
from rapidfuzz import fuzz, process

os.environ['TESSDATA_PREFIX'] = r"C:\Users\sasas\Desktop\Projects\Biovatech Hackathon\hackathon\backend\tessdata"
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

img_path = r"C:\Users\sasas\.gemini\antigravity\brain\231a0707-0f04-4b92-9777-1866d0eb68b7\uploaded_media_1777506132758.png"
if not os.path.exists(img_path):
    print("IMAGE NOT FOUND!")
    sys.exit(1)

img_bgr = cv2.imread(img_path)

config = r"--oem 3 --psm 6"
raw_text = pytesseract.image_to_string(img_bgr, lang="fra+eng", config=config)
print("--- RAW TEXT ---")
print(raw_text)

text = slice_after_ordonnance(raw_text)
print("--- SLICED TEXT ---")
print(text)

MIN_TOKEN_LEN = 6
raw_tokens = re.findall(r"[A-Za-zÀ-ÿ]{" + str(MIN_TOKEN_LEN) + r",}", text)
words = [w for w in raw_tokens]
bigrams  = [f"{words[i]} {words[i+1]}" for i in range(len(words)-1)] if len(words) > 1 else []
trigrams = [f"{words[i]} {words[i+1]} {words[i+2]}" for i in range(len(words)-2)] if len(words) > 2 else []
all_tokens = words + bigrams + trigrams

print("--- TOKENS ---")
print(all_tokens)

drugs = Drug.objects.all()
drug_names_map = {}
for drug in drugs:
    if drug.brand_name:
        drug_names_map[drug.brand_name.upper().strip()] = drug
    if drug.generic_name:
        drug_names_map[drug.generic_name.upper().strip()] = drug
        
all_drug_names = list(drug_names_map.keys())

for token in all_tokens:
    norm = token.upper().strip()
    if len(norm) < MIN_TOKEN_LEN:
        continue
    result = process.extractOne(norm, all_drug_names, scorer=fuzz.WRatio, score_cutoff=80)
    if result:
        print(f"MATCH: {token} -> {result[0]} (Score: {result[1]})")
