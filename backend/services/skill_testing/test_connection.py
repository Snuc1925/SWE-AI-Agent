# test_connection.py
import asyncio
import httpx

# Sửa lại URL này cho đúng với địa chỉ và Port mà service AG1 của bạn mình đang chạy
AG1_BASE_URL = "http://127.0.0.1:8001" 
SKILLS_ENDPOINT = f"{AG1_BASE_URL}/skills"

async def test_ag1_connection():
    print("=================================================================")
    print("🌐 BẮT ĐẦU KIỂM THỬ KẾT NỐI MICROSERVICE (AG2 ──> AG1) 🌐")
    print("=================================================================\n")
    
    print(f"📡 Đang bắn request GET tới Endpoint: {SKILLS_ENDPOINT}...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(SKILLS_ENDPOINT, timeout=10.0)
            if response.status_code == 200:
                print("✅ [SUCCESS] Kết nối tới Microservice AG1 thành công rực rỡ!")
  
                raw_json = response.json()
                print(f"📦 Dữ liệu JSON thô nhận về từ AG1:\n{raw_json}\n")
                
                print("⚙️ Đang thực hiện bóc tách lấy mảng tên kỹ năng (Skill Names)...")
                
                skills_list = [item["name"] for item in raw_json.get("items", [])]
                
                print(f"🎯 Kết quả mảng list[str] sau khi bóc tách: {skills_list}")
                
                if len(skills_list) > 0:
                    print("\n🎉 BÀI TEST THÀNH CÔNG! Dữ liệu đã sẵn sàng để nạp thẳng vào Registry.")
                else:
                    print("\n⚠️ CẢNH BÁO: Kết nối được nhưng mảng trả về rỗng. Hãy kiểm tra xem bên AG1 đã thêm Skill nào vào Database chưa.")
                    
            else:
                print(f"❌ [FAILED] Kết nối thành công nhưng API trả về mã lỗi HTTP: {response.status_code}")
                print(f"Chi tiết phản hồi: {response.text}")
                
        except httpx.ConnectError:
            print(f"❌ [CRITICAL ERROR] Không thể kết nối tới {AG1_BASE_URL}.")
            print("Vui lòng kiểm tra xem bạn AG1 đã start server chưa, hoặc có gõ sai Port/IP không.")
        except Exception as e:
            print(f"❌ [UNEXPECTED ERROR] Quá trình kiểm thử bị gián đoạn: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_ag1_connection())