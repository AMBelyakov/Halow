# Model of Taixin LMAC rate control (mars_lmac_rc.o, v2.4.1.3), 2 MHz channel.
# Reconstructed from disassembly: ah_get_rate / ah_tx_status / prob_rate_update.
import random, sys
from collections import Counter

RATE = [300,600,900,1200,1800,2400,2700,3000, 650,1300,1950,2600,3900,5200,5850,6500,
        1350,2700,4050,5400,8100,10800,12150,13500, 2925,5850,8775,11700,17550,23400,26325,29250]
PROB_TBL = bytes.fromhex("1b1a1f03040c090d0705150b1018010f1c021319120e17161d081100140a1e06")
QS_TBL = [10,12,14,18,20,22,26,28,30]
def tb(h): return bytes.fromhex(h)
RC_NEW = [None,
  tb("0010203001112131011121310212223203132333041424340515253506162636"),
  tb("0010102000111121011112220111132302121424031315250414162605151727"),
  tb("0a10102000111111001111120111121301111314021214150313151604141617"),
  tb("0a1010100a111111001111110011111201111213011113140212141503131516"),
  tb("0a1010100a1111110a1111110a1111110a1111110a1111110a1111110a111111")]
MAXBW = 1          # 2 MHz only
def invalid(i): bw = (i >> 3) & 3; return bw > MAXBW or bw == 0
def mcs(i): return i & 7

class RC:
    def __init__(s, version=3, fixed=False, cnt_max=7):
        s.version, s.fixed, s.cnt_max = version, fixed, cnt_max
        s.seq = 0; s.reset()
    def reset(s):
        s.prob = [0]*32; s.cnt = [0]*32
        s.qs = 0; s.state = 0; s.ctr = 0
        s.best = s.second = 8; s.best_cnt = s.second_cnt = 0; s.probe = 8
    def probe_update(s, thr):
        for _ in range(32):
            r = PROB_TBL[s.seq & 31]; s.seq = (s.seq + 1) & 0xff
            if invalid(r) or r == s.best or r == s.second: continue
            if RATE[r] >= thr: s.probe = r; return
        s.probe = s.best
    def get_rate(s, retry):
        if s.qs < 9:
            while s.qs < 9 and invalid(QS_TBL[s.qs]): s.qs += 1
            if s.qs < 9: s.state = 'qs'; return QS_TBL[s.qs]
            return s.best            # real code returns -1 here once (quirk)
        if s.ctr >= 20:
            s.probe_update(RATE[s.best] if retry == 0 else 0)
            s.state = 'probe'; return s.probe
        if retry >= 3: s.ctr += 2
        b = s.best
        if s.version == 1:
            r = b
            if s.cnt_max >= 4:
                if retry >= s.cnt_max - 1: r = 9
                elif retry >= s.cnt_max - 3: r = s.second
        elif s.version == 3:
            if retry == 0: r = b
            else:
                t = RC_NEW[min(retry, 5)][mcs(b) * 4 + ((b >> 3) & 3)]
                r = ((t >> 4) & 3) * 8 + (t & 7)
        if s.fixed: r = b
        return r
    def tx_status(s, r, ok):
        s.cnt[r] = (s.cnt[r] + 1) & 0xff
        p = 25600 if ok else 0
        st, s.state = s.state, 0
        if st == 'qs':
            n = s.cnt[r]
            s.prob[r] = p if n < 2 else (p + s.prob[r] * (n - 1)) // n
            s.qs += 1
        else:
            if st == 'probe':
                s.seq = (s.seq + 1) & 31
                if s.ctr >= 20: s.ctr = 0
            s.prob[r] = (p * 6 + s.prob[r] * 122) >> 7
        if r == s.best: s.best_cnt = (s.best_cnt + 1) & 0xff
        if r == s.second: s.second_cnt = (s.second_cnt + 1) & 0xff
        if s.qs >= 9 and r == s.best and s.best_cnt >= 31 and s.prob[s.best] < 5120:
            s.reset(); s.resets = getattr(s, 'resets', 0) + 1
        else:
            for which in ('best', 'second'):
                mx, bi = 0, 0
                for i in range(32):
                    if which == 'second' and i == s.best: continue
                    if s.cnt[i] and s.prob[i] and RATE[i] * s.prob[i] > mx: mx, bi = RATE[i] * s.prob[i], i
                if mx and bi != getattr(s, which):
                    setattr(s, which, bi); setattr(s, which + '_cnt', 0)
        s.ctr += 1

def run(psucc, frames=60000, attempts=8, bits=11200, ovh_ms=1.0, seed=1, **kw):
    random.seed(seed); rc = RC(**kw)
    best_t, att_mcs = Counter(), Counter(); air = 0.0; deliv = 0
    for f in range(frames):
        for k in range(attempts):
            r = rc.get_rate(k)
            air += ovh_ms + bits / RATE[r]
            att_mcs[mcs(r)] += 1
            ok = random.random() < psucc(mcs(r))
            rc.tx_status(r, ok)
            if ok: deliv += 1; break
        if f > frames // 5: best_t[mcs(rc.best)] += 1
    n = sum(best_t.values()); na = sum(att_mcs.values())
    return dict(best={m: round(100 * c / n) for m, c in sorted(best_t.items()) if c * 100 >= n},
                att={m: round(100 * c / na) for m, c in sorted(att_mcs.items()) if c * 100 >= na},
                kbps=round(deliv * bits / air), deliv=round(100 * deliv / frames),
                resets=getattr(rc, 'resets', 0))

scen = {
  'flat70 (PER 70% any MCS)': lambda m: 0.30,
  'flat85 (PER 85%, close range)': lambda m: 0.15,
  'snr-ish (MCS7 worse)': lambda m: [0.35,0.35,0.34,0.33,0.32,0.30,0.25,0.18][m],
}
pol = {'default v3 chain': dict(version=3), 'TX_RATE_FIXED=1': dict(version=3, fixed=True),
       'RC_NEW=1': dict(version=1)}
for sn, ps in scen.items():
    print('==', sn)
    for pn, kw in pol.items():
        res = [run(ps, seed=s, **kw) for s in (1, 2, 3)]
        print(f'  {pn:18s} kbps={[r["kbps"] for r in res]} deliv%={res[0]["deliv"]} '
              f'resets={[r["resets"] for r in res]}\n     best MCS %: {res[0]["best"]}\n     attempts MCS %: {res[0]["att"]}')
