#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mutlu TV Lig Veri Çekici
Sporx.com'dan Süper Lig verilerini çeker ve JSON olarak kaydeder.
GitHub Actions ile otomatik çalışacak şekilde optimize edilmiştir.
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
    Mutlu TV Lig için Sporx.com veri çekici sınıfı
    """
    
    def __init__(self):
        self.site_adi = "Mutlu TV Lig"
        self.sezon = "2026-2027"
        self.url = "https://m.sporx.com/turkiye-super-lig-puan-durumu"
        self.user_agent = os.environ.get("USER_AGENT", "MutluTVLigBot/1.0 (+https://mutlutvlig.com)")
        self.timeout = 30
        self.veri = {}
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept-Language': 'tr-TR,tr;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })

    def sayfayi_cek(self) -> Optional[BeautifulSoup]:
        """
        Hedef URL'den HTML içeriğini çeker ve BeautifulSoup nesnesi döndürür.
        """
        try:
            logger.info(f"Sayfa çekiliyor: {self.url}")
            response = self.session.get(self.url, timeout=self.timeout)
            response.raise_for_status()
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            logger.info("Sayfa başarıyla çekildi.")
            return soup
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP hatası: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Beklenmeyen hata: {str(e)}")
            return None

    def puan_durumunu_cek(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        BeautifulSoup nesnesinden puan durumu tablosunu ayrıştırır.
        """
        puan_durumu = []
        try:
            # Tabloyu bul - birden fazla tablo olabilir, ilk tabloyu al
            tablo = soup.find('table')
            if not tablo:
                logger.warning("Tablo bulunamadı!")
                return puan_durumu

            satirlar = tablo.find_all('tr')
            logger.info(f"Toplam {len(satirlar)} satır bulundu.")

            for idx, satir in enumerate(satirlar[1:], start=1):  # Başlık satırını atla
                hucreler = satir.find_all(['td', 'th'])
                if len(hucreler) < 8:
                    logger.debug(f"{idx}. satır yetersiz hücre içeriyor: {len(hucreler)}")
                    continue

                try:
                    # Takım adı ve durumu
                    takim_hucresi = hucreler[1]
                    takim_adi = takim_hucresi.get_text(strip=True)
                    
                    # Durum bilgisini çek - özel sınıf veya son sütun
                    durum = ""
                    # Önce özel durum etiketi ara
                    durum_etiketi = takim_hucresi.find('span', class_=re.compile(r'durum|status|badge'))
                    if durum_etiketi:
                        durum = durum_etiketi.get_text(strip=True)
                    elif len(hucreler) > 9:  # Durum sütunu varsa (9. indeks)
                        durum = hucreler[9].get_text(strip=True)
                    else:
                        # Bazı durumlarda tablonun son sütunu durum olabilir
                        durum = hucreler[-1].get_text(strip=True)

                    # Sayısal verileri güvenli şekilde dönüştür
                    def safe_int(value, default=0):
                        try:
                            # Boş veya geçersiz değerleri temizle
                            cleaned = re.sub(r'[^\d-]', '', value.strip())
                            return int(cleaned) if cleaned else default
                        except (ValueError, AttributeError):
                            return default

                    oynanan = safe_int(hucreler[2].get_text(strip=True)) if len(hucreler) > 2 else 0
                    galibiyet = safe_int(hucreler[3].get_text(strip=True)) if len(hucreler) > 3 else 0
                    beraberlik = safe_int(hucreler[4].get_text(strip=True)) if len(hucreler) > 4 else 0
                    maglubiyet = safe_int(hucreler[5].get_text(strip=True)) if len(hucreler) > 5 else 0
                    atilan_gol = safe_int(hucreler[6].get_text(strip=True)) if len(hucreler) > 6 else 0
                    yenilen_gol = safe_int(hucreler[7].get_text(strip=True)) if len(hucreler) > 7 else 0
                    averaj = safe_int(hucreler[8].get_text(strip=True)) if len(hucreler) > 8 else 0
                    puan = safe_int(hucreler[9].get_text(strip=True)) if len(hucreler) > 9 else 0

                    # Takım verisini ekle
                    puan_durumu.append({
                        "sira": idx,
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
                    logger.debug(f"{idx}. takım eklendi: {takim_adi}")

                except IndexError as e:
                    logger.warning(f"{idx}. satırda indeks hatası: {str(e)}")
                    continue
                except Exception as e:
                    logger.warning(f"{idx}. satır işlenirken hata: {str(e)}")
                    continue

            logger.info(f"{len(puan_durumu)} takım başarıyla eklendi.")
            
        except Exception as e:
            logger.error(f"Puan durumu çekilirken hata: {str(e)}")

        return puan_durumu

    def panorama_olustur(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Panorama verilerini oluşturur. Gerçek veri için ayrı sayfalardan çekim yapılmalıdır.
        """
        # Not: Sporx mobil sayfasında panorama genellikle ayrı bir sayfadadır.
        # Bu örnek, veri yapısını göstermek için oluşturulmuştur.
        try:
            # Gerçek uygulamada burada ayrı bir API veya sayfa çağrısı yapılır.
            # Örnek veri:
            panorama = {
                "son_maclar": [
                    {"takim": "Galatasaray", "rakip": "Fenerbahçe", "skor": "2-1", "tarih": "2026-08-09"},
                    {"takim": "Beşiktaş", "rakip": "Trabzonspor", "skor": "0-0", "tarih": "2026-08-08"}
                ],
                "gelecek_maclar": [
                    {"takim": "Fenerbahçe", "rakip": "Galatasaray", "tarih": "2026-08-16"},
                    {"takim": "Trabzonspor", "rakip": "Beşiktaş", "tarih": "2026-08-15"}
                ]
            }
            logger.info("Panorama verisi oluşturuldu.")
            return panorama
        except Exception as e:
            logger.error(f"Panorama oluşturulurken hata: {str(e)}")
            return {"son_maclar": [], "gelecek_maclar": []}

    def fikstur_olustur(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Fikstür verilerini oluşturur. Gerçek veri için ayrı sayfalardan çekim yapılmalıdır.
        """
        try:
            # Gerçek uygulamada burada ayrı bir API veya sayfa çağrısı yapılır.
            fikstur = {
                "hafta_1": [
                    {"ev_sahibi": "Galatasaray", "deplasman": "Gaziantep FK", "tarih": "2026-08-01", "skor": "3-0"},
                    {"ev_sahibi": "Fenerbahçe", "deplasman": "Alanyaspor", "tarih": "2026-08-01", "skor": "1-1"}
                ],
                "hafta_2": [
                    {"ev_sahibi": "Beşiktaş", "deplasman": "Galatasaray", "tarih": "2026-08-08", "skor": "2-2"},
                    {"ev_sahibi": "Trabzonspor", "deplasman": "Fenerbahçe", "tarih": "2026-08-09", "skor": "0-2"}
                ]
            }
            logger.info("Fikstür verisi oluşturuldu.")
            return fikstur
        except Exception as e:
            logger.error(f"Fikstür oluşturulurken hata: {str(e)}")
            return {"hafta_1": [], "hafta_2": []}

    def veri_cek(self) -> Dict[str, Any]:
        """
        Tüm verileri çeken ana fonksiyon.
        """
        logger.info("Veri çekme işlemi başlatılıyor...")
        
        soup = self.sayfayi_cek()
        if not soup:
            logger.error("Sayfa çekilemedi, işlem iptal ediliyor.")
            return {"hata": "Sayfa çekilemedi"}

        puan_durumu = self.puan_durumunu_cek(soup)
        if not puan_durumu:
            logger.warning("Puan durumu boş geldi, kontrol edin.")

        # Veriyi yapılandır
        self.veri = {
            "site_adi": self.site_adi,
            "sezon": self.sezon,
            "guncelleme_tarihi": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "puan_durumu": puan_durumu,
            "panorama": self.panorama_olustur(),
            "fikstur": self.fikstur_olustur(),
            "kaynak_url": self.url,
            "veri_kaynak": "sporx.com",
            "version": "1.0.0"
        }

        # Başarı durumunu logla
        if puan_durumu:
            logger.info(f"Veri çekme başarılı! {len(puan_durumu)} takım eklendi.")
        else:
            logger.warning("Veri çekme kısmen başarılı, puan durumu boş.")

        return self.veri

    def json_olarak_kaydet(self, dosya_adi: str = "mutlu_tv_lig_verisi.json") -> bool:
        """
        Veriyi JSON formatında dosyaya kaydeder.
        """
        try:
            with open(dosya_adi, 'w', encoding='utf-8') as f:
                json.dump(self.veri, f, ensure_ascii=False, indent=2)
            logger.info(f"Veri '{dosya_adi}' dosyasına kaydedildi.")
            return True
        except Exception as e:
            logger.error(f"JSON kaydedilirken hata: {str(e)}")
            return False

    def ozet_tablo_goster(self) -> None:
        """
        Puan durumunu konsolda tablo olarak gösterir.
        """
        puan_durumu = self.veri.get("puan_durumu", [])
        if not puan_durumu:
            print("Gösterilecek puan durumu verisi yok.")
            return

        print("\n" + "="*85)
        print(f"{self.site_adi} - {self.sezon} Sezonu Puan Durumu")
        print(f"Güncelleme: {self.veri.get('guncelleme_tarihi', 'Bilinmiyor')}")
        print("="*85)
        print(f"{'Sira':<4} {'Takim':<22} {'O':<3} {'G':<3} {'B':<3} {'M':<3} {'A':<3} {'Y':<3} {'Av':<4} {'P':<3} {'Durum'}")
        print("-"*85)
        
        for takim in puan_durumu:
            print(f"{takim['sira']:<4} {takim['takim']:<22} {takim['oynanan']:<3} {takim['galibiyet']:<3} {takim['beraberlik']:<3} {takim['maglubiyet']:<3} {takim['atilan_gol']:<3} {takim['yenilen_gol']:<3} {takim['averaj']:<4} {takim['puan']:<3} {takim['durum']}")
        print("="*85)

    def veri_dogrula(self) -> bool:
        """
        Çekilen verinin geçerliliğini kontrol eder.
        """
        if not self.veri:
            return False
        
        puan_durumu = self.veri.get("puan_durumu", [])
        if not puan_durumu:
            logger.error("Veri doğrulama başarısız: Puan durumu boş.")
            return False
        
        # En az 18 takım olmalı (Süper Lig)
        if len(puan_durumu) < 18:
            logger.warning(f"Beklenen takım sayısı 18, ancak {len(puan_durumu)} takım bulundu.")
            # Yine de geçerli sayabiliriz, ama uyarı veririz
        
        # Zorunlu alanları kontrol et
        zorunlu_alanlar = ["sira", "takim", "oynanan", "galibiyet", "beraberlik", 
                          "maglubiyet", "atilan_gol", "yenilen_gol", "averaj", "puan"]
        
        for takim in puan_durumu:
            for alan in zorunlu_alanlar:
                if alan not in takim:
                    logger.error(f"Veri doğrulama başarısız: '{alan}' alanı eksik.")
                    return False
        
        logger.info("Veri doğrulama başarılı.")
        return True


def main():
    """
    Ana program akışı.
    """
    logger.info("Mutlu TV Lig Veri Çekici başlatıldı.")
    
    # Veri çekici sınıfını oluştur
    cekici = MutluTvLigVeriCekici()
    
    # Verileri çek
    veri = cekici.veri_cek()
    
    # Hata kontrolü
    if "hata" in veri:
        logger.error(f"Veri çekilemedi: {veri['hata']}")
        sys.exit(1)
    
    # Veriyi doğrula
    if not cekici.veri_dogrula():
        logger.error("Veri doğrulama başarısız, çıkılıyor.")
        sys.exit(1)
    
    # JSON olarak kaydet
    if not cekici.json_olarak_kaydet():
        logger.error("JSON kaydedilemedi, çıkılıyor.")
        sys.exit(1)
    
    # Özet tabloyu göster
    cekici.ozet_tablo_goster()
    
    # İstatistikleri göster
    puan_durumu = veri.get("puan_durumu", [])
    logger.info(f"Toplam {len(puan_durumu)} takım verisi kaydedildi.")
    
    # Başarılı
    logger.info("İşlem başarıyla tamamlandı.")
    sys.exit(0)


if __name__ == "__main__":
    main()
