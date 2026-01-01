import requests
import time
from django.core.management.base import BaseCommand
from django.conf import settings
from stores.models import NearbyStore
from django.contrib.gis.geos import Point  # ★ Point 객체 필수 임포트

class Command(BaseCommand):
    help = '여러 다이소 지점 주변의 다양한 상권(카페, 편의점, 마트 등) 데이터를 수집하여 PostGIS에 저장합니다.'

    def handle(self, *args, **kwargs):
        # ==========================================
        # 1. 설정 (API 키 가져오기)
        # ==========================================
        KAKAO_API_KEY = getattr(settings, 'KAKAO_API_KEY', None)

        # 방어 코드: 키가 없는 경우
        if not KAKAO_API_KEY:
            self.stdout.write(self.style.ERROR("❌ API 키가 설정되지 않았습니다! settings.py를 확인해주세요."))
            return

        HEADERS = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}

        # ==========================================
        # 2. 조사할 타겟 리스트
        # ==========================================
        DAISO_TARGETS = [
            "다이소 강남본점",
            "다이소 홍대2호점",
            "다이소 부산서면점",
            "다이소 대전둔산점",
            # 필요한 지점 계속 추가...
        ]

        # ==========================================
        # 3. 수집할 업종 리스트
        # ==========================================
        TARGET_CATEGORIES = {
            "CS2": "편의점",
            "MT1": "대형마트",
            "CE7": "카페"
        }

        self.stdout.write(self.style.WARNING(f"🚀 총 {len(DAISO_TARGETS)}개 다이소 지점 분석을 시작합니다... (PostGIS 저장)"))

        # ----------------------------------------------------
        # [Loop 1] 다이소 지점별 반복
        # ----------------------------------------------------
        total_saved = 0
        
        for daiso_name in DAISO_TARGETS:
            self.stdout.write(f"\n🏢 [분석 중] {daiso_name}")
            
            # (1) 다이소 위치 찾기
            url_loc = "https://dapi.kakao.com/v2/local/search/keyword.json"
            try:
                resp_loc = requests.get(url_loc, headers=HEADERS, params={"query": daiso_name})
                if not resp_loc.json()['documents']:
                    self.stdout.write(self.style.ERROR(f"   ❌ 위치를 찾을 수 없습니다: {daiso_name}"))
                    continue
                
                place = resp_loc.json()['documents'][0]
                daiso_x, daiso_y = place['x'], place['y'] # 중심점 좌표
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"   ❌ 에러 발생: {e}"))
                continue

            # ----------------------------------------------------
            # [Loop 2] 업종별 반복 (편의점 -> 마트 -> 카페)
            # ----------------------------------------------------
            for cat_code, cat_name in TARGET_CATEGORIES.items():
                
                url_cat = "https://dapi.kakao.com/v2/local/search/category.json"
                page = 1
                collected_count = 0
                
                # [Loop 3] 페이지 넘기기
                while page <= 3:
                    params_cat = {
                        "category_group_code": cat_code,
                        "x": daiso_x,
                        "y": daiso_y,
                        "radius": 1000, # 반경 1km
                        "sort": "distance",
                        "size": 15,
                        "page": page
                    }
                    
                    resp_cat = requests.get(url_cat, headers=HEADERS, params=params_cat)
                    if resp_cat.status_code != 200:
                        break
                        
                    documents = resp_cat.json().get('documents', [])
                    if not documents:
                        break
                    
                    # DB 저장
                    for item in documents:
                        # 중복 방지 체크
                        if not NearbyStore.objects.filter(name=item['place_name'], address=item['road_address_name']).exists():
                            
                            # ★ 핵심 변경 사항: Point 객체 생성
                            # item['x'] = 경도(Longitude), item['y'] = 위도(Latitude)
                            # 반드시 Point(경도, 위도) 순서로 넣어야 함!
                            point_location = Point(float(item['x']), float(item['y']))

                            NearbyStore.objects.create(
                                base_daiso=daiso_name,
                                name=item['place_name'],
                                category=cat_name,
                                address=item['road_address_name'],
                                phone=item['phone'],
                                distance=int(item['distance']),
                                location=point_location  # ★ 위도/경도 숫자 대신 Point 객체 저장
                            )
                            total_saved += 1
                            collected_count += 1

                    # 다음 페이지 확인
                    if resp_cat.json()['meta']['is_end']:
                        break
                    
                    page += 1
                    time.sleep(0.2) 

                print(f"      - {cat_name}: {collected_count}개 발견")

        self.stdout.write(self.style.SUCCESS(f"\n🎉 모든 작업 완료! 총 {total_saved}개의 데이터가 PostGIS에 저장되었습니다."))