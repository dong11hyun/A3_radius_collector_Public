# stores/management/commands/collect_cafes.py

import requests
from django.core.management.base import BaseCommand
from stores.models import NearbyStore

class Command(BaseCommand):
    help = '카카오 API를 이용해 다이소 주변 카페 데이터를 수집합니다.'

    def handle(self, *args, **kwargs):
        # ==========================================
        # 1. 설정 (깃허브 올릴 땐 키를 지우세요!)
        # ==========================================
        KAKAO_API_KEY = ""    # 업로드 시 무조건 삭제
        HEADERS = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
        
        TARGET_NAME = "다이소 강남본점" # 원하는 지점으로 변경 가능
        
        # ==========================================
        # 2. 로직 시작
        # ==========================================
        
        # (1) 다이소 좌표 찾기
        self.stdout.write(f"🔍 '{TARGET_NAME}' 위치를 찾는 중...")
        url_loc = "https://dapi.kakao.com/v2/local/search/keyword.json"
        params_loc = {"query": TARGET_NAME}
        resp_loc = requests.get(url_loc, headers=HEADERS, params=params_loc)
        
        if not resp_loc.json()['documents']:
            self.stdout.write(self.style.ERROR('❌ 다이소 위치를 못 찾았습니다.'))
            return

        place = resp_loc.json()['documents'][0]
        x, y = place['x'], place['y']
        
        # (2) 주변 카페 검색 (반경 1km = 1000m)
        self.stdout.write(f"☕ 반경 1km 내 카페를 검색합니다...")
        url_cat = "https://dapi.kakao.com/v2/local/search/category.json"
        params_cat = {
            "category_group_code": "CE7", # 카페 코드
            "x": x,
            "y": y,
            "radius": 1000,
            "sort": "distance",
            "size": 15  # 테스트용 15개
        }
        
        resp_cat = requests.get(url_cat, headers=HEADERS, params=params_cat)
        cafes = resp_cat.json()['documents']
        
        # (3) DB에 저장
        count = 0
        for cafe in cafes:
            # 중복 방지 (이미 있는 가게면 저장 안 함)
            if not NearbyStore.objects.filter(name=cafe['place_name'], address=cafe['road_address_name']).exists():
                NearbyStore.objects.create(
                    base_daiso=TARGET_NAME,
                    name=cafe['place_name'],
                    address=cafe['road_address_name'],
                    phone=cafe['phone'],
                    distance=int(cafe['distance'])
                )
                count += 1
        
        self.stdout.write(self.style.SUCCESS(f'✅ 총 {count}개의 새로운 카페 데이터가 저장되었습니다!'))