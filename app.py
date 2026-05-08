import os
import json
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, PostbackEvent,
    FlexSendMessage, TextSendMessage
)

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET')

if not CHANNEL_ACCESS_TOKEN:
    raise ValueError("CHANNEL_ACCESS_TOKEN is not set")
if not CHANNEL_SECRET:
    raise ValueError("CHANNEL_SECRET is not set")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ── 記憶體狀態管理 ──
user_states = {}
user_orders = {}

PRICE_PER_PACK = 200
MIN_PACKS = 4
MAX_PACKS = 12

def get_shipping_fee(total_packs):
    if total_packs >= 12:
        return 0
    elif total_packs >= 10:
        return 100
    elif total_packs >= 7:
        return 150
    else:
        return 175

# ══════════════════════════════════════════
#  共用按鈕
# ══════════════════════════════════════════
def btn_cancel():
    return {
        "type": "button",
        "action": {
            "type": "postback",
            "label": "取消訂單",
            "data": "cancel_order"
        },
        "style": "secondary",
        "height": "sm"
    }

# ══════════════════════════════════════════
#  Flex Messages
# ══════════════════════════════════════════
def make_welcome_flex():
    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {
                    "type": "text",
                    "text": "歡迎來到 A-MU水餃",
                    "weight": "bold",
                    "size": "lg",
                    "wrap": True
                },
                {"type": "separator"},
                {
                    "type": "text",
                    "text": "商品介紹",
                    "weight": "bold",
                    "size": "sm"
                },
                {
                    "type": "text",
                    "text": "高麗菜韭黃黑豬肉水餃 NT$200/包\n韭菜黑豬肉水餃 NT$200/包",
                    "size": "sm",
                    "color": "#333333",
                    "wrap": True
                },
                {"type": "separator"},
                {
                    "type": "text",
                    "text": "運費說明",
                    "weight": "bold",
                    "size": "sm"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "4 ~ 6 包",
                                    "size": "sm",
                                    "color": "#333333",
                                    "flex": 3
                                },
                                {
                                    "type": "text",
                                    "text": "運費 NT$175",
                                    "size": "sm",
                                    "color": "#E05C5C",
                                    "flex": 4,
                                    "weight": "bold"
                                },
                                {
                                    "type": "text",
                                    "text": "入門首選",
                                    "size": "sm",
                                    "color": "#888888",
                                    "flex": 3
                                }
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "7 ~ 9 包",
                                    "size": "sm",
                                    "color": "#333333",
                                    "flex": 3
                                },
                                {
                                    "type": "text",
                                    "text": "運費 NT$150",
                                    "size": "sm",
                                    "color": "#E05C5C",
                                    "flex": 4,
                                    "weight": "bold"
                                },
                                {
                                    "type": "text",
                                    "text": "人氣推薦",
                                    "size": "sm",
                                    "color": "#888888",
                                    "flex": 3
                                }
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "10 ~ 11 包",
                                    "size": "sm",
                                    "color": "#333333",
                                    "flex": 3
                                },
                                {
                                    "type": "text",
                                    "text": "運費 NT$100",
                                    "size": "sm",
                                    "color": "#E05C5C",
                                    "flex": 4,
                                    "weight": "bold"
                                },
                                {
                                    "type": "text",
                                    "text": "超值精選",
                                    "size": "sm",
                                    "color": "#888888",
                                    "flex": 3
                                }
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "12 包",
                                    "size": "sm",
                                    "color": "#333333",
                                    "flex": 3
                                },
                                {
                                    "type": "text",
                                    "text": "免運費",
                                    "size": "sm",
                                    "color": "#27AE60",
                                    "flex": 4,
                                    "weight": "bold"
                                },
                                {
                                    "type": "text",
                                    "text": "最划算",
                                    "size": "sm",
                                    "color": "#888888",
                                    "flex": 3
                                }
                            ]
                        }
                    ]
                },
                {"type": "separator"},
                {
                    "type": "text",
                    "text": "最少4包，最多12包",
                    "size": "sm",
                    "color": "#888888",
                    "wrap": True
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "了解，開始訂購",
                        "data": "welcome_confirm"
                    },
                    "style": "primary",
                    "color": "#E05C5C",
                    "height": "sm"
                },
                btn_cancel()
            ]
        }
    }
    return FlexSendMessage(alt_text='歡迎來到 A-MU水餃', contents=bubble)


