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


class NotificationService(BaseService):
    """Class responsible for communication with notification service."""

    def __init__(self):
        """To initialize notification."""

        self.base_url = settings.NOTIFICATION_MICRO_SERVICE_URL

    def send_forgot_password_email(self, user, token):
        """
        Call the API to send email of notification micro service.

        :param args:
        :param kwargs: type(specified in settings EMAIL_TEMPLATES),context
        parameters, receiver=ema     l
        :return: boolean or raises KeyError if mandatory parameters are missing
        """
        context = {
            'url': "{0}/reset-password/{1}/".format(settings.APP_URL, token.token),
            'name': user.full_name,
            'subject': "Reset Password"
        }

        data = {
            "type": "email",
            "template": "forgot_password",
            "context": json.dumps(context),
            "receiver": user.email,

        }
        self.make_request("notifications/", data, expected_response_code=201)

    def send_user_registration_invite_email(self, user, token):
        """
        Call the API to send email of notification micro service.

        :param args:
        :param kwargs: type(specified in settings EMAIL_TEMPLATES),context
        parameters, receiver=ema     l
        :return: boolean or raises KeyError if mandatory parameters are missing
        """
        context = {
            'url': "{0}/signup/{1}/".format(settings.APP_URL, token.token),
            'subject': "Welcome to Innovo Builders"
        }

        data = {
            "type": "email",
            "template": "registration",
            "context": json.dumps(context),
            "receiver": user.email,
        }

        self.make_request("notifications/", data, expected_response_code=201)

    def send_project_invitation_email(self, user, project):
        """
        Call the API to send email of notification microservice.

        :param args:
        :param kwargs: type(specified in settings EMAIL_TEMPLATES),context
        parameters, receiver=email
        :return: boolean or raises KeyError if mandatory parameters are missing
        """
        context = {
            'url': "{0}/notifications/".format(settings.APP_URL),
            'project_name': project.name,
            'subject': "Invitation to collaborate"
        }

        data = {
            "type": "email",
            "template": "project_invitation",
            "context": json.dumps(context),
            "receiver": user.email,
        }

        self.make_request("notifications/", data, expected_response_code=201)

    def send_email(self, project_member, context_data):
        data = {
            "type": "email",
            "context": json.dumps(context_data),
            "receiver": project_member.email
        }
        response = self.make_request("send-email/", data, expected_response_code=200)
        return response

