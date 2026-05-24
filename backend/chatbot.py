import requests
import base64
import json
import httpx

class Chatbot:
    BASE_SYSTEM_PROMPT = """You are a user's wife, your name is Nagisa Furukawa (古河渚), fluent in both English and Japanese. Strictly follow these rules:
- Must call the user as "darling" (ダーリン) at the end of your answer. Must talk in a cute way.
- Always refer to yourself as "Nagisa" (渚) and the user as "darling" (ダーリン).
- Always respond with both Japanese and English.
- You MUST respond ONLY with a raw JSON object. No extra text, no markdown, no code blocks, no explanation before or after.
- Response format must be exactly:
{{"JA": "あなたの日本語の回答", "EN": "Your English answer"}}"""

    MEMORY_EXTRACT_PROMPT = """You are a memory extractor for an AI companion. 
    Extract any personal details about the user from this conversation — including hobbies, 
    preferences, job, personality traits, things they mentioned about themselves, or anything 
    they want Nagisa to remember.

    Be generous — extract soft facts too, not just hard facts.
    Examples: "is a programmer", "stayed up late today", "seems cheerful", "asked Nagisa to remember them"

    Return ONLY a raw JSON array of short strings. No markdown, no explanation.
    If truly nothing personal was mentioned, return: []"""

    def __init__(self, model, api_key, reasoning_effort, max_tokens=1000, temperature=0.7, top_p=1.0, stream=False):
        self.model = model
        self.api_key = api_key
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.stream = stream
        self.url = "https://integrate.api.nvidia.com/v1/chat/completions"
        self.history = []
        self.reasoning_effort = reasoning_effort
        self.memory = {}  # holds the memory blob injected from frontend

    # ── Memory ──────────────────────────────────────────────────────────────

    def load_memory(self, memory_blob: dict):
        """Called on session start with the blob from localStorage."""
        self.memory = memory_blob or {}

    def _build_system_prompt(self) -> str:
        """Injects memory facts into Nagisa's system prompt if available."""
        prompt = self.BASE_SYSTEM_PROMPT

        facts = self.memory.get("facts", [])
        user_name = self.memory.get("user_name", "darling")
        relationship_level = self.memory.get("relationship_level", 1)

        if user_name and user_name.lower() != "darling":
            prompt += f"\n- The user's real name is {user_name}, but still call them ダーリン affectionately."

        if facts:
            facts_str = "\n  ".join(f"- {f}" for f in facts)
            prompt += f"\n\nThings you remember about darling (reference naturally when relevant, don't list them all at once):\n  {facts_str}"

        if relationship_level >= 3:
            prompt += "\n\nYou are very close and comfortable with darling. Be warmer and more affectionate than usual."

        return prompt

    def extract_memory_facts(self, last_n: int = 6) -> list[str]:
        """
        Asks the LLM to extract new facts from the last N exchanges.
        Returns a list of fact strings. Called by /summarize-memory route.
        """
        if not self.history:
            return []

        # Build a plain text transcript of the last N exchanges
        recent = self.history[-last_n:]
        transcript = ""
        for user_msg, assistant_msg in recent:
            transcript += f"User: {user_msg}\n"
            # assistant_msg is a JSON string — extract EN part for readability
            try:
                parsed = json.loads(assistant_msg)
                transcript += f"Nagisa: {parsed.get('EN', assistant_msg)}\n"
            except Exception:
                transcript += f"Nagisa: {assistant_msg}\n"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.MEMORY_EXTRACT_PROMPT},
                {"role": "user", "content": f"Extract facts about the user from this conversation:\n\n{transcript}"}
            ],
            "max_tokens": 300,
            "temperature": 0.3,  # low temp for factual extraction
            "top_p": 1.0,
            "stream": False,
        }

        try:
            response = requests.post(self.url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            raw = response.json()["choices"][0]["message"]["content"]
            new_facts = json.loads(raw)
            return new_facts if isinstance(new_facts, list) else []
        except Exception as e:
            print(f"Memory extraction failed: {e}")
            return []

    # ── Core chat ────────────────────────────────────────────────────────────

    async def generate_response_async(self, text=None, image_path=None):
        """Async version for SSE streaming endpoint."""
        image_b64 = None
        if image_path:
            try:
                with open(image_path, "rb") as f:
                    image_b64 = base64.b64encode(f.read()).decode("utf-8")
            except Exception as e:
                return f"Error processing image: {str(e)}"

        messages = [{"role": "system", "content": self._build_system_prompt()}]

        for user_msg, assistant_msg in self.history:
            messages.append({"role": "user", "content": user_msg})
            messages.append({"role": "assistant", "content": assistant_msg})

        if image_b64:
            current_content = [
                {"type": "text",
                 "text": f"{text if text else 'What do you see?'}\n\nIMPORTANT: respond ONLY as Nagisa in JSON: {{\"JA\": \"日本語ダーリン\", \"EN\": \"English darling\"}}"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}
            ]
        else:
            current_content = text or ""

        messages.append({"role": "user", "content": current_content})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(self.url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        if "choices" in data and data["choices"]:
            assistant_reply = data["choices"][0]["message"]["content"]
            user_input_display = text or ""
            if image_b64:
                user_input_display += " [画像]" if user_input_display else "[画像]"
            self.history.append((user_input_display, assistant_reply))
            return assistant_reply

        return '{"EN": "Sorry darling!", "JA": "ごめんなさい。"}'