def make_cabbage_flex(order):
    remaining = MAX_PACKS - order.get('chives', 0)
    max_cabbage = min(remaining, MAX_PACKS)

    buttons = []
    for i in range(0, max_cabbage + 1):
        buttons.append({
            "type": "button",
            "action": {
                "type": "postback",
                "label": f"{i} 包",
                "data": f"cabbage_{i}"
            },
            "style": "primary" if i > 0 else "secondary",
            "color": "#E05C5C" if i > 0 else "#AAAAAA",
            "height": "sm"
        })

    rows = []
    row = []
    for idx, btn in enumerate(buttons):
        row.append(btn)
        if len(row) == 4:
            rows.append({
                "type": "box",
                "layout": "horizontal",
                "spacing": "sm",
                "contents": row
            })
            row = []
    if row:
        rows.append({
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": row
        })

    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {
                    "type": "text",
                    "text": "高麗菜韭黃黑豬肉水餃",
                    "weight": "bold",
                    "size": "md",
                    "wrap": True
                },
                {
                    "type": "text",
                    "text": f"NT$200/包｜請選擇數量（0～{max_cabbage} 包）",
                    "size": "sm",
                    "color": "#888888",
                    "wrap": True
                },
                {"type": "separator"},
                *rows
            ]
        },
        "footer": {
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": [btn_cancel()]
        }
    }
    return FlexSendMessage(alt_text='選擇高麗菜韭黃水餃數量', contents=bubble)


def make_chives_flex(order):
    cabbage = order.get('cabbage', 0)
    remaining = MAX_PACKS - cabbage
    max_chives = min(remaining, MAX_PACKS)

    buttons = []
    for i in range(0, max_chives + 1):
        buttons.append({
            "type": "button",
            "action": {
                "type": "postback",
                "label": f"{i} 包",
                "data": f"chives_{i}"
            },
            "style": "primary" if i > 0 else "secondary",
            "color": "#E05C5C" if i > 0 else "#AAAAAA",
            "height": "sm"
        })

    rows = []
    row = []
    for idx, btn in enumerate(buttons):
        row.append(btn)
        if len(row) == 4:
            rows.append({
                "type": "box",
                "layout": "horizontal",
                "spacing": "sm",
                "contents": row
            })
            row = []
    if row:
        rows.append({
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": row
        })

    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {
                    "type": "text",
                    "text": "韭菜黑豬肉水餃",
                    "weight": "bold",
                    "size": "md",
                    "wrap": True
                },
                {
                    "type": "text",
                    "text": f"NT$200/包｜請選擇數量（0～{max_chives} 包）",
                    "size": "sm",
                    "color": "#888888",
                    "wrap": True
                },
                {
                    "type": "text",
                    "text": f"已選高麗菜水餃：{cabbage} 包",
                    "size": "sm",
                    "color": "#333333"
                },
                {"type": "separator"},
                *rows
            ]
        },
        "footer": {
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": [btn_cancel()]
        }
    }
    return FlexSendMessage(alt_text='選擇韭菜黑豬肉水餃數量', contents=bubble)


