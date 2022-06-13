"""Used for send notifications"""
from django.conf import settings
from django.core.management.base import BaseCommand

from api.models import Stage


class Command(BaseCommand):
    """Fetches and processes notifications that are pending."""

    def handle(self, *args, **kwargs):
        for default_stage in settings.STAGES:
            Stage.objects.get_or_create(name=default_stage.get('name'),
                                        is_default_stage=default_stage.get('is_default'),
                                        default_position=default_stage.get('position'))



