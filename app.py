from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *
import os

app = Flask(__name__)

line_bot_api = LineBotApi(os.environ.get('CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.environ.get('CHANNEL_SECRET'))
OWNER_ID = os.environ.get('OWNER_ID', '')

# ─── 記憶體儲存 ───────────────────────────────────────────
user_states = {}
user_orders = {}
# ──────────────────────────────────────────────────────────


# ═══════════════════════════════════════════════════════════
#  工具函式
# ═══════════════════════════════════════════════════════════

def calc_price(order: dict) -> dict:
    cabbage     = order.get('cabbage', 0)
    chives      = order.get('chives', 0)
    total_packs = cabbage + chives
    subtotal    = total_packs * 200
    shipping    = 0 if subtotal >= 2000 else 170
    total       = subtotal + shipping
    return {
        'cabbage':     cabbage,
        'chives':      chives,
        'total_packs': total_packs,
        'subtotal':    subtotal,
        'shipping':    shipping,
        'total':       total,
    }


PAYMENT_INFO = """\
━━━━━━━━━━━━
💳 匯款資訊：
銀行：中國信託(822)
帳號：370540364486
戶名：徐志帆
分行：頭份分行"""


def get_order_summary(order: dict) -> str:
    p = calc_price(order)
    shipping_text = "免運" if p['shipping'] == 0 else f"NT${p['shipping']}"
    return f"""\
✅ 訂單確認

👤 姓名：{order.get('name')}
📞 電話：{order.get('phone')}
📍 地址：{order.get('address')}
📅 希望到貨時間：{order.get('delivery_time')}
📝 備註：{order.get('remarks', '無')}

🥟 高麗菜豬肉水餃：{p['cabbage']} 包 (NT${p['cabbage'] * 200})
🥟 韭菜豬肉水餃：{p['chives']} 包 (NT${p['chives'] * 200})
📦 總包數：{p['total_packs']} 包

💰 小計：NT${p['subtotal']}
🚚 運費：{shipping_text}
💳 總計：NT${p['total']}

{PAYMENT_INFO}

匯款後請告知後五碼，謝謝！🙏"""


def get_owner_notification(order: dict) -> str:
    p = calc_price(order)
    return f"""\
🔔 新訂單通知！

👤 姓名：{order.get('name')}
📞 電話：{order.get('phone')}
📍 地址：{order.get('address')}
📅 希望到貨時間：{order.get('delivery_time')}
📝 備註：{order.get('remarks', '無')}

🥟 高麗菜豬肉水餃：{p['cabbage']} 包
🥟 韭菜豬肉水餃：{p['chives']} 包
📦 總包數：{p['total_packs']} 包

💰 小計：NT${p['subtotal']}
🚚 運費：NT${p['shipping']}
💳 總計：NT${p['total']}

{PAYMENT_INFO}"""


def send_owner_notification(order: dict):
    if OWNER_ID:
        line_bot_api.push_message(
            OWNER_ID,
            TextSendMessage(text=get_owner_notification(order))
        )


# ═══════════════════════════════════════════════════════════
#  Quick Reply 數量選擇（0~15，橫排）
# ═══════════════════════════════════════════════════════════

def build_quantity_quick_reply(flavor: str) -> list:
    return [
        QuickReplyButton(
            action=PostbackAction(
                label=str(i),
                data=f'{flavor}_{i}',
                display_text=f'{i} 包'
            )
        )
        for i in range(16)  # 0 ~ 15
    ]


def ask_cabbage(reply_token):
    line_bot_api.reply_message(
        reply_token,
        TextSendMessage(
            text='🥟 高麗菜黑豬肉水餃\nNT$200／包，請選擇數量（0～15）：',
            quick_reply=QuickReply(items=build_quantity_quick_reply('cabbage'))
        )
    )


def ask_chives(reply_token, *, push_to=None):
    msg = TextSendMessage(
        text='🥟 韭菜黑豬肉水餃\nNT$200／包，請選擇數量（0～15）：',
        quick_reply=QuickReply(items=build_quantity_quick_reply('chives'))
    )
    if push_to:
        line_bot_api.push_message(push_to, msg)
    else:
        line_bot_api.reply_message(reply_token, msg)


# ═══════════════════════════════════════════════════════════
#  訂購流程入口
# ═══════════════════════════════════════════════════════════

def start_order(user_id: str, reply_token):
    user_states[user_id] = 'select_cabbage'
    user_orders[user_id] = {}
    ask_cabbage(reply_token)


# ═══════════════════════════════════════════════════════════
#  Webhook 入口
# ═══════════════════════════════════════════════════════════

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'


# ═══════════════════════════════════════════════════════════
#  文字訊息處理
# ═══════════════════════════════════════════════════════════

ORDER_KEYWORDS = {'go', 'GO', 'Go'}

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text    = event.message.text.strip()
    state   = user_states.get(user_id, 'idle')

    # ── 查詢自己的 User ID ──────────────────────────────────
    if text == '我的ID':
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f'你的 User ID 是：\n{user_id}')
        )
        return

    # ── 開始訂購 ────────────────────────────────────────────
    if text in ORDER_KEYWORDS:
        start_order(user_id, event.reply_token)
        return

    # ── 收集個人資料 ────────────────────────────────────────
    if state == 'input_name':
        user_orders[user_id]['name'] = text
        user_states[user_id] = 'input_phone'
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='請輸入您的電話號碼：')
        )
        return

    if state == 'input_phone':
        user_orders[user_id]['phone'] = text
        user_states[user_id] = 'input_address'
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='請輸入收貨地址：')
        )
        return

    if state == 'input_address':
        user_orders[user_id]['address'] = text
        user_states[user_id] = 'input_delivery_time'
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='請輸入希望到貨時間\n（例如：12/25 下午）：')
        )
        return

    if state == 'input_delivery_time':
        user_orders[user_id]['delivery_time'] = text
        user_states[user_id] = 'input_remarks'
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='請輸入備註\n（無備註請輸入「無」）：')
        )
        return

    if state == 'input_remarks':
        user_orders[user_id]['remarks'] = text
        user_states[user_id] = 'idle'

        order   = user_orders[user_id]
        summary = get_order_summary(order)
        send_owner_notification(order)

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=summary)
        )
        return

    # ── 預設回覆 ────────────────────────────────────────────
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(
            text=(
                '歡迎來到 A-MU水餃！🥟\n'
                '━━━━━━━━━━━━\n'
                '📦 每包 NT$200\n'
                '📌 最少訂購 2 包\n'
                '📌 每單上限 15 包\n'
                '🚚 滿 NT$2000 免運費\n'
                '━━━━━━━━━━━━\n'
                '輸入「Go」開始訂單 👇'
            )
        )
    )


