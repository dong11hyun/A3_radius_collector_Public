# 🏪 다이소 상권 분석 프로젝트 (Daiso Research)

이 프로젝트는 **중소기업벤처부 리서치**를 위해 개발된 Django 기반 데이터 수집 서비스입니다.
카카오맵 API를 활용하여 다이소 지점 주변(반경 1km~5km)의 경쟁 매장(카페, 편의점 등) 데이터를 수집하고 분석합니다.

---

## 1. 개발 환경 (Tech Stack)

* **Language:** Python 3.10+
* **Framework:** Django
* **API:** Kakao Maps REST API
* **Data Processing:** Pandas, OpenPyXL

---

## 2. 설치 및 환경 설정 (Installation)

이 프로젝트를 실행하기 위해서는 Python이 설치되어 있어야 합니다.

### 2.1 가상환경 생성 및 활성화

프로젝트 폴더에서 터미널을 열고 가상환경을 생성합니다.

**Windows:**
```bash
python -m venv venv
가상환경
.\venv\Scripts\activate

가상환경이 켜진 상태(괄호로 (venv)가 보이는 상태)에서 패키지를 설치합니다.

Bash

pip install -r requirements.txt


+ env
+ python manage.py migrate
+ python manage.py createsuperuser