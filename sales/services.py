
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from django.db import IntegrityError, transaction

from catalog.models import Product
from inventory.services import change_stock
from .models import Sale, SaleLine


def record_sale(
    items, user, submission_key,
    discount_type='none', discount_value=0
):
    if not user or not user.is_authenticated or not user.is_active:
        raise ValueError('An active user is required')

    if user.role not in ['sales', 'manager']:
        raise ValueError('You cannot record sales')

    if not isinstance(submission_key, str) or not submission_key.strip():
        raise ValueError('Submission key is required')

    submission_key = submission_key.strip()

    if len(submission_key) > 36:
        raise ValueError('Invalid submission key')

    if not isinstance(items, (list, tuple)) or not items:
        raise ValueError('Add at least one product')

    if discount_type not in ['none', 'fixed', 'percent']:
        raise ValueError('Invalid discount type')

    try:
        discount_value = Decimal(str(discount_value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('Invalid discount value')

    if not discount_value.is_finite():
        raise ValueError('Invalid discount value')

    if discount_value < 0:
        raise ValueError('Discount cannot be negative')

    if discount_value.as_tuple().exponent < -2:
        raise ValueError('Discount must have at most two decimal places')

    if discount_type == 'none' and discount_value != 0:
        raise ValueError('Discount must be zero when type is none')

    if discount_type == 'percent' and discount_value > 100:
        raise ValueError('Percentage cannot exceed 100')

    with transaction.atomic():


        existing_sale = Sale.objects.filter(
            submission_key=submission_key
        ).first()

        if existing_sale:
            if existing_sale.created_by_id != user.pk:
                raise ValueError('Submission key already used')

            if (
                existing_sale.discount_type != discount_type
                or existing_sale.discount_value != discount_value
            ):
                raise ValueError(
                    'Submission key used with different discount'
                )

            original_items = {
                (line.product_id, line.quantity)
                for line in existing_sale.lines.all()
            }

            requested_items = set()

            for item in items:
                if not isinstance(item, dict):
                    raise ValueError('Invalid sale item')

                product_id = item.get('product_id')
                quantity = item.get('quantity')

                if (
                    type(product_id) is not int
                    or product_id <= 0
                    or type(quantity) is not int
                    or quantity <= 0
                ):
                    raise ValueError('Invalid sale item')

                if product_id in {
                    product_id for product_id, _ in requested_items
                }:
                    raise ValueError('Duplicate products are not allowed')

                requested_items.add((product_id, quantity))

            if original_items != requested_items:
                raise ValueError(
                    'Submission key used with different items'
                )

            return existing_sale


        prepared_items = []
        product_ids = set()
        subtotal = Decimal('0.00')

        for item in items:
            if not isinstance(item, dict):
                raise ValueError('Invalid sale item')

            product_id = item.get('product_id')
            quantity = item.get('quantity')

            if type(product_id) is not int or product_id <= 0:
                raise ValueError('Invalid product')

            if type(quantity) is not int or quantity <= 0:
                raise ValueError('Quantity must be a positive integer')

            if product_id in product_ids:
                raise ValueError('Duplicate products are not allowed')

            product_ids.add(product_id)

            try:
                product = Product.objects.get(
                    pk=product_id,
                    is_active=True
                )
            except Product.DoesNotExist:
                raise ValueError('Active product not found')

            line_total = product.unit_price * quantity

            prepared_items.append({
                'product': product,
                'quantity': quantity,
                'unit_price': product.unit_price,
                'line_total': line_total,
            })

            subtotal += line_total

        if discount_type == 'fixed':
            discount_amount = discount_value
        elif discount_type == 'percent':
            discount_amount = (
                subtotal * discount_value / Decimal('100')
            ).quantize(Decimal('0.01'))
        else:
            discount_amount = Decimal('0.00')

        if discount_amount > subtotal:
            raise ValueError('Discount exceeds subtotal')

        total = subtotal - discount_amount

        try:
            with transaction.atomic():
                sale = Sale.objects.create(
                    sale_number='S' + uuid4().hex[:16].upper(),
                    submission_key=submission_key,
                    created_by=user,
                    discount_type=discount_type,
                    discount_value=discount_value,
                    subtotal=subtotal,
                    total=total
                )
        except IntegrityError:
            raise ValueError(
                'Sale could not be created. '
                'Please check whether it was already submitted.'
            )

        for item in prepared_items:
            product = item['product']
            quantity = item['quantity']

            SaleLine.objects.create(
                sale=sale,
                product=product,
                product_name=product.name,
                quantity=quantity,
                unit_price=item['unit_price'],
                line_total=item['line_total']
            )

            change_stock(
                product_id=product.pk,
                delta=-quantity,
                movement_type='sale',
                reason='Sale recorded',
                user=user,
                source=sale.sale_number
            )

    return sale
