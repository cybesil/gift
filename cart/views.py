from django.shortcuts import render, get_object_or_404, redirect
from .cart import Cart
from django.views.decorators.csrf import csrf_exempt
from ecommerce.models import Product, Size, ProductSize, Order, OrderItem, ShippingAddress
from django.http import JsonResponse
import json
import uuid
import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
import requests
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def cart_summary(request):
    cart = Cart(request)
    cart_products, total_sum = cart.get_prods()
    context = {
        'cart_products': cart_products,
        'total_sum': total_sum,
    }
    return render(request, 'Cart/cart_summary.html', context)


def cart_add(request):
    cart = Cart(request)

    if request.POST.get('action') == 'post':
        product_id = int(request.POST.get('product_id'))
        quantity = int(request.POST.get('quantity', 1))
        size_val = request.POST.get('size_id', '').strip() or None  # now a string value like 'XL' or '20"'
        product = get_object_or_404(Product, id=product_id)

        added = cart.add(product=product, quantity=quantity, size=size_val)

        if not added:
            return JsonResponse({
                'success': False,
                'error': 'The selected size is out of stock.',
                'qty': cart.total_quantities(),
            }, status=400)

        cart_key = Cart.make_key(product_id, size_val)
        product_cart_data = cart.cart.get(cart_key, {}).get('quantity', {})

        return JsonResponse({
            'success': True,
            'qty': cart.total_quantities(),
            'cart_data': {
                'product_id': product_id,
                'quantity': product_cart_data.get('quantity'),
                'size': product_cart_data.get('size', ''),
                'cart_key': cart_key,
            }
        })

    return JsonResponse({'error': 'Invalid request'}, status=400)


@csrf_exempt
def cart_delete(request):
    if request.POST.get('action') == 'post':
        cart = Cart(request)
        product_id = int(request.POST.get('product_id'))
        size_id = request.POST.get('size_id', '')

        cart.remove(product_id, size=size_id or None)
        total_quantity = cart.total_quantities()
        return JsonResponse({'success': True, 'total_quantity': total_quantity})

    return JsonResponse({'error': 'Invalid request'}, status=400)


@csrf_exempt
def update_cart(request):
    if request.method == 'POST':
        cart = Cart(request)
        cart_data = json.loads(request.POST.get('cart_data', '[]'))

        capped_items = []

        for item in cart_data:
            product_id = item.get('product_id')
            quantity = item.get('quantity')
            size_id = item.get('size_id', '')

            product = get_object_or_404(Product, id=product_id)
            result = cart.update(product, quantity, size=size_id or None)

            if result.get('capped'):
                capped_items.append({
                    'product_id': product_id,
                    'size_id': size_id,
                    'allowed': result['allowed'],
                })

        cart_quantity = cart.total_quantities()
        return JsonResponse({
            'qty': cart_quantity,
            'capped_items': capped_items,  # empty list = all quantities accepted as-is
        })

    return JsonResponse({'error': 'Invalid request'}, status=400)



@login_required(login_url="accounts:account")
def initiate_checkout(request):
    cart = Cart(request)
    cart_products, total_sum = cart.get_prods()

    if not cart_products:
        messages.error(request, "Your cart is empty.")
        return redirect('cart:cart_summary')

    shipping_address = ShippingAddress.objects.filter(user=request.user).first()
    required = [
        shipping_address.full_name if shipping_address else None,
        shipping_address.phone if shipping_address else None,
        shipping_address.street_address if shipping_address else None,
        shipping_address.country if shipping_address else None,
        shipping_address.state if shipping_address else None,
    ]
    if not shipping_address or not all(required):
        messages.error(request, "Please complete your shipping details before checking out.")
        return redirect('ecommerce:dashboard')

    order = None
    pending_order_id = request.session.get('pending_order_id')
    if pending_order_id:
        order = Order.objects.filter(
            id=pending_order_id, user=request.user, status='pending'
        ).first()

    if order:
        order.items.all().delete()
    else:
        order = Order(user=request.user, status='pending')

    order.shipping_address = shipping_address
    order.shipping_address_snapshot = (
        f"{shipping_address.full_name}\n{shipping_address.street_address}\n"
        f"{shipping_address.city}, {shipping_address.state}\n"
        f"{shipping_address.country}\nPhone: {shipping_address.phone}"
    )
    order.total = total_sum
    order.tx_ref = f"GE-{uuid.uuid4().hex[:12]}"
    order.save()

    request.session['pending_order_id'] = order.id

    for item in cart_products:
        # size_id here is now the size string value e.g. 'XL', '20"'
        product_size = None
        if item['size_id']:
            product_size = item['product_obj'].sizes.filter(
                size=item['size_id']
            ).first()

        OrderItem.objects.create(
            order=order,
            product=item['product_obj'],
            product_size=product_size,
            size_display=item['size'],
            product_name=item['product_name'],
            quantity=item['quantity'],
            price=item['price'],
        )

    context = {
        'order': order,
        'flw_public_key': settings.FLW_PUBLIC_KEY,
        'customer_email': request.user.email,
        'customer_name': shipping_address.full_name,
        'customer_phone': shipping_address.phone,
        'cart_products': cart_products,
        'total_sum': total_sum,
    }
    return render(request, 'Cart/cart_summary.html', context)


