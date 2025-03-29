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

            # Handle response based on streaming mode
            if not payload["stream"]:
                # For non-streaming requests, get the complete response
                first_response = r.json()
                print("First response complete:", first_response)
                
                # Make second request after first is complete
                second_messages = [{"role": "user", "content": "我剛剛前面聊天記錄說了啥?"}]
                second_payload = {
                    "model": MODEL.strip(),
                    "messages": second_messages,
                    "stream": False
                }
                
                second_response = requests.post(
                    url=f"{OLLAMA_BASE_URL}/v1/chat/completions",
                    json=second_payload
                ).json()
                
                # Combine responses
                first_response["second_response"] = second_response
                return first_response
            else:
                # For streaming requests
                def combined_response():
                    # Collect all content from first response
                    first_response_content = ""
                    
                    # Process and yield first response
                    for line in r.iter_lines():
                        if line:
                            yield line
                            
                            # Try to extract the content to build complete response
                            try:
                                data = json.loads(line.decode('utf-8').replace('data: ', ''))
                                if 'choices' in data and len(data['choices']) > 0:
                                    if 'delta' in data['choices'][0] and 'content' in data['choices'][0]['delta']:
                                        first_response_content += data['choices'][0]['delta']['content']
                            except:
                                pass
                    
                    # Print the complete first response content
                    print("First response complete content:", first_response_content)
                    
                    # Make second request after first is complete
                    second_messages = [{"role": "user", "content": f"{first_response_content}\n\n以上說了啥?"}]
                    second_payload = {
                        "model": MODEL.strip(),
                        "messages": second_messages,
                        "stream": True
                    }
                    
                    second_r = requests.post(
                        url=f"{OLLAMA_BASE_URL}/v1/chat/completions",
                        json=second_payload,
                        stream=True
                    )
                    
                    second_r.raise_for_status()
                    
                    # Add a separator between responses
                    yield b"\n\nSecond answer: "
                    
                    # Process and yield second response
                    for line in second_r.iter_lines():
                        if line:
                            yield line
                
                return combined_response()
        
        except Exception as e:
            return f"Error: {e}"
