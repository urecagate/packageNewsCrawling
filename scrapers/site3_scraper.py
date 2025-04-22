import time
import re
from selenium.webdriver.common.by import By
from dateutil.parser import parse as date_parse
from utils import close_popups, dt, gettz

def scrape_site3(driver):
    articles = []
    base_url = "https://petpla.net/category/news/"
    try:
        driver.get(base_url)
        time.sleep(3)
        close_popups(driver)
    except Exception as e:
        print("scrape_site3 - base URL 접근 실패:", e)
        return articles

    candidates = []
    try:
        # 전체 기사 요소를 수집 (각 grid 항목이 <article> 태그에 포함되어 있다고 가정)
        all_articles = driver.find_elements(By.CSS_SELECTOR, "article")
        if not all_articles:
            print("scrape_site3 - 기사 요소를 찾지 못했습니다.")
            return articles

        # 첫 번째 기사는 메인 그리드, 나머지는 리스트형 그리드로 간주
        main_grid = all_articles[0]
        list_grids = all_articles[1:]

        # 메인 그리드 항목 처리
        try:
            link_elem = main_grid.find_element(By.CSS_SELECTOR, "header.entry-header h2.entry-title a")
            article_url = link_elem.get_attribute("href")
            article_title = link_elem.text.strip()
            try:
                # 날짜 정보는 <time class="entry-date published"> 요소에서 추출
                date_elem = main_grid.find_element(By.CSS_SELECTOR, "div.below-entry-meta a time.entry-date.published")
                date_text = date_elem.text.strip()
            except Exception as e:
                print("scrape_site3 - 메인 그리드 날짜 추출 실패:", e)
                date_text = ""
            candidates.append({
                "url": article_url,
                "title": article_title,
                "date_text": date_text,
                "type": "main"
            })
        except Exception as e:
            print("scrape_site3 - 메인 그리드 기사 정보 추출 실패:", e)

        # 리스트형 그리드 항목 처리
        for elem in list_grids:
            try:
                link_elem = elem.find_element(By.CSS_SELECTOR, "header.entry-header h2.entry-title a")
                article_url = link_elem.get_attribute("href")
                article_title = link_elem.text.strip()
            except Exception as e:
                print("scrape_site3 - 리스트 기사 URL/제목 추출 실패:", e)
                continue
            try:
                date_elem = elem.find_element(By.CSS_SELECTOR, "div.below-entry-meta a time.entry-date.published")
                date_text = date_elem.text.strip()
            except Exception as e:
                print("scrape_site3 - 리스트 기사 날짜 추출 실패:", e)
                date_text = ""
            candidates.append({
                "url": article_url,
                "title": article_title,
                "date_text": date_text,
                "type": "list"
            })

        print(f"scrape_site3 - 총 후보 기사 수: {len(candidates)}개")
    except Exception as e:
        print("scrape_site3 - 후보 기사 요소 찾기 실패:", e)
        return articles

    # 오늘 날짜 비교 (후보 grid 항목에 포함된 날짜 정보를 사용)
    today = dt.now(gettz("Asia/Seoul")).date()
    valid_candidates = []
    for cand in candidates:
        try:
            # 예: "2 Apr 2025" 혹은 "2nd April, 2025" → 숫자 접미사 제거
            clean_date = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', cand["date_text"])
            pub_date = date_parse(clean_date, fuzzy=True).date()
            if pub_date == today:
                valid_candidates.append(cand)
            else:
                print(f"scrape_site3 - 날짜 불일치: {cand['title']} ({pub_date} != {today})")
        except Exception as e:
            print("scrape_site3 - 날짜 파싱 오류:", cand["date_text"], e)

    total_valid = len(valid_candidates)
    print(f"scrape_site3 - 오늘 날짜 후보 기사 수: {total_valid}")

    # 오늘 날짜로 필터링된 후보들에 대해 개별 기사 페이지에서 본문 추출
    for idx, cand in enumerate(valid_candidates):
        try:
            print(f"scrape_site3 - 기사 추출 진행: {idx+1} / {total_valid} - {cand['url']}")
            driver.get(cand["url"])
            time.sleep(2)
            close_popups(driver)
            try:
                content_elem = driver.find_element(By.CSS_SELECTOR, "div.entry-content.clearfix")
                full_text = content_elem.text.strip()
            except Exception as e:
                print("scrape_site3 - 본문 추출 실패:", e)
                full_text = ""
            articles.append({
                "title": cand["title"],
                "url": cand["url"],
                "date": cand["date_text"],
                "body": full_text
            })
        except Exception as e:
            print("scrape_site3 - 개별 기사 추출 실패:", e)
            continue
        try:
            driver.back()
            time.sleep(1)
        except Exception as e:
            print("scrape_site3 - driver.back() 실패:", e)

    # print(f"scrape_site3 기사 수집 완료: {len(articles)}개") main 함수에서 출력하므로 주석 처리
    return articles