def make_confirm_flex(order):
    cabbage = order.get('cabbage', 0)
    chives = order.get('chives', 0)
    total_packs = cabbage + chives
    subtotal = total_packs * PRICE_PER_PACK
    shipping = get_shipping_fee(total_packs)
    total = subtotal + shipping

    contents = [
        {
            "type": "text",
            "text": "訂單確認",
            "weight": "bold",
            "size": "lg"
        },
        {"type": "separator"},
        {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {"type": "text", "text": "高麗菜韭黃水餃", "size": "sm", "flex": 5},
                {"type": "text", "text": f"{cabbage} 包", "size": "sm", "flex": 2, "align": "end"}
            ]
        },
        {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {"type": "text", "text": "韭菜黑豬肉水餃", "size": "sm", "flex": 5},
                {"type": "text", "text": f"{chives} 包", "size": "sm", "flex": 2, "align": "end"}
            ]
        },
        {"type": "separator"},
        {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {"type": "text", "text": "小計", "size": "sm", "flex": 5},
                {"type": "text", "text": f"NT${subtotal}", "size": "sm", "flex": 2, "align": "end"}
            ]
        },
        {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {"type": "text", "text": "運費", "size": "sm", "flex": 5},
                {"type": "text", "text": f"NT${shipping}", "size": "sm", "flex": 2, "align": "end",
                 "color": "#27AE60" if shipping == 0 else "#E05C5C"}
            ]
        },
        {"type": "separator"},
        {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {"type": "text", "text": "總計", "size": "md", "weight": "bold", "flex": 5},
                {"type": "text", "text": f"NT${total}", "size": "md", "weight": "bold",
                 "flex": 2, "align": "end", "color": "#E05C5C"}
            ]
        }
    ]

    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": contents
        },
        "footer": {
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "確認，填寫資料",
                        "data": "confirm_order"
                    },
                    "style": "primary",
                    "color": "#E05C5C",
                    "height": "sm"
                },
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "重新選擇",
                        "data": "restart_order"
                    },
                    "style": "secondary",
                    "height": "sm"
                }
            ]
        }
    }
    return FlexSendMessage(alt_text='訂單確認', contents=bubble)


def make_pickup_flex():
    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {
                    "type": "text",
                    "text": "請選擇取貨日期",
                    "weight": "bold",
                    "size": "md",
                    "wrap": True
                },
                {
                    "type": "text",
                    "text": "請選擇您方便的取貨時段",
                    "size": "sm",
                    "color": "#888888",
                    "wrap": True
                },
                {"type": "separator"},
                {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "button",
                            "action": {
                                "type": "postback",
                                "label": "平日",
                                "data": "pickup_weekday"
                            },
                            "style": "primary",
                            "color": "#E05C5C",
                            "height": "sm"
                        },
                        {
                            "type": "button",
                            "action": {
                                "type": "postback",
                                "label": "星期六",
                                "data": "pickup_saturday"
                            },
                            "style": "primary",
                            "color": "#E05C5C",
                            "height": "sm"
                        },
                        {
                            "type": "button",
                            "action": {
                                "type": "postback",
                                "label": "皆可",
                                "data": "pickup_both"
                            },
                            "style": "primary",
                            "color": "#E05C5C",
                            "height": "sm"
                        }
                    ]
                }
            ]
        },
        "footer": {
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": [btn_cancel()]
        }
    }
    return FlexSendMessage(alt_text='請選擇取貨日期', contents=bubble)


