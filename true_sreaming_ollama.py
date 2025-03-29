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
  

            def combined_response():
                #--------------------- first start ---------------------
                payload = {
                    "model": MODEL.strip(),
                    "messages": messages, 
                    "stream": True
                }

                r = requests.post(
                    url=f"{OLLAMA_BASE_URL}/v1/chat/completions",
                    json=payload,
                    stream=payload["stream"]
                )

                r.raise_for_status()


                # Collect and process first response
                first_response_content = ""
                
                # Process first response and collect content
                for chunk in self.process_llm_response(r):
                    yield chunk
                    
                    # Extract content from chunk
                    content = self.extract_content_from_chunk(chunk)
                    if content:
                        first_response_content += content
                
                # Print the complete first response content
                print("First response complete content:", first_response_content)

                #--------------------- first end ---------------------
                
                # 顯示字串在UI (注意: 顯示的字串會含在聊天記錄中)
                yield """\n\n## 注意: 我是一段要被顯示在UI上的字串!!!我會含在聊天記錄中\n\n""" # 記得\n\n 要加在字串後面, 否則 markdown 語法會傳到後面字串
                yield "\n\n### Second answer:\n\n"
                yield "\n\n River is 24 years old\n\n"
                
                #--------------------- second start ---------------------
                second_messages = [{"role": "user", "content": f"{first_response_content}\n\n以上说了啥?"}]

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

                second_response_content = ""
                
                # Process first response and collect content
                for chunk in self.process_llm_response(second_r):
                    yield chunk
                    
                    # Extract content from chunk
                    content = self.extract_content_from_chunk(chunk)
                    if content:
                        second_response_content += content
                
                # Print the complete first response content
                print("Second response complete content:", second_response_content)
                #--------------------- second end ---------------------
            
            return combined_response()
        
        except Exception as e:
            return f"Error: {e}"
    
    def process_llm_response(self, response):
        """Process a streaming LLM response and yield each chunk."""
        for line in response.iter_lines():
            if line:
                yield line
    
    def extract_content_from_chunk(self, chunk):
        """Extract text content from a response chunk."""
        try:
            data = json.loads(chunk.decode('utf-8').replace('data: ', ''))
            if 'choices' in data and len(data['choices']) > 0:
                if 'delta' in data['choices'][0] and 'content' in data['choices'][0]['delta']:
                    return data['choices'][0]['delta']['content']
        except:
            pass
        return ""
    
