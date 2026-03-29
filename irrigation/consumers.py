from channels.generic.websocket import AsyncWebsocketConsumer
import logging

logger = logging.getLogger(__name__)


class SensorDataConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        try:
            self.user_id = self.scope['url_route']['kwargs']['user_id']
            self.group_name = f'sensor_updates_{self.user_id}'

            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )
            await self.accept()
            logger.info(f"[WEBSOCKET] Client connected for user {self.user_id}")
        except Exception as e:
            logger.error(f"[WEBSOCKET] Connection error: {str(e)}")
            await self.close()

    async def disconnect(self, close_code):
        try:
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
            logger.info(f"[WEBSOCKET] Client disconnected for user {self.user_id}")
        except Exception as e:
            logger.error(f"[WEBSOCKET] Disconnection error: {str(e)}")

    async def send_sensor_data(self, event):
        try:
            await self.send(text_data=event['data'])
            logger.debug(f"[WEBSOCKET] Data sent to user {self.user_id}")
        except Exception as e:
            logger.error(f"[WEBSOCKET] Send error: {str(e)}")
