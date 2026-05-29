import threading
import time
from datetime import datetime
import kiwoom_api
import kis_api
import strategy
import discord_bot
import config

# --- [설정 변수] ---
MAX_POSSESSION = 5  # 최대 보유 종목 수
CONDITION_NAME = "급등주발굴"  # 키움증권 영웅문 조건식 이름
BUY_PROB_THRESHOLD = 70  # 매수 최소 RF 확률


def sync_balance_status(kis_token):
    """현재 한투 잔고를 읽어와서 봇의 상태를 최신화합니다."""
    try:
        balance_res = kis_api.get_inquire_balance(kis_token)
        if balance_res and balance_res.get('rt_cd') == '0':
            # 핵심 수정: 기존 기록을 싹 지우지 말고 업데이트만 합니다.
            output1 = balance_res.get('output1', [])

            # 현재 한투 잔고에 있는 종목들 추출
            current_hold_codes = [item['pdno'] for item in output1]

            for item in output1:
                code = item['pdno']
                name = item['prdt_name']
                discord_bot.order_states[code] = True  # 보유 중인 건 확실히 True
                discord_bot.avg_buy_prices[code] = float(item['pchs_avg_pric'])
                if code not in discord_bot.target_codes:
                    discord_bot.target_codes[code] = name

            for code in list(discord_bot.order_states.keys()):
                if discord_bot.order_states[code] and code not in current_hold_codes:

                    pass

            return True
    except Exception as e:
        print(f"🔄 잔고 동기화 중 오류: {e}")
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
    last_condition_sync = 0  # 조건식 마지막 조회 시간 기록용
    condition_codes = []

    # --- [메인 무한 루프 시작] ---
    while True:
        try:
            now = datetime.now()
            print(f"\n--- [ {now.strftime('%H:%M:%S')} ] 탐색 엔진 재가동 ---")

            # 장 운영 시간 체크 (9시 ~ 15시 20분)
            is_market_open = (now.weekday() < 5) and (9 <= now.hour < 15 or (now.hour == 15 and now.minute <= 20))

            # 1. 조건식 리스트 업데이트 (60초 주기로 키움 서버 요청)
            if time.time() - last_condition_sync > 60:
                print("📡 키움 조건식 종목 리스트 업데이트 중...")
                time.sleep(1.0)  # 서버 안정을 위해 조회 전 1초 휴식
                condition_codes = km.get_condition_codes(CONDITION_NAME) or []
                last_condition_sync = time.time()
                print(f"✅ 업데이트 완료: {len(condition_codes)}개 종목 발견")

            # 검색기 종목 + 현재 보유 종목을 합쳐서 검사 (검색기에서 사라져도 매도 대응 가능)
            my_hold_codes = list(discord_bot.order_states.keys())
            search_codes = list(set(condition_codes + my_hold_codes))

            current_possession = sum(1 for v in discord_bot.order_states.values() if v)

            for code in search_codes:
                name = km.get_master_code_name(code)
                time.sleep(0.6)  # 키움 TR 과부하 방지

                df = km.get_ohlcv(code, count=30)
                if df is None or df.empty:
                    continue

                current_price = km.get_current_price(code)
                if current_price and current_price > 0:
                    discord_bot.current_prices_cache[code] = current_price

                profit_rate = 0.0
                force_sell_signal = False
                is_owned = discord_bot.order_states.get(code, False)

                # 보유 종목일 경우 수익률 계산 및 익절/손절 체크
                if is_owned:
                    avg_p = discord_bot.avg_buy_prices.get(code, 0)
                    if avg_p > 0 and current_price > 0:
                        profit_rate = (current_price - avg_p) / avg_p * 100
                        if profit_rate >= 5.0 or profit_rate <= -3.0:
                            force_sell_signal = True

                # 전략 신호 및 RF 확률 획득
                signal, up_prob = strategy.get_signal(df)
                if force_sell_signal:
                    signal = "SELL"

                # 📢 실시간 탐색 로그 출력
                state_str = f"| 수익률: {profit_rate:.2f}%" if is_owned else "| 미보유"
                print(f"🔍 {name}({code}): {current_price:,.0f}원 | RF: {up_prob}% {state_str}")

                # --- [매매 실행 로직] ---
                if is_market_open:
                    # [A] 매도 로직
                    if is_owned and signal == "SELL":
                        print(f"📢 [매도 시도] {name} (수익률: {profit_rate:.2f}%)")

                        # 실제 잔고 수량 확인
                        balance_res = kis_api.get_inquire_balance(kis_token)
                        hold_qty = "0"
                        if balance_res and 'output1' in balance_res:
                            hold_qty = next(
                                (item['hldg_qty'] for item in balance_res['output1'] if item['pdno'] == code), "0")

                        if int(hold_qty) > 0:
                            # --- 수익 계산 로직 ---
                            avg_p = discord_bot.avg_buy_prices.get(code, 0)
                            realized_profit = (current_price - avg_p) * int(hold_qty)  # 수익금
                            realized_rate = (current_price - avg_p) / avg_p * 100 if avg_p > 0 else 0  # 수익률

                            # 실제 매도 주문 전송z
                            res = kis_api.send_sell_order(kis_token, code, qty=hold_qty)

                            if res.get('rt_cd') == '0':
                                # 봇 메모리 업데이트 (중복 방지)
                                discord_bot.order_states[code] = False

                                # --- 🚀 디스코드 알림 메시지 구성 ---
                                result_icon = "💰" if realized_profit > 0 else "📉"
                                msg = (
                                    f"{result_icon} **[자동 매도 완료]** {name}({code})\n"
                                    f"━━━━━━━━━━━━━━\n"
                                    f"💵 **매도가**: {current_price:,.0f}원\n"
                                    f"🏷️ **평단가**: {avg_p:,.0f}원\n"
                                    f"📊 **수익률**: **{realized_rate:+.2f}%**\n"
                                    f"🪙 **수익금**: **{realized_profit:+,0f}원** (약)\n"
                                    f"━━━━━━━━━━━━━━"
                                )

                                # 디스코드 채널로 전송
                                discord_bot.send_sync_message(msg)

                                # 터미널 확인용 출력 (선택사항)
                                print(f"✅ 디스코드 수익 알림 전송 완료: {name}")

                                # 메모리에서 평단가 삭제
                                if code in discord_bot.avg_buy_prices:
                                    del discord_bot.avg_buy_prices[code]

                                time.sleep(2.0)  # 서버 반영 대기
                            else:
                                err = res.get('msg1', '에러')
                                discord_bot.send_sync_message(f"❌ **[자동 매도 실패]** {name}: {err}")
                    # [B] 매수 로직 (elif를 사용하여 매도한 종목은 바로 다시 사지 않음)
                    elif not is_owned and not force_sell_signal and up_prob >= BUY_PROB_THRESHOLD:
                        if current_possession >= MAX_POSSESSION:
                            print(f"⚠️ 매수 스킵: 보유 한도 초과")
                            continue

                        orderable_cash = kis_api.get_orderable_cash(kis_token)
                        if orderable_cash >= current_price:
                            res = kis_api.send_buy_order(kis_token, code, qty="1")
                            if res.get('rt_cd') == '0':
                                discord_bot.order_states[code] = True
                                current_possession += 1
                                discord_bot.send_sync_message(f"🚀 **[매수 완료]** {name}({code}) | {current_price:,.0f}원")
                                time.sleep(2.0)
                        else:
                            print(f"⚠️ 잔액 부족: {name}")

            # 5분마다 전체 잔고 강제 동기화 (오차 방지)
            if time.time() - last_full_sync > 300:
                sync_balance_status(kis_token)
                last_full_sync = time.time()
                print("🔄 정기 잔고 동기화 완료")

            print(f"🏁 [{datetime.now().strftime('%H:%M:%S')}] 모든 종목 분석 끝. 10초 대기...")
            time.sleep(10)

        except Exception as e:
            print(f"⚠️ 에러 발생: {e}")
            time.sleep(10)


if __name__ == "__main__":
    run_trading_bot()