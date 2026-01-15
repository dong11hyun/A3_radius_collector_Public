from django.db import models
from django.contrib.gis.db import models as gis_models

# 1. 다이소 지점들 자체를 저장할 모델 (서울 다이소 목록 저장용)
class DaisoStore(models.Model):
    name = models.CharField(max_length=100)       # 지점명
    address = models.CharField(max_length=200)    # 주소
    daiso_id = models.CharField(max_length=50, unique=True) # 다이소 ID
    location = gis_models.PointField(srid=4326, null=True, blank=True) # 위치

    def __str__(self):
        return self.name

# 2. 주변 매장 정보
class NearbyStore(models.Model):
    place_id = models.CharField(max_length=50, unique=True) # 카카오 고유 ID 저장
    # [수정] ForeignKey 대신 다시 CharField(글자)로 변경!
    # 이렇게 하면 기존에 있던 "다이소 강남본점" 데이터와 충돌하지 않습니다.
    base_daiso = models.CharField(max_length=100) 
    
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50, default='')
    address = models.CharField(max_length=200)
    phone = models.CharField(max_length=50, null=True, blank=True)
    distance = models.IntegerField()
    
    location = gis_models.PointField(srid=4326)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} (near {self.base_daiso})"


# 3. 영등포구 다이소 전용 모델 (서울 전체와 분리)
class YeongdeungpoDaiso(models.Model):
    """영등포구 내 다이소 지점 (서울 전체와 분리)"""
    name = models.CharField(max_length=100)       # 지점명
    address = models.CharField(max_length=200)    # 주소
    daiso_id = models.CharField(max_length=50, unique=True)  # 카카오 place_id
    location = gis_models.PointField(srid=4326, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'yeongdeungpo_daiso'
        verbose_name = '영등포구 다이소'
        verbose_name_plural = '영등포구 다이소 목록'

    def __str__(self):
        return f"[영등포] {self.name}"


# 4. 영등포구 편의점 전용 모델 (서울 전체와 분리)
class YeongdeungpoConvenience(models.Model):
    """영등포구 다이소 주변 편의점 (서울 전체와 분리)"""
    place_id = models.CharField(max_length=50, unique=True)  # 카카오 고유 ID
    base_daiso = models.CharField(max_length=100)  # 기준이 된 다이소 지점명
    
    name = models.CharField(max_length=100)
    address = models.CharField(max_length=200)
    phone = models.CharField(max_length=50, null=True, blank=True)
    distance = models.IntegerField()  # 기준 다이소와의 거리(m)
    
    location = gis_models.PointField(srid=4326)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'yeongdeungpo_convenience'
        verbose_name = '영등포구 편의점'
        verbose_name_plural = '영등포구 편의점 목록'

    def __str__(self):
        return f"[영등포] {self.name} (near {self.base_daiso})"


# 5. 서울시 Open API 휴게음식점 인허가 정보 (편의점 등)
class SeoulRestaurantLicense(models.Model):
    """서울시 Open API에서 가져온 휴게음식점 인허가 정보"""
    mgtno = models.CharField(max_length=100, unique=True, verbose_name='관리번호')  # 관리번호 (고유키)
    opnsfteamcode = models.CharField(max_length=20, null=True, blank=True, verbose_name='개방자치단체코드')
    
    # 사업장 정보
    bplcnm = models.CharField(max_length=200, verbose_name='사업장명')
    uptaenm = models.CharField(max_length=100, null=True, blank=True, verbose_name='업태구분명')
    sntuptaenm = models.CharField(max_length=100, null=True, blank=True, verbose_name='위생업태명')
    
    # 영업 상태
    trdstategbn = models.CharField(max_length=10, null=True, blank=True, verbose_name='영업상태코드')
    trdstatenm = models.CharField(max_length=50, null=True, blank=True, verbose_name='영업상태명')
    dtlstategbn = models.CharField(max_length=10, null=True, blank=True, verbose_name='상세영업상태코드')
    dtlstatenm = models.CharField(max_length=50, null=True, blank=True, verbose_name='상세영업상태명')
    
    # 인허가/폐업/휴업 일자
    apvpermymd = models.CharField(max_length=20, null=True, blank=True, verbose_name='인허가일자')
    apvcancelymd = models.CharField(max_length=20, null=True, blank=True, verbose_name='인허가취소일자')
    dcbymd = models.CharField(max_length=20, null=True, blank=True, verbose_name='폐업일자')
    clgstdt = models.CharField(max_length=20, null=True, blank=True, verbose_name='휴업시작일자')
    clgenddt = models.CharField(max_length=20, null=True, blank=True, verbose_name='휴업종료일자')
    ropnymd = models.CharField(max_length=20, null=True, blank=True, verbose_name='재개업일자')
    
    # 주소 정보
    sitewhladdr = models.CharField(max_length=300, null=True, blank=True, verbose_name='지번주소')
    rdnwhladdr = models.CharField(max_length=300, null=True, blank=True, verbose_name='도로명주소')
    sitepostno = models.CharField(max_length=10, null=True, blank=True, verbose_name='소재지우편번호')
    rdnpostno = models.CharField(max_length=10, null=True, blank=True, verbose_name='도로명우편번호')
    
    # 연락처
    sitetel = models.CharField(max_length=50, null=True, blank=True, verbose_name='전화번호')
    homepage = models.CharField(max_length=300, null=True, blank=True, verbose_name='홈페이지')
    
    # 좌표 정보 (원본 TM 좌표)
    x = models.CharField(max_length=50, null=True, blank=True, verbose_name='좌표X (TM)')
    y = models.CharField(max_length=50, null=True, blank=True, verbose_name='좌표Y (TM)')
    
    # 변환된 WGS84 좌표 (위도/경도)
    latitude = models.FloatField(null=True, blank=True, verbose_name='위도')
    longitude = models.FloatField(null=True, blank=True, verbose_name='경도')
    location = gis_models.PointField(srid=4326, null=True, blank=True, verbose_name='위치')
    
    # 면적 및 규모
    sitearea = models.CharField(max_length=50, null=True, blank=True, verbose_name='소재지면적')
    faciltotscp = models.CharField(max_length=50, null=True, blank=True, verbose_name='시설총규모')
    
    # 종업원 수
    totepnum = models.CharField(max_length=20, null=True, blank=True, verbose_name='총인원')
    maneipcnt = models.CharField(max_length=20, null=True, blank=True, verbose_name='남성종사자수')
    wmeipcnt = models.CharField(max_length=20, null=True, blank=True, verbose_name='여성종사자수')
    
    # 기타 정보
    bdngownsenm = models.CharField(max_length=50, null=True, blank=True, verbose_name='건물소유구분명')
    multusnupsoyn = models.CharField(max_length=10, null=True, blank=True, verbose_name='다중이용업소여부')
    
    # 데이터 갱신 정보
    lastmodts = models.CharField(max_length=30, null=True, blank=True, verbose_name='최종수정일자')
    updategbn = models.CharField(max_length=10, null=True, blank=True, verbose_name='데이터갱신구분')
    updatedt = models.CharField(max_length=30, null=True, blank=True, verbose_name='데이터갱신일자')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'yeongdeungpo_convenience_license'
        verbose_name = '영등포구 편의점 인허가'
        verbose_name_plural = '영등포구 편의점 인허가 목록'

    def __str__(self):
        return f"[{self.uptaenm}] {self.bplcnm} ({self.trdstatenm})"