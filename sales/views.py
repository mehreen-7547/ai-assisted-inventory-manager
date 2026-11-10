
from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required
from .forms import SaleForm
from .models import Sale
from .services import record_sale


@login_required
@role_required('sales', 'manager')
def sale_create(request):
    if request.method == 'POST':
        form = SaleForm(request.POST)
        submission_key = request.POST.get('submission_key', '')

        if form.is_valid():
            try:
                sale = record_sale(
                    items=form.cleaned_data['items'],
                    user=request.user,
                    submission_key=submission_key,
                    discount_type=form.cleaned_data['discount_type'],
                    discount_value=form.cleaned_data['discount_value']
                )

                messages.success(
                    request,
                    'Sale recorded successfully.'
                )

                return redirect('sale_detail', sale_id=sale.pk)

            except ValueError as error:
                form.add_error(None, str(error))

    else:
        form = SaleForm()
        submission_key = str(uuid4())

    return render(request, 'sales/sale_form.html', {
        'form': form,
        'submission_key': submission_key,
        'row_numbers': range(1, 6)
    })


@login_required
@role_required('sales', 'manager')
def sale_detail(request, sale_id):
    sale = get_object_or_404(
        Sale.objects.select_related('created_by'),
        pk=sale_id
    )

    if (
        request.user.role == 'sales'
        and sale.created_by_id != request.user.pk
    ):
        messages.error(
            request,
            'You cannot view another employee\'s sale.'
        )
        return redirect('home')

    lines = sale.lines.all()

    return render(request, 'sales/sale_detail.html', {
        'sale': sale,
        'lines': lines
    })
