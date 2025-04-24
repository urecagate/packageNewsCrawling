import time
import re
from selenium.webdriver.common.by import By
from dateutil.parser import parse as date_parse
from datetime import timedelta
from utils import dt, gettz

def safe_close_popups(driver):
    try:
        from utils import close_popups
        close_popups(driver)
    except Exception as e:
        print("safe_close_popups: 팝업 처리 오류(무시):", e)

def scrape_site7(driver):
    articles = []
    base_url = "https://packagingeurope.com/sections/news"
    try:
        driver.get(base_url)
        time.sleep(3)
        safe_close_popups(driver)
    except Exception as e:
        print("scrape_site7 - base URL 접근 실패:", e)
        return articles

    # 1. "Latest News" 섹션에서 후보 기사 수집
    candidates = []
    try:
        # "Latest News" 영역은 id "_222"와 클래스 "gridLayout hastitle"를 가집니다.
        news_container = driver.find_element(By.CSS_SELECTOR, "div#_222.gridLayout.hastitle")
        li_elements = news_container.find_elements(By.CSS_SELECTOR, "ul li")
        print(f"scrape_site7 - Latest News li 요소 개수: {len(li_elements)}개")
        
        for idx, li in enumerate(li_elements):
            try:
                # 제목 링크 요소가 반드시 있어야 함 (날짜 정보는 없음)
                link_elems = li.find_elements(By.CSS_SELECTOR, "div.subSleeve h2 a")
                if not link_elems:
                    # 해당 li 요소에 제목 링크가 없으면 건너뜁니다.
                    continue
                link_elem = link_elems[0]
                article_url = link_elem.get_attribute("href")
                article_title = link_elem.text.strip()
                candidates.append({
                    "url": article_url,
                    "title": article_title,
                    "type": "list"
                })
                print(f"scrape_site7 - 후보 기사 [{len(candidates)}] 수집 성공: {article_url}")
            except Exception as e:
                print(f"scrape_site7 - 후보 기사 정보 추출 실패 (idx {idx+1}):", e)
    except Exception as e:
        print("scrape_site7 - 후보 기사 수집 실패:", e)

    print(f"scrape_site7 - 총 후보 기사 수: {len(candidates)}개")

    # 2. FIFO 전략: 후보 기사를 순서대로 개별 페이지로 들어가 날짜를 확인
    # (목록에 날짜 정보가 없으므로 개별 기사에서 날짜 추출)
    today = dt.now(gettz("Asia/Seoul")).date()
    yesterday = today - timedelta(days=1)
    valid_candidates = []
    for idx, cand in enumerate(candidates):
        try:
            driver.get(cand["url"])
            time.sleep(3)
            safe_close_popups(driver)
            # 개별 페이지에서 날짜 추출 (예: "p.byline.meta span.date")
            date_elem = driver.find_element(By.CSS_SELECTOR, "p.byline.meta span.date")
            date_text = date_elem.text.strip()
            # 서수(예: "2nd") 제거: "2nd April, 2025" → "2 April, 2025"
            clean_date_text = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_text)
            pub_date = date_parse(clean_date_text, fuzzy=True).date()
            if pub_date == today or pub_date == yesterday:
                cand["date_text"] = date_text
                valid_candidates.append(cand)
                print(f"scrape_site7 - FIFO: 후보 {idx+1} 날짜 일치 ({pub_date})")
            else:
                print(f"scrape_site7 - FIFO 종료: 후보 {idx+1}의 날짜 {pub_date} != 오늘 {today} 또는 어제 {yesterday}")
                break  # 오늘/어제 날짜가 아닌 후보가 나오면 더 이상 처리하지 않음.
        except Exception as e:
            print("scrape_site7 - 날짜 추출 실패:", cand["url"], e)
            continue

    print(f"scrape_site7 - 오늘/어제 날짜 기사 후보 수: {len(valid_candidates)}개")

    # 3. 오늘/어제 날짜 후보들에 대해 개별 페이지에서 제목과 본문 재추출
    total_valid = len(valid_candidates)
    for idx, cand in enumerate(valid_candidates):
        try:
            print(f"scrape_site7 - 기사 추출 진행: {idx+1}/{total_valid} - {cand['url']}")
            driver.get(cand["url"])
            time.sleep(3)
            safe_close_popups(driver)
            try:
                title_elem = driver.find_element(By.CSS_SELECTOR, "div.story_title h1")
                article_title = title_elem.text.strip()
            except Exception as e:
                print("scrape_site7 - 개별 기사 제목 추출 실패:", e)
                article_title = cand["title"]
            try:
                content_elem = driver.find_element(By.CSS_SELECTOR, "div.storytext")
                full_text = content_elem.text.strip()
            except Exception as e:
                print("scrape_site7 - 개별 기사 본문 추출 실패:", e)
                full_text = ""
            articles.append({
                "title": article_title,
                "url": cand["url"],
                "date": cand["date_text"],
                "body": full_text
            })
        except Exception as e:
            print("scrape_site7 - 개별 기사 추출 실패:", e)
        try:
            driver.back()
            time.sleep(2)
        except Exception as e:
            print("scrape_site7 - driver.back() 실패:", e)

    # print(f"scrape_site7 기사 수집 완료: {len(articles)}개") main 함수에서 출력하므로 주석 처리
    return articles
