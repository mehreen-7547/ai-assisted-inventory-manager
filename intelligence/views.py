from django.shortcuts import render
from django.utils import timezone

from accounts.decorators import role_required
from catalog.models import Product

from .forecasting import forecast_product_demand
from .shortage_prediction import predict_stock_shortage
from .reorder_recommendation import recommend_reorder_quantity
from .anomaly_detection import detect_sales_anomalies
from .models import DailySales


@role_required('manager')
def intelligence_dashboard(request):
    products = Product.objects.filter(
        is_active=True
    ).order_by('name')

    selected_product = None
    results = {}
    errors = {}
    analysis_date = None

    product_id = request.GET.get('product')

    if product_id:
        selected_product = products.filter(
            pk=product_id
        ).first() if product_id.isdigit() else None

        if selected_product is None:
            errors['selection'] = (
                'Please select a valid active product.'
            )
        else:
            latest_sales_date = DailySales.objects.filter(
                product=selected_product,
                date__lte=timezone.localdate()
            ).order_by('-date').values_list('date', flat=True).first()

            end_date = latest_sales_date or timezone.localdate()
            analysis_date = end_date

            services = {
                'forecast': forecast_product_demand,
                'shortage': predict_stock_shortage,
                'reorder': recommend_reorder_quantity,
                'anomalies': detect_sales_anomalies
            }

            for name, service in services.items():
                try:
                    results[name] = service(
                        selected_product.pk,
                        end_date
                    )
                except Exception:
                    errors[name] = (
                        'This analysis is currently unavailable.'
                    )

    return render(
        request,
        'intelligence/dashboard.html',
        {
            'products': products,
            'selected_product': selected_product,
            'results': results,
            'errors': errors,
            'analysis_date': analysis_date
        }
    )
