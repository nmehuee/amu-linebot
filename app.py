from flask import Flask, request, abort, send_file
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    QuickReply, QuickReplyButton, MessageAction,
    FlexSendMessage
)
import os
from supabase import create_client, Client
from openpyxl import Workbook
from datetime import datetime
import io

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("CHANNEL_SECRET")
OWNER_ID = os.environ.get("OWNER_ID")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

user_states = {}

CANCEL_QR = QuickReply(items=[
    QuickReplyButton(action=MessageAction(label="❌ 取消訂單", text="取消")),
])


def get_state(user_id):
    if user_id not in user_states:
        user_states[user_id] = {"step": 0, "order": {}}
    return user_states[user_id]

def reset_state(user_id):
    user_states[user_id] = {"step": 0, "order": {}}

def calculate_order(qty_a, qty_b):
    total_qty = qty_a + qty_b
    subtotal = total_qty * 200
    shipping = 0 if subtotal >= 2000 else 170
    total = subtotal + shipping
    return subtotal, shipping, total

def cancel_order(user_id, reply_token):
    reset_state(user_id)
    quick_reply = QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="🛒 開始訂購", text="開始訂購")),
    ])
    line_bot_api.reply_message(
        reply_token,
        TextSendMessage(
            text="已取消訂單，歡迎下次再來！😊\n\n點下方按鈕可重新開始訂購：",
            quick_reply=quick_reply
        )
    )

def get_user_profile(user_id):
    try:
        res = supabase.table("user_profiles").select("*").eq("user_id", user_id).execute()
        if res.data:
            return res.data[0]
    except Exception as e:
        print(f"get_user_profile error: {e}")
    return None

