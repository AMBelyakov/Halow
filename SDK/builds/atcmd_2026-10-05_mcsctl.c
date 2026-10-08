
int32 sys_atcmd_sysdbg(const char *cmd, char *argv[], uint32 argc)
{
    char *arg = argv[0];
    if (argc == 2) {
        if (os_strcasecmp(arg, "heap") == 0) {
            sys_status.dbg_heap = (os_atoi(argv[1]) == 1);
        }
        if (os_strcasecmp(arg, "top") == 0) {
            sys_status.dbg_top = os_atoi(argv[1]);
        }
        if (os_strcasecmp(arg, "lmac") == 0) {
            sys_status.dbg_lmac = os_atoi(argv[1]);
        }
        if (os_strcasecmp(arg, "umac") == 0) {
            sys_status.dbg_umac = (os_atoi(argv[1]) == 1);
        }
        if (os_strcasecmp(arg, "irq") == 0) {
            sys_status.dbg_irq = (os_atoi(argv[1]) == 1);
        }
        if (os_strcasecmp(arg, "net") == 0) {
            sys_status.dbg_net = (os_atoi(argv[1]) == 1);
        }
        atcmd_ok;
    } else {
        atcmd_error;
    }
    return 0;
}

#if SYS_APP_UART_P2P
/* Аварийный люк для отката прошивки.
 *
 * uart_p2p_init() забирает UART1 себе (uart_request_irq + disable_print),
 * после чего AT-команды на нём мертвы — включая AT+FWUPG. То есть без этого
 * люка перепрошить модуль обратно можно было бы только вынув флеш-чип из
 * панельки (docs/Firmware_burn_1.md / _2.md), потому что оба софтовых пути
 * отката (WNBOTA и NETAT) требуют уже поднявшегося линка.
 *
 * Поэтому uart_p2p стартует не сразу, а через UART_P2P_START_DELAY_MS
 * (см. sys_app_init в main.c). Если в это окно прислать AT+NOP2P, флаг
 * ниже отменяет запуск НАСОВСЕМ до следующей перезагрузки, и AT-режим
 * остаётся доступен без ограничения по времени — этого хватает на
 * AT+FWUPG и минутную передачу по XMODEM.
 *
 * Порядок восстановления: обесточить -> подать питание -> в первые
 * UART_P2P_START_DELAY_MS мс послать AT+NOP2P -> дождаться OK -> AT+FWUPG.
 */
static volatile uint8 uart_p2p_inhibit = 0;

static int32 sys_atcmd_nop2p(const char *cmd, char *argv[], uint32 argc)
{
    uart_p2p_inhibit = 1;
    atcmd_ok;
    return 0;
}

/*
 * AT+P2PDEST — кому uart_p2p шлёт видео.
 *
 *     AT+P2PDEST=?                     прочитать текущий адрес
 *     AT+P2PDEST=c6:e8:35:70:7a:68     слать одноадресно
 *     AT+P2PDEST=ff:ff:ff:ff:ff:ff     вернуть широковещание
 *
 * ЗАЧЕМ. Транспорт шлёт кадры на широковещательный адрес. Такие кадры никто
 * не подтверждает: нет ни повторов, ни обратной связи, а без обратной связи
 * модуль не может подбирать модуляцию и обязан сидеть на MCS 0. Отсюда и
 * характер потерь — пакеты пропадают целиком при нулевой порче байтов, потому
 * что попытка у каждого ровно одна. Подставив MAC получателя, включаем
 * штатные подтверждения, повторы и автоподбор скорости.
 *
 * ПОЧЕМУ НЕЛЬЗЯ ПРОСТО ПЕРЕПИСАТЬ АДРЕС — ошибка 04.09, стоившая модуля.
 * uart_p2p_task берёт адрес назначения не из своей переменной, а из ОБЩЕЙ
 * константы broadcast_addr (в сборке 15.09 это 0x20059e50, core_utils.o).
 * По карте символов её читают ещё двое:
 *     ieee80211_scan_do_action   — поиск сети,
 *     ieee80211_ap_build_hdr     — сборка заголовков точки доступа.
 * Перепиши мы эти шесть байт — камера заговорила бы одноадресно и при этом
 * перестала бы находить точку доступа и подключаться к ней.
 *
 * ЧТО ДЕЛАЕМ ВМЕСТО ЭТОГО. Правим не константу, а УКАЗАТЕЛЬ на неё: слово в
 * литеральном пуле самой uart_p2p_task (инструкция lrw r8, <broadcast_addr>).
 * Это слово принадлежит только ей. Код исполняется из ОЗУ — makecode.ini,
 * CodeLoadToSramAddr=20001000, — поэтому литерал доступен на запись; а lrw
 * выполняется на каждой отправке, значит переключение действует сразу и без
 * перезагрузки.
 *
 * АДРЕС ЛИТЕРАЛА ИЩЕМ, А НЕ ХАРДКОДИМ: при любой пересборке он уедет. Опора —
 * uart_p2p_init: он объявлен в lib/net/utils.h, лежит в том же объектном файле
 * и сразу после uart_p2p_task, так что литерал всегда в нескольких сотнях байт
 * ПЕРЕД ним. Ищем в этом окне слово, указывающее на шесть байт 0xff, и требуем
 * ЕДИНСТВЕННОГО совпадения. Не нашлось или нашлось дважды — отказ и печать,
 * молча не деградируем. Два других читателя константы лежат на 130 КБ дальше
 * и в окно не попадают.
 *
 * ВОЗВРАТ К ШИРОКОВЕЩАНИЮ — не перезаливка, а AT+P2PDEST=ff:ff:ff:ff:ff:ff.
 * После первой правки литерал всегда смотрит на наш массив, а режим задаётся
 * его содержимым. Один образ на обе платы, A/B за один цикл питания.
 */
static uint8   p2p_dest_mac[6] = { 0xff, 0xff, 0xff, 0xff, 0xff, 0xff };
static uint32 *p2p_dest_lit    = NULL;

#define P2P_LIT_WINDOW 0x400        /* сколько байт перед uart_p2p_init смотреть */
#define P2P_RAM_LO     0x20000000
#define P2P_RAM_HI     0x20080000

