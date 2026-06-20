from .models import Category
from django.db.models import Prefetch

def categories(request):
    active_children = Category.objects.filter(is_active=True)

    top_level = Category.objects.filter(
        parent=None,
        is_active=True
    ).prefetch_related(
        Prefetch('children', queryset=active_children)
    )

    return {'categories': top_level}


# ecommerce/context_processors.py
from django.core.cache import cache
from .models import ExchangeRate

CURRENCY_SYMBOLS = {'NGN': '₦', 'USD': '$', 'EUR': '€'}

def currency(request):
    code = request.session.get('currency', 'NGN')
    rate = 1
    if code != 'NGN':
        rate = cache.get(f'exchange_rate_{code}')
        if rate is None:
            try:
                rate = ExchangeRate.objects.get(currency=code).rate_to_ngn
            except ExchangeRate.DoesNotExist:
                code, rate = 'NGN', 1
            cache.set(f'exchange_rate_{code}', rate, 60 * 60)  # refresh hourly
    return {
        'current_currency': code,
        'current_currency_symbol': CURRENCY_SYMBOLS.get(code, '₦'),
        'current_currency_rate': rate,
    }