
from django.db import transaction
from django.db.models import F

from catalog.models import Product
from .models import StockMovement


def change_stock(product_id, delta, movement_type, reason, user, source=''):
    if type(delta) is not int or delta == 0:
        raise ValueError('Stock change must be a non-zero integer')

    if movement_type not in dict(StockMovement.MOVEMENT_CHOICES):
        raise ValueError('Invalid stock movement type')

    if not reason or not reason.strip():
        raise ValueError('Reason is required')

    with transaction.atomic():
        if delta < 0:
            changed = Product.objects.filter(
                pk=product_id,
                on_hand__gte=-delta
            ).update(on_hand=F('on_hand') + delta)
        else:
            changed = Product.objects.filter(
                pk=product_id
            ).update(on_hand=F('on_hand') + delta)

        if changed == 0:
            if not Product.objects.filter(pk=product_id).exists():
                raise ValueError('Product not found')
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
