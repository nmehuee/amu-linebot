import os
import json
import re
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    FlexSendMessage, PostbackEvent
)

app = Flask(__name__)

# ── 環境變數（對應 Render 設定的 KEY 名稱）──
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("CHANNEL_SECRET")
OWNER_ID = os.environ.get("OWNER_ID")

# ── 啟動前檢查 ──
if not LINE_CHANNEL_ACCESS_TOKEN:
    raise RuntimeError("❌ 缺少環境變數：CHANNEL_ACCESS_TOKEN")
if not LINE_CHANNEL_SECRET:
    raise RuntimeError("❌ 缺少環境變數：CHANNEL_SECRET")
if not OWNER_ID:
    print("⚠️  警告：OWNER_ID 未設定，將無法通知店主")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ── 商品設定 ──────────────────────────────────────────
PRODUCTS = {
    "cabbage": {"name": "高麗菜豬肉水餃", "price": 200},
    "chives":  {"name": "韭菜豬肉水餃",   "price": 200},
}
MIN_ORDER = 4
MAX_ORDER = 12

# ── 運費計算 ──────────────────────────────────────────
def calc_shipping(total_packs):
    if total_packs >= 12:
        return 0
    elif total_packs >= 10:
        return 100
    elif total_packs >= 7:
        return 150
    elif total_packs >= 4:
        return 175
    else:
        return 0

# ── 使用者狀態管理（記憶體版）────────────────────────
user_states = {}

def get_state(uid):
    if uid not in user_states:
        user_states[uid] = {"step": "idle", "order": {}}
    return user_states[uid]

def reset_state(uid):
    user_states[uid] = {"step": "idle", "order": {}}

# ── 歡迎 Flex 訊息 ────────────────────────────────────
def make_welcome_flex():
    return FlexSendMessage(
        alt_text="歡迎光臨 A-MU 水餃！",
        contents={
            "type": "bubble",
            "size": "kilo",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#FFF3E0",
                "paddingAll": "16px",
                "contents": [
                    {
                        "type": "text",
                        "text": "🥟 A-MU 水餃",
                        "weight": "bold",
                        "size": "xl",
                        "color": "#D35400",
                        "align": "center"
                    },
                    {
                        "type": "text",
                        "text": "手工現包・每包50顆",
                        "size": "sm",
                        "color": "#888888",
                        "align": "center",
                        "margin": "sm"
                    }
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "paddingAll": "16px",
                "contents": [
                    # ── 商品價格 ──
                    {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#FFF8F0",
                        "cornerRadius": "8px",
                        "paddingAll": "12px",
                        "spacing": "sm",
                        "contents": [
                            {
                                "type": "text",
                                "text": "🛒 商品價格",
                                "weight": "bold",
                                "size": "sm",
                                "color": "#D35400"
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {
                                        "type": "text",
                                        "text": "高麗菜豬肉水餃",
                                        "size": "sm",
                                        "color": "#333333",
                                        "flex": 5
                                    },
                                    {
                                        "type": "text",
                                        "text": "NT$200 / 包",
                                        "size": "sm",
                                        "color": "#E05C5C",
                                        "flex": 4,
                                        "weight": "bold",
                                        "align": "end"
                                    }
                                ]
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {
                                        "type": "text",
                                        "text": "韭菜豬肉水餃",
                                        "size": "sm",
                                        "color": "#333333",
                                        "flex": 5
                                    },
                                    {
                                        "type": "text",
                                        "text": "NT$200 / 包",
                                        "size": "sm",
                                        "color": "#E05C5C",
                                        "flex": 4,
                                        "weight": "bold",
                                        "align": "end"
                                    }
                                ]
                            }
                        ]
                    },
                    # ── 運費說明 ──
                    {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#F0F8FF",
                        "cornerRadius": "8px",
                        "paddingAll": "12px",
                        "spacing": "sm",
                        "contents": [
                            {
                                "type": "text",
                                "text": "🚚 運費說明",
                                "weight": "bold",
                                "size": "sm",
                                "color": "#2471A3"
                            },
                            {
                                "type": "box",
                                "layout": "horizontal",
                                "contents": [
                                    {
                                        "type": "text",
                                        "text": "4 ~ 6 包",
                                        "size": "sm",
                                        "color": "#333333",
                                        "flex": 3
                                    },
                                    {
                                        "type": "text",
                                        "text": "運費 NT$175",
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
                                        "text": "7 ~ 9 包",
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
                                        "text": "10 ~ 11 包",
                                        "size": "sm",
                                        "color": "#333333",
                                        "flex": 3
                                    },
                                    {
                                        "type": "text",
                                        "text": "運費 NT$100",
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
                                        "text": "12 包",
                                        "size": "sm",
                                        "color": "#333333",
                                        "flex": 3
                                    },
                                    {
                                        "type": "text",
                                        "text": "免運費 🎉",
                                        "size": "sm",
                                        "color": "#27AE60",
                                        "flex": 5,
                                        "weight": "bold"
                                    }
                                ]
                            }
                        ]
                    },
                    # ── 訂購說明 ──
                    {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": "#F9F9F9",
                        "cornerRadius": "8px",
                        "paddingAll": "12px",
                        "spacing": "xs",
                        "contents": [
                            {
                                "type": "text",
                                "text": "📋 訂購說明",
                                "weight": "bold",
                                "size": "sm",
                                "color": "#555555"
                            },
                            {
                                "type": "text",
                                "text": "• 最少訂購 4 包，最多 12 包",
                                "size": "xs",
                                "color": "#666666",
                                "wrap": True
                            },
                            {
                                "type": "text",
                                "text": "• 兩種口味可自由搭配",
                                "size": "xs",
                                "color": "#666666",
                                "wrap": True
                            },
                            {
                                "type": "text",
                                "text": "• 付款方式：銀行轉帳",
                                "size": "xs",
                                "color": "#666666",
                                "wrap": True
                            }
                        ]
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "paddingAll": "12px",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "🛒 立即訂購",
                            "data": "action=start_order"
                        },
                        "style": "primary",
                        "color": "#D35400",
                        "height": "sm"
                    }
                ]
            }
        }
    )

