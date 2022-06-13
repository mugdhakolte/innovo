import datetime
from datetime import timedelta, date

from django.db.models import *

from rest_framework import status
from rest_framework.response import Response

from api.models import *
from api.inter_service_communicator import *

PRODUCT = ProcurementService()

def from_task_tasks_gantt_chart_position(task_to_move):
    if task_to_move.parent_task_id:
        tasks = task_to_move.parent_task_id.sub_tasks.all().exclude(id=task_to_move.id)
        labels = task_to_move.parent_task_id.gantt_chart_labels.all()
        task_to_move_gantt_position = task_to_move.gantt_chart_position
        for task in tasks:
            if task.gantt_chart_position > task_to_move_gantt_position:
                task.gantt_chart_position = task.gantt_chart_position - 1
                task.save()
        for label in labels:
            if label.position > task_to_move_gantt_position:
                label.position = label.position - 1
                label.save()


def to_gantt_tasks_new_task_position(new_position, requested_task):
    tasks = requested_task.sub_tasks.all()
    labels = requested_task.gantt_chart_labels.all()
    for task in tasks:
        if task.gantt_chart_position >= new_position:
            task.gantt_chart_position = task.gantt_chart_position + 1
            task.save()
    for label in labels:
        if label.position >= new_position:
            label.position = label.position + 1
            label.save()


def move_task_from_label(task_to_move):
    if task_to_move.task_labels:
        tasks = task_to_move.task_labels.taskss.all().exclude(id=task_to_move.id)
        labels = task_to_move.task_labels.sub_labels.all()
        task_to_move_gantt_position = task_to_move.gantt_chart_position
        for task in tasks:
            if task.gantt_chart_position > task_to_move_gantt_position:
                task.gantt_chart_position = task.gantt_chart_position - 1
                task.save()
        for label in labels:
            if label.position > task_to_move_gantt_position:
                label.position = label.position - 1
                label.save()


def move_task_to_label(new_position, label_to_move):
    new_label_tasks = Task.objects.filter(task_labels=label_to_move)
    new_label_stages = BoardStageMap.objects.filter(board_stage_label=label_to_move)
    for task in new_label_tasks:
        if task.gantt_chart_position >= new_position:
            task.gantt_chart_position = task.gantt_chart_position + 1
            task.save()
    for stage in new_label_stages:
        if stage.gantt_chart_position >= new_position:
            stage.gantt_chart_position = stage.gantt_chart_position + 1
            stage.save()


def from_stage_tasks_gantt_chart_position(task_to_move):
    """
    change position of task in stage.
    """
    old_stage_tasks = Task.objects.filter(board_stage=task_to_move.board_stage_id,
                                          display_in_gantt_chart=True).exclude(id=task_to_move.id)
    if task_to_move.board_stage:
        labels = task_to_move.board_stage.gantt_chart_labels.all()
    else:
        labels = task_to_move.gantt_chart_labels.all()
    task_to_move_gantt_position = task_to_move.gantt_chart_position
    for label in labels:
        if label.position > task_to_move_gantt_position:
            label.position = label.position - 1
            label.save()
    for task in old_stage_tasks:
        if task.gantt_chart_position > task_to_move_gantt_position:
            task.gantt_chart_position = task.gantt_chart_position - 1
            task.save()


def to_gantt_tasks_new_stage_position(new_position, board_stage_request):
    new_stage_tasks = Task.objects.filter(board_stage=board_stage_request,
                                          display_in_gantt_chart=True)
    labels = GanttChartLable.objects.filter(stages=board_stage_request)
    for label in labels:
        if label.position >= new_position:
            label.position = label.position + 1
            label.save()
    for task in new_stage_tasks:
        if task.gantt_chart_position >= new_position:
            task.gantt_chart_position = task.gantt_chart_position + 1
            task.save()
    return True


def check_task_board(task):
    """
    return baord object.
    """
    if hasattr(task, 'board_stage') and task.board_stage:
        return task.board_stage.board
    if hasattr(task, 'parent_task_id') and task.parent_task_id:
        if task.parent_task_id.board_stage:
            return task.parent_task_id.board_stage.board
        else:
            return check_task_board_stage(task.parent_task_id)
    if hasattr(task, 'task_labels') and task.task_labels:
        if task.task_labels.board:
            return task.task_labels.board
        else:
            return check_task_board_stage(task.task_labels)


