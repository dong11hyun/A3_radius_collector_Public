from django.shortcuts import render
from django.conf import settings
from .models import NearbyStore
import json

def map_view(request):
    stores = NearbyStore.objects.all()
    
    # 자바스크립트에서 쓰기 편하게 리스트로 변환
    store_list = []
    for store in stores:
        store_list.append({
            'name': store.name,
            'lat': store.lat,
            'lng': store.lng,
            'category': store.base_daiso  # 혹은 다른 카테고리 정보
        })

    context = {
        'store_json': json.dumps(store_list), # JSON 형태로 변환해서 전달
        'kakao_js_key': settings.KAKAO_JS_KEY,
    }
    return render(request, 'map.html', context)