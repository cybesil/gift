from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import Paginator
from .forms import AccountDetailsForm, ShippingAddressForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, F
from django.http import JsonResponse
from .models import Category, Product, ProductImage, ProductSize, Size, Order, OrderItem, ShippingAddress, ExchangeRate
import requests
from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
# Create your views here.

def home(request):
    products = Product.objects.filter(is_active=True)[:8]
    ft_products = Product.objects.filter(is_featured=True, is_active=True)[:8]
    context = {
        "products": products,
        "ft_products": ft_products
    }
    return render(request, 'User/index.html', context)

def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    related = Product.objects.filter(category=product.category, is_active=True).exclude(pk=product.pk)[:5]
    ft_related = Product.objects.filter(category=product.category, is_active=True, is_featured=True).exclude(pk=product.pk)[:5]
    sizes = product.sizes.all().order_by('size')
    context = {
        "product": product,
        "related": related,
        "ft_related": ft_related,
        "sizes": sizes
    }
    return render(request, 'Product/details.html', context)

def products(request, slug):
    category = get_object_or_404(Category, slug=slug, is_active=True)

    product_list = Product.objects.filter(
        category=category,
        is_active=True
    ).prefetch_related('images')

    # Sorting
    sort = request.GET.get('sort', 'newest')
    sort_options = {
        'newest':     '-created_at',
        'oldest':     'created_at',
        'price_asc':  'price',
        'price_desc': '-price',
        'name_asc':   'name',
        'name_desc':  '-name',
    }
    product_list = product_list.order_by(sort_options.get(sort, '-created_at'))

    # Pagination
    paginator = Paginator(product_list, 12)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'category': category,
        'page_obj': page_obj,
        'sort': sort,
        'sort_options': [
            ('newest',     'Newest Arrivals'),
            ('oldest',     'Oldest First'),
            ('price_asc',  'Price: Low to High'),
            ('price_desc', 'Price: High to Low'),
            ('name_asc',   'Name: A–Z'),
            ('name_desc',  'Name: Z–A'),
        ],
        'total_count': paginator.count,
    }
    return render(request, "Product/products.html", context)


from django.core.paginator import Paginator


@login_required(login_url="accounts:account")
def dashboard(request):
    profile = request.user.profile
    shipping_address, _ = ShippingAddress.objects.get_or_create(
        user=request.user, defaults={'is_default': True}
    )

    account_form = AccountDetailsForm(instance=request.user, profile=profile)
    shipping_form = ShippingAddressForm(instance=shipping_address)

    # Get user's orders
    orders_list = Order.objects.filter(user=request.user).order_by('-created_at')

    # Paginate orders
    paginator = Paginator(orders_list, 10)  # 10 orders per page
    page_number = request.GET.get('orders_page', 1)
    orders = paginator.get_page(page_number)

    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'account_details':
            account_form = AccountDetailsForm(
                request.POST, instance=request.user, profile=profile
            )
            if account_form.is_valid():
                account_form.save()
                messages.success(request, 'Account details updated successfully.')
                return redirect('ecommerce:dashboard')

        elif form_type == 'shipping_address':
            shipping_form = ShippingAddressForm(
                request.POST, instance=shipping_address
            )
            if shipping_form.is_valid():
                shipping_form.save()
                messages.success(request, 'Shipping address updated successfully.')
                return redirect('ecommerce:dashboard')

    context = {
        'profile': profile,
        'shipping_address': shipping_address,
        'account_form': account_form,
        'shipping_form': shipping_form,
        'orders': orders,
    }
    return render(request, 'User/dashboard.html', context)


