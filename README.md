# Google Search API 뉴스 크롤링

이 프로젝트는 Google Search API를 활용하여 특정 키워드에 대한 뉴스 기사를 수집, 분석하고 평가하는 기능을 제공합니다.

## 기능 개요

- Google Custom Search API를 사용하여 뉴스 기사 검색
- 특정 키워드에 대한 최신 뉴스 기사 수집
- 기사 내용 추출 및 분석
- AI 평가를 통한 관련성 높은 기사 필터링

## 설치 방법

1. 필요한 패키지 설치:
```bash
pip install requests beautifulsoup4 selenium newspaper3k python-dateutil
```

2. Google Custom Search API 설정:
   - [Google Cloud Console](https://console.cloud.google.com/)에서 새 프로젝트 생성
   - [API 라이브러리](https://console.cloud.google.com/apis/library)에서 Custom Search API 활성화
   - [사용자 인증 정보](https://console.cloud.google.com/apis/credentials)에서 API 키 생성
   - [Programmable Search Engine](https://programmablesearchengine.google.com/about/)에서 검색 엔진 생성하고 검색 엔진 ID(cx) 받기

3. 환경 변수 설정:
```bash
export GOOGLE_API_KEY="YOUR_API_KEY"
export GOOGLE_SEARCH_ENGINE_ID="YOUR_SEARCH_ENGINE_ID"
export ARTICLE_LIMIT=30  # 수집할 최대 기사 수
export MIN_ARTICLE_SCORE=5.0  # 최소 평가 점수
export PER_KEYWORD_LIMIT=10  # 키워드당 최대 기사 수
```

## 사용 방법

### 기존 코드와의 통합

기존의 `scrape_keyword_search_articles` 함수 대신 `search_api_news_articles` 함수를 사용하려면:

```python
# 기존 임포트 유지
from utils import create_driver_debug, build_and_send_email

# 새 함수 임포트
from google_api_search import search_api_news_articles

# 크롬 드라이버 초기화
driver = create_driver_debug()

try:
    # API를 사용하여 기사 수집 (기존 스크래핑 함수를 대체)
    valid_articles = search_api_news_articles(driver)
    
    # 수집된 기사로 이메일 작성 및 발송
    if valid_articles:
        build_and_send_email(valid_articles)
    else:
        print("수집된 유효 기사가 없습니다.")
        
finally:
    # 드라이버 종료
    driver.quit()
```

## API 사용 제한 및 주의사항

- Google Custom Search API는 일일 사용량 제한이 있습니다 (무료 계정: 100회/일)
- 과도한 요청은 API 할당량을 초과할 수 있으므로 호출 간격을 적절히 조절하세요
- 상업적 용도로 사용 시 요금이 부과될 수 있습니다

## 기존 웹 크롤링과의 차이점

| 특성 | 웹 크롤링 | Google Search API |
|------|---------|------------------|
| 속도 | 느림 (페이지 로딩 필요) | 빠름 (직접 결과 반환) |
| 안정성 | HTML 구조 변경에 취약 | 안정적 API 인터페이스 |
| 제한 | 웹사이트 차단 위험 | API 사용 할당량 제한 |
| 비용 | 무료 | 일정 사용량 초과 시 유료 |
| 정확성 | 크롤링 패턴에 의존 | 구글 검색 알고리즘 활용 |

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 