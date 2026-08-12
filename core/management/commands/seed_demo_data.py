from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import RetailerProfile, Item, Bill, Order, OrderItem, Collection
from decimal import Decimal
from django.utils import timezone

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds initial demo data for AB Traders Credit Management System'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Seeding demo data..."))

        # 1. SuperUser Account
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'first_name': 'System',
                'last_name': 'Administrator',
                'email': 'admin@abtraders.com',
                'phone_number': '9000000000',
                'role': User.Role.SUPERUSER,
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if created:
            admin_user.set_password('adminpass')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS("Created SuperUser: admin / adminpass"))

        # 2. Owner Account
        owner_user, created = User.objects.get_or_create(
            username='owner1',
            defaults={
                'first_name': 'Rajesh',
                'last_name': 'Sharma',
                'email': 'owner@abtraders.com',
                'phone_number': '9111111111',
                'role': User.Role.OWNER,
                'is_staff': True,
            }
        )
        if created:
            owner_user.set_password('ownerpass')
            owner_user.save()
            self.stdout.write(self.style.SUCCESS("Created Owner: owner1 / ownerpass"))

        # 3. Staff Accounts
        staff1, created = User.objects.get_or_create(
            username='staff1',
            defaults={
                'first_name': 'Amit',
                'last_name': 'Kumar',
                'email': 'amit@abtraders.com',
                'phone_number': '9222222222',
                'role': User.Role.STAFF,
                'is_staff': True,
            }
        )
        if created:
            staff1.set_password('staffpass')
            staff1.save()

        staff2, created = User.objects.get_or_create(
            username='staff2',
            defaults={
                'first_name': 'Suresh',
                'last_name': 'Verma',
                'email': 'suresh@abtraders.com',
                'phone_number': '9333333333',
                'role': User.Role.STAFF,
                'is_staff': True,
            }
        )
        if created:
            staff2.set_password('staffpass')
            staff2.save()
        self.stdout.write(self.style.SUCCESS("Created Field Staff: staff1, staff2 / staffpass"))

        # 4. Retailers
        retailer_data = [
            {
                'username': 'shop101',
                'shop_name': 'Apex Super Mart',
                'shop_number': 'SHOP-101',
                'phone_number': '9876543210',
                'address': '12 MG Road, Sector 4, City Center',
                'credit': Decimal('25000.00'),
            },
            {
                'username': 'shop102',
                'shop_name': 'City General Store',
                'shop_number': 'SHOP-102',
                'phone_number': '9876543211',
                'address': '45 Station Road, Near Bus Stand',
                'credit': Decimal('12500.00'),
            },
            {
                'username': 'shop103',
                'shop_name': 'Metro Provision Traders',
                'shop_number': 'SHOP-103',
                'phone_number': '9876543212',
                'address': '88 Market Complex, Main Bazaar',
                'credit': Decimal('45000.00'),
            },
        ]

        retailer_profiles = []
        for rdata in retailer_data:
            user, created = User.objects.get_or_create(
                username=rdata['username'],
                defaults={
                    'phone_number': rdata['phone_number'],
                    'role': User.Role.RETAILER,
                }
            )
            if created:
                user.set_password(rdata['phone_number'])
                user.save()

            profile, _ = RetailerProfile.objects.get_or_create(
                user=user,
                defaults={
                    'shop_number': rdata['shop_number'],
                    'shop_name': rdata['shop_name'],
                    'address': rdata['address'],
                    'credit_balance': rdata['credit'],
                }
            )
            retailer_profiles.append(profile)

        self.stdout.write(self.style.SUCCESS("Created 3 Retailers with passwordless phone login"))

        # 5. Inventory Items
        items_data = [
            {'name': 'Wheat Flour (Atta) 10kg Bag', 'description': 'Premium Whole Wheat Atta', 'price': Decimal('450.00'), 'stock': 150},
            {'name': 'Refined Cooking Oil 5L Can', 'description': 'Sun-flower refined edible oil', 'price': Decimal('720.00'), 'stock': 80},
            {'name': 'Basmati Rice 25kg Bag', 'description': 'Long grain aged aromatic rice', 'price': Decimal('1850.00'), 'stock': 40},
            {'name': 'Sugar 50kg Sack', 'description': 'Refined white refined sugar', 'price': Decimal('2100.00'), 'stock': 25},
            {'name': 'Tea Powder 1kg Pack', 'description': 'Strong CTC leaf tea', 'price': Decimal('380.00'), 'stock': 200},
        ]

        items = []
        for idata in items_data:
            item, _ = Item.objects.get_or_create(
                name=idata['name'],
                defaults={
                    'description': idata['description'],
                    'price': idata['price'],
                    'stock_quantity': idata['stock'],
                }
            )
            items.append(item)
        self.stdout.write(self.style.SUCCESS("Created 5 Inventory Items"))

        # 6. Sample Bills
        b1, _ = Bill.objects.get_or_create(
            bill_number='BILL-20260811-0001',
            defaults={
                'retailer': retailer_profiles[0],
                'created_by': owner_user,
                'total_amount': Decimal('12500.00'),
                'status': 'pending',
            }
        )
        b2, _ = Bill.objects.get_or_create(
            bill_number='BILL-20260811-0002',
            defaults={
                'retailer': retailer_profiles[1],
                'created_by': staff1,
                'total_amount': Decimal('8400.00'),
                'status': 'approved',
            }
        )
        b3, _ = Bill.objects.get_or_create(
            bill_number='BILL-20260811-0003',
            defaults={
                'retailer': retailer_profiles[2],
                'created_by': owner_user,
                'total_amount': Decimal('15000.00'),
                'status': 'rejected',
                'rejection_reason': 'Price discrepancy on cooking oil items. Awaiting revised bill.',
            }
        )

        # 7. Sample Orders
        order1, _ = Order.objects.get_or_create(
            id=1,
            defaults={
                'retailer': retailer_profiles[0],
                'taken_by_staff': staff1,
                'status': 'processing',
            }
        )
        if order1.items.count() == 0:
            OrderItem.objects.create(order=order1, item=items[0], quantity=10, price=items[0].price)
            OrderItem.objects.create(order=order1, item=items[1], quantity=5, price=items[1].price)

        order2, _ = Order.objects.get_or_create(
            id=2,
            defaults={
                'retailer': retailer_profiles[1],
                'taken_by_staff': staff2,
                'status': 'placed',
            }
        )
        if order2.items.count() == 0:
            OrderItem.objects.create(order=order2, item=items[2], quantity=2, price=items[2].price)

        # 8. Sample Collections
        Collection.objects.get_or_create(
            id=1,
            defaults={
                'retailer': retailer_profiles[0],
                'collected_by': staff1,
                'amount_collected': Decimal('5000.00'),
                'notes': 'Cash payment collected at shop premise.',
            }
        )
        Collection.objects.get_or_create(
            id=2,
            defaults={
                'retailer': retailer_profiles[1],
                'collected_by': staff2,
                'amount_collected': Decimal('2500.00'),
                'notes': 'UPI transfer receipt #UPI998822',
            }
        )

        self.stdout.write(self.style.SUCCESS("Demo data seeding completed successfully!"))
