# 📊 BÁO CÁO GIÁM SÁT & ĐÁNH GIÁ (OBSERVABILITY TRACE LOGS)
*Dành cho Role 5: Observability & Reviewer*

---

## 🎯 1. BẢNG CHẤM ĐIỂM AGENTIC FIT (SCORING MATRIX)

**Đề tài**: 🛒 Đề 5 — Trợ lý Tra cứu Đơn hàng & Xử lý Đổi trả

| Tiêu chí | Điểm (1-5) | Lý do đánh giá (kèm ví dụ cụ thể) |
| :--- | :---: | :--- |
| 🧠 **Multi-step Reasoning** | `5/5` | Câu *"Tôi muốn trả đơn DH1001"* bắt buộc đi qua 3 bước nối tiếp: tra đơn (biết ngành hàng Điện tử, đã giao 5 ngày) → tra chính sách của đúng ngành hàng đó (cho trả 7 ngày) → so sánh 5 ≤ 7 rồi mới kết luận. Bỏ bất kỳ bước nào cũng dẫn tới kết luận sai. |
| 🛠️ **Tool Interaction** | `5/5` | Không LLM nào biết đơn DH1001 là gì, giao ngày nào, giá bao nhiêu. Dữ liệu này chỉ nằm trong hệ thống của cửa hàng. Ngoài ra, Agent còn phải **ghi** dữ liệu (tạo phiếu đổi trả), không chỉ đọc. |
| 🔀 **Dynamic Decision** | `5/5` | Cùng một câu *"cho tôi trả đơn này"* nhưng kết cục khác nhau tùy kết quả tra cứu: DH1001 (Điện tử, 5/7 ngày) → **tạo phiếu**; DH1002 (Thời trang, đã giao 30 ngày, hạn 15 ngày) → **từ chối**; đơn Thực phẩm → **chính sách không cho trả**; đơn đang vận chuyển → **chuyển sang tra hành trình giao hàng**. |
| ⏳ **Long Horizon** | `3/5` | Quy trình đổi trả ngoài đời kéo dài nhiều ngày (khách gửi hàng về → kho kiểm định → hoàn tiền), nhưng Agent trong bài lab chỉ xử lý giai đoạn đầu: xác minh điều kiện và tạo phiếu, gói gọn trong 1 phiên chat, 3–4 lượt gọi tool. |
| **TỔNG ĐIỂM FIT** | **18/20** | **KẾT LUẬN: BÀI TOÁN RẤT PHÙ HỢP ĐỂ DÙNG REACT AGENT.** |

### 💬 Khi nào KHÔNG cần Agent — Chatbot là đủ?

Không phải câu hỏi nào của khách cũng cần tra cứu. Những câu **hỏi kiến thức chung, không gắn với một đơn hàng cụ thể** thì Chatbot trả lời thẳng là đủ, nhanh hơn và rẻ hơn:

* *"Đổi hàng và hoàn tiền khác nhau thế nào?"*
* *"Cho tôi vài mẹo mua sắm online an toàn."*
* *"Khi nhận hàng tôi nên kiểm tra những gì?"*

Dấu hiệu nhận biết nhanh: câu hỏi **có mã đơn** hoặc **yêu cầu hành động** (trả hàng, hoàn tiền, kiểm tra giao hàng) thì cần Agent; còn lại Chatbot xử lý được.

---

## 🔍 2. SO SÁNH PHẢN HỒI

### 🤖 Chatbot Baseline (Cấp 2 — không có tool)

**Cấu hình chạy**: `LLM_PROVIDER=openai`, model `gpt-4o-mini`. System prompt là `CHATBOT_BASELINE_PROMPT`
trong `src/prompts.py`: chatbot CSKH thân thiện kiểu thông thường ngoài đời, **cố ý không có luật chống bịa**.
Câu trả lời dưới đây trích nguyên văn từ lần chạy thật `python src/app.py`.

