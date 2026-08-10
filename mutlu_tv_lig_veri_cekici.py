#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mutlu TV Lig Veri Çekici - SADECE GERÇEK VERİ
Sporx.com mobil sitesinden gerçek verileri çeker.
ÖRNEK VERI KESINLIKLE KULLANILMAZ.
"""

import requests
from bs4 import BeautifulSoup
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
        self.user_agent = os.environ.get("USER_AGENT", "MutluTVLigBot/9.0")
        self.timeout = 30
        self.veri = {}
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'tr-TR,tr;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Upgrade-Insecure-Requests': '1'
        })

    def sayfayi_cek(self, url: str) -> Optional[str]:
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

    def puan_durumunu_cek(self, html: str) -> List[Dict[str, Any]]:
        """
        Sporx mobil sayfasından puan durumu verilerini çeker.
        """
        puan_durumu = []
        
        try:
            # Tabloyu bul - premium-standings
            tablo_baslangic = html.find('<div class="premium-standings">')
            if tablo_baslangic == -1:
                logger.error("❌ premium-standings div'i bulunamadı!")
                return []
            
            # Tablo bitişini bul
            tablo_bitis = html.find('<div class="standings-legend">', tablo_baslangic)
            if tablo_bitis == -1:
                # Alternatif bitiş
                tablo_bitis = html.find('</div>', tablo_baslangic + 1000)
                if tablo_bitis == -1:
                    logger.error("❌ Tablo bitişi bulunamadı!")
                    return []
            
            tablo_html = html[tablo_baslangic:tablo_bitis]
            
            # tbody genel'i bul
            tbody_baslangic = tablo_html.find('<tbody id="genel">')
            if tbody_baslangic == -1:
                logger.error("❌ tbody genel bulunamadı!")
                return []
            
            tbody_bitis = tablo_html.find('</tbody>', tbody_baslangic)
            if tbody_bitis == -1:
                logger.error("❌ tbody bitişi bulunamadı!")
                return []
            
            tbody_html = tablo_html[tbody_baslangic:tbody_bitis + 8]
            
            # Her satırı bul
            satir_baslangic = 0
            while True:
                satir_start = tbody_html.find('<tr', satir_baslangic)
                if satir_start == -1:
                    break
                
                satir_end = tbody_html.find('</tr>', satir_start)
                if satir_end == -1:
                    break
                
                satir_html = tbody_html[satir_start:satir_end + 5]
                satir_baslangic = satir_end + 5
                
                try:
                    # Sıra
                    sira_match = re.search(r'<span[^>]*class="[^"]*position-number[^"]*"[^>]*>(\d+)</span>', satir_html)
                    if not sira_match:
                        continue
                    sira = int(sira_match.group(1))
                    
                    # Takım adı
                    takim_match = re.search(r'<td[^>]*class="[^"]*td-team[^"]*"[^>]*>.*?<a[^>]*>(.*?)</a>', satir_html, re.DOTALL)
                    if not takim_match:
                        continue
                    takim_adi = takim_match.group(1).strip()
                    
                    if not takim_adi:
                        continue
                    
                    # Sayısal veriler - td'leri bul
                    tdler = re.findall(r'<td[^>]*>([^<]+)</td>', satir_html)
                    
                    # Sayısal değerleri çıkar
                    sayilar = []
                    for td in tdler:
                        td_clean = td.strip()
                        if re.match(r'^-?\d+$', td_clean):
                            sayilar.append(int(td_clean))
                    
                    # O, G, B, M, A, Y, Av, P - sırasıyla
                    if len(sayilar) >= 8:
                        oynanan = sayilar[0] if len(sayilar) > 0 else 0
                        galibiyet = sayilar[1] if len(sayilar) > 1 else 0
                        beraberlik = sayilar[2] if len(sayilar) > 2 else 0
                        maglubiyet = sayilar[3] if len(sayilar) > 3 else 0
                        atilan_gol = sayilar[4] if len(sayilar) > 4 else 0
                        yenilen_gol = sayilar[5] if len(sayilar) > 5 else 0
                        averaj = sayilar[6] if len(sayilar) > 6 else 0
                        puan = sayilar[7] if len(sayilar) > 7 else 0
                    else:
                        # Alternatif: doğrudan td içeriklerinden al
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
            
            logger.info(f"{len(puan_durumu)} takım bulundu.")
            
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

    def fikstur_cek(self, html: str) -> Dict[str, List[Dict[str, str]]]:
        """
        Sporx mobil sayfasından fikstür verilerini çeker.
        """
        fikstur = {"hafta_1": []}
        
        try:
            # box-fixture bul
            fixture_baslangic = html.find('<div class="box-fixture">')
            if fixture_baslangic == -1:
                logger.error("❌ box-fixture bulunamadı!")
                return fikstur
            
            fixture_bitis = html.find('</div>', fixture_baslangic + 1000)
            if fixture_bitis == -1:
                logger.error("❌ fixture bitişi bulunamadı!")
                return fikstur
            
            fixture_html = html[fixture_baslangic:fixture_bitis]
            
            # tbody fixtureTbody bul
            tbody_baslangic = fixture_html.find('<tbody id="fixtureTbody">')
            if tbody_baslangic == -1:
                logger.error("❌ fixtureTbody bulunamadı!")
                return fikstur
            
            tbody_bitis = fixture_html.find('</tbody>', tbody_baslangic)
            if tbody_bitis == -1:
                logger.error("❌ tbody bitişi bulunamadı!")
                return fikstur
            
            tbody_html = fixture_html[tbody_baslangic:tbody_bitis + 8]
            
            # Tarih ve maçları bul
            tarih = ""
            satir_baslangic = 0
            
            while True:
                satir_start = tbody_html.find('<tr', satir_baslangic)
                if satir_start == -1:
                    break
                
                satir_end = tbody_html.find('</tr>', satir_start)
                if satir_end == -1:
                    break
                
                satir_html = tbody_html[satir_start:satir_end + 5]
                satir_baslangic = satir_end + 5
                
                # Tarih satırı
                if 'fixture-date-row' in satir_html:
                    tarih_match = re.search(r'<td[^>]*>(.*?)</td>', satir_html)
                    if tarih_match:
                        tarih = tarih_match.group(1).strip()
                    continue
                
                # Maç satırı
                if 'fixture-row' in satir_html:
                    # Ev sahibi
                    ev_match = re.search(r'<span[^>]*class="[^"]*fixture-team-name[^"]*"[^>]*>(.*?)</span>', satir_html)
                    if not ev_match:
                        continue
                    ev_adi = ev_match.group(1).strip()
                    
                    # Deplasman (ikinci takım)
                    dep_matches = re.findall(r'<span[^>]*class="[^"]*fixture-team-name[^"]*"[^>]*>(.*?)</span>', satir_html)
                    if len(dep_matches) < 2:
                        continue
                    dep_adi = dep_matches[1].strip()
                    
                    # Saat/skor
                    saat_match = re.search(r'<span[^>]*class="[^"]*fixture-match-time[^"]*"[^>]*>(.*?)</span>', satir_html)
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
        """
        Veriyi doğrular - HATA varsa exit.
        """
        puan_durumu = self.veri.get("puan_durumu", [])
        fikstur = self.veri.get("fikstur", {})
        
        if len(puan_durumu) < 18:
            logger.error(f"❌ PUAN DURUMU EKSİK: {len(puan_durumu)}/18 takım")
            return False
        
        # Takım adları kontrolü
        for takim in puan_durumu:
            if not takim.get('takim') or len(takim['takim']) < 2:
                logger.error(f"❌ GEÇERSİZ TAKIM ADI: {takim.get('takim')}")
                return False
        
        toplam_mac = sum(len(m) for m in fikstur.values())
        if toplam_mac < 9:
            logger.error(f"❌ FİKSTÜR EKSİK: {toplam_mac} maç")
            return False
        
        logger.info("✅ VERİ DOĞRULAMA BAŞARILI!")
        return True

    def veri_cek(self) -> Dict[str, Any]:
        """
        Ana veri çekme fonksiyonu.
        """
        logger.info("========== GERÇEK VERİ ÇEKME BAŞLATILDI ==========")
        
        # Puan durumu çek
        html = self.sayfayi_cek(self.puan_durumu_url)
        if not html:
            logger.error("❌ PUAN DURUMU SAYFASI ÇEKİLEMEDİ!")
            sys.exit(1)
        
        # Debug
        with open("debug_puan_durumu.html", "w", encoding="utf-8") as f:
            f.write(html)
        
        puan_durumu = self.puan_durumunu_cek(html)
        if not puan_durumu:
            logger.error("❌ PUAN DURUMU VERİSİ ÇEKİLEMEDİ!")
            sys.exit(1)

        # Fikstür çek
        html_fikstur = self.sayfayi_cek(self.fikstur_url)
        if not html_fikstur:
            logger.error("❌ FİKSTÜR SAYFASI ÇEKİLEMEDİ!")
            sys.exit(1)
        
        with open("debug_fikstur.html", "w", encoding="utf-8") as f:
            f.write(html_fikstur)
        
        fikstur = self.fikstur_cek(html_fikstur)
        if not fikstur or not fikstur.get("hafta_1"):
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
            "version": "9.0.0",
            "durum": "basarili"
        }

        if not self.veri_dogrula():
            logger.error("❌ VERİ DOĞRULAMA BAŞARISIZ!")
            sys.exit(1)

        logger.info("========== VERİ ÇEKME BAŞARILI ==========")
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
    logger.info("Mutlu TV Lig Veri Çekici (SADECE GERÇEK VERİ) başlatıldı.")
    
    cekici = MutluTvLigVeriCekici()
    veri = cekici.veri_cek()
    
    if not cekici.json_olarak_kaydet():
        sys.exit(1)
    
    cekici.ozet_tablo_goster()
    logger.info("✅ İşlem BAŞARIYLA tamamlandı!")
    sys.exit(0)


if __name__ == "__main__":
    main()
