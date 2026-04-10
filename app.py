import os
import io
import json
from datetime import datetime
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    PostbackEvent, FollowEvent,
    FlexSendMessage, BubbleContainer, BoxComponent,
    TextComponent, ButtonComponent, SeparatorComponent,
    PostbackAction, MessageAction, URIAction
)
from supabase import create_client, Client
import openpyxl
from openpyxl.styles import Alignment

app = Flask(__name__)

# ── 環境變數 ──────────────────────────────────────────────
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET       = os.environ.get("CHANNEL_SECRET")
OWNER_ID                  = os.environ.get("OWNER_ID")
SUPABASE_URL              = os.environ.get("SUPABASE_URL")
SUPABASE_KEY              = os.environ.get("SUPABASE_KEY")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler      = WebhookHandler(LINE_CHANNEL_SECRET)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── 暫存使用者狀態 ────────────────────────────────────────
user_states = {}

PRICE_PER_PACK  = 200
MAX_PACKS       = 15
MIN_PACKS       = 2
SHIPPING_FEE    = 170
FREE_SHIPPING   = 2000

# ════════════════════════════════════════════════════════
#  Helper Functions
# ════════════════════════════════════════════════════════

def get_state(uid):
    return user_states.get(uid, {"step": 0})

def set_state(uid, state):
    user_states[uid] = state

def reset_state(uid):
    user_states[uid] = {"step": 0}

def calc_order(qty_a, qty_b):
    subtotal = (qty_a + qty_b) * PRICE_PER_PACK
    shipping = 0 if subtotal >= FREE_SHIPPING else SHIPPING_FEE
    total    = subtotal + shipping
    return subtotal, shipping, total

def get_user_profile(uid):
    res = supabase.table("user_profiles").select("*").eq("user_id", uid).execute()
    if res.data:
        return res.data[0]
    return None

def save_user_profile(uid, name, phone, address):
    existing = get_user_profile(uid)
    if existing:
        supabase.table("user_profiles").update({
            "name": name, "phone": phone,
            "address": address, "updated_at": datetime.utcnow().isoformat()
        }).eq("user_id", uid).execute()
    else:
        supabase.table("user_profiles").insert({
            "user_id": uid, "name": name,
            "phone": phone, "address": address,
            "updated_at": datetime.utcnow().isoformat()
        }).execute()

def save_order(uid, state):
    qty_a = state["qty_a"]
    qty_b = state["qty_b"]
    subtotal, shipping, total = calc_order(qty_a, qty_b)
    supabase.table("orders").insert({
        "user_id":       uid,
        "name":          state["name"],
        "phone":         state["phone"],
        "address":       state["address"],
        "delivery_time": state["delivery_time"],
        "qty_a":         qty_a,
        "qty_b":         qty_b,
        "subtotal":      subtotal,
        "shipping":      shipping,
        "total":         total,
        "exported":      False
    }).execute()

# ════════════════════════════════════════════════════════
#  Flex Message Builders
# ════════════════════════════════════════════════════════

def make_cancel_button():
    return ButtonComponent(
        action=PostbackAction(label="❌ 取消訂單", data="action=cancel"),
        style="secondary", color="#FF6B6B", height="sm", margin="md"
    )

def welcome_flex():
    bubble = BubbleContainer(
        body=BoxComponent(layout="vertical", contents=[
            TextComponent(text="🥟 A-MU水餃", weight="bold", size="xl", color="#1E90FF"),
            TextComponent(text="歡迎光臨！請開始訂購", size="md", margin="md"),
            SeparatorComponent(margin="md"),
            TextComponent(text="• 高麗菜豬肉 (A) NT$200/包", size="sm", margin="md"),
            TextComponent(text="• 韭菜黑豬肉 (B) NT$200/包", size="sm"),
            TextComponent(text="• 最少2包，最多15包", size="sm", color="#888888"),
            TextComponent(text="• 滿$2000免運，未滿加$170", size="sm", color="#888888"),
        ]),
        footer=BoxComponent(layout="vertical", contents=[
            ButtonComponent(
                action=PostbackAction(label="🛒 開始訂購", data="action=start"),
                style="primary", color="#1E90FF"
            )
        ])
    )
    return FlexSendMessage(alt_text="歡迎來到A-MU水餃", contents=bubble)

