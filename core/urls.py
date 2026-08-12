from django.urls import path
from . import views

urlpatterns = [
    # Dashboard & Root
    path('', views.dashboard_view, name='dashboard'),

    # Authentication & User Profile
    path('login/', views.login_view, name='login'),
    path('retailer-login/', views.retailer_login_view, name='retailer_login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),

    # User Management
    path('users/', views.user_list_view, name='user_list'),
    path('users/create/', views.user_create_view, name='user_create'),
    path('users/<int:pk>/edit/', views.user_edit_view, name='user_edit'),
    path('users/<int:pk>/toggle-lock/', views.user_toggle_lock_view, name='user_toggle_lock'),
    path('users/<int:pk>/toggle-active/', views.user_toggle_active_view, name='user_toggle_active'),
    path('users/<int:pk>/reset-password/', views.user_reset_password_view, name='user_reset_password'),
    path('users/<int:pk>/delete/', views.user_delete_view, name='user_delete'),

    # Retailer Onboarding & Field Ops
    path('onboard-retailer/', views.onboard_retailer_view, name='onboard_retailer'),
    path('retailers/<int:pk>/generate-qr/', views.generate_retailer_qr_view, name='generate_retailer_qr'),
    path('log-collection/', views.log_collection_view, name='log_collection'),
    path('collections/', views.collections_list_view, name='collections_list'),
    path('credit-balances/', views.credit_balances_view, name='credit_balances'),

    # Inventory Management
    path('inventory/', views.inventory_list_view, name='inventory_list'),
    path('inventory/add/', views.item_create_view, name='item_create'),
    path('inventory/<int:pk>/edit/', views.item_edit_view, name='item_edit'),
    path('inventory/<int:pk>/delete/', views.item_delete_view, name='item_delete'),

    # Bill Management
    path('bills/', views.bill_list_view, name='bill_list'),
    path('bills/create/', views.bill_create_view, name='bill_create'),
    path('bills/<int:pk>/', views.bill_detail_view, name='bill_detail'),
    path('bills/<int:pk>/edit/', views.bill_edit_view, name='bill_edit'),
    path('bills/<int:pk>/approve/', views.approve_bill_view, name='approve_bill'),
    path('bills/<int:pk>/reject/', views.reject_bill_view, name='reject_bill'),

    # Order Management
    path('orders/', views.order_list_view, name='order_list'),
    path('orders/create/', views.order_create_view, name='order_create'),
    path('orders/<int:pk>/', views.order_detail_view, name='order_detail'),
    path('orders/<int:pk>/edit/', views.order_edit_view, name='order_edit'),
    path('orders/<int:pk>/deliver/', views.deliver_order_view, name='deliver_order'),

    # Owner Analytics
    path('analytics/', views.owner_analytics_view, name='owner_analytics'),
]
