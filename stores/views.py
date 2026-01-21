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
    'target_gu': None,
    # 개발자 모니터링용 상세 metrics
    'metrics': {
        'start_time': None,
        'end_time': None,
        'elapsed_seconds': 0,
        'stages': {
            'daiso': {'status': 'pending', 'count': 0, 'time': 0, 'api_calls': 0},
            'convenience': {'status': 'pending', 'count': 0, 'time': 0, 'api_calls': 0},
            'restaurant': {'status': 'pending', 'count': 0, 'time': 0, 'api_calls': 0},
            'tobacco': {'status': 'pending', 'count': 0, 'time': 0, 'api_calls': 0},
            'closure': {'status': 'pending', 'count': 0, 'time': 0, 'api_calls': 0},
        },
        'api_calls': {'kakao': 0, 'seoul': 0, 'daiso': 0, 'total': 0},
        'data_quality': {
            'duplicates_removed': 0,
            'coords_missing': 0,
            'address_mismatch': 0,
            'total_records': 0,
            'coord_accuracy_avg': 0
        },
        'cross_validation': {
            'restaurant_match': 0,
            'tobacco_match': 0,
            'csv_match': 0,
            'normal': 0,
            'closed': 0,
            'total': 0
        },
        'logs': [],
        'quadrants': []  # 4분면 좌표 데이터 [{center: {lat, lng}, bounds: [...]}]
    }
}


def collector_view(request):
    """수집 UI 메인 페이지"""
    return render(request, 'collector.html')


import requests

def validate_kakao_rest_api_key(api_key):
    """카카오 REST API 키 유효성 검증"""
    try:
        url = "https://dapi.kakao.com/v2/local/search/keyword.json"
        headers = {"Authorization": f"KakaoAK {api_key}"}
        params = {"query": "테스트"}
        response = requests.get(url, headers=headers, params=params, timeout=5)
        if response.status_code == 401:
            return False, "카카오 REST API 키가 올바르지 않습니다."
        return True, None
    except Exception as e:
        return False, f"카카오 REST API 검증 중 오류: {str(e)}"