def critical_path_tasks(board_stage_obj, task_to_move, project_task=None, headers=None):
    """critical task assign"""
    task_end_date = task_to_move.end_date
    max_end_date = board_stage_obj.tasks.filter(is_display_in_board=True).exclude(id__in=[task_to_move.id,project_task.id]).aggregate(Max('end_date')).get('end_date__max')
    tasks = board_stage_obj.tasks.filter(display_in_gantt_chart=True, end_date=max_end_date).exclude(id__in=[task_to_move.id,project_task.id] )
    if max_end_date:
        if task_end_date < max_end_date:
            if not task_to_move.display_in_gantt_chart:
                for task in tasks:
                    if task.end_date == max_end_date and task.display_in_gantt_chart:
                        if not task.is_critical_path_task:
                            task.is_critical_path_task=True
                            task.save()
                            update_child_tasks_true(task_to_move, headers)
                            prdecessor_cretical_task_true(task_to_move, headers)
                            if task.procurement_id:
                                try:
                                    update_product_from_board_gant_chart(task, headers, )
                                except Exception as e:
                                    pass
                return task_to_move
            if task_to_move.display_in_gantt_chart and task_to_move.successors.filter(target=task_to_move.id):
                for successor in task_to_move.successors.filter(target=task_to_move.id):
                    if successor.source.is_critical_path_task:
                        if task_to_move.is_critical_path_task:
                            pass
                        else:
                            if task_to_move.display_in_gantt_chart:
                                task_to_move.is_critical_path_task = True
                                task_to_move.save()
                                update_child_tasks_true(task_to_move, headers)
                                prdecessor_cretical_task_true(task_to_move, headers)
                                break
            elif task_to_move.display_in_gantt_chart and task_to_move.parent_task_id and task_to_move.parent_task_id.is_critical_path_task \
                    and project_task.id != task_to_move.parent_task_id_id:
                if task_to_move.is_critical_path_task:
                    pass
                else:
                    if task_to_move.display_in_gantt_chart:
                        task_to_move.is_critical_path_task = True
                        task_to_move.save()
                        update_child_tasks_true(task_to_move, headers)
                        prdecessor_cretical_task_true(task_to_move, headers)
            else:
                counter_var = None
                if task_to_move.display_in_gantt_chart and task_to_move.successors.filter(target=task_to_move.id): #3[0].source.id
                    for successor in task_to_move.successors.filter(target=task_to_move.id):
                        if successor.source.is_critical_path_task:
                            counter_var = True
                            if task_to_move.is_is_critical_path_task:
                                pass
                            else:
                                if task_to_move.display_in_gantt_chart:
                                    task_to_move.is_is_critical_path_task=True
                                    task_to_move.save()
                                    update_child_tasks_true(task_to_move, headers)
                                    prdecessor_cretical_task_true(task_to_move, headers)
                                    break
                if not counter_var:
                    task_to_move.is_critical_path_task = False
                    task_to_move.save()
                    update_child_tasks_false(task_to_move, headers)
                    prdecessor_cretical_task(task_to_move, headers)
            if task_to_move.procurement_id:
                try:
                    update_product_from_board_gant_chart(task_to_move, headers, )
                except Exception as e:
                    pass
            for task in tasks:
                if task.end_date == max_end_date and task.display_in_gantt_chart:
                    if task.is_critical_path_task:
                        pass
                    else:
                        if task.display_in_gantt_chart:
                            task.is_critical_path_task = True
                            task.save()
                            update_child_tasks_true(task, headers)
                            prdecessor_cretical_task_true(task, headers)
                            if task.procurement_id:
                                try:
                                    update_product_from_board_gant_chart(task, headers, )
                                except Exception as e:
                                    pass
            return task_to_move
        if task_end_date == max_end_date:
            if task_to_move.display_in_gantt_chart:
                if task_to_move.is_critical_path_task:
                    pass
                else:
                    if task_to_move.display_in_gantt_chart:
                        task_to_move.is_critical_path_task = True
                        task_to_move.save()
                        update_child_tasks_true(task_to_move, headers)
                        prdecessor_cretical_task_true(task_to_move, headers)
                        if task_to_move.procurement_id:
                            try:
                                update_product_from_board_gant_chart(task_to_move, headers, )
                            except Exception as e:
                                pass
            return task_to_move
        if task_end_date > max_end_date:
            if task_to_move.display_in_gantt_chart:
                if task_to_move.is_critical_path_task:
                    pass
                else:
                    if task_to_move.display_in_gantt_chart:
                        task_to_move.is_critical_path_task = True
                        task_to_move.save()
                        update_child_tasks_true(task_to_move, headers)
                        prdecessor_cretical_task_true(task_to_move, headers)
                        if task_to_move.procurement_id:
                            try:
                                update_product_from_board_gant_chart(task_to_move, headers)
                            except Exception as e:
                                pass
            for task in tasks:
                if task.parent_task_id and task.parent_task_id.is_critical_path_task \
                        and project_task.id != task.parent_task_id_id:
                    if task.is_critical_path_task :
                        pass
                    else:
                        if task.display_in_gantt_chart:
                            task.is_critical_path_task = True
                            task.save()
                            update_child_tasks_true(task, headers)
                            prdecessor_cretical_task_true(task, headers)
                elif task.predecessors.filter(target=task.id):
                    for predecessor in task.predecessors.filter(target=task.id):
                        if predecessor.source.is_critical_path_task:
                            if task.is_critical_path_task:
                                pass
                            else:
                                if task.display_in_gantt_chart:
                                    task.is_critical_path_task = True
                                    task.save()
                                    update_child_tasks_true(task, headers)
                                    prdecessor_cretical_task_true(task, headers)
                                    break
                else:
                    counter_var = None
                    if task.successors.all():
                        for successor in task.successors.all():
                            if successor.source.is_critical_path_task:
                                counter_var = True
                                if task.is_critical_path_task:
                                    pass
                                else:
                                    if task.display_in_gantt_chart:
                                        task.is_critical_path_task = True
                                        task.save()
                                        update_child_tasks_true(task, headers)
                                        prdecessor_cretical_task_true(task, headers)
                                        break
                    if not counter_var:
                        task.is_critical_path_task = False
                        task.save()
                        update_child_tasks_false(task, headers)
                        prdecessor_cretical_task(task, headers)
                if task.procurement_id:
                    try:
                        update_product_from_board_gant_chart(task, headers, )
                    except Exception as e:
                        pass
        return task_to_move
    else:
        if task_to_move.display_in_gantt_chart:
            if task_to_move.display_in_gantt_chart:
                task_to_move.is_critical_path_task = True
                task_to_move.save()
                update_child_tasks_true(task_to_move, headers)
                prdecessor_cretical_task_true(task_to_move, headers)
                if task_to_move.procurement_id:
                    try:
                        update_product_from_board_gant_chart(task_to_move, headers, )
                    except Exception as e:
                        pass
                return task_to_move
        else:
            return task_to_move


