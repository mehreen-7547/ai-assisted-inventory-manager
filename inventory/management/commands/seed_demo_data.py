
from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal
import random

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from catalog.models import Product, Supplier
from inventory.models import StockMovement
from inventory.services import change_stock
from purchasing.models import GoodsReceipt, PurchaseOrder
from purchasing.services import (
    change_purchase_order_status,
    create_purchase_order,
    receive_goods
)
from sales.models import Sale
from sales.services import record_sale


PRODUCT_DATA = [
    ('Stationery', 'A5 Notebook', '55.00'),
    ('Stationery', 'Blue Ballpoint Pen', '12.00'),
    ('Stationery', 'Black Gel Pen', '25.00'),
    ('Stationery', 'HB Pencil', '8.00'),
    ('Stationery', 'White Eraser', '10.00'),
    ('Office Supplies', 'A4 Printer Paper', '320.00'),
    ('Office Supplies', 'Desktop Stapler', '110.00'),
    ('Office Supplies', 'Staple Pins Box', '30.00'),
    ('Office Supplies', 'File Folder', '35.00'),
    ('Office Supplies', 'Sticky Notes', '65.00'),
    ('Electronics', 'USB C Cable', '180.00'),
    ('Electronics', 'Wireless Mouse', '650.00'),
    ('Electronics', 'USB Keyboard', '480.00'),
    ('Electronics', '32GB USB Drive', '520.00'),
    ('Electronics', 'Laptop Stand', '900.00'),
    ('Cleaning', 'Floor Cleaner', '140.00'),
    ('Cleaning', 'Liquid Hand Wash', '95.00'),
    ('Cleaning', 'Tissue Box', '75.00'),
    ('Cleaning', 'Microfiber Cloth', '85.00'),
    ('Cleaning', 'Trash Bags Pack', '130.00'),
    ('Pantry', 'Tea Bags Box', '160.00'),
    ('Pantry', 'Instant Coffee Jar', '290.00'),
    ('Pantry', 'Sugar Pack', '58.00'),
    ('Pantry', 'Paper Cups Pack', '100.00'),
    ('Pantry', 'Biscuit Pack', '45.00')
]

ANOMALY_DAY_NUMBERS = (34, 96, 158, 220, 282, 344)