@login_required(login_url="accounts:account")
def admin_dashboard(request):
    """
    Single view handling all admin operations:
    - Listing Products, Orders, Categories with filters & pagination
    - Adding/Editing/Deleting Categories (page reload with messages)
    - Updating Order status (page reload with messages)
    - Viewing Order details
    """
    context = {}

    # ─────────────────────────────────────────────
    # HANDLE POST REQUESTS (Actions that cause reload)
    # ─────────────────────────────────────────────
    if request.method == 'POST':
        action = request.POST.get('action')

        # ─── CATEGORY ACTIONS ───
        if action == 'add_category':
            name = request.POST.get('category_name', '').strip()
            image = request.FILES.get('category_image')
            if name:
                try:
                    cat = Category.objects.create(name=name, image=image)
                    messages.success(request, f'Category "{cat.name}" created successfully.')
                except Exception as e:
                    messages.error(request, f'Error creating category: {str(e)}')
            else:
                messages.error(request, 'Category name is required.')
            return redirect('ecommerce:admin_dashboard')

        elif action == 'edit_category':
            cat_id = request.POST.get('category_id')
            name = request.POST.get('category_name', '').strip()
            image = request.FILES.get('category_image')
            remove_image = request.POST.get('remove_image') == 'on'

            try:
                cat = Category.objects.get(pk=cat_id)
                if name:
                    cat.name = name
                if remove_image:
                    cat.image = None
                elif image:
                    cat.image = image
                cat.save()
                messages.success(request, f'Category "{cat.name}" updated successfully.')
            except Category.DoesNotExist:
                messages.error(request, 'Category not found.')
            except Exception as e:
                messages.error(request, f'Error updating category: {str(e)}')
            return redirect('ecommerce:admin_dashboard')

        elif action == 'delete_category':
            cat_id = request.POST.get('category_id')
            try:
                cat = Category.objects.get(pk=cat_id)
                name = cat.name
                cat.delete()
                messages.success(request, f'Category "{name}" deleted successfully.')
            except Category.DoesNotExist:
                messages.error(request, 'Category not found.')
            return redirect('ecommerce:admin_dashboard')

        # ─── ORDER STATUS UPDATE ───
        elif action == 'update_order_status':
            order_id = request.POST.get('order_id')
            new_status = request.POST.get('status')
            try:
                order = Order.objects.get(pk=order_id)
                old_status = order.get_status_display()
                order.status = new_status
                order.save()
                messages.success(
                    request, 
                    f'Order #{order.id} status updated from {old_status} to {order.get_status_display()}.'
                )
            except Order.DoesNotExist:
                messages.error(request, 'Order not found.')
            return redirect('ecommerce:admin_dashboard')

    # ─────────────────────────────────────────────
    # HANDLE GET REQUESTS (Filtering & Pagination)
    # ─────────────────────────────────────────────

    # Get all filter parameters
    tab = request.GET.get('tab', 'orders')  # Default tab

    # ─── ORDERS FILTERING ───
    orders_qs = Order.objects.select_related('user', 'shipping_address').prefetch_related('items__product', 'items__product_size')

    order_search = request.GET.get('order_search', '')
    order_status = request.GET.get('order_status', 'all')

    if order_search:
        orders_qs = orders_qs.filter(
            Q(id__icontains=order_search) |
            Q(user__username__icontains=order_search) |
            Q(user__email__icontains=order_search) |
            Q(tracking_number__icontains=order_search)
        )

    if order_status and order_status != 'all':
        orders_qs = orders_qs.filter(status=order_status)

    orders_qs = orders_qs.order_by('-created_at')

    # Paginate orders
    orders_paginator = Paginator(orders_qs, 10)
    orders_page_num = request.GET.get('orders_page', 1)
    orders_page = orders_paginator.get_page(orders_page_num)

    # ─── PRODUCTS FILTERING ───
    products_qs = Product.objects.select_related('category').prefetch_related('images', 'sizes')

    product_search = request.GET.get('product_search', '')
    product_category = request.GET.get('product_category', '')
    product_visibility = request.GET.get('product_visibility', '')

    if product_search:
        products_qs = products_qs.filter(
            Q(name__icontains=product_search) |
            Q(sku__icontains=product_search) |
            Q(slug__icontains=product_search)
        )

    if product_category:
        products_qs = products_qs.filter(category_id=product_category)

    if product_visibility:
        if product_visibility == 'active':
            products_qs = products_qs.filter(is_active=True)
        elif product_visibility == 'inactive':
            products_qs = products_qs.filter(is_active=False)
        elif product_visibility == 'featured':
            products_qs = products_qs.filter(is_featured=True)
        elif product_visibility == 'not_featured':
            products_qs = products_qs.filter(is_featured=False)
        elif product_visibility == 'featured_active':
            products_qs = products_qs.filter(is_featured=True, is_active=True)
        elif product_visibility == 'featured_inactive':
            products_qs = products_qs.filter(is_featured=True, is_active=False)
        elif product_visibility == 'out_of_stock':
            products_qs = products_qs.filter(stock_quantity=0)
        elif product_visibility == 'variant_out':
            products_qs = products_qs.filter(sizes__stock=0).distinct()

    products_qs = products_qs.order_by('-created_at')

    # Paginate products
    products_paginator = Paginator(products_qs, 10)
    products_page_num = request.GET.get('products_page', 1)
    products_page = products_paginator.get_page(products_page_num)

    # ─── CATEGORIES LISTING ───
    categories_qs = Category.objects.all().order_by('sort_order', 'name')

    category_search = request.GET.get('category_search', '')
    if category_search:
        categories_qs = categories_qs.filter(name__icontains=category_search)

    categories_paginator = Paginator(categories_qs, 15)
    categories_page_num = request.GET.get('categories_page', 1)
    categories_page = categories_paginator.get_page(categories_page_num)

    # ─── ORDER DETAIL (if viewing specific order) ───
    view_order_id = request.GET.get('view_order')
    view_order = None
    if view_order_id:
        try:
            view_order = Order.objects.select_related('user', 'shipping_address').prefetch_related(
                'items__product', 'items__product_size'
            ).get(pk=view_order_id)
        except Order.DoesNotExist:
            pass

    # ─── EDIT CATEGORY (if editing specific category) ───
    edit_category_id = request.GET.get('edit_category')
    edit_category_obj = None
    if edit_category_id:
        try:
            edit_category_obj = Category.objects.get(pk=edit_category_id)
        except Category.DoesNotExist:
            pass

    # ─── CONTEXT BUILDING ───
    context = {
        # Tab state
        'active_tab': tab,

        # Orders
        'orders': orders_page,
        'order_search': order_search,
        'order_status': order_status,
        'order_status_choices': Order.STATUS_CHOICES,

        # Products
        'products': products_page,
        'product_search': product_search,
        'product_category': product_category,
        'product_visibility': product_visibility,
        'categories_for_filter': Category.objects.all().order_by('name'),
        'product_visibility_options': [
            ('active', 'Active State Only'),
            ('inactive', 'Inactive State Only'),
            ('featured', 'Featured Status Only'),
            ('not_featured', 'Non-Featured Rows Only'),
            ('featured_active', 'Featured & Active Mix'),
            ('featured_inactive', 'Featured & Inactive Mix'),
            ('out_of_stock', 'Global Out of Stock Pool'),
            ('variant_out', 'Sizes Variant Out of Stock'),
        ],

        # Categories
        'categories': categories_page,
        'category_search': category_search,
        'edit_category_obj': edit_category_obj,

        # Order detail view
        'view_order': view_order,
    }

    return render(request, 'Admin/admin.html', context)



