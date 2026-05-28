from django.urls import re_path
from .consumers import LiveInterviewConsumer

websocket_urlpatterns = [
    re_path(r'ws/interview/(?P<room_id>[^/]+)/$', LiveInterviewConsumer.as_asgi()),
]
