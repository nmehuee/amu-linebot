import os
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, PostbackEvent,
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
SHIPPING_FEE = 170
FREE_SHIPPING_THRESHOLD = 2000
MIN_ORDER = 2
MAX_ORDER = 15

ORDER_KEYWORDS = {'go', 'GO', 'Go'}

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

def ask_cabbage(reply_token):
    items = []
    for i in range(0, 13):
        items.append(
            QuickReplyButton(
                action=PostbackAction(
                    label=str(i),
                    data=f'cabbage={i}'
                )
            )
        )
    line_bot_api.reply_message(
        reply_token,
        TextSendMessage(
            text='🥬 請選擇【高麗菜豬肉水餃】數量（包）\n（0-12包，下一步可選13-15包）',
            quick_reply=QuickReply(items=items)
        )
    )

def ask_cabbage_more(reply_token):
    items = []
    for i in range(13, 16):
        items.append(
            QuickReplyButton(
                action=PostbackAction(
                    label=str(i),
                    data=f'cabbage={i}'
                )
            )
        )
    line_bot_api.reply_message(
        reply_token,
        TextSendMessage(
            text='🥬 請選擇【高麗菜豬肉水餃】數量（包）\n（13-15包）',
            quick_reply=QuickReply(items=items)
        )
    )

def ask_chives(reply_token):
    items = []
    for i in range(0, 13):
        items.append(
            QuickReplyButton(
                action=PostbackAction(
                    label=str(i),
                    data=f'chives={i}'
                )
            )
        )
    line_bot_api.reply_message(
        reply_token,
        TextSendMessage(
            text='🌿 請選擇【韭菜豬肉水餃】數量（包）\n（0-12包，下一步可選13-15包）',
            quick_reply=QuickReply(items=items)
        )
    )

def ask_chives_more(reply_token):
    items = []
    for i in range(13, 16):
        items.append(
            QuickReplyButton(
                action=PostbackAction(
                    label=str(i),
                    data=f'chives={i}'
                )
            )
        )
    line_bot_api.reply_message(
        reply_token,
        TextSendMessage(
            text='🌿 請選擇【韭菜豬肉水餃】數量（包）\n（13-15包）',
            quick_reply=QuickReply(items=items)
        )
    )

