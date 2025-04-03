from django.urls import path

from mindframe.views.chat import ChatDetailView, ChatReplyView, NewMessagesView, TurnDetailView

urlpatterns = [
    path("c/<str:uuid>/", ChatDetailView.as_view(), name="chat-detail"),
    path("new/<str:since_uuid>/", NewMessagesView.as_view(), name="chat-new-messages"),
    path("t/<str:uuid>/", TurnDetailView.as_view(), name="turn-detail"),
    path("reply/<str:uuid>/", ChatReplyView.as_view(), name="chat-reply"),
]
