import discord
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
CHANNEL_ID = 1490610602694017024
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
    return {"000660": "SK하이닉스"}

def save_target_codes():
    with open(TARGET_CODES_FILE, "w", encoding="utf-8") as f:
        json.dump(target_codes, f, indent=4, ensure_ascii=False)

# 초기 로드
target_codes = load_target_codes()

@bot.tree.command(name="잔고조회", description="현재 한투 계좌 잔고를 확인합니다.")
async def balance(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        if not shared_token:
            await interaction.followup.send("⚠️ 시스템에서 토큰이 준비되지 않았습니다.")
            return

        res = kis_api.get_inquire_balance(shared_token)
        if res.get('rt_cd') == '0':
            msg = "💰 **현재 계좌 잔고**\n"
            if not res.get('output1'):
                msg += "보유 중인 종목이 없습니다."
            else:
                for item in res['output1']:
                    name = item.get('prdt_name', '알 수 없음')
                    qty = item.get('hldg_qty', '0')
                    rt = item.get('evlu_pfls_rt', '0')
                    msg += f"- {name}: {qty}주 (수익률: {rt}%)\n"
            await interaction.followup.send(msg)
        else:
            await interaction.followup.send(f"❌ 조회 실패: {res.get('msg1', '에러')}")
    except Exception as e:
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

    # 코드가 직접 딕셔너리에 있는지 확인
    target_c = None
    if code in target_codes:
        target_c = code
    else:
        # 이름으로 입력했을 경우 코드를 찾아서 확인
        found_code = km.get_code_from_name(code) if km else None
        if found_code in target_codes:
            target_c = found_code

    if target_c:
        name = target_codes.pop(target_c)
        save_target_codes()
        await interaction.followup.send(f"🗑️ [{name}]({target_c}) 감시를 중단합니다.")
    else:
        await interaction.followup.send("⚠️ 리스트에 없는 종목입니다.")


@bot.tree.command(name="감시현황", description="현재 감시 중인 종목 리스트를 확인합니다.")
async def watch_status(interaction: discord.Interaction):
    if not target_codes:
        await interaction.response.send_message("⚠️ 현재 감시 중인 종목이 없습니다.")
        return

    msg = "📋 **현재 종목 감시 현황**\n"
    msg += "---" * 10 + "\n"

    for i, (code, name) in enumerate(target_codes.items(), 1):

        price = current_prices_cache.get(code, "조회 대기 중")

        if isinstance(price, (int, float)):
            p_str = f"**{format(int(price), ',')}원**"
        else:
            p_str = f"*{price}*"

        msg += f"{i}. **{name}**(`{code}`): {p_str}\n"

    msg += "---" * 10 + "\n"
    msg += "💡 실시간 가격은 매매 루프에서 갱신됩니다."
    await interaction.response.send_message(msg)


@bot.tree.command(name="수익률", description="감시 종목들의 수익률 현황을 확인합니다.")
async def profit_status(interaction: discord.Interaction):
    if not target_codes:
        await interaction.response.send_message("⚠️ 현재 감시 중인 종목이 없습니다.")
        return
    msg = "📊 **실시간 종목 수익률 현황**\n"
    msg += "```"
    msg += f"{'종목명':<10} | {'평단가':>10} | {'현재가':>10} | {'수익률':>7}\n"
    msg += "-" * 50 + "\n"

    found_any = False
    for code, name in target_codes.items():
        # 보유 중(True)인 종목만 출력
        if order_states.get(code) == True:
            found_any = True
            avg_p = avg_buy_prices.get(code, 0)
            curr_p = current_prices_cache.get(code, 0)

            profit_rt = 0.0
            if avg_p > 0:
                profit_rt = (curr_p - avg_p) / avg_p * 100

            msg += f"{name:<8} | {format(int(avg_p), ','):>10} | {format(int(curr_p), ','):>10} | {profit_rt:+.2f}%\n"

    msg += "```"

    if not found_any:
        await interaction.response.send_message("ℹ️ 현재 실제로 보유 중인 감시 종목이 없습니다. (잔고 동기화 중...)")
    else:
        await interaction.response.send_message(msg)

@bot.tree.command(name="매수", description="시장가로 즉시 종목을 매수합니다.")
async def manual_buy(interaction: discord.Interaction, 종목: str, 수량: int = 1):
    await interaction.response.defer()

    # 종목코드 찾기
    code = 종목 if 종목.isdigit() and len(종목) == 6 else km.get_code_from_name(종목)
    name = km.get_master_code_name(code) if km else 종목

    if not code:
        await interaction.followup.send(f"❌ '{종목}' 종목을 찾을 수 없습니다.")
        return

    res = kis_api.send_buy_order(shared_token, code, qty=str(수량))

    if res.get('rt_cd') == '0':
        await interaction.followup.send(f"🔥 **[수동 매수 성공]** {name}({code}) {수량}주\n곧 수익률 현황에 반영됩니다.")
    else:
        await interaction.followup.send(f"❌ 매수 실패: {res.get('msg1')}")


@bot.tree.command(name="매도", description="시장가로 즉시 종목을 매도합니다.")
async def manual_sell(interaction: discord.Interaction, 종목: str, 수량: int = None):
    await interaction.response.defer()

    # 1. 종목 코드 확인
    code = 종목 if 종목.isdigit() and len(종목) == 6 else km.get_code_from_name(종목)
    name = km.get_master_code_name(code) if km else 종목

    if not code:
        await interaction.followup.send(f"❌ '{종목}' 종목을 찾을 수 없습니다.")
        return

    # 2. 잔고 조회 (API 호출 1)
    time.sleep(0.5)  # 호출 전 짧은 휴식
    balance_res = kis_api.get_inquire_balance(shared_token)

    if 수량 is None and balance_res.get('rt_cd') == '0':
        for item in balance_res.get('output1', []):
            if item['pdno'] == code:
                수량 = int(item['hldg_qty'])
                break

    if not 수량 or 수량 <= 0:
        await interaction.followup.send(f"⚠️ 보유 수량이 없거나 조회가 실패했습니다.")
        return

    # 3. 매도 주문 실행 (API 호출 2)
    time.sleep(1.0)  # 이전 호출(잔고조회)과 겹치지 않게 1초 대기
    res = kis_api.send_sell_order(shared_token, code, qty=str(수량))

    if res.get('rt_cd') == '0':
        await interaction.followup.send(f"📉 **[수동 매도 성공]** {name}({code}) {수량}주 매도 완료!")

        # 4. 잔고 동기화 유도 (선택 사항)
    else:
        await interaction.followup.send(f"❌ 매도 실패: {res.get('msg1')}")

def send_sync_message(msg):
    try:
        if bot.loop is None or not bot.loop.is_running():
            return

        async def send():
            channel = bot.get_channel(CHANNEL_ID)
            if channel is None:
                try:
                    channel = await bot.fetch_channel(CHANNEL_ID)
                except:
                    return
            if channel:
                await channel.send(msg)

        asyncio.run_coroutine_threadsafe(send(), bot.loop)
    except Exception as e:
        print(f"❌ 디스코드 메시지 전송 실패: {e}")