ACTION_PERMISSIONS_MAP = {
            'list': 'can_view_board',
            'retrieve': 'can_view_board',
            'destroy': 'can_delete_board',
            'create': 'can_add_board',
            'update': 'can_edit_board',
            'partial_update': 'can_edit_board',

            'copy_task': 'can_edit_board',
            'move_task': 'can_edit_board',
            'archive_task': 'can_edit_board',
            'unarchive_task': 'can_edit_board',
            'get_labels': 'can_view_board',
            'add_label': 'can_add_board',
            'remove_label': 'can_delete_board',
            'get_members': 'can_view_members',
            'add_member': 'can_add_members',
            'remove_member': 'can_delete_members',
            'create_gantt_task': 'can_add_ganttchart',
            'remove_gantt_chart_task': 'can_delete_ganttchart',
            'update_gantt_chart_task': 'can_edit_ganttchart',
            'move_gantt_chart_task': 'can_edit_ganttchart',

            'ganttchart_task_predecessor': 'can_view_ganttchart',
            'move_ganttchart_label': 'can_edit_ganttchart'
        }