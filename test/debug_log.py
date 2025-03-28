from remedios.log.sender import *

phone_number = "34671276538"
n = 10

messages = session.query(Message).filter(
(Message.sender_phone == phone_number) | (Message.receiver_phone == phone_number),
).order_by(Message.timestamp.desc()).limit(n).all()

print("hola probando")
print(messages[::-1])


las_ms = __get_last_text_messages(phone_number)
formateao_y_to = get_embeddings_context(phone_number, "mensaje nuevo")
print(formateao_y_to)