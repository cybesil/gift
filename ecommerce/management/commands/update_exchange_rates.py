# ecommerce/management/commands/update_exchange_rates.py
import requests
from django.core.management.base import BaseCommand
from django.core.cache import cache
from ecommerce.models import ExchangeRate

class Command(BaseCommand):
    help = 'Fetch latest exchange rates and update ExchangeRate table'

    def handle(self, *args, **options):
        try:
            response = requests.get(
                'https://open.er-api.com/v6/latest/NGN',
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            if data.get('result') != 'success':
                self.stderr.write(f"API returned non-success result: {data}")
                return

            # Early warning if the provider has scheduled this endpoint for retirement
            if data.get('time_eol_unix'):
                self.stderr.write(
                    f"WARNING: open.er-api.com has an end-of-life date set "
                    f"({data['time_eol_unix']}) — check docs for a migration path."
                )

            rates = data['rates']  # e.g. {'USD': 0.000732, 'EUR': 0.000647, ...}

            for code in ['USD', 'EUR']:
                if code in rates:
                    rate_to_ngn = round(1 / rates[code], 4)
                    obj, _ = ExchangeRate.objects.update_or_create(
                        currency=code,
                        defaults={'rate_to_ngn': rate_to_ngn}
                    )
                    cache.set(f'exchange_rate_{code}', obj.rate_to_ngn, 60 * 60 * 2)
                    self.stdout.write(f"Updated {code}: {obj.rate_to_ngn}")

        except (requests.RequestException, KeyError, ValueError) as e:
            self.stderr.write(f"Exchange rate fetch failed: {e}")
            # leave existing rows untouched — site keeps using last known good rate