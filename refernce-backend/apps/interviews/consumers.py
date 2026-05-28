import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer
import logging

logger = logging.getLogger(__name__)

class LiveInterviewConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'interview_{self.room_id}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        
        # Broadcast user joining event
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'broadcast_message',
                'sender_channel_name': self.channel_name,
                'message': {
                    'type': 'peer_status',
                    'action': 'join',
                    'message': 'A peer has joined the room.'
                }
            }
        )

    async def disconnect(self, close_code):
        # Broadcast user leaving event
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'broadcast_message',
                'sender_channel_name': self.channel_name,
                'message': {
                    'type': 'peer_status',
                    'action': 'leave',
                    'message': 'A peer has left the room.'
                }
            }
        )

        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive_json(self, content):
        """
        Receive message from WebSocket and broadcast to room group.
        """
        msg_type = content.get('type')
        
        # We forward all known messaging formats (signal, code_edit, language_change, whiteboard_draw, chat_message, problem_change)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'broadcast_message',
                'sender_channel_name': self.channel_name,
                'message': content
            }
        )

    async def broadcast_message(self, event):
        """
        Send the broadcasted message to the WebSocket client if it's not the sender.
        """
        sender = event['sender_channel_name']
        message = event['message']

        # Avoid echo to the sender (unless it's a chat message where the sender needs validation/echo status)
        if self.channel_name != sender or message.get('type') == 'chat_message':
            await self.send_json(message)
