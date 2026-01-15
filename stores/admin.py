from django.contrib import admin
from .models import DaisoStore, NearbyStore, YeongdeungpoDaiso, YeongdeungpoConvenience, SeoulRestaurantLicense

# 1. 다이소 매장 관리 (기존 유지 + 보완)
@admin.register(DaisoStore)
class DaisoStoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'daiso_id', 'address', 'display_coordinates')
    search_fields = ('name', 'address', 'daiso_id')
    readonly_fields = ('display_coordinates',)

    # 좌표를 예쁘게 보여주는 함수
    def display_coordinates(self, obj):
        if obj.location:
            return f"X:{obj.location.x:.6f}, Y:{obj.location.y:.6f}"
        return "-"
    display_coordinates.short_description = "좌표 (경도, 위도)"


# 2. 주변 매장 (카페, 편의점) 관리 - 여기가 핵심!
@admin.register(NearbyStore)
class NearbyStoreAdmin(admin.ModelAdmin):
    # 목록에 보여줄 칼럼들
    list_display = (
        'name', 
        'category_badge',  # 카테고리 (카페/편의점)
        'distance_display', # 거리 (km 변환)
        'base_daiso',      # 기준이 된 다이소 지점
        'address', 
        'display_coordinates'
    )
    
    # [중요] 오른쪽 사이드바에 필터 기능 추가
    list_filter = (
        'category',      # 카페 vs 편의점 클릭해서 필터링
        'base_daiso',    # 특정 다이소 지점 데이터만 모아보기
    )

    # 검색 기능 (매장명, 기준 다이소 이름으로 검색)
    search_fields = ('name', 'base_daiso', 'address')

    # 페이징 처리 (데이터가 많으므로 한 페이지에 50개씩)
    list_per_page = 50

    # --- 커스텀 함수들 ---

    # 1. 거리(m)를 km로 변환해서 보여주기
    def distance_display(self, obj):
        if obj.distance is not None:
            if obj.distance < 1000:
                return f"{obj.distance}m"
            else:
                return f"{obj.distance / 1000:.2f}km"
        return "-"
    distance_display.short_description = "거리"
    distance_display.admin_order_field = 'distance' # 컬럼 클릭 시 거리순 정렬 가능하게 함

    # 2. 좌표 보여주기 (location 필드에서 추출)
    def display_coordinates(self, obj):
        if obj.location:
            return f"({obj.location.x:.5f}, {obj.location.y:.5f})"
        return "-"
    display_coordinates.short_description = "좌표"

    # 3. 카테고리 좀 더 눈에 띄게 표시 (선택사항)
    def category_badge(self, obj):
        return obj.category
    category_badge.short_description = "분류"


# 3. 영등포구 다이소 관리
@admin.register(YeongdeungpoDaiso)
class YeongdeungpoDaisoAdmin(admin.ModelAdmin):
    list_display = ('name', 'daiso_id', 'address', 'display_coordinates', 'created_at')
    search_fields = ('name', 'address', 'daiso_id')
    list_filter = ('created_at',)
    list_per_page = 50

    def display_coordinates(self, obj):
        if obj.location:
            return f"({obj.location.x:.6f}, {obj.location.y:.6f})"
        return "-"
    display_coordinates.short_description = "좌표"


# 4. 영등포구 편의점 관리
@admin.register(YeongdeungpoConvenience)
class YeongdeungpoConvenienceAdmin(admin.ModelAdmin):
    list_display = ('name', 'distance_display', 'base_daiso', 'address', 'display_coordinates')
    search_fields = ('name', 'address', 'base_daiso')
    list_filter = ('base_daiso', 'created_at')
    list_per_page = 50

    def distance_display(self, obj):
        if obj.distance is not None:
            if obj.distance < 1000:
                return f"{obj.distance}m"
            else:
                return f"{obj.distance / 1000:.2f}km"
        return "-"
    distance_display.short_description = "거리"
    distance_display.admin_order_field = 'distance'

    def display_coordinates(self, obj):
        if obj.location:
            return f"({obj.location.x:.5f}, {obj.location.y:.5f})"
        return "-"
    display_coordinates.short_description = "좌표"


# 5. 서울시 휴게음식점 인허가 정보 (편의점) 관리
@admin.register(SeoulRestaurantLicense)
class SeoulRestaurantLicenseAdmin(admin.ModelAdmin):
    list_display = (
        'bplcnm',           # 사업장명
        'uptaenm',          # 업태구분명
        'trdstatenm',       # 영업상태명
        'rdnwhladdr',       # 도로명주소
        'latitude',         # 위도
        'longitude',        # 경도
        'apvpermymd',       # 인허가일자
    )
    
    # 필터 기능
    list_filter = (
        'trdstatenm',       # 영업상태 (영업/정상, 폐업 등)
        'uptaenm',          # 업태구분 (편의점 등)
        'dtlstatenm',       # 상세영업상태
    )
    
    # 검색 기능
    search_fields = ('bplcnm', 'rdnwhladdr', 'sitewhladdr', 'mgtno')
    
    # 페이징
    list_per_page = 50
    
    # 읽기 전용 필드
    readonly_fields = ('mgtno', 'created_at', 'updated_at')
    
    # 필드 그룹화
    fieldsets = (
        ('기본 정보', {
            'fields': ('mgtno', 'bplcnm', 'uptaenm', 'sntuptaenm')
        }),
        ('영업 상태', {
            'fields': ('trdstatenm', 'dtlstatenm', 'apvpermymd', 'dcbymd')
        }),
        ('주소 및 연락처', {
            'fields': ('rdnwhladdr', 'sitewhladdr', 'sitetel', 'homepage')
        }),
        ('좌표 정보', {
            'fields': ('x', 'y', 'latitude', 'longitude'),
            'classes': ('collapse',)  # 접을 수 있게
        }),
        ('시스템 정보', {
            'fields': ('lastmodts', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )