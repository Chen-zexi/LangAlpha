from openai import OpenAI
from pydantic import BaseModel
import json

import os
from dotenv import load_dotenv

load_dotenv()


class LLM:
    def __init__(self):
        pass

    def generate_response(self, prompt):
        pass


class GEMINI(LLM):
    def __init__(self):
        super().__init__()
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client = OpenAI(api_key=self.api_key,
                             base_url="https://generativelanguage.googleapis.com/v1beta/openai/")

    def generate_response(self, prompt):
        pass