def is_critical_path_delay_task_dependancy(task_dependancy, delay=None, headers=None):
    """While adding task predecssor update task as critical task."""
    if task_dependancy.source and task_dependancy.target:
        if delay:
            task_dependancy.source.end_date = task_dependancy.source.end_date + timedelta(delay)
            if not task_dependancy.source.due_date:
                task_dependancy.source.due_date = date.today()
            if task_dependancy.source.end_date > task_dependancy.source.due_date:
                task_dependancy.source.delay = (task_dependancy.source.end_date - task_dependancy.source.due_date).days
            elif task_dependancy.source.end_date <= task_dependancy.source.due_date:
                task_dependancy.source.delay = 0
            task_dependancy.source.save()
            if task_dependancy.source.is_critical_path_task:
                if task_dependancy.target.display_in_gantt_chart:
                    if task_dependancy.target.is_critical_path_task:
                        pass
                    else:
                        if task_dependancy.target.display_in_gantt_chart:
                            task_dependancy.target.is_critical_path_task = True
                            task_dependancy.target.save()
                            if task_dependancy.target.procurement_id:
                                try:
                                    update_product_from_board_gant_chart(task_dependancy.target, headers, )
                                except Exception as e:
                                    pass
                            prdecessor_cretical_task_true(task_dependancy.target, headers)
            return task_dependancy.source.delay
        elif task_dependancy.source.is_critical_path_task:
            if task_dependancy.target.display_in_gantt_chart:
                if task_dependancy.target.is_critical_path_task:
                    pass
                else:
                    if task_dependancy.target.display_in_gantt_chart:
                        task_dependancy.target.is_critical_path_task = True
                        task_dependancy.target.save()
                        if task_dependancy.target.procurement_id:
                            try:
                                update_product_from_board_gant_chart(task_dependancy.target, headers, )
                            except Exception as e:
                                pass
                        prdecessor_cretical_task_true(task_dependancy.target, headers)


