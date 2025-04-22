import time
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dateutil.parser import parse as date_parse
from utils import close_popups, dt, gettz

def is_logged_in_beveragedaily(driver, wait_time=5):
    """
    Sign Out 버튼이 나타날 때까지 대기하여 로그인 상태를 판단합니다.
    """
    try:
        wait = WebDriverWait(driver, wait_time)
        wait.until(EC.presence_of_element_located(
            (By.XPATH, "//button[@class='c-button c-button--medium c-button--secondary-reverse pre-header-button']/span[text()='Sign Out']")))
        return True
    except Exception:
        return False

def login_beveragedaily(driver):
    """
    BeverageDaily 사이트에 로그인하는 함수.
    쿠키 배너 처리 후, Sign In 버튼 클릭 → iframe 내에서 이메일/비밀번호 입력 → 최종 SIGN IN 버튼 클릭 후 로그인 상태 확인.
    """
    try:
        driver.get("https://www.beveragedaily.com/")
        time.sleep(2)
        close_popups(driver)
        try:
            cookie_pref_btn = driver.find_element(By.ID, "onetrust-pc-btn-handler")
            cookie_pref_btn.click()
            time.sleep(1)
            reject_all_btn = driver.find_element(By.CSS_SELECTOR, "button.ot-pc-refuse-all-handler")
            reject_all_btn.click()
            print("쿠키 배너 reject 버튼 클릭 성공")
            time.sleep(2)
        except Exception as e:
            print("쿠키 배너 처리 실패 또는 존재하지 않음:", e)
        if is_logged_in_beveragedaily(driver):
            print("이미 로그인된 상태입니다.")
            return
        try:
            sign_in_btn = driver.find_element(By.XPATH, "//button[@class='c-button c-button--medium c-button--secondary-reverse pre-header-button']/span[text()='Sign In']")
            sign_in_btn.click()
        except Exception as e:
            print("로그인 링크를 찾지 못했거나 이미 로그인되어 있을 수 있음:", e)
            return
        try:
            wait = WebDriverWait(driver, 20)
            wait.until(EC.frame_to_be_available_and_switch_to_it((By.XPATH, "//iframe[contains(@src, 'tinypass.com/id/')]")))
            print("iframe 전환 성공")
        except Exception as e:
            print("iframe 전환 실패:", e)
        try:
            email_input = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[@name='email']")))
            email_input.clear()
            email_input.send_keys("archerree@gmail.com")
            print("이메일 입력란 찾음")
        except Exception as e:
            print("이메일 입력란을 찾지 못했습니다:", e)
        try:
            password_input = wait.until(EC.visibility_of_element_located((By.XPATH, "//input[@type='password']")))
            password_input.clear()
            password_input.send_keys("eoapWkd1!")
            print("비밀번호 입력란 찾음")
        except Exception as e:
            print("비밀번호 입력란을 찾지 못했습니다:", e)
        try:
            sign_in_final = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@actionlogin and @type='submit']//span[normalize-space()='Sign in']")))
            sign_in_final.click()
            print("SIGN IN 버튼 클릭 성공")
            time.sleep(2)
            driver.switch_to.default_content()
            driver.refresh()
            if is_logged_in_beveragedaily(driver, wait_time=10):
                print("BeverageDaily 로그인 성공!")
            else:
                print("로그인 후에도 Sign Out 버튼을 찾지 못했습니다. 로그인 실패 가능성.")
        except Exception as e:
            print("SIGN IN 버튼 클릭 실패:", e)
            return
    except Exception as e:
        print("login_beveragedaily() 전체 오류:", e)

