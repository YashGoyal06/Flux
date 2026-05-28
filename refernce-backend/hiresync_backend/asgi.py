"""
ASGI config for hiresync_backend project.
"""
import os
import django
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hiresync_backend.settings')
django.setup()

# Import channels routes after django.setup() to prevent AppRegistryNotReady error
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import interviews.routing

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            interviews.routing.websocket_urlpatterns
        )
    ),
})
