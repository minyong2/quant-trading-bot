<img src="https://capsule-render.vercel.app/api?type=waving&color=BDBDC8&height=150&section=header" title="header" />

# 📈 AI AUTO TRADING SYSTEM (KIWOOM x KIS)

---

## 🛠️ PROJECT STATUS
<p align="left">
  <img src="https://img.shields.io/badge/VERSION-1.0.0-blue?style=flat-square">
  <img src="https://img.shields.io/badge/STRATEGY-RANDOM_FOREST-brightgreen?style=flat-square">
  <img src="https://img.shields.io/badge/STABILITY-HIGH-orange?style=flat-square">
</p>

---

## 🚀 About This Bot
- 🤖 **Hybrid Logic:** 키움증권의 **조건검색식**으로 발굴하고, 한국투자증권으로 **실전 매매**.
- 🧠 **Smart Brain:** Random Forest 머신러닝 모델이 실시간 상승 확률(**RF%**) 분석.
- 🛡️ **Risk Guard:** 무한 매수 방지 로직 및 자동 익절(+5%)/손절(-3%) 시스템 구축.
- 📡 **Real-time Notify:** 매매의 모든 순간을 **Discord**로 즉시 브리핑.

---

## 💻 Tech Stacks

### ⚙️ Core Engines
<p align="left">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white">
  <img src="https://img.shields.io/badge/Kiwoom_API-003D7C?style=for-the-badge&logo=windows&logoColor=white">
  <img src="https://img.shields.io/badge/KIS_API-FF0000?style=for-the-badge&logo=target&logoColor=white">
</p>

### 📊 Data & ML
<p align="left">
  <img src="https://img.shields.io/badge/Pandas-150458?style=for-the-badge&logo=pandas&logoColor=white">
  <img src="https://img.shields.io/badge/Scikit_Learn-F7931E?style=for-the-badge&logo=scikitlearn&logoColor=white">
  <img src="https://img.shields.io/badge/NumPy-013243?style=for-the-badge&logo=numpy&logoColor=white">
</p>

### 💬 Communication
<p align="left">
  <img src="https://img.shields.io/badge/Discord_Bot-5865F2?style=for-the-badge&logo=discord&logoColor=white">
</p>

---

## 📂 Project Structure
```text
├── main.py                # ⚙️ 시스템 메인 엔진 (Trading Loop)
├── kiwoom_api.py          # 📡 Kiwoom Manager (Stock Search)
├── kis_api.py             # 💰 KIS Manager (Order/Balance)
├── strategy.py            # 🧠 RF Machine Learning Strategy
├── discord_bot.py         # 📢 Discord Notification Center
└── config.py              # 🔐 API Credentials (Hidden)
