# main.py
from config import (
    azure_endpoint, azure_subscription_key, azure_application, 
    azure_compCode, azure_userID, azure_userNM, azure_serviceType, 
    sender_email, MUST_VISIT_WEBSITES
)
from utils import (
    kill_chrome, start_chrome_debug, create_driver_debug, close_popups, 
    get_article_date_from_meta, translate_text, send_email, get_article_text_with_selenium, 
    get_article_text, get_articles_from_google_news, get_newspaper_name, os, HTML,
    process_site_articles, scrape_keyword_search_articles, process_keyword_articles, build_and_send_email,
    write_to_spreadsheet, write_to_csv
)
from scrapers import (
    scrape_site1, scrape_site2, scrape_site3, scrape_site4, 
    scrape_site5, scrape_site6, scrape_site7, scrape_site8, scrape_site9
)
from urllib.parse import urlparse, urljoin
import time
from bs4 import BeautifulSoup
from dateutil.parser import parse
from datetime import datetime as dt
from dateutil.tz import gettz

def main():
    chrome_process = start_chrome_debug()
    driver = create_driver_debug()
    print("Chrome 드라이버 및 프로세스 준비 완료.")
    
    # ----------------------------------------------------------------
    # [필수 웹사이트 방문 스크래핑 코드 (통합 테스트용)]
    # 아래 코드는 나중에 통합 테스트 시 사용하기 위해 주석 처리해두었습니다.
    site_articles = []
    for func in [scrape_site1, 
                 scrape_site2, 
                 scrape_site3, 
                 scrape_site4, 
                 scrape_site5, 
                 scrape_site6, 
                 scrape_site7, 
                 scrape_site8, 
                 scrape_site9]:
        try:
            articles = func(driver)
            print(f"{func.__name__} 기사 수집 완료: {len(articles)}개")
            site_articles.extend(articles)
        except Exception as e:
            print(f"{func.__name__} 스크래핑 함수 오류:", e)
    print(f"전체 기사 수: {len(site_articles)}개")
    processed_site_articles = process_site_articles(driver, site_articles)
    # ----------------------------------------------------------------

    # [키워드 검색 기사 스크래핑 테스트]
    try:
        keyword_articles = scrape_keyword_search_articles(driver)
        print(f"scrape_keyword_search_articles 기사 수집 완료: {len(keyword_articles)}개")
    except Exception as e:
        print("scrape_keyword_search_articles 스크래핑 함수 오류:", e)
        keyword_articles = []

    processed_keyword_articles = process_keyword_articles(driver, keyword_articles)
    print(f"최종 유효 기사 수: {len(processed_keyword_articles)}개")
    
    # 두 리스트를 합치기
    combined_articles = processed_site_articles + processed_keyword_articles
    build_and_send_email(combined_articles)

    # (추가) 구글 스프레드시트에 저장
    #write_to_spreadsheet(processed_keyword_articles)

    #write_to_csv(processed_keyword_articles)
    
    driver.quit()

    # chrome_process가 None이 아니면 종료, None이면 메시지 출력
    if chrome_process is not None:
        chrome_process.terminate()
        print("Chrome 프로세스 종료 완료.")
    else:
        print("Chrome 프로세스가 시작되지 않았습니다.")

if __name__ == "__main__":
    main()