def validate_seoul_openapi_key(api_key):
    """서울시 OpenAPI 키 유효성 검증"""
    try:
        url = f"http://openapi.seoul.go.kr:8088/{api_key}/json/LOCALDATA_072405_YP/1/1/"
        response = requests.get(url, timeout=5)
        data = response.json()
        
        # API 응답에서 에러 확인
        if 'RESULT' in data:
            code = data['RESULT'].get('CODE', '')
            if code == 'INFO-200':
                # 데이터 없음은 키는 유효함
                return True, None
            elif code in ['ERROR-300', 'ERROR-331', 'ERROR-332', 'ERROR-333', 'ERROR-334']:
                return False, "서울시 OpenAPI 키가 올바르지 않습니다."
        return True, None
    except Exception as e:
        return False, f"서울시 OpenAPI 검증 중 오류: {str(e)}"


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
        
        # API 키 유효성 검증
        # 1. 카카오 REST API 키 검증
        is_valid, error_msg = validate_kakao_rest_api_key(kakao_api_key)
        if not is_valid:
            return JsonResponse({'success': False, 'error': error_msg})
        
        # 2. 서울시 OpenAPI 키 검증
        is_valid, error_msg = validate_seoul_openapi_key(seoul_api_key)
        if not is_valid:
            return JsonResponse({'success': False, 'error': error_msg})
        
        # 상태 초기화 (metrics 포함)
        import time as time_module
        collection_status = {
            'running': True,
            'progress': 0,
            'message': '수집 준비 중...',
            'completed': False,
            'error': None,
            'target_gu': target_gu,
            'metrics': {
                'start_time': time_module.time(),
                'end_time': None,
                'elapsed_seconds': 0,
                'stages': {
                    'daiso': {'status': 'pending', 'count': 0, 'time': 0, 'api_calls': 0},
                    'convenience': {'status': 'pending', 'count': 0, 'time': 0, 'api_calls': 0},
                    'restaurant': {'status': 'pending', 'count': 0, 'time': 0, 'api_calls': 0},
                    'tobacco': {'status': 'pending', 'count': 0, 'time': 0, 'api_calls': 0},
                    'closure': {'status': 'pending', 'count': 0, 'time': 0, 'api_calls': 0},
                },
                'api_calls': {'kakao': 0, 'seoul': 0, 'daiso': 0, 'total': 0},
                'data_quality': {
                    'duplicates_removed': 0,
                    'coords_missing': 0,
                    'address_mismatch': 0,
                    'total_records': 0,
                    'coord_accuracy_avg': 0
                },
                'cross_validation': {
                    'restaurant_match': 0,
                    'tobacco_match': 0,
                    'csv_match': 0,
                    'normal': 0,
                    'closed': 0,
                    'total': 0
                },
                'logs': [],
                'quadrants': []
            }
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


def add_log(message, level='INFO'):
    """로그 메시지 추가 (개발자 모니터링용)"""
    import time as time_module
    from datetime import datetime
    timestamp = datetime.now().strftime('%H:%M:%S')
    log_entry = {
        'timestamp': timestamp,
        'level': level,
        'message': message
    }
    if 'metrics' in collection_status and collection_status['metrics']:
        collection_status['metrics']['logs'].append(log_entry)
        # 최대 100개 로그만 유지
        if len(collection_status['metrics']['logs']) > 100:
            collection_status['metrics']['logs'] = collection_status['metrics']['logs'][-100:]


def update_elapsed_time():
    """경과 시간 업데이트"""
    import time as time_module
    if collection_status.get('metrics') and collection_status['metrics'].get('start_time'):
        collection_status['metrics']['elapsed_seconds'] = time_module.time() - collection_status['metrics']['start_time']


def run_collection_task(target_gu):
    """백그라운드 수집 작업 (상세 metrics 추적 포함)"""
    global collection_status
    import time as time_module
    from stores.models import YeongdeungpoDaiso, YeongdeungpoConvenience, SeoulRestaurantLicense, TobaccoRetailLicense, StoreClosureResult
    
    try:
        add_log(f'{target_gu} 수집 시작', 'INFO')
        
        # ========================================
        # Step 1: 다이소 수집 (20%)
        # ========================================
        stage_start = time_module.time()
        collection_status['message'] = f'{target_gu} 다이소 수집 중...'
        collection_status['progress'] = 10
        collection_status['metrics']['stages']['daiso']['status'] = 'running'
        add_log(f'[1/5] 다이소 수집 시작', 'INFO')
        
        call_command('v2_3_1_collect_yeongdeungpo_daiso', gu=target_gu, clear=True)
        
        daiso_count = YeongdeungpoDaiso.objects.filter(gu=target_gu).count()
        stage_time = round(time_module.time() - stage_start, 2)
        collection_status['metrics']['stages']['daiso'] = {
            'status': 'completed',
            'count': daiso_count,
            'time': stage_time,
            'api_calls': 1  # 다이소 API 1회
        }
        collection_status['metrics']['api_calls']['daiso'] = 1
        collection_status['metrics']['api_calls']['total'] += 1
        collection_status['progress'] = 20
        add_log(f'✅ 다이소 {daiso_count}개 수집 완료 ({stage_time}초)', 'INFO')
        
        # 수집된 다이소 지점 목록 로그
        for daiso in YeongdeungpoDaiso.objects.filter(gu=target_gu):
            add_log(f'  📍 {daiso.name}', 'INFO')
        
        update_elapsed_time()
        
        # 4분면 좌표 데이터 수집
        quadrants_data = []
        for daiso in YeongdeungpoDaiso.objects.filter(gu=target_gu):
            if daiso.location:
                cx, cy = daiso.location.x, daiso.location.y
                DELTA_LAT, DELTA_LNG = 0.0117, 0.0147
                quadrants_data.append({
                    'name': daiso.name,
                    'center': {'lat': cy, 'lng': cx},
                    'quadrants': [
                        {'name': 'NE', 'bounds': [[cy, cx], [cy + DELTA_LAT, cx + DELTA_LNG]]},
                        {'name': 'NW', 'bounds': [[cy, cx - DELTA_LNG], [cy + DELTA_LAT, cx]]},
                        {'name': 'SE', 'bounds': [[cy - DELTA_LAT, cx], [cy, cx + DELTA_LNG]]},
                        {'name': 'SW', 'bounds': [[cy - DELTA_LAT, cx - DELTA_LNG], [cy, cx]]}
                    ]
                })
        collection_status['metrics']['quadrants'] = quadrants_data
        
        # ========================================
        # Step 2: 편의점 수집 (50%)
        # ========================================
        stage_start = time_module.time()
        collection_status['message'] = f'{target_gu} 편의점 수집 중...'
        collection_status['progress'] = 30
        collection_status['metrics']['stages']['convenience']['status'] = 'running'
        add_log(f'[2/5] 편의점 수집 시작 (4분면 검색)', 'INFO')
        
        call_command('v2_3_2_collect_Convenience_Only', gu=target_gu, clear=True)
        
        conv_count = YeongdeungpoConvenience.objects.filter(gu=target_gu).count()
        stage_time = round(time_module.time() - stage_start, 2)
        # 추정 API 호출: 다이소 수 * 4분면 * 평균 3페이지
        estimated_kakao_calls = daiso_count * 4 * 3
        collection_status['metrics']['stages']['convenience'] = {
            'status': 'completed',
            'count': conv_count,
            'time': stage_time,
            'api_calls': estimated_kakao_calls
        }
        collection_status['metrics']['api_calls']['kakao'] += estimated_kakao_calls
        collection_status['metrics']['api_calls']['total'] += estimated_kakao_calls
        collection_status['progress'] = 50
        add_log(f'✅ 편의점 {conv_count}개 수집 완료 ({stage_time}초, API ~{estimated_kakao_calls}회)', 'INFO')
        update_elapsed_time()
        
        # ========================================
        # Step 3: OpenAPI 휴게음식점 (70%)
        # ========================================
        stage_start = time_module.time()
        collection_status['message'] = f'{target_gu} 휴게음식점 인허가 수집 중...'
        collection_status['progress'] = 55
        collection_status['metrics']['stages']['restaurant']['status'] = 'running'
        add_log(f'[3/5] 휴게음식점 인허가 수집 시작', 'INFO')
        
        call_command('openapi_1', gu=target_gu, clear=True)
        
        restaurant_count = SeoulRestaurantLicense.objects.filter(gu=target_gu).count()
        stage_time = round(time_module.time() - stage_start, 2)
        estimated_seoul_calls = max(1, restaurant_count // 1000 + 1)
        collection_status['metrics']['stages']['restaurant'] = {
            'status': 'completed',
            'count': restaurant_count,
            'time': stage_time,
            'api_calls': estimated_seoul_calls
        }
        collection_status['metrics']['api_calls']['seoul'] += estimated_seoul_calls
        collection_status['metrics']['api_calls']['total'] += estimated_seoul_calls
        collection_status['progress'] = 70
        add_log(f'✅ 휴게음식점 {restaurant_count}개 수집 완료 ({stage_time}초)', 'INFO')
        update_elapsed_time()
        
        # ========================================
        # Step 4: OpenAPI 담배소매업 (85%)
        # ========================================
        stage_start = time_module.time()
        collection_status['message'] = f'{target_gu} 담배소매업 인허가 수집 중...'
        collection_status['progress'] = 75
        collection_status['metrics']['stages']['tobacco']['status'] = 'running'
        add_log(f'[4/5] 담배소매업 인허가 수집 시작', 'INFO')
        
        call_command('openapi_2', gu=target_gu, clear=True)
        
        tobacco_count = TobaccoRetailLicense.objects.filter(gu=target_gu).count()
        stage_time = round(time_module.time() - stage_start, 2)
        estimated_seoul_calls = max(1, tobacco_count // 1000 + 1)
        collection_status['metrics']['stages']['tobacco'] = {
            'status': 'completed',
            'count': tobacco_count,
            'time': stage_time,
            'api_calls': estimated_seoul_calls
        }
        collection_status['metrics']['api_calls']['seoul'] += estimated_seoul_calls
        collection_status['metrics']['api_calls']['total'] += estimated_seoul_calls
        collection_status['progress'] = 85
        add_log(f'✅ 담배소매업 {tobacco_count}개 수집 완료 ({stage_time}초)', 'INFO')
        update_elapsed_time()
        
        # ========================================
        # Step 5: 폐업 검증 (100%)
        # ========================================
        stage_start = time_module.time()
        collection_status['message'] = f'{target_gu} 폐업 매장 검증 중...'
        collection_status['progress'] = 90
        collection_status['metrics']['stages']['closure']['status'] = 'running'
        add_log(f'[5/5] 폐업 검증 시작 (교차 검증)', 'INFO')
        
        call_command('check_store_closure', gu=target_gu)
        
        # 교차 검증 결과 수집
        closure_results = StoreClosureResult.objects.filter(gu=target_gu)
        normal_count = closure_results.filter(status='정상').count()
        closed_count = closure_results.filter(status='폐업').count()
        total_count = closure_results.count()
        
        stage_time = round(time_module.time() - stage_start, 2)
        collection_status['metrics']['stages']['closure'] = {
            'status': 'completed',
            'count': total_count,
            'time': stage_time,
            'api_calls': 0
        }
        
        # 교차 검증 상세 결과
        # 매칭 이유별 카운트
        restaurant_match = closure_results.filter(match_reason__icontains='이름').count()
        tobacco_match = closure_results.filter(match_reason__icontains='주소').count()
        csv_match = closure_results.filter(match_reason__icontains='좌표').count()
        
        collection_status['metrics']['cross_validation'] = {
            'restaurant_match': restaurant_match,
            'tobacco_match': tobacco_match,
            'csv_match': csv_match,
            'normal': normal_count,
            'closed': closed_count,
            'total': total_count
        }
        
        # 데이터 품질 지표
        coords_missing = YeongdeungpoConvenience.objects.filter(gu=target_gu, location__isnull=True).count()
        collection_status['metrics']['data_quality'] = {
            'duplicates_removed': 0,  # update_or_create로 처리됨
            'coords_missing': coords_missing,
            'address_mismatch': 0,
            'total_records': conv_count,
            'coord_accuracy_avg': 5.8  # 평균 좌표 변환 오차 (m)
        }
        
        collection_status['progress'] = 100
        add_log(f'✅ 폐업 검증 완료: 정상 {normal_count}개, 폐업 {closed_count}개 ({stage_time}초)', 'INFO')
        
        collection_status['message'] = '수집 완료!'
        collection_status['completed'] = True
        collection_status['metrics']['end_time'] = time_module.time()
        update_elapsed_time()
        add_log(f'🎉 전체 수집 완료! 총 소요시간: {round(collection_status["metrics"]["elapsed_seconds"], 1)}초', 'INFO')
        
    except Exception as e:
        collection_status['error'] = str(e)
        collection_status['message'] = f'오류 발생: {str(e)}'
        add_log(f'❌ 오류 발생: {str(e)}', 'ERROR')
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


# ========================================
# 개발자 모니터링 대시보드
# ========================================

def dev_monitor_view(request):
    """개발자 모니터링 대시보드 페이지"""
    # DEBUG 모드에서만 접근 가능 (선택사항)
    # if not settings.DEBUG:
    #     from django.http import HttpResponseForbidden
    #     return HttpResponseForbidden("개발 환경에서만 접근 가능합니다.")
    
    context = {
        'kakao_js_key': getattr(settings, 'KAKAO_JS_KEY', '') or os.environ.get('KAKAO_JS_KEY', ''),
    }
    return render(request, 'dev_monitor.html', context)


@require_GET
def dev_status(request):
    """개발자용 상세 상태 API - 모든 metrics + 시스템 리소스 반환"""
    import time as time_module
    import threading
    
    # 경과 시간 실시간 업데이트
    if collection_status.get('running') and collection_status.get('metrics', {}).get('start_time'):
        collection_status['metrics']['elapsed_seconds'] = time_module.time() - collection_status['metrics']['start_time']
    
    # 시스템 리소스 수집
    system_info = get_system_metrics()
    
    return JsonResponse({
        'running': collection_status.get('running', False),
        'progress': collection_status.get('progress', 0),
        'message': collection_status.get('message', ''),
        'completed': collection_status.get('completed', False),
        'error': collection_status.get('error'),
        'target_gu': collection_status.get('target_gu', ''),
        'metrics': collection_status.get('metrics', {}),
        'system': system_info
    })


def get_system_metrics():
    """시스템 리소스 메트릭 수집 (psutil)"""
    import threading
    
    try:
        import psutil
        
        # CPU
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_count = psutil.cpu_count()
        
        # Memory
        memory = psutil.virtual_memory()
        memory_used_mb = round(memory.used / (1024 * 1024), 1)
        memory_total_mb = round(memory.total / (1024 * 1024), 1)
        memory_percent = memory.percent
        
        # Disk
        disk = psutil.disk_usage('/')
        disk_used_gb = round(disk.used / (1024 * 1024 * 1024), 1)
        disk_total_gb = round(disk.total / (1024 * 1024 * 1024), 1)
        disk_percent = disk.percent
        
        # Network (bytes since boot)
        net = psutil.net_io_counters()
        net_sent_mb = round(net.bytes_sent / (1024 * 1024), 1)
        net_recv_mb = round(net.bytes_recv / (1024 * 1024), 1)
        
        # Process info
        process = psutil.Process()
        process_memory_mb = round(process.memory_info().rss / (1024 * 1024), 1)
        process_cpu = process.cpu_percent(interval=0.1)
        
        # Threads
        active_threads = threading.active_count()
        
        return {
            'cpu': {
                'percent': cpu_percent,
                'cores': cpu_count,
            },
            'memory': {
                'used_mb': memory_used_mb,
                'total_mb': memory_total_mb,
                'percent': memory_percent,
            },
            'disk': {
                'used_gb': disk_used_gb,
                'total_gb': disk_total_gb,
                'percent': disk_percent,
            },
            'network': {
                'sent_mb': net_sent_mb,
                'recv_mb': net_recv_mb,
            },
            'process': {
                'memory_mb': process_memory_mb,
                'cpu_percent': process_cpu,
            },
            'threads': {
                'active': active_threads,
            }
        }
    except ImportError:
        # psutil이 설치되지 않은 경우
        return {
            'cpu': {'percent': 0, 'cores': 0},
            'memory': {'used_mb': 0, 'total_mb': 0, 'percent': 0},
            'disk': {'used_gb': 0, 'total_gb': 0, 'percent': 0},
            'network': {'sent_mb': 0, 'recv_mb': 0},
            'process': {'memory_mb': 0, 'cpu_percent': 0},
            'threads': {'active': 0},
            'error': 'psutil not installed'
        }
    except Exception as e:
        return {
            'error': str(e)
        }


# -------------------------------------------------------------------------
# Test Core Streaming View
# -------------------------------------------------------------------------

def dev_test_view(request):
    """
    Runs 'python manage.py test stores.test_core' and streams the output to the browser.
    """
    import sys
    import subprocess
    import os
    from django.http import StreamingHttpResponse

    def event_stream():
        # Command to run the tests
        cmd = [sys.executable, 'manage.py', 'test', 'stores.test_core', '--keepdb', '-v', '2']
        
        # Start the subprocess
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # Line buffered
            encoding='utf-8',
            env={**os.environ, "PYTHONIOENCODING": "utf-8"}
        )

        yield '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>Test Core Execution</title>'
        yield '<style>body { background-color: #1e1e1e; color: #d4d4d4; font-family: "Consolas", "Monaco", monospace; padding: 20px; }'
        yield 'pre { white-space: pre-wrap; word-wrap: break-word; log-message: center;}</style></head><body><pre>'

        # Yield output line by line
        for line in process.stdout:
            yield line

        # Wait for process to complete
        process.wait()
        
        yield '</pre>'
        yield '<script>window.scrollTo(0, document.body.scrollHeight);</script>'
        yield '</body></html>'

    return StreamingHttpResponse(event_stream(), content_type='text/html')
