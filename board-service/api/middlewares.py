import ast

from django.http import JsonResponse

from api.inter_service_communicator import AuthService


class InnovoAuthMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        auth_service = AuthService()
        try:
            response = auth_service.get_my_profile({'Authorization': request.headers.get('Authorization')})
            request.innovo_user = str(response.json())
            return self.get_response(request)
        except Exception as e:
            return JsonResponse(ast.literal_eval(str(e)), status=401)



