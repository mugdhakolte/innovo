from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None and isinstance(response.data, dict):
        custom_data = response.data
        if "detail" in response.data.keys() and response.status_code in [401, 403, 500]:
            pass
        else:
            custom_data["detail"] = "Error, please try again later."
        response.data = custom_data
    return response