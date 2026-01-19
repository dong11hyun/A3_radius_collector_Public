# stores/management/commands/gu_codes.py
"""
서울시 25개 구별 OpenAPI 서비스명 매핑
- 휴게음식점 인허가: LOCALDATA_072405_XX
- 담배소매업 인허가: LOCALDATA_114302_XX
"""

# 서울시 구별 API 코드 매핑
# 참고: 서울시 OpenAPI 서비스명 suffix는 구별로 다름
GU_CODES = {
    '강남구': {'code': 'GN', 'restaurant': 'LOCALDATA_072405_GN', 'tobacco': 'LOCALDATA_114302_GN'},
    '강동구': {'code': 'GD', 'restaurant': 'LOCALDATA_072405_GD', 'tobacco': 'LOCALDATA_114302_GD'},
    '강북구': {'code': 'GB', 'restaurant': 'LOCALDATA_072405_GB', 'tobacco': 'LOCALDATA_114302_GB'},
    '강서구': {'code': 'GS', 'restaurant': 'LOCALDATA_072405_GS', 'tobacco': 'LOCALDATA_114302_GS'},
    '관악구': {'code': 'GA', 'restaurant': 'LOCALDATA_072405_GA', 'tobacco': 'LOCALDATA_114302_GA'},
    '광진구': {'code': 'GJ', 'restaurant': 'LOCALDATA_072405_GJ', 'tobacco': 'LOCALDATA_114302_GJ'},
    '구로구': {'code': 'GR', 'restaurant': 'LOCALDATA_072405_GR', 'tobacco': 'LOCALDATA_114302_GR'},
    '금천구': {'code': 'GC', 'restaurant': 'LOCALDATA_072405_GC', 'tobacco': 'LOCALDATA_114302_GC'},
    '노원구': {'code': 'NW', 'restaurant': 'LOCALDATA_072405_NW', 'tobacco': 'LOCALDATA_114302_NW'},
    '도봉구': {'code': 'DB', 'restaurant': 'LOCALDATA_072405_DB', 'tobacco': 'LOCALDATA_114302_DB'},
    '동대문구': {'code': 'DD', 'restaurant': 'LOCALDATA_072405_DD', 'tobacco': 'LOCALDATA_114302_DD'},
    '동작구': {'code': 'DJ', 'restaurant': 'LOCALDATA_072405_DJ', 'tobacco': 'LOCALDATA_114302_DJ'},
    '마포구': {'code': 'MP', 'restaurant': 'LOCALDATA_072405_MP', 'tobacco': 'LOCALDATA_114302_MP'},
    '서대문구': {'code': 'SD', 'restaurant': 'LOCALDATA_072405_SD', 'tobacco': 'LOCALDATA_114302_SD'},
    '서초구': {'code': 'SC', 'restaurant': 'LOCALDATA_072405_SC', 'tobacco': 'LOCALDATA_114302_SC'},
    '성동구': {'code': 'SDG', 'restaurant': 'LOCALDATA_072405_SDG', 'tobacco': 'LOCALDATA_114302_SDG'},
    '성북구': {'code': 'SB', 'restaurant': 'LOCALDATA_072405_SB', 'tobacco': 'LOCALDATA_114302_SB'},
    '송파구': {'code': 'SP', 'restaurant': 'LOCALDATA_072405_SP', 'tobacco': 'LOCALDATA_114302_SP'},
    '양천구': {'code': 'YC', 'restaurant': 'LOCALDATA_072405_YC', 'tobacco': 'LOCALDATA_114302_YC'},
    '영등포구': {'code': 'YD', 'restaurant': 'LOCALDATA_072405_YD', 'tobacco': 'LOCALDATA_114302_YD'},
    '용산구': {'code': 'YS', 'restaurant': 'LOCALDATA_072405_YS', 'tobacco': 'LOCALDATA_114302_YS'},
    '은평구': {'code': 'EP', 'restaurant': 'LOCALDATA_072405_EP', 'tobacco': 'LOCALDATA_114302_EP'},
    '종로구': {'code': 'JR', 'restaurant': 'LOCALDATA_072405_JR', 'tobacco': 'LOCALDATA_114302_JR'},
    '중구': {'code': 'JG', 'restaurant': 'LOCALDATA_072405_JG', 'tobacco': 'LOCALDATA_114302_JG'},
    '중랑구': {'code': 'JN', 'restaurant': 'LOCALDATA_072405_JN', 'tobacco': 'LOCALDATA_114302_JN'},
}


def get_gu_info(gu_name):
    """구 이름으로 API 코드 정보 조회"""
    if gu_name not in GU_CODES:
        raise ValueError(f"지원하지 않는 구: {gu_name}. 지원 구 목록: {list(GU_CODES.keys())}")
    return GU_CODES[gu_name]


def get_restaurant_service(gu_name):
    """구 이름으로 휴게음식점 서비스명 조회"""
    return get_gu_info(gu_name)['restaurant']


def get_tobacco_service(gu_name):
    """구 이름으로 담배소매업 서비스명 조회"""
    return get_gu_info(gu_name)['tobacco']


def list_supported_gu():
    """지원하는 구 목록 반환"""
    return list(GU_CODES.keys())
