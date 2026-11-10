
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required

from accounts.decorators import role_required
from catalog.models import Product

from .forms import StockAdjustmentForm
from .services import adjust_stock


@login_required
@role_required('manager')
def stock_adjustment(request, product_id):
    product = get_object_or_404(
        Product,
        pk=product_id
    )

    if not product.is_active:
        return redirect('product_list')

    if request.method == 'POST':
        form = StockAdjustmentForm(request.POST)

        if form.is_valid():
            try:
                adjust_stock(
                    product_id=product.pk,
                    counted_quantity=form.cleaned_data[
                        'counted_quantity'
                    ],
                    reason=form.cleaned_data['reason'],
                    user=request.user,
                    expected_balance=form.cleaned_data[
                        'expected_balance'
                    ]
                )
            except ValueError as error:
                form.add_error(None, str(error))
            else:
                return redirect(
                    'product_stock_history',
                    product_id=product.pk
                )
    else:
        form = StockAdjustmentForm(initial={
            'expected_balance': product.on_hand
        })

    return render(
        request,
        'inventory/stock_adjustment.html',
        {
            'form': form,
            'product': product
        }
    )
