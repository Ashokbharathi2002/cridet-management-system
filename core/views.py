import base64
import io
import uuid
import qrcode
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.db.models import Sum, Q, Count, F
from django.utils import timezone

from .models import User, RetailerProfile, Item, Bill, Order, OrderItem, Collection
from .forms import (
    StaffLoginForm, RetailerLoginForm, UserCreateForm, UserEditForm,
    PasswordResetAdminForm, RetailerOnboardingForm, ItemForm, BillForm,
    BillRejectForm, CollectionForm, DeliverySignatureForm,
    UserProfileUpdateForm, RetailerProfileUpdateForm, SelfPasswordChangeForm
)
from .decorators import role_required

User = get_user_model()


# ==========================================
# AUTHENTICATION VIEWS
# ==========================================

def login_view(request):
    """Standard Login for SuperUser, Owner, and Staff."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = StaffLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)

            if user is not None:
                if user.is_locked:
                    messages.error(request, "Your account is locked by an administrator.")
                elif not user.is_active:
                    messages.error(request, "Your account is inactive.")
                else:
                    login(request, user)
                    messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
                    return redirect('dashboard')
            else:
                messages.error(request, "Invalid username or password.")
    else:
        form = StaffLoginForm()

    return render(request, 'login.html', {'form': form})


def retailer_login_view(request):
    """Passwordless Authentication for Retailers using shop_number and phone_number."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = RetailerLoginForm(request.POST)
        if form.is_valid():
            shop_number = form.cleaned_data['shop_number'].strip()
            phone_number = form.cleaned_data['phone_number'].strip()

            try:
                profile = RetailerProfile.objects.select_related('user').get(shop_number__iexact=shop_number)
                user = profile.user

                if user.phone_number and user.phone_number.strip() == phone_number:
                    if user.is_locked:
                        messages.error(request, "Your account is locked by an administrator.")
                    elif not user.is_active:
                        messages.error(request, "Your retailer account is inactive.")
                    else:
                        login(request, user)
                        messages.success(request, f"Welcome to AB Traders, {profile.shop_name}!")
                        return redirect('dashboard')
                else:
                    messages.error(request, "Phone number does not match registered shop records.")
            except RetailerProfile.DoesNotExist:
                messages.error(request, f"No retailer account found for shop number: {shop_number}")
    else:
        shop_number = request.GET.get('shop_number', '').strip()
        phone_number = request.GET.get('phone_number', '').strip()
        if shop_number and phone_number:
            try:
                profile = RetailerProfile.objects.select_related('user').get(shop_number__iexact=shop_number)
                user = profile.user
                if user.phone_number and user.phone_number.strip() == phone_number and user.is_active and not user.is_locked:
                    login(request, user)
                    messages.success(request, f"QR Code authentication successful! Welcome to AB Traders, {profile.shop_name}!")
                    return redirect('dashboard')
            except RetailerProfile.DoesNotExist:
                pass
            form = RetailerLoginForm(initial={'shop_number': shop_number, 'phone_number': phone_number})
        else:
            form = RetailerLoginForm()

    return render(request, 'retailer_login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('login')


# ==========================================
# DASHBOARD ROUTER & MAIN VIEWS
# ==========================================

@login_required
def dashboard_view(request):
    """Dispatches user to their role-specific dashboard."""
    user = request.user

    if user.is_locked:
        logout(request)
        messages.error(request, "Your account is locked.")
        return redirect('login')

    if user.is_superuser_role():
        total_users = User.objects.count()
        total_retailers = RetailerProfile.objects.count()
        total_bills = Bill.objects.count()
        total_collections = Collection.objects.aggregate(Sum('amount_collected'))['amount_collected__sum'] or Decimal('0.00')
        total_credit_outstanding = RetailerProfile.objects.aggregate(Sum('credit_balance'))['credit_balance__sum'] or Decimal('0.00')
        recent_users = User.objects.order_by('-date_joined')[:5]

        context = {
            'total_users': total_users,
            'total_retailers': total_retailers,
            'total_bills': total_bills,
            'total_collections': total_collections,
            'total_credit_outstanding': total_credit_outstanding,
            'recent_users': recent_users,
        }
        return render(request, 'dashboard_superuser.html', context)

    elif user.is_owner_role():
        total_retailers = RetailerProfile.objects.count()
        total_staff = User.objects.filter(role=User.Role.STAFF).count()
        total_credit = RetailerProfile.objects.aggregate(Sum('credit_balance'))['credit_balance__sum'] or Decimal('0.00')
        total_collections = Collection.objects.aggregate(Sum('amount_collected'))['amount_collected__sum'] or Decimal('0.00')
        todays_collections = Collection.objects.filter(
            collected_at__date=timezone.now().date()
        ).aggregate(Sum('amount_collected'))['amount_collected__sum'] or Decimal('0.00')
        pending_bills = Bill.objects.filter(status='pending').count()
        recent_bills = Bill.objects.select_related('retailer').order_by('-created_at')[:5]
        recent_collections = Collection.objects.select_related('retailer', 'collected_by').order_by('-collected_at')[:5]

        context = {
            'total_retailers': total_retailers,
            'total_staff': total_staff,
            'total_credit': total_credit,
            'total_collections': total_collections,
            'todays_collections': todays_collections,
            'pending_bills': pending_bills,
            'recent_bills': recent_bills,
            'recent_collections': recent_collections,
        }
        return render(request, 'dashboard_owner.html', context)

    elif user.is_staff_role():
        retailers = RetailerProfile.objects.all()
        pending_bills = Bill.objects.filter(status='pending').count()
        todays_collections = Collection.objects.filter(
            collected_by=user,
            collected_at__date=timezone.now().date()
        ).aggregate(Sum('amount_collected'))['amount_collected__sum'] or Decimal('0.00')
        pending_orders = Order.objects.filter(status__in=['placed', 'processing'])

        context = {
            'retailers': retailers,
            'pending_bills': pending_bills,
            'todays_collections': todays_collections,
            'pending_orders': pending_orders,
        }
        return render(request, 'dashboard_staff.html', context)

    elif user.is_retailer_role():
        profile = getattr(user, 'retailer_profile', None)
        if not profile:
            messages.error(request, "Retailer profile missing. Contact support.")
            return render(request, 'dashboard_retailer.html', {'profile': None})

        my_bills = Bill.objects.filter(retailer=profile).order_by('-created_at')
        my_orders = Order.objects.filter(retailer=profile).order_by('-created_at')
        my_collections = Collection.objects.filter(retailer=profile).order_by('-collected_at')[:5]

        context = {
            'profile': profile,
            'my_bills': my_bills,
            'my_orders': my_orders,
            'my_collections': my_collections,
        }
        return render(request, 'dashboard_retailer.html', context)

    messages.error(request, "Role not recognized.")
    return redirect('login')


# ==========================================
# SUPERUSER & OWNER USER MANAGEMENT VIEWS
# ==========================================

@role_required(['SUPERUSER', 'OWNER'])
def user_list_view(request):
    query = request.GET.get('q', '')
    role_filter = request.GET.get('role', '')

    users = User.objects.all().order_by('-id')

    if not (request.user.is_superuser or request.user.role == 'SUPERUSER'):
        # Owners can manage Staff and Retailers only
        users = users.filter(role__in=[User.Role.STAFF, User.Role.RETAILER])

    if query:
        users = users.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(phone_number__icontains=query)
        )

    if role_filter:
        users = users.filter(role=role_filter)

    return render(request, 'user_list.html', {'users': users, 'query': query, 'role_filter': role_filter})


