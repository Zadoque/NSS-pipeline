import pandas as pd

from app.pipeline.sinan.gold import age_band, decode_sinan_age_years


def test_decode_sinan_age_uses_encoded_unit():
    encoded = pd.Series([1001, 2007, 3009, 4018])
    result = decode_sinan_age_years(encoded)

    assert result.iloc[0] == 1 / (24 * 365.25)
    assert result.iloc[1] == 7 / 365.25
    assert result.iloc[2] == 9 / 12
    assert result.iloc[3] == 18


def test_age_band_does_not_treat_encoded_age_as_years():
    result = age_band(
        pd.Series([2026, 2026, 2026]),
        pd.Series([pd.NA, pd.NA, pd.NA], dtype="Int64"),
        pd.Series([3009, 4018, 2000]),
    )

    assert result.tolist() == ["LT1", "15_19", "LT1"]
