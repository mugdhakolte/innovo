import sys

from datetime import *

from django.db.models import *

from nested_lookup import nested_lookup

from statistics import *
from decimal import *

from .models import *

sys.setrecursionlimit(10**6)


def get_labels(label):
    """
    get all labels
    :param label: label
    :return: data
    """
    data = []
    if not label.start_date:
        label.start_date = date.today()
    if not label.end_date:
        label.end_date = date.today()
    label.save()
    if label.parent_label_id:
        label = get_label_progress(label)
        task_label = {'id': 'label-' + str(label.id),
                      'text': label.name,
                      'start_date': label.start_date,
                      'end_date': label.end_date,
                      "duration": (label.end_date - label.start_date).days,
                      'progress': label.progress,
                      'parent': 'label-' + str(label.parent_label_id.id),  # 0, #
                      'position': label.position}
        data.append(task_label)
        return data
    if label.tasks:
        label = get_label_progress(label)
        task_label = {'id': 'label-' + str(label.id),
                      'text': label.name,
                      'start_date': label.start_date,
                      'end_date': label.end_date,
                      "duration": (label.end_date - label.start_date).days,
                      'parent': 'task-' + str(label.tasks.id),  # 0, #
                      'progress': label.progress,
                      'position': label.position}
        data.append(task_label)
        return data
    else:
        label = get_label_progress(label)
        task_label = {'id': 'label-' + str(label.id),
                      'text': label.name,
                      'start_date': label.start_date,
                      'end_date': label.end_date,
                      "duration": (label.end_date - label.start_date).days,
                      'parent': 0,
                      'progress': label.progress,
                      'position': label.position}
        data.append(task_label)
        return data


def get_label_progress(label):
    data = []
    if label.sub_labels.all():
        for labell in label.sub_labels.all():
            label_datas = get_labels(labell)
            if label_datas:
                for label_data in label_datas:
                    data.append(label_data)
    if label.taskss.all():
        for taskk in label.taskss.all():
            task_datas = get_tasks(taskk)
            if task_datas:
                for task_data in task_datas:
                    data.append(task_data)
    all_progress = nested_lookup('progress', data)
    start_dates = nested_lookup('start_date', data)
    start_date = min(start_dates) if start_dates else label.start_date
    end_dates = nested_lookup('end_date', data)
    end_date = max(end_dates) if end_dates else label.end_date
    progress = round(mean(all_progress), 2) if all_progress else label.progress
    label.end_date = end_date if end_date > label.end_date else label.end_date
    label.start_date = start_date if start_date < label.start_date else label.start_date
    label.progress = progress
    label.save()
    return label


def get_tasks(task):
    """
    Get list of tasks.
    :param task: task.
    :return: data with task list.
    """
    data = []
    if not task.start_date:
        start_date = date.today()
        task.start_date = start_date
        task.save()
    if not task.end_date:
        end_date = date.today()
        task.end_date = end_date
        task.save()
    if not task.due_date:
        task.due_date = date.today()
        task.save()
    if task.parent_task_id and task.display_in_gantt_chart:
        task = get_task_progress(task)
        board = get_task_board(task)
        gantt_chart = {'id': 'task-' + str(task.id),
                       'text': task.title,
                       'start_date': task.start_date,
                       'end_date': task.end_date,
                       "duration": (task.end_date - task.start_date).days,
                       'progress': task.progress,
                       'parent': 'task-' + str(task.parent_task_id.id),
                       'position': task.gantt_chart_position,
                       'board_id': board.id if board else None,
                       'stage_id': task.board_stage.id if task.board_stage else None,
                       'board_name': board.name if board else None,
                       'description': task.description if task.description else None,
                       'is_display_in_dashboard': task.is_display_in_dashboard}
        task_dependency = TaskDependencyMap.objects.filter(Q(source=task.id))
        if task_dependency:
            links = [{"id": int(task_dep.id),
                      "source": "task-" + str(task_dep.source.id),
                      "target": "task-" + str(task_dep.target.id),
                      "type": task_dep.type} for task_dep in task_dependency if task_dep.source and task_dep.target]
            gantt_chart['links'] = links
        data.append(gantt_chart)
        return data
    if task.task_labels and task.display_in_gantt_chart:
        task = get_task_progress(task)
        gantt_chart = {'id': 'task-' + str(task.id),
                       'text': task.title,
                       'start_date': task.start_date,
                       'end_date': task.end_date,
                       "duration": (task.end_date - task.start_date).days,
                       'progress': task.progress,
                       'parent': 'label-' + str(task.task_labels.id),  # 0,  #
                       'position': task.gantt_chart_position,
                       'board_id': task.board_stage.board.id if task.board_stage else None,
                       'stage_id': task.board_stage.id,
                       'board_name': task.board_stage.board.name if task.board_stage else None,
                       'description': task.description if task.description else None,
                       'is_display_in_dashboard': task.is_display_in_dashboard
                       }
        task_dependency = TaskDependencyMap.objects.filter(Q(source=task.id))
        if task_dependency:
            links = [{"id": int(task_dep.id),
                      "source": "task-" + str(task_dep.source.id),
                      "target": "task-" + str(task_dep.target.id),
                      "type": task_dep.type} for task_dep in task_dependency if task_dep.source and task_dep.target]
            gantt_chart['links'] = links
        data.append(gantt_chart)
        return data
    if not task.task_labels and not task.parent_task_id:
        task = get_task_progress(task)
        gantt_chart = {'id': 'task-' + str(task.id),
                       'text': task.title,
                       'start_date': task.start_date,
                       'end_date': task.end_date,
                       "duration": (task.end_date - task.start_date).days,
                       'progress': task.progress,
                       'parent': 0,
                       'position': task.gantt_chart_position,
                       'board_id': task.board_stage.board.id if task.board_stage else None,
                       'stage_id': task.board_stage.id,
                       'board_name': task.board_stage.board.name if task.board_stage else None,
                       'description': task.description if task.description else None,
                       'is_display_in_dashboard': task.is_display_in_dashboard
                       }
        task_dependency = TaskDependencyMap.objects.filter(Q(source=task.id))
        if task_dependency:
            links = [{"id": int(task_dep.id),
                      "source": "task-" + str(task_dep.source.id),
                      "target": "task-" + str(task_dep.target.id),
                      "type": task_dep.type} for task_dep in task_dependency if task_dep.source and task_dep.target]
            gantt_chart['links'] = links
        data.append(gantt_chart)
        return data


