# google_api_search.py
import os
import time
import json
import requests
from urllib.parse import urlparse
from datetime import datetime, timedelta
from dateutil.tz import gettz
from bs4 import BeautifulSoup

# utils.py에서 필요한 함수들 임포트
from utils import (
    get_article_text, 
    filter_articles_by_evaluation, 
    balance_articles_by_keyword,
    split_html_into_top_level_tags,
    split_body_html_into_tags
)

# 환경 변수에서 기사 개수 제한 가져오기
DEFAULT_ARTICLE_LIMIT = 30  # 기본값
ARTICLE_LIMIT = int(os.environ.get("ARTICLE_LIMIT", DEFAULT_ARTICLE_LIMIT))
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

def get_yesterday_date_string(format="%Y-%m-%d"):
    """
    한국 시간(Asia/Seoul) 기준 어제 날짜를 계산하여 반환합니다.
    
    Args:
        format (str): 날짜 포맷 스트링 (기본값: "%Y-%m-%d")
        
    Returns:
        str: 지정된 포맷의 어제 날짜 문자열
    """
    yesterday = datetime.now(gettz("Asia/Seoul")) - timedelta(days=1)
    return yesterday.strftime(format)

def search_api_news_articles(driver):
    """
    구글 검색 API를 사용하여 키워드별 뉴스 기사를 수집하고 분석합니다.
    
    Args:
        driver: Selenium 웹드라이버 객체
        
    Returns:
        list: 평가된 유효 기사 목록
    """
    collected_articles = []
    
    # API 키와 검색 엔진 ID (CSE ID) 환경 변수에서 가져오기
    api_key = os.environ.get("GOOGLE_API_KEY")
    search_engine_id = os.environ.get("GOOGLE_SEARCH_ENGINE_ID")
    
    if not api_key or not search_engine_id:
        print("[오류] 환경 변수 GOOGLE_API_KEY와 GOOGLE_SEARCH_ENGINE_ID가 설정되어 있지 않습니다.")
        print("다음 명령으로 환경 변수를 설정하세요:")
        print('export GOOGLE_API_KEY="YOUR_API_KEY"')
        print('export GOOGLE_SEARCH_ENGINE_ID="YOUR_SEARCH_ENGINE_ID"')
        return []
    
    # 어제 날짜 문자열 계산
    yesterday_str = get_yesterday_date_string()
    day_before_str = (datetime.now(gettz("Asia/Seoul")) - timedelta(days=2)).strftime("%Y-%m-%d")
    
    # 디버그 모드 여부에 따른 키워드 설정
    if DEBUG_MODE:
        keywords = [
            "Beer Market", "Soju Market", "Korean rice wine Market", "Beverage Market",
            "Bottled Water Company", "Carbonated Beverage", "Sparkling Water", 
            "Children Beverage", "Sports Drink", "RTD Coffee", "Engery Drink",
            "Health Tonic", "Aseptic", "RTD Beverage", "Hangover Cure"
        ]
    else:
        keywords = [
            "Beer Market", "Soju Market", "Korean rice wine Market", "Beverage Market",
            "Bottled Water Company", "Carbonated Beverage", "Sparkling Water", 
            "Children Beverage", "Sports Drink", "RTD Coffee", "Engery Drink",
            "Health Tonic", "Aseptic", "RTD Beverage", "Hangover Cure"
        ]
    
    excluded_domains = [
        "chosun.com", "koreatimes.co.kr", "mk.co.kr",
        "koreaherald.com", "koreajoongangdaily.joins.com", "businesskorea.co.kr"
    ]
    
    total_articles_found = 0
    total_excluded = 0
    
    # --- 1. 구글 검색 API를 사용하여 검색 결과 수집 ---
    for keyword in keywords:
        print(f"\n[키워드: {keyword}] 검색 시작")
        
        # Google Custom Search API 설정
        # 특정 날짜 범위 지정은 API에서 직접 지원하지 않으므로 검색어에 날짜 포함
        search_query = f"{keyword} after:{day_before_str} before:{yesterday_str}"
        start_index = 1  # 검색 결과 시작 인덱스
        max_results_per_keyword = 20  # 키워드당 최대 결과 수
        results_per_page = 10  # 한 번의 API 요청으로 가져올 결과 수
        
        keyword_found = 0
        keyword_collected = 0
        keyword_excluded = 0
        
        while start_index <= max_results_per_keyword:
            try:
                # Google Custom Search API 호출
                search_url = "https://www.googleapis.com/customsearch/v1"
                params = {
                    "key": api_key,
                    "cx": search_engine_id,
                    "q": search_query,
                    "start": start_index,
                    "num": results_per_page,
                    "sort": "date:r:20230101:20301231",  # 날짜순 정렬 (최신순)
                }
                
                response = requests.get(search_url, params=params)
                
                if response.status_code != 200:
                    print(f"  -> API 오류 (상태 코드: {response.status_code}): {response.text}")
                    break
                
                search_results = response.json()
                
                # 검색 결과가 있는지 확인
                if "items" not in search_results:
                    print(f"  -> 키워드 '{keyword}'에 대한 검색 결과가 없거나 모두 수집 완료")
                    break
                
                items = search_results["items"]
                
                # 검색 결과 처리
                for item in items:
                    keyword_found += 1
                    
                    url = item.get("link")
                    title = item.get("title", "제목 없음")
                    snippet = item.get("snippet", "요약 없음")
                    
                    # 제외 도메인 확인
                    domain = urlparse(url).netloc.lower()
                    if any(excl in domain for excl in excluded_domains):
                        keyword_excluded += 1
                        continue
                    
                    # 기사 정보 수집
                    formatted_date = item.get("pagemap", {}).get("metatags", [{}])[0].get("article:published_time")
                    if not formatted_date:
                        formatted_date = ""
                    
                    collected_articles.append({
                        "url": url,
                        "title": title,
                        "snippet": snippet,
                        "date": formatted_date,
                        "keyword": keyword
                    })
                    keyword_collected += 1
                
                total_articles_found += keyword_found
                total_excluded += keyword_excluded
                
                print(f"  -> [페이지 {(start_index-1)//results_per_page + 1}] 결과 {len(items)}개 중 {keyword_excluded}개 제외, {keyword_collected}개 수집")
                
                # 다음 페이지로 이동
                start_index += results_per_page
                
                # API 호출 간격 조절 (분당 요청 수 제한 고려)
                time.sleep(1)
                
            except Exception as e:
                print(f"  -> 검색 API 호출 중 오류 발생: {e}")
                break
    
    print(f"\nGoogle API 검색: 총 {total_articles_found}개 기사 중 {total_excluded}개 제외됨.")
    
    # 중복 제거 (URL 기준)
    unique_articles = {}
    for article in collected_articles:
        url = article.get("url")
        if url and url not in unique_articles:
            unique_articles[url] = article
        else:
            if url:
                print(f"중복 기사 제거: {url}")
    articles = list(unique_articles.values())
    
    # 환경 변수에서 키워드당 최대 기사 수 가져오기
    per_keyword_limit = int(os.environ.get("PER_KEYWORD_LIMIT", "10"))
    articles = balance_articles_by_keyword(articles, ARTICLE_LIMIT, per_keyword_limit)
    
    # --- 2. 각 기사에서 실제 기사 내용 추출 (newspaper3k + Selenium Fallback) ---
    valid_articles = []
    for art in articles:
        print(f"\n[기사 추출 시도] URL: {art['url']}")
        # newspaper3k를 사용하여 기사 내용 추출, 실패 시 Selenium Fallback 적용
        np_title, article_text, publish_date = get_article_text(art["url"], driver)
        if np_title == "제목 없음" or article_text == "본문 없음":
            print("  -> 기사 추출 실패 (newspaper3k 및 Selenium fallback 모두 실패):", art["url"])
            continue
        
        art["np_title"] = np_title
        art["article_text"] = article_text
        # 날짜 정보가 추출되었으면 문자열로 저장
        if publish_date and hasattr(publish_date, "strftime"):
            art["date"] = publish_date.strftime("%Y-%m-%d")
        
        # 추가적으로 기사 페이지의 HTML 전체를 가져와 최상위 태그와 <body> 내부 태그로 분할 (선택사항)
        try:
            driver.set_page_load_timeout(20)
            driver.get(art["url"])
            time.sleep(3)  # 페이지 로딩 대기
            full_html = driver.page_source
            # 전체 HTML을 "html" 키에 저장
            art["html"] = full_html
            art["html_top"] = split_html_into_top_level_tags(full_html)
            art["html_body"] = split_body_html_into_tags(full_html)
        except Exception as e:
            print(f"  -> 기사 HTML 수집 중 오류 ({art['url']}):", e)
            art["html_top"] = []
            art["html_body"] = []
            art["html"] = ""
        
        valid_articles.append(art)
    
    # 기사 평가 및 점수 기준 필터링 (환경 변수에서 가져온 값 사용)
    evaluated_articles = filter_articles_by_evaluation(valid_articles)
    
    return evaluated_articles 