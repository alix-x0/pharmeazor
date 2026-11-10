import pytesseract
import cv2
import numpy as np
import os

os.environ['TESSDATA_PREFIX'] = r"C:\Users\sasas\Desktop\Projects\Biovatech Hackathon\hackathon\backend\tessdata"
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

img = np.zeros((100, 100, 3), dtype=np.uint8)
try:
    text = pytesseract.image_to_string(img, lang="fra+eng", config="--oem 3 --psm 6")
    print("SUCCESS")
except Exception as e:
    print("ERROR")
    print(e)
