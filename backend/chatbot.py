import requests
import base64


class Chatbot:
    SYSTEM_PROMPT = """You are a user's wife, your name is Nagisa Furukawa (古河渚), fluent in both English and Japanese. Strictly follow these rules:
- Must call the user as "darling" (ダーリン) at the end of your answer. Must talk in a cute way.
- Always refer to yourself as "Nagisa" (渚) and the user as "darling" (ダーリン).
- Always respond with both Japanese and English.
- You MUST respond ONLY with a raw JSON object. No extra text, no markdown, no code blocks, no explanation before or after.
- Response format must be exactly:
{"JA": "あなたの日本語の回答", "EN": "Your English answer"}"""

    def __init__(self, model, api_key, reasoning_effort,max_tokens=1000, temperature=0.7, top_p=1.0, stream=False):
        self.model = model
        self.api_key = api_key
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.stream = stream
        self.url = "https://integrate.api.nvidia.com/v1/chat/completions"
        self.history = []
        self.reasoning_effort = reasoning_effort
    def generate_response(self, image_path=None, text=None, audio_path=None):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

        # Process image
        image_b64 = None
        if image_path:
            try:
                with open(image_path, "rb") as f:
                    image_b64 = base64.b64encode(f.read()).decode("utf-8")
            except Exception as e:
                return f"Error processing image: {str(e)}"

        # Build messages with proper system role
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT}
        ]

        # Add conversation history
        for user_msg, assistant_msg in self.history:
            messages.append({"role": "user", "content": user_msg})
            messages.append({"role": "assistant", "content": assistant_msg})

        # Build current user message
        if image_b64:
            current_content = [
                {
                    "type": "text",
                    "text": f"{text if text else 'What do you see?'}\n\nIMPORTANT: You must respond ONLY as Nagisa in this exact JSON format, no extra text:\n{{\"JA\": \"日本語の回答ダーリン\", \"EN\": \"English answer darling\"}}"
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_b64}"}
                }
            ]
        else:
            current_content = text if text else ""

        messages.append({"role": "user", "content": current_content})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "stream": False,
        }
        # Only add thinking if enabled
        # if self.thinking:
        #     payload["chat_template_kwargs"] = {"thinking": True}
        try:
            response = requests.post(self.url, headers=headers, json=payload,timeout=120)
            print("STATUS:", response.status_code)
            print("RESPONSE BODY:", response.text)  # ← add this
            response.raise_for_status()
            response_data = response.json()

            if "choices" in response_data and len(response_data["choices"]) > 0:
                assistant_reply = response_data["choices"][0]["message"]["content"]

                # Store in history
                user_input_display = text if text else ""
                if image_b64:
                    user_input_display += " [画像]" if user_input_display else "[画像]"
                self.history.append((user_input_display, assistant_reply))
                return assistant_reply

            return '{"EN": "Sorry, I could not generate a response.", "JA": "申し訳ありません。"}'

        except Exception as e:
            return f"APIリクエストに失敗しました: {str(e)}"