from django import template
register = template.Library()


@register.simple_tag(takes_context=True)
def to_currency(context, ngn_amount):
    if ngn_amount is None:
        return ''
    rate = context.get('current_currency_rate', 1)
    symbol = context.get('current_currency_symbol', '₦')
    converted = ngn_amount / rate if rate else ngn_amount
    return f"{symbol}{converted:,.2f}"