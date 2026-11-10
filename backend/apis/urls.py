from django.urls import path
from rest_framework_simplejwt.views import (TokenObtainPairView, TokenRefreshView)
from .views import *

urlpatterns = [
    # Authentication
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', TokenObtainPairView.as_view(), name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/profile/', UserProfileView.as_view(), name='profile'),
    path('auth/change-password/', ChangePasswordView.as_view(), name='change_password'),

    # Users
    path('users/', UserListView.as_view(), name='user-list'),

    # Drugs & Interactions
    path('drugs/', DrugListView.as_view(), name='drug-list'),
    path('interactions/analyze/', analyze_interactions, name='analyze-interactions'),

    # Medication Profile
    path('medication-profile/', MedicationProfileListCreate.as_view(), name='medication-profile'),
    path('medication-profile/<int:pk>/', MedicationProfileDelete.as_view(), name='medication-profile-delete'),
    path('medication-profile/check/', check_against_profile, name='check-against-profile'),
    path('medication-profile/scan/', scan_prescription, name='scan-prescription'),
]