# ─────────────────────────────────────────────────────────────
# ADD PRODUCT
# ─────────────────────────────────────────────────────────────

@login_required(login_url="accounts:account")
def add_product(request):
    """
    Handle creating a new product with:
    - Core fields (name, description, price, discount, stock, weight, category, flags)
    - Multiple image uploads (first uploaded becomes key image unless user marks one)
    - Multiple size variants (Size FK + stock + price_adjustment + sku)
    """
    categories = Category.objects.filter(is_active=True).order_by('name')
    sizes      = Size.objects.all().order_by('size_type', 'display_order', 'value')

    if request.method == 'POST':
        # ── Core fields ──────────────────────────────────────
        name             = request.POST.get('name', '').strip()
        description      = request.POST.get('description', '').strip()
        category_id      = request.POST.get('category')
        price            = request.POST.get('price', '').strip()
        discount_price   = request.POST.get('discount_price', '').strip() or None
        discount_percent = request.POST.get('discount_percent', '').strip() or None
        stock_quantity   = request.POST.get('stock_quantity', '0').strip()
        weight           = request.POST.get('weight', '').strip() or None
        is_active        = request.POST.get('is_active') == 'on'
        is_featured      = request.POST.get('is_featured') == 'on'

        # ── Validation ───────────────────────────────────────
        errors = []
        if not name:
            errors.append('Product name is required.')
        if not price:
            errors.append('Price is required.')
        else:
            try:
                price = float(price)
                if price < 0:
                    errors.append('Price must be a positive number.')
            except ValueError:
                errors.append('Price must be a valid number.')
        if not category_id:
            errors.append('Category is required.')
        else:
            try:
                category = Category.objects.get(pk=category_id)
            except Category.DoesNotExist:
                errors.append('Selected category does not exist.')
                category = None

        if discount_price:
            try:
                discount_price = float(discount_price)
            except ValueError:
                errors.append('Discount price must be a valid number.')
                discount_price = None

        if discount_percent:
            try:
                discount_percent = int(discount_percent)
                if not (0 <= discount_percent <= 100):
                    errors.append('Discount percent must be between 0 and 100.')
            except ValueError:
                errors.append('Discount percent must be a whole number.')
                discount_percent = None

        try:
            stock_quantity = int(stock_quantity)
        except ValueError:
            stock_quantity = 0

        if errors:
            for err in errors:
                messages.error(request, err)
            # Re-render with posted data so user doesn't lose everything
            context = {
                'categories': categories,
                'sizes': sizes,
                'posted': request.POST,
            }
            return render(request, 'Admin/add_product.html', context)

        # ── Create product ───────────────────────────────────
        try:
            product = Product.objects.create(
                name             = name,
                description      = description,
                category         = category,
                price            = price,
                discount_price   = discount_price,
                discount_percent = discount_percent,
                stock_quantity   = stock_quantity,
                weight           = weight,
                is_active        = is_active,
                is_featured      = is_featured,
            )
        except Exception as e:
            messages.error(request, f'Error creating product: {str(e)}')
            context = {'categories': categories, 'sizes': sizes, 'posted': request.POST}
            return render(request, 'Admin/add_product.html', context)

        # ── Handle images ────────────────────────────────────
        # The form sends multiple files under the name 'images'
        # and a single 'key_image_index' indicating which (0-based) is the primary
        images        = request.FILES.getlist('images')
        key_image_idx = request.POST.get('key_image_index', '0')
        try:
            key_image_idx = int(key_image_idx)
        except ValueError:
            key_image_idx = 0

        for idx, img_file in enumerate(images):
            ProductImage.objects.create(
                product    = product,
                image      = img_file,
                is_key     = (idx == key_image_idx),
                sort_order = idx,
            )

        # If no images were uploaded but key index is still set, that's fine —
        # product can exist without images.

        # ── Handle size variants ─────────────────────────────
        # The form sends parallel lists:
        #   size_ids[]        → FK to Size
        #   size_stocks[]     → stock for each variant
        #   size_adjustments[] → price_adjustment
        #   size_skus[]       → optional variant SKU
        size_values     = request.POST.getlist('size_values[]')
        size_stocks     = request.POST.getlist('size_stocks[]')
        size_adjustments = request.POST.getlist('size_adjustments[]')
        size_skus       = request.POST.getlist('size_skus[]')

        for i, size_val in enumerate(size_values):
            if not size_val:
                continue
            try:
                stock      = int(size_stocks[i]) if i < len(size_stocks) and size_stocks[i] else 0
                adjustment = float(size_adjustments[i]) if i < len(size_adjustments) and size_adjustments[i] else 0.0
                variant_sku = size_skus[i].strip() if i < len(size_skus) else ''

                ProductSize.objects.get_or_create(
                    product = product,
                    size    = size_val,
                    defaults={
                        'stock'            : stock,
                        'price_adjustment' : adjustment,
                        'sku'              : variant_sku,
                    }
                )
            except (ValueError, IndexError):
                continue

        messages.success(request, f'Product "{product.name}" created successfully.')
        return redirect('ecommerce:admin_dashboard')

    # ── GET ──────────────────────────────────────────────────
    context = {
        'categories': categories,
        'sizes'     : sizes,
    }
    return render(request, 'Admin/add_product.html', context)