@role_required(['SUPERUSER', 'OWNER'])
def user_create_view(request):
    if request.method == 'POST':
        form = UserCreateForm(request.POST, request_user=request.user)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            
            # Non-superusers cannot create Superuser or Owner accounts
            if not request.user.is_superuser_role() and user.role in [User.Role.SUPERUSER, User.Role.OWNER]:
                messages.error(request, "Only Super Users can create Super User or Owner accounts.")
                return redirect('user_list')
                
            user.save()
            messages.success(request, f"User '{user.username}' created successfully.")
            return redirect('user_list')
    else:
        form = UserCreateForm(request_user=request.user)

    return render(request, 'user_form.html', {'form': form, 'title': 'Create New User'})


@role_required(['SUPERUSER', 'OWNER'])
def user_edit_view(request, pk):
    target_user = get_object_or_404(User, pk=pk)

    if not request.user.is_superuser_role() and target_user.role in [User.Role.SUPERUSER, User.Role.OWNER]:
        messages.error(request, "Only Super Users can edit Super User or Owner accounts.")
        return redirect('user_list')

    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=target_user, request_user=request.user)
        if form.is_valid():
            user_obj = form.save(commit=False)
            if not request.user.is_superuser_role() and user_obj.role in [User.Role.SUPERUSER, User.Role.OWNER]:
                messages.error(request, "Only Super Users can assign Super User or Owner roles.")
                return redirect('user_list')
            user_obj.save()
            messages.success(request, f"User '{target_user.username}' updated successfully.")
            return redirect('user_list')
    else:
        form = UserEditForm(instance=target_user, request_user=request.user)

    return render(request, 'user_form.html', {'form': form, 'title': f'Edit User: {target_user.username}'})


