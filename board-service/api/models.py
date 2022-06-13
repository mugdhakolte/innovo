"""Author: board service models."""
import random
import string

from datetime import timedelta
from itertools import chain

from model_clone import CloneMixin

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import FileExtensionValidator

from api.utils import get_attachments_dynamic_path
from api.move_task_utils import *


class Board(models.Model):
    """Class representing a Board."""

    name = models.CharField(max_length=128, null=False, blank=False)
    project_id = models.IntegerField(null=False, blank=False)
    display_color = models.CharField(max_length=48, null=False, blank=False)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True,
                                      null=False, blank=False)
    created_by = models.IntegerField(null=False, blank=False)
    stages = models.ManyToManyField('Stage', through='BoardStageMap', related_name='boards')

    def __str__(self):
        """
        project_id and Board name
        :return: project_id-name
        """
        return "{0}-{1}".format(self.project_id, self.name)

    def has_permission(self, user):
        if self.board_members.all():
            try:
                board_member = self.board_members.all().get(user_id=user)
                return board_member
            except BoardMember.DoesNotExist:
                return False
        else:
            return False

    class Meta:
        """Meta class for Board."""

        ordering = ['-created_at']
        unique_together = (('name', 'project_id'),)


class GanttChartLable(models.Model):
    """"""
    name = models.CharField(max_length=48, null=False, blank=False)
    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='gantt_chart_labels')
    position = models.IntegerField(null=True, blank=True)
    stages = models.ForeignKey('BoardStageMap', null=True, on_delete=models.SET_NULL, related_name='gantt_chart_labels')
    tasks = models.ForeignKey('Task', null=True, on_delete=models.SET_NULL, related_name='gantt_chart_labels')
    progress = models.DecimalField(default=0,max_digits=5, decimal_places=3)
    start_date = models.DateField(_('start date'), null=True, blank=True)
    end_date = models.DateField(_('end date'), null=True, blank=True)
    parent_label_id = models.ForeignKey('GanttChartLable', null=True, blank=True, on_delete=models.CASCADE,
                                        related_name='sub_labels')


    def __str__(self):
        """
        Stage name
        :return: name
        """
        return "{0}".format(self.name)

    def gantt_chart_label_move(self, new_position):
        if all([self.tasks, self.stages, self.board]):
            labels = GanttChartLable.objects.filter(board=self.board,
                                                    stages=self.stages,
                                                    tasks=self.tasks).exclude(id=self.id)
            self._move(new_position, labels)
        if all([self.stages, self.board]):
            labels = GanttChartLable.objects.filter(board=self.board,
                                                    stages=self.stages,
                                                    tasks__isnull=True).exclude(id=self.id)
            self._move(new_position, labels)
        if self.board:
            labels = GanttChartLable.objects.filter(board=self.board,
                                                    stages__isnull=True,
                                                    tasks__isnull=True).exclude(id=self.id)
            self._move(new_position, labels)
        return True

    def _move(self, new_position, labels):
        old_position = self.position
        new_position = int(new_position)
        for label in labels:
            position = label.position
            if old_position < position <= new_position:
                label.position = position - 1
                label.save()
            elif old_position >= position >= new_position:
                label.position = position + 1
                label.save()
        self.position = new_position
        self.save()
        return True


class Stage(models.Model):
    """Class representing a Board member stage."""

    name = models.CharField(max_length=48, null=False, blank=False, unique=True)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True,
                                      null=False, blank=False)
    is_default_stage = models.BooleanField(default=False)
    default_position = models.IntegerField(null=True, blank=True)


    def __str__(self):
        """
        Stage name
        :return: name
        """
        return "{0}".format(self.name)

