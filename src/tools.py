"""
🛠️ TOOL REGISTRY & SCHEMAS (Dành cho Role 2: Tool & Spec Engineer)
Đề tài: TRỢ LÝ TRA CỨU ĐƠN HÀNG & XỬ LÝ ĐỔI TRẢ

Nơi khai báo tất cả các "món đồ nghề" mà ReAct Agent có thể gọi.

3 NGUYÊN TẮC:
  1. Phần mô tả (docstring) là "sách hướng dẫn" để LLM biết khi nào dùng tool nào.
  2. Gặp lỗi thì RETURN chuỗi bắt đầu bằng "LỖI:", không làm sập chương trình.
     Câu báo lỗi sẽ được gửi lại cho LLM để nó tự sửa ở bước sau.
  3. Tool ghi dữ liệu (create_return_ticket) phải tự kiểm tra lại quy định, không tin LLM.
"""

import re


# =====================================================================
# 📦 DỮ LIỆU GIẢ LẬP (thay cho database thật của cửa hàng)
# =====================================================================
TODAY = "10/09/2026"

# Mỗi đơn được chọn để kích hoạt một nhánh xử lý khác nhau của Agent
ORDERS = {
    "DH1001": {   # ✅ Đủ điều kiện: Điện tử, giao 5 ngày < hạn 7 ngày
        "product": "Tai nghe Sony WH-1000XM5",
        "category": "Điện tử",
        "price": 8_490_000,
        "status": "Đã giao",
        "days_since_delivery": 5,
    },
    "DH1002": {   # ❌ Quá hạn: Thời trang, giao 30 ngày > hạn 15 ngày
        "product": "Áo khoác gió Uniqlo",
        "category": "Thời trang",
        "price": 990_000,
        "status": "Đã giao",
        "days_since_delivery": 30,
    },
    "DH1003": {   # 🚫 Chính sách chặn: Thực phẩm không cho đổi trả
        "product": "Thùng sữa tươi TH True Milk 48 hộp",
        "category": "Thực phẩm",
        "price": 350_000,
        "status": "Đã giao",
        "days_since_delivery": 2,
    },
    "DH1004": {   # 🚚 Chưa giao: phải tra vận chuyển, chưa có quyền đổi trả
        "product": "Laptop Dell XPS 13",
        "category": "Điện tử",
        "price": 32_000_000,
        "status": "Đang vận chuyển",
        "days_since_delivery": None,
    },
    "DH1005": {   # ✅ Đủ điều kiện: Gia dụng, giao 6 ngày < hạn 15 ngày
        "product": "Nồi chiên không dầu Lock&Lock 5.5L",
        "category": "Gia dụng",
        "price": 2_100_000,
        "status": "Đã giao",
        "days_since_delivery": 6,
    },
}

# Chính sách đổi trả theo ngành hàng. window_days = 0 nghĩa là KHÔNG cho trả.
RETURN_POLICIES = {
    "Điện tử":    {"window_days": 7,  "refund_percent": 100,
                   "conditions": "Còn nguyên hộp, đủ phụ kiện."},
    "Thời trang": {"window_days": 15, "refund_percent": 100,
                   "conditions": "Còn nguyên tem mác, chưa giặt."},
    "Gia dụng":   {"window_days": 15, "refund_percent": 90,
                   "conditions": "Còn nguyên hộp và phiếu bảo hành."},
    "Thực phẩm":  {"window_days": 0,  "refund_percent": 0,
                   "conditions": "Không đổi trả vì lý do cá nhân. Hàng lỗi do nhà sản xuất "
                                 "vui lòng báo trong 24 giờ kể từ khi nhận."},
}

# Nơi lưu các phiếu đổi trả đã tạo (mất đi khi tắt chương trình)
RETURN_TICKETS = {}

ORDER_ID_FORMAT = re.compile(r"^DH\d{4}$")


def _normalize_order_id(order_id):
    """Hàm phụ: chuẩn hoá mã đơn. Trả về (mã_chuẩn, None) hoặc (None, câu_lỗi)."""
    if not isinstance(order_id, str) or not order_id.strip():
        return None, "LỖI: Thiếu mã đơn hàng. Hãy hỏi khách mã đơn, dạng 'DH1001'."
    oid = order_id.strip().upper()
    if not ORDER_ID_FORMAT.match(oid):
        return None, (f"LỖI: Mã đơn '{order_id}' sai định dạng. Mã đúng gồm 'DH' + 4 chữ số, "
                      f"ví dụ DH1001. Không được tự đoán mã, hãy hỏi lại khách.")
    if oid not in ORDERS:
        return None, (f"LỖI: Không tìm thấy đơn '{oid}'. Hãy nhờ khách kiểm tra lại mã đơn "
                      f"trong mục 'Đơn mua'.")
    return oid, None


