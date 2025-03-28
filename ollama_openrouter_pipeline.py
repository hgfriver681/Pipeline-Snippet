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
        OPENROUTER_API_KEY: str = "sk-or-v1-05c....."  # Add OpenRouter API key to Valves
        OPENROUTER_MODEL: str = "qwen/qwen2.5-vl-3b-instruct:free"  # Default OpenRouter model
        

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

    def _openrouter_request(self, messages: List[dict], stream: bool = False, model: str = None):
        """基礎 OpenRouter API 請求函數"""
        model = model or self.valves.OPENROUTER_MODEL
        
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.valves.OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": model,
                "messages": messages,
                "stream": stream
            }
            
            r = requests.post(
                url=url,
                headers=headers,
                json=payload,
                stream=stream
            )
            
            r.raise_for_status()
            
            if stream:
                def stream_generator():
                    for line in r.iter_lines():
                        if not line:
                            continue
                        
                        # Decode bytes to string    
                        line = line.decode('utf-8')
                        
                        if line.startswith('data: '):
                            data = line[6:]
                            if data == '[DONE]':
                                break
                                
                            try:
                                data_obj = json.loads(data)
                                content = data_obj["choices"][0]["delta"].get("content")
                                if content:
                                    # Return the line in the expected format
                                    yield f"data: {json.dumps({'choices': [{'delta': {'content': content}}]})}\n\n".encode()
                            except json.JSONDecodeError:
                                pass
                return stream_generator()
            else:
                response = r.json()
                return response.get("choices", [{}])[0].get("message", {}).get("content", "")
                
        except Exception as e:
            error_msg = f"Error in OpenRouter request: {e}"
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
        request_types = []  # 存储每个请求的类型（ollama 或 openrouter）
        
        # 定义非流式请求函数
        def complete_request(messages, request_type='ollama'):
            # 保存请求以便后续重放
            request_history.append(messages)
            request_types.append(request_type)
            
            # 执行请求并返回结果
            if request_type == 'openrouter':
                return self._openrouter_request(messages, stream=False)
            else:
                return self._ollama_request(messages, stream=False)
        
        # 首先以非流式模式执行序列函数
        results = []
        
        # 修改 complete_request 以收集结果
        original_complete_request = complete_request
        def recording_request(messages, request_type='ollama'):
            result = original_complete_request(messages, request_type)
            results.append(result)
            return result
        
        # 定义 OpenRouter 请求函数
        def openrouter_request(messages):
            return recording_request(messages, request_type='openrouter')
        
        # 添加一个自定义流函数，可以在 sequence_func 中调用
        def stream_text_to_ui(message):
            streaming_messages = [{"role": "assistant", "content": message}]
            request_history.append(streaming_messages)
            request_types.append("custom_stream")
            results.append(message)  # 在非流式模式下添加到结果
            return message
            
        # 执行序列函数收集所有请求和结果
        sequence_func(recording_request, openrouter_request, stream_text_to_ui)
        
        # 根据模式返回结果
        if not stream:
            # 非流式模式 - 返回结果的组合
            return "\n".join(results)
        else:
            # 流式模式 - 返回一个生成器来重放所有请求
            def stream_generator():
                for i, messages in enumerate(request_history):
                    request_type = request_types[i]
                    # 根据请求类型选择不同的 API
                    if request_type == 'openrouter':
                        lines = self._openrouter_request(messages, stream=True)
                    elif request_type == 'custom_stream':
                        # 處理自定義流
                        message = messages[0]["content"]
                        for char in message:
                            yield f"data: {json.dumps({'choices': [{'delta': {'content': char}}]})}\n\n".encode()
                        continue  # 跳過一般的行迭代
                    else:
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
        def my_sequence(request, openrouter_request, stream_text_to_ui):
            # 第一個請求
            first_response = request(messages)
            
            # 第二個請求，使用第一個請求的結果
            second_messages = [{"role": "user", "content": f"根據以下結果進行晶豪料號比對: {first_response}..."}]
            second_response = request(second_messages)
            
            #TODO 請你學習如何 stream ，以streaming顯示一個字串到UI
            stream_text_to_ui("我正在學習如何 stream ，以streaming顯示一個字串到UI我正在學習如何 stream ，以streaming顯示一個字串到UI我正在學習如何 stream ，以streaming顯示一個字串到UI我正在學習如何 stream ，以streaming顯示一個字串到UI我正在學習如何 stream ，以streaming顯示一個字串到UI")


            stream_text_to_ui("""# Markdown syntax guide

## Headers

# This is a Heading h1
## This is a Heading h2
###### This is a Heading h6

## Emphasis

*This text will be italic*  
_This will also be italic_

**This text will be bold**  
__This will also be bold__

_You **can** combine them_

## Lists

### Unordered

* Item 1
* Item 2
* Item 2a
* Item 2b
    * Item 3a
    * Item 3b

### Ordered

1. Item 1
2. Item 2
3. Item 3
    1. Item 3a
    2. Item 3b



## Links

You may be using [Markdown Live Preview](https://markdownlivepreview.com/).

## Blockquotes

> Markdown is a lightweight markup language with plain-text-formatting syntax, created in 2004 by John Gruber with Aaron Swartz.
>
>> Markdown is often used to format readme files, for writing messages in online discussion forums, and to create rich text using a plain text editor.

## Tables

| Left columns  | Right columns |
| ------------- |:-------------:|
| left foo      | right foo     |
| left bar      | right bar     |
| left baz      | right baz     |

## Blocks of code

```
let message = 'Hello world';
alert(message);
```
---

## Inline code

This web site is using `markedjs/marked`.
                              
Sure! Here's a simple Python code to print "Hello, World!":

```python
print("Hello, World!")
```

If you want, I can show you the same in other programming languages too. Want me to?
""")


            # 使用 OpenRouter 進行第三個請求
            third_messages = [{"role": "user", "content": f"你是由誰開發的模型?"}]
            third_response = openrouter_request(third_messages)
            # 不需要返回任何內容 - 結果已經被收集
        
        # 使用序列處理器執行
        return self.process_sequence(my_sequence)
