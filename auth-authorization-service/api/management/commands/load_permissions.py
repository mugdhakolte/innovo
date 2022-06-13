from django.conf import settings
from django.core.management.base import BaseCommand

from api.models import Permission


class Command(BaseCommand):
    """
    To create permissions in db.

    Management command will create the commands specified in the config and
    will create in database.
    """
    help = 'Creates permissions in db.'

    def handle(self, *args, **options):
        for permission in settings.PERMISSIONS:
            Permission.objects.get_or_create(**permission)
