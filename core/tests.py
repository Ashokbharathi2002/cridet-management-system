from django.test import TestCase, Client
from django.db import IntegrityError
from core.models import User, RetailerProfile, Order, Bill, Collection

class CMSFeatureRequirementsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.superuser = User.objects.create_superuser(
            username='admin',
            password='adminpassword',
            phone_number='9999999999',
            role=User.Role.SUPERUSER
        )
        self.owner = User.objects.create_user(
            username='owner1',
            password='ownerpassword',
            phone_number='8888888888',
            role=User.Role.OWNER
        )
        self.staff = User.objects.create_user(
            username='staff1',
            password='staffpassword',
            phone_number='7777777777',
            role=User.Role.STAFF
        )
        self.retailer_user = User.objects.create_user(
            username='retailer1',
            password='retailerpassword',
            phone_number='6666666666',
            role=User.Role.RETAILER
        )
        self.retailer_profile = RetailerProfile.objects.create(
            user=self.retailer_user,
            shop_number='SH001',
            shop_name='Test Retailer Shop',
            address='123 Retailer Lane'
        )

    def test_phone_number_unique_constraint(self):
        """1. Unique phone number enforcement."""
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                username='duplicate_phone_user',
                password='password123',
                phone_number='9999999999'  # Already taken by superuser
            )

    def test_restrict_superuser_owner_creation(self):
        """3. Restrict creation of Super User and Owner accounts to Super Users only."""
        self.client.force_login(self.owner)
        # Owner attempts to create a Superuser account -> form invalid (role choice restricted)
        response = self.client.post('/users/create/', {
            'username': 'unauthorized_admin',
            'password': 'password123',
            'confirm_password': 'password123',
            'phone_number': '1111111111',
            'role': User.Role.SUPERUSER
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='unauthorized_admin').exists())

        # Superuser creates an Owner account successfully
        self.client.force_login(self.superuser)
        response = self.client.post('/users/create/', {
            'username': 'new_owner',
            'password': 'password123',
            'confirm_password': 'password123',
            'phone_number': '2222222222',
            'role': User.Role.OWNER
        })
        self.assertRedirects(response, '/users/')
        self.assertTrue(User.objects.filter(username='new_owner').exists())

    def test_qr_code_generation_permissions_and_flow(self):
        """4 & 5. QR code generation for Retailer login and dashboard rendering."""
        # Staff is restricted from generating QR codes (redirected to dashboard)
        self.client.force_login(self.staff)
        res = self.client.get(f'/retailers/{self.retailer_profile.pk}/generate-qr/')
        self.assertRedirects(res, '/')

        # Superuser generates QR code
        self.client.force_login(self.superuser)
        res = self.client.get(f'/retailers/{self.retailer_profile.pk}/generate-qr/', follow=True)
        self.assertEqual(res.status_code, 200)

        self.retailer_profile.refresh_from_db()
        self.assertTrue(bool(self.retailer_profile.qr_code))

        # Retailer logs in and views QR on dashboard
        self.client.force_login(self.retailer_user)
        dashboard_res = self.client.get('/')
        self.assertEqual(dashboard_res.status_code, 200)
        self.assertContains(dashboard_res, 'Retailer Quick Login QR Code')

    def test_bill_specific_collection_processing(self):
        """6. Daily collection with specific bill selection and status update to paid."""
        bill = Bill.objects.create(
            bill_number='BILL-TEST-001',
            retailer=self.retailer_profile,
            created_by=self.superuser,
            total_amount=1500.00,
            status='approved'
        )
        self.retailer_profile.credit_balance = 1500.00
        self.retailer_profile.save()

        self.client.force_login(self.staff)
        res = self.client.post('/log-collection/', {
            'retailer': self.retailer_profile.pk,
            'bill': bill.pk,
            'amount_collected': '1500.00',
            'notes': 'Paid in cash for BILL-TEST-001'
        })
        self.assertRedirects(res, '/collections/')

        bill.refresh_from_db()
        self.assertEqual(bill.status, 'paid')

        self.retailer_profile.refresh_from_db()
        self.assertEqual(self.retailer_profile.credit_balance, 0.00)

    def test_itemized_bill_creation_and_stock_auto_deduction(self):
        """Automated stock deduction on bill creation."""
        from core.models import Item, Bill
        item = Item.objects.create(name='Test Item', price=100.00, stock_quantity=50)

        self.client.force_login(self.superuser)
        res = self.client.post('/bills/create/', {
            'retailer': self.retailer_profile.pk,
            f'quantity_{item.pk}': 10
        })
        self.assertRedirects(res, '/bills/')

        item.refresh_from_db()
        self.assertEqual(item.stock_quantity, 40)
        bill = Bill.objects.latest('id')
        self.assertEqual(bill.total_amount, 1000.00)

    def test_owner_bill_editing(self):
        """Owner editing bill number and itemized contents."""
        from core.models import Bill, Item
        item = Item.objects.create(name='Widget A', price=50.00, stock_quantity=100)
        bill = Bill.objects.create(
            bill_number='BILL-ORIGINAL-001',
            retailer=self.retailer_profile,
            created_by=self.superuser,
            total_amount=500.00,
            status='pending'
        )

        self.client.force_login(self.owner)
        res = self.client.post(f'/bills/{bill.pk}/edit/', {
            'bill_number': 'BILL-EDITED-999',
            'retailer': self.retailer_profile.pk,
            'status': 'approved',
            'total_amount': '750.00',
            f'quantity_{item.pk}': 15
        })
        self.assertRedirects(res, f'/bills/{bill.pk}/')

        bill.refresh_from_db()
        self.assertEqual(bill.bill_number, 'BILL-EDITED-999')
        self.assertEqual(bill.status, 'approved')
        self.assertEqual(bill.total_amount, 750.00)

    def test_negative_inventory_billing(self):
        """Negative inventory billing test."""
        from core.models import Item, Bill
        item = Item.objects.create(name='Low Stock Item', price=200.00, stock_quantity=5)

        self.client.force_login(self.superuser)
        res = self.client.post('/bills/create/', {
            'retailer': self.retailer_profile.pk,
            f'quantity_{item.pk}': 12
        })
        self.assertRedirects(res, '/bills/')

        item.refresh_from_db()
        self.assertEqual(item.stock_quantity, -7)

    def test_order_creation_with_note_and_timing(self):
        """Order creation with Order Note and Delivery Time."""
        from core.models import Item, Order
        item = Item.objects.create(name='Gadget B', price=300.00, stock_quantity=10)

        self.client.force_login(self.retailer_user)
        res = self.client.post('/orders/create/', {
            'order_note': 'Deliver via back entrance',
            'delivery_time': '2026-08-15T10:30',
            f'quantity_{item.pk}': 2
        })
        order = Order.objects.latest('id')
        self.assertRedirects(res, f'/orders/{order.pk}/')
        self.assertEqual(order.order_note, 'Deliver via back entrance')
        self.assertIsNotNone(order.delivery_time)

    def test_order_cancellation_and_deletion(self):
        """Order cancellation and deletion flow."""
        from core.models import Order
        order = Order.objects.create(
            retailer=self.retailer_profile,
            taken_by_staff=self.staff,
            status='placed'
        )

        # Retailer cancels order
        self.client.force_login(self.retailer_user)
        res = self.client.get(f'/orders/{order.pk}/cancel/')
        self.assertRedirects(res, f'/orders/{order.pk}/')
        order.refresh_from_db()
        self.assertEqual(order.status, 'cancelled')

        # Superuser deletes order
        self.client.force_login(self.superuser)
        del_res = self.client.get(f'/orders/{order.pk}/delete/')
        self.assertRedirects(del_res, '/orders/')
        self.assertFalse(Order.objects.filter(pk=order.pk).exists())

