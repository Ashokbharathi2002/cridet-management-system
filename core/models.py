from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from decimal import Decimal

class User(AbstractUser):
    class Role(models.TextChoices):
        SUPERUSER = 'SUPERUSER', 'SuperUser'
        OWNER = 'OWNER', 'Owner'
        STAFF = 'STAFF', 'Staff'
        RETAILER = 'RETAILER', 'Retailer'

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.RETAILER)
    phone_number = models.CharField(max_length=15, unique=True, blank=True, null=True)
    is_locked = models.BooleanField(default=False, help_text="Locked users cannot log in.")

    def is_superuser_role(self):
        return self.role == self.Role.SUPERUSER or self.is_superuser

    def is_owner_role(self):
        return self.role == self.Role.OWNER

    def is_staff_role(self):
        return self.role == self.Role.STAFF

    def is_retailer_role(self):
        return self.role == self.Role.RETAILER

    @property
    def display_name(self):
        full_name = self.get_full_name().strip()
        return full_name if full_name else self.username

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class RetailerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='retailer_profile')
    shop_number = models.CharField(max_length=50, unique=True)
    shop_name = models.CharField(max_length=150)
    address = models.TextField()
    credit_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    qr_code = models.ImageField(upload_to='qr_codes/', null=True, blank=True)

    def __str__(self):
        return f"{self.shop_name} ({self.shop_number})"


class Item(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - ₹{self.price} (Stock: {self.stock_quantity})"


class Bill(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('rejected', 'Rejected'),
    )

    bill_number = models.CharField(max_length=50, unique=True)
    retailer = models.ForeignKey(RetailerProfile, on_delete=models.CASCADE, related_name='bills')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_bills')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    rejection_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Bill #{self.bill_number} - {self.retailer.shop_name} - ₹{self.total_amount}"


class BillItem(models.Model):
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def subtotal(self):
        return Decimal(self.quantity) * self.price

    def __str__(self):
        return f"{self.quantity} x {self.item.name} for Bill #{self.bill.bill_number}"


class Order(models.Model):
    STATUS_CHOICES = (
        ('placed', 'Placed'),
        ('processing', 'Processing'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    )

    retailer = models.ForeignKey(RetailerProfile, on_delete=models.CASCADE, related_name='orders')
    taken_by_staff = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='taken_orders')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='placed')
    digital_signature = models.ImageField(upload_to='signatures/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def total_amount(self):
        return sum(item.subtotal for item in self.items.all())

    def __str__(self):
        return f"Order #{self.id} - {self.retailer.shop_name} ({self.get_status_display()})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def subtotal(self):
        return Decimal(self.quantity) * self.price

    def __str__(self):
        return f"{self.quantity} x {self.item.name} for Order #{self.order.id}"


class Collection(models.Model):
    retailer = models.ForeignKey(RetailerProfile, on_delete=models.CASCADE, related_name='collections')
    collected_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='collected_payments')
    bill = models.ForeignKey(Bill, on_delete=models.SET_NULL, null=True, blank=True, related_name='collections')
    amount_collected = models.DecimalField(max_digits=12, decimal_places=2)
    collected_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Collection ₹{self.amount_collected} from {self.retailer.shop_name}"
