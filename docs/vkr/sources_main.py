# -*- coding: utf-8 -*-
"""Источники основной части ВКР. Ключи совпадают с разделом экономики там, где
источник общий (ali, alfa, nrc, evk, ieee, wfa, bas) — текст скопирован дословно.

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
    "gkrch": "Решение ГКРЧ от 07.05.2007 № 07-20-03-001 «О выделении полос радиочастот устройствам "
             "малого радиуса действия» (в действующей редакции).",
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
    "mm3": "Morse Micro Demonstrates World's Longest Range Wi-Fi HaLow Solution, Reaching 3 Kilometers "
           "// Morse Micro. – URL: https://www.morsemicro.com/news/morse-micro-demonstrates-worlds-"
           "longest-range-wi-fi-halow-solution-reaching-3-kilometers (дата обращения: 27.09.2026).",
    "mmjt": "Pushing the limits: Wi-Fi HaLow Testing in Joshua Tree National Park // Morse Micro. – "
            "URL: https://www.morsemicro.com/2024/09/09/pushing-the-limits-wi-fi-halow-testing-in-"
            "joshua-tree-national-park/ (дата обращения: 27.09.2026).",
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
    "nrc": "NRC7394 Evaluation Kit Purchase page; NRC7292 EVK // NEWRACOM. – URL: "
           "https://newracom.com/nrc7394-evaluation-kit-purchase-page ; "
           "https://newracom.com/products/nrc7292-evk (дата обращения: 24.09.2026).",
    "evk": "MM6108-EKH05-05US, WiFi Development Tools – 802.11 Wi-Fi HaLow IoT Development Board // "
           "ЧИП и ДИП. – URL: https://chipdip.ru/product0/8040419288 (дата обращения: 24.09.2026).",
    "lilygo": "LilyGO T-Halow: исходные тексты, схема платы, комплект разработки модуля TX-AH // GitHub. "
              "– URL: https://github.com/Xinyuan-LilyGO/T-Halow (дата обращения: 27.09.2026).",
    "esp32s3": "ESP32-S3 Series Datasheet // Espressif Systems. – URL: https://www.espressif.com/sites/"
               "default/files/documentation/esp32-s3_datasheet_en.pdf (дата обращения: 27.09.2026).",
    "espidf": "ESP-IDF: Espressif IoT Development Framework, ветка 4.4, файл components/soc/esp32s3/"
              "include/soc/soc_caps.h // GitHub. – URL: https://github.com/espressif/esp-idf "
              "(дата обращения: 27.09.2026).",
    "elrs": "ExpressLRS: open source radio link for RC applications // ExpressLRS. – URL: "
            "https://www.expresslrs.org (дата обращения: 27.09.2026).",
}
