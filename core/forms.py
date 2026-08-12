from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm as BaseUserCreationForm
from .models import RetailerProfile, Item, Bill, Order, OrderItem, Collection
from decimal import Decimal

User = get_user_model()

class StaffLoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username', 'autocomplete': 'username'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password', 'autocomplete': 'current-password'})
    )


class RetailerLoginForm(forms.Form):
    shop_number = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Shop Number (e.g. SHOP-101)'})
    )
    phone_number = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Registered Phone Number'})
    )


class UserCreateForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'phone_number', 'role']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, request_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if request_user and not request_user.is_superuser_role():
            allowed_roles = [c for c in User.Role.choices if c[0] not in [User.Role.SUPERUSER, User.Role.OWNER]]
            self.fields['role'].choices = allowed_roles

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            phone_number = phone_number.strip()
            if User.objects.filter(phone_number=phone_number).exists():
                raise forms.ValidationError("A user with this phone number already exists.")
        return phone_number

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data


class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'phone_number', 'role', 'is_active', 'is_locked']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_locked': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, request_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if request_user and not request_user.is_superuser_role():
            allowed_roles = [c for c in User.Role.choices if c[0] not in [User.Role.SUPERUSER, User.Role.OWNER]]
            self.fields['role'].choices = allowed_roles

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            phone_number = phone_number.strip()
            qs = User.objects.filter(phone_number=phone_number)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("A user with this phone number already exists.")
        return phone_number


class PasswordResetAdminForm(forms.Form):
    new_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'New Password'}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm New Password'}))

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('new_password')
        p2 = cleaned_data.get('confirm_password')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data


class RetailerOnboardingForm(forms.Form):
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Retailer Username'}))
    shop_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Shop Name'}))
    shop_number = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Shop Number (Unique)'}))
    phone_number = forms.CharField(max_length=15, widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'}))
    address = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Shop Address'}))
    initial_credit_balance = forms.DecimalField(max_digits=12, decimal_places=2, initial=Decimal('0.00'), widget=forms.NumberInput(attrs={'class': 'form-control'}))

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("A user with this username already exists.")
        return username

    def clean_shop_number(self):
        shop_number = self.cleaned_data.get('shop_number')
        if RetailerProfile.objects.filter(shop_number=shop_number).exists():
            raise forms.ValidationError("A retailer with this shop number already exists.")
        return shop_number

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            phone_number = phone_number.strip()
            if User.objects.filter(phone_number=phone_number).exists():
                raise forms.ValidationError("A user with this phone number already exists.")
        return phone_number


class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['name', 'description', 'price', 'stock_quantity']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Item Name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Description'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'stock_quantity': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class BillForm(forms.ModelForm):
    total_amount = forms.DecimalField(
        max_digits=12, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )

    class Meta:
        model = Bill
        fields = ['retailer', 'total_amount']
        widgets = {
            'retailer': forms.Select(attrs={'class': 'form-select'}),
        }


class BillEditForm(forms.ModelForm):
    class Meta:
        model = Bill
        fields = ['bill_number', 'retailer', 'status', 'total_amount', 'rejection_reason']
        widgets = {
            'bill_number': forms.TextInput(attrs={'class': 'form-control'}),
            'retailer': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'total_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'rejection_reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def clean_bill_number(self):
        bill_number = self.cleaned_data.get('bill_number').strip()
        qs = Bill.objects.filter(bill_number__iexact=bill_number)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A bill with this bill number already exists.")
        return bill_number


class BillRejectForm(forms.Form):
    rejection_reason = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Please specify reason for rejecting this bill...'}),
        required=True
    )


class CollectionForm(forms.ModelForm):
    bill = forms.ModelChoiceField(
        queryset=Bill.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Apply Payment to Bill"
    )

    class Meta:
        model = Collection
        fields = ['retailer', 'bill', 'amount_collected', 'notes']
        widgets = {
            'retailer': forms.Select(attrs={'class': 'form-select'}),
            'amount_collected': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional notes or receipt no...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        retailer_id = None
        if self.is_bound:
            retailer_id = self.data.get('retailer')
        elif self.initial.get('retailer'):
            retailer_id = self.initial.get('retailer')
        elif self.instance and self.instance.retailer_id:
            retailer_id = self.instance.retailer_id

        if retailer_id:
            self.fields['bill'].queryset = Bill.objects.filter(
                retailer_id=retailer_id
            ).exclude(status='rejected').order_by('-created_at')
        else:
            self.fields['bill'].queryset = Bill.objects.exclude(status='rejected').order_by('-created_at')


class DeliverySignatureForm(forms.Form):
    signature_data = forms.CharField(widget=forms.HiddenInput(), required=False)


class UserProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            phone_number = phone_number.strip()
            qs = User.objects.filter(phone_number=phone_number)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("A user with this phone number already exists.")
        return phone_number


class RetailerProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = RetailerProfile
        fields = ['shop_name', 'address']
        widgets = {
            'shop_name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class SelfPasswordChangeForm(forms.Form):
    old_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Current Password'}),
        label="Current Password"
    )
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'New Password'}),
        label="New Password"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm New Password'}),
        label="Confirm New Password"
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_old_password(self):
        old_password = self.cleaned_data.get('old_password')
        if not self.user.check_password(old_password):
            raise forms.ValidationError("Current password is incorrect.")
        return old_password

    def clean(self):
        cleaned_data = super().clean()
        new_pass = cleaned_data.get('new_password')
        confirm_pass = cleaned_data.get('confirm_password')

        if new_pass and confirm_pass and new_pass != confirm_pass:
            raise forms.ValidationError("New passwords do not match.")
        return cleaned_data

