from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from dateutil.parser import parse as date_parse
from utils import close_popups, dt, gettz


def reject_cookie_banner(driver):
    """
    쿠키 배너의 'Reject All' 버튼을 클릭합니다.
    버튼의 id가 'onetrust-reject-all-handler'라고 가정합니다.
    """
    try:
        wait = WebDriverWait(driver, 5)
        reject_btn = wait.until(EC.element_to_be_clickable((By.ID, "onetrust-reject-all-handler")))
        driver.execute_script("arguments[0].click();", reject_btn)
        print("쿠키 배너 reject 버튼 클릭 성공")
        time.sleep(1)
    except Exception as e:
        print("쿠키 배너 reject 버튼 처리 실패 또는 존재하지 않음:", e)



def login_bevindustry(driver):
    """
    BevIndustry 로그인 절차를 수행하는 함수.
    로그인 링크 클릭 대신 직접 로그인 페이지 URL로 이동합니다.
    """
    try:
        # 쿠키 배너 처리
        main_url = "https://www.bevindustry.com/"
        driver.get(main_url)
        time.sleep(3)
        close_popups(driver)
        reject_cookie_banner(driver)
        time.sleep(2)
        
        # 로그인 페이지로 직접 이동
        login_url = ("https://bnp.dragonforms.com/loading.do?pk=X_W_WRSIGN"
                     "&returnurl=https%3A%2F%2Fwww.bevindustry.com%2Fuser%2Fomeda%3Freferer%3Dhttps%3A%2F%2Fwww.bevindustry.com%2F"
                     "&omedasite=BI_Login")
        driver.get(login_url)
        time.sleep(3)
        
        # 이메일 입력란 찾기
        wait = WebDriverWait(driver, 10)
        email_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input#id152[name='demo645669']")))
        email_input.clear()
        email_input.send_keys("archerree@gmail.com")
        
        # 비밀번호 입력란 찾기
        password_input = driver.find_element(By.CSS_SELECTOR, "input#id16[name='demo645670']")
        password_input.clear()
        password_input.send_keys("eoapWkd1!")
        
        # SIGN IN 버튼 클릭
        sign_in_button = driver.find_element(By.CSS_SELECTOR, "input#custombtn[type='submit']")
        driver.execute_script("arguments[0].click();", sign_in_button)
        time.sleep(5)
    except Exception as e:
        print("로그인 처리 중 오류:", e)

