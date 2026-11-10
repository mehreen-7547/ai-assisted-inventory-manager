from django.db import models


class Supplier(models.Model):
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    category = models.CharField(max_length=100)

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT
    )

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    lead_time_days = models.PositiveIntegerField(default=0)
    safety_stock = models.PositiveIntegerField(default=0)
    on_hand = models.PositiveIntegerField(
        default=0,
        editable=False
    )

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
