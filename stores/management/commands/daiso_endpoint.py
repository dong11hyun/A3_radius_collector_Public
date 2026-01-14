import requests
import json

def get_daiso_stores(keyword):
    url = "https://fapi.daisomall.co.kr/ms/msg/selStr"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Referer": "https://www.daisomall.co.kr/",
        "Origin": "https://www.daisomall.co.kr",
        "Host": "fapi.daisomall.co.kr"
    }

    # pageSize를 크게 잡아서 페이징 없이 한 번에 조회
    payload = {
        "curLitd": 126.9088468,
        "curLttd": 37.4989756,
        "currentPage": 1,
        "geolocationAgrYn": "Y",
        "keyword": keyword,
        "pageSize": 100, 
        "srchBassPkupStrYn": "Y",
        "srchYn": "Y"
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        result = response.json()

        if result.get('success'):
            stores = result.get('data', [])
            print(f"--- '{keyword}' 검색 결과: 총 {len(stores)}건 ---")
            
            for store in stores:
                name = store.get('strNm', '이름없음')       # 매장명
                address = store.get('strAddr', '주소없음')  # 주소
                lng = store.get('strLitd', '경도없음')      # 경도 (longitude)
                lat = store.get('strLttd', '위도없음')      # 위도 (latitude)
                store_code = store.get('strCd', '')         # 매장 코드
                
                print(f"[{name}] {address}")
                print(f"    좌표: ({lat}, {lng}) | 매장코드: {store_code}")
        else:
            print("데이터 조회 실패")

    except Exception as e:
        print(f"에러 발생: {e}")

# 실행
if __name__ == "__main__":
    get_daiso_stores("영등포")