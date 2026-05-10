import threading
import time
from datetime import datetime
import kiwoom_api
import kis_api
import strategy
import discord_bot
import config

# --- [설정 변수] ---
MAX_POSSESSION = 10  # 최대 보유 종목 수
CONDITION_NAME = "급등주발굴"  # 키움증권 영웅문 조건식 이름
BUY_PROB_THRESHOLD = 75  # 매수 최소 RF 확률


# -------------------

def sync_balance_status(kis_token):
    """현재 한투 잔고를 읽어와서 봇의 상태를 최신화합니다."""
    balance_res = kis_api.get_inquire_balance(kis_token)
    if balance_res and balance_res.get('rt_cd') == '0':
        new_order_states = {}
        output1 = balance_res.get('output1', [])
        for item in output1:
            code = item['pdno']
            name = item['prdt_name']
            new_order_states[code] = True
            discord_bot.avg_buy_prices[code] = float(item['pchs_avg_pric'])
            if code not in discord_bot.target_codes:
                discord_bot.target_codes[code] = name
        discord_bot.order_states = new_order_states
        return True
    return False


def run_trading_bot():
    print(f"[{datetime.now()}] 🚀 AI 완전 자동 탐색 시스템 가동 (MAX: {MAX_POSSESSION})")

    km = kiwoom_api.KiwoomManager()
    discord_bot.set_kiwoom_manager(km)

    # 디스코드 봇을 별도 쓰레드로 실행
    discord_thread = threading.Thread(target=lambda: discord_bot.bot.run(config.DISCORD_TOKEN), daemon=True)
    discord_thread.start()

    # 한국투자증권 토큰 발급
    kis_token = kis_api.get_access_token()
    if not kis_token:
        print("❌ 한투 토큰 발급 실패. 프로그램을 종료합니다.")
        return
    discord_bot.set_token(kis_token)

    # 초기 잔고 동기화
    sync_balance_status(kis_token)
    last_full_sync = time.time()

    while True:
        try:
            now = datetime.now()
            # 장 운영 시간 체크 (9시 ~ 15시 20분)
            is_market_open = (now.weekday() < 5) and (9 <= now.hour < 15 or (now.hour == 15 and now.minute <= 20))

            # 검색기 종목 + 현재 보유 종목을 합쳐서 검사 (검색기에서 사라져도 매도 대응 가능)
            condition_codes = km.get_condition_codes(CONDITION_NAME) or []
            my_hold_codes = list(discord_bot.order_states.keys())
            search_codes = list(set(condition_codes + my_hold_codes))

            current_possession = sum(1 for v in discord_bot.order_states.values() if v)

            for code in search_codes:
                name = km.get_master_code_name(code)
                time.sleep(0.2)  # 키움 TR 과부하 방지

                df = km.get_ohlcv(code, count=30)
                if df is None or df.empty: continue

                current_price = km.get_current_price(code)

                # 디스코드 봇 캐시에 현재가 공유
                if current_price > 0:
                    discord_bot.current_prices_cache[code] = current_price

                profit_rate = 0.0
                force_sell_signal = False
                is_owned = discord_bot.order_states.get(code, False)

                # 1. 보유 종목일 경우 수익률 계산 및 익절/손절 체크
                if is_owned:
                    avg_p = discord_bot.avg_buy_prices.get(code, 0)
                    if avg_p > 0 and current_price > 0:
                        profit_rate = (current_price - avg_p) / avg_p * 100

                        # 익절(+5%) 또는 손절(-3%) 조건 확인
                        if profit_rate >= 5.0 or profit_rate <= -3.0:
                            force_sell_signal = True
                            cond_type = "🚀 [익절 구간 통과]" if profit_rate >= 5.0 else "⚠️ [손절 구간 진입]"

                            # 알림 전송 (중복 전송 방지를 위해 로그는 출력하되 전송은 신중하게)
                            discord_bot.send_sync_message(
                                f"{cond_type} {name}({code})\n"
                                f"📈 현재 수익률: **{profit_rate:.2f}%**\n"
                                f"🔔 상태: {'장 오픈 시 즉시 매도 예정' if not is_market_open else '현재 자동 매도를 시도합니다.'}"
                            )

                # 2. 전략 신호 및 RF 확률 획득
                signal, up_prob = strategy.get_signal(df)

                # 강제 매도 조건이면 전략 신호 무시하고 SELL로 고정
                if force_sell_signal:
                    signal = "SELL"

                # 📢 실시간 탐색 로그 출력
                state_str = f"| 수익률: {profit_rate:.2f}%" if is_owned else "| 미보유"
                print(
                    f"🔍 [{now.strftime('%H:%M:%S')}] {name}({code}): {current_price:,.0f}원 | RF: {up_prob}% {state_str}")

                # --- [매매 실행 로직] ---
                if is_market_open:

                    # [A] 매도 로직 (최우선순위)
                    if is_owned and signal == "SELL":
                        print(f"📢 [매도 시도] {name} (수익률: {profit_rate:.2f}%)")

                        balance_res = kis_api.get_inquire_balance(kis_token)
                        hold_qty = "0"
                        if balance_res and 'output1' in balance_res:
                            hold_qty = next(
                                (item['hldg_qty'] for item in balance_res['output1'] if item['pdno'] == code), "0")

                        if int(hold_qty) > 0:
                            res = kis_api.send_sell_order(kis_token, code, qty=hold_qty)
                            if res.get('rt_cd') == '0':
                                discord_bot.send_sync_message(f"✅ **[자동 매도 성공]** {name}({code}) {hold_qty}주 전량 매도 완료!")
                                # 매도 성공 후 즉시 상태값 업데이트하여 중복 매도/매수 방지
                                discord_bot.order_states[code] = False
                                time.sleep(1.0)
                                sync_balance_status(kis_token)
                            else:
                                err = res.get('msg1', '알 수 없는 오류')
                                discord_bot.send_sync_message(
                                    f"❌ **[자동 매도 실패!!]** {name}({code})\n사유: {err}\n명령어: `/매도 {name}`")

                    # [B] 매수 로직 (매도 대상이 아닐 때만 진입)
                    elif not is_owned and not force_sell_signal and up_prob >= BUY_PROB_THRESHOLD:
                        # 보유 한도 체크
                        if current_possession >= MAX_POSSESSION:
                            print(f"⚠️ 매수 스킵: 보유 한도({MAX_POSSESSION}개) 초과")
                            continue

                        # 2중 체크: 이미 봇 메모리에 매수된 것으로 확인되면 통과
                        if discord_bot.order_states.get(code) == True:
                            continue

                        orderable_cash = kis_api.get_orderable_cash(kis_token)
                        if orderable_cash >= current_price:
                            res = kis_api.send_buy_order(kis_token, code, qty="1")
                            if res.get('rt_cd') == '0':
                                discord_bot.send_sync_message(
                                    f"🚀 **[매수 완료]** {name}({code})\n확률: {up_prob}% | 가격: {current_price:,.0f}원")
                                # 즉시 보유 상태로 변경하여 다음 루프에서 또 사는 것 방지
                                discord_bot.order_states[code] = True
                                current_possession += 1
                                time.sleep(1.5)
                                sync_balance_status(kis_token)
                        else:
                            print(f"⚠️ 잔액 부족으로 {name} 매수 실패")

            # 5분마다 전체 잔고 강제 동기화 (오차 방지)
            if time.time() - last_full_sync > 300:
                sync_balance_status(kis_token)
                last_full_sync = time.time()
                print("🔄 정기 잔고 동기화 완료")

            print(f"🏁 [탐색 완료] {len(search_codes)}개 종목 분석 끝. 5초 후 재시작...")
            time.sleep(5)

        except Exception as e:
            print(f"⚠️ 에러 발생: {e}")
            time.sleep(10)


if __name__ == "__main__":
    run_trading_bot()