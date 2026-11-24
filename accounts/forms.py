from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import CustomUser


class SignupForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'you@example.com',
            'autocomplete': 'email',
        }),
    )
    full_name = forms.CharField(
        max_length=120,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Your full name',
            'autocomplete': 'name',
        }),
    )

    class Meta:
        model = CustomUser
        fields = ['email', 'full_name', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({
            'class': 'form-input', 'placeholder': 'Create a password',
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-input', 'placeholder': 'Repeat the password',
        })

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('This email is already registered.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.full_name = self.cleaned_data.get('full_name', '')
        # AbstractUser still requires a unique username; derive one from email.
        base = (user.email.split('@')[0] or 'user')[:130]
        username = base
        counter = 1
        while CustomUser.objects.filter(username=username).exclude(pk=user.pk).exists():
            counter += 1
            username = f'{base}{counter}'
        user.username = username
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'you@example.com',
            'autocomplete': 'email',
            'autofocus': True,
        }),
    )
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Your password',
            'autocomplete': 'current-password',
        }),
    )


class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['full_name', 'theme_preference']
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-input'}),
            'theme_preference': forms.Select(attrs={'class': 'form-input'}),
        }
