import pandas as pd

from card_fraud_detection.data.quality import (
    duplicates,
    fraud_bursts,
    inconsistent_card_attributes,
    overlap,
    unix_time_offset,
)


def _frame(rows):
    df = pd.DataFrame(rows, columns=["cc_num", "trans_date_trans_time", "amt", "is_fraud"])
    df["trans_date_trans_time"] = pd.to_datetime(df["trans_date_trans_time"])
    return df


def test_duplicates():
    df = _frame([
        (1, "2020-01-01 10:00", 5.0, 0),
        (1, "2020-01-01 10:00", 5.0, 0),   # birebir tekrar
        (1, "2020-01-01 10:00", 7.0, 0),   # aynı kart ve zaman, farklı tutar
        (2, "2020-01-01 10:00", 5.0, 0),
    ])
    df["trans_num"] = ["a", "b", "c", "d"]
    res = duplicates(df)
    assert res["tam satır tekrarı"] == 0          # trans_num farklı
    assert res["aynı kart + zaman + tutar"] == 1
    assert res["aynı kart + zaman"] == 2


def test_unix_time_offset_constant():
    df = _frame([(1, "2020-01-02 00:00", 1.0, 0), (1, "2020-01-03 12:00", 1.0, 0)])
    unix = pd.to_datetime(["2020-01-01 00:00", "2020-01-02 12:00"])
    df["unix_time"] = (unix - pd.Timestamp("1970-01-01")) // pd.Timedelta(seconds=1)
    assert unix_time_offset(df).tolist() == [1.0, 1.0]


def test_inconsistent_card_attributes():
    df = _frame([(1, "2020-01-01", 1.0, 0), (1, "2020-01-02", 1.0, 0), (2, "2020-01-01", 1.0, 0)])
    df["gender"] = ["F", "F", "M"]
    df["city"] = ["A", "B", "C"]                  # 1 numaralı kartta şehir değişmiş
    res = inconsistent_card_attributes(df)
    assert res["gender"] == 0
    assert res["city"] == 1


def test_fraud_bursts():
    df = _frame([
        (1, "2020-01-01 00:00", 1.0, 1),
        (1, "2020-01-03 00:00", 1.0, 1),
        (1, "2020-01-05 00:00", 1.0, 0),   # dolandırıcılıktan sonra normal işlem
        (2, "2020-01-01 00:00", 1.0, 0),
        (3, "2020-01-01 00:00", 1.0, 1),
    ])
    b = fraud_bursts(df)
    assert list(b.index) == [1, 3]                # dolandırıcılık görmeyen kart yok
    assert b.loc[1, "n_fraud"] == 2
    assert b.loc[1, "sure_gun"] == 2.0
    assert bool(b.loc[1, "sonrasinda_islem_var"])
    assert not bool(b.loc[3, "sonrasinda_islem_var"])


def test_overlap():
    tr = pd.DataFrame({"c": [1, 2, 3]})
    te = pd.DataFrame({"c": [3, 4]})
    res = overlap(tr, te, "c")
    assert res["ortak"] == 1
    assert res["yalnızca testte"] == 1
    assert res["testin eğitimde görülen oranı (%)"] == 50.0
