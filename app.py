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

user_states = {}
user_profiles = {}

# ─────────────────────────────────────────
# 常數：取消按鈕（單獨）
# ─────────────────────────────────────────
CANCEL_QR = QuickReply(items=[
    QuickReplyButton(action=MessageAction(label="❌ 取消訂單", text="取消")),
])


# ─────────────────────────────────────────
# 工具函式
# ─────────────────────────────────────────
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

def cancel_order(user_id, reply_token):
    """取消訂單，重置狀態，回覆取消訊息 + 重新開始按鈕"""
    reset_state(user_id)
    quick_reply = QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="🛒 開始訂購", text="開始訂購")),
    ])
    line_bot_api.reply_message(
        reply_token,
        TextSendMessage(
            text="已取消訂單，歡迎下次再來！😊\n\n點下方按鈕可重新開始訂購：",
            quick_reply=quick_reply
        )
    )


# ─────────────────────────────────────────
# Webhook 入口
# ─────────────────────────────────────────
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"


# ─────────────────────────────────────────
# 主要訊息處理
# ─────────────────────────────────────────
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    # 忽略群組訊息（只用來取得 Group ID）
    if event.source.type == "group":
        print(f"✅ Group ID: {event.source.group_id}")
        return

    user_id = event.source.user_id
    text = event.message.text.strip()
    state = get_state(user_id)
    step = state["step"]

    # ── 任何步驟都可取消（step > 0）──
    if text in ["取消", "離開", "掰掰"] and step > 0:
        cancel_order(user_id, event.reply_token)
        return

    # ── Step 0：歡迎頁 ──
    if step == 0 or text in ["訂購", "開始訂購", "我要訂購", "你好", "hi", "Hi", "Hello", "hello"]:
        reset_state(user_id)
        state = get_state(user_id)

        if text in ["開始訂購", "訂購", "我要訂購"]:
            # 直接進入 Step 1
            state["step"] = 1
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text="🥟 請輸入【A 高麗菜韭黃黑豬肉】數量（0～15）：",
                    quick_reply=CANCEL_QR
                )
            )
        else:
            # 顯示歡迎頁 + 開始訂購按鈕
            state["step"] = 0
            quick_reply = QuickReply(items=[
                QuickReplyButton(action=MessageAction(label="🛒 開始訂購", text="開始訂購")),
            ])
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=(
                        "👋 歡迎來到 A-MU 水餃！\n\n"
                        "【商品】\n"
                        "🥟 A. 高麗菜韭黃黑豬肉 NT$200/包\n"
                        "🥟 B. 韭黃黑豬肉 NT$200/包\n\n"
                        "📦 最少2包，最多15包\n"
                        "🚚 滿NT$2000免運，未滿運費NT$170\n\n"
                        "點下方按鈕開始訂購！"
                    ),
                    quick_reply=quick_reply
                )
            )
        return

    # ── Step 1：輸入 A 數量 ──
    if step == 1:
        if not text.isdigit():
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text="❌ 請輸入數字（0～15）：",
                    quick_reply=CANCEL_QR
                )
            )
            return

        qty_a = int(text)
        if qty_a < 0 or qty_a > 15:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text="❌ 數量需在 0～15 之間，請重新輸入：",
                    quick_reply=CANCEL_QR
                )
            )
            return

        state["order"]["qty_a"] = qty_a

        if qty_a == 15:
            # A 選滿，B 自動為 0，跳到身份確認
            state["order"]["qty_b"] = 0
            _go_to_name_step(user_id, event.reply_token, state)
        else:
            remaining = 15 - qty_a
            min_b = max(0, 2 - qty_a)
            state["step"] = 2
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f"A 已選 {qty_a} 包\n請輸入【B 韭黃黑豬肉】數量（{min_b}～{remaining}）：",
                    quick_reply=CANCEL_QR
                )
            )
        return

    # ── Step 2：輸入 B 數量 ──
    if step == 2:
        qty_a = state["order"]["qty_a"]
        remaining = 15 - qty_a
        min_b = max(0, 2 - qty_a)

        if not text.isdigit():
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f"❌ 請輸入數字（{min_b}～{remaining}）：",
                    quick_reply=CANCEL_QR
                )
            )
            return

        qty_b = int(text)
        if qty_b < min_b or qty_b > remaining:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f"❌ 數量需在 {min_b}～{remaining} 之間，請重新輸入：",
                    quick_reply=CANCEL_QR
                )
            )
            return

        state["order"]["qty_b"] = qty_b
        _go_to_name_step(user_id, event.reply_token, state)
        return

    # ── Step 3：沿用 or 重新填寫 or 輸入姓名 ──
    if step == 3:
        if text == "沿用上次資料":
            profile = user_profiles.get(user_id)
            if profile:
                state["order"]["name"] = profile["name"]
                state["order"]["phone"] = profile["phone"]
                state["order"]["address"] = profile["address"]
                state["step"] = 6
                _ask_delivery_time(event.reply_token)
            else:
                # 資料消失（重啟後），改為詢問姓名
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(
                        text="找不到上次資料，請輸入您的【姓名】：",
                        quick_reply=CANCEL_QR
                    )
                )
            return

        if text == "重新填寫資料":
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text="請輸入您的【姓名】：",
                    quick_reply=CANCEL_QR
                )
            )
            return

        # 直接輸入姓名
        state["order"]["name"] = text
        state["step"] = 4
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text="請輸入您的【手機號碼】：",
                quick_reply=CANCEL_QR
            )
        )
        return

    # ── Step 4：輸入電話 ──
    if step == 4:
        state["order"]["phone"] = text
        state["step"] = 5
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text="請輸入【收貨地址】：",
                quick_reply=CANCEL_QR
            )
        )
        return

    # ── Step 5：輸入地址 ──
    if step == 5:
        state["order"]["address"] = text
        state["step"] = 6
        _ask_delivery_time(event.reply_token)
        return

    # ── Step 6：選擇到貨時間 ──
    if step == 6:
        if text not in ["平日", "禮拜六", "皆可"]:
            _ask_delivery_time(event.reply_token, error=True)
            return
        state["order"]["delivery_time"] = text
        state["step"] = 7
        _show_confirm(event.reply_token, state)
        return

    # ── Step 7：確認送出 ──
    if step == 7:
        if text == "重新填寫":
            reset_state(user_id)
            state = get_state(user_id)
            state["step"] = 1
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text="🔄 重新開始！\n\n請輸入【A 高麗菜韭黃黑豬肉】數量（0～15）：",
                    quick_reply=CANCEL_QR
                )
            )
            return

        if text == "確認送出":
            order = state["order"]
            qty_a = order["qty_a"]
            qty_b = order["qty_b"]
            subtotal, shipping, total = calculate_order(qty_a, qty_b)

            # 儲存客戶資料
            user_profiles[user_id] = {
                "name": order["name"],
                "phone": order["phone"],
                "address": order["address"]
            }

            user_msg = (
                f"✅ 訂單已送出！\n"
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
                f"{'─'*20}\n\n"
                f"💳 請匯款至：\n"
                f"銀行：中國信託(822)\n"
                f"帳號：370540364486\n"
                f"戶名：徐志帆\n\n"
                f"匯款後請告知帳號後5碼，確認後將盡快安排出貨！🙏"
            )

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
                f"User ID：{user_id}"
            )

            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=user_msg))
            if OWNER_ID:
                line_bot_api.push_message(OWNER_ID, TextSendMessage(text=owner_msg))

            reset_state(user_id)
            return

        # 亂打字 → 重新顯示確認頁
        _show_confirm(event.reply_token, state)
        return

    # ── 預設回覆（理論上不會到這裡）──
    quick_reply = QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="🛒 開始訂購", text="開始訂購")),
    ])
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(
            text="👋 歡迎來到 A-MU 水餃！\n點下方按鈕開始訂購 🥟",
            quick_reply=quick_reply
        )
    )