def make_final_summary_flex(order):
    cabbage = order.get('cabbage', 0)
    chives = order.get('chives', 0)
    total_packs = cabbage + chives
    subtotal = total_packs * PRICE_PER_PACK
    shipping = get_shipping_fee(total_packs)
    total = subtotal + shipping

    name = order.get('name', '')
    phone = order.get('phone', '')
    address = order.get('address', '')
    pickup = order.get('pickup_date', '')
    remarks = order.get('remarks', '無')

    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {
                    "type": "text",
                    "text": "✅ 訂單已成立",
                    "weight": "bold",
                    "size": "lg",
                    "color": "#27AE60"
                },
                {"type": "separator"},
                {
                    "type": "text",
                    "text": "訂購明細",
                    "weight": "bold",
                    "size": "sm"
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": "高麗菜韭黃水餃", "size": "sm", "flex": 5},
                        {"type": "text", "text": f"{cabbage} 包", "size": "sm", "flex": 2, "align": "end"}
                    ]
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": "韭菜黑豬肉水餃", "size": "sm", "flex": 5},
                        {"type": "text", "text": f"{chives} 包", "size": "sm", "flex": 2, "align": "end"}
                    ]
                },
                {"type": "separator"},
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": "小計", "size": "sm", "flex": 5},
                        {"type": "text", "text": f"NT${subtotal}", "size": "sm", "flex": 2, "align": "end"}
                    ]
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": "運費", "size": "sm", "flex": 5},
                        {"type": "text", "text": f"NT${shipping}", "size": "sm", "flex": 2, "align": "end",
                         "color": "#27AE60" if shipping == 0 else "#E05C5C"}
                    ]
                },
                {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": "總計", "size": "md", "weight": "bold", "flex": 5},
                        {"type": "text", "text": f"NT${total}", "size": "md", "weight": "bold",
                         "flex": 2, "align": "end", "color": "#E05C5C"}
                    ]
                },
                {"type": "separator"},
                {
                    "type": "text",
                    "text": "收件資料",
                    "weight": "bold",
                    "size": "sm"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "xs",
                    "contents": [
                        {"type": "text", "text": f"姓名：{name}", "size": "sm", "wrap": True},
                        {"type": "text", "text": f"電話：{phone}", "size": "sm", "wrap": True},
                        {"type": "text", "text": f"地址：{address}", "size": "sm", "wrap": True},
                        {"type": "text", "text": f"取貨日期：{pickup}", "size": "sm", "wrap": True},
                        {"type": "text", "text": f"備註：{remarks}", "size": "sm", "wrap": True, "color": "#888888"}
                    ]
                },
                {"type": "separator"},
                {
                    "type": "text",
                    "text": "付款資訊",
                    "weight": "bold",
                    "size": "sm"
                },
                {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "xs",
                    "contents": [
                        {"type": "text", "text": "銀行：中國信託(822)", "size": "sm", "wrap": True},
                        {"type": "text", "text": "分行：頭份分行", "size": "sm", "wrap": True},
                        {"type": "text", "text": "帳號：370540364486", "size": "sm", "wrap": True},
                        {"type": "text", "text": "戶名：徐志帆", "size": "sm", "wrap": True},
                        {
                            "type": "text",
                            "text": f"轉帳金額：NT${total}",
                            "size": "sm",
                            "weight": "bold",
                            "color": "#E05C5C",
                            "wrap": True
                        }
                    ]
                },
                {"type": "separator"},
                {
                    "type": "text",
                    "text": "請完成轉帳後，將收據截圖傳送給我們，謝謝！",
                    "size": "sm",
                    "color": "#888888",
                    "wrap": True
                }
            ]
        }
    }
    return FlexSendMessage(alt_text='訂單已成立', contents=bubble)


# ══════════════════════════════════════════
#  Webhook
# ══════════════════════════════════════════
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'


# ══════════════════════════════════════════
#  文字訊息處理
# ══════════════════════════════════════════
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    state = user_states.get(user_id, 'idle')

    # 隨時可以輸入「訂購」或「開始」重啟
    if text in ['訂購', '開始', '訂購水餃', 'order']:
        user_states[user_id] = 'welcome'
        user_orders[user_id] = {}
        line_bot_api.reply_message(event.reply_token, make_welcome_flex())
        return

    # ── 收集姓名 ──
    if state == 'waiting_name':
        user_orders[user_id]['name'] = text
        user_states[user_id] = 'waiting_phone'
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='請輸入您的電話號碼：')
        )
        return

    # ── 收集電話 ──
    if state == 'waiting_phone':
        if not text.isdigit() or len(text) < 8:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text='電話號碼格式不正確，請重新輸入（純數字，至少8碼）：')
            )
            return
        user_orders[user_id]['phone'] = text
        user_states[user_id] = 'waiting_address'
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='請輸入您的收件地址：')
        )
        return

    # ── 收集地址 ──
    if state == 'waiting_address':
        user_orders[user_id]['address'] = text
        user_states[user_id] = 'waiting_pickup'
        line_bot_api.reply_message(
            event.reply_token,
            make_pickup_flex()
        )
        return

    # ── 收集備註 ──
    if state == 'waiting_remarks':
        user_orders[user_id]['remarks'] = text
        user_states[user_id] = 'done'
        summary = make_final_summary_flex(user_orders[user_id])
        line_bot_api.reply_message(event.reply_token, summary)
        return

    # 其他狀況
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text='請輸入「訂購」開始訂購水餃 🥟')
    )


