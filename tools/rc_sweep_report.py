# -*- coding: utf-8 -*-
"""Сводка перебора ручек выбора модуляции (VAR_SWEEP var0930rc) по логу камеры.

    python tools/rc_sweep_report.py rcsweep          # все cam_air_*rcsweep*.txt
    python tools/rc_sweep_report.py путь/к/логу.txt   # один лог

Лог делится на включения по строке «Стартовое окно (». Для каждого включения:
вариант и ответ модуля на его команды, что реально стоит после (чтение
TX_MCS_MIN / TX_RATE_FIXED / TX_CNT_MAX), строки «ОПЫТ ИТОГ» этапов,
распределение mcs= из строк tx0 по этапам (это MCS ПОСЛЕДНЕЙ попытки, не выбор
автоподбора) и строки отчёта модуля, которых раньше в логе не было, — среди них
таблица AT+LMAC_DBGSEL=2, формат которой заранее не известен.
"""
import glob, os, re, sys
from collections import Counter, OrderedDict

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
KNOWN = ('LMAC STATUS', 'local:', 'per=', 'dbg:', 'STA0:', 'tx0:', 'UARTSTAT', 'PWRCTL',
         # отчёт модуля целиком (LMAC_DBG_EVERY) и таблица AT+LMAC_DBGSEL=2, формат снят 30.09:
         # «dbg0: tp1=13 tp2=12 pbtk= 21» (лучшая/вторая, индекс = 8 + MCS), «[t]tp2= 9 rate= R
         # prr= P» (смена; rate = скорость PHY · P / 256), «[t]grp= 10: tx_cnt= 3 rate= 7800 prr= 4»
         'tp1=', 'tp2=', 'grp', 'qs', 'freq=', 'chn:', 'bgr:', 'iq=', 'buf:', 'ac=', 'irq:', 'tx :',
         'rx :', 'cts_bm', 'cca:', ' ed', 'chip-temperature', 'bw=', 'rx0:', 'agc=', '-----')

arg = sys.argv[1] if len(sys.argv) > 1 else 'rcsweep'
files = [arg] if os.path.isfile(arg) else sorted(glob.glob(os.path.join(LOG, 'cam_air_*%s*.txt' % arg)))
if not files:
    sys.exit('нет логов по «%s»' % arg)

ITOG = re.compile(r'ОПЫТ ИТОГ \| (?P<name>[^|]+?) \| (?P<s>\d+) с \| кадров отпр (?P<sent>\d+), подтв (?P<ack>\d+), '
                  r'неполных (?P<inc>\d+), списано (?P<to>\d+) .*?подача (?P<fed>\d+) кбит/с, кадр (?P<fr>\d+) Б \| '
                  r'эфир (?P<air>\d+) кбит/с.*?PER модуля (?P<per>\d+) %, MCS (?P<mcs>[\d.]+) \((?P<n>\d+) замеров\) \| '
                  r'RTT (?P<rtt>\d+) мс \| мощность (?P<pwr>-?\d+) дБм.*?окно закрыто (?P<blk>\d+) %, качество ср (?P<q>\d+)')


def boots(path):
    """Включения питания: список строк лога от «Стартовое окно (» до следующего."""
    cur = []
    for line in open(path, encoding='utf-8', errors='replace'):
        line = line.rstrip('\n')
        if line.startswith('Стартовое окно (') and cur:
            yield cur
            cur = []
        cur.append(line)
    if cur:
        yield cur


def answer(lines, i):
    """Ответ модуля на команду окна: хвост той же строки или следующие строки."""
    head = lines[i].split('->', 1)[1].strip()
    if head:
        return head
    out = []
    for l in lines[i + 1:i + 4]:
        if '->' in l or l.startswith(('ВАРИАНТ', 'КАНАЛ', 'Стартовое')):
            break
        out.append(l.strip())
    return ' / '.join(x for x in out if x) or '(пусто)'


