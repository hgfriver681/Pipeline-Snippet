from typing import List, Union, Generator, Iterator
from schemas import OpenAIChatMessage
import requests
from pydantic import BaseModel
import json

class Pipeline:

    class Valves(BaseModel):
        OLLAMA_MODEL: str = "qwen2.5:latest"
        STREAM: bool = True  # Add streaming control to Valves
        OLLAMA_BASE_URL: str = "http://ollama:11434"  # Base URL for Ollama API
        

    def __init__(self):
        # Optionally, you can set the id and name of the pipeline.
        # Best practice is to not specify the id so that it can be automatically inferred from the filename, so that users can install multiple versions of the same pipeline.
        # The identifier must be unique across all pipelines.
        # The identifier must be an alphanumeric string that can include underscores or hyphens. It cannot contain spaces, special characters, slashes, or backslashes.
        # self.id = "ollama_pipeline"
        self.name = "Ollama Pipeline"
        self.valves = self.Valves()

    async def on_startup(self):
        # This function is called when the server is started.
        print(f"on_startup:{__name__}")
        pass

    async def on_shutdown(self):
        # This function is called when the server is stopped.
        print(f"on_shutdown:{__name__}")
        pass

    def _ollama_request(self, messages: List[dict], stream: bool = False, model: str = None):
        """基礎 Ollama API 請求函數"""
        model = model or self.valves.OLLAMA_MODEL
        
        try:
            payload = {
                "model": model,
                "messages": messages,
                "stream": stream
            }
            
            r = requests.post(
                url=f"{self.valves.OLLAMA_BASE_URL}/v1/chat/completions",
                json=payload,
                stream=stream
            )
            
            r.raise_for_status()
            
            if stream:
                return r.iter_lines()
            else:
                response = r.json()
                return response.get("choices", [{}])[0].get("message", {}).get("content", "")
                
        except Exception as e:
            error_msg = f"Error: {e}"
            if stream:
                error_notification = {
                    "id": "error-chunk",
                    "object": "chat.completion.chunk",
                    "choices": [{
                        "delta": {
                            "content": error_msg
                        },
                        "index": 0,
                        "finish_reason": "error"
                    }]
                }
                # 創建一個迭代器來模擬流式回應
                def error_stream():
                    yield f"data: {json.dumps(error_notification)}\n\n".encode()
                return error_stream()
            else:
                return error_msg

    def process_sequence(self, sequence_func, stream: bool = None):
        """
        抽象的请求序列处理器 - 更简单的实现
        
        sequence_func: 一个函数，它定义了请求的执行顺序
        stream: 是否使用流式模式，默认使用 valves 中的设置
        """
        if stream is None:
            stream = self.valves.STREAM
        
        # 存储请求历史
        request_history = []
        
        # 定义非流式请求函数
        def complete_request(messages):
            # 保存请求以便后续重放
            request_history.append(messages)
            
            # 执行请求并返回结果
            return self._ollama_request(messages, stream=False)
        
        # 首先以非流式模式执行序列函数
        results = []
        
        # 修改 complete_request 以收集结果
        original_complete_request = complete_request
        def recording_request(messages):
            result = original_complete_request(messages)
            results.append(result)
            return result
        
        # 执行序列函数收集所有请求和结果
        sequence_func(recording_request)
        
        # 根据模式返回结果
        if not stream:
            # 非流式模式 - 返回结果的组合
            return "\n".join(results)
        else:
            # 流式模式 - 返回一个生成器来重放所有请求
            def stream_generator():
                for messages in request_history:
                    # 重新执行每个请求，这次使用流式模式
                    lines = self._ollama_request(messages, stream=True)
                    for line in lines:
                        if line:
                            yield line
            
            return stream_generator()

    def pipe(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, Generator, Iterator]:
        print(f"pipe:{__name__}")

        if "user" in body:
            print("######################################")
            print(f'# User: {body["user"]["name"]} ({body["user"]["id"]})')
            print(f"# Message: {user_message}")
            print("######################################")

        # 定義請求序列 - 完全不需要關心流式/非流式實現
        def my_sequence(request):
            # 第一個請求
            first_response = request(messages)
            

            # 第二個請求，使用第一個請求的結果
            second_messages = [{"role": "user", "content": f"根據以下結果進行晶豪料號比對: {first_response[:100]}..."}]
            second_response = request(second_messages)
            
            # 不需要返回任何內容 - 結果已經被收集
        
        # 使用序列處理器執行
        return self.process_sequence(my_sequence)
