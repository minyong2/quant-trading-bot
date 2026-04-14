from pykiwoom.kiwoom import *
import pandas as pd
import time


class KiwoomManager:
    def __init__(self):
        self.kiwoom = Kiwoom()
        self.kiwoom.CommConnect(block=True)
        print("✅ 키움증권 API 연결 성공!")

    def get_master_code_name(self, code):
        try:
            ocx = self.kiwoom.kiwoom
            name = ocx.dynamicCall("GetMasterCodeName(QString)", [code])
            return name.strip() if name else code
        except Exception as e:
            print(f"❌ 종목명 조회 에러: {e}")
            return code

    def get_current_price(self, code):
        """현재가 한 개만 가져오기"""
        try:

            df = self.kiwoom.block_request("opt10001",
                                           종목코드=code,
                                           output="주식기본정보",
                                           next=0,
                                           show=False)
            return abs(int(df['현재가'].iloc[0]))
        except Exception as e:
            print(f"❌ 현재가 조회 에러: {e}")
            return None

    def get_ohlcv(self, code, interval='day', count=100):
        try:
            df = self.kiwoom.block_request("opt10081",
                                           종목코드=code,
                                           기준일자=time.strftime('%Y%m%d'),
                                           수정주가구분=1,
                                           output="주식일봉차트조회",
                                           next=0,
                                           show=False)

            cols = ['일자', '현재가', '시가', '고가', '저가', '거래량']
            df = df[cols]

            # 영문 컬럼명으로 변경
            df.columns = ['date', 'close', 'open', 'high', 'low', 'volume']

            for col in ['close', 'open', 'high', 'low', 'volume']:
                df[col] = pd.to_numeric(df[col].str.strip()).abs()

            df = df.sort_values(by='date').reset_index(drop=True)

            return df.tail(count).copy()

        except Exception as e:
            print(f"❌ OHLCV 데이터 로드 실패: {e}")
            return None

    def get_code_from_name(self, name):
        """종목명을 넣으면 종목코드를 반환 (예: '삼성전자' -> '005930')"""
        try:
            ocx = self.kiwoom.kiwoom

            markets = ["0", "10", "8"]
            all_codes = []
            for market in markets:
                codes = ocx.dynamicCall("GetCodeListByMarket(QString)", [market])
                all_codes.extend(codes.split(';'))


            search_name = name.strip()

            for code in all_codes:
                if not code: continue

                target_name = ocx.dynamicCall("GetMasterCodeName(QString)", [code]).strip()

                if target_name == search_name:
                    return code

            for code in all_codes:
                if not code: continue
                target_name = ocx.dynamicCall("GetMasterCodeName(QString)", [code]).strip()
                if search_name in target_name:
                    print(f"🔍 유사 종목 발견: {target_name}({code})")
                    return code

            return None

        except Exception as e:
            print(f"❌ 종목명 변환 중 에러 발생: {e}")
            return None
if __name__ == "__main__":
    km = KiwoomManager()
    # 테스트: 데이터프레임 확인
    df = km.get_ohlcv("005380")
    print(df.tail())  # 하위 5개 행 출력