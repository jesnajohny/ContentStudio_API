import json
import os
from google.cloud import pubsub_v1
from app.core.config import get_settings

settings = get_settings()

class PubSubService:
    def __init__(self):
        # Explicitly set the credentials environment variable
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.GOOGLE_APPLICATION_CREDENTIALS
        
        try:
            self.publisher = pubsub_v1.PublisherClient()
            self.topic_path = self.publisher.topic_path(
                settings.GOOGLE_CLOUD_PROJECT, 
                settings.PUBSUB_TOPIC_NAME
            )
            print(f"✅ Pub/Sub Client initialized for topic: {settings.PUBSUB_TOPIC_NAME}")
        except Exception as e:
            print(f"❌ Failed to initialize Pub/Sub: {e}")
            self.publisher = None

    def publish_message(self, data: dict) -> str:
        """
        Publishes a JSON serializable dictionary to the configured Pub/Sub topic.
        """
        if not self.publisher:
            print("⚠️ Pub/Sub publisher not available.")
            return None

        try:
            # Data must be a bytestring
            data_str = json.dumps(data)
            print(f"Data to be published: {data_str}")
            data_bytes = data_str.encode("utf-8")
            
            # Publish the message
            future = self.publisher.publish(self.topic_path, data_bytes)
            message_id = future.result()
            
            print(f"✅ Message published to Pub/Sub with ID: {message_id}")
            return message_id
            
        except Exception as e:
            print(f"❌ Pub/Sub Publish Error: {e}")
            raise e