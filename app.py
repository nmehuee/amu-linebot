import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    PostbackEvent, FlexSendMessage, QuickReply, QuickReplyButton,
    PostbackAction
)

app = Flask(__name__)

CHANNEL_ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET')
OWNER_ID = os.environ.get('OWNER_ID')

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

user_states = {}
user_orders = {}

PRICE_PER_PACK = 200
MIN_ORDER = 2
MAX_ORDER = 12


@app.route('/')
def index():
    return 'A-MU LINE Bot is running!', 200


@app.route('/callback', methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK', 200


def cancel_quick_reply():
    return QuickReply(items=[
        QuickReplyButton(
            action=PostbackAction(
                label='✖ 取消填單',
                data='cancel'
            )
        )
    ])


def make_welcome_flex():
    flex_content = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {
                    "type": "text",
                    "text": "歡迎來到 A-MU水餃！🥟",
                    "weight": "bold",
                    "size": "lg",
                    "wrap": True
                },
                {"type": "separator"},

                # 商品
                {
                    "type": "text",
                    "text": "📦 商品：",
                    "weight": "bold",
                    "size": "sm"
                },
                {
                    "type": "text",
                    "text": "• 高麗菜韭黃黑豬肉水餃 NT$200/包\n• 韭菜黑豬肉水餃 NT$200/包",
                    "size": "sm",
                    "color": "#333333",
                    "wrap": True
                },
                {"type": "separator"},

                # 運費說明
                {
                    "type": "text",
                    "text": "🚚 運費說明：",
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
                                    "text": "2 ~ 5 包",
                                    "size": "sm",
                                    "color": "#333333",
                                    "flex": 3
                                },
                                {
                                    "type": "text",
                                    "text": "運費 NT$225",
                                    "size": "sm",
                                    "color": "#E05C5C",
                                    "flex": 5,
                                    "weight": "bold"
                                }
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "6 ~ 9 包",
                                    "size": "sm",
                                    "color": "#333333",
                                    "flex": 3
                                },
                                {
                                    "type": "text",
                                    "text": "運費 NT$150，現省75 🎉",
                                    "size": "sm",
                                    "color": "#E05C5C",
                                    "flex": 5,
                                    "weight": "bold"
                                }
                            ]
                        },
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": "10 ~ 12 包",
                                    "size": "sm",
                                    "color": "#333333",
                                    "flex": 3
                                },
                                {
                                    "type": "text",
                                    "text": "免運，最划算 🏆",
                                    "size": "sm",
                                    "color": "#27AE60",
                                    "flex": 5,
                                    "weight": "bold"
                                }
                            ]
                        }
                    ]
                },
                {"type": "separator"},

                # 訂購限制
                {
                    "type": "text",
                    "text": "⚠️ 最少2包，最多12包",
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
                        "label": "✅ 了解",
                        "data": "welcome_confirm"
                    },
                    "style": "primary",
                    "color": "#E05C5C",
                    "height": "sm"
                },
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "✖ 取消填單",
                        "data": "cancel"
                    },
                    "style": "secondary",
                    "height": "sm"
                }
            ]
        }
    }

    return FlexSendMessage(alt_text='歡迎來到 A-MU水餃！', contents=flex_content)


def make_quantity_flex(title, subtitle, postback_prefix, max_qty=12):
    buttons = []
    for i in range(0, max_qty + 1):
        buttons.append({
            "type": "button",
            "action": {
                "type": "postback",
                "label": str(i),
                "data": f"{postback_prefix}={i}"
            },
            "style": "primary",
            "color": "#E05C5C",
            "height": "sm",
            "flex": 1
        })

    rows = []
    for row_start in range(0, len(buttons), 4):
        row_buttons = buttons[row_start:row_start + 4]
        while len(row_buttons) < 4:
            row_buttons.append({"type": "filler"})
        rows.append({
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": row_buttons
        })

    cancel_row = {
        "type": "box",
        "layout": "horizontal",
        "spacing": "sm",
        "contents": [
            {
                "type": "button",
                "action": {
                    "type": "postback",
                    "label": "✖ 取消填單",
                    "data": "cancel"
                },
                "style": "secondary",
                "height": "sm"
            }
        ]
    }

    flex_content = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {
                    "type": "text",
                    "text": title,
                    "weight": "bold",
                    "size": "xl"
                },
                {
                    "type": "text",
                    "text": subtitle,
                    "size": "sm",
                    "color": "#888888",
                    "wrap": True
                },
                {"type": "separator"},
                *rows,
                {"type": "separator"},
                cancel_row
            ]
        }
    }

    return FlexSendMessage(alt_text=title, contents=flex_content)


def make_pickup_flex():
    options = ['平日', '禮拜六', '皆可']

    buttons = []
    for option in options:
        buttons.append({
            "type": "button",
            "action": {
                "type": "postback",
                "label": option,
                "data": f"pickup_day={option}"
            },
            "style": "primary",
            "color": "#E05C5C",
            "height": "sm"
        })

    flex_content = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {
                    "type": "text",
                    "text": "希望取貨日期",
                    "weight": "bold",
                    "size": "xl"
                },
                {
                    "type": "text",
                    "text": "請選擇方便取貨的時間",
                    "size": "sm",
                    "color": "#888888"
                },
                {"type": "separator"},
                *buttons,
                {"type": "separator"},
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "✖ 取消填單",
                        "data": "cancel"
                    },
                    "style": "secondary",
                    "height": "sm"
                }
            ]
        }
    }

    return FlexSendMessage(alt_text='希望取貨日期', contents=flex_content)


