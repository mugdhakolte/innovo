from django.apps import AppConfig


class ApiConfig(AppConfig) :
    name = 'api'
    verbose_name = 'API Data'
    label = 'api'

    def ready(self) :
        """
        To execute on app load.

        Creates storage bucket if does not exists from settings.
        """
        super().ready()


