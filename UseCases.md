# Mô tả kịch bản sử dụng

## 1. Tổng quan

Tài liệu này mô tả các kịch bản sử dụng chính của hệ thống **SWE AI Agent - Skill Library and Evaluation Platform**. Hệ thống cho phép người dùng quản lý thư viện skill, cấu hình bộ tiêu chí đánh giá, đồng bộ feature cho thư viện skill, đánh giá một skill mới và quan sát phân bố feature trên toàn bộ thư viện.

Tác nhân chính của hệ thống là **Người dùng**. Người dùng có thể là người xây dựng skill, người quản lý thư viện skill hoặc người đánh giá chất lượng skill. Trong phạm vi hệ thống hiện tại, các vai trò này được gom thành một tác nhân duy nhất vì giao diện chưa tách cơ chế đăng nhập và phân quyền.

---

## 2. Danh sách use case chính

| Mã use case | Tên use case | Mô tả ngắn |
|-------------|--------------|------------|
| UC-01 | Quản lý thư viện skill | Người dùng xem, tìm kiếm, import, export và xem chi tiết skill trong thư viện. |
| UC-02 | Cấu hình evaluation profile | Người dùng định nghĩa feature, bucket scoring, criteria, condition và score action. |
| UC-03 | Đồng bộ feature cho skill library | Người dùng chạy sync feature cho từng skill hoặc toàn bộ thư viện skill. |
| UC-04 | Đánh giá skill mới | Người dùng upload hoặc paste `SKILL.md`, trích xuất feature, chỉnh sửa feature và chấm điểm. |
| UC-05 | Phân tích và trực quan hóa feature | Người dùng xem phân bố feature trên tập skill đã đồng bộ. |

---

## 3. UC-01 - Quản lý thư viện skill

### Mô tả

Người dùng truy cập màn hình **Skill Browser** để xem danh sách skill hiện có trong thư viện. Thư viện skill được lưu trong thư mục `skill-library/` và được chia theo các category của Software Engineering như backend, frontend, testing, devops, security, architecture.

### Luồng chính

1. Người dùng mở màn hình Skill Browser.
2. Hệ thống gọi API `GET /skills` để lấy danh sách skill.
3. Hệ thống hiển thị danh sách skill gồm tên, version, level, category, tags và thao tác tương ứng.
4. Người dùng nhập từ khóa tìm kiếm hoặc chọn bộ lọc category/level.
5. Hệ thống cập nhật danh sách skill theo điều kiện lọc.
6. Người dùng chọn một skill để xem chi tiết.
7. Hệ thống mở màn hình Skill Detail và hiển thị metadata, instruction, raw markdown và extracted features nếu đã có cache.

### Luồng phát sinh

- Nếu danh sách skill rỗng, hệ thống hiển thị trạng thái không có dữ liệu.
- Nếu API lỗi, frontend hiển thị thông báo lỗi thay vì để giao diện treo.
- Nếu người dùng import file không hợp lệ, hệ thống trả lỗi validate metadata hoặc markdown.

### Tiền điều kiện

- Backend `skill-management` đang chạy.
- Thư mục `skill-library/` tồn tại và có các file `SKILL.md`.

### Hậu điều kiện

- Người dùng xem được danh sách skill và có thể truy cập chi tiết từng skill.
- Nếu có import skill mới, dữ liệu được lưu vào `database/skills.json` và markdown được ghi vào thư viện skill.

---

## 4. UC-02 - Cấu hình evaluation profile

### Mô tả

Người dùng cấu hình cách hệ thống đánh giá skill thông qua **evaluation profile**. Profile mặc định được lưu tại `database/evaluation_profiles/default_distribution.json`. Profile định nghĩa model LLM, danh sách feature cần trích xuất, cơ chế bucket scoring và các tiêu chí chấm điểm.

### Luồng chính

1. Người dùng mở màn hình Evaluation.
2. Hệ thống gọi API `GET /evaluation/profiles/default`.
3. Frontend hiển thị profile editor gồm các tab Model, Features, Bucket Scoring và Criteria.
4. Người dùng thêm, sửa hoặc xóa feature.
5. Người dùng cấu hình bucket scoring cho feature dạng integer.
6. Người dùng thêm, sửa hoặc xóa criteria.
7. Người dùng cấu hình condition và action trong từng rule step.
8. Người dùng nhấn Save Profile.
9. Hệ thống gọi API `PUT /evaluation/profiles/default` để validate và lưu profile.

### Luồng phát sinh

- Nếu profile không hợp lệ, backend trả lỗi 400 và frontend hiển thị thông báo lỗi.
- Nếu người dùng reset profile, frontend tải lại profile mặc định từ backend.
- Nếu API key LLM bị thiếu, profile vẫn có thể lưu nhưng các bước cần gọi LLM sẽ báo lỗi khi chạy.

### Tiền điều kiện

- Backend `skill-evaluation` đang chạy.
- File profile mặc định tồn tại hoặc backend có thể tạo profile mặc định.

### Hậu điều kiện