@role_required(['SUPERUSER', 'OWNER'])
def user_toggle_lock_view(request, pk):
    target_user = get_object_or_404(User, pk=pk)
    if target_user == request.user:
        messages.error(request, "You cannot lock your own account.")
        return redirect('user_list')

    target_user.is_locked = not target_user.is_locked
    target_user.save()
    status_str = "locked" if target_user.is_locked else "unlocked"
    messages.success(request, f"User '{target_user.username}' has been {status_str}.")
    return redirect('user_list')


@role_required(['SUPERUSER', 'OWNER'])
def user_toggle_active_view(request, pk):
    target_user = get_object_or_404(User, pk=pk)
    if target_user == request.user:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect('user_list')

    target_user.is_active = not target_user.is_active
    target_user.save()
    status_str = "activated" if target_user.is_active else "deactivated"
    messages.success(request, f"User '{target_user.username}' has been {status_str}.")
    return redirect('user_list')


@role_required(['SUPERUSER', 'OWNER'])
def user_reset_password_view(request, pk):
    target_user = get_object_or_404(User, pk=pk)

    if request.method == 'POST':
        form = PasswordResetAdminForm(request.POST)
        if form.is_valid():
            target_user.set_password(form.cleaned_data['new_password'])
            target_user.save()
            messages.success(request, f"Password for '{target_user.username}' reset successfully.")
            return redirect('user_list')
    else:
        form = PasswordResetAdminForm()

    return render(request, 'user_reset_password.html', {'form': form, 'target_user': target_user})


@role_required(['SUPERUSER'])
def user_delete_view(request, pk):
    target_user = get_object_or_404(User, pk=pk)
    if target_user == request.user:
        messages.error(request, "You cannot delete your own account.")
        return redirect('user_list')

    username = target_user.username
    target_user.delete()
    messages.success(request, f"User '{username}' has been deleted.")
    return redirect('user_list')


# ==========================================
# RETAILER ONBOARDING & FIELD OPERATIONS
# ==========================================

@role_required(['SUPERUSER', 'OWNER', 'STAFF'])
def onboard_retailer_view(request):
    if request.method == 'POST':
        form = RetailerOnboardingForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            shop_name = form.cleaned_data['shop_name']
            shop_number = form.cleaned_data['shop_number']
            phone_number = form.cleaned_data['phone_number']
            address = form.cleaned_data['address']
            initial_credit = form.cleaned_data['initial_credit_balance']

            # Create User for Retailer
            user = User.objects.create_user(
                username=username,
                phone_number=phone_number,
                role=User.Role.RETAILER
            )
            # Default password set to phone_number
            user.set_password(phone_number)
            user.save()

            # Create RetailerProfile
            profile = RetailerProfile.objects.create(
                user=user,
                shop_number=shop_number,
                shop_name=shop_name,
                address=address,
                credit_balance=initial_credit
            )

            messages.success(request, f"Retailer '{shop_name}' ({shop_number}) onboarded successfully!")
            return redirect('dashboard')
    else:
        form = RetailerOnboardingForm()

    return render(request, 'retailer_onboard.html', {'form': form})


@role_required(['SUPERUSER', 'OWNER', 'STAFF'])
def log_collection_view(request):
    """Log daily collection per retailer and optionally apply to a specific bill."""
    if request.method == 'POST':
        form = CollectionForm(request.POST)
        if form.is_valid():
            collection = form.save(commit=False)
            collection.collected_by = request.user
            collection.save()

            # Deduct collected amount from retailer's outstanding credit balance
            retailer = collection.retailer
            retailer.credit_balance -= collection.amount_collected
            retailer.save()

            # Update selected bill status to paid
            if collection.bill:
                collection.bill.status = 'paid'
                collection.bill.save()
                messages.success(
                    request,
                    f"Collection of ₹{collection.amount_collected} logged for '{retailer.shop_name}'. Applied to Bill #{collection.bill.bill_number} (Status: Paid). Remaining Credit: ₹{retailer.credit_balance}"
                )
            else:
                messages.success(
                    request,
                    f"Collection of ₹{collection.amount_collected} from '{retailer.shop_name}' logged. Remaining Credit: ₹{retailer.credit_balance}"
                )
            return redirect('collections_list')
    else:
        retailer_id = request.GET.get('retailer_id')
        bill_id = request.GET.get('bill_id')
        initial = {}
        if retailer_id:
            initial['retailer'] = retailer_id
        if bill_id:
            try:
                bill_obj = Bill.objects.get(pk=bill_id)
                initial['retailer'] = bill_obj.retailer_id
                initial['bill'] = bill_obj.pk
                initial['amount_collected'] = bill_obj.total_amount
            except Bill.DoesNotExist:
                pass
        form = CollectionForm(initial=initial)

    return render(request, 'collection_form.html', {'form': form})


