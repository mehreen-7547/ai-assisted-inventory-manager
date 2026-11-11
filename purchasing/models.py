
from django.conf import settings
from django.db import models


class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('ordered', 'Ordered'),
        ('partially_received', 'Partially Received'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
        ('closed_short', 'Closed Short'),
    ]

    po_number = models.CharField(
        max_length=20,
        unique=True
    )
    supplier = models.ForeignKey(
        'catalog.Supplier',
        on_delete=models.PROTECT
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    expected_delivery_date = models.DateField(
        null=True,
        blank=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT
    )
    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.po_number


class PurchaseOrderLine(models.Model):
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.PROTECT,
        related_name='lines'
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.PROTECT
    )
    quantity_ordered = models.PositiveIntegerField()
    quantity_received = models.PositiveIntegerField(default=0)
    unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    def __str__(self):
        return self.product.name


class GoodsReceipt(models.Model):
    receipt_number = models.CharField(
        max_length=20,
        unique=True
    )
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT
    )
    received_at = models.DateTimeField(auto_now_add=True)
    note = models.TextField(blank=True)
    submission_key = models.CharField(
        max_length=100,
        unique=True
    )

    def __str__(self):
        return self.receipt_number


class GoodsReceiptLine(models.Model):
    receipt = models.ForeignKey(
        GoodsReceipt,
        on_delete=models.PROTECT,
        related_name='lines'
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.PROTECT
    )
    quantity_received = models.PositiveIntegerField()
    quantity_damaged = models.PositiveIntegerField(default=0)
    note = models.TextField(blank=True)

    def __str__(self):
        return self.product.name