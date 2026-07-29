import asyncio
import json
import os
from services.skill_testing.test_pipeline import run_pipeline
from services.skill_testing.core.skill_client import SkillExecutionClient

async def main():
    # Tải các kịch bản test
    testcases_path = os.path.join(os.path.dirname(__file__), "testcases.json")
    with open(testcases_path, "r", encoding="utf-8") as f:
        testcases = json.load(f)

    # Khởi tạo client để tìm thư mục workspace dọn dẹp
    client = SkillExecutionClient()
    workspace_dir = client.workspace_dir
    java_src_dir = client.java_src_dir

    print(f"📁 Workspace: {workspace_dir}")
    print(f"🧪 Tổng số testcases tìm thấy: {len(testcases)}\n")

    results = []
    
    for tc in testcases:
        tc_id = tc["id"]
        filename = tc["filename"]
        code_content = tc["code_content"]
        stacktrace = tc["stacktrace"]
        message = tc["message"]

        print("=" * 80)
        print(f"🎬 ĐANG CHẠY TEST CASE: {tc_id}")
        print(f"   Mô tả: {message}")
        print("=" * 80)

        # Dọn dẹp stub User.java cũ để đảm bảo môi trường sạch trước mỗi case
        user_java_path = os.path.join(java_src_dir, "User.java")
        if os.path.exists(user_java_path):
            print(f"🧹 Đang xóa file stub cũ: {user_java_path}")
            os.remove(user_java_path)

        # Chạy pipeline đồ thị
        try:
            # final_state sẽ là kiểu dict hoặc BaseModel
            final_state = await run_pipeline(
                code_content=code_content,
                filename=filename,
                stacktrace=stacktrace,
                message=message
            )
            
            # Lấy thông tin kết quả
            is_finished = False
            final_answer = ""
            if isinstance(final_state, dict):
                is_finished = final_state.get("is_finished", False)
                final_answer = final_state.get("final_answer", "")
            else:
                is_finished = getattr(final_state, "is_finished", False)
                final_answer = getattr(final_state, "final_answer", "")
            
            # Đánh giá kết quả Pass / Fail
            passed = False
            if is_finished and "SUCCESS" in final_answer:
                passed = True
            elif tc_id == "TC_02_StubGeneration" and os.path.exists(user_java_path):
                # Nếu file stub User.java đã được tạo thành công trên đĩa thì coi như pass case này
                passed = True
            
            results.append({
                "id": tc_id,
                "passed": passed,
                "is_finished": is_finished,
                "final_answer": final_answer,
                "error": None
            })
            
        except Exception as e:
            print(f"❌ Xảy ra ngoại lệ khi chạy test case {tc_id}: {e}")
            results.append({
                "id": tc_id,
                "passed": False,
                "is_finished": False,
                "final_answer": None,
                "error": str(e)
            })

    # Tổng kết
    print("\n" + "=" * 80)
    print("📊 BÁO CÁO TỔNG HỢP TEST SUITE RUNNER")
    print("=" * 80)
    
    passed_count = sum(1 for r in results if r["passed"])
    total_count = len(results)
    pass_rate = (passed_count / total_count) * 100 if total_count > 0 else 0
    
    for r in results:
        status = "✅ PASS" if r["passed"] else "❌ FAIL"
        err_msg = f" (Error: {r['error']})" if r["error"] else ""
        print(f"- [{r['id']}] {status} | Finished: {r['is_finished']} | Answer: {r['final_answer']}{err_msg}")
        
    print("-" * 80)
    print(f"📈 Tỷ lệ đạt (Pass Rate): {pass_rate:.1f}% ({passed_count}/{total_count})")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
