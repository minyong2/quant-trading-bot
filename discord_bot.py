import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import kis_api
import time
import json
import os

# 봇 설정
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)
km = None

TARGET_CODES_FILE = "target_codes.json"
CHANNEL_ID = 1490610604036325417
shared_token = None

current_prices_cache = {}  # 메인 루프에서 업데이트할 공용 캐시
order_states = {}
avg_buy_prices = {}


def set_token(token):
    global shared_token
    shared_token = token
    print("✅ 디스코드 봇에 한투 공유 토큰이 설정되었습니다.")


def set_kiwoom_manager(kiwoom_manager):
    global km
    km = kiwoom_manager
    print("✅ 디스코드 봇에 키움 매니저가 연결되었습니다.")


@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)}개의 명령어가 성공적으로 동기화되었습니다!")
        print(f"✅ 로그인 성공: {bot.user.name}")

        channel = bot.get_channel(int(CHANNEL_ID))
        if channel:
            await channel.send("🚀 **알림 시스템 온라인!**")
    except Exception as e:
        print(f"❌ 명령어 동기화 에러: {e}")


def load_target_codes():
    if os.path.exists(TARGET_CODES_FILE):
        try:
            with open(TARGET_CODES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ 파일 로드 중 오류 발생: {e}")
    return {"000660": "SK하이닉스"}


def save_target_codes():
    with open(TARGET_CODES_FILE, "w", encoding="utf-8") as f:
        json.dump(target_codes, f, indent=4, ensure_ascii=False)


target_codes = load_target_codes()


# --- [명령어 섹션] ---

@bot.tree.command(name="잔고조회", description="현재 한투 계좌의 실시간 잔고와 수익률을 확인합니다.")
async def balance(interaction: discord.Interaction):
    await interaction.response.defer()  # 3초 타임아웃 방지
    try:
        if not shared_token:
            await interaction.followup.send("⚠️ 시스템에서 토큰이 준비되지 않았습니다.")
            return

        res = kis_api.get_inquire_balance(shared_token)
        if res.get('rt_cd') == '0':
            msg = "💰 **실시간 계좌 잔고 및 수익률**\n"
            msg += "```"
            msg += f"{'종목명(코드)':<15} | {'수량':>5} | {'평단가':>10} | {'수익률':>8}\n"
            msg += "-" * 55 + "\n"

            output1 = res.get('output1', [])
            if not output1:
                msg += "보유 중인 종목이 없습니다."
            else:
                for item in output1:
                    name = item.get('prdt_name', '알 수 없음')
                    code = item.get('pdno', '      ')
                    qty = item.get('hldg_qty', '0')
                    avg_p = item.get('pchs_avg_pric', '0')
                    rt = item.get('evlu_pfls_rt', '0.00')

                    display_name = f"{name}({code})"
                    msg += f"{display_name:<15} | {qty:>5} | {format(int(float(avg_p)), ','):>10} | {float(rt):>+7.2f}%\n"

            msg += "```"
            await interaction.followup.send(msg)
        else:
            await interaction.followup.send(f"❌ 조회 실패: {res.get('msg1', '에러')}")
    except Exception as e:
        print(f"잔고조회 에러: {e}")
        await interaction.followup.send(f"⚠️ 시스템 오류 발생")


@bot.tree.command(name="종목추가", description="종목을 추가합니다.")
async def add_code(interaction: discord.Interaction, search_val: str):
    await interaction.response.defer()
    global target_codes
    code = search_val if search_val.isdigit() and len(search_val) == 6 else km.get_code_from_name(search_val)
    name = km.get_master_code_name(code) if km else search_val

    if code:
        if code not in target_codes:
            target_codes[code] = name
            save_target_codes()
            await interaction.followup.send(f"✅ [{name}]({code}) 추가 성공!")
        else:
            await interaction.followup.send(f"⚠️ 이미 감시 중인 종목입니다.")
    else:
        await interaction.followup.send(f"❌ '{search_val}'을 찾을 수 없습니다.")


@bot.tree.command(name="종목제거", description="감시 리스트에서 종목을 제거합니다.")
async def remove_code(interaction: discord.Interaction, code: str):
    await interaction.response.defer()
    global target_codes
    target_c = code if code in target_codes else (km.get_code_from_name(code) if km else None)

    if target_c in target_codes:
        name = target_codes.pop(target_c)
        save_target_codes()
        await interaction.followup.send(f"🗑️ [{name}]({target_c}) 감시를 중단합니다.")
    else:
        await interaction.followup.send("⚠️ 리스트에 없는 종목입니다.")


@bot.tree.command(name="매수", description="시장가로 즉시 종목을 매수합니다.")
@app_commands.describe(종목="매수할 종목명 또는 코드", 수량="매수할 수량 (기본값 1)")
async def manual_buy(interaction: discord.Interaction, 종목: str, 수량: int = 1):
    await interaction.response.defer()

    # 1. 종목코드 찾기
    code = 종목 if 종목.isdigit() and len(종목) == 6 else km.get_code_from_name(종목)
    name = km.get_master_code_name(code) if km else 종목

    if not code:
        await interaction.followup.send(f"❌ '{종목}' 종목을 찾을 수 없습니다.")
        return

    # 2. 수량 유효성 체크
    if 수량 <= 0:
        await interaction.followup.send(f"⚠️ 수량은 1주 이상이어야 합니다.")
        return

    # 3. 매수 주문 실행
    res = kis_api.send_buy_order(shared_token, code, qty=str(수량))

    if res.get('rt_cd') == '0':
        await interaction.followup.send(f"🔥 **[수동 매수 성공]** {name}({code}) {수량}주 매수 완료!")

        # 봇 메모리에 즉시 반영 (매수했음을 알림)
        order_states[code] = True
    else:
        err_msg = res.get('msg1', '에러 발생')
        await interaction.followup.send(f"❌ 매수 실패: {err_msg}")


@bot.tree.command(name="매도", description="시장가로 즉시 종목을 매도합니다.")
async def manual_sell(interaction: discord.Interaction, 종목: str, 수량: int = None):
    await interaction.response.defer()
    code = 종목 if 종목.isdigit() and len(종목) == 6 else km.get_code_from_name(종목)
    name = km.get_master_code_name(code) if km else 종목

    if not code:
        await interaction.followup.send(f"❌ '{종목}' 종목을 찾을 수 없습니다.")
        return

    balance_res = kis_api.get_inquire_balance(shared_token)
    current_hold = 0
    if balance_res.get('rt_cd') == '0':
        for item in balance_res.get('output1', []):
            if item['pdno'] == code:
                current_hold = int(item['hldg_qty'])
                break

    sell_qty = 수량 if 수량 is not None else current_hold
    if sell_qty <= 0:
        await interaction.followup.send(f"⚠️ 팔 주식이 없습니다. (잔고: {current_hold}주)")
        return

    res = kis_api.send_sell_order(shared_token, code, qty=str(sell_qty))
    if res.get('rt_cd') == '0':
        await interaction.followup.send(f"📉 **[수동 매도 성공]** {name}({code}) {sell_qty}주 완료!")
    else:
        msg = res.get('msg1', '에러')
        await interaction.followup.send(f"❌ 매도 실패: {msg}")


def send_sync_message(msg):
    try:
        if bot.loop is None or not bot.loop.is_running(): return

        async def send():
            await bot.wait_until_ready()
            channel = bot.get_channel(int(CHANNEL_ID))
            if channel:
                await channel.send(msg)
                print(f"📡 [디코 전송 완료] {msg[:20]}...")

        asyncio.run_coroutine_threadsafe(send(), bot.loop)
    except Exception as e:
        print(f"❌ send_sync_message 에러: {e}")