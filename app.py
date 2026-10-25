import urllib.request
import json
from pandas import json_normalize
 
api = "https://open.neis.go.kr/hub/mealServiceDietInfo"
key = "a8c601f5ff5b4a739866af067cff1fe6"
edu_code = "S10"   # 예: 서울 B10
school_code = "9010048"  # NEIS에서 학교명으로 검색 가능
 
url = f"{api}?KEY={key}&Type=json&ATPT_OFCDC_SC_CODE={edu_code}&SD_SCHUL_CODE={school_code}"
text = urllib.request.urlopen(url).read().decode("utf-8")
data = json.loads(text)
df = json_normalize(data["mealServiceDietInfo"][1]["row"])
print(df[["MLSV_YMD", "DDISH_NM"]])