class BoardStageMap(models.Model):
    """Class representing a Board stage map."""
    board = models.ForeignKey(Board, null=True, on_delete=models.SET_NULL, related_name='board_stage_maps')
    stage = models.ForeignKey(Stage, on_delete=models.CASCADE, related_name='board_stage_maps')
    position = models.IntegerField(null=False, blank=False, default=0)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True,
                                      null=False, blank=False)
    gantt_chart_position = models.IntegerField(default=0)
    progress = models.DecimalField(default=0, max_digits=3, decimal_places=1)
    board_stage_label = models.ForeignKey(GanttChartLable, null=True, on_delete=models.SET_NULL,
                                          related_name='board_stage_map')
    start_date = models.DateField(_('start date'), null=True, blank=True)
    end_date = models.DateField(_('end date'), null=True, blank=True)
    display_in_gantt_chart = models.BooleanField(default=False)
    is_display_in_board = models.BooleanField(default=False)

    class Meta:
        """Meta class for Board stage map."""

        ordering = ['position']
        unique_together = (('board', 'stage'),)

    def copy(self, new_position):
        for board_stage in self.board.board_stage_maps.all().exclude(id=self.id):
            position = board_stage.position
            if new_position <= position:
                board_stage.position = position + 1
                board_stage.save()
        self.position = new_position
        self.save()
        return True

    def move(self, new_position):
        old_position = self.position
        for board_stage in self.board.board_stage_maps.all().exclude(id=self.id):
            position = board_stage.position
            if old_position < position <= new_position:
                board_stage.position = position - 1
                board_stage.save()
            elif old_position >= position >= new_position:
                board_stage.position = position + 1
                board_stage.save()
        self.position = new_position
        self.save()
        return True

    def move_gantt_stages(self, new_position, stages):
        old_position = self.gantt_chart_position
        for stage in stages:
            position = int(stage.gantt_chart_position)
            if old_position > position >= new_position:
                stage.gantt_chart_position = position + 1
                stage.save()
            if old_position < position <= new_position:
                stage.gantt_chart_position = position - 1
                stage.save()
        return True

    def move_gantt_labels(self, new_position, labels):
        old_position = self.gantt_chart_position
        for label in labels:
            position = int(label.position)
            if old_position > position >= new_position:
                label.position = position + 1
                label.save()
            if old_position < position <= new_position:
                label.position = position - 1
                label.save()
        return True

    def gantt_chart_stage_move(self, new_position):
        old_position = self.gantt_chart_position
        boards = Board.objects.filter(project_id=self.board.project_id)
        board_stage_maps = [board.board_stage_maps.all() for board in boards if board.board_stage_maps]
        board_stage_maps = [bsm for bsms in board_stage_maps for bsm in bsms if bsm.id != self.id]
        board_labels = [board.gantt_chart_labels.all() for board in boards if board.gantt_chart_labels]
        labels = [label for labels in board_labels for label in labels if label]
        for label in labels:
            position = label.position
            if old_position < position <= new_position:
                label.position = position - 1
                label.save()
            elif old_position >= position >= new_position:
                label.position = position + 1
                label.save()
        for board_stage_map in board_stage_maps:
            position = board_stage_map.gantt_chart_position
            if old_position < position <= new_position:
                board_stage_map.gantt_chart_position = position - 1
                board_stage_map.save()
            elif old_position >= position >= new_position:
                board_stage_map.gantt_chart_position = position + 1
                board_stage_map.save()
        self.gantt_chart_position = new_position
        if self.board_stage_label:
            self.board_stage_label = None
        self.save()
        return True

    @property
    def stage_name(self):
        return self.stage.name

    @property
    def board_name(self):
        return self.board.name


class BoardMember(models.Model):
    """Class representing a Board member."""

    board = models.ForeignKey(Board, on_delete=models.CASCADE, related_name='board_members')
    user_id = models.IntegerField(null=False, blank=False)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True,
                                      null=False, blank=False)
    created_by = models.IntegerField(null=False, blank=False)

    class Meta:
        """Meta class for Board Member."""

        unique_together = (('board', 'user_id'),)


class Label(models.Model):
    """Class representing a Label."""

    name = models.CharField(max_length=48, null=False, blank=False)
    color_code = models.CharField(max_length=48, null=False, blank=False)
    board = models.ForeignKey(Board, null=True, blank=True, on_delete=models.CASCADE, related_name='labels')
    project_id = models.IntegerField(null=True, blank=True)

    def __str__(self):
        """
        Label name
        :return: name
        """
        return '{}'.format(self.name)

    class Meta:
        """Meta class for Board stage map."""

        unique_together = (('name', 'board'), ('name', 'project_id'), )


class Category(models.Model):
    """Class representing the categories."""

    name = models.CharField(max_length=48, null=False, blank=False, unique=True)

    def __str__(self):
        """
        Category name
        :return: name
        """
        return '{}'.format(self.name)