def save_user_profile(user_id, name, phone, address):
    try:
        supabase.table("user_profiles").upsert({
            "user_id": user_id,
            "name": name,
            "phone": phone,
            "address": address,
            "updated_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        print(f"save_user_profile error: {e}")

def save_order(user_id, order, subtotal, shipping, total):
    try:
        supabase.table("orders").insert({
            "user_id": user_id,
            "name": order["name"],
            "phone": order["phone"],
            "address": order["address"],
            "delivery_time": order["delivery_time"],
            "qty_a": order["qty_a"],
            "qty_b": order["qty_b"],
            "subtotal": subtotal,
            "shipping": shipping,
            "total": total,
            "exported": False
        }).execute()
    except Exception as e:
        print(f"save_order error: {e}")


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    if event.source.type == "group":
        group_id = event.source.group_id
        text = event.message.text.strip()
        print(f"✅ Group ID: {group_id}")

        # 匯出功能（只有 OWNER_ID 群組可用）
        if group_id == OWNER_ID and text == "匯出":
            _export_orders(event.reply_token, group_id)
        return

    user_id = event.source.user_id
    text = event.message.text.strip()
    state = get_state(user_id)
    step = state["step"]

    if text in ["取消", "離開", "掰掰"] and step > 0:
        cancel_order(user_id, event.reply_token)
        return

    if step == 0 or text in ["訂購", "開始訂購", "我要訂購", "你好", "hi", "Hi", "Hello", "hello"]:
        reset_state(user_id)
        state = get_state(user_id)

        if text in ["開始訂購", "訂購", "我要訂購"]:
            state["step"] = 1
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text="🥟 請輸入【A 高麗菜韭黃黑豬肉】數量（0～15）：",
                    quick_reply=CANCEL_QR
                )
            )
        else:
            state["step"] = 0
            quick_reply = QuickReply(items=[
                QuickReplyButton(action=MessageAction(label="🛒 開始訂購", text="開始訂購")),
            ])
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=(
                        "👋 歡迎來到 A-MU 水餃！\n\n"
                        "【商品】\n"
                        "🥟 A. 高麗菜韭黃黑豬肉 NT$200/包\n"
                        "🥟 B. 韭黃黑豬肉 NT$200/包\n\n"
                        "📦 最少2包，最多15包\n"
                        "🚚 滿NT$2000免運，未滿運費NT$170\n\n"
                        "點下方按鈕開始訂購！"
                    ),
                    quick_reply=quick_reply
                )
            )
        return

    if step == 1:
        if not text.isdigit():
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="❌ 請輸入數字（0～15）：", quick_reply=CANCEL_QR)
            )
            return

        qty_a = int(text)
        if qty_a < 0 or qty_a > 15:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="❌ 數量需在 0～15 之間，請重新輸入：", quick_reply=CANCEL_QR)
            )
            return

        state["order"]["qty_a"] = qty_a

        if qty_a == 15:
            state["order"]["qty_b"] = 0
            _go_to_name_step(user_id, event.reply_token, state)
        else:
            remaining = 15 - qty_a
            min_b = max(0, 2 - qty_a)
            state["step"] = 2
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f"A 已選 {qty_a} 包\n請輸入【B 韭黃黑豬肉】數量（{min_b}～{remaining}）：",
                    quick_reply=CANCEL_QR
                )
            )
        return

    if step == 2:
        qty_a = state["order"]["qty_a"]
        remaining = 15 - qty_a
        min_b = max(0, 2 - qty_a)

        if not text.isdigit():
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"❌ 請輸入數字（{min_b}～{remaining}）：", quick_reply=CANCEL_QR)
            )
            return

        qty_b = int(text)
        if qty_b < min_b or qty_b > remaining:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"❌ 數量需在 {min_b}～{remaining} 之間，請重新輸入：", quick_reply=CANCEL_QR)
            )
            return

        state["order"]["qty_b"] = qty_b
        _go_to_name_step(user_id, event.reply_token, state)
        return

    if step == 3:
        if text == "沿用上次資料":
            profile = get_user_profile(user_id)
            if profile:
                state["order"]["name"] = profile["name"]
                state["order"]["phone"] = profile["phone"]
                state["order"]["address"] = profile["address"]
                state["step"] = 6
                _ask_delivery_time(event.reply_token)
            else:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="找不到上次資料，請輸入您的【姓名】：", quick_reply=CANCEL_QR)
                )
            return

        if text == "重新填寫資料":
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="請輸入您的【姓名】：", quick_reply=CANCEL_QR)
            )
            return

        state["order"]["name"] = text
        state["step"] = 4
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="請輸入您的【手機號碼】：", quick_reply=CANCEL_QR)
        )
        return

    if step == 4:
        state["order"]["phone"] = text
        state["step"] = 5
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="請輸入【收貨地址】：", quick_reply=CANCEL_QR)
        )
        return

    if step == 5:
        state["order"]["address"] = text
        state["step"] = 6
        _ask_delivery_time(event.reply_token)
        return

    if step == 6:
        if text not in ["平日", "禮拜六", "皆可"]:
            _ask_delivery_time(event.reply_token, error=True)
            return
        state["order"]["delivery_time"] = text
        state["step"] = 7
        _show_confirm(event.reply_token, state)
        return

    if step == 7:
        if text == "重新填寫":
            reset_state(user_id)
            state = get_state(user_id)
            state["step"] = 1
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text="🔄 重新開始！\n\n請輸入【A 高麗菜韭黃黑豬肉】數量（0～15）：",
                    quick_reply=CANCEL_QR
                )
            )
            return

        if text == "確認送出":
            order = state["order"]
            qty_a = order["qty_a"]
            qty_b = order["qty_b"]
            subtotal, shipping, total = calculate_order(qty_a, qty_b)

            # 儲存到 Supabase
            save_user_profile(user_id, order["name"], order["phone"], order["address"])
            save_order(user_id, order, subtotal, shipping, total)

            # ── 送給用戶的 Flex Message ──
            flex_payment = {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "md",
                    "contents": [
                        {
                            "type": "text",
                            "text": "✅ 訂單已送出！",
                            "weight": "bold",
                            "size": "lg"
                        },
                        {"type": "separator"},
                        {
                            "type": "box",
                            "layout": "vertical",
                            "spacing": "sm",
                            "contents": [
                                {
                                    "type": "box",
                                    "layout": "horizontal",
                                    "contents": [
                                        {"type": "text", "text": "🥟 高麗菜韭黃黑豬肉", "size": "sm", "flex": 5},
                                        {"type": "text", "text": f"{qty_a} 包", "size": "sm", "flex": 2, "align": "end"}
                                    ]
                                },
                                {
                                    "type": "box",
                                    "layout": "horizontal",
                                    "contents": [
                                        {"type": "text", "text": "🥟 韭黃黑豬肉", "size": "sm", "flex": 5},
                                        {"type": "text", "text": f"{qty_b} 包", "size": "sm", "flex": 2, "align": "end"}
                                    ]
                                }
                            ]
                        },
                        {"type": "separator"},
                        {
                            "type": "box",
                            "layout": "vertical",
                            "spacing": "sm",
                            "contents": [
                                {
                                    "type": "box",
                                    "layout": "horizontal",
                                    "contents": [
                                        {"type": "text", "text": "小計", "size": "sm", "color": "#888888", "flex": 3},
                                        {"type": "text", "text": f"NT${subtotal}", "size": "sm", "flex": 4, "align": "end"}
                                    ]
                                },
                                {
                                    "type": "box",
                                    "layout": "horizontal",
                                    "contents": [
                                        {"type": "text", "text": "運費", "size": "sm", "color": "#888888", "flex": 3},
                                        {"type": "text", "text": f"NT${shipping}", "size": "sm", "flex": 4, "align": "end"}
                                    ]
                                },
                                {
                                    "type": "box",
                                    "layout": "horizontal",
                                    "contents": [
                                        {"type": "text", "text": "💰 總計", "size": "sm", "weight": "bold", "flex": 3},
                                        {"type": "text", "text": f"NT${total}", "size": "sm", "weight": "bold", "flex": 4, "align": "end"}
                                    ]
                                }
                            ]
                        },
                        {"type": "separator"},
                        {
                            "type": "box",
                            "layout": "vertical",
                            "spacing": "sm",
                            "contents": [
                                {
                                    "type": "box",
                                    "layout": "horizontal",
                                    "contents": [
                                        {"type": "text", "text": "姓名", "size": "sm", "color": "#888888", "flex": 2},
                                        {"type": "text", "text": order['name'], "size": "sm", "flex": 5}
                                    ]
                                },
                                {
                                    "type": "box",
                                    "layout": "horizontal",
                                    "contents": [
                                        {"type": "text", "text": "電話", "size": "sm", "color": "#888888", "flex": 2},
                                        {"type": "text", "text": order['phone'], "size": "sm", "flex": 5}
                                    ]
                                },
                                {
                                    "type": "box",
                                    "layout": "horizontal",
                                    "contents": [
                                        {"type": "text", "text": "地址", "size": "sm", "color": "#888888", "flex": 2},
                                        {"type": "text", "text": order['address'], "size": "sm", "flex": 5, "wrap": True}
                                    ]
                                },
                                {
                                    "type": "box",
                                    "layout": "horizontal",
                                    "contents": [
                                        {"type": "text", "text": "到貨", "size": "sm", "color": "#888888", "flex": 2},
                                        {"type": "text", "text": order['delivery_time'], "size": "sm", "flex": 5}
                                    ]
                                }
                            ]
                        },
                        {"type": "separator"},
                        {
                            "type": "text",
                            "text": "💳 付款資訊",
                            "weight": "bold",
                            "size": "md",
                            "margin": "md"
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
                                        {"type": "text", "text": "銀行", "size": "sm", "color": "#888888", "flex": 2},
                                        {"type": "text", "text": "中國信託 (822)", "size": "sm", "flex": 5}
                                    ]
                                },
                                {
                                    "type": "box",
                                    "layout": "horizontal",
                                    "contents": [
                                        {"type": "text", "text": "帳號", "size": "sm", "color": "#888888", "flex": 2},
                                        {"type": "text", "text": "370540364486", "size": "sm", "flex": 5}
                                    ]
                                },
                                {
                                    "type": "box",
                                    "layout": "horizontal",
                                    "contents": [
                                        {"type": "text", "text": "戶名", "size": "sm", "color": "#888888", "flex": 2},
                                        {"type": "text", "text": "徐志帆", "size": "sm", "flex": 5}
                                    ]
                                }
                            ]
                        },
                        {"type": "separator"},
                        {
                            "type": "text",
                            "text": "匯款後請告知帳號後5碼，確認後將盡快安排出貨！🙏",
                            "color": "#1E90FF",
                            "weight": "bold",
                            "size": "sm",
                            "wrap": True,
                            "margin": "md"
                        }
                    ]
                }
            }

            line_bot_api.reply_message(
                event.reply_token,
                FlexSendMessage(alt_text="訂單已送出！請查看付款資訊", contents=flex_payment)
            )

            # ── 通知店主 ──
            owner_msg = (
                f"🔔 新訂單通知！\n"
                f"{'─'*20}\n"
                f"🥟 高麗菜韭黃黑豬肉：{qty_a} 包\n"
                f"🥟 韭黃黑豬肉：{qty_b} 包\n"
                f"{'─'*20}\n"
                f"小計：NT${subtotal}\n"
                f"運費：NT${shipping}\n"
                f"💰 總計：NT${total}\n"
                f"{'─'*20}\n"
                f"姓名：{order['name']}\n"
                f"電話：{order['phone']}\n"
                f"地址：{order['address']}\n"
                f"到貨時間：{order['delivery_time']}\n"
                f"User ID：{user_id}"
            )
            if OWNER_ID:
                line_bot_api.push_message(OWNER_ID, TextSendMessage(text=owner_msg))

            reset_state(user_id)
            return

        _show_confirm(event.reply_token, state)
        return

    quick_reply = QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="🛒 開始訂購", text="開始訂購")),
    ])
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(
            text="👋 歡迎來到 A-MU 水餃！\n點下方按鈕開始訂購 🥟",
            quick_reply=quick_reply
        )
    )


