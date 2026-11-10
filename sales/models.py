
from django.conf import settings
from django.db import models


class Sale(models.Model):
    STATUS_CHOICES = [
        ('completed', 'Completed'),
        ('voided', 'Voided'),
    ]

    DISCOUNT_CHOICES = [
        ('none', 'None'),
        ('fixed', 'Fixed'),
        ('percent', 'Percent'),
    ]

    sale_number = models.CharField(max_length=20, unique=True)
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='completed'
    )
    discount_type = models.CharField(
        max_length=10,
        choices=DISCOUNT_CHOICES,
        default='none'
    )
    discount_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    subtotal = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    total = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_sales'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='voided_sales'
    )
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.TextField(blank=True)
    submission_key = models.CharField(max_length=36, unique=True)

    def __str__(self):
        return self.sale_number


class SaleLine(models.Model):
    sale = models.ForeignKey(
        Sale,
        on_delete=models.PROTECT,
        related_name='lines'
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.PROTECT
    )
    product_name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(
        max_digits=10, decimal_places=2
    )
    line_total = models.DecimalField(
        max_digits=12, decimal_places=2
    )

    def __str__(self):
        return self.product_name