def start_order(user_id, reply_token):
    user_states[user_id] = 'selecting_cabbage'
    user_orders[user_id] = {}
    items = []
    for i in range(0, 13):
        items.append(
            QuickReplyButton(
                action=PostbackAction(
                    label=str(i),
                    data=f'cabbage={i}'
                )
            )
        )
    line_bot_api.reply_message(
        reply_token,
        TextSendMessage(
            text=(
                '歡迎來到 A-MU水餃！🥟\n\n'
                '📦 商品：\n'
                '• 高麗菜豬肉水餃 NT$200/包\n'
                '• 韭菜豬肉水餃 NT$200/包\n\n'
                '🚚 運費：NT$170（滿NT$2000免運）\n'
                '⚠️ 最少訂購2包，最多15包\n\n'
                '🥬 請選擇【高麗菜豬肉水餃】數量（0-12包）\n'
                '若需要13-15包請在選完後繼續選擇'
            ),
            quick_reply=QuickReply(items=items)
        )
    )

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
    remarks = order.get('remarks', '無')

    summary = (
        f'📋 訂單確認\n'
        f'{'─'*20}\n'
        f'🥬 高麗菜豬肉水餃：{cabbage} 包\n'
        f'🌿 韭菜豬肉水餃：{chives} 包\n'
        f'{'─'*20}\n'
        f'小計：NT${subtotal}\n'
        f'運費：NT${shipping}\n'
        f'💰 總計：NT${total}\n'
        f'{'─'*20}\n'
        f'👤 姓名：{name}\n'
        f'📞 電話：{phone}\n'
        f'📍 地址：{address}\n'
        f'🕐 到貨時間：{delivery_time}\n'
        f'📝 備註：{remarks}\n'
        f'{'─'*20}\n'
        f'💳 匯款資訊：\n'
        f'中國信託銀行(822)\n'
        f'豐原分行\n'
        f'帳號：370540364486\n'
        f'戶名：徐志帆\n\n'
        f'請於24小時內完成匯款，謝謝！🙏'
    )

    line_bot_api.reply_message(
        reply_token,
        TextSendMessage(text=summary)
    )

    if OWNER_ID:
        owner_msg = (
            f'🔔 新訂單通知！\n'
            f'{'─'*20}\n'
            f'🥬 高麗菜：{cabbage} 包\n'
            f'🌿 韭菜：{chives} 包\n'
            f'💰 總計：NT${total}（含運NT${shipping}）\n'
            f'{'─'*20}\n'
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

    if data.startswith('cabbage='):
        qty = int(data.split('=')[1])
        user_orders[user_id]['cabbage'] = qty
        user_states[user_id] = 'selecting_chives'

        items = []
        for i in range(0, 13):
            items.append(
                QuickReplyButton(
                    action=PostbackAction(
                        label=str(i),
                        data=f'chives={i}'
                    )
                )
            )
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=f'已選擇高麗菜：{qty} 包\n\n🌿 請選擇【韭菜豬肉水餃】數量（0-12包）',
                quick_reply=QuickReply(items=items)
            )
        )

    elif data.startswith('chives='):
        qty = int(data.split('=')[1])
        cabbage = user_orders[user_id].get('cabbage', 0)
        total = cabbage + qty

        if total < MIN_ORDER:
            items = []
            for i in range(0, 13):
                items.append(
                    QuickReplyButton(
                        action=PostbackAction(
                            label=str(i),
                            data=f'chives={i}'
                        )
                    )
                )
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f'⚠️ 總數量不足！\n目前：高麗菜{cabbage}包 + 韭菜{qty}包 = {total}包\n最少需要 {MIN_ORDER} 包，請重新選擇韭菜數量',
                    quick_reply=QuickReply(items=items)
                )
            )
            return

        if total > MAX_ORDER:
            items = []
            for i in range(0, 13):
                items.append(
                    QuickReplyButton(
                        action=PostbackAction(
                            label=str(i),
                            data=f'chives={i}'
                        )
                    )
                )
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f'⚠️ 總數量超過上限！\n目前：高麗菜{cabbage}包 + 韭菜{qty}包 = {total}包\n最多 {MAX_ORDER} 包，請重新選擇韭菜數量',
                    quick_reply=QuickReply(items=items)
                )
            )
            return

        user_orders[user_id]['chives'] = qty
        user_states[user_id] = 'input_name'
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=f'✅ 已選擇：高麗菜{cabbage}包 + 韭菜{qty}包 = 共{total}包\n\n請輸入您的【姓名】'
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
            TextSendMessage(text=f'您的 LINE ID 是：\n{user_id}')
        )
        return

    if text in ORDER_KEYWORDS:
        start_order(user_id, event.reply_token)
        return

    if state == 'input_name':
        user_orders[user_id]['name'] = text
        user_states[user_id] = 'input_phone'
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='請輸入您的【電話號碼】')
        )

    elif state == 'input_phone':
        user_orders[user_id]['phone'] = text
        user_states[user_id] = 'input_address'
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='請輸入您的【收貨地址】')
        )

    elif state == 'input_address':
        user_orders[user_id]['address'] = text
        user_states[user_id] = 'input_delivery_time'
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='請輸入【希望到貨時間】\n（例如：2026/04/15 下午）')
        )

    elif state == 'input_delivery_time':
        user_orders[user_id]['delivery_time'] = text
        user_states[user_id] = 'input_remarks'
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='請輸入【備註】\n（無備註請輸入「無」）')
        )

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