def _go_to_name_step(user_id, reply_token, state):
    profile = get_user_profile(user_id)
    state["step"] = 3

    if profile:
        quick_reply = QuickReply(items=[
            QuickReplyButton(action=MessageAction(label="✅ 沿用上次資料", text="沿用上次資料")),
            QuickReplyButton(action=MessageAction(label="✏️ 重新填寫", text="重新填寫資料")),
            QuickReplyButton(action=MessageAction(label="❌ 取消訂單", text="取消")),
        ])
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(
                text=(
                    f"查到您上次的資料：\n"
                    f"{'─'*20}\n"
                    f"姓名：{profile['name']}\n"
                    f"電話：{profile['phone']}\n"
                    f"地址：{profile['address']}\n"
                    f"{'─'*20}\n"
                    f"是否沿用上次資料？"
                ),
                quick_reply=quick_reply
            )
        )
    else:
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text="請輸入您的【姓名】：", quick_reply=CANCEL_QR)
        )


def _ask_delivery_time(reply_token, error=False):
    quick_reply = QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="平日", text="平日")),
        QuickReplyButton(action=MessageAction(label="禮拜六", text="禮拜六")),
        QuickReplyButton(action=MessageAction(label="皆可", text="皆可")),
        QuickReplyButton(action=MessageAction(label="❌ 取消訂單", text="取消")),
    ])
    msg = "❌ 請點選下方按鈕選擇到貨時間：" if error else "請選擇【希望到貨時間】："
    line_bot_api.reply_message(reply_token, TextSendMessage(text=msg, quick_reply=quick_reply))