def qty_a_flex():
    buttons = []
    for i in range(0, 16):
        buttons.append(ButtonComponent(
            action=PostbackAction(label=str(i), data=f"action=qty_a&value={i}"),
            style="primary" if i > 0 else "secondary",
            color="#1E90FF" if i > 0 else "#AAAAAA",
            height="sm"
        ))
    rows = []
    row = []
    for i, btn in enumerate(buttons):
        row.append(btn)
        if len(row) == 4:
            rows.append(BoxComponent(layout="horizontal", contents=row, spacing="sm"))
            row = []
    if row:
        rows.append(BoxComponent(layout="horizontal", contents=row, spacing="sm"))

    bubble = BubbleContainer(
        body=BoxComponent(layout="vertical", contents=[
            TextComponent(text="步驟 1/2 - 選擇數量", weight="bold", color="#1E90FF"),
            TextComponent(text="高麗菜豬肉 (A)", size="lg", margin="md"),
            TextComponent(text="幾包？(0-15)", size="sm", color="#888888"),
        ]),
        footer=BoxComponent(layout="vertical", contents=rows + [make_cancel_button()], spacing="sm")
    )
    return FlexSendMessage(alt_text="選擇A數量", contents=bubble)

def qty_b_flex(max_b):
    buttons = []
    for i in range(0, max_b + 1):
        buttons.append(ButtonComponent(
            action=PostbackAction(label=str(i), data=f"action=qty_b&value={i}"),
            style="primary" if i > 0 else "secondary",
            color="#1E90FF" if i > 0 else "#AAAAAA",
            height="sm"
        ))
    rows = []
    row = []
    for btn in buttons:
        row.append(btn)
        if len(row) == 4:
            rows.append(BoxComponent(layout="horizontal", contents=row, spacing="sm"))
            row = []
    if row:
        rows.append(BoxComponent(layout="horizontal", contents=row, spacing="sm"))

    bubble = BubbleContainer(
        body=BoxComponent(layout="vertical", contents=[
            TextComponent(text="步驟 2/2 - 選擇數量", weight="bold", color="#1E90FF"),
            TextComponent(text="韭菜黑豬肉 (B)", size="lg", margin="md"),
            TextComponent(text=f"幾包？(0-{max_b})", size="sm", color="#888888"),
        ]),
        footer=BoxComponent(layout="vertical", contents=rows + [make_cancel_button()], spacing="sm")
    )
    return FlexSendMessage(alt_text="選擇B數量", contents=bubble)

def identity_flex(profile):
    bubble = BubbleContainer(
        body=BoxComponent(layout="vertical", contents=[
            TextComponent(text="找到上次資料", weight="bold", color="#1E90FF"),
            SeparatorComponent(margin="md"),
            TextComponent(text=f"姓名：{profile['name']}", size="sm", margin="md"),
            TextComponent(text=f"電話：{profile['phone']}", size="sm"),
            TextComponent(text=f"地址：{profile['address']}", size="sm", wrap=True),
        ]),
        footer=BoxComponent(layout="vertical", contents=[
            ButtonComponent(
                action=PostbackAction(label="✅ 沿用上次資料", data="action=use_existing"),
                style="primary", color="#1E90FF"
            ),
            ButtonComponent(
                action=PostbackAction(label="✏️ 重新填寫", data="action=new_info"),
                style="secondary", margin="sm"
            ),
            make_cancel_button()
        ])
    )
    return FlexSendMessage(alt_text="確認身份資料", contents=bubble)

