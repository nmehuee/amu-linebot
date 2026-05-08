import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    FlexSendMessage, PostbackEvent, QuickReply, QuickReplyButton,
    PostbackAction, MessageAction
)

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET')

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

user_states = {}

PRICE_PER_PACK = 200
MIN_PACKS = 4
MAX_PACKS = 12

def get_shipping_fee(total_packs):
    if total_packs >= 12:
        return 0
    elif total_packs >= 10:
        return 125
    elif total_packs >= 7:
        return 150
    else:
        return 175

def cancel_quick_reply():
    return QuickReply(items=[
        QuickReplyButton(action=PostbackAction(label='❌ 取消訂單', data='action=cancel'))
    ])

def send_welcome(reply_token):
    flex_message = FlexSendMessage(
        alt_text='A-MU水餃 歡迎訊息',
        contents={
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "🥟 A-MU水餃", "weight": "bold", "size": "xl", "color": "#FFFFFF"},
                    {"type": "text", "text": "手工現包，美味送到家", "size": "sm", "color": "#FFFFFF"}
                ],
                "backgroundColor": "#FF6B35"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "📦 商品資訊", "weight": "bold", "size": "md"},
                    {"type": "separator", "margin": "sm"},
                    {
                        "type": "box", "layout": "horizontal", "margin": "md",
                        "contents": [
                            {"type": "text", "text": "高麗菜韭黃水餃", "size": "sm", "flex": 3},
                            {"type": "text", "text": "NT$200 / 包", "size": "sm", "flex": 2, "align": "end", "color": "#FF6B35"}
                        ]
                    },
                    {
                        "type": "box", "layout": "horizontal", "margin": "sm",
                        "contents": [
                            {"type": "text", "text": "韭菜黑豬肉水餃", "size": "sm", "flex": 3},
                            {"type": "text", "text": "NT$200 / 包", "size": "sm", "flex": 2, "align": "end", "color": "#FF6B35"}
                        ]
                    },
                    {"type": "separator", "margin": "lg"},
                    {"type": "text", "text": "🚚 運費說明", "weight": "bold", "size": "md", "margin": "lg"},
                    {"type": "separator", "margin": "sm"},
                    {
                        "type": "box", "layout": "horizontal", "margin": "md",
                        "contents": [
                            {"type": "text", "text": "4–6 包", "size": "sm", "flex": 2},
                            {"type": "text", "text": "NT$175", "size": "sm", "flex": 2, "align": "end"}
                        ]
                    },
                    {
                        "type": "box", "layout": "horizontal", "margin": "sm",
                        "contents": [
                            {"type": "text", "text": "7–9 包", "size": "sm", "flex": 2},
                            {"type": "text", "text": "NT$150", "size": "sm", "flex": 2, "align": "end"}
                        ]
                    },
                    {
                        "type": "box", "layout": "horizontal", "margin": "sm",
                        "contents": [
                            {"type": "text", "text": "10–11 包", "size": "sm", "flex": 2},
                            {"type": "text", "text": "NT$125", "size": "sm", "flex": 2, "align": "end"}
                        ]
                    },
                    {
                        "type": "box", "layout": "horizontal", "margin": "sm",
                        "contents": [
                            {"type": "text", "text": "12 包", "size": "sm", "flex": 2},
                            {"type": "text", "text": "免運費 🎉", "size": "sm", "flex": 2, "align": "end", "color": "#00B900"}
                        ]
                    },
                    {"type": "separator", "margin": "lg"},
                    {
                        "type": "box", "layout": "horizontal", "margin": "md",
                        "contents": [
                            {"type": "text", "text": "最少訂購", "size": "sm", "flex": 2, "color": "#888888"},
                            {"type": "text", "text": "4 包", "size": "sm", "flex": 2, "align": "end", "color": "#888888"}
                        ]
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "action": {"type": "postback", "label": "🛒 開始訂購", "data": "action=start_order"},
                        "style": "primary",
                        "color": "#FF6B35"
                    }
                ]
            }
        }
    )
    line_bot_api.reply_message(reply_token, flex_message)