# =====================================================================
# 🔧 TOOL 1 — TRA CỨU ĐƠN HÀNG
# =====================================================================
def lookup_order(order_id: str) -> str:
    """
    Tra thông tin một đơn hàng.

    DÙNG KHI: khách nhắc tới một mã đơn, hoặc cần biết NGÀNH HÀNG / SỐ NGÀY ĐÃ GIAO
    trước khi xét đổi trả. Đây luôn là bước đầu tiên khi xử lý yêu cầu về một đơn.

    Nhận:    order_id (str) - mã đơn, ví dụ 'DH1001'
    Trả về:  sản phẩm, ngành hàng, giá, trạng thái, số ngày đã giao.
             Hoặc chuỗi bắt đầu bằng 'LỖI:' nếu mã sai / không tồn tại.
    """
    oid, error = _normalize_order_id(order_id)
    if error:
        return error

    o = ORDERS[oid]
    info = (f"Đơn {oid} | Sản phẩm: {o['product']} | Ngành hàng: {o['category']} "
            f"| Giá: {o['price']:,} VNĐ | Trạng thái: {o['status']}")

    if o["status"] != "Đã giao":
        return info + " | Chưa giao tới khách nên CHƯA thể đổi trả."
    return info + f" | Đã giao được {o['days_since_delivery']} ngày (tính đến {TODAY})."


# =====================================================================
# 🔧 TOOL 2 — TRA CỨU CHÍNH SÁCH ĐỔI TRẢ
# =====================================================================
def check_return_policy(category: str) -> str:
    """
    Tra chính sách đổi trả của MỘT NGÀNH HÀNG.

    DÙNG KHI: đã biết ngành hàng của sản phẩm (lấy từ lookup_order, KHÔNG tự đoán)
    và cần biết được trả trong bao nhiêu ngày, điều kiện gì, hoàn bao nhiêu phần trăm.

    Nhận:    category (str) - một trong: 'Điện tử', 'Thời trang', 'Gia dụng', 'Thực phẩm'
    Trả về:  số ngày được trả, điều kiện, % hoàn tiền.
             Hoặc chuỗi 'LỖI:' nếu ngành hàng không có trong hệ thống.
    """
    if not isinstance(category, str) or not category.strip():
        return "LỖI: Thiếu tên ngành hàng. Hãy gọi lookup_order trước để biết ngành hàng."

    name = next((k for k in RETURN_POLICIES if k.lower() == category.strip().lower()), None)
    if name is None:
        return (f"LỖI: Không có ngành hàng '{category}'. "
                f"Ngành hàng hợp lệ: {', '.join(RETURN_POLICIES)}.")

    p = RETURN_POLICIES[name]
    if p["window_days"] == 0:
        return f"Chính sách '{name}': KHÔNG cho đổi trả. {p['conditions']}"
    return (f"Chính sách '{name}': được đổi trả trong {p['window_days']} ngày kể từ ngày giao. "
            f"Điều kiện: {p['conditions']} Hoàn tiền: {p['refund_percent']}%.")


# =====================================================================
# 🔧 TOOL 3 — TẠO PHIẾU ĐỔI TRẢ  (tool GHI dữ liệu)
# =====================================================================
def create_return_ticket(order_id: str, reason: str) -> str:
    """
    Tạo phiếu đổi trả cho một đơn. ĐÂY LÀ HÀNH ĐỘNG GHI DỮ LIỆU.

    DÙNG KHI: đã so sánh 'số ngày đã giao' (từ lookup_order) với 'số ngày được trả'
    (từ check_return_policy) và CHẮC CHẮN đơn còn trong hạn.
    KHÔNG gọi khi đơn quá hạn, chưa giao, hoặc ngành hàng không cho trả.

    Nhận:    order_id (str) - mã đơn, ví dụ 'DH1001'
             reason (str)   - lý do khách đưa ra, ví dụ 'Tai nghe bị rè một bên'
    Trả về:  mã phiếu và số tiền hoàn dự kiến.
             Hoặc chuỗi 'LỖI:' nếu yêu cầu bị từ chối.
    """
    oid, error = _normalize_order_id(order_id)
    if error:
        return error

    if not isinstance(reason, str) or len(reason.strip()) < 5:
        return "LỖI: Thiếu lý do đổi trả hoặc lý do quá ngắn. Hãy hỏi khách lý do cụ thể."

    # 🛡️ Tự kiểm tra lại toàn bộ điều kiện — kể cả khi LLM đã "kết luận" là được
    o = ORDERS[oid]
    p = RETURN_POLICIES[o["category"]]

    if o["status"] != "Đã giao":
        return f"LỖI: Đơn {oid} đang '{o['status']}', chưa giao nên chưa thể đổi trả."
    if p["window_days"] == 0:
        return f"LỖI: Ngành hàng '{o['category']}' không cho đổi trả. Từ chối tạo phiếu."
    if o["days_since_delivery"] > p["window_days"]:
        return (f"LỖI: Đơn {oid} đã giao {o['days_since_delivery']} ngày, quá hạn "
                f"{p['window_days']} ngày của ngành '{o['category']}'. Từ chối tạo phiếu.")
    if oid in RETURN_TICKETS:
        return f"LỖI: Đơn {oid} đã có phiếu {RETURN_TICKETS[oid]}. Không tạo trùng."

    ticket_id = f"RT{1001 + len(RETURN_TICKETS)}"
    RETURN_TICKETS[oid] = ticket_id
    refund = o["price"] * p["refund_percent"] // 100
    return (f"THÀNH CÔNG: Đã tạo phiếu {ticket_id} cho đơn {oid}. Lý do: {reason.strip()}. "
            f"Tiền hoàn dự kiến: {refund:,} VNĐ ({p['refund_percent']}%). "
            f"CSKH sẽ liên hệ trong 24 giờ.")


