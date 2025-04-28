# utils.py
import os
import re
import json
import time
import smtplib
import platform
import gspread
import subprocess
from datetime import datetime as dt
from datetime import timedelta
from dateutil.tz import gettz
from dateutil.parser import parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from urllib.parse import urlparse, urljoin
from newspaper import Article
from weasyprint import HTML

# Import configuration variables from config.py
from config import (
    azure_endpoint, azure_subscription_key, azure_application, 
    azure_compCode, azure_userID, azure_userNM, azure_serviceType, 
    sender_email
)

# 최대 허용 제목 길이 (문자 수)
MAX_TITLE_LENGTH = 100

# 길이 초과 시 재추출할 후보 셀렉터 목록: (CSS selector, attribute or None for text)
TITLE_FALLBACK_SELECTORS = [
    ("h1", None),
    ("meta[property='og:title']", "content"),
    ("meta[name='title']", "content"),
]


# DEBUG_MODE 환경변수에 따라 디버깅 모드 여부 판단 (true이면 디버깅 모드)
DEBUG_MODE = False
print(DEBUG_MODE)

# 환경 변수에서 기사 개수 제한 가져오기
DEFAULT_ARTICLE_LIMIT = 30  # 기본값
ARTICLE_LIMIT = int(os.environ.get("ARTICLE_LIMIT", DEFAULT_ARTICLE_LIMIT))
MIN_SCORE = float(os.environ.get("MIN_ARTICLE_SCORE", "5.0"))

print(f"기사 개수 제한: {ARTICLE_LIMIT}, 최소 점수: {MIN_SCORE}")

# --------------------------------------------------------------------
# Chrome 프로세스를 종료하는 함수 (OS에 따라 분기)
def kill_chrome():
    if platform.system() == "Windows":
        try:
            subprocess.call("taskkill /F /IM chrome.exe", shell=True)
            print("Windows: 모든 Chrome 프로세스 종료 완료")
        except Exception as e:
            print("Windows에서 Chrome 종료 중 오류 발생:", e)
    else:
        try:
            subprocess.call("pkill chrome", shell=True)
            print("Linux: 모든 Chrome 프로세스 종료 완료")
        except Exception as e:
            print("Linux에서 Chrome 종료 중 오류 발생:", e)
    time.sleep(2)

# --------------------------------------------------------------------
# remote debugging 모드로 Chrome 실행 (최종 배포용)
# 디버깅 시에는 incognito 모드로 실행하여 기존 크롬을 종료하지 않고 디버깅합니다.
def start_chrome_debug():
    # 환경 변수로 CI 환경 여부 확인 (GitHub Actions)
    is_ci = os.environ.get('CI', 'false').lower() == 'true'
    
    if DEBUG_MODE:
        print("DEBUG_MODE: Incognito 모드로 실행하므로 remote debugging 모드 생략합니다.")
        return None
    elif is_ci:
        print("CI 환경에서 실행 중: 별도의 Chrome 프로세스를 시작하지 않습니다.")
        return None
    else:
        if platform.system() == "Windows":
            chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            user_data_dir = r"C:\chrome_debug_profile"
            cmd = [
                chrome_path,
                "--remote-debugging-port=9222",
                f"--user-data-dir={user_data_dir}",
                "--headless",  # headless 모드 활성화
                "--disable-gpu"
            ]
            process = subprocess.Popen(cmd)
        else:
            chrome_path = "/usr/bin/google-chrome"
            user_data_dir = "/tmp/chrome_debug_profile"
            cmd = f"{chrome_path} --headless --no-sandbox --disable-setuid-sandbox --disable-dev-shm-usage --disable-gpu --remote-debugging-port=9222 --user-data-dir={user_data_dir}"
            process = subprocess.Popen(cmd, shell=True, env=os.environ.copy())
        print("Chrome remote debugging 모드 실행 중...")
        time.sleep(5)
        return process

# --------------------------------------------------------------------
# Selenium 드라이버 생성 함수
def create_driver_debug():
    # 환경 변수로 CI 환경 여부 확인 (GitHub Actions)
    is_ci = os.environ.get('CI', 'false').lower() == 'true'
    
    chrome_options = Options()
    
    if DEBUG_MODE:
        chrome_options.add_argument("--incognito")
    elif not is_ci:
        chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    
    # 공통 옵션 설정
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-setuid-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--start-maximized")
    
    # CI 환경 또는 도커 환경에서는 항상 headless 모드 사용
    if is_ci or os.path.exists("/.dockerenv"):
        chrome_options.add_argument("--headless=new")
        print("CI 또는 도커 환경: 헤드리스 모드 활성화")
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        from selenium_stealth import stealth
        stealth(driver,
                languages=["ko-KR", "en-US", "en"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True)
    except Exception as e:
        print("selenium_stealth 적용 중 오류:", e)
    
    print("Selenium 드라이버 생성 완료.")
    return driver

# --------------------------------------------------------------------
# 여러 후보 CSS 선택자를 반환하는 함수
def get_candidate_selectors():
    """
    제목, 날짜, 본문에 대해 다양한 후보 CSS 선택자를 반환합니다.
    """
    # 제목 추출: 기존의 일반 선택자에 MSN 전용 영역(h1 태그 내 MSN 전용 요소)을 추가.
    title_selectors = (
        "h1, h2, h3, h4, h5, h6, "
        ".article-title, .headline, [class*='title'], [class*='header'], "
        "msn-article-page h1, cp-article h1"
    )
    
    # 날짜 추출: 기존 선택자에 MSN의 날짜 정보를 담은 span 태그를 추가.
    date_selectors = (
        "time, .published-info, .date, [class*='date'], [class*='time'], "
        "span.viewsAttribution"
    )
    
    # 본문 추출: 일반 기사 본문 후보 외에 MSN 페이지의 기사 영역도 포함.
    body_selectors = (
        ".article-body, .article-content, .storytext, article, "
        "[class*='content'], [class*='body'], msn-article-page, cp-article"
    )
    return {
        "title": title_selectors,
        "date": date_selectors,
        "body": body_selectors
    }

# --------------------------------------------------------------------
# 메타 태그에서 날짜 정보 추출 함수 (여러 후보 선택자 적용)
def get_article_date_from_meta(driver):
    meta_selectors = [
        "meta[property='article:published_time']",
        "meta[name='pubdate']",
        "meta[name='publication_date']",
        "meta[name='date']",
        "div.publishedby p",  # 예시
        "div.below-entry-meta a",  # 예시
        "p.Contributors-Date[data-testid='contributors-date']",
        "div.article-author span",  # Packaging News Australia 등
        "div.date.date-bottom-border span.published-info"  # Packaging Dive 등
    ]
    for selector in meta_selectors:
        try:
            meta_elem = driver.find_element(By.CSS_SELECTOR, selector)
            published_date = meta_elem.get_attribute("content") or meta_elem.text
            if published_date:
                return published_date
        except Exception:
            continue
    return None

# --------------------------------------------------------------------
# 번역 함수 (Azure OpenAI API)
def translate_text(text, mode="default"):
    headers = {
        "Ocp-Apim-Subscription-Key": azure_subscription_key,
        "application": azure_application,
        "compCode": azure_compCode,
        "userID": azure_userID,
        "userNM": azure_userNM,
        "serviceType": azure_serviceType,
        "Content-Type": "application/json; charset=utf-8"
    }
    if mode == "title":
        user_content = f"다음 텍스트를 한국어로 번역해줘:\n\n{text}"
    elif mode == "content":
        user_content = (
            f"다음 기사 본문을 읽고, 머릿말 기호('-')를 사용해 핵심 요약만 만들어줘. "
            f"불필요한 부가 설명이나 원문은 생략하고 오직 요약만 출력해줘. "
            f"또한, 약어가 있다면 전체 단어(병기)를 추가해줘:\n\n{text}"
        )
    else:
        user_content = f"다음 텍스트를 한국어로 번역해줘:\n\n{text}"
    data = {
        "messages": [
            {"role": "system", "content": "너는 한국어 번역 및 요약 도우미야."},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.3
    }
    try:
        data_str = json.dumps(data, ensure_ascii=False).encode("utf-8")
        response = requests.post(azure_endpoint, headers=headers, data=data_str)
        response.raise_for_status()
        result = response.json()
        translated = result["choices"][0]["message"]["content"].strip()
        print("번역 결과:", translated)
        return translated
    except Exception as e:
        print("번역 중 오류 발생:", e)
        return text

def evaluate_article(keyword, article_summary):
    """
    키워드와 기사 요약을 평가하여 점수(float)와 해설(str)을 분리하여 반환하는 함수
    
    Args:
        keyword (str): 검색 키워드
        article_summary (str): 기사 요약 텍스트
        
    Returns:
        tuple: (점수(float), 해설(str))
    """
    headers = {
        "Ocp-Apim-Subscription-Key": azure_subscription_key,
        "application": azure_application,
        "compCode": azure_compCode,
        "userID": azure_userID,
        "userNM": azure_userNM,
        "serviceType": azure_serviceType,
        "Content-Type": "application/json; charset=utf-8"
    }
    
    user_content = f"""당신의 역할은 다음과 같습니다:
- "키워드"와 "기사 요약"을 입력값으로 받습니다.
- 기사 요약이 키워드와 얼마나 직접적이고 깊이 있게 연관되는지(키워드 연관성), 그리고 기사 내용이 포장재 회사에 실질적으로 도움이 되는 정보인지(실용성)를 각각 10점 만점으로 평가합니다.
- 두 점수의 평균을 내어 통합점수(0.5점 단위, 소수 첫째자리까지)를 산출합니다.
- 통합점수 기준으로 해당 기사의 '유효성'(유효/참고용/유효하지 않음)을 판단합니다.
- 최종 리턴은 반드시 "X.X점" 형식으로 시작하고, 그 다음 줄부터 해설을 작성하세요.
- 해설은 키워드 연관성, 실용성 평가를 포함하여 한줄로 요약하세요.

평가 기준은 다음과 같습니다:
- 키워드 연관성: 기사 요약이 키워드를 직접적으로, 깊이 있게 다루면 10점, 거의 무관하면 1점.
- 실용성: 기사 내용이 포장재 회사 실무에 직접적으로 도움이 되면 10점, 전혀 도움되지 않으면 1점.
- 통합점수 = (키워드 연관성 + 실용성) ÷ 2 (소수 첫째자리)
- 유효성: 통합점수 8점 이상=유효, 5~7.5점=참고용, 5점 미만=유효하지 않음.

---
키워드: {keyword}
기사 요약: {article_summary}
---"""
    
    data = {
        "messages": [
            {"role": "system", "content": "당신은 포장재 산업 전문 분석가입니다. 기사의 연관성과 실용성을 객관적으로 평가합니다."},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.3
    }
    
    try:
        data_str = json.dumps(data, ensure_ascii=False).encode("utf-8")
        response = requests.post(azure_endpoint, headers=headers, data=data_str)
        response.raise_for_status()
        result = response.json()
        evaluation = result["choices"][0]["message"]["content"].strip()
        
        # 점수와 해설 분리 - 여러 패턴 시도
        import re
        
        # 패턴 1: "X.X점" 형식으로 시작하는 경우
        score_match = re.match(r'^(\d+(\.\d+)?)[점점]\s*(.*)', evaluation, re.DOTALL)
        if score_match:
            score = float(score_match.group(1))
            explanation = score_match.group(3).strip()
            return score, explanation
            
        # 패턴 2: 숫자로 시작하고 줄바꿈이나 대시(—)로 구분된 경우
        score_match = re.match(r'^(\d+(\.\d+)?)\s*[\n\r—\-–]*\s*(.*)', evaluation, re.DOTALL)
        if score_match:
            score = float(score_match.group(1))
            explanation = score_match.group(3).strip()
            return score, explanation
        
        # 그 외의 경우: 첫 줄에서 숫자만 추출
        first_line = evaluation.split('\n', 1)[0].strip()
        score_match = re.search(r'(\d+(\.\d+)?)', first_line)
        if score_match:
            score = float(score_match.group(1))
            # 첫 줄을 제외한 나머지를 설명으로
            if '\n' in evaluation:
                explanation = evaluation.split('\n', 1)[1].strip()
            else:
                # 숫자 부분을 제외한 나머지를 설명으로
                explanation = first_line.replace(score_match.group(0), '').strip()
                if explanation.startswith('점'):
                    explanation = explanation[1:].strip()
            return score, explanation
            
        # 모든 시도 실패 시
        print(f"파싱 실패. 원본 응답: {evaluation}")
        return 0.0, evaluation
        
    except Exception as e:
        print("평가 중 오류 발생:", e)
        return 0.0, f"평가 오류 발생: {str(e)}"


# --------------------------------------------------------------------
# 이메일 발송 함수 (SMTP)
def send_email(subject, html_body, recipient, attachment_path=None):
    sender = sender_email
    email_pw = os.getenv("EMAIL_PASSWORD")
    if email_pw is None:
        print("EMAIL_PASSWORD 환경변수가 설정되어 있지 않습니다.")
        return False
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))
    if attachment_path is not None:
        from email.mime.base import MIMEBase
        from email import encoders
        try:
            with open(attachment_path, "rb") as attachment:
                part = MIMEBase("application", "pdf")
                part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{os.path.basename(attachment_path)}"')
            msg.attach(part)
        except Exception as e:
            print("첨부 파일 추가 중 오류 발생:", e)
            return False
    try:
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender, email_pw)
        server.sendmail(sender, recipient, msg.as_string())
        server.quit()
        print("이메일 발송 성공!")
        return True
    except Exception as e:
        print("이메일 발송 중 오류 발생:", e)
        return False

# --------------------------------------------------------------------
# 팝업 닫기 함수 (명시적 대기 추가)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def close_popups(driver):
    try:
        wait = WebDriverWait(driver, 5)
        popups = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".popup-close, .close-btn")))
        for popup in popups:
            try:
                popup.click()
                print("팝업 닫기 성공")
                time.sleep(0.5)
            except Exception as inner_e:
                print("팝업 클릭 실패:", inner_e)
                continue
    except Exception as e:
        print("팝업 요소 찾기 실패 또는 존재하지 않음:", e)
        pass

