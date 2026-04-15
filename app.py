import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    PostbackEvent, FlexSendMessage,
    QuickReply, QuickReplyButton, PostbackAction
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


def calc_shipping(total_packs):
    if total_packs >= 10:
        return 0
    elif total_packs >= 6:
        return 150
    else:
        return 225


def cancel_quick_reply():
    return QuickReply(items=[
        QuickReplyButton(
            action=PostbackAction(
                label='取消填單',
                data='cancel'
            )
        )
    ])


def btn_cancel():
    return {
        "type": "button",
        "action": {
            "type": "postback",
            "label": "取消填單",
            "data": "cancel"
        },
        "style": "secondary",
        "height": "sm"
    }


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
                                    "text": "運費 NT$150",
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
                                    "text": "免運費",
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
                    "text": "最少2包，最多12包",
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


def make_quantity_flex(title, subtitle, postback_prefix, max_qty=12):
    buttons = []
    for i in range(0, max_qty + 1):
        buttons.append({
            "type": "button",
            "action": {
                "type": "postback",
                "label": str(i),
                "data": postback_prefix + "=" + str(i)
            },
            "style": "primary",
            "color": "#E05C5C",
            "height": "sm",
            "flex": 1
        })

    rows = []
    for row_start in range(0, len(buttons), 4):
        chunk = buttons[row_start:row_start + 4]
        while len(chunk) < 4:
            chunk.append({"type": "filler"})
        rows.append({
            "type": "box",
            "layout": "horizontal",
            "spacing": "sm",
            "contents": chunk
        })

    body_contents = [
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
        {"type": "separator"}
    ]
    body_contents.extend(rows)
    body_contents.append({"type": "separator"})
    body_contents.append(btn_cancel())

    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": body_contents
        }
    }
    return FlexSendMessage(alt_text=title, contents=bubble)


def make_pickup_flex():
    options = ['平日', '禮拜六', '皆可']
    buttons = []
    for opt in options:
        buttons.append({
            "type": "button",
            "action": {
                "type": "postback",
                "label": opt,
                "data": "pickup_day=" + opt
            },
            "style": "primary",
            "color": "#E05C5C",
            "height": "sm"
        })

    body_contents = [
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
        {"type": "separator"}
    ]
    body_contents.extend(buttons)
    body_contents.append({"type": "separator"})
    body_contents.append(btn_cancel())

    bubble = {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": body_contents
        }
    }
    return FlexSendMessage(alt_text='希望取貨日期', contents=bubble)


def info_row(label, value, value_color="#333333", value_bold=False):
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


