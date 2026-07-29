# from asyncio.log import logger

# import httpx
# from typing import Dict, Any, List

# from shared.schemas import SkillRead

# class SkillManagementClient:
#     def __init__(self, base_url: str = "http://localhost:8000"):
#         self.base_url = base_url
#         self.client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)

#     async def fetch_all_skills(self) -> List[SkillRead]:
#         try:
#             response = await self.client.get("/api/v1/skills")
#             response.raise_for_status()
#             data = response.json()
#             if isinstance(data, dict):
#                 items = data.get("items", data)
#             else:
#                 items = data
#             return [SkillRead(**item) for item in items]
#         except httpx.HTTPStatusError as e:
#             logger.error(f"Lỗi API từ Skill Management: {e.response.status_code}")
#             raise
#         except Exception as e:
#             logger.error(f"Lỗi kết nối đến Skill Management: {str(e)}")
#             raise
#     async def close(self):
#         await self.client.aclose()

import httpx
import logging
from typing import List, Dict, Any
from datetime import datetime
from backend.shared.schemas import SkillRead

logger = logging.getLogger(__name__)

# --- DỮ LIỆU MOCK 7 SKILLS ---
MOCK_SKILLS_DATA = {
    "items": [
        {
            "id": "5b1b2974-03c6-4b40-9d03-dae25a370b3d",
            "name": "run-python-test",
            "version": "1.0.0",
            "level": "atomic",
            "category": "python/testing",
            "tags": ["python", "testing", "validation", "pytest"],
            "metadata": {
                "description": "Dùng để thực thi các đoạn code Python và kiểm tra xem chúng có vượt qua các bài unit test hay không.",
                "input": {
                    "type": "object",
                    "required": ["code_snippet", "test_case"],
                    "properties": {
                        "test_case": {"type": "string", "description": "Đoạn code test (unit test) để verify logic."},
                        "code_snippet": {"type": "string", "description": "Đoạn code Python đã được sửa hoặc cần kiểm tra."}
                    }
                }
            },
            "updated_at": "2026-05-29T05:11:12Z",
            "raw_content": "", "full_markdown": ""
        },
        {
            "id": "f0cd1e4c-e935-481e-9258-58bda61705c2",
            "name": "debug-python-error",
            "version": "1.0.0",
            "level": "composite",
            "category": "python/debugging",
            "tags": ["python", "debug", "pipeline", "attributeerror"],
            "metadata": {
                "description": "Full pipeline to debug any Python exception — analyzes the stacktrace to find the root cause, then generates an actionable fix suggestion.",
                "input": {
                    "type": "object",
                    "required": ["stacktrace", "source_path"],
                    "properties": {
                        "stacktrace": {"type": "string", "description": "Full Python exception traceback"},
                        "source_path": {"type": "string", "description": "Path to the Python source file with the bug"}
                    }
                }
            },
            "updated_at": "2026-05-29T05:11:12Z",
            "raw_content": "", "full_markdown": ""
        },
        {
            "id": "aa70106b-046d-4615-97cc-d993dbc67a8f",
            "name": "suggest-python-fix",
            "version": "1.0.0",
            "level": "atomic",
            "category": "python/debugging",
            "tags": ["python", "fix", "attributeerror", "patch"],
            "metadata": {
                "description": "Suggests a concrete, actionable Python fix for an exception given the file, line number, variable name, and error type.",
                "input": {
                    "type": "object",
                    "required": ["file", "line", "variable", "error_type"],
                    "properties": {
                        "file": {"type": "string"},
                        "line": {"type": "integer"},
                        "variable": {"type": "string"},
                        "error_type": {"type": "string"},
                        "code_context": {"type": "string"}
                    }
                }
            },
            "updated_at": "2026-05-29T05:11:12Z",
            "raw_content": "", "full_markdown": ""
        },
        {
            "id": "1434afbe-602a-468e-aa6d-a844a6ab5629",
            "name": "debug-java-null-pointer",
            "version": "1.0.0",
            "level": "composite",
            "category": "java/debugging",
            "tags": ["java", "debug", "null-pointer", "pipeline"],
            "metadata": {
                "description": "Full pipeline to debug a Java NullPointerException. Analyzes the stacktrace and provides actionable fix suggestions.",
                "input": {
                    "type": "object",
                    "required": ["stacktrace", "source_path"],
                    "properties": {
                        "stacktrace": {"type": "string"},
                        "source_path": {"type": "string"}
                    }
                }
            },
            "updated_at": "2026-05-29T05:11:12Z",
            "raw_content": "", "full_markdown": ""
        },
        {
            "id": "abaa3845-b359-4b4b-90bd-ea7cf4488b95",
            "name": "suggest-java-fix",
            "version": "1.0.0",
            "level": "atomic",
            "category": "java/debugging",
            "tags": ["java", "fix", "null-pointer"],
            "metadata": {
                "description": "Suggests a concrete Java fix pattern for a NullPointerException given the file location and the null variable.",
                "input": {
                    "type": "object",
                    "required": ["file", "line", "variable"],
                    "properties": {
                        "file": {"type": "string"},
                        "line": {"type": "integer"},
                        "variable": {"type": "string"},
                        "code_context": {"type": "string"}
                    }
                }
            },
            "updated_at": "2026-05-29T05:11:12Z",
            "raw_content": "", "full_markdown": ""
        },
        {
            "id": "60a0da02-1c33-4d97-a574-9b736e6ed860",
            "name": "analyze-stacktrace",
            "version": "1.0.0",
            "level": "atomic",
            "category": "universal/debugging",
            "tags": ["stacktrace", "debug", "troubleshooting"],
            "metadata": {
                "description": "Analyzes an exception stacktrace to pinpoint the exact source file, line number, and the variable or root cause.",
                "input": {
                    "type": "object",
                    "required": ["stacktrace", "source_path"],
                    "properties": {
                        "stacktrace": {"type": "string"},
                        "source_path": {"type": "string"}
                    }
                }
            },
            "updated_at": "2026-05-29T05:11:12Z",
            "raw_content": "", "full_markdown": ""
        },
        {
            "id": "c4b90445-960e-4ff9-a2cf-a09f8632e3bd",
            "name": "read-code-context",
            "version": "1.0.0",
            "level": "atomic",
            "category": "universal/debugging",
            "tags": ["system", "file-io", "context"],
            "metadata": {
                "description": "Reads source code around a specific line to provide context for debugging.",
                "input": {
                    "type": "object",
                    "required": ["file", "line"],
                    "properties": {
                        "file": {"type": "string"},
                        "line": {"type": "integer"},
                        "window": {"type": "integer"}
                    }
                }
            },
            "updated_at": "2026-05-29T05:11:12Z",
            "raw_content": "", "full_markdown": ""
        }
    ]
}

class SkillManagementClient:
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=10.0)

    # async def fetch_all_skills(self) -> List[str]:
    #     """[MOCK] Trả về 7 skills để Agent lập kế hoạch"""
    #     logger.info("--- [MOCK] Đang lấy danh sách kỹ năng ---")
    #     skills = []
    #     for item in MOCK_DATA:
    #         skills.append(
    #             id=item["id"], name=item["name"], version="1.0.0", level="atomic",
    #             category=item["category"], tags=[],
    #             metadata={"description": item["desc"], "input": {"type": "object", "properties": {}}},
    #             updated_at=datetime.now(), raw_content="", full_markdown=""
    #         )
    #     return skills

    async def load_available_skills(self) -> list[str]:
        """Gọi sang endpoint của AG1 để lấy danh sách skill"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/api/v1/skills")
                if response.status_code == 200:
                    data = response.json()
                    return [item["name"] for item in data.get("items", [])]
                return []
        except Exception as e:
            print(f"⚠️ Không thể kết nối Microservice AG1: {e}. Sử dụng danh sách rỗng.")
            return []
   
    async def close(self):
        await self.client.aclose()