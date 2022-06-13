import ast
import json
import random
import string
import datetime

from itertools import chain

from datetime import timedelta, date

from django.db.models import Max, Q
from django.shortcuts import get_object_or_404

from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

from api.models import *
from api.move_task_utils import *
from api.inter_service_communicator import *


class CategorySerializer(serializers.ModelSerializer):
    """Category model serializer class for Category."""

    class Meta:
        """Meta class for Category model serializer."""

        model = Category
        fields = "__all__"


class ChecklistItemSerializer(serializers.ModelSerializer):
    """ChecklistItem model serializer class for Checklist."""

    class Meta:
        """Meta class for ChecklistItem model serializer."""
        model = ChecklistItem
        fields = "__all__"


class ChecklistSerializer(serializers.ModelSerializer):
    """Checklist model serializer class for Checklist."""

    checklist_items = ChecklistItemSerializer(many=True, read_only=True)

    class Meta:
        """Meta class for Checklist model serializer."""
        model = Checklist
        fields = "__all__"


class ChecklistDetailSerializer(serializers.ModelSerializer):
    """Checklist model serializer class for Checklist."""

    checklist_items = ChecklistItemSerializer(many=True, read_only=True)

    class Meta:
        """Meta class for Checklist model serializer."""
        model = Checklist
        fields = "__all__"
        depth = 2


class LabelSerializer(serializers.ModelSerializer):
    """Label model serializer class for Label."""

    class Meta:
        """Meta class for Label model serializer."""

        model = Label
        fields = "__all__"


class BoardMemberSerializer(serializers.ModelSerializer):

    created_by = serializers.IntegerField(required=False)

    def create(self, validated_data):
        if 'created_by' not in validated_data.keys():
            request = self.context['request']
            created_by = ast.literal_eval(request.innovo_user).get('id')
            validated_data['created_by'] = created_by
        return super(BoardMemberSerializer, self).create(validated_data)

    class Meta:
        model = BoardMember
        fields = "__all__"


class BoardSerializer(serializers.ModelSerializer):
    is_favourite = serializers.SerializerMethodField()
    number_of_tasks = serializers.SerializerMethodField()
    created_by = serializers.IntegerField(required=False)

    def get_number_of_tasks(self, instance):
        return sum([stage.tasks.count() for stage in instance.board_stage_maps.all()])

    def get_is_favourite(self, instance):
        request = self.context['request']
        innovo_user = ast.literal_eval(request.innovo_user)
        favourite_boards = innovo_user.get('favourite_boards')
        return str(instance.id) in favourite_boards

    def create(self, validated_data):
        request = self.context['request']
        user = ast.literal_eval(request.innovo_user)
        created_by = user.get('id')
        validated_data['created_by'] = created_by
        response = super(BoardSerializer, self).create(validated_data)
        if not user.get('is_superuser'):
            data = {'created_by': created_by,
                    'user_id': created_by,
                    'board': response.id
                    }
            serializer = BoardMemberSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
        return response

    class Meta:
        model = Board
        exclude = ['stages']


class BoardDetailSerializer(serializers.ModelSerializer):

    board_members = BoardMemberSerializer(many=True, read_only=True)
    labels = LabelSerializer(many=True, read_only=True)
    number_of_tasks = serializers.SerializerMethodField()
    board_stages = serializers.SerializerMethodField(read_only=True)
    is_favourite = serializers.SerializerMethodField()

    def get_number_of_tasks(self, instance):
        return sum([stage.tasks.count() for stage in instance.board_stage_maps.all()])

    def get_board_stages(self, instance):
        return BoardStageSerializer(instance=instance.board_stage_maps.all(), many=True).data

    def get_is_favourite(self, instance):
        request = self.context['request']
        innovo_user = ast.literal_eval(request.innovo_user)
        favourite_boards = innovo_user.get('favourite_boards')
        return str(instance.id) in favourite_boards

    class Meta:
        """Meta class for Board model serializer."""

        model = Board
        exclude = ('stages',)
        depth=2


