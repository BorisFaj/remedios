kafka_route = {
    "audio": "transcription_requests",
    "text": "answer_request",
    "dlq": "incoming.messages.text.dlq",
}

api_route = {
    "job_status": "/internal/job_status",
    "job_result": "/internal/job_result",
    "job_audio": "/internal/job_audio",
    "audio_upload_url": "/internal/audio_upload_url",
}