def make_summary_flex(order):
    cabbage = order.get('cabbage', 0)
    chives = order.get('chives', 0)
    total_packs = cabbage + chives
    subtotal = total_packs * PRICE_PER_PACK
    shipping = calc_shipping(total_packs)
    total = subtotal + shipping

    name = order.get('name', '')
    phone = order.get('phone', '')
    address = order.get('address', '')
    delivery_time = order.get('delivery_time', '')
    remarks = order.get('remarks', 'No')

    blue = "#1D6FA4"

    body_contents = [
        {
            "type": "text",
            "text": "商品明細",
            "weight": "bold",
            "size": "md",
            "color": "#333333"
        },
        info_row("高麗菜韭黃黑豬肉", str(cabbage) + " 包"),
        info_row("韭菜黑豬肉", str(chives) + " 包"),
        {"type": "separator"},
        {
            "type": "text",
            "text": "費用明細",
            "weight": "bold",
            "size": "md",
            "color": "#333333"
        },
        info_row("小計", "NT$" + str(subtotal), value_color=blue, value_bold=True),
        info_row("運費", "NT$" + str(shipping), value_color=blue, value_bold=True),
        info_row("總計", "NT$" + str(total), value_color=blue, value_bold=True),
        {"type": "separator"},
        {
            "type": "text",
            "text": "收件資訊",
            "weight": "bold",
            "size": "md",
            "color": "#333333"
        },
        info_row("姓名", name),
        info_row("電話", phone),
        info_row("地址", address),
        info_row("取貨日期", delivery_time),
        info_row("備註", remarks),
        {"type": "separator"},
        {
            "type": "text",
            "text": "匯款資訊",
            "weight": "bold",
            "size": "md",
            "color": blue
        },
        info_row("銀行", "中國信託銀行(822)", value_color=blue, value_bold=True),
        info_row("分行", "頭份分行", value_color=blue, value_bold=True),
        info_row("帳號", "370540364486", value_color=blue, value_bold=True),
        info_row("戶名", "徐志帆", value_color=blue, value_bold=True),
        {"type": "separator"},
        {
            "type": "text",
            "text": "請於24小時內完成匯款，並告知匯款帳號後5碼",
            "size": "sm",
            "color": blue,
            "wrap": True,
            "weight": "bold"
        }
    ]

    bubble = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#E05C5C",
            "contents": [
                {
                    "type": "text",
                    "text": "訂單確認",
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
            "contents": body_contents
        }
    }
    return FlexSendMessage(alt_text='訂單確認', contents=bubble)


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
    subtitle = ('請選擇數量（包）\n'
                '目前高麗菜韭黃：' + str(cabbage_qty) +
                '包，最多還可選 ' + str(remaining) + ' 包')
    flex = make_quantity_flex(
        title='韭菜黑豬肉水餃',
        subtitle=subtitle,
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
        shipping = calc_shipping(total_packs)
        total = subtotal + shipping
        sep = '--------------------'

        lines = [
            '新訂單通知',
            sep,
            '高麗菜韭黃黑豬肉：' + str(cabbage) + ' 包',
            '韭菜黑豬肉：' + str(chives) + ' 包',
            '總計：NT$' + str(total) + '（運費 NT$' + str(shipping) + '）',
            sep,
            '姓名：' + order.get('name', ''),
            '電話：' + order.get('phone', ''),
            '地址：' + order.get('address', ''),
            '取貨日期：' + order.get('delivery_time', ''),
            '備註：' + order.get('remarks', 'No')
        ]
        owner_msg = '\n'.join(lines)
        line_bot_api.push_message(OWNER_ID, TextSendMessage(text=owner_msg))


@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.data

    if data == 'cancel':
        user_states[user_id] = None
        user_orders[user_id] = {}
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='已取消填單\n如需重新訂購，請輸入 Go')
        )
        return

    if data == 'welcome_confirm':
        ask_cabbage(user_id, event.reply_token)
        return

    if data.startswith('cabbage='):
        qty = int(data.split('=')[1])
        user_orders[user_id]['cabbage'] = qty
        ask_chives(user_id, event.reply_token, qty)

    elif data.startswith('chives='):
        qty = int(data.split('=')[1])
        cabbage = user_orders[user_id].get('cabbage', 0)
        total = cabbage + qty

        if total < MIN_ORDER:
            msg = ('總數量不足\n'
                   '高麗菜韭黃黑豬肉 ' + str(cabbage) +
                   ' 包 + 韭菜黑豬肉 ' + str(qty) +
                   ' 包 = ' + str(total) + ' 包\n'
                   '最少需要 ' + str(MIN_ORDER) + ' 包\n\n'
                   '請重新輸入 Go 再試一次')
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=msg)
            )
            user_states[user_id] = None
            return

        user_orders[user_id]['chives'] = qty
        user_states[user_id] = 'input_name'
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text='請輸入您的姓名',
                quick_reply=cancel_quick_reply()
            )
        )

    elif data.startswith('pickup_day='):
        day = data.split('=')[1]
        user_orders[user_id]['delivery_time'] = day
        user_states[user_id] = 'input_remarks'
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text='請輸入備註\n（無備註請輸入 No）',
                quick_reply=cancel_quick_reply()
            )
        )


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    state = user_states.get(user_id)

    if text == '我的ID':
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='您的 LINE ID 是：\n' + user_id)
        )
        return

    if text.lower() == 'go':
        start_order(user_id, event.reply_token)
        return

    if state == 'input_name':
        user_orders[user_id]['name'] = text
        user_states[user_id] = 'input_phone'
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text='請輸入您的電話號碼',
                quick_reply=cancel_quick_reply()
            )
        )

    elif state == 'input_phone':
        user_orders[user_id]['phone'] = text
        user_states[user_id] = 'input_address'
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text='請輸入您的收貨地址',
                quick_reply=cancel_quick_reply()
            )
        )

    elif state == 'input_address':
        user_orders[user_id]['address'] = text
        user_states[user_id] = 'selecting_pickup_day'
        line_bot_api.reply_message(
            event.reply_token,
            make_pickup_flex()
        )

    elif state == 'input_remarks':
        user_orders[user_id]['remarks'] = text
        user_states[user_id] = None
        send_order_summary(user_id, event.reply_token)

    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='請輸入 Go 開始訂購水餃')
        )


if __name__ == '__main__':
    app.run(debug=True)