# ── 數量選擇 Flex ─────────────────────────────────────
def make_quantity_flex(product_key):
    product = PRODUCTS[product_key]
    buttons = []
    for i in range(MIN_ORDER, MAX_ORDER + 1):
        buttons.append({
            "type": "button",
            "action": {
                "type": "postback",
                "label": f"{i} 包",
                "data": f"action=set_qty&product={product_key}&qty={i}"
            },
            "style": "secondary",
            "height": "sm",
            "margin": "xs"
        })
    return FlexSendMessage(
        alt_text=f"請選擇 {product['name']} 的數量",
        contents={
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    {
                        "type": "text",
                        "text": f"🥟 {product['name']}",
                        "weight": "bold",
                        "size": "md",
                        "color": "#D35400"
                    },
                    {
                        "type": "text",
                        "text": "請選擇數量（包）：",
                        "size": "sm",
                        "color": "#555555"
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "xs",
                        "contents": buttons
                    },
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "✖ 不購買此口味",
                            "data": f"action=set_qty&product={product_key}&qty=0"
                        },
                        "style": "secondary",
                        "height": "sm",
                        "margin": "md",
                        "color": "#AAAAAA"
                    }
                ]
            }
        }
    )

# ── 訂單確認 Flex ─────────────────────────────────────
def make_confirm_flex(order):
    cabbage_qty = order.get("cabbage", 0)
    chives_qty  = order.get("chives",  0)
    total_packs = cabbage_qty + chives_qty
    subtotal    = total_packs * 200
    shipping    = calc_shipping(total_packs)
    total       = subtotal + shipping

    if shipping == 0:
        shipping_text = "免運費 🎉"
        shipping_color = "#27AE60"
    else:
        shipping_text = f"NT${shipping}"
        shipping_color = "#E05C5C"

    rows = []
    if cabbage_qty > 0:
        rows.append({
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {"type": "text", "text": "高麗菜豬肉水餃",
                 "size": "sm", "color": "#333333", "flex": 5},
                {"type": "text", "text": f"{cabbage_qty} 包",
                 "size": "sm", "color": "#333333", "flex": 2, "align": "end"},
                {"type": "text", "text": f"NT${cabbage_qty*200}",
                 "size": "sm", "color": "#333333", "flex": 3, "align": "end"}
            ]
        })
    if chives_qty > 0:
        rows.append({
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {"type": "text", "text": "韭菜豬肉水餃",
                 "size": "sm", "color": "#333333", "flex": 5},
                {"type": "text", "text": f"{chives_qty} 包",
                 "size": "sm", "color": "#333333", "flex": 2, "align": "end"},
                {"type": "text", "text": f"NT${chives_qty*200}",
                 "size": "sm", "color": "#333333", "flex": 3, "align": "end"}
            ]
        })

    return FlexSendMessage(
        alt_text="請確認您的訂單",
        contents={
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#FFF3E0",
                "paddingAll": "12px",
                "contents": [
                    {
                        "type": "text",
                        "text": "📋 訂單確認",
                        "weight": "bold",
                        "size": "lg",
                        "color": "#D35400",
                        "align": "center"
                    }
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "paddingAll": "16px",
                "contents": [
                    *rows,
                    {"type": "separator"},
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {"type": "text", "text": "商品小計",
                             "size": "sm", "color": "#555555", "flex": 5},
                            {"type": "text", "text": f"NT${subtotal}",
                             "size": "sm", "color": "#333333", "flex": 5, "align": "end"}
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {"type": "text", "text": "運費",
                             "size": "sm", "color": "#555555", "flex": 5},
                            {"type": "text", "text": shipping_text,
                             "size": "sm", "color": shipping_color,
                             "flex": 5, "align": "end", "weight": "bold"}
                        ]
                    },
                    {"type": "separator"},
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {"type": "text", "text": "總金額",
                             "size": "md", "weight": "bold", "color": "#D35400", "flex": 5},
                            {"type": "text", "text": f"NT${total}",
                             "size": "md", "weight": "bold", "color": "#D35400",
                             "flex": 5, "align": "end"}
                        ]
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "paddingAll": "12px",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "✅ 確認，繼續填寫資料",
                            "data": "action=confirm_order"
                        },
                        "style": "primary",
                        "color": "#D35400",
                        "height": "sm"
                    },
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": "🔄 重新選擇數量",
                            "data": "action=restart_qty"
                        },
                        "style": "secondary",
                        "height": "sm"
                    }
                ]
            }
        }
    )

