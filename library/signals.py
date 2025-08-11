from datetime import timedelta

from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone

from library.models import Loan


@receiver(pre_save, sender=Loan)
def update_due_date_before_save(sender, instance, **kwargs):
    if instance.due_date is None:
        due_date = instance.loan_date
        print("Due date", due_date)
        if due_date is None:
            due_date = timezone.now()
        due_date = due_date + timedelta(days=14)

        instance.due_date = due_date


