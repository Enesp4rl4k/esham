# -*- coding: utf-8 -*-
"""KAP Akıllı Filtreleme, Rutin Bildirim Kalkanı ve Config Güvenlik Testleri."""
import os
import pytest
from esham.config import _safe_int
from esham.sources import Disclosure
from esham.sources.kap_filter import is_routine_daily_buyback, score, is_significant


def test_safe_int():
    os.environ["TEST_EMPTY_VAL"] = ""
    assert _safe_int("TEST_EMPTY_VAL", 587) == 587

    os.environ["TEST_INVALID_VAL"] = "abc"
    assert _safe_int("TEST_INVALID_VAL", 42) == 42

    os.environ["TEST_VALID_VAL"] = "8080"
    assert _safe_int("TEST_VALID_VAL", 80) == 8080

    assert _safe_int("NON_EXISTING_ENV_XYZ", 999) == 999


def test_routine_daily_buyback_filter():
    disc_routine = Disclosure(
        title="02.11.2026 Tarihli Pay Geri Alim Islemleri",
        company="TEST HOLDING A.S.",
        date="2026-11-02",
        disclosure_type="Ozel Durum Aciklamasi",
        ticker="TEST",
        raw_text="Sirketimizce 02.11.2026 tarihinde 50.000 adet pay 45,20 TL fiyattan geri alinmistir.",
    )
    assert is_routine_daily_buyback(disc_routine.title, disc_routine.raw_text) is True
    assert score(disc_routine) < 0
    assert is_significant(disc_routine) is False

    disc_material_buyback = Disclosure(
        title="Pay Geri Alim Programi Baslatilmasi Hakkinda Yonetim Kurulu Karari",
        company="SANAYI TICARET A.S.",
        date="2026-11-02",
        disclosure_type="Ozel Durum Aciklamasi",
        ticker="SNT",
        raw_text="Yonetim Kurulumuz 500.000.000 TL fon ayrilarak pay geri alim programi baslatilmasina karar vermistir.",
    )
    assert is_routine_daily_buyback(disc_material_buyback.title, disc_material_buyback.raw_text) is False
    assert score(disc_material_buyback) >= 3
    assert is_significant(disc_material_buyback) is True


def test_routine_bureaucracy_penalties():
    disc_sube = Disclosure(
        title="Yeni Sube Acilisi Tescili",
        company="PERAKENDE A.S.",
        date="2026-11-02",
        disclosure_type="Ozel Durum Aciklamasi",
        ticker="PRK",
        raw_text="Kadikoy subemiz tescil edilerek faaliyetine baslamistir.",
    )
    assert is_significant(disc_sube) is False

    disc_imza = Disclosure(
        title="Imza Sirkuleri Degisikligi",
        company="LOJISTIK A.S.",
        date="2026-11-02",
        disclosure_type="Ozel Durum Aciklamasi",
        ticker="LJS",
        raw_text="Mali isler mudurumuzun yetkisi tescil edilmistir.",
    )
    assert is_significant(disc_imza) is False


def test_material_disclosures_pass():
    disc_order = Disclosure(
        title="Yeni Is Iliskisi ve Siparis Alinmasi",
        company="TEKNOLOJI A.S.",
        date="2026-11-02",
        disclosure_type="Ozel Durum Aciklamasi",
        ticker="TEKNO",
        raw_text="Yurt disi yerlesik bir musteri ile 15.000.000 USD tutarinda yeni siparis sozlesmesi imzalanmistir.",
    )
    assert score(disc_order) >= 3
    assert is_significant(disc_order) is True
