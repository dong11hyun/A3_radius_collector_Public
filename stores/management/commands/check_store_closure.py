"""
카카오맵 폐업 매장 체크 프로그램

카카오 API 편의점과 2개 데이터셋을 비교:
1. SeoulRestaurantLicense (휴게음식점 인허가 - 편의점)
2. TobaccoRetailLicense (담배소매점 인허가)

public_data.csv (소상공인상권 데이터) (Default)기본값으로 영등포구에서만 사용!

매칭 조건 (OR):
- 이름이 일치하거나
- 주소가 일치하거나
- 위도/경도가 일치하면 → 정상(영업)

아무것도 일치하지 않으면 → 폐업

--gu 옵션으로 대상 구 지정 가능
"""

import os
import re
import pandas as pd
from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from stores.models import SeoulRestaurantLicense, TobaccoRetailLicense, YeongdeungpoConvenience, StoreClosureResult
from .gu_codes import list_supported_gu


def normalize_name(name):
    """이름 정규화: 공백 제거, 소문자, 특수문자 제거"""
    if not name or pd.isna(name):
        return ""
    name = str(name).strip()
    name = name.replace(" ", "").replace("-", "").replace("_", "")
    name = name.lower()
    return name


def extract_road_address(address, target_gu='영등포구'):
    """
    도로명 주소에서 핵심 부분 추출
    - 서울특별시/서울시/서울 → 통일
    - 도로명 + 번호 추출 (예: 양평로 49)
    - target_gu: 동적으로 구 이름 지정
    """
    if not address or pd.isna(address):
        return ""
    
    address = str(address).strip()
    if address == 'nan':
        return ""
    
    # 서울 표기 통일
    address = address.replace("서울특별시", "서울")
    address = address.replace("서울시", "서울")
    
    # 도로명 주소 패턴 추출: "~로/길/대로 + 숫자"
    road_pattern = r'([가-힣]+(?:로|길|대로)[0-9가-힣]*)\s*(\d+(?:-\d+)?)'
    match = re.search(road_pattern, address)
    
    if match:
        road_name = match.group(1)
        road_num = match.group(2)
        
        # 구 이름 추출 (동적으로 target_gu 사용)
        gu_pattern = rf'({target_gu})'
        gu_match = re.search(gu_pattern, address)
        gu = gu_match.group(1) if gu_match else ""
        
        normalized = f"서울 {gu} {road_name} {road_num}".strip()
        normalized = " ".join(normalized.split())
        return normalized
    
    # 패턴 없으면 정리해서 반환
    address = re.sub(r'\([^)]*\)', '', address)
    address = re.sub(r',.*$', '', address)
    address = " ".join(address.split())
    return address


def round_coord(val, decimals=4):
    """좌표 반올림"""
    try:
        return round(float(val), decimals)
    except (ValueError, TypeError):
        return None


