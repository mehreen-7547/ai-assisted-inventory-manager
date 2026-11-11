
from django.contrib import admin

from .models import PurchaseOrder, PurchaseOrderLine


class PurchaseOrderLineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 1


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = [
        'po_number',
        'supplier',
        'status',
        'expected_delivery_date',
        'created_by',
        'created_at'
    ]
    list_filter = ['status']
    search_fields = [
        'po_number',
        'supplier__name'
    ]
    inlines = [PurchaseOrderLineInline]
