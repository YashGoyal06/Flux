import uuid

from channels.generic.websocket import AsyncJsonWebsocketConsumer


rooms = {}


class CallConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.room_code = self.scope["url_route"]["kwargs"]["room_code"]
        self.room_group_name = f"call_{self.room_code}"
        self.client_id = uuid.uuid4().hex
        self.username = "Guest"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        await self.send_json({"event": "connect", "socketId": self.client_id})

    async def disconnect(self, close_code):
        room = rooms.get(self.room_code, {})
        was_joined = self.client_id in room

        if was_joined:
            room.pop(self.client_id, None)
            if not room:
                rooms.pop(self.room_code, None)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "room_event",
                    "sender_channel_name": self.channel_name,
                    "payload": {
                        "event": "user-left",
                        "socketId": self.client_id,
                    },
                },
            )

        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive_json(self, content):
        event = content.get("event")

        if event == "username":
            self.username = content.get("username") or "Guest"
            room = rooms.get(self.room_code, {})
            if self.client_id in room:
                room[self.client_id]["username"] = self.username
                await self._broadcast({
                    "event": "username",
                    "socketId": self.client_id,
                    "username": self.username,
                })
            return

        if event == "join-call":
            room = rooms.setdefault(self.room_code, {})
            existing_users = [
                {"socketId": socket_id, "username": participant["username"]}
                for socket_id, participant in room.items()
                if socket_id != self.client_id
            ]

            room[self.client_id] = {
                "channel_name": self.channel_name,
                "username": self.username,
            }

            await self.send_json({"event": "room-users", "users": existing_users})
            await self._broadcast({
                "event": "user-joined",
                "user": {
                    "socketId": self.client_id,
                    "username": self.username,
                },
            })
            return

        if event == "signal":
            await self._send_to_peer(
                content.get("toId"),
                {
                    "event": "signal",
                    "fromSocketId": self.client_id,
                    "message": content.get("message"),
                },
            )
            return

        if event == "chat-message":
            await self._broadcast(
                {
                    "event": "chat-message",
                    "data": content.get("data", ""),
                    "sender": content.get("sender") or self.username,
                    "socketIdSender": self.client_id,
                },
                include_sender=False,
            )
            return

        if event in ("screen-share-started", "screen-share-stopped"):
            await self._broadcast(
                {
                    "event": event,
                    "sharerSocketId": content.get("sharerSocketId") or self.client_id,
                },
                include_sender=False,
            )

    async def _send_to_peer(self, socket_id, payload):
        participant = rooms.get(self.room_code, {}).get(socket_id)
        if not participant:
            return

        await self.channel_layer.send(
            participant["channel_name"],
            {
                "type": "direct_event",
                "payload": payload,
            },
        )

    async def _broadcast(self, payload, include_sender=True):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "room_event",
                "sender_channel_name": None if include_sender else self.channel_name,
                "payload": payload,
            },
        )

    async def room_event(self, event):
        if event.get("sender_channel_name") == self.channel_name:
            return
        await self.send_json(event["payload"])

    async def direct_event(self, event):
        await self.send_json(event["payload"])