# ═══════════════════════════════════════════════════════════
#  Postback 處理（Quick Reply 數量回傳）
# ═══════════════════════════════════════════════════════════

@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    data    = event.postback.data

    # ── 高麗菜數量 ──────────────────────────────────────────
    if data.startswith('cabbage_'):
        count = int(data.split('_')[1])
        user_orders.setdefault(user_id, {})['cabbage'] = count
        user_states[user_id] = 'select_chives'
        ask_chives(event.reply_token)
        return

    # ── 韭菜數量 ────────────────────────────────────────────
    if data.startswith('chives_'):
        count   = int(data.split('_')[1])
        cabbage = user_orders.get(user_id, {}).get('cabbage', 0)
        total   = cabbage + count

        # 最低 2 包
        if total < 2:
            user_states[user_id] = 'select_cabbage'
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f'⚠️ 最少需訂購 2 包！\n目前只選了 {total} 包，請重新選擇！'
                )
            )
            ask_cabbage(user_id)
            return

        # 上限 15 包
        if total > 15:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f'⚠️ 每單上限 15 包！\n目前選了 {total} 包，請重新選擇！'
                )
            )
            ask_chives(None, push_to=user_id)
            return

        user_orders[user_id]['chives'] = count
        user_states[user_id] = 'input_name'

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=(
                    f'✅ 已選擇：\n'
                    f'🥟 高麗菜豬肉：{cabbage} 包\n'
                    f'🥟 韭菜豬肉：{count} 包\n'
                    f'📦 共 {total} 包\n\n'
                    f'請輸入您的姓名：'
                )
            )
        )
        return


# ═══════════════════════════════════════════════════════════
#  健康檢查
# ═══════════════════════════════════════════════════════════

@app.route("/", methods=['GET'])
def home():
    return 'A-MU水餃 LINE Bot 運行中！'


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
