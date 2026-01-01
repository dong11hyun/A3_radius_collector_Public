# 1. 파이썬 베이스 이미지 사용 (버전은 로컬과 맞추는 게 좋음, 예: 3.10)
FROM python:3.10-slim

# 2. 작업 디렉토리 설정
WORKDIR /app

#  (GDAL 및 관련 라이브러리 설치)
RUN apt-get update && apt-get install -y \
    binutils \
    libproj-dev \
    gdal-bin \
    && rm -rf /var/lib/apt/lists/*

# 3. 환경 변수 설정 (파이썬 버퍼링 비활성화 등)
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 4. 의존성 설치
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# 5. 프로젝트 코드 복사
COPY . /app/

# 6. 서버 실행 명령어 (0.0.0.0으로 열어야 외부에서 접속 가능)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]