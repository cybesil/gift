from django.urls import path
from .views import *

app_name = 'ecommerce'

urlpatterns = [
    path('', home, name='home'),
    path('details/<slug:slug>', product_detail, name='product_detail'),
    path('products/<slug:slug>', products, name='products'),
    path('dashboard/', dashboard, name='dashboard'),
    path('admin-dashboard/', admin_dashboard, name='admin_dashboard'),
    path('add-product/', add_product, name='add_product'),
    path('add-product/<slug:slug>', edit_product, name='edit_product'),
    path('currency/<str:code>/', set_currency, name='set_currency'),
    path('internal/refresh-rates/', refresh_exchange_rates, name='refresh_rates'),
]