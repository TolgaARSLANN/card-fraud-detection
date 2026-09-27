import pandas as pd

from card_fraud_detection.config import TARGET, TIME_COL
from card_fraud_detection.data.download import read_raw_csv

CSV = """\
,trans_date_trans_time,cc_num,merchant,category,amt,first,last,gender,street,city,state,zip,lat,long,city_pop,job,dob,trans_num,unix_time,merch_lat,merch_long,is_fraud
0,2019-01-01 00:00:18,2703186189652095,fraud_Rippin,misc_net,4.97,Jennifer,Banks,F,561 Perry,Moravian Falls,NC,28654,36.0788,-81.1781,3495,Psychologist,1988-03-09,0b242abb,1325376018,36.011293,-82.048315,0
1,2019-01-01 00:00:44,630423337322,fraud_Heller,grocery_pos,107.23,Stephanie,Gill,F,43039 Riley,Orient,WA,00123,48.8878,-118.2105,149,Teacher,1978-06-21,1f76529f,1325376044,49.159047,-118.186462,1
"""


def test_read_raw_csv_types(tmp_path):
    path = tmp_path / "raw.csv"
    path.write_text(CSV)
    df = read_raw_csv(path)

    assert not any(c.startswith("Unnamed") for c in df.columns)   # indeks sütunu atıldı
    assert pd.api.types.is_datetime64_any_dtype(df[TIME_COL])
    assert pd.api.types.is_datetime64_any_dtype(df["dob"])
    assert df["cc_num"].iloc[0] == 2703186189652095               # 16 hane kaybolmadı
    assert df["zip"].iloc[1] == "00123"                           # baştaki sıfır korundu
    assert df[TARGET].tolist() == [0, 1]