class Command(BaseCommand):
    help = 'Create 365 days of reproducible local demo inventory and sales history'

    def add_arguments(self, parser):
        parser.add_argument(
            '--manager',
            help='Username of an existing active Inventory Manager'
        )

    def timestamp(self, day, hour, minute=0):
        return timezone.make_aware(
            datetime.combine(day, time(hour, minute))
        )

    def handle(self, *args, **options):
        username = (options.get('manager') or '').strip()

        if not username:
            raise CommandError('Provide --manager with an existing username.')

        User = get_user_model()
        manager = User.objects.filter(
            username=username,
            role='manager',
            is_active=True
        ).first()

        if manager is None:
            raise CommandError('An active Inventory Manager is required.')

        if Sale.objects.exists():
            raise CommandError(
                'Sales already exist. Use a fresh demo database; '
                'existing sales will not be altered.'
            )

        if Product.objects.filter(sku__startswith='DEMO-').exists():
            raise CommandError('Demo product SKUs already exist.')

        if PurchaseOrder.objects.filter(
            po_number__startswith='DEMO-PO-'
        ).exists():
            raise CommandError('Demo purchase order numbers already exist.')

        first_day = timezone.localdate() - timedelta(days=365)
        last_day = first_day + timedelta(days=364)
        rng = random.Random(2026)

        try:
            with transaction.atomic():
                suppliers = self.create_suppliers()
                products = self.create_products(
                    suppliers, manager, first_day, rng
                )

                sales_people = list(
                    User.objects.filter(
                        role='sales', is_active=True
                    ).order_by('pk')
                )

                if not sales_people:
                    sales_people = [manager]

                po_number = 0
                sale_count = 0
                receipt_count = 0
                anomaly_days = []

                for day_number in range(365):
                    day = first_day + timedelta(days=day_number)
                    is_anomaly = day_number in ANOMALY_DAY_NUMBERS

                    if is_anomaly:
                        anomaly_days.append(day)
                        sale_total = 12 + rng.randint(0, 2)
                    elif day.weekday() >= 5:
                        sale_total = 3 + rng.randint(0, 1)
                    else:
                        sale_total = 2 + rng.randint(0, 1)

                    planned_sales = []
                    required = defaultdict(int)

                    for sale_index in range(sale_total):
                        selection = rng.sample(
                            products, rng.randint(1, 3)
                        )
                        items = []

                        for product in selection:
                            quantity = rng.randint(1, 3)

                            if is_anomaly:
                                quantity *= 3

                            items.append({
                                'product_id': product.pk,
                                'quantity': quantity
                            })

                            required[product.pk] += quantity

                        planned_sales.append(items)

                    stock = dict(
                        Product.objects.filter(
                            pk__in=[p.pk for p in products]
                        ).values_list('pk', 'on_hand')
                    )

                    orders_by_supplier = defaultdict(list)

                    for product in products:
                        available = stock[product.pk]
                        needed = required[product.pk]

                        regular_restock = (
                            day_number % 7 == 0 and available < 120
                        )

                        shortage_risk = available < needed + 10

                        if regular_restock or shortage_risk:
                            target = max(220, needed + 60)
                            quantity = target - available

                            if quantity > 0:
                                orders_by_supplier[product.supplier_id].append({
                                    'product_id': product.pk,
                                    'quantity': quantity,
                                    'unit_cost': str(
                                        (
                                            product.unit_price
                                            * Decimal('0.75')
                                        ).quantize(Decimal('0.01'))
                                    )
                                })

                    for supplier_id, order_items in orders_by_supplier.items():
                        po_number += 1

                        order = create_purchase_order(
                            po_number=f'DEMO-PO-{po_number:05d}',
                            supplier_id=supplier_id,
                            items=order_items,
                            user=manager
                        )

                        change_purchase_order_status(
                            order.pk, 'ordered', manager
                        )

                        PurchaseOrder.objects.filter(pk=order.pk).update(
                            created_at=self.timestamp(
                                day - timedelta(days=3), 9
                            ),
                            expected_delivery_date=day
                        )

                        receipt_items = [
                            {
                                'product_id': item['product_id'],
                                'quantity_received': item['quantity'],
                                'quantity_damaged': 0
                            }
                            for item in order_items
                        ]

                        receipt = receive_goods(
                            order_id=order.pk,
                            items=receipt_items,
                            submission_key=f'demo-receipt-{po_number:05d}',
                            user=manager
                        )

                        received_time = self.timestamp(day, 9)

                        GoodsReceipt.objects.filter(pk=receipt.pk).update(
                            received_at=received_time
                        )

                        StockMovement.objects.filter(
                            source=receipt.receipt_number,
                            movement_type='receipt'
                        ).update(created_at=received_time)

                        receipt_count += 1

                    for sale_index, items in enumerate(planned_sales):
                        seller = sales_people[
                            (day_number + sale_index) % len(sales_people)
                        ]

                        has_discount = (
                            (day_number + sale_index) % 17 == 0
                        )

                        sale = record_sale(
                            items=items,
                            user=seller,
                            submission_key=(
                                f'demo-{day_number:03d}-{sale_index:02d}'
                            ),
                            discount_type=(
                                'percent' if has_discount else 'none'
                            ),
                            discount_value=(5 if has_discount else 0)
                        )

                        sold_at = self.timestamp(
                            day, 11, 0
                        ) + timedelta(minutes=sale_index * 20)

                        Sale.objects.filter(pk=sale.pk).update(
                            created_at=sold_at
                        )

                        StockMovement.objects.filter(
                            source=sale.sale_number,
                            movement_type='sale'
                        ).update(created_at=sold_at)

                        sale_count += 1

                po_number, extra_receipts = self.create_open_orders(
                    suppliers,
                    products,
                    manager,
                    last_day,
                    po_number
                )

                receipt_count += extra_receipts

                # A failing check aborts the outer transaction.
                call_command('check_ledger', stdout=self.stdout)

                self.stdout.write(self.style.SUCCESS(
                    f'Seeded {sale_count} sales over 365 days '
                    f'({first_day} to {last_day}).'
                ))

                self.stdout.write(
                    f'Created 3 suppliers, {len(products)} products, '
                    f'{po_number} purchase orders and '
                    f'{receipt_count} goods receipts.'
                )

                self.stdout.write(
                    'Six high-sales days: ' +
                    ', '.join(str(day) for day in anomaly_days)
                )

        except ValueError as error:
            raise CommandError(str(error)) from error

    def create_suppliers(self):
        names = [
            'Demo Office Supply Co',
            'Demo Technology Warehouse',
            'Demo Daily Essentials'
        ]

        return [
            Supplier.objects.create(name=name)
            for name in names
        ]

    def create_products(self, suppliers, manager, first_day, rng):
        products = []

        for number, (category, name, price) in enumerate(
            PRODUCT_DATA, 1
        ):
            if category in ['Stationery', 'Office Supplies']:
                supplier = suppliers[0]
            elif category == 'Electronics':
                supplier = suppliers[1]
            else:
                supplier = suppliers[2]

            product = Product.objects.create(
                sku=f'DEMO-{number:03d}',
                name=name,
                category=category,
                supplier=supplier,
                unit_price=Decimal(price),
                safety_stock=12 + number % 9,
                lead_time_days=2 + number % 6
            )

            initial_quantity = 80 + rng.randint(0, 30)

            movement = change_stock(
                product_id=product.pk,
                delta=initial_quantity,
                movement_type='opening',
                reason='Demo opening inventory',
                user=manager,
                source=f'demo-opening-{number:03d}'
            )

            StockMovement.objects.filter(pk=movement.pk).update(
                created_at=self.timestamp(first_day, 8)
            )

            products.append(product)

        return products

    def create_open_orders(
        self, suppliers, products, manager, last_day, po_number
    ):
        receipt_count = 0

        examples = [
            (
                suppliers[0],
                'ordered',
                last_day - timedelta(days=3)
            ),
            (
                suppliers[1],
                'ordered',
                last_day + timedelta(days=7)
            ),
            (
                suppliers[2],
                'partially_received',
                last_day - timedelta(days=2)
            )
        ]

        for supplier, status, expected in examples:
            product = next(
                p for p in products
                if p.supplier_id == supplier.pk
            )

            po_number += 1

            order = create_purchase_order(
                po_number=f'DEMO-PO-{po_number:05d}',
                supplier_id=supplier.pk,
                items=[{
                    'product_id': product.pk,
                    'quantity': 120,
                    'unit_cost': str(
                        (
                            product.unit_price
                            * Decimal('0.75')
                        ).quantize(Decimal('0.01'))
                    )
                }],
                user=manager
            )

            change_purchase_order_status(
                order.pk, 'ordered', manager
            )

            PurchaseOrder.objects.filter(pk=order.pk).update(
                created_at=self.timestamp(
                    last_day - timedelta(days=14), 9
                ),
                expected_delivery_date=expected
            )

            if status == 'partially_received':
                receipt = receive_goods(
                    order_id=order.pk,
                    items=[{
                        'product_id': product.pk,
                        'quantity_received': 20,
                        'quantity_damaged': 0
                    }],
                    submission_key=f'demo-receipt-{po_number:05d}',
                    user=manager
                )

                received_at = self.timestamp(last_day, 18)

                GoodsReceipt.objects.filter(pk=receipt.pk).update(
                    received_at=received_at
                )

                StockMovement.objects.filter(
                    movement_type='receipt',
                    source=receipt.receipt_number
                ).update(created_at=received_at)

                receipt_count += 1

        return po_number, receipt_count