def delivery_flex():
    bubble = BubbleContainer(
        body=BoxComponent(layout="vertical", contents=[
            TextComponent(text="選擇到貨時間", weight="bold", color="#1E90FF"),
            TextComponent(text="請選擇您方便收件的時間", size="sm", margin="md"),
        ]),
        footer=BoxComponent(layout="vertical", contents=[
            ButtonComponent(
                action=PostbackAction(label="平日", data="action=delivery&value=平日"),
                style="primary", color="#1E90FF"
            ),
            ButtonComponent(
                action=PostbackAction(label="禮拜六", data="action=delivery&value=禮拜六"),
                style="primary", color="#1E90FF", margin="sm"
            ),
            ButtonComponent(
                action=PostbackAction(label="皆可", data="action=delivery&value=皆可"),
                style="secondary", margin="sm"
            ),
            make_cancel_button()
        ])
    )
    return FlexSendMessage(alt_text="選擇到貨時間", contents=bubble)

def confirmation_flex(state):
    qty_a = state["qty_a"]
    qty_b = state["qty_b"]
    subtotal, shipping, total = calc_order(qty_a, qty_b)

    contents_text = []
    if qty_a > 0:
        contents_text.append(f"高麗菜豬肉 x{qty_a}包")
    if qty_b > 0:
        contents_text.append(f"韭菜黑豬肉 x{qty_b}包")

    bubble = BubbleContainer(
        body=BoxComponent(layout="vertical", contents=[
            TextComponent(text="📋 訂單確認", weight="bold", size="xl", color="#1E90FF"),
            SeparatorComponent(margin="md"),
            TextComponent(text="商品", weight="bold", margin="md"),
            TextComponent(text="\n".join(contents_text), size="sm", wrap=True),
            SeparatorComponent(margin="md"),
            TextComponent(text="收件資訊", weight="bold", margin="md"),
            TextComponent(text=f"姓名：{state['name']}", size="sm"),
            TextComponent(text=f"電話：{state['phone']}", size="sm"),
            TextComponent(text=f"地址：{state['address']}", size="sm", wrap=True),
            TextComponent(text=f"到貨：{state['delivery_time']}", size="sm"),
            SeparatorComponent(margin="md"),
            TextComponent(text=f"小計：NT${subtotal}", size="sm", margin="md"),
            TextComponent(text=f"運費：NT${shipping}", size="sm"),
            TextComponent(text=f"總計：NT${total}", weight="bold", size="lg", color="#FF6B6B"),
            SeparatorComponent(margin="md"),
            TextComponent(text="💳 付款資訊", weight="bold", margin="md", color="#1E90FF"),
            TextComponent(text="中國信託銀行 (822)", size="sm", margin="sm"),
            TextComponent(text="竹南分行", size="sm"),
            TextComponent(text="帳號：370540364486", size="sm"),
            TextComponent(text="戶名：徐志帆", size="sm"),
            TextComponent(
                text=f"請轉帳 NT${total} 並傳送截圖",
                size="sm", color="#1E90FF", weight="bold", wrap=True, margin="sm"
            ),
        ]),
        footer=BoxComponent(layout="vertical", contents=[
            ButtonComponent(
                action=PostbackAction(label="✅ 確認送出", data="action=confirm"),
                style="primary", color="#1E90FF"
            ),
            make_cancel_button()
        ])
    )
    return FlexSendMessage(alt_text="訂單確認", contents=bubble)

# ════════════════════════════════════════════════════════
#  Excel Export
# ════════════════════════════════════════════════════════

