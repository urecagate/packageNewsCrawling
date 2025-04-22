import time
import re
from selenium.webdriver.common.by import By
from utils import close_popups
from dateutil.parser import parse as date_parse
from datetime import datetime
from utils import dt, gettz

def scrape_site1(driver):
    articles = []
    base_url = "https://www.glass-international.com/news"
    try:
        driver.get(base_url)
        time.sleep(2)
        close_popups(driver)
    except Exception as e:
        print("scrape_site1 - base URL 접근 실패:", e)
        return articles

    candidates = []

    # 1. 그리드 기사 후보 수집 (페이지 상단)
    try:
        grid_elements = driver.find_elements(By.CSS_SELECTOR, "div.w-full.md\\:w-1\\/3.flex.flex-col.px-3.mb-4")
        print(f"scrape_site1 - 그리드 기사 개수: {len(grid_elements)}")
        for elem in grid_elements:
            try:
                url_elem = elem.find_element(By.CSS_SELECTOR, "a.no-underline")
                article_url = url_elem.get_attribute("href")
                title_elem = elem.find_element(By.CSS_SELECTOR, "h4.mb-1 a.no-underline")
                article_title = title_elem.text.strip()
                date_elem = elem.find_element(By.CSS_SELECTOR, "div.text-gray-500.text-xs span")
                date_text = date_elem.text.strip()
                candidates.append({
                    "url": article_url,
                    "title": article_title,
                    "date_text": date_text,
                    "type": "grid"
                })
            except Exception as e:
                print("scrape_site1 - 그리드 기사 정보 추출 실패:", e)
    except Exception as e:
        print("scrape_site1 - 그리드 기사 요소 찾기 실패:", e)

    # 2. 리스트형 기사 후보 수집 (페이지 하단)
    try:
        list_elements = driver.find_elements(By.CSS_SELECTOR, "li.flex.mb-6")
        print(f"scrape_site1 - 리스트 기사 개수: {len(list_elements)}")
        for elem in list_elements:
            try:
                url_elem = elem.find_element(By.CSS_SELECTOR, "a.block")
                article_url = url_elem.get_attribute("href")
                title_elem = elem.find_element(By.CSS_SELECTOR, "h4")
                article_title = title_elem.text.strip()
                date_elem = elem.find_element(By.CSS_SELECTOR, "div.text-gray-500.text-xs span")
                date_text = date_elem.text.strip()
                candidates.append({
                    "url": article_url,
                    "title": article_title,
                    "date_text": date_text,
                    "type": "list"
                })
            except Exception as e:
                print("scrape_site1 - 리스트 기사 정보 추출 실패:", e)
    except Exception as e:
        print("scrape_site1 - 리스트 기사 요소 찾기 실패:", e)

    print(f"scrape_site1 - 총 후보 기사 수: {len(candidates)}개")

    # 오늘 날짜 기준 필터링
    today = dt.now(gettz("Asia/Seoul")).date()
    valid_candidates = []

    # 3. 그리드 영역부터 처리 (순서대로 진행)
    print("scrape_site1 - 그리드 영역 처리 시작")
    for cand in candidates:
        if cand["type"] != "grid":
            continue
        try:
            clean_date_text = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', cand["date_text"])
            pub_date = date_parse(clean_date_text, fuzzy=True).date()
            if pub_date == today:
                valid_candidates.append(cand)
            else:
                print(f"scrape_site1 - 그리드 항목 날짜 불일치: {cand['title']} ({pub_date} != {today}). 그리드 처리를 종료하고 리스트 영역으로 이동합니다.")
                break
        except Exception as e:
            print("scrape_site1 - 그리드 날짜 파싱 오류:", cand["date_text"], e)

    # 4. 그리드 영역에서 종료 후, 리스트 영역 처리 (남은 후보 중 리스트 타입 순서대로)
    if not valid_candidates:
        print("scrape_site1 - 그리드 영역에 오늘 날짜 기사가 없으므로 리스트 영역 처리 시작")
    else:
        # 만약 그리드 영역 처리를 중간에 종료했다면, 후보 목록 중 아직 리스트 항목이 남아 있다면 처리
        print("scrape_site1 - 리스트 영역 처리 시작")
    for cand in candidates:
        if cand["type"] != "list":
            continue
        try:
            clean_date_text = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', cand["date_text"])
            pub_date = date_parse(clean_date_text, fuzzy=True).date()
            if pub_date == today:
                valid_candidates.append(cand)
            else:
                print(f"scrape_site1 - 리스트 항목 날짜 불일치: {cand['title']} ({pub_date} != {today}). 리스트 영역 처리를 종료합니다.")
                break
        except Exception as e:
            print("scrape_site1 - 리스트 날짜 파싱 오류:", cand["date_text"], e)

    print(f"scrape_site1 - 오늘 날짜 기사 후보 수: {len(valid_candidates)}개")

    # 5. 오늘 날짜 후보들에 대해 개별 기사 페이지에서 본문 추출
    total_valid = len(valid_candidates)
    for idx, cand in enumerate(valid_candidates):
        try:
            print(f"scrape_site1 - 기사 추출 진행: {idx+1} / {total_valid} - {cand['url']}")
            driver.get(cand["url"])
            time.sleep(2)
            close_popups(driver)
            try:
                content_elem = driver.find_element(By.CSS_SELECTOR, "div.article-body.o-4")
            except Exception as e:
                print("scrape_site1 - 기본 본문 선택자 실패, 대체 선택자 시도:", e)
                content_elem = driver.find_element(By.CSS_SELECTOR, "div.post-content")
            full_text = content_elem.text.strip()
            articles.append({
                "title": cand["title"],
                "url": cand["url"],
                "date": cand["date_text"],
                "body": full_text
            })
        except Exception as e:
            print("scrape_site1 - 개별 기사 추출 실패:", e)
        try:
            driver.back()
            time.sleep(1)
        except Exception as e:
            print("scrape_site1 - driver.back() 실패:", e)

    # print(f"scrape_site1 기사 수집 완료: {len(articles)}개") main 함수에서 출력하므로 주석 처리
    return articles
