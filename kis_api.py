import requests
import json
import config
import pandas as pd


# 접근 토큰 발급 함수
def get_access_token():
    url = f"{config.URL_BASE}/oauth2/tokenP"
    headers = {"content-type": "application/json"}
    body = {
        "grant_type": "client_credentials",
        "appkey": config.APP_KEY,
        "appsecret": config.APP_SECRET
    }
    res = requests.post(url, headers=headers, data=json.dumps(body))

    res_json = res.json()
    if 'access_token' not in res_json:
        print("❌ 토큰 발급 실패!")
        print(f"응답 내용: {json.dumps(res_json, indent=4, ensure_ascii=False)}")
        return None

    return res_json['access_token']

def get_orderable_cash(token):
    """실제 주문 가능한 순수 현금 잔고 조회"""
    url = f"{config.URL_BASE}/uapi/domestic-stock/v1/trading/inquire-psbl-order"
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": config.APP_KEY,
        "appsecret": config.APP_SECRET,
        "tr_id": config.TR_ID_ORDER_POSSIBLE  # 모의투자용 (실전은 'TTTC8908R')
    }
    params = {
        "CANO": config.CANO,
        "ACNT_PRDT_CD": config.ACNT_PRDT_CD,
        "PDNO": "",
        "ORD_UNPR": "0",
        "ORD_DVSN": "01", # 시장가 기준
        "CMA_EVLU_AMT_ICLD_YN": "Y",
        "OVRS_ICLD_YN": "N"
    }
    try:
        res = requests.get(url, headers=headers, params=params)
        data = res.json()
        if data.get('rt_cd') == '0':
            # nrcv_buy_amt: 미수 없는 순수 현금 주문 가능 금액
            # return int(data['output']['nrcv_buy_amt'])
            return int(data['output']['ord_psbl_cash'])
        return 0
    except:
        return 0

# 내 계좌 잔고(예수금) 조회 함수
def get_balance(token):
    url = f"{config.URL_BASE}/uapi/domestic-stock/v1/trading/inquire-psbl-order"
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": config.APP_KEY,
        "appsecret": config.APP_SECRET,
        "tr_id": "VTTC8908R"  # 'TTTC0802U'(실전) , 'VTTC0802U'(모의)
    }
    params = {
        "CANO": config.CANO,
        "ACNT_PRDT_CD": config.ACNT_PRDT_CD,
        "PDNO": "",  # 종목번호 비우면 전체 잔고
        "ORD_UNPR": "",
        "ORD_DVSN": "01",  # 현금 주문
        "CMA_EVLU_AMT_ICLD_YN": "Y",
        "OVRS_ICLD_YN": "N"
    }
    res = requests.get(url, headers=headers, params=params)
    return res.json()

def send_buy_order(token, ticker, qty="1"):
    """국내주식 현금 매수 주문 (시장가)"""
    url = f"{config.URL_BASE}/uapi/domestic-stock/v1/trading/order-cash"
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": config.APP_KEY,
        "appsecret": config.APP_SECRET,
        "tr_id": config.TR_ID_ORDER_CASH,  # 'TTTC0802U'(실전) , 'VTTC0802U'(모의)
        "custtype": "P",
        "custid": "owow77",
        "hashkey": ""
    }
    data = {
        "CANO": config.CANO,
        "ACNT_PRDT_CD": config.ACNT_PRDT_CD,
        "PDNO": ticker,
        "ORD_DVSN": "01",  # 01: 시장가 (가장 확실한 체결)
        "ORD_QTY": str(qty),
        "ORD_UNPR": "0",   # 시장가는 단가를 0으로 설정
    }
    res = requests.post(url, headers=headers, data=json.dumps(data))
    return res.json()


def send_sell_order(token, ticker, qty="1"):
    """국내주식 현금 매도 주문 (시장가)"""
    url = f"{config.URL_BASE}/uapi/domestic-stock/v1/trading/order-cash"

    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": config.APP_KEY,
        "appsecret": config.APP_SECRET,
        "tr_id": "VTTC0801U",  # 👈 반드시 'VTTC0801U'로 수정! (끝자리가 1입니다)
        "custtype": "P",
        "custid": "owow77",
        "hashkey": ""
    }
    data = {
        "CANO": config.CANO,
        "ACNT_PRDT_CD": config.ACNT_PRDT_CD,
        "PDNO": ticker,
        "ORD_DVSN": "01",  # 시장가
        "ORD_QTY": str(qty),
        "ORD_UNPR": "0",
    }
    res = requests.post(url, headers=headers, data=json.dumps(data))
    return res.json()


