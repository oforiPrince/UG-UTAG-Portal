"""
ASGI config for utag_ug_archiver project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'utag_ug_archiver.settings')

django_asgi_app = get_asgi_application()

# Defer import of chat.routing until after Django is initialized to avoid AppRegistryNotReady
def get_websocket_urlpatterns():
	from chat.routing import websocket_urlpatterns
	return websocket_urlpatterns

application = ProtocolTypeRouter({
	'http': django_asgi_app,
	'websocket': AuthMiddlewareStack(
		URLRouter(get_websocket_urlpatterns())
	),
})
