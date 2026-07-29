import os
import requests
from typing import List, Dict, Any
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

MANAGEMENT_API_URL = "http://skill-management:8001"

def fetch_skill_tools(api_key: str, mock_mode: bool = False) -> List[StructuredTool]:
    response = requests.get(f"{MANAGEMENT_API_URL}/skills/tools")
    response.raise_for_status()
    skill_defs = response.json()
    
    tools = []
    for s_def in skill_defs:
        skill_id = s_def["skill_id"]
        name = s_def["name"]
        description = s_def["description"]
        
        # We must create a function that binds the skill_id, api_key, etc.
        def create_skill_executor(sid=skill_id):
            def execute_skill(**kwargs):
                payload = {
                    "input": kwargs,
                    "mock_mode": mock_mode,
                    "api_key": api_key
                }
                res = requests.post(f"{MANAGEMENT_API_URL}/skills/{sid}/execute", json=payload)
                if res.status_code != 200:
                    return f"Error executing skill: {res.text}"
                return res.json().get("output", res.text)
            return execute_skill
            
        tool = StructuredTool.from_function(
            func=create_skill_executor(),
            name=name.replace("-", "_").replace(" ", "_"), # Langchain tool names can't have spaces or dashes usually, actually dashes are sometimes ok, let's replace them
            description=description,
        )
        tools.append(tool)
        
    return tools

def run_agent_chat(messages_dict: List[Dict[str, str]], model_name: str, api_key: str):
    api_key = api_key.strip() if isinstance(api_key, str) else api_key
    # Fetch tools
    tools = fetch_skill_tools(api_key=api_key, mock_mode=False)
    
    if model_name.startswith("deepseek"):
        base_url = "https://api.deepseek.com/v1"
    else:
        base_url = "https://api.openai.com/v1" # Default OpenAI
        
    llm_api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not llm_api_key:
        raise ValueError("Missing API key: pass api_key with your request or set OPENAI_API_KEY in the backend environment.")

    llm = ChatOpenAI(
        model=model_name,
        api_key=llm_api_key,
        base_url=base_url,
        temperature=0.1
    )
    
    agent = create_react_agent(llm, tools)
    
    # Convert messages
    langchain_messages = []
    for msg in messages_dict:
        if msg["role"] == "user":
            langchain_messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            langchain_messages.append(AIMessage(content=msg["content"]))
        elif msg["role"] == "system":
            langchain_messages.append(SystemMessage(content=msg["content"]))
            
    system_prompt = SystemMessage(content="You are a helpful AI assistant with access to SWE skills. Use the provided tools to fulfill the user's request. If you encounter an error, explain it to the user.")
    if not langchain_messages or not isinstance(langchain_messages[0], SystemMessage):
        langchain_messages.insert(0, system_prompt)
        
    result = agent.invoke({"messages": langchain_messages})
    
    return [
        {"role": m.type, "content": m.content}
        for m in result["messages"]
    ]
