"""Cliente para WhatsApp Business API (Meta)."""
import httpx
from config import settings

WHATSAPP_API_URL = ""https://graph.facebook.com/v18.0""

class WhatsAppClient:
    def __init__(self):
        self.token = settings.whatsapp_token
        self.phone_id = settings.whatsapp_phone_number_id
        self.headers = {
            ""Authorization"": ""Bearer "" + self.token,
            ""Content-Type"": ""application/json""
        }
    
    async def send_text(self, to: str, text: str):
        url = WHATSAPP_API_URL + ""/"" + self.phone_id + ""/messages""
        payload = {
            ""messaging_product"": ""whatsapp"",
            ""recipient_type"": ""individual"",
            ""to"": to,
            ""type"": ""text"",
            ""text"": {""body"": text}
        }
        async with httpx.AsyncClient() as client:
            r = await client.post(url, headers=self.headers, json=payload)
            return r.status_code == 200

whatsapp = WhatsAppClient()
