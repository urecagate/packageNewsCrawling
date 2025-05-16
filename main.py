# main.py
from config import (
    azure_endpoint, azure_subscription_key, azure_application, 
    azure_compCode, azure_userID, azure_userNM, azure_serviceType, 
    sender_email, MUST_VISIT_WEBSITES
)
from utils import (
    kill_chrome, start_chrome_debug, create_driver_debug, close_popups, 
    get_article_date_from_meta, translate_text, send_email_ews, get_article_text_with_selenium, 
    get_article_text, get_articles_from_google_news, get_newspaper_name, os, HTML,
    process_site_articles, scrape_keyword_search_articles, process_keyword_articles, build_and_send_email,
    write_to_spreadsheet, write_to_csv, SeleniumSearchError
)
from scrapers import (
    scrape_site1, scrape_site2, scrape_site3, scrape_site4, 
    scrape_site5, scrape_site6, scrape_site7, scrape_site8, scrape_site9
)
# 구글 API 검색 모듈 추가
from google_api_search import search_api_news_articles
from urllib.parse import urlparse, urljoin
import time
from bs4 import BeautifulSoup
from dateutil.parser import parse
from datetime import datetime as dt
from dateutil.tz import gettz

def try_api_search(driver):
    """
    구글 API를 사용한 검색을 시도합니다.
    
    Args:
        driver: Selenium 웹드라이버 객체
        
    Returns:
        list: 검색된 기사 목록 (검색 실패 시 빈 목록)
    """
    # 환경 변수 확인 (API 키와 검색 엔진 ID)
    api_key = os.environ.get("GOOGLE_API_KEY")
    search_engine_id = os.environ.get("GOOGLE_SEARCH_ENGINE_ID")
    
    if not api_key or not search_engine_id:
        print("[오류] API 키 또는 검색 엔진 ID가 설정되어 있지 않아 API 검색을 진행할 수 없습니다.")
        print("환경 변수 설정 방법:")
        print('export GOOGLE_API_KEY="YOUR_API_KEY"')
        print('export GOOGLE_SEARCH_ENGINE_ID="YOUR_SEARCH_ENGINE_ID"')
        return []
    
    try:
        articles = search_api_news_articles(driver)
        print(f"API 키워드 검색 기사 처리 완료: {len(articles)}개")
        return articles
    except Exception as api_e:
        print(f"API 검색도 실패했습니다: {api_e}")
        return []

def main():
    # 환경 변수로 CI 환경 여부 확인
    is_ci = os.environ.get('CI', 'false').lower() == 'true'
    
    try:
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

        # [키워드 검색 기사 스크래핑]
        processed_keyword_articles = []
        
        # 기본적으로 셀레늄 방식으로 검색 시도
        try:
            print("셀레늄을 사용하여 키워드 검색 시작...")
            processed_keyword_articles = scrape_keyword_search_articles(driver)
            print(f"셀레늄 키워드 검색 기사 처리 완료: {len(processed_keyword_articles)}개")
        except SeleniumSearchError as selenium_error:
            print(f"셀레늄 검색 실패 감지됨: {selenium_error}")
            # 셀레늄 검색 중 키워드 페이지 접근 실패 발생 시 즉시 API 검색으로 전환
            print("Google API로 대체 검색 시도...")
            processed_keyword_articles = try_api_search(driver)
        except Exception as e:
            error_msg = str(e)
            print(f"구글 조회 실패: {error_msg}")
        
        # 두 리스트를 합치기
        combined_articles = processed_site_articles + processed_keyword_articles
        build_and_send_email(combined_articles)

        # (추가) 구글 스프레드시트에 저장
        #write_to_spreadsheet(processed_keyword_articles)

        #write_to_csv(processed_keyword_articles)
        
    except Exception as e:
        print(f"실행 중 오류 발생: {e}")
    finally:
        # 종료 처리
        if 'driver' in locals() and driver:
            try:
                driver.quit()
                print("드라이버 종료 완료.")
            except Exception as e:
                print(f"드라이버 종료 중 오류: {e}")
                
        # chrome_process가 None이 아니면 종료
        if 'chrome_process' in locals() and chrome_process is not None:
            try:
                chrome_process.terminate()
                print("Chrome 프로세스 종료 완료.")
            except Exception as e:
                print(f"Chrome 프로세스 종료 중 오류: {e}")

if __name__ == "__main__":
    main()
