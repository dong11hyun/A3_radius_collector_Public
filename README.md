#  Radius Collector: 편의점 폐업 검증 

> **"API 한계를 넘어, 신뢰할 수 있는 상권 데이터를 만들다"**  
> 카카오맵 데이터의 정확성을 공공데이터와 교차 검증하여 폐업 매장을 자동 탐지하는 시스템

![Map Result](map_result.png)


**문제 인식**: 카카오맵에 등록된 편의점들이 실제로 영업 중인지 확인할 방법이 없음

**해결 방안**: 3가지 공공데이터(휴게음식점 인허가, 담배소매업 인허가, 소상공인 상권정보)와 교차 검증하여 폐업 추정 매장 자동 탐지

---

## 🤔기술 스택 & 아키텍처 

| 분류 | 기술 |
|------|------|
| **Backend** | Django 5.2, Python 3.x |
| **Database** | PostgreSQL + PostGIS |
| **Infra** | Docker Compose | 
| **API** | Kakao Local API, 서울시 OpenAPI, 다이소 내부 API | 
| **Frontend** | Kakao Maps JS API | 


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
[2단계: 교차 검증]                  ▼
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
------------------------------------------------------

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

##  핵심 트러블슈팅

### 1. API 45개 제한 돌파 — 4분면 분할 검색

**문제**: 카카오 API는 반경 검색 시 최대 45개(15개×3페이지)만 반환  

**왜 다이소가 기준점인가?**
- 다이소는 영등포구 내에 **가장 이상적인 분포**로 존재 (16개 매장)
- 각 다이소를 중심으로 **1.3km 사각형** 검색 시 영등포구 전체 커버 가능

**왜 4분면인가?**
- 각 다이소 기준 1.3km 영역을 **4분면으로 분할**
- 각 사각형 내 편의점 수가 **45개 미만**이 되도록 설계
- 4개 영역 검색 → 중복 제거 → 전수 조사 달성

```python
# 다이소 중심점 기준 4분면 분할 (1.3km 커버)
quadrants = [
    (center_lat + offset, center_lng + offset),  # NE (북동)
    (center_lat + offset, center_lng - offset),  # NW (북서)
    (center_lat - offset, center_lng + offset),  # SE (남동)
    (center_lat - offset, center_lng - offset),  # SW (남서)
]
# 결과: 16개 다이소 × 4분면 = 영등포구 전체 463개 편의점 수집
```

### 2. 신규 매장 누락 — 다이소 공식 API 리버스 엔지니어링

**문제**: 카카오 API에서 신규 오픈 매장(다이소 신길점) 검색 불가

**해결 과정:**
| 단계 | 작업 | 결과 |
|------|------|------|
| 1 | 다이소몰 매장찾기 페이지 접속 | `daisomall.co.kr/store` |
| 2 | 개발자도구(F12) → Network 탭 | 서버 요청 트리거 모니터링 |
| 3 | 검색 액션 시 트래픽 캡처 | JSON 응답 포함된 요청 식별 |
| 4 | 패킷 분석 | Endpoint, Method, Content-Type 명세 확보 |
| 5 | 필수 헤더/페이로드 식별 | `Referer`, `Origin`, `keyword` 필드 확인 |

```python
# 최종 추출된 API 스펙
url = "https://fapi.daisomall.co.kr/ms/msg/selStr"
headers = {
    "Content-Type": "application/json",
    "Referer": "https://www.daisomall.co.kr/",
    "Origin": "https://www.daisomall.co.kr"
}
payload = {"keyword": "영등포", "pageSize": 100}
# 결과: 신길점 포함 16개 매장 전수 확보
```

### 3. 좌표계 불일치 — EPSG 변환

**문제**: 서울시 OpenAPI(TM좌표 EPSG:5174) ≠ 카카오(WGS84 EPSG:4326)  
**해결**: `pyproj` 라이브러리로 좌표 변환 후 소수점 4자리 반올림(오차 5~7m)

