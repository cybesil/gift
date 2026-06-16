from ecommerce.models import Product, UserProfile, ProductSize
from decimal import Decimal
import json


class Cart():
    def __init__(self, request):
        self.session = request.session
        self.request = request

        # get session key
        cart = self.session.get('session_key')

        # create session key for new user
        if 'session_key' not in request.session:
            cart = self.session['session_key'] = {}

        # Make session key available everywhere
        self.cart = cart

    @staticmethod
    def make_key(product_id, size_id=None):
        """Build a composite cart key so the same product with different
        sizes is tracked as separate lines. Products with no size keep a
        plain product_id key."""
        if size_id:
            return f"{product_id}_{size_id}"
        return str(product_id)

    def _sync_session_to_profile(self):
        """Persist the current cart state to the logged-in user's
        UserProfile.old_cart as a JSON string."""
        if self.request.user.is_authenticated:
            cart_string = json.dumps(self.cart)
            UserProfile.objects.filter(user__id=self.request.user.id).update(old_cart=cart_string)

    def add(self, product, quantity, size=None):
        """Add a product to the cart, optionally with a size.

        - size is validated against the product's ProductSize entries.
        - Each product+size combination is tracked as a separate cart line.
        - If the same product+size already exists, the quantity is increased.
        """
        product_id = product.id

        # Validate size against this product's available sizes
        size_id = None
        if size:
            try:
                size_id = int(size)
            except (TypeError, ValueError):
                size_id = None

            if size_id:
                product_size = ProductSize.objects.filter(
                    product=product, size_id=size_id
                ).first()

                if not product_size:
                    # Size doesn't belong to this product — ignore it
                    size_id = None
                elif product_size.stock <= 0:
                    # Out of stock for this size — don't add
                    return False

        cart_key = self.make_key(product_id, size_id)

        if cart_key in self.cart:
            self.cart[cart_key]['quantity']['quantity'] += quantity
        else:
            self.cart.setdefault(cart_key, {
                'quantity': {
                    'product_id': product_id,
                    'price': str(product.price),
                    'quantity': quantity,
                    'size': size_id or '',
                }
            })

        self.session.modified = True
        self._sync_session_to_profile()
        return True

    def update(self, product, quantity, size=None):
        product_id = product.id

        size_id = None
        if size:
            try:
                size_id = int(size)
            except (TypeError, ValueError):
                size_id = None

        cart_key = self.make_key(product_id, size_id)

        if cart_key in self.cart:
            self.cart[cart_key]['quantity']['quantity'] = quantity
            self.session.modified = True
            self._sync_session_to_profile()

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

                size_id = data.get('size', None)
                size_name = ''
                if size_id:
                    try:
                        size_obj = ProductSize.objects.select_related('size').get(
                            product=product, size_id=int(size_id)
                        )
                        size_name = size_obj.size.value
                    except ProductSize.DoesNotExist:
                        size_name = ''
                        size_id = None

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
                    'size_id': size_id,
                })
                total_sum += total_price
            except (Product.DoesNotExist, KeyError):
                # Clean up any malformed/orphaned entries
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
        size_id = None
        if size:
            try:
                size_id = int(size)
            except (TypeError, ValueError):
                size_id = None

        cart_key = self.make_key(product_id, size_id)

        if cart_key in self.cart:
            del self.cart[cart_key]
            self.session.modified = True
            self._sync_session_to_profile()