class BoardLabelDetailSerializer(serializers.ModelSerializer):
    """
    board detail with label filtered tasks
    """

    board_members = BoardMemberSerializer(many=True, read_only=True)
    labels = LabelSerializer(many=True, read_only=True)
    number_of_tasks = serializers.SerializerMethodField()
    board_stages = serializers.SerializerMethodField(read_only=True)
    is_favourite = serializers.SerializerMethodField()


    def get_number_of_tasks(self, instance):
        return sum([stage.tasks.count() for stage in instance.board_stage_maps.all()])

    def get_board_stages(self, instance):
        return BoardStageLabelSerializer(instance=instance.board_stage_maps.all(),
                                         context=self.context,
                                         many=True).data


    def get_is_favourite(self, instance):
        request = self.context['request']
        innovo_user = ast.literal_eval(request.innovo_user)
        favourite_boards = innovo_user.get('favourite_boards')
        return str(instance.id) in favourite_boards

    class Meta:
        """Meta class for Board model serializer."""
        model = Board
        exclude = ('stages',)
        depth=2


class BoardStageLabelSerializer(serializers.ModelSerializer):
    """
    Board stages with task filtered using label.
    """
    tasks = serializers.SerializerMethodField(read_only=True, allow_null=True)
    text = serializers.SerializerMethodField(read_only=True)


    class Meta:
        model = BoardStageMap
        fields = '__all__'
        depth=2

    def get_tasks(self, instance):
        """
        filter board tasks
        :param instance: label ids, title text
        :return: filtered tasks
        """
        request = self.context['request']
        # label_ids = [label for label in request.data.get('label_ids') if label]
        # title_text = request.data.get('text_search')
        try:
            label_ids = [label for label in request.data.getlist('label_ids') if label]
        except AttributeError as ae:
            label_ids = [label for label in request.data.get('label_ids') if label]
        title_text = request.data.get('text_search')

        if title_text and label_ids:
            tasks = instance.tasks.filter(is_display_in_board=True,
                                          title__icontains=title_text,
                                          labels__in=label_ids
                                          )
            serializer = TaskSerializer(tasks, many=True)
            return serializer.data
        elif label_ids:
            tasks = instance.tasks.filter(is_display_in_board=True,
                                          labels__in=label_ids
                                          )
            serializer = TaskSerializer(tasks, many=True)
            return serializer.data
        elif title_text:
            tasks = instance.tasks.filter(is_display_in_board=True,
                                          title__icontains=title_text,
                                          )
            serializer = TaskSerializer(tasks, many=True)
            return serializer.data
        else:
            tasks = instance.tasks.filter(is_display_in_board=True
                                          )
            serializer = TaskSerializer(tasks, many=True)
            return serializer.data

    def get_text(self, instance):
        return instance.stage.name


class GanttBoardDetailSerializer(serializers.ModelSerializer):

    board_members = BoardMemberSerializer(many=True, read_only=True)
    board_stages = serializers.SerializerMethodField(read_only=True)

    def get_board_stages(self, instance):
        return BoardStageSerializer(instance=instance.board_stage_maps.all(), many=True).data

    class Meta:
        """Meta class for Board model serializer."""

        model = Board
        exclude = ('stages',)
        depth=2


class AttachmentSerializer(serializers.ModelSerializer):

    attached_by = serializers.IntegerField(required=False)

    def create(self, validated_data):
        request = self.context['request']
        created_by = ast.literal_eval(request.innovo_user).get('id')
        validated_data['attached_by'] = created_by
        return super(AttachmentSerializer, self).create(validated_data)

    class Meta:
        model = Attachment
        fields = "__all__"


class ActivitySerializer(serializers.ModelSerializer):

    replies = serializers.SerializerMethodField(read_only=True)
    created_by = serializers.IntegerField(required=False)

    def get_replies(self, activity):
        serializer = ActivitySerializer(instance=activity.child_activities.all(), many=True)
        return serializer.data

    def create(self, validated_data):
        request = self.context['request']
        created_by = ast.literal_eval(request.innovo_user).get('id')
        validated_data['created_by'] = created_by
        return super(ActivitySerializer, self).create(validated_data)

    class Meta:
        model = Activity
        fields = "__all__"


