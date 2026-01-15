from django.shortcuts import render
from django.conf import settings
from .models import NearbyStore
import json

def map_view(request):
    # 1. DB에서 데이터 가져오기
    stores = NearbyStore.objects.all()

    # 2. JSON 변환을 위한 리스트 만들기
    stores_list = []
    for store in stores:
        stores_list.append({
            'name': store.name,
            'lat': store.location.y,  # PointField에서 위도 추출
            'lng': store.location.x,  # PointField에서 경도 추출
            'category': store.category,
        })

    # 3. 데이터 포장
    context = {
        # 자바스크립트로 보낼 데이터 (한글 깨짐 방지 처리)
        'stores_json': json.dumps(stores_list, ensure_ascii=False),
        # API 키를 settings.py에서 가져오거나, 여기에 직접 문자열로 넣어도 됨
        'kakao_js_key': settings.KAKAO_JS_KEY, 
    }
    
    return render(request, 'map.html', context)


def kakao_map_test(request):
    """카카오 지도 마커 테스트 뷰"""
    return render(request, 'kakao_map_test.html')