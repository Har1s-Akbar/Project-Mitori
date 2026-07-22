from django.db import models
from django.conf import settings
from decimal import Decimal
from django.utils import timezone

class Portfolio(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL,
                                on_delete=models.CASCADE)
    cash_balance = models.DecimalField(max_digits=15,decimal_places=2 , default=Decimal(0.00))
    created_at = models.DateTimeField(default=timezone.now)

class Position(models.Model):
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE)
    asset_symbol = models.CharField(max_length=6, blank=False, null=False)
    quantity = models.DecimalField(max_digits=10, decimal_places=2 , null=False, blank=False)
    average_entry_price = models.DecimalField(max_digits=10, decimal_places=2, null=False , blank=False)


class TransactionType(models.TextChoices):
    DEPOSIT = 'DEPOSIT', 'deposit'
    WITHDRAWL = 'WITHDRAWAL', 'withdrawal'
    BUY = 'BUY', 'buy'
    SELL = 'SELL', 'sell'

class Status(models.TextChoices):
    COMPLETED = 'COMPLETED', 'completed'
    PENDING = 'PENDING', 'pending'
    FAILED = 'FAILED', 'failed'

class LedgerTransaction(models.Model):
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=10, choices=TransactionType.choices)
    price_setteled_at = models.DecimalField(max_digits=15, decimal_places=2, null=False, blank=False)
    price_locked_by_user = models.DecimalField(max_digits=15, decimal_places=2, null=False, blank=False,default=Decimal('0.00'))
    quantity = models.DecimalField(max_digits=10, decimal_places=2 , null=False, blank=False, default=Decimal(0.00))
    status = models.CharField(max_length=10, choices=Status.choices, default = Status.PENDING)
    asset_symbol = models.CharField(max_length=8, blank=True, null=True)
    time_stamp = models.DateTimeField(auto_now_add=True)
    
# Create your models here.
