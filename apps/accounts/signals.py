from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Community, CommunityScope, Company, Department


@receiver(post_save, sender=Company)
def create_company_community(sender, instance, created, **kwargs):
    if created:
        Community.objects.create(
            company=instance, scope=CommunityScope.COMPANY, name=f'{instance.name} - All Members'
        )


@receiver(post_save, sender=Department)
def create_department_community(sender, instance, created, **kwargs):
    if created:
        Community.objects.create(
            company=instance.company, scope=CommunityScope.DEPARTMENT, department=instance, name=instance.name
        )