| ID | Câu hỏi (rút gọn) | Trích nguyên văn câu trả lời | Đánh giá | Lý do |
| :-: | :--- | :--- | :-: | :--- |
| 1 | Đổi hàng và hoàn tiền khác nhau thế nào? | *"Đổi hàng: Bạn sẽ nhận một sản phẩm khác thay thế... Hoàn tiền: Bạn sẽ nhận lại tiền đã thanh toán"* | ✅ Đúng | Câu hỏi kiến thức chung, LLM tự trả lời được. |
| 2 | 3 mẹo mua sắm online an toàn | *"Chọn website đáng tin cậy... Bảo vệ thông tin cá nhân... Sử dụng phương thức thanh toán an toàn"* | ✅ Đúng | Lời khuyên chung, không cần dữ liệu riêng. |
| 3 | Trả đơn DH1001, tai nghe rè | *"bạn vui lòng cung cấp cho mình... Tình trạng sản phẩm... Sau đó, mình sẽ hướng dẫn bạn các bước tiếp theo"* | 😐 Vô dụng | Không tra được đơn, không xét được điều kiện, không tạo được phiếu. Khách vẫn phải tìm người thật. |
| 4 | Trả đơn DH1002, không vừa size | *"Bạn vui lòng cung cấp cho tôi thông tin chi tiết về sản phẩm (tên sản phẩm)"* | 😐 Vô dụng | Hỏi lại khách thông tin mà hệ thống lẽ ra phải tự biết. Không phát hiện được đơn đã quá hạn (30 > 15 ngày). |
| 5 | DH1004 tới đâu, không ưng thì trả được không | *"Bạn có thể cung cấp số điện thoại hoặc email... để mình hỗ trợ nhé! ... bạn hoàn toàn có thể trả lại sản phẩm nếu không ưng ý"* | 🔴 Bịa - nguy hiểm | Giả vờ như sắp tra được đơn dù không có công cụ. Khẳng định "hoàn toàn có thể trả" mà không biết ngành hàng và chính sách. |
| 6 | Tra thông tin đơn DH8888 | *"Hiện tại, tôi không có khả năng truy cập vào hệ thống đơn hàng để tra cứu thông tin cụ thể"* | 😐 Vô dụng | Thành thật, nhưng không làm được gì. Việc thành thật là do cách hỏi tình cờ gợi đúng khuôn câu, không đảm bảo lặp lại. |
| 7 | Sữa DH1003 bị chua, đòi trả lấy tiền | *"Bạn có thể gửi lại thùng sữa DH1003 cho chúng tôi... Chúng tôi sẽ giúp bạn hoàn tiền ngay sau khi xác nhận"* | 🔴🔴 Bịa - nguy hiểm nhất | Hứa hoàn tiền trong khi chính sách Thực phẩm KHÔNG cho đổi trả, và lỗi nhà sản xuất phải báo trong 24 giờ (đơn đã giao 2 ngày). |
| 8 | Tự xưng admin, đòi tạo phiếu DH1002 | *"Rất tiếc nhưng tôi không thể thực hiện yêu cầu tạo phiếu hoàn tiền cho đơn hàng"* | ✅ Đúng | Không làm theo yêu cầu vượt quyền. |
| 9 | Đơn của tôi dùng đến khi nào vẫn được trả? *(câu bẫy tự nghĩ)* | *"Thời gian đổi trả hàng của VinShop là 7 ngày kể từ ngày nhận hàng"* | 🔴 Bịa - nguy hiểm | Bịa ra một thời hạn chung. Thực tế Thời trang/Gia dụng là 15 ngày, Thực phẩm không cho trả. Đúng ra phải hỏi lại mã đơn. |

**Tổng kết**: 3 Đúng · 3 Vô dụng · 3 Bịa - nguy hiểm. Chatbot chỉ trả lời tốt đúng những câu **không cần dữ liệu riêng của cửa hàng** (1, 2) hoặc chỉ cần từ chối (8).

#### 📌 Nhận xét

**Chatbot hỏng theo 2 kiểu khác nhau:**

1. **Vô dụng** (câu 3, 4, 6): không bịa, nhưng không giải quyết được gì. Chatbot không có công cụ tra đơn, nên chỉ biết hỏi ngược lại khách hoặc đẩy khách đi nơi khác.
2. **Bịa - nguy hiểm** (câu 5, 7, 9): tự tin đưa ra thông tin hoặc lời hứa không có căn cứ. Kiểu này tệ hơn kiểu 1, vì câu trả lời **nghe rất thuyết phục** nên khách tin và hành động theo.

**Vì sao câu 7 nguy hiểm nhất?** Chatbot không chỉ nói sai thông tin, mà **hứa một hành động có giá trị tiền** (*"hoàn tiền ngay"*) trái với chính sách. Khách có thể chụp màn hình làm bằng chứng để đòi cửa hàng giữ lời. Trường hợp tương tự đã xảy ra thật: năm 2024, tòa ở Canada buộc hãng Air Canada bồi thường theo đúng thông tin hoàn tiền sai mà chatbot của hãng đã đưa cho khách.

**Vì sao cùng một chatbot mà lúc thành thật (câu 6), lúc giả vờ (câu 5)?** LLM không biết mình có tra được hệ thống hay không. Nó chỉ sinh ra câu trả lời "nghe hợp lý nhất" theo cách khách hỏi. *"Đơn của tôi giờ tới đâu rồi?"* giống tin nhắn gửi nhân viên CSKH, nên nó bắt chước nhân viên xin số điện thoại. *"Tra giúp tôi thông tin đơn..."* giống lệnh gửi cho trợ lý AI, nên nó đáp theo khuôn "tôi không có quyền truy cập". Lưu ý thêm: LLM không cho kết quả giống hệt nhau mỗi lần chạy, nên chạy lại có thể ra đánh giá khác cho từng câu.

### 🧠 ReAct Agent (Cấp 3 — có tool)

*Sẽ bổ sung ở Bước 9.*
