
from decimal import Decimal
from uuid import uuid4

from django.db import IntegrityError, transaction

from catalog.models import Product, Supplier
from inventory.services import change_stock

from .models import (
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine
)


def create_purchase_order(po_number, supplier_id, items, user):
    if (
        not user
        or not user.is_authenticated
        or not user.is_active
        or user.role != 'manager'
    ):
        raise ValueError('Only active managers can create purchase orders.')

    if not isinstance(po_number, str) or not po_number.strip():
        raise ValueError('Purchase order number is required.')

    po_number = po_number.strip()

    if len(po_number) > 20:
        raise ValueError('Purchase order number is too long.')

    if not isinstance(items, list) or not items:
        raise ValueError('At least one product is required.')

    if not isinstance(supplier_id, int) or isinstance(supplier_id, bool):
        raise ValueError('Invalid supplier.')

    with transaction.atomic():
        try:
            supplier = Supplier.objects.get(id=supplier_id)
        except Supplier.DoesNotExist:
            raise ValueError('Supplier not found.')

        if not supplier.is_active:
            raise ValueError('Supplier is inactive.')

        if PurchaseOrder.objects.filter(
            po_number=po_number
        ).exists():
            raise ValueError('Purchase order number already exists.')

        validated_items = []
        product_ids = set()

        for item in items:
            if not isinstance(item, dict):
                raise ValueError('Invalid product entry.')

            try:
                product_id = item['product_id']
                quantity = item['quantity']
                unit_cost = Decimal(str(item['unit_cost']))
            except (KeyError, TypeError, ValueError, ArithmeticError):
                raise ValueError('Invalid product details.')

            if not isinstance(product_id, int) or isinstance(product_id, bool):
                raise ValueError('Invalid product.')

            if not isinstance(quantity, int) or isinstance(quantity, bool):
                raise ValueError('Quantity must be a whole number.')

            if quantity <= 0:
                raise ValueError('Quantity must be greater than zero.')

            if (
                not unit_cost.is_finite()
                or unit_cost < 0
                or unit_cost > Decimal('99999999.99')
                or unit_cost.as_tuple().exponent < -2
            ):
                raise ValueError('Invalid unit cost.')

            if product_id in product_ids:
                raise ValueError('Duplicate product in purchase order.')

            product_ids.add(product_id)

            try:
                product = Product.objects.get(id=product_id)
            except Product.DoesNotExist:
                raise ValueError('Product not found.')

            if not product.is_active:
                raise ValueError('Product is inactive.')

            if product.supplier_id != supplier.id:
                raise ValueError('Product belongs to another supplier.')

            validated_items.append({
                'product': product,
                'quantity': quantity,
                'unit_cost': unit_cost
            })

        try:
            with transaction.atomic():
                order = PurchaseOrder.objects.create(
                    po_number=po_number,
                    supplier=supplier,
                    created_by=user
                )

                for item in validated_items:
                    PurchaseOrderLine.objects.create(
                        purchase_order=order,
                        product=item['product'],
                        quantity_ordered=item['quantity'],
                        unit_cost=item['unit_cost']
                    )

        except IntegrityError:
            raise ValueError(
                'Purchase order number already exists.'
            )

        return order


def change_purchase_order_status(order_id, new_status, user):
    if (
        not user
        or not user.is_authenticated
        or not user.is_active
        or user.role != 'manager'
    ):
        raise ValueError('Only active managers can change order status.')

    if new_status not in ('ordered', 'cancelled', 'closed_short'):
        raise ValueError('Invalid purchase order status.')

    with transaction.atomic():
        try:
            order = PurchaseOrder.objects.select_for_update().get(
                pk=order_id
            )
        except PurchaseOrder.DoesNotExist:
            raise ValueError('Purchase order not found.')

        if new_status == 'ordered':
            if order.status != 'draft':
                raise ValueError(
                    'Only draft purchase orders can be marked as ordered.'
                )

        elif new_status == 'cancelled':
            if order.status not in ('draft', 'ordered'):
                raise ValueError(
                    'This purchase order cannot be cancelled.'
                )

        elif new_status == 'closed_short':
            if order.status != 'partially_received':
                raise ValueError(
                    'Only partially received orders can be closed short.'
                )

            lines = PurchaseOrderLine.objects.select_for_update().filter(
                purchase_order=order
            )

            if not any(
                line.quantity_received < line.quantity_ordered
                for line in lines
            ):
                raise ValueError(
                    'This purchase order has no outstanding quantity.'
                )

        order.status = new_status
        order.save(update_fields=['status'])

        return order


