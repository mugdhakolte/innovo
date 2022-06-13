from django.db import models

from django_filters import rest_framework as filters

from api.models import *


class ProjectMemberFilter(filters.FilterSet):
    """To filter plans on all fields"""

    class Meta:
        model = ProjectMember
        fields = '__all__'
        filter_overrides = {
            models.DateTimeField: {
                'filter_class': filters.DateFromToRangeFilter,
            },
            models.ForeignKey: {
                'filter_class': filters.NumberFilter,
            }
        }


class ProjectFilter(filters.FilterSet):
    class Meta:
        model = Project
        fields = '__all__'
        filter_overrides = {
            models.CharField: {
                'filter_class': filters.CharFilter,
                'extra': lambda f: {
                    'lookup_expr': 'icontains',
                },
            },
            models.FileField: {
                'filter_class': filters.CharFilter,
                'extra': lambda f: {
                    'lookup_expr': 'icontains',
                }
            }
        }