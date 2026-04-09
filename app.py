from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
OWNER_ID = os.environ.get("OWNER_ID")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 儲存用戶狀態
user_states = {}

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    if user_id not in user_states:
        user_states[user_id] = {"step": "idle"}

    state = user_states[user_id]
    step = state.get("step")

    # ── 開始訂購 ──
    if text in ["開始訂購", "訂購", "order", "Order"]:
        user_states[user_id] = {"step": "select_a"}
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=(
                    "🥟 A-MU 水餃訂購開始！\n"
                    "══════════════════\n"
                    "【A款】高麗菜韭黃黑豬肉水餃\n"
                    "【B款】韭黃黑豬肉水餃\n"
                    "每包 NT$200｜最少2包｜最多15包\n"
                    "══════════════════\n"
                    "請輸入【A款】數量（0～15）："
                )
            )
        )
        return

    # ── 選擇 A 數量 ──
    if step == "select_a":
        if not text.isdigit():
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="⚠️ 請輸入數字（0～15）：")
            )
            return

        qty_a = int(text)

        if qty_a < 0 or qty_a > 15:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="⚠️ 數量需介於 0～15，請重新輸入【A款】數量：")
            )
            return

        state["qty_a"] = qty_a
        state["step"] = "select_b"

        if qty_a == 15:
            # A已達上限，B自動為0
            state["qty_b"] = 0
            state["step"] = "input_name"
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=(
                        f"✅ A款：15 包（已達上限，B款自動設為 0）\n\n"
                        f"請輸入您的姓名："
                    )
                )
            )
        else:
            remaining = 15 - qty_a
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=(
                        f"✅ A款：{qty_a} 包\n"
                        f"請輸入【B款】數量（0～{remaining}）："
                    )
                )
            )
        return

    # ── 選擇 B 數量 ──
    if step == "select_b":
        qty_a = state.get("qty_a", 0)
        remaining = 15 - qty_a

        if not text.isdigit():
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"⚠️ 請輸入數字（0～{remaining}）：")
            )
            return

        qty_b = int(text)

        if qty_b < 0 or qty_b > remaining:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f"⚠️ B款數量需介於 0～{remaining}，請重新輸入："
                )
            )
            return

        total = qty_a + qty_b

        if total < 2:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=(
                        f"⚠️ 合計僅 {total} 包，最少需訂購 2 包！\n"
                        f"請重新傳送「開始訂購」"
                    )
                )
            )
            user_states[user_id] = {"step": "idle"}
            return

        state["qty_b"] = qty_b
        state["step"] = "input_name"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=(
                    f"✅ B款：{qty_b} 包\n"
                    f"合計：{total} 包\n\n"
                    f"請輸入您的姓名："
                )
            )
        )
        return

    # ── 輸入姓名 ──
    if step == "input_name":
        state["name"] = text
        state["step"] = "input_phone"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="請輸入您的電話號碼：")
        )
        return

    # ── 輸入電話 ──
    if step == "input_phone":
        state["phone"] = text
        state["step"] = "input_address"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="請輸入收件地址：")
        )
        return

    # ── 輸入地址 ──
    if step == "input_address":
        state["address"] = text
        state["step"] = "input_time"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text="請輸入希望到貨時間：\n（例：2026/04/15 上午）"
            )
        )
        return

    # ── 輸入到貨時間 ──
    if step == "input_time":
        state["time"] = text
        state["step"] = "input_remark"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="請輸入備註：\n（無備註請輸入「無」）")
        )
        return

    # ── 輸入備註 → 完成訂單 ──
    if step == "input_remark":
        state["remark"] = text
        state["step"] = "done"

        qty_a = state.get("qty_a", 0)
        qty_b = state.get("qty_b", 0)
        total_qty = qty_a + qty_b
        subtotal = total_qty * 200
        shipping = 0 if subtotal >= 2000 else 170
        total_price = subtotal + shipping

        order_summary = (
            f"📦 訂單確認\n"
            f"══════════════════\n"
            f"🥟 A款 高麗菜韭黃黑豬肉：{qty_a} 包\n"
            f"🥟 B款 韭黃黑豬肉：{qty_b} 包\n"
            f"══════════════════\n"
            f"合計數量：{total_qty} 包\n"
            f"商品金額：NT${subtotal}\n"
            f"運　　費：{'免運 🎉' if shipping == 0 else f'NT${shipping}'}\n"
            f"💰 總金額：NT${total_price}\n"
            f"══════════════════\n"
            f"👤 姓　名：{state['name']}\n"
            f"📞 電　話：{state['phone']}\n"
            f"📍 地　址：{state['address']}\n"
            f"🕐 到貨時間：{state['time']}\n"
            f"📝 備　註：{state['remark']}\n"
            f"══════════════════\n"
            f"💳 匯款資訊\n"
            f"銀行：中國信託(822)\n"
            f"帳號：370540364486\n"
            f"戶名：徐志帆\n"
            f"══════════════════\n"
            f"請於 3 天內完成匯款\n"
            f"匯款後請傳末五碼給我們，謝謝！🙏"
        )

        # 回覆用戶
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=order_summary)
        )

        # 通知老闆
        if OWNER_ID:
            owner_msg = (
                f"🔔 新訂單通知！\n"
                f"══════════════════\n"
                f"🥟 A款 高麗菜韭黃黑豬肉：{qty_a} 包\n"
                f"🥟 B款 韭黃黑豬肉：{qty_b} 包\n"
                f"合計：{total_qty} 包｜NT${total_price}\n"
                f"══════════════════\n"
                f"👤 {state['name']}｜📞 {state['phone']}\n"
                f"📍 {state['address']}\n"
                f"🕐 {state['time']}\n"
                f"📝 {state['remark']}"
            )
            line_bot_api.push_message(OWNER_ID, TextSendMessage(text=owner_msg))

        user_states[user_id] = {"step": "idle"}
        return

    # ── 預設回覆 ──
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(
            text=(
                "您好！歡迎光臨 A-MU 水餃 🥟\n"
                "請傳送「開始訂購」來下訂單！"
            )
        )
    )

if __name__ == "__main__":
    app.run()