class TaskMemberSerializer(serializers.ModelSerializer):

    created_by = serializers.IntegerField(required=False)
    
    def create(self, validated_data):
        if 'created_by' not in validated_data.keys():
            request = self.context['request']
            created_by = ast.literal_eval(request.innovo_user).get('id')
            validated_data['created_by'] = created_by
        return super(TaskMemberSerializer, self).create(validated_data)

    class Meta:
        model = TaskMember
        fields = "__all__"


class MoveTaskSerializer(serializers.Serializer):

    position = serializers.IntegerField(required=True)
    board_stage = serializers.PrimaryKeyRelatedField(queryset=BoardStageMap.objects)


class CopyTaskSerializer(serializers.Serializer):

    title = serializers.CharField(required=True)
    board_stage = serializers.PrimaryKeyRelatedField(queryset=BoardStageMap.objects)
    copy_checklists = serializers.BooleanField(default=False)
    copy_labels = serializers.BooleanField(default=False)
    copy_attchments = serializers.BooleanField(default=False)
    # copy_comments = serializers.BooleanField(default=False)
    position = serializers.IntegerField(required=True)

    class Meta :
        validators = [
            UniqueTogetherValidator(
                queryset=Task.objects.all(),
                fields=['title', 'board_stage']
            )
        ]


class TaskLabelSerializer(serializers.Serializer):

    label_id = serializers.PrimaryKeyRelatedField(queryset=Label.objects)


