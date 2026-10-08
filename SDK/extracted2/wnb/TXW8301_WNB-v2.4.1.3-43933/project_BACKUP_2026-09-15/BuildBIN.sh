#!/bin/bash

if [ -e tmp ]; then
files=$(ls tmp)
for f in $files
do
	ff=$(cat tmp/$f)
	mv -f $ff.bak $ff
done
rm -rf tmp
fi

cp  ./Obj/txw4002a.elf project.elf
cp  ./Lst/txw4002a.map project.map
cp  ./Obj/txw4002a.ihex project.hex

cp ../../../../tools/makecode/BinScript.exe BinScript.exe
cp ../../../../tools/makecode/crc.exe crc.exe
cp ../../../../tools/makecode/makecode.exe makecode.exe

BinScript.exe BinScript.BinScript
makecode.exe
#crc.exe crc.ini
#BinScript.exe BinScript_Bin2Hex.BinScript

