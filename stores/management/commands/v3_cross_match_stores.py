"""
세 가지 편의점 데이터 교차 매칭 스크립트 V4 (중복 제거 포함)
1. public_data.csv (소상공인상권 CSV)
2. SeoulRestaurantLicense (영등포구 휴게음식점 인허가 OpenAPI)
3. YeongdeungpoConvenience (다이소 기반 추출)

OR 조건으로 매칭:
- 이름이 3개 데이터에 모두 존재
- 주소가 3개 데이터에 모두 존재 (도로명 정규화 적용)
- 위도/경도가 3개 데이터에 모두 존재 (소수점 반올림)

추가: 주소 일치 시 이름 또는 좌표로 2차 검증
추가: 주소_정규화 기준 중복 제거
"""

import os
import re
import pandas as pd
from django.core.management.base import BaseCommand
from stores.models import SeoulRestaurantLicense, YeongdeungpoConvenience


def normalize_name(name):
    """이름 정규화: 공백 제거, 소문자, 특수문자 제거"""
    if not name or pd.isna(name):
        return ""
    name = str(name).strip()
    name = name.replace(" ", "").replace("-", "").replace("_", "")
    name = name.lower()
    return name


def extract_road_address(address):
    """
    도로명 주소에서 핵심 부분 추출
    - 서울특별시/서울시/서울 → 통일
    - 도로명 + 번호 추출 (예: 양평로 49)
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
        
        # 구 이름 추출
        gu_pattern = r'(영등포구)'
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


def extract_dong_from_address(address):
    """지번주소에서 동 이름 추출 (예: 신길동, 당산동5가)"""
    if not address or pd.isna(address):
        return ""
    
    address = str(address)
    # 동 패턴: ~동, ~동1가, ~동2가 등
    dong_pattern = r'([가-힣]+동(?:\d+가)?)'
    match = re.search(dong_pattern, address)
    return match.group(1) if match else ""


def round_coord(val, decimals=4):
    """좌표 반올림"""
    try:
        return round(float(val), decimals)
    except (ValueError, TypeError):
        return None


class Command(BaseCommand):
    help = '세 가지 편의점 데이터 교차 매칭 V4 (중복 제거 포함)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--decimals',
            type=int,
            default=4,
            help='좌표 비교 시 소수점 자릿수 (기본: 4)'
        )
        parser.add_argument(
            '--output',
            type=str,
            default='matched_stores_unique.csv',
            help='결과 출력 파일명'
        )
        parser.add_argument(
            '--debug',
            action='store_true',
            help='디버그 정보 출력'
        )

    def handle(self, *args, **options):
        decimals = options['decimals']
        output_file = options['output']
        debug = options['debug']
        
        self.stdout.write(self.style.SUCCESS("=" * 70))
        self.stdout.write(self.style.SUCCESS("🔍 세 가지 편의점 데이터 교차 매칭 V4 (중복 제거 포함)"))
        self.stdout.write(self.style.SUCCESS("=" * 70))
        
        # 1. 데이터 로드
        self.stdout.write("\n📥 [1단계] 데이터 로드 중...")
        
        # 1-1. public_data.csv 로드
        csv_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'public_data.csv')
        csv_path = os.path.normpath(csv_path)
        
        if not os.path.exists(csv_path):
            csv_path = os.path.join(os.getcwd(), 'public_data.csv')
        
        csv_df = pd.read_csv(csv_path, encoding='cp949')
        self.stdout.write(f"  ✅ 소상공인상권 CSV: {len(csv_df)}개")
        
        csv_data = []
        for _, row in csv_df.iterrows():
            name = str(row['Column2']) if pd.notna(row['Column2']) else ""
            
            # Column32 = 도로명주소 (우선), Column25 = 지번주소
            road_addr = str(row['Column32']) if pd.notna(row['Column32']) else ""
            lot_addr = str(row['Column25']) if pd.notna(row['Column25']) else ""
            
            # 도로명주소가 없거나 nan이면 지번주소 사용
            if not road_addr or road_addr == 'nan':
                address = lot_addr
            else:
                address = road_addr
            
            lat = row['Column39'] if pd.notna(row['Column39']) else None
            lng = row['Column38'] if pd.notna(row['Column38']) else None
            
            csv_data.append({
                'source': 'csv',
                'id': row['Column1'],
                'name': name,
                'address': address,
                'road_addr': road_addr if road_addr != 'nan' else '',
                'lot_addr': lot_addr if lot_addr != 'nan' else '',
                'dong': extract_dong_from_address(lot_addr),
                'lat': lat,
                'lng': lng,
                'name_norm': normalize_name(name),
                'address_norm': extract_road_address(address),
                'lat_round': round_coord(lat, decimals),
                'lng_round': round_coord(lng, decimals)
            })
        
        # 1-2. SeoulRestaurantLicense 로드 (OpenAPI)
        openapi_qs = SeoulRestaurantLicense.objects.filter(uptaenm='편의점')
        self.stdout.write(f"  ✅ OpenAPI (휴게인허가): {openapi_qs.count()}개")
        
        openapi_data = []
        for store in openapi_qs:
            name = store.bplcnm or ""
            road_addr = store.rdnwhladdr or ""
            lot_addr = store.sitewhladdr or ""
            address = road_addr if road_addr else lot_addr
            lat = store.latitude
            lng = store.longitude
            
            openapi_data.append({
                'source': 'openapi',
                'id': store.mgtno,
                'name': name,
                'address': address,
                'road_addr': road_addr,
                'lot_addr': lot_addr,
                'dong': extract_dong_from_address(lot_addr),
                'lat': lat,
                'lng': lng,
                'name_norm': normalize_name(name),
                'address_norm': extract_road_address(address),
                'lat_round': round_coord(lat, decimals),
                'lng_round': round_coord(lng, decimals)
            })
        
        # 1-3. YeongdeungpoConvenience 로드 (다이소 기반)
        daiso_qs = YeongdeungpoConvenience.objects.all()
        self.stdout.write(f"  ✅ 다이소 기반 (카카오): {daiso_qs.count()}개")
        
        daiso_data = []
        for store in daiso_qs:
            name = store.name or ""
            address = store.address or ""
            lat = store.location.y if store.location else None
            lng = store.location.x if store.location else None
            
            daiso_data.append({
                'source': 'daiso',
                'id': store.place_id,
                'name': name,
                'address': address,
                'road_addr': address,
                'lot_addr': '',
                'dong': extract_dong_from_address(address),
                'lat': lat,
                'lng': lng,
                'name_norm': normalize_name(name),
                'address_norm': extract_road_address(address),
                'lat_round': round_coord(lat, decimals),
                'lng_round': round_coord(lng, decimals)
            })
        
        # 디버그: 샘플 출력
        if debug:
            self.stdout.write("\n🔧 [DEBUG] CSV 주소 샘플:")
            for d in csv_data[:3]:
                self.stdout.write(f"  {d['name']}")
                self.stdout.write(f"    도로명: {d['road_addr']}")
                self.stdout.write(f"    지번: {d['lot_addr']}")
                self.stdout.write(f"    정규화: {d['address_norm']}")
        
        # 2. 정규화 세트 생성
        self.stdout.write(f"\n🔎 [2단계] 교차 매칭 (소수점 {decimals}자리)...")
        
        csv_names = set(d['name_norm'] for d in csv_data if d['name_norm'])
        csv_addresses = set(d['address_norm'] for d in csv_data if d['address_norm'])
        csv_coords = set((d['lat_round'], d['lng_round']) for d in csv_data 
                        if d['lat_round'] is not None and d['lng_round'] is not None)
        
        openapi_names = set(d['name_norm'] for d in openapi_data if d['name_norm'])
        openapi_addresses = set(d['address_norm'] for d in openapi_data if d['address_norm'])
        openapi_coords = set((d['lat_round'], d['lng_round']) for d in openapi_data 
                            if d['lat_round'] is not None and d['lng_round'] is not None)
        
        daiso_names = set(d['name_norm'] for d in daiso_data if d['name_norm'])
        daiso_addresses = set(d['address_norm'] for d in daiso_data if d['address_norm'])
        daiso_coords = set((d['lat_round'], d['lng_round']) for d in daiso_data 
                          if d['lat_round'] is not None and d['lng_round'] is not None)
        
        # 세 데이터에 모두 존재하는 값
        common_names = csv_names & openapi_names & daiso_names
        common_addresses = csv_addresses & openapi_addresses & daiso_addresses  
        common_coords = csv_coords & openapi_coords & daiso_coords
        
        self.stdout.write(f"  📊 공통 이름: {len(common_names)}개")
        self.stdout.write(f"  📊 공통 주소: {len(common_addresses)}개")
        self.stdout.write(f"  📊 공통 좌표: {len(common_coords)}개")
        
        # 3. 주소 일치 시 2차 검증 (이름 OR 좌표)
        self.stdout.write("\n🔄 [3단계] 주소 일치 시 2차 검증...")
        
        # 데이터별 인덱스 생성 (주소 기반)
        csv_by_addr = {}
        for d in csv_data:
            if d['address_norm']:
                csv_by_addr.setdefault(d['address_norm'], []).append(d)
        
        openapi_by_addr = {}
        for d in openapi_data:
            if d['address_norm']:
                openapi_by_addr.setdefault(d['address_norm'], []).append(d)
        
        daiso_by_addr = {}
        for d in daiso_data:
            if d['address_norm']:
                daiso_by_addr.setdefault(d['address_norm'], []).append(d)
        
        # 주소가 2개 소스에서 일치하는 경우, 이름 또는 좌표로 3번째 소스 매칭 시도
        secondary_matches = set()  # (name_norm, match_type)
        
        # CSV-OpenAPI 주소 일치 → Daiso에서 이름/좌표 매칭
        csv_openapi_addrs = set(csv_by_addr.keys()) & set(openapi_by_addr.keys())
        for addr in csv_openapi_addrs:
            csv_stores = csv_by_addr[addr]
            openapi_stores = openapi_by_addr[addr]
            
            for cs in csv_stores:
                for os_ in openapi_stores:
                    # 이름 또는 좌표가 같으면 Daiso에서 검색
                    if cs['name_norm'] in daiso_names or (cs['lat_round'], cs['lng_round']) in daiso_coords:
                        secondary_matches.add((cs['name_norm'], '주소2차(CSV-OA)+이름/좌표'))
        
        # CSV-Daiso 주소 일치 → OpenAPI에서 이름/좌표 매칭
        csv_daiso_addrs = set(csv_by_addr.keys()) & set(daiso_by_addr.keys())
        for addr in csv_daiso_addrs:
            csv_stores = csv_by_addr[addr]
            daiso_stores = daiso_by_addr[addr]
            
            for cs in csv_stores:
                for ds in daiso_stores:
                    if cs['name_norm'] in openapi_names or (cs['lat_round'], cs['lng_round']) in openapi_coords:
                        secondary_matches.add((cs['name_norm'], '주소2차(CSV-DA)+이름/좌표'))
        
        # OpenAPI-Daiso 주소 일치 → CSV에서 이름/좌표 매칭
        openapi_daiso_addrs = set(openapi_by_addr.keys()) & set(daiso_by_addr.keys())
        for addr in openapi_daiso_addrs:
            openapi_stores = openapi_by_addr[addr]
            daiso_stores = daiso_by_addr[addr]
            
            for os_ in openapi_stores:
                for ds in daiso_stores:
                    if os_['name_norm'] in csv_names or (os_['lat_round'], os_['lng_round']) in csv_coords:
                        secondary_matches.add((os_['name_norm'], '주소2차(OA-DA)+이름/좌표'))
        
        self.stdout.write(f"  📊 2차 검증 추가 매칭: {len(secondary_matches)}개")
        
        if debug and secondary_matches:
            self.stdout.write("🔧 [DEBUG] 2차 검증 샘플:")
            for name, reason in list(secondary_matches)[:5]:
                self.stdout.write(f"    {name}: {reason}")
        
        # 4. 최종 매칭 결과 수집 (중복 허용)
        self.stdout.write("\n📋 [4단계] 매칭 결과 수집...")
        
        matched_stores = []
        seen_normalized_names = set()
        secondary_match_names = {m[0] for m in secondary_matches}
        
        all_data = csv_data + openapi_data + daiso_data
        
        for store in all_data:
            match_reason = []
            
            # 기본 매칭
            if store['name_norm'] in common_names:
                match_reason.append("이름매칭")
            if store['address_norm'] in common_addresses:
                match_reason.append("주소매칭")
            if (store['lat_round'], store['lng_round']) in common_coords:
                match_reason.append("좌표매칭")
            
            # 2차 검증 매칭
            if store['name_norm'] in secondary_match_names:
                if not match_reason:  # 기본 매칭이 없는 경우에만 추가
                    match_reason.append("2차검증")
            
            if match_reason and store['name_norm'] not in seen_normalized_names:
                source_map = {'csv': '소상공인상권', 'openapi': 'OpenAPI인허가', 'daiso': '다이소기반'}
                matched_stores.append({
                    '출처': source_map.get(store['source'], store['source']),
                    'ID': store['id'],
                    '이름': store['name'],
                    '주소': store['address'],
                    '주소_정규화': store['address_norm'],
                    '위도': store['lat'],
                    '경도': store['lng'],
                    '매칭이유': ', '.join(match_reason),
                    '이름_정규화': store['name_norm']
                })
                seen_normalized_names.add(store['name_norm'])
        
        self.stdout.write(f"  📊 매칭된 편의점 (중복 포함): {len(matched_stores)}개")
        
        # 5. 중복 제거 (주소_정규화 기준)
        self.stdout.write("\n🔄 [5단계] 중복 제거 (주소_정규화 기준)...")
        
        result_df = pd.DataFrame(matched_stores)
        before_count = len(result_df)
        
        # 주소_정규화 기준으로 중복 제거 (첫 번째 항목 유지)
        result_df = result_df.drop_duplicates(subset=['주소_정규화'], keep='first')
        after_count = len(result_df)
        
        self.stdout.write(f"  📊 중복 제거 전: {before_count}개")
        self.stdout.write(f"  📊 중복 제거 후: {after_count}개 (제거됨: {before_count - after_count}개)")
        
        # 6. 결과 출력
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS(f"🎯 최종 결과: {len(result_df)}개 고유 편의점"))
        self.stdout.write("=" * 70)
        
        if len(result_df) > 0:
            result_df.to_csv(output_file, index=False, encoding='utf-8-sig')
            self.stdout.write(self.style.SUCCESS(f"\n📁 결과 저장: {output_file}"))
            
            # 상세 출력
            self.stdout.write("\n" + "-" * 70)
            self.stdout.write("📌 매칭된 편의점 (상위 30개):")
            self.stdout.write("-" * 70)
            
            for i, (_, store) in enumerate(result_df.head(30).iterrows(), 1):
                self.stdout.write(f"\n[{i}] {store['이름']}")
                self.stdout.write(f"    주소: {store['주소']}")
                self.stdout.write(f"    좌표: ({store['위도']}, {store['경도']})")
                self.stdout.write(f"    매칭: {store['매칭이유']}")
            
            if len(result_df) > 30:
                self.stdout.write(f"\n... 외 {len(result_df) - 30}개")
            
            # 통계
            self.stdout.write("\n" + "-" * 70)
            self.stdout.write("📊 매칭 통계:")
            self.stdout.write("-" * 70)
            
            name_match = len(result_df[result_df['매칭이유'].str.contains('이름매칭')])
            addr_match = len(result_df[result_df['매칭이유'].str.contains('주소매칭')])
            coord_match = len(result_df[result_df['매칭이유'].str.contains('좌표매칭')])
            secondary = len(result_df[result_df['매칭이유'].str.contains('2차검증')])
            
            self.stdout.write(f"  이름 매칭: {name_match}개")
            self.stdout.write(f"  주소 매칭: {addr_match}개")
            self.stdout.write(f"  좌표 매칭: {coord_match}개")
            self.stdout.write(f"  2차 검증: {secondary}개")
            
            # 출처별 통계
            self.stdout.write("\n" + "-" * 70)
            self.stdout.write("📊 출처별 분포:")
            self.stdout.write("-" * 70)
            for source, count in result_df['출처'].value_counts().items():
                self.stdout.write(f"  {source}: {count}개")
        else:
            self.stdout.write(self.style.WARNING("\n⚠️ 매칭된 편의점이 없습니다."))
        
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("✅ 완료"))
        self.stdout.write("=" * 70)
