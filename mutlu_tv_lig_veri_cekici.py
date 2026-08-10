#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mutlu TV Lig Veri Çekici - SADECE GERÇEK VERİ
Demo veya örnek veri KESİNLİKLE kullanılmaz.
Veri çekilemezse işlem HATA ile sonlanır.
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

# Logging ayarları
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
    """
    Mutlu TV Lig için Sporx.com veri çekici - SADECE GERÇEK VERİ
    """
    
    def __init__(self):
        self.site_adi = "Mutlu TV Lig"
        self.sezon = "2026-2027"
        self.puan_durumu_url = "https://m.sporx.com/turkiye-super-lig-puan-durumu"
        self.fikstur_url = "https://m.sporx.com/turkiye-super-lig-fikstur"
        self.user_agent = os.environ.get("USER_AGENT", "MutluTVLigBot/3.0 (+https://mutlutvlig.com)")
        self.timeout = 30
        self.veri = {}
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept-Language': 'tr-TR,tr;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'no-cache'
        })

    def sayfayi_cek(self, url: str) -> Optional[BeautifulSoup]:
        """
        Verilen URL'den HTML içeriğini çeker.
        """
        try:
            logger.info(f"Sayfa çekiliyor: {url}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            response.encoding = 'utf-8'
            
            # HTML'i debug için kaydet
            with open(f"debug_{url.split('/')[-1]}.html", "w", encoding="utf-8") as f:
                f.write(response.text)
            
            soup = BeautifulSoup(response.text, 'html.parser')
            logger.info(f"Sayfa başarıyla çekildi: {url}")
            return soup
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP hatası ({url}): {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Beklenmeyen hata ({url}): {str(e)}")
            return None

    def puan_durumunu_cek(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Puan durumu sayfasından gerçek verileri çeker.
        """
        puan_durumu = []
        
        # Tabloyu bul
        tablo = self._tablo_bul(soup)
        if not tablo:
            logger.error("❌ PUAN DURUMU TABLOSU BULUNAMADI!")
            return []

        # Tablo satırlarını al
        satirlar = tablo.find_all('tr')
        logger.info(f"Puan durumu: {len(satirlar)} satır bulundu.")

        # Başlık satırını bul
        baslik_satiri = None
        for satir in satirlar:
            hucreler = satir.find_all(['td', 'th'])
            metinler = [h.get_text(strip=True).lower() for h in hucreler]
            if any(k in ' '.join(metinler) for k in ['sıra', 'takım', 'puan', 'o']):
                baslik_satiri = satir
                break

        if not baslik_satiri:
            logger.error("❌ BAŞLIK SATIRI BULUNAMADI!")
            return []

        # Sütun indekslerini belirle
        sutun_map = self._sutun_indeksleri_bul(baslik_satiri)
        
        # Geçerli sütunlar var mı kontrol et
        if sutun_map['takim'] == -1 or sutun_map['puan'] == -1:
            logger.error("❌ GEREKLİ SÜTUNLAR BULUNAMADI!")
            logger.error(f"Sütun haritası: {sutun_map}")
            return []

        # Veri satırlarını işle
        for satir in satirlar:
            if satir == baslik_satiri:
                continue
                
            hucreler = satir.find_all(['td', 'th'])
            if len(hucreler) < 5:
                continue

            takim_verisi = self._satir_isle(hucreler, sutun_map)
            if takim_verisi and takim_verisi.get('takim'):
                puan_durumu.append(takim_verisi)

        # Benzersiz takım listesi oluştur
        benzersiz_takimlar = {}
        for takim in puan_durumu:
            takim_adi = takim['takim']
            if takim_adi not in benzersiz_takimlar:
                benzersiz_takimlar[takim_adi] = takim
            else:
                # Daha dolu olanı koru
                mevcut = benzersiz_takimlar[takim_adi]
                if takim['puan'] > mevcut['puan'] or takim['oynanan'] > mevcut['oynanan']:
                    benzersiz_takimlar[takim_adi] = takim

        puan_durumu = list(benzersiz_takimlar.values())
        
        # En az 18 takım olmalı
        if len(puan_durumu) < 18:
            logger.error(f"❌ BEKLENEN 18 TAKIM, BULUNAN: {len(puan_durumu)}")
            # Yine de devam et, ama uyarı ver
            
        logger.info(f"{len(puan_durumu)} takım bulundu.")
        return puan_durumu

    def _tablo_bul(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        """
        Sayfadaki tabloyu bulur.
        """
        # Strateji 1: İlk tablo
        tablo = soup.find('table')
        if tablo and tablo.find('tr'):
            return tablo

        # Strateji 2: Sınıf ile ara
        for sinif in ['table', 'standings-table', 'puan-durumu', 'lig-tablosu']:
            tablo = soup.find('table', class_=re.compile(sinif, re.I))
            if tablo:
                return tablo

        # Strateji 3: Div içinde ara
        for div in soup.find_all('div', class_=re.compile(r'table|standing|puan', re.I)):
            tablo = div.find('table')
            if tablo:
                return tablo

        return None

    def _sutun_indeksleri_bul(self, baslik_satiri: BeautifulSoup) -> Dict[str, int]:
        """
        Başlık satırından sütun indekslerini belirler.
        """
        hucreler = baslik_satiri.find_all(['td', 'th'])
        sutun_map = {
            'sira': -1, 'takim': -1, 'oynanan': -1, 'galibiyet': -1,
            'beraberlik': -1, 'maglubiyet': -1, 'atilan_gol': -1,
            'yenilen_gol': -1, 'averaj': -1, 'puan': -1, 'durum': -1
        }
        
        for i, hucre in enumerate(hucreler):
            metin = hucre.get_text(strip=True).lower()
            if any(k in metin for k in ['sıra', 'no', '#']):
                sutun_map['sira'] = i
            elif any(k in metin for k in ['takım', 'kulüp', 'team']):
                sutun_map['takim'] = i
            elif any(k in metin for k in ['o', 'maç', 'match']):
                sutun_map['oynanan'] = i
            elif metin == 'g' or metin == 'galibiyet':
                sutun_map['galibiyet'] = i
            elif metin == 'b' or metin == 'beraberlik':
                sutun_map['beraberlik'] = i
            elif metin == 'm' or metin == 'mağlubiyet':
                sutun_map['maglubiyet'] = i
            elif metin == 'a' or metin == 'atılan':
                sutun_map['atilan_gol'] = i
            elif metin == 'y' or metin == 'yenilen':
                sutun_map['yenilen_gol'] = i
            elif any(k in metin for k in ['av', 'averaj']):
                sutun_map['averaj'] = i
            elif any(k in metin for k in ['p', 'puan']):
                sutun_map['puan'] = i
            elif any(k in metin for k in ['durum', 'status']):
                sutun_map['durum'] = i

        return sutun_map

    def _satir_isle(self, hucreler: List, sutun_map: Dict[str, int]) -> Optional[Dict[str, Any]]:
        """
        Tek bir satırdan takım verisini çıkarır.
        """
        try:
            def safe_text(index):
                if 0 <= index < len(hucreler):
                    return hucreler[index].get_text(strip=True)
                return ""

            def safe_int(index):
                try:
                    if 0 <= index < len(hucreler):
                        text = hucreler[index].get_text(strip=True)
                        cleaned = re.sub(r'[^\d-]', '', text)
                        return int(cleaned) if cleaned else 0
                except:
                    pass
                return 0

            takim_adi = safe_text(sutun_map['takim'])
            if not takim_adi:
                return None

            # Takım adını temizle
            takim_adi = re.sub(r'^\d+\s*', '', takim_adi).strip()
            
            return {
                "sira": safe_int(sutun_map['sira']) or 0,
                "takim": takim_adi,
                "oynanan": safe_int(sutun_map['oynanan']),
                "galibiyet": safe_int(sutun_map['galibiyet']),
                "beraberlik": safe_int(sutun_map['beraberlik']),
                "maglubiyet": safe_int(sutun_map['maglubiyet']),
                "atilan_gol": safe_int(sutun_map['atilan_gol']),
                "yenilen_gol": safe_int(sutun_map['yenilen_gol']),
                "averaj": safe_int(sutun_map['averaj']),
                "puan": safe_int(sutun_map['puan']),
                "durum": safe_text(sutun_map['durum'])
            }
        except Exception as e:
            logger.debug(f"Satır işlenirken hata: {str(e)}")
            return None

    def fikstur_cek(self, soup: BeautifulSoup) -> Dict[str, List[Dict[str, str]]]:
        """
        Fikstür sayfasından gerçek maçları çeker.
        """
        fikstur = {}
        
        # Hafta başlıklarını bul
        hafta_basliklari = soup.find_all(['h2', 'h3', 'strong'], string=re.compile(r'hafta|week', re.I))
        if not hafta_basliklari:
            hafta_basliklari = soup.find_all('div', class_=re.compile(r'hafta|week', re.I))
            hafta_basliklari = [h for h in hafta_basliklari if h.find('h2') or h.find('h3')]

        if not hafta_basliklari:
            logger.error("❌ FİKSTÜR HAFTA BAŞLIKLARI BULUNAMADI!")
            return {}

        # Maçları bul
        mac_elemanlari = soup.find_all('div', class_=re.compile(r'match|mac|game', re.I))
        if not mac_elemanlari:
            tablo = soup.find('table')
            if tablo:
                mac_elemanlari = tablo.find_all('tr')

        if not mac_elemanlari:
            logger.error("❌ FİKSTÜR MAÇLARI BULUNAMADI!")
            return {}

        # Haftaları doldur
        for i, baslik in enumerate(hafta_basliklari[:5], 1):
            hafta_adi = f"hafta_{i}"
            fikstur[hafta_adi] = []
            
            # Bu haftaya ait maçları bul
            maclar = []
            for mac in mac_elemanlari:
                mac_bilgisi = self._mac_bilgisi_cek(mac)
                if mac_bilgisi:
                    maclar.append(mac_bilgisi)
            
            fikstur[hafta_adi] = maclar[:6]

        # Hiç maç yoksa hata ver
        toplam_mac = sum(len(m) for m in fikstur.values())
        if toplam_mac == 0:
            logger.error("❌ HİÇ MAÇ BULUNAMADI!")
            return {}

        logger.info(f"{len(fikstur)} hafta, {toplam_mac} maç bulundu.")
        return fikstur

    def _mac_bilgisi_cek(self, eleman: BeautifulSoup) -> Optional[Dict[str, str]]:
        """
        Tek bir maç elemanından bilgileri çıkarır.
        """
        try:
            ev_sahibi = eleman.find(class_=re.compile(r'home|ev', re.I))
            deplasman = eleman.find(class_=re.compile(r'away|deplasman', re.I))
            skor = eleman.find(class_=re.compile(r'score|skor', re.I))
            tarih = eleman.find(class_=re.compile(r'date|tarih', re.I))
            
            if ev_sahibi and deplasman:
                return {
                    "ev_sahibi": ev_sahibi.get_text(strip=True),
                    "deplasman": deplasman.get_text(strip=True),
                    "skor": skor.get_text(strip=True) if skor else "-",
                    "tarih": tarih.get_text(strip=True) if tarih else ""
                }
        except:
            pass
        return None

    def veri_dogrula(self) -> bool:
        """
        Çekilen verinin gerçekliğini kontrol eder.
        """
        puan_durumu = self.veri.get("puan_durumu", [])
        fikstur = self.veri.get("fikstur", {})
        
        # Puan durumu kontrolü
        if len(puan_durumu) < 18:
            logger.error(f"❌ PUAN DURUMU EKSİK: {len(puan_durumu)}/18 takım")
            return False
        
        # Takım adları kontrolü
        takim_adlari = [t['takim'] for t in puan_durumu]
        for takim in takim_adlari:
            if not takim or len(takim) < 2:
                logger.error(f"❌ GEÇERSİZ TAKIM ADI: {takim}")
                return False
        
        # Fikstür kontrolü
        if not fikstur:
            logger.error("❌ FİKSTÜR BOŞ!")
            return False
        
        toplam_mac = sum(len(m) for m in fikstur.values())
        if toplam_mac < 9:
            logger.error(f"❌ FİKSTÜR EKSİK: {toplam_mac} maç")
            return False
        
        logger.info("✅ VERİ DOĞRULAMA BAŞARILI!")
        return True

    def veri_cek(self) -> Dict[str, Any]:
        """
        Tüm verileri çeker.
        """
        logger.info("========== GERÇEK VERİ ÇEKME BAŞLATILDI ==========")
        
        # Puan durumu çek
        puan_soup = self.sayfayi_cek(self.puan_durumu_url)
        if not puan_soup:
            logger.error("❌ PUAN DURUMU SAYFASI ÇEKİLEMEDİ!")
            sys.exit(1)
        
        puan_durumu = self.puan_durumunu_cek(puan_soup)
        if not puan_durumu:
            logger.error("❌ PUAN DURUMU VERİSİ ÇEKİLEMEDİ!")
            sys.exit(1)

        # Fikstür çek
        fikstur_soup = self.sayfayi_cek(self.fikstur_url)
        if not fikstur_soup:
            logger.error("❌ FİKSTÜR SAYFASI ÇEKİLEMEDİ!")
            sys.exit(1)
        
        fikstur = self.fikstur_cek(fikstur_soup)
        if not fikstur:
            logger.error("❌ FİKSTÜR VERİSİ ÇEKİLEMEDİ!")
            sys.exit(1)

        # Veriyi yapılandır
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
            "veri_kaynak": "sporx.com",
            "version": "4.0.0",
            "durum": "basarili"
        }

        # Veriyi doğrula
        if not self.veri_dogrula():
            logger.error("❌ VERİ DOĞRULAMA BAŞARISIZ!")
            sys.exit(1)

        logger.info("========== VERİ ÇEKME BAŞARILI ==========")
        return self.veri

    def json_olarak_kaydet(self, dosya_adi: str = "mutlu_tv_lig_verisi.json") -> bool:
        """
        Veriyi JSON olarak kaydeder.
        """
        try:
            with open(dosya_adi, 'w', encoding='utf-8') as f:
                json.dump(self.veri, f, ensure_ascii=False, indent=2)
            logger.info(f"✅ Veri '{dosya_adi}' dosyasına kaydedildi.")
            return True
        except Exception as e:
            logger.error(f"❌ JSON kaydedilirken hata: {str(e)}")
            return False

    def ozet_tablo_goster(self) -> None:
        """
        Puan durumunu konsolda gösterir.
        """
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
    """
    Ana program - SADECE GERÇEK VERİ
    """
    logger.info("Mutlu TV Lig Veri Çekici (SADECE GERÇEK VERİ) başlatıldı.")
    
    cekici = MutluTvLigVeriCekici()
    veri = cekici.veri_cek()
    
    # JSON kaydet
    if not cekici.json_olarak_kaydet():
        sys.exit(1)
    
    # Özet göster
    cekici.ozet_tablo_goster()
    
    logger.info("✅ İşlem BAŞARIYLA tamamlandı!")
    sys.exit(0)


if __name__ == "__main__":
    main()
