"""Author : filters for all models"""
from django_filters import rest_framework as filters

from api.models import *
from api.mixins import *


class BoardFilter(BoardProjectBoardMemberFilterMixin):

    class Meta(MetaFilterSetMixin):
        """Meta class for board"""
        model = Board


class StageFilter(filters.FilterSet):
    """To filter plans on all fields"""

    class Meta(MetaFilterSetMixin):
        """Meta class for Stage"""
        model = Stage


class BoardStageMapFilter(filters.FilterSet):
    """To filter plans on all fields"""

    class Meta(MetaFilterSetMixin):
        """Meta class for BoardStageMap"""
        model = BoardStageMap


class BoardMemberFilter(filters.FilterSet):
    """To filter plans on all fields"""

    class Meta(MetaFilterSetMixin):
        """Meta class for BoardMember"""
        model = BoardMember


class LabelFilter(filters.FilterSet):
    """To filter plans on all fields"""

    class Meta(MetaFilterSetMixin):
        """Meta class for Label"""
        model = Label


class CategoryFilter(filters.FilterSet):
    """To filter plans on all fields"""

    class Meta(MetaFilterSetMixin):
        """Meat class for Category"""
        model = Category


class TaskFilter(TaskProjectFilterSetMixin):
    """To filter plans on all fields"""

    class Meta(MetaFilterSetMixin):
        """Meta class for Task"""
        model = Task


class TaskMemberFilter(filters.FilterSet):
    """To filter plans on all fields"""

    class Meta(MetaFilterSetMixin):
        """Meta class for TaskMember"""
        model = TaskMember


class AttachmentFilter(filters.FilterSet):
    """To filter plans on all fields"""

    class Meta(MetaFilterSetMixin):
        """Meta class for Attachment"""
        model = Attachment


class ChecklistFilter(filters.FilterSet):
    """To filter plans on all fields"""

    class Meta(MetaFilterSetMixin):
        """Meta class for Checklist"""
        model = Checklist


class ChecklistItemFilter(filters.FilterSet):
    """To filter plans on all fields"""

    class Meta(MetaFilterSetMixin):
        """Meta class for ChecklistItem"""
        model = ChecklistItem


class ActivityFilter(filters.FilterSet):
    """To filter plans on all fields"""

    class Meta(MetaFilterSetMixin):
        """Meta class for Activity"""
        model = Activity
