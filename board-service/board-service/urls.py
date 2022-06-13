from django.urls import path
from django.conf.urls import include

from rest_framework_swagger.views import get_swagger_view


handler404 = 'api.error_handlers.page_not_found'

handler500 = 'api.error_handlers.server_error'

excluded_url = [
    path('board/api/v1/', include('api.urls')),
]

urlpatterns = excluded_url + [
    path(
        'api-docs/', get_swagger_view(
            title='Innovo Builders Boards API',
            patterns=excluded_url,
        ),
    ),
]
