import time
import re
from selenium.webdriver.common.by import By
from utils import close_popups
from dateutil.parser import parse as date_parse
from datetime import datetime, timedelta
from utils import close_popups, dt, gettz
def scrape_site4(driver):
    articles = []
    base_url = "https://www.packagingdigest.com/"
    try:
        driver.get(base_url)
        time.sleep(3)
        close_popups(driver)
    except Exception as e:
        print("scrape_site4 - base URL 접근 실패:", e)
        return articles

    candidates = []
    # 그리드형 기사 후보 추출
    try:
        grid_elements = driver.find_elements(By.CSS_SELECTOR, "div.w-full.md\\:w-1\\/3.flex.flex-col.px-3.mb-4")
        total_grids = len(grid_elements)
        print(f"scrape_site4 - 그리드 기사 개수: {total_grids}")
        for elem in grid_elements:
            try:
                link_elem = elem.find_element(By.CSS_SELECTOR, "a")
                article_url = link_elem.get_attribute("href")
                title_elem = elem.find_element(By.CSS_SELECTOR, "h4.mb-1 a")
                article_title = title_elem.text.strip()
                date_elem = elem.find_element(By.CSS_SELECTOR, "div.text-gray-500.text-xs span")
                date_text = date_elem.text.strip()
                candidates.append({
                    "url": article_url,
                    "title": article_title,
                    "date_text": date_text,
                    "section": "grid"
                })
                print(f"scrape_site4 - 그리드 기사 추출 성공: {article_title}")
            except Exception as e:
                print("scrape_site4 - 그리드 기사 추출 실패:", e)
                continue
    except Exception as e:
        print("scrape_site4 - 그리드 섹션 찾기 실패:", e)

    # ListPreview형 기사 후보 추출
    try:
        list_elements = driver.find_elements(By.CSS_SELECTOR, "div.ListPreview")
        total_list = len(list_elements)
        print(f"scrape_site4 - 리스트 기사 개수: {total_list}")
        for elem in list_elements:
            try:
                link_elem = elem.find_element(By.CSS_SELECTOR, "div.ListPreview-TitleWrapper a")
                article_url = link_elem.get_attribute("href")
                article_title = link_elem.text.strip()
                date_elem = elem.find_element(By.CSS_SELECTOR, "span.ListPreview-Date")
                date_text = date_elem.text.strip()
                candidates.append({
                    "url": article_url,
                    "title": article_title,
                    "date_text": date_text,
                    "section": "list"
                })
                print(f"scrape_site4 - 리스트 기사 추출 성공: {article_title}")
            except Exception as e:
                print("scrape_site4 - 리스트 기사 추출 실패:", e)
                continue
    except Exception as e:
        print("scrape_site4 - 리스트 섹션 찾기 실패:", e)
    
    print(f"scrape_site4 - 총 후보 기사 수: {len(candidates)}")

    # 오늘과 어제 날짜 필터링
    today = dt.now(gettz("Asia/Seoul")).date()
    yesterday = today - timedelta(days=1)
    valid_candidates = []
    for cand in candidates:
        try:
            clean_date = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', cand["date_text"])
            pub_date = date_parse(clean_date, fuzzy=True).date()
            if pub_date == today or pub_date == yesterday:
                valid_candidates.append(cand)
            else:
                print(f"scrape_site4 - 날짜 불일치: {cand['title']} ({pub_date} != {today} 또는 {yesterday})")
        except Exception as e:
            print("scrape_site4 - 날짜 파싱 오류:", cand["date_text"], e)
    candidates = valid_candidates

    total_candidates = len(candidates)
    for idx, cand in enumerate(candidates):
        try:
            print(f"scrape_site4 - 개별 기사 추출 진행: {idx+1}/{total_candidates} - {cand['url']}")
            driver.get(cand["url"])
            time.sleep(2)
            close_popups(driver)
            # 개별 페이지에서 제목 추출 (그리드형일 경우 제목이 다르게 보일 수 있으므로 fallback)
            try:
                title_elem = driver.find_element(By.CSS_SELECTOR, "span.ArticleBase-LargeTitle[data-testid='article-title']")
                article_title = title_elem.text.strip()
            except Exception as e:
                print("scrape_site4 - 개별 기사 제목 추출 실패:", e)
                article_title = cand["title"]
            # 개별 페이지에서 날짜 추출
            try:
                date_elem = driver.find_element(By.CSS_SELECTOR, "p.Contributors-Date[data-testid='contributors-date']")
                publish_date = date_elem.text.strip()
            except Exception as e:
                print("scrape_site4 - 개별 기사 날짜 추출 실패:", e)
                publish_date = cand["date_text"]
            # 개별 페이지에서 본문 추출
            try:
                content_elem = driver.find_element(By.CSS_SELECTOR, "div.ArticleBase-BodyContent_Article")
                full_text = content_elem.text.strip()
            except Exception as e:
                print("scrape_site4 - 개별 기사 본문 추출 실패:", e)
                full_text = ""
            
            articles.append({
                "title": article_title,
                "url": cand["url"],
                "date": publish_date,
                "body": full_text
            })
        except Exception as e:
            print("scrape_site4 - 개별 기사 페이지 처리 실패:", e)
            continue
        try:
            driver.back()
            time.sleep(1)
        except Exception as e:
            print("scrape_site4 - driver.back() 실패:", e)
    
    # print(f"scrape_site4 기사 수집 완료: {len(articles)}개") main 함수에서 출력하므로 주석 처리
    return articles
