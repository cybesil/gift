from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static


app_name = 'cart'

urlpatterns = [
    path('', views.cart_summary, name="cart_summary"),
    path('add/', views.cart_add, name="cart_add"),
    path('cart-del/', views.cart_delete, name="cart_delete"),
    path('cart-upd/', views.update_cart, name="update_cart"),
    path('checkout/', views.initiate_checkout, name='initiate_checkout'),
    path('checkout/verify/', views.verify_payment, name='verify_payment'),
    path('checkout/webhook/', views.flutterwave_webhook, name='flutterwave_webhook'),

]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