def send_cabbage_selection(reply_token):
    buttons = []
    for i in range(0, 13):
        buttons.append({
            "type": "button",
            "action": {"type": "postback", "label": f"{i} 包", "data": f"action=set_cabbage&qty={i}"},
            "style": "secondary",
            "height": "sm"
        })

    flex_message = FlexSendMessage(
        alt_text='選擇高麗菜韭黃水餃數量',
        contents={
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "高麗菜韭黃水餃", "weight": "bold", "size": "lg", "color": "#FFFFFF"}
                ],
                "backgroundColor": "#FF6B35"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "請選擇數量（0–12包）", "size": "sm", "color": "#888888", "margin": "sm"},
                    {
                        "type": "box", "layout": "vertical", "margin": "md", "spacing": "sm",
                        "contents": buttons
                    }
                ]
            }
        }
    )
    line_bot_api.reply_message(reply_token, flex_message)

def send_chives_selection(reply_token, cabbage_qty):
    max_chives = MAX_PACKS - cabbage_qty
    buttons = []
    for i in range(0, max_chives + 1):
        buttons.append({
            "type": "button",
            "action": {"type": "postback", "label": f"{i} 包", "data": f"action=set_chives&qty={i}"},
            "style": "secondary",
            "height": "sm"
        })

    flex_message = FlexSendMessage(
        alt_text='選擇韭菜黑豬肉水餃數量',
        contents={
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "韭菜黑豬肉水餃", "weight": "bold", "size": "lg", "color": "#FFFFFF"}
                ],
                "backgroundColor": "#4CAF50"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": f"已選高麗菜韭黃：{cabbage_qty} 包", "size": "sm", "color": "#888888"},
                    {"type": "text", "text": f"請選擇韭菜黑豬肉數量（0–{max_chives}包）", "size": "sm", "color": "#888888", "margin": "sm"},
                    {
                        "type": "box", "layout": "vertical", "margin": "md", "spacing": "sm",
                        "contents": buttons
                    }
                ]
            }
        }
    )
    line_bot_api.reply_message(reply_token, flex_message)