@role_required(['SUPERUSER', 'OWNER'])
def generate_retailer_qr_view(request, pk):
    """Generate Login QR Code for a Retailer Profile (SuperUser & Owner only)."""
    retailer = get_object_or_404(RetailerProfile, pk=pk)
    phone_number = retailer.user.phone_number or ''
    login_url = f"{request.scheme}://{request.get_host()}/retailer-login/?shop_number={retailer.shop_number}&phone_number={phone_number}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(login_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    file_name = f"qr_{retailer.shop_number}.png"
    retailer.qr_code.save(file_name, ContentFile(buffer.getvalue()), save=True)

    messages.success(request, f"QR code generated successfully for Retailer '{retailer.shop_name}'!")
    return redirect(request.META.get('HTTP_REFERER', 'user_list'))


@role_required(['SUPERUSER', 'OWNER', 'STAFF', 'RETAILER'])
def collections_list_view(request):
    if request.user.is_retailer_role():
        profile = getattr(request.user, 'retailer_profile', None)
        base_qs = Collection.objects.filter(retailer=profile).order_by('-collected_at')
    else:
        query = request.GET.get('q', '')
        base_qs = Collection.objects.select_related('retailer', 'collected_by', 'bill').order_by('-collected_at')
        if query:
            base_qs = base_qs.filter(
                Q(retailer__shop_name__icontains=query) |
                Q(retailer__shop_number__icontains=query) |
                Q(notes__icontains=query)
            )

    todays_collections = base_qs.filter(collected_at__date=timezone.now().date())
    todays_total = todays_collections.aggregate(Sum('amount_collected'))['amount_collected__sum'] or Decimal('0.00')
    overall_total = base_qs.aggregate(Sum('amount_collected'))['amount_collected__sum'] or Decimal('0.00')

    context = {
        'todays_collections': todays_collections,
        'overall_collections': base_qs,
        'todays_total': todays_total,
        'overall_total': overall_total,
    }
    return render(request, 'collections_list.html', context)


@role_required(['SUPERUSER', 'OWNER', 'STAFF'])
def credit_balances_view(request):
    query = request.GET.get('q', '')
    retailers = RetailerProfile.objects.all().order_by('-credit_balance')

    if query:
        retailers = retailers.filter(
            Q(shop_name__icontains=query) |
            Q(shop_number__icontains=query) |
            Q(user__phone_number__icontains=query)
        )

    pending_bills = Bill.objects.filter(status='pending').select_related('retailer')

    context = {
        'retailers': retailers,
        'pending_bills': pending_bills,
        'query': query,
    }
    return render(request, 'credit_balances.html', context)


# ==========================================
# INVENTORY MANAGEMENT VIEWS (ITEM)
# ==========================================

@role_required(['SUPERUSER', 'OWNER', 'STAFF', 'RETAILER'])
def inventory_list_view(request):
    query = request.GET.get('q', '')
    items = Item.objects.all().order_by('name')

    if query:
        items = items.filter(Q(name__icontains=query) | Q(description__icontains=query))

    return render(request, 'inventory_list.html', {'items': items, 'query': query})


@role_required(['SUPERUSER', 'OWNER'])
def item_create_view(request):
    if request.method == 'POST':
        form = ItemForm(request.POST)
        if form.is_valid():
            item = form.save()
            messages.success(request, f"Item '{item.name}' added successfully.")
            return redirect('inventory_list')
    else:
        form = ItemForm()

    return render(request, 'item_form.html', {'form': form, 'title': 'Add New Item'})


@role_required(['SUPERUSER', 'OWNER'])
def item_edit_view(request, pk):
    item = get_object_or_404(Item, pk=pk)

    if request.method == 'POST':
        form = ItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, f"Item '{item.name}' updated successfully.")
            return redirect('inventory_list')
    else:
        form = ItemForm(instance=item)

    return render(request, 'item_form.html', {'form': form, 'title': f'Edit Item: {item.name}'})


@role_required(['SUPERUSER', 'OWNER'])
def item_delete_view(request, pk):
    item = get_object_or_404(Item, pk=pk)
    name = item.name
    item.delete()
    messages.success(request, f"Item '{name}' deleted successfully.")
    return redirect('inventory_list')


