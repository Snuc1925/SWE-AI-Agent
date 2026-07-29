# import httpx

# class OpenAIClient:
#     def __init__(self, api_key: str, model_name: str = "gpt-4-mini"):
#         self.api_key = api_key
#         self.model_name = model_name
#         self.url = "https://api.openai.com/v1/chat/completions" 
#     async def call(self, system_prompt: str, user_prompt: str) -> str:
#         headers = {
#             "Authorization": f"Bearer {self.api_key}",
#             "Content-Type": "application/json"
#         }
#         payload = {
#             "model": self.model_name,
#             "messages": [
#                 {"role": "system", "content": system_prompt},
#                 {"role": "user", "content": user_prompt}
#             ],
#             "temperature": 0.1
#         }
        
#         async with httpx.AsyncClient() as client:
#             response = await client.post(self.url, headers=headers, json=payload, timeout=60.0)
#             result = response.json()
#             return result['choices'][0]['message']['content']

import httpx

class OpenAIClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.url = "https://api.openai.com/v1/chat/completions"

    async def call(self, system_prompt: str, user_prompt: str, model: str = "gpt-4o-mini") -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"} if "JSON" in system_prompt else None,
            "temperature": 0.1
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(self.url, headers=headers, json=payload, timeout=60.0)
            if response.status_code != 200:
                raise Exception(f"LLM Error: {response.text}")
            result = response.json()
            return result['choices'][0]['message']['content']