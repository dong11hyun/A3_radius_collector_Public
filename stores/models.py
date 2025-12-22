from django.db import models 

class NearbyStore(models.Model):
    # 기준 다이소 지점 (예: 다이소 강남본점)
    base_daiso = models.CharField(max_length=50)
    
    # 수집된 매장 정보
    name = models.CharField(max_length=100)       # 상호명
    category = models.CharField(max_length=50, default='') # 업종 (카페, 편의점 등)
    address = models.CharField(max_length=200)    # 주소
    phone = models.CharField(max_length=50, null=True, blank=True) # 전화번호
    distance = models.IntegerField()              # 거리(m)
    
    lat = models.FloatField(default=0.0) # 위도 (y)
    lng = models.FloatField(default=0.0) # 경도 (x)

    created_at = models.DateTimeField(auto_now_add=True) # 수집 날짜

    def __str__(self):
        return self.name