from kafka import KafkaAdminClient
from kafka.admin import NewTopic
from kafka.errors import TopicAlreadyExistsError
from dotenv import load_dotenv, find_dotenv
import os


load_dotenv(find_dotenv(".env"))

admin = KafkaAdminClient(
  bootstrap_servers="cv49rf4id6h4h1mpb8qg.any.eu-central-1.mpx.prd.cloud.redpanda.com:9092",
  security_protocol="SASL_SSL",
  sasl_mechanism="SCRAM-SHA-256",
  sasl_plain_username=os.environ.get("REDPANDA_USER"),
  sasl_plain_password=os.environ.get("REDPANDA_PASS"),
)

try:
  topic = NewTopic(name="whatsapp-events", num_partitions=1, replication_factor=-1, replica_assignments=[])
  admin.create_topics(new_topics=[topic])
  print("Created topic")
except TopicAlreadyExistsError as e:
  print("Topic already exists")
finally:
  admin.close()