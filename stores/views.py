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


def matched_stores_map(request):
    """교차 매칭된 편의점 데이터를 카카오맵에 표시"""
    import os
    import pandas as pd
    
    # CSV 파일 경로 (프로젝트 루트의 matched_stores_unique.csv)
    csv_path = os.path.join(settings.BASE_DIR, 'matched_stores_unique.csv')
    
    stores_list = []
    store_count = 0
    
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path, encoding='utf-8-sig')
        store_count = len(df)
        
        for _, row in df.iterrows():
            # 위도/경도가 있는 경우만 추가
            if pd.notna(row['위도']) and pd.notna(row['경도']):
                stores_list.append({
                    'name': row['이름'],
                    'address': row['주소'],
                    'lat': float(row['위도']),
                    'lng': float(row['경도']),
                    'source': row['출처'],
                    'match_reason': row['매칭이유']
                })
    
    context = {
        'stores_json': json.dumps(stores_list, ensure_ascii=False),
        'kakao_js_key': settings.KAKAO_JS_KEY,
        'store_count': store_count,
    }
    
    return render(request, 'matched_stores_map.html', context)