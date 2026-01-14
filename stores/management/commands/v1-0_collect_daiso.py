import requests
import time
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from stores.models import DaisoStore

class Command(BaseCommand):
    help = '서울 25개 구를 순회하며 모든 다이소 정보를 수집합니다.'

    def handle(self, *args, **options):
        # 1. API 키 설정 (본인의 키로 변경 필수!)
        KAKAO_API_KEY = ''
        headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
        
        # 2. 서울의 25개 구 리스트
        seoul_gu_list = [
            "강남구", "강동구", "강북구", "강서구", "관악구", "광진구", "구로구", "금천구",
            "노원구", "도봉구", "동대문구", "동작구", "마포구", "서대문구", "서초구", "성동구",
            "성북구", "송파구", "양천구", "영등포구", "용산구", "은평구", "종로구", "중구", "중랑구"
        ]

        total_collected = 0
        url = "https://dapi.kakao.com/v2/local/search/keyword.json"

        # 3. 구 별로 반복 (예: 서울 강남구 다이소 -> 서울 강동구 다이소 ...)
        for gu in seoul_gu_list:
            query = f"서울 {gu} 다이소"
            self.stdout.write(self.style.WARNING(f"--- 검색 시작: {query} ---"))
            
            page = 1
            while True:
                params = {
                    "query": query,
                    "page": page,
                    "size": 15,  # 최대 15개
                }

                try:
                    response = requests.get(url, headers=headers, params=params, timeout=5)
                    response.raise_for_status() # 200 OK가 아니면 에러 발생
                except requests.exceptions.RequestException as e:
                    self.stdout.write(self.style.ERROR(f"네트워크 오류: {e}"))
                    break

                data = response.json()
                documents = data.get('documents', [])
                meta = data.get('meta', {})

                if not documents:
                    break # 결과가 없으면 종료

                for item in documents:
                    # '다이소' 이름이 포함된 것만 저장 (혹시나 이상한 가게 걸러내기)
                    if '다이소' not in item.get('place_name', ''):
                        continue

                    daiso_id = item.get('id')
                    name = item.get('place_name')
                    address = item.get('address_name') or item.get('road_address_name')
                    
                    # 좌표 변환
                    try:
                        lng = float(item.get('x'))
                        lat = float(item.get('y'))
                        point = Point(lng, lat)
                    except (ValueError, TypeError):
                        continue # 좌표 없으면 패스

                    # DB 저장 (중복 방지: daiso_id가 같으면 업데이트, 없으면 생성)
                    store, created = DaisoStore.objects.update_or_create(
                        daiso_id=daiso_id,
                        defaults={
                            'name': name,
                            'address': address,
                            'location': point,
                        }
                    )
                    
                    action = "생성" if created else "업데이트"
                    # 너무 시끄러우면 아래 출력문은 주석 처리 가능
                    # self.stdout.write(f"[{gu}] {name} - {action}")
                    total_collected += 1

                # 4. 다음 페이지 확인 (is_end가 True면 마지막 페이지)
                if meta.get('is_end'):
                    break
                
                page += 1
                time.sleep(0.5) # 카카오 API 도배 방지용 딜레이

        self.stdout.write(self.style.SUCCESS(f"총 {total_collected}개의 데이터 처리가 완료되었습니다."))