def scrape_site5(driver):
    # 먼저 로그인 처리
    try:
        login_bevindustry(driver)
        time.sleep(3)
    except Exception as e:
        print("scrape_site5 - 로그인 처리 중 오류:", e)
        return []

    articles = []
    seen_urls = set()  # 중복 기사 방지를 위한 집합

    # 스크래핑 대상 URL (두 개)
    urls = [
        "https://www.bevindustry.com/topics/2642-beverage-news",  # 첫 번째 URL: grid형 후보만 존재
        "https://www.bevindustry.com/articles/topic/2642"         # 두 번째 URL: list형 후보만 존재
    ]
    
    for page in urls:
        try:
            driver.get(page)
            time.sleep(3)
            close_popups(driver)
        except Exception as e:
            print("scrape_site5 - base URL 접근 실패:", e)
            continue

        candidates = []
        is_first_url = ("topics/2642-beverage-news" in page)

        if is_first_url:
            # 첫 번째 URL: grid형 후보만 수집 (리스트형은 없음)
            try:
                grid_elements = driver.find_elements(By.CSS_SELECTOR, "li.article-list-hz-l2__item")
                print(f"scrape_site5 - Grid 형식 기사 개수: {len(grid_elements)}개")
                for idx, elem in enumerate(grid_elements):
                    try:
                        url_elem = elem.find_element(By.CSS_SELECTOR, "a.article-list-hz-l2__thumbnail-link")
                        article_url = url_elem.get_attribute("href")
                        title_elem = elem.find_element(By.CSS_SELECTOR, "h2.article-list-hz-l2__headline a")
                        article_title = title_elem.text.strip()
                        # grid형은 목록에 날짜 정보가 없으므로 date_text은 빈 문자열로 설정
                        candidates.append({
                            "url": article_url,
                            "title": article_title,
                            "date_text": "",
                            "type": "grid"
                        })
                        print(f"scrape_site5 - Grid [{idx+1}/{len(grid_elements)}] URL 수집 성공: {article_url}")
                    except Exception as e:
                        print(f"scrape_site5 - Grid [{idx+1}/{len(grid_elements)}] 기사 URL 추출 실패:", e)
            except Exception as e:
                print("scrape_site5 - Grid 형식 기사 요소 찾기 실패:", e)
        else:
            # 두 번째 URL: list형 후보 수집
            try:
                list_elements = driver.find_elements(By.CSS_SELECTOR, "div.article-summary__details.has-image")
                print(f"scrape_site5 - List 형식 기사 개수: {len(list_elements)}개")
                for idx, elem in enumerate(list_elements):
                    try:
                        url_elem = elem.find_element(By.CSS_SELECTOR, "h2.headline.article-summary__headline a")
                        article_url = url_elem.get_attribute("href")
                        article_title = url_elem.text.strip()
                        date_elem = elem.find_element(By.CSS_SELECTOR, "div.date.article-summary__post-date")
                        date_text = date_elem.text.strip()
                        candidates.append({
                            "url": article_url,
                            "title": article_title,
                            "date_text": date_text,
                            "type": "list"
                        })
                        print(f"scrape_site5 - List [{idx+1}/{len(list_elements)}] URL 수집 성공: {article_url}")
                    except Exception as e:
                        print(f"scrape_site5 - List [{idx+1}/{len(list_elements)}] 기사 URL 추출 실패:", e)
            except Exception as e:
                print("scrape_site5 - List 형식 기사 요소 찾기 실패:", e)

        print(f"scrape_site5 - 총 후보 기사 수 (현재 페이지): {len(candidates)}개")

        # 오늘 날짜 기준 후보 필터링
        today = dt.now(gettz("Asia/Seoul")).date()
        valid_candidates = []
        for cand in candidates:
            if cand["type"] == "list":
                try:
                    pub_date = date_parse(cand["date_text"], fuzzy=True).date()
                    if pub_date == today:
                        valid_candidates.append(cand)
                    else:
                        print(f"scrape_site5 - List 날짜 불일치: {cand['title']} ({pub_date} != {today})")
                except Exception as e:
                    print("scrape_site5 - List 날짜 파싱 오류:", cand["date_text"], e)
            else:
                # grid형은 개별 페이지에서 날짜를 추출할 예정이므로 후보로 모두 포함
                valid_candidates.append(cand)
        print(f"scrape_site5 - 유효 후보 기사 수 (필터 후): {len(valid_candidates)}개")

        # 개별 기사 페이지에서 본문(및 날짜) 추출
        total_valid = len(valid_candidates)
        for idx, cand in enumerate(valid_candidates):
            # 중복 기사(URL) 체크
            if cand["url"] in seen_urls:
                print(f"scrape_site5 - 이미 처리된 기사 중복 스킵: {cand['url']}")
                continue

            print(f"scrape_site5 - 기사 추출 진행: {idx+1}/{total_valid} - {cand['url']}")
            try:
                driver.get(cand["url"])
                time.sleep(3)
                close_popups(driver)
                
                # grid형의 경우, 개별 페이지에서 날짜 추출 후 오늘 날짜인지 재확인
                if cand["type"] == "grid":
                    try:
                        date_elem = driver.find_element(By.CSS_SELECTOR, "div.article-date-social div.date")
                        publish_date = date_elem.text.strip()
                        cand["date_text"] = publish_date
                    except Exception as e:
                        print("scrape_site5 - Grid 개별 기사 날짜 추출 실패:", e)
                
                # 리스트형은 이미 날짜 정보가 있으므로 추가 작업 없음

                # 날짜 재검증 (grid형)
                if cand["type"] == "grid":
                    try:
                        pub_date = date_parse(cand["date_text"], fuzzy=True).date()
                        if pub_date != today:
                            print(f"scrape_site5 - Grid 기사 날짜 불일치 (개별 추출): {cand['title']} ({pub_date} != {today})")
                            continue
                    except Exception as e:
                        print("scrape_site5 - Grid 날짜 파싱 오류:", cand["date_text"], e)
                        continue
                
                # 개별 기사 제목 추출 (업데이트된 제목이 있을 경우)
                try:
                    title_elem = driver.find_element(By.CSS_SELECTOR, "h1.headline")
                    article_title = title_elem.text.strip()
                except Exception as e:
                    print("scrape_site5 - 개별 기사 제목 추출 실패:", e)
                    article_title = cand["title"]
                
                # 개별 기사 본문 추출
                try:
                    content_elem = driver.find_element(By.CSS_SELECTOR, "div.content div.body.gsd-paywall")
                    full_text = content_elem.text.strip()
                except Exception as e:
                    print("scrape_site5 - 개별 기사 본문 추출 실패:", e)
                    full_text = ""
                
                articles.append({
                    "title": article_title,
                    "url": cand["url"],
                    "date": cand["date_text"],
                    "body": full_text
                })
                seen_urls.add(cand["url"])
            except Exception as e:
                print("scrape_site5 - 개별 기사 추출 실패:", e)
            try:
                driver.back()
                time.sleep(2)
            except Exception as e:
                print("scrape_site5 - driver.back() 실패:", e)
    # print(f"scrape_site5 기사 수집 완료: {len(articles)}개") main 함수에서 출력하므로 주석 처리
    return articles