def export_orders():
    res = supabase.table("orders").select("*").eq("exported", False).execute()
    orders = res.data
    if not orders:
        return None, "目前沒有未匯出的訂單"

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Orders"

    headers = ["溫層", "姓名", "電話(空)", "手機", "地址", "出貨日期", "內容物", "類別", "到貨時間"]
    ws.append(headers)

    ids_to_update = []
    for order in orders:
        qty_a = order.get("qty_a", 0)
        qty_b = order.get("qty_b", 0)
        parts = []
        if qty_a > 0:
            parts.append(f"高麗菜豬肉x{qty_a}包")
        if qty_b > 0:
            parts.append(f"韭菜黑豬肉x{qty_b}包")
        content = "、".join(parts)

        ws.append([
            "冷凍",
            order.get("name", ""),
            "",
            order.get("phone", ""),
            order.get("address", ""),
            "",
            content,
            "冷凍食品",
            order.get("delivery_time", ""),
        ])
        ids_to_update.append(order["id"])

    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        ws.column_dimensions[col[0].column_letter].width = max_len + 4

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename  = f"orders_{timestamp}.xlsx"

    supabase.storage.from_("exports").upload(
        filename,
        buf.getvalue(),
        {"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
    )

    public_url = supabase.storage.from_("exports").get_public_url(filename)

    for oid in ids_to_update:
        supabase.table("orders").update({"exported": True}).eq("id", oid).execute()

    return public_url, f"✅ 匯出 {len(orders)} 筆訂單"

# ════════════════════════════════════════════════════════
#  Webhook
# ════════════════════════════════════════════════════════

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body      = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

# ── Follow Event ─────────────────────────────────────────
@handler.add(FollowEvent)
def handle_follow(event):
    uid = event.source.user_id
    reset_state(uid)
    line_bot_api.reply_message(event.reply_token, welcome_flex())

# ── Text Message ─────────────────────────────────────────
@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    uid  = event.source.user_id
    text = event.message.text.strip()

    # 群組匯出
    if hasattr(event.source, "group_id") and text == "匯出":
        url, msg = export_orders()
        if url:
            line_bot_api.reply_message(event.reply_token, [
                TextSendMessage(text=msg),
                TextSendMessage(text=f"📥 下載連結：\n{url}")
            ])
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=msg))
        return

    # 取消關鍵字
    if text in ["取消", "離開", "掰掰", "cancel"]:
        reset_state(uid)
        line_bot_api.reply_message(event.reply_token, [
            TextSendMessage(text="已取消訂單 👋"),
            welcome_flex()
        ])
        return

    # 開始 / 菜單關鍵字
    if text in ["開始", "訂購", "你好", "hi", "hello", "哈囉", "菜單"]:
        reset_state(uid)
        line_bot_api.reply_message(event.reply_token, welcome_flex())
        return

    state = get_state(uid)
    step  = state.get("step", 0)

    # 填寫姓名
    if step == 4:
        state["name"] = text
        state["step"] = 5
        set_state(uid, state)
        line_bot_api.reply_message(event.reply_token, [
            TextSendMessage(text="請輸入您的手機號碼："),
        ])
        return

    # 填寫電話
    if step == 5:
        state["phone"] = text
        state["step"]  = 6
        set_state(uid, state)
        line_bot_api.reply_message(event.reply_token, [
            TextSendMessage(text="請輸入收件地址："),
        ])
        return

    # 填寫地址
    if step == 6:
        state["address"] = text
        state["step"]    = 7
        set_state(uid, state)
        line_bot_api.reply_message(event.reply_token, delivery_flex())
        return

    # 預設
    line_bot_api.reply_message(event.reply_token, welcome_flex())

