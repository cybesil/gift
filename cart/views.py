from django.shortcuts import render, get_object_or_404
from .cart import Cart
from django.views.decorators.csrf import csrf_exempt
from ecommerce.models import Product, Size, ProductSize
from django.http import JsonResponse
import json
from django.db.models import F


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
        size_id = request.POST.get('size_id', '')  # may be '' or a numeric string
        size = None
        product_size = None
        product = get_object_or_404(Product, id=product_id)

        if size_id:
            size = get_object_or_404(Size, id=size_id)
            product_size = get_object_or_404(ProductSize, product=product, size=size)

        added = cart.add(product=product, quantity=quantity, size=size_id)

        product.stock_quantity = F('stock_quantity') - quantity
        product.save()

        if product_size:
            product_size.stock = F('stock') - quantity
            product_size.save()

        if not added:
            return JsonResponse({
                'success': False,
                'error': 'The selected size is out of stock.',
                'qty': cart.total_quantities(),
            }, status=400)

        cart_key = Cart.make_key(product_id, int(size_id) if size_id else None)
        product_cart_data = cart.cart.get(cart_key, {}).get('quantity', {})

        response = JsonResponse({
            'success': True,
            'qty': cart.total_quantities(),
            'cart_data': {
                'product_id': product_id,
                'quantity': product_cart_data.get('quantity'),
                'size': product_cart_data.get('size', ''),
                'cart_key': cart_key,
            }
        })
        return response

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

        for item in cart_data:
            product_id = item.get('product_id')
            quantity = item.get('quantity')
            size_id = item.get('size_id', '')

            product = get_object_or_404(Product, id=product_id)
            cart.update(product, quantity, size=size_id or None)

        cart_quantity = cart.total_quantities()
        return JsonResponse({'qty': cart_quantity})

    return JsonResponse({'error': 'Invalid request'}, status=400)