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