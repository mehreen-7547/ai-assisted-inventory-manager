
from decimal import Decimal
from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from catalog.models import Product
from .forms import PurchaseOrderForm
from .models import PurchaseOrder
from .services import (
    change_purchase_order_status,
    create_purchase_order
)


def manager_allowed(user):
    return (
        user.is_authenticated
        and user.is_active
        and user.role == 'manager'
    )


@login_required
def purchase_order_create(request):
    if not manager_allowed(request.user):
        messages.error(
            request,
            'Only active managers can create purchase orders.'
        )
        return redirect('home')

    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST)

        if form.is_valid():
            data = form.cleaned_data
            supplied_number = data.get('po_number')

            for attempt in range(5):
                po_number = supplied_number or (
                    'PO-' + uuid4().hex[:12].upper()
                )

                try:
                    order = create_purchase_order(
                        po_number=po_number,
                        supplier_id=data['supplier'].pk,
                        items=data['items'],
                        user=request.user
                    )

                except ValueError as error:
                    if (
                        not supplied_number
                        and str(error) ==
                        'Purchase order number already exists.'
                        and attempt < 4
                    ):
                        continue

                    form.add_error(None, str(error))
                    break

                else:
                    messages.success(
                        request,
                        'Purchase order created successfully.'
                    )

                    if supplied_number:
                        return redirect('home')

                    return redirect(
                        'purchase_order_detail',
                        pk=order.pk
                    )

    else:
        form = PurchaseOrderForm()

    available_products = Product.objects.filter(
        is_active=True,
        supplier__is_active=True
    ).order_by('name')

    product_suppliers = {
        str(product.pk): product.supplier_id
        for product in available_products
    }

    product_details = {
        str(product.pk): {
            'on_hand': product.on_hand,
            'safety_stock': product.safety_stock,
            'lead_time_days': product.lead_time_days,
            'unit_price': str(product.unit_price)
        }
        for product in available_products
    }

    order_rows = []

    for number in form.row_numbers:
        order_rows.append({
            'product': form[f'product_{number}'],
            'quantity': form[f'quantity_{number}'],
            'unit_cost': form[f'unit_cost_{number}']
        })

    next_row_number = max(form.row_numbers, default=0) + 1

    return render(
        request,
        'purchasing/purchase_order_form.html',
        {
            'form': form,
            'order_rows': order_rows,
            'available_products': available_products,
            'product_suppliers': product_suppliers,
            'product_details': product_details,
            'next_row_number': next_row_number
        }
    )


@login_required
def purchase_order_list(request):
    if not manager_allowed(request.user):
        messages.error(
            request,
            'Only active managers can view purchase orders.'
        )
        return redirect('home')

    orders = PurchaseOrder.objects.select_related(
        'supplier',
        'created_by'
    ).annotate(
        product_count=Count('lines')
    ).order_by('-created_at', '-pk')

    return render(
        request,
        'purchasing/purchase_order_list.html',
        {
            'orders': orders
        }
    )


@login_required
def purchase_order_detail(request, pk):
    if not manager_allowed(request.user):
        messages.error(
            request,
            'Only active managers can view purchase orders.'
        )
        return redirect('home')

    order = get_object_or_404(
        PurchaseOrder.objects.select_related(
            'supplier',
            'created_by'
        ),
        pk=pk
    )

    lines = order.lines.select_related('product').all()
    order_items = []
    order_total = Decimal('0.00')

    for line in lines:
        line_total = line.quantity_ordered * line.unit_cost
        order_total += line_total

        order_items.append({
            'line': line,
            'line_total': line_total
        })

    return render(
        request,
        'purchasing/purchase_order_detail.html',
        {
            'order': order,
            'order_items': order_items,
            'order_total': order_total
        }
    )


@login_required
@require_POST
def purchase_order_status(request, pk):
    if not manager_allowed(request.user):
        messages.error(
            request,
            'Only active managers can change order status.'
        )
        return redirect('home')

    new_status = request.POST.get('status', '')

    try:
        change_purchase_order_status(
            order_id=pk,
            new_status=new_status,
            user=request.user
        )

    except ValueError as error:
        messages.error(request, str(error))

    else:
        messages.success(
            request,
            'Purchase order status updated successfully.'
        )

    return redirect('purchase_order_detail', pk=pk)