# ─────────────────────────────────────────
# 輔助函式
# ─────────────────────────────────────────

def _go_to_name_step(user_id, reply_token, state):
    """判斷是否有舊資料，決定顯示沿用按鈕或直接問姓名"""
    profile = user_profiles.get(user_id)
    state["step"] = 3

    if profile:
        quick_reply = QuickReply(items=[
            QuickReplyButton(action=MessageAction(label="✅ 沿用上次資料", text="沿用上次資料")),
            QuickReplyButton(action=MessageAction(label="✏️ 重新填寫", text="重新填寫資料")),
            QuickReplyButton(action=MessageAction(label="❌ 取消訂單", text="取消")),
        ])
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(
                text=(
                    f"查到您上次的資料：\n"
                    f"{'─'*20}\n"
                    f"姓名：{profile['name']}\n"
                    f"電話：{profile['phone']}\n"
                    f"地址：{profile['address']}\n"
                    f"{'─'*20}\n"
                    f"是否沿用上次資料？"
                ),
                quick_reply=quick_reply
            )
        )
    else:
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(
                text="請輸入您的【姓名】：",
                quick_reply=CANCEL_QR
            )
        )


def _ask_delivery_time(reply_token, error=False):
    """顯示到貨時間選項"""
    quick_reply = QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="平日", text="平日")),
        QuickReplyButton(action=MessageAction(label="禮拜六", text="禮拜六")),
        QuickReplyButton(action=MessageAction(label="皆可", text="皆可")),
        QuickReplyButton(action=MessageAction(label="❌ 取消訂單", text="取消")),
    ])
    msg = "❌ 請點選下方按鈕選擇到貨時間：" if error else "請選擇【希望到貨時間】："
    line_bot_api.reply_message(
        reply_token,
        TextSendMessage(text=msg, quick_reply=quick_reply)
    )


def _show_confirm(reply_token, state):
    """顯示訂單確認頁"""
    order = state["order"]
    qty_a = order["qty_a"]
    qty_b = order["qty_b"]
    subtotal, shipping, total = calculate_order(qty_a, qty_b)

    confirm_msg = (
        f"📋 請確認您的訂單：\n"
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
        f"{'─'*20}\n\n"
        f"請確認資料是否正確？"
    )

    quick_reply = QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="✅ 確認送出", text="確認送出")),
        QuickReplyButton(action=MessageAction(label="✏️ 重新填寫", text="重新填寫")),
        QuickReplyButton(action=MessageAction(label="❌ 取消訂單", text="取消")),
    ])
    line_bot_api.reply_message(
        reply_token,
        TextSendMessage(text=confirm_msg, quick_reply=quick_reply)
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
