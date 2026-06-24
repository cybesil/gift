from ecommerce.models import Product, UserProfile, ProductSize
from decimal import Decimal
import json


class Cart():
    def __init__(self, request):
        self.session = request.session
        self.request = request

        cart = self.session.get('session_key')

        if 'session_key' not in request.session:
            cart = self.session['session_key'] = {}

        self.cart = cart

    @staticmethod
    def make_key(product_id, size=None):
        if size:
            return f"{product_id}_{size}"
        return str(product_id)

    def _sync_session_to_profile(self):
        if self.request.user.is_authenticated:
            cart_string = json.dumps(self.cart)
            UserProfile.objects.filter(user__id=self.request.user.id).update(old_cart=cart_string)

    def add(self, product, quantity, size=None):
        product_id = product.id
        size_val = str(size).strip() if size else None

        if size_val:
            product_size = ProductSize.objects.filter(
                product=product, size=size_val
            ).first()

            if not product_size:
                size_val = None
            elif product_size.stock <= 0:
                return False
            elif quantity > product_size.stock:
                return False

        if not size_val and quantity > product.stock_quantity:
            return False

        cart_key = self.make_key(product_id, size_val)

        if cart_key in self.cart:
            self.cart[cart_key]['quantity']['quantity'] += quantity
        else:
            self.cart.setdefault(cart_key, {
                'quantity': {
                    'product_id': product_id,
                    'price': str(product.price),
                    'quantity': quantity,
                    'size': size_val or '',
                }
            })

        self.session.modified = True
        self._sync_session_to_profile()
        return True

    def update(self, product, quantity, size=None):
        product_id = product.id
        size_val = str(size).strip() if size else None

        cart_key = self.make_key(product_id, size_val)

        if cart_key not in self.cart:
            return {'error': 'Item not in cart', 'capped': False}

        if size_val:
            product_size = ProductSize.objects.filter(
                product=product, size=size_val
            ).first()
            available_stock = product_size.stock if product_size else 0
        else:
            available_stock = product.stock_quantity

        capped = quantity > available_stock
        clamped_quantity = min(quantity, available_stock)

        if clamped_quantity < 1:
            return {'error': 'Out of stock', 'capped': True, 'allowed': 0}

        self.cart[cart_key]['quantity']['quantity'] = clamped_quantity
        self.session.modified = True
        self._sync_session_to_profile()

        return {'error': None, 'capped': capped, 'allowed': clamped_quantity}

    def __len__(self):
        return len(self.cart)

    def total_quantities(self):
        total = 0
        for item in self.cart.values():
            if 'quantity' in item and 'quantity' in item['quantity']:
                total += item['quantity']['quantity']
        return total

    def remove_non_existent_products(self):
        existing_ids = set(
            Product.objects.filter(
                id__in=[item['quantity']['product_id'] for item in self.cart.values()
                        if 'quantity' in item and 'product_id' in item['quantity']]
            ).values_list('id', flat=True)
        )

        for cart_key in list(self.cart.keys()):
            item = self.cart[cart_key]
            product_id = item.get('quantity', {}).get('product_id')
            if product_id not in existing_ids:
                del self.cart[cart_key]
                self.session.modified = True

    def get_prods(self):
        self.remove_non_existent_products()
        products = []
        total_sum = Decimal('0.00')

        for cart_key, item in list(self.cart.items()):
            try:
                data = item['quantity']
                product_id = data['product_id']
                product = Product.objects.get(id=product_id)

                quantity = int(data['quantity'])
                price = Decimal(data['price'])

                size_val = data.get('size', None) or None
                size_name = size_val or ''

                if size_val:
                    product_size = ProductSize.objects.filter(
                        product=product, size=size_val
                    ).first()
                    if not product_size:
                        size_val = None
                        size_name = ''

                total_price = round(price * quantity, 2)

                products.append({
                    'cart_key': cart_key,
                    'id': product.id,
                    'product_obj': product,
                    'product_img': product.primary_image,
                    'product_name': product.name,
                    'display_price': product.display_price,
                    'quantity': quantity,
                    'price': price,
                    'total_price': total_price,
                    'size': size_name,
                    'size_id': size_val,  # kept as 'size_id' key for template/views compatibility
                })
                total_sum += total_price
            except (Product.DoesNotExist, KeyError):
                del self.cart[cart_key]
                self.session.modified = True

        return products, total_sum

    def get_cart_ids(self):
        return [
            item['quantity']['product_id']
            for item in self.cart.values()
            if 'quantity' in item and 'product_id' in item['quantity']
        ]

    def remove(self, product_id, size=None):
        size_val = str(size).strip() if size else None
        cart_key = self.make_key(product_id, size_val)

        if cart_key in self.cart:
            del self.cart[cart_key]
            self.session.modified = True
            self._sync_session_to_profile()