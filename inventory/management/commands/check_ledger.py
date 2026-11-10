
from django.core.management.base import BaseCommand, CommandError

from catalog.models import Product
from inventory.models import StockMovement


class Command(BaseCommand):
    help = 'Check stock movement history against product balances'

    def handle(self, *args, **options):
        errors = []

        for product in Product.objects.all().order_by('pk'):
            movements = StockMovement.objects.filter(
                product=product
            ).order_by('created_at', 'pk')

            previous_balance = 0

            for movement in movements:
                if movement.balance_before != previous_balance:
                    errors.append(
                        f'{product.sku}: movement {movement.pk} '
                        'has an incorrect starting balance'
                    )

                expected_after = (
                    movement.balance_before + movement.quantity_delta
                )

                if movement.balance_after != expected_after:
                    errors.append(
                        f'{product.sku}: movement {movement.pk} '
                        'has incorrect balance arithmetic'
                    )

                previous_balance = movement.balance_after

            if product.on_hand != previous_balance:
                errors.append(
                    f'{product.sku}: product stock is '
                    f'{product.on_hand}, but ledger shows '
                    f'{previous_balance}'
                )

        if errors:
            for error in errors:
                self.stderr.write(self.style.ERROR(error))

            raise CommandError(
                f'Ledger check failed: {len(errors)} issue(s) found'
            )

        self.stdout.write(
            self.style.SUCCESS('Stock ledger check passed')
        )