# ─────────────────────────────────────────────────────────────
# EDIT PRODUCT
# ─────────────────────────────────────────────────────────────

@login_required(login_url="accounts:account")
def edit_product(request, slug):
    """
    Handle editing an existing product:
    - Update core fields
    - Add new images / delete existing images / set a new key image
    - Add new size variants / update existing ones / delete removed ones
    """
    product    = get_object_or_404(Product, slug=slug)
    categories = Category.objects.filter(is_active=True).order_by('name')

    if request.method == 'POST':
        # ── Core fields ──────────────────────────────────────
        name             = request.POST.get('name', '').strip()
        description      = request.POST.get('description', '').strip()
        category_id      = request.POST.get('category')
        price            = request.POST.get('price', '').strip()
        discount_price   = request.POST.get('discount_price', '').strip() or None
        discount_percent = request.POST.get('discount_percent', '').strip() or None
        stock_quantity   = request.POST.get('stock_quantity', '0').strip()
        weight           = request.POST.get('weight', '').strip() or None
        is_active        = request.POST.get('is_active') == 'on'
        is_featured      = request.POST.get('is_featured') == 'on'

        # ── Validation ───────────────────────────────────────
        errors = []
        if not name:
            errors.append('Product name is required.')
        if not price:
            errors.append('Price is required.')
        else:
            try:
                price = float(price)
                if price < 0:
                    errors.append('Price must be a positive number.')
            except ValueError:
                errors.append('Price must be a valid number.')
        if not category_id:
            errors.append('Category is required.')
        else:
            try:
                category = Category.objects.get(pk=category_id)
            except Category.DoesNotExist:
                errors.append('Selected category does not exist.')
                category = product.category  # Fallback to current

        if discount_price:
            try:
                discount_price = float(discount_price)
            except ValueError:
                errors.append('Discount price must be a valid number.')
                discount_price = None

        if discount_percent:
            try:
                discount_percent = int(discount_percent)
                if not (0 <= discount_percent <= 100):
                    errors.append('Discount percent must be between 0 and 100.')
            except ValueError:
                errors.append('Discount percent must be a whole number.')
                discount_percent = None

        try:
            stock_quantity = int(stock_quantity)
        except ValueError:
            stock_quantity = product.stock_quantity

        if errors:
            for err in errors:
                messages.error(request, err)
            context = {
                'product'   : product,
                'categories': categories,
                'existing_images'  : product.images.all(),
                'existing_variants': product.sizes.all(),
            }
            return render(request, 'Admin/edit_product.html', context)

        # ── Update product fields ─────────────────────────────
        try:
            product.name             = name
            product.description      = description
            product.category         = category
            product.price            = price
            product.discount_price   = discount_price
            product.discount_percent = discount_percent
            product.stock_quantity   = stock_quantity
            product.weight           = weight
            product.is_active        = is_active
            product.is_featured      = is_featured
            product.save()
        except Exception as e:
            messages.error(request, f'Error updating product: {str(e)}')
            context = {
                'product'          : product,
                'categories'       : categories,
                'existing_images'  : product.images.all(),
                'existing_variants': product.sizes.all(),
            }
            return render(request, 'Admin/edit_product.html', context)

        # ── Handle image deletions ───────────────────────────
        delete_image_ids = request.POST.getlist('delete_images[]')
        if delete_image_ids:
            ProductImage.objects.filter(
                product=product, pk__in=delete_image_ids
            ).delete()

        # ── Handle key image change on existing images ───────
        set_key_image_id = request.POST.get('set_key_image')
        if set_key_image_id:
            try:
                key_img = ProductImage.objects.get(pk=set_key_image_id, product=product)
                key_img.is_key = True
                key_img.save()
            except ProductImage.DoesNotExist:
                pass

        # ── Handle new image uploads ─────────────────────────
        new_images        = request.FILES.getlist('images')
        new_key_image_idx = request.POST.get('new_key_image_index', '')
        try:
            new_key_image_idx = int(new_key_image_idx)
        except (ValueError, TypeError):
            new_key_image_idx = None

        existing_count = product.images.count()
        for idx, img_file in enumerate(new_images):
            is_key = (new_key_image_idx is not None and idx == new_key_image_idx)
            ProductImage.objects.create(
                product    = product,
                image      = img_file,
                is_key     = is_key,
                sort_order = existing_count + idx,
            )

        # ── Handle size variant updates ──────────────────────
        delete_variant_ids = request.POST.getlist('delete_variants[]')
        if delete_variant_ids:
            ProductSize.objects.filter(
                product=product, pk__in=delete_variant_ids
            ).delete()

        existing_variant_ids    = request.POST.getlist('variant_ids[]')
        existing_variant_stocks = request.POST.getlist('variant_stocks[]')
        existing_variant_adj    = request.POST.getlist('variant_adjustments[]')
        existing_variant_skus   = request.POST.getlist('variant_skus[]')

        for i, v_id in enumerate(existing_variant_ids):
            if not v_id or v_id in delete_variant_ids:
                continue
            try:
                ps = ProductSize.objects.get(pk=v_id, product=product)
                ps.stock            = int(existing_variant_stocks[i]) if i < len(existing_variant_stocks) and existing_variant_stocks[i] else ps.stock
                ps.price_adjustment = float(existing_variant_adj[i])  if i < len(existing_variant_adj)    and existing_variant_adj[i]    else ps.price_adjustment
                ps.sku              = existing_variant_skus[i].strip() if i < len(existing_variant_skus)   else ps.sku
                ps.save()
            except (ProductSize.DoesNotExist, ValueError, IndexError):
                continue

        # New size variants
        new_size_values     = request.POST.getlist('size_values[]')
        new_size_stocks     = request.POST.getlist('size_stocks[]')
        new_size_adjustments = request.POST.getlist('size_adjustments[]')
        new_size_skus       = request.POST.getlist('size_skus[]')

        for i, size_val in enumerate(new_size_values):
            if not size_val:
                continue
            try:
                stock      = int(new_size_stocks[i])     if i < len(new_size_stocks)     and new_size_stocks[i]     else 0
                adjustment = float(new_size_adjustments[i]) if i < len(new_size_adjustments) and new_size_adjustments[i] else 0.0
                variant_sku = new_size_skus[i].strip()   if i < len(new_size_skus)       else ''

                ProductSize.objects.get_or_create(
                    product = product,
                    size    = size_val,
                    defaults={
                        'stock'            : stock,
                        'price_adjustment' : adjustment,
                        'sku'              : variant_sku,
                    }
                )
            except (ValueError, IndexError):
                continue

        messages.success(request, f'Product "{product.name}" updated successfully.')
        return redirect('ecommerce:admin_dashboard')

    # ── GET ──────────────────────────────────────────────────
    context = {
        'product'          : product,
        'categories'       : categories,
        'existing_images'  : product.images.all(),
        'existing_variants': product.sizes.all(),
    }
    return render(request, 'Admin/edit_product.html', context)


