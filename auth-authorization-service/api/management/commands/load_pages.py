import os

from django.conf import settings
from django.core.management.base import BaseCommand

from api.models import Page


class Command(BaseCommand):
    """
    To create pages in db.

    Management command will create the commands specified in the config and
    will create in database.
    """
    help = 'Creates pages in db.'

    def handle(self, *args, **options):
        for page_template_name in settings.PAGE_TEMPLATES:

            try:
                page_template = Page.objects.get(name=page_template_name)
            except Page.DoesNotExist:
                page_template = Page()
                page_template.name = page_template_name
            finally:
                template_name = "{}_page_template.html".format(page_template_name)
                template_path = os.path.join(settings.BASE_DIR, 'api/templates', template_name)
                with open(template_path, 'r') as f:
                    template_content = f.read()
                page_template.content = template_content
                page_template.save()