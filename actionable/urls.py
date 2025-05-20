from django.urls import include, path
from .views import GenericActionDispatcherView


urlpatterns = [
    path(
        "<str:app>/<str:model>/<str:identifier>/",
        GenericActionDispatcherView.as_view(),
        name="action",
    ),
]