def get_task_board(task):
    board = None
    if task.board_stage:
        if task.board_stage.board:
            board = task.board_stage.board
        return board
    if task.parent_task_id:
        if task.parent_task_id.board_stage:
            if task.parent_task_id.board_stage.board:
                board = task.parent_task_id.board_stage.board
        return board
    else:
        return board


def get_task_progress(task):
    data = []
    if task.sub_tasks.all():
        for taskk in task.sub_tasks.all():
            task_datas = get_tasks(taskk)
            if task_datas:
                for task_data in task_datas:
                    data.append(task_data)
    if task.gantt_chart_labels.all():
        for labell in task.gantt_chart_labels.all():
            label_datas = get_labels(labell)
            if label_datas:
                for label_data in label_datas:
                    data.append(label_data)
    all_progress = nested_lookup('progress', data)
    start_dates = nested_lookup('start_date', data)
    start_date = min(start_dates) if start_dates else task.start_date
    end_dates = nested_lookup('end_date', data)
    end_date = max(end_dates) if end_dates else task.end_date
    progress = round(mean(all_progress) if all_progress else task.progress, 2)
    task.progress = progress
    task.end_date = end_date if end_date > task.end_date else task.end_date
    task.start_date = start_date if start_date < task.start_date else task.start_date
    task.save()
    return task


def get_stages(stage):
    """
    get list of stages
    :param stage: stage
    :return: data
    """
    data = []
    start_date = stage.start_date
    end_date = stage.end_date
    progress_list = [stage.progress]
    if not stage.start_date and not stage.end_date:
        end_date = Task.objects.filter(board_stage=stage.id).aggregate(Max('end_date')).get('end_date__max')
        if not end_date:
            end_date = date.today()
        start_date = stage.created_at.date()
    if stage.tasks:
        progress = stage.tasks.filter(board_stage=stage.id).aggregate(Avg('progress')).get('progress__avg')
        if progress:
            progress_list.append(progress)
        for taskk in stage.tasks.all():
            task_datas = get_tasks(taskk)
            if task_datas:
                for task_data in task_datas:
                    data.append(task_data)
    if stage.gantt_chart_labels:
        for labell in stage.gantt_chart_labels.all():
            for label_data in get_labels(labell):
                data.append(label_data)
    if data:
        progress = mean(list(nested_lookup('progress', data))) if list(nested_lookup('progress', data)) else progress
        stage.progress = progress
    if stage.board_stage_label:
        progress = sum(progress_list) / len(progress_list)
        gantt_chart = {'id': 'stage-' + str(stage.id),
                       'text': stage.stage.name,
                       'start_date': start_date,
                       'end_date': end_date,
                       'duration': (end_date - start_date).days,
                       'open': True,
                       'parent': 'label-' + str(stage.board_stage_label.id),
                       'position': stage.gantt_chart_position,
                       'progress': progress, }
        data.append(gantt_chart)
        if progress:
            stage.progress = progress
            stage.save()
    else:
        start_date = stage.start_date
        end_date = stage.end_date
        if not start_date:
            start_date = stage.created_at.date()
            stage.start_date = start_date
            stage.save()
        if not end_date:
            end_date = date.today()
            stage.end_date = date.today()
        stage.save()
        gantt_chart = {'id': 'stage-' + str(stage.id),
                       'text': stage.stage.name,
                       'start_date': start_date if start_date else date.today(),
                       'end_date': end_date if end_date else date.today(),
                       'duration': (end_date - start_date).days,
                       'open': True,
                       'position': stage.gantt_chart_position,
                       'progress': progress, }
        data.append(gantt_chart)
    return data
