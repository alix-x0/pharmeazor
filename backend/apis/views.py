from rest_framework import generics, status, filters
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.views import TokenObtainPairView
from django.db.models import Q, Count, Avg
from django.utils import timezone
from django.http import FileResponse
from .models import *
from .serializers import *
from .permissions import *
import requests
from django.conf import settings
import cv2
import numpy as np
import pytesseract
import re
from rapidfuzz import fuzz, process


# Authentication Views

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]


class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user


class UserListView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['username', 'email']
    ordering_fields = ['id', 'username']

class ChangePasswordView(generics.UpdateAPIView):
    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        self.object = self.get_object()
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            if not self.object.check_password(serializer.data.get("old_password")):
                return Response({"old_password": ["Wrong password."]}, status=status.HTTP_400_BAD_REQUEST)
            
            self.object.set_password(serializer.data.get("new_password"))
            self.object.save()
            return Response({"status": "success", "message": "Password updated successfully"}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class DrugListView(generics.ListAPIView):
    queryset = Drug.objects.all()
    serializer_class = DrugSerializer
    permission_classes = [AllowAny]
    filter_backends = [filters.SearchFilter]
    search_fields = ['brand_name', 'generic_name']

@api_view(['POST'])
@permission_classes([AllowAny])
def analyze_interactions(request):
    drugs_raw = request.data.get('drugs', [])
    user_role = request.data.get('user_role', 'pharmacist')
    if not drugs_raw:
        return Response({"error": "No drugs provided"}, status=status.HTTP_400_BAD_REQUEST)
    
    # Resolve brand names to generic names using our local DB for better matching
    drugs_resolved = []
    for d_name in drugs_raw:
        # Try exact brand name match
        drug_obj = Drug.objects.filter(Q(brand_name__iexact=d_name) | Q(generic_name__iexact=d_name)).first()
        if drug_obj:
            # Use generic name for clinical accuracy, or brand if generic is missing
            drugs_resolved.append(drug_obj.generic_name or drug_obj.brand_name)
        else:
            drugs_resolved.append(d_name)

    base_url = getattr(settings, 'FASTAPI_BASE', 'http://127.0.0.1:8001')
    if not base_url.startswith('http'):
        base_url = f"http://{base_url}"
    
    fastapi_url = f"{base_url}/api/v1/interactions/analyze"
    
    try:
        response = requests.post(
            fastapi_url, 
            json={"drugs": drugs_resolved, "user_role": user_role}, 
            timeout=60
        )
        return Response(response.json(), status=response.status_code)
    except requests.exceptions.Timeout:
        return Response({"error": "MedSafe engine timed out. It might still be loading the AI model."}, status=status.HTTP_504_GATEWAY_TIMEOUT)
    except requests.exceptions.RequestException as e:
        print(f"MedSafe Connection Error: {e}")
        return Response({"error": f"Could not connect to MedSafe engine: {str(e)}"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


# Medication Profile Views

class MedicationProfileListCreate(generics.ListCreateAPIView):
    """List all saved medications for the current user, or add a new one."""
    serializer_class = MedicationProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return MedicationProfile.objects.filter(user=self.request.user).select_related('drug')


class MedicationProfileDelete(generics.DestroyAPIView):
    """Remove a medication from the user's profile."""
    serializer_class = MedicationProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return MedicationProfile.objects.filter(user=self.request.user)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def check_against_profile(request):
    """Check a new drug against ALL medications in the user's saved profile."""
    new_drug = request.data.get('drug_name', '')
    user_role = request.data.get('user_role', 'patient')  # Default to patient for profile checks
    if not new_drug:
        return Response({"error": "No drug_name provided"}, status=status.HTTP_400_BAD_REQUEST)

    profile_meds = MedicationProfile.objects.filter(user=request.user).select_related('drug')
    if not profile_meds.exists():
        return Response({"error": "Your medication profile is empty. Add your regular medications first."}, status=status.HTTP_400_BAD_REQUEST)

    # Build pairs: new drug vs each saved medication
    profile_drug_names = [
        med.drug.brand_name or med.drug.generic_name
        for med in profile_meds
    ]
    all_drugs = [new_drug] + profile_drug_names

    base_url = getattr(settings, 'FASTAPI_BASE', 'http://127.0.0.1:8001')
    if not base_url.startswith('http'):
        base_url = f"http://{base_url}"

    fastapi_url = f"{base_url}/api/v1/interactions/analyze"

    try:
        response = requests.post(
            fastapi_url, 
            json={"drugs": all_drugs, "user_role": user_role}, 
            timeout=60
        )
        return Response(response.json(), status=response.status_code)
    except requests.exceptions.Timeout:
        return Response({"error": "MedSafe engine timed out."}, status=status.HTTP_504_GATEWAY_TIMEOUT)
    except requests.exceptions.RequestException as e:
        return Response({"error": f"Could not connect to MedSafe engine: {str(e)}"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

def deskew(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    gray = cv2.bitwise_not(gray)
    coords = np.column_stack(np.where(gray > 0))
    if len(coords) == 0:
        return image
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) < 0.5:
        return image
    (h, w) = image.shape[:2]
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REPLICATE)

def preprocess_image(img_bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    if w < 1000:
        scale = 1000 / w
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    
    # Tesseract internally handles binarization (Otsu) which is often much more robust
    # than hardcoded adaptiveThreshold and morphological operations across diverse lighting.
    return gray

PRESCRIPTION_START_KEYWORDS = [
    "ORDONNANCE",
    "PRESCRIPTION",
    "TRAITEMENT",
    "Rp/",
    "RP/",
]

def slice_after_ordonnance(text: str) -> str:
    text_upper = text.upper()
    earliest_idx = len(text)
    found_kw = ""
    for kw in PRESCRIPTION_START_KEYWORDS:
        idx = text_upper.find(kw.upper())
        if idx != -1 and idx < earliest_idx:
            earliest_idx = idx
            found_kw = kw
    if earliest_idx < len(text):
        cut = earliest_idx + len(found_kw)
        return text[cut:]
    return text

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def scan_prescription(request):
    """OCR endpoint to extract medications from an uploaded prescription image."""
    if 'file' not in request.FILES:
        return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)
        
    try:
        file_bytes = np.frombuffer(request.FILES['file'].read(), np.uint8)
        img_bgr = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        
        if img_bgr is None:
            return Response({"error": "Invalid image format"}, status=status.HTTP_400_BAD_REQUEST)
            
        processed = preprocess_image(img_bgr)
        
        import os
        os.environ['TESSDATA_PREFIX'] = r"C:\Users\sasas\Desktop\Projects\Biovatech Hackathon\hackathon\backend\tessdata"
        pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        
        config = r"--oem 3 --psm 6"
        raw_text = pytesseract.image_to_string(processed, lang="fra+eng", config=config)
        
        text = slice_after_ordonnance(raw_text)
        
        drugs = Drug.objects.all()
        drug_names_map = {}
        for drug in drugs:
            if drug.brand_name:
                drug_names_map[drug.brand_name.upper().strip()] = drug
            if drug.generic_name:
                drug_names_map[drug.generic_name.upper().strip()] = drug
                
        all_drug_names = list(drug_names_map.keys())
        
        MIN_TOKEN_LEN = 6
        raw_tokens = re.findall(r"[A-Za-zÀ-ÿ]{" + str(MIN_TOKEN_LEN) + r",}", text)
        words = [w for w in raw_tokens]
        bigrams  = [f"{words[i]} {words[i+1]}" for i in range(len(words)-1)]
        trigrams = [f"{words[i]} {words[i+1]} {words[i+2]}" for i in range(len(words)-2)]
        all_tokens = words + bigrams + trigrams
        
        matches = []
        seen_drugs = set()
        
        for token in all_tokens:
            norm = token.upper().strip()
            if len(norm) < MIN_TOKEN_LEN:
                continue
                
            result = process.extractOne(
                norm,
                all_drug_names,
                scorer=fuzz.WRatio,
                score_cutoff=80
            )
            
            if result is None:
                continue
                
            matched_name, score, _ = result
            
            matched_drug = drug_names_map[matched_name]
            if matched_drug.id in seen_drugs:
                continue
                
            seen_drugs.add(matched_drug.id)
            serializer = DrugSerializer(matched_drug)
            matches.append({
                "drug": serializer.data,
                "match_score": round(score, 1),
                "ocr_token": token
            })
            
        matches = sorted(matches, key=lambda x: x['match_score'], reverse=True)
        return Response({"extracted_text": raw_text, "matches": matches}, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({"error": f"OCR processing failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

