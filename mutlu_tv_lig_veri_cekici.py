#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mutlu TV Lig Veri Çekici - ALTERNATIF TABLO ALGILAMA
Sporx.com'dan gerçek puan durumu ve fikstür verilerini çeker.
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

    def sayfayi_cek(self, url: str) -> Optional[BeautifulSoup]:
        try:
            logger.info(f"Sayfa çekiliyor: {url}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            logger.info(f"Sayfa başarıyla çekildi: {url}")
            return soup
        except Exception as e:
            logger.error(f"Sayfa çekilemedi ({url}): {str(e)}")
            return None

    def puan_durumunu_cek(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Puan durumu sayfasından verileri çeker.
        Birden fazla strateji dener.
        """
        puan_durumu = []
        
        try:
            # Strateji 1: premium-standings div'i
            standings_div = soup.find('div', class_='premium-standings')
            if standings_div:
                logger.info("Strateji 1: premium-standings bulundu.")
                tablo = standings_div.find('table', class_='premium-table')
                if tablo:
                    tbody = tablo.find('tbody', id='genel')
                    if tbody:
                        return self._tablo_parse(tbody)
            
            # Strateji 2: Sınıf adıyla ara
            logger.info("Strateji 2: Sınıf adıyla aranıyor...")
            for sinif in ['standings-table', 'puan-durumu', 'table-league', 'lig-tablosu']:
                tablo = soup.find('table', class_=re.compile(sinif, re.I))
                if tablo:
                    logger.info(f"Tablo bulundu (sınıf: {sinif})")
                    return self._tablo_parse_standart(tablo)
            
            # Strateji 3: İlk tablo
            logger.info("Strateji 3: İlk tablo aranıyor...")
            tablo = soup.find('table')
            if tablo:
                logger.info("İlk tablo bulundu.")
                return self._tablo_parse_standart(tablo)
            
            # Strateji 4: Div içinde tablo ara
            logger.info("Strateji 4: Div içinde tablo aranıyor...")
            for div in soup.find_all('div', class_=re.compile(r'table|standing|puan', re.I)):
                tablo = div.find('table')
                if tablo:
                    logger.info("Div içinde tablo bulundu.")
                    return self._tablo_parse_standart(tablo)
            
            # Strateji 5: Tüm tabloları dene
            logger.info("Strateji 5: Tüm tablolar taranıyor...")
            tablolar = soup.find_all('table')
            for tablo in tablolar:
                satirlar = tablo.find_all('tr')
                if len(satirlar) > 10:
                    logger.info(f"Tablo bulundu ({len(satirlar)} satır)")
                    return self._tablo_parse_standart(tablo)
            
            logger.error("❌ Hiçbir tablo bulunamadı!")
            
        except Exception as e:
            logger.error(f"Puan durumu çekilirken hata: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
        
        return puan_durumu

    def _tablo_parse(self, tbody: BeautifulSoup) -> List[Dict[str, Any]]:
        """Premium tablo parse"""
        puan_durumu = []
        satirlar = tbody.find_all('tr')
        logger.info(f"Premium tablo: {len(satirlar)} satır")
        
        for satir in satirlar:
            try:
                sira_td = satir.find('td', class_='td-order')
                if not sira_td:
                    continue
                
                sira_span = sira_td.find('span', class_='position-number')
                sira = int(sira_span.get_text(strip=True)) if sira_span else 0
                
                logo_td = satir.find('td', class_='td-logo')
                logo_img = logo_td.find('img') if logo_td else None
                logo_url = logo_img.get('src', '') if logo_img else ''
                
                takim_td = satir.find('td', class_='td-team')
                takim_link = takim_td.find('a') if takim_td else None
                takim_adi = takim_link.get_text(strip=True) if takim_link else ''
                
                hucreler = satir.find_all('td')
                if len(hucreler) < 12:
                    continue
                
                def safe_int(index):
                    try:
                        text = hucreler[index].get_text(strip=True) if index < len(hucreler) else '0'
                        cleaned = re.sub(r'[^\d-]', '', text)
                        return int(cleaned) if cleaned else 0
                    except:
                        return 0
                
                oynanan = safe_int(4) if len(hucreler) > 4 else 0
                galibiyet = safe_int(5) if len(hucreler) > 5 else 0
                beraberlik = safe_int(6) if len(hucreler) > 6 else 0
                maglubiyet = safe_int(7) if len(hucreler) > 7 else 0
                atilan_gol = safe_int(8) if len(hucreler) > 8 else 0
                yenilen_gol = safe_int(9) if len(hucreler) > 9 else 0
                averaj = safe_int(10) if len(hucreler) > 10 else 0
                puan = safe_int(11) if len(hucreler) > 11 else 0
                
                durum_td = satir.find('td', class_='td-desc')
                durum_span = durum_td.find('span', class_='position-badge') if durum_td else None
                durum = durum_span.get_text(strip=True) if durum_span else ''
                
                if takim_adi:
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
            except Exception as e:
                logger.debug(f"Satır hatası: {str(e)}")
                continue
        
        return puan_durumu

    def _tablo_parse_standart(self, tablo: BeautifulSoup) -> List[Dict[str, Any]]:
        """Standart tablo parse"""
        puan_durumu = []
        satirlar = tablo.find_all('tr')
        logger.info(f"Standart tablo: {len(satirlar)} satır")
        
        # Başlık satırını bul
        baslik_satiri = None
        for satir in satirlar:
            hucreler = satir.find_all(['td', 'th'])
            metin = ' '.join([h.get_text(strip=True).lower() for h in hucreler])
            if any(k in metin for k in ['sıra', 'takım', 'puan', 'o']):
                baslik_satiri = satir
                break
        
        # Sütun indekslerini belirle
        sutun_map = {'sira': -1, 'takim': -1, 'oynanan': -1, 'galibiyet': -1,
                     'beraberlik': -1, 'maglubiyet': -1, 'atilan_gol': -1,
                     'yenilen_gol': -1, 'averaj': -1, 'puan': -1, 'durum': -1}
        
        if baslik_satiri:
            hucreler = baslik_satiri.find_all(['td', 'th'])
            for i, h in enumerate(hucreler):
                metin = h.get_text(strip=True).lower()
                if any(k in metin for k in ['sıra', 'no', '#']):
                    sutun_map['sira'] = i
                elif any(k in metin for k in ['takım', 'kulüp', 'team']):
                    sutun_map['takim'] = i
                elif metin == 'o' or 'maç' in metin:
                    sutun_map['oynanan'] = i
                elif metin == 'g':
                    sutun_map['galibiyet'] = i
                elif metin == 'b':
                    sutun_map['beraberlik'] = i
                elif metin == 'm':
                    sutun_map['maglubiyet'] = i
                elif metin == 'a':
                    sutun_map['atilan_gol'] = i
                elif metin == 'y':
                    sutun_map['yenilen_gol'] = i
                elif any(k in metin for k in ['av', 'averaj']):
                    sutun_map['averaj'] = i
                elif any(k in metin for k in ['p', 'puan']):
                    sutun_map['puan'] = i
                elif any(k in metin for k in ['durum', 'status']):
                    sutun_map['durum'] = i
        
        # Varsayılan indeksler
        if sutun_map['takim'] == -1:
            sutun_map = {'sira': 0, 'takim': 1, 'oynanan': 2, 'galibiyet': 3,
                         'beraberlik': 4, 'maglubiyet': 5, 'atilan_gol': 6,
                         'yenilen_gol': 7, 'averaj': 8, 'puan': 9, 'durum': 10}
        
        for satir in satirlar:
            if satir == baslik_satiri:
                continue
            
            hucreler = satir.find_all(['td', 'th'])
            if len(hucreler) < 5:
                continue
            
            try:
                def get_text(idx):
                    return hucreler[idx].get_text(strip=True) if idx < len(hucreler) else ''
                
                def get_int(idx):
                    try:
                        text = get_text(idx)
                        cleaned = re.sub(r'[^\d-]', '', text)
                        return int(cleaned) if cleaned else 0
                    except:
                        return 0
                
                takim_adi = get_text(sutun_map['takim'])
                takim_adi = re.sub(r'^\d+\s*', '', takim_adi).strip()
                
                if not takim_adi:
                    continue
                
                puan_durumu.append({
                    "sira": get_int(sutun_map['sira']),
                    "takim": takim_adi,
                    "logo": "",
                    "oynanan": get_int(sutun_map['oynanan']),
                    "galibiyet": get_int(sutun_map['galibiyet']),
                    "beraberlik": get_int(sutun_map['beraberlik']),
                    "maglubiyet": get_int(sutun_map['maglubiyet']),
                    "atilan_gol": get_int(sutun_map['atilan_gol']),
                    "yenilen_gol": get_int(sutun_map['yenilen_gol']),
                    "averaj": get_int(sutun_map['averaj']),
                    "puan": get_int(sutun_map['puan']),
                    "durum": get_text(sutun_map['durum'])
                })
            except Exception as e:
                logger.debug(f"Satır hatası: {str(e)}")
                continue
        
        return puan_durumu

    def fikstur_cek(self, soup: BeautifulSoup) -> Dict[str, List[Dict[str, str]]]:
        """Fikstür sayfasından maçları çeker."""
        fikstur = {}
        
        try:
            # Strateji 1: box-fixture
            fixture_div = soup.find('div', class_='box-fixture')
            if fixture_div:
                tablo = fixture_div.find('table', class_='table-fixture')
                if tablo:
                    tbody = tablo.find('tbody', id='fixtureTbody')
                    if tbody:
                        return self._fikstur_parse(tbody)
            
            # Strateji 2: Doğrudan tablo
            tablo = soup.find('table', class_=re.compile(r'fixture|fikstur', re.I))
            if tablo:
                tbody = tablo.find('tbody')
                if tbody:
                    return self._fikstur_parse(tbody)
            
            logger.error("❌ Fikstür tablosu bulunamadı!")
            
        except Exception as e:
            logger.error(f"Fikstür çekilirken hata: {str(e)}")
        
        return fikstur

    def _fikstur_parse(self, tbody: BeautifulSoup) -> Dict[str, List[Dict[str, str]]]:
        """Fikstür tablosunu parse eder."""
        fikstur = {"hafta_1": []}
        mevcut_tarih = ""
        
        satirlar = tbody.find_all('tr')
        for satir in satirlar:
            if 'fixture-date-row' in satir.get('class', []):
                tarih_td = satir.find('td')
                if tarih_td:
                    mevcut_tarih = tarih_td.get_text(strip=True)
                continue
            
            if 'fixture-row' in satir.get('class', []):
                try:
                    fixture_item = satir.find('div', class_='fixture-item')
                    if not fixture_item:
                        continue
                    
                    takim_linkleri = fixture_item.find_all('a', class_='fixture-team-link')
                    if len(takim_linkleri) < 2:
                        continue
                    
                    ev_sahibi = takim_linkleri[0].find('span', class_='fixture-team-name')
                    ev_adi = ev_sahibi.get_text(strip=True) if ev_sahibi else ''
                    
                    deplasman = takim_linkleri[1].find('span', class_='fixture-team-name')
                    dep_adi = deplasman.get_text(strip=True) if deplasman else ''
                    
                    sag_taraf = fixture_item.find('a', class_='fixture-side-link')
                    saat_span = sag_taraf.find('span', class_='fixture-match-time') if sag_taraf else None
                    saat = saat_span.get_text(strip=True) if saat_span else ''
                    
                    skor = saat if re.match(r'^\d+-\d+$', saat) else ''
                    saat_bilgisi = saat if not skor else ''
                    
                    if ev_adi and dep_adi:
                        fikstur["hafta_1"].append({
                            "ev_sahibi": ev_adi,
                            "deplasman": dep_adi,
                            "tarih": mevcut_tarih,
                            "saat": saat_bilgisi,
                            "skor": skor
                        })
                except Exception as e:
                    logger.debug(f"Maç hatası: {str(e)}")
                    continue
        
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
        
        puan_soup = self.sayfayi_cek(self.puan_durumu_url)
        if not puan_soup:
            logger.error("❌ PUAN DURUMU SAYFASI ÇEKİLEMEDİ!")
            sys.exit(1)
        
        puan_durumu = self.puan_durumunu_cek(puan_soup)
        if not puan_durumu:
            logger.error("❌ PUAN DURUMU VERİSİ ÇEKİLEMEDİ!")
            sys.exit(1)

        fikstur_soup = self.sayfayi_cek(self.fikstur_url)
        if not fikstur_soup:
            logger.error("❌ FİKSTÜR SAYFASI ÇEKİLEMEDİ!")
            sys.exit(1)
        
        fikstur = self.fikstur_cek(fikstur_soup)
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
            "version": "6.0.0",
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
    logger.info("Mutlu TV Lig Veri Çekici (ALTERNATİF TABLO) başlatıldı.")
    
    cekici = MutluTvLigVeriCekici()
    veri = cekici.veri_cek()
    
    if not cekici.json_olarak_kaydet():
        sys.exit(1)
    
    cekici.ozet_tablo_goster()
    logger.info("✅ İşlem BAŞARIYLA tamamlandı!")
    sys.exit(0)


if __name__ == "__main__":
    main()
