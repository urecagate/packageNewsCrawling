# config.py
import os

# === Azure OpenAI API 및 이메일 관련 민감 정보 설정 ===
azure_endpoint = "https://apim-dwdp-openai.azure-api.net/007/openai/deployments/gpt-4o-mini/chat/completions?api-version=2024-04-01-preview"
azure_subscription_key = "d932deacbffc451e84417fac864394b9"
azure_application = "nikkei_nes_scrapping_test"
azure_compCode = "industry"
azure_userID = "eoaud0012"
azure_userNM = "daemyeong_lee"
azure_serviceType = "translate"  # 번역 서비스

email_password = "xbpq aico snlu dlwt"  # 앱 전용 비밀번호(2FA 사용 시) 권장
sender_email = "dwcbj6214@gmail.com"
os.environ["EMAIL_PASSWORD"] = email_password

# --------------------------------------------------------------------
# MUST VISIT 사이트 목록
MUST_VISIT_WEBSITES = [
    "https://www.glass-international.com/news",
    # "https://canmaker.com/", Canmaker는 유료 구독 필요
    "https://petpla.net/category/news/",
    "https://www.packagingdigest.com/",
    "https://www.bevindustry.com/articles/topic/2642",
    "https://www.beveragedaily.com/News/",
    "https://packagingeurope.com/sections/news",
    "https://www.packagingnews.com.au/latest",
    "https://www.packagingdive.com/"
]