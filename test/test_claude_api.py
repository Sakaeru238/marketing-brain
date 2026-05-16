import os
import sys

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, ".."))

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from anthropic import Anthropic

print("FILE STARTED")

api_key = os.getenv("CLAUDE_API_KEY")
print("API KEY FOUND:", bool(api_key))
print("API KEY PREFIX:", api_key[:12] if api_key else None)

if not api_key:
    raise ValueError("CLAUDE_API_KEY chưa được load từ environment")

client = Anthropic(api_key=api_key)

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=100,
    messages=[{"role": "user", "content": "Say hello in one sentence."}],
)

print("CLAUDE RESPONSE:")
print(response.content[0].text)
