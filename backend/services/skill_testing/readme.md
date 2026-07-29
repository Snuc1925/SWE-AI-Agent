Trong `skill_management` hiện tại đã được bổ sung thêm các API để phục vụ việc tích hợp với LangGraph (hoặc các Agent framework khác):

1.  **API thực thi trực tiếp**:
    *   `POST /skills/{skill_id}/execute`: Cho phép bạn gửi input tùy ý để thực thi kỹ năng. Bạn có thể chọn `mock_mode: true` (mặc định) để chạy thử mà không tốn API key, hoặc truyền `api_key` để chạy thật.
2.  **API phục vụ LangGraph/LangChain**:
    *   `GET /skills/tools`: Trả về danh sách toàn bộ kỹ năng dưới định dạng Tool Definition (bao gồm `name`, `description`, và `input_schema` chuẩn JSON Schema). LangGraph có thể gọi API này để tự động nạp danh sách công cụ.
    *   `GET /skills/{skill_id}/tool`: Lấy định dạng tool cho một kỹ năng cụ thể.

**Cách sử dụng cho LangGraph:**
Khi xây dựng Agent, bạn có thể gọi `GET /skills/tools` để lấy danh sách các tool. Khi Agent quyết định sử dụng một tool, bạn chỉ cần gọi `POST /skills/{skill_id}/execute` với các tham số mà Agent đã sinh ra.

Các thay đổi này đã được cập nhật và dịch vụ tự động reload. Bạn có thể kiểm tra qua Swagger UI tại `http://localhost:8001/docs`.