# ==========================================
# BILL MANAGEMENT VIEWS
# ==========================================

@role_required(['SUPERUSER', 'OWNER', 'STAFF', 'RETAILER'])
def bill_list_view(request):
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')

    if request.user.is_retailer_role():
        profile = getattr(request.user, 'retailer_profile', None)
        bills = Bill.objects.filter(retailer=profile).order_by('-created_at')
    else:
        bills = Bill.objects.select_related('retailer', 'created_by').order_by('-created_at')

    if query:
        bills = bills.filter(
            Q(bill_number__icontains=query) |
            Q(retailer__shop_name__icontains=query) |
            Q(retailer__shop_number__icontains=query)
        )

    if status_filter:
        bills = bills.filter(status=status_filter)

    return render(request, 'bill_list.html', {'bills': bills, 'query': query, 'status_filter': status_filter})


@role_required(['SUPERUSER', 'OWNER', 'STAFF'])
def bill_create_view(request):
    items = Item.objects.all().order_by('name')

    if request.method == 'POST':
        form = BillForm(request.POST)
        if form.is_valid():
            bill = form.save(commit=False)
            bill.created_by = request.user
            bill.bill_number = f"BILL-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
            bill.status = 'pending'
            
            # Check items and inventory stock
            total_calc = Decimal('0.00')
            bill_items_to_create = []

            for key, val in request.POST.items():
                if key.startswith('quantity_'):
                    item_id = key.split('_')[1]
                    try:
                        qty = int(val)
                        if qty > 0:
                            item_obj = Item.objects.get(pk=item_id)
                            if qty > item_obj.stock_quantity:
                                messages.error(request, f"Insufficient stock for '{item_obj.name}'. Available: {item_obj.stock_quantity}, requested: {qty}.")
                                return render(request, 'bill_create.html', {'form': form, 'items': items})
                            bill_items_to_create.append((item_obj, qty, item_obj.price))
                            total_calc += (Decimal(qty) * item_obj.price)
                    except (ValueError, Item.DoesNotExist):
                        pass

            if bill_items_to_create:
                bill.total_amount = total_calc
            elif not bill.total_amount:
                bill.total_amount = Decimal('0.00')

            bill.save()

            # Create BillItems and auto-deduct stock
            from .models import BillItem
            for item_obj, qty, price in bill_items_to_create:
                BillItem.objects.create(
                    bill=bill,
                    item=item_obj,
                    quantity=qty,
                    price=price
                )
                item_obj.stock_quantity = max(0, item_obj.stock_quantity - qty)
                item_obj.save()

            messages.success(request, f"Bill #{bill.bill_number} generated for {bill.retailer.shop_name}! Stock updated automatically.")
            return redirect('bill_list')
    else:
        retailer_id = request.GET.get('retailer_id')
        initial = {}
        if retailer_id:
            initial['retailer'] = retailer_id
        form = BillForm(initial=initial)

    return render(request, 'bill_create.html', {'form': form, 'items': items})


@role_required(['SUPERUSER', 'OWNER', 'STAFF', 'RETAILER'])
def bill_detail_view(request, pk):
    bill = get_object_or_404(Bill, pk=pk)

    if request.user.is_retailer_role():
        profile = getattr(request.user, 'retailer_profile', None)
        if bill.retailer != profile:
            messages.error(request, "Access denied.")
            return redirect('dashboard')

    return render(request, 'bill_detail.html', {'bill': bill})


@role_required(['RETAILER', 'SUPERUSER', 'OWNER', 'STAFF'])
def approve_bill_view(request, pk):
    bill = get_object_or_404(Bill, pk=pk)

    if request.user.is_retailer_role():
        profile = getattr(request.user, 'retailer_profile', None)
        if bill.retailer != profile:
            messages.error(request, "Unauthorized action.")
            return redirect('dashboard')

    if bill.status != 'pending':
        messages.warning(request, f"Bill is already {bill.status}.")
        return redirect('bill_detail', pk=bill.pk)

    bill.status = 'approved'
    bill.save()

    # Add bill amount to retailer's credit balance
    retailer = bill.retailer
    retailer.credit_balance += bill.total_amount
    retailer.save()

    messages.success(request, f"Bill #{bill.bill_number} approved! Total credit balance updated.")
    return redirect('bill_detail', pk=bill.pk)


