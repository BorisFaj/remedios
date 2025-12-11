from abc import ABC, abstractmethod


class LogBase(ABC):
    def __init__(self, message_queue: [str]):
        self.m_queue = message_queue