class TaskSerializer(serializers.ModelSerializer):

    number_of_activities = serializers.SerializerMethodField()
    created_by = serializers.IntegerField(required=False)

    def _update_validated_data_with_shair_key_and_created_by(self, validated_data):
        allowed_chars = ''.join((string.ascii_letters, string.digits))
        key = ''.join(random.choice(allowed_chars) for _ in range(16))
        validated_data['share_key'] = key
        return validated_data

    def update(self, instance, validated_data):
        pay_load = {}
        product = ProcurementService()
        request = self.context['request']
        headers = {"Authorization": request.headers.get('Authorization')}
        project_task = self._get_project_task(instance.board_stage,
                                              headers={"Authorization": request.headers.get('Authorization')})
        if request.data.get('selectedStage'):
            board_stage_obj = request.data.get('selectedStage').get('id')
            requested_stage = get_object_or_404(BoardStageMap, id=board_stage_obj)
            if requested_stage.id == instance.board_stage_id:
                pass
            else:
                old_stage = instance.board_stage
                old_stage_tasks = old_stage.tasks.all().exclude(id=instance.id)
                max_end_date = old_stage.tasks.all().exclude(id=instance.id).aggregate(Max('end_date'))\
                    .get('end_date__max')
                tasks = old_stage.tasks.filter(end_date=max_end_date).exclude(id=instance.id)
                for task in tasks:
                    if task.display_in_gantt_chart:
                        task.is_critical_path_task = True
                        task.save()
                instance.move_task_or_stage_from_board(old_stage_tasks)
                max_position = requested_stage.tasks.all().aggregate(Max('position')).get('position__max')
                critical_path_tasks(requested_stage, instance,
                                    project_task=project_task,
                                    headers=headers)
                instance.board_stage = requested_stage
                instance.position = max_position + 1 if max_position else 1
                instance.save()
        if request.data.get('start_date'):
            start_date = datetime.datetime.strptime(request.data.get('start_date'), '%Y-%m-%d') if \
                request.data.get('start_date') else instance.start_date
            validated_data['start_date'] = start_date.date()
        if request.data.get('end_date'):
            end_date = datetime.datetime.strptime(request.data.get('end_date'), '%Y-%m-%d') if \
                request.data.get('end_date') else instance.end_date
            instance.end_date = end_date.date()
            instance.save()
            validated_data['end_date'] = end_date.date()
        if request.data.get('duration'):
            end_date = validated_data['start_date'] + timedelta(int(request.data.get('duration')))
            validated_data['end_date'] = end_date

        if validated_data.get('display_in_gantt_chart'):
            project_id = instance.board_stage.board.project_id
            boards = Board.objects.filter(project_id=project_id)
            gant_position = task_gantchart_position(boards)
            instance.display_in_gantt_chart = True
            instance.gantt_chart_position = gant_position+1
            instance.save()
            self._update_stage_tasks(instance.board_stage, project_task, headers)
        if validated_data.get('display_in_gantt_chart') == False:
            self._update_child_tasks(instance, project_task, headers)
        if request.data.get('end_date') or validated_data.get('display_in_gantt_chart') or not validated_data.get('display_in_gantt_chart'):
            critical_path_tasks(instance.board_stage,
                                instance,
                                project_task=project_task,
                                headers=headers)
        if instance.procurement_id:
            if validated_data.get('start_date'):
                pay_load['purchase_order_date'] = str(validated_data.get('start_date'))
            if validated_data.get('end_date'):
                pay_load['estimated_arrival_date'] = str(validated_data.get('end_date'))
            if validated_data.get('title'):
                pay_load['name'] = validated_data.get('title')
            if validated_data.get('description'):
                pay_load['description'] = validated_data.get('description')
            if instance.is_critical_path_task:
                pay_load['is_critical_path_item'] = True
            else:
                pay_load['is_critical_path_item'] = False
            try:
                product.update_product(pay_load,
                                       product_id=instance.procurement_id,
                                       headers=headers)
                return super(TaskSerializer, self).update(instance, validated_data)
            except Exception as e:
                return serializers.ValidationError("Please try again")
        return super(TaskSerializer, self).update(instance, validated_data)

    def _get_project_task(self, board_stage, headers):
        project_id = board_stage.board.project_id
        response_data = get_project_details(project_id, headers)
        task_name = response_data.get('name') + "_" + str(response_data.get('id'))
        project_task = Task.objects.filter(title=response_data.get('name'), task_type=task_name).first()
        return project_task

    def _update_child_tasks(self, task, project_task, headers):
        task.display_in_gantt_chart = False
        task.is_critical_path_task = False
        task.is_display_in_dashboard = False
        task.parent_task_id = None
        task.save()
        if task.procurement_id:
            try:
                update_product_from_board_gant_chart(task, headers, )
            except Exception as e:
                pass
        prdecessor_cretical_task(task, headers)
        tasks = task.sub_tasks.all()
        if tasks:
            for child_task in tasks:
                self._update_child_tasks(child_task, project_task, headers)
        else:
            return True

    def _update_stage_tasks(self, board_stage, project_task, headers):
        '''
        Update stage tasks.
        '''
        max_end_date = board_stage.tasks.filter(is_display_in_board=True).exclude(id=project_task.id).aggregate(Max('end_date')).get('end_date__max')
        tasks = board_stage.tasks.filter(display_in_gantt_chart=True, end_date=max_end_date).exclude(id=project_task.id)
        for task in tasks:
            if task.end_date == max_end_date and task.display_in_gantt_chart:
                if task.is_critical_path_task:
                    pass
                else:
                    task.is_critical_path_task = True
                    task.save()
                    update_child_tasks_true(task, headers)
                    prdecessor_cretical_task_true(task, headers)


    def create(self, validated_data):
        request = self.context['request']
        created_by = ast.literal_eval(request.innovo_user).get('id')
        validated_data['created_by'] = created_by
        headers = {"Authorization": request.headers.get('Authorization')}
        allowed_chars = ''.join((string.ascii_letters, string.digits))
        key = ''.join(random.choice(allowed_chars) for _ in range(16))
        validated_data['share_key'] = key

        board_stage = validated_data.get('board_stage')
        project_task = self._get_project_task(board_stage,
                                              headers={"Authorization": request.headers.get('Authorization')})
        tasks_max_position = board_stage.tasks.select_related('position', 'is_display_in_board')\
            .filter(is_display_in_board=True).aggregate(Max('position')).get('position__max')
        project_id = board_stage.board.project_id
        max_ganttchart_position = self._get_max_ganttchart_position(project_id, request)
        validated_data['gantt_chart_position'] = max_ganttchart_position+1 if max_ganttchart_position else 1
        validated_data['position'] = tasks_max_position + 1 if tasks_max_position else 1
        validated_data['display_in_gantt_chart'] = True
        validated_data['is_display_in_board'] = True
        max_end_date = None
        try:
            max_end_date = board_stage.tasks.all().exclude(id=project_task.id).aggregate(Max('end_date')).get('end_date__max')
        except Exception as e:
            max_end_date = board_stage.tasks.all().aggregate(Max('end_date')).get('end_date__max')
        # max_end_date = board_stage.tasks.all().exclude(id=project_task.id).aggregate(Max('end_date')).get(
        #     'end_date__max')
        if not max_end_date:
            validated_data['is_critical_path_task'] = True
        else:
            if validated_data.get('end_date'):
                if validated_data.get('end_date') == max_end_date:
                    validated_data['is_critical_path_task'] = True
                if validated_data.get('end_date') > max_end_date:
                    self._change_critical_task(board_stage, max_end_date, project_task, headers)
                    validated_data['is_critical_path_task'] = True
            else:
                if date.today() == max_end_date:
                    validated_data['is_critical_path_task'] = True
                if date.today() > max_end_date:
                    self._change_critical_task(board_stage, max_end_date, project_task, headers)
                    validated_data['is_critical_path_task'] = True
                validated_data['end_date'] = date.today()
        if not validated_data.get('start_date'):
            validated_data['start_date'] = date.today()
        if not validated_data.get('due_date'):
            validated_data['due_date'] = validated_data['end_date']
        return super(TaskSerializer, self).create(validated_data)

    def _get_max_ganttchart_position(self, project_id, request):
        max_position = 0
        boards = Board.objects.filter(project_id=project_id)
        project_task = None
        response_data = get_project_details(project_id,{'Authorization': request.headers.get('Authorization')})
        if response_data:
            task_name = response_data.get('name') + "_" + str(response_data.get('id'))
            project_task = Task.objects.filter(title=response_data.get('name'), task_type=task_name).first()
        if boards:
            max_position_li = []
            stages = [stage for board in boards for stage in board.board_stage_maps.all() if stage]
            for stage in stages:
                gantt_chart_position = stage.tasks.all().aggregate(Max('gantt_chart_position')).get(
                    'gantt_chart_position__max')
                if gantt_chart_position:
                    max_position_li.append(gantt_chart_position)
            for board in boards:
                if project_task:
                    gantt_chart_position = board.gantt_chart_labels.filter(tasks=project_task.id)\
                        .aggregate(Max('position')).get('position__max')
                    if gantt_chart_position:
                        max_position_li.append(gantt_chart_position)
            if max_position_li:
                max_position = max(max_position_li)
        return max_position

    def _change_critical_task(self, board_stage, max_date, project_task, headers):
        tasks = board_stage.tasks.filter(end_date=max_date)
        for task in tasks:
            if task.parent_task_id and task.parent_task_id.is_critical_path_task and project_task.id != task.parent_task_id_id:
                task.is_critical_path_task = True
                task.save()
                update_child_tasks_true(task, headers)
                prdecessor_cretical_task_true(task, headers)
            elif task.successors.all():
                for successor in task.successors.all():
                    if successor.source.is_critical_path_task:
                        task.is_critical_path_task = True
                        task.save()
                        update_child_tasks_true(task, headers)
                        prdecessor_cretical_task_true(task, headers)
                        break
            else:
                task.is_critical_path_task = False
                task.save()
                update_child_tasks_false(task, headers)
                prdecessor_cretical_task(task, headers)
            if task.procurement_id:
                update_product_from_board_gant_chart(task, headers)

    def get_number_of_activities(self, instance):
        if instance.activities:
            return instance.activities.count()
        else:
            return 0

    class Meta:
        model = Task
        fields = "__all__"


