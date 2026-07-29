from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from services.skill_testing.state import AgentState
# Import app = workflow.compile() từ file pipeline của bạn

app = FastAPI(title="AG2 Orchestrator API")

class UserRequest(BaseModel):
    code: str
    stacktrace: str
    message: str

@app.post("/api/v1/agent/run")
async def run_agent_workflow(request: UserRequest):
    initial_state = AgentState(
        user_context={
            "code": request.code,
            "stacktrace": request.stacktrace,
            "message": request.message
        }
    )
    
    # Kích hoạt đồ thị LangGraph chạy ngầm thực tế
    try:
        final_state = await app_langgraph.ainvoke(initial_state)
        return {
            "status": "COMPLETED",
            "final_answer": final_state.get("final_answer"),
            "steps_taken": final_state.get("step_count"),
            "history": final_state.get("history") # Gửi lịch sử chạy để FE hiển thị logs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# from __future__ import annotations

# import os
# import logging
# from contextlib import asynccontextmanager
# from typing import Optional, List, Dict, Any

# from fastapi import FastAPI, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel

# # Import logic cốt lõi của Agent
# from services.skill_testing.core.llm_client import OpenAIClient
# from services.skill_testing.core.registry import semantic_registry
# from services.skill_testing.client import SkillManagementClient
# from services.skill_testing.orchestrator import orchestrate_task, create_agent_graph

# # Thiết lập log để dễ debug trong Docker
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# # --- SCHEMA ĐẦU VÀO ---
# class TaskRequest(BaseModel):
#     code: str
#     stacktrace: Optional[str] = ""
#     message: str
#     api_key: str
#     model: str = "gpt-4o-mini"

# # --- CẤU HÌNH APP ---
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     """
#     Khởi tạo hệ thống: Fetch skill từ Manager và build Vector Index.
#     Dùng lifespan thay cho on_event('startup') vì đây là chuẩn mới của FastAPI.
#     """
#     # Lấy URL của management từ biến môi trường (Docker) hoặc localhost
#     mgmt_url = os.getenv("MANAGEMENT_URL", "http://127.0.0.1:8001")
#     client = SkillManagementClient(base_url=mgmt_url)
    
#     try:
#         logger.info(f"Connecting to Skill Management at {mgmt_url}...")
#         skills = await client.fetch_all_skills()
        
#         # Xây dựng bộ não Semantic Search trong RAM
#         semantic_registry.build_index(skills)
#         logger.info(f"✅ Startup complete: Indexed {len(skills)} skills.")
#     except Exception as e:
#         logger.error(f"❌ Startup failed to sync skills: {str(e)}")
#     finally:
#         await client.close()
#     yield

# app = FastAPI(
#     title="AI Software Engineering Agent - Testing Service", 
#     version="2.0.0", 
#     lifespan=lifespan
# )

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # --- ENDPOINTS ---

# @app.get("/health")
# async def health_check():
#     return {"status": "healthy", "skills_loaded": len(semantic_registry.all_skills())}

# @app.post("/orchestrate")
# async def orchestrate_endpoint(request: TaskRequest):
#     """
#     Endpoint chính để chạy Agent giải quyết lỗi code.
#     """
#     try:
#         # 1. Khởi tạo LLM Client (Dùng API Key người dùng gửi lên)
#         model_client = OpenAIClient(api_key=request.api_key)
        
#         # 2. Khởi tạo Skill Client để gọi thực thi skill bên Management
#         mgmt_url = os.getenv("MANAGEMENT_URL", "http://skill-management:8001")
#         skill_client = SkillManagementClient(base_url=mgmt_url)
        
#         # 3. Chạy Orchestrator (LangGraph Workflow)
#         # model_dump() dành cho Pydantic v2
#         result = await orchestrate_task(request.model_dump(), model_client, skill_client)
        
#         return result
#     except Exception as e:
#         logger.error(f"Orchestration Error: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))

# @app.get("/graph-image")
# def get_graph():
#     """
#     Trả về cấu trúc đồ thị Agent dưới dạng Mermaid để debug.
#     """
#     try:
#         graph_app = create_agent_graph()
#         return {"mermaid": graph_app.get_graph().draw_mermaid()}
#     except Exception as e:
#         return {"error": str(e)}