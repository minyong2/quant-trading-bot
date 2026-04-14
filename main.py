import threading
import time
from datetime import datetime
import kiwoom_api
import kis_api
import strategy
import discord_bot
import config


def sync_balance_status(kis_token):
    """현재 한투 잔고를 읽어와서 봇의 상태(평단가, 보유여부)를 최신화합니다."""
    balance_res = kis_api.get_inquire_balance(kis_token)
    if balance_res and balance_res.get('rt_cd') == '0':
        # 기존 보유 상태 초기화 (수동 매도 대응)
        for code in discord_bot.order_states.keys():
            discord_bot.order_states[code] = False

        output1 = balance_res.get('output1', [])
        for item in output1:
            code = item['pdno']
            name = item['prdt_name']

            # 수동으로 산 종목이 감시 리스트에 없으면 자동 추가
            if code not in discord_bot.target_codes:
                discord_bot.target_codes[code] = name
                discord_bot.save_target_codes()

            # 데이터 업데이트
            discord_bot.order_states[code] = True
            discord_bot.avg_buy_prices[code] = float(item['pchs_avg_pric'])
        return True
    return False


def run_trading_bot():
    print(f"[{datetime.now()}] 🚀 AI 자동매매 시스템 가동")

    km = kiwoom_api.KiwoomManager()
    discord_bot.set_kiwoom_manager(km)

    discord_thread = threading.Thread(target=lambda: discord_bot.bot.run(config.DISCORD_TOKEN), daemon=True)
    discord_thread.start()

    kis_token = kis_api.get_access_token()
    if not kis_token: return
    discord_bot.set_token(kis_token)

    # 초기 동기화
    print("📋 잔고 확인 및 보유 상태 동기화 중...")
    sync_balance_status(kis_token)

    last_full_sync = time.time()

    while True:
        try:
            # 5분에 한 번씩 전체 잔고 강제 동기화 (MTS 수동 매매 대응)
            if time.time() - last_full_sync > 300:
                sync_balance_status(kis_token)
                last_full_sync = time.time()
                print("🔄 정기 잔고 동기화 완료 (MTS/수동 매매 반영)")

            now = datetime.now()
            is_market_open = (now.weekday() < 5) and (9 <= now.hour < 15 or (now.hour == 15 and now.minute <= 20))

            for code, name in discord_bot.target_codes.items():
                # 데이터 수집 (키움)
                time.sleep(1.0)
                df = km.get_ohlcv(code, count=30)
                if df is None or df.empty: continue

                current_price = km.get_current_price(code)
                if current_price:
                    discord_bot.current_prices_cache[code] = current_price

                # 수익률 계산
                profit_rate = 0.0
                force_sell_signal = False
                if discord_bot.order_states.get(code) and discord_bot.avg_buy_prices.get(code, 0) > 0:
                    avg_p = discord_bot.avg_buy_prices[code]
                    profit_rate = (current_price - avg_p) / avg_p * 100
                    if profit_rate >= 5.0 or profit_rate <= -3.0:
                        force_sell_signal = True

                signal, up_prob = strategy.get_signal(df)
                if force_sell_signal: signal = "SELL"

                state_str = f"| 수익률: {profit_rate:.2f}%" if discord_bot.order_states.get(code) else "| 미보유"
                print(
                    f"🔍 [{now.strftime('%H:%M:%S')}] {name}({code}): {current_price:,.0f}원 | RF: {up_prob}% | 신호: {signal} {state_str}")

                if is_market_open:
                    # [매도 로직]
                    if signal == "SELL" and discord_bot.order_states.get(code):
                        res = kis_api.send_sell_order(kis_token, code, qty="all")  # 전량매도 함수화 필요
                        if res.get('rt_cd') == '0':
                            sync_balance_status(kis_token)  # 즉시 동기화

                    # [매수 로직]
                    elif signal == "BUY" and not discord_bot.order_states.get(code) and up_prob >= 70:
                        res = kis_api.send_buy_order(kis_token, code)
                        if res.get('rt_cd') == '0':
                            sync_balance_status(kis_token)  # 즉시 동기화

            time.sleep(5)
        except Exception as e:
            print(f"⚠️ 에러: {e}");
            time.sleep(10)


if __name__ == "__main__":
    run_trading_bot()