class Task(CloneMixin, models.Model):
    """Class representing task model."""
    TYPES = [('High', 'High'), ('Medium', 'Medium'), ('Low', 'Low')]

    title = models.CharField(max_length=128, null=False, blank=False)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True,
                                      null=False, blank=False)
    created_by = models.IntegerField(null=False, blank=False)
    description = models.TextField(null=False, blank=False)
    is_archived = models.BooleanField(default=False)
    """ updated title with unique=True, and board_stage with null, and removed unique_together"""
    board_stage = models.ForeignKey(BoardStageMap, on_delete=models.SET_NULL, null=True, related_name='tasks')
    # board_stage = models.ForeignKey(BoardStageMap, on_delete=models.CASCADE, related_name='tasks')
    display_in_gantt_chart = models.BooleanField(default=False)
    start_date = models.DateField(_('start date'), null=True, blank=True)
    end_date = models.DateField(_('end date'), null=True, blank=True)
    is_key_task = models.BooleanField(default=False)
    position = models.IntegerField(null=False, blank=False, default=0)
    gantt_chart_position = models.IntegerField(null=False, blank=False, default=0)
    category = models.IntegerField(null=True, blank=True)
    labels = models.ManyToManyField(Label, related_name='tasks', blank=True)
    share_key = models.CharField(max_length=16, null=True, unique=True)
    is_display_in_board = models.BooleanField(default=True)
    parent_task_id = models.ForeignKey('Task', null=True, blank=True,
                                       related_name='sub_tasks', on_delete=models.CASCADE)
    task_dependencies = models.ManyToManyField('Task', through='TaskDependencyMap', related_name='tasks')
    delay = models.IntegerField(default=0)
    due_date = models.DateField(_('start date'), null=True, blank=True)
    progress = models.DecimalField(default=0, max_digits=5, decimal_places=3)
    """task_labels field is added for gantt chart"""
    task_labels = models.ForeignKey(GanttChartLable, null=True, on_delete=models.SET_NULL, related_name='taskss')
    priority = models.CharField(max_length=8, choices=TYPES, default="Low")
    is_display_in_dashboard = models.BooleanField(default=False)
    task_type = models.CharField(max_length=120, null=True, blank=True)
    is_critical_path_task = models.BooleanField(default=False)
    procurement_id = models.IntegerField(null=True, blank=True)
    product_category_id = models.IntegerField(null=True, blank=True)

    # _clonable_many_to_many_fields = ['labels']

    def __str__(self):
        """
        Task title
        :return: title
        """
        return '{}'.format(self.title)

    def move(self, new_position):
        old_position = self.position
        for task in self.board_stage.tasks.filter(is_display_in_board=True).exclude(id=self.id):
            position = task.position
            if old_position < position <= new_position:
                task.position = position - 1
                task.save()
            elif old_position >= position >= new_position:
                task.position = position + 1
                task.save()

        self.position = new_position
        self.save()
        return True

    def move_gantt_chart_task(self, new_position):
        """
        Move gantt chart task
        :param new_position:
        :return:
        """
        tasks, stages, labels = None, None, None
        old_position = self.gantt_chart_position
        if not self.parent_task_id and not self.task_labels:
            board = check_task_board(self)
            boards = Board.objects.filter(project_id=board.project_id)
            stages = [stage for board in boards for stage in board.board_stage_maps.all() if stage]
            labels = [label for board in boards for label in board.gantt_chart_labels.filter \
                (tasks__isnull=True, parent_label_id__isnull=True)]
            tasks = [task for stage in stages for task in stage.tasks.filter(display_in_gantt_chart=True,
                                                                             task_labels__isnull=True,
                                                                             parent_task_id__isnull=True).exclude(id=self.id)]
        if self.parent_task_id:
            labels = self.parent_task_id.gantt_chart_labels.all().exclude(id=self.id)
            tasks = self.parent_task_id.sub_tasks.filter(display_in_gantt_chart=True).exclude(id=self.id)
        if self.task_labels:
            labels = self.task_labels.sub_labels.all()
            tasks = self.task_labels.taskss.filter(display_in_gantt_chart=True).exclude(id=self.id)
        if labels:
            for label in labels:
                position = label.position
                if old_position < position <= new_position:
                    label.position = position - 1
                    label.save()
                elif old_position >= position >= new_position:
                    label.position = position + 1
                    label.save()
        if tasks:
            for task in tasks:
                position = task.gantt_chart_position
                if old_position < position <= new_position:
                    task.gantt_chart_position = position - 1
                    task.save()
                elif old_position >= position >= new_position:
                    task.gantt_chart_position = position + 1
                    task.save()
        self.gantt_chart_position = new_position
        self.save()
        return True

    def move_task_or_stage_from_board(self, tasks_or_stages):
        for task_or_stage in tasks_or_stages:
            if task_or_stage.position > self.position:
                task_or_stage.position = task_or_stage.position - 1
                task_or_stage.save()

    def move_task_or_stage_from_gantt_chart(self, tasks_or_stages):
        for task_or_stage in tasks_or_stages:
            if task_or_stage.gantt_chart_position > self.gantt_chart_position:
                task_or_stage.gantt_chart_position = task_or_stage.gantt_chart_position - 1
                task_or_stage.save()

    def copy(self, to_stage, new_title=None, checklists=None, labels=None, attachments=None, comments=None):

        if new_title:
            allowed_chars = ''.join((string.ascii_letters, string.digits))
            task_copy_key = ''.join(random.choice(allowed_chars) for _ in range(16))
            copied_task = self.make_clone(attrs={'board_stage': to_stage, 'title': new_title, 'share_key': task_copy_key})
        else:
            allowed_chars = ''.join((string.ascii_letters, string.digits))
            key = ''.join(random.choice(allowed_chars) for _ in range(16))
            copied_task = self.make_clone(attrs={'board_stage': to_stage, 'title': self.title,
                                                 'share_key': key})

        [task_member.copy(copied_task) for task_member in self.task_members.all()]

        if checklists:
            [check_list.copy(copied_task) for check_list in self.checklists.all()]
        if labels:
            for labels_to_copy in self.labels.all():
                copied_task.labels.add(labels_to_copy)
        if attachments:
            [attachment.copy(copied_task) for attachment in self.attachments.all()]
        if comments:
            copied_activity_ids = {}
            activities_with_parent_activity = []
            for activity in self.activities.all():
                copied_activity = activity.make_clone(attrs={'task': copied_task, 'content': activity.content})
                copied_activity_ids[activity.id] = copied_activity.id
                if activity.parent_activity:
                    activities_with_parent_activity.append(copied_activity)

            for activity in activities_with_parent_activity:
                 activity.parent_activity_id = copied_activity_ids[activity.parent_activity_id]
                 activity.save()

        return copied_task

    class Meta:
        """Meta class for Task."""

        ordering = ['position']
        # unique_together = (('title', 'board_stage'),)


