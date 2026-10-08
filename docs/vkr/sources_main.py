# -*- coding: utf-8 -*-
"""Источники основной части ВКР. Ключи совпадают с разделом экономики там, где
источник общий (ali, alfa, nrc, evk, ieee, wfa, bas) — текст скопирован дословно.
08.10: запись nrc разделена на две (nrc — NRC7394, nrc7292 — NRC7292), у каждой один URL.

Выходные данные научных статей сверены по базам 27.09.2026 (arXiv, ScienceDirect,
MDPI, IEEE Xplore, ResearchGate).
"""

SOURCES = {
    # --- стандарты, регулирование, государственные документы
    "ieee": "IEEE Std 802.11ah-2016. IEEE Standard for Information technology — Telecommunications "
            "and information exchange between systems. Local and metropolitan area networks — "
            "Specific requirements. Part 11: Wireless LAN Medium Access Control (MAC) and Physical "
            "Layer (PHY) Specifications. Amendment 2: Sub 1 GHz License Exempt Operation. – New "
            "York : IEEE, 2017. – 594 p. – DOI 10.1109/IEEESTD.2017.7920364. – Текст : электронный "
            "// IEEE Xplore : [сайт]. – URL: https://ieeexplore.ieee.org/document/7920364 (дата "
            "обращения: 08.10.2026).",
    "wfa": "Wi-Fi HaLow. – Текст : электронный // Wi-Fi Alliance : [сайт]. – URL: "
           "https://www.wi-fi.org/discover-wi-fi/wi-fi-halow (дата обращения: 24.09.2026).",
    "gkrch": "О выделении полос радиочастот устройствам малого радиуса действия : решение ГКРЧ при "
             "Мининформсвязи России от 07.05.2007 № 07-20-03-001 (ред. от 24.12.2018). – Текст : "
             "электронный // ГАРАНТ.РУ : информационно-правовой портал. – URL: "
             "https://base.garant.ru/192210/ (дата обращения: 08.10.2026).",
    "gkrch2018": "О выделении полос радиочастот, внесении изменений в решения ГКРЧ и продлении срока "
                 "действия решений ГКРЧ : решение ГКРЧ при Минкомсвязи России от 11.09.2018 "
                 "№ 18-46-03-1. – Текст : электронный // ГАРАНТ.РУ : информационно-правовой портал. "
                 "– URL: https://base.garant.ru/72061772/ (дата обращения: 08.10.2026).",
    "bas": "Паспорт национального проекта «Беспилотные авиационные системы» (2024–2030 гг.). – Текст : "
           "электронный // КонсультантПлюс : [сайт]. – URL: "
           "https://www.consultant.ru/document/cons_doc_LAW_310251/ (дата обращения: 24.09.2026).",
    "gov": "Правительство закрепило решение о распределении радиочастот для создания единой "
           "инфраструктуры управления гражданскими беспилотниками. – Текст : электронный // "
           "Правительство России : [сайт]. – URL: http://government.ru/docs/49544/ "
           "(дата обращения: 27.09.2026).",
    # --- научные работы по IEEE 802.11ah и LoRa
    "adame": "IEEE 802.11AH : the WiFi approach for M2M communications / T. Adame, A. Bel, "
             "B. Bellalta [et al.] // IEEE Wireless Communications. – 2014. – Vol. 21, no. 6. – "
             "P. 144–152. – DOI 10.1109/MWC.2014.7000982. – Текст : электронный.",
    "khorov": "A survey on IEEE 802.11ah : An enabling networking technology for smart cities / "
              "E. Khorov, A. Lyakhov, A. Krotov [et al.] // Computer Communications. – 2015. – "
              "Vol. 58. – P. 53–69. – Текст : электронный.",
    "tian": "Wi-Fi HaLow for the Internet of Things : An up-to-date survey on IEEE 802.11ah research / "
            "L. Tian, S. Santi, A. Seferagić [et al.] // Journal of Network and Computer Applications. "
            "– 2021. – Vol. 182. – Art. 103036. – Текст : электронный.",
    "chounos": "Chounos, K. Scalability and Performance Evaluation of IEEE 802.11ah IoT Deployments : "
               "A Testbed Approach / K. Chounos, K. Kyriakou, T. Korakis. – 2025. – arXiv:2508.03146. "
               "– Текст : электронный // arXiv.org : [сайт]. – URL: https://arxiv.org/abs/2508.03146 "
               "(дата обращения: 27.09.2026).",
    # --- теория распространения и связи
    "aust": "Aust, S. Sub 1GHz wireless LAN propagation path loss models for urban smart grid "
            "applications / S. Aust, T. Ito // 2012 International Conference on Computing, Networking "
            "and Communications (ICNC). – Maui : IEEE, 2012. – P. 116–120. – "
            "DOI 10.1109/ICCNC.2012.6167392. – Текст : электронный.",
    "friis": "Friis, H. T. A Note on a Simple Transmission Formula / H. T. Friis // Proceedings of the "
             "IRE. – 1946. – Vol. 34, no. 5. – P. 254–256. – Текст : электронный.",
    "rappaport": "Rappaport, T. S. Wireless Communications : Principles and Practice / T. S. "
                 "Rappaport. – 2nd ed. – Upper Saddle River : Prentice Hall PTR, 2002. – XXIII, 707 "
                 "p. – ISBN 0-13-042232-0. – Текст : непосредственный.",
    "shannon": "Shannon, C. E. A Mathematical Theory of Communication / C. E. Shannon // Bell System "
               "Technical Journal. – 1948. – Vol. 27, no. 3. – P. 379–423. – Текст : электронный.",
    # --- аппаратура и программные средства
    "ali": "LILYGO T-Halow ESP32-S3 Development Board, Wi-Fi HaLow. – Текст : электронный // "
           "AliExpress : [сайт]. – URL: https://www.aliexpress.com/item/1005007402959136.html "
           "(дата обращения: 24.09.2026).",
    "alfa": "ALFA Network AHPI7292S IEEE 802.11ah sub 1 GHz module in Raspberry Pi HAT form factor. – "
            "Текст : электронный // Rokland : [сайт]. – URL: https://store.rokland.com/products/"
            "alfa-network-ahpi7292s-ieee-802-11ah-sub-1-ghz-module-in-raspberry-pi-hat-form-factor "
            "(дата обращения: 24.09.2026).",
    "nrc": "NRC7394 Evaluation Kit Purchase page. – Текст : электронный // NEWRACOM : [сайт]. – URL: "
           "https://newracom.com/nrc7394-evaluation-kit-purchase-page (дата обращения: 24.09.2026).",
    "nrc7292": "NRC7292 EVK. – Текст : электронный // NEWRACOM : [сайт]. – URL: "
               "https://newracom.com/products/nrc7292-evk (дата обращения: 24.09.2026).",
    "evk": "MM6108-EKH05-05US, WiFi Development Tools — 802.11 Wi-Fi HaLow IoT Development Board. – "
           "Текст : электронный // ЧИП и ДИП : [сайт]. – URL: https://chipdip.ru/product0/8040419288 "
           "(дата обращения: 24.09.2026).",
    "lilygo": "T-Halow : исходные тексты, схема платы, комплект разработки модуля TX-AH / LilyGO "
              "(Xinyuan-LilyGO). – Текст : электронный // GitHub : [сайт]. – URL: "
              "https://github.com/Xinyuan-LilyGO/T-Halow (дата обращения: 27.09.2026).",
    "esp32s3": "ESP32-S3 Series Datasheet : version 1.1 / Espressif Systems. – 2022. – Текст : "
               "электронный // GitHub : копия в репозитории Xinyuan-LilyGO/T-Display-S3-AMOLED "
               "(doc/esp32-s3_datasheet_en.pdf). – URL: https://github.com/Xinyuan-LilyGO/"
               "T-Display-S3-AMOLED/blob/main/doc/esp32-s3_datasheet_en.pdf (дата обращения: 08.10.2026).",
    "espidf": "ESP-IDF : Espressif IoT Development Framework : ветка 4.4, файл components/soc/esp32s3/"
              "include/soc/soc_caps.h / Espressif Systems. – Текст : электронный // GitHub : [сайт]. "
              "– URL: https://github.com/espressif/esp-idf (дата обращения: 27.09.2026).",
    # --- исходные материалы из задания на ВКР
    "smirnova": "Технологии современных беспроводных сетей Wi-Fi : учебное пособие / Е. В. "
                "Смирнова, А. В. Пролетарский, Е. А. Ромашкина [и др.] ; под общей редакцией А. В. "
                "Пролетарского. – Москва : Издательство МГТУ им. Н. Э. Баумана, 2017. – 448 с. – "
                "(Компьютерные системы и сети ; вып. 2). – ISBN 978-5-7038-4620-9. – Текст : "
                "непосредственный.",
    "koshkin": "Кошкин, Р. П. Беспилотные авиационные системы / Р. П. Кошкин. – Москва : "
               "Стратегические приоритеты, 2016. – 676 с. – Текст : непосредственный.",
    # --- открытые данные для сравнения (проверены по первоисточникам 08.10.2026)
    "txspec": "泰芯 802.11ah TX-AH-Rx00P 系列模组技术规格书 [Технические характеристики модулей серии "
              "TX-AH-Rx00P] : версия V6.2 от 16.11.2023 / Zhuhai Taixin Semiconductor Co., Ltd. – "
              "Текст : электронный // GitHub : репозиторий Xinyuan-LilyGO/T-Halow. – URL: "
              "https://github.com/Xinyuan-LilyGO/T-Halow/tree/master/hardware/TX_AH "
              "(дата обращения: 08.10.2026).",
    "txbridge": "泰芯 AH 网桥使用说明 [Руководство по использованию моста AH] : версия V1.3.4 от "
                "07.09.2023 / Zhuhai Taixin Semiconductor Co., Ltd. – Текст : электронный // GitHub : "
                "репозиторий Xinyuan-LilyGO/T-Halow. – URL: https://github.com/Xinyuan-LilyGO/T-Halow/"
                "tree/master/hardware/TX_AH (дата обращения: 08.10.2026).",
    "linuxs1g": "Linux kernel source tree : net/wireless/util.c, функция "
                "cfg80211_calculate_bitrate_s1g / L. Torvalds [и др.]. – Текст : электронный // "
                "GitHub : [сайт]. – URL: https://github.com/torvalds/linux/blob/master/net/wireless/"
                "util.c (дата обращения: 08.10.2026).",
    "espwifi": "ESP-IDF Programming Guide v5.5.5. Wi-Fi Driver : разделы «ESP32-S3 Wi-Fi Throughput», "
               "«Long Range (LR)» / Espressif Systems. – Текст : электронный // GitHub : espressif/"
               "esp-idf, docs/en/api-guides/wifi.rst. – URL: https://github.com/espressif/esp-idf/blob/"
               "v5.5.5/docs/en/api-guides/wifi.rst (дата обращения: 08.10.2026).",
    "esp32cam": "ESP32-CAM Performance Reference Benchmark : dataset / TNeutron. – 2025. – Текст : "
                "электронный // GitHub : [сайт]. – URL: https://github.com/TNeutron/"
                "ESP32-CAM-Performence-Reference-Benchmark (дата обращения: 08.10.2026).",
    "tr38901": "Sionna : src/sionna/phy/channel/tr38901/lsp.py (модель потерь проникновения 3GPP "
               "TR 38.901, п. 7.4.3.1) / NVIDIA (NVlabs). – Текст : электронный // GitHub : [сайт]. – "
               "URL: https://github.com/NVlabs/sionna (дата обращения: 08.10.2026).",
    "an1200": "AN1200.22. LoRa Modulation Basics : application note, revision 2 / Semtech Corporation. "
              "– 2015. – Текст : электронный // GitHub : ExpressLRS/ExpressLRS-Hardware, "
              "Doc/an1200.22.pdf. – URL: https://github.com/ExpressLRS/ExpressLRS-Hardware/tree/master/"
              "Doc (дата обращения: 08.10.2026).",
    "meshtastic": "Radio Settings ; LoRa Region by Country / Meshtastic. – Текст : электронный // "
                  "GitHub : meshtastic/meshtastic. – URL: https://github.com/meshtastic/meshtastic/blob/"
                  "master/docs/about/overview/radio-settings.mdx (дата обращения: 08.10.2026).",
    "elrshealth": "Signal Health / ExpressLRS. – Текст : электронный // GitHub : ExpressLRS/Docs. – "
                  "URL: https://github.com/ExpressLRS/Docs/blob/master/docs/info/signal-health.md "
                  "(дата обращения: 08.10.2026).",
    "elrsrange": "Long Range / ExpressLRS. – Текст : электронный // GitHub : ExpressLRS/Docs. – URL: "
                 "https://github.com/ExpressLRS/Docs/blob/master/docs/info/long-range.md "
                 "(дата обращения: 08.10.2026).",
    "robinson": "Robinson, S. SX12XX-LoRa : What is LoRa ; ReadMe / S. Robinson. – Текст : электронный "
                "// GitHub : [сайт]. – URL: https://github.com/StuartsProjects/SX12XX-LoRa "
                "(дата обращения: 08.10.2026).",
    "cattani": "Cattani, M. An Experimental Evaluation of the Reliability of LoRa Long-Range Low-Power "
               "Wireless Communication / M. Cattani, C. A. Boano, K. Römer // Journal of Sensor and "
               "Actuator Networks. – 2017. – Vol. 6, no. 2. – Art. 7. – DOI 10.3390/jsan6020007. – "
               "Текст : электронный.",
    "elrs": "ExpressLRS : open source radio link for RC applications. – Текст : электронный // "
            "ExpressLRS : [сайт]. – URL: https://www.expresslrs.org (дата обращения: 27.09.2026).",
}
