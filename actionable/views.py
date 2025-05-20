import rules
from django.apps import apps
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, HttpResponseNotFound, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View

from .mixins import ActionableObjectMixin


@method_decorator(login_required, name="dispatch")
class GenericActionDispatcherView(View):
    model_field = "pk"  # or override to 'slug' if needed

    def get_model_class(self, app_label, model_name):
        try:
            return apps.get_model(app_label, model_name)
        except LookupError:
            return None

    def get_object(self, model_class, identifier):
        filter_kwargs = {self.model_field: identifier}
        return model_class.objects.get(**filter_kwargs)

    def post(self, request, *args, **kwargs):
        app_label = kwargs.get("app")
        model_name = kwargs.get("model")
        identifier = kwargs.get("identifier")
        action_name = request.POST.get("action")

        model_class = self.get_model_class(app_label, model_name)
        if not model_class:
            return HttpResponseNotFound("Invalid model")

        obj = self.get_object(model_class, identifier)

        handler = obj  # assumes actions live on model instance
        if not isinstance(handler, ActionableObjectMixin):
            return HttpResponseNotFound("Not actionable")

        method = getattr(handler, action_name, None)
        if not callable(method) or not getattr(method, "_is_action", False):
            return JsonResponse({"error": "No such action"})

        permission = handler.get_action_permission(action_name)

        can_cancel = request.user.has_perm(permission)
        if not permission or not can_cancel:
            return JsonResponse({"error": "Permission denied"})

        # don't blindly drop POST data into kwargs
        raw_data = request.POST.dict()
        allowed_args = getattr(method, "_action_args", [])
        safe_kwargs = {k: raw_data[k] for k in allowed_args if k in raw_data}
        print(allowed_args, safe_kwargs, method)
        return JsonResponse({"result": method(**safe_kwargs)})