# ── Webhook ───────────────────────────────────────────
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

# ── 文字訊息處理 ──────────────────────────────────────
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    uid  = event.source.user_id
    text = event.message.text.strip()
    state = get_state(uid)
    step  = state["step"]

    # 任何時候輸入「訂購」或「開始」都重新來
    if text in ["訂購", "開始", "start", "Start"]:
        reset_state(uid)
        line_bot_api.reply_message(event.reply_token, make_welcome_flex())
        return

    # ── 填寫聯絡資料流程 ──
    if step == "wait_name":
        state["order"]["name"] = text
        state["step"] = "wait_phone"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="📱 請輸入您的手機號碼：")
        )

    elif step == "wait_phone":
        if not re.fullmatch(r"09\d{8}", text):
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="❌ 手機格式不正確，請輸入 09 開頭的 10 位數號碼：")
            )
            return
        state["order"]["phone"] = text
        state["step"] = "wait_date"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="📅 請輸入希望取貨日期（例如：2025/08/10）：")
        )

    elif step == "wait_date":
        state["order"]["date"] = text
        state["step"] = "wait_remark"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="📝 請輸入備註（無備註請輸入「無」）：")
        )

    elif step == "wait_remark":
        state["order"]["remark"] = text
        state["step"] = "idle"
        send_final_summary(event.reply_token, uid, state["order"])

    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text='請輸入「訂購」開始下單 🥟')
        )