@role_required(['RETAILER', 'SUPERUSER', 'OWNER', 'STAFF'])
def reject_bill_view(request, pk):
    bill = get_object_or_404(Bill, pk=pk)

    if request.user.is_retailer_role():
        profile = getattr(request.user, 'retailer_profile', None)
        if bill.retailer != profile:
            messages.error(request, "Unauthorized action.")
            return redirect('dashboard')

    if bill.status != 'pending':
        messages.warning(request, f"Bill is already {bill.status}.")
        return redirect('bill_detail', pk=bill.pk)

    if request.method == 'POST':
        form = BillRejectForm(request.POST)
        if form.is_valid():
            bill.status = 'rejected'
            bill.rejection_reason = form.cleaned_data['rejection_reason']
            bill.save()
            messages.info(request, f"Bill #{bill.bill_number} rejected.")
            return redirect('bill_detail', pk=bill.pk)
    else:
        form = BillRejectForm()

    return render(request, 'bill_reject.html', {'form': form, 'bill': bill})


@role_required(['SUPERUSER', 'OWNER'])
def bill_edit_view(request, pk):
    """Allows Owner and Superuser to edit bill numbers, retailer, status, and itemized contents."""
    from .models import BillItem
    from .forms import BillEditForm
    bill = get_object_or_404(Bill, pk=pk)
    available_items = Item.objects.all().order_by('name')

    if request.method == 'POST':
        form = BillEditForm(request.POST, instance=bill)
        if form.is_valid():
            edited_bill = form.save(commit=False)
            
            # Update items if provided in POST
            has_posted_items = any(key.startswith('quantity_') for key in request.POST)
            if has_posted_items:
                # Delete existing bill items
                bill.items.all().delete()
                total_calc = Decimal('0.00')
                for key, val in request.POST.items():
                    if key.startswith('quantity_'):
                        item_id = key.split('_')[1]
                        try:
                            qty = int(val)
                            if qty > 0:
                                item_obj = Item.objects.get(pk=item_id)
                                BillItem.objects.create(
                                    bill=edited_bill,
                                    item=item_obj,
                                    quantity=qty,
                                    price=item_obj.price
                                )
                                total_calc += (Decimal(qty) * item_obj.price)
                        except (ValueError, Item.DoesNotExist):
                            pass
                if total_calc > 0:
                    edited_bill.total_amount = total_calc

            edited_bill.save()
            messages.success(request, f"Bill #{edited_bill.bill_number} updated successfully!")
            return redirect('bill_detail', pk=edited_bill.pk)
    else:
        form = BillEditForm(instance=bill)

    context = {
        'form': form,
        'bill': bill,
        'available_items': available_items,
        'bill_items': bill.items.select_related('item').all()
    }
    return render(request, 'bill_edit.html', context)


# ==========================================
# ORDER MANAGEMENT VIEWS
# ==========================================

@role_required(['SUPERUSER', 'OWNER', 'STAFF', 'RETAILER'])
def order_list_view(request):
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')

    if request.user.is_retailer_role():
        profile = getattr(request.user, 'retailer_profile', None)
        orders = Order.objects.filter(retailer=profile).order_by('-created_at')
    else:
        orders = Order.objects.select_related('retailer', 'taken_by_staff').order_by('-created_at')

    if query:
        orders = orders.filter(
            Q(id__icontains=query) |
            Q(retailer__shop_name__icontains=query)
        )

    if status_filter:
        orders = orders.filter(status=status_filter)

    return render(request, 'order_list.html', {'orders': orders, 'query': query, 'status_filter': status_filter})


@role_required(['SUPERUSER', 'OWNER', 'STAFF', 'RETAILER'])
def order_create_view(request):
    items = Item.objects.filter(stock_quantity__gt=0)

    if request.method == 'POST':
        if request.user.is_retailer_role():
            retailer = getattr(request.user, 'retailer_profile', None)
            staff_user = None
        else:
            retailer_id = request.POST.get('retailer_id')
            retailer = get_object_or_404(RetailerProfile, pk=retailer_id)
            staff_user = request.user

        order = Order.objects.create(
            retailer=retailer,
            taken_by_staff=staff_user,
            status='placed'
        )

        total = Decimal('0.00')
        has_items = False

        for key, val in request.POST.items():
            if key.startswith('quantity_'):
                item_id = key.split('_')[1]
                try:
                    qty = int(val)
                    if qty > 0:
                        item_obj = Item.objects.get(pk=item_id)
                        OrderItem.objects.create(
                            order=order,
                            item=item_obj,
                            quantity=qty,
                            price=item_obj.price
                        )
                        total += (Decimal(qty) * item_obj.price)
                        has_items = True
                except (ValueError, Item.DoesNotExist):
                    pass

        if not has_items:
            order.delete()
            messages.error(request, "Please select at least one item to place an order.")
            return render(request, 'order_create.html', {
                'items': items,
                'retailers': RetailerProfile.objects.all() if not request.user.is_retailer_role() else None
            })

        messages.success(request, f"Order #{order.id} placed successfully!")
        return redirect('order_detail', pk=order.pk)

    retailers = RetailerProfile.objects.all() if not request.user.is_retailer_role() else None
    return render(request, 'order_create.html', {'items': items, 'retailers': retailers})