class Command(BaseCommand):
    help = '카카오맵 폐업 매장 체크 - 카카오 API 편의점과 3개 데이터셋 비교 (--gu 옵션으로 대상 구 지정)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--gu',
            type=str,
            default='영등포구',
            help=f'대상 구 (기본: 영등포구). 지원: {", ".join(list_supported_gu())}'
        )
        parser.add_argument(
            '--decimals',
            type=int,
            default=4,
            help='좌표 비교 시 소수점 자릿수 (기본: 4)'
        )
        parser.add_argument(
            '--save-db',
            action='store_true',
            default=True,
            help='결과를 DB에 저장 (기본: True)'
        )
        parser.add_argument(
            '--no-save-db',
            action='store_true',
            help='DB 저장 안함'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            default=False,
            help='실행 전 해당 구의 기존 데이터 삭제'
        )

    def handle(self, *args, **options):
        target_gu = options['gu']
        decimals = options['decimals']
        
        self.stdout.write(self.style.SUCCESS("=" * 70))
        self.stdout.write(self.style.SUCCESS(f"🔍 {target_gu} 폐업 매장 체크 프로그램"))
        self.stdout.write(self.style.SUCCESS("=" * 70))

        # 기존 데이터 삭제
        if options['clear']:
            deleted_count, _ = StoreClosureResult.objects.filter(gu=target_gu).delete()
            self.stdout.write(self.style.WARNING(f"\n🧹 기존 {target_gu} 데이터 {deleted_count}건 삭제 완료"))
        
        # ========================================
        # 1단계: 카카오 API 편의점 데이터 로드 (기준 데이터) - 해당 구만
        # ========================================
        self.stdout.write("\n📥 [1단계] 카카오 API 편의점 데이터 로드 (기준 데이터)...")
        
        kakao_qs = YeongdeungpoConvenience.objects.filter(gu=target_gu)
        self.stdout.write(f"  ✅ {target_gu} 카카오 API 편의점: {kakao_qs.count()}개")
        
        kakao_data = []
        for store in kakao_qs:
            name = store.name or ""
            address = store.address or ""
            lat = store.location.y if store.location else None
            lng = store.location.x if store.location else None
            
            kakao_data.append({
                'place_id': store.place_id,
                'name': name,
                'address': address,
                'lat': lat,
                'lng': lng,
                'name_norm': normalize_name(name),
                'address_norm': extract_road_address(address, target_gu),
                'lat_round': round_coord(lat, decimals),
                'lng_round': round_coord(lng, decimals)
            })
        
        # ========================================
        # 2단계: 비교 데이터셋 로드
        # ========================================
        self.stdout.write("\n📥 [2단계] 비교 데이터셋 로드...")
        
        # 2-1. 휴게음식점 (SeoulRestaurantLicense) - 해당 구 + 편의점 필터
        restaurant_qs = SeoulRestaurantLicense.objects.filter(gu=target_gu, uptaenm='편의점')
        self.stdout.write(f"  ✅ {target_gu} 휴게음식점(편의점): {restaurant_qs.count()}개")
        
        restaurant_names = set()
        restaurant_addresses = set()
        restaurant_coords = set()
        
        for store in restaurant_qs:
            name_norm = normalize_name(store.bplcnm)
            if name_norm:
                restaurant_names.add(name_norm)
            
            road_addr = store.rdnwhladdr or ""
            lot_addr = store.sitewhladdr or ""
            address = road_addr if road_addr else lot_addr
            addr_norm = extract_road_address(address, target_gu)
            if addr_norm:
                restaurant_addresses.add(addr_norm)
            
            lat_r = round_coord(store.latitude, decimals)
            lng_r = round_coord(store.longitude, decimals)
            if lat_r is not None and lng_r is not None:
                restaurant_coords.add((lat_r, lng_r))
        
        # 2-2. 담배소매점 (TobaccoRetailLicense) - 해당 구만
        tobacco_qs = TobaccoRetailLicense.objects.filter(gu=target_gu)
        self.stdout.write(f"  ✅ {target_gu} 담배소매점: {tobacco_qs.count()}개")
        
        tobacco_names = set()
        tobacco_addresses = set()
        tobacco_coords = set()
        
        for store in tobacco_qs:
            name_norm = normalize_name(store.bplcnm)
            if name_norm:
                tobacco_names.add(name_norm)
            
            road_addr = store.rdnwhladdr or ""
            lot_addr = store.sitewhladdr or ""
            address = road_addr if road_addr else lot_addr
            addr_norm = extract_road_address(address, target_gu)
            if addr_norm:
                tobacco_addresses.add(addr_norm)
            
            lat_r = round_coord(store.latitude, decimals)
            lng_r = round_coord(store.longitude, decimals)
            if lat_r is not None and lng_r is not None:
                tobacco_coords.add((lat_r, lng_r))
        
        # 2-3. public_data.csv (소상공인상권)
        csv_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'public_data.csv')
        csv_path = os.path.normpath(csv_path)
        
        if not os.path.exists(csv_path):
            csv_path = os.path.join(os.getcwd(), 'public_data.csv')
        
        csv_df = pd.read_csv(csv_path, encoding='cp949')
        self.stdout.write(f"  ✅ 소상공인상권 CSV: {len(csv_df)}개")
        
        csv_names = set()
        csv_addresses = set()
        csv_coords = set()
        
        for _, row in csv_df.iterrows():
            name = str(row['Column2']) if pd.notna(row['Column2']) else ""
            name_norm = normalize_name(name)
            if name_norm:
                csv_names.add(name_norm)
            
            road_addr = str(row['Column32']) if pd.notna(row['Column32']) else ""
            lot_addr = str(row['Column25']) if pd.notna(row['Column25']) else ""
            
            if not road_addr or road_addr == 'nan':
                address = lot_addr
            else:
                address = road_addr
            
            addr_norm = extract_road_address(address, target_gu)
            if addr_norm:
                csv_addresses.add(addr_norm)
            
            lat = row['Column39'] if pd.notna(row['Column39']) else None
            lng = row['Column38'] if pd.notna(row['Column38']) else None
            lat_r = round_coord(lat, decimals)
            lng_r = round_coord(lng, decimals)
            if lat_r is not None and lng_r is not None:
                csv_coords.add((lat_r, lng_r))
        
        # ========================================
        # 3단계: 매칭 수행
        # ========================================
        self.stdout.write("\n🔎 [3단계] 매칭 수행 (OR 조건)...")
        
        # 모든 비교 데이터 합치기
        all_names = restaurant_names | tobacco_names | csv_names
        all_addresses = restaurant_addresses | tobacco_addresses | csv_addresses
        all_coords = restaurant_coords | tobacco_coords | csv_coords
        
        self.stdout.write(f"  📊 전체 비교 이름: {len(all_names)}개")
        self.stdout.write(f"  📊 전체 비교 주소: {len(all_addresses)}개")
        self.stdout.write(f"  📊 전체 비교 좌표: {len(all_coords)}개")
        
        results = []
        normal_count = 0
        closed_count = 0
        
        for store in kakao_data:
            is_matched = False
            match_reasons = []
            
            # 이름 매칭
            if store['name_norm'] and store['name_norm'] in all_names:
                is_matched = True
                match_reasons.append("이름")
            
            # 주소 매칭
            if store['address_norm'] and store['address_norm'] in all_addresses:
                is_matched = True
                match_reasons.append("주소")
            
            # 좌표 매칭
            coord = (store['lat_round'], store['lng_round'])
            if coord[0] is not None and coord[1] is not None and coord in all_coords:
                is_matched = True
                match_reasons.append("좌표")
            
            # 결과 저장
            status = "정상" if is_matched else "폐업"
            match_reason = ", ".join(match_reasons) if match_reasons else "없음"
            
            if is_matched:
                normal_count += 1
            else:
                closed_count += 1
            
            results.append({
                'place_id': store['place_id'],
                '이름': store['name'],
                '주소': store['address'],
                '위도': store['lat'],
                '경도': store['lng'],
                '상태': status,
                '매칭이유': match_reason
            })
        
        # ========================================
        # 4단계: 결과 출력
        # ========================================
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("🎯 매칭 결과"))
        self.stdout.write("=" * 70)
        self.stdout.write(f"  🔵 정상 영업: {normal_count}개")
        self.stdout.write(f"  🔴 폐업 (카카오맵 업데이트 필요): {closed_count}개")
        self.stdout.write(f"  📊 전체: {len(results)}개")
        

        
        # DB 저장
        save_db = options['save_db'] and not options['no_save_db']
        if save_db:
            self.stdout.write("\n💾 [5단계] DB 저장 중...")
            new_count = 0
            update_count = 0
            
            for r in results:
                lat = r['위도']
                lng = r['경도']
                location = Point(lng, lat, srid=4326) if lat and lng else None
                
                obj, created = StoreClosureResult.objects.update_or_create(
                    place_id=r['place_id'],
                    defaults={
                        'name': r['이름'],
                        'address': r['주소'],
                        'gu': target_gu,  # 구 정보 저장
                        'latitude': lat,
                        'longitude': lng,
                        'location': location,
                        'status': r['상태'],
                        'match_reason': r['매칭이유'],
                    }
                )
                if created:
                    new_count += 1
                else:
                    update_count += 1
            
            self.stdout.write(self.style.SUCCESS(f"  ✅ DB 저장 완료: 신규 {new_count}건, 업데이트 {update_count}건"))
        
        # 폐업 매장 샘플 출력
        closed_stores = [r for r in results if r['상태'] == '폐업']
        if closed_stores:
            self.stdout.write("\n" + "-" * 70)
            self.stdout.write("🔴 폐업 추정 매장 (상위 20개):")
            self.stdout.write("-" * 70)
            for i, store in enumerate(closed_stores[:20], 1):
                self.stdout.write(f"  [{i}] {store['이름']}")
                self.stdout.write(f"      주소: {store['주소']}")
            
            if len(closed_stores) > 20:
                self.stdout.write(f"\n  ... 외 {len(closed_stores) - 20}개")
        
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("✅ 완료"))
        self.stdout.write("=" * 70)
