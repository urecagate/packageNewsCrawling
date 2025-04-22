# site2_scraper.py
import time
from selenium.webdriver.common.by import By
from utils import close_popups
from utils import close_popups, dt, gettz
def scrape_site2(driver):
    """
    Canmaker는 유료 구독 사이트이므로 스크래핑 대상에서 제외합니다.
    따라서 빈 리스트를 반환합니다.
    """
    print("Canmaker는 유료 구독 사이트이므로 스크래핑을 건너뜁니다.")
    return []
