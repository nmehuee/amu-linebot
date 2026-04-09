from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    QuickReply, QuickReplyButton, MessageAction
)
import os
import json

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET')
OWNER_ID = os.environ.get('OWNER_ID')

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# 暫存使用者狀態
user_states = {}

PRODUCT_A = "高麗菜韭黃黑豬水餃"
PRODUCT_B = "韭黃黑豬水餃"
PRICE = 200
SHIPPING = 170
FREE_SHIPPING = 2000
MIN_ORDER = 2
MAX_ORDER = 15

def get_quick_reply_numbers(max_num=15):
    items = []
    for i in range(0, max_num + 1):
        items.append(
            QuickReplyButton(
                action=MessageAction(label=str(i), text=str(i))
            )
        )
    return QuickReply(items=items)

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    # 查詢自己的ID
    if text == "我的ID":
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"你的 User ID 是：\n{user_id}")
        )
        return

    # 開始訂購
    if text == "開始訂購":
        user_states[user_id] = {"step": "select_a"}
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=f"🥟 請選擇「{PRODUCT_A}」的數量：\n（最多可選 {MAX_ORDER} 包）",
                quick_reply=get_quick_reply_numbers(MAX_ORDER)
            )
        )
        return

    # 取得使用者狀態
    state = user_states.get(user_id, {})
    step = state.get("step", "")

    # 第一步：選 A 數量
    if step == "select_a":
        if not text.isdigit():
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f"⚠️ 請用下方按鈕選擇數量！",
                    quick_reply=get_quick_reply_numbers(MAX_ORDER)
                )
            )
            return

        qty_a = int(text)
        if qty_a > MAX_ORDER:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f"⚠️ 已超過最大訂購量（{MAX_ORDER}包）！\n請重新選擇：",
                    quick_reply=get_quick_reply_numbers(MAX_ORDER)
                )
            )
            return

        state["qty_a"] = qty_a
        state["step"] = "select_b"
        user_states[user_id] = state

        # 計算 B 的最大可選數量
        max_b = MAX_ORDER - qty_a

        if max_b == 0:
            # A 已選滿 15 包，B 只能選 0
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f"🥟 請選擇「{PRODUCT_B}」的數量：\n（{PRODUCT_A} 已選 {qty_a} 包，已達上限，{PRODUCT_B} 只能選 0）",
                    quick_reply=QuickReply(items=[
                        QuickReplyButton(action=MessageAction(label="0", text="0"))
                    ])
                )
            )
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f"🥟 請選擇「{PRODUCT_B}」的數量：\n（{PRODUCT_A} 已選 {qty_a} 包，{PRODUCT_B} 最多可選 {max_b} 包）",
                    quick_reply=get_quick_reply_numbers(max_b)
                )
            )
        return

    # 第二步：選 B 數量
    if step == "select_b":
        if not text.isdigit():
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f"⚠️ 請用下方按鈕選擇數量！",
                    quick_reply=get_quick_reply_numbers(MAX_ORDER - state.get("qty_a", 0))
                )
            )
            return

        qty_b = int(text)
        qty_a = state.get("qty_a", 0)
        max_b = MAX_ORDER - qty_a

        if qty_b > max_b:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f"⚠️ 已超過最大訂購量！\n{PRODUCT_A} 已選 {qty_a} 包，{PRODUCT_B} 最多只能選 {max_b} 包\n請重新選擇：",
                    quick_reply=get_quick_reply_numbers(max_b)
                )
            )
            return

        total_qty = qty_a + qty_b

        # 檢查最小訂購量
        if total_qty < MIN_ORDER:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f"⚠️ 最少需訂購 {MIN_ORDER} 包！\n目前合計：{total_qty} 包\n請重新選擇「{PRODUCT_A}」的數量：",
                    quick_reply=get_quick_reply_numbers(MAX_ORDER)
                )
            )
            state["step"] = "select_a"
            user_states[user_id] = state
            return

        state["qty_b"] = qty_b
        state["step"] = "input_name"
        user_states[user_id] = state

        # 計算金額
        subtotal = total_qty * PRICE
        shipping = 0 if subtotal >= FREE_SHIPPING else SHIPPING
        total = subtotal + shipping

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=(
                    f"✅ 數量確認：\n"
                    f"・{PRODUCT_A}：{qty_a} 包\n"
                    f"・{PRODUCT_B}：{qty_b} 包\n"
                    f"・合計：{total_qty} 包\n"
                    f"・小計：NT${subtotal}\n"
                    f"・運費：NT${shipping}\n"
                    f"・總金額：NT${total}\n\n"
                    f"📝 請輸入您的姓名："
                )
            )
        )
        return

    # 第三步：輸入姓名
    if step == "input_name":
        state["name"] = text
        state["step"] = "input_phone"
        user_states[user_id] = state
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="📞 請輸入您的電話號碼：")
        )
        return

    # 第四步：輸入電話
    if step == "input_phone":
        state["phone"] = text
        state["step"] = "input_address"
        user_states[user_id] = state
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="🏠 請輸入收貨地址：")
        )
        return

    # 第五步：輸入地址
    if step == "input_address":
        state["address"] = text
        state["step"] = "input_time"
        user_states[user_id] = state
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="🕐 請輸入希望到貨時間：\n（例如：2024/12/25 下午）")
        )
        return

    # 第六步：輸入到貨時間
    if step == "input_time":
        state["time"] = text
        state["step"] = "input_remark"
        user_states[user_id] = state
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="💬 請輸入備註：\n（沒有備註請輸入「無」）")
        )
        return

    # 第七步：輸入備註 → 產生訂單
    if step == "input_remark":
        state["remark"] = text
        user_states[user_id] = state

        qty_a = state.get("qty_a", 0)
        qty_b = state.get("qty_b", 0)
        total_qty = qty_a + qty_b
        subtotal = total_qty * PRICE
        shipping = 0 if subtotal >= FREE_SHIPPING else SHIPPING
        total = subtotal + shipping

        order_summary = (
            f"📦 訂單確認\n"
            f"{'─' * 20}\n"
            f"🥟 {PRODUCT_A}：{qty_a} 包\n"
            f"🥟 {PRODUCT_B}：{qty_b} 包\n"
            f"{'─' * 20}\n"
            f"小計：NT${subtotal}\n"
            f"運費：NT${shipping}\n"
            f"💰 總金額：NT${total}\n"
            f"{'─' * 20}\n"
            f"👤 姓名：{state['name']}\n"
            f"📞 電話：{state['phone']}\n"
            f"🏠 地址：{state['address']}\n"
            f"🕐 到貨時間：{state['time']}\n"
            f"💬 備註：{state['remark']}\n"
            f"{'─' * 20}\n"
            f"💳 付款資訊\n"
            f"銀行：國泰世華銀行（822）\n"
            f"帳號：370540364486\n"
            f"戶名：徐志帆\n"
            f"{'─' * 20}\n"
            f"請於 24 小時內完成匯款\n"
            f"匯款後請傳收據照片給我們 📸"
        )

        # 回覆顧客
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=order_summary)
        )

        # 通知老闆
        if OWNER_ID:
            owner_message = (
                f"🔔 新訂單通知！\n"
                f"{'─' * 20}\n"
                f"🥟 {PRODUCT_A}：{qty_a} 包\n"
                f"🥟 {PRODUCT_B}：{qty_b} 包\n"
                f"合計：{total_qty} 包\n"
                f"{'─' * 20}\n"
                f"小計：NT${subtotal}\n"
                f"運費：NT${shipping}\n"
                f"💰 總金額：NT${total}\n"
                f"{'─' * 20}\n"
                f"👤 姓名：{state['name']}\n"
                f"📞 電話：{state['phone']}\n"
                f"🏠 地址：{state['address']}\n"
                f"🕐 到貨時間：{state['time']}\n"
                f"💬 備註：{state['remark']}\n"
                f"{'─' * 20}\n"
                f"顧客 ID：{user_id}"
            )
            line_bot_api.push_message(
                OWNER_ID,
                TextSendMessage(text=owner_message)
            )

        # 清除狀態
        user_states.pop(user_id, None)
        return

    # 預設回覆
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(
            text="歡迎光臨 A-MU 水餃！🥟\n請輸入「開始訂購」來下單",
        )
    )

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