class TaskDetailSerializer(serializers.ModelSerializer):

    task_members = TaskMemberSerializer(many=True, read_only=True)

    attachments = AttachmentSerializer(many=True, read_only=True)

    checklists = ChecklistSerializer(many=True, read_only=True)

    activities = serializers.SerializerMethodField()

    def get_activities(self, instance):
        serializer = ActivitySerializer(instance=instance.activities.filter(parent_activity__isnull=True), many=True)
        return serializer.data

    class Meta:
        model = Task
        fields = "__all__"
        depth = 2


class MoveBoardStageSerializer(serializers.Serializer):

    position = serializers.IntegerField(required=True)


class CopyBoardStageSerializer(serializers.Serializer):

    stage_name = serializers.CharField(required=True)
    position = serializers.IntegerField(required=True)


class CreateBoardStageSerializer(serializers.Serializer):

    stage_name = serializers.CharField(required=True)
    board_id = serializers.PrimaryKeyRelatedField(required=True, queryset=Board.objects)

    def validate(self, data):
        board_id = data['board_id']
        stage_name = data['stage_name']
        try:
            BoardStageMap.objects.get(board_id=board_id, stage__name=stage_name)
            raise serializers.ValidationError('Stage with this name already exist')
        except BoardStageMap.DoesNotExist as e:
            return data


