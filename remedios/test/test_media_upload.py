import requests
import os

from dotenv import find_dotenv, load_dotenv
from pydub import AudioSegment

env_file = find_dotenv(".env")
load_dotenv(env_file)

GRAPH_API_TOKEN = os.environ.get("GRAPH_API_TOKEN")
BUSINESS_NUMBER_ID = "34671276538"

__URL = "https://graph.facebook.com/v21.0"
__HEADERS = {"Authorization": "Bearer {}".format(GRAPH_API_TOKEN)}


with open("converted.mp3", 'rb') as file:
    # Crear el payload con el archivo
    payload = {
        "type": "audio",
        "messaging_product": "whatsapp",
        "file": file
    }

    # Realizar la petición POST
    media_response = requests.post(
        "{}/{}/media".format(__URL, BUSINESS_NUMBER_ID),
        headers=__HEADERS,
        data=file
    )

# _mp3_file = AudioSegment.from_mp3("converted.mp3").array_type

# Crear el payload con el archivo
# payload = {
#     "type": "audio",
#     "messaging_product": "whatsapp",
#     "file": _mp3_file
# }
#
# # Realizar la petición POST
# media_response = requests.post(
#     "{}/{}/media".format(__URL, BUSINESS_NUMBER_ID),
#     headers={"Authorization": "Bearer {}".format(GRAPH_API_TOKEN), "Content-Type": "mp3"},
#     data=_mp3_file
# )

print(media_response.status_code)
print(media_response.content)