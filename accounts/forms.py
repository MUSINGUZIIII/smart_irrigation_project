import os
from PIL import Image
from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import CustomUser, validate_phone_number
import phonenumbers
from django.core.validators import RegexValidator


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'location', 'age', 'phone_number')


class CustomUserChangeForm(UserChangeForm):
    password = None

    class Meta:
        model = CustomUser
        fields = ('email', 'first_name', 'last_name', 'location', 'age', 'phone_number')

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            try:
                parsed_number = phonenumbers.parse(phone_number, None)
                if not phonenumbers.is_valid_number(parsed_number):
                    raise forms.ValidationError("Invalid phone number, start with country code:")
                return phonenumbers.format_number(
                    parsed_number,
                    phonenumbers.PhoneNumberFormat.E164
                )
            except phonenumbers.phonenumberutil.NumberParseException:
                raise forms.ValidationError("Invalid phone number, start with country code:")
        return phone_number


    def has_double_extension(self, filename):
        """Check if filename has double extensions"""
        import os
        basename = os.path.basename(filename)
        name_parts = basename.split('.')

        # If there are more than 2 parts and the last parts are image extensions
        if len(name_parts) > 2:
            extensions = ['jpg', 'jpeg', 'png', 'gif']
            if name_parts[-1].lower() in extensions and name_parts[-2].lower() in extensions:
                return True
        return False


class NotificationPreferencesForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['sms_notification_frequency', 'receive_sms_alerts']
        widgets = {
            'sms_notification_frequency': forms.Select(choices=CustomUser.SMS_NOTIFICATION_CHOICES),
            'receive_sms_alerts': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure the checkbox is unchecked by default for new users
        if not self.instance.pk:  # New user
            self.initial['receive_sms_alerts'] = False


class SMSVerificationForm(forms.Form):
    code = forms.CharField(
        max_length=6,
        min_length=6,
        validators=[RegexValidator(r'^\d{6}$', 'Enter a valid 6-digit code.')],
        widget=forms.TextInput(attrs={
            'placeholder': '123456',
            'class': 'form-control',
            'inputmode': 'numeric',
            'pattern': '[0-9]*'
        })
    )


class PhoneNumberForm(forms.Form):
    phone_number = forms.CharField(
        max_length=20,
        validators=[validate_phone_number],
        widget=forms.TextInput(attrs={
            'placeholder': '+256712345678',
            'class': 'form-control'
        })
    )

