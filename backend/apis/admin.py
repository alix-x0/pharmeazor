from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Patient, Pharmacist, Administrator

class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('role', 'profile_picture')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': ('role',)}),
    )
    list_display = ['username', 'email', 'role', 'is_staff']
    list_filter = ['role', 'is_staff', 'is_superuser']

admin.site.register(User, CustomUserAdmin)
admin.site.register(Patient)
admin.site.register(Pharmacist)
admin.site.register(Administrator)