def _show_confirm(reply_token, state):
    order = state["order"]
    qty_a = order["qty_a"]
    qty_b = order["qty_b"]
    subtotal, shipping, total = calculate_order(qty_a, qty_b)

    confirm_msg = (
        f"📋 請確認您的訂單：\n"
        f"{'─'*20}\n"
        f"🥟 高麗菜韭黃黑豬肉：{qty_a} 包\n"
        f"🥟 韭黃黑豬肉：{qty_b} 包\n"
        f"{'─'*20}\n"
        f"小計：NT${subtotal}\n"
        f"運費：NT${shipping}\n"
        f"💰 總計：NT${total}\n"
        f"{'─'*20}\n"
        f"姓名：{order['name']}\n"
        f"電話：{order['phone']}\n"
        f"地址：{order['address']}\n"
        f"到貨時間：{order['delivery_time']}\n"
        f"{'─'*20}\n\n"
        f"請確認資料是否正確？"
    )

    quick_reply = QuickReply(items=[
        QuickReplyButton(action=MessageAction(label="✅ 確認送出", text="確認送出")),
        QuickReplyButton(action=MessageAction(label="✏️ 重新填寫", text="重新填寫")),
        QuickReplyButton(action=MessageAction(label="❌ 取消訂單", text="取消")),
    ])
    line_bot_api.reply_message(
        reply_token,
        TextSendMessage(text=confirm_msg, quick_reply=quick_reply)
    )