static uint32 *p2p_find_dest_lit(void)
{
    uint32 end   = (uint32)uart_p2p_init;
    uint32 start = (end - P2P_LIT_WINDOW) & ~3u;
    uint32 *hit  = NULL;
    uint32 cnt   = 0;
    uint32 a;

    for (a = start; a < end; a += 4) {
        uint32 v = *(volatile uint32 *)a;
        const uint8 *p;

        if (v < P2P_RAM_LO || v > P2P_RAM_HI - 6) {
            continue;
        }
        p = (const uint8 *)v;
        if (p[0] == 0xff && p[1] == 0xff && p[2] == 0xff &&
            p[3] == 0xff && p[4] == 0xff && p[5] == 0xff) {
            hit = (uint32 *)a;
            cnt++;
        }
    }

    if (cnt != 1) {
        atcmd_printf("+P2PDEST:literal not found, %u matches in [%08x,%08x)\r\n",
                     (unsigned)cnt, (unsigned)start, (unsigned)end);
        return NULL;
    }
    atcmd_printf("+P2PDEST:literal at %08x -> %08x\r\n",
                 (unsigned)(uint32)hit, (unsigned)*hit);
    return hit;
}

/* Разбор "xx:xx:xx:xx:xx:xx". str2mac из osal ничего не проверяет, поэтому
 * форму проверяем сами: иначе опечатка молча превратится в 00:00:00:00:00:00
 * и уедет в эфир как адрес назначения. */
static int32 p2p_parse_mac(const char *s, uint8 *mac)
{
    uint32 i;
    uint32 v[6];

    for (i = 0; i < 17; i++) {
        if (s[i] == 0) {
            return 0;
        }
    }
    if (s[17] != 0) {
        return 0;
    }
    for (i = 0; i < 5; i++) {
        if (s[2 + i * 3] != ':') {
            return 0;
        }
    }
    for (i = 0; i < 6; i++) {
        const char *p = s + i * 3;
        uint32 j;
        v[i] = 0;
        for (j = 0; j < 2; j++) {
            char c = p[j];
            uint32 d;
            if (c >= '0' && c <= '9') {
                d = (uint32)(c - '0');
            } else if (c >= 'a' && c <= 'f') {
                d = (uint32)(c - 'a') + 10;
            } else if (c >= 'A' && c <= 'F') {
                d = (uint32)(c - 'A') + 10;
            } else {
                return 0;
            }
            v[i] = (v[i] << 4) | d;
        }
    }
    for (i = 0; i < 6; i++) {
        mac[i] = (uint8)v[i];
    }
    return 1;
}

/* AT+P2PLOG — вернуть печать статистики модуля ПОСЛЕ старта прозрачного режима.
 *
 * ЗАЧЕМ. Прошивка умеет печатать по каждой станции строку вида
 *
 *     tx0: mcs=*1 snr=74 data=0KB(0kbps) per=0
 *          bw=2MHz cnt=2 agg=1 ... ack=0KB(2) drop=0KB(0)
 *     rx0: mcs=5 evm(avg:std)=-31:0 rssi=-5 ... fcsErr=0
 *
 * Здесь есть всё, чего не хватало для ответа на главный вопрос: `ack` — счётчик
 * подтверждений, `per` — доля неудачных передач, `mcs=*` — скорость, ВЫБРАННАЯ
 * автоподбором (звёздочка означает «авто»). Узнать, что одноадресный пакет не
 * дошёл, можно только по отсутствию подтверждения, поэтому эти числа прямо
 * говорят, работают ли ACK.
 *
 * ПОЧЕМУ ОНИ НЕ ВИДНЫ. Последним делом uart_p2p_init() вызывает
 * disable_print(1) — тот самый вызов, что упомянут в комментарии к аварийному
 * люку выше. Печать замолкает ровно на 30-й секунде, когда транспорт забирает
 * UART, то есть за мгновение до того, как пойдёт видео. Всё интересное
 * происходит уже в тишине.
 *
 * ЧТО ДЕЛАЕТ КОМАНДА. Заводит периодический таймер, который возвращает
 * disable_print(0). uart_p2p_init глушит печать ОДИН раз при старте, а наш
 * таймер тикает постоянно — значит через период после старта транспорта печать
 * оживает и дальше держится.
 *
 *     AT+P2PLOG=?      состояние
 *     AT+P2PLOG=2000   оживлять печать каждые 2000 мс
 *     AT+P2PLOG=0      выключить
 *
 * КУДА ИДЁТ ТЕКСТ И ЧЕМУ ЭТО ВРЕДИТ. В UART, то есть В СТОРОНУ ESP32 — навстречу
 * видео. Исходящие кадры не затрагиваются совсем. Но этим же путём приходят
 * принятые из эфира пакеты, и текст вклинивается между ними: приёмная сторона
 * увидит мусор, часть пакетов побьётся. На плате КАМЕРЫ это безобидно (теряются
 * лишь отчёты приёмника, у них своё кадрирование с CRC), а вот на плате
 * ПРИЁМНИКА этим путём идёт само видео — там команду включать НЕЛЬЗЯ.
 *
 * ПО УМОЛЧАНИЮ ВЫКЛЮЧЕНА. Обычный прогон ведёт себя как раньше; это
 * диагностический режим, а не рабочий.
 */
static struct os_timer p2plog_timer;
static uint8  p2plog_on     = 0;
static uint16 p2plog_period = 0;

static void p2plog_tick(void *arg)
{
    (void)arg;
    disable_print(0);
}

/*
 * 24.09.2026. Счётчики приёма UART модуля (определены в sdk/driver/uart/
 * hguart.c) и переключатель режима выгребания FIFO.
 *
 * Печать идёт отдельной задачей, а не из p2plog_tick: колбэк таймера может
 * исполняться в контексте, где printf нельзя. Задача заводится при первом
 * AT+P2PLOG и печатает с тем же периодом. Строка содержит «STA» (UARTSTAT),
 * чтобы её пропустил строгий фильтр lmacTextByte в скетче камеры.
 *
 *   isr  — входов в обработчик приёма
 *   rx   — байт отдано uart_p2p
 *   oe   — сколько раз регистр LSR показал ПЕРЕПОЛНЕНИЕ FIFO (потеря байтов)
 *   cto  — прерываний «таймаут символа»
 *   lost — байт, выброшенных вендорской веткой CHAR_TIMEOUT
 *
 * rx/isr показывает, сколько байт забирается за вход: в режиме вендора это
 * ровно 1, при выгребании — больше. oe>0 — прямое доказательство потерь.
 */
