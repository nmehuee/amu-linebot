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


def cancel_quick_reply():
    """建立帶有「取消填單」Quick Reply 按鈕"""
    return QuickReply(items=[
        QuickReplyButton(
            action=PostbackAction(
                label='✖ 取消填單',
                data='cancel'
            )
        )
    ])


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
    """建立訂單確認 Flex Message，費用明細與匯款資訊以藍色粗體顯示"""
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

    def row(label, value, value_color="#333333", value_bold=False):
        return {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {
                    "type": "text",
                    "text": label,
                    "size": "sm",
                    "color": "#888888",
                    "flex": 3
                },
                {
                    "type": "text",
                    "text": str(value),
                    "size": "sm",
                    "color": value_color,
                    "weight": "bold" if value_bold else "regular",
                    "flex": 5,
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
                row("🥬 高麗菜韭黃黑豬肉", f"{cabbage} 包"),
                row("🌿 韭菜黑豬肉", f"{chives} 包"),
                {"type": "separator"},

                # 費用明細（藍色粗體）
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
                row("👤 姓名", name),
                row("📞 電話", phone),
                row("📍 地址", address),
                row("🕐 取貨日期", delivery_time),
                row("📝 備註", remarks),
                {"type": "separator"},

                # 匯款資訊（藍色粗體）
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

                # 注意事項（藍色粗體）
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
    user_states[user_id] = 'selecting_cabbage'
    user_orders[user_id] = {}

    welcome = TextSendMessage(
        text=(
            '歡迎來到 A-MU水餃！🥟\n\n'
            '📦 商品：\n'
            '• 高麗菜韭黃黑豬肉水餃 NT$200/包\n'
            '• 韭菜黑豬肉水餃 NT$200/包\n\n'
            '🚚 運費：NT$170（滿NT$2000免運）\n'
            '⚠️ 最少2包，最多15包'
        )
    )

    flex = make_quantity_flex(
        title='高麗菜韭黃黑豬肉水餃',
        subtitle='請選擇數量（包）',
        postback_prefix='cabbage'
    )

    line_bot_api.reply_message(reply_token, [welcome, flex])


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

    # 發送 Flex Message 訂單確認給用戶
    line_bot_api.reply_message(reply_token, make_summary_flex(order))

    # 推送純文字通知給店主
    if OWNER_ID:
        cabbage = order.get('cabbage', 0)
        chives = order.get('chives', 0)
        total_packs = cabbage + chives
        subtotal = total_packs * PRICE_PER_PACK
        shipping = 0 if subtotal >= FREE_SHIPPING_THRESHOLD else SHIPPING_FEE
        total = subtotal + shipping

        owner_msg = (
            f'🔔 新訂單通知！\n'
            f'────────────────────\n'
            f'🥬 高麗菜韭黃黑豬肉：{cabbage} 包\n'
            f'🌿 韭菜黑豬肉：{chives} 包\n'
            f'💰 總計：NT${total}（運費NT${shipping}）\n'
            f'────────────────────\n'
            f'👤 {order.get("name", "")}\n'
            f'📞 {order.get("phone", "")}\n'
            f'📍 {order.get("address", "")}\n'
            f'🕐 {order.get("delivery_time", "")}\n'
            f'📝 {order.get("remarks", "No")}'
        )
        line_bot_api.push_message(OWNER_ID, TextSendMessage(text=owner_msg))


@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.data

    # 取消填單
    if data == 'cancel':
        user_states[user_id] = None
        user_orders[user_id] = {}
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='已取消填單 ❌\n如需重新訂購，請輸入「Go」')
        )
        return

    # 選擇高麗菜韭黃黑豬肉數量
    if data.startswith('cabbage='):
        qty = int(data.split('=')[1])
        user_orders[user_id]['cabbage'] = qty
        ask_chives(user_id, event.reply_token, qty)

    # 選擇韭菜黑豬肉數量
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
                        f'高麗菜韭黃黑豬肉{cabbage}包 + 韭菜黑豬肉{qty}包 = {total}包\n'
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
                    f'✅ 高麗菜韭黃黑豬肉{cabbage}包 + 韭菜黑豬肉{qty}包 = 共{total}包\n\n'
                    f'請輸入您的【姓名】'
                ),
                quick_reply=cancel_quick_reply()
            )
        )

    # 選擇取貨日期
    elif data.startswith('pickup_day='):
        day = data.split('=')[1]
        user_orders[user_id]['delivery_time'] = day
        user_states[user_id] = 'input_remarks'
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=f'✅ 取貨日期：{day}\n\n請輸入【備註】\n（無備註請輸入「No」）',
                quick_reply=cancel_quick_reply()
            )
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
            TextSendMessage(
                text='請輸入您的【電話號碼】',
                quick_reply=cancel_quick_reply()
            )
        )

    # 輸入電話
    elif state == 'input_phone':
        user_orders[user_id]['phone'] = text
        user_states[user_id] = 'input_address'
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text='請輸入您的【收貨地址】',
                quick_reply=cancel_quick_reply()
            )
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
