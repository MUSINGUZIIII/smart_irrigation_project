from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.admin import TokenAdmin


class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_token')
    fieldsets = UserAdmin.fieldsets + (
        ('Additional Info', {
            'fields': ('profile_picture', 'location', 'age', 'phone_number', 'receive_sms_alerts')
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Additional Info', {
            'fields': ('profile_picture', 'location', 'age', 'phone_number', 'receive_sms_alerts')
        }),
    )

    def get_token(self, obj):
        token, created = Token.objects.get_or_create(user=obj)
        return token.key
    get_token.short_description = 'API Token'


# First register the Token model with our custom admin
admin.site.register(Token, TokenAdmin)

# Then register your CustomUser
admin.site.register(CustomUser, CustomUserAdmin)