#include "osal/task.h"
extern volatile uint32 g_uart_isr;
extern volatile uint32 g_uart_rx;
extern volatile uint32 g_uart_oe;
extern volatile uint32 g_uart_cto;
extern volatile uint32 g_uart_cto_lost;
extern volatile uint8  g_uart_drain;

static struct os_task uartstat_task;
static uint8 uartstat_started = 0;

static void uartstat_fn(void *arg)
{
    (void)arg;
    for (;;) {
        os_sleep_ms(p2plog_period ? p2plog_period : 5000);
        if (!p2plog_on) {
            continue;
        }
        disable_print(0);
        hgprintf("UARTSTAT drain=%d isr=%u rx=%u oe=%u cto=%u lost=%u\r\n",
                 (int)g_uart_drain, (unsigned)g_uart_isr, (unsigned)g_uart_rx,
                 (unsigned)g_uart_oe, (unsigned)g_uart_cto,
                 (unsigned)g_uart_cto_lost);
    }
}

/* AT+UARTDRAIN=0|1|? — режим приёма в hguart.c, см. комментарий там. */
static int32 sys_atcmd_uartdrain(const char *cmd, char *argv[], uint32 argc)
{
    if (argc != 1) {
        atcmd_error;
        return 0;
    }
    if (argv[0][0] != '?') {
        g_uart_drain = os_atoi(argv[0]) ? 1 : 0;
    }
    atcmd_printf("+UARTDRAIN:%d\r\n", (int)g_uart_drain);
    atcmd_ok;
    return 0;
}

static int32 sys_atcmd_p2plog(const char *cmd, char *argv[], uint32 argc)
{
    int v;

    if (argc != 1) {
        atcmd_error;
        return 0;
    }
    if (argv[0][0] == '?') {
        atcmd_printf("+P2PLOG:%s period=%u ms\r\n",
                     p2plog_on ? "on" : "off", (unsigned)p2plog_period);
        atcmd_ok;
        return 0;
    }

    v = os_atoi(argv[0]);
    if (v <= 0) {
        if (p2plog_on) {
            os_timer_stop(&p2plog_timer);
            p2plog_on = 0;
        }
        atcmd_printf("+P2PLOG:off\r\n");
        atcmd_ok;
        return 0;
    }

    /* Нижняя граница бережёт канал: печать идёт по тому же UART, по которому
     * приходят пакеты из эфира, и слишком частая вытеснит их совсем. */
    if (v < 500)   v = 500;
    if (v > 60000) v = 60000;

    if (!p2plog_on) {
        os_timer_init(&p2plog_timer, p2plog_tick, OS_TIMER_MODE_PERIODIC, NULL);
        p2plog_on = 1;
        if (!uartstat_started) {
            uartstat_started = 1;
            OS_TASK_INIT("uartstat", &uartstat_task, uartstat_fn, 0,
                         OS_TASK_PRIORITY_LOW, 1024);
        }
    } else {
        os_timer_stop(&p2plog_timer);
    }
    p2plog_period = (uint16)v;
    os_timer_start(&p2plog_timer, (unsigned long)v);

    atcmd_printf("+P2PLOG:on period=%d ms\r\n", v);
    atcmd_ok;
    return 0;
}

static int32 sys_atcmd_p2pdest(const char *cmd, char *argv[], uint32 argc)
{
    uint8 mac[6];
    uint32 i;
    uint32 zero = 1;

    if (argc != 1) {
        atcmd_error;
        return 0;
    }

    if (argv[0][0] == '?') {
        atcmd_printf("+P2PDEST:%02x:%02x:%02x:%02x:%02x:%02x patched=%d\r\n",
                     p2p_dest_mac[0], p2p_dest_mac[1], p2p_dest_mac[2],
                     p2p_dest_mac[3], p2p_dest_mac[4], p2p_dest_mac[5],
                     p2p_dest_lit ? 1 : 0);
        atcmd_ok;
        return 0;
    }

    if (!p2p_parse_mac(argv[0], mac)) {
        atcmd_printf("+P2PDEST:bad mac, need xx:xx:xx:xx:xx:xx\r\n");
        atcmd_error;
        return 0;
    }
    for (i = 0; i < 6; i++) {
        if (mac[i]) {
            zero = 0;
        }
    }
    if (zero) {
        atcmd_printf("+P2PDEST:refusing all-zero mac\r\n");
        atcmd_error;
        return 0;
    }

    /* Сначала заполняем массив, и только потом переводим на него указатель:
     * иначе uart_p2p_task успела бы прочитать полупустой адрес. */
    os_memcpy(p2p_dest_mac, mac, 6);

    if (p2p_dest_lit == NULL) {
        p2p_dest_lit = p2p_find_dest_lit();
        if (p2p_dest_lit == NULL) {
            atcmd_error;
            return 0;
        }
        *p2p_dest_lit = (uint32)p2p_dest_mac;
    }

    atcmd_printf("+P2PDEST:%02x:%02x:%02x:%02x:%02x:%02x\r\n",
                 p2p_dest_mac[0], p2p_dest_mac[1], p2p_dest_mac[2],
                 p2p_dest_mac[3], p2p_dest_mac[4], p2p_dest_mac[5]);
    atcmd_ok;
    return 0;
}

