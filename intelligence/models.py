
from django.db import models


class DailySales(models.Model):
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.PROTECT,
        related_name='daily_sales'
    )

    date = models.DateField(db_index=True)

    units_sold = models.PositiveIntegerField(
        default=0
    )

    gross_revenue = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'date'],
                name='unique_daily_sales_product_date'
            )
        ]
        ordering = ['date', 'product_id']

    def __str__(self):
        return f'{self.product.name} - {self.date}'