def destroy_task_util(task_to_remove, task_end_date, headers=None):
    max_end_date = task_to_remove.board_stage.tasks.all().exclude(id=task_to_remove.id).aggregate(
        Max('end_date')).get('end_date__max')
    tasks = task_to_remove.board_stage.tasks.filter(end_date=max_end_date).exclude(id=task_to_remove.id)
    for task in tasks:
        if task.display_in_gantt_chart and task.end_date == max_end_date:
            task.is_critical_path_task = True
            update_child_tasks_true(task, headers)
            prdecessor_cretical_task_true(task, headers)
        task.save()


def task_gantchart_position(boards):
    stages = [stage for board in boards for stage in board.board_stage_maps.all() if stage]
    gantt_position = []
    for stage in stages:
        max_position = stage.tasks.filter(is_display_in_board=True).aggregate(Max('gantt_chart_position')) \
            .get('gantt_chart_position__max')
        if max_position:
            gantt_position.append(max_position)
    if gantt_position:
        return max(gantt_position)
    else:
        return 0


def get_project_details(project_id, headers):
    auth = AuthService()
    response = auth.get_project_dtails_by_id(project_id, headers)
    response_data = {}
    if response.status_code == 200:
        response_data = json.loads(response.text)
    return response_data


def remove_task(task, header):
    if task.gantt_chart_labels.all():
        for label in task.gantt_chart_labels.all():
            remve_gantchart_labels(label, header)
    if task.sub_tasks.all():
        for task_d in task.sub_tasks.all():
            remove_task(task_d, header)
    if task.procurement_id:
        try:
            pay_load = {'is_display_in_ganttchart': False}
            PRODUCT.update_product(pay_load, product_id=task.procurement_id, headers={"Authorization": header})
        except Exception as e:
            return {'Message': 'Network error please try again'}
    task.delete()
    return True


def remve_gantchart_labels(label, header):
    if label.taskss.all():
        for task in label.taskss.all():
            remove_task(task, header)
    if label.sub_labels.all():
        for label in label.sub_labels.all():
            remve_gantchart_labels(label, header)
    label.delete()
    return True


def remove_gantchart_task(task):
    if task.gantt_chart_labels.all():
        for label in task.gantt_chart_labels.all():
            remve_labels(label)
    if task.sub_tasks.all():
        for task_d in task.sub_tasks.all():
            remove_gantchart_task(task_d)
    if task.procurement_id:
        if task.parent_task_id:
            task.parent_task_id = None
        if task.task_labels:
            task.task_labels = None
        task.save()
        return True
    task.display_in_gantt_chart=False
    if task.parent_task_id:
        task.parent_task_id = None
    if task.task_labels:
        task.task_labels=None
    task.save()
    return True


def remve_labels(label):
    if label.taskss.all():
        for task in label.taskss.all():
            remove_gantchart_task(task)
    if label.sub_labels.all():
        for label in label.sub_labels.all():
            remve_labels(label)
    label.delete()
    return True


def get_product_category_name(product_category_id, headers):
        name = None
        if product_category_id:
            procurement_service = ProcurementService()
            try:
                response = procurement_service.get_product_category(int(product_category_id),headers)
                if response.status_code == 200:
                    response_data = json.loads(response.text)
                    name = response_data.get('name')
                    return name
                else:
                    return name
            except Exception as e:
                return name
        else:
            return name


def update_product_from_board_gant_chart(task, headers, end_date=None):
    pay_load = {}
    pay_load['purchase_order_date'] = str(task.start_date)
    pay_load['estimated_arrival_date'] = str(end_date) if end_date else str(task.end_date)
    pay_load['name'] = str(task.title)
    pay_load['description'] = str(task.description)
    if task.is_critical_path_task:
        pay_load['is_critical_path_item'] = True
    else:
        pay_load['is_critical_path_item'] = False
    try:
        PRODUCT.update_product(pay_load,
                               product_id=task.procurement_id,
                               headers= headers)
    except Exception as e:
        return Response({"detail": "Error, Please try again"}, status=status.HTTP_400_BAD_REQUEST)
    return True


