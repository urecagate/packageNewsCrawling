import time
import re
from selenium.webdriver.common.by import By
from dateutil.parser import parse as date_parse
from datetime import timedelta
from utils import close_popups, dt, gettz

def scrape_site8(driver):
    articles = []
    base_url = "https://www.packagingnews.com.au/latest"
    try:
        driver.get(base_url)
        time.sleep(3)
        close_popups(driver)
    except Exception as e:
        print("scrape_site8 - base URL 접근 실패:", e)
        return articles

    candidates = []
    
    # 1. 메인 그리드 후보 수집 (상단 영역: div.col-xx-8 내의 div.gallery-feature)
    try:
        main_grids = driver.find_elements(By.CSS_SELECTOR, "div.col-xx-8 div.gallery-feature")
        print(f"scrape_site8 - 메인 그리드 개수: {len(main_grids)}개")
        for idx, elem in enumerate(main_grids):
            try:
                link_elem = elem.find_element(By.CSS_SELECTOR, "a.gallery-link")
                article_url = link_elem.get_attribute("href")
                try:
                    title_elem = elem.find_element(By.CSS_SELECTOR, "div.gallery-link-pop h1.h4")
                    article_title = title_elem.text.strip()
                except Exception as e:
                    print(f"scrape_site8 - 메인 그리드 [{idx+1}] 제목 추출 실패:", e)
                    article_title = ""
                try:
                    date_elem = elem.find_element(By.CSS_SELECTOR, "small.text-hint")
                    date_text = date_elem.text.strip()
                except Exception as e:
                    print(f"scrape_site8 - 메인 그리드 [{idx+1}] 날짜 추출 실패:", e)
                    date_text = ""
                candidates.append({
                    "url": article_url,
                    "title": article_title,
                    "date_text": date_text,
                    "type": "main"
                })
                print(f"scrape_site8 - 메인 그리드 [{idx+1}] URL 및 날짜 수집 성공: {article_url} / {date_text}")
            except Exception as e:
                print(f"scrape_site8 - 메인 그리드 [{idx+1}] 기사 정보 추출 실패:", e)
    except Exception as e:
        print("scrape_site8 - 메인 그리드 기사 요소 찾기 실패:", e)
    
    # 2. 리스트형 그리드 후보 수집 (하단 영역: 각 기사가 포함된 영역은 div.landing-cell)
    try:
        grid_cells = driver.find_elements(By.CSS_SELECTOR, "div.landing-cell")
        print(f"scrape_site8 - 리스트형 그리드 셀 개수: {len(grid_cells)}개")
        for idx, cell in enumerate(grid_cells):
            # 광고 셀 건너뛰기: 내부에 div.landing-ad가 있으면 광고로 취급
            if cell.find_elements(By.CSS_SELECTOR, "div.landing-ad"):
                print(f"scrape_site8 - 리스트형 그리드 [{idx+1}] 광고 셀 건너뛰기")
                continue
            # 빈 셀 건너뛰기: landing-card-inner가 없으면 빈 셀로 취급
            if not cell.find_elements(By.CSS_SELECTOR, "div.landing-card-inner"):
                print(f"scrape_site8 - 리스트형 그리드 [{idx+1}] 빈 셀 건너뛰기")
                continue
            try:
                title_elem = cell.find_element(By.CSS_SELECTOR, "div.landing-card-inner div.landing-card-title h3 a")
                article_title = title_elem.text.strip()
                article_url = title_elem.get_attribute("href")
                try:
                    date_elem = cell.find_element(By.CSS_SELECTOR, "div.landing-card-footer span.text-hint")
                    date_text = date_elem.text.strip()
                except Exception as e:
                    print(f"scrape_site8 - 리스트형 그리드 [{idx+1}] 날짜 추출 실패:", e)
                    date_text = ""
                candidates.append({
                    "url": article_url,
                    "title": article_title,
                    "date_text": date_text,
                    "type": "list"
                })
                print(f"scrape_site8 - 리스트형 그리드 [{idx+1}] URL 및 날짜 수집 성공: {article_url} / {date_text}")
            except Exception as e:
                print(f"scrape_site8 - 리스트형 그리드 [{idx+1}] 기사 정보 추출 실패:", e)
    except Exception as e:
        print("scrape_site8 - 리스트형 그리드 기사 요소 찾기 실패:", e)
    
    print(f"scrape_site8 - 총 후보 기사 수 (수집 전): {len(candidates)}개")
    
    # 3. 중복 제거 (URL 기준)
    unique_candidates = {}
    for cand in candidates:
        url = cand.get("url")
        if url and url not in unique_candidates:
            unique_candidates[url] = cand
        else:
            if url:
                print(f"scrape_site8 - 중복 기사 제거: {url}")
    candidates = list(unique_candidates.values())
    print(f"scrape_site8 - 총 후보 기사 수 (중복 제거 후): {len(candidates)}개")
    
    # 4. 오늘과 어제 날짜 후보 필터링 (날짜 정보: date_text)
    today = dt.now(gettz("Asia/Seoul")).date()
    yesterday = today - timedelta(days=1)
    valid_candidates = []
    for cand in candidates:
        try:
            # 날짜 정보가 None인 경우 빈 문자열로 대체
            date_text = cand.get("date_text") or ""
            if not date_text:
                print(f"scrape_site8 - 날짜 정보 없음: {cand.get('title')}")
                continue
            # 서수(ordinal suffix) 제거 (예: "3rd" → "3")
            clean_date_text = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_text)
            pub_date = date_parse(clean_date_text, fuzzy=True).date()
            if pub_date == today or pub_date == yesterday:
                valid_candidates.append(cand)
            else:
                print(f"scrape_site8 - 날짜 불일치: {cand.get('title')} ({pub_date} != {today} 또는 {yesterday})")
        except Exception as e:
            print("scrape_site8 - 날짜 파싱 오류:", cand.get("date_text"), e)
    print(f"scrape_site8 - 오늘/어제 날짜 후보 기사 수: {len(valid_candidates)}개")
    
    # 5. 오늘/어제 날짜 후보 기사에 대해 개별 페이지에서 제목 및 본문 추출
    total_valid = len(valid_candidates)
    for idx, cand in enumerate(valid_candidates):
        try:
            print(f"scrape_site8 - 기사 추출 진행: {idx+1}/{total_valid} - {cand.get('url')}")
            driver.get(cand.get("url"))
            time.sleep(3)
            close_popups(driver)
            # 개별 기사 페이지의 제목 추출: <h1 class="article-title">
            try:
                title_elem = driver.find_element(By.CSS_SELECTOR, "h1.article-title")
                article_title = title_elem.text.strip()
            except Exception as e:
                print("scrape_site8 - 개별 기사 제목 추출 실패:", e)
                article_title = cand.get("title", "")
            # 만약 후보 날짜 정보가 없다면 개별 페이지의 날짜도 시도 (예: "By 작성자 | 3 April 2025")
            if not cand.get("date_text"):
                try:
                    auth_elem = driver.find_element(By.CSS_SELECTOR, "div.article-author span")
                    auth_text = auth_elem.text.strip()
                    parts = auth_text.split("|")
                    if len(parts) > 1:
                        cand["date_text"] = parts[1].strip()
                except Exception as e:
                    print("scrape_site8 - 개별 기사 날짜 추출 실패:", e)
            # 본문 추출: 우선 <div class="article-content">를 시도하고, 없으면 다른 선택자 순차 시도
            full_text = ""
            for selector in ["div.article-content", "div.storytext", "div.article-body", "article.article-body"]:
                try:
                    content_elem = driver.find_element(By.CSS_SELECTOR, selector)
                    full_text = content_elem.text.strip()
                    if full_text:
                        break
                except Exception:
                    continue
            if not full_text:
                print("scrape_site8 - 개별 기사 본문 추출 실패, 빈 문자열 할당")
            articles.append({
                "title": article_title,
                "url": cand.get("url"),
                "date": cand.get("date_text", ""),
                "body": full_text
            })
        except Exception as e:
            print("scrape_site8 - 개별 기사 추출 실패:", e)
            continue
        try:
            driver.back()
            time.sleep(2)
        except Exception as e:
            print("scrape_site8 - driver.back() 실패:", e)
    
    # print(f"scrape_site8 기사 수집 완료: {len(articles)}개") main 함수에서 출력하므로 주석 처리
    return articles
