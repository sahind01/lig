#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mutlu TV Lig Veri Çekici - GERÇEK VERİ (FİNAL)
Sporx.com'dan gerçek puan durumu ve fikstür verilerini çeker.
Demo veya örnek veri KESİNLİKLE kullanılmaz.
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
        self.user_agent = os.environ.get("USER_AGENT", "MutluTVLigBot/4.0 (+https://mutlutvlig.com)")
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
        
        try:
            # Tabloyu bul - premium-standings içindeki tablo
            standings_div = soup.find('div', class_='premium-standings')
            if not standings_div:
                logger.error("❌ Puan durumu div'i bulunamadı!")
                return []
            
            tablo = standings_div.find('table', class_='premium-table')
            if not tablo:
                logger.error("❌ Puan durumu tablosu bulunamadı!")
                return []
            
            # Tablo gövdelerini bul - genel sıralama
            tbody = tablo.find('tbody', id='genel')
            if not tbody:
                logger.error("❌ Genel sıralama tablosu bulunamadı!")
                return []
            
            satirlar = tbody.find_all('tr')
            logger.info(f"Puan durumu: {len(satirlar)} satır bulundu.")
            
            for satir in satirlar:
                try:
                    # Sıra
                    sira_td = satir.find('td', class_='td-order')
                    if not sira_td:
                        continue
                    
                    sira_span = sira_td.find('span', class_='position-number')
                    sira = int(sira_span.get_text(strip=True)) if sira_span else 0
                    
                    # Logo
                    logo_td = satir.find('td', class_='td-logo')
                    logo_img = logo_td.find('img') if logo_td else None
                    logo_url = logo_img.get('src', '') if logo_img else ''
                    
                    # Takım adı
                    takim_td = satir.find('td', class_='td-team')
                    takim_link = takim_td.find('a') if takim_td else None
                    takim_adi = takim_link.get_text(strip=True) if takim_link else ''
                    
                    # İstatistikler
                    hucreler = satir.find_all('td')
                    if len(hucreler) < 13:
                        continue
                    
                    # O, G, B, M, A, Y, Av, P
                    oynanan = self._safe_int(hucreler[4].get_text(strip=True)) if len(hucreler) > 4 else 0
                    galibiyet = self._safe_int(hucreler[5].get_text(strip=True)) if len(hucreler) > 5 else 0
                    beraberlik = self._safe_int(hucreler[6].get_text(strip=True)) if len(hucreler) > 6 else 0
                    maglubiyet = self._safe_int(hucreler[7].get_text(strip=True)) if len(hucreler) > 7 else 0
                    atilan_gol = self._safe_int(hucreler[8].get_text(strip=True)) if len(hucreler) > 8 else 0
                    yenilen_gol = self._safe_int(hucreler[9].get_text(strip=True)) if len(hucreler) > 9 else 0
                    averaj = self._safe_int(hucreler[10].get_text(strip=True)) if len(hucreler) > 10 else 0
                    puan = self._safe_int(hucreler[11].get_text(strip=True)) if len(hucreler) > 11 else 0
                    
                    # Durum
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
                        logger.debug(f"{sira}. {takim_adi}: {puan} puan")
                        
                except Exception as e:
                    logger.warning(f"Satır işlenirken hata: {str(e)}")
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

    def fikstur_cek(self, soup: BeautifulSoup) -> Dict[str, List[Dict[str, str]]]:
        """
        Fikstür sayfasından gerçek maçları çeker.
        """
        fikstur = {}
        
        try:
            # Fikstür tablosunu bul
            fixture_div = soup.find('div', class_='box-fixture')
            if not fixture_div:
                logger.error("❌ Fikstür div'i bulunamadı!")
                return {}
            
            tablo = fixture_div.find('table', class_='table-fixture')
            if not tablo:
                logger.error("❌ Fikstür tablosu bulunamadı!")
                return {}
            
            tbody = tablo.find('tbody', id='fixtureTbody')
            if not tbody:
                logger.error("❌ Fikstür tbody bulunamadı!")
                return {}
            
            # Hafta bilgisi - aktif haftayı bul
            hafta_elemani = fixture_div.find('a', class_='week-item active')
            aktif_hafta = hafta_elemani.get_text(strip=True) if hafta_elemani else "1. Hafta"
            hafta_adi = f"hafta_{aktif_hafta.split('.')[0]}"
            
            fikstur[hafta_adi] = []
            
            # Maçları parse et
            satirlar = tbody.find_all('tr')
            mevcut_tarih = ""
            
            for satir in satirlar:
                # Tarih satırı
                if 'fixture-date-row' in satir.get('class', []):
                    tarih_td = satir.find('td')
                    if tarih_td:
                        mevcut_tarih = tarih_td.get_text(strip=True)
                    continue
                
                # Maç satırı
                if 'fixture-row' in satir.get('class', []):
                    mac = self._mac_bilgisi_cek(satir, mevcut_tarih)
                    if mac:
                        fikstur[hafta_adi].append(mac)
            
            logger.info(f"Fikstür: {len(fikstur[hafta_adi])} maç bulundu.")
            
        except Exception as e:
            logger.error(f"Fikstür çekilirken hata: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
        
        return fikstur

    def _mac_bilgisi_cek(self, satir: BeautifulSoup, tarih: str) -> Optional[Dict[str, str]]:
        """
        Maç satırından bilgileri çıkarır.
        """
        try:
            fixture_item = satir.find('div', class_='fixture-item')
            if not fixture_item:
                return None
            
            # Takım bilgileri
            takim_linkleri = fixture_item.find_all('a', class_='fixture-team-link')
            if len(takim_linkleri) < 2:
                return None
            
            # Ev sahibi
            ev_sahibi_link = takim_linkleri[0]
            ev_sahibi = ev_sahibi_link.find('span', class_='fixture-team-name')
            ev_sahibi_adi = ev_sahibi.get_text(strip=True) if ev_sahibi else ''
            
            # Deplasman
            deplasman_link = takim_linkleri[1]
            deplasman = deplasman_link.find('span', class_='fixture-team-name')
            deplasman_adi = deplasman.get_text(strip=True) if deplasman else ''
            
            # Saat / skor
            sag_taraf = fixture_item.find('a', class_='fixture-side-link')
            saat_span = sag_taraf.find('span', class_='fixture-match-time') if sag_taraf else None
            saat = saat_span.get_text(strip=True) if saat_span else ''
            
            # Skor kontrolü - eğer saat formatında değilse skordur
            skor = saat if re.match(r'^\d+-\d+$', saat) else ''
            saat_bilgisi = saat if not skor else ''
            
            return {
                "ev_sahibi": ev_sahibi_adi,
                "deplasman": deplasman_adi,
                "tarih": tarih,
                "saat": saat_bilgisi,
                "skor": skor
            }
        except Exception as e:
            logger.debug(f"Maç bilgisi çekilirken hata: {str(e)}")
            return None

    def panorama_olustur(self, puan_durumu: List, fikstur: Dict) -> Dict:
        """
        Panorama verisi oluşturur.
        """
        panorama = {
            "lider": puan_durumu[0]['takim'] if puan_durumu else "",
            "lider_puan": puan_durumu[0]['puan'] if puan_durumu else 0,
            "son_sira": puan_durumu[-1]['takim'] if len(puan_durumu) > 1 else "",
            "toplam_takim": len(puan_durumu),
            "guncel_hafta": list(fikstur.keys())[0] if fikstur else "",
            "son_maclar": [],
            "gelecek_maclar": []
        }
        
        # Fikstürden maçları al
        if fikstur:
            for hafta, maclar in fikstur.items():
                for mac in maclar[:3]:
                    if mac.get('skor'):
                        panorama["son_maclar"].append(mac)
                    else:
                        panorama["gelecek_maclar"].append(mac)
        
        return panorama

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
        for takim in puan_durumu:
            if not takim.get('takim') or len(takim['takim']) < 2:
                logger.error(f"❌ GEÇERSİZ TAKIM ADI: {takim.get('takim')}")
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

        # Panorama oluştur
        panorama = self.panorama_olustur(puan_durumu, fikstur)

        # Veriyi yapılandır
        self.veri = {
            "site_adi": self.site_adi,
            "sezon": self.sezon,
            "guncelleme_tarihi": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "puan_durumu": puan_durumu,
            "fikstur": fikstur,
            "panorama": panorama,
            "kaynaklar": {
                "puan_durumu": self.puan_durumu_url,
                "fikstur": self.fikstur_url
            },
            "veri_kaynak": "sporx.com",
            "version": "5.0.0",
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

        # Panorama özeti
        panorama = self.veri.get("panorama", {})
        if panorama:
            print(f"\n📊 PANORAMA:")
            print(f"  • Lider: {panorama.get('lider', '-')} ({panorama.get('lider_puan', 0)} puan)")
            print(f"  • Son sırada: {panorama.get('son_sira', '-')}")
            print(f"  • Toplam takım: {panorama.get('toplam_takim', 0)}")
            print(f"  • Güncel hafta: {panorama.get('guncel_hafta', '-')}")


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