def update_critical_path_tasks(board_stage_obj, task_to_move, end_date=None, project_task=None, headers=None):
    """critical task assign"""
    id_list = []
    task_end_date = task_to_move.end_date
    counter_var = None
    if end_date:
        task_end_date = end_date
    max_end_date = board_stage_obj.tasks.filter(is_display_in_board=True).exclude(id__in=[task_to_move.id, project_task.id]).aggregate(
        Max('end_date')).get('end_date__max')
    tasks = board_stage_obj.tasks.filter(display_in_gantt_chart=True, end_date=max_end_date).exclude(id__in=[task_to_move.id, project_task.id])
    if max_end_date:
        if task_end_date > max_end_date:
            if task_to_move.display_in_gantt_chart:
                if task_to_move.is_critical_path_task:
                    pass
                else:
                    task_to_move.is_critical_path_task = True
                    task_to_move.end_date = task_end_date
                    task_to_move.save()
                    update_child_tasks_true(task_to_move, headers)
                    prdecessor_cretical_task_true(task_to_move, headers)
            else:
                if task_to_move.parent_task_id and project_task.id != task_to_move.parent_task_id_id:
                    if task_to_move.parent_task_id.is_critical_path_task:
                        counter_var = True
                        if task_to_move.is_critical_path_task:
                            pass
                        elif task_to_move.display_in_gantt_chart:
                            task_to_move.is_critical_path_task = True
                            task_to_move.save()
                            update_child_tasks_true(task_to_move, headers)
                            prdecessor_cretical_task_true(task_to_move, headers)
                if task_to_move.predecessors.all():
                    for predecessor in task_to_move.predecessors.all():
                        if predecessor.source.is_critical_path_task:
                            counter_var = True
                            if task_to_move.is_critical_path_task:
                                pass
                            elif task_to_move.display_in_gantt_chart:
                                task_to_move.is_critical_path_task = True
                                task_to_move.save()
                                update_child_tasks_true(task_to_move, headers)
                                prdecessor_cretical_task_true(task_to_move, headers)
                                break
                if not counter_var:
                    if not task_to_move.is_critical_path_task:
                        pass
                    else:
                        task_to_move.is_critical_path_task = False
                        task_to_move.save()
                        update_child_tasks_false(task_to_move, headers)
                        prdecessor_cretical_task(task_to_move, headers)
            task_to_move.end_date = task_end_date
            task_to_move.save()
            if task_to_move.procurement_id:
                try:
                    update_product_from_board_gant_chart(task_to_move, headers)
                except Exception as e:
                    pass
            for task in tasks:
                if task_to_move.end_date == task.end_date and task.display_in_gantt_chart:
                    if task.is_critical_path_task:
                        pass
                    else:
                        if task.display_in_gantt_chart:
                            task.is_critical_path_task = True
                            task.save()
                            update_child_tasks_true(task, headers)
                            prdecessor_cretical_task_true(task, headers)
                else:
                    if task.parent_task_id and project_task.id != task.parent_task_id_id:
                        if task.parent_task_id.is_critical_path_task:
                            counter_var = True
                            if task.is_critical_path_task:
                                pass
                            else:
                                if task.display_in_gantt_chart:
                                    task.is_critical_path_task = True
                                    task.save()
                                    update_child_tasks_true(task, headers)
                                    prdecessor_cretical_task_true(task, headers)
                    if task.predecessors.all():
                        for predecessor in task.predecessors.all():
                            if predecessor.target.is_critical_path_task:
                                counter_var = True
                                if task.is_critical_path_task:
                                    pass
                                else:
                                    if task.display_in_gantt_chart:
                                        task.is_critical_path_task = True
                                        task.save()
                                        update_child_tasks_true(task, headers)
                                        prdecessor_cretical_task_true(task, headers)
                                        break

                    if not counter_var:
                        if not task.is_critical_path_task:
                            pass
                        else:
                            task.is_critical_path_task = False
                            task.save()
                            update_child_tasks_false(task, headers)
                            prdecessor_cretical_task(task, headers)
                if task.procurement_id:
                    try:
                        update_product_from_board_gant_chart(task, headers)
                    except Exception as e:
                        pass
            task_to_move.save()
            return task_to_move
        elif task_end_date == max_end_date and task_to_move.display_in_gantt_chart:
            if task_to_move.is_critical_path_task:
                pass
            else:
                if task_to_move.display_in_gantt_chart:
                    task_to_move.is_critical_path_task = True
                    task_to_move.save()
                    update_child_tasks_true(task_to_move, headers)
                    prdecessor_cretical_task_true(task_to_move, headers)
                if task_to_move.procurement_id:
                    try:
                        update_product_from_board_gant_chart(task_to_move, headers)
                    except Exception as e:
                        pass
            return task_to_move
        else:
            if task_to_move.successors.all():
                for successor in task_to_move.successors.all():
                    if successor.source.is_critical_path_task and task_to_move.display_in_gantt_chart:
                        counter_var = True
                        if task_to_move.is_critical_path_task:
                            pass
                        else:
                            if task_to_move.display_in_gantt_chart:
                                task_to_move.is_critical_path_task = True
                                task_to_move.save()
                                update_child_tasks_true(task_to_move, headers)
                                prdecessor_cretical_task_true(task_to_move, headers)
                        break
            if not counter_var:
                if not task_to_move.is_critical_path_task:
                    pass
                else:
                    task_to_move.is_critical_path_task = False
                    task_to_move.save()
                    update_child_tasks_false(task_to_move, headers)
                    prdecessor_cretical_task(task_to_move, headers)
            if task_to_move.procurement_id:
                try:
                    update_product_from_board_gant_chart(task_to_move, headers)
                except Exception as e:
                    pass
            for task in tasks:
                if task.end_date == max_end_date and task.display_in_gantt_chart:
                    if task.is_critical_path_task:
                        pass
                    else:
                        if task.display_in_gantt_chart:
                            task.is_critical_path_task = True
                            task.save()
                            update_child_tasks_true(task, headers)
                            prdecessor_cretical_task_true(task, headers)
                        if task.procurement_id:
                            try:
                                update_product_from_board_gant_chart(task, headers)
                            except Exception as e:
                                pass
            return task_to_move
    elif task_to_move.display_in_gantt_chart:
        task_to_move.is_critical_path_task = True
        task_to_move.save()
        update_child_tasks_true(task_to_move, headers)
        prdecessor_cretical_task_true(task_to_move, headers)
        if task_to_move.procurement_id:
            try:
                update_product_from_board_gant_chart(task_to_move, headers)
            except Exception as e:
                pass
    return task_to_move