/*
 * AT+PWRCTL — регулировка мощности передатчика по уровню (28.09.2026).
 *
 * ЗАЧЕМ. На столе при 20 дБм приёмник в перегрузке: SNR 66 дБ, PER 75–82 %,
 * эфир 200–450 кбит/с вместо 700–970, очередь модуля копит секунды видео, а
 * наводка передатчика портит захват камеры. Штатная AT+TX_PWR_AUTO уровень не
 * снижает (26.09: SNR 54 против 55 дБ, 28.09: 66 против 66) — она режет
 * мощность только на старших MCS ради линейности.
 *
 * ПО ЧЕМУ РЕГУЛИРУЕМ. По tx_snr из списка станций — SNR, с которым СОСЕД
 * слышит НАС (обратная связь MFB). Доказано опытом 26.09: смена мощности
 * камеры 1 -> 20 дБм подняла её «tx0 snr» 39 -> 55 при неизменном приёмнике.
 * Это принципиально: если бы каждая сторона крутила мощность по тому, как
 * слышит соседа сама (rssi/rx_snr), связка была бы неустойчива — разность
 * мощностей растёт, одна сторона уходит в минимум, другая в максимум. По
 * обратной связи каждая управляет только своим сигналом, контуры развязаны.
 *
 * АЛГОРИТМ. Раз в PWRCTL_PERIOD_MS читаем tx_snr, сглаживаем (1/4 нового).
 * Раз в PWRCTL_DECIDE_MS: выше коридора — минус шаг, ниже — плюс шаг, внутри
 * — ничего. Пределы 1..PWRCTL_CAP_DBM (14) дБм. Защиты:
 *   - tx_snr не менялся PWRCTL_STALE_MS — обратная связь устарела, держим;
 *   - станции нет PWRCTL_LOST_MS — связь потеряна, возвращаем потолок.
 *
 *     AT+PWRCTL=?            состояние
 *     AT+PWRCTL=0            только измерять и печатать (с AT+P2PLOG)
 *     AT+PWRCTL=1            регулировать, коридор по умолчанию
 *     AT+PWRCTL=1,25,35      регулировать, коридор SNR 25..35 дБ
 *     AT+PWRCTL=1,25,35,14   то же с потолком мощности 14 дБм
 *
 * ПОТОЛОК (28.09). По умолчанию 14 дБм = 25 мВт — предел ГКРЧ 07-20-03-001 для
 * 866–868 МГц. Регулятор не поднимает мощность выше потолка ни шагом, ни при
 * потере связи, а стартовую (от AT+TXPOWER) срезает до потолка на первом же
 * решении. Аппаратный предел модуля 20 дБм, выше потолок не задаётся.
 *
 * ПО УМОЛЧАНИЮ НЕ ЗАПУЩЕНА: пока команды не было, задачи нет и модуль ведёт
 * себя как прежняя сборка. Печать — только при включённом AT+P2PLOG (на
 * приёмнике он выключен: там этим UART идёт видео). Строка содержит «snr=»,
 * чтобы её пропустил фильтр lmacTextByte в скетче камеры.
 */
#define PWRCTL_PERIOD_MS 250
#define PWRCTL_DECIDE_MS 1000
#define PWRCTL_STALE_MS  5000
#define PWRCTL_LOST_MS   3000
#define PWRCTL_STEP_DB   2
#define PWRCTL_MIN_DBM   1
#define PWRCTL_HW_MAX_DBM 20   /* предел AT+TXPOWER */
#define PWRCTL_CAP_DBM   14     /* 25 мВт — предел ГКРЧ для 866–868 МГц */

extern void *lmacops;

static struct os_task pwrctl_task;
static uint8  pwrctl_started = 0;
static uint8  pwrctl_mode = 0;          /* 0 — мерить, 1 — регулировать */
static int8   pwrctl_lo = 25;
static int8   pwrctl_hi = 35;
static int8   pwrctl_max = PWRCTL_CAP_DBM;   /* потолок мощности, дБм */
static int8   pwrctl_pwr = 0;           /* заданная мощность; 0 — ещё не читали */
static int16  pwrctl_ema10 = -32000;    /* tx_snr x10, сглаженный */
static uint32 pwrctl_chg = 0;           /* сколько раз меняли мощность */
static uint32 pwrctl_up = 0, pwrctl_down = 0, pwrctl_stale = 0, pwrctl_lost = 0;

static void pwrctl_set(int8 p)
{
    if (p < PWRCTL_MIN_DBM) p = PWRCTL_MIN_DBM;
    if (p > pwrctl_max) p = pwrctl_max;
    if (p != pwrctl_pwr) {
        lmac_set_txpower(lmacops, p);
        pwrctl_pwr = p;
        pwrctl_chg++;
    }
}

/*
 * AT+MCSCTL — подстройка модуляции ШИРОКОВЕЩАТЕЛЬНЫХ кадров по уровню (05.10.2026).
 *
 * ЗАЧЕМ. 05.10 модуль камеры стал точкой доступа и шлёт видео всем: без
 * подтверждений и повторов куски доходили в 99,4–99,7 % (журнал, раздел 05.10).
 * Но своей подстройки модуляции у широковещательных кадров нет: AT+MCAST_MCS
 * задаёт одну на всё включение, а сменить её после стартового окна ESP32 не
 * может — AT в прозрачном режиме не работает. В полёте модуляция должна идти за
 * дальностью: рядом MCS 6, дальше 4, 2, 1, 0.
 *
 * ПО ЧЕМУ. По тому же сглаженному tx_snr, что и PWRCTL, — SNR, с которым сосед
 * слышит НАС. У точки доступа он есть и при широковещании: 05.10 у ноутбука 48 дБ,
 * в 5 м 28–34, провалы до 18 (печать PWRCTL в логе камеры).
 *
 * КАК. Раз в секунду, вместе с решением PWRCTL: сглаженный SNR ниже порога
 * текущей ступени — сразу ступень вниз; выше порога следующей на MCSCTL_UP_DB
 * MCSCTL_UP_N решений подряд — ступень вверх. Связь пропала — нижняя ступень:
 * маяки, судя по 18.08, идут той же модуляцией, по ним станция вернётся.
 * Обратная связь застыла — держим. Пишем в ah_lmac+0x88c — туда же, куда
 * atcmd_mcast_mcs_hdl; читает этот байт lmac_update_tx_rate на каждом
 * широковещательном кадре (дизассемблер сборки 29.09, 0x2002df8a). Смещение
 * верно для этой версии mars_lmac.o — при смене SDK проверить заново.
 *
 * С PWRCTL контуры не спорят: регулятор мощности держит SNR в коридоре (25..35),
 * а модуляция садится, только когда мощность упёрлась в потолок и SNR всё равно
 * ушёл ниже порога. На дальности сначала растёт мощность, потом падает MCS.
 *
 * ПОРОГИ (SNR, дБ) — первые, по таблицам 802.11 для той же модуляции с запасом и
 * по замеру 05.10 (5 м, 28–34 дБ: MCS 4 теряла 0,3–0,6 % кусков, MCS 6 — 1,5 %).
 * Проверить в поле; все разом сдвигаются вторым параметром.
 *
 *     AT+MCSCTL=?            состояние
 *     AT+MCSCTL=0            не трогать модуляцию (только печать)
 *     AT+MCSCTL=1            подстраивать, ступени 0..6
 *     AT+MCSCTL=1,3          то же, все пороги на 3 дБ выше (осторожнее)
 *     AT+MCSCTL=1,0,1,6      ступени не ниже 1 и не выше 6
 *
 * ПО УМОЛЧАНИЮ НЕ ЗАПУЩЕНА, модуль ведёт себя как сборка 29.09. Состояние — в
 * строке PWRCTL (поля mcs=, mcsctl=). На клиенте смысла нет: его групповые кадры
 * идут точке адресно, своей подстройкой (опыт 30.09).
 */
