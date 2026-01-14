# stores/views_closed.py
"""
폐업 의심 매장 관리 뷰
3가지 기능 구현:
1. 제보하기 - 카카오맵 등에 폐업 정보 제보
2. 새로운 맵 만들기 - 폐업 매장만 표시하는 전용 지도
3. 잘못된 데이터만 보기 - 폐업인데 영업으로 표시된 오류 데이터 필터링
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from django.contrib import messages
from stores.models import NearbyStore


def closed_stores_list(request):
    """
    폐업 의심 매장 목록 - 3가지 기능 선택 페이지
    
    실제 운영 시에는 ClosedButActiveStore 모델에서 데이터를 가져옵니다.
    현재는 NearbyStore를 사용하여 데모 목적으로 구현합니다.
    """
    # 데모: 편의점 데이터를 폐업 의심 목록으로 표시
    stores = NearbyStore.objects.filter(category='편의점').order_by('-created_at')[:50]
    
    context = {
        'stores': stores,
        'total': stores.count(),
        'verified': 0,
        'reported': 0,
    }
    
    return render(request, 'stores/closed_stores_list.html', context)


def closed_stores_map(request):
    """
    폐업 매장 전용 맵 (기능 2)
    폐업 의심 매장만 지도에 표시
    """
    stores = NearbyStore.objects.filter(category='편의점')
    
    stores_data = []
    for store in stores:
        if store.location:
            stores_data.append({
                'id': store.id,
                'name': store.name,
                'address': store.address,
                'lat': store.location.y,
                'lng': store.location.x,
                'base_daiso': store.base_daiso,
            })
    
    context = {
        'stores_data': stores_data,
        'total': len(stores_data),
    }
    
    return render(request, 'stores/closed_stores_map.html', context)


def error_data_only(request):
    """
    잘못된 데이터만 보기 (기능 3)
    폐업인데 카카오맵에 영업으로 나오는 데이터만 필터링
    
    실제 운영 시에는 ClosedButActiveStore 모델에서 verified=False인 데이터를 가져옵니다.
    """
    # 데모: 편의점 데이터 표시
    stores = NearbyStore.objects.filter(category='편의점').order_by('name')[:20]
    
    context = {
        'stores': stores,
        'total': stores.count(),
    }
    
    return render(request, 'stores/error_data_only.html', context)


def report_store(request, store_id):
    """
    매장 제보하기 (기능 1)
    카카오맵 등에 폐업 정보 제보
    """
    store = get_object_or_404(NearbyStore, id=store_id)
    
    if request.method == 'POST':
        note = request.POST.get('note', '')
        
        # 실제 운영 시에는 ClosedButActiveStore 모델 업데이트
        messages.success(request, f"'{store.name}' 매장이 제보되었습니다.")
        return redirect('closed_stores_list')
    
    # 카카오맵 제보 URL 생성
    kakao_map_url = f"https://map.kakao.com/link/map/{store.place_id}"
    
    context = {
        'store': store,
        'kakao_map_url': kakao_map_url,
    }
    
    return render(request, 'stores/report_store.html', context)


def verify_store(request, store_id):
    """
    매장 검증 처리 API
    AJAX 요청으로 호출
    """
    if request.method == 'POST':
        store = get_object_or_404(NearbyStore, id=store_id)
        
        # 실제 운영 시에는 ClosedButActiveStore 모델 업데이트
        return JsonResponse({
            'success': True,
            'message': f'{store.name} 검증 완료'
        })
    
    return JsonResponse({
        'success': False,
        'message': 'POST 요청만 허용'
    })


def convenience_stores_map(request):
    """
    영등포구 편의점 지도 (기존 map.html 확장)
    편의점만 표시하는 지도
    """
    stores = NearbyStore.objects.filter(category='편의점')
    
    stores_data = []
    for store in stores:
        if store.location:
            stores_data.append({
                'id': store.id,
                'name': store.name,
                'address': store.address,
                'phone': store.phone or '',
                'lat': store.location.y,
                'lng': store.location.x,
                'distance': store.distance,
                'base_daiso': store.base_daiso,
            })
    
    context = {
        'stores_data': stores_data,
        'total': len(stores_data),
        'title': '영등포구 편의점 지도',
    }
    
    return render(request, 'stores/convenience_stores_map.html', context)
