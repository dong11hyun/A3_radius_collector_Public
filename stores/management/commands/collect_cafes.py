import requests
import time
from django.core.management.base import BaseCommand
from django.conf import settings
from stores.models import NearbyStore
from django.contrib.gis.geos import Point

class Command(BaseCommand):
    help = '다이소 지점 좌표를 기반으로 주변 상권 데이터를 수집합니다.'

    def handle(self, *args, **kwargs):
        KAKAO_API_KEY = getattr(settings, 'KAKAO_API_KEY', None)
        if not KAKAO_API_KEY:
            self.stdout.write(self.style.ERROR("API 키가 없습니다."))
            return

        HEADERS = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}

        #  [핵심 변경] 검색하지 말고, 좌표를 직접 입력합니다. (실패 확률 0%)
        # x: 경도(Longitude), y: 위도(Latitude)
        DAISO_TARGETS = [
            {"name": "다이소 강남본점", "x": "127.028726", "y": "37.498000"},
            {"name": "다이소 홍대2호점", "x": "126.924466", "y": "37.555546"},
            {"name": "다이소 부산서면점", "x": "129.059483", "y": "35.155336"},
            {"name": "다이소 대전둔산점", "x": "127.377063", "y": "36.351783"},
        ]

        TARGET_CATEGORIES = {"CS2": "편의점", "MT1": "대형마트", "CE7": "카페"}

        self.stdout.write(self.style.WARNING(f"🚀 총 {len(DAISO_TARGETS)}개 지점 분석 시작 (좌표 기반)"))

        total_new_saved = 0

        for daiso in DAISO_TARGETS:
            daiso_name = daiso["name"]
            daiso_x = daiso["x"]
            daiso_y = daiso["y"]

            self.stdout.write(f"\n🏢 [분석 중] {daiso_name}")
            self.stdout.write(f"   📍 좌표 확인: {daiso_y}, {daiso_x}") # 디버깅용 로그 추가

            for cat_code, cat_name in TARGET_CATEGORIES.items():
                url = "https://dapi.kakao.com/v2/local/search/category.json"
                params = {
                    "category_group_code": cat_code,
                    "x": daiso_x,
                    "y": daiso_y,
                    "radius": 1000, 
                    "size": 15
                }

                try:
                    resp = requests.get(url, headers=HEADERS, params=params)
                    if resp.status_code != 200:
                        self.stdout.write(self.style.ERROR(f"   ❌ API 요청 실패: {resp.status_code}"))
                        continue
                    
                    documents = resp.json().get('documents', [])
                    
                    # 로그 개선: "찾은 개수"와 "저장한 개수"를 분리해서 출력
                    found_count = len(documents)
                    new_saved_count = 0

                    for item in documents:
                        # 중복 체크 (이름 + 주소가 같으면 패스)
                        if not NearbyStore.objects.filter(
                            name=item['place_name'], 
                            address=item['road_address_name']
                        ).exists():
                            
                            point = Point(float(item['x']), float(item['y']))
                            
                            NearbyStore.objects.create(
                                base_daiso=daiso_name,
                                name=item['place_name'],
                                category=cat_name,
                                address=item['road_address_name'],
                                phone=item['phone'],
                                distance=int(item['distance']),
                                location=point
                            )
                            new_saved_count += 1
                            total_new_saved += 1
                    
                    #  여기서 "0개 저장됨(이미 있음)" 인지 "0개 발견됨(검색실패)" 인지 구분 가능
                    if found_count > 0:
                        msg = f"   - {cat_name}: {found_count}개 발견 -> {new_saved_count}개 신규 저장"
                        if new_saved_count == 0:
                            msg += " (모두 이미 DB에 있음)"
                        print(msg)
                    else:
                        print(f"   - {cat_name}: 검색 결과 없음 (0개 발견)")

                    time.sleep(0.2) # API 제한 고려

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"   ❌ 에러: {e}"))

        self.stdout.write(self.style.SUCCESS(f"\n🎉 작업 완료! 총 {total_new_saved}개가 새로 저장되었습니다."))