def _confirm_paid_order(order, transaction_id):
    """Mark an order paid and decrement stock. Called from both the
    redirect-based verify view and the webhook, guarded so it only
    ever runs once per order no matter which path gets there first."""
    if order.status == 'paid':
        print(f'order stat{order.status}')
        return
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        order.status = 'paid'
        order.flw_transaction_id = transaction_id

        order.save()
        print(f'order stat{order.status}')
        print(f'order transact-id{order.flw_transaction_id}')
        for item in order.items.select_related('product', 'product_size'):
            if not item.product_size:
                print(f"Before: stock={item.product.stock_quantity}, deducting={item.quantity}")
                item.product.stock_quantity = F('stock_quantity') - item.quantity
                print(f"After: stock={item.product.stock_quantity}")
                item.product.save()
            if item.product_size:
                print(f"Before: stock={item.product_size.stock}, deducting={item.quantity}")
                item.product_size.stock = F('stock') - item.quantity
                print(f"After: stock={item.product_size.stock}")
                item.product_size.save()


@login_required(login_url="accounts:account")
def verify_payment(request):
    tx_ref = request.GET.get('tx_ref')
    transaction_id = request.GET.get('transaction_id')
    order = get_object_or_404(Order, tx_ref=tx_ref, user=request.user)
    print(f"tx-{tx_ref}, transact-{transaction_id}")
    if order.status == 'paid':
        return render(request, 'checkout/success.html', {'order': order})

    headers = {'Authorization': f'Bearer {settings.FLW_SECRET_KEY}'}
    resp = requests.get(
        f'https://api.flutterwave.com/v3/transactions/{transaction_id}/verify',
        headers=headers, timeout=15
    )
    data = resp.json()

    verified_ok = (
        data.get('status') == 'success'
        and data.get('data', {}).get('status') == 'successful'
        and data['data'].get('tx_ref') == order.tx_ref
        and float(data['data'].get('amount', 0)) >= float(order.total)
        and data['data'].get('currency') == 'NGN'
    )

    if verified_ok:
        _confirm_paid_order(order, transaction_id)
        notify_discord_order(order)
        request.session['session_key'] = {}
        request.session.modified = True
        request.session.pop('pending_order_id', None)
        return render(request, 'Checkout/success.html', {'order': order})

    messages.error(request, "We couldn't confirm your payment. Please try again or contact support.")
    return redirect('cart:cart_summary')


from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def flutterwave_webhook(request):
    if request.method != 'POST':
        return HttpResponse(status=405)

    signature = request.headers.get('verif-hash')
    if not signature or signature != settings.FLW_WEBHOOK_HASH:
        return HttpResponse(status=401)

    payload = json.loads(request.body)
    data = payload.get('data', {})
    tx_ref = data.get('tx_ref')
    transaction_id = data.get('id')
    status = data.get('status')

    if status == 'successful' and tx_ref:
        order = Order.objects.filter(tx_ref=tx_ref).first()
        if order and order.status != 'paid':
            headers = {'Authorization': f'Bearer {settings.FLW_SECRET_KEY}'}
            resp = requests.get(
                f'https://api.flutterwave.com/v3/transactions/{transaction_id}/verify',
                headers=headers, timeout=15
            )
            verify_data = resp.json()
            if (
                verify_data.get('status') == 'success'
                and verify_data.get('data', {}).get('status') == 'successful'
                and verify_data['data'].get('tx_ref') == order.tx_ref
                and float(verify_data['data'].get('amount', 0)) >= float(order.total)
            ):
                _confirm_paid_order(order, transaction_id)

    return HttpResponse(status=200)




def notify_discord_order(order):
    if not settings.ORDERHOOK:
        return

    items = order.items.select_related('product', 'product_size').all()

    item_lines = []
    for item in items:
        size = f" ({item.size_display})" if item.size_display else ""
        item_lines.append(
            f"• {item.quantity}x {item.product_name}{size} — ₦{item.subtotal:,.2f}"
        )

    items_text = "\n".join(item_lines) if item_lines else "No items found"

    shipping = order.shipping_address_snapshot or "N/A"

    embed = {
        "title": f"🛍️ New Order #{order.id}",
        "color": 5763719,  # green
        "fields": [
            {"name": "Customer", "value": order.user.get_username(), "inline": True},
            {"name": "Total", "value": f"₦{order.total:,.2f}", "inline": True},
            {"name": "Status", "value": order.status, "inline": True},
            {"name": "Items", "value": items_text, "inline": False},
            {"name": "Shipping Address", "value": shipping[:1000], "inline": False},
        ],
        "timestamp": order.created_at.isoformat(),
    }

    payload = {"embeds": [embed]}

    try:
        resp = requests.post(settings.ORDERHOOK, json=payload, timeout=10)
        resp.raise_for_status()
    except requests.RequestException:
        logger.exception("Failed to send Discord order notification for order %s", order.id)
