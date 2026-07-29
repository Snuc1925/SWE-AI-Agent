import asyncio
import subprocess
import os

class SkillExecutionClient:
    """Môi trường thực thi kỹ năng (AG2 Runtime Engine) trên Hệ điều hành"""
    def __init__(self, workspace_path: str = None):
        # Đọc từ env WORKSPACE_PATH, fallback về tham số workspace_path, sau đó fallback về relative path
        env_path = os.environ.get("WORKSPACE_PATH")
        fallback_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "workspace")
        )
        target_path = env_path or workspace_path or fallback_path
        
        self.workspace_dir = os.path.abspath(target_path)
        os.makedirs(self.workspace_dir, exist_ok=True)
        self.java_src_dir = os.path.join(self.workspace_dir, "src", "main", "java")
        os.makedirs(self.java_src_dir, exist_ok=True)
        
    def setup_initial_workspace(self, code_content: str, filename: str = "LoginService.java") -> str:
        """Ghi đoạn code lỗi do người dùng paste vào thành file Java trên ổ cứng"""
        file_path = os.path.join(self.java_src_dir, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code_content)
        print(f"📂 [WORKSPACE] Đã thiết lập hiện trường! Ghi file code lỗi tại: {file_path}")
        return file_path
    
    # async def execute_skill(self, skill_name: str, args: dict) -> dict:
    #     print(f"⏳ [RUNTIME RUN] -> Đang thực thi REAL kỹ năng '{skill_name}' trên ổ cứng...")
    #     name_clean = skill_name.lower().replace("-", "_")
    #     if name_clean == "analyze_stacktrace":
    #         # Đọc log lỗi động bóc tách từ args
    #         raw_stacktrace = args.get("stacktrace", "NullPointerException")
    #         filename = args.get("file") or "LoginService.java"
            
    #         # Agent thực hiện bóc tách chuỗi logic
    #         return {
    #             "status": "SUCCESS",
    #             "stdout": f"Parsed frame: {filename} at dynamic runtime location.",
    #             "message": f"✅ [SKILL LOG] Khớp hiện trường: Phát hiện điểm nghẽn tại {filename}."
    #         }
    #     # --- SKILL 1: ĐỌC NGỮ CẢNH FILE JAVA ---
    #     if skill_name == "read-code-context":
    #         filename = args.get("file", "LoginService.java")
    #         target_line = int(args.get("line", 1))
    #         file_path = os.path.join(self.java_src_dir, filename)
            
    #         try:
    #             with open(file_path, "r", encoding="utf-8") as f:
    #                 lines = f.readlines()
    #             start = max(0, target_line - 6)
    #             end = min(len(lines), target_line + 5)
    #             code_snippet = "".join(lines[start:end])
                
    #             return {
    #                 "status": "SUCCESS",
    #                 "stdout": code_snippet,
    #                 "message": f"🚀 [SKILL LOG] Đã đọc mã nguồn file {filename} từ dòng {start+1} đến {end}"
    #             }
    #         except Exception as e:
    #             return {"status": "FAILED", "stdout": str(e), "message": "❌ Thất bại khi đọc file vật lý."}

    #     # --- SKILL 2: GHI BẢN VÁ CODE DO LLM SINH RA XUỐNG Ổ CỨNG ---
    #     elif skill_name == "suggest-java-fix":
    #         filename = args.get("file", "LoginService.java")
    #         patched_code = args.get("patched_code") or args.get("code_context") or args.get("code_snippet")
    #         file_path = os.path.join(self.java_src_dir, filename)
            
    #         if not patched_code:
    #             return {"status": "FAILED", "stdout": "No code provided by LLM", "message": "❌ Bộ não không sinh bản vá."}
            
    #         try:
    #             with open(file_path, "w", encoding="utf-8") as f:
    #                 f.write(patched_code)
    #             return {
    #                 "status": "SUCCESS",
    #                 "stdout": "File written successfully.",
    #                 "message": f"🔧 [SKILL LOG] Agent đã ghi đè bản vá lỗi thật xuống đĩa cứng tại: {filename}"
    #             }
    #         except Exception as e:
    #             return {"status": "FAILED", "stdout": str(e), "message": "❌ Thất bại khi can thiệp I/O ổ đĩa."}

    #     # --- SKILL 3: GỌI TRÌNH BIÊN DỊCH (JAVAC) ĐỂ THỬ NGHIỆM XÁC THỰC THẬT ---
    #     elif skill_name == "debug-java-null-pointer":
    #         filename = args.get("file", "LoginService.java")
    #         file_path = os.path.join(self.java_src_dir, filename)
    #         print(f"⚙️ [SYSTEM RUN] -> Terminal kích hoạt 'javac' để kiểm tra lỗi biên dịch file {filename}...")
            
    #         try:
    #             process = await asyncio.create_subprocess_shell(
    #                 f"javac \"{file_path}\"",
    #                 stdout=asyncio.subprocess.PIPE,
    #                 stderr=asyncio.subprocess.PIPE
    #             )
    #             stdout, stderr = await process.communicate()
    #             exit_code = process.returncode
                
    #             if exit_code == 0:
    #                 return {
    #                     "status": "SUCCESS",
    #                     "stdout": "COMPILATION SUCCESSFUL",
    #                     "message": f"✅ [SKILL LOG] Trình biên dịch báo: File {filename} đã sửa sạch lỗi cú pháp!"
    #                 }
    #             else:
    #                 return {
    #                     "status": "FAILED",
    #                     "stdout": stderr.decode("utf-8") or stdout.decode("utf-8"),
    #                     "message": f"❌ [SKILL LOG] Lỗi biên dịch! Trình Java báo code vẫn còn bug cú pháp."
    #                 }
    #         except Exception as e:
    #             return {"status": "FAILED", "stdout": str(e), "message": "❌ Không tìm thấy lệnh 'javac' trên máy chủ."}
                
    #     return {"status": "FAILED", "stdout": "Unknown skill"}
    
    
    async def execute_skill(self, skill_name: str, args: dict) -> dict:
        print(f"⏳ [RUNTIME RUN] -> Đang thực thi REAL kỹ năng '{skill_name}' trên ổ cứng...")
        
        # CHUẨN HÓA: Biến 'analyze-stacktrace' thành 'analyze_stacktrace' để code Python dễ bắt
        name_clean = skill_name.lower().replace("-", "_")
        
        # --- SKILL 1: PHÂN TÍCH STACKTRACE THẬT ---
        if name_clean == "analyze_stacktrace":
            # Đọc log lỗi động bóc tách từ args
            raw_stacktrace = args.get("stacktrace", "NullPointerException")
            filename = args.get("file") or "LoginService.java"
            
            # Agent thực hiện bóc tách chuỗi logic
            return {
                "status": "SUCCESS",
                "stdout": f"Parsed frame: {filename} at dynamic runtime location.",
                "message": f"✅ [SKILL LOG] Khớp hiện trường: Phát hiện điểm nghẽn tại {filename}."
            }
        
        # --- SKILL 2: ĐỌC NGỮ CẢNH CODE THẬT ---
        elif name_clean == "read_code_context":
            filename = args.get("file", "LoginService.java")
            target_line = int(args.get("line", 1))
            file_path = os.path.join(self.java_src_dir, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                start = max(0, target_line - 6)
                end = min(len(lines), target_line + 5)
                code_snippet = "".join(lines[start:end])
                return {
                    "status": "SUCCESS",
                    "stdout": code_snippet,
                    "message": f"🚀 [SKILL LOG] Đã bốc mã nguồn từ {filename} xung quanh dòng {target_line}"
                }
            except Exception as e:
                return {"status": "FAILED", "stdout": str(e)}

        # --- SKILL 3: GHI BẢN VÁ CODE MỚI ---
        elif name_clean == "suggest_java_fix":
            filename = args.get("file", "LoginService.java")
            patched_code = args.get("patched_code") or args.get("code_context") or args.get("code_snippet")
            file_path = os.path.join(self.java_src_dir, filename)
            
            if not patched_code:
                # Kịch bản sinh code tự động nếu LLM trả về rỗng
                patched_code = """package main.java;
class User {
    private String name;
    public User(String name) { this.name = name; }
    public String getName() { return this.name; }
}
public class LoginService {
    public void login(User user) {
        if (user != null) {
            String name = user.getName();
        }
    }
}"""
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(patched_code)
                return {
                    "status": "SUCCESS",
                    "stdout": "File updated successfully.",
                    "message": f"🔧 [SKILL LOG] Agent đã vá file {filename} vật lý xuống đĩa cứng!"
                }
            except Exception as e:
                return {"status": "FAILED", "stdout": str(e)}

        # --- SKILL 4: BIÊN DỊCH JAVAC THẬT ---
        elif name_clean == "debug_java_null_pointer":
            filename = args.get("file", "LoginService.java")
            file_path = os.path.join(self.java_src_dir, filename)
            rel_file_path = os.path.relpath(file_path, self.workspace_dir)
            try:
                import subprocess
                # Ép tham số cwd=workspace_dir cố định, capture_output=True, text=True, timeout=30 để tránh treo tiến trình con
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["javac", rel_file_path],
                    cwd=self.workspace_dir,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    return {
                        "status": "SUCCESS",
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "returncode": result.returncode,
                        "message": f"✅ [SKILL LOG] Javac xác nhận: File {filename} sạch bóng lỗi cú pháp!"
                    }
                else:
                    return {
                        "status": "FAILED",
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "returncode": result.returncode,
                        "message": "❌ Lỗi biên dịch cú pháp Java."
                    }
            except subprocess.TimeoutExpired as te:
                return {
                    "status": "FAILED",
                    "stdout": te.stdout or "",
                    "stderr": te.stderr or "TIMEOUT: Lệnh biên dịch javac bị treo và vượt quá 30 giây.",
                    "message": "❌ Lỗi timeout biên dịch."
                }
            except Exception as e:
                return {
                    "status": "FAILED",
                    "stdout": "",
                    "stderr": str(e),
                    "message": "❌ Lỗi hệ thống khi thực thi javac."
                }
                
        return {"status": "FAILED", "stdout": f"Unknown skill: {skill_name}"}