
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from catalog.models import Product
from .forms import PurchaseOrderForm
from .services import create_purchase_order


@login_required
def purchase_order_create(request):
    if not request.user.is_active or request.user.role != 'manager':
        messages.error(
            request,
            'Only active managers can create purchase orders.'
        )
        return redirect('home')

    if request.method == 'POST':
        form = PurchaseOrderForm(request.POST)

        if form.is_valid():
            data = form.cleaned_data

            try:
                create_purchase_order(
                    po_number=data['po_number'],
                    supplier_id=data['supplier'].pk,
                    items=data['items'],
                    user=request.user
                )

            except ValueError as error:
                form.add_error(None, str(error))

            else:
                messages.success(
                    request,
                    'Purchase order created successfully.'
                )
                return redirect('home')

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
            'next_row_number': next_row_number
        }
    )
