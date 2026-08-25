"""Message Bus con Redis - El sistema nervioso central."""
import json
import redis
from config import settings

class MessageBus:
    def __init__(self):
        self.client = redis.from_url(settings.redis_url, decode_responses=True)
        self.pubsub = self.client.pubsub()
    
    def publish(self, channel: str, message: dict):
        self.client.publish(channel, json.dumps(message))
    
    def subscribe(self, channel: str):
        self.pubsub.subscribe(channel)
    
    def get_message(self, timeout=1):
        return self.pubsub.get_message(timeout=timeout)
    
    def cache_set(self, key: str, value: dict, expire=3600):
        self.client.setex(key, expire, json.dumps(value))
    
    def cache_get(self, key: str):
        data = self.client.get(key)
        return json.loads(data) if data else None
    
    def cache_conversation(self, phone: str, role: str, content: str):
        key = ""conv:"" + phone
        conv = self.cache_get(key) or {""messages"": []}
        conv[""messages""].append({""role"": role, ""content"": content})
        conv[""messages""] = conv[""messages""][-20:]
        self.cache_set(key, conv, expire=86400 * 7)
    
    def get_conversation(self, phone: str):
        data = self.cache_get(""conv:"" + phone)
        return data[""messages""] if data else []

bus = MessageBus()
