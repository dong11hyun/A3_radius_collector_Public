# stores/management/commands/collect_cafes.py

import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from stores.models import NearbyStore

# 👇 이 줄이 없어서 에러가 난 겁니다! (지우지 마세요)
class Command(BaseCommand):
    help = '카카오 API를 이용해 다이소 주변 카페 데이터를 수집합니다.'

    def handle(self, *args, **kwargs):
        # ==========================================
        # 1. 설정 (키 입력 필수!)
        # ==========================================
        KAKAO_API_KEY = settings.KAKAO_API_KEY
        
        # 키가 없는 경우를 대비한 방어 코드
        if not KAKAO_API_KEY or "키를_여기에" in KAKAO_API_KEY:
             self.stdout.write(self.style.ERROR("❌ API 키가 입력되지 않았습니다! 코드를 열어 키를 입력해주세요."))
             return

        HEADERS = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
        TARGET_NAME = "다이소 강남본점"
        
        # ==========================================
        # 2. 로직 시작
        # ==========================================
        
        # (1) 다이소 좌표 찾기
        self.stdout.write(f"🔍 '{TARGET_NAME}' 위치를 찾는 중...")
        url_loc = "https://dapi.kakao.com/v2/local/search/keyword.json"
        params_loc = {"query": TARGET_NAME}
        
        try:
            resp_loc = requests.get(url_loc, headers=HEADERS, params=params_loc)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ 인터넷 연결 또는 요청 실패: {e}"))
            return

        # 에러 체크
        if resp_loc.status_code != 200:
            self.stdout.write(self.style.ERROR(f"❌ API 호출 실패! 상태 코드: {resp_loc.status_code}"))
            self.stdout.write(self.style.ERROR(f"❌ 내용: {resp_loc.json()}"))
            return
            
        if 'documents' not in resp_loc.json():
            self.stdout.write(self.style.ERROR(f"❌ 응답 형식 오류: {resp_loc.json()}"))
            return

        if not resp_loc.json()['documents']:
            self.stdout.write(self.style.ERROR('❌ 다이소 위치를 못 찾았습니다.'))
            return

        place = resp_loc.json()['documents'][0]
        x, y = place['x'], place['y']
        
        # (2) 주변 카페 검색 (반경 1km)
        self.stdout.write(f"☕ 반경 1km 내 카페를 검색합니다...")
        url_cat = "https://dapi.kakao.com/v2/local/search/category.json"
        params_cat = {
            "category_group_code": "CE7", 
            "x": x,
            "y": y,
            "radius": 1000,
            "sort": "distance",
            "size": 15
        }
        
        resp_cat = requests.get(url_cat, headers=HEADERS, params=params_cat)
        cafes = resp_cat.json().get('documents', [])
        
        # (3) DB에 저장
        count = 0
        for cafe in cafes:
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