def send_order_confirmation(reply_token, user_data):
    cabbage_qty = user_data.get('cabbage_qty', 0)
    chives_qty = user_data.get('chives_qty', 0)
    total_packs = cabbage_qty + chives_qty
    shipping_fee = get_shipping_fee(total_packs)
    product_total = total_packs * PRICE_PER_PACK
    grand_total = product_total + shipping_fee

    pickup_map = {'weekday': '平日取貨', 'saturday': '週六取貨', 'any': '皆可'}
    pickup_text = pickup_map.get(user_data.get('pickup', ''), '未指定')

    shipping_text = f"NT${shipping_fee}" if shipping_fee > 0 else "免運費 🎉"

    flex_message = FlexSendMessage(
        alt_text='訂單確認',
        contents={
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "✅ 訂單確認", "weight": "bold", "size": "xl", "color": "#FFFFFF"}
                ],
                "backgroundColor": "#FF6B35"
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "📦 訂購明細", "weight": "bold", "size": "md"},
                    {"type": "separator", "margin": "sm"},
                    {
                        "type": "box", "layout": "horizontal", "margin": "md",
                        "contents": [
                            {"type": "text", "text": "高麗菜韭黃水餃", "size": "sm", "flex": 3},
                            {"type": "text", "text": f"{cabbage_qty} 包", "size": "sm", "flex": 2, "align": "end"}
                        ]
                    },
                    {
                        "type": "box", "layout": "horizontal", "margin": "sm",
                        "contents": [
                            {"type": "text", "text": "韭菜黑豬肉水餃", "size": "sm", "flex": 3},
                            {"type": "text", "text": f"{chives_qty} 包", "size": "sm", "flex": 2, "align": "end"}
                        ]
                    },
                    {
                        "type": "box", "layout": "horizontal", "margin": "sm",
                        "contents": [
                            {"type": "text", "text": "商品小計", "size": "sm", "flex": 3, "color": "#888888"},
                            {"type": "text", "text": f"NT${product_total}", "size": "sm", "flex": 2, "align": "end", "color": "#888888"}
                        ]
                    },
                    {
                        "type": "box", "layout": "horizontal", "margin": "sm",
                        "contents": [
                            {"type": "text", "text": "運費", "size": "sm", "flex": 3, "color": "#888888"},
                            {"type": "text", "text": shipping_text, "size": "sm", "flex": 2, "align": "end", "color": "#888888"}
                        ]
                    },
                    {"type": "separator", "margin": "md"},
                    {
                        "type": "box", "layout": "horizontal", "margin": "md",
                        "contents": [
                            {"type": "text", "text": "總金額", "weight": "bold", "flex": 3},
                            {"type": "text", "text": f"NT${grand_total}", "weight": "bold", "flex": 2, "align": "end", "color": "#FF6B35"}
                        ]
                    },
                    {"type": "separator", "margin": "lg"},
                    {"type": "text", "text": "👤 收件資訊", "weight": "bold", "size": "md", "margin": "lg"},
                    {"type": "separator", "margin": "sm"},
                    {
                        "type": "box", "layout": "horizontal", "margin": "md",
                        "contents": [
                            {"type": "text", "text": "姓名", "size": "sm", "flex": 2, "color": "#888888"},
                            {"type": "text", "text": user_data.get('name', ''), "size": "sm", "flex": 3, "align": "end"}
                        ]
                    },
                    {
                        "type": "box", "layout": "horizontal", "margin": "sm",
                        "contents": [
                            {"type": "text", "text": "電話", "size": "sm", "flex": 2, "color": "#888888"},
                            {"type": "text", "text": user_data.get('phone', ''), "size": "sm", "flex": 3, "align": "end"}
                        ]
                    },
                    {
                        "type": "box", "layout": "horizontal", "margin": "sm",
                        "contents": [
                            {"type": "text", "text": "地址", "size": "sm", "flex": 2, "color": "#888888"},
                            {"type": "text", "text": user_data.get('address', ''), "size": "sm", "flex": 3, "align": "end", "wrap": True}
                        ]
                    },
                    {
                        "type": "box", "layout": "horizontal", "margin": "sm",
                        "contents": [
                            {"type": "text", "text": "取貨日", "size": "sm", "flex": 2, "color": "#888888"},
                            {"type": "text", "text": pickup_text, "size": "sm", "flex": 3, "align": "end"}
                        ]
                    },
                    {
                        "type": "box", "layout": "horizontal", "margin": "sm",
                        "contents": [
                            {"type": "text", "text": "備註", "size": "sm", "flex": 2, "color": "#888888"},
                            {"type": "text", "text": user_data.get('remarks', '無'), "size": "sm", "flex": 3, "align": "end", "wrap": True}
                        ]
                    },
                    {"type": "separator", "margin": "lg"},
                    {"type": "text", "text": "💳 匯款資訊", "weight": "bold", "size": "md", "margin": "lg"},
                    {"type": "separator", "margin": "sm"},
                    {
                        "type": "box", "layout": "horizontal", "margin": "md",
                        "contents": [
                            {"type": "text", "text": "銀行", "size": "sm", "flex": 2, "color": "#888888"},
                            {"type": "text", "text": "中國信託 (822)", "size": "sm", "flex": 3, "align": "end"}
                        ]
                    },
                    {
                        "type": "box", "layout": "horizontal", "margin": "sm",
                        "contents": [
                            {"type": "text", "text": "分行", "size": "sm", "flex": 2, "color": "#888888"},
                            {"type": "text", "text": "頭份分行", "size": "sm", "flex": 3, "align": "end"}
                        ]
                    },
                    {
                        "type": "box", "layout": "horizontal", "margin": "sm",
                        "contents": [
                            {"type": "text", "text": "帳號", "size": "sm", "flex": 2, "color": "#888888"},
                            {"type": "text", "text": "370540364486", "size": "sm", "flex": 3, "align": "end"}
                        ]
                    },
                    {
                        "type": "box", "layout": "horizontal", "margin": "sm",
                        "contents": [
                            {"type": "text", "text": "戶名", "size": "sm", "flex": 2, "color": "#888888"},
                            {"type": "text", "text": "徐志帆", "size": "sm", "flex": 3, "align": "end"}
                        ]
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {"type": "text", "text": "請完成匯款後，截圖傳送給我們 📸", "size": "sm", "color": "#888888", "align": "center", "wrap": True}
                ]
            }
        }
    )
    line_bot_api.reply_message(reply_token, flex_message)

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
    reply_token = event.reply_token

    if text.lower() == 'go':
        user_states[user_id] = {}
        send_welcome(reply_token)
        return

    state = user_states.get(user_id, {})
    step = state.get('step')

    if step == 'waiting_name':
        state['name'] = text
        state['step'] = 'waiting_phone'
        user_states[user_id] = state
        line_bot_api.reply_message(reply_token, TextSendMessage(
            text='請輸入收件人電話：',
            quick_reply=cancel_quick_reply()
        ))

    elif step == 'waiting_phone':
        state['phone'] = text
        state['step'] = 'waiting_address'
        user_states[user_id] = state
        line_bot_api.reply_message(reply_token, TextSendMessage(
            text='請輸入收件地址：',
            quick_reply=cancel_quick_reply()
        ))

    elif step == 'waiting_address':
        state['address'] = text
        state['step'] = 'waiting_pickup'
        user_states[user_id] = state
        line_bot_api.reply_message(reply_token,
            TextSendMessage(
                text='請選擇取貨日期偏好：',
                quick_reply=QuickReply(items=[
                    QuickReplyButton(action=PostbackAction(label='平日', data='action=pickup&type=weekday')),
                    QuickReplyButton(action=PostbackAction(label='週六', data='action=pickup&type=saturday')),
                    QuickReplyButton(action=PostbackAction(label='皆可', data='action=pickup&type=any')),
                    QuickReplyButton(action=PostbackAction(label='❌ 取消訂單', data='action=cancel'))
                ])
            )
        )

    elif step == 'waiting_remarks':
        state['remarks'] = text
        state['step'] = 'done'
        user_states[user_id] = state
        send_order_confirmation(reply_token, state)

