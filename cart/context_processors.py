# context_processors.py
from .cart import Cart

def cart_quantity(request):
    cart = Cart(request)
    return {'cart_qty': cart.total_quantities()}