from pykiwoom.kiwoom import *
import pandas as pd
import time


pd.options.mode.chained_assignment = None

class KiwoomManager:
    def __init__(self):
        self.kiwoom = Kiwoom()
        self.kiwoom.CommConnect(block=True)
        print("✅ 키움증권 API 연결 성공!")

    def get_current_price(self, code):
        """현재가 한 개만 가져오기"""
        try:
            df = self.kiwoom.block_request("opt10001",
                                           종목코드=code,
                                           output="주식기본정보",
                                           next=0,
                                           show=False)
            if df is not None and not df.empty:
                return abs(int(df['현재가'].iloc[0]))
            return None
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

            if df is None or df.empty:
                return None

            cols = ['일자', '현재가', '시가', '고가', '저가', '거래량']
            df = df[cols]

            # 컬럼명 변경 및 수치 데이터 변환
            df.columns = ['date', 'close', 'open', 'high', 'low', 'volume']
            for col in ['close', 'open', 'high', 'low', 'volume']:
                df[col] = pd.to_numeric(df[col].str.strip(), errors='coerce').fillna(0).abs()

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

    def get_master_code_name(self, code):
        """종목코드로부터 종목명을 가져옵니다."""
        try:
            # pykiwoom에서 제공하는 GetMasterCodeName을 직접 사용
            name = self.kiwoom.GetMasterCodeName(code)
            return name.strip() if name else code
        except Exception as e:
            print(f"❌ 종목명 조회 에러: {e}")
            return code

    def get_condition_codes(self, condition_name):
        try:
            self.kiwoom.GetConditionLoad()
            time.sleep(1)

            condition_dict = self.kiwoom.GetConditionNameList()
            print(f"📋 [시스템 체크] 인식된 목록: {condition_dict}")

            condition_index = None

            # --- 수정된 부분: 리스트와 딕셔너리 모두 대응 가능 ---
            if isinstance(condition_dict, list):
                # 리스트 형태일 때 (예: [('000', '급등주발굴')])
                for idx, name in condition_dict:
                    if condition_name in name:
                        condition_index = int(idx)
                        break
            elif isinstance(condition_dict, dict):
                # 딕셔너리 형태일 때 (예: {'000': '급등주발굴'})
                for idx, name in condition_dict.items():
                    if condition_name in name:
                        condition_index = int(idx)
                        break
            # ----------------------------------------------

            if condition_index is None:
                print(f"❌ '{condition_name}' 조건식을 찾을 수 없습니다.")
                return []

            codes = self.kiwoom.SendCondition("0150", condition_name, condition_index, 0)
            return codes if codes else []

        except Exception as e:
            print(f"⚠️ 종목 발굴 중 오류 발생: {e}")
            return []

if __name__ == "__main__":
    km = KiwoomManager()
    # 테스트: 데이터프레임 확인
    df = km.get_ohlcv("005380")
    print(df.tail())  # 하위 5개 행 출력