@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.data
    reply_token = event.reply_token

    params = dict(item.split('=') for item in data.split('&'))
    action = params.get('action')

    if action == 'cancel':
        user_states.pop(user_id, None)
        line_bot_api.reply_message(reply_token, TextSendMessage(text='已取消訂單。如需重新訂購，請輸入 Go'))
        return

    if action == 'start_order':
        user_states[user_id] = {'step': 'selecting_cabbage'}
        send_cabbage_selection(reply_token)
        return

    state = user_states.get(user_id, {})

    if action == 'set_cabbage':
        cabbage_qty = int(params.get('qty', 0))
        state['cabbage_qty'] = cabbage_qty
        state['step'] = 'selecting_chives'
        user_states[user_id] = state
        send_chives_selection(reply_token, cabbage_qty)

    elif action == 'set_chives':
        chives_qty = int(params.get('qty', 0))
        cabbage_qty = state.get('cabbage_qty', 0)
        total = cabbage_qty + chives_qty

        if total < MIN_PACKS:
            line_bot_api.reply_message(reply_token, TextSendMessage(
                text=f'總包數需至少 {MIN_PACKS} 包（目前：{total} 包），請重新選擇韭菜黑豬肉數量。',
                quick_reply=cancel_quick_reply()
            ))
            send_chives_selection(reply_token, cabbage_qty)
            return

        state['chives_qty'] = chives_qty
        state['step'] = 'waiting_name'
        user_states[user_id] = state
        line_bot_api.reply_message(reply_token, TextSendMessage(
            text=f'共 {total} 包！請輸入收件人姓名：',
            quick_reply=cancel_quick_reply()
        ))

    elif action == 'pickup':
        pickup_type = params.get('type')
        state['pickup'] = pickup_type
        state['step'] = 'waiting_remarks'
        user_states[user_id] = state
        line_bot_api.reply_message(reply_token, TextSendMessage(
            text='請輸入備註（無則輸入「無」）：',
            quick_reply=cancel_quick_reply()
        ))

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