class BoardStageSerializer(serializers.ModelSerializer):
    # tasks = TaskSerializer(many=True, read_only=True)
    text = serializers.SerializerMethodField(read_only=True)
    tasks = serializers.SerializerMethodField(read_only=True, allow_null=True)


    class Meta:
        model = BoardStageMap
        fields = '__all__'
        depth=2

    def get_tasks(self, instance):
        tasks = Task.objects.filter(board_stage=instance.id, is_display_in_board=True)
        serializer = TaskSerializer(tasks, many=True)
        return serializer.data

    def get_text(self, instance):
        return instance.stage.name


class TaskDependencyMapSerializer(serializers.ModelSerializer):
    delay = serializers.IntegerField(read_only=True)
    source_delay = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = TaskDependencyMap
        fields ="__all__"

    def get_source_delay(self, instance):
        return instance.source.delay

    def validate(self, attrs):
        successor_task = attrs.get('source')
        predecessor_task = attrs.get('target')
        if attrs.get('type') == 0:
            """finish to start: predecessor must finish successor can start"""
            if successor_task.start_date > predecessor_task.end_date:
                return attrs
            else:
                raise serializers.ValidationError("predecessor end date must be after successor start date.")
        elif attrs.get('type') == 1:
            """finish to finish :  predecessor must finish before successor can start"""
            if predecessor_task.end_date < successor_task.end_date:
                return attrs
            else:
                raise serializers.ValidationError("Predecessor end date must before successor end date.")
        elif attrs.get('type') == 2:
            """start to start : Predecessor  must start before successor can start"""
            if predecessor_task.start_date < successor_task.start_date:
                return attrs
            else:
                raise serializers.ValidationError("Predecessor start date must before successor start date.")
        else:
            """start to finish :Predecessor must start before successor can finish"""
            if predecessor_task.start_date < successor_task.end_date:
                return attrs
            else:
                raise serializers.ValidationError("Predecessor start date must before successor finish date.")



class GanttChartTaskDependencyMapSerializer(serializers.ModelSerializer):

    class Meta:
        model = TaskDependencyMap
        fields ="__all__"


class GanttChartLableSerializer(serializers.ModelSerializer):

    class Meta:
        model = GanttChartLable
        fields = '__all__'


class GanttTaskSerializer(serializers.ModelSerializer):

    class Meta:
        model = Task
        fields = '__all__'


class MoveLabelTaskSerializer(serializers.Serializer):
    position = serializers.IntegerField(required=True)
    label_id = serializers.PrimaryKeyRelatedField(queryset=GanttChartLable.objects)


class MoveParentTaskSerializer(serializers.Serializer):
    position = serializers.IntegerField(required=True)
    parent_task_id = serializers.PrimaryKeyRelatedField(queryset=Task.objects)


class MoveGanttChartStageSerializer(serializers.Serializer):
    position = serializers.IntegerField(required=True)
    label_id = serializers.IntegerField(required=False)


class MoveGanttChartLabelSerializer(serializers.Serializer):
    position = serializers.IntegerField(required=True)
    stage_id = serializers.IntegerField(required=False)
    tasks_id = serializers.IntegerField(required=False)
    parent_label_id = serializers.IntegerField(required=False)