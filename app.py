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

DIVIDER = '--------------------'  # ← 避免特殊字元在 f-string 出錯


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
                label='取消填單',
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
                        "label": "✖ 取消填](streamdown:incomplete-link)