def set_currency(request, code):
    valid = ['NGN'] + list(ExchangeRate.objects.values_list('currency', flat=True))
    if code in valid:
        request.session['currency'] = code
    return redirect(request.META.get('HTTP_REFERER', '/'))


def refresh_exchange_rates(request):
    # Simple shared-secret check so randos on the internet can't spam this
    if request.GET.get('token') != settings.RATE_REFRESH_TOKEN:
        return JsonResponse({'error': 'forbidden'}, status=403)

    # Skip if rates were refreshed recently, even if pinged more than hourly
    latest = ExchangeRate.objects.order_by('-updated_at').first()
    if latest and latest.updated_at > timezone.now() - timedelta(hours=1):
        return JsonResponse({'status': 'skipped', 'reason': 'recently updated'})

    try:
        response = requests.get('https://open.er-api.com/v6/latest/NGN', timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get('result') != 'success':
            return JsonResponse({'status': 'error', 'detail': data}, status=502)

        rates = data['rates']
        updated = []
        for code in ['USD', 'EUR']:
            if code in rates:
                rate_to_ngn = round(1 / rates[code], 4)
                ExchangeRate.objects.update_or_create(
                    currency=code, defaults={'rate_to_ngn': rate_to_ngn}
                )
                updated.append(code)
        return JsonResponse({'status': 'success', 'updated': updated})

    except (requests.RequestException, KeyError, ValueError) as e:
        return JsonResponse({'status': 'error', 'detail': str(e)}, status=502)