def make_summary_flex(order):
    cabbage = order.get('cabbage', 0)
    chives = order.get('chives', 0)
    total_packs = cabbage + chives
    subtotal = total_packs * PRICE_PER_PACK

    # 新運費邏輯
    if total_packs >= 10:
        shipping = 0
    elif total_packs >= 6:
        shipping = 150
    else:
        shipping = 225

    total = subtotal + shipping

    name = order.get('name', '')
    phone = order.get('phone', '')
    address = order.get('address', '')
    delivery_time = order.get('delivery_time', '')
    remarks = order.get('remarks', 'No')

    def row(label, value, value_color="#333333", value_bold=False):
        return {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "text",
                    "text": label,
                    "size": "sm",
                    "color": "#333333",
                    "flex": 4
                },
                {
                    "type": "text",
                    "text": str(value),
                    "size": "sm",
                    "color": value_color,
                    "weight": "bold" if value_bold else "regular",
                    "flex": 4,
                    "wrap": True
                }
            ]
        }

    flex_content = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#E05C5C",
            "contents": [
                {
                    "type": "text",
                    "text": "📋 訂單確認",
                    "color": "#FFFFFF",
                    "weight": "bold",
                    "size": "xl"
                }
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [

                # 商品明細
                {
                    "type": "text",
                    "text": "🛒 商品明細",
                    "weight": "bold",
                    "size": "md",
                    "color": "#333333"
                },
                row("高麗菜韭黃黑豬肉", f"{cabbage} 包"),
                row("韭菜黑豬肉", f"{chives} 包"),
                {"type": "separator"},

                # 費用明細
                {
                    "type": "text",
                    "text": "💰 費用明細",
                    "weight": "bold",
                    "size": "md",
                    "color": "#333333"
                },
                row("小計", f"NT${subtotal}", value_color="#1D6FA4", value_bold=True),
                row("運費", f"NT${shipping}", value_color="#1D6FA4", value_bold=True),
                row("總計", f"NT${total}", value_color="#1D6FA4", value_bold=True),
                {"type": "separator"},

                # 收件資訊
                {
                    "type": "text",
                    "text": "📦 收件資訊",
                    "weight": "bold",
                    "size": "md",
                    "color": "#333333"
                },
                row("姓名", name),
                row("電話", phone),
                row("地址", address),
                row("取貨日期", delivery_time),
                row("備註", remarks),
                {"type": "separator"},

                # 匯款資訊
                {
                    "type": "text",
                    "text": "💳 匯款資訊",
                    "weight": "bold",
                    "size": "md",
                    "color": "#1D6FA4"
                },
                row("銀行", "中國信託銀行(822)", value_color="#1D6FA4", value_bold=True),
                row("分行", "頭份分行", value_color="#1D6FA4", value_bold=True),
                row("帳號", "370540364486", value_color="#1D6FA4", value_bold=True),
                row("戶名", "徐志帆", value_color="#1D6FA4", value_bold=True),
                {"type": "separator"},

                # 注意事項
                {
                    "type": "text",
                    "text": "請於24小時內完成匯款，並告知匯款帳號後5碼！🙏",
                    "size": "sm",
                    "color": "#1D6FA4",
                    "wrap": True,
                    "weight": "bold"
                }
            ]
        }
    }

    return FlexSendMessage(alt_text='📋 訂單確認', contents=flex_content)


def start_order(user_id, reply_token):
    user_states[user_id] = 'waiting_welcome_confirm'
    user_orders[user_id] = {}
    line_bot_api.reply_message(reply_token, make_welcome_flex())


def ask_cabbage(user_id, reply_token):
    user_states[user_id] = 'selecting_cabbage'
    flex = make_quantity_flex(
        title='高麗菜韭黃黑豬肉水餃',
        subtitle='請選擇數量（包）',
        postback_prefix='cabbage'
    )
    line_bot_api.reply_message(reply_token, flex)


def ask_chives(user_id, reply_token, cabbage_qty):
    user_states[user_id] = 'selecting_chives'
    remaining = MAX_ORDER - cabbage_qty

    flex = make_quantity_flex(
        title='韭菜黑豬肉水餃',
        subtitle=f'請選擇數量（包）\n目前高麗菜韭黃：{cabbage_qty}包，最多還可選 {remaining} 包',
        postback_prefix='chives',
        max_qty=remaining
    )
    line_bot_api.reply_message(reply_token, flex)


def send_order_summary(user_id, reply_token):
    order = user_orders[user_id]
    line_bot_api.reply_message(reply_token, make_summary_flex(order))

    if OWNER_ID:
        cabbage = order.get('cabbage', 0)
        chives = order.get('chives', 0)
        total_packs = cabbage + chives
        subtotal = total_packs * PRICE_PER_PACK

        if total_packs >= 10:
            shipping = 0
        elif total_packs >= 6:
            shipping = 150
        else:
            shipping = 225

        total = subtotal + shipping

        owner_msg = (
            f'🔔 新訂單通知！\n'
            f'────
