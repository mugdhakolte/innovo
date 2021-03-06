# -*- coding: utf-8 -*-
"""auth_service URL Configuration.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))

"""
from django.urls import path
from django.contrib import admin
from django.conf.urls import include

from rest_framework_swagger.views import get_swagger_view


excluded_url = [
    path('admin/', admin.site.urls),
    path('auth/api/v1/', include('api.urls')),
]

urlpatterns = excluded_url + [
    path(
        'api-docs/', get_swagger_view(
            title='Innovo Builders Auth API',
            patterns=excluded_url,
        ),
    ),
]

handler404 = 'api.error_handlers.page_not_found'

handler500 = 'api.error_handlers.server_error'