def receive_goods(order_id, items, submission_key, user):
    if (
        not user
        or not user.is_authenticated
        or not user.is_active
        or user.role != 'manager'
    ):
        raise ValueError('Only active managers can receive goods.')

    if not isinstance(submission_key, str) or not submission_key.strip():
        raise ValueError('Submission key is required.')

    submission_key = submission_key.strip()

    if len(submission_key) > 100:
        raise ValueError('Invalid submission key.')

    if not isinstance(items, list) or not items:
        raise ValueError('At least one product is required.')

    with transaction.atomic():
        existing = GoodsReceipt.objects.filter(
            submission_key=submission_key
        ).first()

        if existing:
            if existing.purchase_order_id != order_id:
                raise ValueError('Submission key already used.')

            if existing.received_by_id != user.pk:
                raise ValueError('Submission key already used.')

            return existing

        try:
            order = PurchaseOrder.objects.select_for_update().get(
                pk=order_id
            )
        except PurchaseOrder.DoesNotExist:
            raise ValueError('Purchase order not found.')

        if order.status not in ('ordered', 'partially_received'):
            raise ValueError('This order cannot receive goods.')

        order_lines = {
            line.product_id: line
            for line in PurchaseOrderLine.objects.select_for_update().filter(
                purchase_order=order
            )
        }

        validated_items = []
        seen_products = set()

        for item in items:
            if not isinstance(item, dict):
                raise ValueError('Invalid receipt item.')

            product_id = item.get('product_id')
            quantity = item.get('quantity_received')
            damaged = item.get('quantity_damaged', 0)

            if type(product_id) is not int:
                raise ValueError('Invalid product.')

            if type(quantity) is not int or quantity < 0:
                raise ValueError('Invalid received quantity.')

            if type(damaged) is not int or damaged < 0:
                raise ValueError('Invalid damaged quantity.')

            if quantity + damaged == 0:
                raise ValueError('Received quantity must be greater than zero.')

            if product_id in seen_products:
                raise ValueError('Duplicate product in receipt.')

            seen_products.add(product_id)

            line = order_lines.get(product_id)

            if line is None:
                raise ValueError('Product is not in this purchase order.')

            remaining = (
                line.quantity_ordered - line.quantity_received
            )

            if quantity + damaged > remaining:
                raise ValueError('Cannot receive more than ordered.')

            validated_items.append({
                'line': line,
                'quantity': quantity,
                'damaged': damaged
            })

        receipt = GoodsReceipt.objects.create(
            receipt_number='GR-' + uuid4().hex[:12].upper(),
            purchase_order=order,
            received_by=user,
            submission_key=submission_key
        )

        for item in validated_items:
            line = item['line']
            quantity = item['quantity']
            damaged = item['damaged']

            GoodsReceiptLine.objects.create(
                receipt=receipt,
                product=line.product,
                quantity_received=quantity,
                quantity_damaged=damaged
            )

            line.quantity_received += quantity + damaged
            line.save(update_fields=['quantity_received'])

            if quantity > 0:
                change_stock(
                    product_id=line.product_id,
                    delta=quantity,
                    movement_type='receipt',
                    reason='Goods received from supplier',
                    user=user,
                    source=receipt.receipt_number
                )

        all_received = all(
            line.quantity_received == line.quantity_ordered
            for line in order_lines.values()
        )

        if all_received:
            order.status = 'received'
        else:
            order.status = 'partially_received'

        order.save(update_fields=['status'])

        return receipt