# --------------------------------------------------------------------
# Fallback: Selenium을 이용하여 페이지 소스에서 기사 제목/본문 추출 (메타 태그에서 날짜도 추출)
def get_article_text_with_selenium(driver, url):
    try:
        driver.set_page_load_timeout(20)
        driver.get(url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        close_popups(driver)

        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")
        selectors = get_candidate_selectors()

        # 1) 기본 제목 추출
        title_tag = soup.select_one(selectors["title"])
        title = title_tag.get_text(strip=True) if title_tag else "제목 없음"

        # 2) 제목 길이 체크 & 후보에서 재추출
        if title and len(title) > MAX_TITLE_LENGTH:
            print(f"[TitleFilter] 추출된 제목 길이 {len(title)}자 초과, 후보에서 재추출 시도")
            for sel, attr in TITLE_FALLBACK_SELECTORS:
                elem = soup.select_one(sel)
                if not elem:
                    continue
                candidate = elem.get(attr, "").strip() if attr else elem.get_text(strip=True)
                if candidate and len(candidate) <= MAX_TITLE_LENGTH:
                    title = candidate
                    print(f"[TitleFilter] 후보 '{sel}'에서 제목 재추출: {title}")
                    break
            else:
                print("[TitleFilter] 모든 후보 제목 길이 초과 또는 없음 → 제목 없음 처리")
                title = "제목 없음"

        # 3) 날짜 추출
        meta_date = None
        meta = soup.find("meta", {"property": "article:published_time"})
        if meta and meta.get("content"):
            meta_date = meta.get("content")
        if not meta_date:
            date_tag = soup.select_one(selectors["date"])
            if date_tag:
                meta_date = (
                    date_tag.get("datetime")
                    if date_tag.has_attr("datetime")
                    else date_tag.get_text(strip=True)
                )

        # 4) 본문 추출
        p_tags = soup.select(selectors["body"])
        if p_tags:
            paragraphs = [p.get_text(strip=True) for p in p_tags if p.get_text(strip=True)]
            content = "\n".join(paragraphs)
        else:
            content = "본문 없음"

        print("Selenium Fallback로 추출된 제목:", title)
        return title, content, meta_date

    except Exception as e:
        print("Selenium Fallback 추출 중 오류:", e)
        return "제목 없음", "본문 없음", None

# --------------------------------------------------------------------
# newspaper3k를 사용하여 기사 추출, 실패 시 Selenium Fallback 적용
def get_article_text(url, driver, method=None):
    """
    지정한 방법(method)이 있으면 해당 라이브러리로,
    없으면 newspaper3k, trafilatura, goose3, readability 순서로 시도하여 기사 제목, 본문, 날짜를 추출합니다.
    모두 실패하면 Selenium Fallback을 사용합니다.
    """
    # 초기 헤더 확인으로 403 빠르게 걸러내기
    try:
        head_response = requests.head(url, timeout=3)
        if head_response.status_code == 403:
            print(f"사이트 접근 거부(403): {url} - 추출 시도 건너뜀")
            return "제목 없음", "본문 없음", None
    except Exception:
        pass  # 헤더 확인 실패 시 계속 진행
    
    methods = ['newspaper3k', 'trafilatura', 'goose3', 'readability']
    if method:
        methods = [method]
    for m in methods:
        try:
            if m == 'newspaper3k':
                from newspaper import Article, Config
                config = Config()
                config.request_timeout = 10
                article = Article(url, language="en", config=config,
                                  browser_user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
                article.download()
                article.parse()
                title = article.title.strip() if article.title.strip() else "제목 없음"
                text = article.text.strip() if article.text.strip() else "본문 없음"
                publish_date = article.publish_date
                if not publish_date:
                    meta_date = get_article_date_from_meta(driver)
                    if meta_date:
                        publish_date = parse(meta_date)
                if title != "제목 없음" and text != "본문 없음":
                    print("newspaper3k로 추출 성공:", url)
                    return title, text, publish_date

            elif m == 'trafilatura':
                import trafilatura
                downloaded = trafilatura.fetch_url(url)
                if not downloaded:
                    raise Exception("Trafilatura 다운로드 실패")
                result = trafilatura.extract(downloaded, output_format='json', with_metadata=True)
                if not result:
                    raise Exception("Trafilatura 추출 실패")
                result_json = json.loads(result)
                title = result_json.get("title", "").strip() or "제목 없음"
                text = result_json.get("text", "").strip() or "본문 없음"
                publish_date = result_json.get("date")
                if publish_date:
                    try:
                        publish_date = parse(publish_date)
                    except Exception:
                        publish_date = None
                if title != "제목 없음" and text != "본문 없음":
                    print("Trafilatura로 추출 성공:", url)
                    return title, text, publish_date

            elif m == 'goose3':
                from goose3 import Goose
                g = Goose()
                article = g.extract(url=url)
                title = article.title.strip() if article.title else "제목 없음"
                text = article.cleaned_text.strip() if article.cleaned_text else "본문 없음"
                publish_date = article.publish_date  # goose3는 날짜 정보를 항상 제공하지 않음
                if title != "제목 없음" and text != "본문 없음":
                    print("Goose3로 추출 성공:", url)
                    return title, text, publish_date

            elif m == 'readability':
                response = requests.get(url, timeout=10)
                if response.status_code != 200:
                    raise Exception("HTTP error")
                from readability import Document
                doc = Document(response.text)
                title = doc.short_title().strip() or "제목 없음"
                # readability의 summary HTML을 BeautifulSoup으로 텍스트 추출
                soup = BeautifulSoup(doc.summary(), "html.parser")
                text = soup.get_text(separator="\n").strip() or "본문 없음"
                publish_date = None
                if title != "제목 없음" and text != "본문 없음":
                    print("readability-lxml로 추출 성공:", url)
                    return title, text, publish_date

        except Exception as e:
            print(f"{m} 추출 중 오류 또는 결과 부족: {e}")
            continue

    # 모든 방법 실패 시 Selenium Fallback 사용
    title, text, publish_date = get_article_text_with_selenium(driver, url)
    if title != "제목 없음" and text != "본문 없음":
        print("Selenium Fallback로 추출 성공:", url)
    return title, text, publish_date

# --------------------------------------------------------------------
# BeautifulSoup으로 Google News 검색 결과 파싱
def get_articles_from_page(html):
    articles = []
    soup = BeautifulSoup(html, "html.parser")
    containers = soup.find_all("div", class_="SoaBEf")
    for container in containers:
        a_tag = container.find("a", class_="WlydOe")
        url = a_tag.get("href") if a_tag else None
        title_tag = container.find("div", class_="n0jPhd")
        title = title_tag.get_text(strip=True) if title_tag else "제목 없음"
        snippet_tag = container.find("div", class_="GI74Re")
        snippet = snippet_tag.get_text(strip=True) if snippet_tag else "요약 없음"
        date_tag = container.find("div", class_="OSrXXb")
        date = date_tag.get_text(strip=True) if date_tag else "날짜 없음"
        if url:
            articles.append({
                "url": url,
                "title": title,
                "snippet": snippet,
                "date": date
            })
    return articles

def get_articles_from_google_news(driver, scrolls=3):
    for _ in range(scrolls):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
    html = driver.page_source
    return get_articles_from_page(html)

def get_newspaper_name(url):
    domain = urlparse(url).netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain

# --------------------------------------------------------------------
# 패키징 관련 키워드를 기사 내용에 따라 할당하는 함수
def assign_packaging_keywords(article):
    """
    기사 URL과 내용을 분석하여 적절한 패키지 산업 관련 키워드 할당
    
    Args:
        article (dict): 기사 정보를 담은 딕셔너리 (np_title, article_text, url 필드 포함)
        
    Returns:
        str: 패키징 산업 관련 키워드
    """
    # 기본 키워드 (fallback)
    domain = get_newspaper_name(article["url"])
    
    # 기사 제목과 내용
    title = article.get("np_title", "").lower()
    content = article.get("article_text", "").lower()
    
    # 키워드 맵핑 (영어 키워드: 패턴 리스트)
    keyword_mapping = {
        "Sustainable Packaging": ["sustainable", "eco", "green", "environment", "친환경"],
        "Biodegradable Materials": ["biodegradable", "compostable", "생분해", "분해성"],
        "Recycling Technology": ["recycl", "circular", "재활용", "순환"],
        "Smart Packaging": ["smart", "intelligent", "스마트", "인텔리전트"],
        "Food Packaging": ["food", "식품", "식료품"],
        "Beverage Packaging": ["beverage", "drink", "음료"],
        "E-commerce Packaging": ["e-commerce", "ecommerce", "online", "이커머스", "전자상거래"],
        "Digital Printing": ["digital print", "디지털 인쇄"],
        "Packaging Regulations": ["regulat", "compliance", "law", "규제", "법규"],
        "Packaging Market": ["market", "industry", "growth", "시장", "산업"],
        "Flexible Packaging": ["flexible", "flexpack", "플렉시블"],
        "Rigid Packaging": ["rigid", "hard", "경질"],
        "Packaging Innovation": ["innovation", "innovative", "new", "혁신"],
        "Plastic Packaging": ["plastic", "플라스틱"],
        "Paper Packaging": ["paper", "paperboard", "종이", "지류"],
        "Metal Packaging": ["metal", "can", "금속", "캔"],
        "Glass Packaging": ["glass", "bottle", "유리", "병"],
        "Packaging Machinery": ["machinery", "machine", "equipment", "기계", "장비"]
    }
    
    # 제목과 내용에서 키워드 패턴 검색 (최대 2000자 제한)
    text_to_search = (title + " " + content[:2000]).lower()
    
    # 패턴 매칭 수 기준 점수 계산
    keyword_scores = {}
    
    for keyword, patterns in keyword_mapping.items():
        score = 0
        for pattern in patterns:
            occurrences = text_to_search.count(pattern)
            if occurrences > 0:
                # 제목에 패턴이 있으면 가중치 부여
                if pattern in title:
                    score += occurrences * 3
                else:
                    score += occurrences
        
        if score > 0:
            keyword_scores[keyword] = score
    
    # 점수가 가장 높은 키워드 선택
    if keyword_scores:
        best_keyword = max(keyword_scores.items(), key=lambda x: x[1])[0]
        print(f"  -> 키워드 할당: '{best_keyword}' (패턴 매칭 기반)")
        return best_keyword
    
    # 매칭되는 패턴이 없는 경우 기본 키워드 반환
    print(f"  -> 기본 키워드 할당: 'Packaging Industry' (패턴 매칭 실패)")
    return "Packaging Industry"

# --------------------------------------------------------------------
# 필수 사이트 기사 처리 함수
def process_site_articles(driver, articles):
    valid_articles = []
    total_articles = len(articles)
    
    # 드라이버 재초기화 주기 설정
    RESET_INTERVAL = 3  # 3개 기사마다 드라이버 재시작
    
    for idx, article in enumerate(articles):
        try:
            print(f"사이트 기사 처리 진행: {idx+1} / {total_articles} - {article['url']}")
            
            # 주기적 드라이버 초기화
            if idx > 0 and idx % RESET_INTERVAL == 0:
                print(f"--- 드라이버 재초기화 ({idx}/{total_articles}) ---")
                # 기존 드라이버 종료
                try:
                    driver.quit()
                except Exception as e:
                    print(f"드라이버 종료 중 오류: {e}")
                
                # 메모리 정리
                import gc
                gc.collect()
                time.sleep(1)
                
                # 새 드라이버 생성
                driver = create_driver_debug()
                print("드라이버 재초기화 완료")
            
            # 기존 코드: 기사 내용 추출
            np_title, article_text, publish_date = get_article_text(article["url"], driver)
            if np_title == "제목 없음" or article_text == "본문 없음":
                print("추출 실패로 기사 제외:", article["url"])
                continue
                
            if article.get("is_must_visit"):
                if publish_date is None:
                    print("MUST VISIT 기사 날짜 정보 없음:", article["url"])
                    continue
                try:
                    pub_date_obj = parse(publish_date) if not hasattr(publish_date, "date") else publish_date
                except Exception as e:
                    print("날짜 파싱 오류:", article["url"], e)
                    continue
                today = dt.now(gettz("Asia/Seoul")).date()
                yesterday = today - timedelta(days=1)
                if pub_date_obj.date() != today and pub_date_obj.date() != yesterday:
                    print(f"MUST VISIT 기사 날짜가 오늘/어제가 아님: {article['url']} ({pub_date_obj.date()} != {today} 또는 {yesterday})")
                    continue
                article["date"] = pub_date_obj.strftime("%Y-%m-%d")
            else:
                if publish_date and hasattr(publish_date, "strftime"):
                    article["date"] = publish_date.strftime("%Y-%m-%d")
            article["np_title"] = np_title
            article["article_text"] = article_text
            
            # 기사 평가 추가 (필수 사이트는 필터링하지 않고 평가 점수만 추가)
            try:
                # 키워드가 없는 경우, 패키징 관련 키워드 자동 할당
                keyword = article.get('keyword', assign_packaging_keywords(article))
                
                # 요약이 너무 긴 경우 앞부분만 사용
                if len(article_text) > 3000:
                    article_summary = article_text[:3000] + "..."
                else:
                    article_summary = article_text
                    
                # 기사 평가 실행
                score, explanation = evaluate_article(keyword, article_summary)
                article['evaluation_score'] = score
                article['evaluation_explanation'] = explanation
                print(f"  -> 필수 사이트 기사 평가 결과: {score}점")
            except Exception as e:
                print(f"  -> 기사 평가 중 오류 발생: {e}")
                
            valid_articles.append(article)
            
        except Exception as e:
            print(f"기사 {idx+1} 처리 중 오류 발생: {e}")
            # 오류 발생 시 드라이버 재초기화
            try:
                driver.quit()
            except:
                pass
            driver = create_driver_debug()
            print("오류 후 드라이버 재초기화 완료")
    
    return valid_articles

# --------------------------------------------------------------------
# 키워드 기사 처리 함수
def process_keyword_articles(driver, articles):
    valid_articles = []
    total_articles = len(articles)
    
    # 드라이버 재초기화 주기 설정
    RESET_INTERVAL = 3  # 3개 기사마다 드라이버 재시작
    
    for idx, article in enumerate(articles):
        try:
            print(f"키워드 기사 처리 진행: {idx+1} / {total_articles} - {article['url']}")
            
            # 주기적 드라이버 초기화
            if idx > 0 and idx % RESET_INTERVAL == 0:
                print(f"--- 드라이버 재초기화 ({idx}/{total_articles}) ---")
                # 기존 드라이버 종료
                try:
                    driver.quit()
                except Exception as e:
                    print(f"드라이버 종료 중 오류: {e}")
                
                # 메모리 정리
                import gc
                gc.collect()
                time.sleep(1)
                
                # 새 드라이버 생성
                driver = create_driver_debug()
                print("드라이버 재초기화 완료")
            
            # 기존 코드: 기사 내용 추출
            np_title, article_text, publish_date = get_article_text(article["url"], driver)
            if np_title == "제목 없음" or article_text == "본문 없음":
                print("추출 실패로 기사 제외:", article["url"])
                continue
                
            if publish_date and hasattr(publish_date, "strftime"):
                article["date"] = publish_date.strftime("%Y-%m-%d")
                
            article["np_title"] = np_title
            article["article_text"] = article_text
            valid_articles.append(article)
            
        except Exception as e:
            print(f"기사 {idx+1} 처리 중 오류 발생: {e}")
            # 오류 발생 시 드라이버 재초기화
            try:
                driver.quit()
            except:
                pass
            driver = create_driver_debug()
            print("오류 후 드라이버 재초기화 완료")
    
    return valid_articles

# --------------------------------------------------------------------
# 기사를 평가 점수 기준으로 정렬하는 유틸리티 함수
def sort_articles_by_score(articles, reverse=True):
    """
    기사 목록을 평가 점수(evaluation_score) 기준으로 정렬합니다.
    
    Parameters:
    - articles: 기사 목록 (딕셔너리 리스트)
    - reverse: True이면 내림차순(높은 점수 → 낮은 점수), False이면 오름차순(낮은 점수 → 높은 점수)
    
    Returns:
    - 정렬된 기사 목록
    """
    sorted_articles = sorted(articles, key=lambda x: x.get('evaluation_score', 0.0), reverse=reverse)
    sort_direction = "내림차순" if reverse else "오름차순"
    print(f"기사 {len(sorted_articles)}개를 평가 점수 기준으로 {sort_direction} 정렬했습니다.")
    return sorted_articles

# --------------------------------------------------------------------
# 이메일 발송 및 PDF 생성 함수
def build_and_send_email(valid_articles):
    # 기사를 평가 점수 기준으로 내림차순 정렬
    valid_articles = sort_articles_by_score(valid_articles)
    
    html_parts = []
    html_parts.append('<div style="font-family: Roboto, Nanum Gothic, sans-serif; color: #333; line-height: 1.6;">')
    
    # 목차 추가 - 시작
    html_parts.append('<div style="margin-bottom: 30px; padding: 15px; background-color: #f5f5f5; border-radius: 8px;">')
    html_parts.append('<h2 style="margin-top: 0; border-bottom: 1px solid #ddd; padding-bottom: 10px;">기사 목차</h2>')
    html_parts.append('<ol style="margin: 0; padding-left: 20px;">')
    
    # 각 기사의 간략 정보를 목차에 추가
    for i, art in enumerate(valid_articles):
        title_display = art["np_title"]
        translated_title = translate_text(art["np_title"], mode="title") if len(title_display) > 50 else ""
        short_title = title_display[:50] + "..." if len(title_display) > 50 else title_display
        
        # 평가 점수가 있으면 표시
        score_display = f" - {art.get('evaluation_score', 0.0):.1f}점" if 'evaluation_score' in art else ""
        
        # 필수 사이트 여부 표시
        star_mark = "★ " if art.get("is_must_visit") else ""
        
        # 목차 항목 추가
        html_parts.append(f'<li><a href="#article-{i+1}" style="text-decoration: none; color: #1a73e8;">')
        html_parts.append(f'{star_mark}{short_title}{score_display}</a>')
        
        # 번역된 제목이 있으면 괄호 안에 추가 (선택적)
        if translated_title:
            short_translated = translated_title[:30] + "..." if len(translated_title) > 30 else translated_title
            html_parts.append(f' <small style="color: #666;">({short_translated})</small>')
            
        html_parts.append('</li>')
    
    html_parts.append('</ol>')
    html_parts.append('</div>')
    # 목차 추가 - 끝
    
    for i, art in enumerate(valid_articles):
        print(f"번역 요청 중: {art['np_title']} ({i+1}/{len(valid_articles)})")
        translated_title = translate_text(art["np_title"], mode="title")
        summary = translate_text(art["article_text"], mode="content")
        newspaper_name = get_newspaper_name(art["url"])
        title_display = art["np_title"]
        
        # 평가 점수와 설명이 있는 경우 추가
        evaluation_score = art.get('evaluation_score', None)
        evaluation_explanation = art.get('evaluation_explanation', None)
        
        # 기사 출처 정보 (키워드 또는 사이트)
        source_info = ""
        if art.get("is_must_visit"):
            source_info = f"<p style=\"margin: 3px 0;\"><strong>출처 사이트:</strong> {newspaper_name}</p>"
        else:
            keyword = art.get('keyword', '기타')
            source_info = f"<p style=\"margin: 3px 0;\"><strong>검색 키워드:</strong> {keyword}</p>"
        
        if art.get("is_must_visit"):
            title_display = f"★ {title_display} ★"
            
        # 기사 ID 추가하여 목차에서 링크 가능하게 함
        article_html = f"""
        <div id="article-{i+1}" style="margin-bottom: 20px;">
          <h2 style="margin: 0 0 5px 0;"><span style="color: #1a73e8; font-weight: bold; margin-right: 10px;">{i+1}.</span>{title_display}</h2>
          <h3 style="margin: 0 0 10px 0; color: #555;">{translated_title}</h3>
        """
        
        # 평가 점수가 있는 경우 추가 (타이틀 아래로 이동)
        if evaluation_score is not None:
            article_html += f"""
          <p style="margin: 3px 0;"><strong>GPT 연관성 평가 점수:</strong> {evaluation_score:.1f}점</p>
            """
            
        article_html += f"""
          <p style="margin: 3px 0;"><strong>업로드 시간:</strong> {art.get('date', '정보 없음')}</p>
          <p style="margin: 3px 0;"><strong>원문 URL:</strong> <a href="{art['url']}" style="color: #1a73e8; text-decoration: none;">{newspaper_name}</a></p>
          {source_info}
        </div>
        <div style="margin-bottom: 20px;">
          <p style="margin: 3px 0;"><strong>요약:</strong></p>
          <ul style="margin: 0 0 0 20px; padding: 0;">
        """
        summary_lines = [line.strip().lstrip('-') for line in summary.splitlines() if line.strip()]
        if summary_lines:
            li_items = "".join(f"<li>{l}</li>" for l in summary_lines)
        else:
            li_items = "<li>요약 내용 없음</li>"
        article_html += li_items
        article_html += """
          </ul>
        </div>
        """
        
        # 평가 설명이 있는 경우 추가 (요약 다음으로 이동)
        if evaluation_explanation:
            article_html += f"""
        <div style="margin-bottom: 20px;">
          <p style="margin: 3px 0;"><strong>평가 내용:</strong></p>
          <ul style="margin: 0 0 0 20px; padding: 0;">
        """
            evaluation_lines = [line.strip() for line in evaluation_explanation.splitlines() if line.strip()]
            if evaluation_lines:
                eval_items = "".join(f"<li>{l}</li>" for l in evaluation_lines)
                article_html += eval_items
            else:
                article_html += f"<li>{evaluation_explanation}</li>"
            
            article_html += """
          </ul>
        </div>
            """
        
        article_html += """
        <hr style="border: none; border-top: 2px dashed #888; margin: 30px 0;">
        """
        html_parts.append(article_html)
    html_parts.append("</div>")
    html_body_content = "".join(html_parts)
    
    date_str = dt.now(gettz("Asia/Seoul")).strftime("%y/%m/%d")
    subject = f"[{date_str}] Packaging 뉴스 기사 번역 및 요약 ({len(valid_articles)}개)"
    html_template = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>{subject}</title>
  <style>
    body {{
      font-family: Roboto, Nanum Gothic, sans-serif;
      color: #333;
      line-height: 1.6;
      margin: 20px;
    }}
    h1 {{
      text-align: left;
      margin-top: 20px;
    }}
    h2 {{
      margin: 0 0 5px 0;
    }}
    h3 {{
      margin: 0 0 10px 0;
      color: #555;
    }}
    p {{
      margin: 3px 0;
    }}
    a {{
      color: #1a73e8;
      text-decoration: none;
    }}
    hr {{
      border: none;
      border-top: 2px dashed #888;
      margin: 30px 0;
    }}
    ul {{
      margin: 0 0 0 20px;
      padding: 0;
    }}
    .toc {{
      background-color: #f5f5f5;
      border-radius: 8px;
      padding: 15px;
      margin-bottom: 30px;
    }}
    .toc h2 {{
      border-bottom: 1px solid #ddd;
      padding-bottom: 10px;
      margin-top: 0;
    }}
    .toc ol {{
      margin: 0;
      padding-left: 20px;
    }}
    .toc a {{
      text-decoration: none;
    }}
    .article-number {{
      color: #1a73e8;
      font-weight: bold;
      margin-right: 10px;
    }}
  </style>
</head>
<body>
  <h1>{subject}</h1>
  {html_body_content}
</body>
</html>"""
    
    safe_date_str = dt.now(gettz("Asia/Seoul")).strftime("%y_%m_%d")
    pdf_filename = f"[{safe_date_str}] Packaging 뉴스 기사 번역 및 요약 ({len(valid_articles)}개).pdf"
    try:
        HTML(string=html_template).write_pdf(pdf_filename)
        print("PDF 파일 생성 완료 (WeasyPrint 사용).")
    except Exception as e:
        print("PDF 생성 중 오류 발생:", e)
        pdf_filename = None
    
    recipient = os.environ.get("EMAIL_RECIPIENT", "cbj6214@dongwon.com")
    
    email_success = send_email(subject, html_template, recipient, attachment_path=pdf_filename)
    if email_success:
        print(f"이메일 발송 성공: 총 {len(valid_articles)}개 기사 발송됨.")
    else:
        print("이메일 발송 실패.")
    
    if email_success and pdf_filename and os.path.exists(pdf_filename):
        os.remove(pdf_filename)
        print("PDF 파일 삭제 완료.")
    else:
        print("이메일 발송 오류로 PDF 파일을 삭제하지 않음.")


# 평가 점수에 따른 기사 필터링 함수 추가
def filter_articles_by_evaluation(articles, min_score=None, total_limit=None):
    """
    기사를 평가하여 점수 기준 이상인 기사만 필터링하는 함수
    
    Parameters:
    - articles: 기사 목록 (딕셔너리 리스트)
    - min_score: 최소 점수 기준 (기본값: 환경변수 또는 5.0)
    - total_limit: 반환할 최대 기사 수 (기본값: 환경변수 또는 30)
    
    Returns:
    - 평가 점수가 min_score 이상인 기사 목록 (점수 내림차순 정렬)
    """
    # 환경 변수 또는 기본값 사용
    if min_score is None:
        min_score = MIN_SCORE
    
    if total_limit is None:
        total_limit = ARTICLE_LIMIT
    
    # 평가 결과를 저장할 리스트
    evaluated_articles = []
    
    # API 호출 관련 변수 설정
    API_RETRY_COUNT = 3
    API_RETRY_DELAY = 2
    
    print(f"\n[기사 평가] 총 {len(articles)}개 기사 평가 시작 (최소 점수: {min_score}, 최대 기사 수: {total_limit})")
    
    # 각 기사에 대해 평가 수행
    for idx, article in enumerate(articles):
        keyword = article.get('keyword', assign_packaging_keywords(article))
        title = article.get('np_title', '제목 없음')
        print(f"\n[평가 진행] {idx+1}/{len(articles)} - 키워드: {keyword}, 제목: {title}")
        
        # 메모리 사용량 로깅 (선택사항)
        log_memory_usage(f"기사 평가 {idx+1} 전")
        
        # 기사 요약 추출
        article_text = article.get('article_text', '')
        
        # 기사가 없는 경우 건너뛰기
        if article_text == '본문 없음' or not article_text:
            print("  -> 기사 본문이 없어 평가 제외")
            continue
            
        # 요약이 너무 긴 경우 앞부분만 사용
        if len(article_text) > 3000:
            article_summary = article_text[:3000] + "..."
        else:
            article_summary = article_text
        
        # 키워드 저장
        article['keyword'] = keyword
            
        # 기사 평가 실행 (재시도 로직 추가)
        for attempt in range(API_RETRY_COUNT):
            try:
                start_time = time.time()
                score, explanation = evaluate_article(keyword, article_summary)
                elapsed = time.time() - start_time
                print(f"  -> API 응답 시간: {elapsed:.2f}초")
                
                article['evaluation_score'] = score
                article['evaluation_explanation'] = explanation
                
                print(f"  -> 평가 결과: {score}점 ({explanation[:30] if explanation else '설명 없음'}...)")
                
                # 최소 점수 이상인 경우 목록에 추가
                if score >= min_score:
                    evaluated_articles.append(article)
                    print(f"  -> 평가 통과: {score}점")
                else:
                    print(f"  -> 평가 미달: {score}점 (기준: {min_score}점)")
                
                # 성공 시 재시도 루프 종료
                break
                
            except Exception as e:
                print(f"  -> 평가 시도 {attempt+1}/{API_RETRY_COUNT} 중 오류: {e}")
                if attempt < API_RETRY_COUNT - 1:
                    retry_delay = API_RETRY_DELAY * (attempt + 1)
                    print(f"  -> {retry_delay}초 후 재시도...")
                    time.sleep(retry_delay)
                else:
                    print(f"  -> 모든 재시도 실패, 기사 평가 건너뛰기")
                    
        # 메모리 사용량 로깅 (선택사항)
        log_memory_usage(f"기사 평가 {idx+1} 후")
        
        # 주기적 메모리 정리
        if idx > 0 and idx % 10 == 0:
            print(f"--- 메모리 정리 중 ({idx}/{len(articles)}) ---")
            import gc
            gc.collect()
    
    # 평가 점수 기준으로 내림차순 정렬
    evaluated_articles = sort_articles_by_score(evaluated_articles)
    
    # 총 제한 개수 적용
    if len(evaluated_articles) > total_limit:
        print(f"\n평가 통과 기사 {len(evaluated_articles)}개 중 상위 {total_limit}개만 선택")
        evaluated_articles = evaluated_articles[:total_limit]
    else:
        print(f"\n평가 통과 기사: 총 {len(evaluated_articles)}개")
    
    # 각 기사의 최종 평가 결과 출력
    for idx, article in enumerate(evaluated_articles):
        keyword = article.get('keyword', '기타')
        title = article.get('np_title', '제목 없음')
        score = article.get('evaluation_score', 0.0)
        print(f"{idx+1}. [{keyword}] {title} - {score}점")
    
    return evaluated_articles

# 메모리 사용량 모니터링 함수 추가
def log_memory_usage(label=""):
    """
    현재 프로세스의 메모리 사용량을 로깅하는 함수
    """
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        print(f"[메모리] {label}: {memory_info.rss / (1024 * 1024):.2f} MB")
    except ImportError:
        print("[메모리] psutil 라이브러리가 설치되지 않았습니다.")
    except Exception as e:
        print(f"[메모리] 측정 오류: {e}")

# 수정된 scrape_keyword_search_articles 함수
def scrape_keyword_search_articles(driver):
    collected_articles = []
    
    # 어제 날짜 문자열 계산 (예: "4/4/2025")
    yesterday_str = get_yesterday_date_string()

    # 구글 뉴스 검색 URL 템플릿
    GOOGLE_NEWS_URL = (
        "https://www.google.com/search"
        "?q={query}"
        "&tbm=nws"
        "&tbs=sbd:1,"         # 날짜순 정렬
        f"cdr:1,cd_min:{yesterday_str},cd_max:{yesterday_str}"  # 시작/종료 날짜 모두 어제로
        "&hl=en"
        "&gl=us"
    )
    
    # 디버그 모드 여부에 따른 키워드 설정
    if DEBUG_MODE:
        keywords = [
            "Beer Market", "Soju Market", "Korean rice wine Market", "Beverage Market",
            "Bottled Water Company", "Carbonated Beverage", "Sparkling Water", 
            "Children Beverage", "Sports Drink", "RTD Coffee", "Engery Drink",
            "Health Tonic", "Aseptic", "RTD Beverage", "Hangover Cure"
        ]
    else:
        keywords = [
            "Beer Market", "Soju Market", "Korean rice wine Market", "Beverage Market",
            "Bottled Water Company", "Carbonated Beverage", "Sparkling Water", 
            "Children Beverage", "Sports Drink", "RTD Coffee", "Engery Drink",
            "Health Tonic", "Aseptic", "RTD Beverage", "Hangover Cure"
        ]
    
    excluded_domains = [
        "chosun.com", "koreatimes.co.kr", "mk.co.kr",
        "koreaherald.com", "koreajoongangdaily.joins.com", "businesskorea.co.kr"
    ]
    
    total_articles_found = 0
    total_excluded = 0
    max_pages = 99  # 페이지 최대 수 (무한 스크롤 방지)

    # --- 1. 구글 뉴스 검색 결과 수집 ---
    for keyword in keywords:
        print(f"\n[키워드: {keyword}] 검색 시작")
        try:
            driver.get(GOOGLE_NEWS_URL.format(query=keyword))
        except Exception as e:
            print("  -> 키워드 검색 페이지 접근 실패:", e)
            continue
        
        current_page = 1
        while True:
            time.sleep(1)  # 줄인 대기 시간
            for _ in range(2):  # 반복 횟수를 줄여서 불필요한 대기 제거
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(0.5)  # 스크롤 후 대기

            html = driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            containers = soup.find_all("div", class_="SoaBEf")
            
            keyword_found = 0
            keyword_collected = 0
            keyword_excluded = 0
            
            for container in containers:
                a_tag = container.find("a", class_="WlydOe")
                url = a_tag.get("href") if a_tag else None
                title_tag = container.find("div", class_="n0jPhd")
                title = title_tag.get_text(strip=True) if title_tag else "제목 없음"
                snippet_tag = container.find("div", class_="GI74Re")
                snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
                date_tag = container.find("div", class_="OSrXXb")
                date = date_tag.get_text(strip=True) if date_tag else ""
                
                keyword_found += 1
                if url:
                    domain = urlparse(url).netloc.lower()
                    # 제외 도메인 체크
                    if any(excl in domain for excl in excluded_domains):
                        keyword_excluded += 1
                        continue
                    collected_articles.append({
                        "url": url,
                        "title": title,
                        "snippet": snippet,
                        "date": date,
                        "keyword": keyword
                    })
                    keyword_collected += 1
            
            total_articles_found += keyword_found
            total_excluded += keyword_excluded
            
            print(f"  -> [페이지 {current_page}] 결과 {keyword_found}개 중 {keyword_excluded}개 제외, {keyword_collected}개 수집")
            
            if current_page >= max_pages:
                print(f"  -> 최대 페이지({max_pages}) 도달. 다음 페이지 탐색 중지")
                break
            
            # 다음 페이지 버튼(Next) 클릭 시도
            try:
                next_btn = driver.find_element(By.XPATH, "//span[@class='oeN89d' and text()='Next']")
                if next_btn.is_displayed() and next_btn.is_enabled():
                    driver.execute_script("arguments[0].click();", next_btn)
                    current_page += 1
                    time.sleep(2)
                else:
                    print("  -> Next 버튼이 비활성화되어 있음. 페이지 탐색 중지")
                    break
            except Exception:
                print("  -> Next 버튼을 찾지 못함. 페이지 탐색 중지")
                break

    print(f"\nGoogle 뉴스: 총 {total_articles_found}개 기사 중 {total_excluded}개 제외됨.")
    
    # 중복 제거 (URL 기준)
    unique_articles = {}
    for article in collected_articles:
        url = article.get("url")
        if url and url not in unique_articles:
            unique_articles[url] = article
        else:
            if url:
                print(f"중복 기사 제거: {url}")
    articles = list(unique_articles.values())

    # 환경 변수에서 키워드당 최대 기사 수 가져오기
    per_keyword_limit = int(os.environ.get("PER_KEYWORD_LIMIT", "10"))
    articles = balance_articles_by_keyword(articles, ARTICLE_LIMIT, per_keyword_limit)

    # --- 2. 각 기사에서 실제 기사 내용 추출 (newspaper3k + Selenium Fallback) ---
    valid_articles = []
    for art in articles:
        print(f"\n[기사 추출 시도] URL: {art['url']}")
        # newspaper3k를 사용하여 기사 내용 추출, 실패 시 Selenium Fallback 적용
        np_title, article_text, publish_date = get_article_text(art["url"], driver)
        if np_title == "제목 없음" or article_text == "본문 없음":
            print("  -> 기사 추출 실패 (newspaper3k 및 Selenium fallback 모두 실패):", art["url"])
            continue
        
        art["np_title"] = np_title
        art["article_text"] = article_text
        # 날짜 정보가 추출되었으면 문자열로 저장
        if publish_date and hasattr(publish_date, "strftime"):
            art["date"] = publish_date.strftime("%Y-%m-%d")
        
        # 추가적으로 기사 페이지의 HTML 전체를 가져와 최상위 태그와 <body> 내부 태그로 분할 (선택사항)
        try:
            driver.set_page_load_timeout(20)
            driver.get(art["url"])
            time.sleep(3)  # 페이지 로딩 대기
            full_html = driver.page_source
            # 전체 HTML을 "html" 키에 저장
            art["html"] = full_html
            art["html_top"] = split_html_into_top_level_tags(full_html)
            art["html_body"] = split_body_html_into_tags(full_html)
        except Exception as e:
            print(f"  -> 기사 HTML 수집 중 오류 ({art['url']}):", e)
            art["html_top"] = []
            art["html_body"] = []
            art["html"] = ""
        
        valid_articles.append(art)
    
    # 기사 평가 및 점수 기준 필터링 (환경 변수에서 가져온 값 사용)
    evaluated_articles = filter_articles_by_evaluation(valid_articles)
    
    return evaluated_articles

def balance_articles_by_keyword(articles, total_limit=None, per_keyword_limit=None):
    """
    기사 목록을 키워드별로 균등하게 배분하면서 전체 개수를 제한하는 함수
    
    Parameters:
    - articles: 기사 목록 (딕셔너리 리스트)
    - total_limit: 반환할 최대 기사 수 (기본값: 환경변수 또는 30)
    - per_keyword_limit: 키워드당 최대 기사 수 (기본값: None, 자동 계산)
    
    Returns:
    - 키워드별로 균등하게 배분된 기사 목록
    """
    # 환경 변수 또는 기본값 사용
    if total_limit is None:
        total_limit = ARTICLE_LIMIT
    
    # 키워드별로 기사 그룹화
    keyword_groups = {}
    for article in articles:
        keyword = article.get('keyword', '기타')
        if keyword not in keyword_groups:
            keyword_groups[keyword] = []
        keyword_groups[keyword].append(article)
    
    # 각 키워드별 기사 수를 균등하게 계산
    keyword_count = len(keyword_groups)
    if keyword_count == 0:
        return []
    
    # per_keyword_limit이 지정되지 않은 경우 자동 계산
    if per_keyword_limit is None:
        per_keyword_limit = max(1, total_limit // keyword_count)
    
    # 결과 리스트 준비
    balanced_articles = []
    
    # 각 키워드 그룹에서 기사 선택
    for keyword, group in keyword_groups.items():
        # 최신 기사 우선 선택 (날짜 정보가 있다면 정렬)
        selected_articles = group[:per_keyword_limit]
        balanced_articles.extend(selected_articles)
        print(f"키워드 '{keyword}': 전체 {len(group)}개 중 {len(selected_articles)}개 선택")
    
    # 전체 제한 개수를 초과하는 경우 잘라내기
    if len(balanced_articles) > total_limit:
        print(f"전체 {len(balanced_articles)}개 기사 중 {total_limit}개로 제한합니다.")
        balanced_articles = balanced_articles[:total_limit]
    
    return balanced_articles

def get_yesterday_date_string():
    """
    한국 시간(Asia/Seoul) 기준 어제 날짜를 계산하여,
    DEBUG_MODE가 True이면 Windows 스타일(예: 4/3/2025)로,
    False이면 Linux 스타일(예: 4/3/2025)로 포맷팅하여 반환합니다.
    """
    DEBUG_MODE = os.getenv("DEBUG_MODE", "true").lower() == "true"
    yesterday = datetime.now(gettz("Asia/Seoul")) - timedelta(days=1)
    if DEBUG_MODE:
        # Windows에서는 %#m, %#d 사용 (앞의 0 제거)
        return yesterday.strftime("%#m/%#d/%Y")
    else:
        # Linux에서는 %-m, %-d 사용 (앞의 0 제거)
        return yesterday.strftime("%-m/%-d/%Y")
    

def write_to_spreadsheet(articles):
    """
    각 기사에 대해 "성공여부", "신문사", "제목", "링크" 뒤에,
    평탄화된 HTML 태그(최상위 및 모든 자식 태그)를 별도의 셀에 입력합니다.
    기사는 평가 점수 기준으로 내림차순 정렬됩니다.
    최대 100개의 태그 열을 생성하며, 셀 당 최대 50,000자까지 저장합니다.
    """
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    home_dir = os.path.expanduser("~")
    cred_path = os.path.join(home_dir, "API", "demianlee-c18e8f2ad88f.json")
    creds = Credentials.from_service_account_file(cred_path, scopes=scope)
    client = gspread.authorize(creds)
    spreadsheet_name = "[RPA]news_scrapping_database"
    sheet = client.open(spreadsheet_name).worksheet("List")
    
    # 기사를 평가 점수 기준으로 내림차순 정렬
    articles = sort_articles_by_score(articles)
    
    # 헤더: 기본 4개 열 + 최대 100개의 태그 열
    header = ["성공여부", "신문사", "제목", "링크"]
    for i in range(1, 101):
        header.append(f"태그{i}")
    sheet.append_row(header)
    
    MAX_CELL_LEN = 50000  # 셀당 최대 문자 수
    max_tag_columns = 100
    
    for art in articles:
        domain = get_newspaper_name(art["url"])
        title = art.get("np_title", "제목 없음")
        link = art.get("url", "")
        success_status = (
            "성공"
            if art.get("np_title", "제목 없음") != "제목 없음" and art.get("article_text", "본문 없음") != "본문 없음"
            else "실패"
        )
        
        # art["html"]에 전체 HTML이 저장되어 있다고 가정하고, 평탄화된 태그 리스트 생성
        full_html = art.get("html", "")
        flat_tags = flatten_html_tags(full_html) if full_html else []
        
        # 각 태그 셀의 길이를 체크하여, MAX_CELL_LEN 초과 시 잘라내기
        adjusted_tags = []
        for tag in flat_tags:
            if len(tag) > MAX_CELL_LEN:
                tag = tag[:MAX_CELL_LEN] + "\n...[truncated]"
            adjusted_tags.append(tag)
        
        # 최대 100개 열로 맞추기: 부족하면 빈 문자열 추가, 초과하면 처음 100개만 사용
        if len(adjusted_tags) < max_tag_columns:
            adjusted_tags.extend([""] * (max_tag_columns - len(adjusted_tags)))
        else:
            adjusted_tags = adjusted_tags[:max_tag_columns]
        
        row = [success_status, domain, title, link] + adjusted_tags
        sheet.append_row(row)
        print(f"새 데이터 추가: {row}")

        # ---------------------------

# CSV로 저장하는 함수
def write_to_csv(articles, filepath=None):
    """
    크롤링된 기사 데이터를 CSV 파일로 저장합니다.
    기사는 평가 점수 기준으로 내림차순 정렬됩니다.
    
    Parameters:
    - articles: 기사 목록 (딕셔너리 리스트)
    - filepath: 저장할 CSV 파일 경로 (기본값: 현재 디렉토리에 날짜_시간 기준 파일명)
    
    Returns:
    - 성공 시 True, 실패 시 False
    """
    import csv
    import os
    from datetime import datetime
    
    try:
        # 기사를 평가 점수 기준으로 내림차순 정렬
        articles = sort_articles_by_score(articles)
        
        # 파일명이 지정되지 않은 경우 현재 날짜와 시간으로 파일명 생성
        if filepath is None:
            now = datetime.now().strftime("%y%m%d_%H%M%S")
            filepath = f"news_articles_{now}.csv"
        
        # CSV 파일 열기 (한글 인코딩을 위해 UTF-8 BOM 사용)
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
            # 헤더 설정 (기존 write_to_spreadsheet와 동일)
            header = ["성공여부", "신문사", "제목", "링크", "번역된 제목", "날짜", "요약"]
            writer = csv.writer(csvfile)
            writer.writerow(header)
            
            # 각 기사 데이터 쓰기
            for article in articles:
                # 기본 정보 추출
                domain = get_newspaper_name(article.get("url", ""))
                title = article.get("np_title", "제목 없음")
                link = article.get("url", "")
                date = article.get("date", "날짜 없음")
                
                # 번역된 제목과 요약 가져오기 (있을 경우)
                translated_title = article.get("translated_title", "")
                summary = article.get("summary", "")
                
                # 성공 여부 판단
                success_status = (
                    "성공"
                    if title != "제목 없음" and article.get("article_text", "본문 없음") != "본문 없음"
                    else "실패"
                )
                
                # 요약이 여러 줄인 경우 단일 텍스트로 변환
                if isinstance(summary, list):
                    summary = " | ".join(summary)
                
                # CSV 행 작성
                row = [success_status, domain, title, link, translated_title, date, summary]
                writer.writerow(row)
                
            print(f"CSV 파일이 성공적으로 저장되었습니다: {filepath}")
            return True
            
    except Exception as e:
        print(f"CSV 파일 저장 중 오류 발생: {e}")
        return False
    

# 1. HTML 전체의 최상위 태그 단위로 분할하는 함수
def split_html_into_top_level_tags(html_str):
    """
    주어진 HTML 문자열을 파싱하여 최상위 태그 단위로 분할합니다.
    예를 들어, HTML 문서가 하나의 <html> 태그로 감싸져 있다면, 
    그 태그 전체가 리스트의 유일한 요소로 반환됩니다.
    
    만약 여러 최상위 태그가 있다면, 각 태그의 HTML 문자열이 리스트로 반환됩니다.
    
    반환 예시:
      [ '<html lang="en"><head>...</head><body>...</body></html>' ]
    """
    soup = BeautifulSoup(html_str, "html.parser")
    chunks = []
    for child in soup.contents:
        if getattr(child, "name", None):  # 태그인 경우만 선택
            chunks.append(str(child))
    return chunks

# ---------------------------
# 2. <body> 내부의 태그들을 분할하는 함수
def split_body_html_into_tags(html_str):
    """
    주어진 HTML 문자열에서 <body> 태그 내부의 최상위 자식 태그들을 분할합니다.
    예를 들어, <body> 내부에 <div>, <p>, <section> 등 여러 태그가 있다면,
    각 태그의 HTML 문자열을 리스트로 반환합니다.
    
    반환 예시:
      [ '<div id="content">...</div>', '<section>...</section>', ... ]
    """
    soup = BeautifulSoup(html_str, "html.parser")
    body = soup.body
    if body:
        chunks = []
        for child in body.contents:
            if getattr(child, "name", None):  # 태그인 경우만 선택
                chunks.append(str(child))
        return chunks
    else:
        return []
    

def flatten_html_tags(html_str):
    """
    주어진 HTML 문자열을 파싱하여, 최상위 태그부터 모든 자식 태그까지 재귀적으로 추출하여 평탄한 리스트로 반환합니다.
    """
    soup = BeautifulSoup(html_str, "html.parser")
    flat_tags = []
    
    def recursive_extract(tag):
        # 자식 태그를 재귀적으로 추출
        for child in tag.find_all(recursive=False):
            flat_tags.append(str(child))
            recursive_extract(child)
    
    # 최상위 태그들에 대해 재귀 처리
    for top in soup.find_all(recursive=False):
        flat_tags.append(str(top))
        recursive_extract(top)
    
    return flat_tags