#define MCSCTL_UP_DB 3
#define MCSCTL_UP_N  3
extern uint8 ah_lmac[];                   /* struct ah_lmac из mars_lmac.o, 3048 байт */
#define MCSCTL_MCS   (ah_lmac[0x88c])

static const int8 mcsctl_thr[8] = { -100, 8, 12, 16, 20, 30, 34, 38 };
static uint8  mcsctl_mode = 0;           /* 0 — не трогать, 1 — подстраивать */
static int8   mcsctl_shift = 0;          /* сдвиг всех порогов, дБ */
static uint8  mcsctl_min = 0, mcsctl_max = 6;
static uint8  mcsctl_upn = 0;            /* решений подряд «можно выше» */
static uint32 mcsctl_up = 0, mcsctl_down = 0, mcsctl_lost = 0;

static void mcsctl_set(int m)
{
    if (m < mcsctl_min) m = mcsctl_min;
    if (m > mcsctl_max) m = mcsctl_max;
    if (m != MCSCTL_MCS) {
        if (m > MCSCTL_MCS) mcsctl_up++;
        else                mcsctl_down++;
        MCSCTL_MCS = (uint8)m;
    }
}

/* Раз в секунду из pwrctl_fn. n — станций в списке, lost/stale — как у PWRCTL. */
static void mcsctl_decide(int n, int lost, int stale, int snr)
{
    int cur = MCSCTL_MCS;

    if (!mcsctl_mode) {
        return;
    }
    if (cur > 7) {
        cur = 0;                          /* как lmac_update_tx_rate: >7 — не задано */
    }
    if (n <= 0) {
        if (lost && cur != mcsctl_min) {
            mcsctl_lost++;
            mcsctl_set(mcsctl_min);       /* связь пропала — самая живучая */
        }
        mcsctl_upn = 0;
        return;
    }
    if (stale) {
        mcsctl_upn = 0;                   /* обратная связь застыла — держим */
        return;
    }
    if (cur > mcsctl_min && snr < mcsctl_thr[cur] + mcsctl_shift) {
        mcsctl_upn = 0;
        mcsctl_set(cur - 1);
    } else if (cur < mcsctl_max && snr >= mcsctl_thr[cur + 1] + mcsctl_shift + MCSCTL_UP_DB) {
        if (++mcsctl_upn >= MCSCTL_UP_N) {
            mcsctl_upn = 0;
            mcsctl_set(cur + 1);
        }
    } else {
        mcsctl_upn = 0;
    }
}

static void pwrctl_fn(void *arg)
{
    struct hgic_sta_info st[4];
    uint32 t = 0, t_decide = 0, t_print = 0, t_mcs = 0;
    uint32 t_seen = 0, t_snr_moved = 0;
    int8   snr_prev = -128;
    int32  n;

    (void)arg;
    for (;;) {
        os_sleep_ms(PWRCTL_PERIOD_MS);
        t += PWRCTL_PERIOD_MS;

        if (pwrctl_pwr == 0) {
            int32 p = lmac_get_txpower(lmacops);   /* стартовая — от AT+TXPOWER */
            pwrctl_pwr = (p >= PWRCTL_MIN_DBM && p <= PWRCTL_HW_MAX_DBM) ? (int8)p : PWRCTL_HW_MAX_DBM;
        }

        os_memset(st, 0, sizeof(st));
        n = ieee80211_get_stalist(sys_cfgs.wifi_mode, st, 4);
        if (n > 0) {
            t_seen = t;
            if (st[0].tx_snr != snr_prev) {
                snr_prev = st[0].tx_snr;
                t_snr_moved = t;
            }
            if (pwrctl_ema10 == -32000) {
                pwrctl_ema10 = (int16)(st[0].tx_snr * 10);
            } else {
                pwrctl_ema10 += (int16)((st[0].tx_snr * 10 - pwrctl_ema10) / 4);
            }
        }

        if (t - t_mcs >= PWRCTL_DECIDE_MS) {
            /* 05.10: модуляция — своим контуром, решение раз в секунду, см. MCSCTL.
             * Свой отсчёт: t_decide двигается, только когда регулирует PWRCTL. */
            t_mcs = t;
            mcsctl_decide((int)n, t - t_seen >= PWRCTL_LOST_MS,
                          n > 0 && t - t_snr_moved >= PWRCTL_STALE_MS, pwrctl_ema10 / 10);
        }
        if (pwrctl_mode && t - t_decide >= PWRCTL_DECIDE_MS) {
            t_decide = t;
            if (pwrctl_pwr > pwrctl_max) {
                pwrctl_set(pwrctl_max);           /* стартовая выше потолка — срезать */
            } else if (n <= 0 && t - t_seen >= PWRCTL_LOST_MS) {
                if (pwrctl_pwr != pwrctl_max) {
                    pwrctl_lost++;
                }
                pwrctl_set(pwrctl_max);           /* связь пропала — на потолок */
            } else if (n > 0 && t - t_snr_moved >= PWRCTL_STALE_MS) {
                pwrctl_stale++;                   /* обратная связь застыла — держим */
            } else if (n > 0) {
                int snr = pwrctl_ema10 / 10;
                if (snr > pwrctl_hi && pwrctl_pwr > PWRCTL_MIN_DBM) {
                    pwrctl_down++;
                    pwrctl_set((int8)(pwrctl_pwr - PWRCTL_STEP_DB));
                } else if (snr < pwrctl_lo && pwrctl_pwr < pwrctl_max) {
                    pwrctl_up++;
                    pwrctl_set((int8)(pwrctl_pwr + PWRCTL_STEP_DB));
                }
            }
        }

        if (p2plog_on && t - t_print >= (p2plog_period ? p2plog_period : 5000)) {
            t_print = t;
            disable_print(0);
            hgprintf("PWRCTL snr=%d ema=%d rx_snr=%d rssi=%d evm=%d n=%d pwr=%d "
                     "mode=%d lo=%d hi=%d max=%d chg=%u up=%u down=%u stale=%u lost=%u "
                     "mcs=%d mcsctl=%d mup=%u mdown=%u mlost=%u\r\n",
                     (int)st[0].tx_snr, (int)(pwrctl_ema10 / 10), (int)st[0].rx_snr,
                     (int)st[0].rssi, (int)st[0].evm, (int)n, (int)pwrctl_pwr,
                     (int)pwrctl_mode, (int)pwrctl_lo, (int)pwrctl_hi, (int)pwrctl_max,
                     (unsigned)pwrctl_chg, (unsigned)pwrctl_up, (unsigned)pwrctl_down,
                     (unsigned)pwrctl_stale, (unsigned)pwrctl_lost,
                     (int)MCSCTL_MCS, (int)mcsctl_mode, (unsigned)mcsctl_up,
                     (unsigned)mcsctl_down, (unsigned)mcsctl_lost);
        }
    }
}

