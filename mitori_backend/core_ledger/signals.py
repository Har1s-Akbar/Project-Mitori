from django.db.models.signals import post_save
from django.conf import settings
from django.dispatch import receiver
from core_ledger.models import Portfolio, LedgerTransaction

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def initialize_tables(sender, instance,created,**kwargs):
    if created:
        Portfolio.objects.create(user=instance)