def scrape_site6(driver):
    """
    BeverageDaily 뉴스 섹션의 10개 URL에서 리스트 형식 기사를 FIFO 방식으로 스캔합니다.
    각 URL에서 리스트형 기사 후보를 순차적으로 확인하며, 첫 번째로 오늘 날짜가 아닌 항목이 나오면
    해당 URL의 처리를 중단하고 다음 URL로 넘어갑니다.
    Headlines와 Products 섹션(필요시)도 제외하도록 필터링할 수 있습니다.
    오늘 날짜 기사에 대해서만 개별 기사 페이지에 진입하여 제목, 본문, (업데이트된) 날짜를 추출합니다.
    """
    articles = []
    try:
        login_beveragedaily(driver)
        time.sleep(3)
    except Exception as e:
        print("scrape_site6 - 로그인 처리 중 오류:", e)
        return articles

    urls = [
        "https://www.beveragedaily.com/News/Retail-shopper-insights/",
        "https://www.beveragedaily.com/News/Manufacturers/",
        "https://www.beveragedaily.com/News/Ingredients/",
        "https://www.beveragedaily.com/News/Processing-packaging/",
        "https://www.beveragedaily.com/News/Markets/",
        "https://www.beveragedaily.com/News/R-D/",
        "https://www.beveragedaily.com/News/Regulation-safety/",
        "https://www.beveragedaily.com/News/Editor-s-choice/",
        "https://www.beveragedaily.com/News/Industry-voices/",
        # "https://www.beveragedaily.com/News/Promotional-features/" 광고이므로 제외
    ]
    
    seen_urls = set()
    today = dt.now(gettz("Asia/Seoul")).date()

    # 각 URL의 인덱스 표시
    total_urls = len(urls)
    for url_index, page in enumerate(urls, start=1):
        print(f"\nscrape_site6 - 현재 URL {url_index}/{total_urls}: {page}")
        try:
            driver.get(page)
            time.sleep(3)
            close_popups(driver)
        except Exception as e:
            print("scrape_site6 - base URL 접근 실패:", e)
            continue

        try:
            # Headlines나 Products 섹션에 해당하는 항목은 CSS 선택자로 필터링(추가 조건 필요 시 여기서 구현)
            list_elements = driver.find_elements(By.CSS_SELECTOR, "div.story-item-text")
            print(f"scrape_site6 - List 형식 기사 개수 ({page}): {len(list_elements)}개")
        except Exception as e:
            print("scrape_site6 - List 형식 기사 요소 찾기 실패:", e)
            continue

        # FIFO 방식: 순차적으로 처리, 첫 번째로 오늘 날짜가 아닌 항목이 나오면 break
        for idx, elem in enumerate(list_elements):
            try:
                title_elem = elem.find_element(By.CSS_SELECTOR, "h2.story-item-text-headline a")
                article_url = title_elem.get_attribute("href")
                if article_url in seen_urls:
                    print(f"scrape_site6 - 중복 기사 스킵: {article_url}")
                    continue
                article_title = title_elem.text.strip()
                date_elem = elem.find_element(By.CSS_SELECTOR, "div.story-item-text-date-author time")
                publish_date = date_elem.get_attribute("datetime")
                if not publish_date:
                    publish_date = date_elem.text.strip()
                pub_date = date_parse(publish_date, fuzzy=True).date()
                if pub_date != today:
                    print(f"scrape_site6 - 날짜 불일치 (URL {page}): {article_title} ({pub_date} != {today}). 해당 URL 처리를 종료합니다.")
                    break  # FIFO: 오늘 날짜가 아닌 기사가 나오면 해당 URL은 더 이상 처리하지 않음.
                seen_urls.add(article_url)
                # 후보 기사 추가
                candidate = {
                    "url": article_url,
                    "title": article_title,
                    "date_text": publish_date,
                    "type": "list"
                }
                # (필요하다면 Headlines/Products 여부 추가 필터링 조건을 여기에)
                # 개별 기사 페이지로 진입하여 기사 내용 추출
                try:
                    print(f"scrape_site6 - 기사 추출 진행: {article_url}")
                    driver.get(article_url)
                    time.sleep(3)
                    close_popups(driver)
                    try:
                        title_detail = driver.find_element(By.CSS_SELECTOR, "h1.headline").text.strip()
                    except Exception as e:
                        print("scrape_site6 - 개별 기사 제목 추출 실패:", e)
                        title_detail = article_title
                    try:
                        date_detail_elem = driver.find_element(By.CSS_SELECTOR, "div.article-date-social div.date")
                        date_detail = date_detail_elem.text.strip()
                    except Exception as e:
                        print("scrape_site6 - 개별 기사 날짜 추출 실패:", e)
                        date_detail = publish_date
                    try:
                        content_elem = driver.find_element(By.CSS_SELECTOR, "article.b-article-body")
                        paragraphs = content_elem.find_elements(By.CSS_SELECTOR, "p.c-paragraph")
                        full_text = "\n".join([p.text.strip() for p in paragraphs if p.text.strip()])
                    except Exception as e:
                        print("scrape_site6 - 개별 기사 본문 추출 실패:", e)
                        full_text = ""
                    articles.append({
                        "title": title_detail,
                        "url": article_url,
                        "date": date_detail,
                        "body": full_text
                    })
                except Exception as e:
                    print("scrape_site6 - 개별 기사 추출 실패:", e)
                try:
                    driver.back()
                    time.sleep(2)
                except Exception as e:
                    print("scrape_site6 - driver.back() 실패:", e)
            except Exception as e:
                print(f"scrape_site6 - List 항목 처리 실패 (idx {idx}):", e)

    # print(f"\nscrape_site6 - 최종 수집 기사 개수: {len(articles)}개") main 함수에서 출력하므로 주석 처리
    return articles
