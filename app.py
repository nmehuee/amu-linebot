from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    QuickReply, QuickReplyButton, MessageAction
)
import os

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("CHANNEL_SECRET")
OWNER_ID = os.environ.get("OWNER_ID")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 儲存訂單狀態
user_states = {}

def get_state(user_id):
    if user_id not in user_states:
        user_states[user_id] = {"step": 0, "order": {}}
    return user_states[user_id]

def reset_state(user_id):
    user_states[user_id] = {"step": 0, "order": {}}

def calculate_order(qty_a, qty_b):
    total_qty = qty_a + qty_b
    subtotal = total_qty * 200
    shipping = 0 if subtotal >= 2000 else 170
    total = subtotal + shipping
    return subtotal, shipping, total

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
    state = get_state(user_id)
    step = state["step"]

    # 開始訂購
    if text in ["訂購", "開始訂購", "我要訂購"]:
        reset_state(user_id)
        state = get_state(user_id)
        state["step"] = 1
        reply = (
            "🥟 歡迎訂購 A-MU 水餃！\n\n"
            "【商品】\n"
            "A. 高麗菜韭黃黑豬肉 NT$200/包\n"
            "B. 韭黃黑豬肉 NT$200/包\n\n"
            "📦 最少2包，最多15包\n\n"
            "請輸入【A 高麗菜韭黃黑豬肉】數量（0～15）："
        )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # Step 1：輸入 A 數量
    if step == 1:
        if not text.isdigit():
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❌ 請輸入數字（0～15）："))
            return
        qty_a = int(text)
        if qty_a < 0 or qty_a > 15:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="❌ 數量需在 0～15 之間，請重新輸入："))
            return
        state["order"]["qty_a"] = qty_a
        if qty_a == 15:
            state["order"]["qty_b"] = 0
            state["step"] = 3
            reply = (
                "A 已選 15 包，B 自動設為 0 包。\n\n"
                "請輸入您的【姓名】："
            )
        else:
            remaining = 15 - qty_a
            min_b = max(0, 2 - qty_a)
            state["step"] = 2
            reply = (
                f"A 已選 {qty_a} 包\n"
                f"請輸入【B 韭黃黑豬肉】數量（{min_b}～{remaining}）："
            )
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # Step 2：輸入 B 數量
    if step == 2:
        qty_a = state["order"]["qty_a"]
        remaining = 15 - qty_a
        min_b = max(0, 2 - qty_a)
        if not text.isdigit():
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"❌ 請輸入數字（{min_b}～{remaining}）："))
            return
        qty_b = int(text)
        if qty_b < min_b or qty_b > remaining:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=f"❌ 數量需在 {min_b}～{remaining} 之間，請重新輸入："))
            return
        state["order"]["qty_b"] = qty_b
        state["step"] = 3
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請輸入您的【姓名】："))
        return

    # Step 3：輸入姓名
    if step == 3:
        state["order"]["name"] = text
        state["step"] = 4
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請輸入您的【手機號碼】："))
        return

    # Step 4：輸入電話
    if step == 4:
        state["order"]["phone"] = text
        state["step"] = 5
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請輸入【收貨地址】："))
        return

    # Step 5：輸入地址 → 送出到貨時間選項
    if step == 5:
        state["order"]["address"] = text
        state["step"] = 6
        quick_reply = QuickReply(items=[
            QuickReplyButton(action=MessageAction(label="平日", text="平日")),
            QuickReplyButton(action=MessageAction(label="禮拜六", text="禮拜六")),
            QuickReplyButton(action=MessageAction(label="皆可", text="皆可")),
        ])
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="請選擇【希望到貨時間】：", quick_reply=quick_reply)
        )
        return

    # Step 6：收到到貨時間選項
    if step == 6:
        if text not in ["平日", "禮拜六", "皆可"]:
            quick_reply = QuickReply(items=[
                QuickReplyButton(action=MessageAction(label="平日", text="平日")),
                QuickReplyButton(action=MessageAction(label="禮拜六", text="禮拜六")),
                QuickReplyButton(action=MessageAction(label="皆可", text="皆可")),
            ])
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="❌ 請點選下方按鈕選擇到貨時間：", quick_reply=quick_reply)
            )
            return
        state["order"]["delivery_time"] = text
        state["step"] = 7
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="請輸入【備註】（無則輸入「無」）："))
        return

    # Step 7：輸入備註，完成訂單
    if step == 7:
        state["order"]["remarks"] = text
        order = state["order"]
        qty_a = order["qty_a"]
        qty_b = order["qty_b"]
        subtotal, shipping, total = calculate_order(qty_a, qty_b)

        # 用戶確認訊息
        user_msg = (
            f"✅ 訂單確認！\n"
            f"{'─'*20}\n"
            f"🥟 高麗菜韭黃黑豬肉：{qty_a} 包\n"
            f"🥟 韭黃黑豬肉：{qty_b} 包\n"
            f"{'─'*20}\n"
            f"小計：NT${subtotal}\n"
            f"運費：NT${shipping}\n"
            f"💰 總計：NT${total}\n"
            f"{'─'*20}\n"
            f"姓名：{order['name']}\n"
            f"電話：{order['phone']}\n"
            f"地址：{order['address']}\n"
            f"到貨時間：{order['delivery_time']}\n"
            f"備註：{order['remarks']}\n"
            f"{'─'*20}\n\n"
            f"💳 請匯款至：\n"
            f"銀行：中國信託(822)\n"
            f"帳號：370540364486\n"
            f"戶名：徐志帆\n\n"
            f"匯款後請傳匯款截圖，我們確認後將盡快安排出貨！🙏"
        )

        # 店家通知訊息
        owner_msg = (
            f"🔔 新訂單通知！\n"
            f"{'─'*20}\n"
            f"🥟 高麗菜韭黃黑豬肉：{qty_a} 包\n"
            f"🥟 韭黃黑豬肉：{qty_b} 包\n"
            f"{'─'*20}\n"
            f"小計：NT${subtotal}\n"
            f"運費：NT${shipping}\n"
            f"💰 總計：NT${total}\n"
            f"{'─'*20}\n"
            f"姓名：{order['name']}\n"
            f"電話：{order['phone']}\n"
            f"地址：{order['address']}\n"
            f"到貨時間：{order['delivery_time']}\n"
            f"備註：{order['remarks']}\n"
            f"User ID：{user_id}"
        )

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=user_msg))
        if OWNER_ID:
            line_bot_api.push_message(OWNER_ID, TextSendMessage(text=owner_msg))

        reset_state(user_id)
        return

    # 預設回覆
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="請輸入「訂購」開始訂單 🥟")
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
