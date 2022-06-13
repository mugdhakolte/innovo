"""Module to format serializer errors and to send email."""

import json
import requests

from django.conf import settings


class BaseService(object):
    """Base class to communicate with services internally"""

    def __init__(self):
        self.base_url = ""

    def make_request(self, relative_url, payload=None, params=None,
                     request_type='POST', expected_response_code=200, headers={}):
        """To make http request to hubspot depending upon given params."""

        if not payload:
            payload = {}
        if not params:
            params = {}
        url = self.base_url + relative_url

        if request_type == 'POST':
            response = requests.post(url, json=payload, params=params, headers=headers)
        elif request_type == 'GET':
            response = requests.get(url, params=params, headers=headers)
        else:
            raise Exception('Invalid request type provided.')

        status_code = response.status_code
        if status_code != expected_response_code:
            raise Exception(response.text)
        return response


class AuthService(BaseService):
    """Class responsible for communication with auth service."""

    def __init__(self):
        self.base_url = settings.AUTH_MICRO_SERVICE_URL

    def get_users_from_ids(self, user_ids, headers):
        """Call the API to get user details from id."""
        if user_ids:
            payload = {'user_id': user_ids}
            return self.make_request("user/get-user-data/", payload=payload, request_type='POST', headers=headers)
        else:
            pass


    def get_user_details_from_id(self, user_id):
        """Call the API to get user details from id."""

        return self.make_request("user/{}/".format(user_id), request_type='GET', expected_response_code=200)

    def get_user_from_id_s(self, user_id, headers):
        return self.make_request("user/{}/".format(user_id), request_type='GET', expected_response_code=200, headers=headers)

    def get_my_profile(self, headers):
        """Call the API to get myprofile."""
        return self.make_request("my-profile", request_type='GET', expected_response_code=200, headers=headers)

    def add_board_to_favourites(self, headers, board_id):
        """Call the API to get myprofile."""
        return self.make_request("user/{}/add-board-to-favourites/".format(board_id), request_type='POST',
                                 expected_response_code=200, headers=headers)

    def remove_board_from_favourites(self, headers, board_id):
        """Call the API to get myprofile."""
        return self.make_request("user/{}/remove-board-from-favourites/".format(board_id),
                                 request_type='POST', expected_response_code=200, headers=headers)

    def has_permission(self, project_id, permission_code, headers):
        data = {"project_id" : project_id,
                "permission_code" : permission_code}
        return self.make_request("has-permission/", payload=data, request_type='POST', expected_response_code=200, headers=headers)

    def is_project_admin(self, project_id, headers):
        data = {"project_id" : project_id}
        return self.make_request("is-project-admin/", payload=data, request_type='POST', expected_response_code=200, headers=headers)

    def get_project_dtails_by_id(self, project_id, headers):
        return self.make_request("project/{0}/get-project-detail/".format(project_id), request_type='GET', expected_response_code=200)


class NotificationService(BaseService):
    """Class responsible for communication with notification service."""

    def __init__(self):
        """To initialize notification."""

        self.base_url = settings.NOTIFICATION_MICRO_SERVICE_URL
        self.auth_service = AuthService()

    def send_board_invitation_email(self, user, board):
        """
        Call the API to send email of notification microservice.

        :param args:
        :param kwargs: type(specified in settings EMAIL_TEMPLATES),context
        parameters, receiver=email
        :return: boolean or raises KeyError if mandatory parameters are missing
        """

        user_email = self.auth_service.get_user_details_from_id(user).json()['email']

        context = {
            'url': "{0}/boards/{1}".format(settings.APP_URL, board.id),
            'board_name': board.name,
            'subject': "Board Invitation"
        }
        data = {
            "type": "email",
            "template": "board_invitation",
            "context": json.dumps(context),
            "receiver": user_email,
        }
        self.make_request("notifications/", data, expected_response_code=201)

    def send_task_invitation_email(self, user, task):
        """
        Call the API to send email of notification microservice.

        :param args:
        :param kwargs: type(specified in settings EMAIL_TEMPLATES),context
        parameters, receiver=email
        :return: boolean or raises KeyError if mandatory parameters are missing
        """

        user_email = self.auth_service.get_user_details_from_id(user).json()['email']

        context = {
            'url': "{0}/boards/{1}".format(settings.APP_URL, task.board_stage.board.id),
            'task_name': task.title,
            'subject': "Task Invitation"
        }
        data = {
            "type": "email",
            "template": "task_invitation",
            "context": json.dumps(context),
            "receiver": user_email,
        }
        self.make_request("notifications/", data, expected_response_code=201)


class ProcurementService(BaseService):

    def __init__(self):
        self.base_url = settings.PROCUREMENT_MICRO_SERVICE_URL

    def update_product(self, pay_load, product_id, headers):
        return self.make_request("products/{0}/update-product-from-ganttchart/".format(product_id), pay_load,
                                 request_type='POST', expected_response_code=202, headers=headers)

    def get_product_category(self, category_id, headers):
        return self.make_request('categories/{0}/'.format(category_id), request_type='GET',
                                 expected_response_code=200, headers=headers)

    def get_cretical_path_item(self, product_id, headers):
        return self.make_request('products/get-critical-path-item/?product_id={0}'.format(product_id), request_type='GET',
                                 expected_response_code=200, headers=headers)
