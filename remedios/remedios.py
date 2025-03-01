from app import whats

def run(request: dict):
    print("Incoming webhook message: {}".format(request))
    message = whats.get_message(request)
    phone_number = whats.get_phone_number(request)
    print(f"numero de origen: {phone_number}")

    if message:
        if message.get("type") == "text":
            _message_body = message['text']['body']
            respuesta_chatgpt = whats.ask(_message_body)
            # respuesta_chatgpt = "recibido lokiii"

            print(f"[HUMAN]: {_message_body}")
            print(f"[IA]: {respuesta_chatgpt}")

            whats.send_text_answer(respuesta_chatgpt, message["from"], message["id"], phone_number)

            print("Text answer send ;)")
        elif message.get("type") == "audio":
            audio = whats.extract_audio(message, phone_number)
            # _pregunta = whats.transcribe(audio)
            # answer = whats.ask(_pregunta)
            # whats.send_text_answer(answer, message["from"], message["id"], phone_number)
            # whats.send_audio_answer(answer, phone_number)

            whats.send_text_answer(whats.transcribe(audio), message["from"], message["id"], phone_number)
        else:
            print("pos na")