######## INFOBIP ########

# from infobip_channels.whatsapp.channel import WhatsAppChannel
# from app.config.settings import settings

# whatsapp_channel = WhatsAppChannel.from_auth_params({
#     "base_url": settings.INFOBIP_BASE_URL,    
#     "api_key": settings.INFOBIP_API_KEY
# })

####### META CLOUD API ########

import requests
from app.config.settings import settings
from app.config.logger import get_logger

logger = get_logger("Meta API Logger")

class MetaWhatsAppChannel:
    def __init__(self, access_token: str, phone_number_id: str, api_version: str = "v19.0"):
        self.base_url = f"https://graph.facebook.com/{api_version}"
        self.phone_number_id = phone_number_id
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    def send_text_message(self, recipient_no: str, message_text: str):
        """
        Args:
            recipient_no (str): The recipient's phone number with country code.
            message_text (str): The text message to send.
        """
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient_no,
            "type": "text",
            "text": {"body": message_text},
        }
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            logger.info(f"Successfully sent message to {recipient_no}. Response: {response.json()}")
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error sending message to {recipient_no}: {e}")
            logger.error(f"Response body: {e.response.text if e.response else 'No response'}")
            return None

    def get_media_url(self, media_id: str) -> str | None:
        """
        Retrieves the temporary download URL for a media file.

        Args:
            media_id (str): The ID of the media object.

        Returns:
            str | None: The temporary URL to download the media, or None if an error occurs.
        """
        url = f"{self.base_url}/{media_id}"
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            media_data = response.json()
            logger.info(f"Retrieved media URL for media ID {media_id}")
            return media_data.get("url")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting media URL for ID {media_id}: {e}")
            return None

    def download_media(self, media_url: str) -> bytes | None:
        try:
            response = requests.get(media_url, headers={"Authorization": self.headers["Authorization"]})
            response.raise_for_status()
            logger.info(f"Successfully downloaded media from {media_url}")
            return response.content
        except requests.exceptions.RequestException as e:
            logger.error(f"Error downloading media from {media_url}: {e}")
            return None

    def mark_message_as_read(self, message_id: str):
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id
        }
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.content
        except requests.exceptions.RequestException as e:
            logger.error(f"Error while performing mark_as_read: {e.response.text if e.response else 'No response'}")
            return None
    
    def send_typing_indicator(self, message_id: str):
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
            "typing_indicator": {
                "type": "text"
            }
        }
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error while sending typing indicator {e.response.text if e.response else 'No response'}")
            return None
    
whatsapp_channel = MetaWhatsAppChannel(
    access_token=settings.META_ACCESS_TOKEN,
    phone_number_id=settings.META_PHONE_NUMBER_ID,
    api_version=settings.META_API_VERSION
)