def _export_orders(reply_token, group_id):
    try:
        # 取得未匯出訂單
        res = supabase.table("orders").select("*").eq("exported", False).execute()
        orders = res.data

        if not orders:
            line_bot_api.reply_message(
                reply_token,
                TextSendMessage(text="📭 目前沒有新訂單可以匯出！")
            )
            return

        # 建立 Excel
        wb = Workbook()
        ws = wb.active
        ws.title = "訂單"

        today = datetime.now().strftime("%Y-%m-%d")

        for row_idx, order in enumerate(orders, start=1):
            qty_a = order.get("qty_a", 0)
            qty_b = order.get("qty_b", 0)

            parts = []
            if qty_a > 0:
                parts.append(f"高麗菜韭黃黑豬肉水餃x{qty_a}包")
            if qty_b > 0:
                parts.append(f"韭黃黑豬肉水餃x{qty_b}包")
            goods = "、".join(parts)

            ws.cell(row=row_idx, column=1, value="冷凍")           # A 溫層
            ws.cell(row=row_idx, column=2, value=order["name"])    # B 收件人姓名
            ws.cell(row=row_idx, column=3, value="")               # C 收件人電話（空白）
            ws.cell(row=row_idx, column=4, value=order["phone"])   # D 收件人手機
            ws.cell(row=row_idx, column=5, value=order["address"]) # E 收件人地址
            ws.cell(row=row_idx, column=6, value=today)            # F 出貨日期
            ws.cell(row=row_idx, column=7, value=goods)            # G 貨物內容
            ws.cell(row=row_idx, column=8, value="冷凍食品")        # H 貨物類別
            ws.cell(row=row_idx, column=9, value=order["delivery_time"])  # I 到貨時間

        # 儲存到記憶體
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        # 上傳到 Supabase Storage
        filename = f"orders_{today}_{datetime.now().strftime('%H%M%S')}.xlsx"
        supabase.storage.from_("exports").upload(
            filename,
            output.getvalue(),
            {"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
        )

        # 取得公開下載連結
        public_url = supabase.storage.from_("exports").get_public_url(filename)

        # 標記為已匯出
        ids = [o["id"] for o in orders]
        supabase.table("orders").update({"exported": True}).in_("id", ids).execute()

        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(
                text=f"✅ 匯出完成！共 {len(orders)} 筆訂單\n\n📥 下載連結：\n{public_url}"
            )
        )

    except Exception as e:
        print(f"_export_orders error: {e}")
        line_bot_api.reply_message(
            reply_token,
            TextSendMessage(text=f"❌ 匯出失敗：{str(e)}")
        )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