static int32 sys_atcmd_pwrctl(const char *cmd, char *argv[], uint32 argc)
{
    int lo, hi;

    if (argc < 1) {
        atcmd_error;
        return 0;
    }
    if (argv[0][0] != '?') {
        if (argc >= 3) {
            lo = os_atoi(argv[1]);
            hi = os_atoi(argv[2]);
            if (lo < 0 || hi > 80 || lo >= hi) {
                atcmd_printf("+PWRCTL:bad range, need 0 <= lo < hi <= 80\r\n");
                atcmd_error;
                return 0;
            }
            pwrctl_lo = (int8)lo;
            pwrctl_hi = (int8)hi;
        }
        if (argc >= 4) {
            int mx = os_atoi(argv[3]);
            if (mx < PWRCTL_MIN_DBM || mx > PWRCTL_HW_MAX_DBM) {
                atcmd_printf("+PWRCTL:bad max, need %d..%d dBm\r\n",
                             PWRCTL_MIN_DBM, PWRCTL_HW_MAX_DBM);
                atcmd_error;
                return 0;
            }
            pwrctl_max = (int8)mx;
        }
        pwrctl_mode = os_atoi(argv[0]) ? 1 : 0;
        if (!pwrctl_started) {
            pwrctl_started = 1;
            OS_TASK_INIT("pwrctl", &pwrctl_task, pwrctl_fn, 0,
                         OS_TASK_PRIORITY_LOW, 1024);
        }
    }
    atcmd_printf("+PWRCTL:mode=%d lo=%d hi=%d max=%d pwr=%d task=%d\r\n",
                 (int)pwrctl_mode, (int)pwrctl_lo, (int)pwrctl_hi, (int)pwrctl_max,
                 (int)pwrctl_pwr, (int)pwrctl_started);
    atcmd_ok;
    return 0;
}

static int32 sys_atcmd_mcsctl(const char *cmd, char *argv[], uint32 argc)
{
    if (argc < 1) {
        atcmd_error;
        return 0;
    }
    if (argv[0][0] != '?') {
        if (argc >= 2) {
            int sh = os_atoi(argv[1]);
            if (sh < -20 || sh > 20) {
                atcmd_printf("+MCSCTL:bad shift, need -20..20 dB\r\n");
                atcmd_error;
                return 0;
            }
            mcsctl_shift = (int8)sh;
        }
        if (argc >= 4) {
            int mn = os_atoi(argv[2]), mx = os_atoi(argv[3]);
            if (mn < 0 || mx > 7 || mn > mx) {
                atcmd_printf("+MCSCTL:bad range, need 0 <= min <= max <= 7\r\n");
                atcmd_error;
                return 0;
            }
            mcsctl_min = (uint8)mn;
            mcsctl_max = (uint8)mx;
        }
        mcsctl_mode = os_atoi(argv[0]) ? 1 : 0;
        mcsctl_upn = 0;
        if (!pwrctl_started) {
            /* Задача общая с PWRCTL; без AT+PWRCTL она мерит, но мощность не трогает. */
            pwrctl_started = 1;
            OS_TASK_INIT("pwrctl", &pwrctl_task, pwrctl_fn, 0,
                         OS_TASK_PRIORITY_LOW, 1024);
        }
    }
    atcmd_printf("+MCSCTL:mode=%d shift=%d min=%d max=%d mcs=%d up=%u down=%u lost=%u task=%d\r\n",
                 (int)mcsctl_mode, (int)mcsctl_shift, (int)mcsctl_min, (int)mcsctl_max,
                 (int)MCSCTL_MCS, (unsigned)mcsctl_up, (unsigned)mcsctl_down,
                 (unsigned)mcsctl_lost, (int)pwrctl_started);
    atcmd_ok;
    return 0;
}
#endif

