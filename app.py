import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    PostbackEvent, FlexSendMessage
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
SHIPPING_FEE = 170
FREE_SHIPPING_THRESHOLD = 2000
MIN_ORDER = 2
MAX_ORDER = 15


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


def make_quantity_flex(title, subtitle, postback_prefix, max_qty=15):
    """建立數量選擇的 Flex Message，格狀排列"""

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
            row_buttons.append({
                "type": "filler"
            })
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
                    "label": "✖ 取消訂單",
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
                {
                    "type": "separator"
                },
                *rows,
                {
                    "type": "separator"
                },
                cancel_row
            ]
        }
    }

    return FlexSendMessage(alt_text=title, contents=flex_content)


def make_pickup_flex():
    """建立取貨日期選擇的 Flex Message"""
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
                {
                    "type": "separator"
                },
                *buttons,
                {
                    "type": "separator"
                },
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "✖ 取消訂單",
                        "data": "cancel"
                    },
                    "style": "secondary",
                    "height": "sm"
                }
            ]
        }
    }

    return FlexSendMessage(alt_text='希望取貨日期', contents=flex_content)


def start_order(user_id, reply_token):
    user_states[user_id] = 'selecting_cabbage'
    user_orders[user_id] = {}

    welcome = TextSendMessage(
        text=(
            '歡迎來到 A-MU水餃！🥟\n\n'
            '📦 商品：\n'
            '• 高麗菜豬肉水餃 NT$200/包\n'
            '• 韭菜豬肉水餃 NT$200/包\n\n'
            '🚚 運費：NT$170（滿NT$2000免運）\n'
            '⚠️ 最少2包，最多15包'
        )
    )

    flex = make_quantity_flex(
        title='高麗菜豬肉水餃',
        subtitle='請選擇數量（包）',
        postback_prefix='cabbage'
    )

    line_bot_api.reply_message(reply_token, [welcome, flex])


def ask_chives(user_id, reply_token, cabbage_qty):
    user_states[user_id] = 'selecting_chives'
    remaining = MAX_ORDER - cabbage_qty

    flex = make_quantity_flex(
        title='韭菜豬肉水餃',
        subtitle=f'請選擇數量（包）\n目前高麗菜：{cabbage_qty}包，最多還可選 {remaining} 包',
        postback_prefix='chives',
        max_qty=remaining
    )

    line_bot_api.reply_message(reply_token, flex)


def send_order_summary(user_id, reply_token):
    order = user_orders[user_id]
    cabbage = order.get('cabbage', 0)
    chives = order.get('chives', 0)
    total_packs = cabbage + chives
    subtotal = total_packs * PRICE_PER_PACK
    shipping = 0 if subtotal >= FREE_SHIPPING_THRESHOLD else SHIPPING_FEE
    total = subtotal + shipping

    name = order.get('name', '')
    phone = order.get('phone', '')
    address = order.get('address', '')
    delivery_time = order.get('delivery_time', '')
    remarks = order.get('remarks', 'No')

    summary = (
        f'📋 訂單確認\n'
        f'────────────────────\n'
        f'🥬 高麗菜豬肉水餃：{cabbage} 包\n'
        f'🌿 韭菜豬肉水餃：{chives} 包\n'
        f'────────────────────\n'
        f'小計：NT${subtotal}\n'
        f'運費：NT${shipping}\n'
        f'💰 總計：NT${total}\n'
        f'────────────────────\n'
        f'👤 姓名：{name}\n'
        f'📞 電話：{phone}\n'
        f'📍 地址：{address}\n'
        f'🕐 取貨日期：{delivery_time}\n'
        f'📝 備註：{remarks}\n'
        f'────────────────────\n'
        f'💳 匯款資訊：\n'
        f'中國信託銀行(822)\n'
        f'豐原分行\n'
        f'帳號：370540364486\n'
        f'戶名：徐志帆\n\n'
        f'請於24小時內完成匯款，謝謝！🙏'
    )

    line_bot_api.reply_message(reply_token, TextSendMessage(text=summary))

    if OWNER_ID:
        owner_msg = (
            f'🔔 新訂單通知！\n'
            f'────────────────────\n'
            f'🥬 高麗菜：{cabbage} 包\n'
            f'🌿 韭菜：{chives} 包\n'
            f'💰 總計：NT${total}（運費NT${shipping}）\n'
            f'────────────────────\n'
            f'👤 {name}\n'
            f'📞 {phone}\n'
            f'📍 {address}\n'
            f'🕐 {delivery_time}\n'
            f'📝 {remarks}'
        )
        line_bot_api.push_message(OWNER_ID, TextSendMessage(text=owner_msg))


@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.data

    # 取消訂單
    if data == 'cancel':
        user_states[user_id] = None
        user_orders[user_id] = {}
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='已取消訂單 ❌\n如需重新訂購，請輸入「Go」')
        )
        return

    # 選擇高麗菜數量
    if data.startswith('cabbage='):
        qty = int(data.split('=')[1])
        user_orders[user_id]['cabbage'] = qty
        ask_chives(user_id, event.reply_token, qty)

    # 選擇韭菜數量
    elif data.startswith('chives='):
        qty = int(data.split('=')[1])
        cabbage = user_orders[user_id].get('cabbage', 0)
        total = cabbage + qty

        if total < MIN_ORDER:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=(
                        f'⚠️ 總數量不足！\n'
                        f'高麗菜{cabbage}包 + 韭菜{qty}包 = {total}包\n'
                        f'最少需要 {MIN_ORDER} 包\n\n'
                        f'請重新輸入「Go」再試一次'
                    )
                )
            )
            user_states[user_id] = None
            return

        user_orders[user_id]['chives'] = qty
        user_states[user_id] = 'input_name'
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=(
                    f'✅ 高麗菜{cabbage}包 + 韭菜{qty}包 = 共{total}包\n\n'
                    f'請輸入您的【姓名】'
                )
            )
        )

    # 選擇取貨日期
    elif data.startswith('pickup_day='):
        day = data.split('=')[1]
        user_orders[user_id]['delivery_time'] = day
        user_states[user_id] = 'input_remarks'
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f'✅ 取貨日期：{day}\n\n請輸入【備註】\n（無備註請輸入「No」）')
        )


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    state = user_states.get(user_id)

    # 查詢自己 ID
    if text == '我的ID':
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f'您的 LINE ID 是：\n{user_id}')
        )
        return

    # 開始訂購
    if text.lower() == 'go':
        start_order(user_id, event.reply_token)
        return

    # 輸入姓名
    if state == 'input_name':
        user_orders[user_id]['name'] = text
        user_states[user_id] = 'input_phone'
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='請輸入您的【電話號碼】')
        )

    # 輸入電話
    elif state == 'input_phone':
        user_orders[user_id]['phone'] = text
        user_states[user_id] = 'input_address'
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='請輸入您的【收貨地址】')
        )

    # 輸入地址
    elif state == 'input_address':
        user_orders[user_id]['address'] = text
        user_states[user_id] = 'selecting_pickup_day'
        line_bot_api.reply_message(
            event.reply_token,
            make_pickup_flex()
        )

    # 輸入備註
    elif state == 'input_remarks':
        user_orders[user_id]['remarks'] = text
        user_states[user_id] = None
        send_order_summary(user_id, event.reply_token)

    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='請輸入「Go」開始訂購水餃 🥟')
        )


if __name__ == '__main__':
    app.run(debug=True)
