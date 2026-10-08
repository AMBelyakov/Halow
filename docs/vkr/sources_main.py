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
            "and information exchange between systems. Local and metropolitan area networks — Specific "
            "requirements. Part 11: Wireless LAN Medium Access Control (MAC) and Physical Layer (PHY) "
            "Specifications. Amendment 2: Sub 1 GHz License Exempt Operation. – IEEE, 2017.",
    "wfa": "Wi-Fi HaLow // Wi-Fi Alliance. – URL: https://www.wi-fi.org/discover-wi-fi/wi-fi-halow "
           "(дата обращения: 24.09.2026).",
    "gkrch": "О выделении полос радиочастот устройствам малого радиуса действия : решение ГКРЧ при "
             "Мининформсвязи России от 07.05.2007 № 07-20-03-001 (с изм. и доп.). – Текст : "
             "электронный. – URL: https://base.garant.ru/192210/ (дата обращения: 08.10.2026).",
    "gkrch2018": "О выделении полос радиочастот, внесении изменений в решения ГКРЧ и продлении срока "
                 "действия решений ГКРЧ : решение ГКРЧ при Минкомсвязи России от 11.09.2018 "
                 "№ 18-46-03-1. – Текст : электронный. – URL: https://base.garant.ru/72061772/ "
                 "(дата обращения: 08.10.2026).",
    "bas": "Паспорт национального проекта «Беспилотные авиационные системы» (2024–2030 гг.) // "
           "КонсультантПлюс. – URL: https://www.consultant.ru/document/cons_doc_LAW_310251/ "
           "(дата обращения: 24.09.2026).",
    "gov": "Правительство закрепило решение о распределении радиочастот для создания единой "
           "инфраструктуры управления гражданскими беспилотниками // Правительство России. – URL: "
           "http://government.ru/docs/49544/ (дата обращения: 27.09.2026).",
    # --- научные работы по IEEE 802.11ah и LoRa
    "adame": "Adame T., Bel A., Bellalta B., Barcelo J., Oliver M. IEEE 802.11AH: the WiFi approach for "
             "M2M communications // IEEE Wireless Communications. – 2014. – Vol. 21, no. 6. – "
             "P. 144–152. – DOI: 10.1109/MWC.2014.7000982.",
    "khorov": "Khorov E., Lyakhov A., Krotov A., Guschin A. A survey on IEEE 802.11ah: An enabling "
              "networking technology for smart cities // Computer Communications. – 2015. – Vol. 58. – "
              "P. 53–69.",
    "tian": "Tian L., Santi S., Seferagić A., Lan J., Famaey J. Wi-Fi HaLow for the Internet of Things: "
            "An up-to-date survey on IEEE 802.11ah research // Journal of Network and Computer "
            "Applications. – 2021. – Vol. 182. – Art. 103036.",
    "chounos": "Chounos K., Kyriakou K., Korakis T. Scalability and Performance Evaluation of IEEE "
               "802.11ah IoT Deployments: A Testbed Approach. – 2025. – arXiv:2508.03146. – URL: "
               "https://arxiv.org/abs/2508.03146 (дата обращения: 27.09.2026).",
    "augustin": "Augustin A., Yi J., Clausen T., Townsley W. M. A Study of LoRa: Long Range & Low Power "
                "Networks for the Internet of Things // Sensors. – 2016. – Vol. 16, no. 9. – "
                "Art. 1466. – DOI: 10.3390/s16091466.",
    # --- теория распространения и связи
    "aust": "Aust S., Ito T. Sub 1GHz wireless LAN propagation path loss models for urban smart grid "
            "applications // 2012 International Conference on Computing, Networking and Communications "
            "(ICNC). – Maui : IEEE, 2012. – P. 116–120. – DOI: 10.1109/ICCNC.2012.6167392.",
    "friis": "Friis H. T. A Note on a Simple Transmission Formula // Proceedings of the IRE. – 1946. – "
             "Vol. 34, no. 5. – P. 254–256.",
    "rappaport": "Rappaport T. S. Wireless Communications: Principles and Practice. – 2nd ed. – Upper "
                 "Saddle River : Prentice Hall, 2002.",
    "shannon": "Shannon C. E. A Mathematical Theory of Communication // Bell System Technical Journal. "
               "– 1948. – Vol. 27, no. 3. – P. 379–423.",
    # --- аппаратура и программные средства
    "ali": "LILYGO T-Halow ESP32-S3 Development Board, Wi-Fi HaLow // AliExpress. – URL: "
           "https://www.aliexpress.com/item/1005007402959136.html (дата обращения: 24.09.2026).",
    "alfa": "ALFA Network AHPI7292S IEEE 802.11ah sub 1 GHz module in Raspberry Pi HAT form factor // "
            "Rokland. – URL: https://store.rokland.com/products/alfa-network-ahpi7292s-ieee-802-11ah-sub-1-"
            "ghz-module-in-raspberry-pi-hat-form-factor (дата обращения: 24.09.2026).",
    "nrc": "NRC7394 Evaluation Kit Purchase page // NEWRACOM. – URL: "
           "https://newracom.com/nrc7394-evaluation-kit-purchase-page (дата обращения: 24.09.2026).",
    "nrc7292": "NRC7292 EVK // NEWRACOM. – URL: https://newracom.com/products/nrc7292-evk "
               "(дата обращения: 24.09.2026).",
    "evk": "MM6108-EKH05-05US, WiFi Development Tools – 802.11 Wi-Fi HaLow IoT Development Board // "
           "ЧИП и ДИП. – URL: https://chipdip.ru/product0/8040419288 (дата обращения: 24.09.2026).",
    "lilygo": "LilyGO T-Halow: исходные тексты, схема платы, комплект разработки модуля TX-AH // GitHub. "
              "– URL: https://github.com/Xinyuan-LilyGO/T-Halow (дата обращения: 27.09.2026).",
    "esp32s3": "ESP32-S3 Series Datasheet : version 1.1 / Espressif Systems. – 2022. – Текст : "
               "электронный // GitHub : копия в репозитории Xinyuan-LilyGO/T-Display-S3-AMOLED "
               "(doc/esp32-s3_datasheet_en.pdf). – URL: https://github.com/Xinyuan-LilyGO/"
               "T-Display-S3-AMOLED/blob/main/doc/esp32-s3_datasheet_en.pdf (дата обращения: 08.10.2026).",
    "espidf": "ESP-IDF: Espressif IoT Development Framework, ветка 4.4, файл components/soc/esp32s3/"
              "include/soc/soc_caps.h // GitHub. – URL: https://github.com/espressif/esp-idf "
              "(дата обращения: 27.09.2026).",
    # --- исходные материалы из задания на ВКР
    "smirnova": "Смирнова Е. В., Пролетарский А. В. [и др.] Технологии современных беспроводных "
                "сетей Wi-Fi : учебное пособие. – М. : Изд-во МГТУ им. Н. Э. Баумана, 2017. – 446 с.",
    "koshkin": "Кошкин Р. П. Беспилотные авиационные системы. – М. : Стратегические приоритеты, "
               "2016. – 676 с.",
    # --- открытые данные для сравнения (проверены по первоисточникам 08.10.2026)
    "txspec": "Технические характеристики модулей серии TX-AH-Rx00P [泰芯 802.11ah TX-AH-Rx00P 系列模组"
              "技术规格书] : версия V6.2 от 16.11.2023 / Zhuhai Taixin Semiconductor Co., Ltd. – Текст : "
              "электронный // GitHub : репозиторий Xinyuan-LilyGO/T-Halow. – URL: https://github.com/"
              "Xinyuan-LilyGO/T-Halow/tree/master/hardware/TX_AH (дата обращения: 08.10.2026).",
    "txbridge": "Руководство по использованию моста AH [泰芯 AH 网桥使用说明] : версия V1.3.4 от "
                "07.09.2023 / Zhuhai Taixin Semiconductor Co., Ltd. – Текст : электронный // GitHub : "
                "репозиторий Xinyuan-LilyGO/T-Halow. – URL: https://github.com/Xinyuan-LilyGO/T-Halow/"
                "tree/master/hardware/TX_AH (дата обращения: 08.10.2026).",
    "linuxs1g": "Linux kernel source tree : net/wireless/util.c, функция "
                "cfg80211_calculate_bitrate_s1g / L. Torvalds [и др.]. – Текст : электронный // GitHub. "
                "– URL: https://github.com/torvalds/linux/blob/master/net/wireless/util.c "
                "(дата обращения: 08.10.2026).",
    "espwifi": "ESP-IDF Programming Guide v5.5.5. Wi-Fi Driver : разделы «ESP32-S3 Wi-Fi Throughput», "
               "«Long Range (LR)» / Espressif Systems. – Текст : электронный // GitHub : espressif/"
               "esp-idf, docs/en/api-guides/wifi.rst. – URL: https://github.com/espressif/esp-idf/blob/"
               "v5.5.5/docs/en/api-guides/wifi.rst (дата обращения: 08.10.2026).",
    "esp32cam": "ESP32-CAM Performance Reference Benchmark : dataset / TNeutron. – 2025. – Текст : "
                "электронный // GitHub. – URL: https://github.com/TNeutron/"
                "ESP32-CAM-Performence-Reference-Benchmark (дата обращения: 08.10.2026).",
    "tr38901": "Sionna : src/sionna/phy/channel/tr38901/lsp.py (модель потерь проникновения 3GPP "
               "TR 38.901, п. 7.4.3.1) / NVIDIA (NVlabs). – Текст : электронный // GitHub. – URL: "
               "https://github.com/NVlabs/sionna (дата обращения: 08.10.2026).",
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
    "robinson": "Robinson S. SX12XX-LoRa : What is LoRa ; ReadMe. – Текст : электронный // GitHub. – "
                "URL: https://github.com/StuartsProjects/SX12XX-LoRa (дата обращения: 08.10.2026).",
    "cattani": "Cattani M., Boano C. A., Römer K. An Experimental Evaluation of the Reliability of LoRa "
               "Long-Range Low-Power Wireless Communication // Journal of Sensor and Actuator "
               "Networks. – 2017. – Vol. 6, № 2. – Art. 7. – DOI: 10.3390/jsan6020007.",
    "elrs": "ExpressLRS: open source radio link for RC applications // ExpressLRS. – URL: "
            "https://www.expresslrs.org (дата обращения: 27.09.2026).",
}
