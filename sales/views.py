
from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required

from .models import Sale

from django.core.paginator import Paginator
from django.db.models import Q

from django.views.decorators.http import require_POST

from .forms import SaleForm, VoidSaleForm
from .services import record_sale, void_sale

from catalog.models import Product




@login_required
@role_required('sales', 'manager')
def sale_list(request):
    sales = Sale.objects.select_related(
        'created_by'
    ).order_by('-created_at', '-pk')

    if request.user.role == 'sales':
        sales = sales.filter(created_by=request.user)

    search = request.GET.get('search', '').strip()
    status = request.GET.get('status', '').strip()

    if search:
        sales = sales.filter(
            Q(sale_number__icontains=search)
            | Q(created_by__username__icontains=search)
        )

    if status in ['completed', 'voided']:
        sales = sales.filter(status=status)
    else:
        status = ''

    paginator = Paginator(sales, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'sales/sale_list.html', {
        'page_obj': page_obj,
        'search': search,
        'status': status
    })




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

    sale_rows = [
        {
            'product': form[f'product_{number}'],
            'quantity': form[f'quantity_{number}']
        }
        for number in form.row_numbers
    ]

    available_products = Product.objects.filter(
        is_active=True,
        on_hand__gt=0
    ).order_by('name')

    return render(request, 'sales/sale_form.html', {
        'form': form,
        'submission_key': submission_key,
        'sale_rows': sale_rows,
        'available_products': available_products,
        'next_row_number': max(form.row_numbers, default=0) + 1
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


@login_required
@role_required('manager')
def sale_void(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id)

    if request.method == 'POST':
        form = VoidSaleForm(request.POST)

        if form.is_valid():
            try:
                void_sale(
                    sale_id=sale.pk,
                    reason=form.cleaned_data['reason'],
                    user=request.user
                )

                messages.success(
                    request,
                    'Sale voided and stock restored successfully.'
                )

                return redirect('sale_detail', sale_id=sale.pk)

            except ValueError as error:
                form.add_error(None, str(error))

    else:
        form = VoidSaleForm()

    return render(request, 'sales/sale_void.html', {
        'sale': sale,
        'form': form
    })