static const struct hgic_atcmd static_atcmds[] = {
    { "AT+RST", sys_atcmd_reset },
    { "AT+SYSDBG", sys_atcmd_sysdbg },
    { "AT+LOADDEF", sys_atcmd_loaddef },
#if SYS_APP_UART_P2P
    { "AT+NOP2P", sys_atcmd_nop2p },
    { "AT+P2PDEST", sys_atcmd_p2pdest },
    { "AT+P2PLOG",  sys_atcmd_p2plog },
    { "AT+UARTDRAIN", sys_atcmd_uartdrain },
    { "AT+PWRCTL", sys_atcmd_pwrctl },
    { "AT+MCSCTL", sys_atcmd_mcsctl },
#endif

    /*TESTMODE ATCMD*/
    { "AT+ACS_START", atcmd_acs_start_hdl },
    { "AT+ACK_TO", atcmd_ack_to_extra_hdl },
    { "AT+ADC_DUMP", atcmd_adc_dump_hdl },
    { "AT+AP_SLEEP_MODE", atcmd_ap_sleep_mode },
    { "AT+ANT_DUAL", atcmd_ant_dual_hdl },
    { "AT+ANT_CTRL", atcmd_ant_ctrl_hdl },
    { "AT+ANT_AUTO", atcmd_ant_auto_hdl },
    { "AT+ANT_DEF", atcmd_ant_def_hdl },
    { "AT+BGRSSI_MARGIN", atcmd_bgrssi_margin_hdl },
    { "AT+BGRSSI_SPUR", atcmd_bgrssi_spur_hdl },
    //{ "AT+BSS_BW", atcmd_bss_bw_hdl },
    { "AT+BUS_WT", atcmd_bus_wt_hdl },
    { "AT+CCA_OBSV", atcmd_cca_obsv_hdl },
    { "AT+CCA_CE", atcmd_cca_ce_hdl },
    { "AT+CCMP_SUPPORT", atcmd_ccmp_support_hdl },
    { "AT+CHAN_SCAN", atcmd_chan_scan_hdl },
    { "AT+CS_CNT", atcmd_cs_cnt_hdl },
    { "AT+CS_EN", atcmd_cs_enable_hdl },
    { "AT+CS_NUM", atcmd_cs_num_hdl },
    { "AT+CS_PERIOD", atcmd_cs_period_hdl },
    { "AT+CS_TH", atcmd_cs_th_hdl },
    { "AT+CTS_DUP", atcmd_cts_dup_hdl },
    { "AT+EDCA_AIFS", atcmd_edca_aifs_hdl },
    { "AT+EDCA_CW", atcmd_edca_cw_hdl },
    { "AT+EDCA_TXOP", atcmd_edca_txop_hdl },
    { "AT+AP_BACKOFF", atcmd_edca_ap_backoff_hdl },
    { "AT+EVM_MARGIN", atcmd_evm_margin_hdl },
    { "AT+FREQ_LIST", atcmd_freq_list_hdl },
#if !defined (TX4001A)
    { "AT+FT_ATT", atcmd_ft_att_hdl },
#endif
    { "AT+LMAC_DBGSEL", atcmd_lmac_dbgsel_hdl },
    { "AT+LO_FREQ", atcmd_lo_freq_hdl },
    //{ "AT+LOADDEF", atcmd_loaddef_hdl },
    { "AT+MAC_ADDR", atcmd_mac_addr_hdl },
    { "AT+MCAST_DUP", atcmd_mcast_dup_hdl },
    { "AT+MCAST_REORDER", atcmd_mcast_reorder_hdl },
    { "AT+MCAST_BW", atcmd_mcast_bw_hdl },
    { "AT+MCAST_MCS", atcmd_mcast_mcs_hdl },
    { "AT+MCAST_RTS", atcmd_mcast_rts_hdl },
    { "AT+NOR_RD", atcmd_nor_rd_hdl },
    { "AT+OBSS_CCA_DIFF", atcmd_obss_cca_diff_hdl },
    { "AT+OBSS_EDCA", atcmd_obss_edca_hdl },
    { "AT+OBSS_NAV_DIFF", atcmd_obss_nav_diff_hdl },
    { "AT+OBSS_SWITCH", atcmd_obss_switch_hdl },
    { "AT+OBSS_TH", atcmd_obss_th_hdl },
    { "AT+PCF_EN", atcmd_pcf_en_hdl },
    { "AT+PCF_PERCENT", atcmd_pcf_percent_hdl },
    { "AT+PCF_PERIOD", atcmd_pcf_period_hdl },
    { "AT+PHY_RESET", atcmd_phy_reset_hdl },
    { "AT+PRI_CHAN", atcmd_set_pri_chan_hdl },
    { "AT+PRINT_PERIOD", atcmd_lmac_print_period_hdl },
    { "AT+QA_ATT", atcmd_qa_att_hdl },
    { "AT+QA_CFG", atcmd_qa_cfg_hdl },
    { "AT+QA_RESULTS", atcmd_qa_results_hdl },
    { "AT+QA_RXTHD", atcmd_qa_rxthd_hdl },
    { "AT+QA_START", atcmd_qa_start_hdl },
    { "AT+QA_TXTHD", atcmd_qa_txthd_hdl },
    { "AT+RC_NEW", atcmd_rc_new_hdl },
    { "AT+REG_RD", atcmd_reg_rd_hdl },
    { "AT+REG_WT", atcmd_reg_wt_hdl },
    //{ "AT+REBOOT", atcmd_reboot_hdl },
    { "AT+RF_RESET", atcmd_rf_reset_hdl },
    { "AT+RTS_DUP", atcmd_rts_dup_hdl },
    { "AT+RX_AGC", atcmd_rx_agc_rd_hdl },
    { "AT+RX_ERR", atcmd_rx_err_rd_hdl },
    { "AT+RX_EVM", atcmd_rx_evm_rd_hdl },
    { "AT+RX_PKTS", atcmd_rx_pkts_rd_hdl },
    { "AT+RX_REORDER", atcmd_rx_ordered_hdl },
    { "AT+RX_RSSI", atcmd_rx_rssi_rd_hdl },
    //{ "AT+RX_ADDR_FILTER", atcmd_rx_addr_filter_hdl },
    //{ "AT+RX_PHY_CHECK", atcmd_rx_phy_check_hdl },
    { "AT+SET_AGC", atcmd_set_agc_hdl },
    { "AT+SET_AGC_TH", atcmd_set_agc_threshold_hdl },
    { "AT+SET_BGRSSI", atcmd_set_bgrssi_hdl },
    { "AT+SET_BGRSSI_AVG", atcmd_set_bgrssi_avg_hdl },
    { "AT+SET_RTS", atcmd_set_rts_hdl },
    { "AT+SHORT_GI", atcmd_short_gi_hdl },
    { "AT+SHORT_TH", atcmd_short_th_hdl },
    { "AT+SLEEP_EN", atcmd_sleep_en_hdl },
    { "AT+T_SENSOR", atcmd_t_sensor_hdl },
    { "AT+TEST_START", atcmd_test_start_hdl },
    { "AT+TX_AGG_AUTO", atcmd_agg_auto_hdl },
    { "AT+TX_ATTN", atcmd_tx_attn_hdl },
    { "AT+TX_CW", atcmd_tx_cw_hdl },
    { "AT+TX_BW", atcmd_tx_bw_hdl },
    { "AT+TX_BW_DYNAMIC", atcmd_tx_bw_dynamic_hdl },
    { "AT+TX_CNT_MAX", atcmd_tx_cnt_max_hdl },
    { "AT+TX_CONT", atcmd_tx_cont_hdl },
    { "AT+TX_DELAY", atcmd_tx_delay_hdl },
    { "AT+TX_DST_ADDR", atcmd_tx_dst_addr_hdl },
    { "AT+TX_FAIL", atcmd_tx_fail_rd_hdl },
    { "AT+TX_FC", atcmd_tx_fc_hdl },
    { "AT+TX_FLAGS", atcmd_tx_flags_hdl },
    { "AT+TX_LEN", atcmd_tx_len_hdl },
    { "AT+TX_MAX_AGG", atcmd_tx_max_agg_hdl },
    { "AT+TX_MAX_SYMS", atcmd_tx_max_syms_hdl },
    { "AT+TX_MCS", atcmd_tx_mcs_hdl },
    { "AT+TX_MCS_MAX", atcmd_tx_mcs_max_hdl },
    { "AT+TX_MCS_MIN", atcmd_tx_mcs_min_hdl },
    { "AT+TX_ORDERED", atcmd_strictly_ordered_hdl },
    { "AT+TX_PHA_AMP", atcmd_tx_pha_amp_hdl },
    { "AT+TX_PKTS", atcmd_tx_pkts_rd_hdl },
    { "AT+TX_PWR_AUTO", atcmd_tx_pwr_auto_hdl },
    { "AT+TX_PWR_MAX", atcmd_tx_pwr_max_hdl },
    { "AT+TX_PWR_SUPER", atcmd_tx_pwr_super_hdl },
    { "AT+TX_PWR_SUPER_TH", atcmd_tx_pwr_super_th_hdl },
    { "AT+TX_RATE_FIXED", atcmd_tx_rate_fixed_hdl },
    { "AT+TX_START", atcmd_tx_start_hdl },
    { "AT+TX_STEP", atcmd_tx_step_hdl },
    { "AT+TX_TRIG", atcmd_tx_trig_hdl },
    { "AT+TX_TYPE", atcmd_tx_type_hdl },
    { "AT+TXOP_EN", atcmd_txop_en_hdl },
    { "AT+TX_TRV_PILOT_EN", atcmd_tx_trv_pilot_en_hdl },
    { "AT+WAKE_EN", atcmd_wake_stas_hdl },
    { "AT+XO_CS", atcmd_xo_cs_hdl },
    { "AT+XO_CS_AUTO", atcmd_xo_cs_auto_hdl },
    { "AT+LO_TABLE", atcmd_lo_table_read_hdl },
    { "AT+PS_CHECK", atcmd_ps_check_hdl },
    { "AT+RADIO_ONOFF", atcmd_radio_onoff_hdl },
    { "AT+STA_INFO", atcmd_sta_info_hdl },
    { "AT+TXPOWER", atcmd_txpower_hdl },
    { "AT+SET_VDD13", atcmd_set_vdd13_hdl },
    { "AT+SMT_DAT", atcmd_smt_dat_hdl },

    { "AT+SYSCFG", sys_syscfg_dump_hdl },
    { "AT+FWUPG", xmodem_fwupgrade_hdl },
    { "AT+SSID", sys_wifi_atcmd_set_ssid },
    { "AT+KEY", sys_wifi_atcmd_set_key },
    { "AT+PSK", sys_wifi_atcmd_set_psk },
    { "AT+ENCRYPT", sys_wifi_atcmd_set_encrypt },
    { "AT+WIFIMODE", sys_wifi_atcmd_set_wifimode },
    { "AT+CHANNEL", sys_wifi_atcmd_set_channel },
    { "AT+APHIDE", sys_wifi_atcmd_aphide },
    { "AT+SCAN", sys_wifi_atcmd_scan },
    { "AT+PAIR", sys_wifi_atcmd_pair },    
    { "AT+ICMPMNTR", sys_atcmd_icmp_mntr},
    { "AT+RSSI", sys_wifi_atcmd_get_rssi},
    
    { "AT+ROAM", sys_wifi_atcmd_roam},
#if SYS_NETWORK_SUPPORT && LWIP_RAW
    { "AT+PING", sys_atcmd_ping},
#endif
#if SYS_NETWORK_SUPPORT
    { "AT+IPERF2", sys_atcmd_iperf2},
#endif
#if WIFI_REPEATER_SUPPORT
    { "AT+R_SSID", sys_wifi_atcmd_set_rssid },
    { "AT+R_KEY", sys_wifi_atcmd_set_rkey },
    { "AT+R_PSK", sys_wifi_atcmd_set_rpsk },
#endif
    // AH特有
    { "AT+BSS_BW", sys_wifi_atcmd_bss_bw },
    { "AT+CHAN_LIST", sys_wifi_atcmd_chan_list },
    { "AT+WAKEUP", sys_wifi_atcmd_wakeup },
    { "AT+VERSION", sys_wifi_atcmd_version },

#ifdef CONFIG_SLEEP
    { "AT+AP_PSMODE", sys_wifi_atcmd_ap_psmode },
    { "AT+DSLEEP", sys_wifi_atcmd_dsleep },
#endif

    { "AT+SET_WMM", sys_wifi_atcmd_set_wmm_param },

};

__init void sys_atcmd_init(void)
{
    struct atcmd_settings setting;
    os_memset(&setting, 0, sizeof(setting));
    setting.args_count = ATCMD_ARGS_COUNT;
    setting.printbuf_size = ATCMD_PRINT_BUF_SIZE;
    setting.static_atcmds = static_atcmds;
    setting.static_cmdcnt = ARRAY_SIZE(static_atcmds);
    atcmd_uart_init(ATCMD_UARTDEV, 115200, 5, &setting);
}

