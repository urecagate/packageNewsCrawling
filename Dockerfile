# Python 3.10.11-slim 이미지를 베이스로 사용
FROM python:3.10.11-slim

# Python 출력 버퍼링 해제
ENV PYTHONUNBUFFERED=1

# Headless Chrome 실행에 필요한 최소 라이브러리 설치
RUN apt-get update && apt-get install -y procps \
    libxrender1 libxi6 libgl1-mesa-glx libgl1-mesa-dri libgles2-mesa mesa-utils

# Chrome 실행에 필요한 패키지와 의존성 설치
# 아래는 일본어 폰트를 설치하는 부분입니다.
# fonts-nanum: 한글 폰트 설치, fonts-noto-cjk: 일본어 폰트 설치
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    curl \
    ca-certificates \
    fonts-liberation \
    fonts-nanum \
    fonts-noto-cjk \
    libasound2 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libgbm1 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxss1 \
    libxtst6 \
    libappindicator3-1 \
    libdbus-1-3 \
    libgconf-2-4 \
    libgtk-3-0 \
    xdg-utils \
    --no-install-recommends && rm -rf /var/lib/apt/lists/*

# Google Chrome 설치
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && apt-get install -y google-chrome-stable

# WeasyPrint가 동작하기 위한 의존 라이브러리 설치
RUN apt-get update && apt-get install -y \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    --no-install-recommends && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app

# 필요한 파일 복사
COPY . .

# 의존성 설치
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    pip install exchangelib google-api-python-client

# 컨테이너 실행 시 main.py 실행
CMD ["python", "main.py"]