@role_required(['SUPERUSER', 'OWNER', 'STAFF', 'RETAILER'])
def order_detail_view(request, pk):
    order = get_object_or_404(Order, pk=pk)

    if request.user.is_retailer_role():
        profile = getattr(request.user, 'retailer_profile', None)
        if order.retailer != profile:
            messages.error(request, "Access denied.")
            return redirect('dashboard')

    return render(request, 'order_detail.html', {'order': order})


@role_required(['SUPERUSER', 'OWNER', 'STAFF'])
def order_edit_view(request, pk):
    """Allows Superuser, Owner, and Staff to edit order items and quantities."""
    order = get_object_or_404(Order, pk=pk)
    available_items = Item.objects.all().order_by('name')

    if request.method == 'POST':
        retailer_id = request.POST.get('retailer_id')
        if retailer_id:
            order.retailer = get_object_or_404(RetailerProfile, pk=retailer_id)

        # Update order items
        order.items.all().delete()
        has_items = False

        for key, val in request.POST.items():
            if key.startswith('quantity_'):
                item_id = key.split('_')[1]
                try:
                    qty = int(val)
                    if qty > 0:
                        item_obj = Item.objects.get(pk=item_id)
                        OrderItem.objects.create(
                            order=order,
                            item=item_obj,
                            quantity=qty,
                            price=item_obj.price
                        )
                        has_items = True
                except (ValueError, Item.DoesNotExist):
                    pass

        if not has_items:
            messages.error(request, "Order must contain at least one item.")
        else:
            order.save()
            messages.success(request, f"Order #{order.id} details updated successfully!")

        return redirect('order_detail', pk=order.pk)

    context = {
        'order': order,
        'available_items': available_items,
        'retailers': RetailerProfile.objects.all(),
        'order_items_dict': {item.item_id: item.quantity for item in order.items.all()}
    }
    return render(request, 'order_edit.html', context)


@role_required(['SUPERUSER', 'OWNER', 'STAFF'])
def deliver_order_view(request, pk):
    """Mark order as delivered with base64 digital signature upload from HTML5 Canvas."""
    from .models import BillItem
    order = get_object_or_404(Order, pk=pk)

    if request.method == 'POST':
        form = DeliverySignatureForm(request.POST)
        if form.is_valid():
            sig_data = form.cleaned_data.get('signature_data')
            
            if sig_data and 'base64,' in sig_data:
                format_str, imgstr = sig_data.split(';base64,')
                ext = format_str.split('/')[-1]
                data = ContentFile(base64.b64decode(imgstr), name=f"sig_order_{order.id}.{ext}")
                order.digital_signature = data

            order.status = 'delivered'
            order.save()

            # Auto-generate an itemized Bill for the delivered order and reduce item stock
            if order.total_amount > 0:
                bill_num = f"BILL-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
                bill = Bill.objects.create(
                    bill_number=bill_num,
                    retailer=order.retailer,
                    created_by=request.user,
                    total_amount=order.total_amount,
                    status='pending'
                )

                for order_item in order.items.select_related('item').all():
                    BillItem.objects.create(
                        bill=bill,
                        item=order_item.item,
                        quantity=order_item.quantity,
                        price=order_item.price
                    )
                    # Automatically deduct inventory stock quantity
                    order_item.item.stock_quantity = max(0, order_item.item.stock_quantity - order_item.quantity)
                    order_item.item.save()

                messages.success(
                    request,
                    f"Order #{order.id} marked as Delivered with signature! Generated pending Bill #{bill.bill_number} for ₹{bill.total_amount} and updated stock levels."
                )
            else:
                messages.success(request, f"Order #{order.id} marked as Delivered!")

            return redirect('order_detail', pk=order.pk)
    else:
        form = DeliverySignatureForm()

    return render(request, 'deliver_order.html', {'order': order, 'form': form})


# ==========================================
# OWNER ANALYTICS & FINANCIAL DASHBOARD
# ==========================================