---

## 🫡 실행 가이드

#### 환경 설정

```bash
# 1. 환경변수 설정 (.env)
KAKAO_API_KEY=your_kakao_rest_api_key
KAKAO_JS_KEY=your_kakao_js_key
SEOUL_OPENAPI_KEY=your_seoul_openapi_key

# 2. Docker 실행
docker compose up -d
docker compose exec web python manage.py migrate
```

#### 데이터 수집 및 분석

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


## 📊 결과 요약

| 검증 항목 | 결과 |
|-----------|------|
| 카카오맵 편의점 | 463개 |
| 공공데이터 교차 확인 (정상) | 452개 (97.6%) |
| **폐업 추정** | **11개 (2.4%)** |

> 폐업 추정 매장: 3가지 공공데이터 어디에서도 확인되지 않은 매장

---

## 📈 버전별 개발 히스토리

> **"API 45개 제한을 어떻게 뛰어넘었는가?"** — 제약 사항이 만들어낸 창의적 해결책들

### v1.0 — MVP: 데이터 수집기
| 구분 | 내용 |
|------|------|
| **목표** | 카카오 API로 다이소 주변 상권 데이터 수집 |
| **문제** | Rate Limit(0.2초 딜레이 필요), 동기식 처리로 속도 저하 |
| **해결** | `time.sleep(0.2)` 적용, SQLite + CSV 저장 |
| **한계** | 페이지네이션 45개 제한 미인지 → 대량 데이터 누락 |

### v1.1 — 안정성 및 정합성 강화
| 구분 | 내용 |
|------|------|
| **문제 1** | 스크립트 재실행 시 DB 중복 적재 |
| **해결** | `update_or_create()` Upsert 로직 도입 |
| **문제 2** | Docker/Local DB 포트 충돌 (5432 동시 사용) |
| **해결** | Docker DB 포트를 5433으로 분리 |
| **발견** | API 45개 제한 확인 → 강남역 반경 100개+ 편의점 중 45개만 수집 |

### v2.0 — 공간 DB (PostGIS) 도입
| 구분 | 내용 |
|------|------|
| **목표** | 단순 주소 저장 → 위도/경도 좌표 기반 공간 분석 |
| **도입** | PostgreSQL + PostGIS, GeoDjango |
| **성과** | 웹 지도 시각화 (`/map/`), 공간 쿼리 성능 확보 |
| **한계** | 45개 제한 미해결 → 밀집 지역 데이터 여전히 누락 |

### v2.1 — BigQuery 실험 (실패 → 교훈)
| 구분 | 내용 |
|------|------|
| **시도** | Google BigQuery + OSM 데이터로 API 제한 우회 |
| **결과** | 기술적으로는 성공, 데이터 품질은 실패 |
| **비교** | 서울 다이소: 실제 260개 vs OSM 60개 (75% 누락) |
| **교훈** | **"도구의 화려함보다 데이터의 정확도가 중요하다"** |
| **결정** | Kakao API + PostGIS 조합으로 회귀 |

### v2.3 — 최종 완성: 3중 검증 시스템
| 구분 | 내용 |
|------|------|
| **문제 1** | 카카오 API에서 신규 매장(다이소 신길점) 누락 |
| **해결** | 다이소 공식 API 엔드포인트 발견 (네트워크 분석) |
| **문제 2** | 반경 검색 45개 제한 |
| **해결** | 4분면 분할 전략 (Quadrant Search) |
| **문제 3** | CSV 정적 데이터만으로는 최신 상태 반영 불가 |
| **해결** | OpenAPI(동적) + CSV(정적) 3중 교차 검증 |
| **문제 4** | 서울시 OpenAPI 좌표계(EPSG:5174) ≠ 카카오(WGS84) |
| **해결** | `pyproj` 라이브러리로 좌표 변환 |

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
