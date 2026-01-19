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


def store_closure_map_view(request):
    """폐업 매장 체크 결과를 카카오맵에 표시"""
    import os
    import pandas as pd
    
    # CSV 파일 경로 (프로젝트 루트의 store_closure_result.csv)
    csv_path = os.path.join(settings.BASE_DIR, 'store_closure_result.csv')
    
    stores_list = []
    normal_count = 0
    closed_count = 0
    
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path, encoding='utf-8-sig')
        
        for _, row in df.iterrows():
            # 위도/경도가 있는 경우만 추가
            if pd.notna(row['위도']) and pd.notna(row['경도']):
                status = row['상태']
                if status == '정상':
                    normal_count += 1
                else:
                    closed_count += 1
                    
                stores_list.append({
                    'name': row['이름'],
                    'address': row['주소'],
                    'lat': float(row['위도']),
                    'lng': float(row['경도']),
                    'status': status,
                    'match_reason': row['매칭이유']
                })
    
    context = {
        'stores_json': json.dumps(stores_list, ensure_ascii=False),
        'kakao_js_key': settings.KAKAO_JS_KEY,
        'normal_count': normal_count,
        'closed_count': closed_count,
    }
    
    return render(request, 'store_closure_map.html', context)


# ========================================
# 수집 UI 관련 뷰
# ========================================
import os
import threading
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.core.management import call_command


# 수집 상태 저장 (메모리, 단일 사용자용)
collection_status = {
    'running': False,
    'progress': 0,
    'message': '',
    'completed': False,
    'error': None,
    'target_gu': None
}


def collector_view(request):
    """수집 UI 메인 페이지"""
    return render(request, 'collector.html')


@csrf_exempt
@require_POST
def start_collection(request):
    """수집 시작 API"""
    global collection_status
    
    # 이미 실행 중이면 거부
    if collection_status['running']:
        return JsonResponse({'success': False, 'error': '이미 수집이 진행 중입니다.'})
    
    try:
        data = json.loads(request.body)
        kakao_api_key = data.get('kakao_api_key')
        kakao_js_key = data.get('kakao_js_key')
        seoul_api_key = data.get('seoul_api_key')
        target_gu = data.get('target_gu', '영등포구')
        
        if not all([kakao_api_key, kakao_js_key, seoul_api_key]):
            return JsonResponse({'success': False, 'error': 'API 키가 누락되었습니다.'})
        
        # 상태 초기화
        collection_status = {
            'running': True,
            'progress': 0,
            'message': '수집 준비 중...',
            'completed': False,
            'error': None,
            'target_gu': target_gu
        }
        
        # 환경변수 설정
        os.environ['KAKAO_API_KEY'] = kakao_api_key
        os.environ['KAKAO_JS_KEY'] = kakao_js_key
        os.environ['SEOUL_OPENAPI_KEY'] = seoul_api_key
        
        # 백그라운드 스레드에서 수집 실행
        thread = threading.Thread(
            target=run_collection_task,
            args=(target_gu,)
        )
        thread.daemon = True
        thread.start()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def run_collection_task(target_gu):
    """백그라운드 수집 작업"""
    global collection_status
    
    try:
        # Step 1: 다이소 수집 (20%)
        collection_status['message'] = f'{target_gu} 다이소 수집 중...'
        collection_status['progress'] = 10
        call_command('v2_3_1_collect_yeongdeungpo_daiso', gu=target_gu, clear=True)
        collection_status['progress'] = 20
        
        # Step 2: 편의점 수집 (50%)
        collection_status['message'] = f'{target_gu} 편의점 수집 중...'
        collection_status['progress'] = 30
        call_command('v2_3_2_collect_Convenience_Only', gu=target_gu, clear=True)
        collection_status['progress'] = 50
        
        # Step 3: OpenAPI 휴게음식점 (70%)
        collection_status['message'] = f'{target_gu} 휴게음식점 인허가 수집 중...'
        collection_status['progress'] = 55
        call_command('openapi_1', gu=target_gu, clear=True)
        collection_status['progress'] = 70
        
        # Step 4: OpenAPI 담배소매업 (85%)
        collection_status['message'] = f'{target_gu} 담배소매업 인허가 수집 중...'
        collection_status['progress'] = 75
        call_command('openapi_2', gu=target_gu, clear=True)
        collection_status['progress'] = 85
        
        # Step 5: 폐업 검증 (100%)
        collection_status['message'] = f'{target_gu} 폐업 매장 검증 중...'
        collection_status['progress'] = 90
        call_command('check_store_closure', gu=target_gu)
        collection_status['progress'] = 100
        
        collection_status['message'] = '수집 완료!'
        collection_status['completed'] = True
        
    except Exception as e:
        collection_status['error'] = str(e)
        collection_status['message'] = f'오류 발생: {str(e)}'
    finally:
        collection_status['running'] = False


@require_GET
def check_status(request):
    """수집 진행 상태 확인 API"""
    return JsonResponse({
        'running': collection_status['running'],
        'progress': collection_status['progress'],
        'message': collection_status['message'],
        'completed': collection_status['completed'],
        'error': collection_status['error']
    })


@require_GET
def get_results(request):
    """수집 결과 반환 API"""
    import pandas as pd
    
    csv_path = os.path.join(settings.BASE_DIR, 'store_closure_result.csv')
    stores_list = []
    
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path, encoding='utf-8-sig')
        
        for _, row in df.iterrows():
            if pd.notna(row['위도']) and pd.notna(row['경도']):
                stores_list.append({
                    'name': row['이름'],
                    'address': row['주소'],
                    'lat': float(row['위도']),
                    'lng': float(row['경도']),
                    'status': row['상태'],
                    'match_reason': row['매칭이유']
                })
    
    return JsonResponse({
        'stores': stores_list,
        'target_gu': collection_status.get('target_gu', '영등포구')
    })

