from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *
import os

app = Flask(__name__)

line_bot_api = LineBotApi(os.environ.get('CHANNEL_ACCESS_TOKEN'))
handler = WebhookHandler(os.environ.get('CHANNEL_SECRET'))
OWNER_ID = os.environ.get('OWNER_ID', '')

# 儲存使用者訂單狀態
user_states = {}
user_orders = {}

def send_owner_notification(order):
    """傳送訂單通知給店家"""
    if not OWNER_ID:
        return
    
    cabbage = order.get('cabbage', 0)
    chives = order.get('chives', 0)
    total_packs = cabbage + chives
    subtotal = total_packs * 200
    shipping = 0 if subtotal >= 2000 else 170
    total = subtotal + shipping

    msg = f"""🔔 新訂單通知！

👤 姓名：{order.get('name')}
📞 電話：{order.get('phone')}
📍 地址：{order.get('address')}
📅 希望到貨時間：{order.get('delivery_time')}
📝 備註：{order.get('remarks', '無')}

🥟 高麗菜豬肉水餃：{cabbage} 包
🥟 韭菜豬肉水餃：{chives} 包
📦 總包數：{total_packs} 包

💰 小計：NT${subtotal}
🚚 運費：NT${shipping}
💳 總計：NT${total}

匯款資訊：
銀行：中國信託(822)
帳號：370540364486
戶名：徐志帆
分行：頭份分行"""

    line_bot_api.push_message(OWNER_ID, TextSendMessage(text=msg))

def get_order_summary(order):
    cabbage = order.get('cabbage', 0)
    chives = order.get('chives', 0)
    total_packs = cabbage + chives
    subtotal = total_packs * 200
    shipping = 0 if subtotal >= 2000 else 170
    total = subtotal + shipping

    return f"""✅ 訂單確認

👤 姓名：{order.get('name')}
📞 電話：{order.get('phone')}
📍 地址：{order.get('address')}
📅 希望到貨時間：{order.get('delivery_time')}
📝 備註：{order.get('remarks', '無')}

🥟 高麗菜豬肉水餃：{cabbage} 包 (NT${cabbage*200})
🥟 韭菜豬肉水餃：{chives} 包 (NT${chives*200})
📦 總包數：{total_packs} 包

💰 小計：NT${subtotal}
🚚 運費：{"免運" if shipping == 0 else f"NT${shipping}"}
💳 總計：NT${total}

━━━━━━━━━━━━
💳 請匯款至：
銀行：中國信託(822)
帳號：370540364486
戶名：徐志帆
分行：頭份分行

匯款後請告知後五碼，謝謝！🙏"""

def start_order(user_id):
    user_states[user_id] = 'select_cabbage'
    user_orders[user_id] = {}
    
    buttons_template = TemplateSendMessage(
        alt_text='選擇高麗菜豬肉水餃數量',
        template=ButtonsTemplate(
            title='🥟 高麗菜黑豬肉水餃',
            text='NT$200/包，請選擇數量',
            actions=[
                PostbackAction(label='0包', data='cabbage_0'),
                PostbackAction(label='1包', data='cabbage_1'),
                PostbackAction(label='2包', data='cabbage_2'),
                PostbackAction(label='3包', data='cabbage_3'),
            ]
        )
    )
    return buttons_template

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
    
    # 回覆 User ID（方便設定）
    if text == '我的ID':
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f'你的 User ID 是：\n{user_id}')
        )
        return

    state = user_states.get(user_id, 'idle')

    if text in ['訂購', '開始訂購', '我要訂購', '點餐']:
        line_bot_api.reply_message(event.reply_token, start_order(user_id))
        return

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
            TextSendMessage(text='請輸入備註（如無備註請輸入「無」）：')
        )
        return

    if state == 'input_remarks':
        user_orders[user_id]['remarks'] = text
        user_states[user_id] = 'idle'
        
        order = user_orders[user_id]
        summary = get_order_summary(order)
        
        send_owner_notification(order)
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=summary)
        )
        return

    # 預設回覆
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text='歡迎來到 A-MU水餃！\n請輸入「訂購」開始訂單 🥟')
    )

@handler.add(PostbackEvent)
def handle_postback(event):
    user_id = event.source.user_id
    data = event.postback.data

    if data.startswith('cabbage_'):
        count = int(data.split('_')[1])
        user_orders[user_id]['cabbage'] = count
        user_states[user_id] = 'select_chives'

        buttons_template = TemplateSendMessage(
            alt_text='選擇韭菜豬肉水餃數量',
            template=ButtonsTemplate(
                title='🥟 韭菜黑豬肉水餃',
                text='NT$200/包，請選擇數量',
                actions=[
                    PostbackAction(label='0包', data='chives_0'),
                    PostbackAction(label='1包', data='chives_1'),
                    PostbackAction(label='2包', data='chives_2'),
                    PostbackAction(label='3包', data='chives_3'),
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, buttons_template)

    elif data.startswith('chives_'):
        count = int(data.split('_')[1])
        user_orders[user_id]['chives'] = count

        cabbage = user_orders[user_id].get('cabbage', 0)
        chives = count
        total = cabbage + chives

        if total < 2:
            user_states[user_id] = 'select_cabbage'
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f'⚠️ 最少需訂購2包！\n目前只選了 {total} 包，請重新選擇！')
            )
            line_bot_api.push_message(user_id, start_order(user_id))
            return

        user_states[user_id] = 'input_name'
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f'✅ 已選擇：\n高麗菜豬肉：{cabbage}包\n韭菜豬肉：{chives}包\n共{total}包\n\n請輸入您的姓名：')
        )

@app.route("/", methods=['GET'])
def home():
    return 'A-MU水餃 LINE Bot 運行中！'

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
