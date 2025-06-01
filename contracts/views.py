from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework import status, viewsets
from django.utils.timezone import now
from django.conf import settings
import base64
import os
import json
import threading
import logging
import pika
import requests

from .utils import generate_keys, sign_message
from .models import Contract
from .serialiazars import ContractSerializer
from .gemini_helper import GeminiHelper

# ----------- Logging -----------
logger = logging.getLogger("rabbitmq_consumer")
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# ----------- RabbitMQ Setup -----------

def get_rabbitmq_channel():
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=os.environ.get('RABBITMQ_HOST', 'host.docker.internal'),
                port=int(os.environ.get('RABBITMQ_PORT', 5672)),
                heartbeat=int(os.environ.get('RABBITMQ_HEARTBEAT', 600)),
                blocked_connection_timeout=int(os.environ.get('RABBITMQ_TIMEOUT', 300))
            )
        )
        channel = connection.channel()
        channel.queue_declare(queue='generate_contract', durable=True)
        logger.info("Connected to RabbitMQ and declared queue 'generate_contract'")
        return connection, channel
    except Exception as e:
        logger.error(f"Failed to connect to RabbitMQ: {e}")
        raise

# ----------- External API Calls -----------

def fetch_profile(user):
    try:
        url = f"http://host.docker.internal:8008/profile/profil/?user={user}"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Failed to fetch profile for user {user}: {e}")
        return None

def fetch_equipment(equipment_id):
    try:
        url = f"http://host.docker.internal:8006/api/stuffs/{equipment_id}/"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Failed to fetch equipment ID {equipment_id}: {e}")
        return None

# ----------- RabbitMQ Consumer Thread -----------

def rabbitmq_consumer():
    try:
        connection, channel = get_rabbitmq_channel()

        def callback(ch, method, properties, body):
            try:
                data = json.loads(body)
                logger.info(f"Received message: {data}")

                owner_name = data.get("rental")
                client_name = data.get("client")
                equipment_id = data.get("equipment")

                profile_info_client = fetch_profile(client_name)
                profile_info_owner = fetch_profile(owner_name)
                equipment_info = (
                    [fetch_equipment(eid) for eid in equipment_id]
                    if isinstance(equipment_id, list)
                    else fetch_equipment(equipment_id)
                )

                contract_data = {
                    "owner_name": owner_name,
                    "client_name": client_name,
                    "equipment": equipment_id,
                    "start_date": data.get("start_date"),
                    "end_date": data.get("end_date"),
                    "total_value": data.get("total_price"),
                    "details": data.get("status", ""),
                }

                helper = GeminiHelper()
                contract = helper.create_draft_contract(contract_data, profile_info_client, profile_info_owner, equipment_info)

                logger.info(f"Contract created with ID: {contract.id}")
                ch.basic_ack(delivery_tag=method.delivery_tag)
            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)

        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(queue='generate_contract', on_message_callback=callback)
        logger.info("Waiting for messages on 'generate_contract'. To exit press CTRL+C")
        channel.start_consuming()

    except Exception as e:
        logger.error(f"Fatal error in RabbitMQ consumer: {e}", exc_info=True)
    finally:
        if 'connection' in locals() and connection.is_open:
            connection.close()
            logger.info("RabbitMQ connection closed.")

# Start consumer thread
consumer_thread = threading.Thread(target=rabbitmq_consumer, daemon=True)
consumer_thread.start()

# ----------- Signature API -----------

@api_view(['POST'])
@parser_classes([JSONParser])
def sign_contract(request):
    try:
        owner_name = request.data.get("owner_name")
        client_name = request.data.get("client_name")
        contract_text = request.data.get("contract_text")
        signature_image_data = request.data.get("signature_image")

        if not all([owner_name, client_name, contract_text, signature_image_data]):
            return Response({"error": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST)

        contract = get_contract_or_404(owner_name, client_name)
        signature_image_path = save_signature_image(owner_name, signature_image_data)

        private_key, public_key = generate_keys()
        signature = sign_message(contract_text, private_key)

        contract.signed_date = now().date()
        contract.status = 'signed'
        contract.document.name = signature_image_path
        contract.save()

        return Response({
            "message": contract_text,
            "owner_name": owner_name,
            "client_name": client_name,
            "signature": signature,
            "public_key": public_key.decode(),
            "signature_image_url": os.path.join(settings.MEDIA_URL, signature_image_path),
            "contract_id": contract.id,
            "status": contract.status,
            "signed_date": contract.signed_date,
            "total_value": contract.total_value,
            "start_date": contract.start_date,
            "end_date": contract.end_date
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ----------- Contract ViewSet -----------

class ContractViewSet(viewsets.ModelViewSet):
    queryset = Contract.objects.all()
    serializer_class = ContractSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        return self.filter_queryset_by_params(queryset)

    def filter_queryset_by_params(self, queryset):
        owner_name = self.request.query_params.get('owner_name')
        client_name = self.request.query_params.get('client_name')

        if owner_name:
            queryset = queryset.filter(owner_name=owner_name)
        if client_name:
            queryset = queryset.filter(client_name=client_name)

        return queryset

# ----------- Utility Functions -----------

def save_signature_image(owner_name: str, signature_image_data: str) -> str:
    try:
        header, encoded = signature_image_data.split(",", 1)
        image_data = base64.b64decode(encoded)
    except (ValueError, IndexError):
        raise ValueError("Invalid base64 image data")

    image_name = f"{owner_name.replace(' ', '_')}_{now().strftime('%Y%m%d%H%M%S')}.png"
    image_dir = os.path.join(settings.MEDIA_ROOT, "signatures")
    os.makedirs(image_dir, exist_ok=True)

    image_path = os.path.join(image_dir, image_name)
    with open(image_path, "wb") as f:
        f.write(image_data)

    return os.path.join('signatures', image_name)

def get_contract_or_404(owner_name: str, client_name: str) -> Contract:
    try:
        return Contract.objects.get(owner_name=owner_name, client_name=client_name)
    except Contract.DoesNotExist:
        raise ValueError("Contract not found")
