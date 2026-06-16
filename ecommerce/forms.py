from django import forms

from .models import User, UserProfile, ShippingAddress


class AccountDetailsForm(forms.ModelForm):
    full_name = forms.CharField(max_length=255, required=True)
    phone_num = forms.CharField(max_length=20, required=False, label="Phone (Call line)")
    phone_num2 = forms.CharField(max_length=20, required=False, label="Phone (WhatsApp)")
    address = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.profile = kwargs.pop('profile', None)
        super().__init__(*args, **kwargs)

        for field_name in ['full_name', 'phone_num', 'phone_num2', 'address']:
            self.fields[field_name].widget.attrs.update({'class': 'form-control'})

        if self.profile and not self.is_bound:
            self.fields['full_name'].initial = self.profile.full_name
            self.fields['phone_num'].initial = self.profile.phone_num
            self.fields['phone_num2'].initial = self.profile.phone_num2
            self.fields['address'].initial = self.profile.address

    def save(self, commit=True):
        user = super().save(commit=commit)

        if self.profile:
            self.profile.full_name = self.cleaned_data['full_name']
            self.profile.phone_num = self.cleaned_data['phone_num']
            self.profile.phone_num2 = self.cleaned_data['phone_num2']
            self.profile.address = self.cleaned_data['address']
            if commit:
                self.profile.save()

        return user


class ShippingAddressForm(forms.ModelForm):
    class Meta:
        model = ShippingAddress
        fields = [
            'full_name', 'phone', 'email', 'street_address',
            'city', 'state', 'postal_code', 'country',
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'street_address': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'House number and street name',
            }),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.Select(attrs={'class': 'form-control'}),
        }

    COUNTRY_CHOICES = [
        ('Nigeria', 'Nigeria'),
        # ─── Africa ───
        ('Algeria', 'Algeria'),
        ('Angola', 'Angola'),
        ('Benin', 'Benin'),
        ('Botswana', 'Botswana'),
        ('Burkina Faso', 'Burkina Faso'),
        ('Burundi', 'Burundi'),
        ('Cabo Verde', 'Cabo Verde'),
        ('Cameroon', 'Cameroon'),
        ('Central African Republic', 'Central African Republic'),
        ('Chad', 'Chad'),
        ('Comoros', 'Comoros'),
        ('Congo (Republic of the)', 'Congo (Republic of the)'),
        ('Democratic Republic of the Congo', 'Democratic Republic of the Congo'),
        ('Djibouti', 'Djibouti'),
        ('Egypt', 'Egypt'),
        ('Equatorial Guinea', 'Equatorial Guinea'),
        ('Eritrea', 'Eritrea'),
        ('Eswatini', 'Eswatini'),
        ('Ethiopia', 'Ethiopia'),
        ('Gabon', 'Gabon'),
        ('Gambia', 'Gambia'),
        ('Ghana', 'Ghana'),
        ('Guinea', 'Guinea'),
        ('Guinea-Bissau', 'Guinea-Bissau'),
        ('Ivory Coast', 'Ivory Coast'),
        ('Kenya', 'Kenya'),
        ('Lesotho', 'Lesotho'),
        ('Liberia', 'Liberia'),
        ('Libya', 'Libya'),
        ('Madagascar', 'Madagascar'),
        ('Malawi', 'Malawi'),
        ('Mali', 'Mali'),
        ('Mauritania', 'Mauritania'),
        ('Mauritius', 'Mauritius'),
        ('Morocco', 'Morocco'),
        ('Mozambique', 'Mozambique'),
        ('Namibia', 'Namibia'),
        ('Niger', 'Niger'),
        ('Rwanda', 'Rwanda'),
        ('Sao Tome and Principe', 'Sao Tome and Principe'),
        ('Senegal', 'Senegal'),
        ('Seychelles', 'Seychelles'),
        ('Sierra Leone', 'Sierra Leone'),
        ('Somalia', 'Somalia'),
        ('South Africa', 'South Africa'),
        ('South Sudan', 'South Sudan'),
        ('Sudan', 'Sudan'),
        ('Tanzania', 'Tanzania'),
        ('Togo', 'Togo'),
        ('Tunisia', 'Tunisia'),
        ('Uganda', 'Uganda'),
        ('Zambia', 'Zambia'),
        ('Zimbabwe', 'Zimbabwe'),
        # ─── Other / International ───
        ('United States', 'United States'),
        ('United Kingdom', 'United Kingdom'),
        ('Canada', 'Canada'),
        ('Germany', 'Germany'),
        ('France', 'France'),
        ('Netherlands', 'Netherlands'),
        ('Spain', 'Spain'),
        ('Italy', 'Italy'),
        ('Ireland', 'Ireland'),
        ('Belgium', 'Belgium'),
        ('Sweden', 'Sweden'),
        ('Switzerland', 'Switzerland'),
        ('United Arab Emirates', 'United Arab Emirates'),
        ('Saudi Arabia', 'Saudi Arabia'),
        ('Qatar', 'Qatar'),
        ('China', 'China'),
        ('India', 'India'),
        ('Brunei', 'Brunei'),
        ('Bulgaria', 'Bulgaria'),
        ('Australia', 'Australia'),
        ('Brazil', 'Brazil'),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['country'] = forms.ChoiceField(
            choices=self.COUNTRY_CHOICES,
            widget=forms.Select(attrs={'class': 'form-control'}),
        )
        self.fields['full_name'].required = True
        self.fields['phone'].required = True
        self.fields['street_address'].required = True
        self.fields['city'].required = True
        self.fields['state'].required = True
        self.fields['postal_code'].required = True