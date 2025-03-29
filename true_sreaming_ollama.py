from typing import List, Union, Generator, Iterator
from schemas import OpenAIChatMessage
import requests
import json


class Pipeline:
    def __init__(self):
        # Optionally, you can set the id and name of the pipeline.
        # Best practice is to not specify the id so that it can be automatically inferred from the filename, so that users can install multiple versions of the same pipeline.
        # The identifier must be unique across all pipelines.
        # The identifier must be an alphanumeric string that can include underscores or hyphens. It cannot contain spaces, special characters, slashes, or backslashes.
        # self.id = "ollama_pipeline"
        self.name = "Ollama Pipeline"
        pass

    async def on_startup(self):
        # This function is called when the server is started.
        print(f"on_startup:{__name__}")
        pass

    async def on_shutdown(self):
        # This function is called when the server is stopped.
        print(f"on_shutdown:{__name__}")
        pass

    def pipe(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, Generator, Iterator]:
        # This is where you can add your custom pipelines like RAG.
        print(f"pipe:{__name__}")

        OLLAMA_BASE_URL = "http://ollama:11434"
        MODEL = "qwen2.5:latest "

        if "user" in body:
            print("######################################")
            print(f'# User: {body["user"]["name"]} ({body["user"]["id"]})')
            print(f"# Message: {user_message}")
            print("######################################")
        
        print(f"body: {body}\n=============")
        if user_message.startswith("Create a concise"):
            return "我是標題"

        try:
            payload = {
                "model": MODEL.strip(),
                "messages": messages, 
                "stream": body.get("stream", True)
            }

            r = requests.post(
                url=f"{OLLAMA_BASE_URL}/v1/chat/completions",
                json=payload,
                stream=payload["stream"]
            )

            r.raise_for_status()

            # 添加第二個消息請求，也使用流式響應
            second_messages = [{"role": "user", "content": "我剛剛前面聊天記錄說了啥?"}]
            second_payload = {
                "model": MODEL.strip(),
                "messages": second_messages,
                "stream": True  # 對於第二個請求，也使用流式響應
            }
            
            second_r = requests.post(
                url=f"{OLLAMA_BASE_URL}/v1/chat/completions",
                json=second_payload,
                stream=True
            )
            
            second_r.raise_for_status()
            
            # 將第二個響應的內容合併到第一個響應中
            if not payload["stream"]:
                first_response = r.json()
                # 如果第一個請求不是流式的，第二個請求也應該不是
                second_response = requests.post(
                    url=f"{OLLAMA_BASE_URL}/v1/chat/completions",
                    json={
                        "model": MODEL.strip(),
                        "messages": second_messages,
                        "stream": False
                    }
                ).json()
                
                # 將兩個響應合併
                first_response["second_response"] = second_response
                return first_response
            else:
                # 流式響應的處理方式
                def combined_response():
                    # 首先輸出第一個請求的所有響應
                    for line in r.iter_lines():
                        if line:
                            yield line
                    
                    # 添加一個分隔標記
                    yield b"\n\nSecond answer: "
                    
                    # 然後輸出第二個請求的所有響應
                    for line in second_r.iter_lines():
                        if line:
                            yield line
                
                return combined_response()

        except Exception as e:
            return f"Error: {e}"

