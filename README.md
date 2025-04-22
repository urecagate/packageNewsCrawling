# 뉴스 크롤링 프로젝트

이 프로젝트는 다양한 뉴스 사이트에서 기사를 크롤링하는 파이썬 패키지입니다.

## 설치 방법

```bash
# 클론 후 설치
git clone [저장소 URL]
cd src_pack
pip install -r requirements.txt
```

## 사용 방법

```python
from src_pack import main

# 크롤링 실행
main.run_crawling()
```

## 구성 요소

- `main.py`: 메인 실행 파일
- `utils.py`: 유틸리티 함수 모음
- `config.py`: 설정 파일
- `scrapers/`: 각 사이트별 크롤러 모듈

## 라이센스

MIT 