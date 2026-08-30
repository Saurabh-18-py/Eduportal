from django import forms
from django.contrib.auth.models import User
from .models import CLASS_CHOICES, Avatar


class SignupForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)
    class_level = forms.ChoiceField(choices=CLASS_CHOICES, label="Class")
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data


class ProfileForm(forms.Form):
    first_name = forms.CharField(max_length=150, required=False, label="Name")
    email = forms.EmailField(required=False)
    class_level = forms.ChoiceField(choices=CLASS_CHOICES, label="Class")
    phone = forms.CharField(max_length=15, required=False)


class AvatarForm(forms.Form):
    avatar = forms.ModelChoiceField(
        queryset=Avatar.objects.none(),
        widget=forms.RadioSelect,
        empty_label=None,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['avatar'].queryset = Avatar.objects.filter(is_active=True)