# ── Postback 處理 ─────────────────────────────────────
@handler.add(PostbackEvent)
def handle_postback(event):
    uid  = event.source.user_id
    data = dict(pair.split("=") for pair in event.postback.data.split("&"))
    action = data.get("action")
    state  = get_state(uid)

    if action == "start_order":
        state["step"] = "select_cabbage"
        state["order"] = {}
        line_bot_api.reply_message(
            event.reply_token,
            make_quantity_flex("cabbage")
        )

    elif action == "set_qty":
        product = data.get("product")
        qty     = int(data.get("qty", 0))
        state["order"][product] = qty

        if product == "cabbage":
            state["step"] = "select_chives"
            line_bot_api.reply_message(
                event.reply_token,
                make_quantity_flex("chives")
            )

        elif product == "chives":
            cabbage_qty = state["order"].get("cabbage", 0)
            chives_qty  = state["order"].get("chives",  0)
            total_packs = cabbage_qty + chives_qty

            if total_packs == 0:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="❌ 請至少選擇一種口味！")
                )
                state["step"] = "select_cabbage"
                state["order"] = {}
                line_bot_api.push_message(uid, make_quantity_flex("cabbage"))
                return

            if total_packs < MIN_ORDER:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(
                        text=f"❌ 最少需訂購 {MIN_ORDER} 包（目前選擇 {total_packs} 包），請重新選擇！"
                    )
                )
                state["step"] = "select_cabbage"
                state["order"] = {}
                line_bot_api.push_message(uid, make_quantity_flex("cabbage"))
                return

            if total_packs > MAX_ORDER:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(
                        text=f"❌ 最多訂購 {MAX_ORDER} 包（目前選擇 {total_packs} 包），請重新選擇！"
                    )
                )
                state["step"] = "select_cabbage"
                state["order"] = {}
                line_bot_api.push_message(uid, make_quantity_flex("cabbage"))
                return

            state["step"] = "confirm"
            line_bot_api.reply_message(
                event.reply_token,
                make_confirm_flex(state["order"])
            )

    elif action == "confirm_order":
        state["step"] = "wait_name"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="👤 請輸入您的姓名：")
        )

    elif action == "restart_qty":
        state["step"] = "select_cabbage"
        state["order"] = {}
        line_bot_api.reply_message(
            event.reply_token,
            make_quantity_flex("cabbage")
        )

# ── 最終訂單摘要 ──────────────────────────────────────
def send_final_summary(reply_token, uid, order):
    cabbage_qty = order.get("cabbage", 0)
    chives_qty  = order.get("chives",  0)
    total_packs = cabbage_qty + chives_qty
    subtotal    = total_packs * 200
    shipping    = calc_shipping(total_packs)
    total       = subtotal + shipping

    shipping_text = "免運費 🎉" if shipping == 0 else f"NT${shipping}"

    lines = ["✅ 訂單已成立！", ""]
    lines.append("【訂購內容】")
    if cabbage_qty > 0:
        lines.append(f"  高麗菜豬肉水餃 × {cabbage_qty} 包")
    if chives_qty > 0:
        lines.append(f"  韭菜豬肉水餃 × {chives_qty} 包")
    lines.append("")
    lines.append("【費用明細】")
    lines.append(f"  商品小計：NT${subtotal}")
    lines.append(f"  運費：{shipping_text}")
    lines.append(f"  總金額：NT${total}")
    lines.append("")
    lines.append("【聯絡資料】")
    lines.append(f"  姓名：{order.get('name', '')}")
    lines.append(f"  電話：{order.get('phone', '')}")
    lines.append(f"  取貨日期：{order.get('date', '')}")
    lines.append(f"  備註：{order.get('remark', '')}")
    lines.append("")
    lines.append("【付款資訊】")
    lines.append("  銀行：中國信託（822）")
    lines.append("  帳號：370540364486")
    lines.append(f"  轉帳金額：NT${total}")
    lines.append("")
    lines.append("請完成轉帳後，傳送轉帳截圖給我們，謝謝！🙏")

    summary_text = "\n".join(lines)

    # 回覆給顧客
    line_bot_api.reply_message(
        reply_token,
        TextSendMessage(text=summary_text)
    )

    # 通知店主
    owner_msg = (
        f"🔔 新訂單通知！\n"
        f"姓名：{order.get('name', '')}\n"
        f"電話：{order.get('phone', '')}\n"
        f"取貨日期：{order.get('date', '')}\n"
        f"高麗菜水餃：{cabbage_qty} 包\n"
        f"韭菜水餃：{chives_qty} 包\n"
        f"總金額：NT${total}（含運 {shipping_text}）\n"
        f"備註：{order.get('remark', '')}"
    )
    if OWNER_ID:
        line_bot_api.push_message(OWNER_ID, TextSendMessage(text=owner_msg))

# ── 啟動 ──────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
