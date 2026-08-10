#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mutlu TV Lig Veri Çekici - FLASHSCORE
Flashscore.com.tr'den gerçek verileri çeker.
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
        self.flashscore_url = "https://www.flashscore.com.tr/futbol/turkiye/super-li-g/"
        self.user_agent = os.environ.get("USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
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

    def flashscore_api_ile_cek(self) -> Dict[str, Any]:
        """
        Flashscore'un arka uç API'sinden veri çeker.
        """
        try:
            # Flashscore'un veri API'si
            api_urls = [
                "https://d.flashscore.com.tr/x/feed/d_1_1_tr_1",
                "https://d.flashscore.com.tr/x/feed/d_1_2_tr_1",
                "https://d.flashscore.com.tr/x/feed/s_1_1_tr_1",
                "https://d.flashscore.com.tr/x/feed/d_1_3_tr_1"
            ]
            
            for api_url in api_urls:
                try:
                    logger.info(f"API deneniyor: {api_url}")
                    response = self.session.get(api_url, timeout=self.timeout)
                    if response.status_code == 200:
                        # Flashscore özel formatında veri gelir
                        data = response.text
                        if data and len(data) > 100:
                            logger.info(f"API başarılı: {api_url}")
                            return self._flashscore_verisi_parse(data)
                except:
                    continue
            
            # Ana sayfadan JSON-LD bul
            html = self.sayfayi_cek(self.flashscore_url)
            if not html:
                return {}
            
            # JSON-LD verilerini bul
            json_ld_matches = re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)
            for json_str in json_ld_matches:
                try:
                    data = json.loads(json_str.strip())
                    if data and isinstance(data, dict):
                        logger.info("JSON-LD verisi bulundu.")
                        return data
                except:
                    continue
            
            # __NEXT_DATA__ bul
            next_data = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
            if next_data:
                try:
                    data = json.loads(next_data.group(1))
                    logger.info("__NEXT_DATA__ bulundu.")
                    return data
                except:
                    pass
            
            # JavaScript değişkenleri
            js_matches = re.findall(r'var\s+(\w+)\s*=\s*({.*?});', html, re.DOTALL)
            for var_name, var_value in js_matches:
                try:
                    if 'standings' in var_name.lower() or 'table' in var_name.lower():
                        data = json.loads(var_value)
                        logger.info(f"JavaScript değişkeni bulundu: {var_name}")
                        return data
                except:
                    continue
            
            return {}
            
        except Exception as e:
            logger.error(f"Flashscore API hatası: {str(e)}")
            return {}

    def _flashscore_verisi_parse(self, raw_data: str) -> Dict[str, Any]:
        """
        Flashscore'un özel veri formatını parse eder.
        """
        try:
            # Flashscore verisi genellikle ~ işareti ile ayrılmış alanlardan oluşur
            # Örnek: "~1~2~3~" şeklinde
            parts = raw_data.split('~')
            
            # Takım bilgilerini bul
            teams = []
            for i, part in enumerate(parts):
                if 'team' in part.lower() or 'takim' in part.lower():
                    teams.append(part)
            
            # Puan durumu verilerini çıkar
            standings = []
            for i in range(0, len(parts) - 10, 10):
                if len(parts[i:i+10]) == 10:
                    try:
                        item = {
                            'position': int(parts[i]) if parts[i].isdigit() else 0,
                            'team': parts[i+1] if i+1 < len(parts) else '',
                            'played': int(parts[i+2]) if i+2 < len(parts) and parts[i+2].isdigit() else 0,
                            'wins': int(parts[i+3]) if i+3 < len(parts) and parts[i+3].isdigit() else 0,
                            'draws': int(parts[i+4]) if i+4 < len(parts) and parts[i+4].isdigit() else 0,
                            'losses': int(parts[i+5]) if i+5 < len(parts) and parts[i+5].isdigit() else 0,
                            'goals_for': int(parts[i+6]) if i+6 < len(parts) and parts[i+6].isdigit() else 0,
                            'goals_against': int(parts[i+7]) if i+7 < len(parts) and parts[i+7].isdigit() else 0,
                            'points': int(parts[i+8]) if i+8 < len(parts) and parts[i+8].isdigit() else 0
                        }
                        if item['team'] and len(item['team']) > 1:
                            standings.append(item)
                    except:
                        continue
            
            if standings:
                logger.info(f"{len(standings)} takım bulundu.")
                return {'standings': standings}
            
            return {}
            
        except Exception as e:
            logger.error(f"Flashscore parse hatası: {str(e)}")
            return {}

    def puan_durumunu_olustur(self, data: Dict) -> List[Dict[str, Any]]:
        """
        API verisinden puan durumu oluşturur.
        """
        puan_durumu = []
        
        try:
            standings = None
            
            if 'standings' in data:
                standings = data['standings']
            elif 'table' in data:
                standings = data['table']
            elif 'data' in data and isinstance(data['data'], dict):
                if 'standings' in data['data']:
                    standings = data['data']['standings']
            
            if not standings:
                logger.error("❌ Puan durumu verisi bulunamadı!")
                return []
            
            if isinstance(standings, list):
                for item in standings:
                    takim = self._takim_verisi_cek(item)
                    if takim:
                        puan_durumu.append(takim)
            elif isinstance(standings, dict):
                for key, value in standings.items():
                    if isinstance(value, list):
                        for item in value:
                            takim = self._takim_verisi_cek(item)
                            if takim:
                                puan_durumu.append(takim)
            
            # Sıraya göre sırala
            puan_durumu.sort(key=lambda x: x.get('sira', 999))
            
            logger.info(f"{len(puan_durumu)} takım verisi oluşturuldu.")
            
        except Exception as e:
            logger.error(f"Puan durumu oluşturulurken hata: {str(e)}")
        
        return puan_durumu

    def _takim_verisi_cek(self, item: Dict) -> Optional[Dict[str, Any]]:
        """
        Tek bir takım verisini çıkarır.
        """
        try:
            takim_adi = (
                item.get('team') or 
                item.get('team_name') or 
                item.get('name') or 
                item.get('club') or
                item.get('takim') or
                ''
            )
            
            if not takim_adi:
                return None
            
            return {
                "sira": self._safe_int(item.get('position') or item.get('rank') or item.get('sira') or 0),
                "takim": takim_adi.strip(),
                "oynanan": self._safe_int(item.get('played') or item.get('matches') or item.get('oynanan') or 0),
                "galibiyet": self._safe_int(item.get('wins') or item.get('won') or item.get('galibiyet') or 0),
                "beraberlik": self._safe_int(item.get('draws') or item.get('draw') or item.get('beraberlik') or 0),
                "maglubiyet": self._safe_int(item.get('losses') or item.get('lost') or item.get('maglubiyet') or 0),
                "atilan_gol": self._safe_int(item.get('goals_for') or item.get('scored') or item.get('atilan_gol') or 0),
                "yenilen_gol": self._safe_int(item.get('goals_against') or item.get('conceded') or item.get('yenilen_gol') or 0),
                "averaj": self._safe_int(item.get('goal_diff') or item.get('averaj') or 0),
                "puan": self._safe_int(item.get('points') or item.get('puan') or 0),
                "durum": item.get('status') or item.get('durum') or ''
            }
        except Exception as e:
            logger.debug(f"Takım verisi hatası: {str(e)}")
            return None

    def _safe_int(self, value) -> int:
        try:
            return int(float(str(value).strip())) if value else 0
        except:
            return 0

    def veri_dogrula(self) -> bool:
        puan_durumu = self.veri.get("puan_durumu", [])
        
        if len(puan_durumu) < 18:
            logger.error(f"❌ PUAN DURUMU EKSİK: {len(puan_durumu)}/18 takım")
            return False
        
        for takim in puan_durumu:
            if not takim.get('takim') or len(takim['takim']) < 2:
                logger.error(f"❌ GEÇERSİZ TAKIM ADI: {takim.get('takim')}")
                return False
        
        logger.info("✅ VERİ DOĞRULAMA BAŞARILI!")
        return True

    def veri_cek(self) -> Dict[str, Any]:
        logger.info("========== FLASHSCORE VERİ ÇEKME BAŞLATILDI ==========")
        
        data = self.flashscore_api_ile_cek()
        if not data:
            logger.error("❌ FLASHSCORE VERİSİ ÇEKİLEMEDİ!")
            sys.exit(1)
        
        puan_durumu = self.puan_durumunu_olustur(data)
        if not puan_durumu:
            logger.error("❌ PUAN DURUMU VERİSİ ÇEKİLEMEDİ!")
            sys.exit(1)

        self.veri = {
            "site_adi": self.site_adi,
            "sezon": self.sezon,
            "guncelleme_tarihi": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "puan_durumu": puan_durumu,
            "fikstur": {"hafta_1": []},
            "kaynak": "flashscore.com.tr",
            "version": "11.0.0",
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
        print(f"📡 Kaynak: {self.veri.get('kaynak', 'Bilinmiyor')}")
        print("="*100)
        print(f"{'Sira':<4} {'Takim':<25} {'O':<3} {'G':<3} {'B':<3} {'M':<3} {'A':<3} {'Y':<3} {'Av':<5} {'P':<4}")
        print("-"*100)
        
        for takim in puan_durumu:
            print(f"{takim.get('sira', 0):<4} {takim.get('takim', '')[:25]:<25} {takim.get('oynanan', 0):<3} {takim.get('galibiyet', 0):<3} {takim.get('beraberlik', 0):<3} {takim.get('maglubiyet', 0):<3} {takim.get('atilan_gol', 0):<3} {takim.get('yenilen_gol', 0):<3} {takim.get('averaj', 0):<5} {takim.get('puan', 0):<4}")
        print("="*100)


def main():
    logger.info("Mutlu TV Lig Veri Çekici (FLASHSCORE) başlatıldı.")
    
    cekici = MutluTvLigVeriCekici()
    veri = cekici.veri_cek()
    
    if not cekici.json_olarak_kaydet():
        sys.exit(1)
    
    cekici.ozet_tablo_goster()
    logger.info("✅ İşlem BAŞARIYLA tamamlandı!")
    sys.exit(0)


if __name__ == "__main__":
    main()