# =====================================================================
# 🔧 TOOL 4 — TRA CỨU VẬN CHUYỂN
# =====================================================================
def check_shipping_status(order_id: str) -> str:
    """
    Tra hành trình vận chuyển của một đơn.

    DÙNG KHI: khách hỏi 'hàng tới đâu rồi', 'bao giờ nhận được',
    hoặc lookup_order cho thấy đơn đang 'Đang vận chuyển'.

    Nhận:    order_id (str) - mã đơn, ví dụ 'DH1004'
    Trả về:  vị trí hiện tại và ngày giao dự kiến.
             Hoặc chuỗi 'LỖI:' nếu mã sai / không tồn tại.
    """
    oid, error = _normalize_order_id(order_id)
    if error:
        return error

    o = ORDERS[oid]
    if o["status"] == "Đã giao":
        return f"Đơn {oid} đã giao thành công {o['days_since_delivery']} ngày trước."
    return (f"Đơn {oid} ({o['product']}) đang vận chuyển. "
            f"Vị trí: Kho trung chuyển Bình Dương. Dự kiến giao: 12/09/2026.")


# =====================================================================
# 📋 DANH BẠ TOOL — Agent chỉ gọi được những tool có tên ở đây
# =====================================================================
AVAILABLE_TOOLS = {
    "lookup_order": lookup_order,
    "check_return_policy": check_return_policy,
    "create_return_ticket": create_return_ticket,
    "check_shipping_status": check_shipping_status,
}


# =====================================================================
# 🧪 CHẠY THỬ:  python src/tools.py
# =====================================================================
if __name__ == "__main__":
    import sys
    if sys.stdout.encoding != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    def show(title, result):
        print(f"\n▶ {title}\n  {result}")

    print("=" * 70)
    print("🧪 CHẠY THỬ 4 TOOL")
    print("=" * 70)

    print("\n---------- TOOL 1: lookup_order ----------")
    show("Đơn hợp lệ DH1001", lookup_order("DH1001"))
    show("Đơn đang vận chuyển DH1004", lookup_order("DH1004"))
    show("Mã không tồn tại DH9999", lookup_order("DH9999"))
    show("Mã sai định dạng 'abc'", lookup_order("abc"))

    print("\n---------- TOOL 2: check_return_policy ----------")
    show("Ngành Điện tử", check_return_policy("Điện tử"))
    show("Ngành Thực phẩm (không cho trả)", check_return_policy("Thực phẩm"))
    show("Ngành không tồn tại 'Mỹ phẩm'", check_return_policy("Mỹ phẩm"))

    print("\n---------- TOOL 3: create_return_ticket ----------")
    show("DH1001 còn hạn -> phải THÀNH CÔNG", create_return_ticket("DH1001", "Tai nghe bị rè một bên"))
    show("DH1001 tạo lần 2 -> phải chặn trùng", create_return_ticket("DH1001", "Tai nghe bị rè một bên"))
    show("DH1002 quá hạn -> tool phải TỰ TỪ CHỐI", create_return_ticket("DH1002", "Không vừa size"))
    show("DH1003 thực phẩm -> phải từ chối", create_return_ticket("DH1003", "Sữa bị chua"))
    show("DH1004 chưa giao -> phải từ chối", create_return_ticket("DH1004", "Đổi ý không mua"))

    print("\n---------- TOOL 4: check_shipping_status ----------")
    show("Đơn đang vận chuyển DH1004", check_shipping_status("DH1004"))
    show("Đơn đã giao DH1005", check_shipping_status("DH1005"))