def update_child_tasks_true(task, headers):
    if task.sub_tasks.all():
        for child_task in task.sub_tasks.all():
            if child_task.is_critical_path_task:
                pass
            else:
                if child_task.display_in_gantt_chart:
                    child_task.is_critical_path_task=True
                    child_task.save()
                    prdecessor_cretical_task_true(child_task, headers)
                    update_child_tasks_true(child_task, headers)
                    if child_task.procurement_id:
                        try:
                            update_product_from_board_gant_chart(child_task, headers)
                        except Exception as e:
                            pass
    else:
        return True

def update_child_tasks_false(task, headers):
    if task.sub_tasks.all():
        for child_task in task.sub_tasks.all():
            max_end_date = child_task.board_stage.tasks.filter(is_display_in_board=True).aggregate(Max('end_date')).get(
                'end_date__max')
            if child_task.end_date == max_end_date:
                if child_task.display_in_gantt_chart:
                    child_task.is_critical_path_task = True
                    child_task.save()
                    prdecessor_cretical_task_true(child_task, headers)
                    update_child_tasks_true(child_task, headers)
                    if child_task.procurement_id:
                        try:
                            update_product_from_board_gant_chart(child_task, headers)
                        except Exception as e:
                            pass

            elif child_task.end_date < max_end_date:
                if child_task.predecessors.filter(target=child_task.id):
                    for predecessor in child_task.predecessors.filter(target=child_task.id):
                        if predecessor.target.is_critical_path_task:
                            if child_task.display_in_gantt_chart:
                                child_task.is_critical_path_task = True
                                child_task.save()
                                break
                else:
                    counter_var = None
                    if child_task.successors.all():
                        for successor in child_task.successors.all():
                            if successor.source.is_critical_path_task:
                                counter_var = True
                                if child_task.display_in_gantt_chart:
                                    child_task.is_critical_path_task = True
                                    update_child_tasks_true(child_task, headers)
                                    prdecessor_cretical_task_true(child_task, headers)
                                    break
                    if not counter_var:
                        if not child_task.is_critical_path_task:
                            pass
                        else:
                            child_task.is_critical_path_task = False
                            child_task.save()
                            update_child_tasks_false(child_task, headers)
                            prdecessor_cretical_task(child_task, headers)
                if child_task.procurement_id:
                    try:
                        update_product_from_board_gant_chart(child_task, headers)
                    except Exception as e:
                        pass
            else:
                if child_task.board_stage:
                    max_end_date = child_task.board_stage.tasks.filter(is_display_in_board=True).aggregate(Max('end_date')).get('end_date__max')
                    if child_task.end_date == max_end_date:
                        if child_task.display_in_gantt_chart:
                            child_task.is_critical_path_task = True
                            child_task.save()
                else:
                    counter_var = None
                    if child_task.predecessor.all():
                        for predecessor in child_task.predecessor.all():
                            if predecessor.target.is_critical_path_task:
                                counter_var = True
                                if child_task.display_in_gantt_chart:
                                    child_task.is_critical_path_task = True
                                    child_task.save()
                                    break
                    if not counter_var:
                        if not child_task.is_critical_path_task:
                            pass
                        else:
                            child_task.is_critical_path_task=False
                            child_task.save()
                            update_child_tasks_false(child_task, headers)
                            prdecessor_cretical_task(child_task, headers)
                if child_task.procurement_id:
                    try:
                        update_product_from_board_gant_chart(child_task, headers)
                    except Exception as e:
                        pass
                if child_task.display_in_gantt_chart:
                    if child_task.predecessors.all():
                        prdecessor_cretical_task(child_task, headers)
                    update_child_tasks_false(child_task, headers)
    else:
        return False


