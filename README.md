# 🏪 Radius Collector: 편의점 폐업 검증 시스템

> **"API 한계를 넘어, 신뢰할 수 있는 상권 데이터를 만들다"**  
> 카카오맵 데이터의 정확성을 공공데이터와 교차 검증하여 폐업 매장을 자동 탐지하는 시스템

![Map Result](https://github.com/user-attachments/assets/placeholder)

## 🎯 프로젝트 개요

**문제 인식**: 카카오맵에 등록된 편의점들이 실제로 영업 중인지 확인할 방법이 없음

**해결 방안**: 3가지 공공데이터(휴게음식점 인허가, 담배소매업 인허가, 소상공인 상권정보)와 교차 검증하여 폐업 추정 매장 자동 탐지

| 수집 대상 | 결과 |
|-----------|------|
| 영등포구 다이소 | 16개 매장 |
| 반경 내 편의점 | 463개 |
| ✅ 정상 영업 | 452개 |
| 🔴 폐업 추정 | 11개 |

---

## 🔧 기술 스택

| 분류 | 기술 | 선택 이유 |
|------|------|-----------|
| **Backend** | Django 5.2, Python 3.x | Management Command 기반 데이터 파이프라인 |
| **Database** | PostgreSQL + PostGIS | 공간 쿼리 및 좌표 기반 검색 최적화 |
| **Infra** | Docker Compose | DB 및 앱 컨테이너화, 일관된 개발 환경 |
| **API** | Kakao Local API, 서울시 OpenAPI, 다이소 내부 API | 데이터 수집 및 좌표 보완 |
| **Frontend** | Kakao Maps JS API | 지도 시각화 (정상: 🔵 / 폐업: 🔴) |

---

## 🏗️ 시스템 아키텍처

```
[1단계: 데이터 수집]
┌─────────────────┐     ┌──────────────────────┐
│ 다이소 공식 API  │────▶│ YeongdeungpoDaiso    │ 16개
│ + 카카오 API    │     │ (좌표 보완)           │
└─────────────────┘     └──────────┬───────────┘
                                   │ 기준점
                                   ▼
┌─────────────────┐     ┌──────────────────────┐
│ 카카오 API      │────▶│ YeongdeungpoConvenience│ 463개
│ (4분면 검색)    │     │                       │
└─────────────────┘     └──────────┬────────────┘
                                   │
[2단계: 교차 검증]                   ▼
┌─────────────────────────────────────────────────┐
│ 공공데이터 3종                                    │
│ ├─ 휴게음식점 인허가 (OpenAPI) - 310개 편의점     │
│ ├─ 담배소매업 인허가 (OpenAPI) - 1,034개          │
│ └─ 소상공인 상권정보 (CSV) - 504개                │
└────────────────────────┬────────────────────────┘
                         │ OR 조건 매칭
                         │ (이름/주소/좌표)
                         ▼
[3단계: 결과]    ┌──────────────────────┐
                │ StoreClosureResult   │
                │ 정상: 452 / 폐업: 11  │
                └──────────┬───────────┘
                           ▼
                    [카카오맵 시각화]
```

---

## 💡 핵심 트러블슈팅

### 1. API 45개 제한 돌파 — 4분면 분할 검색

**문제**: 카카오 API는 검색 결과 최대 45개(15개×3페이지)만 반환  
**해결**: 검색 영역을 4분면으로 분할하여 각각 45개씩 수집

```python
# 중심점 기준 4분면으로 분할
quadrants = [
    (center_lat + offset, center_lng + offset),  # NE
    (center_lat + offset, center_lng - offset),  # NW
    (center_lat - offset, center_lng + offset),  # SE
    (center_lat - offset, center_lng - offset),  # SW
]
```

### 2. 신규 매장 누락 — 다이소 공식 API 발견

**문제**: 카카오 API에서 신규 오픈 매장(다이소 신길점) 검색 불가  
**해결**: 다이소 공식 사이트의 내부 API 엔드포인트 발견 및 활용

```python
# 다이소 공식 API 엔드포인트 (네트워크 분석으로 발견)
url = "https://fapi.daisomall.co.kr/ms/msg/selStr"
payload = {"keyword": "영등포", "pageSize": 100}
```

### 3. 좌표계 불일치 — EPSG 변환

**문제**: 서울시 OpenAPI는 TM좌표(EPSG:5174), 카카오는 WGS84(EPSG:4326) 사용  
**해결**: pyproj 라이브러리로 좌표계 변환

```python
from pyproj import Transformer
transformer = Transformer.from_crs("EPSG:5174", "EPSG:4326", always_xy=True)
lon, lat = transformer.transform(x, y)
```

### 4. 데이터 신뢰성 — 정적 vs 동적 데이터

**문제**: CSV(정적 데이터)만으로는 최신 영업 상태 반영 불가  
**해결**: OpenAPI(동적 데이터) 추가 확보하여 3중 교차 검증

---

## 🚀 실행 가이드

### 환경 설정

```bash
# 1. 환경변수 설정 (.env)
KAKAO_API_KEY=your_kakao_rest_api_key
KAKAO_JS_KEY=your_kakao_js_key
SEOUL_OPENAPI_KEY=your_seoul_openapi_key

# 2. Docker 실행
docker compose up -d
docker compose exec web python manage.py migrate
```

### 데이터 수집 및 분석

```bash
# 1단계: 다이소 + 편의점 수집
docker compose exec web python manage.py v2_3_1_collect_yeongdeungpo_daiso
docker compose exec web python manage.py v2_3_2_collect_Convenience_Only

# 2단계: 공공데이터 수집
docker compose exec web python manage.py openapi_1  # 휴게음식점
docker compose exec web python manage.py openapi_2  # 담배소매업

# 3단계: 폐업 분석 + 시각화
docker compose exec web python manage.py check_store_closure
# 결과 확인: http://127.0.0.1:8000/store-closure/
```

---

## 📁 프로젝트 구조

```
├── stores/
│   ├── management/commands/     # 데이터 수집 커맨드
│   │   ├── v2_3_1_collect_yeongdeungpo_daiso.py  # 다이소 수집
│   │   ├── v2_3_2_collect_Convenience_Only.py    # 편의점 수집
│   │   ├── openapi_1.py         # 휴게음식점 인허가
│   │   ├── openapi_2.py         # 담배소매업 인허가
│   │   └── check_store_closure.py  # 폐업 판별
│   ├── templates/
│   │   └── store_closure_map.html  # 카카오맵 시각화
│   └── models.py                # DB 모델 정의
├── public_data.csv              # 소상공인 상권정보
├── docker-compose.yml
└── requirements.txt
```

---

## 📊 결과 요약

| 검증 항목 | 결과 |
|-----------|------|
| 카카오맵 편의점 | 463개 |
| 공공데이터 교차 확인 (정상) | 452개 (97.6%) |
| **폐업 추정** | **11개 (2.4%)** |

> 폐업 추정 매장: 3가지 공공데이터 어디에서도 확인되지 않은 매장

---

## 🎓 회고

1. **데이터 품질이 도구보다 중요하다**  
   구글 BigQuery(OSM지도 데이터)보다 Kakao API의 한국 내 데이터가 훨씬 정확

2. **API 한계는 알고리즘으로 극복한다**  
   45개 제한 → Divide & Conquer(지역/4분면 분할)로 전수 조사 달성

3. **단일 소스의 한계는 교차 검증으로 보완한다**  
   API 데이터의 신뢰성을 **공공데이터 3종** 으로 검증

---

**프로젝트 기간**: 2025.11 ~ 2026.01  
**Author**: DaewonJeon
