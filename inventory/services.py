
from django.db import transaction
from django.db.models import F

from catalog.models import Product
from .models import StockMovement


def change_stock(
    product_id, delta, movement_type, reason, user,
    source='', expected_balance=None
):
    if type(delta) is not int or delta == 0:
        raise ValueError('Stock change must be a non-zero integer')

    if movement_type not in dict(StockMovement.MOVEMENT_CHOICES):
        raise ValueError('Invalid stock movement type')

    if not reason or not reason.strip():
        raise ValueError('Reason is required')

    with transaction.atomic():
        
        products = Product.objects.filter(pk=product_id)

        if expected_balance is not None:
            products = products.filter(
                on_hand=expected_balance
            )

        if delta < 0:
            products = products.filter(
                on_hand__gte=-delta
            )

        changed = products.update(
            on_hand=F('on_hand') + delta
        )

        if changed == 0:
            if not Product.objects.filter(pk=product_id).exists():
                raise ValueError('Product not found')

            if expected_balance is not None:
                raise ValueError(
                    'Stock changed since the page was opened. '
                    'Refresh and check the quantity again.'
                )

            raise ValueError('Not enough stock')


        product = Product.objects.get(pk=product_id)

        movement = StockMovement.objects.create(
            product=product,
            movement_type=movement_type,
            quantity_delta=delta,
            balance_before=product.on_hand - delta,
            balance_after=product.on_hand,
            reason=reason,
            source=source,
            created_by=user
        )

    return movement




def adjust_stock(
    product_id, counted_quantity, reason, user,
    expected_balance
):
    if type(counted_quantity) is not int or counted_quantity < 0:
        raise ValueError(
            'Counted quantity must be zero or greater'
        )

    if type(expected_balance) is not int or expected_balance < 0:
        raise ValueError('Invalid recorded quantity')

    if not reason or not reason.strip():
        raise ValueError('Reason is required')

    difference = counted_quantity - expected_balance

    if difference == 0:
        raise ValueError(
            'Counted quantity is already correct'
        )

    return change_stock(
        product_id=product_id,
        delta=difference,
        movement_type='adjustment',
        reason=reason.strip(),
        user=user,
        expected_balance=expected_balance
    )