- Evaluation profile được lưu vào JSON file.
- Các lần evaluate sau sử dụng bộ feature và criteria mới nhất.

---

## 5. UC-03 - Đồng bộ feature cho skill library

### Mô tả

Người dùng đồng bộ feature cho các skill trong thư viện để tạo dữ liệu phục vụ cache, calibration và visualization. Khi sync, hệ thống kiểm tra cache trước. Nếu feature đã tồn tại và còn hợp lệ theo hash nội dung skill và hash profile, hệ thống dùng lại cache. Nếu thiếu cache hoặc feature đã thay đổi, hệ thống gọi LLM để trích xuất lại.

### Luồng chính

1. Người dùng mở Skill Browser.
2. Người dùng nhấn nút Sync Features.
3. Frontend mở modal hiển thị danh sách skill cần sync.
4. Người dùng nhấn Start Sync.
5. Frontend chạy sync lần lượt từng skill.
6. Với mỗi skill, hệ thống kiểm tra cache.
7. Nếu cache hit, frontend hiển thị trạng thái cache hit.
8. Nếu cache miss, backend gọi LLM để trích xuất feature.
9. Nếu trích xuất thành công, kết quả được lưu vào `evaluation_feature_cache.json`.
10. Nếu trích xuất thất bại, frontend hiển thị fail và tiếp tục skill kế tiếp.
11. Khi hoàn tất, modal hiển thị tổng số success, cache hit và fail.

### Luồng phát sinh

- Nếu LLM API key thiếu, backend trả lỗi rõ ràng.
- Nếu một skill lỗi, tiến trình không dừng toàn bộ mà chuyển sang skill tiếp theo.
- Nếu cache đã đầy đủ, hệ thống không gọi LLM lại.

### Tiền điều kiện

- Skill library đã có danh sách skill.
- Evaluation profile đã định nghĩa feature cần trích xuất.
- API key LLM được cấu hình nếu cần gọi LLM.

### Hậu điều kiện

- Cache feature của thư viện được cập nhật.
- Dữ liệu có thể dùng cho calibration và visualization.

---

## 6. UC-04 - Đánh giá skill mới

### Mô tả

Người dùng upload hoặc paste một file `SKILL.md` mới để đánh giá. Hệ thống trích xuất feature, cho phép người dùng kiểm tra/chỉnh sửa feature, sau đó tính điểm deterministic dựa trên evaluation profile.

### Luồng chính

1. Người dùng mở màn hình Evaluation.
2. Người dùng paste markdown hoặc upload file `SKILL.md`.
3. Người dùng chọn Evaluate Directly hoặc Extract Features.
4. Nếu chọn Extract Features, backend trích xuất feature và trả về evidence, confidence.
5. Frontend hiển thị danh sách feature đã trích xuất.
6. Người dùng chỉnh sửa feature nếu thấy cần thiết.
7. Người dùng nhấn Score Reviewed Features.
8. Backend chạy rule engine deterministic trên feature đã duyệt.
9. Frontend hiển thị điểm tổng, điểm từng criterion, explanation và applied rule steps.
10. Người dùng có thể export kết quả ra HTML.

### Luồng phát sinh

- Nếu markdown thiếu frontmatter hoặc format không hợp lệ, format feature vẫn được tính và lỗi được hiển thị.
- Nếu LLM lỗi, frontend hiển thị thông báo lỗi thay vì đứng im.
- Nếu người dùng chỉnh sửa feature, backend không gọi LLM lại khi chấm điểm.

### Tiền điều kiện

- Có nội dung markdown hợp lệ hoặc gần hợp lệ để đánh giá.
- Evaluation profile đã được cấu hình.

### Hậu điều kiện

- Người dùng nhận được kết quả đánh giá content theo từng criterion.
- Kết quả có thể được export thành file HTML.

---

## 7. UC-05 - Phân tích và trực quan hóa feature

### Mô tả

Người dùng xem phân bố feature trên toàn bộ skill library. Chức năng này sử dụng dữ liệu đã sync trong cache để hiển thị tỷ lệ true/false của feature boolean và phân bố giá trị của feature integer.

### Luồng chính

1. Người dùng mở Skill Browser.
2. Người dùng chuyển sang tab Visualization.
3. Hệ thống đọc dữ liệu feature đã cache.
4. Frontend hiển thị danh sách feature có dữ liệu.
5. Người dùng chọn một feature để xem phân bố.
6. Với feature boolean, hệ thống hiển thị số lượng skill true/false.
7. Với feature integer, hệ thống hiển thị phân bố giá trị và các ngưỡng percentile.

### Luồng phát sinh

- Nếu chưa sync feature, hệ thống yêu cầu người dùng sync trước.
- Nếu một số skill thiếu feature, hệ thống vẫn hiển thị dữ liệu còn lại.

### Tiền điều kiện

- Đã có dữ liệu feature trong cache.

### Hậu điều kiện

- Người dùng quan sát được đặc điểm chung của thư viện skill.
- Người dùng có thêm cơ sở để điều chỉnh feature definition, bucket scoring hoặc criteria.
