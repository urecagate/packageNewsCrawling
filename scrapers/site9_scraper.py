import time
import re
from selenium.webdriver.common.by import By
from dateutil.parser import parse as date_parse
from utils import close_popups, dt, gettz

def scrape_site9(driver):
    articles = []
    base_url = "https://www.packagingdive.com/"
    try:
        driver.get(base_url)
        time.sleep(3)
        # 쿠키 배너 처리: "모두 거부" 버튼 클릭
        try:
            reject_btn = driver.find_element(By.CSS_SELECTOR, "button.osano-cm-denyAll")
            reject_btn.click()
            print("Cookie banner '모두 거부' 클릭 성공")
            time.sleep(2)
        except Exception as e:
            print("쿠키 배너 처리 실패 또는 존재하지 않음:", e)
        close_popups(driver)
    except Exception as e:
        print("scrape_site9 - base URL 접근 실패:", e)
        return articles

    candidates = []
    today = dt.now(gettz("Asia/Seoul")).date()

    # 1. 메인 그리드 처리 (FIFO: 한 건만 있으므로 날짜 불일치 시 건너뜀)
    try:
        main_grid_elem = driver.find_element(By.CSS_SELECTOR, "div.large-6.columns")
        try:
            hero_link = main_grid_elem.find_element(By.CSS_SELECTOR, "section.hero-article h1#hero-item-title a")
            article_url = hero_link.get_attribute("href")
            article_title = hero_link.text.strip()
            # 개별 페이지 접속하여 날짜 추출
            driver.get(article_url)
            time.sleep(3)
            close_popups(driver)
            date_str = ""
            try:
                time_elem = driver.find_element(By.CSS_SELECTOR, "time")
                date_str = time_elem.get_attribute("datetime")
                if not date_str:
                    date_str = time_elem.text.strip()
            except Exception:
                # Top Stories처럼 날짜 정보가 없으면 빈 문자열
                date_str = ""
            try:
                pub_date = date_parse(date_str, fuzzy=True).date()
            except Exception as e:
                print("scrape_site9 - 메인 그리드 날짜 파싱 오류:", date_str, e)
                pub_date = None

            if pub_date == today:
                candidates.append({
                    "url": article_url,
                    "title": article_title,
                    "date_text": date_str,
                    "section": "main_grid"
                })
                print(f"scrape_site9 - Main Grid URL 수집 성공: {article_url}")
            else:
                print(f"scrape_site9 - Main Grid 날짜 불일치: {article_title} ({pub_date} != {today})")
        except Exception as e:
            print("scrape_site9 - 메인 그리드 기사 추출 실패:", e)
    except Exception as e:
        print("scrape_site9 - 메인 그리드 섹션 미발견:", e)

    # 2. Top Stories 처리 (FIFO: 순서대로 진행, 첫 날짜 불일치 시 break)
    try:
        top_stories_elements = driver.find_elements(By.CSS_SELECTOR, "section.top-stories ol li")
        print(f"scrape_site9 - Top Stories 기사 개수: {len(top_stories_elements)}개")
        for idx, li in enumerate(top_stories_elements):
            try:
                a_elem = li.find_element(By.CSS_SELECTOR, "h3 a")
                article_url = a_elem.get_attribute("href")
                article_title = a_elem.text.strip()
                # 개별 페이지 접속 후, Top Stories는 <span class="published-info">에 날짜가 있음
                driver.get(article_url)
                time.sleep(3)
                close_popups(driver)
                date_str = ""
                try:
                    pub_elem = driver.find_element(By.CSS_SELECTOR, "span.published-info")
                    date_str = pub_elem.text.strip()
                    date_str = re.sub(r"^Published\s*", "", date_str)
                except Exception as e:
                    print("scrape_site9 - Top Stories 날짜 추출 실패:", article_url, e)
                    continue

                try:
                    pub_date = date_parse(date_str, fuzzy=True).date()
                except Exception as e:
                    print("scrape_site9 - Top Stories 날짜 파싱 오류:", date_str, e)
                    continue

                if pub_date == today:
                    candidates.append({
                        "url": article_url,
                        "title": article_title,
                        "date_text": date_str,
                        "section": "top_stories"
                    })
                    print(f"scrape_site9 - Top Stories [{idx+1}/{len(top_stories_elements)}] URL 및 날짜 수집 성공: {article_url} / {date_str}")
                else:
                    print(f"scrape_site9 - Top Stories FIFO break: {article_title} ({pub_date} != {today})")
                    break  # FIFO: 더 이상 후보가 오늘 날짜가 아니면 종료
            except Exception as e:
                print(f"scrape_site9 - Top Stories [{idx+1}/{len(top_stories_elements)}] 추출 실패:", e)
    except Exception as e:
        print("scrape_site9 - Top Stories 섹션 미발견:", e)

    # 3. The Latest 처리 (FIFO: 광고/칸 나누기 셀은 건너뛰고, 유효 셀 순서대로 진행 후 FIFO break)
    try:
        all_latest_elements = driver.find_elements(By.CSS_SELECTOR, "ul.feed.layout-stack-xxl li.row.feed__item")
        valid_latest_elements = []
        for li in all_latest_elements:
            classes = li.get_attribute("class")
            # 광고 또는 칸 나누기 셀은 "feed-item-ad" 클래스가 포함되어 있으면 건너뛴다.
            if classes and "feed-item-ad" in classes:
                print("scrape_site9 - The Latest 광고/칸 나누기 셀 건너뛰기")
                continue
            valid_latest_elements.append(li)
        print(f"scrape_site9 - The Latest 유효 기사 셀 개수: {len(valid_latest_elements)}개")
        for idx, li in enumerate(valid_latest_elements):
            try:
                a_elem = li.find_element(By.CSS_SELECTOR, "h3.feed__title a")
            except Exception as e:
                try:
                    a_elem = li.find_element(By.CSS_SELECTOR, "a.analytics")
                except Exception as e2:
                    print(f"scrape_site9 - The Latest [{idx+1}/{len(valid_latest_elements)}] 추출 실패:", e2)
                    continue
            article_url = a_elem.get_attribute("href")
            article_title = a_elem.text.strip()
            driver.get(article_url)
            time.sleep(3)
            close_popups(driver)
            date_str = ""
            try:
                time_elem = driver.find_element(By.CSS_SELECTOR, "time")
                date_str = time_elem.get_attribute("datetime")
                if not date_str:
                    date_str = time_elem.text.strip()
            except Exception as e:
                print("scrape_site9 - The Latest 날짜 추출 실패:", article_url, e)
                continue
            try:
                pub_date = date_parse(date_str, fuzzy=True).date()
            except Exception as e:
                print("scrape_site9 - The Latest 날짜 파싱 오류:", date_str, e)
                continue
            if pub_date == today:
                candidates.append({
                    "url": article_url,
                    "title": article_title,
                    "date_text": date_str,
                    "section": "the_latest"
                })
                print(f"scrape_site9 - The Latest [{idx+1}/{len(valid_latest_elements)}] URL 수집 성공: {article_url}")
            else:
                print(f"scrape_site9 - The Latest FIFO break: {article_title} ({pub_date} != {today})")
                break  # FIFO: 더 이상 오늘 날짜가 아니면 종료
        # End of The Latest 처리
    except Exception as e:
        print("scrape_site9 - The Latest 섹션 미발견:", e)

    print(f"scrape_site9 - 총 후보 기사 수: {len(candidates)}개")
    print(f"scrape_site9 - 오늘 날짜 후보 기사 수: {len(candidates)}개")  # FIFO 처리 시, candidates에 이미 오늘날짜 기사만 남음

    # 4. 오늘 날짜 후보 기사에 대해 개별 페이지에서 제목 및 본문 재추출
    for idx, cand in enumerate(candidates):
        try:
            print(f"scrape_site9 - 기사 추출 진행: {idx+1}/{len(candidates)} - {cand['url']}")
            driver.get(cand["url"])
            time.sleep(3)
            close_popups(driver)
            # 제목 추출: 기본적으로 <h1> 태그 사용, 없으면 기존 제목 사용
            try:
                title_elem = driver.find_element(By.CSS_SELECTOR, "h1")
                article_title = title_elem.text.strip()
            except Exception as e:
                print("scrape_site9 - 개별 기사 제목 추출 실패:", e)
                article_title = cand["title"]
            # 본문 추출: "div.article-body, div.article-content" 선택자 사용
            try:
                content_elem = driver.find_element(By.CSS_SELECTOR, "div.article-body, div.article-content")
                full_text = content_elem.text.strip()
            except Exception as e:
                print("scrape_site9 - 개별 기사 본문 추출 실패:", e)
                full_text = ""
            articles.append({
                "title": article_title,
                "url": cand["url"],
                "date": cand.get("date_text", ""),
                "body": full_text
            })
        except Exception as e:
            print("scrape_site9 - 개별 기사 추출 실패:", e)
            continue
        try:
            driver.back()
            time.sleep(2)
        except Exception as e:
            print("scrape_site9 - driver.back() 실패:", e)

    # print(f"scrape_site9 기사 수집 완료: {len(articles)}개") main 함수에서 출력하므로 주석 처리
    return articles
