import requests
import time
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from stores.models import DaisoStore, NearbyStore

class Command(BaseCommand):
    help = '수집된 다이소 지점을 기준으로 반경 1km 내 카페와 편의점을 사분면으로 나누어 수집합니다.'

    def handle(self, *args, **options):
        # [주의] 본인의 카카오 API REST KEY를 입력하세요
        KAKAO_API_KEY = '' 
        headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
        
        TARGET_CATEGORIES = ['CE7', 'CS2'] # CE7: 카페, CS2: 편의점
        
        daiso_list = DaisoStore.objects.all()
        total_daiso_count = daiso_list.count()
        
        self.stdout.write(self.style.SUCCESS(f"총 {total_daiso_count}개의 다이소 지점에 대해 수집을 시작합니다."))

        # 1km 근사치
        DELTA_LAT = 0.0090  
        DELTA_LNG = 0.0113 

        for idx, daiso in enumerate(daiso_list, 1):
            if not daiso.location:
                continue

            cx = daiso.location.x # 경도 (Center X)
            cy = daiso.location.y # 위도 (Center Y)

            self.stdout.write(f"[{idx}/{total_daiso_count}] '{daiso.name}' 주변 탐색 중...")

            # 사분면 좌표 생성 (소수점 6자리 제한)
            quadrants = [
                # 1사분면 (우상)
                f"{cx:.6f},{cy:.6f},{(cx + DELTA_LNG):.6f},{(cy + DELTA_LAT):.6f}",
                # 2사분면 (좌상)
                f"{(cx - DELTA_LNG):.6f},{cy:.6f},{cx:.6f},{(cy + DELTA_LAT):.6f}",
                # 3사분면 (좌하)
                f"{(cx - DELTA_LNG):.6f},{(cy - DELTA_LAT):.6f},{cx:.6f},{cy:.6f}",
                # 4사분면 (우하)
                f"{cx:.6f},{(cy - DELTA_LAT):.6f},{(cx + DELTA_LNG):.6f},{cy:.6f}"
            ]

            stored_count = 0

            for category_code in TARGET_CATEGORIES:
                for rect in quadrants:
                    url = "https://dapi.kakao.com/v2/local/search/category.json"
                    page = 1
                    
                    while True:
                        # [핵심 수정] sort='distance'를 쓰려면 x, y가 필수입니다!
                        params = {
                            "category_group_code": category_code,
                            "rect": rect,
                            "x": f"{cx:.6f}",  # 거리 계산의 기준점 X (다이소 경도)
                            "y": f"{cy:.6f}",  # 거리 계산의 기준점 Y (다이소 위도)
                            "page": page,
                            "size": 15,
                            "sort": "distance" # 거리순 정렬
                        }

                        try:
                            response = requests.get(url, headers=headers, params=params, timeout=5)
                            
                            if response.status_code == 400:
                                # 여전히 400이면 파라미터 조합 문제일 수 있으니 로그 출력
                                self.stdout.write(self.style.ERROR(f"API 400 에러: {response.text}"))
                                break
                                
                            response.raise_for_status()
                            data = response.json()
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"API 요청 실패: {e}"))
                            break

                        documents = data.get('documents', [])
                        
                        if not documents:
                            break

                        for item in documents:
                            try:
                                lng = float(item.get('x'))
                                lat = float(item.get('y'))
                                point = Point(lng, lat)
                                dist = int(item.get('distance', 0))
                                
                                # [핵심 수정] 카카오의 고유 ID(item.get('id'))를 기준으로 중복 검사
                                # 나머지는 모두 defaults(업데이트 대상)로 넣습니다.
                                NearbyStore.objects.update_or_create(
                                    place_id=item.get('id'), # 고유 ID를 기준값으로 설정
                                    defaults={
                                        'name': item.get('place_name'),
                                        'address': item.get('road_address_name') or item.get('address_name'),
                                        'phone': item.get('phone'),
                                        'category': item.get('category_group_name'),
                                        'location': point,
                                        'distance': dist, # 가장 마지막에 검색된 거리로 갱신됨
                                        'base_daiso': daiso.name # 이 가게가 발견된 다이소 이름 (덮어쓰기 됨)
                                    }
                                )
                                stored_count += 1
                            except Exception as e:
                                self.stdout.write(self.style.ERROR(f"저장 실패: {e}"))
                                continue

                        if data.get('meta', {}).get('is_end'):
                            break
                        
                        page += 1
                        if page > 3: 
                            break
                        
                        time.sleep(0.2) 

            # self.stdout.write(f"  -> {stored_count}개 저장 완료")
            time.sleep(0.3) 

        self.stdout.write(self.style.SUCCESS("모든 수집이 완료되었습니다."))