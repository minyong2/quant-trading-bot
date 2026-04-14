import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import numpy as np
from google import genai  # 최신 google-genai SDK
import json
import time

from config import GEMIN_API_KEY

client = genai.Client(api_key=GEMIN_API_KEY)
MODEL_NAME = 'gemini-2.0-flash-lite'


def get_signal(df):
    if len(df) < 30: return "HOLD", 0

    df = df.copy()
    df['ma5'] = df['close'].rolling(window=5).mean()
    df['ma20'] = df['close'].rolling(window=20).mean()
    df['diff'] = df['close'].diff()
    df['vol_ma5'] = df['volume'].rolling(window=5).mean()

    train_df = df.dropna().copy()
    features = ['close', 'open', 'high', 'low', 'volume', 'ma5', 'ma20', 'diff', 'vol_ma5']
    X = train_df[features]
    y = (train_df['close'].shift(-1) > train_df['close']).astype(int)

    # 머신러닝 모델 학습
    rf_model = RandomForestClassifier(n_estimators=100, random_state=42)
    rf_model.fit(X.iloc[:-1], y.iloc[:-1])

    # 상승 확률 예측
    last_data = X.tail(1)
    prob = rf_model.predict_proba(last_data)[0]
    up_probability = round(prob[1] * 100, 2)

    current_close = df['close'].iloc[-1]
    ma20_curr = df['ma20'].iloc[-1]

    # 기술적 신호 결정
    signal = "HOLD"
    if up_probability > 60 and current_close > ma20_curr:
        signal = "BUY"
    elif current_close < ma20_curr:
        signal = "SELL"

    return signal, up_probability


def get_ai_prediction(df):
    try:
        # 최근 20일치 데이터를 마크다운 표 형식으로 변환
        ohlcv_data = df.tail(20).to_markdown()

        prompt = f"""
        당신은 대한민국 주식 시장 전문 투자 분석가입니다. 
        제공된 최근 주가 데이터를 바탕으로 기술적 분석을 수행하고 향후 전망을 제시하세요.

        [주가 데이터 (최근 20일)]
        {ohlcv_data}

        [지시 사항]
        1. 현재 추세를 분석하고 단기(5일 이내) 목표가(target_price)를 제시하세요. 
           현재가({df['close'].iloc[-1]}원) 대비 현실적인 목표가를 숫자로만 제시하세요.
        2. 'BUY', 'SELL', 'HOLD' 중 하나의 결정을 내리세요.
        3. 반드시 아래 JSON 형식으로만 답변하세요. 다른 설명은 생략하세요.

        {{
            "decision": "BUY",
            "target_price": 200000,
            "reason": "이유를 간결하게 한 문장으로"
        }}
        """

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )

        if not response or not response.text:
            print("❌ AI 응답이 비어있습니다.")
            return None

        raw_text = response.text.strip()

        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text:
            raw_text = raw_text.split("```")[1].split("```")[0].strip()

        return json.loads(raw_text)

    except Exception as e:
        if "429" in str(e):
            print(f"⚠️ 할당량 초과(429): 잠시 후 다시 시도합니다.")
        else:
            print(f"❌ AI 분석 중 에러 발생: {e}")
        return None