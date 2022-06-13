"""Mixins for api app."""
from django_filters import rest_framework as filters

from django.db import models


class BoardProjectBoardMemberFilterMixin(filters.FilterSet):

    @property
    def qs(self):
        project_id = self.request.query_params.get("project_id")
        user_id = self.request.query_params.get("user_id")
        if user_id:
            return super().qs.filter(board_members__user_id=user_id, project_id=project_id)
        else:
            return super().qs.filter()


class TaskProjectFilterSetMixin(filters.FilterSet):
    """To filter on exact field for date from and to arguments"""

    @property
    def qs(self):
        """
        :return: filter by date
        """
        project_id = self.request.query_params.get("project_id")
        if project_id:
            return super().qs.filter(board_stage__board__project_id=project_id)
        return super().qs.filter()


class DjangoFilterSetMixin:
    """To filter on exact field for date from and to arguments"""

    @property
    def qs(self):
        """
        :return: filter by date
        """
        date = self.request.query_params.get("created_at")
        if date:
            return super().qs.filter(created_at__date=date)
        else:
            return super().qs.filter()


class MetaFilterSetMixin:
    """To override datetime fields with date from and to filters"""

    fields = '__all__'
    filter_overrides = {
        models.DateTimeField: {
            'filter_class': filters.DateFromToRangeFilter,
        },
        models.FileField: {
            'filter_class': filters.CharFilter,
            'extra': lambda f: {
                'lookup_expr': 'icontains',
            }
        }
    }