def prdecessor_cretical_task(task_to_remove, headers):
    for predecessor in task_to_remove.predecessors.all():
        if predecessor.target:
            max_end_date = predecessor.target.board_stage.tasks.filter(is_display_in_board=True)\
                .aggregate(Max('end_date')).get('end_date__max')
            if max_end_date == predecessor.target.end_date:
                if predecessor.target.is_critical_path_task:
                    pass
                else:
                    if predecessor.target.display_in_gantt_chart:
                        predecessor.target.is_critical_path_task = True
                        if predecessor.target.procurement_id:
                            try:
                                update_product_from_board_gant_chart(predecessor.target, headers)
                            except Exception as e:
                                pass
                        update_child_tasks_true(predecessor.target, headers)
                        prdecessor_cretical_task_true(predecessor.target, headers)
            else:
                counter_var = None
                if predecessor.target.successors.filter(target=predecessor.target.id):
                    for successor in predecessor.target.successors.filter(target=predecessor.target.id):
                        if successor.source.is_critical_path_task:
                            counter_var = True
                            if predecessor.target.is_is_critical_path_task:
                                pass
                            else:
                                if predecessor.target.display_in_gantt_chart:
                                    predecessor.target.is_is_critical_path_task = True
                                    predecessor.target.save()
                                    update_child_tasks_true(predecessor.target, headers)
                                    prdecessor_cretical_task_true(predecessor.target, headers)
                                    break
                if not counter_var:
                    if not predecessor.target.is_critical_path_task:
                        pass
                    else:
                        predecessor.target.is_critical_path_task = False
                        predecessor.target.save()
                if predecessor.target.procurement_id:
                    try:
                        update_product_from_board_gant_chart(predecessor.target, headers)
                    except Exception as e:
                        pass
                update_child_tasks_false(predecessor.target, headers)
                prdecessor_cretical_task(predecessor.target, headers)


def prdecessor_cretical_task_true(task_to_remove, headers):
    for predecessor in task_to_remove.predecessors.all():
        if predecessor.target:
            if predecessor.target.display_in_gantt_chart:
                if predecessor.target.is_critical_path_task:
                    pass
                else:
                    if predecessor.target.display_in_gantt_chart:
                        predecessor.target.is_critical_path_task = True
                        predecessor.target.save()
                        update_child_tasks_true(predecessor.target, headers)
                        prdecessor_cretical_task_true(predecessor.target, headers)
                        if predecessor.target.procurement_id:
                            try:
                                update_product_from_board_gant_chart(predecessor.target, headers)
                            except Exception as e:
                                pass
            else:
                if not predecessor.target.is_critical_path_task:
                    pass
                else:
                    predecessor.target.is_critical_path_task = False
                    if predecessor.target.procurement_id:
                        try:
                            update_product_from_board_gant_chart(predecessor.target, headers)
                        except Exception as e:
                            pass
                    predecessor.target.save()
                    update_child_tasks_false(predecessor.target, headers)
                    prdecessor_cretical_task(predecessor.target, headers)




