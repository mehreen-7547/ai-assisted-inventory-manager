
from django.conf import settings
from django.db import models


class StockMovement(models.Model):
    MOVEMENT_CHOICES = (
        ('opening', 'Opening Stock'),
        ('sale', 'Sale'),
        ('void', 'Void Sale'),
        ('receipt', 'Goods Receipt'),
        ('adjustment', 'Stock Adjustment'),
    )

    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.PROTECT
    )
    movement_type = models.CharField(
        max_length=20,
        choices=MOVEMENT_CHOICES
    )
    quantity_delta = models.IntegerField()
    balance_before = models.PositiveIntegerField()
    balance_after = models.PositiveIntegerField()
    reason = models.TextField()
    source = models.CharField(max_length=150, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.product.name}: {self.quantity_delta}'