@role_required(['SUPERUSER', 'OWNER'])
def owner_analytics_view(request):
    import json
    from datetime import timedelta
    today = timezone.now().date()

    total_credit_outstanding = RetailerProfile.objects.aggregate(Sum('credit_balance'))['credit_balance__sum'] or Decimal('0.00')
    total_collections = Collection.objects.aggregate(Sum('amount_collected'))['amount_collected__sum'] or Decimal('0.00')
    total_approved_bills = Bill.objects.filter(status__in=['approved', 'paid']).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
    pending_bills_amount = Bill.objects.filter(status='pending').aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')

    # Top Credit Debtors
    top_debtors = RetailerProfile.objects.order_by('-credit_balance')[:5]

    # Bill Status Breakdown
    approved_count = Bill.objects.filter(status__in=['approved', 'paid']).count()
    pending_count = Bill.objects.filter(status='pending').count()
    rejected_count = Bill.objects.filter(status='rejected').count()

    # Monthly P&L Trend (Last 6 Months)
    months = []
    revenue_data = []
    expense_data = []
    profit_data = []

    for i in range(5, -1, -1):
        # Month start and end
        first_day_of_month = (today.replace(day=1) - timedelta(days=i*30)).replace(day=1)
        if first_day_of_month.month == 12:
            next_month = first_day_of_month.replace(year=first_day_of_month.year + 1, month=1)
        else:
            next_month = first_day_of_month.replace(month=first_day_of_month.month + 1)
        
        m_label = first_day_of_month.strftime('%b %Y')
        months.append(m_label)

        # Revenue = collections in that month
        m_rev = Collection.objects.filter(
            collected_at__date__gte=first_day_of_month,
            collected_at__date__lt=next_month
        ).aggregate(Sum('amount_collected'))['amount_collected__sum'] or Decimal('0.00')

        # Bills issued in that month (estimated COGS / wholesale cost ~60% of bill value)
        m_bills = Bill.objects.filter(
            created_at__date__gte=first_day_of_month,
            created_at__date__lt=next_month
        ).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')

        m_exp = m_bills * Decimal('0.65')
        m_profit = m_rev - m_exp

        revenue_data.append(float(m_rev))
        expense_data.append(float(m_exp))
        profit_data.append(float(m_profit))

    context = {
        'total_credit_outstanding': total_credit_outstanding,
        'total_collections': total_collections,
        'total_approved_bills': total_approved_bills,
        'pending_bills_amount': pending_bills_amount,
        'top_debtors': top_debtors,
        'approved_count': approved_count,
        'pending_count': pending_count,
        'rejected_count': rejected_count,
        'chart_months': json.dumps(months),
        'chart_revenue': json.dumps(revenue_data),
        'chart_expense': json.dumps(expense_data),
        'chart_profit': json.dumps(profit_data),
    }
    return render(request, 'analytics_owner.html', context)


# ==========================================
# USER SELF PROFILE & PASSWORD MANAGEMENT
# ==========================================

@login_required
def profile_view(request):
    """Allows any logged-in user to view & upgrade their profile details and change their password."""
    user = request.user
    retailer_profile = getattr(user, 'retailer_profile', None)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_profile':
            profile_form = UserProfileUpdateForm(request.POST, instance=user)
            retailer_form = RetailerProfileUpdateForm(request.POST, instance=retailer_profile) if retailer_profile else None
            password_form = SelfPasswordChangeForm(user=user)

            if profile_form.is_valid() and (not retailer_form or retailer_form.is_valid()):
                profile_form.save()
                if retailer_form:
                    retailer_form.save()
                messages.success(request, "Your profile details have been updated successfully!")
                return redirect('profile')
            else:
                messages.error(request, "Please correct the errors in the profile form.")

        elif action == 'change_password':
            profile_form = UserProfileUpdateForm(instance=user)
            retailer_form = RetailerProfileUpdateForm(instance=retailer_profile) if retailer_profile else None
            password_form = SelfPasswordChangeForm(user=user, data=request.POST)

            if password_form.is_valid():
                new_pass = password_form.cleaned_data['new_password']
                user.set_password(new_pass)
                user.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Your password has been changed successfully!")
                return redirect('profile')
            else:
                messages.error(request, "Please correct the errors in the password change form.")
    else:
        profile_form = UserProfileUpdateForm(instance=user)
        retailer_form = RetailerProfileUpdateForm(instance=retailer_profile) if retailer_profile else None
        password_form = SelfPasswordChangeForm(user=user)

    context = {
        'profile_form': profile_form,
        'retailer_form': retailer_form,
        'password_form': password_form,
        'retailer_profile': retailer_profile,
    }
    return render(request, 'profile.html', context)