# ── Postback Event ────────────────────────────────────────
@handler.add(PostbackEvent)
def handle_postback(event):
    uid  = event.source.user_id
    data = event.postback.data
    params = dict(p.split("=") for p in data.split("&"))
    action = params.get("action")

    # 取消
    if action == "cancel":
        reset_state(uid)
        line_bot_api.reply_message(event.reply_token, [
            TextSendMessage(text="已取消訂單 👋"),
            welcome_flex()
        ])
        return

    # 開始
    if action == "start":
        reset_state(uid)
        state = {"step": 1}
        set_state(uid, state)
        line_bot_api.reply_message(event.reply_token, qty_a_flex())
        return

    state = get_state(uid)

    # 數量 A
    if action == "qty_a":
        qty_a = int(params.get("value", 0))
        state["qty_a"] = qty_a
        state["step"]  = 2
        set_state(uid, state)
        max_b = MAX_PACKS - qty_a
        if max_b == 0:
            # A已滿15包，B=0，跳到身份確認
            state["qty_b"] = 0
            state["step"]  = 3
            set_state(uid, state)
            profile = get_user_profile(uid)
            if profile:
                line_bot_api.reply_message(event.reply_token, identity_flex(profile))
            else:
                state["step"] = 4
                set_state(uid, state)
                line_bot_api.reply_message(event.reply_token, [
                    TextSendMessage(text="請輸入您的姓名：")
                ])
        else:
            line_bot_api.reply_message(event.reply_token, qty_b_flex(max_b))
        return

    # 數量 B
    if action == "qty_b":
        qty_b  = int(params.get("value", 0))
        qty_a  = state.get("qty_a", 0)
        total_packs = qty_a + qty_b

        if total_packs < MIN_PACKS:
            line_bot_api.reply_message(event.reply_token, [
                TextSendMessage(text=f"⚠️ 最少需訂購 {MIN_PACKS} 包，目前共 {total_packs} 包"),
                qty_b_flex(MAX_PACKS - qty_a)
            ])
            return

        state["qty_b"] = qty_b
        state["step"]  = 3
        set_state(uid, state)
        profile = get_user_profile(uid)
        if profile:
            line_bot_api.reply_message(event.reply_token, identity_flex(profile))
        else:
            state["step"] = 4
            set_state(uid, state)
            line_bot_api.reply_message(event.reply_token, [
                TextSendMessage(text="請輸入您的姓名：")
            ])
        return

    # 沿用舊資料
    if action == "use_existing":
        profile = get_user_profile(uid)
        state["name"]    = profile["name"]
        state["phone"]   = profile["phone"]
        state["address"] = profile["address"]
        state["step"]    = 7
        set_state(uid, state)
        line_bot_api.reply_message(event.reply_token, delivery_flex())
        return

    # 重新填寫
    if action == "new_info":
        state["step"] = 4
        set_state(uid, state)
        line_bot_api.reply_message(event.reply_token, [
            TextSendMessage(text="請輸入您的姓名：")
        ])
        return

    # 選擇到貨時間
    if action == "delivery":
        state["delivery_time"] = params.get("value", "皆可")
        state["step"]          = 8
        set_state(uid, state)
        line_bot_api.reply_message(event.reply_token, confirmation_flex(state))
        return

    # 確認訂單
    if action == "confirm":
        save_user_profile(uid, state["name"], state["phone"], state["address"])
        save_order(uid, state)

        qty_a = state["qty_a"]
        qty_b = state["qty_b"]
        subtotal, shipping, total = calc_order(qty_a, qty_b)

        # 通知老闆
        parts = []
        if qty_a > 0: parts.append(f"高麗菜豬肉x{qty_a}包")
        if qty_b > 0: parts.append(f"韭菜黑豬肉x{qty_b}包")

        owner_msg = (
            f"🔔 新訂單！\n"
            f"姓名：{state['name']}\n"
            f"電話：{state['phone']}\n"
            f"地址：{state['address']}\n"
            f"商品：{'、'.join(parts)}\n"
            f"到貨：{state['delivery_time']}\n"
            f"總計：NT${total}（運費NT${shipping}）"
        )
        try:
            line_bot_api.push_message(OWNER_ID, TextSendMessage(text=owner_msg))
        except Exception as e:
            print(f"Owner notify error: {e}")

        reset_state(uid)
        line_bot_api.reply_message(event.reply_token, [
            TextSendMessage(
                text=f"✅ 訂單已成功送出！\n\n"
                     f"請轉帳 NT${total} 至：\n"
                     f"中國信託(822) 竹南分行\n"
                     f"帳號：370540364486\n"
                     f"戶名：徐志帆\n\n"
                     f"轉帳後請傳截圖給我們，謝謝！🙏"
            )
        ])
        return

@app.route("/", methods=["GET"])
def index():
    return "A-MU Dumpling Bot is running! 🥟"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
