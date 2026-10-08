# -*- coding: utf-8 -*-
"""Таймер тишины uart_p2p в utils_uart_p2p.o: 250 << 3 = 2000 мкс -> IMM << 3.

    python silpatch.py utils_uart_p2p.o 50     # 50 << 3 = 400 мкс

Модуль режет поток UART на эфирные кадры по тишине: каждый принятый байт
перезапускает таймер, по истечении накопленное уходит в эфир. В
uart_p2p_irq_hdl (дизассемблер, 29.09):

    5e: 31fa   movi r1, 250
    64: 4123   lsli r1, r1, 3        ; 2000 мкс -> timer_device_start

Меняется один непосредственный операнд 16-битной movi (0x3100 | imm8).
"""
import struct, sys, io

path, imm = sys.argv[1], int(sys.argv[2])
assert 1 <= imm <= 255, 'imm8'

d = bytearray(io.open(path, 'rb').read())
assert d[:4] == b'\x7fELF' and d[4] == 1 and d[5] == 1, 'не ELF32 LE'
e_shoff, = struct.unpack_from('<I', d, 0x20)
e_shentsize, e_shnum, e_shstrndx = struct.unpack_from('<HHH', d, 0x2E)

def sh(i):
    o = e_shoff + i * e_shentsize
    name, typ, flags, addr, off, size = struct.unpack_from('<6I', d, o)
    return dict(name=name, off=off, size=size)

stroff = sh(e_shstrndx)['off']
def nm(x):
    e = d.index(b'\0', stroff + x)
    return d[stroff + x:e].decode()

secs = {nm(sh(i)['name']): sh(i) for i in range(e_shnum)}
irq = secs['.text.uart_p2p_irq_hdl']
o_movi, o_lsli = irq['off'] + 0x5e, irq['off'] + 0x64
movi = struct.unpack_from('<H', d, o_movi)[0]
lsli = struct.unpack_from('<H', d, o_lsli)[0]
assert lsli == 0x4123, 'ожидал lsli r1,r1,3 (0x4123), нашёл 0x%04x' % lsli
assert movi & 0xff00 == 0x3100, 'ожидал movi r1,imm (0x31xx), нашёл 0x%04x' % movi
old = movi & 0xff
new = 0x3100 | imm
struct.pack_into('<H', d, o_movi, new)
io.open(path, 'wb').write(bytes(d))
print('movi r1: %d -> %d  (0x%04x -> 0x%04x), таймер %d -> %d мкс'
      % (old, imm, movi, new, old << 3, imm << 3))