rows = []
for path in files:
    for b in boots(path):
        var = next((l for l in b if l.startswith('ВАРИАНТ:')), None)
        if not var:
            continue
        info = OrderedDict(var=var.split(',', 1)[1].strip(), log=os.path.basename(path))
        win = next((l for l in b if l.startswith('Стартовое окно открыто') or 'НЕ ОТКРЫЛОСЬ' in l), '')
        m = re.search(r'(\d+) ответов с OK', win)
        info['ok'] = int(m.group(1)) if m else 0
        cmds, reads = [], []
        for i, l in enumerate(b):
            s = l.strip()
            if '->' not in s or not s.startswith('AT+'):
                continue
            cmd = s.split('->', 1)[0].strip()
            if re.match(r'AT\+(RC_NEW|LMAC_DBGSEL|TX_RATE_FIXED|TX_MCS_MIN|P2PDEST)=[0-9f]|AT\+MCAST_MCS=[1-9]', cmd):
                cmds.append('%s → %s' % (cmd, answer(b, i)))
            elif cmd in ('AT+TX_MCS_MIN=?', 'AT+TX_RATE_FIXED=?', 'AT+TX_CNT_MAX=?'):
                reads.append(answer(b, i))
        info['cmds'], info['reads'] = cmds, reads
        # этапы: mcs= из tx0 и лучшая MCS (tp1 в строке dbg0 таблицы LMAC_DBGSEL=2,
        # индекс = 8 + MCS на 2 МГц) между «ОПЫТ: этап» и «ОПЫТ ИТОГ»; новые строки модуля
        stage, stages, mcs, best, novel = None, [], Counter(), Counter(), Counter()
        tp, ck = {}, {}
        info['reinit'] = sum(1 for l in b if l.startswith('КАМЕРА: ') and 'перезапуск драйвера' in l)
        for l in b:
            if l.startswith('ОПЫТ: этап'):
                stage, mcs, best = l.split('—', 1)[1].rsplit(',', 1)[0].strip(), Counter(), Counter()
            m = ITOG.search(l)
            if m:
                d = m.groupdict()
                d['mcs_last'] = dict(sorted(mcs.items()))
                d['best'] = dict(sorted(best.items()))
                stages.append(d)
                stage = None
            m = re.search(r'dbg0: tp1=(\d+)', l)
            if m and stage:
                best[int(m.group(1)) - 8] += 1
            m = re.search(r'ОПЫТ ТАБЛИЦА \| (.+?) \| смен лучшей за этап (\d+)', l)
            if m:
                tp[m.group(1).strip()] = int(m.group(2))
            # 05.10, опыт «камера — точка доступа»: куски по списку в квитанции
            m = re.search(r'ОПЫТ КУСКИ \| (.+?) \| (.+)$', l)
            if m:
                ck[m.group(1).strip()] = m.group(2).strip()
            if 'МОДУЛЬ:' in l:
                t = l.split('МОДУЛЬ:', 1)[1].strip()
                m = re.search(r'tx0: mcs=\*?(\d+)', t)
                if m and stage:
                    mcs[int(m.group(1))] += 1
                if t and not any(k in t for k in KNOWN):
                    novel[re.sub(r'\d+', '#', t)[:90]] += 1
        info['stages'], info['tp'], info['ck'], info['novel'] = stages, tp, ck, novel
        rows.append(info)

for r in rows:
    if r['ok'] < 3:
        # перезапуск одного ESP32 (заливка) без снятия питания: модуль не спрашивали,
        # настройки варианта не применены, шаг не засчитан — в сравнение не идёт
        print('-' * 100 + '\n%s   [%s] — окно не открылось, не в счёт' % (r['var'], r['log']))
        continue
    print('=' * 100)
    print('%s   [%s, окно: %d OK%s]' % (r['var'], r['log'], r['ok'],
                                        ', ПЕРЕЗАПУСКОВ КАМЕРЫ %d' % r['reinit'] if r['reinit'] else ''))
    for c in r['cmds']:
        print('  команда: ' + c)
    for c in r['reads']:
        print('  стоит:   ' + c)
    for d in r['stages']:
        s = int(d['s']) or 1
        good = int(d['ack']) * int(d['fr']) * 8 / s / 1000
        print('  %-20s %3s с | подтв %4s (%.1f к/с) полезно %4.0f кбит/с, подача %4s, эфир %4s | PER %s %%, '
              'RTT %4s мс, списано %3s, неполных %3s, окно закрыто %2s %%, Q %s, кадр %s Б, %s дБм'
              % (d['name'], d['s'], d['ack'], int(d['ack']) / s, good, d['fed'], d['air'], d['per'],
                 d['rtt'], d['to'], d['inc'], d['blk'], d['q'], d['fr'], d['pwr']))
        tot = sum(d['mcs_last'].values()) or 1
        print('  %-20s mcs= последней попытки: %s   смен лучшей: %s'
              % ('', ' '.join('%d:%d%%' % (k, round(100 * v / tot)) for k, v in d['mcs_last'].items()),
                 r['tp'].get(d['name'].strip(), '—')))
        if d['name'].strip() in r['ck']:
            print('  %-20s КУСКИ: %s' % ('', r['ck'][d['name'].strip()]))
        if d['best']:
            tb = sum(d['best'].values())
            print('  %-20s ЛУЧШАЯ MCS (выбор модуля): %s'
                  % ('', ' '.join('%d:%d%%' % (k, round(100 * v / tb)) for k, v in d['best'].items())))
    if r['novel']:
        print('  новые строки модуля (цифры → #), первые 25 по частоте:')
        for t, n in r['novel'].most_common(25):
            print('    %4d  %s' % (n, t))
