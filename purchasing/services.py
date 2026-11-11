
from decimal import Decimal


from accounts.models import CustomUser
from catalog.models import Product, Supplier

from .models import PurchaseOrder, PurchaseOrderLine

from django.db import IntegrityError, transaction



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