# ══════════════════════════════════════════
#  Postback 事件處理
# ══════════════════════════════════════════
@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.data
    order = user_orders.get(user_id, {})

    # ── 取消訂單 ──
    if data == 'cancel_order':
        user_states[user_id] = 'idle'
        user_orders[user_id] = {}
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='訂單已取消。若需重新訂購，請輸入「訂購」。')
        )
        return

    # ── 歡迎頁確認 ──
    if data == 'welcome_confirm':
        user_states[user_id] = 'selecting_cabbage'
        user_orders[user_id] = {}
        line_bot_api.reply_message(
            event.reply_token,
            make_cabbage_flex(user_orders[user_id])
        )
        return

    # ── 重新選擇 ──
    if data == 'restart_order':
        user_states[user_id] = 'selecting_cabbage'
        user_orders[user_id] = {}
        line_bot_api.reply_message(
            event.reply_token,
            make_cabbage_flex(user_orders[user_id])
        )
        return

    # ── 選擇高麗菜水餃數量 ──
    if data.startswith('cabbage_'):
        qty = int(data.split('_')[1])
        user_orders[user_id]['cabbage'] = qty
        user_states[user_id] = 'selecting_chives'
        line_bot_api.reply_message(
            event.reply_token,
            make_chives_flex(user_orders[user_id])
        )
        return

    # ── 選擇韭菜水餃數量 ──
    if data.startswith('chives_'):
        qty = int(data.split('_')[1])
        user_orders[user_id]['chives'] = qty
        cabbage = user_orders[user_id].get('cabbage', 0)
        total = cabbage + qty

        if total < MIN_PACKS:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f'總數量不足！目前共 {total} 包，最少需訂購 {MIN_PACKS} 包。\n請重新選擇。'
                )
            )
            user_states[user_id] = 'selecting_cabbage'
            user_orders[user_id] = {}
            line_bot_api.reply_message(
                event.reply_token,
                make_cabbage_flex(user_orders[user_id])
            )
            return

        if total > MAX_PACKS:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f'總數量超過上限！目前共 {total} 包，最多 {MAX_PACKS} 包。\n請重新選擇。'
                )
            )
            user_states[user_id] = 'selecting_cabbage'
            user_orders[user_id] = {}
            line_bot_api.reply_message(
                event.reply_token,
                make_cabbage_flex(user_orders[user_id])
            )
            return

        user_states[user_id] = 'confirming'
        line_bot_api.reply_message(
            event.reply_token,
            make_confirm_flex(user_orders[user_id])
        )
        return

    # ── 確認訂單，開始收集資料 ──
    if data == 'confirm_order':
        user_states[user_id] = 'waiting_name'
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='請輸入您的姓名：')
        )
        return

    # ── 選擇取貨日期 ──
    if data in ['pickup_weekday', 'pickup_saturday', 'pickup_both']:
        pickup_map = {
            'pickup_weekday': '平日',
            'pickup_saturday': '星期六',
            'pickup_both': '皆可'
        }
        user_orders[user_id]['pickup_date'] = pickup_map[data]
        user_states[user_id] = 'waiting_remarks'
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='請輸入備註（如無備註請輸入「無」）：')
        )
        return


# ══════════════════════════════════════════
#  啟動
# ══════════════════════════════════════════
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
