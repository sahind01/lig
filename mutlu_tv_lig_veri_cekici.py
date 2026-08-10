#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mutlu TV Lig Veri Çekici - RAW HTML KONTROL
Sporx.com'dan gerçek puan durumu verilerini ham HTML üzerinden çeker.
"""

import requests
import json
import re
import os
import sys
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("mutlu_tv_lig.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class MutluTvLigVeriCekici:
    def __init__(self):
        self.site_adi = "Mutlu TV Lig"
        self.sezon = "2026-2027"
        self.puan_durumu_url = "https://m.sporx.com/turkiye-super-lig-puan-durumu"
        self.fikstur_url = "https://m.sporx.com/turkiye-super-lig-fikstur"
        self.user_agent = os.environ.get("USER_AGENT", "MutluTVLigBot/5.0")
        self.timeout = 30
        self.veri = {}
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept-Language': 'tr-TR,tr;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache'
        })

    def sayfayi_cek_raw(self, url: str) -> Optional[str]:
        """Sayfayı ham HTML olarak çeker."""
        try:
            logger.info(f"Sayfa çekiliyor: {url}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            response.encoding = 'utf-8'
            logger.info(f"Sayfa başarıyla çekildi: {url} (boyut: {len(response.text)} bayt)")
            return response.text
        except Exception as e:
            logger.error(f"Sayfa çekilemedi ({url}): {str(e)}")
            return None

    def puan_durumunu_cek_raw(self, html: str) -> List[Dict[str, Any]]:
        """
        Ham HTML içinde puan durumu verilerini regex ile arar.
        """
        puan_durumu = []
        
        try:
            # 1. premium-standings içindeki tabloyu ara
            standings_match = re.search(r'<div[^>]*class="[^"]*premium-standings[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>\s*</div>\s*<div class="standings-legend"', html, re.DOTALL)
            if not standings_match:
                logger.warning("premium-standings bulunamadı, alternatif aranıyor...")
                # Alternatif: table-league ara
                standings_match = re.search(r'<table[^>]*class="[^"]*premium-table[^"]*"[^>]*>(.*?)</table>', html, re.DOTALL)
            
            if not standings_match:
                logger.warning("Tablo bulunamadı, tüm tablolar taranıyor...")
                # Tüm tabloları bul
                tablolar = re.findall(r'<table[^>]*>(.*?)</table>', html, re.DOTALL)
                for tablo_html in tablolar:
                    if 'Şampiyonlar Ligi' in tablo_html or 'Küme düşme' in tablo_html:
                        logger.info("Tablo bulundu (içerik kontrolü)")
                        return self._tablo_parse_raw(tablo_html)
                return []
            
            tablo_html = standings_match.group(1)
            logger.info(f"Tablo HTML boyutu: {len(tablo_html)} bayt")
            
            # Tablo satırlarını bul - tbody genel
            tbody_match = re.search(r'<tbody[^>]*id="genel"[^>]*>(.*?)</tbody>', tablo_html, re.DOTALL)
            if not tbody_match:
                # Alternatif: doğrudan tr'leri ara
                tbody_match = re.search(r'<tbody[^>]*>(.*?)</tbody>', tablo_html, re.DOTALL)
            
            if not tbody_match:
                logger.error("❌ Tablo gövdesi bulunamadı!")
                return []
            
            tbody_html = tbody_match.group(1)
            
            # Her satırı parse et
            satirlar = re.findall(r'<tr[^>]*>(.*?)</tr>', tbody_html, re.DOTALL)
            logger.info(f"{len(satirlar)} satır bulundu.")
            
            for satir_html in satirlar:
                try:
                    # Sıra
                    sira_match = re.search(r'<td[^>]*class="[^"]*td-order[^"]*"[^>]*>.*?<span[^>]*class="[^"]*position-number[^"]*"[^>]*>(\d+)</span>', satir_html, re.DOTALL)
                    if not sira_match:
                        continue
                    sira = int(sira_match.group(1))
                    
                    # Takım adı
                    takim_match = re.search(r'<td[^>]*class="[^"]*td-team[^"]*"[^>]*>.*?<a[^>]*>(.*?)</a>', satir_html, re.DOTALL)
                    if not takim_match:
                        continue
                    takim_adi = takim_match.group(1).strip()
                    
                    # Logo
                    logo_match = re.search(r'<td[^>]*class="[^"]*td-logo[^"]*"[^>]*>.*?<img[^>]*src="([^"]+)"', satir_html, re.DOTALL)
                    logo_url = logo_match.group(1) if logo_match else ""
                    
                    # İstatistikler - sayısal değerleri bul
                    sayilar = re.findall(r'<td[^>]*>(\d+)</td>', satir_html)
                    # Sıra ve takımdan sonra gelen sayılar: O, G, B, M, A, Y, Av, P
                    if len(sayilar) >= 7:
                        oynanan = int(sayilar[0]) if len(sayilar) > 0 else 0
                        galibiyet = int(sayilar[1]) if len(sayilar) > 1 else 0
                        beraberlik = int(sayilar[2]) if len(sayilar) > 2 else 0
                        maglubiyet = int(sayilar[3]) if len(sayilar) > 3 else 0
                        atilan_gol = int(sayilar[4]) if len(sayilar) > 4 else 0
                        yenilen_gol = int(sayilar[5]) if len(sayilar) > 5 else 0
                        averaj = int(sayilar[6]) if len(sayilar) > 6 else 0
                        puan = int(sayilar[7]) if len(sayilar) > 7 else 0
                    else:
                        # Alternatif: doğrudan td'lerden al
                        tdler = re.findall(r'<td[^>]*>([^<]+)</td>', satir_html)
                        if len(tdler) >= 12:
                            oynanan = self._safe_int(tdler[4])
                            galibiyet = self._safe_int(tdler[5])
                            beraberlik = self._safe_int(tdler[6])
                            maglubiyet = self._safe_int(tdler[7])
                            atilan_gol = self._safe_int(tdler[8])
                            yenilen_gol = self._safe_int(tdler[9])
                            averaj = self._safe_int(tdler[10])
                            puan = self._safe_int(tdler[11])
                        else:
                            continue
                    
                    # Durum
                    durum_match = re.search(r'<span[^>]*class="[^"]*position-badge[^"]*"[^>]*>(.*?)</span>', satir_html, re.DOTALL)
                    durum = durum_match.group(1).strip() if durum_match else ""
                    
                    puan_durumu.append({
                        "sira": sira,
                        "takim": takim_adi,
                        "logo": logo_url,
                        "oynanan": oynanan,
                        "galibiyet": galibiyet,
                        "beraberlik": beraberlik,
                        "maglubiyet": maglubiyet,
                        "atilan_gol": atilan_gol,
                        "yenilen_gol": yenilen_gol,
                        "averaj": averaj,
                        "puan": puan,
                        "durum": durum
                    })
                    logger.debug(f"{sira}. {takim_adi}: {puan} puan")
                    
                except Exception as e:
                    logger.debug(f"Satır hatası: {str(e)}")
                    continue
            
            logger.info(f"{len(puan_durumu)} takım başarıyla eklendi.")
            
        except Exception as e:
            logger.error(f"Puan durumu çekilirken hata: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
        
        return puan_durumu

    def _safe_int(self, value: str) -> int:
        """Güvenli integer dönüşümü."""
        try:
            cleaned = re.sub(r'[^\d-]', '', str(value).strip())
            return int(cleaned) if cleaned else 0
        except:
            return 0

    def _tablo_parse_raw(self, tablo_html: str) -> List[Dict[str, Any]]:
        """Raw tablo HTML'inden veri çıkarır."""
        puan_durumu = []
        
        try:
            satirlar = re.findall(r'<tr[^>]*>(.*?)</tr>', tablo_html, re.DOTALL)
            for satir_html in satirlar:
                try:
                    # Takım adı ve sayıları bul
                    tdler = re.findall(r'<td[^>]*>([^<]+)</td>', satir_html)
                    if len(tdler) < 10:
                        continue
                    
                    # Takım adı genellikle 2. sütunda
                    takim_adi = tdler[1].strip() if len(tdler) > 1 else ""
                    takim_adi = re.sub(r'^\d+\s*', '', takim_adi).strip()
                    
                    if not takim_adi:
                        continue
                    
                    puan_durumu.append({
                        "sira": self._safe_int(tdler[0]) if len(tdler) > 0 else 0,
                        "takim": takim_adi,
                        "logo": "",
                        "oynanan": self._safe_int(tdler[2]) if len(tdler) > 2 else 0,
                        "galibiyet": self._safe_int(tdler[3]) if len(tdler) > 3 else 0,
                        "beraberlik": self._safe_int(tdler[4]) if len(tdler) > 4 else 0,
                        "maglubiyet": self._safe_int(tdler[5]) if len(tdler) > 5 else 0,
                        "atilan_gol": self._safe_int(tdler[6]) if len(tdler) > 6 else 0,
                        "yenilen_gol": self._safe_int(tdler[7]) if len(tdler) > 7 else 0,
                        "averaj": self._safe_int(tdler[8]) if len(tdler) > 8 else 0,
                        "puan": self._safe_int(tdler[9]) if len(tdler) > 9 else 0,
                        "durum": tdler[10].strip() if len(tdler) > 10 else ""
                    })
                except Exception as e:
                    continue
        except Exception as e:
            logger.error(f"Tablo parse hatası: {str(e)}")
        
        return puan_durumu

    def fikstur_cek_raw(self, html: str) -> Dict[str, List[Dict[str, str]]]:
        """Ham HTML'den fikstür verilerini çeker."""
        fikstur = {"hafta_1": []}
        
        try:
            # box-fixture içindeki tabloyu bul
            fixture_match = re.search(r'<div[^>]*class="[^"]*box-fixture[^"]*"[^>]*>(.*?)</div>\s*</div>\s*<script', html, re.DOTALL)
            if not fixture_match:
                logger.warning("box-fixture bulunamadı, alternatif aranıyor...")
                fixture_match = re.search(r'<table[^>]*class="[^"]*table-fixture[^"]*"[^>]*>(.*?)</table>', html, re.DOTALL)
            
            if not fixture_match:
                logger.error("❌ Fikstür tablosu bulunamadı!")
                return fikstur
            
            fixture_html = fixture_match.group(1)
            
            # Tarih ve maçları bul
            tarih = ""
            maclar = re.findall(r'<tr[^>]*>(.*?)</tr>', fixture_html, re.DOTALL)
            
            for mac_html in maclar:
                if 'fixture-date-row' in mac_html:
                    tarih_match = re.search(r'<td[^>]*>(.*?)</td>', mac_html)
                    if tarih_match:
                        tarih = tarih_match.group(1).strip()
                elif 'fixture-row' in mac_html:
                    # Maç bilgilerini çıkar
                    ev_match = re.search(r'<span[^>]*class="[^"]*fixture-team-name[^"]*"[^>]*>(.*?)</span>', mac_html)
                    if not ev_match:
                        continue
                    ev_adi = ev_match.group(1).strip()
                    
                    # İkinci takımı bul
                    dep_match = re.findall(r'<span[^>]*class="[^"]*fixture-team-name[^"]*"[^>]*>(.*?)</span>', mac_html)
                    if len(dep_match) < 2:
                        continue
                    dep_adi = dep_match[1].strip()
                    
                    # Saat/skor
                    saat_match = re.search(r'<span[^>]*class="[^"]*fixture-match-time[^"]*"[^>]*>(.*?)</span>', mac_html)
                    saat = saat_match.group(1).strip() if saat_match else ""
                    
                    skor = saat if re.match(r'^\d+-\d+$', saat) else ""
                    saat_bilgisi = saat if not skor else ""
                    
                    if ev_adi and dep_adi:
                        fikstur["hafta_1"].append({
                            "ev_sahibi": ev_adi,
                            "deplasman": dep_adi,
                            "tarih": tarih,
                            "saat": saat_bilgisi,
                            "skor": skor
                        })
            
            logger.info(f"Fikstür: {len(fikstur['hafta_1'])} maç bulundu.")
            
        except Exception as e:
            logger.error(f"Fikstür çekilirken hata: {str(e)}")
        
        return fikstur

    def veri_dogrula(self) -> bool:
        puan_durumu = self.veri.get("puan_durumu", [])
        fikstur = self.veri.get("fikstur", {})
        
        if len(puan_durumu) < 18:
            logger.error(f"❌ PUAN DURUMU EKSİK: {len(puan_durumu)}/18")
            return False
        
        toplam_mac = sum(len(m) for m in fikstur.values())
        if toplam_mac < 9:
            logger.error(f"❌ FİKSTÜR EKSİK: {toplam_mac} maç")
            return False
        
        logger.info("✅ VERİ DOĞRULAMA BAŞARILI!")
        return True

    def veri_cek(self) -> Dict[str, Any]:
        logger.info("========== VERİ ÇEKME BAŞLATILDI ==========")
        
        # Puan durumu
        html = self.sayfayi_cek_raw(self.puan_durumu_url)
        if not html:
            logger.error("❌ PUAN DURUMU SAYFASI ÇEKİLEMEDİ!")
            sys.exit(1)
        
        # HTML'i debug için kaydet
        with open("debug_puan_durumu.html", "w", encoding="utf-8") as f:
            f.write(html)
        logger.info("HTML debug dosyası kaydedildi: debug_puan_durumu.html")
        
        puan_durumu = self.puan_durumunu_cek_raw(html)
        if not puan_durumu:
            logger.error("❌ PUAN DURUMU VERİSİ ÇEKİLEMEDİ!")
            sys.exit(1)

        # Fikstür
        html_fikstur = self.sayfayi_cek_raw(self.fikstur_url)
        if not html_fikstur:
            logger.error("❌ FİKSTÜR SAYFASI ÇEKİLEMEDİ!")
            sys.exit(1)
        
        with open("debug_fikstur.html", "w", encoding="utf-8") as f:
            f.write(html_fikstur)
        logger.info("HTML debug dosyası kaydedildi: debug_fikstur.html")
        
        fikstur = self.fikstur_cek_raw(html_fikstur)
        if not fikstur:
            logger.error("❌ FİKSTÜR VERİSİ ÇEKİLEMEDİ!")
            sys.exit(1)

        self.veri = {
            "site_adi": self.site_adi,
            "sezon": self.sezon,
            "guncelleme_tarihi": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "puan_durumu": puan_durumu,
            "fikstur": fikstur,
            "kaynaklar": {
                "puan_durumu": self.puan_durumu_url,
                "fikstur": self.fikstur_url
            },
            "version": "7.0.0",
            "durum": "basarili"
        }

        if not self.veri_dogrula():
            logger.error("❌ VERİ DOĞRULAMA BAŞARISIZ!")
            sys.exit(1)

        return self.veri

    def json_olarak_kaydet(self, dosya_adi: str = "mutlu_tv_lig_verisi.json") -> bool:
        try:
            with open(dosya_adi, 'w', encoding='utf-8') as f:
                json.dump(self.veri, f, ensure_ascii=False, indent=2)
            logger.info(f"✅ Veri '{dosya_adi}' dosyasına kaydedildi.")
            return True
        except Exception as e:
            logger.error(f"❌ JSON kaydedilirken hata: {str(e)}")
            return False

    def ozet_tablo_goster(self) -> None:
        puan_durumu = self.veri.get("puan_durumu", [])
        if not puan_durumu:
            print("\n⚠️ Puan durumu verisi bulunamadı!")
            return

        print("\n" + "="*100)
        print(f"🏆 {self.site_adi} - {self.sezon} Sezonu")
        print(f"📅 Güncelleme: {self.veri.get('guncelleme_tarihi', 'Bilinmiyor')}")
        print("="*100)
        print(f"{'Sira':<4} {'Takim':<25} {'O':<3} {'G':<3} {'B':<3} {'M':<3} {'A':<3} {'Y':<3} {'Av':<5} {'P':<4} {'Durum'}")
        print("-"*100)
        
        for takim in puan_durumu:
            durum = takim.get('durum', '')[:12] if takim.get('durum') else ""
            print(f"{takim.get('sira', 0):<4} {takim.get('takim', '')[:25]:<25} {takim.get('oynanan', 0):<3} {takim.get('galibiyet', 0):<3} {takim.get('beraberlik', 0):<3} {takim.get('maglubiyet', 0):<3} {takim.get('atilan_gol', 0):<3} {takim.get('yenilen_gol', 0):<3} {takim.get('averaj', 0):<5} {takim.get('puan', 0):<4} {durum}")
        print("="*100)


def main():
    logger.info("Mutlu TV Lig Veri Çekici (RAW HTML) başlatıldı.")
    
    cekici = MutluTvLigVeriCekici()
    veri = cekici.veri_cek()
    
    if not cekici.json_olarak_kaydet():
        sys.exit(1)
    
    cekici.ozet_tablo_goster()
    logger.info("✅ İşlem BAŞARIYLA tamamlandı!")
    sys.exit(0)


if __name__ == "__main__":
    main()