class TaskMember(CloneMixin, models.Model):
    """Class representing a Task member."""

    user_id = models.IntegerField(null=False, blank=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='task_members')
    created_at = models.DateField(_('created at'), auto_now_add=True,
                                  null=False, blank=False)
    created_by = models.IntegerField(null=False, blank=False)

    def copy(self, to_task):
        self.make_clone(attrs={'task': to_task})

    class Meta:
        """Meta class for Task Members."""

        unique_together = (('user_id', 'task'),)


class Attachment(CloneMixin, models.Model):
    """Class representing task."""

    name = models.CharField(max_length=48, null=False, blank=False)
    created_at = models.DateTimeField(_('created at'), null=False, blank=False,
                                      auto_now_add=True)
    attached_by = models.IntegerField(null=False, blank=False)
    attachment = models.FileField(upload_to=get_attachments_dynamic_path,
                                  validators=[FileExtensionValidator(
                                      allowed_extensions=['pdf', 'doc', 'jpg', 'jpeg', 'png', 'gif'])])
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='attachments')

    def copy(self, to_task):
        self.make_clone(attrs={'task': to_task, 'name': self.name})

    def __str__(self):
        """
        Attachment name
        :return: name
        """
        return '{}'.format(self.name)

    class Meta:
        """Meta class for Attachment."""
        unique_together = (('name', 'task'),)
        ordering = ['-created_at']


class Checklist(CloneMixin, models.Model):
    """Class representing task."""
    name = models.CharField(max_length=48, null=False, blank=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='checklists')

    def __str__(self):
        """
        Attachment name
        :return: name
        """
        return '{}'.format(self.name)

    def copy(self, to_task):
        copied_check_list = self.make_clone(attrs={'task': to_task, 'name': self.name})
        [ check_list_item.copy(copied_check_list) for check_list_item in self.checklist_items.all()]

    class Meta:
        """Meta class for Check list."""
        unique_together = (('task', 'name'),)


class ChecklistItem(CloneMixin, models.Model):
    """Class representing task."""

    name = models.CharField(max_length=48, null=False, blank=False)
    checklist = models.ForeignKey(Checklist, on_delete=models.CASCADE,
                                  related_name='checklist_items', null=False, blank=False)
    is_completed = models.BooleanField(default=False)
    completed_by = models.IntegerField(null=True, blank=True)
    completed_at = models.DateTimeField(_('completed at'), null=True, blank=True)

    def copy(self, to_checklist):
        self.make_clone(attrs={'checklist': to_checklist, 'name': self.name})

    class Meta:
        """Meta class for Check list item."""
        unique_together = (('name', 'checklist'),)


class Activity(CloneMixin, models.Model):
    """Class representing Board activity"""

    content = models.TextField(max_length=200, null=False, blank=False)
    created_at = models.DateTimeField(_('created at'), auto_now_add=True,
                                      null=False, blank=False)
    last_updated_at = models.DateTimeField(_('last updated at'), auto_now=True,
                                           null=False, blank=False)
    created_by = models.IntegerField(null=False, blank=False)

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='activities')

    parent_activity = models.ForeignKey('Activity', null=True, blank=True,
                                        related_name='child_activities', on_delete=models.CASCADE)
    is_activity = models.BooleanField(null=False, blank=False, default=False)


class TaskDependencyMap(models.Model):
    TYPES = [(0, 'finish-to-start'),
             (1, 'finish-to-finish'),
             (2, 'start-to-start'),
             (3, 'start-to-finish')]

    source = models.ForeignKey(Task, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name='predecessors')
    target = models.ForeignKey(Task, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name='successors')
    type = models.CharField(max_length=2, choices=TYPES, default=0)


from api.signal_receivers import *