def get_inquire_balance(token):
    """
    한국투자증권 주식잔고조회[v2] API 호출
    """
    url = f"{config.URL_BASE}/uapi/domestic-stock/v1/trading/inquire-balance"

    # 헤더 설정
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": config.APP_KEY,
        "appsecret": config.APP_SECRET,
        "tr_id": config.TR_ID_BALANCE,
    }
    params = {
        "CANO": config.CANO,  # 계좌번호 앞 8자리
        "ACNT_PRDT_CD": config.ACNT_PRDT_CD,  # 계좌번호 뒤 2자리
        "AFHR_FLPR_YN": "N",  # 시간외단가여부 (N: 아니오)
        "OFL_YN": "",  # 오프라인여부 (공백)
        "INQR_DVSN": "02",  # 조회구분 (02: 종목별)
        "UNPR_DVSN": "01",  # 단가구분 (01: 평단가)
        "FUND_STTL_ICLD_YN": "N",  # 펀드결제포함여부 (N)
        "FNCG_AMT_AUTO_RDPT_YN": "N",  # 융자금액자동상환여부 (N)
        "PRCS_DVSN": "00",  # 처리구분 (00: 전일포함)
        "CTX_AREA_FK100": "",  # 연속조회검색조건
        "CTX_AREA_NK100": ""  # 연속조회키
    }

    try:
        res = requests.get(url, headers=headers, params=params)
        res_data = res.json()

        if res_data.get('rt_cd') != '0':
            print(f"❌ 잔고 조회 실패 메시지: {res_data.get('msg1')}")

        return res_data
    except Exception as e:
        print(f"❌ 한투 잔고 조회 API 호출 에러: {e}")
        return {"rt_cd": "7", "msg1": str(e)}


#
# def get_overseas_ohlcv(token, ticker):
#     """미국 주식 분봉/일봉 데이터를 가져옵니다. (감시용)"""
#     url = f"{config.URL_BASE}/uapi/overseas-stock/v1/quotations/dailyprice"
#
#     # 미국 주식은 'NAS' (나스닥), 'NYS' (뉴욕) 등 시장 구분 코드가 필요할 수 있습니다.
#     # 여기서는 범용적으로 티커만 사용하거나 시장코드를 조합합니다.
#     headers = {
#         "Content-Type": "application/json",
#         "authorization": f"Bearer {token}",
#         "appkey": config.APP_KEY,
#         "appsecret": config.APP_SECRET,
#         "tr_id": "HHDFS01010100",  # 실전 해외주식 일봉 조회 ID
#         "custtype": "P"
#     }
#     params = {
#         "AUTH": "",
#         "EXCD": "NAS",  # MSFT는 나스닥(NAS) 종목
#         "SYMB": ticker,
#         "GUBN": "0",  # 0: 일봉
#         "BYMD": "",
#         "MODP": "Y"
#     }
#
#     res = requests.get(url, headers=headers, params=params)
#     data = res.json()
#
#     if data.get('rt_cd') == '0':
#         # 분석하기 좋게 Pandas DataFrame으로 변환
#         output = data.get('output2', [])
#         df = pd.DataFrame(output)
#         df = df[['clo5', 'open', 'high', 'low', 'tvol']]  # 종가, 시가, 고가, 저가, 거래량
#         df.columns = ['close', 'open', 'high', 'low', 'volume']
#         df = df.apply(pd.to_numeric)
#         return df.iloc[::-1]  # 데이터를 현재 순서로 뒤집음
#     else:
#         print(f"❌ 해외 시세 조회 실패: {data.get('msg1')}")
#         return None




if __name__ == "__main__":
    token = get_access_token()
    balance_data = get_balance(token)

    # 서버 응답 전체 출력 (에러 확인용)
    print("--- 서버 응답 데이터 ---")
    print(json.dumps(balance_data, indent=4, ensure_ascii=False))
    print("-----------------------")

    # 정상일 때만 출력하도록 방어 코드 추가
    if 'output' in balance_data:
        print(f"💰 현재 내 계좌 예수금: {balance_data['output']['ord_psbl_cash']}원")
    else:
        print(f"❌ 에러 발생: {balance_data.get('msg1', '알 수 없는 에러')}")


