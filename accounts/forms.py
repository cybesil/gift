from django import forms
from django.contrib.auth import get_user_model

User = get_user_model()


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-input form-wide',
            'id': 'login-email',
            'required': True,
            'placeholder': 'Email address',
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input form-wide',
            'id': 'login-password',
            'required': True,
            'placeholder': 'Password',
        })
    )
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'custom-control-input',
        })
    )

    def clean(self):
        from django.contrib.auth import authenticate
        cleaned = super().clean()
        email = cleaned.get('email')
        password = cleaned.get('password')

        if email and password:
            # look up user by email first
            try:
                username = User.objects.get(email=email).username
            except User.DoesNotExist:
                raise forms.ValidationError("No account found with that email address.")

            user = authenticate(username=username, password=password)
            if user is None:
                raise forms.ValidationError("Invalid email or password.")
            if not user.is_active:
                raise forms.ValidationError("This account has been disabled.")
            cleaned['user'] = user

        return cleaned


class RegistrationForm(forms.ModelForm):
    password = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input form-wide',
            'type': 'password',
            'required': True,
            'placeholder': 'Password',
            'autocomplete': 'new-password',
            'id': 'register-password',
        })
    )
    confirm_password = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input form-wide',
            'type': 'password',
            'required': True,
            'placeholder': 'Confirm Password',
            'id': 'register-password2',
        })
    )

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-input form-wide',
                'required': True,
                'placeholder': 'First Name',
                'id': 'register-first-name',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-input form-wide',
                'required': True,
                'placeholder': 'Last Name',
                'id': 'register-last-name',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-input form-wide',
                'required': True,
                'placeholder': 'Email address',
                'id': 'register-email',
            }),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_confirm_password(self):
        password = self.cleaned_data.get('password')
        confirm = self.cleaned_data.get('confirm_password')
        if password and confirm and password != confirm:
            raise forms.ValidationError("Passwords do not match.")
        return confirm

    def save(self, commit=True):
        user = super().save(commit=False)
        # derive username from email prefix, ensure uniqueness
        base = self.cleaned_data['email'].split('@')[0]
        username = base
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base}{counter}"
            counter += 1
        user.username = username
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user