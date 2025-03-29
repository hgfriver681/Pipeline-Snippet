from typing import List, Union, Generator, Iterator
from schemas import OpenAIChatMessage
import requests
import json

# Import the selector function
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'files'))
from selector import get_filtered_products
from duckduckgo_search import DDGS
import random
import time
import re

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

    def bulk_duckduckgo_search(self, queries, max_results=5, region='tw', max_retries=3):
        """批量執行 DuckDuckGo 搜尋，添加簡單重試機制"""
        all_results = {}
        
        for query in queries:
            for retry in range(max_retries):
                try:
                    # 如果是重試，添加等待時間
                    if retry > 0:
                        wait_time = 2 * retry
                        print(f"Retry #{retry} for '{query}' after {wait_time}s")
                        time.sleep(wait_time)
                    
                    # 每次查詢創建新的 DDGS 會話
                    with DDGS() as ddgs:
                        results = [r for r in ddgs.text(query, max_results=max_results, region=region)]
                        print(f"Success: found {len(results)} results for '{query}'")
                        all_results[query] = results
                        # Add random wait time between 0 and 0.5 seconds
                        random_time = random.uniform(0, 0.5)
                        time.sleep(random_time)
                        # 成功後跳出重試循環
                        break
                except Exception as e:
                    print(f"Error (attempt {retry+1}/{max_retries}) searching for '{query}': {e}")
                    # 如果已重試到最大次數仍失敗
                    if retry == max_retries - 1:
                        print(f"All {max_retries} attempts failed for '{query}'")
                        all_results[query] = []
        
        return all_results
    
    def extract_function_call(self, response_text):
        """從 LLM 回應中提取函數呼叫參數"""
        pattern = r'<get_filtered_products>(.*?)</get_filtered_products>'
        matches = re.findall(pattern, response_text, re.DOTALL)
        
        if not matches:
            return {}
        
        function_text = matches[-1].strip()
        params = {}
        param_pattern = r'(\w+)=["\'](.*?)["\']'
        param_matches = re.findall(param_pattern, function_text)
        
        for param_name, param_value in param_matches:
            params[param_name] = param_value
        
        return params
    
    def pipe(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, Generator, Iterator]:
        # This is where you can add your custom pipelines like RAG.
        print(f"pipe:{__name__}")

        OLLAMA_BASE_URL = "http://ollama:11434"
        # MODEL = "qwen2.5:latest"
        MODEL = "qwen2.5-32b-20k:latest"

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

                # Step 1: Stream initial message
                other_company_pn = user_message.strip()
                yield f"## Processing part number: {other_company_pn}\n\nPerforming web search to gather information..."
                
                # Step 2: Perform DuckDuckGo searches
                search_queries = [
                    f"{other_company_pn} ddr type",
                    f"{other_company_pn} operation voltage",
                    f"{other_company_pn} density",
                    f"{other_company_pn} operating temperature",
                    f"{other_company_pn} max frequency"
                ]
                
                # Modify the method to track and yield search progress
                yield "\n\n### Starting web searches...\n"
                
                # Instead of directly calling bulk_duckduckgo_search, we'll implement the search logic here
                # to be able to yield status updates
                search_results = {}
                max_results = 5
                region = 'tw'
                max_retries = 3
                
                for query in search_queries:
                    yield f"\n- Searching for: '{query}'"
                    
                    for retry in range(max_retries):
                        try:
                            # If retry, add waiting time
                            if retry > 0:
                                wait_time = 2 * retry
                                yield f"\n  - Retry #{retry} for '{query}' after {wait_time}s"
                                time.sleep(wait_time)
                            
                            # Create new DDGS session for each query
                            with DDGS() as ddgs:
                                results = [r for r in ddgs.text(query, max_results=max_results, region=region)]
                                
                                yield f"\n  - ✅ Found {len(results)} results for '{query}'"
                                search_results[query] = results
                                
                                # Add random wait time between 0 and 0.5 seconds
                                random_time = random.uniform(0, 0.5)
                                time.sleep(random_time)
                                break
                        except Exception as e:
                            yield f"\n  - ❌ Error (attempt {retry+1}/{max_retries}) searching for '{query}': {str(e)}"
                            # If already retried to maximum times and still failed
                            if retry == max_retries - 1:
                                yield f"\n  - ⚠️ All {max_retries} attempts failed for '{query}'"
                                search_results[query] = []
                
                yield "\n\n### Search completed. Analyzing information...\n\n"


                result_ddr_type = search_results[search_queries[0]]
                result_operation_voltage = search_results[search_queries[1]]
                result_density = search_results[search_queries[2]]
                result_operating_temperature = search_results[search_queries[3]]
                result_max_frequency = search_results[search_queries[4]]
                # Combine all search results
                result_duckduckgo = result_ddr_type + result_operation_voltage + result_density + result_operating_temperature + result_max_frequency
            

                # Step 3: Use OpenRouter API to summarize search results
                summarize_prompt = f"User query: {other_company_pn}\n\n\nGoogle search result: {result_duckduckgo}\n\nSummarize the google search result to satisfy the user query in a detailed way. Do not include any other knowledge, just the google search result. Speed/Frequency should show in Hz, not bps."
                summary_messages = [{"role": "user", "content": summarize_prompt}]
                payload = {
                    "model": MODEL.strip(),
                    "messages": summary_messages, 
                    "stream": True
                }
                r = requests.post(
                    url=f"{OLLAMA_BASE_URL}/v1/chat/completions",
                    json=payload,
                    stream=payload["stream"]
                )
                r.raise_for_status()

                # Collect and process first response
                result_summary = ""

                # Process first response and collect content
                for chunk in self.process_llm_response(r):
                    yield chunk
                    
                    # Extract content from chunk
                    content = self.extract_content_from_chunk(chunk)
                    if content:
                        result_summary += content
                
                # Print the complete first response content
                yield f"\n\n### Summary of Google search results:\n\n{result_summary}\n\n"
                #------------------------------------------
                
                # Step 4: Extract function parameters for get_filtered_products
                extract_params_prompt = f"""
You are an AI assistant specialized in parsing memory component specifications and translating them into function parameters. Your task is to:
1. Read and understand the Google search results containing memory specifications
2. Extract key parameters like DDR type, voltage, density, I/O configuration, and addressing
3. Map these specifications to the appropriate arguments for the get_filtered_products function

user query for google search: {other_company_pn}

google search result: {result_summary}

the argument for the selector function get_filtered_products is:
get_filtered_products(
    type_of_ddr="SDRAM", # can be one of the following: "SDRAM", "DDR SDRAM", "DDR II SDRAM", "DDR3 SDRAM or DDR3(L) SDRAM", "DDR4 SDRAM", "PSRAM", "Mobile SDRAM", "Mobile DDR SDRAM", "LPDDR SDRAM", "LPDDR2 SDRAM", "LPDDR3 SDRAM", "LPDDR4X SDRAM or LPDDR4/LPDDR4X SDRAM"
    Operation_Voltage="D", # can be one of the following: "L", "S", "F", "T", "U", "D", "Y", "Z"
    Density="64Mb" # can be one of the following: "8Mb", "16Mb", "32Mb", "64Mb", "128Mb", "256Mb", "512Mb", "1Gb", "2Gb", "4Gb", "8Gb", "16Gb"
)

Operation Voltage argument explanation:
L: 3.3V 
S: 2.5V
F: 1.5V
T: 1.35V
U: 1.2V
D: 1.8V (VDD1=1.8V, VDD2=VDDQ=1.2V)
Y: 1.8V (VDD1=1.8V, VDD2=VDDQ=1.1V)
Z: 1.8V (VDD1=1.8V, VDD2=1.1V, VDDQ=0.6V)

If the google search result does not contain the information of some arguments, please just don't fill in the argument.

Example get_filtered_products:
<get_filtered_products>
get_filtered_products(
    type_of_ddr="DDR SDRAM",
    Operation_Voltage="D",
)
</get_filtered_products>

You first print chain of thought, then print the get_filtered_products function.
the printed get_filtered_products function should be between the tag <get_filtered_products> and </get_filtered_products>"""
                params_messages = [{"role": "user", "content": extract_params_prompt}]
                payload = {
                    "model": MODEL.strip(),
                    "messages": params_messages, 
                    "stream": True
                }
                r = requests.post(
                    url=f"{OLLAMA_BASE_URL}/v1/chat/completions",
                    json=payload,
                    stream=payload["stream"]
                )
                r.raise_for_status()

                # Collect and process first response
                llm_params_response = ""

                # Process first response and collect content
                for chunk in self.process_llm_response(r):
                    yield chunk
                    
                    # Extract content from chunk
                    content = self.extract_content_from_chunk(chunk)
                    if content:
                        llm_params_response += content
                
                # Print the complete first response content
                #yield f"\n\n### Summary of Google search results:\n\n{llm_params_response}\n\n"
                
                # Extract parameters from the LLM response
                print(f"llm_params_response: {llm_params_response}")
                filtered_params = self.extract_function_call(llm_params_response)

                filtered_products = get_filtered_products(**filtered_params)
                print(f"filtered_products: {filtered_products}")
                yield f"\n\n### Found {len(filtered_products)} potential matching products\n\nDecoding product information...\n\n"
 
                #------------------------------------------

                decode_prompt = f"""This is the golden target to be matched:
{result_summary}

This is the candidate products:
{filtered_products}

#### DRAM Naming Pattern
`<Category> <Product Family> <Operation Voltage> <Density> <I/O Pin Number> <Address>`

DRAM_Naming_Rule:
  Category:
    - Description: "Category identifier for memory"
    - Values:
        - M: "Fixed category for DRAM products"

  Product_Family:
    - Description: "Defines the DRAM type and generation"
    - Values:
      - 12: "SDRAM"
      - 52: "LP SDRAM"
      - 13: "DDR SDRAM"
      - 53: "LPDDR SDRAM"
      - 14: "DDR2 SDRAM"
      - 54: "LPDDR2 SDRAM"
      - 15: "DDR3 SDRAM"
      - 55: "LPDDR3 SDRAM"
      - 16: "DDR4 SDRAM"
      - 56 "LPDDR4/4X SDRAM"

  Operation_Voltage:
    - Description: "Defines the operating voltage of the DRAM"
    - Values:
      - L: "3.3V"
      - S: "2.5V"
      - F: "1.5V"
      - T: "1.35V"
      - U: "1.2V"
      - D: "1.8V (VDD=1.8V, VDD2=VDDQ=1.2V)"
      - Y: "1.8V (VDD=1.8V, VDD2=VDDQ=1.1V)"
      - Z: "1.8V (VDD=1.8V, VDD2=1.1V, VDDQ=0.6V)"

  Density:
    - Description: "Defines the storage density of the DRAM"
    - Values:
      - "8": "8Mb"
      - "16": "16Mb"
      - "32": "32Mb"
      - "64": "64Mb"
      - "128": "128Mb"
      - "256": "256Mb"
      - "512": "512Mb"
      - "1G": "1Gb"
      - "2G": "2Gb"
      - "4G": "4Gb"
      - "8G": "8Gb"
      - "16G": "16Gb"

  I/O_Pin_Number:
    - Description: "Defines the number of I/O pins for the DRAM"
    - Values:
      - "8": "x8"
      - "16": "x16"
      - "32": "x32"

  Address: 
    - Description: "Defines the addressable memory of the DRAM"
    - Values:
      - "512": "512Kb"
      - "1": "1Mb"
      - "2": "2Mb"
      - "4": "4Mb"
      - "8": "8Mb"
      - "16": "16Mb"
      - "32": "32Mb"
      - "64": "64Mb"
      - "128": "128Mb"
      - "256": "256Mb"
      - "512": "512Mb"

Please decode the candidate products by the DRAM Naming Pattern, and also include all the features of the candidate products.

Show the decoded result and all the features of the candidate product ids in json format.
"""
                decode_messages = [{"role": "user", "content": decode_prompt}]
                payload = {
                    "model": MODEL.strip(),
                    "messages": decode_messages, 
                    "stream": True
                }
                r = requests.post(
                    url=f"{OLLAMA_BASE_URL}/v1/chat/completions",
                    json=payload,
                    stream=payload["stream"]
                )
                r.raise_for_status()

                # Collect and process first response
                decode_result = ""

                # Process first response and collect content
                for chunk in self.process_llm_response(r):
                    yield chunk
                    
                    # Extract content from chunk
                    content = self.extract_content_from_chunk(chunk)
                    if content:
                        decode_result += content

                #------------------------------------------

                # Step 6: Find best match
                match_prompt = f"""You are an AI assistant specialized in matching memory component specifications to golden target. Your task is to:
1. Read and understand the golden target to be matched
2. Read and understand the decoded result and all the features of the candidate products
3. Match the golden target with the candidate products based on the features

Original user query for golden target: <query>{other_company_pn}</query>

This is the golden target's description. The golden target is the product that the user wants to match:
<golden_target_description>{result_summary}</golden_target_description>

And this is the decoded result and all the features of the candidate products:
<candidate>{decode_result}</candidate>

Some rules you should know:
- If the golden target's description says that '533 MHz clock speed,' it means that the golden target's clock max frequency is 533 MHz.
- If the golden target's description says that it is 0°C to 85°C, you can select candidate products's operation temperature range: 0°C to 85°C, or can be wider: 0°C to 95°C, but you cannot select: -40°C to 95°C as the Best Match.
- Only select the product ID(s) that fully meet the golden target's required max frequency.
- 1600 MHz is equal to 1.6 GHz.

Show me a markdown table with ✅ or ❌ compared with golden target for every single feature for each candidate product.
In each table cell, please first tell reason and then tell the result ✅ or ❌

And then for the best match part_number in the table, analyze the reason and tell me the best match product_id under the part_number"""
            
                match_messages = [{"role": "user", "content": match_prompt}]
                payload = {
                    "model": MODEL.strip(),
                    "messages": match_messages, 
                    "stream": True
                }
                r = requests.post(
                    url=f"{OLLAMA_BASE_URL}/v1/chat/completions",
                    json=payload,
                    stream=payload["stream"]
                )
                r.raise_for_status()

                # Collect and process first response
                final_match_result = ""

                # Process first response and collect content
                for chunk in self.process_llm_response(r):
                    yield chunk
                    
                    # Extract content from chunk
                    content = self.extract_content_from_chunk(chunk)
                    if content:
                        final_match_result += content


                


            
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
    
